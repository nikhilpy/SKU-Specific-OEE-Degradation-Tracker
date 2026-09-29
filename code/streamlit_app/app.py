import os
import streamlit as st
from wizard import is_setup_complete, render_setup_wizard

st.set_page_config(
    page_title="OEE Command Center",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 1. Check if SNOWFLAKE_ACCOUNT and SLACK_BOT_TOKEN exist in env or .env
if not is_setup_complete():
    # 2-5. Render Setup Wizard
    render_setup_wizard()
else:
    # Setup is complete - Main Command Center Overview
    from wizard import render_infrastructure_setup

    st.title("🏭 SKU-Specific OEE Degradation Tracker")
    
    if st.session_state.get("show_infra_setup", False):
        st.warning("⚠️ **Infrastructure Missing**: Database objects not found. Please run the One-Click Setup.")
        render_infrastructure_setup()
        
        st.markdown("---")
        if st.button("⬅️ Return to Main App"):
            st.session_state["show_infra_setup"] = False
            st.rerun()
        st.stop()
        
    tab1, tab2 = st.tabs(["🚀 Command Center", "🏗️ Infrastructure Setup"])

    with tab1:
        st.markdown("### 🚀 Autonomous Command Center")

        # Status Bar
        account = os.getenv("SNOWFLAKE_ACCOUNT") or "Configured"
        channel = os.getenv("SLACK_CHANNEL") or "#oee-production-alerts"
        warehouse = os.getenv("SNOWFLAKE_WAREHOUSE") or "COMPUTE_WH"

        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            st.success(f"❄️ **Snowflake Account:** `{account}`")
        with col_s2:
            st.info(f"⚡ **Warehouse:** `{warehouse}`")
        with col_s3:
            st.success(f"💬 **Slack Channel:** `{channel}`")

        st.markdown("---")

        st.markdown(
            """
            Welcome to the **OEE Degradation Command Center**!
            
            The autonomous pipeline continuously fuses **IT work orders** with **OT machine telemetry** in Snowflake, forecasting Remaining Useful Life (RUL) and triggering agentic Slack mitigations.
            """
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.markdown(
                """
                <div style="background-color: rgba(56, 189, 248, 0.08); padding: 20px; border-radius: 10px; border: 1px solid rgba(56, 189, 248, 0.3); height: 100%;">
                    <h3>📊 Live Dashboard</h3>
                    <p>Monitor converged IT/OT telemetry and real-time ML-predicted RUL alert cards for equipment degradation.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Dashboard", type="primary", use_container_width=True):
                st.switch_page("pages/1_Dashboard.py")

        with col2:
            st.markdown(
                """
                <div style="background-color: rgba(168, 85, 247, 0.08); padding: 20px; border-radius: 10px; border: 1px solid rgba(168, 85, 247, 0.3); height: 100%;">
                    <h3>🕵️ Investigate Agent</h3>
                    <p>Engage the multi-agent investigative assistant for root-cause analysis and automated Slack mitigation.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Investigative Agent", use_container_width=True):
                st.switch_page("pages/2_Investigate.py")

        with col3:
            st.markdown(
                """
                <div style="background-color: rgba(34, 197, 94, 0.08); padding: 20px; border-radius: 10px; border: 1px solid rgba(34, 197, 94, 0.3); height: 100%;">
                    <h3>📜 Alerts History</h3>
                    <p>Review the permanent audit trail of all automated mitigation actions taken by the autonomous daemon.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )
            if st.button("Open Alerts History", use_container_width=True):
                st.switch_page("pages/3_Alerts_History.py")

        st.markdown("---")

        with st.expander("⚙️ Reconfigure Credentials / Settings"):
            st.caption("Need to update your Snowflake or Slack settings?")
            if st.button("Modify Connection Settings"):
                st.session_state["force_setup"] = True
                st.session_state["setup_complete"] = False
                st.rerun()

    with tab2:
        render_infrastructure_setup()

