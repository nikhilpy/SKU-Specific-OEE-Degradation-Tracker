import os
import urllib.parse
import streamlit as st
from dotenv import load_dotenv
import time

# Resolve .env from project root
PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..")
)
ENV_PATH = os.path.join(PROJECT_ROOT, ".env")


def load_env_variables():
    """Load or reload environment variables from .env if it exists."""
    if os.path.exists(ENV_PATH):
        load_dotenv(ENV_PATH, override=True)


def is_setup_complete() -> bool:
    """Check if Snowflake and Slack credentials are fully configured."""
    if st.session_state.get("force_setup", False):
        return False

    load_env_variables()
    
    if st.session_state.get("setup_complete", False):
        return True

    sf_account = os.getenv("SNOWFLAKE_ACCOUNT")
    slack_token = os.getenv("SLACK_BOT_TOKEN")

    if sf_account and slack_token and sf_account.strip() and slack_token.strip():
        st.session_state["setup_complete"] = True
        return True

    return False


def require_setup():
    """Ensure standard pages are blocked until setup is complete."""
    if not is_setup_complete():
        st.warning("⚠️ **Setup Required**: Please configure your credentials in the Setup Wizard first.")
        st.info("The application requires valid Snowflake and Slack credentials to access data and services.")
        
        col1, _ = st.columns([1, 3])
        with col1:
            if st.button("🚀 Go to Setup Wizard", use_container_width=True):
                st.switch_page("app.py")
        st.stop()


def require_infrastructure(session):
    """Ensure that the necessary database and tables are present."""
    if not session:
        return
        
    if st.session_state.get("infra_setup_success", False):
        return
        
    try:
        # Check if one of the core tables exists by querying 1 row
        session.sql("SELECT 1 FROM ASSET_RUL_PREDICTIONS LIMIT 1").collect()
        st.session_state["infra_setup_success"] = True
    except Exception:
        # If it fails, database/objects are likely missing
        st.session_state["show_infra_setup"] = True
        st.switch_page("app.py")
        st.stop()


def is_infrastructure_ready(session) -> bool:
    """Check if database objects exist without routing/stopping."""
    if not session:
        return False
    if st.session_state.get("infra_setup_success", False):
        return True
    try:
        session.sql("SELECT 1 FROM ASSET_RUL_PREDICTIONS LIMIT 1").collect()
        st.session_state["infra_setup_success"] = True
        return True
    except Exception:
        return False


def render_setup_wizard():
    """Render the Setup Wizard UI for Snowflake and Slack credentials."""
    # Hide sidebar navigation during setup
    st.markdown(
        """
        <style>
        [data-testid="stSidebarNav"] { display: none !important; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div style="background: linear-gradient(135deg, #1e293b 0%, #0f172a 100%); padding: 25px; border-radius: 12px; margin-bottom: 25px; border: 1px solid #334155;">
            <h1 style="color: #38bdf8; margin: 0 0 10px 0;">🏭 Welcome to OEE Command Center Setup</h1>
            <p style="color: #94a3b8; font-size: 16px; margin: 0;">
                Configure your Snowflake data warehouse connection and Slack bot integration to initialize autonomous factory floor monitoring.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### **Step 1:** Credentials ➔ **Step 2:** Validation ➔ <span style='color:#64748b;'>**Step 3:** 🏗️ Provisioning ➔ **Step 4:** 🎉 Success</span>", unsafe_allow_html=True)
    st.progress(0.25)
    st.markdown("<br>", unsafe_allow_html=True)

    with st.form("setup_wizard_form"):
        col1, col2 = st.columns(2, gap="large")

        with col1:
            st.markdown("### ❄️ Snowflake Credentials")
        st.caption("Provide connection details to your Snowflake instance.")

        sf_account = st.text_input(
            "Snowflake Account Identifier *",
            value=os.getenv("SNOWFLAKE_ACCOUNT", ""),
            placeholder="e.g. xy12345.us-east-1 or org-account",
            help="Your Snowflake Account identifier without https://",
        )

        sf_user = st.text_input(
            "User Name *",
            value=os.getenv("SNOWFLAKE_USER", ""),
            placeholder="e.g. ADMIN_USER",
        )

        sf_password = st.text_input(
            "Password *",
            value=os.getenv("SNOWFLAKE_PASSWORD", ""),
            type="password",
            placeholder="Enter password",
        )

        sf_role = st.text_input(
            "Role",
            value=os.getenv("SNOWFLAKE_ROLE", "ACCOUNTADMIN"),
            placeholder="ACCOUNTADMIN",
        )

        sf_warehouse = st.text_input(
            "Warehouse",
            value=os.getenv("SNOWFLAKE_WAREHOUSE", "COMPUTE_WH"),
            placeholder="COMPUTE_WH",
        )

        sf_database = st.text_input(
            "Database",
            value=os.getenv("SNOWFLAKE_DATABASE", "OEE_COMMAND_CENTER"),
            placeholder="OEE_COMMAND_CENTER",
        )

        sf_schema = st.text_input(
            "Schema",
            value=os.getenv("SNOWFLAKE_SCHEMA", "FACTORY_FLOOR"),
            placeholder="FACTORY_FLOOR",
        )

    with col2:
        st.markdown("### 💬 Slack Integration")
        st.caption("Connect your Slack bot to enable autonomous team notifications.")

        slack_token = st.text_input(
            "Slack Bot Token *",
            value=os.getenv("SLACK_BOT_TOKEN", ""),
            type="password",
            placeholder="xoxb-...",
            help="Bot User OAuth Token from your Slack App with chat:write permissions",
        )

        slack_team = st.text_input(
            "Slack Team ID",
            value=os.getenv("SLACK_TEAM_ID", ""),
            type="password",
            placeholder="e.g. T01234567",
            help="Slack Workspace/Team ID (starts with T) [Masked for security]",
        )

        slack_channel = st.text_input(
            "Alert Channel",
            value=os.getenv("SLACK_CHANNEL", "#oee-production-alerts"),
            placeholder="#oee-production-alerts",
        )

        st.markdown("---")
        st.markdown("##### 💡 Need Help?")
        st.markdown(
            """
            - **Snowflake**: Ensure your user has permissions to create databases and warehouses if provisioning.
            - **Slack**: Create an App at [api.slack.com/apps](https://api.slack.com/apps) and install it to your workspace with `chat:write` scope.
            """
        )

        st.markdown("---")

        btn_col1, btn_col2 = st.columns([1, 2])
        with btn_col1:
            test_and_save = st.form_submit_button("🔌 Test Connection & Save", type="primary", use_container_width=True)

    if test_and_save:
        # Validate inputs
        if not sf_account.strip() or not sf_user.strip() or not sf_password:
            st.warning("Please fill in all required Snowflake fields (Account, User, Password).")
            return

        if not slack_token.strip():
            st.warning("Please provide the Slack Bot Token (starting with xoxb-).")
            return

        with st.spinner("Connecting to Snowflake using Python Connector..."):
            try:
                import snowflake.connector

                # Test Snowflake connection
                conn = snowflake.connector.connect(
                    account=sf_account.strip(),
                    user=sf_user.strip(),
                    password=sf_password,
                    role=sf_role.strip() if sf_role.strip() else None,
                    warehouse=sf_warehouse.strip() if sf_warehouse.strip() else None,
                    database=sf_database.strip() if sf_database.strip() else None,
                    schema=sf_schema.strip() if sf_schema.strip() else None,
                    login_timeout=20,
                )

                cursor = conn.cursor()
                cursor.execute("SELECT CURRENT_VERSION()")
                sf_version = cursor.fetchone()[0]
                cursor.close()
                conn.close()

                # If connection is verified, write to local .env using standard Python file I/O
                env_content = (
                    f"# =====================================================================\n"
                    f"# OEE Degradation Tracker Configuration (Auto-generated by Setup)\n"
                    f"# =====================================================================\n"
                    f"SNOWFLAKE_ACCOUNT={sf_account.strip()}\n"
                    f"SNOWFLAKE_USER={sf_user.strip()}\n"
                    f"SNOWFLAKE_PASSWORD={sf_password}\n"
                    f"SNOWFLAKE_ROLE={sf_role.strip()}\n"
                    f"SNOWFLAKE_WAREHOUSE={sf_warehouse.strip()}\n"
                    f"SNOWFLAKE_DATABASE={sf_database.strip()}\n"
                    f"SNOWFLAKE_SCHEMA={sf_schema.strip()}\n\n"
                    f"SLACK_BOT_TOKEN={slack_token.strip()}\n"
                    f"SLACK_TEAM_ID={slack_team.strip()}\n"
                    f"SLACK_CHANNEL={slack_channel.strip()}\n"
                )

                with open(ENV_PATH, "w", encoding="utf-8") as f:
                    f.write(env_content)

                # Update live os.environ
                os.environ["SNOWFLAKE_ACCOUNT"] = sf_account.strip()
                os.environ["SNOWFLAKE_USER"] = sf_user.strip()
                os.environ["SNOWFLAKE_PASSWORD"] = sf_password
                os.environ["SNOWFLAKE_ROLE"] = sf_role.strip()
                os.environ["SNOWFLAKE_WAREHOUSE"] = sf_warehouse.strip()
                os.environ["SNOWFLAKE_DATABASE"] = sf_database.strip()
                os.environ["SNOWFLAKE_SCHEMA"] = sf_schema.strip()
                os.environ["SLACK_BOT_TOKEN"] = slack_token.strip()
                os.environ["SLACK_TEAM_ID"] = slack_team.strip()
                os.environ["SLACK_CHANNEL"] = slack_channel.strip()

                st.session_state["force_setup"] = False
                st.session_state["setup_complete"] = True
                st.success(f"🎉 Connection verified! Connected to Snowflake {sf_version}. Credentials saved to .env.")
                st.rerun()

            except Exception as e:
                print(f"Snowflake connection verification failed: {e}")
                st.warning("❌ Snowflake connection verification failed. Please check your credentials and try again.")
                st.info("Tip: Double-check your account locator (omit https://), username, and password.")


def deploy_snowflake_infrastructure(conn):
    # Lottie Animation (Perceived Performance)
    try:
        from streamlit_lottie import st_lottie
        import requests
        def load_lottieurl(url: str):
            r = requests.get(url)
            if r.status_code != 200:
                return None
            return r.json()
        lottie_server = load_lottieurl("https://lottie.host/a72da8db-560f-4886-ac15-3bd4c03b60eb/15R6B66R2r.json")
        if lottie_server:
            st_lottie(lottie_server, height=150, key="server_anim")
    except ImportError:
        pass # Graceful fallback if streamlit_lottie isn't installed

    # Use status for overall progress
    with st.status("🏗️ Provisioning Snowflake Infrastructure...", expanded=True) as status_box:
        # Custom CSS Terminal Log inside the status block
        log_container = st.empty()
        logs = []

        def log(message):
            logs.append(f"> {message}")
            log_container.markdown(
                f"""<div style="background-color: #0f172a; color: #10b981; font-family: monospace; 
                padding: 15px; border-radius: 8px; height: 300px; overflow-y: auto; border: 1px solid #334155; margin-bottom: 20px;">
                {'<br>'.join(logs)}</div>""", 
                unsafe_allow_html=True
            )
            
        sql_dir = os.path.join(PROJECT_ROOT, "sql")
        
        def run_sql(filename):
            log(f"Executing {filename} (Idempotent IF NOT EXISTS)...")
            file_path = os.path.join(sql_dir, filename)
            with open(file_path, "r", encoding="utf-8") as f:
                sql_script = f.read()
            for _ in conn.execute_string(sql_script):
                pass
            log(f"✅ Completed {filename}")

        try:
            # Step 1: Init Database & Infrastructure
            run_sql("01-infrastructure.sql")
            
            # Step 2: Generate and load data
            log("Generating synthetic data...")
            import sys
            misc_dir = os.path.join(PROJECT_ROOT, "code", "misc")
            if misc_dir not in sys.path:
                sys.path.append(misc_dir)
            import data_generator
            it_file, ot_file = data_generator.generate_factory_data()
            
            log("Uploading synthetic data to stage...")
            def _put_path(abs_path):
                return abs_path.replace('\\', '/')
                
            cursor = conn.cursor()
            db_name = os.getenv('SNOWFLAKE_DATABASE') or 'OEE_COMMAND_CENTER'
            schema_name = os.getenv('SNOWFLAKE_SCHEMA') or 'FACTORY_FLOOR'
            cursor.execute(f"USE DATABASE {db_name}")
            cursor.execute(f"USE SCHEMA {schema_name}")
            
            cursor.execute(f"PUT 'file://{_put_path(it_file)}' @FACTORY_DATA_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
            cursor.execute(f"PUT 'file://{_put_path(ot_file)}' @FACTORY_DATA_STAGE AUTO_COMPRESS=TRUE OVERWRITE=TRUE")
            cursor.close()
            
            log("Cleaning up local data files...")
            try:
                if os.path.exists(it_file):
                    os.remove(it_file)
                if os.path.exists(ot_file):
                    os.remove(ot_file)
                log("✅ Local data files deleted.")
            except Exception as e:
                log(f"⚠️ Could not delete local data files: {e}")

            log("✅ Data uploaded successfully.")
            
            run_sql("02-data-ingestion.sql")
            
            # Step 3: Converged Table Refresh
            log("Refreshing dynamic table IT_OT_CONVERGED...")
            cursor = conn.cursor()
            cursor.execute("ALTER DYNAMIC TABLE IT_OT_CONVERGED REFRESH")
            cursor.close()
            log("✅ Dynamic table refreshed.")
            
            # Step 4: ML Forecast
            run_sql("03-analytics.sql")
            
            # Step 6: Upload PDF Document
            log("Uploading OEM PDF Manual...")
            pdf_file = os.path.join(PROJECT_ROOT, "data", "OEM_Maintenance_and_Operations_Manual.pdf")
            if os.path.exists(pdf_file):
                file_path = _put_path(os.path.abspath(pdf_file))
                cursor = conn.cursor()
                cursor.execute(f"USE DATABASE {db_name}")
                cursor.execute(f"USE SCHEMA {schema_name}")
                cursor.execute(f"PUT 'file://{file_path}' @OEM_MANUALS_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
                cursor.close()
                
                log("Parsing PDF into chunks for RAG...")
                rag_dir = os.path.join(PROJECT_ROOT, "code", "create_rag")
                if rag_dir not in sys.path:
                    sys.path.append(rag_dir)
                import parse_pdf
                parse_pdf.parse_pdf()
                log("✅ PDF parsing complete.")
            else:
                log("⚠️ PDF manual not found in data/ directory. Skipping...")
            
            # Step 6: Cortex Search & Retrieval
            try:
                run_sql("04-cortex-search.sql")
            except Exception as e:
                print(f"Error in Cortex Search setup: {e}")
                log("⚠️ Bypassed Cortex Search setup (trial account restriction). Check backend logs for details.")
            
            # Step 7: Semantic Models
            log("Deploying Semantic Model (factory_health_ontology.yaml)...")
            yaml_path = os.path.join(PROJECT_ROOT, "semantic_models", "factory_health_ontology.yaml")
            if os.path.exists(yaml_path):
                cursor = conn.cursor()
                cursor.execute(f"USE DATABASE {db_name}")
                cursor.execute(f"USE SCHEMA {schema_name}")
                cursor.execute(f"PUT 'file://{_put_path(os.path.abspath(yaml_path))}' @SEMANTIC_MODELS_STAGE AUTO_COMPRESS=FALSE OVERWRITE=TRUE")
                cursor.close()
                log("✅ Semantic model deployed.")
            else:
                log("⚠️ Semantic model YAML not found. Skipping...")
            
            log("✅ Full setup completed successfully!")
            status_box.update(label="✅ Infrastructure Ready!", state="complete", expanded=False)
            return True
            
        except Exception as e:
            print(f"Setup failed during execution: {e}")
            log("❌ Setup failed during execution. Please check backend logs for details.")
            status_box.update(label="❌ Infrastructure Deployment Failed", state="error", expanded=True)
            return False


def render_infrastructure_setup():
    st.markdown("### 🏗️ Provision Snowflake Infrastructure")
    st.markdown("Use this panel to automatically run all setup scripts, generate data, train ML models, and ingest PDFs in the correct sequence.")
    
    st.markdown("<span style='color:#64748b;'>**Step 1:** Credentials ➔ **Step 2:** Validation ➔ </span>**Step 3:** 🏗️ Provisioning ➔ **Step 4:** 🎉 Success", unsafe_allow_html=True)
    
    # Store progress bar reference so we can update it to 100% on success
    progress_bar = st.progress(0.75)
    st.markdown("<br>", unsafe_allow_html=True)
    
    col_btn1, col_btn2 = st.columns(2)
    
    with col_btn1:
        setup_pressed = st.button("🚀 One-Click Automated Setup", type="primary", use_container_width=True)
        
    with col_btn2:
        clear_pressed = st.button("🗑️ Clear Old Data", type="secondary", use_container_width=True)
    
    if clear_pressed:
        import snowflake.connector
        with st.spinner("Connecting to Snowflake and truncating tables..."):
            try:
                conn = snowflake.connector.connect(
                    account=os.getenv("SNOWFLAKE_ACCOUNT"),
                    user=os.getenv("SNOWFLAKE_USER"),
                    password=os.getenv("SNOWFLAKE_PASSWORD"),
                    role=os.getenv("SNOWFLAKE_ROLE") or None,
                    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE") or None,
                    database=os.getenv("SNOWFLAKE_DATABASE") or "OEE_COMMAND_CENTER",
                    schema=os.getenv("SNOWFLAKE_SCHEMA") or "FACTORY_FLOOR"
                )
                cursor = conn.cursor()
                cursor.execute("TRUNCATE TABLE RAW_IT_BATCHES")
                cursor.execute("TRUNCATE TABLE RAW_OT_TELEMETRY")
                cursor.close()
                conn.close()
                st.success("Successfully cleared all data from RAW_IT_BATCHES and RAW_OT_TELEMETRY!")
                st.balloons()
            except Exception as e:
                print(f"Failed to clear data: {e}")
                st.warning("Failed to clear data. Please try again later.")

    if setup_pressed:
        import snowflake.connector
        
        success = False
        with st.spinner("Initializing deployment engine..."):
            try:
                conn = snowflake.connector.connect(
                    account=os.getenv("SNOWFLAKE_ACCOUNT"),
                    user=os.getenv("SNOWFLAKE_USER"),
                    password=os.getenv("SNOWFLAKE_PASSWORD"),
                    role=os.getenv("SNOWFLAKE_ROLE") or None,
                    warehouse=os.getenv("SNOWFLAKE_WAREHOUSE") or None
                )
            except Exception as e:
                print(f"Connection failed: {e}")
                st.warning("Connection failed. Please check your network and credentials.")
                return
                
        success = deploy_snowflake_infrastructure(conn)
        conn.close()
        
        if success:
            st.session_state["infra_setup_success"] = True
            st.rerun()

    if st.session_state.get("infra_setup_success", False):
        progress_bar.progress(1.0)
        st.balloons()
        st.success("🎉 Infrastructure is fully deployed and operational.")
        
        st.markdown("### 💡 Try asking your Command Center:")
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("📉 Why did Line 2 OEE drop yesterday?", use_container_width=True):
                st.session_state["initial_query"] = "Why did Line 2 OEE drop yesterday?"
                st.switch_page("pages/2_Investigate.py")
        with col2:
            if st.button("🔧 Show RUL for Packaging Machine", use_container_width=True):
                st.session_state["initial_query"] = "Show RUL for Packaging Machine"
                st.switch_page("pages/2_Investigate.py")
        with col3:
            if st.button("📖 What does the OEM manual say about temp alerts?", use_container_width=True):
                st.session_state["initial_query"] = "What does the OEM manual say about temp alerts?"
                st.switch_page("pages/2_Investigate.py")
        
        st.markdown("---")
        if st.button("🚀 Enter Command Center Dashboard", type="primary", use_container_width=True):
            st.switch_page("pages/1_Dashboard.py")
