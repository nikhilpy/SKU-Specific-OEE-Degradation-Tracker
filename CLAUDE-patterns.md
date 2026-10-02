# Project Patterns and Conventions

## Schema Validation (Pydantic v2)

All multi-agent handoff payloads use strict Pydantic v2 models defined in `code/execute_detection/schemas.py`:

- Use `extra="forbid"` on terminal schemas (e.g., `MitigationDecision`) to reject LLM hallucinated fields.
- Use `extra="ignore"` on intermediate schemas (e.g., `DiagnosticState`, `OEMValidation`) to tolerate extra upstream data.
- Constrain numeric ranges with `Field(ge=, le=)` — e.g., `confidence_score: float = Field(..., ge=0.0, le=1.0)`.
- Use `Literal[...]` for enum-like fields: `priority: Literal["CRITICAL", "HIGH", "MEDIUM"]`.

## DataProvider Abstraction

All data access goes through the `BaseDataProvider` interface (`code/execute_detection/data_provider.py`):

- `SnowflakeDataProvider` — queries live Snowflake tables.
- `MockDataProvider` — returns deterministic synthetic data for tests and Demo Mode.
- Agents accept `data_provider` as a constructor/function argument. Never call Snowflake directly from agent logic.

## Agent Pipeline Pattern

Agents are chained in `detection_workflow.py` with explicit contracts:

1. Each agent is a standalone function returning a typed dict or Pydantic model.
2. The orchestrator handles early-exit logic (e.g., `if not failure_flag: return`).
3. Error fallbacks are deterministic — if LLM is unavailable, hardcoded rules apply.

## SQL Conventions

- All DDL uses `CREATE OR REPLACE` for idempotency.
- Dynamic Tables use `TARGET_LAG` for near-real-time refresh.
- `COALESCE` null joins to sentinel values (`'CHANGEOVER/IDLE'`, `'NONE'`).
- ML Forecast models are trained on hourly aggregate views, not raw tables.

## Naming

- Snowflake objects: `UPPER_SNAKE_CASE` (e.g., `RAW_OT_TELEMETRY`, `IT_OT_CONVERGED`).
- Python files: `lower_snake_case` (e.g., `detection_workflow.py`, `data_provider.py`).
- Pydantic models: `PascalCase` (e.g., `DiagnosticState`, `MitigationDecision`).

## Testing

- Tests use `MockDataProvider` — no Snowflake credentials required.
- Test file: `tests/test_oee_tracker.py`, run with `pytest tests/ -v`.
- Tests validate: SQL rendering, Pydantic schema enforcement, referential integrity, deterministic rule evaluation, OEM fallback logic.
