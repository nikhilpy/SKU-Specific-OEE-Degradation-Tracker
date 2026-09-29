import argparse
import logging
import signal
import sys
import time
import os

# Path setup
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_CODE_ROOT = os.path.dirname(_CURRENT_DIR)
for path in (_CURRENT_DIR, os.path.join(_CODE_ROOT, "misc")):
    if path not in sys.path:
        sys.path.insert(0, path)

from snowflake_client import get_connection, get_df
from detection_workflow import run_workflow

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger("AutonomousDaemon")

_SHUTDOWN = False

def handle_shutdown(signum, frame):
    global _SHUTDOWN
    logger.info(f"Received shutdown signal ({signum}). Initiating graceful shutdown...")
    _SHUTDOWN = True

def ensure_alerts_history(conn):
    try:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS OEE_COMMAND_CENTER.FACTORY_FLOOR.ALERTS_HISTORY (
                EQUIPMENT_ID VARCHAR(255),
                TARGET_SKU VARCHAR(255),
                RUL_HOURS FLOAT,
                STATUS VARCHAR(255),
                ALERT_TIMESTAMP TIMESTAMP_LTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
    except Exception as e:
        logger.error(f"Error ensuring ALERTS_HISTORY table exists: {e}")
    finally:
        cursor.close()

def poll_and_execute():
    # 1. Poll ASSET_RUL_PREDICTIONS
    query_predictions = """
        SELECT EQUIPMENT_ID, SKU_ID, RUL_HOURS 
        FROM OEE_COMMAND_CENTER.FACTORY_FLOOR.ASSET_RUL_PREDICTIONS
        WHERE RUL_HOURS <= 48
    """
    
    try:
        df_preds = get_df(query_predictions)
    except Exception as e:
        logger.error(f"Failed to poll ASSET_RUL_PREDICTIONS: {e}")
        return

    if df_preds.empty:
        logger.debug("No equipment with RUL <= 48 hours.")
        return

    # 2. Check ALERTS_HISTORY to deduplicate
    conn = get_connection()
    try:
        ensure_alerts_history(conn)
        cursor = conn.cursor()
        
        for idx, row in df_preds.iterrows():
            equipment_id = str(row['EQUIPMENT_ID'])
            sku_id = str(row.get('SKU_ID', 'UNKNOWN'))
            rul_hours = float(row['RUL_HOURS'])

            # Check if alert was triggered in last 4 hours
            check_query = """
                SELECT COUNT(*) FROM OEE_COMMAND_CENTER.FACTORY_FLOOR.ALERTS_HISTORY
                WHERE EQUIPMENT_ID = %s 
                  AND TARGET_SKU = %s
                  AND ALERT_TIMESTAMP >= DATEADD(hour, -4, CURRENT_TIMESTAMP())
            """
            try:
                cursor.execute(check_query, (equipment_id, sku_id))
                count = cursor.fetchone()[0]
                if count > 0:
                    logger.info(f"Alert for {equipment_id} (SKU: {sku_id}) already triggered within 4 hours. Skipping.")
                    continue
            except Exception as e:
                logger.warning(f"Failed to query ALERTS_HISTORY, assuming no recent alert: {e}")

            logger.info(f"Triggering workflow for {equipment_id} (RUL: {rul_hours:.2f}h, SKU: {sku_id})")
            
            # 3. Trigger workflow
            try:
                final_result = run_workflow(equipment_id=equipment_id)
                logger.info(f"Workflow completed for {equipment_id}.")
            except Exception as e:
                logger.error(f"Workflow failed for {equipment_id}: {e}")
                continue

            # 4. Write to ALERTS_HISTORY with STATUS='AUTONOMOUS_EXECUTION'
            insert_query = """
                INSERT INTO OEE_COMMAND_CENTER.FACTORY_FLOOR.ALERTS_HISTORY 
                (EQUIPMENT_ID, TARGET_SKU, RUL_HOURS, STATUS)
                VALUES (%s, %s, %s, 'AUTONOMOUS_EXECUTION')
            """
            try:
                cursor.execute(insert_query, (equipment_id, sku_id, rul_hours))
                conn.commit()
                logger.info(f"Recorded alert to ALERTS_HISTORY for {equipment_id}")
            except Exception as e:
                logger.error(f"Failed to record alert in ALERTS_HISTORY for {equipment_id}: {e}")
                
    finally:
        conn.close()

def main():
    parser = argparse.ArgumentParser(description="Autonomous polling daemon for OEE Degradation")
    parser.add_argument("--interval-seconds", type=int, default=60, help="Polling interval in seconds")
    args = parser.parse_args()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(f"Starting autonomous daemon with {args.interval_seconds}s interval...")

    while not _SHUTDOWN:
        logger.info("Heartbeat: Polling predictions...")
        poll_and_execute()
        
        sleep_time = 0
        while sleep_time < args.interval_seconds and not _SHUTDOWN:
            time.sleep(1)
            sleep_time += 1

    logger.info("Daemon shut down cleanly.")

if __name__ == "__main__":
    main()
