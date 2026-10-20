"""
DataClean Studio — AI-Powered Data Profiling Engine
src/ai_profiling.py

Phase 2: Comprehensive column-level profiling and generic pattern detection
for unfamiliar database tables. Produces verifiable observable evidence,
extracts pattern frequencies and suspicious values, and formats compact summaries
for LLM consumption without leaking raw datasets or personal data.

Key Capabilities:
- Full integration with existing DataClean Studio profiling detectors
- Generic pattern detection for unfamiliar columns (currency, mixed alphanumeric,
  date formats, boolean variations, special/control characters, casing distributions)
- Observable facts with exact counts — zero hallucination or invented metrics
- Privacy-aware value anonymization for representative samples
- Token-efficient compact summary generation for AI reasoning
- Strict read-only database operations with parameterization and identifier escaping
"""

from __future__ import annotations

import re
import math
import logging
from typing import Any, Dict, List, Optional, Tuple, Set
import pandas as pd
from sqlalchemy import text

from src.profiling import _get_columns, _quote_identifier, _quote_table, profile_table
from src.staging import evaluate_boolean_series

logger = logging.getLogger(__name__)

# Common world currency symbols for generic detection
CURRENCY_SYMBOLS: Set[str] = {"$", "€", "£", "¥", "₹", "₩", "₣", "₱", "₿", "元", "Rs", "R$"}

# Common missing value representation strings in raw data
COMMON_NA_STRINGS: Set[str] = {
    "n/a", "na", "null", "none", "nil", "unknown", "undefined",
    "missing", "-", "--", "?", "???", "nan", "#n/a", "blank"
}


def anonymize_sample_value(val: Any, max_len: int = 40) -> str:
    """
    Safely sanitizes and anonymizes representative suspicious values before
    including them in profiling summaries or LLM prompts.
    Masks emails, phone numbers, and long credit-card-like number strings.
    """
    if val is None:
        return "NULL"
    s = str(val).strip()
    if not s:
        return '""'

    # Mask email addresses: j***@***.com
    if "@" in s and "." in s:
        s = re.sub(r'([a-zA-Z0-9_.+-])[a-zA-Z0-9_.+-]*@([a-zA-Z0-9-]+)\.[a-zA-Z0-9-.]+', r'\1***@\2.***', s)

    # Mask credit card / SSN-like digit sequences
    s = re.sub(r'\b\d{4}[ -]?\d{4}[ -]?\d{4}[ -]?\d{4}\b', '****-****-****-****', s)
    s = re.sub(r'\b\d{3}[ -]?\d{2}[ -]?\d{4}\b', '***-**-****', s)

    # Mask phone numbers
    s = re.sub(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', '***-***-****', s)

    # Truncate overly long values
    if len(s) > max_len:
        s = s[:max_len - 3] + "..."

    # Strip newlines and carriage returns for clean single-line display
    s = s.replace("\r", " ").replace("\n", " ")
    return s


def analyze_column_generic_patterns(
    series: pd.Series,
    physical_type: str,
    total_table_rows: int,
) -> Dict[str, Any]:
    """
    Performs generic, domain-agnostic pattern discovery on a column series.
    Detects observable facts across:
    - Null & empty string counts
    - Whitespace issues
    - Text casing distribution
    - Numeric & currency patterns in text
    - Date & time patterns
    - Special & control characters
    - Representative suspicious values
    """
    clean_series = series.dropna()
    null_count = int(series.isna().sum())
    null_pct = round((null_count / total_table_rows) * 100, 2) if total_table_rows > 0 else 0.0

    # Base profile dict
    col_data: Dict[str, Any] = {
        "physical_type": physical_type,
        "null_count": null_count,
        "null_pct": null_pct,
        "empty_count": 0,
        "empty_pct": 0.0,
        "unique_count": 0,
        "whitespace_issues": 0,
        "casing_breakdown": {},
        "numeric_patterns": {},
        "date_patterns": {},
        "boolean_patterns": {},
        "special_char_issues": {},
        "suspicious_samples": [],
        "min_val": None,
        "max_val": None,
        "avg_val": None,
        "logical_type": physical_type.upper(),
        "recommended_tool": None,
        "recommended_tool_id": None,
        "anomaly_count": 0,
    }

    if len(clean_series) == 0:
        return col_data

    col_data["unique_count"] = int(clean_series.nunique())

    # 1. Numeric physical columns
    if pd.api.types.is_numeric_dtype(series):
        try:
            col_data["min_val"] = clean_series.min()
            col_data["max_val"] = clean_series.max()
            col_data["avg_val"] = round(float(clean_series.mean()), 4)
            col_data["logical_type"] = "NUMERIC"
        except Exception:
            pass
        return col_data

    # 2. String / Object columns
    str_series = clean_series.astype(str)
    non_null_count = len(str_series)

    # Empty strings (distinct from SQL NULL)
    empty_mask = str_series.str.strip().eq("")
    empty_count = int(empty_mask.sum())
    col_data["empty_count"] = empty_count
    col_data["empty_pct"] = round((empty_count / total_table_rows) * 100, 2) if total_table_rows > 0 else 0.0

    # Non-empty string records
    valid_str_series = str_series[~empty_mask]
    valid_count = len(valid_str_series)

    if valid_count == 0:
        if empty_count > 0:
            col_data["recommended_tool"] = "Blank & NULL Values"
            col_data["recommended_tool_id"] = "blanks"
            col_data["anomaly_count"] = empty_count
        return col_data

    # Whitespace issues: leading, trailing, tabs, newlines
    whitespace_mask = valid_str_series.ne(valid_str_series.str.strip()) | valid_str_series.str.contains(r'[\t\r\n]|\s{2,}', regex=True)
    whitespace_count = int(whitespace_mask.sum())
    col_data["whitespace_issues"] = whitespace_count

    # 3. Boolean Detection
    val_counts = valid_str_series.value_counts().to_dict()
    bool_eval = evaluate_boolean_series(
        column_name=str(series.name),
        declared_dtype=physical_type,
        value_counts=val_counts,
        null_count=null_count,
    )
    if bool_eval.get("is_boolean_like"):
        col_data["logical_type"] = "BOOLEAN"
        col_data["boolean_patterns"] = {
            "is_boolean_like": True,
            "confidence": bool_eval.get("confidence", 0),
            "confidence_level": bool_eval.get("confidence_level", "Low"),
            "true_representations": bool_eval.get("true_representations", []),
            "false_representations": bool_eval.get("false_representations", []),
            "needs_normalization": bool_eval.get("needs_normalization", False),
        }
        if bool_eval.get("needs_normalization"):
            col_data["recommended_tool"] = "Boolean Normalization"
            col_data["recommended_tool_id"] = "boolean"
            col_data["anomaly_count"] += bool_eval.get("recognized_count", 0)

    # 4. Text Casing Breakdown
    upper_count = int(valid_str_series.str.isupper().sum())
    lower_count = int(valid_str_series.str.islower().sum())
    title_count = int(valid_str_series.str.istitle().sum())
    mixed_casing = valid_count - (upper_count + lower_count + title_count)
    col_data["casing_breakdown"] = {
        "upper": upper_count,
        "lower": lower_count,
        "title": title_count,
        "mixed": max(0, mixed_casing),
    }

    # 5. Generic Numeric & Currency Pattern Analysis in Text
    currency_count = 0
    currencies_found: Set[str] = set()
    mixed_alphanumeric_count = 0
    parseable_number_count = 0
    unparseable_text_count = 0
    unit_suffix_count = 0
    na_string_count = 0
    suspicious_samples_map: Dict[str, int] = {}

    for val in valid_str_series:
        s_val = val.strip()
        lower_val = s_val.lower()

        # Check for placeholder missing values ("N/A", "null", "none", "?")
        if lower_val in COMMON_NA_STRINGS:
            na_string_count += 1
            suspicious_samples_map[s_val] = suspicious_samples_map.get(s_val, 0) + 1
            continue

        # Check for currency symbols
        found_curr = [c for c in CURRENCY_SYMBOLS if c in s_val]
        if found_curr:
            currency_count += 1
            currencies_found.update(found_curr)
            suspicious_samples_map[s_val] = suspicious_samples_map.get(s_val, 0) + 1

        # Check for mixed numbers and letters (e.g. 100kg, ORD-102, #45, 12.5%)
        has_digits = any(char.isdigit() for char in s_val)
        has_letters = any(char.isalpha() for char in s_val)

        if has_digits and has_letters:
            mixed_alphanumeric_count += 1
            if len(suspicious_samples_map) < 15:
                suspicious_samples_map[s_val] = suspicious_samples_map.get(s_val, 0) + 1

        # Check numeric parseability (stripping commas/currency)
        cleaned_num = re.sub(r'[\$,€£¥₹\s]', '', s_val)
        try:
            float(cleaned_num)
            parseable_number_count += 1
        except ValueError:
            unparseable_text_count += 1

    col_data["numeric_patterns"] = {
        "currency_count": currency_count,
        "currencies_found": sorted(list(currencies_found)),
        "mixed_alphanumeric_count": mixed_alphanumeric_count,
        "parseable_number_count": parseable_number_count,
        "unparseable_text_count": unparseable_text_count,
        "na_string_count": na_string_count,
    }

    # 6. Generic Date Pattern Analysis
    iso_date_count = int(valid_str_series.str.contains(r'^\d{4}[-/.]\d{1,2}[-/.]\d{1,2}', regex=True).sum())
    slash_date_count = int(valid_str_series.str.contains(r'^\d{1,2}/\d{1,2}/\d{2,4}', regex=True).sum())
    text_month_count = int(valid_str_series.str.contains(r'(?i)\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\b', regex=True).sum())
    total_date_like = iso_date_count + slash_date_count + text_month_count

    col_data["date_patterns"] = {
        "total_date_like": total_date_like,
        "iso_date_count": iso_date_count,
        "slash_date_count": slash_date_count,
        "text_month_count": text_month_count,
        "is_mixed_date_formats": bool((iso_date_count > 0 and slash_date_count > 0) or (text_month_count > 0 and slash_date_count > 0)),
    }

    # 7. Special Characters & Non-Printable
    control_char_count = int(valid_str_series.str.contains(r'[\x00-\x1F\x7F]', regex=True).sum())
    non_ascii_count = int(valid_str_series.str.contains(r'[^\x00-\x7F]', regex=True).sum())
    col_data["special_char_issues"] = {
        "control_char_count": control_char_count,
        "non_ascii_count": non_ascii_count,
    }

    # 8. Determine Logical Type & Recommendations
    if col_data["logical_type"] == physical_type.upper():
        if total_date_like >= valid_count * 0.6:
            col_data["logical_type"] = "DATE / DATETIME"
            if col_data["date_patterns"]["is_mixed_date_formats"]:
                col_data["recommended_tool"] = "Advanced Date Standardization"
                col_data["recommended_tool_id"] = "adv_dates"
            else:
                col_data["recommended_tool"] = "Date Formatting"
                col_data["recommended_tool_id"] = "dates"
        elif (parseable_number_count + currency_count) >= valid_count * 0.7:
            col_data["logical_type"] = "NUMERIC (TEXT)"
            col_data["recommended_tool"] = "Numeric Data Cleaning"
            col_data["recommended_tool_id"] = "numeric"
        elif whitespace_count > 0:
            col_data["recommended_tool"] = "Whitespace Cleaning"
            col_data["recommended_tool_id"] = "whitespace"
        elif control_char_count > 0:
            col_data["recommended_tool"] = "Special Character Cleaning"
            col_data["recommended_tool_id"] = "special_chars"
        elif empty_count > 0 or na_string_count > 0 or null_count > 0:
            col_data["recommended_tool"] = "Blank & NULL Values"
            col_data["recommended_tool_id"] = "blanks"
        elif col_data["casing_breakdown"].get("upper", 0) > 0 and col_data["casing_breakdown"].get("lower", 0) > 0:
            col_data["recommended_tool"] = "Text Casing"
            col_data["recommended_tool_id"] = "casing"

    # Compile representative suspicious samples (top 5 by frequency)
    sorted_samples = sorted(suspicious_samples_map.items(), key=lambda x: x[1], reverse=True)[:5]
    col_data["suspicious_samples"] = [
        {"value": anonymize_sample_value(k), "count": v}
        for k, v in sorted_samples
    ]

    # Calculate total anomaly count for column
    total_anoms = (
        whitespace_count
        + empty_count
        + na_string_count
        + control_char_count
        + (currency_count if col_data["logical_type"] != "NUMERIC (TEXT)" else 0)
        + (col_data["casing_breakdown"].get("mixed", 0) if col_data["logical_type"] == physical_type.upper() else 0)
    )
    col_data["anomaly_count"] = total_anoms

    return col_data


def build_table_ai_profile(
    engine,
    database: str,
    table_name: str,
    is_workspace: bool = False,
    max_sample_rows: int = 25000,
) -> Tuple[bool, str, Optional[Dict[str, Any]]]:
    """
    Constructs a comprehensive, grounded Data Quality Profile for the selected table.
    Combines existing table profiler metrics with generic column pattern detection.
    
    Returns:
        (success: bool, message: str, profile_dict: Optional[Dict])
    """
    if not engine:
        return False, "No active database connection.", None

    if not database or not table_name:
        return False, "Database and table name must be specified.", None

    try:
        quoted_tbl = _quote_table(database, table_name)

        # 1. Exact Row Count Query
        with engine.connect() as conn:
            cnt_res = conn.execute(text(f"SELECT COUNT(*) FROM {quoted_tbl}"))
            total_rows = int(cnt_res.scalar() or 0)

        # 2. Column Metadata from INFORMATION_SCHEMA
        cols_meta = _get_columns(engine, database, table_name)
        if not cols_meta:
            return False, f"Table '{database}.{table_name}' contains no readable columns or does not exist.", None

        # Filter internal workspace columns starting with '__'
        visible_cols_meta = [
            c for c in cols_meta
            if not str(c.get("COLUMN_NAME", "")).startswith("__")
        ]

        # 3. Read DataFrame for Pattern Analysis (bounded to max_sample_rows for large tables)
        is_sampled = total_rows > max_sample_rows
        sample_limit_clause = f"LIMIT {max_sample_rows}" if is_sampled else ""
        query_sql = f"SELECT * FROM {quoted_tbl} {sample_limit_clause}"

        with engine.connect() as conn:
            df = pd.read_sql_query(text(query_sql), conn)

        # Drop internal columns from DataFrame
        clean_cols = [c for c in df.columns if not str(c).startswith("__")]
        df = df[clean_cols]

        # 4. Duplicate Rows Analysis
        duplicate_group_count = int(df.duplicated().sum())
        duplicate_row_count = int(df.duplicated(keep=False).sum())

        # 5. Column-Level Generic Pattern Profiling
        columns_profile: List[Dict[str, Any]] = []
        total_cell_count = total_rows * len(clean_cols)
        total_dirty_cells = 0
        high_severity_count = 0
        med_severity_count = 0
        low_severity_count = 0

        for col_meta in visible_cols_meta:
            col_name = col_meta.get("COLUMN_NAME", "")
            phys_type = col_meta.get("DATA_TYPE", "varchar")

            if col_name not in df.columns:
                continue

            series = df[col_name]
            patterns = analyze_column_generic_patterns(
                series=series,
                physical_type=phys_type,
                total_table_rows=len(df),
            )

            # Extrapolate counts if sampled
            scale_factor = (total_rows / len(df)) if (is_sampled and len(df) > 0) else 1.0
            extrapolated_nulls = int(round(patterns["null_count"] * scale_factor))
            extrapolated_empties = int(round(patterns["empty_count"] * scale_factor))
            extrapolated_whitespace = int(round(patterns["whitespace_issues"] * scale_factor))

            col_entry: Dict[str, Any] = {
                "name": col_name,
                "physical_type": phys_type,
                "logical_type": patterns["logical_type"],
                "total_rows": total_rows,
                "null_count": extrapolated_nulls,
                "null_pct": patterns["null_pct"],
                "empty_count": extrapolated_empties,
                "empty_pct": patterns["empty_pct"],
                "unique_count": patterns["unique_count"],
                "whitespace_issues": extrapolated_whitespace,
                "casing_breakdown": patterns["casing_breakdown"],
                "numeric_patterns": patterns["numeric_patterns"],
                "date_patterns": patterns["date_patterns"],
                "boolean_patterns": patterns["boolean_patterns"],
                "special_char_issues": patterns["special_char_issues"],
                "suspicious_samples": patterns["suspicious_samples"],
                "min_val": patterns["min_val"],
                "max_val": patterns["max_val"],
                "avg_val": patterns["avg_val"],
                "recommended_tool": patterns["recommended_tool"],
                "recommended_tool_id": patterns["recommended_tool_id"],
                "anomaly_count": int(round(patterns["anomaly_count"] * scale_factor)),
            }

            # Track Severity
            if patterns["null_pct"] >= 20.0 or patterns["empty_pct"] >= 20.0:
                high_severity_count += 1
            elif patterns["null_pct"] > 0 or patterns["empty_pct"] > 0:
                med_severity_count += 1

            if patterns["numeric_patterns"].get("currency_count", 0) > 0 and patterns["logical_type"] != "NUMERIC (TEXT)":
                med_severity_count += 1

            if patterns["date_patterns"].get("is_mixed_date_formats"):
                med_severity_count += 1

            if patterns["whitespace_issues"] > 0:
                low_severity_count += 1

            total_dirty_cells += (extrapolated_nulls + extrapolated_empties + extrapolated_whitespace + col_entry["anomaly_count"])
            columns_profile.append(col_entry)

        if duplicate_group_count > 0:
            high_severity_count += 1

        # Calculate Overall Health Score (0 - 100)
        cleanliness_ratio = 1.0 - (min(total_dirty_cells, total_cell_count) / max(total_cell_count, 1))
        quality_score = max(5, int(round(cleanliness_ratio * 100)))

        profile_result: Dict[str, Any] = {
            "database": database,
            "table_name": table_name,
            "is_workspace": is_workspace,
            "table_type_label": "Isolated Cleaning Workspace" if is_workspace else "Source Table (Strict Read-Only)",
            "row_count": total_rows,
            "column_count": len(clean_cols),
            "is_sampled": is_sampled,
            "sample_size": len(df) if is_sampled else total_rows,
            "duplicate_rows": duplicate_row_count,
            "duplicate_groups": duplicate_group_count,
            "quality_score": quality_score,
            "severity_summary": {
                "high": high_severity_count,
                "medium": med_severity_count,
                "low": low_severity_count,
            },
            "columns": columns_profile,
        }

        # Build token-efficient compact summary for AI prompt
        compact_summary = format_compact_ai_summary(profile_result)
        profile_result["compact_summary"] = compact_summary

        return True, f"Profiling analysis completed for `{table_name}` ({total_rows:,} rows, {len(clean_cols)} columns).", profile_result

    except Exception as e:
        logger.error("Error profiling table '%s.%s' for AI: %s", database, table_name, str(e))
        return False, f"Profiling failed: {str(e)}", None


def format_compact_ai_summary(profile: Dict[str, Any]) -> str:
    """
    Constructs a highly compact, structured text summary of the profiling evidence.
    Optimized to fit comfortably in LLM context windows without data loss.
    """
    lines = [
        f"DATASET CONTEXT: Table `{profile['database']}.{profile['table_name']}`",
        f"- Table Type: {profile['table_type_label']}",
        f"- Total Rows: {profile['row_count']:,} | Total Columns: {profile['column_count']}",
        f"- Overall Health Score: {profile['quality_score']}/100",
        f"- Duplicate Rows Detected: {profile['duplicate_groups']:,} duplicate occurrences",
        f"- Issues by Severity: {profile['severity_summary']['high']} High, {profile['severity_summary']['medium']} Medium, {profile['severity_summary']['low']} Low",
        "",
        "COLUMN-BY-COLUMN PROFILING EVIDENCE (Calculated locally):",
    ]

    for idx, col in enumerate(profile.get("columns", []), 1):
        obs = []
        if col["null_count"] > 0:
            obs.append(f"{col['null_count']:,} NULLs ({col['null_pct']}%)")
        if col["empty_count"] > 0:
            obs.append(f"{col['empty_count']:,} empty strings")
        if col["whitespace_issues"] > 0:
            obs.append(f"{col['whitespace_issues']:,} whitespace issues")

        cb = col.get("casing_breakdown", {})
        if cb.get("upper", 0) > 0 and cb.get("lower", 0) > 0:
            obs.append(f"Mixed casing: {cb.get('upper')} UPPER, {cb.get('lower')} lower, {cb.get('title')} Title")

        num = col.get("numeric_patterns", {})
        if num.get("currency_count", 0) > 0:
            curr_str = "/".join(num.get("currencies_found", []))
            obs.append(f"{num['currency_count']} values contain currency symbols ({curr_str})")
        if num.get("mixed_alphanumeric_count", 0) > 0:
            obs.append(f"{num['mixed_alphanumeric_count']} values contain mixed numbers and letters")
        if num.get("na_string_count", 0) > 0:
            obs.append(f"{num['na_string_count']} text placeholders (e.g. 'N/A', 'null')")

        dt = col.get("date_patterns", {})
        if dt.get("total_date_like", 0) > 0:
            obs.append(f"{dt['total_date_like']} date-like values (ISO: {dt.get('iso_date_count')}, Slash: {dt.get('slash_date_count')})")
            if dt.get("is_mixed_date_formats"):
                obs.append("⚠️ Mixed date formats detected")

        sp = col.get("special_char_issues", {})
        if sp.get("control_char_count", 0) > 0:
            obs.append(f"{sp['control_char_count']} values contain control/non-printable characters")

        bool_p = col.get("boolean_patterns", {})
        if bool_p.get("is_boolean_like"):
            true_r = "/".join(bool_p.get("true_representations", [])[:3])
            false_r = "/".join(bool_p.get("false_representations", [])[:3])
            obs.append(f"Boolean column with representations (True: [{true_r}], False: [{false_r}])")

        samples = col.get("suspicious_samples", [])
        sample_str = ""
        if samples:
            sample_items = [f"'{s['value']}' ({s['count']}x)" for s in samples[:3]]
            sample_str = f" | Suspicious examples: {', '.join(sample_items)}"

        tool_str = f" | Recommended Tool: {col['recommended_tool']}" if col.get("recommended_tool") else ""

        obs_text = "; ".join(obs) if obs else "Clean (no anomalies detected)"
        lines.append(
            f"{idx}. `{col['name']}` ({col['physical_type']} -> {col['logical_type']}): "
            f"Unique: {col['unique_count']:,} | {obs_text}{sample_str}{tool_str}"
        )

    return "\n".join(lines)


def format_column_drilldown_prompt(col_profile: Dict[str, Any], table_name: str) -> str:
    """Creates a user inquiry prompt focused on a specific column's findings."""
    return (
        f"Please explain the data quality findings and anomalies in column `{col_profile['name']}` "
        f"of table `{table_name}`. What did the profiler detect, what are the possible root causes, "
        f"and which DataClean Studio tool should I use to clean it?"
    )
