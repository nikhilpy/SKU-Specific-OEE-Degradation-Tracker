from predictive import predict


RUL_THRESHOLD_HOURS = 24


def diagnose(prediction):
    rul = prediction["rul_hours"]

    result = {}

    if rul <= RUL_THRESHOLD_HOURS:
        result = {
            "failure_flag": True,
            "equipment_id": prediction["equipment_id"],
            "rul_hours": rul,
            "predicted_failure_time": prediction["predicted_failure_time"],
            "reason": (
                f"Predicted RUL ({rul} hours) is below "
                f"the {RUL_THRESHOLD_HOURS}-hour threshold."
            ),
            "next_agent": "investigative_agent"
        }
    else:
        result = {
            "failure_flag": False,
            "equipment_id": prediction["equipment_id"],
            "rul_hours": rul,
            "predicted_failure_time": prediction["predicted_failure_time"],
            "reason": "Equipment is currently above the failure threshold.",
            "next_agent": None
        }

    print("\n===== DIAGNOSTIC AGENT =====")

    for key, value in result.items():
        print(f"{key}: {value}")

    return result

if __name__ == "__main__":
    diagnose({
        "equipment_id": "LINE-2-PACKAGING",
        "current_temperature": 84.1,
        "current_vibration": 7.0,
        "temperature_rate_per_hour": 2.3167,
        "vibration_rate_per_hour": 0.3667,
        "temperature_rul_hours": 0.39,
        "vibration_rul_hours": 1.36,
        "rul_hours": 0.39,
        "limiting_parameter": "temperature",
        "predicted_failure_time": "1900-01-01 16:23:18.561151079",
        "failure_threshold_hours": 24,
        "threshold_exceeded": True,
    })