# DataClean Studio

> **Enterprise MySQL Data Quality & Cleaning Platform** — Zero-production-risk, in-database staging, executive-grade audit reports.

---

## Overview

DataClean Studio is an interactive web platform for assessing and cleaning MySQL data quality. Built with **Streamlit (Python)** and **MySQL 8.x**, it provides a **zero-production-risk** environment where all transformations occur on isolated, in-database workspace tables — production tables remain strictly **read-only**.

### The Problem It Solves

Organizations face persistent data quality issues in MySQL databases:
- **Duplicate records** inflating counts and skewing analytics
- **Inconsistent formatting** — dates (`DD/MM/YYYY` vs `MM/DD/YYYY`), casing, boolean representations (`Y/N`, `1/0`, `true/false`)
- **Missing values** (NULLs, blank strings) breaking downstream pipelines
- **Whitespace anomalies** causing join failures and lookup misses
- **No audit trail** — manual cleaning leaves no compliance-ready record

Traditional approaches either risk modifying production data directly, require complex ETL pipelines, or lack auditability for governance.

### What It Delivers Today (v1.2)

| Capability | Description |
|------------|-------------|
| **In-Database Staging** | Creates isolated workspace tables (`{table}__cleaning_{uuid}`) — production never touched |
| **Data Profiling** | Column-level metrics: row count, null %, distinct cardinality, quality scores |
| **Duplicate Detection** | Full-row & business-key deduping with interactive group review & per-group actions |
| **Date Standardization** | Rule-based parsing: textual months (`Jan`, `September`) + numeric (`DD/MM/YYYY`), ambiguity → NULL |
| **Boolean Normalization** | 20+ true/false variants (`Y/N`, `Yes/No`, `1/0`, `Active/Inactive`) → canonical mapping |
| **Text Casing** | UPPER, lower, Title Case, Sentence case per column |
| **Whitespace & Blanks** | Trim, blank→NULL, NULL→default with preview |
| **Multi-Workspace** | Multiple independent workspaces per source table, persist across sessions |
| **Executive PDF Reports** | Branded audit reports: source profile → transformations → workspace profile + delta metrics |
| **Secure Credential Handling** | In-memory only (Streamlit session state), never persisted; auto-dismiss error dialogs |
| **Schema-Agnostic** | 100% dynamic via `INFORMATION_SCHEMA` — zero config, works on any MySQL database |

---

## Architecture Highlights

- **Layered design**: Presentation → Orchestration → Rule Engine → Profiling → Reporting → Connectivity
- **Safety gates**: All DML targets verified `__cleaning_` suffix; identifier escaping via `_quote_identifier()`
- **Parameter binding**: All literals via SQLAlchemy bound params — no string interpolation
- **Atomic operations**: Scoped connections with explicit rollback on failure
- **Design system**: Graphite/silver glassmorphism, CSS custom properties, responsive breakpoints

---

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | Streamlit ≥1.25 |
| Backend | Python 3.14 (≥3.9) |
| Database | MySQL 8.x (via `mysql-connector-python`) |
| ORM/Inspection | SQLAlchemy ≥2.0 (Core) |
| Data Processing | pandas ≥2.0 |
| PDF Generation | fpdf2 ≥2.7 |
| Testing | pytest 9.1 + Faker |

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/<your-username>/data-clean-studio.git
cd data-clean-studio

# 2. Install dependencies
pip install -r requirements.txt

# 3. Run
streamlit run app.py
# Opens at http://localhost:8501
```

**Sidebar** → Enter MySQL credentials (Host, Port, User, Password, Database) → Connect → Select table → Start cleaning.

---

## Project Status

> **⚠️ Under Active Development**
>
> This is v1.2 Standard. Core staging, profiling, cleaning, and reporting are functional.
> **More data cleaning features to be added** in subsequent releases.
>
> After successful data cleaning in the workspace, the cleaned data can be migrated to the production database.

See [ROADMAP.md](.planning/ROADMAP.md) for detailed milestones.

---

## Testing

```bash
# Run full test suite
pytest tests/ -v

# Run specific stage
pytest tests/test_stage4.py -v   # Duplicate detection
pytest tests/test_stage7_date_format.py -v  # Date standardization
```

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit changes (`git commit -m 'feat: add amazing feature'`)
4. Push to branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

---

**Built with ❤️ for data teams who need safe, auditable, production-grade data cleaning.**