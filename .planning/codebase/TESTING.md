---
last_mapped_commit: df6531c57a6b9e852d2a034c380a3e98ef1c60d1
last_mapped_at: 2026-10-09
---
# Testing Strategies & Test Suite Overview

**Analysis Date:** 2026-10-09

## Testing Framework & Tooling

**Core Test Framework:**
- **Framework:** [Pytest 9.1.1](https://docs.pytest.org/)
- **Plugins:** `anyio 4.14.2`, `Faker 40.36.0`
- **Execution Command:**
  ```bash
  python -m pytest
  ```
- **Execution Speed:** Complete test suite of 203 tests executes in ~3.2 seconds.

## Test Suite Structure

```
tests/
├── test_stage1.py                           # 6 tests  - Connection & Discovery
├── test_stage2.py                           # 11 tests - Workspace Creation & Staging
├── test_stage3.py                           # 14 tests - Whitespace & Blank Values
├── test_stage4.py                           # 13 tests - Missing Value Imputation
├── test_stage5_casing.py                    # 13 tests - Text Casing Normalization
├── test_stage6_duplicates.py                # 45 tests - Duplicate Detection & Row Selection
├── test_stage7_date_format.py               # 25 tests - Native Date Formatting
├── test_stage8_boolean_normalization.py     # 13 tests - Boolean Inference & Conversion
├── test_stage9_advanced_date_standardization.py # 50 tests - Deterministic Date Rules 1 & 2
├── test_pdf_report.py                       # 5 tests  - PDF Report Generation
└── test_workspace_persistence.py           # 8 tests  - Multi-Workspace Discovery & Attach
```

**Total Test Coverage:** 203 tests, 100% passing.

## Mocking & Isolation Strategy

**In-Memory & Mock Database Execution:**
- Tests do not require a live MySQL server running during CI or local testing.
- Tests utilize mocked SQLAlchemy engines, mock connections, and SQLite in-memory databases configured to emulate MySQL behavior where appropriate.
- Database metadata inspector results and schema dictionaries are mocked to test edge cases (e.g. system schemas, network timeouts, invalid credentials, empty tables).

**Parametrized Testing:**
- Extensive use of `@pytest.mark.parametrize` to validate multi-format permutations:
  - Date format outputs: `YYYY-MM-DD`, `DD-MM-YYYY`, `MM-DD-YYYY`, `DD/MM/YYYY`, `MM/DD/YYYY`, `YYYY/MM/DD`, `YYYY.MM.DD`.
  - Ambiguous date inputs: Ensuring values like `05/06/2026` or `01-02-2026` safely resolve to `NULL`.
  - Text month formats: `15 August 2026`, `Aug-15-2026`, `15-Nov-2026`, `Sept 09, 2026`.
  - Scan percentage thresholds: 20%, 30%, 40%, 80%.

## Key Verification Patterns

1. **Source Table Immutability:** Tests explicitly assert that source tables are never altered during workspace transformations.
2. **Rollback Verification:** Fault-injection tests verify that SQL failures cleanly trigger transaction rollbacks without leaving partial changes.
3. **Safety Assertions:** Checks that non-workspace tables (missing `__cleaning_` suffix) trigger immediate refusal exceptions.
4. **Interactive Action State Machine:** Tests in `test_stage6_duplicates.py` thoroughly validate keep/remove toggling, select-all behavior, and independent group manipulation.

---

*Testing analysis: 2026-10-09*
*Update as test suites expand*
