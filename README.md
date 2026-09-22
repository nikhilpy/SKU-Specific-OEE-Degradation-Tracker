# SKU-Specific OEE Degradation Tracker

Snowflake CoCo-native prototype that converges high-frequency OT sensor streams with low-frequency IT batch schedules to identify exactly which product runs are destroying machine health.

## 1. Detailed Problem Statement

Manufacturing plants suffer from persistent unplanned downtime because physical machine telemetry (OT) and enterprise business logic (IT) operate in isolated silos. When a critical asset degrades, reliability engineers observe the physical symptoms (e.g., escalating vibration or temperature) but lack the immediate operational context (e.g., what specific product was running, which batch caused the spike, or what material was being processed). 

This disconnect prevents factories from identifying the true root cause of equipment fatigue. Consequently, plants experience recurring "micro-stoppages" and accelerated wear that destroy Overall Equipment Effectiveness (OEE) because the machinery is blindly treated for mechanical failure rather than being optimized for the specific product mix that is causing the stress.

## 2. Proposed Solution

The "SKU-Specific OEE Degradation Tracker" is a Snowflake CoCo-native prototype that converges high-frequency OT sensor streams with low-frequency IT batch schedules to identify exactly which product runs are destroying machine health.

The system continuously joins synthetic telemetry data with ERP production records to map physical asset stress directly to specific SKUs. A CoCo multi-agent orchestration workflow detects these stress patterns, predicts the asset's Remaining Useful Life (RUL), and investigates the root cause. It extracts maximum operational limits from unstructured OEM equipment manuals to validate the anomaly, and finally uses a Model Context Protocol (MCP) connector to automatically trigger a mitigation alert in Slack, turning an obscure machine warning into an automated, business-aware supply chain action.

## 3. Compatibility Review with Challenge Rubrics

This prototype is meticulously reverse-engineered to score maximum points across the specified judging criteria:

*   **IT/OT Convergence:** Merges real-time sensor streams (OT) with ERP schedule records (IT) via a time-series boundary join in Snowflake Dynamic Tables.
*   **Predict Failures & Natural Language Root Cause:** Implements a predictive model to forecast failure horizons and uses an Investigative Agent to explain the SKU-to-degradation correlation in conversational text.
*   **Command Center & Action:** Deploys a CoCo-scaffolded Streamlit app allowing plant managers to triage alerts and trigger cross-tool actions.
*   **Synthetic Data Generation:** Uses CoCo to generate referentially consistent IT and OT datasets, avoiding the need for actual production data.
*   **Semantic Model & Ontology:** Authors a unified semantic view linking physical assets to business batches, validated against natural language queries.
*   **Unstructured Processing:** Parses and extracts thermal/vibration constraints from unstructured PDF equipment manuals to ground the agent's reasoning.

### Ingenuity Bonuses Captured:
*   **MCP Connectors:** Wires the Execution Agent to a local Slack MCP server.
*   **Multi-Agent Orchestration:** Coordinates Diagnostic, Investigative, and Execution agents with explicit JSON state handoffs.
*   **Reusable Skills:** Packages the complex IT/OT time-series SQL join as a distinctly documented, publishable CoCo skill.

## 4 & 5. Phase-Wise Project Plan & System Analysis WBS

This Work Breakdown Structure decomposes the prototype lifecycle into incrementally achievable goals.

### Phase 1: Foundation (Data & Pipelines)
**Goal:** Generate consistent factory floor data and establish the transformation pipelines.
*   **Task 1.1:** Write a Python script to continuously generate synthetic OT data (`Timestamp`, `Equipment_ID`, `Temp`, `Vibration`) and stream it into a raw Snowflake table. Program explicit 15% temperature spikes.
*   **Task 1.2:** Write a script to generate synthetic IT data (`Batch_ID`, `SKU_ID`, `Equipment_ID`, `Start_Time`, `End_Time`). Ensure the time blocks for "SKU-899" perfectly overlap with the OT temperature spikes.
*   **Task 1.3:** Build a Snowflake Dynamic Table that executes a `BETWEEN` join, mapping the OT timestamps squarely inside the IT batch duration blocks. Package this SQL as a CoCo Reusable Skill.

### Phase 2: Predictive Modeling & Semantic Ontology
**Goal:** Define the predictive methodology and structure the data for natural language interactions.
*   **Task 2.1 (Predictive Model Selection):**
    *   **Option A:** Snowflake ML Forecasting *(Medium Difficulty, High Value)*. Use Snowflake Cortex ML functions to forecast the OT metric trajectory based on the SKU schedule.
    *   **Option B:** SQL Rule-Based RUL *(Low Difficulty, Rigid)*. Write a view that calculates failure in X hours if the current `Temp > Threshold`.
    *   **Option C:** LLM Reasoning *(Low Difficulty, High Risk)*. Prompt an agent to estimate RUL based on the data. *(Recommendation: Option A or B for reliable prototype execution).*
*   **Task 2.2:** Use the CoCo CLI to generate a Semantic Model on top of the joined dynamic tables. Explicitly define the relationships between assets and SKUs in the ontology.

### Phase 3: Unstructured Knowledge & Multi-Agent Orchestration
**Goal:** Inject OEM constraints and coordinate the AI reasoning workflow.
*   **Task 3.1:** Upload a mock PDF equipment manual. Use CoCo's unstructured processing to chunk, vectorize, and index the document in Snowflake, linking it to the `Equipment_ID`.
*   **Task 3.2:** Configure the Diagnostic Agent to monitor the semantic model for the predictive failure threshold.
*   **Task 3.3:** Configure the Investigative Agent to receive the failure flag, query the semantic model to identify the active SKU during the degradation, and query the PDF manual to validate the OEM limits.
*   **Task 3.4:** Configure the Execution Agent to receive the final JSON payload containing the SKU, the predicted failure date, and the OEM evidence.

### Phase 4: Command Center UI & MCP Integration
**Goal:** Build the interactive frontend and automate the external Slack action.
*   **Task 4.1:** Install the official Slack MCP server locally in Anigravity IDE and authenticate it.
*   **Task 4.2:** Use CoCo to scaffold the Streamlit app. Build a UI displaying the joined IT/OT data grid alongside a chat interface connected to the Investigative Agent.
*   **Task 4.3:** Embed a "Mitigate Impact" button in the UI. Wire this button to invoke the Execution Agent, triggering the MCP `post_message` tool to push the automated alert into a Slack channel.

## 6. Real-World Use Case Narrative

A high-volume packaging facility runs continuous operations. At 10:00 AM, the Streamlit Command Center flashes a predictive alert: 

> *"Drive-End Bearing Failure Forecasted in 72 Hours on Line 2."*

Instead of dispatching a mechanic to blindly inspect the machine, the Plant Manager asks the Command Center, *"What is driving the thermal stress on Line 2?"* 

The Investigative Agent analyzes the IT/OT semantic model and replies: 
> *"Line 2 baseline temperature rises by 18 degrees exclusively during SKU-899 (Heavy-Duty Cardboard) batch runs. According to the OEM AX-200 manual, this sustained temperature exceeds the maximum continuous operating limit of 90°C, accelerating bearing fatigue."*

The Plant Manager clicks **"Mitigate Impact"** on the dashboard. The Execution Agent connects via MCP to the corporate Slack workspace and automatically posts a message to the `#production-planning` channel: 

> *"URGENT: SKU-899 runs are causing critical thermal stress on Line 2. Please reduce feed rate by 10% for all upcoming SKU-899 batches to preserve bearing life until scheduled weekend maintenance."*

## 7. System Architecture Diagram

```mermaid
C4Container
title Container diagram for SKU-Specific OEE Degradation Tracker

Person(manager, "Plant Manager", "Monitors dashboard, investigates root causes via chat, and triggers mitigations.")

System_Boundary(ingestion, "Data Ingestion Layer") {
    Container(ot_stream, "OT Data Streamer", "Python Script", "Generates and streams high-frequency synthetic sensor telemetry.")
    Container(it_stream, "IT Data Streamer", "Python Script", "Generates and streams low-frequency ERP batch schedules.")
}

System_Boundary(snowflake, "Snowflake Storage & Compute Layer") {
    ContainerDb(raw_ot, "Raw OT Table", "Snowflake Table", "Stores incoming high-frequency OT data.")
    ContainerDb(raw_it, "Raw IT Table", "Snowflake Table", "Stores incoming low-frequency IT data.")
    Container(dynamic_tables, "Snowflake Dynamic Tables", "Snowflake SQL", "Executes the time-series boundary join between OT timestamps and IT batch durations.")
    ContainerDb(cortex_vector, "Cortex Search Vector Store", "Snowflake Vector DB", "Stores chunked OEM PDF equipment manuals for unstructured retrieval.")
    Container(semantic_layer, "Semantic Layer & CoCo Agents", "Snowflake CoCo", "Provides unified ontology and coordinates diagnostic/investigative agent reasoning.")
}

System_Boundary(app_action, "Application & Action Layer") {
    Container(streamlit_app, "Command Center Dashboard", "Streamlit", "Queries the semantic layer, hosts the Chat UI, and provides mitigation action buttons.")
    Container(mcp_server, "Local Slack MCP Server", "Model Context Protocol", "Exposes Slack integration tools to the execution agent.")
}

System_Ext(slack_workspace, "Slack Workspace", "Corporate communication platform (e.g., #production-planning channel).")

Rel(ot_stream, raw_ot, "Streams telemetry data into", "Python Connector")
Rel(it_stream, raw_it, "Streams batch schedule data into", "Python Connector")

Rel(raw_ot, dynamic_tables, "Feeds")
Rel(raw_it, dynamic_tables, "Feeds")

Rel(dynamic_tables, semantic_layer, "Provides joined structured data to")
Rel(cortex_vector, semantic_layer, "Provides unstructured OEM limits to")

Rel(manager, streamlit_app, "Views alerts, asks natural language questions, and clicks mitigation triggers")
Rel(streamlit_app, semantic_layer, "Queries ontology & invokes investigative agents", "SQL / API")
Rel(streamlit_app, mcp_server, "Routes execution agent payloads to", "MCP Protocol")

Rel(mcp_server, slack_workspace, "Pushes automated work orders and mitigation alerts to", "Slack API")
```
## 8. Sequence Diagram for multi-agent orchestration workflow

```mermaid
sequenceDiagram
    participant SSM as Snowflake Semantic Model
    participant DA as Diagnostic Agent
    participant IA as Investigative Agent
    participant CVDB as Cortex Vector DB
    participant EA as Execution Agent
    participant MCP as Slack MCP Server

    SSM->>DA: Predictive Failure Threshold Breach Flag
    
    DA->>IA: {"Equipment_ID": "Line2_Bearing", "Failure_Horizon": "72_Hours"}
    
    IA->>SSM: Query Active SKU_ID at Anomaly Timestamp
    SSM-->>IA: {"SKU_ID": "SKU-899"}
    
    IA->>CVDB: Query OEM constraints for Equipment_ID
    CVDB-->>IA: {"OEM_Constraints": "Max Sustained Temp 90C"}
    
    IA->>EA: {"Equipment_ID": "Line2_Bearing", "Failure_Horizon": "72_Hours", "SKU_ID": "SKU-899", "OEM_Constraints": "Max Sustained Temp 90C"}
    
    EA->>MCP: post_message(channel="#production-planning", text="Mitigation Alert: Reduce SKU-899 feed rate...")
```
## 9. Entity Relationship Diagram for Database Semantic Ontology

```mermaid
erDiagram
    EQUIPMENT {
        string Equipment_ID PK
        string Name
        string Type
    }

    SKU {
        string SKU_ID PK
        string SKU_Name
        string Material_Type
    }

    TELEMETRY_STREAMS_OT {
        string Reading_ID PK
        string Equipment_ID FK
        datetime Timestamp
        float Temp
        float Vibration
    }

    PRODUCTION_BATCHES_IT {
        string Batch_ID PK
        string SKU_ID FK
        string Equipment_ID FK
        datetime Start_Time
        datetime End_Time
    }

    OEM_MANUAL_EMBEDDINGS {
        string Embedding_ID PK
        string Equipment_ID FK
        string Chunk_Text
        string Vector_Data
    }

    EQUIPMENT ||--o{ TELEMETRY_STREAMS_OT : "generates telemetry"
    EQUIPMENT ||--o{ PRODUCTION_BATCHES_IT : "processes"
    EQUIPMENT ||--o{ OEM_MANUAL_EMBEDDINGS : "is documented by"
    SKU ||--o{ PRODUCTION_BATCHES_IT : "is manufactured in"

    %% IT/OT Convergence Logical Join (Snowflake Dynamic Tables)
    TELEMETRY_STREAMS_OT }o--o{ PRODUCTION_BATCHES_IT : "Time-Series Boundary Join (Timestamp BETWEEN Start_Time AND End_Time)"
```
## 10. Data Flow Pipeline

```mermaid
gantt
    title IT/OT Time-Series Boundary Join
    dateFormat  YYYY-MM-DD HH:mm
    axisFormat  %H:%M

    section IT ERP Schedule
    SKU-700 (Batch 4054)     :done, 2026-09-22 09:00, 2026-09-22 10:00
    SKU-899 (Batch 4055)     :active, 2026-09-22 10:00, 2026-09-22 12:00
    SKU-900 (Batch 4056)     :2026-09-22 12:00, 2026-09-22 13:00

    section OT Telemetry Stream
    Ping 1 - Normal (78 C)   :milestone, 2026-09-22 09:15, 0m
    Ping 2 - Normal (80 C)   :milestone, 2026-09-22 09:45, 0m
    Ping 3 - Normal (82 C)   :milestone, 2026-09-22 10:05, 0m
    Ping 4 - SPIKE (92 C)    :milestone, crit, 2026-09-22 10:15, 0m
    Ping 5 - SPIKE (95 C)    :milestone, crit, 2026-09-22 10:45, 0m
    Ping 6 - SPIKE (98 C)    :milestone, crit, 2026-09-22 11:15, 0m
    Ping 7 - SPIKE (93 C)    :milestone, crit, 2026-09-22 11:30, 0m
    Ping 8 - Normal (86 C)   :milestone, 2026-09-22 11:45, 0m
    Ping 9 - Normal (81 C)   :milestone, 2026-09-22 12:15, 0m
    Ping 10 - Normal (79 C)  :milestone, 2026-09-22 12:45, 0m
```
---

## Crucial Prototype Setup Notes:

*   **Slack Workspace Admin Rights:** Ensure you have the necessary administrative privileges in your target Slack workspace to create an app, acquire a Bot User OAuth Token, and grant `chat:write` scopes for the MCP server.
*   **Source for Unstructured Data:** You must procure or generate a mock PDF equipment manual (e.g., a 3-page document detailing operating limits for a motor or gearbox) to ingest into Cortex for the unstructured processing requirement.