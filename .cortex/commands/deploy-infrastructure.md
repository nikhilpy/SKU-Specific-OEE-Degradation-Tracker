# Deploy Infrastructure

Deploy all Snowflake objects for the OEE Degradation Tracker. Executes SQL scripts in the required order with pre-checks and validation.

## Steps

1. **Pre-check**: Verify Snowflake connection is active and `COMPUTE_WH` warehouse is available.

2. **Run SQL scripts in order**:
   - `sql/01-infrastructure.sql` — Creates database `OEE_COMMAND_CENTER`, schema `FACTORY_FLOOR`, raw tables, Dynamic Table `IT_OT_CONVERGED`, auxiliary tables, stages.
   - `sql/02-data-ingestion.sql` — Runs `COPY INTO` to load staged CSV data into `RAW_OT_TELEMETRY` and `RAW_IT_BATCHES`.
   - `sql/03-analytics.sql` — Creates hourly aggregate views, trains `SNOWFLAKE.ML.FORECAST` models (temperature + vibration), generates 72-hour predictions, creates `ASSET_RUL_PREDICTIONS` view.
   - `sql/04-cortex-search.sql` — Creates `OEM_MANUAL_SEARCH` Cortex Search Service on `OEM_MANUAL_CHUNKS`.

3. **Post-validation**: Confirm all objects exist by running:
   ```sql
   SHOW DYNAMIC TABLES IN SCHEMA OEE_COMMAND_CENTER.FACTORY_FLOOR;
   SELECT COUNT(*) FROM IT_OT_CONVERGED;
   SELECT COUNT(*) FROM ASSET_RUL_PREDICTIONS;
   ```

## Prerequisites

- Snowflake credentials configured (`.env` file or CoCo connection)
- Synthetic data must be generated and staged BEFORE step 2 (use `/generate-data` command)
- OEM PDF chunks must be ingested BEFORE step 4 (run `code/create_rag/insert_document.py`)

## Important Notes

- The ML Forecast models in step 3 require several hundred rows spanning multiple hours in `IT_OT_CONVERGED`. Run steps 1-2 first and wait for the Dynamic Table to populate.
- All scripts use `CREATE OR REPLACE` so they are idempotent and safe to re-run.
