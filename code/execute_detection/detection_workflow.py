import json
import os
import sys

from investigative_agent import investigate
from prediction import predict
from retrieve import get_connection, retrieve_documents
from future_prediction import future_prediction

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

    if not prediction["failure_flag"]:
        return prediction

    query = (
        f"OEM operating limits for "
        f"{prediction['equipment_id']}, "
        f"temperature and vibration"
    )

    investigation_result = investigate(
        prediction,
        oem_evidence=search_oem_manual(query)
    )

    final_prediction = future_prediction(investigation_result)
    print("Final", end="\n")
    print(json.dumps(final_prediction, indent=4))
    return final_prediction

if __name__ == "__main__":
    run_workflow()
