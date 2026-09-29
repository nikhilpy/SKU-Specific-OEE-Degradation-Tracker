import os
import sys
import urllib.parse

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "misc"
))

from snowflake_client import get_connection

# 1. Get the directory where this script is located (c:/Users/.../code/create_rag)
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
# 2. Move up two directories to reach the project root (SKU-Specific-OEE-Degradation-Tracker)
PROJECT_ROOT = os.path.abspath(os.path.join(SCRIPT_DIR, "..", ".."))
# 3. Construct the clean, absolute path to the data folder
PDF_FILE = os.path.join(PROJECT_ROOT, "data", "LINE-2-PACKAGING OEM Maintenance Manual.pdf")

# Snowflake stage
STAGE = "@OEE_COMMAND_CENTER.FACTORY_FLOOR.OEM_MANUALS_STAGE"


def upload_pdf(conn):
    print("\nUploading OEM manual...")

    cursor = conn.cursor()

    try:
        # Spaces in the path (e.g. 'OEM Maintenance Manual.pdf') must be
        # percent-encoded or Snowflake's SQL tokeniser splits the token.
        file_path = urllib.parse.quote(
            os.path.abspath(PDF_FILE).replace('\\', '/'),
            safe='/:@'
        )
        sql = f"""
        PUT 'file://{file_path}'
        {STAGE}
        AUTO_COMPRESS=FALSE
        OVERWRITE=TRUE
        """

        cursor.execute(sql)

        for row in cursor.fetchall():
            print(row)

        print("PDF uploaded successfully.")

    finally:
        cursor.close()


def insert_document():

    conn = None

    try:
        conn = get_connection()

        # 1. Upload PDF
        upload_pdf(conn)

        print("\nOEM document pipeline completed.")

    except Exception as e:
        print("\nERROR:")
        print(e)

    finally:
        if conn:
            conn.close()
            print("\nSnowflake connection closed.")

if __name__ == "__main__":
    insert_document()