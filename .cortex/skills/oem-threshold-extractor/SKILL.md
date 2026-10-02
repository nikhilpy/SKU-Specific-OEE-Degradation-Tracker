# OEM Threshold Extraction

## When to Use

Use this skill when retrieving equipment operating limits (max temperature, max vibration) from OEM documentation. The system uses a multi-tier fallback chain to ensure thresholds are always available.

## Fallback Chain

The Diagnostic Agent (`code/execute_detection/prediction.py`) retrieves thresholds in this priority order:

1. **Snowflake Table** — Query `OEM_EQUIPMENT_THRESHOLDS` for the equipment type
2. **Cortex Search** — Semantic search against `OEM_MANUAL_SEARCH` service using the equipment ID
3. **LLM Extraction** — Parse Cortex Search results with Ollama to extract numeric limits
4. **Hardcoded Defaults** — `max_temp=90.0`, `max_vibration=2.5` (safe conservative limits)

## Cortex Search Query

```sql
-- The OEM_MANUAL_SEARCH Cortex Search Service indexes OEM_MANUAL_CHUNKS
-- Query it programmatically via the Python Cortex Search client:
SELECT *
FROM TABLE(OEM_MANUAL_SEARCH(
    query => 'maximum operating temperature for LINE-2-PACKAGING',
    top_k => 3
));
```

## Schema: OEM_EQUIPMENT_THRESHOLDS

```sql
CREATE TABLE OEM_EQUIPMENT_THRESHOLDS (
    EQUIPMENT_TYPE VARCHAR,
    MAX_TEMP_LIMIT FLOAT,
    MAX_VIBRATION_LIMIT FLOAT,
    LAST_UPDATED TIMESTAMP DEFAULT CURRENT_TIMESTAMP()
);
```

## Pydantic Validation

Extracted thresholds are validated via `OEMValidation` schema (`code/execute_detection/schemas.py`):

```python
class OEMValidation(BaseModel):
    max_temp_limit: float
    max_vibration_limit: float
    citation_source: str        # "snowflake_table", "cortex_search", "llm_extraction", or "hardcoded_default"
    breach_detected: bool
    status: Optional[str] = None
```

## Source Documents

- OEM PDF manual: `data/OEM_Maintenance_and_Operations_Manual.pdf`
- PDF chunking: `code/create_rag/parse_pdf.py`
- Chunk ingestion: `code/create_rag/insert_document.py`
- Cortex Search setup: `sql/04-cortex-search.sql`
