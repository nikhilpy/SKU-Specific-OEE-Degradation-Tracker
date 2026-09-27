import os
import json
import snowflake.connector
import pandas as pd
from datetime import datetime
from dotenv import load_dotenv

# Load env from project root .env
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, "..", ".."))
load_dotenv(os.path.join(_PROJECT_ROOT, ".env"))

# OEM thermal/vibration limits (used if Cortex Search is unavailable)
TEMPERATURE_LIMIT = 85.0
VIBRATION_LIMIT = 7.5
FAILURE_THRESHOLD_HOURS = 24


def _get_connection():
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
        database=os.getenv("SNOWFLAKE_DATABASE", "OEE_COMMAND_CENTER"),
        schema=os.getenv("SNOWFLAKE_SCHEMA", "FACTORY_FLOOR"),
    )


def predict():
    """
    Fetches the most recent telemetry records for every equipment from
    RAW_OT_TELEMETRY in Snowflake, computes degradation rates and RUL,
    and returns the result for the equipment closest to failure.
    """
    conn = _get_connection()

    try:
        cursor = conn.cursor()

        # Pull the latest N readings per equipment to compute trend
        cursor.execute("""
            SELECT EQUIPMENT_ID, TIMESTAMP, TEMPERATURE_C, VIBRATION_RMS
            FROM RAW_OT_TELEMETRY
            WHERE EQUIPMENT_ID IS NOT NULL
            ORDER BY EQUIPMENT_ID, TIMESTAMP DESC
            LIMIT 500
        """)
        rows = cursor.fetchall()
        cols = [d[0] for d in cursor.description]
        df = pd.DataFrame(rows, columns=cols)
    finally:
        cursor.close()
        conn.close()

    if df.empty:
        raise RuntimeError("No telemetry data found in RAW_OT_TELEMETRY.")

    # Convert timestamp column
    df["TIMESTAMP"] = pd.to_datetime(df["TIMESTAMP"])

    best_result = None

    for equipment_id, group in df.groupby("EQUIPMENT_ID"):
        group = group.sort_values("TIMESTAMP").reset_index(drop=True)

        if len(group) < 2:
            continue

        time_hours = (
            group["TIMESTAMP"] - group["TIMESTAMP"].iloc[0]
        ).dt.total_seconds() / 3600

        elapsed = time_hours.iloc[-1]
        if elapsed == 0:
            continue

        temp_rate = (
            group["TEMPERATURE_C"].iloc[-1] - group["TEMPERATURE_C"].iloc[0]
        ) / elapsed

        vib_rate = (
            group["VIBRATION_RMS"].iloc[-1] - group["VIBRATION_RMS"].iloc[0]
        ) / elapsed

        current_temp = group["TEMPERATURE_C"].iloc[-1]
        current_vib = group["VIBRATION_RMS"].iloc[-1]

        temperature_rul = (
            (TEMPERATURE_LIMIT - current_temp) / temp_rate
            if temp_rate > 0
            else float("inf")
        )

        vibration_rul = (
            (VIBRATION_LIMIT - current_vib) / vib_rate
            if vib_rate > 0
            else float("inf")
        )

        rul_hours = min(temperature_rul, vibration_rul)
        limiting_parameter = "temperature" if temperature_rul < vibration_rul else "vibration"

        latest_timestamp = group["TIMESTAMP"].iloc[-1]
        predicted_failure_time = str(
            latest_timestamp + pd.Timedelta(hours=rul_hours)
        )

        result = {
            "equipment_id": equipment_id,
            "current_temperature": round(float(current_temp), 2),
            "current_vibration": round(float(current_vib), 2),
            "temperature_rate_per_hour": round(float(temp_rate), 4),
            "vibration_rate_per_hour": round(float(vib_rate), 4),
            "temperature_rul_hours": round(float(temperature_rul), 2),
            "vibration_rul_hours": round(float(vibration_rul), 2),
            "rul_hours": round(float(rul_hours), 2),
            "limiting_parameter": limiting_parameter,
            "predicted_failure_time": predicted_failure_time,
            "failure_threshold_hours": FAILURE_THRESHOLD_HOURS,
            "threshold_exceeded": bool(rul_hours <= FAILURE_THRESHOLD_HOURS),
        }

        # Pick the equipment with the lowest RUL (most critical)
        if best_result is None or rul_hours < best_result["rul_hours"]:
            best_result = result

    if best_result is None:
        raise RuntimeError("Could not compute RUL for any equipment.")

    return best_result


if __name__ == "__main__":
    prediction = predict()
    print(json.dumps(prediction, indent=4))