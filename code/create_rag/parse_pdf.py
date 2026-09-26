import os
from pypdf import PdfReader
import snowflake.connector
from dotenv import load_dotenv

load_dotenv()

db_user = os.getenv("SNOWFLAKE_USER")
db_password = os.getenv("SNOWFLAKE_PASSWORD")
db_account = os.getenv("SNOWFLAKE_ACCOUNT")

PDF_FILE = "LINE-2-PACKAGING OEM Maintenance Manual.pdf"


def get_connection():
    print("Testing Snowflake connection...")

    return snowflake.connector.connect(
        account=db_account,
        user=db_user,
        password=db_password,
        warehouse="COMPUTE_WH",
        database="OEE_COMMAND_CENTER",
        schema="FACTORY_FLOOR"
    )


def chunk_text(text, chunk_size=2000, overlap=300):
    chunks = []

    start = 0

    while start < len(text):
        end = start + chunk_size

        chunks.append(text[start:end])

        start = end - overlap

    return chunks


def parse_pdf():

    conn = None
    cursor = None

    try:
        script_dir = os.path.dirname(
            os.path.abspath(__file__)
        )

        project_root = os.path.abspath(
            os.path.join(script_dir, "..", "..")
        )

        pdf_path = os.path.join(
            project_root,
            "data",
            PDF_FILE
        )

        print(f"Reading PDF: {pdf_path}")

        reader = PdfReader(pdf_path)

        conn = get_connection()
        cursor = conn.cursor()

        sql = """
            INSERT INTO OEM_MANUAL_CHUNKS
            (
                FILE_NAME,
                CHUNK_INDEX,
                CHUNK_TEXT
            )
            VALUES (%s, %s, %s)
        """

        chunk_index = 0

        for page_number, page in enumerate(
            reader.pages,
            start=1
        ):

            text = page.extract_text()

            if not text:
                continue

            chunks = chunk_text(text)

            for chunk in chunks:

                cursor.execute(
                    sql,
                    (
                        PDF_FILE,
                        chunk_index,
                        chunk
                    )
                )

                chunk_index += 1

        conn.commit()

        print(
            f"Inserted {chunk_index} chunks "
            "into OEM_MANUAL_CHUNKS"
        )

    except Exception as e:

        if conn:
            conn.rollback()

        print("\nERROR:")
        print(e)

    finally:

        if cursor:
            cursor.close()

        if conn:
            conn.close()

        print("\nSnowflake connection closed.")


if __name__ == "__main__":
    parse_pdf()