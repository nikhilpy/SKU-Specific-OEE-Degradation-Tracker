import os
import subprocess
import shutil
import snowflake.connector
from dotenv import load_dotenv

# Load the environment variables from the .env file
load_dotenv()

# Access the variables
db_user = os.getenv('SNOWFLAKE_USER')
db_password = os.getenv('SNOWFLAKE_PASSWORD')
db_account = os.getenv('SNOWFLAKE_ACCOUNT')

# Establish the connection
print("Testing Snowflake connection...")
conn = snowflake.connector.connect(
    account = db_account,
    user = db_user,
    password = db_password,
    warehouse = "COMPUTE_WH",
    database = "OEE_COMMAND_CENTER",
    schema = "FACTORY_FLOOR" 
)

cs = conn.cursor()
try:
    pass
finally:
    cs.close()


conn.close()