# Project Research Summary

**Project:** Data Cleaning Tool (DCT) — Interactive Data Quality & Cleaning Web Platform
**Domain:** Data quality / data cleaning for MySQL databases with in-database staging
**Researched:** 2026-10-09
**Confidence:** HIGH

## Executive Summary

The Data Cleaning Tool is a **Streamlit-based interactive web platform** that enables safe, auditable data cleaning directly within MySQL databases. Its core differentiator is **in-database staging** — all transformations execute on isolated workspace tables (`{table}__cleaning_{uuid}`) rather than in memory, ensuring zero production risk even for tables exceeding RAM capacity.

Research confirms the **recommended stack** (Streamlit 1.65, SQLAlchemy Core 2.0, mysql-connector-python 26.7, pandas 3.0, fpdf2 2.8) is production-ready with HIGH confidence. The architecture follows a layered pattern: Streamlit presentation with fragments/caching → orchestration layer managing workspace lifecycle → rule/parse/profiling engines → SQLAlchemy Inspector for dynamic metadata → MySQL workspaces.

**Key risks** center on: (1) SQL injection via identifier interpolation in dynamic DDL (real CVE exists), (2) orphaned workspace tables accumulating indefinitely without TTL/cleanup, (3) INFORMATION_SCHEMA query performance collapse at scale, and (4) monolithic code files (7K+ lines) preventing safe evolution. All have documented prevention strategies.

## Key Findings

### Recommended Stack

The technology stack is well-validated with official sources and version compatibility confirmed for Python 3.14.

**Core technologies:**
- **Streamlit 1.65.0**: Interactive web UI with reactive session state, fragments for partial reruns, multipage workflows — largest ecosystem for data apps, zero frontend build
- **SQLAlchemy Core 2.0.54+**: Dynamic schema reflection via `Inspector`, raw SQL execution for staging DDL/DML — ORM unnecessary for this use case
- **mysql-connector-python 26.7.0**: Official Oracle driver, C-extension performance, synchronous API matching Streamlit execution model
- **pandas 3.0.6**: Tabular manipulation, profiling, CSV export — PyArrow backend optional for performance
- **fpdf2 2.8.9**: Pure Python executive PDF generation, LGPLv3, Unicode TTF fonts, HTML/markdown support
- **python-dotenv 1.0.0**: Environment configuration management
- **openai 1.65.0 + tiktoken + tenacity**: Staged for future GenAI integration (rule suggestion, copilot)

### Expected Features

**Must have (table stakes — already implemented):**
- Connection & schema discovery, data profiling, whitespace cleaning, null handling, text case normalization
- Duplicate detection/removal, boolean normalization, date standardization (with ambiguity guards)
- PDF audit reporting, export/promotion, interactive preview, undo/revert
- Data validation rules engine, referential integrity checks, cross-field validation

**Should have (competitive differentiators — REQ-01 through REQ-08):**
- **In-database staging** (core differentiator) — zero production risk via isolated workspaces
- **Multi-table cleaning with FK relationships** — coordinated transforms preserving referential integrity
- **Custom transformation rules** — user-defined regex/replace, computed columns, lookups
- **Fuzzy matching & entity resolution** — probabilistic linkage with blocking for scale
- **Column-level data lineage** — forward/backward tracing from source through transformations
- **Scheduled/automated cleaning jobs** — config persistence, cron, alerting
- **Team collaboration** — share, review, approve, per-user audit trail
- **Performance optimization** — partitioning, batch processing, progress streaming

**Defer (v2+):**
- AI-powered rule suggestion, data observability, configuration as code/GitOps
- Real-time streaming cleaning, BI/dashboarding, non-MySQL databases

### Architecture Approach

The architecture uses a **5-layer pattern** with clear component boundaries: Presentation (Streamlit app.py with fragments/caching) → Orchestration (staging.py workspace manager, pipeline executor, safety guards) → Engines (Rule/Parse, Profiling/Quality, Quality Rules) → Database Connectivity & Metadata (connection pooling, Inspector) → MySQL (production tables RO, staging workspaces, audit/lineage tables).

**Major components:**
1. **Presentation Layer** (`app.py`) — User interactions, credential forms, workflow stages, real-time previews
2. **Orchestration Layer** (`staging.py`) — Workspace lifecycle, stage execution ordering, safety verification, audit logging
3. **Rule & Parse Engine** (`date_rules.py`, `advanced_date_standardization.py`, `boolean.py`, `fuzzy_matcher.py`) — Deterministic patterns, ML fuzzy matching, ambiguity guards
4. **Profiling & Quality Engine** (`profiling.py`, `quality.py`) — Column metrics, quality scores, expectation validation
5. **Quality Rules Engine** (new) — User-defined expectations, validation execution, violation reporting
6. **Reporting Layer** (`pdf_report.py`, `csv_export.py`) — Executive PDF, CSV downloads, transformation logs
7. **DB Connectivity** (`connection.py`) — Engine creation, pooling, credential management
8. **Metadata Inspector** (`metadata.py`) — Schema reflection, FK discovery, type mapping, Inspector caching

### Critical Pitfalls

1. **SQL Injection via Identifier Interpolation in Dynamic DDL** — Backtick in identifiers closes quoting; with `multipleStatements: true`, stacked statements execute. **Prevention:** Centralize quoting in `_quote_identifier`, double-escape backticks, disable `multiple_statements`, add heuristic validation, audit DDL paths quarterly.

2. **Orphaned Staging Tables Accumulating Indefinitely** — Browser close loses Streamlit session cleanup triggers; no TTL or tracking. **Prevention:** Add `created_at`/`session_id` metadata, implement 24-48hr TTL via MySQL EVENT or cron, admin cleanup UI, registry table tracking.

3. **INFORMATION_SCHEMA Query Performance Collapse at Scale** — Dynamic metadata columns trigger storage engine scans; default 24hr cache expiry causes latency spikes. **Prevention:** Query only view-based tables, avoid dynamic stats columns, set `information_schema_stats_expiry=0`, filter early, cache with 5-15min TTL.

4. **Workspace Confinement Bypass via Identifier Manipulation** — String check on table name *after* quoting can be bypassed. **Prevention:** Validate `__cleaning_` suffix *before* quoting, single `_quote_table` that asserts confinement, resolve workspace ID server-side.

5. **Streamlit Memory Exhaustion with Large DataFrames** — `pd.read_sql()` loads full result sets; session state caches DataFrames. **Prevention:** Server-side sampling (TABLESAMPLE/RAND LIMIT), chunked processing, column pruning, disable session_state caching for large data, progress streaming, hard limits (10M rows/5GB).

## Implications for Roadmap

Based on research dependencies, architecture patterns, and pitfall avoidance, the following phase structure is recommended:

### Phase 1: Foundation Hardening & Safety
**Rationale:** Addresses critical pitfalls before adding features; establishes safe patterns for all future work
**Delivers:** 
- Centralized identifier quoting utility with confinement assertion
- Workspace registry table with TTL cleanup (MySQL EVENT + admin UI)
- INFORMATION_SCHEMA query optimization (filtered, cached, no dynamic stats)
- Codebase modularization: split `app.py` → `src/ui/`, `staging.py` → `src/transformations/`
- Memory safeguards: sampling, chunking, column pruning, hard limits
**Addresses:** FEATURES table stakes (safety, audit); PITFALLS 1, 2, 3, 4, 5, 10
**Avoids:** SQL injection, orphaned tables, metadata query collapse, confinement bypass, OOM

### Phase 2: Data Validation Rules Engine (REQ-04)
**Rationale:** Highest ROI per FEATURES.md; turns reactive cleaning into proactive quality gates; builds on existing profiling
**Delivers:**
- Declarative expectations (YAML/JSON): not_null, unique, range, regex, accepted_values, relationships
- Validation engine generating SQL, auto-flagging violations in UI
- Integration with profiling baseline and post-transformation verification
- Rule priorities and conflict detection at save time
**Addresses:** FEATURES must-have (validation rules, referential integrity, cross-field); ARCHITECTURE Pattern 5 (dbt-inspired)
**Uses:** SQLAlchemy Inspector for schema-aware rules; fpdf2 for rule violation reports

### Phase 3: Multi-Table Cleaning with FK Relationships (REQ-01)
**Rationale:** Unlocks real-world normalized schemas; major competitive gap; depends on workspace safety from Phase 1
**Delivers:**
- FK-aware table selection and workspace creation (one per table)
- Topological sort by FK graph for coordinated transformation ordering
- Cross-table referential integrity validation during cleaning
- Promotion in dependency order with FK checks disabled during bulk load
**Addresses:** FEATURES differentiator (multi-table, referential integrity); ARCHITECTURE enhanced lifecycle step 7
**Avoids:** PITFALLS phase warning — FK constraint violations, circular dependency deadlock

### Phase 4: Custom Transformation Rules (REQ-02)
**Rationale:** Extensibility without code changes; addresses "my messy data doesn't fit presets"; depends on validation engine from Phase 2
**Delivers:**
- User-defined regex/replace, computed columns, lookup mappings, conditional logic
- Rules stored as JSON config, versioned per workspace
- Safe SQL generation from user regex (ReDoS mitigation via `regex` module with timeout)
- Allowlisted regex features; no raw SQL interpolation
**Addresses:** FEATURES differentiator (custom rules); ARCHITECTURE enhanced lifecycle step 8
**Avoids:** PITFALLS phase warning — ReDoS, SQL injection via REGEXP_REPLACE

### Phase 5: Advanced Duplicate Detection & Fuzzy Matching (REQ-06)
**Rationale:** Solves "Bob vs Robert vs B. Smith" problem; builds on normalized data from Phases 2-4
**Delivers:**
- `dedupe` library integration for ML-based entity resolution
- Blocking rules + learned weights for scalable matching
- Human-in-the-loop training UI in Streamlit
- Multi-pass strategy: exact hash → normalized exact → blocking keys → fuzzy within blocks
**Addresses:** FEATURES differentiator (fuzzy matching); ARCHITECTURE Pattern 7, enhanced lifecycle step 12
**Avoids:** PITFALLS 7 (false positives/negatives), phase warning — O(n²) scaling, model drift

### Phase 6: Column-Level Data Lineage (REQ-07)
**Rationale:** Critical for debugging, compliance, impact analysis; builds on transformation logging from Phases 1-5
**Delivers:**
- Column-level lineage records: source_col → transform → target_col per operation
- Storage in `column_lineage` table with DAG visualization in UI
- Aggregate lineage at transformation level (column-level for regulated columns only)
**Addresses:** FEATURES differentiator (lineage); ARCHITECTURE Pattern 6, enhanced lifecycle step 13
**Avoids:** PITFALLS phase warning — lineage graph explosion, storage blowup

### Phase 7: Scheduled Jobs & Team Collaboration (REQ-03, REQ-05)
**Rationale:** Operational maturity; moves from tool to platform; requires validated pipeline from Phases 2-4
**Delivers:**
- Pipeline config persisted to `cleaning_jobs` table with schema hash validation
- APScheduler/Celery headless runs with alerting on failure
- Workspace sharing via `workspace_members`, review/approve workflow, per-user audit
- Optimistic locking on workspace version; linear approval chain
**Addresses:** FEATURES operational maturity (scheduled jobs, collaboration); ARCHITECTURE enhanced lifecycle steps 9, 11
**Avoids:** PITFALLS phase warnings — config drift, silent failures, race conditions, audit trail forks

### Phase 8: Performance Optimization at Scale (REQ-08)
**Rationale:** Enterprise adoption enabler; applies after core features proven; leverages MySQL 8.0 features
**Delivers:**
- Partitioned workspace tables (`PARTITION BY HASH(id)`) for >10M rows
- Batch processing with progress streaming via fragments
- Redis-backed cache for multi-instance deployments
- Workspace TTL auto-cleanup, ProxySQL for connection pooling at scale
**Addresses:** FEATURES operational maturity (performance); ARCHITECTURE scalability strategies, enhanced lifecycle step 14
**Avoids:** PITFALLS phase warning — partition pruning failures, batch boundary transaction splits

### Phase Ordering Rationale

1. **Foundation first** — Critical pitfalls (SQL injection, orphaned tables, memory, monoliths) must be fixed before adding features that depend on safe execution
2. **Validation before multi-table** — Rules engine provides quality gates needed for coordinated multi-table workflows
3. **Multi-table before custom rules** — FK-aware workspaces are prerequisite for cross-table custom transformations
4. **Cleaning before fuzzy matching** — Whitespace, case, null, date standardization must precede entity resolution (FEATURES dependency graph)
5. **Lineage after transformations** — Must capture at each step; retroactive capture is hard (FEATURES cross-cutting)
6. **Operations last** — Scheduled jobs and collaboration require stable, validated pipeline with audit trail

### Research Flags

**Phases likely needing deeper research during planning (`/gsd-plan-phase --research-phase`):**

- **Phase 2 (Validation Rules):** Great Expectations vs custom implementation; expectation serialization format; incremental validation performance
- **Phase 3 (Multi-table):** MySQL FK cascade behavior in staging; transaction boundaries across multiple workspace tables
- **Phase 4 (Custom Rules):** Safe SQL generation from user regex; `re2` vs `regex` vs `re` with timeout benchmarking; sandboxing approach
- **Phase 5 (Fuzzy Matching):** `dedupe` Streamlit integration patterns; training UI design; blocking rule selection UX; FAISS/Annoy/HNSWLib benchmarks at 100K+ rows
- **Phase 6 (Lineage):** Column-level lineage storage schema (adjacency list vs property graph); DAG visualization library selection
- **Phase 8 (Performance):** MySQL 8.0 native partitioning vs manual sharding; TABLESAMPLE availability; ProxySQL configuration; Streamlit Redis cache integration

**Phases with standard patterns (skip research-phase):**

- **Phase 1 (Foundation):** Well-documented patterns — identifier quoting (Ansible), INFORMATION_SCHEMA optimization (MySQL docs), Streamlit modularization, memory management
- **Phase 7 (Scheduled/Collaboration):** APScheduler/Celery patterns established; RBAC and optimistic locking are standard web patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All versions from official PyPI/releases; Python 3.14 compatibility matrix verified; alternatives evaluated with clear rationale |
| Features | HIGH | Based on Wikipedia, Informatica, Great Expectations, Monte Carlo, dbt, Alteryx — industry standards; clear MVP prioritization with dependencies mapped |
| Architecture | HIGH | Directly mapped from current codebase; Streamlit/SQLAlchemy patterns from official docs; dbt/DataHub/dedupe patterns from production systems |
| Pitfalls | HIGH | Real CVE (Budibase), official MySQL 8.0 optimization guide, Streamlit community FAQ, fpdf2 docs, measured file line counts |

**Overall confidence:** HIGH

### Gaps to Address

- **REQ-02 Custom Rules ReDoS mitigation:** Need benchmark comparison of `re2` (no backtracking) vs `regex` (timeout support) vs stdlib `re` with timeout — impacts Phase 4 planning
- **REQ-05 Collaboration real-time sync:** WebSockets vs polling tradeoff; conflict resolution strategy; RBAC model details — needs Phase 7 research
- **REQ-06 Fuzzy matching scale:** Approximate nearest neighbor library selection (FAISS/Annoy/HNSWLib) requires benchmarking on realistic data volumes
- **REQ-07 Lineage storage:** Graph vs relational schema design for column-level lineage — impacts Phase 6 data model
- **REQ-08 Partitioning strategy:** MySQL 8.0 native partitioning vs manual sharding for staging tables — needs MySQL-specific testing
- **AI Integration safety:** Prompt injection prevention, cost control, token estimation patterns for future GenAI features

## Sources

### Primary (HIGH confidence)
- **Streamlit 1.65.0 PyPI / Official Docs** — Architecture, caching, fragments, session state, scaling guidance
- **SQLAlchemy 2.0 Official Docs** — Engine config, Inspector reflection, Core vs ORM, MySQL dialects
- **mysql-connector-python 26.7.0 PyPI / MySQL 8.0 Reference Manual** — Driver features, INFORMATION_SCHEMA optimization (10.2.3), connection parameters
- **pandas 3.0.6 PyPI** — Version compatibility, PyArrow backend, performance extras
- **fpdf2 2.8.9 PyPI / Official Docs** — Tables API, performance guidelines, Unicode support
- **Budibase GHSA-ppj8-hmx2-m546 (CVE-2026-100683)** — Real-world identifier injection in dynamic DDL
- **Ansible community.mysql collection** — Production-grade identifier quoting implementation
- **dbt Data Tests Architecture** — Expectation-based validation patterns
- **DataHub Architecture** — Metadata ingestion, lineage serving at scale
- **dedupe.io Library** — ML-based fuzzy matching, active learning patterns
- **Current DCT Codebase Analysis** — Direct inspection of existing patterns, file sizes, implementation gaps

### Secondary (MEDIUM confidence)
- **Wikipedia: Data Quality / Data Cleansing / Record Linkage / Data Lineage** — Dimension definitions, process models, academic foundations
- **Informatica Data Quality & Observability** — Automated profiling, AI agents, prebuilt rules, observability dimensions
- **Great Expectations (GX)** — Expectations gallery, ExpectAI, root cause analysis, governance
- **Monte Carlo** — Data observability, anomaly detection, field-level lineage, ROI metrics
- **Alteryx / Trifacta** — Profile → Prepare → Pipeline, in-database pushdown, governed workflows
- **Retail Taxonomy / Data Engineer Academy / OvalEdge** — Industry practitioner perspectives on pitfalls and best practices
- **Streamlit Community** — Scaling discussions, large data object handling, memory management

### Tertiary (LOW confidence - needs validation)
- **MySQL HeatWave GenAI (mysql.ai)** — Future LLM-powered cleaning; requires HeatWave, not general MySQL
- **Panel 1.9+ / Solara 1.0** — Alternative UI frameworks; evaluate only at major milestone
- **Free-threaded Python 3.13+** — True parallelism for CPU-bound ops; experimental, wheels available

---

*Research completed: 2026-10-09*
*Ready for roadmap: yes*