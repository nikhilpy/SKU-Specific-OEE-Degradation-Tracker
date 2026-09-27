import os
import streamlit as st
from snowflake.snowpark import Session
from dotenv import load_dotenv

# Resolve .env from project root (two levels up from streamlit_app/)
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
)
load_dotenv(_ENV_PATH)


@st.cache_resource
def init_connection():
    connection_parameters = {
        "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
        "user":      os.getenv("SNOWFLAKE_USER"),
        "password":  os.getenv("SNOWFLAKE_PASSWORD"),
        "database":  os.getenv("SNOWFLAKE_DATABASE", "OEE_COMMAND_CENTER"),
        "schema":    os.getenv("SNOWFLAKE_SCHEMA",   "FACTORY_FLOOR"),
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
    }

    try:
        return Session.builder.configs(connection_parameters).create()
    except Exception as e:
        st.error(f"Failed to connect to Snowflake: {e}")
        return None


def get_active_session():
    return init_connection()
