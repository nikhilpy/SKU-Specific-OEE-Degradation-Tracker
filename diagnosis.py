import predictive


RUL_THRESHOLD_HOURS = 24


def diagnose(prediction):
    rul = prediction["rul_hours"]

    if rul <= RUL_THRESHOLD_HOURS:
        return {
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

    return {
        "failure_flag": False,
        "equipment_id": prediction["equipment_id"],
        "rul_hours": rul,
        "predicted_failure_time": prediction["predicted_failure_time"],
        "reason": "Equipment is currently above the failure threshold.",
        "next_agent": None
    }


if __name__ == "__main__":

    prediction = predictive.result

    diagnosis = diagnose(prediction)

    print("\n===== DIAGNOSTIC AGENT =====")

    for key, value in diagnosis.items():
        print(f"{key}: {value}")