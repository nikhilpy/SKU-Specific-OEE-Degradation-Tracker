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

# Kept as a plain string: inside the f-string below its literal
# braces would be parsed as format fields.
OUTPUT_SCHEMA = """
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
    "reasoning": "Based on the OEM evidence, the equipment has exceeded the predicted degradation threshold."
}
"""


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

Quote the actual limits and RUL from the investigation data. Do not
reuse values from this example.

Return your response as JSON matching the shape below.

<OUTPUT FORMAT>
{OUTPUT_SCHEMA}
</OUTPUT FORMAT>
"""

    return ask_json(prompt)