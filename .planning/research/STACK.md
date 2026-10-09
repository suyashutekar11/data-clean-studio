# Technology Stack

**Project:** Data Cleaning Tool (DCT) — Interactive Data Quality & Cleaning Web Platform
**Researched:** 2026-10-09
**Overall Confidence:** HIGH

---

## Recommended Stack

### Core Framework

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Streamlit** | **1.65.0** (latest stable, Oct 2026) | Interactive web UI, reactive session state, multi-step workflow presentation, data tables, custom CSS styling | Mature, production-stable (Apache 2.0), Python 3.10–3.14 support, largest ecosystem for data apps, zero frontend build step |
| **SQLAlchemy Core** | **2.0.54+** (2.x series, legacy maintenance) | Database engine abstraction, metadata inspection, schema discovery, connection pooling, raw SQL execution | 2.0 style is mandatory (future=True default), Core (not ORM) for dynamic schema, `Inspector` for `INFORMATION_SCHEMA` reflection, `text()` for safe parameterized DDL/DML |

### Database Driver

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **mysql-connector-python** | **26.7.0** (latest, Jul 2026) | Native MySQL driver integrated with SQLAlchemy via `mysql+mysqlconnector` | Official Oracle driver, C-extension for performance, async support, telemetry, Python 3.10–3.14 wheels, GPLv2 with FOSS exception |
| **PyMySQL** | 1.2.3 (Sep 2026) | Pure-Python fallback / alternative driver | MIT license, no C build tools required, PyPy compatible, `mysql+pymysql` dialect, slower than mysql-connector for bulk ops |

### Data Processing

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pandas** | **3.0.6** (latest, Sep 2026) | Tabular data manipulation, preview rendering, statistical data profiling, CSV export | Python 3.11–3.15, PyArrow backend optional, `performance` extra for bottleneck optimizations, free-threading builds available for 3.13+ |
| **numpy** | >=2.0 (transitive via pandas) | Numerical computing backbone for pandas | Required dependency |

### Reporting

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **fpdf2** | **2.8.9** (latest) | Executive-ready PDF report generation with custom layouts, typography, tables, charts | Pure Python, LGPLv3, Unicode/TTF font embedding, SVG import, HTML→PDF, markdown-like styling, 1300+ tests, used in Streamlit apps |

### Configuration & Utilities

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **python-dotenv** | >=1.0.0 | Environment configuration management | Loads `.env` for local dev, credentials never persisted in production |
| **openai** | >=1.0.0 | OpenAI API SDK (staged for GenAI expansion) | LLM integration for future smart cleaning rules |
| **tiktoken** | latest | Token estimation for context window management | Required for OpenAI cost/length control |
| **tenacity** | latest | Exponential backoff & retries for resilient API communication | Handles transient LLM/API failures |
| **Faker** | >=40.36.0 | Synthetic data generation for unit/stage test fixtures | Dev/test only |

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| **Web UI Framework** | Streamlit 1.65 | **Panel** (Holoviz) 1.9.4 | Panel is more powerful (Bokeh-based, reactive params, auth, templates) but steeper learning curve, heavier deps, smaller community for pure data cleaning apps |
| | | **Solara** / **Reflex** / **NiceGUI** | Emerging, less mature, smaller ecosystems, unproven for production data apps |
| | | **Dash** (Plotly) | More verbose, callback-heavy, larger bundle, overkill for form-driven workflows |
| **MySQL Driver** | mysql-connector-python 26.7 | **asyncmy** 0.2.16 | Fastest async driver (2–5x), but requires Cython build tools on Windows, async-only (app is sync), immature for SQLAlchemy 2.0 dialect |
| | | **PyMySQL** 1.2.3 | Pure Python, MIT license, but ~3–5x slower on large result sets, no C-extension |
| | | **mysqlclient** (mysqldb) | C-extension, fast, but unmaintained fork, wheels lag, SQLAlchemy default dialect |
| **PDF Generation** | fpdf2 2.8.9 | **reportlab** | Powerful but verbose API, commercial license for advanced features, steeper learning curve |
| | | **weasyprint** | HTML/CSS→PDF, heavy deps (Cairo, Pango, GDK), hard to deploy on Windows/Cloud |
| | | **xhtml2pdf** | Unmaintained, CSS support limited |
| **Data Profiling** | Custom (pandas-based) | **ydata-profiling** (pandas-profiling) | Heavy, generates full HTML reports, not integrated into workflow, overkill for column-level metrics |
| | | **Great Expectations** | Full validation framework, complex setup, designed for pipelines not interactive cleaning |
| | | **duckdb** | Excellent for in-process analytics, but adds another engine; MySQL staging already handles set operations efficiently |

---

## Installation

```bash
# Core runtime dependencies
pip install \
  "streamlit>=1.65.0" \
  "sqlalchemy>=2.0.0" \
  "mysql-connector-python>=26.7.0" \
  "pandas>=3.0.0" \
  "fpdf2>=2.8.0" \
  "python-dotenv>=1.0.0"

# AI/LLM integration (staged for GenAI expansion)
pip install \
  "openai>=1.0.0" \
  "tiktoken" \
  "tenacity"

# Development & test utilities
pip install -D \
  "pytest>=9.0.0" \
  "Faker>=40.0.0"

# Optional: PyMySQL as pure-Python fallback (no C build)
# pip install "PyMySQL>=1.2.0"

# Optional: asyncmy for future async workloads (requires MSVC Build Tools on Windows)
# pip install "asyncmy>=0.2.16"
```

### Requirements.txt (pinned for reproducibility)

```text
# Core
streamlit==1.65.0
sqlalchemy==2.0.54
mysql-connector-python==26.7.0
pandas==3.0.6
fpdf2==2.8.9
python-dotenv==1.0.1

# AI/LLM (staged)
openai==1.65.0
tiktoken==0.9.0
tenacity==8.5.0

# Dev/Test
pytest==9.1.1
Faker==40.36.0
```

---

## Version Compatibility Matrix

| Component | Python 3.10 | Python 3.11 | Python 3.12 | Python 3.13 | Python 3.14 |
|-----------|-------------|-------------|-------------|-------------|-------------|
| Streamlit | ✅ | ✅ | ✅ | ✅ | ✅ |
| SQLAlchemy 2.0 | ✅ | ✅ | ✅ | ✅ | ✅ |
| mysql-connector-python | ✅ | ✅ | ✅ | ✅ | ✅ |
| PyMySQL | ✅ | ✅ | ✅ | ✅ | ✅ |
| asyncmy | ✅ | ✅ | ✅ | ✅ | ✅ |
| pandas 3.x | ❌ | ✅ | ✅ | ✅ | ✅ |
| fpdf2 | ✅ | ✅ | ✅ | ✅ | ✅ |
| openai | ✅ | ✅ | ✅ | ✅ | ✅ |
| tiktoken | ✅ | ✅ | ✅ | ✅ | ✅ |
| tenacity | ✅ | ✅ | ✅ | ✅ | ✅ |

**Note:** pandas 3.0+ dropped Python 3.10 support (requires 3.11+). Current project uses Python 3.14.6 — all core deps support it.

---

## Key Technical Decisions & Rationale

### 1. Streamlit over Panel/Reflex/Solara
- **Rationale:** Project already built on Streamlit (brownfield). Streamlit 1.65 adds fragments (`@st.fragment`) for partial reruns, better caching (`@st.cache_data`/`resource`), and multipage apps — sufficient for multi-stage cleaning workflows.
- **Migration cost** to Panel would be high (different reactivity model, Bokeh dependency).
- **Future:** If app needs auth, complex dashboards, or embedding → evaluate Panel migration.

### 2. SQLAlchemy Core (not ORM)
- **Rationale:** Dynamic schema (user selects any table), `INFORMATION_SCHEMA` reflection via `Inspector`, raw DDL/DML for staging tables (`CREATE TABLE ... LIKE`, `INSERT ... SELECT`, `ALTER TABLE`).
- ORM adds overhead for no benefit — no domain models, no relationships to manage.

### 3. mysql-connector-python over PyMySQL/asyncmy
- **Rationale:** Official Oracle driver, C-extension performance, synchronous API matches Streamlit's execution model, mature SQLAlchemy dialect (`mysql+mysqlconnector`).
- asyncmy is faster but async-only; would require rewriting connection layer to async — not justified for current sync workload.

### 4. In-Database Staging (not in-memory)
- **Rationale:** Handles tables larger than RAM; leverages MySQL 8.x DDL/DML performance (instant `CREATE TABLE ... LIKE`, bulk `INSERT ... SELECT`, indexed `UPDATE`/`DELETE`).
- MySQL 8.0 features used: CTEs for multi-step transforms, window functions for duplicate detection, `JSON_TABLE` for future rule engine.

### 5. fpdf2 over reportlab/weasyprint
- **Rationale:** Pure Python (no system deps), LGPLv3 (commercial-friendly), Unicode TTF embedding, HTML/markdown support, table engine, active maintenance (2.8.9 Oct 2026).
- reportlab: AGPL/commercial dual license, verbose.
- weasyprint: Heavy native deps (Cairo/Pango), deployment friction.

---

## Emerging Trends to Watch (2025–2026)

| Trend | Impact on DCT | Timeline |
|-------|---------------|----------|
| **Streamlit Fragments** (`@st.fragment`) | Partial reruns for long-running stages (duplicate detection, date standardization) without full app rerun | Now (1.65+) |
| **SQLAlchemy 2.1** (maintenance) | Minor improvements, better typing, deprecation warnings | 2025–2026 |
| **pandas 3.x PyArrow backend** | Faster string/date ops, nullable dtypes | Optional now (`pd.options.mode.string_storage="pyarrow"`) |
| **Free-threaded Python 3.13+** | True parallelism for CPU-bound profiling/parsing | Experimental; wheels available for pandas/numpy |
| **MySQL HeatWave GenAI** (via mysql-connector-python 26.7 `mysql.ai`) | Future: LLM-powered cleaning suggestions, auto-mapping | Requires HeatWave; not general MySQL |
| **Panel 1.9+ / Solara 1.0** | If UI needs grow beyond Streamlit | Evaluate at major milestone |

---

## Sources

- [Streamlit 1.65.0 PyPI](https://pypi.org/project/streamlit/1.65.0/) — Release Oct 2026, Python 3.10–3.14
- [Streamlit Session State Docs](https://docs.streamlit.io/develop/concepts/architecture/session-state) — Official patterns
- [SQLAlchemy 2.0 Engine Config](https://docs.sqlalchemy.org/en/20/core/engines.html) — MySQL dialects, connection pooling
- [mysql-connector-python 26.7.0 PyPI](https://pypi.org/project/mysql-connector-python/26.7.0/) — Release Jul 2026, Python 3.10–3.14
- [PyMySQL 1.2.3 PyPI](https://pypi.org/project/PyMySQL/1.2.3/) — Pure Python, MIT, Sep 2026
- [asyncmy 0.2.16 PyPI](https://pypi.org/project/asyncmy/0.2.16/) — Fastest async driver, Cython, Oct 2026
- [pandas 3.0.6 PyPI](https://pypi.org/project/pandas/3.0.6/) — Release Sep 2026, Python 3.11+
- [fpdf2 2.8.9 PyPI](https://pypi.org/project/fpdf2/2.8.9/) — Pure Python PDF, LGPLv3
- [Panel vs Streamlit Comparison](https://panel.holoviz.org/explanation/comparisons/compare_streamlit.html) — Official migration guide
- [MySQL 8.0 Performance](https://dev.mysql.com/doc/refman/8.0/en/optimization.html) — Staging table optimizations