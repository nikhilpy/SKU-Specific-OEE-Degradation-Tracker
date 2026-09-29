import os
import streamlit as st
import snowflake.connector
from dotenv import load_dotenv

# Resolve .env from project root (two levels up from streamlit_app/)
_ENV_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"
)
load_dotenv(_ENV_PATH)


class _ConnectorSession:
    """
    Thin wrapper around a snowflake.connector connection that exposes a
    Snowpark-compatible `.sql(query).collect()` interface so the rest of the
    app (e.g. ALERTS_HISTORY INSERT in 2_Investigate.py) works unchanged.
    """

    def __init__(self, conn):
        self._conn = conn

    def sql(self, query: str) -> "_Query":
        return _Query(self._conn, query)

    def close(self):
        try:
            self._conn.close()
        except Exception:
            pass


class _Query:
    def __init__(self, conn, query: str):
        self._conn = conn
        self._query = query

    def collect(self):
        cur = self._conn.cursor()
        try:
            cur.execute(self._query)
            return cur.fetchall()
        finally:
            cur.close()

    def to_pandas(self):
        """Return query results as a pandas DataFrame (mirrors Snowpark API)."""
        import pandas as pd
        cur = self._conn.cursor()
        try:
            cur.execute(self._query)
            columns = [col[0] for col in cur.description] if cur.description else []
            rows = cur.fetchall()
            return pd.DataFrame(rows, columns=columns)
        finally:
            cur.close()



@st.cache_resource
def init_connection() -> _ConnectorSession | None:
    connection_parameters = {
        "account":   os.getenv("SNOWFLAKE_ACCOUNT"),
        "user":      os.getenv("SNOWFLAKE_USER"),
        "password":  os.getenv("SNOWFLAKE_PASSWORD"),
        "database":  os.getenv("SNOWFLAKE_DATABASE") or "OEE_COMMAND_CENTER",
        "schema":    os.getenv("SNOWFLAKE_SCHEMA") or "FACTORY_FLOOR",
        "warehouse": os.getenv("SNOWFLAKE_WAREHOUSE") or "COMPUTE_WH",
        "role":      os.getenv("SNOWFLAKE_ROLE") or "ACCOUNTADMIN",
    }

    # Validate that at minimum account + user + password are set
    if not all([
        connection_parameters["account"],
        connection_parameters["user"],
        connection_parameters["password"],
    ]):
        return None

    try:
        conn = snowflake.connector.connect(**connection_parameters)
        return _ConnectorSession(conn)
    except Exception as e:
        print(f"Failed to connect to Snowflake: {e}")
        st.warning("Failed to connect to Snowflake. Please check your network and credentials.")
        return None


def get_active_session() -> _ConnectorSession | None:
    return init_connection()
