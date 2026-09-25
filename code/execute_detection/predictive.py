import pandas as pd
from datetime import datetime, timedelta

# -----------------------------
# Configuration
# -----------------------------

def predict():
    CSV_FILE = "device_data.csv"

    TEMPERATURE_LIMIT = 85.0
    VIBRATION_LIMIT = 7.5

    FAILURE_THRESHOLD_HOURS = 24


    # -----------------------------
    # Load device telemetry
    # -----------------------------
    df = pd.read_csv(CSV_FILE)

    df["Timestamp"] = pd.to_datetime(df["Timestamp"], format="%H:%M")

    df = df.sort_values("Timestamp").reset_index(drop=True)


    # -----------------------------
    # Calculate degradation rates
    # -----------------------------
    time_hours = (
        df["Timestamp"] - df["Timestamp"].iloc[0]
    ).dt.total_seconds() / 3600

    temperature_rate = (
        df["Temperature"].iloc[-1] - df["Temperature"].iloc[0]
    ) / time_hours.iloc[-1]

    vibration_rate = (
        df["Vibration"].iloc[-1] - df["Vibration"].iloc[0]
    ) / time_hours.iloc[-1]


    # -----------------------------
    # Current device state
    # -----------------------------
    current_temperature = df["Temperature"].iloc[-1]
    current_vibration = df["Vibration"].iloc[-1]

    equipment = df["Equipment"].iloc[-1]


    # -----------------------------
    # Calculate RUL
    # -----------------------------
    if temperature_rate > 0:
        temperature_rul = (
            TEMPERATURE_LIMIT - current_temperature
        ) / temperature_rate
    else:
        temperature_rul = float("inf")


    if vibration_rate > 0:
        vibration_rul = (
            VIBRATION_LIMIT - current_vibration
        ) / vibration_rate
    else:
        vibration_rul = float("inf")


    # Earliest predicted failure
    rul_hours = min(
        temperature_rul,
        vibration_rul
    )


    # -----------------------------
    # Determine failure reason
    # -----------------------------
    if temperature_rul < vibration_rul:
        limiting_parameter = "temperature"
    else:
        limiting_parameter = "vibration"


    # -----------------------------
    # Predict failure date
    # -----------------------------
    latest_timestamp = df["Timestamp"].iloc[-1]

    predicted_failure_time = (
        latest_timestamp +
        pd.Timedelta(hours=rul_hours)
    )


    # -----------------------------
    # Failure threshold
    # -----------------------------
    threshold_exceeded = (
        rul_hours <= FAILURE_THRESHOLD_HOURS
    )


    # -----------------------------
    # Output
    # -----------------------------
    result = {
        "equipment_id": equipment,
        "current_temperature": round(current_temperature, 2),
        "current_vibration": round(current_vibration, 2),

        "temperature_rate_per_hour": round(
            temperature_rate, 4
        ),

        "vibration_rate_per_hour": round(
            vibration_rate, 4
        ),

        "temperature_rul_hours": round(
            temperature_rul, 2
        ),

        "vibration_rul_hours": round(
            vibration_rul, 2
        ),

        "rul_hours": round(rul_hours, 2),

        "limiting_parameter": limiting_parameter,

        "predicted_failure_time": str(
            predicted_failure_time
        ),

        "failure_threshold_hours":
            FAILURE_THRESHOLD_HOURS,

        "threshold_exceeded":
            threshold_exceeded
    }


    return result