import json
import os
import sys

sys.path.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "misc"
))

from snowflake_client import search_oem_manual
from investigative_agent import investigate
from prediction import predict
from future_prediction import future_prediction


def run_workflow(equipment_id="LINE-2-PACKAGING"):

    prediction = predict(equipment_id)

    if not prediction["failure_flag"]:
        return prediction

    parts = prediction['equipment_id'].split("-")
    equipment_type = parts[-1] if len(parts) > 1 else prediction['equipment_id']

    query = (
        f"OEM operating limits for "
        f"{equipment_type} equipment, "
        f"temperature and vibration"
    )

    investigation_result = investigate(
        prediction,
        oem_evidence=search_oem_manual(query)
    )

    final_prediction = future_prediction(investigation_result)
    print("Final", end="\n")
    print(json.dumps(final_prediction, indent=4))
    return final_prediction

if __name__ == "__main__":
    run_workflow()
