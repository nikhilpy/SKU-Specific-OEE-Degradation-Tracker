import streamlit as st
from snowflake_conn import get_active_session

def ask_investigative_agent(question: str, context: dict) -> str:
    """
    Stub for the Phase 3 Investigative Agent.
    Calls Snowflake Cortex LLM directly with a constructed prompt.
    """
    session = get_active_session()
    if not session:
        return "Error: No Snowflake session available."
        
    prompt = f"""
    You are an Investigative AI Agent for a manufacturing plant.
    Use the following context to answer the user's question.
    
    Context:
    - Equipment ID: {context.get('equipment_id', 'Unknown')}
    - Active SKU: {context.get('sku', 'Unknown')}
    - Predicted RUL (Hours): {context.get('rul', 'Unknown')}
    - OEM Constraints: Max Sustained Temp 90C (Stub from unstructured data)
    
    User Question: {question}
    """
    
    try:
        # Note: 'mistral-large2' must be available in the region. Using 'mistral-large2' as per README, but fallback might be needed.
        # Snowflake cortex function signature: SNOWFLAKE.CORTEX.COMPLETE('model_name', 'prompt')
        query = "SELECT SNOWFLAKE.CORTEX.COMPLETE('mistral-large2', ?) AS RESPONSE"
        df = session.sql(query, params=[prompt]).to_pandas()
        return df['RESPONSE'].iloc[0]
    except Exception as e:
        return f"Agent Error (Cortex might not be enabled or model not found): {str(e)}"
