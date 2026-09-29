import os
import sys
import streamlit as st

# Ensure parent directory is in sys.path for wizard import
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from wizard import require_setup, require_infrastructure
from snowflake_conn import get_active_session

st.set_page_config(page_title="Alerts History", page_icon="📜", layout="wide")

# Ensure setup is complete before accessing page
require_setup()

st.title("📜 Alerts History & Audit Log")

session = get_active_session()
if not session:
    st.stop()

require_infrastructure(session)

st.markdown(
    "This page shows the history of all automated mitigation actions "
    "taken by the Command Center."
)

try:
    history_df = session.sql(
        "SELECT * FROM ALERTS_HISTORY ORDER BY TIMESTAMP DESC"
    ).to_pandas()

    if history_df.empty:
        st.info("No alerts have been mitigated yet.")
    else:
        # Colour-code PRIORITY column when present
        column_config = {}
        if "PRIORITY" in history_df.columns:
            column_config["PRIORITY"] = st.column_config.TextColumn("Priority")
        if "RUL_HOURS" in history_df.columns:
            column_config["RUL_HOURS"] = st.column_config.NumberColumn(
                "RUL (hrs)", format="%.1f"
            )

        # use_container_width replaces the invalid width='stretch'
        st.dataframe(history_df, use_container_width=True, column_config=column_config)

        # CSV export
        csv = history_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label="⬇️ Download Alerts History as CSV",
            data=csv,
            file_name="alerts_history.csv",
            mime="text/csv",
        )

except Exception as e:
    # Table might not exist yet if no mitigation was triggered
    err_lower = str(e).lower()
    if "does not exist" in err_lower or "not found" in err_lower:
        st.info(
            "No alerts have been mitigated yet "
            "(Table ALERTS_HISTORY not found — it is created on first mitigation)."
        )
    else:
        print(f"Failed to load alerts history: {e}")
        st.warning("Failed to load alerts history. Please try again later.")
