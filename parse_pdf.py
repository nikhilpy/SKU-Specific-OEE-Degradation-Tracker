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

def execute_sql_file(sql_file):

    try:
        cursor = conn.cursor()

        with open(sql_file, "r", encoding="utf-8") as f:
            sql = f.read()

        # Execute individual SQL statements
        statements = [
            statement.strip()
            for statement in sql.split(";")
            if statement.strip()
        ]

        for i, statement in enumerate(statements, start=1):
            print(f"\n[{i}/{len(statements)}]")
            print(statement[:200])

            cursor.execute(statement)

            # Print results for SELECT/DESC/SHOW statements
            if cursor.description:
                rows = cursor.fetchall()

                for row in rows:
                    print(row)

        print(f"\nSuccessfully executed: {sql_file}")

    finally:
        cursor.close()
        conn.close()


if __name__ == "__main__":
    execute_sql_file("05-parse.sql")