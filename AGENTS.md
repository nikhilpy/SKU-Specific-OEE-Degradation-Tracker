# SKU-Specific OEE Degradation Tracker

## Purpose

Manufacturing predictive maintenance system that converges high-frequency OT sensor streams with low-frequency IT batch schedules to identify which specific SKUs (product runs) are destroying machine health. Autonomously alerts plant managers via Slack MCP.

## Snowflake Context

- **Database:** `OEE_COMMAND_CENTER`
- **Schema:** `FACTORY_FLOOR`
- **Warehouse:** `COMPUTE_WH`
- **Role:** `ACCOUNTADMIN`

## Key Snowflake Objects

| Object | Type | Purpose |
|---|---|---|
| `RAW_OT_TELEMETRY` | Table | High-frequency sensor readings (temperature, vibration) |
| `RAW_IT_BATCHES` | Table | IT ERP batch schedules (SKU, equipment, start/end times) |
| `IT_OT_CONVERGED` | Dynamic Table (1-min lag) | Time-series boundary join: `OT.TIMESTAMP BETWEEN IT.START_TIME AND IT.END_TIME` |
| `OEM_EQUIPMENT_THRESHOLDS` | Table | Equipment-type max temp/vibration limits |
| `OEM_MANUAL_CHUNKS` | Table | Chunked OEM PDF text for Cortex Search |
| `OEM_MANUAL_SEARCH` | Cortex Search Service | Semantic search over OEM manual |
| `EQUIPMENT_TEMP_FORECAST` | ML Forecast | 72-hour temperature forecast model |
| `EQUIPMENT_VIBE_FORECAST` | ML Forecast | 72-hour vibration forecast model |
| `ASSET_RUL_PREDICTIONS` | View | Earliest predicted failure per equipment |
| `ALERTS_HISTORY` | Table | Audit log of triggered mitigation actions |
| `factory_health_ontology.yaml` | Semantic Model | Cortex Analyst ontology linking assets, batches, RUL, stress |

## Multi-Agent Pipeline

Three-stage pipeline with Pydantic-validated JSON handoffs (`code/execute_detection/schemas.py`):

1. **Diagnostic Agent** (`prediction.py`) — Fetches telemetry, retrieves OEM thresholds, calculates linear RUL. Emits `DiagnosticState` if RUL < 24h.
2. **Investigative/Execution Agent** (`investigative_agent.py`) — Identifies active SKU, retrieves OEM evidence via Cortex Search, classifies priority (CRITICAL/HIGH/MEDIUM), dispatches Slack alert via MCP.
3. **Future Prediction Agent** (`future_prediction.py`) — LLM-powered enrichment with assessment, causes, and recommendations.

Orchestrator: `detection_workflow.py` chains all three stages.
Autonomous daemon: `autonomous_daemon.py` polls `ASSET_RUL_PREDICTIONS` every 60s.

## File Layout

```
sql/                          SQL scripts (01-infrastructure → 04-cortex-search)
semantic_models/              Cortex Analyst semantic model YAML
skills/                       Reusable CoCo skill YAMLs
code/misc/                    Data generator + Snowflake client
code/create_rag/              PDF chunking + RAG pipeline
code/llm_setup/               Ollama LLM client
code/execute_detection/       Multi-agent detection pipeline
code/streamlit_app/           4-page Streamlit Command Center
tests/                        pytest suite (offline, no Snowflake needed)
```

## Pydantic Schema Contracts

Agent handoffs are strictly validated:
- `DiagnosticState` — equipment_id, metric, current_val, threshold, rul_hours, failure_flag, confidence_score (0-1)
- `OEMValidation` — max_temp_limit, max_vibration_limit, citation_source, breach_detected
- `MitigationDecision` — priority (CRITICAL/HIGH/MEDIUM), action (IMMEDIATE_MAINTENANCE/SCHEDULE_MAINTENANCE/MONITOR_EQUIPMENT), `extra="forbid"` rejects LLM hallucinations

## Testing

Run `pytest tests/test_oee_tracker.py -v` — 6 tests, all offline via `MockDataProvider`.

## Demo Mode

Toggle in Streamlit Investigate page injects `MockDataProvider` — simulates SKU-899 thermal breach on LINE-2-PACKAGING without any Snowflake connection.

## Hard-Coded Scenario

SKU-899 (Heavy-Duty Cardboard) causes a 15% temperature spike and 20% vibration spike on packaging equipment, leading to accelerated bearing fatigue.
