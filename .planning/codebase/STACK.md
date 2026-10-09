# Technology Stack

**Analysis Date:** 2026-10-09

## Languages

**Primary:**
- Python 3.14 (supports Python >= 3.9) - All core backend logic, data processing, and Streamlit frontend application code

**Secondary:**
- SQL (MySQL 8.x dialect) - Dynamic DDL/DML queries for workspace staging, metadata queries against `INFORMATION_SCHEMA`, profiling queries, and row-level transformation statements

## Runtime

**Environment:**
- Python 3.14.6 (CPython)
- Web Application Runtime: Streamlit Local Server (default port 8501)
- Multi-threading: Thread locks (`threading.Lock`) used in `MySQLConnectionManager` for thread-safe session management

**Package Manager:**
- pip
- Dependency specification: `requirements.txt`

## Frameworks

**Core:**
- Streamlit >= 1.25.0 - Interactive web UI, reactive session state management, multi-step workflow presentation, data tables, and custom CSS styling
- SQLAlchemy >= 2.0.0 - Database engine abstraction, metadata inspection, schema discovery, and connection pooling

**Testing:**
- Pytest 9.1.1 - Unit test runner, test discovery, parametrized fixtures, and mock assertions

**Reporting:**
- fpdf2 >= 2.7.0 - Executive-ready PDF report generation with custom layouts, typography, and charts

## Key Dependencies

**Critical:**
- `sqlalchemy>=2.0.0` - Database connectivity abstraction and metadata inspection
- `mysql-connector-python>=8.0.0` - Native MySQL database driver integrated with SQLAlchemy via `mysql+mysqlconnector`
- `pandas>=2.0.0` - Tabular data manipulation, preview rendering, and statistical data profiling
- `fpdf2>=2.7.0` - PDF compilation engine for audit log reports and executive summary exports
- `python-dotenv>=1.0.0` - Environment configuration management

**AI / LLM Integration (Staged for GenAI Expansion):**
- `openai>=1.0.0` - OpenAI API SDK client
- `tiktoken` - Token estimation for context window management
- `tenacity` - Exponential backoff and retries for resilient API communication

**Development & Test Utilities:**
- `Faker>=40.36.0` - Synthetic data generation for unit and stage test fixtures

## Configuration

**Environment:**
- Runtime configuration dynamically provided via Streamlit sidebar credential inputs (Host, Port, User, Password, Database)
- Credentials kept strictly in-memory within `st.session_state` and connection pools, never persisted to disk or log files
- Optional `.env` support via `python-dotenv`

**Application Styling:**
- Embedded CSS injected via `st.markdown(unsafe_allow_html=True)`
- Base64-encoded background branding assets (`Background.png`, `img/Background.png`)
- Custom UI components with enterprise soft dark / light theme support

## Platform Requirements

**Development:**
- Windows 10/11, macOS, or Linux
- Python 3.9+ (Active: Python 3.14.6)
- MySQL Server 8.0+ instance (local or remote) with user privileges for `CREATE TABLE`, `DROP TABLE`, `ALTER TABLE`, `SELECT`, `INSERT`, `UPDATE`, `DELETE`

**Production / Deployment:**
- Streamlit Community Cloud, Docker container, or cloud VM (AWS EC2, GCP Compute Engine)
- Network connectivity to target MySQL database host and port (default 3306)

---

*Stack analysis: 2026-10-09*
*Update after major dependency changes*
