"""
Intelligent Numeric Column Detection, Validation, and Conversion Module.
DataClean Studio — Zero-Production-Risk Staging Pipeline

Automatically scans MySQL text-based columns (CHAR, VARCHAR, TEXT, etc.)
for numeric representations (integers, decimals, scientific notation, formatted amounts),
evaluates precision, ranges, leading zeros, and identifiers, and safely executes
type conversions on isolated cleaning workspace tables ({table}__cleaning_{uuid}).
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation
from enum import Enum
import logging
import math
import re
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy import inspect, text

from src.staging import (
    CLEANING_SUFFIX,
    TEXT_DATA_TYPES,
    _make_safe_table_name,
    _normalize_data_type,
    _quote_identifier,
    _quote_table,
)

logger = logging.getLogger(__name__)

# Supported MySQL Target Numeric Types
SUPPORTED_NUMERIC_TYPES: List[str] = [
    "INT",
    "BIGINT",
    "DECIMAL",
    "DOUBLE",
    "FLOAT",
]

# Supported number formatting conventions
NUMBER_FORMATS: Dict[str, str] = {
    "standard": "Standard US/UK (1,500.75 — comma thousands, dot decimal)",
    "european": "European (1.500,75 — dot thousands, comma decimal)",
    "space_dot": "Space Thousands, Dot Decimal (1 500.75)",
    "space_comma": "Space Thousands, Comma Decimal (1 500,75)",
    "plain": "Plain / No Thousands Separators (1500.75)",
}

# Column name keywords that suggest the column is an identifier, phone number, or code
IDENTIFIER_KEYWORDS: Set[str] = {
    "phone",
    "mobile",
    "telephone",
    "tel",
    "fax",
    "cell",
    "zip",
    "postal",
    "pincode",
    "pin",
    "code",
    "id",
    "ssn",
    "account",
    "acc_no",
    "account_number",
    "serial",
    "barcode",
    "isbn",
    "sku",
    "reference",
    "ref",
    "card",
    "card_number",
    "pan",
    "aadhaar",
}

# Currency symbols to detect
CURRENCY_SYMBOLS: Set[str] = {"$", "€", "£", "¥", "₹", "₩", "₽", "฿", "₫", "CHF"}

# Numeric regex patterns
INT_PATTERN = re.compile(r"^[+-]?\d+$")
DECIMAL_PATTERN = re.compile(r"^[+-]?\d+\.\d+$")
SCIENTIFIC_PATTERN = re.compile(r"^[+-]?\d+(\.\d+)?[eE][+-]?\d+$")
LEADING_ZERO_PATTERN = re.compile(r"^0\d+$")
PHONE_PATTERN = re.compile(r"^\+?[\d\s\-\(\)\.]{9,20}$")


class NumericDetectionClassification(str, Enum):
    """Classification states for candidate text columns evaluated for numeric data."""
    INTEGER_CANDIDATE = "Integer Candidate"
    DECIMAL_CANDIDATE = "Decimal Candidate"
    MIXED_DATA = "Mixed Numeric & Text (Review Required)"
    ORDINARY_TEXT = "Ordinary Text"
    POTENTIAL_IDENTIFIER = "Potential Identifier (Protect as Text)"
    EMPTY_DATA = "Empty / Insufficient Data"


@dataclass
class NumericNormalizationConfig:
    """Configuration options for numeric normalization and parsing."""
    trim_whitespace: bool = True
    number_format: str = "standard"  # 'standard' (US/UK), 'european', 'space_dot', 'space_comma', 'plain'
    normalize_plus_sign: bool = True
    strip_negative_sign: bool = False
    allow_scientific: bool = False
    strip_currency: bool = False
    strip_percentage: bool = False
    allow_leading_zeros: bool = False  # If True, removes leading zeros; if False, flags as identifier
    invalid_resolution: str = "block"  # 'block', 'set_null', 'keep_text'
    detection_threshold: float = 85.0  # Configurable threshold percentage (50%-100%)
    sample_proportion: float = 0.55  # Initial sampling proportion (50%-60% of table rows)
    max_sample_size: int = 50000  # Reasonable performance cap for large tables


@dataclass
class NumericColumnAnalysis:
    """Detailed numeric profile and type recommendation for a column."""
    column: str
    current_type: str
    total_rows: int
    non_null_rows: int
    valid_count: int
    integer_count: int
    decimal_count: int
    normalized_count: int
    invalid_count: int
    ambiguous_count: int
    potential_identifier_count: int
    null_count: int
    empty_count: int
    min_value: Optional[str]
    max_value: Optional[str]
    max_scale: int
    max_integer_digits: int
    numeric_percentage: float
    classification: str
    recommended_type: str
    suggested_action: str
    sample_preview: List[Dict[str, Any]]


@dataclass
class ValueValidationResult:
    """Validation result for a single value."""
    status: str
    original_value: Any
    normalized_value: Optional[str]
    numeric_value: Optional[Decimal]
    is_valid: bool
    error_reason: str
    is_integer: bool = False
    integer_digits: int = 0
    scale: int = 0


def check_numeric_candidate_pattern(raw_val: Any) -> Tuple[bool, bool, int, int, bool, bool]:
    """
    Evaluates whether raw_val matches a potential numeric pattern during candidate detection,
    decoupled from active normalization settings.

    Returns:
        (is_numeric, is_decimal, int_digits, scale, is_potential_identifier, is_empty)
    """
    if raw_val is None:
        return False, False, 0, 0, False, True

    if isinstance(raw_val, (int, float, Decimal)):
        s_val = str(raw_val)
        is_dec = isinstance(raw_val, (float, Decimal)) or "." in s_val
        parts = s_val.split(".")
        int_d = max(1, len(parts[0].lstrip("+-")))
        sc = len(parts[1]) if len(parts) > 1 else 0
        return True, is_dec, int_d, sc, False, False

    s = str(raw_val).strip()
    if not s:
        return False, False, 0, 0, False, True

    # 1. Identifier check: whole number with leading zero(s) (e.g. '00123', '0456')
    clean_id = s.lstrip("+-").replace(" ", "").replace(",", "").replace(".", "")
    if clean_id.isdigit() and len(clean_id) > 1 and clean_id.startswith("0"):
        if not re.search(r"0[\.,]\d+", s):
            return False, False, len(clean_id), 0, True, False

    # 2. Accounting parentheses
    work = s
    if work.startswith("(") and work.endswith(")"):
        work = work[1:-1].strip()

    # 3. Currency symbols
    for sym in CURRENCY_SYMBOLS:
        work = work.replace(sym, "")
    work = work.strip()

    # 4. Percentage symbols
    has_pct = False
    if work.endswith("%"):
        has_pct = True
        work = work[:-1].strip()
    elif work.startswith("%"):
        has_pct = True
        work = work[1:].strip()

    # 5. Scientific notation check before stripping sign
    sci_match = re.match(r"^[+-]?\d+(?:[\.,]\d+)?[eE][+-]?\d+$", work)
    if sci_match:
        is_dec = ("." in work or "," in work or has_pct)
        return True, is_dec, 5, 2, False, False

    # 6. Leading sign
    if work.startswith("+") or work.startswith("-"):
        work = work[1:].strip()

    # 7. Reject if contains any letters (e.g. 12A50, unknown, Order 125 completed)
    if re.search(r"[a-zA-Z]", work):
        return False, False, 0, 0, False, False

    # 8. Check if remaining string consists only of digits and valid separators (., space)
    if not re.match(r"^[\d\s\.,]+$", work):
        return False, False, 0, 0, False, False

    # Must contain at least one digit
    if not re.search(r"\d", work):
        return False, False, 0, 0, False, False

    work_nospace = work.replace(" ", "")
    has_dot = "." in work_nospace
    has_comma = "," in work_nospace

    if has_dot and has_comma:
        last_dot = work_nospace.rfind(".")
        last_comma = work_nospace.rfind(",")
        if last_dot > last_comma:
            dec_part = work_nospace[last_dot + 1:]
            int_part = work_nospace[:last_dot]
            if "." in int_part or not dec_part.isdigit():
                return False, False, 0, 0, False, False
            clean_int = int_part.replace(",", "")
            if not clean_int.isdigit() and clean_int != "":
                return False, False, 0, 0, False, False
            return True, True, max(1, len(clean_int)), len(dec_part), False, False
        else:
            dec_part = work_nospace[last_comma + 1:]
            int_part = work_nospace[:last_comma]
            if "," in int_part or not dec_part.isdigit():
                return False, False, 0, 0, False, False
            clean_int = int_part.replace(".", "")
            if not clean_int.isdigit() and clean_int != "":
                return False, False, 0, 0, False, False
            return True, True, max(1, len(clean_int)), len(dec_part), False, False
    elif has_dot:
        dot_parts = work_nospace.split(".")
        if len(dot_parts) == 2:
            int_part, dec_part = dot_parts
            if not dec_part:
                clean_int = int_part.replace(",", "")
                return True, False, max(1, len(clean_int)), 0, False, False
            if not dec_part.isdigit() or (int_part and not int_part.isdigit()):
                return False, False, 0, 0, False, False
            is_dec = True if (len(dec_part) != 3 or has_pct) else True
            return True, is_dec, max(1, len(int_part)), len(dec_part), False, False
        elif len(dot_parts) > 2:
            if all(len(p) == 3 for p in dot_parts[1:]) and dot_parts[0].isdigit():
                int_part = "".join(dot_parts)
                return True, False, len(int_part), 0, False, False
            else:
                return False, False, 0, 0, False, False
    elif has_comma:
        comma_parts = work_nospace.split(",")
        if len(comma_parts) == 2:
            int_part, dec_part = comma_parts
            if not dec_part:
                clean_int = int_part.replace(".", "")
                return True, False, max(1, len(clean_int)), 0, False, False
            if not dec_part.isdigit() or (int_part and not int_part.isdigit()):
                return False, False, 0, 0, False, False
            is_dec = True if (len(dec_part) != 3 or has_pct) else False
            return True, is_dec, max(1, len(int_part)), (len(dec_part) if is_dec else 0), False, False
        elif len(comma_parts) > 2:
            if all(len(p) == 3 for p in comma_parts[1:]) and comma_parts[0].isdigit():
                int_part = "".join(comma_parts)
                return True, False, len(int_part), 0, False, False
            else:
                return False, False, 0, 0, False, False
    else:
        int_digits = len(work_nospace)
        return True, has_pct, int_digits, (2 if has_pct else 0), False, False


def normalize_and_validate_value(
    raw_val: Any,
    config: Optional[NumericNormalizationConfig] = None,
    column_name: str = "",
) -> ValueValidationResult:
    """
    Normalizes and validates a single value against numeric parsing rules.

    Status Categories:
      - VALID_INTEGER: Whole number within supported integer ranges.
      - VALID_DECIMAL: Decimal number with fractional component.
      - VALID_NORMALIZED: Valid number that required trimming, symbol stripping, or format normalization.
      - POTENTIAL_IDENTIFIER: Leading zeros (e.g. '00125') or phone numbers where text preservation is safer.
      - AMBIGUOUS_FORMAT: Ambiguous separator structure without configured format.
      - OUT_OF_RANGE: Exceeds supported range.
      - NULL_VALUE: SQL NULL.
      - EMPTY_STRING: Empty string or whitespace-only.
      - INVALID: Non-numeric characters or unparseable structure.
    """
    if config is None:
        config = NumericNormalizationConfig()

    if raw_val is None:
        return ValueValidationResult(
            status="NULL_VALUE",
            original_value=raw_val,
            normalized_value=None,
            numeric_value=None,
            is_valid=True,
            error_reason="",
        )

    s = str(raw_val)
    original = s

    # 1. Whitespace handling
    if config.trim_whitespace:
        s = s.strip()
    if s == "":
        return ValueValidationResult(
            status="EMPTY_STRING",
            original_value=original,
            normalized_value=None,
            numeric_value=None,
            is_valid=False,
            error_reason="Empty or whitespace-only value",
        )

    required_normalization = (s != original)

    # 2. Check for Currency Symbols
    has_curr = any(sym in s for sym in CURRENCY_SYMBOLS)
    if has_curr:
        if config.strip_currency:
            for sym in CURRENCY_SYMBOLS:
                s = s.replace(sym, "")
            s = s.strip()
            required_normalization = True
        else:
            return ValueValidationResult(
                status="INVALID",
                original_value=original,
                normalized_value=s,
                numeric_value=None,
                is_valid=False,
                error_reason="Contains currency symbol (enable 'Strip Currency Symbols' to clean)",
            )

    # 3. Check for Percentage Signs
    if "%" in s:
        if config.strip_percentage:
            s = s.replace("%", "").strip()
            required_normalization = True
        else:
            return ValueValidationResult(
                status="INVALID",
                original_value=original,
                normalized_value=s,
                numeric_value=None,
                is_valid=False,
                error_reason="Contains percentage symbol '%' (enable 'Strip Percentage' to clean)",
            )

    # 4. Normalize Leading Plus Sign
    if config.normalize_plus_sign and s.startswith("+"):
        s = s[1:].strip()
        required_normalization = True

    # 4b. Strip / Normalize Negative Sign (Convert to Positive / Absolute Value)
    if config.strip_negative_sign:
        if s.startswith("-"):
            s = s[1:].strip()
            required_normalization = True
        elif s.startswith("(") and s.endswith(")"):
            s = s[1:-1].strip()
            required_normalization = True
        elif s.endswith("-"):
            s = s[:-1].strip()
            required_normalization = True

    # 5. Check for Leading Zeros in Whole Numbers (Potential Identifier)
    clean_digits_check = s.replace(" ", "").replace(",", "").replace(".", "")
    if clean_digits_check.isdigit() and len(clean_digits_check) > 1 and clean_digits_check.startswith("0"):
        # Check if it has a decimal point like '0.5'
        has_dot_dec = "." in s or (config.number_format in ("european", "space_comma") and "," in s)
        if not has_dot_dec:
            if not config.allow_leading_zeros:
                return ValueValidationResult(
                    status="POTENTIAL_IDENTIFIER",
                    original_value=original,
                    normalized_value=s,
                    numeric_value=None,
                    is_valid=False,
                    error_reason=f"Leading zero detected ('{original}'). Converting to numeric will strip leading zero to '{int(clean_digits_check)}'. Enable 'Allow Stripping Leading Zeros' to override.",
                )
            else:
                s = str(int(clean_digits_check))
                required_normalization = True

    # 6. Check Phone Number heuristics if column name suggests phone/mobile
    col_lower = column_name.lower()
    if any(k in col_lower for k in ("phone", "mobile", "tel", "cell", "fax")):
        if clean_digits_check.isdigit() and len(clean_digits_check) >= 9:
            return ValueValidationResult(
                status="POTENTIAL_IDENTIFIER",
                original_value=original,
                normalized_value=s,
                numeric_value=None,
                is_valid=False,
                error_reason="Phone number pattern detected in identifier column. Preserving as text is recommended.",
            )

    # 7. Separator and Format Normalization
    fmt = config.number_format
    if fmt == "standard":
        # Standard US/UK: comma thousands, dot decimal (e.g. 1,500.75 or 25,000)
        if "," in s:
            # Verify proper comma placement or strip commas
            parts = s.split(".")
            if len(parts) <= 2:
                int_part = parts[0].replace(",", "")
                dec_part = ("." + parts[1]) if len(parts) == 2 else ""
                s = int_part + dec_part
                required_normalization = True
            else:
                return ValueValidationResult(
                    status="INVALID",
                    original_value=original,
                    normalized_value=s,
                    numeric_value=None,
                    is_valid=False,
                    error_reason="Multiple decimal points found",
                )
    elif fmt == "european":
        # European: dot thousands, comma decimal (e.g. 1.500,75 or 25.000)
        if "." in s and "," in s:
            # 1.500,75 -> 1500.75
            s = s.replace(".", "").replace(",", ".")
            required_normalization = True
        elif "," in s and "." not in s:
            # 35,50 -> 35.50
            s = s.replace(",", ".")
            required_normalization = True
        elif "." in s and "," not in s:
            # e.g. 1.500 or 15.000 -> check if dot is thousands or decimal
            # If 3 digits after dot, could be thousands
            dot_parts = s.split(".")
            if len(dot_parts) == 2 and len(dot_parts[1]) == 3 and dot_parts[0].isdigit():
                s = s.replace(".", "")
                required_normalization = True
            elif len(dot_parts) > 2:
                s = s.replace(".", "")
                required_normalization = True
    elif fmt == "space_dot":
        # 1 500.75
        if " " in s:
            s = s.replace(" ", "")
            required_normalization = True
    elif fmt == "space_comma":
        # 1 500,75 -> 1500.75
        if " " in s:
            s = s.replace(" ", "")
        if "," in s:
            s = s.replace(",", ".")
        required_normalization = True
    elif fmt == "plain":
        # No thousands separators expected
        if "," in s:
            return ValueValidationResult(
                status="AMBIGUOUS_FORMAT",
                original_value=original,
                normalized_value=s,
                numeric_value=None,
                is_valid=False,
                error_reason="Ambiguous comma separator ',' detected without selecting Standard (US/UK) or European format.",
            )

    # 8. Scientific Notation Check
    if SCIENTIFIC_PATTERN.match(s):
        if not config.allow_scientific:
            return ValueValidationResult(
                status="INVALID",
                original_value=original,
                normalized_value=s,
                numeric_value=None,
                is_valid=False,
                error_reason="Scientific notation detected. Enable 'Support Scientific Notation' to parse.",
            )
        try:
            val_float = float(s)
            val_dec = Decimal(str(val_float))
            return ValueValidationResult(
                status="VALID_NORMALIZED" if required_normalization else "VALID_DECIMAL",
                original_value=original,
                normalized_value=str(val_float),
                numeric_value=val_dec,
                is_valid=True,
                error_reason="",
                is_integer=False,
                integer_digits=len(str(int(abs(val_float)))),
                scale=4,
            )
        except Exception as e:
            return ValueValidationResult(
                status="INVALID",
                original_value=original,
                normalized_value=s,
                numeric_value=None,
                is_valid=False,
                error_reason=f"Failed to parse scientific notation: {str(e)}",
            )

    # 9. Decimal & Integer Parsing via Python Decimal
    try:
        dec_val = Decimal(s)
    except InvalidOperation:
        # Check why it failed for detailed diagnostics
        if re.search(r"[a-zA-Z]", s):
            reason = f"Contains alphabetic characters: '{s}'"
        elif s.count(".") > 1:
            reason = "Contains multiple decimal points"
        elif s.count("-") > 1 or (s.count("-") == 1 and not s.startswith("-")):
            reason = "Malformed negative sign position"
        else:
            reason = "Cannot be parsed as a valid numeric representation"

        return ValueValidationResult(
            status="INVALID",
            original_value=original,
            normalized_value=s,
            numeric_value=None,
            is_valid=False,
            error_reason=reason,
        )

    # 10. Precision and Scale Calculation
    dec_tuple = dec_val.as_tuple()
    exp = dec_tuple.exponent
    if isinstance(exp, int) and exp < 0:
        scale = abs(exp)
        # Check if fractional digits are all zeros (e.g. 25000.00)
        digits_str = "".join(str(d) for d in dec_tuple.digits)
        int_digits = len(digits_str) - scale
        if int_digits < 0:
            int_digits = 1
        is_int = (dec_val == dec_val.to_integral())
    else:
        scale = 0
        int_digits = len(dec_tuple.digits)
        is_int = True

    status = "VALID_NORMALIZED" if required_normalization else ("VALID_INTEGER" if is_int else "VALID_DECIMAL")

    return ValueValidationResult(
        status=status,
        original_value=original,
        normalized_value=s,
        numeric_value=dec_val,
        is_valid=True,
        error_reason="",
        is_integer=is_int,
        integer_digits=int_digits,
        scale=scale,
    )


def get_eligible_text_columns(engine, database: str, working_table_name: str) -> List[Dict[str, Any]]:
    """
    Returns all eligible text columns from the workspace table with their current data types.
    """
    eligible = []
    try:
        column_query = text("""
            SELECT COLUMN_NAME, DATA_TYPE, COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
            ORDER BY ORDINAL_POSITION
        """)
        with engine.connect() as conn:
            result = conn.execute(
                column_query,
                {"database": database, "table_name": working_table_name},
            )
            for row in result:
                row_map = dict(row._mapping)
                col_name = row_map["COLUMN_NAME"]
                dtype = str(row_map["DATA_TYPE"]).lower()
                ctype = str(row_map.get("COLUMN_TYPE") or dtype).upper()
                norm_dtype = _normalize_data_type(dtype)
                if norm_dtype in TEXT_DATA_TYPES and not col_name.startswith("__"):
                    eligible.append({
                        "name": col_name,
                        "data_type": norm_dtype,
                        "column_type": ctype,
                    })
    except Exception:
        # SQLite / Mock fallback
        try:
            insp = inspect(engine)
            cols = insp.get_columns(working_table_name, schema=database if database else None)
            for c in cols:
                raw_type = str(c["type"]).lower()
                base_type = raw_type.split("(")[0].strip()
                norm = _normalize_data_type(base_type)
                if norm in TEXT_DATA_TYPES and not c["name"].startswith("__"):
                    eligible.append({
                        "name": c["name"],
                        "data_type": norm,
                        "column_type": str(c["type"]).upper(),
                    })
        except Exception as e:
            logger.error("Error inspecting columns in %s: %s", working_table_name, str(e))

    return eligible


def analyze_numeric_column(
    engine,
    database: str,
    table_name: str,
    column_name: str,
    config: Optional[NumericNormalizationConfig] = None,
    sample_limit: int = 5000,
) -> Dict[str, Any]:
    """
    Performs comprehensive numeric compatibility profiling on a single text column.
    Never modifies the database.
    """
    if config is None:
        config = NumericNormalizationConfig()

    if isinstance(column_name, dict):
        column_name = column_name.get("name", "")
    if not isinstance(column_name, str) or not column_name.strip():
        raise ValueError("column_name must be a non-empty string.")
    column_name = column_name.strip()

    quoted_table = _quote_table(database, table_name) if database else _quote_identifier(table_name)
    quoted_column = _quote_identifier(column_name)

    # Introspect actual current type
    cur_type = "TEXT"
    try:
        column_type_query = text("""
            SELECT COLUMN_TYPE
            FROM INFORMATION_SCHEMA.COLUMNS
            WHERE TABLE_SCHEMA = :database
              AND TABLE_NAME = :table_name
              AND COLUMN_NAME = :column_name
        """)
        with engine.connect() as conn:
            r = conn.execute(
                column_type_query,
                {"database": database, "table_name": table_name, "column_name": column_name},
            ).fetchone()
            if r and r[0]:
                cur_type = str(r[0]).upper()
    except Exception:
        try:
            insp = inspect(engine)
            cols = insp.get_columns(table_name, schema=database if database else None)
            for c in cols:
                if c["name"] == column_name:
                    cur_type = str(c["type"]).upper()
                    break
        except Exception:
            pass

    # 1. Total row and NULL counts
    total_rows = 0
    null_count = 0
    with engine.connect() as conn:
        try:
            cnt_res = conn.execute(
                text(f"""
                    SELECT 
                        COUNT(*) AS total_rows,
                        SUM(CASE WHEN {quoted_column} IS NULL THEN 1 ELSE 0 END) AS null_cnt
                    FROM {quoted_table}
                """)
            ).fetchone()
            if cnt_res:
                total_rows = cnt_res[0] or 0
                null_count = cnt_res[1] or 0
        except Exception:
            total_rows = 0
            null_count = 0

    # 2. Determine sample limit based on 50%-60% sampling proportion requirement
    effective_limit = sample_limit
    if total_rows > 0:
        if total_rows <= 1000:
            effective_limit = max(1, total_rows)
        else:
            calc_sample = int(total_rows * getattr(config, "sample_proportion", 0.55))
            effective_limit = max(1000, min(getattr(config, "max_sample_size", 50000), calc_sample))

    # Sample non-null values for detailed inspection
    sample_rows_raw = []
    with engine.connect() as conn:
        try:
            sample_query = text(f"""
                SELECT {quoted_column} AS val, COUNT(*) AS cnt
                FROM {quoted_table}
                WHERE {quoted_column} IS NOT NULL
                GROUP BY {quoted_column}
                LIMIT :limit
            """)
            result = conn.execute(sample_query, {"limit": effective_limit})
            for r in result:
                row_map = dict(r._mapping) if hasattr(r, "_mapping") else dict(r)
                sample_rows_raw.append((row_map.get("val"), row_map.get("cnt", 1)))
        except Exception:
            # Fallback without GROUP BY
            try:
                fallback_query = text(f"""
                    SELECT {quoted_column} AS val
                    FROM {quoted_table}
                    WHERE {quoted_column} IS NOT NULL
                    LIMIT :limit
                """)
                result = conn.execute(fallback_query, {"limit": effective_limit})
                for r in result:
                    row_map = dict(r._mapping) if hasattr(r, "_mapping") else dict(r)
                    sample_rows_raw.append((row_map.get("val"), 1))
            except Exception as e:
                logger.error("Error sampling column %s: %s", column_name, str(e))

    # 3. Candidate Pattern Detection & Value-Level Validation
    cand_evaluated_cnt = 0
    cand_numeric_cnt = 0
    cand_int_cnt = 0
    cand_dec_cnt = 0
    cand_id_cnt = 0
    cand_max_int_digits = 1
    cand_max_scale = 0

    valid_int_cnt = 0
    valid_dec_cnt = 0
    valid_norm_cnt = 0
    potential_id_cnt = 0
    invalid_cnt = 0
    ambiguous_cnt = 0
    empty_cnt = 0
    scientific_cnt = 0

    min_val: Optional[Decimal] = None
    max_val: Optional[Decimal] = None
    max_int_digits = 1
    max_scale = 0

    sample_preview: List[Dict[str, Any]] = []
    invalid_samples: List[Dict[str, str]] = []
    ambiguous_samples: List[Dict[str, str]] = []

    for raw_val, occurrence in sample_rows_raw:
        # Candidate pattern recognition (decoupled from active normalization settings)
        p_is_num, p_is_dec, p_int_d, p_scale, p_is_id, p_is_empty = check_numeric_candidate_pattern(raw_val)
        if not p_is_empty:
            cand_evaluated_cnt += occurrence
            if p_is_id:
                cand_id_cnt += occurrence
            elif p_is_num:
                cand_numeric_cnt += occurrence
                if p_is_dec:
                    cand_dec_cnt += occurrence
                else:
                    cand_int_cnt += occurrence
                if p_int_d > cand_max_int_digits:
                    cand_max_int_digits = p_int_d
                if p_scale > cand_max_scale:
                    cand_max_scale = p_scale

        # Value-level validation under current configuration
        res = normalize_and_validate_value(raw_val, config, column_name=column_name)

        if res.status == "NULL_VALUE":
            pass
        elif res.status == "EMPTY_STRING":
            empty_cnt += occurrence
        elif res.status == "POTENTIAL_IDENTIFIER":
            potential_id_cnt += occurrence
            if len(invalid_samples) < 10:
                invalid_samples.append({"value": str(raw_val), "reason": res.error_reason})
        elif res.status == "AMBIGUOUS_FORMAT":
            ambiguous_cnt += occurrence
            if len(ambiguous_samples) < 10:
                ambiguous_samples.append({"value": str(raw_val), "reason": res.error_reason})
        elif res.status == "INVALID":
            invalid_cnt += occurrence
            if len(invalid_samples) < 10:
                invalid_samples.append({"value": str(raw_val), "reason": res.error_reason})
        elif res.is_valid:
            if res.status == "VALID_NORMALIZED":
                valid_norm_cnt += occurrence
            elif res.is_integer:
                valid_int_cnt += occurrence
            else:
                valid_dec_cnt += occurrence

            if res.numeric_value is not None:
                if min_val is None or res.numeric_value < min_val:
                    min_val = res.numeric_value
                if max_val is None or res.numeric_value > max_val:
                    max_val = res.numeric_value

            if res.integer_digits > max_int_digits:
                max_int_digits = res.integer_digits
            if res.scale > max_scale:
                max_scale = res.scale

        proposed_display = str(res.normalized_value) if (res.is_valid and res.normalized_value is not None) else "SQL NULL"
        status_display = "Valid" if res.is_valid else (
            "NULL" if res.status in ("NULL", "NULL_VALUE")
            else "Empty" if res.status == "EMPTY_STRING"
            else "Ambiguous" if "AMBIGUOUS" in res.status
            else "Identifier" if "IDENTIFIER" in res.status
            else "Invalid"
        )
        reason_display = "-" if res.is_valid else (
            "Source value is SQL NULL" if res.status in ("NULL", "NULL_VALUE")
            else "Empty or whitespace-only value" if res.status == "EMPTY_STRING"
            else (res.error_reason or "Cannot convert safely to numeric")
        )

        if len(sample_preview) < 50:
            sample_preview.append({
                "Original value": str(raw_val) if raw_val is not None else "SQL NULL",
                "Proposed numeric value": proposed_display,
                "Conversion status": status_display,
                "Reason": reason_display,
                "Proposed value": proposed_display,
                "Status": res.status,
                "original": str(raw_val) if raw_val is not None else "SQL NULL",
                "normalized": res.normalized_value or "",
                "status": res.status,
                "is_valid": res.is_valid,
                "error_reason": res.error_reason,
                "occurrences": occurrence,
            })

    if null_count > 0 and len(sample_preview) < 50:
        sample_preview.append({
            "Original value": "SQL NULL",
            "Proposed numeric value": "SQL NULL",
            "Conversion status": "NULL",
            "Reason": "Source value is SQL NULL",
            "Proposed value": "SQL NULL",
            "Status": "NULL",
            "original": "SQL NULL",
            "normalized": "",
            "status": "NULL",
            "is_valid": False,
            "error_reason": "Source value is SQL NULL",
            "occurrences": null_count,
        })

    # 4. Classification & Recommendations
    total_evaluated = sum(cnt for _, cnt in sample_rows_raw)
    total_valid = valid_int_cnt + valid_dec_cnt + valid_norm_cnt

    # Calculate numeric percentage using sampled, non-empty values
    # (excluding SQL NULL and empty or whitespace-only values from the denominator)
    cand_numeric_pct = (cand_numeric_cnt / cand_evaluated_cnt * 100.0) if cand_evaluated_cnt > 0 else 0.0
    numeric_pct = cand_numeric_pct

    warnings: List[str] = []

    # Heuristic: Check if column name or values indicate an identifier
    col_lower = column_name.lower()
    is_name_identifier = any(k in col_lower for k in IDENTIFIER_KEYWORDS)
    detection_thresh = getattr(config, "detection_threshold", 85.0)

    if cand_evaluated_cnt == 0:
        classification = "Empty / Insufficient Data"
        rec_type = "VARCHAR"
        rec_reason = "Column contains only NULL or empty values; insufficient data to infer numeric type."
    elif potential_id_cnt > 0 or cand_id_cnt > 0:
        classification = "Potential Identifier (Protect as Text)"
        rec_type = "VARCHAR"
        rec_reason = f"Contains values with leading zeros (e.g. product/postal codes). Converting to numeric would discard leading zeros."
        warnings.append("Leading zeros detected; converting to numeric will strip leading zero digits.")
    elif any(k in col_lower for k in ("phone", "mobile", "tel", "cell", "fax")) and numeric_pct > 80 and max(max_int_digits, cand_max_int_digits) >= 9:
        classification = "Potential Identifier (Protect as Text)"
        rec_type = "VARCHAR"
        rec_reason = f"Column name and length ({max(max_int_digits, cand_max_int_digits)} digits) match phone number patterns. Retaining as text preserves formatting."
        warnings.append("Phone number pattern detected; retaining as text preserves dialing formats.")
    elif numeric_pct >= detection_thresh:
        is_decimal_candidate = (cand_dec_cnt > 0 or valid_dec_cnt > 0 or max_scale > 0 or cand_max_scale > 0)
        eff_scale = max(max_scale, cand_max_scale)
        eff_int_digits = max(max_int_digits, cand_max_int_digits)

        if is_decimal_candidate:
            classification = "Decimal Candidate"
            calc_scale = max(2, min(eff_scale if eff_scale > 0 else 2, 10))
            calc_prec = min(65, max(eff_int_digits + calc_scale, calc_scale + 2))
            rec_type = f"DECIMAL({calc_prec},{calc_scale})"
            rec_reason = f"Contains decimal amounts with up to {calc_scale} fractional digits. DECIMAL({calc_prec},{calc_scale}) preserves exact precision."
        else:
            classification = "Integer Candidate"
            if min_val is not None and max_val is not None:
                if min_val >= -2147483648 and max_val <= 2147483647:
                    rec_type = "INT"
                    rec_reason = f"All values are whole numbers within signed 32-bit INT range ({min_val} to {max_val})."
                else:
                    rec_type = "BIGINT"
                    rec_reason = f"Whole numbers exceed standard INT limits ({min_val} to {max_val}); BIGINT prevents overflow."
            else:
                rec_type = "INT"
                rec_reason = "Whole numbers detected within standard integer range."

        # Add warnings for anomalies or values needing normalization without demoting candidate classification
        non_num_count = cand_evaluated_cnt - cand_numeric_cnt
        if non_num_count > 0:
            warnings.append(f"Contains {non_num_count} non-numeric record(s). Review invalid rows or configure resolution before converting.")
        if invalid_cnt > 0 or ambiguous_cnt > 0:
            warnings.append(f"{invalid_cnt + ambiguous_cnt} value(s) require format normalization or resolution.")
    elif 15.0 <= numeric_pct < detection_thresh:
        classification = "Mixed Numeric & Text (Review Required)"
        rec_type = "DECIMAL" if (cand_dec_cnt > 0 or max_scale > 0 or cand_max_scale > 0) else "INT"
        rec_reason = f"Only {numeric_pct:.1f}% of values match numeric patterns. Manual review recommended before conversion."
        warnings.append(f"Significant non-numeric values ({100 - numeric_pct:.1f}%). High risk of data loss without resolving text records.")
    else:
        classification = "Ordinary Text"
        rec_type = "VARCHAR"
        rec_reason = f"Column contains predominantly ordinary text ({100 - numeric_pct:.1f}% non-numeric)."

    return {
        "column": column_name,
        "column_name": column_name,
        "current_type": cur_type,
        "total_rows": total_rows,
        "non_null_rows": total_evaluated,
        "null_count": null_count,
        "empty_count": empty_cnt,
        "evaluated_count": total_evaluated,
        "valid_count": total_valid,
        "candidate_numeric_count": cand_numeric_cnt,
        "non_empty_count": cand_evaluated_cnt,
        "integer_count": valid_int_cnt,
        "decimal_count": valid_dec_cnt,
        "normalized_count": valid_norm_cnt,
        "valid_integer_count": valid_int_cnt,
        "valid_decimal_count": valid_dec_cnt,
        "valid_normalized_count": valid_norm_cnt,
        "potential_identifier_count": potential_id_cnt,
        "invalid_count": invalid_cnt,
        "ambiguous_count": ambiguous_cnt,
        "scientific_count": scientific_cnt,
        "min_value": float(min_val) if min_val is not None else None,
        "max_value": float(max_val) if max_val is not None else None,
        "max_integer_digits": max(max_int_digits, cand_max_int_digits),
        "max_scale": max(max_scale, cand_max_scale),
        "numeric_percentage": round(numeric_pct, 1),
        "classification": classification,
        "recommended_type": rec_type,
        "recommendation_reason": rec_reason,
        "suggested_action": f"Convert to {rec_type}" if "Candidate" in classification else ("Resolve invalid records" if "Mixed" in classification else "Retain as text"),
        "sample_preview": sample_preview,
        "invalid_samples": invalid_samples,
        "ambiguous_samples": ambiguous_samples,
        "warnings": warnings,
    }


def scan_table_numeric_candidates(
    engine,
    database: str,
    working_table_name: str,
    config: Optional[NumericNormalizationConfig] = None,
) -> List[Dict[str, Any]]:
    """
    Scans all text columns in the workspace table and returns numeric classification reports.
    Does not modify database data.
    """
    if config is None:
        config = NumericNormalizationConfig()

    eligible_cols = get_eligible_text_columns(engine, database, working_table_name)
    reports = []

    for col in eligible_cols:
        col_name = col["name"]
        analysis = analyze_numeric_column(engine, database, working_table_name, col_name, config)
        analysis["current_type"] = col["column_type"]
        reports.append(analysis)

    # Sort candidates so actionable numeric columns appear first
    order_map = {
        "Integer Candidate": 1,
        "Decimal Candidate": 2,
        "Mixed Numeric & Text (Review Required)": 3,
        "Potential Identifier (Protect as Text)": 4,
        "Ordinary Text": 5,
        "Empty / Insufficient Data": 6,
    }
    reports.sort(key=lambda r: order_map.get(r["classification"], 99))
    return reports


def convert_column_to_numeric_workspace(
    engine,
    database: str,
    working_table_name: str,
    column_name: str,
    target_type: str,
    config: Optional[NumericNormalizationConfig] = None,
    conversion_mode: str = "in_place",
    new_column_name: Optional[str] = None,
) -> Tuple[bool, str, Dict[str, Any]]:
    """
    Safely executes numeric data type conversion on the isolated workspace table.
    Production source tables are strictly protected.

    Args:
        engine: SQLAlchemy Engine
        database: Database name
        working_table_name: Authorized workspace table name ({table}__cleaning_{uuid})
        column_name: Column to convert
        target_type: Target SQL type (e.g. 'INT', 'BIGINT', 'DECIMAL(10,2)', 'DOUBLE')
        config: Normalization configuration
        conversion_mode: 'in_place' (ALTER TABLE MODIFY) or 'new_column' (ALTER TABLE ADD)
        new_column_name: Target column name if conversion_mode == 'new_column'

    Returns:
        (success, message, report)
    """
    if config is None:
        config = NumericNormalizationConfig()

    if isinstance(column_name, dict):
        column_name = column_name.get("name", "")
    if not isinstance(column_name, str) or not column_name.strip():
        return (False, "Column name must be a non-empty string.", {})
    column_name = column_name.strip()

    try:
        # 1. Safety verification
        if not working_table_name or working_table_name.count(CLEANING_SUFFIX) != 1:
            return (
                False,
                "Refusing to convert a table that is not identified as an authorized cleaning workspace.",
                {},
            )

        safe_name = _make_safe_table_name(working_table_name)
        if safe_name != working_table_name:
            return (
                False,
                "Refusing to convert an invalid table identifier.",
                {},
            )

        inspector = inspect(engine)
        tables = inspector.get_table_names(schema=database if database else None)
        if working_table_name not in tables:
            return (
                False,
                f"Working table '{working_table_name}' not found in database '{database}'.",
                {},
            )

        # 2. Target type allowlist validation
        clean_target = target_type.strip().upper()
        type_prefix = clean_target.split("(")[0].strip()
        if type_prefix not in SUPPORTED_NUMERIC_TYPES:
            return (
                False,
                f"Unsupported numeric target type '{clean_target}'. Must be one of: {', '.join(SUPPORTED_NUMERIC_TYPES)}.",
                {},
            )

        # 3. Analyze column to verify conversion safety and invalid count
        analysis = analyze_numeric_column(engine, database, working_table_name, column_name, config)
        invalid_count = analysis["invalid_count"] + analysis["ambiguous_count"] + analysis["potential_identifier_count"]

        # Only block in-place conversion if unresolved anomalies exist and config.invalid_resolution is 'block'
        if conversion_mode == "in_place" and invalid_count > 0 and config.invalid_resolution == "block":
            return (
                False,
                f"Conversion blocked: {invalid_count} invalid, ambiguous, or identifier value(s) found in '{column_name}'. "
                f"In-place conversion is disabled when unresolved anomalies exist. "
                f"Please select 'Create New Column' to safely convert valid records while leaving invalid values blank (SQL NULL), "
                f"or change 'Action on Invalid Values' to 'Set invalid values to NULL' to proceed in-place.",
                {},
            )

        quoted_table = _quote_table(database, working_table_name) if database else _quote_identifier(working_table_name)
        quoted_col = _quote_identifier(column_name)

        # Determine target column
        existing_cols = [c["name"] for c in inspector.get_columns(working_table_name, schema=database if database else None)]
        if conversion_mode == "new_column":
            target_col = new_column_name.strip() if (new_column_name and new_column_name.strip()) else f"{column_name}_numeric"
            if target_col in existing_cols:
                return (
                    False,
                    f"Target column '{target_col}' already exists in workspace table. Please specify a different column name.",
                    {},
                )
            quoted_target_col = _quote_identifier(target_col)
        else:
            target_col = column_name
            quoted_target_col = quoted_col

        rows_converted = 0
        invalid_nullified = 0

        # 4. Atomic Execution inside Engine Transaction
        with engine.begin() as conn:
            is_sqlite = (conn.dialect.name == "sqlite")

            # Fetch distinct non-null values
            fetch_query = text(f"SELECT {quoted_col} AS raw_val FROM {quoted_table} WHERE {quoted_col} IS NOT NULL GROUP BY {quoted_col}")
            try:
                distinct_vals = conn.execute(fetch_query).fetchall()
            except Exception:
                distinct_vals = conn.execute(text(f"SELECT {quoted_col} AS raw_val FROM {quoted_table} WHERE {quoted_col} IS NOT NULL")).fetchall()

            if conversion_mode == "new_column":
                # Add new column first
                if is_sqlite:
                    conn.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_target_col} {clean_target}"))
                else:
                    conn.execute(text(f"ALTER TABLE {quoted_table} ADD COLUMN {quoted_target_col} {clean_target} NULL"))

                # Populate new column with normalized values
                for row in distinct_vals:
                    r_val = row[0]
                    res = normalize_and_validate_value(r_val, config, column_name=column_name)
                    if res.is_valid and res.normalized_value is not None:
                        conn.execute(
                            text(f"UPDATE {quoted_table} SET {quoted_target_col} = :norm WHERE {quoted_col} = :orig"),
                            {"norm": res.normalized_value, "orig": r_val},
                        )
                    else:
                        # In new_column mode, invalid/ambiguous/unresolved/empty values become SQL NULL
                        conn.execute(
                            text(f"UPDATE {quoted_table} SET {quoted_target_col} = NULL WHERE {quoted_col} = :orig"),
                            {"orig": r_val},
                        )
            else:
                # In-Place conversion: normalize values first
                for row in distinct_vals:
                    r_val = row[0]
                    res = normalize_and_validate_value(r_val, config, column_name=column_name)
                    if res.is_valid and res.normalized_value is not None:
                        conn.execute(
                            text(f"UPDATE {quoted_table} SET {quoted_col} = :norm WHERE {quoted_col} = :orig"),
                            {"norm": res.normalized_value, "orig": r_val},
                        )
                        rows_converted += 1
                    elif not res.is_valid:
                        if config.invalid_resolution == "set_null":
                            conn.execute(
                                text(f"UPDATE {quoted_table} SET {quoted_col} = NULL WHERE {quoted_col} = :orig"),
                                {"orig": r_val},
                            )
                            invalid_nullified += 1

                # Apply schema alteration
                if not is_sqlite:
                    alter_sql = text(f"ALTER TABLE {quoted_table} MODIFY COLUMN {quoted_col} {clean_target} NULL")
                    conn.execute(alter_sql)

        # 5. Post-Conversion Verification
        final_rows = 0
        final_type = clean_target
        rows_converted = 0
        invalid_nullified = 0

        with engine.connect() as conn:
            final_rows = conn.execute(text(f"SELECT COUNT(*) FROM {quoted_table}")).scalar() or 0
            if conversion_mode == "new_column":
                rows_converted = conn.execute(
                    text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_target_col} IS NOT NULL")
                ).scalar() or 0
                invalid_nullified = conn.execute(
                    text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_target_col} IS NULL AND {quoted_col} IS NOT NULL AND TRIM({quoted_col}) != ''")
                ).scalar() or 0
            else:
                rows_converted = conn.execute(
                    text(f"SELECT COUNT(*) FROM {quoted_table} WHERE {quoted_col} IS NOT NULL")
                ).scalar() or 0
                if config.invalid_resolution == "set_null":
                    invalid_nullified = analysis.get("invalid_count", 0) + analysis.get("ambiguous_count", 0) + analysis.get("potential_identifier_count", 0)

            if not is_sqlite:
                verify_q = text("""
                    SELECT DATA_TYPE, COLUMN_TYPE
                    FROM INFORMATION_SCHEMA.COLUMNS
                    WHERE TABLE_SCHEMA = :database
                      AND TABLE_NAME = :table_name
                      AND COLUMN_NAME = :col_name
                """)
                res_meta = conn.execute(
                    verify_q,
                    {"database": database, "table_name": working_table_name, "col_name": target_col},
                ).fetchone()
                if res_meta:
                    final_type = str(res_meta[1] or res_meta[0]).upper()

        report = {
            "operation": "Numeric Data Conversion",
            "column_name": column_name,
            "target_column": target_col,
            "original_type": analysis.get("current_type", "TEXT"),
            "target_type": clean_target,
            "verified_type": final_type,
            "conversion_mode": conversion_mode,
            "total_rows": final_rows,
            "rows_converted": rows_converted,
            "invalid_nullified": invalid_nullified,
            "config": asdict(config),
            "status": "SUCCESS",
        }

        if conversion_mode == "new_column":
            msg = (
                f"Successfully created numeric column '{target_col}' ({clean_target}) in workspace table '{working_table_name}'. "
                f"{rows_converted} record(s) converted successfully"
                + (f", {invalid_nullified} invalid/ambiguous value(s) left blank (SQL NULL)" if invalid_nullified > 0 else "")
                + f". Original column '{column_name}' preserved unchanged."
            )
        else:
            msg = (
                f"Successfully converted column '{column_name}' to {clean_target} in workspace table '{working_table_name}'."
                + (f" ({invalid_nullified} non-numeric record(s) set to NULL)." if invalid_nullified > 0 else "")
            )
        return (True, msg, report)

    except Exception as e:
        logger.error(
            "Error converting column '%s' in table '%s' to numeric: %s",
            column_name,
            working_table_name,
            str(e),
        )
        return (
            False,
            f"Error during numeric conversion: {str(e)}",
            {},
        )
