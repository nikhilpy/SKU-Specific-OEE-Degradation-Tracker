import json


def get_active_sku(equipment_id):
    """
    Replace this with your Snowflake Semantic Model query.
    For testing, we return the SKU from your synthetic scenario.
    """
    return "SKU-899"


def search_oem_manual(query):
    """
    Replace this with your existing Cortex Search function.
    """
    # Example result from Cortex Search
    return {
        "source": "LINE-2-PACKAGING OEM Maintenance Manual",
        "evidence": [
            {
                "parameter": "temperature",
                "limit": 85.0,
                "unit": "°C"
            },
            {
                "parameter": "vibration",
                "limit": 7.5,
                "unit": "mm/s"
            }
        ]
    }


def investigate(diagnosis, oem_evidence=None):

    if not diagnosis["failure_flag"]:
        return {
            "status": "NO_INVESTIGATION_REQUIRED"
        }

    equipment_id = diagnosis["equipment_id"]

    # 1. Get active SKU
    sku = get_active_sku(equipment_id)

    # 2. Query OEM manual through Cortex Search
    if oem_evidence is None:
        query = (
            f"OEM operating limits for {equipment_id}, "
            f"temperature and vibration"
        )

        oem_evidence = search_oem_manual(query)

    # 3. Create investigation payload
    investigation = {
        "equipment_id": equipment_id,
        "sku": sku,
        "failure_flag": True,
        "rul_hours": diagnosis["rul_hours"],
        "predicted_failure_time": diagnosis[
            "predicted_failure_time"
        ],
        "oem_evidence": oem_evidence
    }

    print("\n===== INVESTIGATIVE AGENT =====")
    print(json.dumps(investigation, indent=4))

    return investigation

if __name__ == "__main__":
    print(investigate({"failure_flag": True,
        "equipment_id": "LINE-2-PACKAGING",
        "rul_hours": 0.39,
        "predicted_failure_time": "1900-01-01 16:23:18.561151079",
        "reason": "Predicted RUL (0.39 hours) is below the 24-hour threshold",
        "next_agent": "investigative_agent"}))