# RUL (Remaining Useful Life) Prediction

## When to Use

Use this skill when working with equipment failure prediction, ML forecast models, or the Diagnostic Agent's RUL calculation logic.

## ML Forecast Models

Two `SNOWFLAKE.ML.FORECAST` models are trained on hourly aggregates from `IT_OT_CONVERGED`:

| Model | Training View | Predicts |
|---|---|---|
| `EQUIPMENT_TEMP_FORECAST` | `V_EQUIPMENT_TEMP_HISTORY` (hourly avg temperature) | 72-hour temperature trajectory |
| `EQUIPMENT_VIBE_FORECAST` | `V_EQUIPMENT_VIBE_HISTORY` (hourly avg vibration) | 72-hour vibration trajectory |

Forecast outputs are stored in `PREDICTED_TEMPERATURES` and `PREDICTED_VIBRATIONS`.

## ASSET_RUL_PREDICTIONS View

Combines both forecast outputs to find the earliest predicted threshold breach per equipment:

```sql
-- Identifies the first future timestamp where temperature or vibration
-- exceeds OEM limits, then calculates hours remaining from now.
SELECT
    EQUIPMENT_ID,
    PREDICTED_FAILURE_TIMESTAMP,
    DATEDIFF('hour', CURRENT_TIMESTAMP(), PREDICTED_FAILURE_TIMESTAMP) AS RUL_HOURS
FROM (
    -- Union of temperature and vibration breach predictions
    -- ordered by earliest breach per equipment
);
```

## Diagnostic Agent RUL Calculation

The Diagnostic Agent (`code/execute_detection/prediction.py`) calculates RUL using linear degradation:

1. Fetch last 100 readings from `IT_OT_CONVERGED` for the equipment
2. Retrieve OEM thresholds (see `oem-threshold-extractor` skill)
3. Calculate degradation rate: `(recent_avg - baseline) / time_window_hours`
4. Estimate RUL: `(threshold - current_value) / degradation_rate`
5. If RUL < 24 hours, emit `DiagnosticState` with `failure_flag=True`

## DiagnosticState Schema

```python
class DiagnosticState(BaseModel):
    equipment_id: str
    metric: str                    # "temperature" or "vibration"
    current_val: float
    dynamic_threshold: float       # OEM limit for this metric
    rul_hours: float
    failure_flag: bool
    confidence_score: float        # 0.0 to 1.0, validated by Pydantic
```

## Alert Thresholds

| Condition | Action |
|---|---|
| RUL <= 24 hours | `failure_flag=True`, triggers Investigative Agent |
| RUL <= 48 hours | Autonomous daemon triggers detection workflow |
| RUL > 48 hours | Monitor only, no action |

## Key Files

- ML model training: `sql/03-analytics.sql`
- Diagnostic Agent: `code/execute_detection/prediction.py`
- Schemas: `code/execute_detection/schemas.py`
- Autonomous daemon: `code/execute_detection/autonomous_daemon.py`
