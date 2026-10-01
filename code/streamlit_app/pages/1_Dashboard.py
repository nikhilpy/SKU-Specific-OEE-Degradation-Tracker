import os
import sys
import streamlit as st
import pandas as pd

# Ensure parent directory is in sys.path for wizard import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wizard import require_setup, require_infrastructure
from snowflake_conn import get_active_session

st.set_page_config(page_title="Dashboard", page_icon="📊", layout="wide")

# Ensure setup is complete before accessing page
require_setup()

st.title("📊 IT/OT Data Grid & Alerts")

if st.session_state.get("pdf_upload_success"):
    st.success("✅ New OEM manual successfully uploaded, parsed, and chunked. Predictions have been updated.")
    st.session_state.pdf_upload_success = False


session = get_active_session()
if not session:
    st.stop()

require_infrastructure(session)

# --- Predictive Alert Cards ---
st.subheader("🚨 Predictive Alerts")
try:
    demo_mode = st.sidebar.toggle("🛠️ Demo Alerts Mode (Synthetic Data)", value=False)
    if demo_mode:
        st.sidebar.info("Demo Alerts Active: Showing Critical, High, and Medium synthetic failures.")
        rul_df = pd.DataFrame([
            {
                "EQUIPMENT_ID": "LINE-1-FILLER",
                "PREDICTED_FAILURE_TIMESTAMP": pd.Timestamp.now() + pd.Timedelta(hours=4.5),
                "RUL_HOURS": 4.5,
                "PREDICTIVE_CAUSE": "Temperature Forecast Breach (Synthetic)"
            },
            {
                "EQUIPMENT_ID": "LINE-2-PACKAGING",
                "PREDICTED_FAILURE_TIMESTAMP": pd.Timestamp.now() + pd.Timedelta(hours=18.5),
                "RUL_HOURS": 18.5,
                "PREDICTIVE_CAUSE": "Vibration Forecast Breach (Synthetic)"
            },
            {
                "EQUIPMENT_ID": "LINE-3-MIXER",
                "PREDICTED_FAILURE_TIMESTAMP": pd.Timestamp.now() + pd.Timedelta(hours=35.2),
                "RUL_HOURS": 35.2,
                "PREDICTIVE_CAUSE": "Combined Forecast Breach (Synthetic)"
            }
        ])
    else:
        rul_df = session.sql(
            "SELECT * FROM ASSET_RUL_PREDICTIONS ORDER BY RUL_HOURS ASC"
        ).to_pandas()
        
    st.sidebar.markdown("---")
    st.sidebar.markdown("### 📄 Update OEM Manual")
    st.sidebar.caption("Upload a new PDF to dynamically extract updated hardcaps.")
    uploaded_file = st.sidebar.file_uploader("Upload new OEM Manual", type=["pdf"])
    if uploaded_file is not None:
        if st.sidebar.button("Process New Manual"):
            with st.spinner("Extracting limits & updating predictions..."):
                # Save uploaded file
                project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                pdf_path = os.path.abspath(os.path.join(project_root, "..", "..", "data", "OEM_Maintenance_and_Operations_Manual.pdf"))
                with open(pdf_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())
                
                # Run the parser script
                sys.path.insert(0, os.path.abspath(os.path.join(project_root, "..", "create_rag")))
                try:
                    from parse_pdf import parse_pdf
                    parse_pdf()
                except Exception as e:
                    st.sidebar.error(f"Failed to parse PDF: {e}")
                    
                # Re-run the analytics script to update predictions
                sql_path = os.path.abspath(os.path.join(project_root, "..", "..", "sql", "03-analytics.sql"))
                if os.path.exists(sql_path):
                    with open(sql_path, "r", encoding="utf-8") as f:
                        sql_script = f.read()
                    for _ in session._conn.execute_string(sql_script):
                        pass
                
                st.session_state.pdf_upload_success = True
                st.rerun()

    if rul_df.empty:
        st.success("No predicted failures in the next 72 hours.")
    else:
        if not demo_mode and not rul_df.empty:
            equip_ids = [str(row["EQUIPMENT_ID"]).strip('"') for _, row in rul_df.iterrows()]
            equip_ids_str = "', '".join(equip_ids)
            try:
                sku_df = session.sql(f"""
                    SELECT EQUIPMENT_ID, SKU_ID
                    FROM IT_OT_CONVERGED 
                    WHERE EQUIPMENT_ID IN ('{equip_ids_str}')
                    QUALIFY ROW_NUMBER() OVER (PARTITION BY EQUIPMENT_ID ORDER BY TIMESTAMP DESC) = 1
                """).to_pandas()
                latest_sku_map = dict(zip(sku_df['EQUIPMENT_ID'], sku_df['SKU_ID']))
            except Exception:
                latest_sku_map = {}
        else:
            latest_sku_map = {}

        cols = st.columns(len(rul_df))
        # Use enumerate so col index is always 0-based regardless of DataFrame index
        for col_idx, (_, row) in enumerate(rul_df.iterrows()):
            with cols[col_idx]:
                # Snowflake ML forecast sometimes returns the series wrapped in literal double quotes
                equip_id = str(row["EQUIPMENT_ID"]).strip('"')
                rul = row["RUL_HOURS"]
                predictive_cause = row.get("PREDICTIVE_CAUSE", "Unknown Cause")

                if demo_mode:
                    triggering_sku = "SKU-899"
                else:
                    triggering_sku = latest_sku_map.get(equip_id, "Unknown")
                    
                if triggering_sku == 'NONE':
                    triggering_sku = '⚙️ Machine Changeover'

                if rul <= 6:
                    color = "red"
                    bg_color = "rgba(255, 0, 0, 0.1)"
                elif rul <= 24:
                    color = "orange"
                    bg_color = "rgba(255, 165, 0, 0.1)"
                else:
                    color = "#d4af37"  # Darker gold/yellow for better text readability
                    bg_color = "rgba(255, 215, 0, 0.1)"

                st.markdown(
                    f"""
                    <div style="padding: 15px; border-radius: 10px;
                                border: 2px solid {color};
                                background-color: {bg_color};">
                        <h4>{equip_id}</h4>
                        <p style="font-size: 24px; font-weight: bold;
                                  color: {color}; margin:0;">
                            {rul} Hours to Failure
                        </p>
                        <p style="margin-top: 5px; margin-bottom: 5px;">
                            <strong>Predictive Cause:</strong> {predictive_cause}
                        </p>
                        <p style="margin-top: 5px;">
                            <strong>Active SKU:</strong> {triggering_sku}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                if st.button(f"Investigate {equip_id}", key=f"inv_{equip_id}"):
                    st.session_state["investigate_context"] = {
                        "equipment_id": equip_id,
                        "sku": triggering_sku,
                        "rul": rul,
                        "predictive_cause": predictive_cause,
                    }
                    st.switch_page("pages/2_Investigate.py")

except Exception as e:
    st.warning(
        "Could not load RUL predictions. "
        "Has sql/03-analytics.sql been run in Snowflake?"
    )
    st.write(e)

st.markdown("---")

# --- IT/OT Joined Data Grid ---
@st.fragment
def render_data_grid(active_session):
    st.subheader("🏭 Converged Factory Telemetry (IT + OT)")
    try:
        data_df = active_session.sql(
            "SELECT * FROM IT_OT_CONVERGED ORDER BY TIMESTAMP DESC LIMIT 200"
        ).to_pandas()

        # Clean up the UI presentation of 'NONE' to make it clear for the judges
        data_df['SKU_ID'] = data_df['SKU_ID'].replace('NONE', '⚙️ Machine Changeover')

        # Filter widgets wrapped in a form for batch interactions
        with st.form("telemetry_filters"):
            col1, col2 = st.columns(2)
            with col1:
                equipment_filter = st.multiselect(
                    "Filter by Equipment", data_df["EQUIPMENT_ID"].unique()
                )
            with col2:
                sku_filter = st.multiselect("Filter by SKU", data_df["SKU_ID"].unique())
            st.form_submit_button("Apply Filters")

        if equipment_filter:
            data_df = data_df[data_df["EQUIPMENT_ID"].isin(equipment_filter)]
        if sku_filter:
            data_df = data_df[data_df["SKU_ID"].isin(sku_filter)]

        # Render table – use_container_width replaces the invalid width='stretch'
        st.dataframe(
            data_df,
            use_container_width=True,
            column_config={
                "TEMPERATURE_C": st.column_config.ProgressColumn(
                    "Temperature (°C)", format="%.1f", min_value=0, max_value=120
                ),
                "VIBRATION_RMS": st.column_config.ProgressColumn(
                    "Vibration (RMS)", format="%.2f", min_value=0, max_value=5.0
                ),
            },
        )
    except Exception as e:
        print(f"Could not load converged data: {e}")
        st.warning("Could not load converged data. Please check logs for details.")

render_data_grid(session)
