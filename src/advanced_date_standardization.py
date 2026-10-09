"""
Advanced Date Standardization Engine (Deterministic Rules 1 & 2).

Detects and standardizes date-like values stored in VARCHAR / TEXT database columns
using strictly deterministic parsing rules:
  - Rule 1: Textual Month Detection (Month name/abbreviation + 4-digit year + remaining day)
  - Rule 2: Numeric Date Detection (Date separators /, -, . + 4-digit year + unambiguous day > 12)
  - Ambiguous (both remaining <= 12), invalid (e.g. 31/02/2026), or unrecognized values -> NULL
  - Always writes to a new output column (<column>_standardized) and preserves the original column.
"""

from datetime import datetime
import logging
import math
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import inspect, text

logger = logging.getLogger(__name__)

# Default threshold for a scanned text column to be flagged as containing date-like values
DEFAULT_DETECTION_THRESHOLD: float = 0.25

# Allowed scan percentages for the UI slider/selector
ALLOWED_SCAN_PERCENTAGES: List[int] = [20, 30, 40, 80]

# Supported output date formats (Section 8)
SUPPORTED_OUTPUT_FORMATS: Dict[str, str] = {
    "YYYY-MM-DD": "%Y-%m-%d",
    "DD-MM-YYYY": "%d-%m-%Y",
    "MM-DD-YYYY": "%m-%d-%Y",
    "DD/MM/YYYY": "%d/%m/%Y",
    "MM/DD/YYYY": "%m/%d/%Y",
    "YYYY/MM/DD": "%Y/%m/%d",
    "YYYY.MM.DD": "%Y.%m.%d",
}

# Rule 1 Month Mapping (Case-insensitive, unambiguous full & abbreviated month names)
MONTH_MAPPING: Dict[str, int] = {
    "january": 1,
    "jan": 1,
    "february": 2,
    "feb": 2,
    "march": 3,
    "mar": 3,
    "april": 4,
    "apr": 4,
    "may": 5,
    "june": 6,
    "jun": 6,
    "july": 7,
    "jul": 7,
    "august": 8,
    "aug": 8,
    "september": 9,
    "sep": 9,
    "sept": 9,
    "october": 10,
    "oct": 10,
    "november": 11,
    "nov": 11,
    "december": 12,
    "dec": 12,
}

# Precompiled regexes
_TEXT_TOKEN_SPLIT_RE = re.compile(r"[\s,/\-\.]+")
_NUMERIC_SEP_RE = re.compile(r"^\s*(\d+)\s*([/\-\.])\s*(\d+)\s*([/\-\.])\s*(\d+)\s*$")


def _quote_identifier(identifier: str) -> str:
    if not isinstance(identifier, str) or not identifier:
        raise ValueError("Identifier must be a non-empty string.")
    return f"`{identifier.replace('`', '``')}`"


def _quote_table(database: str, table_name: str) -> str:
    return f"{_quote_identifier(database)}.{_quote_identifier(table_name)}"


def validate_date(year: int, month: int, day: int) -> Optional[Tuple[int, int, int]]:
    """
    Validate (year, month, day) using Python's calendar-accurate datetime constructor.
    Returns (year, month, day) if valid, or None if invalid (e.g. 31/02/2026, 00/12/2026).
    """
    try:
        if not (1000 <= int(year) <= 9999):
            return None
        if not (1 <= int(month) <= 12):
            return None
        if not (1 <= int(day) <= 31):
            return None
        dt = datetime(int(year), int(month), int(day))
        return (dt.year, dt.month, dt.day)
    except (ValueError, TypeError, OverflowError):
        return None


def extract_four_digit_year(tokens: List[str]) -> Tuple[Optional[int], List[str]]:
    """
    Locate a single 4-digit numeric year token (1000..9999) from a list of tokens.
    Returns (year_int, remaining_tokens). If no 4-digit token or multiple 4-digit tokens
    are found, returns (None, tokens).
    """
    year_indices = [
        idx for idx, tok in enumerate(tokens)
        if tok.isdigit() and len(tok) == 4 and 1000 <= int(tok) <= 9999
    ]
    if len(year_indices) != 1:
        return (None, tokens)
    y_idx = year_indices[0]
    year_val = int(tokens[y_idx])
    remaining = [tok for idx, tok in enumerate(tokens) if idx != y_idx]
    return (year_val, remaining)


def contains_textual_month(value: str) -> bool:
    """Return True if the record contains any recognized textual month token."""
    if not value or not isinstance(value, str):
        return False
    tokens = [t for t in _TEXT_TOKEN_SPLIT_RE.split(value.strip()) if t]
    return any(t.lower() in MONTH_MAPPING for t in tokens)


def parse_text_month_date(value: str) -> Optional[Tuple[int, int, int]]:
    """
    RULE 1 — TEXT MONTH DETECTION:
      1. Check if the record contains a recognized textual month (case-insensitive).
      2. Rule 1A: Find a 4-digit numeric component for YEAR.
      3. Rule 1B: Treat the remaining valid numeric component as DAY.
      4. Validate (year, month, day).
    Returns (year, month, day) or None.
    """
    if not value or not isinstance(value, str):
        return None

    cleaned = value.strip()
    if not cleaned:
        return None

    tokens = [t for t in _TEXT_TOKEN_SPLIT_RE.split(cleaned) if t]
    if len(tokens) != 3:
        return None

    # Find textual month token
    month_indices = [idx for idx, tok in enumerate(tokens) if tok.lower() in MONTH_MAPPING]
    if len(month_indices) != 1:
        return None

    m_idx = month_indices[0]
    month_val = MONTH_MAPPING[tokens[m_idx].lower()]
    other_tokens = [tok for idx, tok in enumerate(tokens) if idx != m_idx]

    # Rule 1A: Find 4-digit year among remaining tokens
    year_val, remaining_after_year = extract_four_digit_year(other_tokens)
    if year_val is None or len(remaining_after_year) != 1:
        return None

    # Rule 1B: Remaining valid numeric component is the day
    day_token = remaining_after_year[0]
    if not day_token.isdigit():
        return None

    day_val = int(day_token)
    return validate_date(year_val, month_val, day_val)


def parse_numeric_date(value: str) -> Optional[Tuple[int, int, int]]:
    """
    RULE 2 — NUMERIC DATE DETECTION:
      1. Identify whether the record contains a 3-part numeric structure separated by /, -, or .
      2. Rule 2A: Detect a valid 4-digit numeric component (YEAR).
      3. Rule 2B: Examine the remaining two numeric components:
         - If one remaining component is > 12, treat it as DAY and the other as MONTH.
         - If neither is > 12 (e.g. 05/06/2026) or both are > 12 (e.g. 15/13/2026),
           do NOT guess; return None (NULL).
      4. Validate (year, month, day).
    Returns (year, month, day) or None.
    """
    if not value or not isinstance(value, str):
        return None

    m = _NUMERIC_SEP_RE.match(value)
    if not m:
        return None

    p1, sep1, p2, sep2, p3 = m.group(1), m.group(2), m.group(3), m.group(4), m.group(5)
    # Require consistent date separator (/, -, or .)
    if sep1 != sep2:
        return None

    parts = [p1, p2, p3]

    # Rule 2A: Detect 4-digit year
    year_val, remaining = extract_four_digit_year(parts)
    if year_val is None or len(remaining) != 2:
        return None

    if not (remaining[0].isdigit() and remaining[1].isdigit()):
        return None

    v1 = int(remaining[0])
    v2 = int(remaining[1])

    # Rule 2B: Determine Day and Month (one must be > 12, the other <= 12)
    if v1 > 12 and v2 <= 12:
        day_val = v1
        month_val = v2
    elif v2 > 12 and v1 <= 12:
        day_val = v2
        month_val = v1
    else:
        # Ambiguous (both <= 12, e.g. 05/06/2026) or invalid (both > 12, e.g. 15/13/2026)
        return None

    return validate_date(year_val, month_val, day_val)


def format_standardized_date(
    components: Tuple[int, int, int],
    output_format: str = "YYYY-MM-DD",
) -> str:
    """
    Format validated (year, month, day) tuple into the user-selected output format.
    """
    if output_format not in SUPPORTED_OUTPUT_FORMATS:
        raise ValueError(
            f"Unsupported output format '{output_format}'. "
            f"Supported formats: {list(SUPPORTED_OUTPUT_FORMATS.keys())}"
        )
    year, month, day = components
    dt = datetime(year, month, day)
    return dt.strftime(SUPPORTED_OUTPUT_FORMATS[output_format])


def parse_and_standardize_record(
    value: Any,
    output_format: str = "YYYY-MM-DD",
) -> Optional[str]:
    """
    Process a single record strictly following the Section 14 Processing Order:
      START -> Read record -> Check for textual month:
        - YES -> Apply Text Month Rule (Rule 1) -> Validate -> Format / NULL
        - NO  -> Apply Numeric Date Rule (Rule 2) -> Validate -> Format / NULL
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None

    raw_str = str(value).strip()
    if not raw_str:
        return None

    # Step 1: Check for textual month
    if contains_textual_month(raw_str):
        components = parse_text_month_date(raw_str)
    else:
        # Step 2: Apply Numeric Date Rule
        components = parse_numeric_date(raw_str)

    if components is None:
        return None

    return format_standardized_date(components, output_format=output_format)


def detect_date_like_value(value: Any) -> bool:
    """
    Determine whether a sampled value resembles a date for column detection scanning (Section 16).
    Returns True if:
      - It parses via Rule 1 (Text Month Rule) or Rule 2 (Numeric Date Rule), OR
      - It is a valid 3-part numeric date structure with a 4-digit year (1000..9999) and
        both remaining parts in 1..12 (an ambiguous date like 05/06/2026 is still a date-like
        record for column detection, even though standardization outputs NULL for it).
    """
    if value is None:
        return False
    if isinstance(value, float) and math.isnan(value):
        return False

    raw_str = str(value).strip()
    if not raw_str:
        return False

    if parse_and_standardize_record(raw_str) is not None:
        return True

    # Also recognize ambiguous numeric dates (e.g. 05/06/2026) as date-like during column scanning
    m = _NUMERIC_SEP_RE.match(raw_str)
    if m and m.group(2) == m.group(4):
        parts = [m.group(1), m.group(3), m.group(5)]
        year_val, rem = extract_four_digit_year(parts)
        if year_val is not None and len(rem) == 2 and rem[0].isdigit() and rem[1].isdigit():
            a, b = int(rem[0]), int(rem[1])
            if 1 <= a <= 12 and 1 <= b <= 12:
                return True

    return False


def get_safe_output_column_name(
    existing_columns: List[str],
    source_column: str,
    requested_name: Optional[str] = None,
) -> str:
    """
    Generate a safe output column name (<original_column>_standardized) that never
    overwrites the source column or any existing column in the table (Section 9).
    """
    existing_lower = {c.lower() for c in existing_columns}
    base_name = (requested_name or f"{source_column}_standardized").strip()
    if not base_name or base_name.lower() == source_column.lower():
        base_name = f"{source_column}_standardized"

    candidate = base_name[:64]
    counter = 2
    while candidate.lower() in existing_lower:
        suffix = f"_{counter}"
        candidate = f"{base_name[:64 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def detect_date_columns(
    engine,
    database: str,
    table_name: str,
    scan_percentage: int = 20,
    detection_threshold: float = DEFAULT_DETECTION_THRESHOLD,
) -> List[Dict[str, Any]]:
    """
    Scan eligible VARCHAR / TEXT columns in `table_name`, sampling `scan_percentage`%
    of records, and return columns whose proportion of date-like values meets or exceeds
    `detection_threshold`.
    """
    from src.staging import get_text_columns

    try:
        text_cols = get_text_columns(engine, database, table_name)
        if not text_cols:
            return []

        quoted_table = _quote_table(database, table_name)
        detected: List[Dict[str, Any]] = []

        with engine.connect() as conn:
            total_rows_q = text(f"SELECT COUNT(*) FROM {quoted_table}")
            total_rows = int(conn.execute(total_rows_q).scalar() or 0)
            if total_rows == 0:
                return []

            pct = max(1, min(100, int(scan_percentage)))
            sample_limit = max(1, int(math.ceil(total_rows * (pct / 100.0))))

            for col in text_cols:
                if col.startswith("__bool_backup_"):
                    continue
                quoted_col = _quote_identifier(col)
                sample_q = text(
                    f"SELECT {quoted_col} AS val FROM {quoted_table} "
                    f"WHERE {quoted_col} IS NOT NULL AND TRIM(CAST({quoted_col} AS CHAR)) != '' "
                    f"LIMIT :sample_limit"
                )
                rows = conn.execute(sample_q, {"sample_limit": sample_limit}).fetchall()
                if not rows:
                    continue

                sampled_values = [r._mapping["val"] for r in rows]
                date_like_count = sum(1 for v in sampled_values if detect_date_like_value(v))
                convertible_count = sum(
                    1 for v in sampled_values if parse_and_standardize_record(v) is not None
                )
                proportion = date_like_count / len(sampled_values)

                if proportion >= detection_threshold:
                    detected.append({
                        "column": col,
                        "date_like_percentage": round(proportion * 100.0, 1),
                        "scan_percentage": pct,
                        "sample_size": len(sampled_values),
                        "date_like_count": date_like_count,
                        "convertible_count": convertible_count,
                        "total_rows": total_rows,
                    })

        detected.sort(key=lambda x: x["date_like_percentage"], reverse=True)
        return detected

    except Exception as e:
        logger.error("Error in detect_date_columns for '%s.%s': %s", database, table_name, str(e))
        return []


def preview_column_standardization(
    engine,
    database: str,
    table_name: str,
    column: str,
    output_format: str = "YYYY-MM-DD",
    preview_limit: int = 100,
) -> Dict[str, Any]:
    """
    Generate a Before / After preview and conversion statistics for `column`
    before creating the standardized output column (Section 18).
    """
    try:
        inspector = inspect(engine)
        cols_info = inspector.get_columns(table_name, schema=database)
        existing_cols = [c["name"] for c in cols_info]
        proposed_col = get_safe_output_column_name(existing_cols, column)

        quoted_table = _quote_table(database, table_name)
        quoted_col = _quote_identifier(column)

        with engine.connect() as conn:
            rows = conn.execute(
                text(f"SELECT {quoted_col} AS val FROM {quoted_table}")
            ).fetchall()

        total_records = len(rows)
        converted_count = 0
        unconverted_count = 0
        preview_rows: List[Dict[str, str]] = []

        for idx, r in enumerate(rows):
            orig = r._mapping["val"]
            std = parse_and_standardize_record(orig, output_format=output_format)
            if std is not None:
                converted_count += 1
            else:
                unconverted_count += 1

            if idx < preview_limit:
                preview_rows.append({
                    "Original Value": "NULL" if orig is None else str(orig),
                    "Standardized Value": "NULL" if std is None else std,
                })

        rate = round((converted_count / total_records) * 100.0, 1) if total_records > 0 else 0.0
        return {
            "source_column": column,
            "proposed_output_column": proposed_col,
            "output_format": output_format,
            "total_records": total_records,
            "successfully_converted": converted_count,
            "unconverted": unconverted_count,
            "conversion_rate": rate,
            "preview_rows": preview_rows,
        }

    except Exception as e:
        logger.error(
            "Error previewing date standardization for '%s.%s' (%s): %s",
            database,
            table_name,
            column,
            str(e),
        )
        return {}


def standardize_column(
    engine,
    database: str,
    working_table_name: str,
    column: str,
    output_format: str = "YYYY-MM-DD",
    output_column: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Execute deterministic Advanced Date Standardization on `column` in `working_table_name`:
      1. Read the selected source column.
      2. Process each record individually through Rule 1 -> Rule 2 -> Validate -> Format.
      3. Create a NEW output column (<column>_standardized, handling collisions safely).
      4. Insert formatted date or NULL for unconvertible/ambiguous/invalid records.
      5. Preserve the original column completely untouched.
    """
    from src.staging import CLEANING_SUFFIX, _make_safe_table_name

    try:
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to modify a table that is not an active cleaning workspace.",
                {},
            )
        if _make_safe_table_name(working_table_name) != working_table_name:
            return (False, "Invalid workspace table identifier.", {})

        if output_format not in SUPPORTED_OUTPUT_FORMATS:
            return (False, f"Unsupported output date format '{output_format}'.", {})

        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database)
        if working_table_name not in tables:
            return (
                False,
                f"Workspace table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        cols_info = inspector.get_columns(working_table_name, schema=database)
        existing_cols = [c["name"] for c in cols_info]
        if column not in existing_cols:
            return (
                False,
                f"Column '{column}' not found in workspace table '{working_table_name}'.",
                {},
            )

        safe_out_col = get_safe_output_column_name(existing_cols, column, output_column)
        quoted_table = _quote_table(database, working_table_name)
        quoted_src_col = _quote_identifier(column)
        quoted_out_col = _quote_identifier(safe_out_col)

        with engine.begin() as conn:
            # 1. Read all records in source column to compute exact per-record stats
            all_rows = conn.execute(
                text(f"SELECT {quoted_src_col} AS val FROM {quoted_table}")
            ).fetchall()

            total_records = len(all_rows)
            converted_count = 0
            distinct_mapping: Dict[str, Optional[str]] = {}

            for r in all_rows:
                orig = r._mapping["val"]
                if orig is None:
                    continue
                orig_str = str(orig)
                if orig_str not in distinct_mapping:
                    distinct_mapping[orig_str] = parse_and_standardize_record(
                        orig_str, output_format=output_format
                    )
                if distinct_mapping[orig_str] is not None:
                    converted_count += 1

            unconverted_count = total_records - converted_count
            conversion_rate = (
                round((converted_count / total_records) * 100.0, 1)
                if total_records > 0
                else 0.0
            )

            # 2. Create the new output column (defaulting all rows to NULL)
            conn.execute(
                text(
                    f"ALTER TABLE {quoted_table} "
                    f"ADD COLUMN {quoted_out_col} VARCHAR(32) NULL DEFAULT NULL"
                )
            )

            # 3. Update converted records using parameterized SQL
            update_stmt = text(
                f"UPDATE {quoted_table} "
                f"SET {quoted_out_col} = :std_val "
                f"WHERE {quoted_src_col} = :orig_val"
            )
            params_batch = [
                {"std_val": std_val, "orig_val": orig_val}
                for orig_val, std_val in distinct_mapping.items()
                if std_val is not None
            ]
            if params_batch:
                conn.execute(update_stmt, params_batch)

        report = {
            "operation": "Advanced Date Standardization",
            "source_column": column,
            "output_column": safe_out_col,
            "output_format": output_format,
            "total_records": total_records,
            "successfully_converted": converted_count,
            "unconverted": unconverted_count,
            "conversion_rate": conversion_rate,
            "status": "completed",
        }

        msg = (
            f"Advanced Date Standardization completed for '{column}' -> '{safe_out_col}'. "
            f"{converted_count:,} of {total_records:,} records converted ({conversion_rate}%)."
        )
        return (True, msg, report)

    except Exception as e:
        logger.error(
            "Error standardizing date column '%s.%s' (%s): %s",
            database,
            working_table_name,
            column,
            str(e),
        )
        return (
            False,
            f"Error during Advanced Date Standardization: {str(e)}",
            {},
        )
