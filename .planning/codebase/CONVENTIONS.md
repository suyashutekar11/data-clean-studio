# Coding Conventions & Development Guidelines

**Analysis Date:** 2026-10-09

## Code Style & Formatting

**Python Standards:**
- **PEP 8 Compliance:** 4-space indentation, snake_case functions and variables, PascalCase classes.
- **Type Annotations:** Extensive type hinting using Python's standard `typing` module (`Optional`, `Dict`, `List`, `Tuple`, `Any`) and `dataclasses`.
- **Docstrings:** Google/Sphinx style docstrings detailing function purpose, arguments, and return types.

## Database & SQL Safety Conventions

**Strict Identifier Quoting:**
- All dynamic MySQL identifiers (database name, table name, column name) must be passed through `_quote_identifier()` before inclusion in any SQL statement.
- Double backticks are escaped to prevent identifier injection:
  ```python
  def _quote_identifier(identifier: str) -> str:
      if not isinstance(identifier, str) or not identifier:
          raise ValueError("Identifier must be a non-empty string.")
      return f"`{identifier.replace('`', '``')}`"
  ```

**Parameterized Queries:**
- Literal values, limits, and filter criteria must be passed via SQLAlchemy bound parameters (`text("... WHERE col = :val")`) rather than string interpolation.

**Workspace Isolation Enforcement:**
- Any modifying operation (drop, update, alter, delete) must verify that the target table is an authentic workspace table before execution:
  - Target table must contain the `__cleaning_` marker.
  - Operations refuse to touch raw source tables without the prefix.

## Error Handling & Logging

**Exception Handling:**
- Wrap database and transformation operations in explicit `try ... except SQLAlchemyError` blocks.
- Distinguish between connection-level errors (`OperationalError`), syntax/table errors (`ProgrammingError`), and general database faults.
- Provide descriptive, user-friendly error messages that do not expose sensitive credentials in traceback strings.
- Always execute database rollbacks within exception blocks to prevent poisoned transactions.

**Logging:**
- Standard Python `logging.getLogger(__name__)` used across backend modules.
- Informative log levels:
  - `DEBUG`: Query strings and intermediate parsing metrics
  - `INFO`: Stage transitions and workspace lifecycle events
  - `WARNING`: Ambiguous date matches or skipped records
  - `ERROR`: Database connection failures or query aborts

## Streamlit UI & Session State Conventions

**Session State Hygiene:**
- Initialize state variables conditionally using `if "key" not in st.session_state:`
- Keep sensitive credentials in memory only; avoid serializing session states to disk.
- Centralize state resets when switching databases or disconnecting to prevent stale metadata leaks.

**Visual & UX Guidelines:**
- Modular UI rendering functions with clear visual hierarchies (KPI metrics, cards, interactive dataframes).
- Consistent color palette matching enterprise soft dark/light branding.
- HTML injections sanitized and formatted via helper `render_html()` to prevent whitespace formatting artifacts.

---

*Conventions analysis: 2026-10-09*
*Update as coding standards evolve*
