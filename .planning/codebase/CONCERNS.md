# Technical Concerns & Architectural Risks

**Analysis Date:** 2026-10-09

## High-Priority Architectural Concerns

### 1. Monolithic Code Files (`app.py` & `src/staging.py`)
- **Issue:**
  - `app.py` contains **7,319 lines** (~401 KB) incorporating page styling, theme toggles, session state variables, navigation routers, UI form components, and stage-by-stage rendering.
  - `src/staging.py` contains **5,365 lines** (~201 KB) implementing workspace lifecycle logic, SQL generation, and transformation operations for Stages 2 through 9.
- **Risk:**
  - High risk of unintended regression during feature additions or bug fixes.
  - Difficult to test individual UI components or stage handlers in isolation.
  - High cognitive load for developers and AI agents reading or modifying code.
- **Recommendation:**
  - Decompose `app.py` into modular components under `src/ui/` (e.g., `src/ui/sidebar.py`, `src/ui/stages/`, `src/ui/components/`).
  - Split `src/staging.py` into focused domain modules (e.g., `src/transformations/duplicates.py`, `src/transformations/dates.py`, `src/workspace.py`).

### 2. Large Table Scalability & Memory Footprint
- **Issue:**
  - Table cloning creates complete copies on the MySQL server (`CREATE TABLE workspace AS SELECT * FROM source`). For tables with millions of rows or multi-gigabyte sizes, this creates significant disk space and I/O overhead.
  - Profiling, duplicate detection, and rule scanning load candidate records into Pandas DataFrames.
- **Risk:**
  - High memory usage on large tables could cause Streamlit worker memory spikes (OOM).
  - Long-running SQL operations might hit connection timeout limits during full table scans.
- **Recommendation:**
  - Implement partition or chunked scanning and configurable sampling limits for tables exceeding 100,000 rows.
  - Add explicit disk and row count warnings before creating workspaces on very large tables.

## Medium-Priority Concerns

### 3. Orphaned Staging Tables
- **Issue:**
  - Temporary workspace tables (`{table}__cleaning_{uuid}`) are persisted directly in the user's database. If a user closes the browser session without clicking "Delete Workspace", these tables remain permanently on the MySQL server.
- **Risk:**
  - Database schema clutter and gradual accumulation of orphaned tables.
- **Recommendation:**
  - Implement automated TTL or timestamp metadata tracking in table comments.
  - Provide an administrative "Cleanup Orphaned Workspaces" tool in the sidebar.

### 4. MySQL Dialect Lock-in
- **Issue:**
  - Code relies heavily on MySQL-specific constructs: backtick quoting, `STR_TO_DATE`, `INFORMATION_SCHEMA.COLUMNS`, and MySQL error numbers (1045, 2002, etc.).
- **Risk:**
  - Cannot readily connect to PostgreSQL, SQLite, Snowflake, or SQL Server without substantial refactoring.
- **Recommendation:**
  - Abstract SQL dialect generation using SQLAlchemy expression constructs where feasible, or isolate dialect adapters.

### 5. Staged AI Dependencies
- **Issue:**
  - `openai`, `tiktoken`, and `tenacity` are declared in `requirements.txt`, but AI capabilities are not yet fully wired into the user workflow.
- **Risk:**
  - Unused dependencies in deployment environments; ambiguous expectations around AI availability.
- **Recommendation:**
  - Implement explicit AI-driven data quality copilot features or document current status as upcoming milestone.

---

*Concerns analysis: 2026-10-09*
*Update as technical debt is addressed or discovered*
