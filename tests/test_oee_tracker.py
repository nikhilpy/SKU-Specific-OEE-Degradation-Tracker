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
    
    assert os.path.exists(os.path.join(_CODE_ROOT, "it_batch_schedule.parquet"))
    assert os.path.exists(os.path.join(_CODE_ROOT, "ot_telemetry_stream.parquet"))
    
    it_df = pd.read_parquet(os.path.join(_CODE_ROOT, "it_batch_schedule.parquet"))
    ot_df = pd.read_parquet(os.path.join(_CODE_ROOT, "ot_telemetry_stream.parquet"))
    
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
        os.remove(os.path.join(_CODE_ROOT, "it_batch_schedule.parquet"))
        os.remove(os.path.join(_CODE_ROOT, "ot_telemetry_stream.parquet"))
    except Exception:
        pass

def test_deterministic_rule_evaluation_dynamic_caps():
    """Test that the deterministic rule evaluation respects dynamic hard caps."""
    from investigative_agent import deterministic_rule_evaluation
    
    # Test breach of dynamic temp cap
    decision = deterministic_rule_evaluation(
        equipment_id="LINE-1",
        sku="SKU-1",
        rul_hours=30.0,  # normally MONITOR
        current_temp=95.0, # breaches 90.0
        current_vibration=1.0,
        dynamic_temp_cap=90.0,
        dynamic_vib_cap=2.3
    )
    assert decision.priority == "CRITICAL"
    assert decision.action == "IMMEDIATE_MAINTENANCE"
    
    # Test safe within dynamic caps
    decision2 = deterministic_rule_evaluation(
        equipment_id="LINE-1",
        sku="SKU-1",
        rul_hours=30.0,
        current_temp=85.0,
        current_vibration=1.0,
        dynamic_temp_cap=90.0,
        dynamic_vib_cap=2.3
    )
    assert decision2.priority == "MEDIUM"
    assert decision2.action == "MONITOR_EQUIPMENT"
    
    # Test dynamic cap adjustment (if cap is raised, 95 is no longer a breach)
    decision3 = deterministic_rule_evaluation(
        equipment_id="LINE-1",
        sku="SKU-1",
        rul_hours=30.0,
        current_temp=95.0,
        current_vibration=1.0,
        dynamic_temp_cap=100.0, # Cap raised!
        dynamic_vib_cap=2.3
    )
    assert decision3.priority == "MEDIUM"
    assert decision3.action == "MONITOR_EQUIPMENT"

def test_validate_oem_evidence_dynamic_fallback():
    """Test that missing chunks fallback gracefully and don't crash."""
    from investigative_agent import validate_oem_evidence
    
    # Ensure attributes exist (usually monkey-patched in investigate())
    validate_oem_evidence.dynamic_temp_cap = 92.0
    validate_oem_evidence.dynamic_vib_cap = 2.5
    
    # Test missing chunks
    validation, status = validate_oem_evidence(
        oem_evidence={"chunks": []},
        current_temp=80.0,
        current_vibration=1.0
    )
    
    assert status == "DEGRADED_LOCAL_HEURISTIC"
    assert validation.breach_detected is False
    assert validation.max_temp_limit == 92.0
    assert validation.max_vibration_limit == 2.5


