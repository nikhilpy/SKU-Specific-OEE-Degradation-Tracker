# Phase 4: Command Center UI & MCP Integration — Plan

> **Context**: Phase 3 (Multi-Agent Orchestration) is being developed in parallel. This plan defines everything Phase 4 can independently build and the minimum stubs required from the data layer (Phases 1 & 2) to operate without Phase 3.

---

## Phase 4 Goal (from README)

> Build the interactive Streamlit Command Center frontend and wire the "Mitigate Impact" button to the Slack MCP connector via the Execution Agent.

**Three canonical tasks from the README:**
- **Task 4.1** — Install & authenticate the local Slack MCP server in Antigravity IDE  
- **Task 4.2** — Scaffold the Streamlit app with an IT/OT data grid + chat UI connected to the Investigative Agent  
- **Task 4.3** — Embed the "Mitigate Impact" button and wire it to invoke the Execution Agent → MCP `post_message` → Slack  

---

## Prerequisites (Phase 4 Independent)

These are requirements Phase 4 needs that are **not** blocked by Phase 3 work.

### ✅ HARD Prerequisites (must be in place before any Phase 4 code runs)

| # | Prerequisite | Owner | Notes |
|---|---|---|---|
| P1 | **Snowflake account accessible** | You | `.env` already configured (`EHLJRXW-PE25246`) |
| P2 | **Snowflake DB/Schema/Warehouse exist** | Phase 1 | `01-init.sql` creates `OEE_DB`, `OEE_WH`, `OEE_SCHEMA` — must be run |
| P3 | **Raw OT + IT tables populated** | Phase 1 | `data_generator.py` must have been run at least once to seed rows |
| P4 | **IT/OT joined Dynamic Table exists** | Phase 1 | `03-join.sql` — the Streamlit grid queries this view |
| P5 | **RUL/predictive view exists** | Phase 2 | `04-rul.sql` — the dashboard reads failure horizon from this view |
| P6 | **Slack workspace with admin access** | You | Needed to create a Slack App and obtain `Bot User OAuth Token` |
| P7 | **Node.js (≥ 18) installed locally** | You | Required to run the official `@modelcontextprotocol/server-slack` package |
| P8 | **Python environment with dependencies** | You | `pip install -r requirements.txt` + add `streamlit snowflake-snowpark-python` |

### ⚠️ SOFT Prerequisites (Phase 4 can stub/mock these until Phase 3 is done)

| # | Prerequisite | Phase 3 Dependency | Phase 4 Mitigation Strategy |
|---|---|---|---|
| S1 | **Investigative Agent endpoint** | Task 3.3 | Mock with a static Cortex `COMPLETE()` SQL call directly in the app |
| S2 | **Diagnostic Agent failure flag** | Task 3.2 | Stub: query `RUL_VIEW` directly and surface alerts in the UI from SQL |
| S3 | **Execution Agent JSON payload handler** | Task 3.4 | Stub: hardcode the payload shape `{Equipment_ID, Failure_Horizon, SKU_ID, OEM_Constraints}` and call MCP directly |
| S4 | **OEM constraints from vector DB** | Task 3.1 | Stub: hardcode `"Max Sustained Temp: 90°C"` in the Slack message template until Phase 3 wires the real retrieval |

> **Key insight:** Phase 4 can be built and fully demonstrated end-to-end using SQL + direct Cortex LLM calls as stubs. Phase 3 agents simply replace the stubs with orchestrated calls when ready.

---

## Incremental Task Breakdown

### Task 4.0 — Environment & Dependency Setup *(Prerequisite task)*
> **Goal:** Ensure the local dev environment can run Streamlit and connect to Snowflake.

- [ ] **4.0.1** Add `streamlit`, `snowflake-snowpark-python`, and `mcp` to `requirements.txt`
- [ ] **4.0.2** Verify Snowflake connectivity from Python using the existing `.env` credentials
- [ ] **4.0.3** Confirm `OEE_DB.OEE_SCHEMA.V_IT_OT_JOINED` (or equivalent joined view) exists and is queryable
- [ ] **4.0.4** Install Node.js and verify `npx @modelcontextprotocol/server-slack --help` runs cleanly

---

### Task 4.1 — Slack MCP Server Setup
> **Goal:** Install and authenticate the Slack MCP server so Antigravity IDE can invoke `post_message`.

- [ ] **4.1.1** Create a Slack App in the target workspace
  - Go to `api.slack.com/apps` → Create New App → From Scratch
  - App Name: `OEE-Tracker-Bot`
  - Add OAuth Scopes: `chat:write`, `chat:write.public`
  - Install to workspace → copy **Bot User OAuth Token** (`xoxb-...`)
- [ ] **4.1.2** Create the Slack channel `#oee-production-alerts` (or use `#production-planning`)
- [ ] **4.1.3** Configure MCP server entry in Antigravity IDE
  - Create/edit `.agents/mcp_config.json` at workspace root
  - Add the Slack server entry with `SLACK_BOT_TOKEN` env var
- [ ] **4.1.4** Smoke-test MCP connection — verify Antigravity IDE can list tools and call `post_message`

---

### Task 4.2 — Streamlit App Scaffold & Data Grid
> **Goal:** Build the core Streamlit app with navigation, a live IT/OT data table, and predictive alert cards.

#### 4.2.1 — App skeleton & Snowflake session
- [ ] Create `code/streamlit_app/app.py` as the main entry point
- [ ] Create `code/streamlit_app/snowflake_conn.py` — session factory using `snowflake.snowpark` + `.env`
- [ ] Set up Streamlit page config: title, icon, layout = `wide`, dark theme via `config.toml`

#### 4.2.2 — IT/OT Joined Data Grid
- [ ] Query `V_IT_OT_JOINED` dynamic table (limit 200 rows, latest first)
- [ ] Render with `st.dataframe()` with column config:
  - `Temp` displayed as a progress bar heat-map column
  - `Vibration` similarly highlighted
  - `Batch_ID`, `SKU_ID`, `Equipment_ID` as searchable text
- [ ] Add filter widgets: Equipment selector, SKU selector, date range picker

#### 4.2.3 — Predictive Alert Cards
- [ ] Query `V_RUL_FORECAST` (or stub from `04-rul.sql`)
- [ ] Render one `st.metric()` card per at-risk asset showing:
  - Asset ID, Predicted Hours to Failure, Triggering SKU
  - Color-coded: red if `< 48h`, orange if `48–96h`
- [ ] Highlight rows in the data grid where that asset appears

#### 4.2.4 — Sidebar & Navigation
- [ ] Sidebar: logo / header, page navigation (Dashboard, Investigate, Alerts History)
- [ ] Session state setup for selected equipment / active alert context

---

### Task 4.3 — Chat Interface (Investigative Agent UI)
> **Goal:** Embed a natural language Q&A panel wired to the Investigative Agent (or its stub).

#### 4.3.1 — Chat panel layout
- [ ] Add a right-panel chat column (2/3 grid + 1/3 chat, or tabbed layout)
- [ ] Use `st.chat_input()` and `st.chat_message()` for the conversation interface
- [ ] Persist chat history in `st.session_state`

#### 4.3.2 — Agent stub (Phase 3-independent)
- [ ] Create `code/streamlit_app/agent_stub.py`
- [ ] Function `ask_investigative_agent(question, context)`:
  - Builds a prompt with the current alert context (Equipment, SKU, Temp readings, OEM limits stub)
  - Calls Snowflake Cortex `COMPLETE('mistral-large2', prompt)` via SQL
  - Returns the text response
- [ ] Wire the chat input → `ask_investigative_agent()` → display response

#### 4.3.3 — Contextual pre-fill
- [ ] When a user clicks an alert card, pre-fill the chat with a starter question:
  - *"What is driving the thermal stress on [Equipment_ID]?"*
- [ ] Include the active `SKU_ID`, latest `Temp`, and `Failure_Horizon` in the LLM context automatically

---

### Task 4.4 — "Mitigate Impact" Button & MCP Wiring
> **Goal:** Wire the action button to invoke the Slack MCP `post_message` tool.

#### 4.4.1 — Button placement & payload assembly
- [ ] Render a `st.button("🚨 Mitigate Impact", type="primary")` on each alert card
- [ ] On click: assemble the mitigation payload:
  ```python
  payload = {
      "Equipment_ID": selected_equipment,
      "Failure_Horizon": failure_hours,
      "SKU_ID": triggering_sku,
      "OEM_Constraints": "Max Sustained Temp: 90°C"  # stub; Phase 3 replaces this
  }
  ```

#### 4.4.2 — MCP invocation layer
- [ ] Create `code/streamlit_app/mcp_client.py`
- [ ] Function `post_slack_alert(payload)`:
  - Formats the Slack message template from the payload
  - Calls the MCP `post_message` tool (via subprocess or MCP Python SDK)
  - Returns success/failure status
- [ ] Handle errors gracefully (token expired, channel not found, network timeout)

#### 4.4.3 — Slack message template
- [ ] Format the message to match the README narrative:
  ```
  🚨 URGENT: SKU-{SKU_ID} runs are causing critical thermal stress on {Equipment_ID}.
  Predicted bearing failure in {Failure_Horizon} hours.
  OEM Limit: {OEM_Constraints}.
  ACTION REQUIRED: Reduce feed rate by 10% for all upcoming {SKU_ID} batches.
  ```
- [ ] Post to `#oee-production-alerts` channel

#### 4.4.4 — UI confirmation feedback
- [ ] Show `st.success("✅ Mitigation alert sent to #oee-production-alerts")` on success
- [ ] Show `st.error("❌ Failed to send alert: [reason]")` on failure
- [ ] Log the action to an `ALERTS_HISTORY` Snowflake table (insert timestamp, payload, status)

---

### Task 4.5 — Alerts History Page
> **Goal:** Provide an audit trail of all triggered mitigations.

- [ ] **4.5.1** Create `ALERTS_HISTORY` table in Snowflake (`CREATE TABLE IF NOT EXISTS`)
- [ ] **4.5.2** Build "Alerts History" page in Streamlit — query and display all logged alerts
- [ ] **4.5.3** Add CSV export button for the alerts log

---

### Task 4.6 — Phase 3 Integration Handoff Points
> **Goal:** Define the exact integration seams so Phase 3 output can replace the stubs cleanly.

| Stub | Integration Point | Phase 3 Replaces With |
|---|---|---|
| `agent_stub.py` `ask_investigative_agent()` | Function signature: `ask(question, context) → str` | CoCo Investigative Agent REST/SQL call |
| Hardcoded `OEM_Constraints` in payload | `payload["OEM_Constraints"]` field | Cortex vector DB retrieval result from Task 3.1 |
| Direct `RUL_VIEW` SQL query for failure flag | Alert trigger logic | Diagnostic Agent event (Task 3.2) pushes to a Snowflake notification table |
| Hardcoded payload shape | `execution_agent_payload` dict | Full JSON from Task 3.4 Execution Agent |

---

## Summary: Build Order

```
4.0 Environment setup
 └─► 4.1 Slack MCP (parallel)
 └─► 4.2.1 App skeleton + DB session
      └─► 4.2.2 IT/OT data grid
      └─► 4.2.3 Alert cards
      └─► 4.2.4 Sidebar
           └─► 4.3 Chat interface (stub)
           └─► 4.4.1 Button + payload assembly
                └─► 4.4.2 MCP client
                └─► 4.4.3 Slack template
                └─► 4.4.4 UI feedback
                     └─► 4.5 Alerts history
                          └─► 4.6 Phase 3 integration handoff
```

---

## Files to Create

```
code/
└── streamlit_app/
    ├── app.py                 # Main Streamlit entry point
    ├── snowflake_conn.py      # Snowpark session factory
    ├── agent_stub.py          # Cortex LLM stub for Investigative Agent
    ├── mcp_client.py          # MCP post_message wrapper
    ├── pages/
    │   ├── 1_Dashboard.py     # IT/OT grid + alert cards
    │   ├── 2_Investigate.py   # Chat UI page
    │   └── 3_Alerts_History.py
    └── .streamlit/
        └── config.toml        # Dark theme + layout config

.agents/
└── mcp_config.json            # Slack MCP server registration
```
