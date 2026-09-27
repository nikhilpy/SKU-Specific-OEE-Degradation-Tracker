import json
import os
import sys

LLM_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "llm_setup"
)

if LLM_DIR not in sys.path:
    sys.path.insert(0, LLM_DIR)

from llm import ask_json

def future_prediction(investigation):

    prompt = f"""
You are a predictive maintenance AI agent.

Analyze the following investigation data:
<Investigation Data>
{json.dumps(investigation, indent=2)}
</Investigation Data>

Using the telemetry, RUL, active SKU, and OEM evidence:

1. Explain the likely degradation.
2. Identify possible causes.
3. Recommend the next maintenance checks.
4. Recommend an appropriate action and priority.

Return your response as JSON with:
- assessment
- possible_causes
- recommended_checks
- action
- priority
- reasoning

<OUTPUT FORMAT>
{
    "assessment": "Predicted degradation due to excessive temperature and vibration",
    "possible_causes": [
        "Insufficient cooling system capacity",
        "Misaligned or worn-out machinery components",
        "Inadequate lubrication or maintenance",
        "Overloading or improper operation"
    ],
    "recommended_checks": [
        "Temperature sensor calibration and accuracy check",
        "Vibration analysis and balancing of machinery components",
        "Cooling system capacity and performance evaluation",
        "Lubrication and maintenance schedule review"
    ],
    "action": "IMMEDIATE_MAINTENANCE",
    "priority": "CRITICAL",
    "reasoning": "Based on the OEM evidence, the equipment has exceeded the predicted degradation threshold. The excessive temperature (85.0\u00b0C) and vibration (7.5 mm/s) levels indicate potential machinery component wear or misalignment. Immediate maintenance is required to prevent equipment failure and ensure production continuity."
}
</OUTPUT FORMAT>
"""

    return ask_json(prompt)