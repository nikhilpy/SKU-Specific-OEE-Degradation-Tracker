import os
import sys
import json

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "misc"
))

from snowflake_client import get_connection

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "llm_setup"
))
from llm import ask_json

PDF_FILE = "OEM_Maintenance_and_Operations_Manual.pdf"


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
        print(f"Extracting {PDF_FILE} using Snowflake Cortex PARSE_DOCUMENT...")

        conn = get_connection()
        cursor = conn.cursor()

        # 1. Fetch text using Snowflake Cortex PARSE_DOCUMENT
        # Ensure the stage has SSE encryption configured.
        stage_path = f"@OEE_COMMAND_CENTER.FACTORY_FLOOR.OEM_MANUALS_STAGE"
        
        cursor.execute(f"""
        SELECT SNOWFLAKE.CORTEX.PARSE_DOCUMENT(
            '{stage_path}', 
            '{PDF_FILE}', 
            {{'mode': 'LAYOUT'}}
        ) AS parsed_data
        """)
        
        row = cursor.fetchone()
        if not row or not row[0]:
            raise Exception("Failed to retrieve parsed document from Snowflake.")
            
        data = json.loads(row[0])
        full_text = data.get('content', '')

        if not full_text:
            raise Exception("Document parsed, but content was empty.")

        # 2. CHUNK THE AGGREGATED TEXT
        chunks = chunk_text(full_text)

        # Clear old chunks to prevent duplicates on re-runs
        cursor.execute("TRUNCATE TABLE OEM_MANUAL_CHUNKS")

        sql = """
            INSERT INTO OEM_MANUAL_CHUNKS
            (
                FILE_NAME,
                CHUNK_INDEX,
                CHUNK_TEXT
            )
            VALUES (%s, %s, %s)
        """

        chunk_data = [(PDF_FILE, idx, chunk) for idx, chunk in enumerate(chunks)]
        cursor.executemany(sql, chunk_data)
        chunk_index = len(chunks)

        conn.commit()
        print(f"Inserted {chunk_index} chunks into OEM_MANUAL_CHUNKS")

        # --- Dynamic Extraction ---
        print("Extracting OEM Hard Caps using Ollama...")
        # Get a substantial portion of the text to ensure we catch LINE-2 thresholds
        extraction_text = full_text
        
        prompt = f"""Extract the maximum temperature limit and maximum vibration limit for different equipment types from the following manual text.
The global cross-line guardrails (Critical upper warning) should be mapped to 'ALL_EQUIPMENT'. 
If there are specific granular thresholds for certain lines (like LINE-2-PACKAGING or specific SKUs within it), list them as separate equipment types (e.g. 'LINE-2-PACKAGING_SKU-100').

IMPORTANT: For specific equipment lines, the limits might be explicitly named "Thermal warning cutoff" and "Max continuous vibration" in the text tables. You MUST extract these specific cutoff/max values for each SKU if they exist, instead of just repeating the global cross-line guardrails.

Respond ONLY with a JSON object containing an 'equipment_thresholds' key which is a list of objects containing EXACTLY these keys:
- "equipment_type": string (e.g. "ALL_EQUIPMENT" or "LINE-2-PACKAGING_SKU-100")
- "max_temp": float (e.g. 85.0)
- "max_vibration": float (e.g. 2.35)

Manual Text snippet:
{extraction_text[:35000]}
"""
        try:
            extracted_json = ask_json(prompt, temperature=0.1)
            
            thresholds = extracted_json.get("equipment_thresholds", [])
            if not thresholds:
                raise ValueError("No thresholds found in JSON response")
            
            cursor.execute("TRUNCATE TABLE OEM_EQUIPMENT_THRESHOLDS")
            
            insert_sql = """
                INSERT INTO OEM_EQUIPMENT_THRESHOLDS (EQUIPMENT_TYPE, MAX_TEMP_LIMIT, MAX_VIBRATION_LIMIT)
                VALUES (%s, %s, %s)
            """
            
            threshold_data = []
            for t in thresholds:
                eq_type = t.get("equipment_type", "ALL_EQUIPMENT")
                # Fallback to global defaults if missing
                temp_limit = float(t.get("max_temp", 85.0))
                vib_limit = float(t.get("max_vibration", 2.35))
                threshold_data.append((eq_type, temp_limit, vib_limit))
                print(f"Extracted Limits -> {eq_type} - Temp: {temp_limit}, Vib: {vib_limit}")
                
            cursor.executemany(insert_sql, threshold_data)
            conn.commit()
            print("Successfully updated OEM_EQUIPMENT_THRESHOLDS table.")
            
        except Exception as e:
            print(f"Failed to extract limits using Ollama: {e}")
            # Fallback to global defaults
            cursor.execute("TRUNCATE TABLE OEM_EQUIPMENT_THRESHOLDS")
            cursor.execute(
                """
                INSERT INTO OEM_EQUIPMENT_THRESHOLDS (EQUIPMENT_TYPE, MAX_TEMP_LIMIT, MAX_VIBRATION_LIMIT)
                VALUES (%s, %s, %s)
                """,
                ('ALL_EQUIPMENT', 85.0, 2.35)
            )
            conn.commit()
            print("Fell back to default global thresholds (85.0, 2.35)")

    except Exception as e:

        if conn:
            conn.rollback()

        print("\nERROR:")
        print(e)

    finally:

        if cursor:
            cursor.close()

        print("\nSnowflake connection pooled.")


if __name__ == "__main__":
    parse_pdf()