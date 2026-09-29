import json
import os
import re

import pandas as pd
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

db_user = os.getenv("SNOWFLAKE_USER")
db_password = os.getenv("SNOWFLAKE_PASSWORD")
db_account = os.getenv("SNOWFLAKE_ACCOUNT")

WAREHOUSE = "COMPUTE_WH"
DATABASE = "OEE_COMMAND_CENTER"
SCHEMA = "FACTORY_FLOOR"
SEARCH_LIMIT = 5

CHUNK_TABLE = "OEE_COMMAND_CENTER.FACTORY_FLOOR.OEM_MANUAL_CHUNKS"

# Rows pulled from Snowflake before ranking in Python
CANDIDATE_ROWS = 500

# Dropped when building search terms, plus common manual filler
STOP_WORDS = {
    "the", "and", "for", "with", "that", "this", "from", "into",
    "are", "was", "were", "what", "which", "how", "does", "doc",
    "documents", "document", "retrieve", "return", "contents",
    "operating", "manual", "line", "packaging"
}

TELEMETRY_TABLE = "OEE_COMMAND_CENTER.FACTORY_FLOOR.IT_OT_CONVERGED"

BATCH_TABLE = "OEE_COMMAND_CENTER.FACTORY_FLOOR.RAW_IT_BATCHES"

# Used when Snowflake or Cortex Search is unreachable
FALLBACK_OEM_EVIDENCE = {
    "source": "LINE-2-PACKAGING OEM Maintenance Manual (Degraded Local Heuristic)",
    "STATUS": "DEGRADED_LOCAL_HEURISTIC",
    "status": "DEGRADED_LOCAL_HEURISTIC",
    "evidence": [
        {
            "parameter": "temperature",
            "limit": 90.0,
            "unit": "°C"
        },
        {
            "parameter": "vibration",
            "limit": 2.3,
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


def query_terms(query):
    """
    Reduce a natural-language query to searchable keywords.
    """
    terms = re.findall(r"[a-z0-9]+", query.lower())

    return [
        term for term in terms
        if len(term) > 2 and term not in STOP_WORDS
    ]


def score_chunk(text, terms):
    """
    Reward chunks matching more distinct terms, then by frequency.
    """
    lowered = text.lower()

    matched = sum(1 for term in terms if term in lowered)
    occurrences = sum(lowered.count(term) for term in terms)

    return 2 * matched + occurrences


def search_oem_manual(query, limit=SEARCH_LIMIT):
    """
    Rank OEM_MANUAL_CHUNKS by keyword relevance to the query.

    Falls back to the stubbed limits when nothing matches or
    Snowflake is unreachable, so the pipeline never hard-fails.
    """
    terms = query_terms(query)

    if not terms:
        return FALLBACK_OEM_EVIDENCE

    conditions = " OR ".join(
        f'"CHUNK_TEXT" ILIKE \'%{term}%\'' for term in terms
    )

    sql = f"""
        SELECT "FILE_NAME", "CHUNK_INDEX", "CHUNK_TEXT"
        FROM {CHUNK_TABLE}
        WHERE {conditions}
        LIMIT {CANDIDATE_ROWS}
    """

    conn = None

    try:
        conn = get_connection()

        cursor = conn.cursor()

        try:
            cursor.execute(sql)

            rows = cursor.fetchall()
            
        finally:
            cursor.close()

        if not rows:
            print("\nNo manual chunks matched the query.")
            return FALLBACK_OEM_EVIDENCE

        ranked = sorted(
            (
                {
                    "file_name": file_name,
                    "chunk_index": chunk_index,
                    "score": score_chunk(text, terms),
                    "text": text
                }
                for file_name, chunk_index, text in rows
            ),
            key=lambda chunk: chunk["score"],
            reverse=True
        )[:limit]

        print(
            f"\nRetrieved {len(ranked)} chunk(s) for: {query}"
        )

        return {
            "source": "OEM_MANUAL_CHUNKS",
            "query": query,
            "terms": terms,
            "chunks": ranked
        }

    except Exception as e:
        print(f"\nOEM retrieval unavailable: {e}")

        return FALLBACK_OEM_EVIDENCE

    finally:
        if conn:
            conn.close()

def get_df(sql, params=None):
    """
    Run a query and return the result as a DataFrame.

    sql:    the SQL text
    params: optional tuple of bind parameters

    Snowflake types are not carried over by the cursor, so numeric
    columns come back as object dtype until infer_objects() runs.
    """
    conn = get_connection()

    try:
        cursor = conn.cursor()

        try:
            cursor.execute(sql, params)

            columns = [
                column[0] for column in cursor.description
            ]

            rows = cursor.fetchall()

        finally:
            cursor.close()

    finally:
        conn.close()

    if not rows:
        return pd.DataFrame(columns=columns)

    return pd.DataFrame(rows, columns=columns).infer_objects()

if __name__ == "__main__":
    query = input("Enter your OEM manual query: ").strip()

    if not query:
        print("Query cannot be empty.")
    else:
        print(json.dumps(search_oem_manual(query), indent=4))
