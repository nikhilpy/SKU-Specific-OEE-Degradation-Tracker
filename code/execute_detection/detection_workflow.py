from diagnosis import diagnosis
from execution import execute
from investigative_agent import investigate
from predictive import predict
from investigation import create_investigation
from retrieve import retrieve

if __name__ == "__main__":
    prediction = predict()
    diagnosis_result = diagnosis()
    execution_result = execute(diagnosis_result)
    investigation_result = investigate(execution_result)
    create_investigation(investigation_result)