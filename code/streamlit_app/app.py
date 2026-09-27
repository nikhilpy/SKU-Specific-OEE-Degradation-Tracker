import streamlit as st

st.set_page_config(
    page_title="Command Center",
    page_icon="🏭",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.title("🏭 SKU-Specific OEE Degradation Tracker")
st.markdown("### Command Center")

st.markdown("""
Welcome to the OEE Degradation Command Center. 
Please select a page from the sidebar to continue:
- **Dashboard**: View the IT/OT data grid and predictive alert cards.
- **Investigate**: Chat with the Investigative Agent.
- **Alerts History**: View past mitigations and alert logs.
""")

st.sidebar.success("Select a page above.")
