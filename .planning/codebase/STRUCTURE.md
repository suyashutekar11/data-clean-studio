---
last_mapped_commit: df6531c57a6b9e852d2a034c380a3e98ef1c60d1
last_mapped_at: 2026-10-09
---
# Directory Structure & File Organization

**Analysis Date:** 2026-10-09

## Directory Layout

```
D:/DATA CLEANING TOOL/
├── .planning/                  # GSD planning directory
│   └── codebase/               # Codebase architecture & mapping documentation
├── .streamlit/                 # Streamlit configuration settings
│   └── config.toml             # Theme and server configurations
├── frontend/                   # Frontend assets / alternative web UI artifacts
├── img/                        # Branding images and UI static assets
│   └── Background.png          # App background graphic
├── src/                        # Core backend library and domain modules
│   ├── __init__.py             # Module initialization
│   ├── advanced_date_standardization.py # Rules 1 & 2 date parsing engine
│   ├── connection.py           # MySQL session & SQLAlchemy engine manager
│   ├── date_rules.py           # Date pattern definitions, dataclasses, regex rules
│   ├── metadata.py             # Schema, table, and column metadata inspector
│   ├── pdf_report.py           # Executive PDF data quality report generator
│   ├── profiling.py            # Column statistics and data profiling engine
│   └── staging.py              # In-database workspace staging & transformations
├── tests/                      # Automated test suite (203 passing tests)
│   ├── test_pdf_report.py      # PDF generation test coverage
│   ├── test_stage1.py          # MySQL connection & discovery unit tests
│   ├── test_stage2.py          # Workspace creation & staging table tests
│   ├── test_stage3.py          # Whitespace & blank value cleaning tests
│   ├── test_stage4.py          # Missing value detection & imputation tests
│   ├── test_stage5_casing.py   # Text casing normalization tests
│   ├── test_stage6_duplicates.py # Duplicate detection & interactive row actions
│   ├── test_stage7_date_format.py # Native date formatting tests
│   ├── test_stage8_boolean_normalization.py # Boolean type inference & normalization
│   ├── test_stage9_advanced_date_standardization.py # Deterministic date rules
│   └── test_workspace_persistence.py # Multi-workspace discovery and attach tests
├── app.py                      # Main Streamlit web application entry point
├── Background.png              # UI visual backdrop
├── README.md                   # Project documentation & Stage 1 overview
└── requirements.txt            # Python dependencies
```

## Key File Locations & Module Responsibilities

| File | Purpose | Size / Complexity |
|---|---|---|
| `app.py` | Complete Streamlit web interface; sidebar controls, session state, UI rendering, stage workflows | ~7,300 lines |
| `src/staging.py` | Workspace lifecycle management, SQL query generation, DDL/DML execution for Stages 2–9 | ~5,300 lines |
| `src/connection.py` | Thread-safe connection pooling, SQLAlchemy engine creation, credentials management | ~195 lines |
| `src/metadata.py` | SQLAlchemy inspector wrapper for databases, tables, columns, PKs/FKs | ~100 lines |
| `src/profiling.py` | Table and column profiling, completeness metrics, cardinality, and type inspection | ~355 lines |
| `src/date_rules.py` | Dataclasses (`ParseResult`, `ColumnAnalysis`), pattern definitions, regex tokenizers | ~520 lines |
| `src/advanced_date_standardization.py` | Implementation of deterministic Rule 1 (text month) and Rule 2 (numeric date) | ~600 lines |
| `src/pdf_report.py` | Publication-ready PDF export via `fpdf2`, character sanitization, and layout logic | ~725 lines |

## Naming & Organization Conventions

- **Module Naming:** Snake_case Python module files in `src/` (e.g. `advanced_date_standardization.py`).
- **Test Naming:** Prefix `test_` matching stage or functional area (`test_stage*.py`), mirroring development milestones.
- **Table Naming:**
  - Workspace tables follow strict format: `{table_name}__cleaning_{uuid_hex[:8]}`
  - Standardized columns append clear suffixes: `{column_name}_standardized`
- **Internal Helpers:** Private or helper functions prefixed with an underscore (e.g., `_quote_identifier`, `_fmt_to_regex`, `_make_safe_table_name`).

---

*Structure analysis: 2026-10-09*
*Update when directories or files are reorganized*
