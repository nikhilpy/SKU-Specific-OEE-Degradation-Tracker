import os
import json
import snowflake.connector
from dotenv import load_dotenv

# Load env from project root .env
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))


def _get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "OEE_COMMAND_CENTER"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", "FACTORY_FLOOR"),
    )


def get_active_sku(equipment_id: str) -> str:
    """
    Queries the IT_OT_CONVERGED dynamic table to find the most recent
    SKU running on the given equipment.  Falls back to 'UNKNOWN' if
    no match is found or the table is unreachable.
    """
    conn = None
    try:
        conn = _get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT SKU_ID
            FROM IT_OT_CONVERGED
            WHERE EQUIPMENT_ID = %s
              AND SKU_ID != 'NONE'
            ORDER BY TIMESTAMP DESC
            LIMIT 1
            """,
            (equipment_id,),
        )
        row = cursor.fetchone()
        cursor.close()
        return row[0] if row else "UNKNOWN"
    except Exception as e:
        print(f"\n[investigative_agent] Could not fetch active SKU from Snowflake: {e}")
        return "UNKNOWN"
    finally:
        if conn:
            conn.close()


def search_oem_manual(query: str) -> dict:
    """
    Last-resort fallback when the Cortex Search service is unavailable.
    Returns a structured stub sourced from the known OEM manual values.
    This should only be called when the upstream retrieve.py fails.
    """
    return {
        "source": "LINE-2-PACKAGING OEM Maintenance Manual (fallback stub)",
        "evidence": [
            {"parameter": "temperature", "limit": 85.0, "unit": "°C"},
            {"parameter": "vibration",   "limit": 7.5,  "unit": "mm/s"},
        ],
    }


def investigate(diagnosis: dict, oem_evidence=None) -> dict:
    if not diagnosis["failure_flag"]:
        return {"status": "NO_INVESTIGATION_REQUIRED"}

    equipment_id = diagnosis["equipment_id"]

    # 1. Get active SKU — live query from Snowflake
    sku = get_active_sku(equipment_id)

    # 2. Use OEM evidence from Cortex Search (passed in); fall back only if None
    if oem_evidence is None:
        query = (
            f"OEM operating limits for {equipment_id}, "
            f"temperature and vibration"
        )
        oem_evidence = search_oem_manual(query)

    # 3. Assemble investigation payload
    investigation = {
        "equipment_id": equipment_id,
        "sku": sku,
        "failure_flag": True,
        "rul_hours": diagnosis["rul_hours"],
        "predicted_failure_time": diagnosis["predicted_failure_time"],
        "oem_evidence": oem_evidence,
    }

    print("\n===== INVESTIGATIVE AGENT =====")
    print(json.dumps(investigation, indent=4))

    return investigation


if __name__ == "__main__":
    print(investigate({
        "failure_flag": True,
        "equipment_id": "LINE-2-PACKAGING",
        "rul_hours": 0.39,
        "predicted_failure_time": "2026-09-27 16:23:00",
        "reason": "Predicted RUL (0.39 hours) is below the 24-hour threshold",
        "next_agent": "investigative_agent",
    }))