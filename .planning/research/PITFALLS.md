# Domain Pitfalls: Data Quality & Cleaning Web Platform with In-Database Staging

**Domain:** Data quality / data cleaning for MySQL databases
**Researched:** 2026-10-09
**Project:** Data Cleaning Tool (DCT) — Interactive Data Quality & Cleaning Web Platform with In-Database Staging

---

## Critical Pitfalls

Mistakes that cause rewrites, data corruption, security breaches, or major operational incidents.

### Pitfall 1: SQL Injection via Identifier Interpolation in Dynamic DDL

**What goes wrong:** User-supplied table/column names interpolated directly into backtick-quoted identifiers without proper escaping allow second-order SQL injection. A backtick (`\``) in a column name closes the identifier; with `multipleStatements: true` on the MySQL connection, a stacked statement executes as the datasource user.

**Why it happens:**
- Dynamic DDL (CREATE, ALTER, DROP, RENAME) cannot use prepared statement parameter binding for identifiers
- Developers assume backtick wrapping is sufficient: `` `table` ``
- Internal backticks in identifiers must be doubled (`` `` ``) to escape
- Quote helper functions exist but are not consistently imported/applied to all dynamic DDL paths

**Real-world example:** Budibase CVE-2026-100683 (GHSA-ppj8-hmx2-m546) — column rename DDL interpolated raw identifiers without quoting helpers, allowing `CREATE USER`/`GRANT`/`DROP` via stacked statements on MySQL with `multipleStatements: true`.

**Consequences:**
- Arbitrary SQL execution as the datasource database user
- Read/write/drop of any data the user can reach, bypassing application permission model
- Full database compromise if datasource user has elevated privileges

**Prevention:**
- Centralize identifier quoting in a single utility (`_quote_identifier`, `_quote_table`) — already present in DCT `src/staging.py`
- Apply quoting to **every** dynamic identifier: database, table, column, index, constraint
- Escape internal backticks by doubling: `identifier.replace('`', '``')`
- Enforce strict identifier allowlists (regex `^[0-9A-Za-z_$]+$`) where possible
- **Disable `multiple_statements` on the MySQL connection** unless explicitly required — eliminates stacked-statement injection
- Add heuristic input validation (`is_input_dangerous` patterns: unclosed quotes + `--`, `UNION SELECT`, `;DROP|TRUNCATE|DELETE`)
- Audit all DDL generation paths quarterly for missed quoting

**Detection:**
- Static analysis: grep for string interpolation in SQL DDL (`f"ALTER TABLE {table}"`, `.format()`)
- Runtime: enable MySQL general log; watch for unexpected stacked statements
- Pen test: attempt column rename with backtick-laden names

---

### Pitfall 2: Orphaned Staging Tables Accumulating Indefinitely

**What goes wrong:** Temporary workspace tables (`{table}__cleaning_{uuid}`) persist in the user's database when browser sessions close without explicit "Delete Workspace" clicks. No TTL, no cleanup job, no ownership tracking.

**Why it happens:**
- Streamlit session state is in-memory; closing browser tab loses cleanup triggers
- Workspace tables created directly in user schema with no metadata table tracking creation time, owner session, or TTL
- No background sweeper or admin UI for orphan detection

**Consequences:**
- Schema clutter: hundreds of `__cleaning_` tables accumulate over months
- Storage bloat: each workspace is a full table copy (data + indexes)
- Confusion: `SHOW TABLES` polluted; `INFORMATION_SCHEMA` queries slow
- Security: stale workspaces may contain sensitive production data snapshots

**Prevention:**
- Add `created_at` timestamp and `session_id` to table comments or a metadata table
- Implement TTL: auto-drop workspaces older than 24–48 hours via scheduled event or cron
- Provide "Cleanup Orphaned Workspaces" admin tool in sidebar (lists tables matching `__cleaning_` pattern with age > threshold)
- On workspace creation, register in a lightweight tracking table (`dct_workspace_registry`) with `workspace_table`, `source_table`, `created_at`, `session_id`, `status`
- Use MySQL `CREATE EVENT` for automatic cleanup if event scheduler enabled

**Detection:**
- Query: `SELECT TABLE_NAME, CREATE_TIME FROM INFORMATION_SCHEMA.TABLES WHERE TABLE_NAME LIKE '%__cleaning_%' AND CREATE_TIME < NOW() - INTERVAL 2 DAY`
- Monitor table count growth rate per database

---

### Pitfall 3: INFORMATION_SCHEMA Query Performance Collapse at Scale

**What goes wrong:** Frequent `INFORMATION_SCHEMA.COLUMNS`, `TABLES`, `STATISTICS` queries for dynamic schema inspection become slow or block on databases with thousands of tables/partitions. Metadata queries that should be milliseconds take seconds.

**Why it happens:**
- MySQL 8.0 serves some `INFORMATION_SCHEMA` tables as views on data dictionary tables (fast), but statistics columns (`TABLES.TABLE_ROWS`, `STATISTICS.CARDINALITY`, `TABLES.DATA_LENGTH`, etc.) require **dynamic metadata** retrieval from storage engine
- Querying dynamic metadata columns alongside static metadata adds overhead
- Default `information_schema_stats_expiry = 86400` (24h) means cached stats reused, but first access after expiry triggers full storage engine scan
- Dynamic schema inspection tools often query `COLUMNS` + `TABLES` + `STATISTICS` joins without filtering early

**Consequences:**
- UI freezes during database/table discovery
- Connection pool exhaustion from long-running metadata queries
- Blocked DDL on monitored tables (metadata locks)

**Prevention (per MySQL 8.0 Reference Manual 10.2.3):**
- Query **only** `INFORMATION_SCHEMA` tables implemented as views on data dictionary (COLUMNS, TABLES, KEY_COLUMN_USAGE, REFERENTIAL_CONSTRAINTS, etc. — see full list in MySQL docs)
- **Avoid** selecting dynamic statistics columns (`TABLE_ROWS`, `AVG_ROW_LENGTH`, `DATA_LENGTH`, `INDEX_LENGTH`, `CARDINALITY`) unless absolutely necessary
- Set session `information_schema_stats_expiry=0` to force fresh stats only when explicitly needed, not on every discovery call
- Filter early: `WHERE TABLE_SCHEMA = ? AND TABLE_NAME = ?` before joins
- Cache schema inspection results in application layer with TTL (5–15 min)
- Use `EXPLAIN` on metadata queries; verify index usage on data dictionary tables

**Detection:**
- Slow query log: `INFORMATION_SCHEMA` queries > 1s
- `SHOW PROCESSLIST` showing "Waiting for table metadata lock" on metadata queries
- UI latency spikes during database/table selection

---

### Pitfall 4: Workspace Confinement Bypass via Identifier Manipulation

**What goes wrong:** Write operations (UPDATE, DELETE, ALTER) intended for workspace tables execute on production tables because confinement check (`__cleaning_` suffix) is bypassed via identifier manipulation.

**Why it happens:**
- Confinement check uses string matching on table name *after* quoting
- If identifier quoting is inconsistent, a crafted name like `prod_table` + `__cleaning_` + `` ` `` + `; UPDATE prod_table SET ... --` could pass string check but execute on production
- Dynamic SQL builds table name from user-selected values without re-validating confinement *after* quoting

**Consequences:**
- **Direct production data modification** — violates core safety principle
- Data corruption, loss, or unauthorized changes
- Audit trail shows workspace operation but production changed

**Prevention:**
- Validate confinement **before** any quoting: `if not table_name.endswith('__cleaning_'): raise`
- Use a single `_quote_table` function that **asserts** confinement internally
- Never accept raw table names from UI for write operations; resolve workspace ID → canonical workspace table name server-side
- Unit test: attempt confinement bypass with malicious identifiers; assert rejection

**Detection:**
- Audit logs: any write operation on non-`__cleaning_` table from cleaning workflow
- Integration test: fuzz table name parameter with injection payloads

---

### Pitfall 5: Streamlit Memory Exhaustion with Large DataFrames

**What goes wrong:** Profiling, duplicate detection, and preview operations load large result sets into Pandas DataFrames in Streamlit worker memory. Tables with 100K+ rows and wide schemas cause OOM kills or 30+ second response times.

**Why it happens:**
- `pd.read_sql()` loads entire result set into memory
- Duplicate detection loads candidate groups into DataFrame for UI rendering
- `st.session_state` caches DataFrames across reruns; no automatic eviction
- Streamlit Cloud / container memory limits (1–2 GB) easily exceeded
- No chunking, sampling, or server-side pagination for large tables

**Consequences:**
- App crashes (OOM kill) during profiling or duplicate review
- Silent data truncation if `LIMIT` applied without user awareness
- Degraded UX: 30–60s spinner, browser tab unresponsive

**Prevention (per Streamlit community best practices):**
- **Server-side sampling**: `SELECT * FROM table TABLESAMPLE SYSTEM (10)` or `ORDER BY RAND() LIMIT 10000` for profiling previews
- **Chunked processing**: Use `LIMIT/OFFSET` or `WHERE pk > last_seen` for duplicate scanning; process in batches
- **Column pruning**: `SELECT col1, col2, col3` instead of `SELECT *` — only fetch columns needed for current stage
- **Disable DataFrame caching in session_state** for large tables; recompute or use `st.cache_data` with `ttl` and `max_entries`
- **Progress streaming**: Use `st.status` / `st.progress` with generator-based chunk processing
- **Hard limits**: Reject workspace creation for tables > 10M rows or > 5 GB without explicit confirmation + partitioning plan
- **Memory monitoring**: Log `psutil.Process().memory_info().rss` at stage boundaries; alert if > 1 GB

**Detection:**
- Container OOM kills (exit code 137)
- Streamlit "resource limits" warnings in Community Cloud
- Browser DevTools: `performance.memory.usedJSHeapSize` spikes

---

## Moderate Pitfalls

### Pitfall 6: Silent Data Corruption from Ambiguous Date/Boolean Parsing

**What goes wrong:** Date standardization and boolean normalization convert ambiguous values incorrectly, silently corrupting data instead of flagging for review.

**Why it happens:**
- Date formats like `01/02/2026` (Jan 2 vs Feb 1) — DCT correctly returns NULL for day ≤ 12, but this loses data
- Boolean-like columns: `Y/N`, `Yes/No`, `True/False`, `1/0`, `T/F` — edge cases (`'YES'`, `'true'`, `'Y '` with trailing space) misclassified
- No "review before apply" for low-confidence conversions

**Consequences:**
- Data loss: valid dates → NULL; valid booleans → wrong canonical value
- Downstream analytics broken without obvious error
- Trust erosion: users stop using automated cleaning

**Prevention:**
- **Ambiguity → NULL is correct** (DCT already does this) — but **preview must show count of NULLed rows prominently**
- Add "ambiguity score" per column: `% rows converted to NULL` / `% rows with conflicting patterns`
- Require explicit user confirmation for any transformation with > 5% ambiguity
- Log every ambiguous conversion with original value, row ID, and reason for NULL
- Provide "download ambiguous rows CSV" for manual review

**Detection:**
- Profiling re-run after transformation: null % spike in cleaned columns
- User reports: "my dates disappeared"

---

### Pitfall 7: Duplicate Detection False Positives/Negatives at Scale

**What goes wrong:** Exact-match duplicate detection misses near-duplicates (typos, whitespace, case differences); fuzzy matching produces false positives merging distinct entities.

**Why it happens:**
- Exact `ROW_HASH` (MD5 of all columns) misses: `John Smith` vs `JOHN SMITH`, `123 Main St` vs `123 Main Street`
- Fuzzy matching (Levenshtein, Jaro-Winkler) on large tables is O(n²) — impractical without blocking
- No domain-aware blocking keys (e.g., match on normalized name + zip, not full row)

**Consequences:**
- False negatives: duplicates remain, inflating counts
- False positives: distinct customers merged, orders attributed incorrectly
- Performance: full pairwise comparison on 100K rows = 5B comparisons

**Prevention:**
- **Multi-pass strategy**: Exact hash → Normalized exact (trim, lower, standardize) → Blocking keys (phonetic name + zip) → Fuzzy within blocks
- Use `mysql-connector-python` + `LIMIT` + application-side blocking; don't pull full table to Python
- Expose blocking key configuration in UI (user defines "what makes a duplicate")
- Preview shows **groups** with row IDs; user confirms keep-first/last per group
- Log all duplicate decisions (kept/removed row IDs) for audit

**Detection:**
- Post-dedupe profiling: distinct count vs row count ratio
- Manual spot-check of removed/kept rows

---

### Pitfall 8: PDF Report Generation Failures on Large Datasets

**What goes wrong:** `fpdf2` table rendering times out, produces malformed PDFs, or exceeds memory when audit reports include large before/after comparison tables.

**Why it happens:**
- fpdf2 Tables (v2.7+) support auto-page-break and heading repeat, but **large tables with many columns/rows** stress layout engine
- `cell_fill_mode="ROWS"` with many rows slows rendering
- Column width auto-calculation on wide tables is expensive
- Font embedding (if using TTF/Unicode) increases memory
- No streaming/chunked PDF generation — entire document built in memory

**Consequences:**
- Report generation fails silently or with cryptic error
- PDF missing pages, truncated tables, overlapping cells
- User cannot download audit trail for compliance

**Prevention (per fpdf2 Tables docs):**
- **Limit report tables**: Summary metrics only; detailed row-level diffs → separate CSV download
- **Disable `cell_fill_mode`** for tables > 100 rows
- **Fix column widths** (`col_widths` as fractions) instead of auto-calc
- **Use `repeat_headings=1`** (default) for multi-page tables
- **Avoid `INTERNAL`/`MINIMAL` borders** if table extraction needed (per fpdf2 parsability notes)
- **Stream to disk**: Write PDF to temp file, not memory buffer
- **Timeout guard**: `signal.alarm(30)` or thread timeout on PDF generation

**Detection:**
- PDF generation time > 10s
- Output file size > 10 MB for standard reports
- User reports: "PDF won't open" or "missing pages"

---

### Pitfall 9: MySQL Dialect Lock-in Prevents Future Portability

**What goes wrong:** Heavy reliance on MySQL-specific constructs (backticks, `STR_TO_DATE`, `INFORMATION_SCHEMA` views, MySQL error codes 1045/2002) makes migrating to PostgreSQL, SQL Server, or Snowflake require near-rewrite.

**Why it happens:**
- `src/metadata.py` and `src/staging.py` embed MySQL dialect directly
- `_quote_identifier` hardcodes backticks
- Date parsing uses `STR_TO_DATE` with MySQL format specifiers
- Error handling checks `err.errno == 1045` (access denied), `2002` (connection refused)

**Consequences:**
- Vendor lock-in; cannot serve customers on other databases
- Technical debt compounds as features grow
- Testing only on MySQL misses dialect-specific bugs

**Prevention:**
- Abstract SQL generation: `Dialect` class with `quote_identifier()`, `date_parse()`, `create_workspace_table()`, `drop_table()`
- Use SQLAlchemy Core `text()` with `bindparam()` for values; `DDLElements` for schema ops where possible
- Isolate MySQL-specific error codes in `connection.py`; expose generic `ConnectionError`, `AuthError`, `PermissionError`
- Add integration test matrix: MySQL 8.0, MariaDB 10.6+ (baseline compatibility)

**Detection:**
- Grep for `STR_TO_DATE`, backtick literals, MySQL error codes outside `connection.py`
- Attempt to run test suite against MariaDB; note failures

---

### Pitfall 10: Monolithic Code Files Prevent Safe Evolution

**What goes wrong:** `app.py` (7,319 lines) and `src/staging.py` (5,365 lines) become unmaintainable — high regression risk, impossible to test in isolation, cognitive overload.

**Why it happens:**
- Incremental feature additions without architectural refactoring
- Streamlit encourages single-file apps; no enforced modularity
- Staging logic accumulates as stages added (now 9 stages in one file)

**Consequences:**
- Bug fixes in Stage 3 break Stage 7
- New developers (human or AI) cannot safely modify
- Unit testing requires full app context; slow, flaky
- Code review ineffective — too much context to hold

**Prevention:**
- Decompose `app.py` → `src/ui/` (sidebar, stages/, components/)
- Split `src/staging.py` → `src/transformations/` (whitespace.py, duplicates.py, dates.py, booleans.py, casing.py, nulls.py) + `src/workspace.py`
- Enforce max 500 lines/file via linting rule
- Add `pytest` fixtures for each transformation module with isolated DB transactions

**Detection:**
- File line count > 500 (current: 7,319 and 5,365)
- Cyclomatic complexity > 20 per function
- Test coverage < 60% on staging modules

---

## Minor Pitfalls

### Pitfall 11: Staged AI Dependencies Create Deployment Ambiguity

**What goes wrong:** `openai`, `tiktoken`, `tenacity` in `requirements.txt` but no AI features wired — deployments install unused heavy deps; users expect AI that doesn't exist.

**Prevention:**
- Move AI deps to `requirements-ai.txt` / optional extra: `pip install dct[ai]`
- Document current status: "AI copilot — planned for Milestone 2"
- Remove from base `requirements.txt` until feature lands

### Pitfall 12: Credential Leakage via Streamlit Session State Serialization

**What goes wrong:** Credentials in `st.session_state` serialized to browser (query params, localStorage) or logged via debug tools.

**Prevention:**
- Never put raw passwords in `st.session_state`; use connection object references only
- Clear credentials on workspace disconnect
- Audit `st.session_state` keys on each render; fail if `password` key exists

### Pitfall 13: Timezone-Aware Datetime Corruption

**What goes wrong:** `pd.to_datetime()` and MySQL `DATETIME`/`TIMESTAMP` mismatch on timezone-aware data — shifts of hours silently applied.

**Prevention:**
- Enforce `TIMESTAMP` columns as UTC in MySQL; convert in app layer
- Use `pd.to_datetime(..., utc=True)` consistently
- Document timezone assumption in PDF reports

### Pitfall 14: Concurrent Workspace Corruption

**What goes wrong:** Two browser tabs for same user create separate workspaces on same source table; operations interleave, last-write-wins loses changes.

**Prevention:**
- Enforce single active workspace per (user, source_table) via registry table
- Lock workspace on attach; release on detach or TTL expiry
- UI: warn "Active workspace exists — attach or create new?"

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|----------------|------------|
| **REQ-01: Multi-table cleaning (FK relationships)** | FK constraint violations when promoting cleaned child before parent; circular FK dependency deadlock | Topological sort by FK graph; promote in dependency order; disable FK checks during bulk promote |
| **REQ-02: Custom transformation rules (regex/replace)** | ReDoS via catastrophic backtracking on user regex; SQL injection via `REGEXP_REPLACE` interpolation | Regex timeout (`re2`/`regex` module with timeout); allowlist regex features; no raw SQL interpolation |
| **REQ-03: Scheduled/automated cleaning jobs** | Config drift: scheduled job runs stale rules on evolved schema; silent failures without alerting | Config versioning + schema hash validation; mandatory runbook with alerting on failure |
| **REQ-04: Data quality rules engine** | Rule explosion: hundreds of rules slow profiling; conflicting rules (not-null + default-null) | Rule priorities + conflict detection at save time; incremental rule evaluation |
| **REQ-05: Team collaboration (share/approve)** | Race condition: two reviewers approve different versions; audit trail forks | Optimistic locking on workspace version; linear approval chain |
| **REQ-06: Advanced duplicate detection (fuzzy/ML)** | O(n²) scaling; model drift on new data patterns; false positive fatigue | Blocking keys + approximate nearest neighbor (FAISS/Annoy); human-in-the-loop threshold tuning |
| **REQ-07: Data lineage tracking** | Lineage graph explosion (column-level × transformation × table); storage blowup | Aggregate lineage at transformation level; column-level only for regulated columns |
| **REQ-08: Performance optimization (partitioning/batching)** | Partition pruning fails if partition key not in WHERE; batch boundaries split transactions | Explicit partition key in all staged queries; idempotent batch design with checkpoint table |

---

## Sources

| Source | Confidence | Relevance |
|--------|------------|-----------|
| MySQL 8.0 Reference Manual 10.2.3 (Optimizing INFORMATION_SCHEMA Queries) | HIGH | Direct from vendor docs |
| MySQL 8.0 Reference Manual 10.2.4 (Optimizing Performance Schema Queries) | HIGH | Direct from vendor docs |
| Budibase GHSA-ppj8-hmx2-m546 (CVE-2026-100683) — Second-order SQL identifier injection | HIGH | Real CVE, same tech stack (MySQL, dynamic DDL, backticks) |
| Ansible community.mysql collection — Identifier Quoting and SQL Safety (DeepWiki) | HIGH | Production-grade identifier quoting implementation |
| Retail Taxonomy — "Common Pitfalls in Data Cleansing and How to Avoid Them" (2023) | MEDIUM | Industry practitioner perspective |
| Data Engineer Academy — "Common Data Pipeline Failures and How to Prevent Them" (2026) | MEDIUM | Pipeline failure taxonomy, silent failure emphasis |
| OvalEdge — "Data Cleaning Techniques: Methods & Best Practices 2026" | MEDIUM | Vendor guide, comprehensive technique coverage |
| Streamlit Community — "FAQ: How to improve performance of apps with large data" (2024) | HIGH | Official Streamlit guidance |
| Streamlit Community — "Scaling streamlit to hundreds of users with heavy data object" (2022) | MEDIUM | Real-world scaling discussion |
| fpdf2 Official Documentation — Tables (v2.7+, 2026) | HIGH | Direct from library docs |
| fpdf2 GitHub Issue #1092 — "FPDFRecorder frequent usage makes document generation slow" | MEDIUM | Known performance issue |

---

## Confidence Assessment

| Area | Confidence | Reason |
|------|------------|--------|
| SQL Injection / Identifier Quoting | HIGH | Real CVE (Budibase), Ansible production code, MySQL docs |
| INFORMATION_SCHEMA Performance | HIGH | Official MySQL 8.0 optimization guide |
| Streamlit Memory/Scaling | HIGH | Official Streamlit FAQ + community reports |
| Orphaned Staging Tables | HIGH | Architectural gap identified in CONCERNS.md + common pattern |
| Workspace Confinement | HIGH | Core safety principle; codebase has `_quote_identifier` but needs audit |
| Date/Boolean Ambiguity | MEDIUM | DCT already implements ambiguity→NULL; risk is UX/communication |
| Duplicate Detection | MEDIUM | Known hard problem; DCT has exact-match only currently |
| PDF Generation | MEDIUM | fpdf2 docs show capabilities/limits; not tested at DCT scale |
| Dialect Lock-in | HIGH | Codebase inspection confirms MySQL-specific constructs throughout |
| Monolithic Files | HIGH | Measured: 7,319 and 5,365 lines |

---

## Gaps to Address (Require Phase-Specific Research)

- [ ] **REQ-02 Custom Rules**: ReDoS mitigation libraries comparison (`re2` vs `regex` vs `re` with timeout)
- [ ] **REQ-06 Fuzzy/ML Duplicates**: Approximate nearest neighbor libraries for Python (FAISS, Annoy, HNSWLib) — benchmark on 100K+ rows
- [ ] **REQ-07 Lineage**: Column-level lineage storage schema design (graph vs relational)
- [ ] **REQ-08 Partitioning**: MySQL 8.0 native partitioning vs manual sharding for staging tables
- [ ] **AI Integration**: `openai`/`tiktoken`/`tenacity` integration patterns for data quality copilot (prompt injection safety, cost control)