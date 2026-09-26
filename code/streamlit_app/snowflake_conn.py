import os
import streamlit as st
from snowflake.snowpark import Session
from dotenv import load_dotenv

@st.cache_resource
def init_connection():
    # Load environment variables
    # Go up two levels to find the .env file in the root
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
    load_dotenv(env_path)
    
    connection_parameters = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "database": "OEE_COMMAND_CENTER",
        "schema": "FACTORY_FLOOR",
        "warehouse": "COMPUTE_WH",
    }
    
    try:
        return Session.builder.configs(connection_parameters).create()
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {e}")
        return None

def get_active_session():
    return init_connection()
