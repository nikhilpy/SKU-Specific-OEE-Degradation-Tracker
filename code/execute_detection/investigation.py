import json


def create_investigation(
    equipment_id,
    sku,
    rul_hours,
    predicted_failure_time,
    current_temperature,
    current_vibration,
    oem_evidence,
):
    """
    Assembles the final investigation JSON payload.
    All values are passed in from the upstream agents — nothing is hardcoded here.
    oem_evidence is the live result from Cortex Search (or the fallback stub if
    the search service is unavailable).
    """
    investigation = {
        "equipment_id": equipment_id,
        "sku": sku,
        "failure_flag": True,
        "rul_hours": rul_hours,
        "predicted_failure_time": predicted_failure_time,
        "current_conditions": {
            "temperature": current_temperature,
            "vibration": current_vibration,
        },
        "oem_evidence": oem_evidence,
    }

    return investigation


if __name__ == "__main__":
    # Demo run using realistic values — not used in the live workflow
    investigation = create_investigation(
        equipment_id="LINE-2-PACKAGING",
        sku="<fetched from Snowflake at runtime>",
        rul_hours=5.2,
        predicted_failure_time="2026-09-27 21:12",
        current_temperature=84.1,
        current_vibration=7.0,
        oem_evidence={
            "source": "Cortex Search — OEM_MANUAL_SEARCH",
            "evidence": [
                {"parameter": "temperature", "limit": 85.0, "unit": "°C"},
                {"parameter": "vibration",   "limit": 7.5,  "unit": "mm/s"},
            ],
        },
    )

    print("\n===== INVESTIGATION JSON =====")
    print(json.dumps(investigation, indent=4))

    with open("investigation.json", "w") as f:
        json.dump(investigation, f, indent=4)
