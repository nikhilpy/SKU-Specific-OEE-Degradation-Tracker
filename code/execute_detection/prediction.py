import json
import math
import os
import re
import sys

import pandas as pd

CODE_ROOT = os.path.dirname(
    os.path.dirname(os.path.abspath(__file__))
)

for path in (CODE_ROOT, os.path.join(CODE_ROOT, "misc"), os.path.dirname(os.path.abspath(__file__))):
    if path not in sys.path:
        sys.path.insert(0, path)

from schemas import DiagnosticState
from llm_setup.llm import ask_json

# Used when the OEM manual yields no usable limits (OEM Hard Caps)
DEFAULT_THRESHOLDS = {
    "temperature_limit": 90.0,
    "vibration_limit": 2.3,
    "failure_threshold_hours": 24.0
}

# -----------------------------
# Configuration
# -----------------------------

def to_float(value):
    """
    Coerce a model value to a number, tolerating units such as
    '82 °C' or '4.2 mm/s'.
    """
    if isinstance(value, bool):
        raise TypeError("bool is not a threshold")

    if isinstance(value, (int, float)):
        return float(value)

    match = re.search(r"-?\d+(?:\.\d+)?", str(value))

    if not match:
        raise ValueError(f"No number in {value!r}")

    return float(match.group())


def get_threshold(retrieved, data_provider=None):
    """
    Extract the OEM operating limits. Dynamically fetches from Snowflake first.
    Falls back to LLM parsing of the retrieved manual text, and finally to DEFAULT_THRESHOLDS.
    """
    if data_provider and hasattr(data_provider, '_get_df'):
        try:
            df = data_provider._get_df(
                "SELECT MAX_TEMP_LIMIT, MAX_VIBRATION_LIMIT FROM OEM_EQUIPMENT_THRESHOLDS LIMIT 1"
            )
            if not df.empty and not pd.isna(df.iloc[0]['MAX_TEMP_LIMIT']):
                print("[Prediction Agent] Successfully fetched dynamic thresholds from OEM_EQUIPMENT_THRESHOLDS")
                return {
                    "temperature_limit": float(df.iloc[0]['MAX_TEMP_LIMIT']),
                    "vibration_limit": float(df.iloc[0]['MAX_VIBRATION_LIMIT']),
                    "failure_threshold_hours": 24.0
                }
        except Exception as e:
            print(f"[Prediction Agent] Failed to fetch dynamic thresholds: {e}")

    if not retrieved:
        return dict(DEFAULT_THRESHOLDS)

    if isinstance(retrieved, dict) and "chunks" in retrieved:
        excerpts = "\n\n".join(
            f"[chunk {chunk['chunk_index']}]\n{chunk['text']}"
            for chunk in retrieved["chunks"]
        )

    else:
        excerpts = json.dumps(retrieved, indent=2)

    prompt = f"""
Extract the operating limits for the packaging equipment from the
OEM manual excerpts below.

<Manual Excerpts>
{excerpts}
</Manual Excerpts>

Return JSON with exactly these keys:
- temperature_limit: the maximum allowed temperature, in degrees Celsius
- vibration_limit: the maximum allowed vibration, in mm/s
- failure_threshold_hours: how many hours of remaining useful life
  should trigger a maintenance alert
"""

    try:
        parsed = ask_json(prompt)

    except Exception as e:
        print(f"\nThreshold extraction failed: {e}")
        return dict(DEFAULT_THRESHOLDS)

    thresholds = dict(DEFAULT_THRESHOLDS)

    for key in DEFAULT_THRESHOLDS:
        try:
            thresholds[key] = to_float(parsed[key])

        except (KeyError, TypeError, ValueError):
            print(f"\nNo usable {key} in model response, using default.")

    return thresholds


def predict(equipment_id="LINE-2-PACKAGING", data_provider=None):
    if data_provider is None:
        from data_provider import SnowflakeDataProvider
        data_provider = SnowflakeDataProvider()

    parts = equipment_id.split("-")
    equipment_type = parts[-1] if len(parts) > 1 else equipment_id

    query = (
        f"OEM operating limits for {equipment_type} equipment, "
        f"temperature, vibration and failure threshold"
    )

    retrieved = data_provider.search_oem_manual(query)

    thresholds = get_threshold(retrieved, data_provider)

    TEMPERATURE_LIMIT = thresholds["temperature_limit"]
    VIBRATION_LIMIT = thresholds["vibration_limit"]
    FAILURE_THRESHOLD_HOURS = thresholds["failure_threshold_hours"]

    # -----------------------------
    # Load device telemetry
    # -----------------------------
    df = data_provider.get_recent_telemetry(equipment_id)

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

    if math.isfinite(rul_hours):
        predicted_failure_time = str(
            latest_timestamp +
            pd.Timedelta(float(rul_hours), unit="h")
        )

    else:
        predicted_failure_time = None


    # -----------------------------
    # Failure threshold
    # -----------------------------
    threshold_exceeded = bool(
        rul_hours <= FAILURE_THRESHOLD_HOURS
    )


    # -----------------------------
    # Output
    # -----------------------------

    current_val = float(current_temperature if limiting_parameter == "temperature" else current_vibration)
    dynamic_threshold = float(TEMPERATURE_LIMIT if limiting_parameter == "temperature" else VIBRATION_LIMIT)
    pipeline_status = (
        "DEGRADED_LOCAL_HEURISTIC"
        if not retrieved or not retrieved.get("chunks") or retrieved.get("STATUS") == "DEGRADED_LOCAL_HEURISTIC"
        else "OPTIMAL_RETRIEVAL"
    )

    diagnostic_state = DiagnosticState(
        equipment_id=str(equipment),
        metric=limiting_parameter,
        current_val=current_val,
        dynamic_threshold=dynamic_threshold,
        rul_hours=float(rul_hours) if math.isfinite(rul_hours) else 999.0,
        failure_flag=threshold_exceeded,
        confidence_score=0.95 if threshold_exceeded else 0.85,
    )

    if threshold_exceeded:
        result = {
            "failure_flag": True,
            "equipment_id": equipment,
            "rul_hours": rul_hours,
            "predicted_failure_time": predicted_failure_time,
            "reason": (
                    f"Predicted RUL ({rul_hours} hours) is below "
                    f"the {FAILURE_THRESHOLD_HOURS}-hour threshold."
                ),
            "next_agent": "investigative_agent",
            "STATUS": pipeline_status,
            "metric": limiting_parameter,
            "current_val": current_val,
            "dynamic_threshold": dynamic_threshold,
            "diagnostic_state": diagnostic_state.model_dump(),
        }
    else:
        result = {
            "failure_flag": False,
            "equipment_id": equipment,
            "rul_hours": rul_hours,
            "predicted_failure_time": predicted_failure_time,
            "reason": "Equipment is currently above the failure threshold.",
            "next_agent": None,
            "STATUS": pipeline_status,
            "metric": limiting_parameter,
            "current_val": current_val,
            "dynamic_threshold": dynamic_threshold,
            "diagnostic_state": diagnostic_state.model_dump(),
        }

    print("\n===== PREDICTION AGENT =====")

    for key, value in result.items():
        print(f"{key}: {value}")

    return result

if __name__ == "__main__":
    prediction = predict()
    print(prediction)