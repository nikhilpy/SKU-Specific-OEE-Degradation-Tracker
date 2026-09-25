from code.diagnosis import diagnosis
from code.execution import execute
from code.investigative_agent import investigate
from code.predictive import predict
from code.investigation import create_investigation

if __name__ == "__main__":
    prediction = predict()
    diagnosis_result = diagnosis()
    execution_result = execute(diagnosis_result)
    investigation_result = investigate(execution_result)
    create_investigation(investigation_result)