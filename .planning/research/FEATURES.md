# Feature Landscape

**Domain:** Data Quality & Cleaning Web Platform with In-Database Staging
**Researched:** 2026-10-09

## Table Stakes

Features users expect. Missing = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Connection & Schema Discovery** | Must connect to DB, browse databases/tables, inspect columns, types, PKs, FKs | Low | Already implemented |
| **Data Profiling** | Column-level metrics: row count, nulls, distinct values, quality scores, value distributions | Low | Already implemented; core to any DQ tool |
| **Whitespace Cleaning** | Trim leading/trailing/internal whitespace; replace blank strings with NULL | Low | Already implemented; most basic cleaning |
| **Null/Missing Handling** | Detect nulls, replace with configurable defaults per column, interpolation options | Low | Already implemented; table stakes for any cleaning |
| **Text Case Normalization** | Standardize casing (UPPER, lower, Title Case) with change preview | Low | Already implemented; expected for text data |
| **Duplicate Detection & Removal** | Identify duplicate rows, preview groups, remove by row IDs with keep-first/last options | Medium | Already implemented; critical for data integrity |
| **Boolean Normalization** | Detect boolean-like columns (Y/N, Yes/No, True/False, 1/0), standardize to TRUE/FALSE | Medium | Already implemented; common messy data pattern |
| **Date Standardization** | Parse messy date formats (textual months, numeric separators), ambiguity guard (days ≤12 → NULL), preview before apply | High | Already implemented; complex but expected |
| **PDF Audit Reporting** | Executive-ready PDF: before/after metrics, transformation log, quality improvement summary | Medium | Already implemented; compliance/audit requirement |
| **Export & Promotion** | Download cleaned data as CSV, promote staging back to database | Low | Already implemented; must close the loop |
| **Data Validation Rules Engine** | Define expectations (not null, unique, range, regex, accepted values, referential integrity), auto-flag violations | High | REQ-04; standard in dbt, Great Expectations, Informatica |
| **Referential Integrity Checks** | Validate FK relationships, flag orphaned records | Medium | Part of rules engine; critical for relational data |
| **Cross-Field Validation** | Multi-column constraints (e.g., discharge_date ≥ admission_date) | Medium | Business rule validation; expected in enterprise tools |
| **Interactive Preview** | See before/after diff with row counts, sample rows before committing | Low | Already implemented; safety requirement |
| **Undo/Revert** | Roll back last transformation or full workspace | Medium | Safety net; expected for interactive tools |

## Differentiators

Features that set product apart. Not expected, but highly valued.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **In-Database Staging (Zero Production Risk)** | Production tables stay strictly read-only; all transforms on isolated `{table}__cleaning_{uuid}` workspaces | High | **DCT Core Differentiator** — most tools stage in-memory or require separate staging DB |
| **Multi-Table Cleaning with FK Relationships** | Clean related tables (parent/child) in single session; coordinated transformations preserving referential integrity | High | REQ-01; major pain point for normalized schemas |
| **Custom Transformation Rules** | User-defined regex/replace, computed columns, lookup mappings, conditional logic | High | REQ-02; enables domain-specific cleaning without code |
| **Fuzzy Matching & Entity Resolution** | Probabilistic record linkage (Jaro-Winkler, Levenshtein, phonetic), blocking for scale, ML-assisted deduplication | High | REQ-06; goes beyond exact duplicate detection |
| **Data Lineage Tracking (Column-Level)** | Track column-level lineage from source through each transformation; forward/backward tracing | High | REQ-07; critical for debugging, compliance, impact analysis |
| **Scheduled/Automated Cleaning Jobs** | Repeatable pipelines with config persistence, parameterization, cron scheduling, alerting | High | REQ-03; moves from ad-hoc to operational |
| **Team Collaboration** | Share workspaces, review/approve changes, per-user audit trail, comments on transformations | Medium | REQ-05; enables governance workflows |
| **AI-Powered Rule Suggestion** | Auto-generate data quality rules from profiling (ExpectAI style); suggest transformations | High | Emerging differentiator; reduces manual rule authoring |
| **Data Observability / Continuous Monitoring** | Freshness, volume, distribution, schema change detection; anomaly alerts | High | Monte Carlo / Informatica territory; proactive vs reactive |
| **Root Cause Analysis for Failures** | Drill from failed expectation to offending rows, upstream lineage, suggested fixes | High | Great Expectations feature; reduces MTTR |
| **Performance Optimization for Large Tables** | Partitioning, batch processing, progress streaming, push-down to MySQL | High | REQ-08; enables enterprise-scale adoption |
| **Configuration as Code / GitOps** | Version-controlled cleaning pipelines, CI/CD integration, promotion across environments | Medium | Modern DevOps expectation; enables reproducibility |

## Anti-Features

Features to explicitly NOT build.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Direct Production Writes** | Core safety principle; violates zero-risk staging | Always use in-database workspace tables (`__cleaning_` suffix) |
| **In-Memory Only Processing** | Cannot handle tables larger than RAM; crashes on large datasets | Leverage MySQL DDL/DML for set operations; hybrid in-db/in-memory |
| **Guessing Ambiguous Data** | Silent data corruption (e.g., 01/02/2023 → Jan 2 or Feb 1?) | Ambiguity → NULL with detailed diagnostics; never guess |
| **Black-Box Transformations** | No audit trail, cannot debug, compliance failure | Every transformation logged with before/after metrics, reversible |
| **Proprietary Export Formats** | Vendor lock-in, interoperability issues | Standard CSV, SQL, Parquet; promote back to MySQL |
| **Separate Frontend Build** | Increases complexity, slows iteration | Streamlit reactive UI — single Python codebase |
| **Real-Time Streaming Cleaning** | Out of scope; batch-oriented by design | Export to streaming tools (Kafka, Flink) if needed |
| **BI/Dashboarding** | Not core competency; specialized tools do it better | Export clean data to Tableau, Power BI, Looker, Metabase |
| **Non-MySQL Databases** | Architecture tied to MySQL `INFORMATION_SCHEMA` and dialect | Stay focused; document MySQL-specific assumptions clearly |
| **Auto-Apply Without Preview** | Dangerous; users need to verify before commit | Mandatory preview step with diff metrics for every transformation |

## Feature Dependencies

```
Connection & Discovery
    ↓
Workspace Creation (requires target table)
    ↓
Data Profiling (baseline) → detects quality issues
    ↓
┌─────────────────────────────────────────────────────────────┐
│ Transformation Stages (can run in any order, but logical flow):│
├─────────────────────────────────────────────────────────────┤
│ 1. Whitespace Cleaning (simplest, safe first step)          │
│ 2. Null/Missing Handling (clean blanks before other rules)  │
│ 3. Text Case Normalization (standardize before matching)    │
│ 4. Boolean Normalization (detect after whitespace/nulls)    │
│ 5. Date Standardization (parse after basic cleaning)        │
│ 6. Custom Rules / Regex Replace (domain-specific)           │
│ 7. Duplicate Detection → Removal (last; needs clean data)   │
└─────────────────────────────────────────────────────────────┘
    ↓
Post-Transformation Profiling (verify improvement)
    ↓
PDF Audit Report Generation
    ↓
Export / Promotion Decision
```

**Cross-cutting dependencies:**
- **Data Validation Rules Engine** → Can run at any stage; best after profiling, before promotion
- **Multi-Table Cleaning** → Requires FK Discovery → Workspace per table → Coordinated transaction
- **Fuzzy Matching** → Requires standardized/cleaned data first (whitespace, case, nulls)
- **Data Lineage** → Must capture at each transformation step; retroactive capture is hard
- **Scheduled Jobs** → Requires validated pipeline + config persistence + parameterization
- **Team Collaboration** → Requires audit trail + workspace sharing + role-based access

## MVP Recommendation

### Prioritize (Next Milestone)

1. **Data Validation Rules Engine (REQ-04)** — Highest ROI: turns reactive cleaning into proactive quality gates; integrates with existing profiling; enables "define once, run many"
2. **Multi-Table Cleaning with FK Relationships (REQ-01)** — Unlocks real-world normalized schemas; major competitive gap vs single-table tools
3. **Custom Transformation Rules (REQ-02)** — Addresses "my messy data doesn't fit your presets"; extensibility without code changes

### Strong Differentiator (Phase 2)

4. **Fuzzy Matching & Entity Resolution (REQ-06)** — Solves the "Bob vs Robert vs B. Smith" problem; probabilistic matching with blocking for scale
5. **Data Lineage Tracking (REQ-07)** — Column-level lineage enables debugging, compliance, impact analysis; builds on existing transformation logging

### Operational Maturity (Phase 3)

6. **Scheduled/Automated Cleaning Jobs (REQ-03)** — Config persistence, parameterization, cron, alerting; moves from tool to platform
7. **Team Collaboration (REQ-05)** — Share, review, approve, audit per user; governance workflow
8. **Performance Optimization (REQ-08)** — Partitioning, batch processing, streaming progress; enterprise scale

### Future / Explore

9. **AI-Powered Rule Suggestion** — Auto-generate expectations from profiling; reduce manual effort
10. **Data Observability** — Continuous monitoring beyond batch cleaning; anomaly detection
11. **Configuration as Code / GitOps** — Version-controlled pipelines, CI/CD, environment promotion

### Defer

- **Real-time streaming cleaning** — Out of scope (batch-oriented)
- **BI/Dashboarding** — Export to specialized tools
- **Non-MySQL databases** — Architecture decision; revisit only if strong demand
- **Privacy-preserving record linkage** — Niche; add only if regulated-industry demand

## Sources

- **Wikipedia: Data Quality** — Dimensions (accuracy, completeness, consistency, validity, uniqueness, timeliness); quality assurance process
- **Wikipedia: Data Cleansing** — Process: auditing → workflow spec → execution → post-processing; quality screens (column, structure, business rule); criticism (cost, time, security)
- **Wikipedia: Record Linkage / Entity Resolution** — Deterministic vs probabilistic (Fellegi-Sunter); blocking; ML methods; human-machine hybrid; privacy-preserving
- **Wikipedia: Data Lineage** — Forward/backward tracing; eager vs lazy capture; association graphs; topological sorting; replay/debugging
- **Informatica Data Quality & Observability** — Automated profiling, AI agents for cleansing, prebuilt rules/accelerators, data observability (freshness, volume, distribution, schema, lineage), consumption pricing
- **Great Expectations (GX)** — Expectations gallery (not_null, unique, accepted_values, relationships, range, regex, etc.); ExpectAI for agent; root cause analysis; expectation history/governance; email alerts; data asset lineage
- **Monte Carlo** — Data + AI observability; agent trust platform; automated anomaly detection; field-level lineage; ROI metrics
- **dbt Data Tests** — Generic tests: unique, not_null, accepted_values, relationships; singular tests; store_failures for debugging; batch tests; severity thresholds; composite uniqueness
- **Alteryx / Trifacta** — Profile → Prepare → Pipeline; visual transformations; cloud-native; in-database pushdown (Snowflake, Databricks); governed workflows; AI-ready data prep
- **Pandas API** — drop_duplicates (subset, keep first/last/False), fillna, dropna, replace, interpolate, astype, convert_dtypes — reference for expected cleaning primitives