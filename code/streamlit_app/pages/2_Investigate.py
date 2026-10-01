import datetime
import os
import sys

import streamlit as st

# ── Path: make execute_detection importable from streamlit_app/pages/ ─────────
_EXEC_DETECTION_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "execute_detection",
)
if _EXEC_DETECTION_PATH not in sys.path:
    sys.path.insert(0, _EXEC_DETECTION_PATH)

import importlib
from investigative_agent import investigate  # noqa: E402  (CoCo Execution Agent)
import investigative_agent
importlib.reload(investigative_agent)

from agent_stub import ask_investigative_agent, _retrieve_oem_constraints, _classify_priority, _ask_via_ollama
import json
from snowflake_conn import get_active_session
from wizard import require_setup, require_infrastructure

# ─────────────────────────────────────────────────────────────────────────────
st.set_page_config(page_title="Investigate", page_icon="🕵️", layout="wide")

# Ensure setup is complete before accessing page
require_setup()

# Ensure database objects exist
session = get_active_session()
if session:
    require_infrastructure(session)

@st.cache_data
def generate_investigation_questions(equip_id, triggering_sku, rul):
    prompt = f"""
You are an expert manufacturing investigative agent. An alert has been triggered for equipment {equip_id} during the production of {triggering_sku} with a predicted Remaining Useful Life (RUL) of {rul} hours.

Generate exactly 3 practical analytical questions an engineer could ask to troubleshoot this specific alert. The questions MUST be simple and answerable using basic SQL queries on equipment sensor telemetry (temperature, vibration) and SKU data. Do NOT ask for complex multi-layered analyses, as the database only contains simple time-series sensor data and basic equipment information.

Return your response in EXACTLY this JSON format (no markdown, no backticks, just the JSON):
{{
  "questions": [
    "Question 1?",
    "Question 2?",
    "Question 3?"
  ]
}}
"""
    try:
        response = _ask_via_ollama(prompt).strip()
        if response.startswith("```json"):
            response = response[7:]
        if response.startswith("```"):
            response = response[3:]
        if response.endswith("```"):
            response = response[:-3]
        return json.loads(response.strip())["questions"]
    except Exception as e:
        return [
            f"What specific sensor telemetry is driving the RUL drop for {equip_id} while producing {triggering_sku}?",
            f"Are there historical patterns of thermal or vibration stress for {equip_id} with similar SKUs?",
            f"Based on OEM constraints, what are the immediate corrective actions to stabilize {equip_id}?"
        ]

st.title("🕵️ Investigative Agent")

demo_mode = st.sidebar.toggle("🛠️ Demo Mode (Mock Data)", value=False)

if demo_mode:
    from data_provider import MockDataProvider
    data_provider = MockDataProvider()
    context = {
        "equipment_id": "LINE-2-PACKAGING",
        "sku": "SKU-899",
        "rul": 0.39,
        "temperature": 94.5,
        "vibration": 2.4,
    }
    st.sidebar.info("Demo Mode Active: Bypassing Snowflake ML Forecast.")
else:
    from data_provider import SnowflakeDataProvider
    data_provider = SnowflakeDataProvider()
    context = st.session_state.get("investigate_context", {})

if not context:
    st.info("Please select an alert from the Dashboard to start investigating.")
    st.stop()

equip_id       = context.get("equipment_id", "Unknown")
triggering_sku = context.get("sku", "Unknown")
rul            = context.get("rul", "Unknown")

# Clear chat history if the investigation context changes
current_context_id = f"{equip_id}_{triggering_sku}_{demo_mode}"
if st.session_state.get("_investigate_context_id") != current_context_id:
    st.session_state["messages"] = []
    st.session_state["_investigate_context_id"] = current_context_id

# Initialize session state for messages if not present
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Classify priority / action (mirrors execute_detection/investigative_agent.py)
try:
    action, priority = _classify_priority(float(rul))
except (TypeError, ValueError):
    action, priority = "MONITOR_EQUIPMENT", "MEDIUM"

# Priority badge colours
_PRIORITY_COLOUR = {"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "gold"}
badge_colour = _PRIORITY_COLOUR.get(priority, "grey")

st.subheader(f"Investigating {equip_id} (Triggered by SKU: {triggering_sku})")

try:
    rul_float = float(rul)
    hours = int(rul_float)
    minutes = int(round((rul_float - hours) * 60))
    if hours > 0 and minutes > 0:
        rul_display = f"{hours} hour{'s' if hours != 1 else ''} and {minutes} minute{'s' if minutes != 1 else ''}"
    elif hours > 0:
        rul_display = f"{hours} hour{'s' if hours != 1 else ''}"
    else:
        rul_display = f"{minutes} minute{'s' if minutes != 1 else ''}"
except (ValueError, TypeError):
    rul_display = f"{rul} hours"

col_l, col_r = st.columns(2)
with col_l:
    st.markdown(f"**Predicted Failure in:** {rul_display}")
with col_r:
    st.markdown(
        f"**Priority:** <span style='color:{badge_colour};font-weight:bold;'>"
        f"{priority}</span> &nbsp;|&nbsp; **Recommended Action:** {action}",
        unsafe_allow_html=True,
    )

st.markdown("---")

# --- Suggested Questions ---
st.markdown("### Suggested Troubleshooting Questions")
with st.spinner("🧠 Agent is generating troubleshooting questions..."):
    suggested_questions = generate_investigation_questions(equip_id, triggering_sku, rul)

for i, question in enumerate(suggested_questions):
    if st.button(question, use_container_width=True, key=f"q_btn_{i}"):
        st.session_state["messages"].append({"role": "user", "content": question})
        
        with st.status("🧠 Agent is analyzing the request...", expanded=True) as status_box:
            answer = ask_investigative_agent(question, context, status=status_box)
            status_box.update(label="Analysis complete!", state="complete", expanded=False)
            
        st.session_state["messages"].append({"role": "assistant", "content": answer})
        st.rerun()

st.markdown("---")

# Display chat messages
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ── Mitigate Impact — CoCo Execution Agent ────────────────────────────────────
st.markdown("---")
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🚨 Mitigate Impact", type="primary"):

        # Try to get latest telemetry directly from Snowflake
        current_temp, current_vib = None, None
        try:
            telemetry_query = f"SELECT TEMPERATURE_C, VIBRATION_RMS FROM IT_OT_CONVERGED WHERE EQUIPMENT_ID = '{equip_id}' ORDER BY TIMESTAMP DESC LIMIT 1"
            telemetry_df = session.sql(telemetry_query).to_pandas()
            if not telemetry_df.empty:
                current_temp = float(telemetry_df["TEMPERATURE_C"].iloc[0])
                current_vib = float(telemetry_df["VIBRATION_RMS"].iloc[0])
        except Exception:
            pass

        diagnosis = {
            "failure_flag":           True,
            "equipment_id":           equip_id,
            "sku":                    triggering_sku,
            "rul_hours":              float(rul) if str(rul).replace(".", "").isdigit() else 0.0,
            "predicted_failure_time": str(datetime.datetime.now()),
            "reason":                 context.get("predictive_cause", "Degradation alert triggered from dashboard"),
            "temperature":            current_temp,
            "vibration":              current_vib
        }

        # ── st.status() streams each agent reasoning step to the UI ──────────
        with st.status(
            "🤖 Execution Agent is running…", expanded=True
        ) as agent_status:

            st.write("🔍 **Step 1** — Analyzing investigation context...")
            st.caption(
                f"Equipment: `{equip_id}` | SKU: `{triggering_sku}` "
                f"| Predicted RUL: `{rul}` hours | Priority: `{priority}`"
            )

            st.write("📚 **Step 2** — Retrieving OEM constraints from Snowflake...")
            st.caption(
                "Querying `OEM_MANUAL_CHUNKS` via keyword-ranked Cortex search."
            )

            st.write("🤖 **Step 3** — Agent is deciding on tools...")
            st.caption(
                f"System prompt active: *'You are an Execution Agent. "
                f"Use the slack_post_message tool to send a mitigation alert "
                f"to the #oee-production-alerts channel…'*"
            )

            st.write("📨 **Step 4** — Calling `slack_post_message` via MCP stdio transport...")
            st.caption(
                "Spawning `@modelcontextprotocol/server-slack` subprocess → "
                "JSON-RPC over stdin/stdout."
            )

            # ── Invoke the autonomous CoCo Execution Agent ────────────────────
            result = investigate(diagnosis, data_provider=data_provider)

            # ── Render outcome in the status container ────────────────────────
            if result.get("status") == "ALERT_SENT":
                st.write(
                    f"✅ **Alert delivered** to `{result.get('channel', '#oee-production-alerts')}`"
                )
                agent_status.update(
                    label="✅ Execution Agent: Alert Delivered!",
                    state="complete",
                    expanded=False,
                )
            else:
                error_detail = result.get("error", "Unknown MCP error")
                print(f"MCP tool call failed: {error_detail}")
                st.write("❌ **MCP tool call failed.** Check logs for details.")
                agent_status.update(
                    label="❌ Execution Agent: Alert Failed",
                    state="error",
                    expanded=True,
                )

        # ── Show result banner outside the status box ─────────────────────────
        if result.get("status") == "ALERT_SENT":
            st.success(
                f"🚨 Slack alert posted to **{result.get('channel')}** | "
                f"Priority: **{result.get('priority')}** | "
                f"Action: **{result.get('action')}**"
            )

            # ── Log to Snowflake ALERTS_HISTORY ──────────────────────────────
            session = get_active_session()
            if session:
                try:
                    oem_text = _retrieve_oem_constraints(equip_id)

                    safe_equip    = str(equip_id).replace("'", "''")
                    safe_sku      = str(triggering_sku).replace("'", "''")
                    safe_action   = str(result.get("action", action)).replace("'", "''")
                    safe_priority = str(result.get("priority", priority)).replace("'", "''")
                    safe_oem      = str(oem_text).replace("'", "''")[:500]

                    session.sql(f"""
                        INSERT INTO ALERTS_HISTORY
                            (EQUIPMENT_ID, SKU_ID, ACTION_TAKEN, PRIORITY,
                             RUL_HOURS, OEM_CONSTRAINTS, STATUS)
                        VALUES
                            ('{safe_equip}', '{safe_sku}', '{safe_action}',
                             '{safe_priority}', {float(rul)},
                             '{safe_oem}', 'SUCCESS')
                    """).collect()

                except Exception as e:
                    print(f"Could not log alert history to Snowflake: {e}")
                    st.warning("Could not log alert history to Snowflake. Check logs for details.")

        else:
            print(f"Alert could not be sent. Error: {result.get('error', 'Unknown MCP error')}")
            st.warning("❌ Alert could not be sent. Please check logs for details.")

# ── Accept new chat input ──────────────────────────────────────────────────────
if prompt := st.chat_input("Ask a follow-up question…"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.status("🧠 Agent is analyzing the request...", expanded=True) as status_box:
        answer = ask_investigative_agent(prompt, context, status=status_box)
        status_box.update(label="Analysis complete!", state="complete", expanded=False)
        
    st.session_state["messages"].append({"role": "assistant", "content": answer})
    with st.chat_message("assistant"):
        st.write(answer)
