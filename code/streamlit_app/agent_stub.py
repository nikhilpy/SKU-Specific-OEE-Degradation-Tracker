import os
import json
import sys
import streamlit as st
import snowflake.connector
from dotenv import load_dotenv
import urllib.request
from snowflake_conn import get_active_session

# ── Add llm_setup/ to sys.path so llm.py is importable ──────────────────────
_LLM_SETUP_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "llm_setup",
)
if _LLM_SETUP_PATH not in sys.path:
    sys.path.insert(0, _LLM_SETUP_PATH)

from llm import complete as ollama_complete, ask_json as ollama_ask_json, OLLAMA_HOST, DEFAULT_MODEL, LAST_USED_LLM  # noqa: E402

# Resolve .env from project root (two levels up from streamlit_app/)
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    ".env",
)
load_dotenv(_ENV_PATH)

_DB     = os.getenv("SNOWFLAKE_DATABASE") or "OEE_COMMAND_CENTER"
_SCHEMA = os.getenv("SNOWFLAKE_SCHEMA") or "FACTORY_FLOOR"
_WH     = os.getenv("SNOWFLAKE_WAREHOUSE") or "COMPUTE_WH"
_ROLE   = os.getenv("SNOWFLAKE_ROLE") or "ACCOUNTADMIN"

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
    # Extract generic equipment type to share manuals across lines
    parts = equipment_id.split("-")
    equipment_type = parts[-1] if len(parts) > 1 else equipment_id
    
    return f"OEM operating limits for {equipment_type} equipment, {_SEARCH_INTENTS[intent]}"


_FALLBACK_OEM_TEXT = (
    "Max Sustained Temp: 85°C, Max Vibration: 7.5 mm/s "
    "(fallback — OEM_MANUAL_CHUNKS not yet deployed; run sql/04-cortex-search.sql)"
)


# ─────────────────────────────────────────────
# Snowflake raw connector (for keyword chunk search)
# ─────────────────────────────────────────────

def _get_connector_connection():
    """Returns the raw snowflake.connector connection from the active session cache."""
    session = get_active_session()
    if session:
        return session._conn
    
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


def _ask_json_via_ollama(prompt: str) -> dict:
    """
    Call the locally hosted Ollama server via llm_setup/llm.py, expecting a JSON response.
    """
    return ollama_ask_json(prompt)


def _query_cortex_analyst(question: str, context: dict, status=None) -> str:
    """
    Calls the Snowflake Cortex Analyst REST API using the deployed semantic model.
    If it generates SQL, it executes it and uses Ollama to summarize the result.
    """
    conn = _get_connector_connection()
    try:
        host = conn.host
        url = f"https://{host}/api/v2/cortex/analyst/message"
        token = conn.rest.token
        
        # Construct context for Analyst
        equip_id = context.get('equipment_id')
        sku = context.get('sku')
        if equip_id and sku:
            analyst_prompt = f"For Equipment {equip_id} and SKU {sku}: {question}"
        else:
            analyst_prompt = question
        
        if status:
            status.write("❄️ **Cortex Analyst:** Generating SQL from natural language...")
        
        payload = {
            "messages": [
                {
                    "role": "user", 
                    "content": [{"type": "text", "text": analyst_prompt}]
                }
            ],
            "semantic_model_file": f"@{_DB}.{_SCHEMA}.SEMANTIC_MODELS_STAGE/factory_health_ontology.yaml"
        }
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'))
        req.add_header('Authorization', f'Snowflake Token="{token}"')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Accept', 'application/json')
        
        with urllib.request.urlopen(req, timeout=20) as response:
            result = json.loads(response.read().decode())
            
        messages = result.get('message', {}).get('content', [])
        sql_query = ""
        text_response = ""
        
        for msg in messages:
            if msg.get('type') == 'sql':
                sql_query = msg.get('statement', '')
            elif msg.get('type') == 'text':
                text_response += msg.get('text', '') + "\n"
                
        if sql_query:
            # We got SQL from Cortex Analyst, run it!
            if status:
                status.write(f"📊 **Snowflake:** Executing generated SQL query:\n```sql\n{sql_query}\n```")
            cursor = conn.cursor()
            cursor.execute(sql_query)
            rows = cursor.fetchmany(100)
            columns = [col[0] for col in cursor.description] if cursor.description else []
            cursor.close()
            
            # Use LLM to format the data nicely
            if status:
                status.write("🤖 **LLM:** Summarizing raw database results...")
            summary_prompt = f"You are a helpful factory assistant. The user asked: '{question}'. \nHere is the data pulled from the database:\nColumns: {columns}\nData: {rows}\n\nSummarize this data clearly for the user."
            answer = _ask_via_ollama(summary_prompt)
            
            backend = LAST_USED_LLM.get("backend", "unknown")
            model = LAST_USED_LLM.get("model", "unknown")
            reason = LAST_USED_LLM.get("reason", "")
            
            if status:
                if backend == "snowflake_cortex":
                    status.write(f"❄️ **LLM Engine:** Snowflake Cortex (`{model}`) - {reason}")
                else:
                    status.write(f"🦙 **LLM Engine:** Local Ollama (`{model}`) - {reason}")
            
            llm_badge = f"\n\n---\n*Answered by: **{backend}** (`{model}`)*"
            return answer + llm_badge
            
        return (text_response or "Cortex Analyst did not return a valid response.") + "\n\n---\n*Answered by: **Snowflake Cortex Analyst***"
            
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        print(f"Cortex Analyst API Error: {e.code} - {error_body}")
        return _fallback_analyst_llm(question, status)
    except Exception as api_err:
        print(f"Cortex Analyst Error: {api_err}")
        return _fallback_analyst_llm(question, status)

def _fallback_analyst_llm(question: str, status) -> str:
    """Fallback to local LLM for Text-to-SQL when Cortex Analyst fails."""
    if status:
        status.write("⚠️ **Cortex Analyst failed.** Falling back to local LLM for Text-to-SQL...")
        
    yaml_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        "semantic_models", "factory_health_ontology.yaml"
    )
    
    try:
        with open(yaml_path, 'r') as f:
            yaml_content = f.read()
    except Exception as e:
        return f"**LLM Fallback Error:** Could not read semantic model. {e}"

    # Prompt LLM to generate SQL
    sql_prompt = f"""You are a Snowflake SQL expert. Given the following semantic model (YAML), generate a Snowflake SQL query to answer the user's question.
<semantic_model>
{yaml_content}
</semantic_model>

User Question: {question}

Return ONLY the raw SQL query. Do not include markdown formatting like ```sql or any other text.
"""
    try:
        sql_query = _ask_via_ollama(sql_prompt).strip()
        # Clean up markdown if the LLM still included it
        if sql_query.startswith("```sql"):
            sql_query = sql_query[6:]
        if sql_query.startswith("```"):
            sql_query = sql_query[3:]
        if sql_query.endswith("```"):
            sql_query = sql_query[:-3]
        sql_query = sql_query.strip()
        
        if status:
            status.write(f"📊 **LLM Fallback:** Executing generated SQL query:\n```sql\n{sql_query}\n```")
            
        conn = _get_connector_connection()
        cursor = conn.cursor()
        cursor.execute(sql_query)
        rows = cursor.fetchmany(100)
        columns = [col[0] for col in cursor.description] if cursor.description else []
        cursor.close()
        
        # Summarize
        if status:
            status.write("🤖 **LLM Fallback:** Summarizing raw database results...")
        summary_prompt = f"You are a helpful factory assistant. The user asked: '{question}'. \nHere is the data pulled from the database:\nColumns: {columns}\nData: {rows}\n\nSummarize this data clearly for the user."
        answer = _ask_via_ollama(summary_prompt)
        
        backend = LAST_USED_LLM.get("backend", "unknown")
        model = LAST_USED_LLM.get("model", "unknown")
        reason = LAST_USED_LLM.get("reason", "Fallback")
        llm_badge = f"\n\n---\n*Answered by: **{backend}** (`{model}`) [Fallback Text-to-SQL]*"
        return answer + llm_badge
        
    except Exception as e:
        return f"**LLM Fallback Error:** Failed to generate/execute SQL or summarize. {e}"



def ask_investigative_agent(question: str, context: dict, status=None) -> str:
    """
    Hybrid Agent Router:
    1. Uses local Ollama to classify intent (Data vs Manual).
    2. If Data -> Calls Cortex Analyst REST API for Text-to-SQL.
    3. If Manual -> Uses OEM_MANUAL_CHUNKS and Ollama for unstructured RAG.
    """
    rul = context.get("rul", "Unknown")

    # ── ROUTER: Classify Intent ──
    if status:
        status.write("🧠 **LLM:** Classifying request intent...")
    try:
        intent_prompt = f"Classify the following question as either 'DATA' (asking for historical metrics, averages, trends, records) or 'MANUAL' (asking for root causes, troubleshooting, operating limits, instructions). Answer with exactly one word. Question: {question}"
        intent_classification = _ask_via_ollama(intent_prompt).strip().upper()
        
        backend = LAST_USED_LLM.get("backend", "unknown")
        if status:
            status.write(f"🧠 **Router:** Intent classified as `{intent_classification}` (via {backend})")
    except Exception as exc:
        intent_classification = "MANUAL" # Fallback if LLM is down
        if status:
            status.write(f"🧠 **Router:** Intent classified as `{intent_classification}` (Fallback)")

    if "DATA" in intent_classification:
        return _query_cortex_analyst(question, context, status=status)

    # ── UNSTRUCTURED RAG (Original Flow) ──
    if status:
        status.write("🔍 **Cortex Search:** Retrieving OEM manuals...")

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

    # 4. Try LLM
    if status:
        status.write("🤖 **LLM:** Generating final troubleshooting answer...")
        
    llm_error: str = ""
    try:
        answer = _ask_via_ollama(prompt)
        
        backend = LAST_USED_LLM.get("backend", "unknown")
        model = LAST_USED_LLM.get("model", "unknown")
        reason = LAST_USED_LLM.get("reason", "")
        
        if status:
            if backend == "snowflake_cortex":
                status.write(f"❄️ **LLM Engine:** Snowflake Cortex (`{model}`) - {reason}")
            else:
                status.write(f"🦙 **LLM Engine:** Local Ollama (`{model}`) - {reason}")
                
        llm_badge = f"\n\n---\n*Answered by: **{backend}** (`{model}`)*"
        return answer + llm_badge
    except Exception as exc:
        llm_error = str(exc)

    # 5. Hard fallback — structured summary when LLM is unreachable
    error_detail = (
        f"\n\n> ⚠️ **LLM error:** Please check logs for details.\n"
        f"> LLM backend in use: `{LAST_USED_LLM.get('backend')}`\n"
        f"> LLM fallback host: `{OLLAMA_HOST}`"
    ) if llm_error else ""
    return (
        f"**Backend Analysis** (LLM unavailable):\n\n"
        f"Your question: *\"{question}\"*\n\n"
        f"Based on the investigation data available:\n"
        f"- Equipment **{context.get('equipment_id')}** has **{rul} hours** of RUL.\n"
        f"- Priority: **{priority}** → Action: **{action}**\n"
        f"- OEM Limits: {oem_constraints}\n\n"
        f"The Investigative Agent could not generate a dynamic LLM answer because "
        f"the LLM endpoints were unreachable."
        f"{error_detail}"
    )
