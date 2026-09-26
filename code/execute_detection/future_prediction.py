from code.llm_setup.llm import complete
import json

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
"""

    return complete(prompt)