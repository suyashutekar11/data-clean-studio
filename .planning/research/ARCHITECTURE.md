---
last_researched: 2026-10-09
mode: ecosystem
confidence: HIGH
---

# Architecture Patterns for Data Quality & Cleaning Web Platform with In-Database Staging

**Domain:** Data quality / data cleaning for MySQL databases
**Project:** Data Cleaning Tool (DCT)
**Research Date:** 2026-10-09

---

## Executive Summary

This research examines architecture patterns for an interactive data quality and cleaning web platform that uses **in-database staging** (not in-memory) as its core safety mechanism. The platform must handle production MySQL databases safely, providing zero-production-risk transformations through isolated workspace tables, with full audit trails and executive-grade reporting.

Key architectural influences studied:
- **Streamlit** execution model (caching, fragments, session state) for reactive web UI
- **SQLAlchemy Core** (Inspector, reflection) for dynamic schema introspection
- **dbt** data test patterns for expectation-based quality rules
- **DataHub** metadata ingestion/serving architecture for lineage and catalog patterns
- **dedupe.io** ML-based fuzzy matching for advanced duplicate detection

---

## Recommended Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Presentation & Workflow Layer               │
│                      app.py (Streamlit)                        │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │  Fragments  │ │  Caching    │ │ Session     │              │
│  │  (stages)   │ │  (profiles) │ │  State      │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│              Transformation & Orchestration Layer              │
│                        src/staging.py                          │
│  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐              │
│  │  Workspace  │ │  Pipeline   │ │  Safety     │              │
│  │  Manager    │ │  Executor   │ │  Guards     │              │
│  └─────────────┘ └─────────────┘ └─────────────┘              │
└──────────┬───────────────────────┬───────────────────────┬─────┘
           │                       │                       │
┌──────────▼──────────┐ ┌─────────▼──────────┐ ┌──────────▼──────────┐
│   Rule & Parse      │ │   Profiling &      │ │   Quality Rules     │
│   Engine            │ │   Quality Engine   │ │   Engine (NEW)      │
│  ┌───────────────┐  │ │  ┌─────────────┐   │ │  ┌─────────────┐    │
│  │ date_rules.py │  │ │  │ profiling.py│   │ │  │ expectations│    │
│  │advanced_date_ │  │ │  │ quality.py  │   │ │  │ validation  │    │
│  │standardization│  │ │  └─────────────┘   │ │  │ auto-flag   │    │
│  │ boolean.py    │  │ │                   │ │  └─────────────┘    │
│  │ fuzzy_matcher │  │ │                   │ │                   │
│  └───────────────┘  │ │                   │ │                   │
└──────────┬──────────┘ └─────────┬──────────┘ └──────────┬──────────┘
           │                       │                       │
┌──────────▼───────────────────────▼───────────────────────▼─────┐
│           Database Connectivity & Metadata Layer              │
│        src/connection.py  │  src/metadata.py                  │
│  ┌─────────────────────┐  ┌─────────────────────────────────┐ │
│  │ Connection Manager  │  │ Metadata Inspector (SQLAlchemy) │ │
│  │ (pooling, threads)  │  │ Inspector.get_columns, FKs, etc.│ │
│  └─────────────────────┘  └─────────────────────────────────┘ │
└────────────────────────────┬────────────────────────────────────┘
                             │
┌────────────────────────────▼────────────────────────────────────┐
│                  Target MySQL Database Server                   │
│         Production Tables (RO)  │  Staging Workspaces           │
│         __cleaning_{uuid}       │  Audit/Lineage Tables (NEW)   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| **Presentation Layer** (`app.py`) | User interactions, credential forms, workflow stage transitions, real-time previews, error banners | Orchestration layer via function calls; Session State for persistence |
| **Orchestration Layer** (`staging.py`) | Workspace lifecycle (create/attach/delete), stage execution ordering, safety constraint verification, audit logging | Rule Engine, Profiling, Quality Rules, Reporting, DB Layer |
| **Rule & Parse Engine** (`date_rules.py`, `advanced_date_standardization.py`, `boolean.py`, `fuzzy_matcher.py`) | Deterministic pattern recognition, ML-based fuzzy matching, ambiguity guards | Orchestration layer; returns structured results (ParseResult, MatchResult) |
| **Profiling & Quality Engine** (`profiling.py`, `quality.py`) | Column-level metrics, quality scores, expectation validation, auto-flagging violations | Orchestration layer; reads from workspace tables |
| **Quality Rules Engine** (new) | User-defined expectations (not null, unique, range, regex), validation execution, violation reporting | Orchestration layer; Profiling engine for metrics |
| **Reporting Layer** (`pdf_report.py`, `csv_export.py`) | Executive PDF reports, CSV downloads, transformation logs, quality improvement summaries | Orchestration layer for data; fpdf2 for rendering |
| **DB Connectivity** (`connection.py`) | Engine creation, connection pooling, thread-safe session registry, credential management | All layers; SQLAlchemy Engine/Connection |
| **Metadata Inspector** (`metadata.py`) | Schema/table/column reflection, FK discovery, type mapping, Inspector caching | Orchestration, Profiling, Quality Rules |

---

## Data Flow

### Typical Cleaning Lifecycle (Current)

1. **Connection & Discovery**
   - User inputs credentials in sidebar
   - `MySQLConnectionManager.create_engine()` establishes pooled engine
   - `MySQLMetadataInspector.get_databases()` discovers accessible databases
   - User selects target database and table

2. **Workspace Creation**
   - User initiates cleaning workflow
   - `staging.create_workspace()` creates staging clone (`source_table__cleaning_xxxxxxxx`)
   - Workspace registered in session state

3. **Profiling (Baseline)**
   - `profiling.profile_table()` profiles baseline data quality
   - Metrics cached via `st.cache_data` (TTL: 1 hour)

4. **Iterative Transformation** (per stage)
   - User chooses transformation stage
   - Python engine generates safe SQL DDL/DML
   - Changes previewed with diff metrics (row counts, value samples)
   - User confirms; transformations commit to workspace table
   - Fragment rerun updates only affected stage UI

5. **Validation & Reporting**
   - Workspace re-profiled to verify improvement metrics
   - `pdf_report.generate_executive_profile_pdf()` generates downloadable PDF
   - CSV export available

6. **Promotion or Teardown**
   - User downloads cleaned data as CSV
   - Promotes staging data back to database (new table or replace)
   - Deletes temporary workspaces

### Enhanced Lifecycle (Planned)

7. **Multi-Table Workflow** (REQ-01)
   - User selects multiple related tables (FK-aware)
   - Single workspace session spans multiple `__cleaning_` tables
   - Cross-table validation (referential integrity)

8. **Custom Rules** (REQ-02)
   - User defines regex/replace, computed columns, lookup mappings
   - Rules stored as JSON config, versioned per workspace
   - Rule engine executes user-defined transformations

9. **Scheduled Jobs** (REQ-03)
   - Pipeline config persisted to `cleaning_jobs` table
   - Scheduler (APScheduler/Celery) triggers headless runs
   - Results stored, notifications sent

10. **Quality Rules** (REQ-04)
    - User defines expectations in UI (YAML/JSON)
    - Engine validates on each stage completion
    - Violations auto-flagged, surfaced in UI

11. **Collaboration** (REQ-05)
    - Workspace sharing via `workspace_members` table
    - Review/approve workflow with status transitions
    - Per-user audit trail

12. **Advanced Dedup** (REQ-06)
    - Integrate `dedupe` library for ML-based entity resolution
    - Blocking rules + learned weights for scalable matching
    - Human-in-the-loop training UI

13. **Lineage Tracking** (REQ-07)
    - Column-level lineage from source → transformations → output
    - Store as `column_lineage` table (source_col, transform, target_col)
    - Visualize in UI as DAG

14. **Performance at Scale** (REQ-08)
    - Partitioned workspace tables for >1M rows
    - Batch processing with progress streaming via fragments
    - `st.cache_resource` for connection pools; `st.cache_data` for profiles

---

## Patterns to Follow

### Pattern 1: In-Database Staging (Core Safety Pattern)
**What:** All write operations target isolated workspace tables (`{table}__cleaning_{uuid}`), never production tables.
**When:** Every transformation stage, duplicate removal, promotion.
**Example:**
```python
def create_workspace(engine, source_table: str) -> str:
    workspace_name = f"{source_table}__cleaning_{uuid.uuid4().hex[:8]}"
    with engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE `{workspace_name}` LIKE `{source_table}`"))
        conn.execute(text(f"INSERT INTO `{workspace_name}` SELECT * FROM `{source_table}`"))
    return workspace_name
```

### Pattern 2: SQLAlchemy Inspector for Dynamic Schema
**What:** Use `Inspector` for all metadata operations — never hardcode schema.
**When:** Profiling, FK discovery, type-aware transformations.
**Example:**
```python
from sqlalchemy import inspect
inspector = inspect(engine)
columns = inspector.get_columns(table_name, schema=database)
fks = inspector.get_foreign_keys(table_name, schema=database)
```

### Pattern 3: Streamlit Fragments for Stage Isolation
**What:** Each cleaning stage runs in its own `@st.fragment` to prevent full-app reruns.
**When:** Whitespace, nulls, casing, duplicates, dates, booleans — each independent.
**Example:**
```python
@st.fragment
def whitespace_stage():
    if st.button("Preview Whitespace Changes"):
        preview = staging.preview_whitespace(workspace)
        st.dataframe(preview)
    if st.button("Apply"):
        staging.remove_whitespace_workspace(workspace)
        st.rerun(scope="fragment")
```

### Pattern 4: Dual Caching Strategy
**What:** `st.cache_resource` for connections/engines; `st.cache_data` for profiles/previews.
**When:** Connection manager (resource), profiling results (data with TTL).
**Example:**
```python
@st.cache_resource
def get_engine(creds): return create_engine(...)

@st.cache_data(ttl=3600)
def profile_workspace(workspace): return profiling.profile_table(workspace)
```

### Pattern 5: Expectation-Based Quality Rules (dbt-inspired)
**What:** Define expectations declaratively; engine generates validation SQL.
**When:** REQ-04 quality rules engine.
**Example:**
```yaml
# User-defined rules config
rules:
  - column: email
    expectations:
      - not_null: true
      - regex: "^[^@]+@[^@]+\\.[^@]+$"
  - column: order_id
    expectations:
      - unique: true
      - relationships:
          to: customers
          field: id
```

### Pattern 6: Column-Level Lineage (DataHub-inspired)
**What:** Track each column through transformations: source → transform → target.
**When:** REQ-07 lineage tracking.
**Example:**
```python
# Lineage record per transformation
lineage = {
    "source_table": "orders",
    "source_column": "order_date",
    "transformation": "standardize_date",
    "target_table": "orders__cleaning_abc123",
    "target_column": "order_date",
    "timestamp": datetime.utcnow(),
    "user": session_state.user
}
```

### Pattern 7: ML-Based Fuzzy Matching (dedupe-inspired)
**What:** Active learning for entity resolution — human labels → learned weights → blocking → clustering.
**When:** REQ-06 advanced duplicate detection.
**Example:**
```python
import dedupe
# Training phase
deduper = dedupe.Dedupe(fields)
deduper.prepare_training(data)
deduper.console_label(deduper.uncertain_pairs())
deduper.train()
# Clustering phase
clusters = deduper.partition(data, threshold=0.5)
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: In-Memory Transformation of Large Tables
**What:** Loading entire tables into pandas DataFrames for transformation.
**Why bad:** OOM crashes on tables >100M rows; loses SQL optimization.
**Instead:** Push transformations to MySQL via DDL/DML; only pull samples for preview.

### Anti-Pattern 2: Direct Production Writes
**What:** Any `UPDATE`, `DELETE`, `ALTER` on production tables.
**Why bad:** Violates zero-risk principle; no rollback; no audit trail.
**Instead:** All writes to `__cleaning_` workspaces; promotion is explicit, logged, reversible.

### Anti-Pattern 3: Uncached Metadata Reflection
**What:** Calling `Inspector.get_columns()` on every interaction.
**Why bad:** INFORMATION_SCHEMA queries are slow; blocks UI.
**Instead:** Cache metadata with `st.cache_resource`; invalidate on schema change detection.

### Anti-Pattern 4: Session State Bloat
**What:** Storing full DataFrames, engine objects, or large preview data in `st.session_state`.
**Why bad:** Serialization overhead; memory pressure; cross-session contamination.
**Instead:** Store only identifiers (workspace name, table name, config dicts); use `st.cache_data` for computed data.

### Anti-Pattern 5: Guessing Ambiguous Data
**What:** Auto-converting "01/02/2023" to Feb 1 or Jan 2 without user confirmation.
**Why bad:** Silent data corruption; violates ambiguity→NULL principle.
**Instead:** Flag ambiguous values as NULL with detailed diagnostics; require explicit user resolution.

### Anti-Pattern 6: Synchronous Long-Running Operations
**What:** Blocking Streamlit main thread on large table operations.
**Why bad:** UI freezes; no progress feedback; timeout errors.
**Instead:** Use `@st.fragment(run_every="5s")` for progress polling; background threads with queue.

---

## Scalability Considerations

| Concern | At 100 users | At 10K users | At 1M rows/table | At 100M rows/table |
|---------|--------------|--------------|------------------|-------------------|
| **Connection Pooling** | 10-20 connections | 100-200 (PgBouncer) | Same | Same + read replicas |
| **Workspace Storage** | MBs per workspace | GBs total | Partitioned tables | Partitioned + archival |
| **Profiling Queries** | <1s cached | <1s cached | Sampling (10%) | Sampling (1%) + approx |
| **PDF Generation** | Sync OK | Async queue | Async required | Chunked + streaming |
| **Duplicate Detection** | Exact match OK | Exact + indexed | Blocking + ML | Blocking + Spark/ML |
| **Session State** | In-memory | Redis-backed | Minimal keys only | Minimal keys only |
| **Fragment Parallelism** | 2-4 parallel | 8-16 parallel | Parallel fragments | Parallel + background jobs |

### Scaling Strategies

1. **Connection Layer**: Migrate from `mysql-connector-python` to `mysql-connector-python` with connection pooling; add PgBouncer-style proxy for MySQL (ProxySQL) at 10K users.

2. **Workspace Storage**: Use MySQL partitioning (`PARTITION BY HASH(id)`) for workspace tables >10M rows; implement workspace TTL auto-cleanup.

3. **Profiling**: Switch from full-table scans to `TABLESAMPLE` (MySQL 8.0+) or `WHERE RAND() < 0.01` for statistical profiling at scale.

4. **Async Job Queue**: For REQ-03 scheduled jobs and REQ-08 large-table operations, introduce Celery + Redis queue; Streamlit polls job status via fragment.

5. **Caching Tier**: At scale, move `st.cache_data` to Redis-backed cache (via `streamlit-redis-cache` or custom) for multi-instance deployments.

6. **Fuzzy Matching**: For REQ-06 at >1M rows, integrate `dedupe` with blocking rules; consider Spark-based `spark-dedupe` for distributed clustering.

---

## Sources

| Source | Confidence | Notes |
|--------|------------|-------|
| Streamlit Architecture Docs (caching, fragments, session state) | HIGH | Official docs, current as of 2026 |
| SQLAlchemy 2.0 Reflection/Inspector Docs | HIGH | Official docs, matches current stack |
| dbt Data Tests Architecture | HIGH | Production patterns for expectation-based validation |
| DataHub Architecture (metadata ingestion, serving, lineage) | HIGH | 3rd-gen metadata platform, 10M+ assets at scale |
| dedupe.io Library (ML fuzzy matching, active learning) | HIGH | 4.5k stars, academic foundation (Bilenko PhD) |
| Current DCT Codebase Analysis | HIGH | Direct inspection of existing patterns |

---

## Gaps Requiring Phase-Specific Research

| Phase Topic | Research Needed |
|-------------|-----------------|
| REQ-01 Multi-table FK workflows | MySQL FK cascade behavior in staging; transaction boundaries across workspaces |
| REQ-02 Custom rules engine | Safe SQL generation from user regex; sandboxing; performance of dynamic SQL |
| REQ-03 Scheduled jobs | APScheduler vs Celery for Streamlit; credential persistence for headless runs |
| REQ-04 Quality rules engine | Great Expectations vs custom; expectation serialization; incremental validation |
| REQ-05 Collaboration | Real-time sync (WebSockets vs polling); conflict resolution; RBAC model |
| REQ-06 Fuzzy matching | dedupe integration patterns; training UI in Streamlit; blocking rule selection |
| REQ-07 Column lineage | Graph storage (adjacency list vs property graph); DAG visualization library |
| REQ-08 Performance | MySQL 8.0 partitioning; TABLESAMPLE; ProxySQL; Streamlit Redis cache |

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| Core Architecture (current) | HIGH | Directly mapped from codebase |
| Streamlit Patterns | HIGH | Official docs + current implementation |
| SQLAlchemy Inspector | HIGH | Official docs + current usage |
| Quality Rules (dbt-style) | HIGH | Well-documented pattern, proven at scale |
| DataHub Lineage | MEDIUM | Conceptually sound; implementation details need validation |
| Fuzzy Matching (dedupe) | MEDIUM | Library mature; Streamlit integration needs prototyping |
| Scaling to 100M rows | MEDIUM | Patterns known; MySQL-specific tuning needs testing |
| Multi-user Collaboration | LOW | Requires significant architecture changes (auth, real-time) |