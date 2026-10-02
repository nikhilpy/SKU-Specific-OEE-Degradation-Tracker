# IT/OT Time-Series Boundary Joiner

## When to Use

Use this skill when converging datasets with different sampling frequencies — typically high-frequency OT sensor telemetry (seconds/minutes) with low-frequency IT enterprise records (hours/shifts) — where the join condition is a timestamp falling within a duration window.

## Pattern

```sql
SELECT
    ot.*,
    it.*
FROM {{ot_table}} ot
LEFT JOIN {{it_table}} it
    ON ot.{{join_key}} = it.{{join_key}}
    AND ot.TIMESTAMP BETWEEN it.START_TIME AND it.END_TIME;
```

## Parameters

| Parameter | Description | Example |
|---|---|---|
| `ot_table` | High-frequency sensor telemetry table | `RAW_OT_TELEMETRY` |
| `it_table` | Low-frequency batch schedule table | `RAW_IT_BATCHES` |
| `join_key` | Shared asset identifier column | `EQUIPMENT_ID` |

## Project Usage

This project uses this pattern in the `IT_OT_CONVERGED` Dynamic Table defined in `sql/01-infrastructure.sql`:

```sql
CREATE OR REPLACE DYNAMIC TABLE IT_OT_CONVERGED
    TARGET_LAG = '1 minute'
    WAREHOUSE = 'COMPUTE_WH'
AS
SELECT
    ot.TIMESTAMP, ot.EQUIPMENT_ID, ot.TEMPERATURE_C, ot.VIBRATION_RMS,
    COALESCE(it.BATCH_ID, 'CHANGEOVER/IDLE') AS BATCH_ID,
    COALESCE(it.SKU_ID, 'NONE') AS SKU_ID
FROM RAW_OT_TELEMETRY ot
LEFT JOIN RAW_IT_BATCHES it
    ON ot.EQUIPMENT_ID = it.EQUIPMENT_ID
    AND ot.TIMESTAMP BETWEEN it.START_TIME AND it.END_TIME;
```

## Reusable Skill YAML

The parameterized version is published at `skills/IT_OT_TimeSeries_Joiner.yaml`.

## Key Considerations

- Use `LEFT JOIN` so OT readings during idle/changeover periods are preserved (no batch match).
- `COALESCE` null batch fields to sentinel values like `'CHANGEOVER/IDLE'` and `'NONE'`.
- The Dynamic Table's `TARGET_LAG = '1 minute'` ensures near-real-time convergence.
- This pattern works for any IT/OT convergence where OT timestamps fall within IT duration windows.
