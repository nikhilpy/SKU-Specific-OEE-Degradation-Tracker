import streamlit as st
import pandas as pd
from snowflake_conn import get_active_session

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")
st.title("📊 IT/OT Data Grid & Alerts")

session = get_active_session()
if not session:
    st.stop()

# --- Predictive Alert Cards ---
st.subheader("🚨 Predictive Alerts")
try:
    rul_df = session.sql("SELECT * FROM ASSET_RUL_PREDICTIONS ORDER BY RUL_HOURS ASC").to_pandas()
    if rul_df.empty:
        st.success("No predicted failures in the next 72 hours.")
    else:
        cols = st.columns(len(rul_df))
        for idx, row in rul_df.iterrows():
            with cols[idx]:
                equip_id = row['EQUIPMENT_ID']
                rul = row['RUL_HOURS']
                
                # Fetch current SKU for this equipment
                sku_df = session.sql(f"SELECT SKU_ID FROM IT_OT_CONVERGED WHERE EQUIPMENT_ID = '{equip_id}' ORDER BY TIMESTAMP DESC LIMIT 1").to_pandas()
                triggering_sku = sku_df['SKU_ID'].iloc[0] if not sku_df.empty else "Unknown"

                color = "red" if rul < 48 else "orange"
                st.markdown(f"""
                <div style="padding: 15px; border-radius: 10px; border: 2px solid {color}; background-color: rgba(255,0,0,0.1);">
                    <h4>{equip_id}</h4>
                    <p style="font-size: 24px; font-weight: bold; color: {color}; margin:0;">{rul} Hours to Failure</p>
                    <p style="margin-top: 5px;"><strong>Active SKU:</strong> {triggering_sku}</p>
                </div>
                """, unsafe_allow_html=True)
                
                if st.button(f"Investigate {equip_id}", key=f"inv_{equip_id}"):
                    st.session_state['investigate_context'] = {
                        "equipment_id": equip_id,
                        "sku": triggering_sku,
                        "rul": rul
                    }
                    st.switch_page("pages/2_Investigate.py")
except Exception as e:
    st.warning("Could not load RUL predictions. Has 04-rul.sql been run?")
    st.write(e)

st.markdown("---")

# --- IT/OT Joined Data Grid ---
st.subheader("🏭 Converged Factory Telemetry (IT + OT)")
try:
    data_df = session.sql("SELECT * FROM IT_OT_CONVERGED ORDER BY TIMESTAMP DESC LIMIT 200").to_pandas()
    
    # Filter widgets
    col1, col2 = st.columns(2)
    with col1:
        equipment_filter = st.multiselect("Filter by Equipment", data_df['EQUIPMENT_ID'].unique())
    with col2:
        sku_filter = st.multiselect("Filter by SKU", data_df['SKU_ID'].unique())
        
    if equipment_filter:
        data_df = data_df[data_df['EQUIPMENT_ID'].isin(equipment_filter)]
    if sku_filter:
        data_df = data_df[data_df['SKU_ID'].isin(sku_filter)]
        
    # Render table with column formatting
    st.dataframe(
        data_df,
        use_container_width=True,
        column_config={
            "TEMPERATURE_C": st.column_config.ProgressColumn("Temperature (°C)", format="%.1f", min_value=0, max_value=120),
            "VIBRATION_RMS": st.column_config.ProgressColumn("Vibration (RMS)", format="%.2f", min_value=0, max_value=5.0),
        }
    )
except Exception as e:
    st.error(f"Could not load converged data: {e}")
