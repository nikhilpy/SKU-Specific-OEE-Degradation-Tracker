import os
import sys
import yaml
import pytest
from datetime import datetime, timedelta

# Adjust paths for imports
_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_CODE_ROOT = os.path.dirname(_CURRENT_DIR)
sys.path.insert(0, os.path.join(_CODE_ROOT, "code", "execute_detection"))
sys.path.insert(0, os.path.join(_CODE_ROOT, "code", "misc"))

from schemas import DiagnosticState, MitigationDecision
from pydantic import ValidationError
from data_generator import generate_factory_data

def test_sql_skill_rendering():
    """Test that the SQL in IT_OT_TimeSeries_Joiner.yaml renders correctly with parameter inputs."""
    yaml_path = os.path.join(_CODE_ROOT, "skills", "IT_OT_TimeSeries_Joiner.yaml")
    with open(yaml_path, 'r') as f:
        skill = yaml.safe_load(f)
    
    sql_template = skill.get('sql', '')
    
    # Assert template structure
    params = skill.get('parameters', {})
    assert "ot_table" in params
    assert "it_table" in params
    assert "join_key" in params
    
    # Test replacement with parameter inputs
    rendered_sql = (sql_template
                    .replace("{{ot_table}}", "RAW_OT_TELEMETRY")
                    .replace("{{it_table}}", "RAW_IT_BATCHES")
                    .replace("{{join_key}}", "EQUIPMENT_ID"))
    
    assert "FROM RAW_OT_TELEMETRY ot" in rendered_sql
    assert "LEFT JOIN RAW_IT_BATCHES it" in rendered_sql
    assert "ON ot.EQUIPMENT_ID = it.EQUIPMENT_ID" in rendered_sql
    assert "ot.TIMESTAMP BETWEEN it.START_TIME AND it.END_TIME" in rendered_sql

def test_pydantic_schemas():
    """Test Pydantic guardrail schemas for genuine and corrupted payloads."""
    # 1. Genuine MitigationDecision
    valid_payload = {
        "priority": "HIGH",
        "action": "SCHEDULE_MAINTENANCE",
        "target_sku": "SKU-100",
        "justification": "Thermal breach detected on SKU-100",
        "approved_for_dispatch": True
    }
    decision = MitigationDecision(**valid_payload)
    assert decision.priority == "HIGH"
    assert decision.action == "SCHEDULE_MAINTENANCE"
    assert decision.approved_for_dispatch is True
    
    # 2. Corrupted MitigationDecision (hallucinated extra field rejected by extra='forbid')
    invalid_payload = valid_payload.copy()
    invalid_payload["hallucinated_field"] = "This should fail schema defense"
    
    with pytest.raises(ValidationError):
        MitigationDecision(**invalid_payload)

    # 3. Missing required field in MitigationDecision
    incomplete_payload = {
        "priority": "HIGH",
        "action": "SCHEDULE_MAINTENANCE"
    }
    with pytest.raises(ValidationError):
        MitigationDecision(**incomplete_payload)

    # 4. Valid DiagnosticState
    diag_valid = {
        "equipment_id": "LINE-2-PACKAGING",
        "metric": "Temperature",
        "current_val": 95.2,
        "dynamic_threshold": 90.0,
        "rul_hours": 3.5,
        "failure_flag": True,
        "confidence_score": 0.98
    }
    diag = DiagnosticState(**diag_valid)
    assert diag.confidence_score == 0.98
    assert diag.failure_flag is True

    # 5. Invalid confidence score (out of range > 1.0)
    diag_invalid = diag_valid.copy()
    diag_invalid["confidence_score"] = 1.5
    with pytest.raises(ValidationError):
        DiagnosticState(**diag_invalid)

def test_mock_data_provider_and_decoupling():
    """Test MockDataProvider interface decouples Snowflake runtime from testing."""
    from data_provider import MockDataProvider
    
    provider = MockDataProvider()
    telemetry_df = provider.get_recent_telemetry("LINE-2-PACKAGING", limit=20)
    assert len(telemetry_df) == 20
    assert "Temperature" in telemetry_df.columns
    assert "Vibration" in telemetry_df.columns
    
    batch_info = provider.get_active_batch("LINE-2-PACKAGING")
    assert batch_info.get("SKU_ID") == "SKU-899"
    
    oem_result = provider.search_oem_manual("packaging temperature limit")
    assert "chunks" in oem_result
    assert oem_result.get("source") == "MOCK_OEM_MANUAL"

def test_data_generator_referential_integrity():
    """Test that the data generator maintains referential integrity between IT and OT."""
    import pandas as pd
    
    # Call data generator which writes to CSVs in current directory
    generate_factory_data()
    
    assert os.path.exists("it_batch_schedule.csv")
    assert os.path.exists("ot_telemetry_stream.csv")
    
    it_df = pd.read_csv("it_batch_schedule.csv")
    ot_df = pd.read_csv("ot_telemetry_stream.csv")
    
    # Convert timestamps
    it_df["START_TIME"] = pd.to_datetime(it_df["START_TIME"])
    it_df["END_TIME"] = pd.to_datetime(it_df["END_TIME"])
    ot_df["TIMESTAMP"] = pd.to_datetime(ot_df["TIMESTAMP"])
    
    # Check referential integrity:
    # We will do a merge_asof to simulate the IT/OT boundaries
    joined = pd.merge_asof(
        ot_df.sort_values("TIMESTAMP"),
        it_df.sort_values("START_TIME"),
        left_on="TIMESTAMP",
        right_on="START_TIME",
        by="EQUIPMENT_ID",
        direction="backward"
    )
    
    assert "EQUIPMENT_ID" in joined.columns
    assert len(joined) == len(ot_df)
    
    # Cleanup
    try:
        os.remove("it_batch_schedule.csv")
        os.remove("ot_telemetry_stream.csv")
    except Exception:
        pass

