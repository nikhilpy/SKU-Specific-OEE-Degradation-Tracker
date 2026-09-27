import os
import sys
from pypdf import PdfReader

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "misc"
))

from snowflake_client import get_connection

PDF_FILE = "LINE-2-PACKAGING OEM Maintenance Manual.pdf"


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