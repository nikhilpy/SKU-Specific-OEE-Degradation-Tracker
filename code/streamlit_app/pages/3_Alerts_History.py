import streamlit as st
import pandas as pd
from snowflake_conn import get_active_session

st.set_page_config(page_title="Alerts History", page_icon="📜", layout="wide")
st.title("📜 Alerts History & Audit Log")

session = get_active_session()
if not session:
    st.stop()

st.markdown("This page shows the history of all automated mitigation actions taken by the Command Center.")

try:
    # Try fetching the alerts history
    history_df = session.sql("SELECT * FROM ALERTS_HISTORY ORDER BY TIMESTAMP DESC").to_pandas()
    
    if history_df.empty:
        st.info("No alerts have been mitigated yet.")
    else:
        st.dataframe(history_df, use_container_width=True)
        
        # Add CSV export
        csv = history_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="Download Alerts History as CSV",
            data=csv,
            file_name='alerts_history.csv',
            mime='text/csv',
        )
except Exception as e:
    # Table might not exist yet if no mitigation was clicked
    if "does not exist" in str(e).lower() or "not found" in str(e).lower():
        st.info("No alerts have been mitigated yet (Table ALERTS_HISTORY not found).")
    else:
        st.error(f"Failed to load alerts history: {e}")
