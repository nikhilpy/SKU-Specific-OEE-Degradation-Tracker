import os
import json
import streamlit as st
import snowflake.connector
from dotenv import load_dotenv
from snowflake_conn import get_active_session

SEARCH_SERVICE = "OEE_COMMAND_CENTER.FACTORY_FLOOR.OEM_MANUAL_SEARCH"


def _get_connector_connection():
    """Creates a raw snowflake.connector connection (used for Cortex Search Preview)."""
    load_dotenv()
    env_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
        '.env'
    )
    load_dotenv(env_path)
    return snowflake.connector.connect(
        account=os.getenv("SNOWFLAKE_ACCOUNT"),
        user=os.getenv("SNOWFLAKE_USER"),
        password=os.getenv("SNOWFLAKE_PASSWORD"),
        warehouse="COMPUTE_WH",
        database="OEE_COMMAND_CENTER",
        schema="FACTORY_FLOOR"
    )


def _retrieve_oem_constraints(equipment_id: str) -> str:
    """
    Calls the Cortex Search Service (built by Phase 3) to retrieve the
    real OEM operating limits for the given equipment from the indexed PDF.
    Falls back to a hardcoded stub if the service is not yet available.
    """
    try:
        conn = _get_connector_connection()
        cursor = conn.cursor()
        search_payload = {
            "query": f"maximum continuous operating temperature limit for {equipment_id}",
            "columns": ["FILE_NAME", "CHUNK_INDEX", "CHUNK_TEXT"],
            "limit": 3
        }
        cursor.execute(
            "SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(%s, PARSE_JSON(%s)) AS SEARCH_RESULTS",
            (SEARCH_SERVICE, json.dumps(search_payload))
        )
        result = cursor.fetchone()
        cursor.close()
        conn.close()

        if result and result[0]:
            parsed = json.loads(result[0]) if isinstance(result[0], str) else result[0]
            results_list = parsed.get("results", [])
            if results_list:
                # Concatenate top chunks for context
                oem_text = " | ".join(
                    r.get("CHUNK_TEXT", "")[:300] for r in results_list[:2]
                )
                return f"[From OEM Manual] {oem_text}"
    except Exception as e:
        # Cortex Search Service not yet deployed — fall back gracefully
        pass

    return "Max Sustained Temp: 90°C (fallback — OEM_MANUAL_SEARCH not yet deployed)"


def ask_investigative_agent(question: str, context: dict) -> str:
    """
    Investigative Agent backed by Snowflake Cortex.
    OEM constraints are now retrieved live from the Cortex Search Service
    built by Phase 3 (OEM_MANUAL_SEARCH). Falls back to stub if unavailable.
    """
    session = get_active_session()
    if not session:
        return "Error: No Snowflake session available."

    # Live retrieval — replaces the hardcoded stub (Task 4.6 integration seam)
    oem_constraints = _retrieve_oem_constraints(context.get('equipment_id', ''))

    prompt = f"""
    You are an Investigative AI Agent for a manufacturing plant.
    Use the following context to answer the user's question concisely and technically.

    Context:
    - Equipment ID: {context.get('equipment_id', 'Unknown')}
    - Active SKU causing stress: {context.get('sku', 'Unknown')}
    - Predicted Remaining Useful Life: {context.get('rul', 'Unknown')} hours
    - OEM Constraints (retrieved from equipment manual): {oem_constraints}

    User Question: {question}
    """

    try:
        query = "SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', ?) AS RESPONSE"
        df = session.sql(query, params=[prompt]).to_pandas()
        return df['RESPONSE'].iloc[0]
    except Exception as e:
        return f"Agent Error (Cortex might not be enabled or model not found): {str(e)}"
