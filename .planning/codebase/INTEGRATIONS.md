---
last_mapped_commit: df6531c57a6b9e852d2a034c380a3e98ef1c60d1
last_mapped_at: 2026-10-09
---
# External Integrations

**Analysis Date:** 2026-10-09

## Database Integrations

**MySQL 8.x Server:**
- **Driver:** `mysql-connector-python` via SQLAlchemy dialect `mysql+mysqlconnector`
- **Connection Management:** `MySQLConnectionManager` in `src/connection.py` handles thread-safe engine creation, session tokens, pool pre-pinging, and connection validation with lightweight `SELECT 1` ping.
- **Metadata Inspection:** `MySQLMetadataInspector` in `src/metadata.py` inspects MySQL schemas, tables, constraints (Primary Key, Foreign Key), nullability, and column types. Queries `INFORMATION_SCHEMA.COLUMNS` directly in `src/profiling.py`.
- **System Database Filtering:** Automatically excludes system schemas:
  - `information_schema`
  - `performance_schema`
  - `mysql`
  - `sys`
- **Error Interception:** Categorized handling for MySQL error codes:
  - Error `1045`: Invalid credentials / Access denied
  - Error `2002` / `2003`: Server unavailable or unreachable host/port
  - Error `1049`: Unknown/missing database schema
  - Timeout errors: Connection timeout alerts

## AI & LLM Services (Staged)

**OpenAI / LLM API:**
- **Status:** Integrated into dependency tree (`openai>=1.0.0`, `tiktoken`, `tenacity`) for planned generative data cleaning assistance.
- **Use Cases:**
  - Automated anomaly classification and cleaning recommendations
  - Ambiguous date interpretation suggestions
  - Intelligent regex pattern generation for unstructured text
- **Resilience:** `tenacity` library configured for exponential backoff retries on rate limits (HTTP 429) and transient server errors (HTTP 500/503).
- **Prompt Safety:** `tiktoken` utilized to calculate token budgets and prevent context length overflow during table profiling summaries.

## Data Persistence & Staging Workspaces

**MySQL In-Database Workspace Staging:**
- **Mechanism:** Workspaces are isolated staging tables created dynamically on the connected MySQL server using naming pattern:
  `{source_table}__cleaning_{uuid_hex[:8]}`
- **Isolation:** All cleaning modifications (casing, trimming, null imputation, duplicate deletion, date standardization) execute exclusively on the workspace staging table.
- **Source Protection:** Production source tables remain strictly read-only until explicit user-directed commit or export.
- **Lifecycle Management:** Managed in `src/staging.py` via `create_workspace`, `attach_workspace`, `list_workspaces_for_table`, `delete_workspace`, and `delete_all_workspaces`.

## Reporting & File Exports

**PDF Audit Reporting:**
- **Engine:** `fpdf2` via `src/pdf_report.py` (`generate_executive_profile_pdf`).
- **Output:** Publication-grade PDF audit logs containing data quality scores, completeness metrics, issue breakdowns, and cleaning logs.
- **Compatibility:** ASCII/Latin-1 font sanitization (`sanitize_pdf_text`) ensures special characters, arrows, and status icons encode cleanly without font rendering crashes.

**CSV / Tabular Exports:**
- Integrated into Streamlit UI via Pandas `.to_csv()` download triggers for cleaned dataset extracts.

## Authentication & Security Protocols

**Credential Handling:**
- No credentials stored in persistent files, environment variables, or databases.
- Credentials supplied interactively via password-masked Streamlit widgets.
- Held in volatile memory during the active Streamlit session and cleared on page reset or session termination.

---

*Integrations analysis: 2026-10-09*
*Update when external interfaces or databases change*
