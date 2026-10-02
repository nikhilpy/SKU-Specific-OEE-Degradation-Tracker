import asyncio
import concurrent.futures
import os
import sys

from dotenv import load_dotenv
from pydantic import ValidationError

# ── Path setup ────────────────────────────────────────────────────────────────
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_CODE_ROOT = os.path.dirname(_CURRENT_DIR)

for path in (_CURRENT_DIR, os.path.join(_CODE_ROOT, "misc"), os.path.join(_CODE_ROOT, "llm_setup")):
    if path not in sys.path:
        sys.path.insert(0, path)

from schemas import DiagnosticState, OEMValidation, MitigationDecision
from data_provider import SnowflakeDataProvider
from snowflake_client import FALLBACK_OEM_EVIDENCE

# Load .env from project root
_ENV_PATH = os.path.join(
    os.path.dirname(_CODE_ROOT),
    ".env",
)
load_dotenv(_ENV_PATH)

# ── OEM Hard Caps (Enterprise Guardrails) ──────────────────────────────────────
OEM_HARD_CAP_TEMP = 90.0        # 90 °C
OEM_HARD_CAP_VIBRATION = 2.3     # 2.3 mm/s

# ── Execution Agent system prompt ─────────────────────────────────────────────
EXECUTION_AGENT_SYSTEM_PROMPT = (
    "You are an Execution Agent. "
    "Use the slack_post_message tool to send a comprehensive mitigation alert to the "
    "#oee-production-alerts channel. "
    "You MUST format the message EXACTLY following this Slack markdown template (use single asterisks * for bolding, NO double asterisks, NO hashes):\n\n"
    "🚨 *Mitigation Alert: Equipment Failure Detected*\n\n"
    "*Equipment ID*: <id>\n"
    "*Active SKU*: <sku>\n"
    "*Predicted RUL*: <rul> hours\n"
    "*Priority*: <priority>\n"
    "*Recommended Action*: <action>\n"
    "*Current Telemetry*: Temp=<temp> C, Vibration=<vib> mm/s\n"
    "*Justification/Cause*: <cause>\n"
    "*OEM Constraints*: <constraints>"
)

# ── Helpers & Telemetry ───────────────────────────────────────────────────────

def get_active_sku(equipment_id: str, data_provider) -> str | None:
    """Return the most recently active SKU for the given equipment."""
    try:
        batch = data_provider.get_active_batch(equipment_id)
        if batch:
            return batch.get("SKU_ID")
    except Exception:
        pass
    return None


def get_latest_telemetry(equipment_id: str, data_provider) -> dict:
    """Retrieve latest telemetry readings for current temperature and vibration."""
    try:
        df = data_provider.get_recent_telemetry(equipment_id, limit=1)
        if not df.empty:
            return {
                "temperature": float(df["Temperature"].iloc[0]),
                "vibration": float(df["Vibration"].iloc[0]),
                "sku": None,
            }
    except Exception:
        pass
    return {"temperature": None, "vibration": None, "sku": None}


def _oem_to_text(oem_evidence, dynamic_temp_cap=OEM_HARD_CAP_TEMP, dynamic_vib_cap=OEM_HARD_CAP_VIBRATION) -> str:
    """Flatten the OEM evidence dict/string to a concise plain-text constraint without raw LaTeX chunks."""
    source = "OEM Hard Caps"
    
    if isinstance(oem_evidence, dict):
        chunks = oem_evidence.get("chunks", [])
        if chunks:
            import re
            best_chunk = chunks[0]
            file_name = best_chunk.get("file_name", "OEM Manual")
            chunk_idx = best_chunk.get("chunk_index", 0)
            page_approx = (chunk_idx // 2) + 1
            
            # Clean LaTeX from chunk text to provide a search snippet
            raw_text = best_chunk.get("text", "")
            clean_text = re.sub(r'\$.*?\$', '', raw_text)
            clean_text = re.sub(r'\\[a-zA-Z]+\{.*?\}', '', clean_text)
            clean_text = clean_text.replace('^', '').replace('{', '').replace('}', '').strip()
            
            snippet = f'"{clean_text[:80]}..."' if clean_text else ""
            
            source = f"{file_name}, Page ~{page_approx} (Look for: {snippet})"
        else:
            source = oem_evidence.get("source", "OEM Manual")
        
    return f"Maximum allowed Temperature is {dynamic_temp_cap} °C and Maximum allowed Vibration is {dynamic_vib_cap} mm/s.\n*Reference*: {source}"


# ── Defensive OEM Validation & Cortex Chunk Handling ──────────────────────────

def validate_oem_evidence(
    oem_evidence: dict | None,
    current_temp: float | None = None,
    current_vibration: float | None = None,
) -> tuple[OEMValidation, str]:
    """
    Validate OEM manual search chunks with Pydantic OEMValidation.
    If Cortex Search chunks are missing, returns OEMValidation with status
    'DEGRADED_LOCAL_HEURISTIC' and falls back to OEM hard caps (90°C, 2.3 mm/s).
    """
    chunks_found = False
    citation_source = "OEM_MANUAL_CHUNKS"
    status = "OPTIMAL_RETRIEVAL"
    
    # We will use the dynamically fetched caps as the defaults
    # but the logic below can still extract from evidence if available.
    max_temp = getattr(validate_oem_evidence, 'dynamic_temp_cap', OEM_HARD_CAP_TEMP)
    max_vib = getattr(validate_oem_evidence, 'dynamic_vib_cap', OEM_HARD_CAP_VIBRATION)

    if isinstance(oem_evidence, dict):
        chunks = oem_evidence.get("chunks", [])
        if chunks:
            chunks_found = True
            citation_source = str(oem_evidence.get("source", "OEM_MANUAL_CHUNKS"))
            for ev in oem_evidence.get("evidence", []):
                param = ev.get("parameter", "").lower()
                if "temp" in param:
                    try:
                        max_temp = float(ev.get("limit", max_temp))
                    except (ValueError, TypeError):
                        pass
                elif "vib" in param:
                    try:
                        max_vib = float(ev.get("limit", max_vib))
                    except (ValueError, TypeError):
                        pass
        else:
            status = "DEGRADED_LOCAL_HEURISTIC"
            citation_source = "DEGRADED_LOCAL_HEURISTIC"
    else:
        status = "DEGRADED_LOCAL_HEURISTIC"
        citation_source = "DEGRADED_LOCAL_HEURISTIC"

    if not chunks_found:
        status = "DEGRADED_LOCAL_HEURISTIC"

    breach = False
    if current_temp is not None and current_temp >= max_temp:
        breach = True
    if current_vibration is not None and current_vibration >= max_vib:
        breach = True

    validation = OEMValidation(
        max_temp_limit=max_temp,
        max_vibration_limit=max_vib,
        citation_source=citation_source,
        breach_detected=breach,
        status=status,
    )
    return validation, status


# ── Deterministic Rule-Based Fallback ──────────────────────────────────────────

def deterministic_rule_evaluation(
    equipment_id: str,
    sku: str | None,
    rul_hours: float,
    current_temp: float | None = None,
    current_vibration: float | None = None,
    dynamic_temp_cap: float = 90.0,
    dynamic_vib_cap: float = 2.3,
) -> MitigationDecision:
    """
    Deterministic rule-based evaluation using the OEM manual hard caps.
    Enforces enterprise guardrail fallback when LLM parsing fails or produces hallucinated fields.
    """
    breaches = []
    if current_temp is not None and current_temp >= dynamic_temp_cap:
        breaches.append(f"Temperature {current_temp:.1f}°C >= {dynamic_temp_cap}°C hard cap")
    if current_vibration is not None and current_vibration >= dynamic_vib_cap:
        breaches.append(f"Vibration {current_vibration:.2f} mm/s >= {dynamic_vib_cap} mm/s hard cap")

    if rul_hours <= 6.0 or breaches:
        priority = "CRITICAL"
        action = "IMMEDIATE_MAINTENANCE"
        detail = "; ".join(breaches) if breaches else f"RUL ({rul_hours:.2f}h) <= 6.0h critical threshold"
        justification = (
            f"[Deterministic OEM Hard Cap Fallback] Equipment {equipment_id} safety threshold exceeded: "
            f"{detail}. Hard caps: {dynamic_temp_cap}°C, {dynamic_vib_cap} mm/s."
        )
    elif rul_hours <= 24.0:
        priority = "HIGH"
        action = "SCHEDULE_MAINTENANCE"
        justification = (
            f"[Deterministic OEM Hard Cap Fallback] Equipment {equipment_id} predicted failure within "
            f"24h operational envelope ({rul_hours:.2f}h). Maintenance scheduling dispatched."
        )
    else:
        priority = "MEDIUM"
        action = "MONITOR_EQUIPMENT"
        justification = (
            f"[Deterministic OEM Hard Cap Fallback] Equipment {equipment_id} telemetry within acceptable "
            f"parameters (RUL: {rul_hours:.2f}h > 24h). Continue active monitoring."
        )

    return MitigationDecision(
        priority=priority,
        action=action,
        target_sku=sku or "UNKNOWN",
        justification=justification,
        approved_for_dispatch=True,
    )


# ── Defensive LLM Parsing with Pydantic Guardrails ────────────────────────────

def parse_and_validate_llm_mitigation(
    equipment_id: str,
    sku: str | None,
    rul_hours: float,
    current_temp: float | None,
    current_vibration: float | None,
    oem_text: str,
    dynamic_temp_cap: float = 90.0,
    dynamic_vib_cap: float = 2.3,
) -> MitigationDecision:
    """
    Query the LLM to assess mitigation priority and action, wrapping parsing
    in a try/except validator using Pydantic (MitigationDecision).
    """
    prompt = f"""You are a Manufacturing Reliability AI Agent. Analyze this failure incident and output a mitigation decision JSON.

<Incident Context>
Equipment ID: {equipment_id}
Active SKU: {sku or 'UNKNOWN'}
Predicted RUL: {round(rul_hours, 2)} hours
Telemetry: Temp={current_temp if current_temp is not None else 'Unknown'} C, Vibration={current_vibration if current_vibration is not None else 'Unknown'} mm/s
OEM Constraints: {oem_text}
OEM Hard Caps: {round(dynamic_temp_cap, 1)} C Temperature, {round(dynamic_vib_cap, 1)} mm/s Vibration
</Incident Context>

Respond ONLY with a JSON object containing EXACTLY these keys:
- "priority": one of ["CRITICAL", "HIGH", "MEDIUM"]
- "action": one of ["IMMEDIATE_MAINTENANCE", "SCHEDULE_MAINTENANCE", "MONITOR_EQUIPMENT"]
- "target_sku": string or null
- "justification": string explaining root cause and recommendation
- "approved_for_dispatch": boolean (true if alert should be dispatched)
"""
    try:
        from llm import ask_json
        
        full_prompt = f"You are a deterministic reliability engineering assistant. Output JSON only.\n\n{prompt}"
        parsed_dict = ask_json(full_prompt, temperature=0.1)
        # Strict validation with extra='forbid' catches hallucinated non-existent fields
        validated_decision = MitigationDecision.model_validate(parsed_dict)
        print(f"[Agent] Guardrail check PASSED: Validated LLM decision ({validated_decision.priority} | {validated_decision.action})")
        return validated_decision

    except (ValidationError, json.JSONDecodeError, KeyError, Exception) as exc:
        print(f"[Guardrail Alert] LLM parsing/schema error: {exc}")
        print(f"[Guardrail Alert] Falling back to deterministic rule-based evaluation using OEM hard caps ({dynamic_temp_cap}°C, {dynamic_vib_cap} mm/s).")
        return deterministic_rule_evaluation(
            equipment_id=equipment_id,
            sku=sku,
            rul_hours=rul_hours,
            current_temp=current_temp,
            current_vibration=current_vibration,
            dynamic_temp_cap=dynamic_temp_cap,
            dynamic_vib_cap=dynamic_vib_cap,
        )


# ── MCP tool execution (async) ─────────────────────────────────────────────────

async def _mcp_slack_post(channel_id: str, text: str) -> str:
    """
    Spawn the Slack MCP server over stdio and call slack_post_message.
    Returns the tool result as a string.
    """
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_params = StdioServerParameters(
        command="npx",
        args=["-y", "@modelcontextprotocol/server-slack"],
        env={
            "SLACK_BOT_TOKEN": os.getenv("SLACK_BOT_TOKEN", ""),
            "SLACK_TEAM_ID":   os.getenv("SLACK_TEAM_ID", ""),
        },
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool(
                "slack_post_message",
                {"channel_id": channel_id, "text": text},
            )
            return str(result)


def _run_mcp_tool(channel_id: str, text: str) -> str:
    """
    Bridge between sync caller and async MCP client.
    Handles both fresh event loops (scripts) and running loops (Streamlit).
    """
    try:
        return asyncio.run(_mcp_slack_post(channel_id, text))
    except RuntimeError:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, _mcp_slack_post(channel_id, text))
            return future.result(timeout=60)


# ── Autonomous Execution Agent ─────────────────────────────────────────────────

def _run_execution_agent(context: dict) -> dict:
    """
    Autonomous CoCo Execution Agent.
    Composes a structured mitigation alert and sends it to Slack via
    the Slack MCP server over stdio.
    """
    equipment_id = context["equipment_id"]
    rul_hours    = context["rul_hours"]
    sku          = context.get("sku") or "UNKNOWN"
    priority     = context["priority"]
    action       = context["action"]
    justification = context.get("justification", "Not provided")
    current_temp = context.get("current_temp", "Unknown")
    current_vib  = context.get("current_vib", "Unknown")
    oem_text     = _oem_to_text(context.get("oem_evidence"))
    channel      = os.getenv("SLACK_CHANNEL", "#oee-production-alerts")

    alert_text = (
        "🚨 *Mitigation Alert: Equipment Failure Detected*\n\n"
        f"*Equipment ID*: {equipment_id}\n"
        f"*Active SKU*: {sku}\n"
        f"*Predicted RUL*: {rul_hours:.2f} hours\n"
        f"*Priority*: {priority}\n"
        f"*Recommended Action*: {action}\n"
        f"*Current Telemetry*: Temp={current_temp} C, Vibration={current_vib} mm/s\n"
        f"*Justification/Cause*: {justification}\n"
        f"*OEM Constraints*: {oem_text}\n"
        f"*ACTION REQUIRED*: Initiate {action.replace('_', ' ').title()} immediately."
    )

    print("\n===== EXECUTION AGENT (MCP Mode) =====")
    print(f"[Agent] System prompt active: Execution Agent")
    print(f"[Agent] Context: {equipment_id} | RUL={rul_hours:.2f}h | {priority}")
    print(f"[Agent] Dispatching Slack alert to {channel}")

    try:
        print(f"[Agent] Calling slack_post_message via MCP stdio transport...")
        mcp_result = _run_mcp_tool(
            channel_id=channel,
            text=alert_text,
        )
        print(f"[Agent] ✅ Slack alert delivered. MCP result: {mcp_result}")
        return {
            "status":       "ALERT_SENT",
            "channel":      channel,
            "equipment_id": equipment_id,
            "rul_hours":    rul_hours,
            "priority":     priority,
            "action":       action,
            "mcp_result":   mcp_result,
        }

    except Exception as exc:
        print(f"[Agent] ❌ MCP tool call failed: {exc}")
        return {
            "status":       "ALERT_FAILED",
            "equipment_id": equipment_id,
            "rul_hours":    rul_hours,
            "priority":     priority,
            "action":       action,
            "error":        str(exc),
        }


# ── Public Entry Point ────────────────────────────────────────────────────────

def investigate(diagnosis: dict | DiagnosticState, oem_evidence=None, data_provider=None) -> dict:
    """
    Investigate a failure diagnosis with schema defense & enterprise guardrails.

    Parameters
    ----------
    diagnosis : dict | DiagnosticState
        Must contain: failure_flag, equipment_id, rul_hours, predicted_failure_time
    oem_evidence : dict | None
        Pre-fetched OEM evidence; fetched from Snowflake/Cortex if omitted.
    data_provider : BaseDataProvider | None
        Data provider for telemetry and SKU lookup. Defaults to SnowflakeDataProvider.

    Returns
    -------
    dict  Agent outcome containing:
        - status: 'ALERT_SENT' / 'ALERT_FAILED' / 'DEGRADED_LOCAL_HEURISTIC'
        - STATUS: 'DEGRADED_LOCAL_HEURISTIC' if Cortex Search chunks missing, else 'OPTIMAL_RETRIEVAL'
        - priority, action, justification, oem_validation, mitigation_decision
    """
    # 0. Coerce diagnosis to dict
    if isinstance(diagnosis, DiagnosticState):
        diag_dict = diagnosis.model_dump()
    else:
        diag_dict = dict(diagnosis)

    if not diag_dict.get("failure_flag", True):
        return {
            "status": "NO_INVESTIGATION_REQUIRED",
            "STATUS": "NO_INVESTIGATION_REQUIRED",
        }

    equipment_id = str(diag_dict.get("equipment_id", "LINE-2-PACKAGING"))
    rul = float(diag_dict.get("rul_hours", 0.0))

    if data_provider is None:
        data_provider = SnowflakeDataProvider()
        
    dynamic_temp_cap = OEM_HARD_CAP_TEMP
    dynamic_vib_cap = OEM_HARD_CAP_VIBRATION
    try:
        if hasattr(data_provider, '_get_df'):
            df = data_provider._get_df("SELECT COALESCE(MAX(MAX_TEMP_LIMIT), 90.0) AS T, COALESCE(MAX(MAX_VIBRATION_LIMIT), 2.3) AS V FROM OEM_EQUIPMENT_THRESHOLDS")
            if not df.empty:
                dynamic_temp_cap = float(df.iloc[0]['T'])
                dynamic_vib_cap = float(df.iloc[0]['V'])
    except Exception:
        pass

    # 1. Telemetry and Active SKU
    telemetry = get_latest_telemetry(equipment_id, data_provider)
    sku = diag_dict.get("sku") or telemetry.get("sku") or get_active_sku(equipment_id, data_provider) or "UNKNOWN"
    current_temp = diag_dict.get("temperature")
    if current_temp is None:
        current_temp = diag_dict.get("current_val") if diag_dict.get("metric") == "temperature" else telemetry.get("temperature")
        
    current_vib = diag_dict.get("vibration")
    if current_vib is None:
        current_vib = diag_dict.get("current_val") if diag_dict.get("metric") == "vibration" else telemetry.get("vibration")

    # 2. OEM Manual Retrieval (never crash on missing Cortex search chunks)
    if oem_evidence is None:
        try:
            oem_evidence = data_provider.search_oem_manual(
                f"OEM operating limits for {equipment_id}, temperature and vibration"
            )
        except Exception as exc:
            print(f"[Agent] OEM manual retrieval error: {exc}. Using fallback.")
            oem_evidence = FALLBACK_OEM_EVIDENCE

    # 3. Guardrail Schema Defense: Validate OEM Evidence Chunks
    # Monkey-patch dynamic caps for the validate_oem_evidence function
    validate_oem_evidence.dynamic_temp_cap = dynamic_temp_cap
    validate_oem_evidence.dynamic_vib_cap = dynamic_vib_cap
    oem_validation, oem_status = validate_oem_evidence(
        oem_evidence,
        current_temp=current_temp,
        current_vibration=current_vib,
    )

    # 4. Guardrail Schema Defense: Validate LLM Mitigation with Pydantic
    decision = parse_and_validate_llm_mitigation(
        equipment_id=equipment_id,
        sku=sku,
        rul_hours=rul,
        current_temp=current_temp,
        current_vibration=current_vib,
        oem_text=_oem_to_text(oem_evidence, dynamic_temp_cap, dynamic_vib_cap),
        dynamic_temp_cap=dynamic_temp_cap,
        dynamic_vib_cap=dynamic_vib_cap,
    )

    # 5. Dispatch Mitigation Alert via MCP
    exec_result = _run_execution_agent({
        "equipment_id":          equipment_id,
        "sku":                   sku,
        "rul_hours":             rul,
        "predicted_failure_time": diag_dict.get("predicted_failure_time", ""),
        "priority":              decision.priority,
        "action":                decision.action,
        "justification":         diag_dict.get("reason", decision.justification),
        "current_temp":          current_temp,
        "current_vib":           current_vib,
        "oem_evidence":          oem_evidence,
    })

    # 6. Assemble Final Protected Response
    final_result = {
        **exec_result,
        "STATUS":                oem_status,  # Explicit 'DEGRADED_LOCAL_HEURISTIC' on missing chunks
        "priority":              decision.priority,
        "action":                decision.action,
        "justification":         decision.justification,
        "oem_validation":        oem_validation.model_dump(),
        "mitigation_decision":   decision.model_dump(),
    }

    # If alert failed or under degraded heuristic without MCP delivery, expose status
    if final_result.get("status") != "ALERT_SENT" and oem_status == "DEGRADED_LOCAL_HEURISTIC":
        final_result["status"] = "DEGRADED_LOCAL_HEURISTIC"

    return final_result


if __name__ == "__main__":
    print(investigate({
        "failure_flag":          True,
        "equipment_id":          "LINE-2-PACKAGING",
        "rul_hours":             0.39,
        "predicted_failure_time": "1900-01-01 16:23:18.561151079",
        "reason":                "Predicted RUL (0.39 hours) is below the 24-hour threshold",
        "next_agent":            "investigative_agent",
    }))