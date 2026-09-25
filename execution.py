import json


def execute(investigation):

    if not investigation.get("failure_flag"):
        return {
            "status": "NO_ACTION",
            "message": "No failure detected."
        }

    rul = investigation["rul_hours"]

    if rul <= 6:
        priority = "CRITICAL"
        action = "IMMEDIATE_MAINTENANCE"
    elif rul <= 24:
        priority = "HIGH"
        action = "SCHEDULE_MAINTENANCE"
    else:
        priority = "MEDIUM"
        action = "MONITOR_EQUIPMENT"

    execution_result = {
        "status": "ACTION_REQUIRED",
        "equipment_id": investigation["equipment_id"],
        "sku": investigation["sku"],
        "action": action,
        "priority": priority,
        "rul_hours": rul,
        "predicted_failure_time": investigation[
            "predicted_failure_time"
        ],
        "reason": "Predicted degradation threshold exceeded.",
        "oem_evidence": investigation["oem_evidence"]
    }

    return execution_result


if __name__ == "__main__":

    with open("investigation.json", "r") as f:
        investigation = json.load(f)

    result = execute(investigation)

    print("\n===== EXECUTION AGENT =====")
    print(json.dumps(result, indent=4))