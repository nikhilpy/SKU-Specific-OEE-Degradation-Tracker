import streamlit as st
import datetime
from agent_stub import ask_investigative_agent
from mcp_client import post_slack_alert
from snowflake_conn import get_active_session

st.set_page_config(page_title="Investigate", page_icon="🕵️", layout="wide")
st.title("🕵️ Investigative Agent")

# Initialize session state for chat and context
if 'messages' not in st.session_state:
    st.session_state['messages'] = []
    
context = st.session_state.get('investigate_context', {})

if not context:
    st.info("Please select an alert from the Dashboard to start investigating.")
    st.stop()

st.subheader(f"Investigating {context.get('equipment_id')} (Triggered by {context.get('sku')})")
st.markdown(f"**Predicted Failure:** {context.get('rul')} hours")

# Pre-fill initial question if empty
if not st.session_state['messages']:
    initial_question = f"What is driving the thermal stress on {context.get('equipment_id')}?"
    st.session_state['messages'].append({"role": "user", "content": initial_question})
    
    with st.spinner("Investigative Agent is analyzing..."):
        answer = ask_investigative_agent(initial_question, context)
        st.session_state['messages'].append({"role": "assistant", "content": answer})

# Display chat messages
for msg in st.session_state['messages']:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Mitigation Action
st.markdown("---")
col1, col2 = st.columns([1, 4])
with col1:
    if st.button("🚨 Mitigate Impact", type="primary", use_container_width=True):
        payload = {
            "Equipment_ID": context.get('equipment_id'),
            "Failure_Horizon": context.get('rul'),
            "SKU_ID": context.get('sku'),
            "OEM_Constraints": "Max Sustained Temp: 90°C" # Stubbed constraint
        }
        
        with st.spinner("Invoking Execution Agent via Slack MCP..."):
            success, result_msg = post_slack_alert(payload)
            
        if success:
            st.success("✅ " + result_msg)
            # Log to Snowflake
            session = get_active_session()
            if session:
                try:
                    # Task 4.5.1 Create table if not exists (we do it lazily here)
                    session.sql("""
                    CREATE TABLE IF NOT EXISTS ALERTS_HISTORY (
                        TIMESTAMP TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP(),
                        EQUIPMENT_ID VARCHAR,
                        SKU_ID VARCHAR,
                        ACTION_TAKEN VARCHAR,
                        STATUS VARCHAR
                    )
                    """).collect()
                    
                    session.sql(f"""
                    INSERT INTO ALERTS_HISTORY (EQUIPMENT_ID, SKU_ID, ACTION_TAKEN, STATUS) 
                    VALUES ('{payload['Equipment_ID']}', '{payload['SKU_ID']}', 'Slack Alert Sent', 'SUCCESS')
                    """).collect()
                except Exception as e:
                    st.warning(f"Could not log alert history to Snowflake: {e}")
        else:
            st.error("❌ " + result_msg)

# Accept new chat input
if prompt := st.chat_input("Ask a follow-up question..."):
    st.session_state['messages'].append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)
        
    with st.spinner("Investigative Agent is analyzing..."):
        answer = ask_investigative_agent(prompt, context)
        st.session_state['messages'].append({"role": "assistant", "content": answer})
        with st.chat_message("assistant"):
            st.write(answer)
