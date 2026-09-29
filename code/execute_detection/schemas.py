"""
schemas.py — Enterprise Guardrails & Schema Defense (Pydantic v2)

Defines strict schemas for multi-agent handoffs in the predictive maintenance pipeline:
1. DiagnosticState: Captures telemetry & RUL status from the Prediction Agent.
2. OEMValidation: Validates OEM manual constraints and chunk retrieval status.
3. MitigationDecision: Validates priority, action, and dispatch approval with extra field forbidding
   to prevent LLM hallucination.
"""

from typing import Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class DiagnosticState(BaseModel):
    """Telemetry and RUL diagnostic state from the Prediction Agent."""
    equipment_id: str
    metric: str
    current_val: float
    dynamic_threshold: float
    rul_hours: float
    failure_flag: bool
    confidence_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score between 0.0 and 1.0"
    )

    model_config = ConfigDict(extra="ignore")


class OEMValidation(BaseModel):
    """Validation of OEM constraints retrieved from Cortex Search / manual chunks."""
    max_temp_limit: float
    max_vibration_limit: float
    citation_source: str
    breach_detected: bool
    status: Optional[str] = None

    model_config = ConfigDict(extra="ignore")


class MitigationDecision(BaseModel):
    """
    Mitigation action and priority decision.
    Strict schema defense with extra='forbid' to reject LLM hallucinations.
    """
    priority: Literal["CRITICAL", "HIGH", "MEDIUM"]
    action: Literal["IMMEDIATE_MAINTENANCE", "SCHEDULE_MAINTENANCE", "MONITOR_EQUIPMENT"]
    target_sku: Optional[str] = None
    justification: str
    approved_for_dispatch: bool

    model_config = ConfigDict(extra="forbid")
