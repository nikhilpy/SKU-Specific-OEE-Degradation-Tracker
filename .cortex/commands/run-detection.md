# Run Detection

Execute the multi-agent detection workflow for a specific equipment to diagnose degradation and trigger mitigation.

## Steps

1. **Run the detection workflow**:
   ```
   python code/execute_detection/detection_workflow.py --equipment-id LINE-2-PACKAGING
   ```
   This chains three agents:
   - **Diagnostic Agent** (`prediction.py`) — Queries `IT_OT_CONVERGED`, retrieves OEM thresholds, calculates RUL
   - **Investigative Agent** (`investigative_agent.py`) — Identifies active SKU, validates OEM constraints, classifies priority
   - **Future Prediction Agent** (`future_prediction.py`) — LLM-enriched assessment with causes and recommendations

2. **Review output**: The workflow returns a structured JSON payload with:
   - `failure_flag`: Whether RUL is below critical threshold
   - `rul_hours`: Estimated hours until equipment failure
   - `priority`: CRITICAL / HIGH / MEDIUM
   - `action`: IMMEDIATE_MAINTENANCE / SCHEDULE_MAINTENANCE / MONITOR_EQUIPMENT
   - `target_sku`: The SKU causing the degradation (e.g., SKU-899)

3. **Optional — Start autonomous daemon**:
   ```
   python code/execute_detection/autonomous_daemon.py
   ```
   Polls `ASSET_RUL_PREDICTIONS` every 60 seconds and triggers the workflow automatically for any equipment with RUL <= 48 hours. Deduplicates alerts (skips if alert was sent within last 4 hours).

## Prerequisites

- Snowflake infrastructure deployed (`/deploy-infrastructure`)
- Data loaded (`/generate-data`)
- Slack MCP server configured (`.env` has `SLACK_BOT_TOKEN` and `SLACK_TEAM_ID`)
- Ollama running locally (optional — deterministic fallback works without it)

## Demo Mode Alternative

If no Snowflake connection is available, use the Streamlit app's Demo Mode toggle on the Investigate page. It injects `MockDataProvider` and runs the full agent pipeline offline.
