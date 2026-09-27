import json
import os

import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

db_user = os.getenv("SNOWFLAKE_USER")
db_password = os.getenv("SNOWFLAKE_PASSWORD")
db_account = os.getenv("SNOWFLAKE_ACCOUNT")

WAREHOUSE = "COMPUTE_WH"
DATABASE = "OEE_COMMAND_CENTER"
SCHEMA = "FACTORY_FLOOR"
SEARCH_SERVICE = "OEE_COMMAND_CENTER.FACTORY_FLOOR.OEM_MANUAL_SEARCH"

SEARCH_LIMIT = 5
SEARCH_COLUMNS = ["FILE_NAME", "CHUNK_INDEX", "CHUNK_TEXT"]

# Used when Snowflake or Cortex Search is unreachable
FALLBACK_OEM_EVIDENCE = {
    "source": "LINE-2-PACKAGING OEM Maintenance Manual",
    "evidence": [
        {
            "parameter": "temperature",
            "limit": 85.0,
            "unit": "°C"
        },
        {
            "parameter": "vibration",
            "limit": 7.5,
            "unit": "mm/s"
        }
    ]
}


def get_connection():
    """
    Open a connection to the OEE_COMMAND_CENTER database.
    """
    return snowflake.connector.connect(
        account=db_account,
        user=db_user,
        password=db_password,
        warehouse=WAREHOUSE,
        database=DATABASE,
        schema=SCHEMA
    )


def search_documents(conn, user_query, limit=SEARCH_LIMIT):
    """
    Run a Cortex Search query over the OEM manual chunks.

    The payload is inlined as a SQL literal because the connector
    wraps bound parameters in TO_CHAR, which PARSE_JSON rejects.
    """
    cursor = conn.cursor()

    try:
        payload = json.dumps({
            "query": user_query,
            "columns": SEARCH_COLUMNS,
            "limit": limit
        })

        sql = f"""
        SELECT SNOWFLAKE.CORTEX.SEARCH_PREVIEW(
            '{SEARCH_SERVICE}',
            PARSE_JSON('{payload}')
        ) AS SEARCH_RESULTS
        """

        cursor.execute(sql)

        result = cursor.fetchone()

        if result:
            return result[0]

        return None

    finally:
        cursor.close()


def search_oem_manual(query):
    """
    Search the OEM manual, falling back to the stubbed limits when
    Snowflake is unreachable so the pipeline never hard-fails.
    """
    conn = None

    try:
        conn = get_connection()

        results = search_documents(conn, query)

        return results if results else FALLBACK_OEM_EVIDENCE

    except Exception as e:
        print(f"\nOEM retrieval unavailable: {e}")

        return FALLBACK_OEM_EVIDENCE

    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    query = input("Enter your OEM manual query: ").strip()

    if not query:
        print("Query cannot be empty.")
    else:
        print(json.dumps(search_oem_manual(query), indent=4))
