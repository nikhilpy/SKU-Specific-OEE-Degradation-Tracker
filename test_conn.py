import os
import sys
from dotenv import load_dotenv
from snowflake.snowpark import Session

def main():
    dotenv_path = os.path.join(os.getcwd(), '.env')
    load_dotenv(dotenv_path)
    print("User:", os.getenv("SNOWFLAKE_USER"))
    print("Account:", os.getenv("SNOWFLAKE_ACCOUNT"))
    
    connection_parameters = {
        "account": os.getenv("SNOWFLAKE_ACCOUNT"),
        "user": os.getenv("SNOWFLAKE_USER"),
        "password": os.getenv("SNOWFLAKE_PASSWORD"),
        "database": "OEE_DB",
        "schema": "OEE_SCHEMA",
        "warehouse": "OEE_WH",
        # Adding role if necessary, or just relying on defaults
    }
    
    try:
        session = Session.builder.configs(connection_parameters).create()
        print("Successfully connected to Snowflake!")
        
        # Test if view/table exists
        df = session.sql("SHOW TABLES LIKE 'V_IT_OT_JOINED' IN OEE_SCHEMA")
        df_views = session.sql("SHOW VIEWS LIKE 'V_IT_OT_JOINED' IN OEE_SCHEMA")
        df_dynamic_tables = session.sql("SHOW DYNAMIC TABLES LIKE 'V_IT_OT_JOINED' IN OEE_SCHEMA")
        
        found = False
        if df.count() > 0:
            print("Table V_IT_OT_JOINED found.")
            found = True
        if df_views.count() > 0:
            print("View V_IT_OT_JOINED found.")
            found = True
        if df_dynamic_tables.count() > 0:
            print("Dynamic Table V_IT_OT_JOINED found.")
            found = True
            
        if not found:
            print("Could not find V_IT_OT_JOINED as a table, view, or dynamic table. Showing all dynamic tables:")
            session.sql("SHOW DYNAMIC TABLES IN OEE_SCHEMA").show()
            session.sql("SHOW TABLES IN OEE_SCHEMA").show()
            session.sql("SHOW VIEWS IN OEE_SCHEMA").show()
        
    except Exception as e:
        print(f"Error connecting to Snowflake: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
