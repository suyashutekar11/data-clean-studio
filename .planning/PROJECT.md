# Data Cleaning Tool — Project Context

**Project Code:** DCT
**Created:** 2026-10-09
**Status:** Active development

---

## What This Is

An **Interactive Data Quality & Cleaning Web Platform** with In-Database Staging and Multi-Stage Transformation Pipeline. Built with Streamlit (Python) and MySQL.

**Core Value:** Zero-production-risk data cleaning — production tables stay strictly read-only; all transformations happen on isolated in-database workspace tables (`{table}__cleaning_{uuid}`), with full audit trail and executive-grade PDF reports.

---

## Context

**Domain:** Data quality / data cleaning for MySQL databases
**Users:** Data analysts, data engineers, DBAs who need to clean messy production data safely
**Problem:** Production data has whitespace issues, nulls, inconsistent casing, duplicates, messy dates, boolean-like text — but modifying production directly is risky
**Solution:** Staged cleaning workflow with preview, validation, and reversible operations

**Existing Codebase:** Brownfield — Streamlit app with 7 cleaning stages already implemented

---

## Requirements

### Validated (Existing Capabilities)

- ✓ **Connection & Discovery** — Connect to MySQL, browse databases/tables, inspect schema — *existing*
- ✓ **Workspace Management** — Create/attach/delete isolated staging tables (`__cleaning_` suffix) — *existing*
- ✓ **Data Profiling** — Column-level metrics: row count, nulls, distinct values, quality scores — *existing*
- ✓ **Whitespace Cleaning** — Trim leading/trailing/internal whitespace, replace blank strings with NULL — *existing*
- ✓ **Null/Missing Handling** — Replace missing values with configurable defaults per column — *existing*
- ✓ **Text Case Normalization** — Standardize casing (UPPER, lower, Title Case) with change preview — *existing*
- ✓ **Duplicate Detection & Removal** — Identify duplicate rows, preview groups, remove by row IDs with keep-first/last options — *existing*
- ✓ **Boolean Normalization** — Detect boolean-like columns (Y/N, Yes/No, True/False, 1/0), standardize to TRUE/FALSE — *existing*
- ✓ **Date Standardization** — Parse messy date formats (textual months, numeric separators), ambiguity guard (days ≤12 → NULL), preview before apply — *existing*
- ✓ **PDF Audit Reporting** — Executive-ready PDF reports: before/after metrics, transformation log, quality improvement summary — *existing*
- ✓ **Export & Promotion** — Download cleaned data as CSV, promote staging back to database — *existing*

### Active (Next Milestone Hypotheses)

- [ ] **REQ-01**: Multi-table cleaning workflow — clean related tables (FK relationships) in a single session
- [ ] **REQ-02**: Custom transformation rules — user-defined regex/replace, computed columns, lookup mappings
- [ ] **REQ-03**: Scheduled/automated cleaning jobs — repeatable pipelines with config persistence
- [ ] **REQ-04**: Data quality rules engine — define expectations (not null, unique, range, regex), auto-flag violations
- [ ] **REQ-05**: Team collaboration — share workspaces, review/approve changes, audit trail per user
- [ ] **REQ-06**: Advanced duplicate detection — fuzzy matching, phonetic matching, ML-based entity resolution
- [ ] **REQ-07**: Data lineage tracking — column-level lineage from source through transformations
- [ ] **REQ-08**: Performance optimization for large tables — partitioning, batch processing, progress streaming

### Out of Scope

- **Direct production writes** — Core safety principle; all changes staged first
- **Non-MySQL databases** — Architecture tied to MySQL `INFORMATION_SCHEMA` and dialect
- **Real-time streaming cleaning** — Batch-oriented by design
- **BI/dashboarding** — Export to tools that specialize in this

---

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| In-database staging (not in-memory) | Handles tables larger than RAM; leverages MySQL DDL/DML performance | ✓ Implemented |
| Streamlit for UI | Rapid iteration, built-in reactive state, no separate frontend build | ✓ Implemented |
| SQLAlchemy Core (not ORM) | Dynamic schema, raw SQL control, metadata inspection via Inspector | ✓ Implemented |
| Ambiguity → NULL (not guess) | Prevents silent data corruption in date/boolean parsing | ✓ Implemented |
| Gradual milestone additions | User wants incremental updates based on evolving requirements | — Pending |

---

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd-transition`):
1. Requirements invalidated? → Move to Out of Scope with reason
2. Requirements validated? → Move to Validated with phase reference
3. New requirements emerged? → Add to Active
4. Decisions to log? → Add to Key Decisions
5. "What This Is" still accurate? → Update if drifted

**After each milestone** (via `/gsd-complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---

*Last updated: 2026-10-09 after initialization*