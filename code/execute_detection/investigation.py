import json


def create_investigation(
    equipment_id,
    sku,
    rul_hours,
    predicted_failure_time,
    current_temperature,
    current_vibration,
    oem_evidence
):
    investigation = {
        "equipment_id": equipment_id,
        "sku": sku,
        "failure_flag": True,
        "rul_hours": rul_hours,
        "predicted_failure_time": predicted_failure_time,
        "current_conditions": {
            "temperature": current_temperature,
            "vibration": current_vibration
        },
        "oem_evidence": oem_evidence
    }

    return investigation


if __name__ == "__main__":

    oem_evidence = {
        "temperature_limit": 85.0,
        "vibration_limit": 7.5,
        "source": "LINE-2-PACKAGING OEM Maintenance Manual"
    }

    investigation = create_investigation(
        equipment_id="LINE-2-PACKAGING",
        sku="SKU-899",
        rul_hours=5.2,
        predicted_failure_time="2026-09-25 21:12",
        current_temperature=84.1,
        current_vibration=7.0,
        oem_evidence=oem_evidence
    )

    print("\n===== INVESTIGATION JSON =====")
    print(json.dumps(investigation, indent=4))

    with open("investigation.json", "w") as f:
        json.dump(investigation, f, indent=4)