import json
import os
import sys

from diagnosis import diagnose
from execution import execute
from investigation import create_investigation
from investigative_agent import investigate
from predictive import predict

CODE_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

RAG_DIR = os.path.join(CODE_ROOT, "create_rag")


def search_oem_manual(query):
    """
    Query the Cortex Search service in create_rag/retrieve.py.

    Returns None when Snowflake is unreachable so the pipeline can
    fall back to the stubbed OEM limits in investigative_agent.py.
    """
    if RAG_DIR not in sys.path:
        sys.path.insert(0, RAG_DIR)

    conn = None

    try:
        from retrieve import get_connection, retrieve_documents

        conn = get_connection()

        return retrieve_documents(conn, query)

    except Exception as e:
        print(f"\nOEM retrieval unavailable: {e}")
        return None

    finally:
        if conn:
            conn.close()


def run_workflow():
    print("===== PREDICTIVE AGENT =====")

    prediction = predict()

    print(json.dumps(prediction, indent=4))

    diagnosis_result = diagnose(prediction)

    if not diagnosis_result["failure_flag"]:
        return diagnosis_result

    query = (
        f"OEM operating limits for "
        f"{diagnosis_result['equipment_id']}, "
        f"temperature and vibration"
    )

    investigation_result = investigate(
        diagnosis_result,
        oem_evidence=search_oem_manual(query)
    )

    execution_result = execute(investigation_result)

    create_investigation(
        equipment_id=investigation_result["equipment_id"],
        sku=investigation_result["sku"],
        rul_hours=investigation_result["rul_hours"],
        predicted_failure_time=investigation_result[
            "predicted_failure_time"
        ],
        current_temperature=prediction["current_temperature"],
        current_vibration=prediction["current_vibration"],
        oem_evidence=investigation_result["oem_evidence"]
    )

    return execution_result


if __name__ == "__main__":
    run_workflow()
