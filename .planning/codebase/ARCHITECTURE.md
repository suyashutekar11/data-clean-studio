---
last_mapped_commit: df6531c57a6b9e852d2a034c380a3e98ef1c60d1
last_mapped_at: 2026-10-09
---
# Architecture

**Analysis Date:** 2026-10-09

## Pattern Overview

**Overall:** Interactive Data Quality & Cleaning Web Platform with In-Database Staging and Multi-Stage Transformation Pipeline.

**Key Characteristics:**
- **Zero-Production-Risk Staging:** Production source tables remain strictly read-only; all data operations, transformations, and row deletions occur on dedicated in-database workspace tables (`{table}__cleaning_{uuid}`).
- **Dynamic & Generic Introspection:** 100% agnostic to business domain or table schema; dynamically inspects database structure, data types, and primary/foreign keys using SQLAlchemy and `INFORMATION_SCHEMA`.
- **Hybrid In-Database & In-Memory Execution:** Large set transformations leverage optimized MySQL DDL/DML queries, while complex rule classification and interactive inspection (e.g. duplicate grouping, date ambiguity detection) execute in Python.
- **Auditable & Reversible:** Changes are previewed before application, tracked in audit state, and exportable as executive-grade PDF reports.

## Layers

```
┌────────────────────────────────────────────────────────┐
│             Presentation & Workflow Layer              │
│               app.py (Streamlit Web UI)                │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│          Transformation & Orchestration Layer          │
│                    src/staging.py                      │
│   (Stages 2-9: Whitespace, Nulls, Casing, Duplicates,  │
│          Date Standardizer, Boolean Normalizer)        │
└──────────┬───────────────────┬───────────────────┬─────┘
           │                   │                   │
┌──────────▼──────────┐ ┌──────▼─────────┐ ┌───────▼─────┐
│ Rule & Parse Engine │ │   Profiling    │ │  Reporting  │
│  src/date_rules.py  │ │src/profiling.py│ │src/pdf_     │
│  src/advanced_date_ │ └────────────────┘ │ report.py   │
│  standardization.py │                    └─────────────┘
└──────────┬──────────┘
           │
┌──────────▼─────────────────────────────────────────────┐
│        Database Connectivity & Metadata Layer          │
│       src/connection.py  │  src/metadata.py            │
└──────────────────────────┬─────────────────────────────┘
                           │
┌──────────────────────────▼─────────────────────────────┐
│             Target MySQL Database Server               │
│       Production Tables (RO) │ Staging Workspaces       │
└────────────────────────────────────────────────────────┘
```

### 1. Presentation & Workflow Layer

- **Component:** `app.py`
- **Purpose:** Manages user interactions, credential input forms, workflow stage transitions, real-time data preview tables, and error banners.
- **State Management:** Uses Streamlit reactive session state (`st.session_state`) for credentials, active database, active table, workspace identifier, inspection metrics, and transformation configurations.

### 2. Transformation & Orchestration Layer

- **Component:** `src/staging.py`
- **Purpose:** Core business logic for creating and managing isolated workspace tables, executing data cleaning transformations, and verifying safety constraints.
- **Key Modules/Functions:**
  - `create_workspace`, `attach_workspace`, `delete_workspace`, `list_workspaces_for_table`
  - `remove_whitespace_workspace`, `replace_blank_values_workspace`, `replace_missing_values_workspace`
  - `normalize_text_case_workspace`, `count_text_casing_changes`
  - `detect_duplicates_workspace`, `remove_duplicates_by_row_ids`, row action toggles
  - `detect_boolean_like_columns`, `transform_boolean_column`, `undo_boolean_normalization`
  - `detect_date_columns`, `preview_column_standardization`, `standardize_column`

### 3. Rule & Parsing Engine

- **Components:** `src/date_rules.py`, `src/advanced_date_standardization.py`
- **Purpose:** Deterministic pattern recognition and parsing for unstructured or messy data representations without risk of data corruption.
- **Rule 1 (Textual Month Detection):** Maps month names/abbreviations (`January`, `Aug`, `Sept`) + 4-digit years.
- **Rule 2 (Numeric Date Detection):** Handles date separators (`/`, `-`, `.`), 4-digit years, and unambiguous day components (> 12).
- **Ambiguity Guard:** Unambiguous days (<= 12) or malformed values are converted to `NULL` to prevent false date conversions.

### 4. Profiling & Quality Assessment Layer

- **Component:** `src/profiling.py`
- **Purpose:** Computes comprehensive column-level metrics: total rows, null counts, null percentage, distinct value cardinality, and candidate quality scores.
- **Key Functions:** `profile_table`, `profile_source_table`, `profile_workspace`.

### 5. Export & Audit Reporting Layer

- **Component:** `src/pdf_report.py`
- **Purpose:** Generates executive-ready PDF audit reports summarizing initial data quality, transformations applied, and post-cleaning improvements.

### 6. Database Connectivity & Metadata Layer

- **Components:** `src/connection.py`, `src/metadata.py`
- **Purpose:** Low-level engine creation, connection pooling, credential verification, and schema/table metadata reflection via SQLAlchemy Core and `INFORMATION_SCHEMA`.

## Data Flow

### Typical Cleaning Lifecycle:

1. **Connection & Discovery:**
   - User inputs credentials in sidebar.
   - `MySQLConnectionManager.create_engine()` establishes engine with timeout.
   - `MySQLMetadataInspector.get_databases()` discovers accessible databases.
   - User selects target database and table.
2. **Workspace Creation:**
   - User initiates cleaning workflow.
   - `staging.create_workspace()` creates staging clone (`source_table__cleaning_xxxxxxxx`).
3. **Profiling:**
   - `profiling.profile_table()` profiles baseline data quality.
4. **Iterative Transformation:**
   - User chooses transformation stage (e.g., whitespace trim, duplicate elimination, boolean fix, date standardizer).
   - Python engine generates safe SQL DDL/DML.
   - Changes are previewed with diff metrics.
   - User confirms; transformations commit to the workspace table.
5. **Validation & Reporting:**
   - Workspace is re-profiled to verify improvement metrics.
   - `pdf_report.generate_executive_profile_pdf()` generates downloadable PDF audit document.
6. **Promotion or Teardown:**
   - User can download cleaned data as CSV, promote staging data back to database, or delete temporary workspaces.

## Key Abstractions

- `MySQLConnectionManager`: Thread-safe connection factory and session registry.
- `MySQLMetadataInspector`: Static inspection utility wrapping SQLAlchemy Inspector.
- `ParseResult` & `ColumnAnalysis` dataclasses: Structured representations of date parse outcomes and format distributions.
- `_quote_identifier` & `_quote_table`: Centralized SQL injection prevention and MySQL identifier escaping utilities.

## Error Handling & Transaction Safety

- **Identifier Escaping:** Every identifier (database, table, column) is sanitized and enclosed in backticks (`_quote_identifier`).
- **Workspace Confinement:** All write operations check and enforce that the target table matches the workspace naming convention (`__cleaning_`).
- **Atomic Operations:** DDL/DML statements run inside scoped connection blocks with explicit rollback on failure.
- **Safe Fallback:** Date and boolean parsers never guess ambiguously; unrecognized or conflicting values are left untouched or assigned `NULL` with detailed diagnostics.

---

*Architecture analysis: 2026-10-09*
*Update when major patterns change*
