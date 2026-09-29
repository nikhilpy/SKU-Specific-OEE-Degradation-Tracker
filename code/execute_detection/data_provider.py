from abc import ABC, abstractmethod
from typing import Dict, Any
import pandas as pd
import json

class BaseDataProvider(ABC):
    @abstractmethod
    def get_recent_telemetry(self, equipment_id: str, limit: int = 100) -> pd.DataFrame:
        pass

    @abstractmethod
    def get_active_batch(self, equipment_id: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def search_oem_manual(self, query: str) -> Dict[str, Any]:
        pass

class SnowflakeDataProvider(BaseDataProvider):
    def __init__(self):
        import sys
        import os
        misc_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "misc")
        if misc_dir not in sys.path:
            sys.path.insert(0, misc_dir)
        # Import existing snowflake_client.py functionality
        from snowflake_client import get_df, search_oem_manual, TELEMETRY_TABLE, BATCH_TABLE
        self._get_df = get_df
        self._search_oem_manual = search_oem_manual
        self.TELEMETRY_TABLE = TELEMETRY_TABLE
        self.BATCH_TABLE = BATCH_TABLE

    def get_recent_telemetry(self, equipment_id: str, limit: int = 100) -> pd.DataFrame:
        query = f"""
        SELECT 
            "TIMESTAMP" AS "Timestamp",
            "EQUIPMENT_ID" AS "Equipment",
            "TEMPERATURE_C" AS "Temperature",
            "VIBRATION_RMS" AS "Vibration"
        FROM {self.TELEMETRY_TABLE}
        WHERE "EQUIPMENT_ID" = '{equipment_id}'
        ORDER BY "TIMESTAMP" DESC
        LIMIT {limit}
        """
        df = self._get_df(query)
        # Convert Timestamp to datetime if not already
        if not df.empty and not pd.api.types.is_datetime64_any_dtype(df["Timestamp"]):
            df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        return df

    def get_active_batch(self, equipment_id: str) -> Dict[str, Any]:
        query = f"""
        SELECT BATCH_ID, SKU_ID, START_TIME, END_TIME
        FROM {self.BATCH_TABLE}
        WHERE EQUIPMENT_ID = '{equipment_id}'
        ORDER BY END_TIME DESC
        LIMIT 1
        """
        df = self._get_df(query)
        if df.empty:
            return {}
        return df.iloc[0].to_dict()

    def search_oem_manual(self, query: str) -> Dict[str, Any]:
        return self._search_oem_manual(query)

class MockDataProvider(BaseDataProvider):
    def get_recent_telemetry(self, equipment_id: str, limit: int = 100) -> pd.DataFrame:
        import numpy as np
        from datetime import datetime, timedelta
        
        now = datetime.now()
        records = []
        # Simulate a thermal breach: temperature rising to critical state (>90)
        # and vibration rising (>2.3)
        for i in range(limit):
            # i=0 is earliest, i=limit-1 is latest
            t = now - timedelta(minutes=limit-i)
            # Temp starts around 75 and rises to 95 at the end
            temp = 75.0 + (20.0 * (i / max(1, limit - 1))) + np.random.normal(0, 0.5)
            # Vib starts around 2.0 and rises to 2.5
            vib = 2.0 + (0.5 * (i / max(1, limit - 1))) + np.random.normal(0, 0.05)
            
            records.append({
                "Timestamp": t,
                "Equipment": equipment_id,
                "Temperature": round(temp, 2),
                "Vibration": round(vib, 2)
            })
        
        df = pd.DataFrame(records)
        df["Timestamp"] = pd.to_datetime(df["Timestamp"])
        # Needs to be sorted descending based on how prediction expects it
        df = df.sort_values(by="Timestamp", ascending=False).reset_index(drop=True)
        return df

    def get_active_batch(self, equipment_id: str) -> Dict[str, Any]:
        from datetime import datetime, timedelta
        now = datetime.now()
        return {
            "BATCH_ID": "B-MOCK-899",
            "SKU_ID": "SKU-899",
            "START_TIME": now - timedelta(hours=2),
            "END_TIME": now + timedelta(hours=2)
        }

    def search_oem_manual(self, query: str) -> Dict[str, Any]:
        return {
            "chunks": [
                {
                    "chunk_index": 0,
                    "text": "WARNING: Packaging equipment LINE-2-PACKAGING has an absolute maximum operating temperature of 90°C. If temperature exceeds 90°C, immediate thermal damage to bearings is imminent. Vibration must not exceed 2.3 mm/s."
                }
            ],
            "evidence": [
                {"parameter": "temperature_limit", "limit": 90.0},
                {"parameter": "vibration_limit", "limit": 2.3}
            ],
            "source": "MOCK_OEM_MANUAL"
        }
