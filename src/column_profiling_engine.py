"""
DataClean Studio — Column Profiling Engine
src/column_profiling_engine.py

Phase 1 Column Profiling Engine:
Reusable, rule-based profiling engine that analyzes actual records in a user-selected
database column and calculates exact counts and percentages across 12 primary value
pattern categories.

Key Architectural Guarantees:
1. Read-only safety: Strictly ANSI SQL SELECT queries with schema validation; zero DDL/DML.
2. Dialect agnostic: Supports MySQL and SQLite (and standard ANSI SQL engines) with dialect-aware quoting.
3. Streamed batch processing: Fetches records in configurable batch chunks (default 5,000)
   to ensure low memory overhead on large tables without sampling.
4. Mutually exclusive classification: Clear rule precedence prevents double counting.
   Every record is assigned exactly one primary category.
5. Accurate percentages: Denominator is strictly total records scanned; handles empty tables safely.
"""

from __future__ import annotations

import datetime
from decimal import Decimal
from enum import Enum
import logging
import math
import re
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import pandas as pd
from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

logger = logging.getLogger(__name__)


class ValuePatternCategory(str, Enum):
    """Enumeration of the primary value pattern categories."""
    NUMERIC_ONLY = "numeric_only"
    ALPHABETIC_ONLY = "alphabetic_only"
    ALPHANUMERIC = "alphanumeric"
    NUMERIC_SPECIAL = "numeric_special"
    TEXT_SPECIAL = "text_special"
    MIXED = "mixed"
    DATE_LIKE = "date_like"
    BOOLEAN_LIKE = "boolean_like"
    EMPTY_STRING = "empty_string"
    WHITESPACE_ONLY = "whitespace_only"
    SQL_NULL = "sql_null"
    MISSING_PLACEHOLDER = "missing_placeholder"
    OTHER = "other"


CATEGORY_DISPLAY_LABELS: Dict[str, str] = {
    ValuePatternCategory.NUMERIC_ONLY.value: "Numeric only",
    ValuePatternCategory.ALPHABETIC_ONLY.value: "Alphabetic text only",
    ValuePatternCategory.ALPHANUMERIC.value: "Alphanumeric",
    ValuePatternCategory.NUMERIC_SPECIAL.value: "Numeric with special characters",
    ValuePatternCategory.TEXT_SPECIAL.value: "Text with special characters",
    ValuePatternCategory.MIXED.value: "Mixed (letters, numbers & special characters)",
    ValuePatternCategory.DATE_LIKE.value: "Date-like",
    ValuePatternCategory.BOOLEAN_LIKE.value: "Boolean-like",
    ValuePatternCategory.EMPTY_STRING.value: "Empty strings",
    ValuePatternCategory.WHITESPACE_ONLY.value: "Whitespace-only",
    ValuePatternCategory.SQL_NULL.value: "SQL NULL",
    ValuePatternCategory.MISSING_PLACEHOLDER.value: "Missing-Value Placeholders",
    ValuePatternCategory.OTHER.value: "Other / Unclassified",
}

# Configurable missing-value placeholders (matched case-insensitively after trimming)
DEFAULT_MISSING_PLACEHOLDERS: Tuple[str, ...] = (
    "n/a",
    "na",
    "not applicable",
    "unknown",
    "none",
    "null",
    "nan",
    "nil",
    "-",
    "--",
    "?",
    "n.a.",
    "n/d",
    "not available",
)

_NORMALIZED_DEFAULT_PLACEHOLDERS: frozenset[str] = frozenset(
    p.strip().lower() for p in DEFAULT_MISSING_PLACEHOLDERS
)


def normalize_missing_placeholders(placeholders: Optional[Iterable[str]] = None) -> frozenset[str]:
    """
    Normalizes a collection of placeholder strings by trimming surrounding whitespace
    and converting to lowercase. If None is provided, returns the default normalized set.
    """
    if placeholders is None:
        return _NORMALIZED_DEFAULT_PLACEHOLDERS
    return frozenset(str(p).strip().lower() for p in placeholders if str(p).strip())


# Canonical boolean tokens (case-insensitive, stripped)
BOOLEAN_CANONICAL_TOKENS = {
    "true", "false",
    "yes", "no",
    "t", "f",
    "y", "n",
}

# Month names and abbreviations for date recognition
MONTH_NAMES = {
    "jan", "january",
    "feb", "february",
    "mar", "march",
    "apr", "april",
    "may",
    "jun", "june",
    "jul", "july",
    "aug", "august",
    "sep", "sept", "september",
    "oct", "october",
    "nov", "november",
    "dec", "december",
}

# Regex for pure numeric strings: integer, decimal, negative, optional exponent
_NUMERIC_REGEX = re.compile(r"^[-+]?(\d+(\.\d*)?|\.\d+)([eE][-+]?\d+)?$")

# Regex for ISO dates: YYYY-MM-DD or YYYY/MM/DD or YYYY.MM.DD with optional time
_ISO_DATE_REGEX = re.compile(
    r"^(\d{4})[-/.](\d{1,2})[-/.](\d{1,2})"
    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?)?$"
)

# Regex for separated dates: DD/MM/YYYY, MM/DD/YYYY, DD-MM-YYYY, etc.
_SEPARATED_DATE_REGEX = re.compile(
    r"^(\d{1,2})[-/.](\d{1,2})[-/.](\d{2,4})"
    r"(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?$"
)

# Regex for textual month dates: "15 Jan 2024", "15-January-2024", "January 15, 2024"
_TEXTUAL_DATE_1 = re.compile(
    r"^(\d{1,2})[-\s/]+([A-Za-z]{3,9})[-\s/]+(\d{2,4})(?:[ T](\d{1,2}):(\d{2}))?$"
)
_TEXTUAL_DATE_2 = re.compile(
    r"^([A-Za-z]{3,9})[-\s/]+(\d{1,2}),?[-\s/]+(\d{2,4})(?:[ T](\d{1,2}):(\d{2}))?$"
)


def _quote_identifier(identifier: str, dialect_name: str = "mysql") -> str:
    """
    Safely quote a SQL identifier based on database dialect.
    Escapes quotes to prevent SQL identifier injection.
    """
    if not isinstance(identifier, str) or not identifier.strip():
        raise ValueError("Identifier must be a non-empty string.")
    
    clean_id = identifier.strip()
    if dialect_name == "sqlite":
        return f'"{clean_id.replace('"', '""')}"'
    return f"`{clean_id.replace('`', '``')}`"


def _quote_table(database: Optional[str], table_name: str, dialect_name: str = "mysql") -> str:
    """Return fully qualified quoted table identifier."""
    quoted_tbl = _quote_identifier(table_name, dialect_name)
    if database and database.strip() and dialect_name != "sqlite":
        quoted_db = _quote_identifier(database, dialect_name)
        return f"{quoted_db}.{quoted_tbl}"
    return quoted_tbl


def _is_date_like(val_str: str) -> bool:
    """
    Determines whether a string represents a recognizable date or timestamp.
    Requires structured delimiters or textual month representations to avoid
    falsely classifying generic numbers as dates.
    """
    s = val_str.strip()
    if len(s) < 6:
        return False

    # Check ISO format: YYYY-MM-DD
    m_iso = _ISO_DATE_REGEX.match(s)
    if m_iso:
        y, m, d = int(m_iso.group(1)), int(m_iso.group(2)), int(m_iso.group(3))
        if 1000 <= y <= 9999 and 1 <= m <= 12 and 1 <= d <= 31:
            return True

    # Check separated dates: DD/MM/YYYY or MM/DD/YYYY or DD-MM-YYYY
    m_sep = _SEPARATED_DATE_REGEX.match(s)
    if m_sep:
        p1, p2, p3 = int(m_sep.group(1)), int(m_sep.group(2)), int(m_sep.group(3))
        # Case A: 4-digit year at end (e.g. 15/03/2024 or 03/15/2024)
        if 1000 <= p3 <= 9999:
            if (1 <= p1 <= 31 and 1 <= p2 <= 12) or (1 <= p1 <= 12 and 1 <= p2 <= 31):
                return True
        # Case B: 2-digit year at end (e.g. 15/03/24)
        elif 0 <= p3 <= 99:
            if (1 <= p1 <= 31 and 1 <= p2 <= 12) or (1 <= p1 <= 12 and 1 <= p2 <= 31):
                return True

    # Check textual month formats: "15 Jan 2024" or "Jan 15, 2024"
    m_txt1 = _TEXTUAL_DATE_1.match(s)
    if m_txt1:
        day_val, month_val, year_val = int(m_txt1.group(1)), m_txt1.group(2).lower(), int(m_txt1.group(3))
        if month_val in MONTH_NAMES and 1 <= day_val <= 31:
            return True

    m_txt2 = _TEXTUAL_DATE_2.match(s)
    if m_txt2:
        month_val, day_val, year_val = m_txt2.group(1).lower(), int(m_txt2.group(2)), int(m_txt2.group(3))
        if month_val in MONTH_NAMES and 1 <= day_val <= 31:
            return True

    return False


def _is_numeric_string(s: str) -> bool:
    """Returns True if string represents a valid integer, decimal, or scientific number."""
    if not _NUMERIC_REGEX.match(s):
        return False
    try:
        float(s)
        return True
    except (ValueError, OverflowError):
        return False


# Column name heuristics for disambiguating numeric 0/1 as boolean flags
_BOOL_NAME_PATTERN = re.compile(
    r"(?:^|_)(?:is|has|can|should|was|did|will|allow|enable|enabled|active|verified|"
    r"available|deleted|archived|approved|confirmed|valid|published|visible|locked|"
    r"default|primary|required|optional|bool|boolean|flag|opt_in|subscribed)(?:$|_)",
    re.I,
)


def _is_boolean_context(declared_type: str = "", column_name: str = "") -> bool:
    """Returns True if declared type or column name suggests a boolean flag context."""
    norm_dtype = (declared_type or "").lower()
    if any(t in norm_dtype for t in ("bool", "boolean", "bit", "tinyint(1)")):
        return True
    if column_name and _BOOL_NAME_PATTERN.search(column_name):
        return True
    return False


def classify_value(
    val: Any,
    declared_type: str = "",
    column_name: str = "",
    missing_placeholders: Optional[Iterable[str]] = None,
) -> ValuePatternCategory:
    """
    Classify a single value into exactly one primary ValuePatternCategory based on
    strict precedence rules to prevent double-counting.

    Precedence Hierarchy:
    1. SQL NULL: None, pd.NA, float('nan')
    2. Boolean instance: bool
    3. Numeric instances: int, float, Decimal
    4. Date & DateTime instances: date, datetime, Timestamp
    5. Empty String: len == 0 string
    6. Whitespace-Only: non-empty string consisting exclusively of whitespace
    7. Missing-Value Placeholders: configurable text placeholders (e.g. N/A, NA, Not Applicable, Unknown)
    8. Boolean-Like: canonical boolean token ("true", "yes", etc., or 0/1 in boolean context)
    9. Date-Like: recognizable date string format
    10. Numeric Only: pure numeric string (+/- and decimal allowed)
    11. Character Composition Analysis:
       - Alphabetic Only: letters only (spaces allowed)
       - Alphanumeric: letters + digits (spaces allowed, no special chars)
       - Numeric with Special Chars: digits + special characters (no letters)
       - Text with Special Chars: letters + special characters (no digits)
       - Mixed: letters + digits + special characters
       - Other / Unclassified: special characters only, symbols, or unclassified
    """
    # 1. SQL NULL
    if val is None:
        return ValuePatternCategory.SQL_NULL
    if isinstance(val, float) and math.isnan(val):
        return ValuePatternCategory.SQL_NULL
    try:
        if pd.isna(val):
            return ValuePatternCategory.SQL_NULL
    except Exception:
        pass

    # 2. Boolean instance (MUST be evaluated before int, because in Python bool subclasses int)
    if isinstance(val, bool):
        return ValuePatternCategory.BOOLEAN_LIKE

    # 3. Numeric Python instances
    if isinstance(val, (int, Decimal)):
        if _is_boolean_context(declared_type, column_name) and val in (0, 1):
            return ValuePatternCategory.BOOLEAN_LIKE
        return ValuePatternCategory.NUMERIC_ONLY

    if isinstance(val, float):
        return ValuePatternCategory.NUMERIC_ONLY

    # 4. Date & DateTime instances
    if isinstance(val, (datetime.date, datetime.datetime, pd.Timestamp)):
        return ValuePatternCategory.DATE_LIKE

    # 5. Non-string types fallback (bytes, bytearrays, custom objects)
    if not isinstance(val, str):
        val_str = str(val)
    else:
        val_str = val

    # 6. String length checks
    if len(val_str) == 0:
        return ValuePatternCategory.EMPTY_STRING

    if val_str.isspace():
        return ValuePatternCategory.WHITESPACE_ONLY

    stripped = val_str.strip()
    lowered = stripped.lower()

    # 7. Missing-value placeholders (case-insensitive after trimming)
    if missing_placeholders is None:
        ph_set = _NORMALIZED_DEFAULT_PLACEHOLDERS
    elif isinstance(missing_placeholders, frozenset):
        ph_set = missing_placeholders
    else:
        ph_set = normalize_missing_placeholders(missing_placeholders)

    if lowered in ph_set:
        return ValuePatternCategory.MISSING_PLACEHOLDER

    # 8. Boolean-like strings
    if lowered in BOOLEAN_CANONICAL_TOKENS:
        return ValuePatternCategory.BOOLEAN_LIKE

    if _is_boolean_context(declared_type, column_name) and stripped in ("0", "1"):
        return ValuePatternCategory.BOOLEAN_LIKE

    # 8. Date-like strings
    if _is_date_like(stripped):
        return ValuePatternCategory.DATE_LIKE

    # 9. Numeric-only strings (valid integers, decimals, negatives, scientific notation)
    if _is_numeric_string(stripped):
        return ValuePatternCategory.NUMERIC_ONLY

    # 10. Character-level composition analysis
    has_letters = any(c.isalpha() for c in stripped)
    has_digits = any(c.isdigit() for c in stripped)
    has_special = any(not c.isalnum() and not c.isspace() for c in stripped)

    if has_letters and not has_digits and not has_special:
        return ValuePatternCategory.ALPHABETIC_ONLY

    if has_letters and has_digits and not has_special:
        return ValuePatternCategory.ALPHANUMERIC

    if not has_letters and has_digits and has_special:
        return ValuePatternCategory.NUMERIC_SPECIAL

    if has_letters and not has_digits and has_special:
        return ValuePatternCategory.TEXT_SPECIAL

    if has_letters and has_digits and has_special:
        return ValuePatternCategory.MIXED

    # Special characters only (e.g. "***", "---", "#@!"), control chars, or other
    return ValuePatternCategory.OTHER


class ColumnProfileResult:
    """
    Structured outcome of a column value pattern profiling analysis.
    Designed for consumption by UI components, reporting exports, and AI prompt contexts.
    """
    def __init__(
        self,
        table_name: str,
        column_name: str,
        column_declared_type: str = "TEXT",
        total_records: int = 0,
        non_null_count: int = 0,
        null_count: int = 0,
        missing_count: int = 0,
        placeholder_count: int = 0,
        dominant_pattern: Optional[str] = None,
        dominant_pattern_label: Optional[str] = None,
        dominant_pattern_percentage: float = 0.0,
        percentage_denominator: str = "total_records_scanned",
        counts: Optional[Dict[str, int]] = None,
        percentages: Optional[Dict[str, float]] = None,
        database: Optional[str] = None,
        data_type: Optional[str] = None,
        non_null_records: Optional[int] = None,
        null_records: Optional[int] = None,
        missing_records: Optional[int] = None,
        placeholder_records: Optional[int] = None,
        dominant_category: Optional[Any] = None,
        dominant_percentage: Optional[float] = None,
        dominant_count: Optional[int] = None,
        is_exact: bool = True,
        batch_size: int = 5000,
        dialect: str = "mysql",
        success: bool = True,
        error_message: Optional[str] = None,
        **kwargs: Any,
    ):
        self.database = database
        self.table_name = table_name
        self.column_name = column_name
        self.column_declared_type = data_type if data_type is not None else column_declared_type
        self.total_records = total_records
        self.non_null_count = non_null_records if non_null_records is not None else non_null_count
        self.null_count = null_records if null_records is not None else null_count
        self.missing_count = missing_records if missing_records is not None else missing_count
        self.placeholder_count = placeholder_records if placeholder_records is not None else placeholder_count

        # Dominant pattern resolution
        if dominant_category is not None:
            dom_val = dominant_category.value if hasattr(dominant_category, "value") else str(dominant_category)
            self.dominant_pattern = dom_val
            self.dominant_pattern_label = CATEGORY_DISPLAY_LABELS.get(dom_val, dom_val)
        else:
            self.dominant_pattern = dominant_pattern
            self.dominant_pattern_label = dominant_pattern_label

        if dominant_percentage is not None:
            self.dominant_pattern_percentage = dominant_percentage
        else:
            self.dominant_pattern_percentage = dominant_pattern_percentage

        self.dominant_count = dominant_count if dominant_count is not None else 0
        self.percentage_denominator = percentage_denominator
        self.counts = counts if counts is not None else {}
        self.percentages = percentages if percentages is not None else {}
        self.is_exact = is_exact
        self.batch_size = batch_size
        self.dialect = dialect
        self.success = success
        self.error_message = error_message

    @property
    def data_type(self) -> str:
        """Alias for column_declared_type."""
        return self.column_declared_type

    @property
    def non_null_records(self) -> int:
        """Alias for non_null_count."""
        return self.non_null_count

    @property
    def null_records(self) -> int:
        """Alias for null_count."""
        return self.null_count

    @property
    def missing_records(self) -> int:
        """Alias for missing_count."""
        return self.missing_count

    @property
    def empty_string_records(self) -> int:
        """Count of exact empty string values."""
        return self.counts.get(ValuePatternCategory.EMPTY_STRING.value, 0)

    @property
    def whitespace_records(self) -> int:
        """Count of whitespace-only values."""
        return self.counts.get(ValuePatternCategory.WHITESPACE_ONLY.value, 0)

    @property
    def placeholder_records(self) -> int:
        """Count of missing-value placeholder strings (N/A, NA, etc.)."""
        return self.counts.get(ValuePatternCategory.MISSING_PLACEHOLDER.value, self.placeholder_count)

    @property
    def dominant_percentage(self) -> float:
        """Alias for dominant_pattern_percentage."""
        return self.dominant_pattern_percentage

    @property
    def dominant_category(self) -> Optional[str]:
        """Alias for dominant_pattern."""
        return self.dominant_pattern

    def to_dict(self) -> Dict[str, Any]:
        """Serializes result into a dictionary."""
        return {
            "database": self.database,
            "table_name": self.table_name,
            "column_name": self.column_name,
            "column_declared_type": self.column_declared_type,
            "total_records": self.total_records,
            "non_null_count": self.non_null_count,
            "null_count": self.null_count,
            "empty_string_count": self.empty_string_records,
            "whitespace_count": self.whitespace_records,
            "placeholder_count": self.placeholder_records,
            "missing_count": self.missing_count,
            "dominant_pattern": self.dominant_pattern,
            "dominant_pattern_label": self.dominant_pattern_label,
            "dominant_pattern_percentage": self.dominant_pattern_percentage,
            "percentage_denominator": self.percentage_denominator,
            "counts": dict(self.counts),
            "percentages": dict(self.percentages),
            "is_exact": self.is_exact,
            "batch_size": self.batch_size,
            "dialect": self.dialect,
            "success": self.success,
            "error_message": self.error_message,
        }

    def __repr__(self) -> str:
        return (
            f"<ColumnProfileResult col='{self.column_name}' total={self.total_records} "
            f"dominant='{self.dominant_pattern}' ({self.dominant_pattern_percentage}%)>"
        )


def _compute_profile_summary(
    counts: Dict[str, int],
    total_records: int,
    database: Optional[str],
    table_name: str,
    column_name: str,
    column_declared_type: str,
    is_exact: bool = True,
    batch_size: int = 5000,
    dialect: str = "mysql",
) -> ColumnProfileResult:
    """Computes exact percentages, dominant pattern, and missing counts from raw category frequencies."""
    null_count = counts.get(ValuePatternCategory.SQL_NULL.value, 0)
    empty_count = counts.get(ValuePatternCategory.EMPTY_STRING.value, 0)
    ws_count = counts.get(ValuePatternCategory.WHITESPACE_ONLY.value, 0)
    placeholder_count = counts.get(ValuePatternCategory.MISSING_PLACEHOLDER.value, 0)
    missing_count = null_count + empty_count + ws_count + placeholder_count
    non_null_count = total_records - null_count

    percentages: Dict[str, float] = {}
    for cat in ValuePatternCategory:
        c = counts.get(cat.value, 0)
        pct = round((c / total_records) * 100.0, 2) if total_records > 0 else 0.0
        percentages[cat.value] = pct

    # Dominant pattern detection
    dominant_pattern: Optional[str] = None
    dominant_label: Optional[str] = None
    dominant_pct: float = 0.0

    if total_records > 0:
        # Find category with highest count; in case of tie, preserve canonical category order
        max_cat = max(ValuePatternCategory, key=lambda cat: counts.get(cat.value, 0))
        max_count = counts.get(max_cat.value, 0)
        if max_count > 0:
            dominant_pattern = max_cat.value
            dominant_label = CATEGORY_DISPLAY_LABELS.get(max_cat.value, max_cat.value)
            dominant_pct = percentages.get(max_cat.value, 0.0)

    return ColumnProfileResult(
        database=database,
        table_name=table_name,
        column_name=column_name,
        column_declared_type=column_declared_type,
        total_records=total_records,
        non_null_count=non_null_count,
        null_count=null_count,
        missing_count=missing_count,
        placeholder_count=placeholder_count,
        dominant_pattern=dominant_pattern,
        dominant_pattern_label=dominant_label,
        dominant_pattern_percentage=dominant_pct,
        percentage_denominator="total_records_scanned",
        counts=counts,
        percentages=percentages,
        is_exact=is_exact,
        batch_size=batch_size,
        dialect=dialect,
        success=True,
    )


def profile_values(
    values: Iterable[Any],
    declared_type: str = "",
    database: Optional[str] = None,
    table_name: str = "in_memory",
    column_name: str = "column",
    missing_placeholders: Optional[Iterable[str]] = None,
) -> ColumnProfileResult:
    """
    Profiles an in-memory iterable of column values.
    Analyzes actual records (including repeated values) to calculate pattern distributions.
    Handles empty collections safely.
    """
    norm_placeholders = normalize_missing_placeholders(missing_placeholders)
    counts = {cat.value: 0 for cat in ValuePatternCategory}
    total_records = 0

    for val in values:
        cat = classify_value(
            val,
            declared_type=declared_type,
            column_name=column_name,
            missing_placeholders=norm_placeholders,
        )
        counts[cat.value] += 1
        total_records += 1

    return _compute_profile_summary(
        counts=counts,
        total_records=total_records,
        database=database,
        table_name=table_name,
        column_name=column_name,
        column_declared_type=declared_type or "VARCHAR",
        is_exact=True,
        batch_size=len(counts),
        dialect="memory",
    )


def profile_column(
    engine: Engine,
    database: Optional[str] = None,
    table_name: str = "",
    column_name: str = "",
    batch_size: int = 5000,
    db_name: Optional[str] = None,
    missing_placeholders: Optional[Iterable[str]] = None,
) -> ColumnProfileResult:
    """
    Safely profiles all records in a database column in stream batches.

    Safety & Dialect Guarantees:
    - Validates table and column presence using schema metadata before executing.
    - Strictly ANSI SQL SELECT query with dialect-aware quoting.
    - Zero modification to database records or schema.
    - Streams records in batch chunks of `batch_size` to maintain flat memory usage.
    - Computes exact distribution across all 12 value pattern categories.
    """
    if database is None and db_name is not None:
        database = db_name

    if not engine:
        return ColumnProfileResult(
            database=database,
            table_name=table_name,
            column_name=column_name,
            column_declared_type="UNKNOWN",
            total_records=0,
            non_null_count=0,
            null_count=0,
            missing_count=0,
            dominant_pattern=None,
            dominant_pattern_label=None,
            dominant_pattern_percentage=0.0,
            percentage_denominator="total_records_scanned",
            counts={cat.value: 0 for cat in ValuePatternCategory},
            percentages={cat.value: 0.0 for cat in ValuePatternCategory},
            success=False,
            error_message="No active database engine provided.",
        )

    dialect_name = engine.dialect.name

    # 1. Metadata Schema Validation
    try:
        inspector = inspect(engine)
        schema_target = database if (database and dialect_name != "sqlite") else None
        
        # Verify table existence
        available_tables = inspector.get_table_names(schema=schema_target)
        if table_name not in available_tables:
            return ColumnProfileResult(
                database=database,
                table_name=table_name,
                column_name=column_name,
                column_declared_type="UNKNOWN",
                total_records=0,
                non_null_count=0,
                null_count=0,
                missing_count=0,
                dominant_pattern=None,
                dominant_pattern_label=None,
                dominant_pattern_percentage=0.0,
                percentage_denominator="total_records_scanned",
                counts={cat.value: 0 for cat in ValuePatternCategory},
                percentages={cat.value: 0.0 for cat in ValuePatternCategory},
                success=False,
                error_message=f"Table '{table_name}' does not exist in schema '{database or 'default'}'.",
            )

        # Verify column existence and fetch declared data type
        columns = inspector.get_columns(table_name, schema=schema_target)
        col_meta = next((c for c in columns if c["name"] == column_name), None)
        if not col_meta:
            return ColumnProfileResult(
                database=database,
                table_name=table_name,
                column_name=column_name,
                column_declared_type="UNKNOWN",
                total_records=0,
                non_null_count=0,
                null_count=0,
                missing_count=0,
                dominant_pattern=None,
                dominant_pattern_label=None,
                dominant_pattern_percentage=0.0,
                percentage_denominator="total_records_scanned",
                counts={cat.value: 0 for cat in ValuePatternCategory},
                percentages={cat.value: 0.0 for cat in ValuePatternCategory},
                success=False,
                error_message=f"Column '{column_name}' does not exist in table '{table_name}'.",
            )

        declared_type = str(col_meta.get("type", "VARCHAR"))

    except SQLAlchemyError as err:
        logger.error("Metadata validation error for '%s.%s': %s", table_name, column_name, err)
        return ColumnProfileResult(
            database=database,
            table_name=table_name,
            column_name=column_name,
            column_declared_type="UNKNOWN",
            total_records=0,
            non_null_count=0,
            null_count=0,
            missing_count=0,
            dominant_pattern=None,
            dominant_pattern_label=None,
            dominant_pattern_percentage=0.0,
            percentage_denominator="total_records_scanned",
            counts={cat.value: 0 for cat in ValuePatternCategory},
            percentages={cat.value: 0.0 for cat in ValuePatternCategory},
            success=False,
            error_message=f"Failed to inspect schema metadata: {err}",
        )

    # 2. Build Safe ANSI SQL Query
    try:
        quoted_col = _quote_identifier(column_name, dialect_name)
        quoted_table = _quote_table(database, table_name, dialect_name)
        sql_query = text(f"SELECT {quoted_col} FROM {quoted_table}")
    except ValueError as ve:
        return ColumnProfileResult(
            database=database,
            table_name=table_name,
            column_name=column_name,
            column_declared_type=declared_type,
            total_records=0,
            non_null_count=0,
            null_count=0,
            missing_count=0,
            dominant_pattern=None,
            dominant_pattern_label=None,
            dominant_pattern_percentage=0.0,
            percentage_denominator="total_records_scanned",
            counts={cat.value: 0 for cat in ValuePatternCategory},
            percentages={cat.value: 0.0 for cat in ValuePatternCategory},
            success=False,
            error_message=f"Identifier validation failed: {ve}",
        )

    # 3. Streamed Batch Execution
    norm_placeholders = normalize_missing_placeholders(missing_placeholders)
    counts = {cat.value: 0 for cat in ValuePatternCategory}
    total_records = 0

    try:
        with engine.connect() as conn:
            # Stream results in batches without loading entire table into memory
            cursor = conn.execution_options(stream_results=True).execute(sql_query)
            
            while True:
                batch = cursor.fetchmany(batch_size)
                if not batch:
                    break
                for row in batch:
                    val = row[0]
                    cat = classify_value(
                        val,
                        declared_type=declared_type,
                        column_name=column_name,
                        missing_placeholders=norm_placeholders,
                    )
                    counts[cat.value] += 1
                    total_records += 1

    except SQLAlchemyError as q_err:
        logger.error("Query execution error profiling '%s.%s': %s", table_name, column_name, q_err)
        return ColumnProfileResult(
            database=database,
            table_name=table_name,
            column_name=column_name,
            column_declared_type=declared_type,
            total_records=0,
            non_null_count=0,
            null_count=0,
            missing_count=0,
            dominant_pattern=None,
            dominant_pattern_label=None,
            dominant_pattern_percentage=0.0,
            percentage_denominator="total_records_scanned",
            counts={cat.value: 0 for cat in ValuePatternCategory},
            percentages={cat.value: 0.0 for cat in ValuePatternCategory},
            success=False,
            error_message=f"Database query execution failed: {q_err}",
        )

    # 4. Compute Structured Summary
    return _compute_profile_summary(
        counts=counts,
        total_records=total_records,
        database=database,
        table_name=table_name,
        column_name=column_name,
        column_declared_type=declared_type,
        is_exact=True,
        batch_size=batch_size,
        dialect=dialect_name,
    )

