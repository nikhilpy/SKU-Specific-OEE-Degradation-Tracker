import os
import json
import sys
import streamlit as st
import snowflake.connector
from dotenv import load_dotenv
from snowflake_conn import get_active_session

# ── Add llm_setup/ to sys.path so llm.py is importable ──────────────────────
_LLM_SETUP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "llm_setup",
)
if _LLM_SETUP_PATH not in sys.path:
    sys.path.insert(0, _LLM_SETUP_PATH)

from llm import complete as ollama_complete, OLLAMA_HOST, DEFAULT_MODEL  # noqa: E402

# Resolve .env from project root (two levels up from streamlit_app/)
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".env",
)
load_dotenv(_ENV_PATH)

_DB     = os.getenv("SNOWFLAKE_DATABASE", "OEE_COMMAND_CENTER")
_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA",   "FACTORY_FLOOR")
_WH     = os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH")
_ROLE   = os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN")

# Snowflake Cortex model for the investigative agent
CORTEX_MODEL = os.getenv("CORTEX_MODEL", "mistral-large2")

# Fully-qualified Cortex Search Service (built by sql/06-cortex.sql)
SEARCH_SERVICE = f"{_DB}.{_SCHEMA}.OEM_MANUAL_SEARCH"

# Chunk table (used by the updated search_oem_manual in misc/snowflake_client.py)
CHUNK_TABLE = f"{_DB}.{_SCHEMA}.OEM_MANUAL_CHUNKS"

# ── Search intent vocabulary ─────────────────────────────────────────────────
# Mirrors the SEARCH_INTENTS dict added to misc/snowflake_client.py in the
# 3:15 PM commit.  Using "investigation" intent gives richer symptom/root-cause
# context, matching what investigative_agent.py would retrieve.
_SEARCH_INTENTS = {
    "threshold": (
        "operating limit threshold maximum temperature "
        "vibration remaining useful life maintenance alert"
    ),
    "investigation": (
        "operating limit threshold maximum temperature vibration "
        "symptom root cause error corrective action"
    ),
}

def _build_query(equipment_id: str, intent: str = "investigation") -> str:
    """
    Build the OEM manual search query string.
    Mirrors misc/snowflake_client.build_query() added in the 3:15 PM commit.
    """
    if intent not in _SEARCH_INTENTS:
        raise ValueError(f"Unknown intent {intent!r}")
    return f"OEM operating limits for {equipment_id}, {_SEARCH_INTENTS[intent]}"

# ── Fallback OEM limits ───────────────────────────────────────────────────────
# Matches misc/snowflake_client.FALLBACK_OEM_EVIDENCE structure
_FALLBACK_OEM_EVIDENCE = {
    "source": "LINE-2-PACKAGING OEM Maintenance Manual",
    "evidence": [
        {"parameter": "temperature", "limit": 85.0, "unit": "°C"},
        {"parameter": "vibration",   "limit": 7.5,  "unit": "mm/s"},
    ],
}

_FALLBACK_OEM_TEXT = (
    "Max Sustained Temp: 85°C, Max Vibration: 7.5 mm/s "
    "(fallback — OEM_MANUAL_CHUNKS not yet deployed; run sql/06-cortex.sql)"
)


# ─────────────────────────────────────────────
# Snowflake raw connector (for keyword chunk search)
# ─────────────────────────────────────────────

def _get_connector_connection():
    """Creates a raw snowflake.connector connection."""
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse=_WH,
        database=_DB,
        schema=_SCHEMA,
        role=_ROLE,
    )


# ─────────────────────────────────────────────
# OEM Constraint retrieval
# Mirrors the updated search_oem_manual() in misc/snowflake_client.py
# which now queries OEM_MANUAL_CHUNKS by keyword ranking instead of
# CORTEX.SEARCH_PREVIEW.  Returns a structured dict or falls back.
# ─────────────────────────────────────────────

import re as _re

_STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into",
    "are", "was", "were", "what", "which", "how", "does", "doc",
    "documents", "document", "retrieve", "return", "contents",
    "operating", "manual", "line", "packaging"
}

def _query_terms(query: str) -> list[str]:
    terms = _re.findall(r"[a-z0-9]+", query.lower())
    return [t for t in terms if len(t) > 2 and t not in _STOP_WORDS]


def _oem_result_to_text(result) -> str:
    """
    Convert the structured OEM search result (new dict format from the updated
    misc/snowflake_client.py) into a plain string for use in prompts.

    The updated search_oem_manual() now returns:
        {"source": "OEM_MANUAL_CHUNKS", "chunks": [{"text": ..., ...}, ...]}
    The old Cortex Search Preview returned a JSON string.
    Both are handled here gracefully.
    """
    if not result:
        return _FALLBACK_OEM_TEXT

    # New format: dict with "chunks" list (from updated snowflake_client.py)
    if isinstance(result, dict):
        if "chunks" in result:
            top_chunks = result["chunks"][:2]
            oem_text = " | ".join(c.get("text", "")[:300] for c in top_chunks)
            return f"[From OEM Manual] {oem_text}" if oem_text.strip() else _FALLBACK_OEM_TEXT

        # Fallback dict structure: {"evidence": [...]}
        if "evidence" in result:
            parts = [
                f"Max {e['parameter'].title()}: {e['limit']} {e['unit']}"
                for e in result.get("evidence", [])
            ]
            return ", ".join(parts) if parts else _FALLBACK_OEM_TEXT

    # Legacy: raw JSON string from old CORTEX.SEARCH_PREVIEW path
    if isinstance(result, str):
        try:
            parsed = json.loads(result)
            results_list = parsed.get("results", [])
            if results_list:
                return "[From OEM Manual] " + " | ".join(
                    r.get("CHUNK_TEXT", "")[:300] for r in results_list[:2]
                )
        except (json.JSONDecodeError, AttributeError):
            return result[:500]

    return _FALLBACK_OEM_TEXT


def _retrieve_oem_constraints(equipment_id: str) -> str:
    """
    Retrieves OEM operating limits for the given equipment.

    Uses the "investigation" intent (new in misc/snowflake_client.SEARCH_INTENTS)
    to get richer symptom/root-cause context from OEM_MANUAL_CHUNKS.

    Query strategy mirrors the updated search_oem_manual() which now does
    keyword ranking over OEM_MANUAL_CHUNKS (not CORTEX.SEARCH_PREVIEW).
    Falls back gracefully if the table or connection is unavailable.
    """
    query = _build_query(equipment_id, intent="investigation")
    terms = _query_terms(query)

    if not terms:
        return _FALLBACK_OEM_TEXT

    conditions = " OR ".join(
        f"\"CHUNK_TEXT\" ILIKE '%{term}%'" for term in terms
    )
    sql = (
        f"SELECT \"FILE_NAME\", \"CHUNK_INDEX\", \"CHUNK_TEXT\" "
        f"FROM {CHUNK_TABLE} "
        f"WHERE {conditions} "
        f"LIMIT 10"
    )

    try:
        conn = _get_connector_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(sql)
            rows = cursor.fetchall()
        finally:
            cursor.close()
        conn.close()

        if not rows:
            return _FALLBACK_OEM_TEXT

        # Score chunks by keyword frequency (mirrors score_chunk in snowflake_client.py)
        def _score(text):
            lowered = text.lower()
            matched = sum(1 for t in terms if t in lowered)
            occurrences = sum(lowered.count(t) for t in terms)
            return 2 * matched + occurrences

        ranked = sorted(
            [{"text": row[2], "score": _score(row[2])} for row in rows],
            key=lambda c: c["score"],
            reverse=True,
        )[:2]

        oem_text = " | ".join(c["text"][:300] for c in ranked)
        return f"[From OEM Manual] {oem_text}" if oem_text.strip() else _FALLBACK_OEM_TEXT

    except Exception:
        return _FALLBACK_OEM_TEXT


# ─────────────────────────────────────────────
# Priority / action classification
# Mirrors execute_detection/investigative_agent.py thresholds exactly
# ─────────────────────────────────────────────

def _classify_priority(rul_hours: float) -> tuple[str, str]:
    """Return (action, priority) matching the backend investigative_agent logic."""
    if rul_hours <= 6:
        return "IMMEDIATE_MAINTENANCE", "CRITICAL"
    elif rul_hours <= 24:
        return "SCHEDULE_MAINTENANCE", "HIGH"
    else:
        return "MONITOR_EQUIPMENT", "MEDIUM"


# ─────────────────────────────────────────────
# Investigative Agent — Local Ollama (primary LLM)
# Snowflake Cortex is NOT used; trial accounts lack Cortex access.
# ─────────────────────────────────────────────

def _ask_via_ollama(prompt: str) -> str:
    """
    Call the locally hosted Ollama server via llm_setup/llm.py.
    Raises RuntimeError (with a human-readable message) if Ollama is unreachable.
    """
    return ollama_complete(prompt)


def ask_investigative_agent(question: str, context: dict) -> str:
    """
    Investigative Agent for the Streamlit UI.

    Primary LLM  : Local Ollama (llm_setup/llm.py) — no Snowflake Cortex needed.
    Hard fallback: Structured text with priority / action details when Ollama
                   is unreachable (e.g. `ollama serve` not running).

    OEM constraints are retrieved via keyword-ranked search over OEM_MANUAL_CHUNKS
    in Snowflake (no Cortex Search required).

    Priority / action classification mirrors execute_detection/investigative_agent.py.
    """
    rul = context.get("rul", "Unknown")

    # 1. Retrieve OEM constraints using "investigation" intent
    oem_constraints = _retrieve_oem_constraints(context.get("equipment_id", ""))

    # 2. Priority classification
    try:
        action, priority = _classify_priority(float(rul))
    except (TypeError, ValueError):
        action, priority = "MONITOR_EQUIPMENT", "MEDIUM"

    # 3. Build prompt
    prompt = f"""You are an Investigative AI Agent for a manufacturing plant.

Analyze the following context and answer the user's question concisely and technically.

<Investigation Data>
- Equipment ID: {context.get('equipment_id', 'Unknown')}
- Active SKU causing stress: {context.get('sku', 'Unknown')}
- Predicted Remaining Useful Life (RUL): {rul} hours
- Recommended Action: {action}
- Priority Level: {priority}
- OEM Constraints (from equipment manual): {oem_constraints}
</Investigation Data>

User Question: {question}

Quote the actual limits and RUL from the investigation data above.
Answer in plain, actionable language referencing the OEM limits and RUL when relevant."""

    # 4. Try local Ollama first
    ollama_error: str = ""
    try:
        return _ask_via_ollama(prompt)
    except Exception as exc:
        ollama_error = str(exc)

    # 5. Hard fallback — structured summary when Ollama is unreachable
    error_detail = (
        f"\n\n> ⚠️ **Ollama error:** `{ollama_error}`\n"
        f"> Make sure Ollama is running: `ollama serve`\n"
        f"> Model in use: `{DEFAULT_MODEL}` (override with `OLLAMA_MODEL` in `.env`)\n"
        f"> Ollama host: `{OLLAMA_HOST}` (override with `OLLAMA_HOST` in `.env`)"
    ) if ollama_error else ""
    return (
        f"**Backend Analysis** (Ollama LLM unavailable):\n\n"
        f"Your question: *\"{question}\"*\n\n"
        f"Based on the investigation data available:\n"
        f"- Equipment **{context.get('equipment_id')}** has **{rul} hours** of RUL.\n"
        f"- Priority: **{priority}** → Action: **{action}**\n"
        f"- OEM Limits: {oem_constraints}\n\n"
        f"The Investigative Agent could not generate a dynamic LLM answer because "
        f"the local Ollama server is unreachable."
        f"{error_detail}"
    )
