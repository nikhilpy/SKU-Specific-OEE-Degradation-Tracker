import streamlit as st
import datetime
from agent_stub import ask_investigative_agent, _retrieve_oem_constraints, _classify_priority
from mcp_client import post_slack_alert
from snowflake_conn import get_active_session

st.set_page_config(page_title="Investigate", page_icon="🕵️", layout="wide")
st.title("🕵️ Investigative Agent")

# Initialize session state for chat and context
if "messages" not in st.session_state:
    st.session_state["messages"] = []

context = st.session_state.get("investigate_context", {})

if not context:
    st.info("Please select an alert from the Dashboard to start investigating.")
    st.stop()

equip_id = context.get("equipment_id", "Unknown")
triggering_sku = context.get("sku", "Unknown")
rul = context.get("rul", "Unknown")

# Classify priority / action (mirrors execute_detection/investigative_agent.py)
try:
    action, priority = _classify_priority(float(rul))
except (TypeError, ValueError):
    action, priority = "MONITOR_EQUIPMENT", "MEDIUM"

# Priority badge colours
_PRIORITY_COLOUR = {"CRITICAL": "red", "HIGH": "orange", "MEDIUM": "gold"}
badge_colour = _PRIORITY_COLOUR.get(priority, "grey")

st.subheader(f"Investigating {equip_id} (Triggered by SKU: {triggering_sku})")
col_l, col_r = st.columns(2)
with col_l:
    st.markdown(f"**Predicted Failure in:** {rul} hours")
with col_r:
    st.markdown(
        f"**Priority:** <span style='color:{badge_colour};font-weight:bold;'>"
        f"{priority}</span> &nbsp;|&nbsp; **Recommended Action:** {action}",
        unsafe_allow_html=True,
    )

st.markdown("---")

# Pre-fill initial question if empty
if not st.session_state["messages"]:
    initial_question = (
        f"What is driving the thermal stress on {equip_id} "
        f"during {triggering_sku} production runs?"
    )
    st.session_state["messages"].append(
        {"role": "user", "content": initial_question}
    )

    with st.spinner("Investigative Agent is analyzing…"):
        answer = ask_investigative_agent(initial_question, context)
        st.session_state["messages"].append(
            {"role": "assistant", "content": answer}
        )

# Display chat messages
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# ── Mitigation Action ──────────────────────────────────────────────────────
st.markdown("---")
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🚨 Mitigate Impact", type="primary"):
        # Retrieve live OEM constraints from Cortex Search Service
        oem_constraints = _retrieve_oem_constraints(equip_id)

        payload = {
            "Equipment_ID": equip_id,
            "Failure_Horizon": rul,
            "SKU_ID": triggering_sku,
            "Action": action,
            "Priority": priority,
            "OEM_Constraints": oem_constraints,
        }

        with st.spinner("Invoking Execution Agent via Slack MCP…"):
            success, result_msg = post_slack_alert(payload)

        if success:
            st.success("✅ " + result_msg)

            # Log to Snowflake ALERTS_HISTORY
            # Schema extended to capture action/priority from the backend pipeline
            session = get_active_session()
            if session:
                try:
                    # Sanitise string fields to avoid SQL injection in f-string
                    safe_equip   = str(equip_id).replace("'", "''")
                    safe_sku     = str(triggering_sku).replace("'", "''")
                    safe_action  = str(action).replace("'", "''")
                    safe_priority = str(priority).replace("'", "''")
                    safe_oem     = str(oem_constraints).replace("'", "''")[:500]

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
                    st.warning(f"Could not log alert history to Snowflake: {e}")
        else:
            st.error("❌ " + result_msg)

# ── Accept new chat input ──────────────────────────────────────────────────
if prompt := st.chat_input("Ask a follow-up question…"):
    st.session_state["messages"].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    with st.spinner("Investigative Agent is analyzing…"):
        answer = ask_investigative_agent(prompt, context)
        st.session_state["messages"].append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.write(answer)
