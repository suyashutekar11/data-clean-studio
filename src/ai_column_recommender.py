"""
DataClean Studio — AI-Powered Column Analysis and SQL Query Recommendations
src/ai_column_recommender.py

Analyzes column pattern profiling results and generates actionable, safe,
syntactically valid SQL queries to resolve detected data-quality issues.

Core Safety & Architecture Principles:
1. Zero Production Risk: All modification queries strictly target isolated workspace tables
   (`{table}__cleaning_{uuid}`). Production tables remain 100% read-only.
2. Dialect Awareness: Generates syntax tailored to MySQL 8.x or SQLite.
3. Preview & Validation First: Every recommendation provides a safe SELECT preview query
   and a SELECT validation query alongside the transformation SQL.
4. Grounded in Profiler Metrics: Recommendations directly reflect actual detected counts
   and percentages (e.g. 24 occurrences of 'N/A' placeholders in performance_score_text).
5. Never Auto-Execute: Queries are strictly advisory and displayed for review.
6. Resilient Fallback: Includes rule-grounded recommendations if AI API is unconfigured or unreachable.
"""

from __future__ import annotations

import json
import logging
import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple, Set, Callable
from urllib.parse import urlparse

from src.ai_column_config import AIColumnConfig
from src.ai_service import sanitize_error_message
from src.column_profiling_engine import (
    ColumnProfileResult,
    ValuePatternCategory,
    CATEGORY_DISPLAY_LABELS,
)

logger = logging.getLogger(__name__)


@dataclass
class ColumnQueryRecommendation:
    """Encapsulates a single detected data-quality issue and its actionable SQL recommendations."""
    issue_id: str
    title: str
    issue_detected: str
    recommended_solution: str
    preview_query: str
    cleaning_query: str
    validation_query: str
    expected_result: str
    risks_and_assumptions: str
    is_modifying: bool = True
    category: str = ""
    affected_records: int = 0
    affected_percentage: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Serializes recommendation into a dictionary."""
        return {
            "issue_id": self.issue_id,
            "title": self.title,
            "issue_detected": self.issue_detected,
            "recommended_solution": self.recommended_solution,
            "preview_query": self.preview_query,
            "cleaning_query": self.cleaning_query,
            "validation_query": self.validation_query,
            "expected_result": self.expected_result,
            "risks_and_assumptions": self.risks_and_assumptions,
            "is_modifying": self.is_modifying,
            "category": self.category,
            "affected_records": self.affected_records,
            "affected_percentage": self.affected_percentage,
        }


@dataclass
class AIAnalysisResult:
    """Complete outcome of the AI Column Analysis phase."""
    table_name: str
    column_name: str
    workspace_table: str
    dialect: str
    recommendations: List[ColumnQueryRecommendation] = field(default_factory=list)
    summary_narrative: str = ""
    success: bool = True
    error_message: Optional[str] = None
    source: str = "ai"  # "ai" or "rules_fallback"
    payload_debug: Optional[List[Dict[str, Any]]] = None
    http_status: Optional[int] = None
    endpoint_host: str = ""
    duration_ms: Optional[int] = None
    finish_reason: Optional[str] = None
    truncated: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Serializes the analysis outcome into a dictionary."""
        return {
            "table_name": self.table_name,
            "column_name": self.column_name,
            "workspace_table": self.workspace_table,
            "dialect": self.dialect,
            "recommendations": [r.to_dict() for r in self.recommendations],
            "summary_narrative": self.summary_narrative,
            "success": self.success,
            "error_message": self.error_message,
            "source": self.source,
            "payload_debug": self.payload_debug,
            "http_status": self.http_status,
            "endpoint_host": self.endpoint_host,
            "duration_ms": self.duration_ms,
            "finish_reason": self.finish_reason,
            "truncated": self.truncated,
        }


def _quote_identifier(ident: str, dialect: str = "mysql") -> str:
    """Escapes and encloses an identifier in appropriate quotation marks."""
    clean = ident.replace("`", "``").replace('"', '""')
    if dialect.lower() == "mysql":
        return f"`{clean}`"
    return f'"{clean}"'


def _extract_quoted_identifiers(sql: str, dialect: str) -> Set[str]:
    """
    Extract quoted column/table identifiers from a SQL string.

    MySQL uses backticks (`col`), SQLite/standard SQL uses double quotes ("col").
    Returns the set of unquoted identifier names found.
    """
    identifiers: Set[str] = set()
    if dialect.lower() == "mysql":
        # Match backtick-quoted identifiers: `col_name`
        for m in re.finditer(r"`([^`]+)`", sql):
            identifiers.add(m.group(1))
    else:
        # Match double-quoted identifiers: "col_name"
        for m in re.finditer(r'"([^"]+)"', sql):
            identifiers.add(m.group(1))
    return identifiers


def _column_appears_as_identifier(col_name: str, sql: str, dialect: str) -> bool:
    """
    Check whether col_name appears as a standalone SQL identifier in sql.

    Uses word-boundary-aware matching so that 'salary' does not match
    'salary_text' or 'my_salary'. Accepts:
    - Backtick-quoted: `salary` (MySQL)
    - Double-quoted: "salary" (SQLite/standard)
    - Unquoted: salary (surrounded by non-identifier characters)
    """
    escaped = re.escape(col_name)

    # Quoted identifier patterns
    if dialect.lower() == "mysql":
        if re.search(r"`" + escaped + r"`", sql):
            return True
    else:
        if re.search(r'"' + escaped + r'"', sql):
            return True

    # Unquoted identifier: must be bounded by non-word characters or string edges
    pattern = r"(?:^|[^a-zA-Z0-9_])" + escaped + r"(?:$|[^a-zA-Z0-9_])"
    if re.search(pattern, sql):
        return True

    return False


def _validate_column_references(
    sql: str,
    profile: ColumnProfileResult,
    workspace_table: str,
    dialect: str,
    item_index: int,
    sql_field: str,
) -> Optional[str]:
    """
    Validate that a SQL query references the correct workspace table and
    profiled column using exact identifier matching (no substring confusion).

    Returns None if valid, or an error message string if invalid.
    """
    q_tbl = _quote_identifier(workspace_table, dialect)

    # Must reference the workspace table using exact identifier matching.
    # No substring fallback: table names with underscores are handled correctly
    # by _column_appears_as_identifier because '_' is a word character, so
    # 'employees__cleaning_test' matches as a whole identifier but not as a
    # substring of 'employees__cleaning_test_backup'.
    if not _column_appears_as_identifier(workspace_table, sql, dialect):
        return (
            f"recommendations[{item_index}] field '{sql_field}' does not reference "
            f"the workspace table '{workspace_table}' as a distinct identifier. "
            f"Production tables are read-only. "
            f"(Note: '{workspace_table}' must not be confused with similarly named tables.)"
        )

    col_name = profile.column_name

    # Must reference the profiled column using exact identifier matching
    if not _column_appears_as_identifier(col_name, sql, dialect):
        # Also check quoted identifiers extracted from SQL
        quoted_ids = _extract_quoted_identifiers(sql, dialect)
        if col_name not in quoted_ids:
            return (
                f"recommendations[{item_index}] field '{sql_field}' does not reference "
                f"the profiled column '{col_name}' as a distinct identifier. "
                f"Recommendations must be grounded in profiling evidence. "
                f"(Note: '{col_name}' must not be confused with similarly named columns.)"
            )

    return None


def _validate_statistical_grounding(
    item: Dict[str, Any],
    profile: ColumnProfileResult,
    item_index: int,
    rounding_tolerance: float = 0.01,
) -> Optional[str]:
    """
    Validate affected_records and affected_percentage against profiling evidence.

    Checks:
    - affected_records is an integer within [0, total_records]
    - affected_percentage is consistent with affected_records / total_records * 100
      within rounding_tolerance (default ±0.01 percentage points)
    - If the recommendation category maps to a known profile count, the claim
      does not exceed that count

    Returns None if valid, or an error message string if invalid.
    """
    affected_records = item.get("affected_records", 0)
    affected_percentage = item.get("affected_percentage", 0.0)
    category = item.get("category", "")
    total_records = profile.total_records

    if total_records <= 0:
        # No profile evidence available; cannot verify statistically
        return None

    # Type validation already done upstream; re-assert for safety
    if not isinstance(affected_records, int) or isinstance(affected_records, bool):
        return (
            f"recommendations[{item_index}] field 'affected_records' must be an integer."
        )
    if not isinstance(affected_percentage, (int, float)) or isinstance(affected_percentage, bool):
        return (
            f"recommendations[{item_index}] field 'affected_percentage' must be a number."
        )

    # Range check: affected_records cannot exceed total records
    if affected_records < 0 or affected_records > total_records:
        return (
            f"recommendations[{item_index}] affected_records ({affected_records}) "
            f"is outside valid range [0, {total_records}] based on profile total_records."
        )

    # Percentage consistency: affected_percentage ≈ affected_records / total_records * 100
    expected_pct = round((affected_records / total_records) * 100.0, 2)
    if abs(affected_percentage - expected_pct) > rounding_tolerance:
        return (
            f"recommendations[{item_index}] affected_percentage ({affected_percentage}) "
            f"is inconsistent with affected_records ({affected_records}) / total_records "
            f"({total_records}) = {expected_pct}% (tolerance ±{rounding_tolerance})."
        )

    # Category-specific grounding: if the category maps to a known profile count,
    # the claim should not exceed that count
    category_max: Optional[int] = None
    cat_lower = (category or "").lower()
    if "missing_placeholder" in cat_lower or "placeholder" in cat_lower:
        category_max = profile.placeholder_count or profile.missing_count or 0
    elif "empty" in cat_lower or "whitespace" in cat_lower:
        category_max = (
            (profile.empty_string_records or 0) + (profile.whitespace_records or 0)
        )
    elif "numeric" in cat_lower and "text" in cat_lower:
        category_max = profile.counts.get("numeric_only", 0) if profile.counts else 0
    elif "date" in cat_lower:
        category_max = profile.counts.get("date_like", 0) if profile.counts else 0

    if category_max is not None and affected_records > category_max:
        return (
            f"recommendations[{item_index}] affected_records ({affected_records}) "
            f"exceeds the profile-verified count for category '{category}' "
            f"({category_max} records). Recommendation is not statistically grounded."
        )

    return None


def generate_grounded_recommendations(
    profile: ColumnProfileResult,
    workspace_table: str,
    dialect: str = "mysql",
) -> List[ColumnQueryRecommendation]:
    """
    Deterministically generates high-fidelity, grounded SQL recommendations from profiler statistics.
    Serves as the foundation for the AI prompt and as a 100% reliable fallback if API access is offline.
    """
    recommendations: List[ColumnQueryRecommendation] = []
    total = profile.total_records
    if total <= 0:
        return recommendations

    col_name = profile.column_name
    q_col = _quote_identifier(col_name, dialect)
    q_tbl = _quote_identifier(workspace_table, dialect)
    dtype = (profile.column_declared_type or "").upper()

    # 1. Missing-Value Placeholders (e.g. 24 occurrences of 'N/A' in performance_score_text)
    ph_count = profile.placeholder_records
    if ph_count > 0:
        ph_pct = round((ph_count / total) * 100.0, 2)
        placeholders_sql = "'n/a', 'na', 'not applicable', 'unknown', 'none', 'null', 'nan', 'nil', '-', '--', '?'"
        
        preview_sql = (
            f"SELECT {q_col}, COUNT(*) AS frequency\n"
            f"FROM {q_tbl}\n"
            f"WHERE LOWER(TRIM({q_col})) IN ({placeholders_sql})\n"
            f"GROUP BY {q_col}\n"
            f"ORDER BY frequency DESC;"
        )
        cleaning_sql = (
            f"UPDATE {q_tbl}\n"
            f"SET {q_col} = NULL\n"
            f"WHERE LOWER(TRIM({q_col})) IN ({placeholders_sql});"
        )
        validation_sql = (
            f"SELECT COUNT(*) AS remaining_placeholders\n"
            f"FROM {q_tbl}\n"
            f"WHERE LOWER(TRIM({q_col})) IN ({placeholders_sql});"
        )
        recommendations.append(ColumnQueryRecommendation(
            issue_id="missing_value_placeholders",
            title=f"Non-Standard Missing Value Placeholders ({ph_count:,} records)",
            issue_detected=(
                f"{ph_count:,} records ({ph_pct}%) contain textual placeholder strings such as 'N/A', 'NA', or 'Unknown' "
                f"instead of standard database NULLs. In text and numeric fields, text placeholders prevent mathematical "
                f"aggregations, type conversion, and consistent querying."
            ),
            recommended_solution=(
                f"Convert identified missing-value placeholder strings to genuine SQL NULL values on the isolated "
                f"workspace table `{workspace_table}`."
            ),
            preview_query=preview_sql,
            cleaning_query=cleaning_sql,
            validation_query=validation_sql,
            expected_result=(
                f"All {ph_count:,} placeholder strings will be converted to NULL. Downstream aggregations "
                f"(AVG, SUM, MIN, MAX) and numeric filters will function correctly without errors."
            ),
            risks_and_assumptions=(
                f"Assumes values like 'N/A' signify absent or unknown data rather than an intentional domain code. "
                f"Operation is safe when performed on workspace table."
            ),
            is_modifying=True,
            category="missing_placeholder",
            affected_records=ph_count,
            affected_percentage=ph_pct,
        ))

    # 2. Empty Strings ("") and Whitespace-Only strings
    empty_count = profile.empty_string_records
    ws_count = profile.whitespace_records
    empty_ws_count = empty_count + ws_count
    if empty_ws_count > 0:
        empty_pct = round((empty_ws_count / total) * 100.0, 2)
        preview_sql = (
            f"SELECT COUNT(*) AS empty_or_whitespace_count\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} = '' OR TRIM({q_col}) = '';"
        )
        cleaning_sql = (
            f"UPDATE {q_tbl}\n"
            f"SET {q_col} = NULL\n"
            f"WHERE {q_col} = '' OR TRIM({q_col}) = '';"
        )
        validation_sql = (
            f"SELECT COUNT(*) AS remaining_empty_whitespace\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} = '' OR TRIM({q_col}) = '';"
        )
        recommendations.append(ColumnQueryRecommendation(
            issue_id="empty_and_whitespace_strings",
            title=f"Empty Strings & Whitespace-Only Values ({empty_ws_count:,} records)",
            issue_detected=(
                f"{empty_ws_count:,} records ({empty_pct}%) consist of exact zero-length strings (\"\") "
                f"or invisible whitespace characters. These represent incomplete data and can cause false distinct groupings."
            ),
            recommended_solution=(
                f"Standardize empty and whitespace-only strings to SQL NULL across `{workspace_table}`."
            ),
            preview_query=preview_sql,
            cleaning_query=cleaning_sql,
            validation_query=validation_sql,
            expected_result=(
                f"Zero-length strings and pure whitespace values will be converted to standardized SQL NULLs."
            ),
            risks_and_assumptions=(
                f"Assumes empty strings represent missing information rather than an intentional blank value."
            ),
            is_modifying=True,
            category="whitespace_empty",
            affected_records=empty_ws_count,
            affected_percentage=empty_pct,
        ))

    # 3. Numeric Values Stored in Text Column
    num_only_count = profile.counts.get(ValuePatternCategory.NUMERIC_ONLY.value, 0)
    if num_only_count > 0 and any(t in dtype for t in ("VARCHAR", "CHAR", "TEXT")):
        num_pct = round((num_only_count / total) * 100.0, 2)
        
        # Check if the column is primarily numeric (e.g. scores, quantities, prices)
        is_predominantly_numeric = (num_pct + (ph_pct if ph_count > 0 else 0)) > 60.0
        
        if is_predominantly_numeric:
            preview_sql = (
                f"SELECT {q_col}\n"
                f"FROM {q_tbl}\n"
                f"WHERE {q_col} IS NOT NULL\n"
                f"  AND {q_col} NOT REGEXP '^[+-]?[0-9]+(\\.[0-9]+)?$'\n"
                f"LIMIT 100;"
            ) if dialect == "mysql" else (
                f"SELECT {q_col}\n"
                f"FROM {q_tbl}\n"
                f"WHERE {q_col} IS NOT NULL\n"
                f"  AND NOT ({q_col} GLOB '[0-9]*' OR {q_col} GLOB '[0-9]*.[0-9]*')\n"
                f"LIMIT 100;"
            )
            cleaning_sql = (
                f"-- Step 1: Clean non-numeric or placeholder entries first (see placeholders recommendation)\n"
                f"-- Step 2: Convert column type to proper numeric type (e.g. DECIMAL(10,2) or INT)\n"
                f"ALTER TABLE {q_tbl} MODIFY COLUMN {q_col} DECIMAL(10, 2) NULL;"
            ) if dialect == "mysql" else (
                f"-- SQLite dynamic typing: Cast values when querying or recreating table\n"
                f"UPDATE {q_tbl} SET {q_col} = CAST({q_col} AS REAL) WHERE {q_col} GLOB '[0-9]*';"
            )
            validation_sql = (
                f"SELECT {q_col}, COUNT(*) AS count\n"
                f"FROM {q_tbl}\n"
                f"GROUP BY {q_col}\n"
                f"ORDER BY count DESC\n"
                f"LIMIT 10;"
            )
            recommendations.append(ColumnQueryRecommendation(
                issue_id="numeric_in_text_type",
                title=f"Numeric Data Stored as Text ({num_only_count:,} records)",
                issue_detected=(
                    f"{num_only_count:,} records ({num_pct}%) contain pure numeric data, but the column "
                    f"is declared with database type '{dtype}'. Storing numbers as text increases storage, "
                    f"leads to lexicographical sorting bugs (e.g. '10' < '2'), and disables mathematical indexing."
                ),
                recommended_solution=(
                    f"Clean non-numeric placeholders, verify numeric validity, and transition the column to a proper "
                    f"DECIMAL or INTEGER representation in the workspace table."
                ),
                preview_query=preview_sql,
                cleaning_query=cleaning_sql,
                validation_query=validation_sql,
                expected_result=(
                    f"Column `{col_name}` will use numeric storage, enabling exact mathematical ordering and aggregations."
                ),
                risks_and_assumptions=(
                    f"Requires all non-numeric values (such as placeholders or text) to be cleaned or set to NULL "
                    f"prior to executing ALTER TABLE, otherwise MySQL will reject the conversion."
                ),
                is_modifying=True,
                category="numeric_only",
                affected_records=num_only_count,
                affected_percentage=num_pct,
            ))

    # 4. Formatted Numeric Strings (Currency, Commas, Percentages)
    num_special_count = profile.counts.get(ValuePatternCategory.NUMERIC_SPECIAL.value, 0)
    if num_special_count > 0:
        ns_pct = round((num_special_count / total) * 100.0, 2)
        preview_sql = (
            f"SELECT {q_col}\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} REGEXP '[$%,]' OR {q_col} LIKE '%$%'\n"
            f"LIMIT 50;"
        ) if dialect == "mysql" else (
            f"SELECT {q_col}\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} LIKE '%$%' OR {q_col} LIKE '%,%' OR {q_col} LIKE '%%%'\n"
            f"LIMIT 50;"
        )
        cleaning_sql = (
            f"UPDATE {q_tbl}\n"
            f"SET {q_col} = TRIM(REPLACE(REPLACE(REPLACE({q_col}, '$', ''), '%', ''), ',', ''))\n"
            f"WHERE {q_col} REGEXP '[$%,]';"
        ) if dialect == "mysql" else (
            f"UPDATE {q_tbl}\n"
            f"SET {q_col} = TRIM(REPLACE(REPLACE(REPLACE({q_col}, '$', ''), '%', ''), ',', ''))\n"
            f"WHERE {q_col} LIKE '%$%' OR {q_col} LIKE '%,%' OR {q_col} LIKE '%%%';"
        )
        validation_sql = (
            f"SELECT COUNT(*) AS remaining_formatted_numbers\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} REGEXP '[$%,]';"
        ) if dialect == "mysql" else (
            f"SELECT COUNT(*) AS remaining_formatted_numbers\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} LIKE '%$%' OR {q_col} LIKE '%,%' OR {q_col} LIKE '%%%';"
        )
        recommendations.append(ColumnQueryRecommendation(
            issue_id="formatted_numeric_symbols",
            title=f"Numbers with Formatting Symbols ({num_special_count:,} records)",
            issue_detected=(
                f"{num_special_count:,} records ({ns_pct}%) contain numeric values formatted with currency symbols ($), "
                f"percentage signs (%), or thousand separators (,). These formatting symbols prevent direct numeric calculation."
            ),
            recommended_solution=(
                f"Strip currency symbols, commas, and percentage signs using REPLACE functions to convert formatted "
                f"strings into pure numeric representations."
            ),
            preview_query=preview_sql,
            cleaning_query=cleaning_sql,
            validation_query=validation_sql,
            expected_result=(
                f"Values like '$2,500.00' and '50%' become '2500.00' and '50', enabling numeric conversion."
            ),
            risks_and_assumptions=(
                f"Percentages may need domain scaling (e.g., 50% &rarr; 0.50) depending on whether the target column "
                f"stores decimal rates or percentages."
            ),
            is_modifying=True,
            category="numeric_special",
            affected_records=num_special_count,
            affected_percentage=ns_pct,
        ))

    # 5. Date-like Strings in Non-Date Column
    date_count = profile.counts.get(ValuePatternCategory.DATE_LIKE.value, 0)
    if date_count > 0 and not any(t in dtype for t in ("DATE", "TIME", "DATETIME", "TIMESTAMP")):
        date_pct = round((date_count / total) * 100.0, 2)
        preview_sql = (
            f"SELECT {q_col}, COUNT(*) AS frequency\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} IS NOT NULL\n"
            f"GROUP BY {q_col}\n"
            f"ORDER BY frequency DESC\n"
            f"LIMIT 50;"
        )
        cleaning_sql = (
            f"-- Standardize ISO dates (YYYY-MM-DD) or convert separated formats:\n"
            f"UPDATE {q_tbl}\n"
            f"SET {q_col} = DATE_FORMAT(STR_TO_DATE({q_col}, '%d/%m/%Y'), '%Y-%m-%d')\n"
            f"WHERE {q_col} REGEXP '^[0-9]{{1,2}}/[0-9]{{1,2}}/[0-9]{{4}}$';"
        ) if dialect == "mysql" else (
            f"UPDATE {q_tbl}\n"
            f"SET {q_col} = substr({q_col},7,4) || '-' || substr({q_col},4,2) || '-' || substr({q_col},1,2)\n"
            f"WHERE {q_col} LIKE '__/__/____';"
        )
        validation_sql = (
            f"SELECT {q_col}\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} IS NOT NULL\n"
            f"  AND {q_col} NOT REGEXP '^[0-9]{{4}}-[0-9]{{2}}-[0-9]{{2}}$'\n"
            f"LIMIT 20;"
        ) if dialect == "mysql" else (
            f"SELECT {q_col} FROM {q_tbl} WHERE {q_col} NOT LIKE '____-__-__' LIMIT 20;"
        )
        recommendations.append(ColumnQueryRecommendation(
            issue_id="date_format_inconsistency",
            title=f"Date-Like Representations in Text Column ({date_count:,} records)",
            issue_detected=(
                f"{date_count:,} records ({date_pct}%) contain date-like strings (ISO dates, slash/dash separated, "
                f"or textual months) stored in a '{dtype}' column."
            ),
            recommended_solution=(
                f"Standardize date representations into canonical ISO format (`YYYY-MM-DD`) on `{workspace_table}`."
            ),
            preview_query=preview_sql,
            cleaning_query=cleaning_sql,
            validation_query=validation_sql,
            expected_result=(
                f"All dates formatted consistently as YYYY-MM-DD, allowing chronological sorting and date filtering."
            ),
            risks_and_assumptions=(
                f"Ambiguous date formats (e.g. 05/06/2023) should be verified for DD/MM vs MM/DD conventions."
            ),
            is_modifying=True,
            category="date_like",
            affected_records=date_count,
            affected_percentage=date_pct,
        ))

    # 6. Leading/Trailing Whitespace in Text
    text_count = profile.counts.get(ValuePatternCategory.ALPHABETIC_ONLY.value, 0) + \
                 profile.counts.get(ValuePatternCategory.TEXT_SPECIAL.value, 0) + \
                 profile.counts.get(ValuePatternCategory.ALPHANUMERIC.value, 0)
    if text_count > 0:
        preview_sql = (
            f"SELECT {q_col}\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} LIKE ' %' OR {q_col} LIKE '% '\n"
            f"LIMIT 25;"
        )
        cleaning_sql = (
            f"UPDATE {q_tbl}\n"
            f"SET {q_col} = TRIM({q_col})\n"
            f"WHERE {q_col} LIKE ' %' OR {q_col} LIKE '% ';"
        )
        validation_sql = (
            f"SELECT COUNT(*) AS remaining_untrimmed_records\n"
            f"FROM {q_tbl}\n"
            f"WHERE {q_col} LIKE ' %' OR {q_col} LIKE '% ';"
        )
        recommendations.append(ColumnQueryRecommendation(
            issue_id="unwanted_text_whitespace",
            title="Unwanted Leading / Trailing Whitespace",
            issue_detected=(
                f"Text columns commonly accumulate leading or trailing spaces from user entry or copy-paste operations, "
                f"causing hidden mismatches during JOINs and GROUP BY operations."
            ),
            recommended_solution=(
                f"Execute TRIM({q_col}) on `{workspace_table}` to remove extraneous leading and trailing spaces."
            ),
            preview_query=preview_sql,
            cleaning_query=cleaning_sql,
            validation_query=validation_sql,
            expected_result=(
                f"Strings stripped of accidental leading/trailing spaces without altering internal spacing between words."
            ),
            risks_and_assumptions=(
                f"Low risk. Preserves internal spacing; only removes outer whitespace."
            ),
            is_modifying=True,
            category="text_whitespace",
            affected_records=text_count,
            affected_percentage=round((text_count / total) * 100.0, 2),
        ))

    return recommendations


def build_system_prompt(dialect: str, workspace_table: str) -> str:
    """Builds a concise, explicit system prompt demanding JSON-only output.

    The model must return ONLY a valid JSON object matching the recommendation
    schema. No introductory text, no Markdown fences, no explanations outside
    the JSON object are permitted.
    """
    quote_char = '`' if dialect.lower() == 'mysql' else '"'
    return (
        f"You are a Data Quality Engineer. Return ONLY a valid JSON object. "
        f"No intro text, no Markdown fences, no explanations outside the JSON.\n\n"
        f"ZERO PRODUCTION RISK: Never modify source/production tables. All cleaning queries "
        f"must target the workspace table `{workspace_table}`.\n\n"
        f"DIALECT: {dialect.upper()}. Use {quote_char} identifier escaping.\n\n"
        f"OUTPUT SCHEMA (exact, no extra keys):\n"
        f'{{\"summary\": \"string\", \"recommendations\": ['
        f'{{\"issue_id\": \"string\", \"title\": \"string\", \"issue_detected\": \"string\", '
        f'\"recommended_solution\": \"string\", \"preview_query\": \"string\", '
        f'\"cleaning_query\": \"string\", \"validation_query\": \"string\", '
        f'\"expected_result\": \"string\", \"risks_and_assumptions\": \"string\", '
        f'\"is_modifying\": true, \"category\": \"string\", \"affected_records\": 0, '
        f'\"affected_percentage\": 0.0}}]}}\n\n'
        f"Ground every recommendation in the profiling metrics provided in the user message."
    )


def build_user_prompt(
    profile: ColumnProfileResult,
    workspace_table: str,
    dialect: str = "mysql",
) -> str:
    """Constructs prompt containing aggregated column profiling statistics."""
    categories_summary = []
    # Include non-zero categories first, or all categories if all 0
    active_cats = [c for c in ValuePatternCategory if profile.counts.get(c.value, 0) > 0]
    display_cats = active_cats if active_cats else list(ValuePatternCategory)
    for cat in display_cats:
        cnt = profile.counts.get(cat.value, 0)
        pct = profile.percentages.get(cat.value, 0.0)
        label = CATEGORY_DISPLAY_LABELS.get(cat.value, cat.value)
        categories_summary.append(f"- {label} (`{cat.value}`): {cnt:,} records ({pct:.2f}%)")

    categories_text = "\n".join(categories_summary)

    total = profile.total_records
    null_pct = round((profile.null_records / total * 100.0), 2) if total > 0 else 0.0
    empty_pct = round((profile.empty_string_records / total * 100.0), 2) if total > 0 else 0.0
    ws_pct = round((profile.whitespace_records / total * 100.0), 2) if total > 0 else 0.0
    ph_pct = round((profile.placeholder_records / total * 100.0), 2) if total > 0 else 0.0

    return (
        f"Analyze the following column profile metrics and generate actionable SQL cleaning queries:\n\n"
        f"### Column Profile Context:\n"
        f"- Target Table: `{profile.table_name}`\n"
        f"- Target Column: `{profile.column_name}`\n"
        f"- Declared Database Data Type: `{profile.column_declared_type}`\n"
        f"- Total Records Scanned: {profile.total_records:,}\n"
        f"- Target Staging/Workspace Table: `{workspace_table}`\n"
        f"- Connected Database Dialect: `{dialect}`\n\n"
        f"### Missing Values Breakdown:\n"
        f"- Total Missing Records: {profile.missing_records:,} ({round((profile.missing_records/total*100.0), 2) if total > 0 else 0.0}%)\n"
        f"- Actual SQL NULL Records: {profile.null_records:,} ({null_pct:.2f}%)\n"
        f"- Empty Strings (\"\"): {profile.empty_string_records:,} ({empty_pct:.2f}%)\n"
        f"- Whitespace-Only Strings: {profile.whitespace_records:,} ({ws_pct:.2f}%)\n"
        f"- Configured Text Placeholders (e.g. 'N/A', 'NA', 'Unknown'): {profile.placeholder_records:,} ({ph_pct:.2f}%)\n\n"
        f"### Value Pattern Distribution:\n"
        f"{categories_text}\n\n"
        f"### Dominant Pattern:\n"
        f"`{profile.dominant_pattern_label or profile.dominant_pattern}` ({profile.dominant_percentage:.2f}%)\n\n"
        f"Generate SQL recommendations for detected issues (e.g. placeholders like 'N/A', empty strings, casing, numeric casting). "
        f"Every query that updates data MUST target `{workspace_table}` and NEVER the production table `{profile.table_name}`. Return valid JSON only."
    )


def _validate_ai_response_structure(data: Any) -> Tuple[bool, Optional[str]]:
    """
    Validates the top-level structure of an AI recommendation response.

    Returns (is_valid, error_message). If invalid, error_message describes
    the first structural problem found.
    """
    if not isinstance(data, dict):
        return False, "AI response is not a JSON object."

    if "summary" not in data:
        return False, "AI response is missing required top-level field: 'summary'."

    if not isinstance(data.get("summary"), str):
        return False, "AI response field 'summary' must be a string."

    if "recommendations" not in data:
        return False, "AI response is missing required top-level field: 'recommendations'."

    recs = data.get("recommendations")
    if not isinstance(recs, list):
        return False, "AI response field 'recommendations' must be a list."

    return True, None


def _validate_recommendation_item(
    item: Any,
    profile: ColumnProfileResult,
    workspace_table: str,
    dialect: str,
    seen_issue_ids: set,
    item_index: int,
) -> Tuple[Optional[ColumnQueryRecommendation], Optional[str]]:
    """
    Validates a single recommendation item from the AI response.

    Returns (recommendation, error_message). If invalid, recommendation is
    None and error_message describes the problem.
    """
    if not isinstance(item, dict):
        return None, f"recommendations[{item_index}] is not a JSON object."

    # Required fields — must be present and non-empty strings
    required_str_fields = [
        ("issue_id", "issue_id"),
        ("title", "title"),
        ("issue_detected", "issue_detected"),
        ("recommended_solution", "recommended_solution"),
        ("preview_query", "preview_query"),
        ("cleaning_query", "cleaning_query"),
        ("validation_query", "validation_query"),
        ("expected_result", "expected_result"),
        ("risks_and_assumptions", "risks_and_assumptions"),
    ]
    values: Dict[str, str] = {}
    for json_key, attr_name in required_str_fields:
        val = item.get(json_key)
        if val is None or not isinstance(val, str) or not val.strip():
            return None, f"recommendations[{item_index}] missing or empty required field: '{json_key}'."
        values[attr_name] = val.strip()

    # Optional fields with type validation
    category_val = item.get("category", "")
    if category_val is not None and not isinstance(category_val, str):
        return None, f"recommendations[{item_index}] field 'category' must be a string."
    category = str(category_val or "").strip()

    is_modifying_val = item.get("is_modifying", True)
    if not isinstance(is_modifying_val, bool):
        return None, f"recommendations[{item_index}] field 'is_modifying' must be a boolean."
    is_modifying = bool(is_modifying_val)

    affected_records_val = item.get("affected_records", 0)
    if not isinstance(affected_records_val, int) or isinstance(affected_records_val, bool):
        return None, f"recommendations[{item_index}] field 'affected_records' must be an integer."
    affected_records = int(affected_records_val)

    affected_percentage_val = item.get("affected_percentage", 0.0)
    if not isinstance(affected_percentage_val, (int, float)) or isinstance(affected_percentage_val, bool):
        return None, f"recommendations[{item_index}] field 'affected_percentage' must be a number."
    affected_percentage = float(affected_percentage_val)

    # Check for duplicate issue_id
    issue_id = values["issue_id"]
    if issue_id in seen_issue_ids:
        return None, f"recommendations[{item_index}] duplicate issue_id: '{issue_id}'."
    seen_issue_ids.add(issue_id)

    # Column name validation: exact identifier matching (no substring confusion)
    for sql_field in ("preview_query", "cleaning_query", "validation_query"):
        sql = values[sql_field]
        col_err = _validate_column_references(
            sql, profile, workspace_table, dialect, item_index, sql_field
        )
        if col_err is not None:
            return None, col_err

    # Statistical grounding: verify affected_records and affected_percentage
    # against profiling evidence when available
    stat_err = _validate_statistical_grounding(item, profile, item_index)
    if stat_err is not None:
        return None, stat_err

    # Check for contradictory suggestions: cleaning_query must not be a SELECT-only
    # when it claims to be modifying, and vice versa
    cleaning_sql = values["cleaning_query"]
    if is_modifying:
        cleaning_upper = cleaning_sql.strip().upper()
        if cleaning_upper.startswith("SELECT") and not cleaning_upper.startswith("SELECT ... INTO"):
            return None, (
                f"recommendations[{item_index}] claims is_modifying=true but cleaning_query "
                f"is a SELECT-only statement. Modifying recommendations must contain an UPDATE, "
                f"ALTER, DELETE, or INSERT statement."
            )

    return ColumnQueryRecommendation(
        issue_id=values["issue_id"],
        title=values["title"],
        issue_detected=values["issue_detected"],
        recommended_solution=values["recommended_solution"],
        preview_query=values["preview_query"],
        cleaning_query=values["cleaning_query"],
        validation_query=values["validation_query"],
        expected_result=values["expected_result"],
        risks_and_assumptions=values["risks_and_assumptions"],
        is_modifying=is_modifying,
        category=category,
        affected_records=affected_records,
        affected_percentage=affected_percentage,
    ), None


def _parse_ai_recommendations(
    raw_response: str,
    profile: ColumnProfileResult,
    workspace_table: str,
    dialect: str = "mysql",
) -> Tuple[List[ColumnQueryRecommendation], str]:
    """
    Parses and validates the JSON response returned by the AI model.

    Unlike the previous lenient parser, this version:
    - Requires the exact top-level key 'recommendations' (no 'issues' fallback)
    - Validates all required fields are present and non-empty
    - Validates data types for every field
    - Validates that SQL queries reference the workspace table and profiled column
    - Detects duplicate issue_id values
    - Detects contradictory is_modifying/cleaning_query combinations
    - Never fills missing fields with defaults; invalid items are rejected

    Raises ValueError with a sanitized message on any validation failure.
    Never exposes API credentials.
    """
    cleaned = raw_response.strip()

    # Phase 3: Markdown fences are prohibited. Reject responses wrapped in ``` fences.
    if cleaned.startswith("```") or "```" in cleaned:
        raise ValueError(
            "AI response contains Markdown code fences. "
            "Return ONLY a valid JSON object with no Markdown fences or explanatory text."
        )

    # Reject responses wrapped in explanatory text — extract only if a clean
    # JSON object is present, but do not hunt for JSON inside conversational text.
    if cleaned.startswith("{") and cleaned.rstrip().endswith("}"):
        json_text = cleaned
    else:
        # Look for a standalone JSON object; refuse conversational wrappers
        start_idx = cleaned.find("{")
        end_idx = cleaned.rfind("}")
        if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
            candidate = cleaned[start_idx : end_idx + 1]
            # Only accept if the candidate parses as complete JSON
            try:
                json.loads(candidate)
                json_text = candidate
            except json.JSONDecodeError:
                raise ValueError(
                    "AI response contains text outside the JSON object. "
                    "Return ONLY a valid JSON object with no intro or outro text."
                )
        else:
            raise ValueError(
                "AI response does not contain a valid JSON object. "
                "Return ONLY a valid JSON object."
            )

    try:
        data = json.loads(json_text)
    except json.JSONDecodeError as json_exc:
        safe_json_err = sanitize_error_message(str(json_exc), "")
        raise ValueError(f"AI response is not valid JSON: {safe_json_err}") from json_exc

    # Top-level structure validation
    is_valid, struct_err = _validate_ai_response_structure(data)
    if not is_valid:
        raise ValueError(struct_err)

    summary = str(data.get("summary") or "").strip()
    raw_recs = data.get("recommendations")

    if not isinstance(raw_recs, list) or len(raw_recs) == 0:
        raise ValueError("AI response 'recommendations' must be a non-empty list.")

    seen_issue_ids: set = set()
    recommendations: List[ColumnQueryRecommendation] = []
    validation_errors: List[str] = []

    for idx, item in enumerate(raw_recs):
        rec, err = _validate_recommendation_item(
            item, profile, workspace_table, dialect, seen_issue_ids, idx
        )
        if err is not None:
            validation_errors.append(err)
        else:
            recommendations.append(rec)

    if validation_errors:
        # Report all validation errors at once; do not partially accept
        joined = "; ".join(validation_errors)
        raise ValueError(f"AI response validation failed: {joined}")

    return recommendations, summary


def send_ai_chat_message(
    profile: ColumnProfileResult,
    config: AIColumnConfig,
    messages: List[Dict[str, str]],
    workspace_table: Optional[str] = None,
    dialect: str = "mysql",
    timeout: float = 60.0,
    max_tokens: int = 8000,
    response_format: Optional[Dict[str, str]] = None,
    stream: bool = True,
    on_delta: Optional[Callable[[str], None]] = None,
    system_prompt: Optional[str] = None,
) -> Tuple[str, Optional[str]]:
    """
    Sends chat messages to the AI and returns the full response text.
    When supported by the endpoint, ``on_delta`` receives the accumulated
    response as each streamed token arrives. A non-streaming retry is used
    only when the endpoint explicitly rejects streaming before any content is
    received; partial responses are always reported as errors.
    Never exposes raw API keys in errors or logs.
    Returns (response_text, error_message). On error, response_text is empty.
    """
    target_workspace = workspace_table or f"{profile.table_name}__cleaning_workspace"
    endpoint_host = urlparse(config.base_url.strip()).netloc or config.base_url.strip() if config and config.base_url else ""

    # Build system prompt
    sys_prompt = system_prompt or build_system_prompt(dialect, target_workspace)
    all_messages = [{"role": "system", "content": sys_prompt}] + messages

    # Build request payload
    request_payload: Dict[str, Any] = {
        "model": config.model_name.strip(),
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "messages": all_messages,
    }
    if response_format:
        request_payload["response_format"] = response_format

    start_t = time.perf_counter()

    def _create_completion(client: Any, use_stream: bool) -> Any:
        return client.chat.completions.create(
            model=request_payload["model"],
            messages=request_payload["messages"],
            temperature=request_payload["temperature"],
            max_tokens=request_payload["max_tokens"],
            response_format=request_payload.get("response_format"),
            stream=use_stream,
        )

    def _streaming_is_unsupported(exc: Exception) -> bool:
        """Returns true only for provider errors that explicitly reject stream."""
        message = str(exc).lower()
        return "stream" in message and any(
            marker in message
            for marker in ("unsupported", "not support", "invalid", "unknown", "not allowed")
        )

    try:
        from openai import OpenAI

        base_url = config.base_url.strip() if config.base_url else None
        if base_url and ("api.openai.com" in base_url and base_url.endswith("/v1")):
            base_url = None

        client = OpenAI(
            api_key=config.api_key.strip(),
            base_url=base_url,
            timeout=timeout,
        )

        if stream:
            full_response = ""
            try:
                response = _create_completion(client, use_stream=True)
                for chunk in response:
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    chunk_content = getattr(choices[0].delta, "content", None)
                    if chunk_content:
                        full_response += chunk_content
                        if on_delta:
                            on_delta(full_response)
            except Exception as exc:
                # Do not turn partial JSON/text into a valid response. Retry only
                # if this endpoint explicitly rejects streaming before output.
                if not full_response and _streaming_is_unsupported(exc):
                    try:
                        response = _create_completion(client, use_stream=False)
                        raw_reply = ""
                        if response and response.choices and response.choices[0].message:
                            raw_reply = (response.choices[0].message.content or "").strip()
                        return raw_reply, None
                    except Exception as fallback_exc:
                        safe_err = sanitize_error_message(str(fallback_exc), config.api_key)
                        return "", safe_err
                safe_err = sanitize_error_message(str(exc), config.api_key)
                return "", safe_err
            return full_response, None
        else:
            response = _create_completion(client, use_stream=False)
            raw_reply = ""
            if response and response.choices and response.choices[0].message:
                raw_reply = (response.choices[0].message.content or "").strip()
            return raw_reply, None

    except Exception as exc:
        safe_err = sanitize_error_message(str(exc), config.api_key)
        return "", safe_err


def analyze_column_with_ai(
    profile: ColumnProfileResult,
    config: AIColumnConfig,
    workspace_table: Optional[str] = None,
    dialect: str = "mysql",
    timeout: float = 60.0,
    max_tokens: int = 8000,
    response_format: Optional[Dict[str, str]] = None,
) -> AIAnalysisResult:
    """
    Executes AI-powered column analysis and SQL query recommendations.
    Uses OpenAI-compatible client interface supported by NVIDIA NIM, OpenAI, Groq, Ollama, etc.
    Never exposes raw API keys in errors or logs.
    Captures exact request payload, HTTP status, endpoint host, finish reason, and duration.
    Distinguishes transport errors, JSON parse errors, schema validation failures,
    and truncated responses. Falls back to grounded rule-based recommendations only
    when the AI endpoint is unavailable or returns unusable output; fallback results
    are always labelled source="rules_fallback" and success=False.
    """
    target_workspace = workspace_table or f"{profile.table_name}__cleaning_workspace"
    endpoint_host = urlparse(config.base_url.strip()).netloc or config.base_url.strip() if config and config.base_url else ""

    # Validate that we have profiling data
    if not profile or profile.total_records <= 0:
        return AIAnalysisResult(
            table_name=profile.table_name if profile else "",
            column_name=profile.column_name if profile else "",
            workspace_table=target_workspace,
            dialect=dialect,
            recommendations=[],
            summary_narrative="Table contains 0 records. No issues detected.",
            success=True,
            source="rules_fallback",
            payload_debug=[{
                "request_index": 1,
                "model": (config.model_name.strip() if config and config.model_name else "N/A"),
                "endpoint_host": endpoint_host,
                "duration_ms": 0,
                "duration_str": "0.00s",
                "http_status": "Not Sent (Empty Table)",
                "status": "not_sent_empty_table",
                "status_description": "Table contains 0 records. No column data to send to AI.",
                "payload": {"messages": []},
            }],
            http_status=None,
            endpoint_host=endpoint_host,
            duration_ms=0,
        )

    # Build prompts
    sys_prompt = build_system_prompt(dialect, target_workspace)
    usr_prompt = build_user_prompt(profile, target_workspace, dialect)
    messages = [
        {"role": "system", "content": sys_prompt},
        {"role": "user", "content": usr_prompt},
    ]

    # If configuration is missing, use grounded rule-based recommendations and record prepared payload
    if not config or not config.is_configured:
        unconf_debug = {
            "request_index": 1,
            "model": (config.model_name.strip() if config and config.model_name else "(unconfigured)"),
            "endpoint_host": endpoint_host,
            "duration_ms": 0,
            "duration_str": "0.00s",
            "http_status": "Not Sent (Unconfigured)",
            "status": "not_sent_unconfigured",
            "status_description": "AI endpoint is not configured in .env. Displaying the exact request payload prepared for the AI model.",
            "payload": {
                "model": (config.model_name.strip() if config and config.model_name else "gpt-4o"),
                "temperature": 0.1,
                "max_tokens": max_tokens,
                "messages": messages,
            },
        }
        grounded_recs = generate_grounded_recommendations(profile, target_workspace, dialect)
        return AIAnalysisResult(
            table_name=profile.table_name,
            column_name=profile.column_name,
            workspace_table=target_workspace,
            dialect=dialect,
            recommendations=grounded_recs,
            summary_narrative=(
                f"Generated {len(grounded_recs)} grounded SQL query recommendations directly from "
                f"profiler metrics (AI endpoint not configured)."
            ),
            success=False,
            error_message="AI endpoint is not configured in .env",
            source="rules_fallback",
            payload_debug=[unconf_debug],
            http_status=None,
            endpoint_host=endpoint_host,
            duration_ms=0,
        )

    # Final exact request payload prepared immediately before the API call
    request_payload: Dict[str, Any] = {
        "model": config.model_name.strip(),
        "temperature": 0.1,
        "max_tokens": max_tokens,
        "messages": messages,
    }
    if response_format:
        request_payload["response_format"] = response_format

    # Monotonic timer started immediately before the HTTP request.
    start_t = time.perf_counter()
    start_ts = time.strftime("%Y-%m-%d %H:%M:%S")

    # Initialize for use in except blocks if the API call fails before they are set.
    finish_reason = None
    truncated = False
    token_usage = None

    try:
        from openai import OpenAI

        base_url = config.base_url.strip() if config.base_url else None
        # Omit default OpenAI URL to let library use standard routing
        if base_url and ("api.openai.com" in base_url and base_url.endswith("/v1")):
            base_url = None

        client = OpenAI(
            api_key=config.api_key.strip(),
            base_url=base_url,
            timeout=timeout,
        )

        response = client.chat.completions.create(
            model=request_payload["model"],
            messages=request_payload["messages"],
            temperature=request_payload["temperature"],
            max_tokens=request_payload["max_tokens"],
            response_format=request_payload.get("response_format"),
        )

        duration_ms = int((time.perf_counter() - start_t) * 1000)
        duration_str = f"{duration_ms / 1000.0:.2f}s"

        # Capture finish reason to detect truncation
        finish_reason = None
        truncated = False
        if response and response.choices:
            fr = getattr(response.choices[0], "finish_reason", None)
            if isinstance(fr, str):
                finish_reason = fr
                if finish_reason == "length":
                    truncated = True

        raw_reply = ""
        if response and response.choices and response.choices[0].message:
            msg = response.choices[0].message
            raw_reply = (msg.content or "").strip()
            if not raw_reply and hasattr(msg, "reasoning_content"):
                raw_reply = (getattr(msg, "reasoning_content", "") or "").strip()

        # Capture token usage from the provider response
        token_usage = None
        usage = getattr(response, "usage", None)
        if usage:
            pt = getattr(usage, "prompt_tokens", None)
            ct = getattr(usage, "completion_tokens", None)
            tt = getattr(usage, "total_tokens", None)
            if all(v is None or isinstance(v, int) for v in (pt, ct, tt)):
                token_usage = {
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "total_tokens": tt,
                }

        if not raw_reply:
            raise ValueError("AI endpoint returned an empty completion response.")

        # Detect truncated output before attempting to parse JSON.
        if truncated:
            raise ValueError(
                f"AI response truncated (finish_reason={finish_reason}, "
                f"max_tokens={max_tokens}). Output is incomplete."
            )

        # Parse JSON; keep JSON decode errors distinct from transport errors.
        try:
            ai_recs, summary = _parse_ai_recommendations(raw_reply, profile, target_workspace, dialect)
        except json.JSONDecodeError as json_exc:
            safe_json_err = sanitize_error_message(str(json_exc), config.api_key)
            raise ValueError(
                f"AI response is not valid JSON: {safe_json_err}"
            ) from json_exc

        if not ai_recs:
            # No usable recommendations parsed; treat as unsuccessful AI result.
            raise ValueError(
                "AI response parsed as JSON but contained no usable recommendations."
            )

        debug_entry = {
            "request_index": 1,
            "model": config.model_name.strip(),
            "endpoint_host": endpoint_host,
            "duration_ms": duration_ms,
            "duration_str": duration_str,
            "http_status": "200 OK",
            "status": "sent_success",
            "status_description": f"Successfully completed in {duration_str} (HTTP 200 OK).",
            "finish_reason": finish_reason,
            "truncated": truncated,
            "token_usage": token_usage,
            "payload": request_payload,
        }

        return AIAnalysisResult(
            table_name=profile.table_name,
            column_name=profile.column_name,
            workspace_table=target_workspace,
            dialect=dialect,
            recommendations=ai_recs,
            summary_narrative=summary or f"AI analyzed {len(ai_recs)} data-quality issues in {duration_str}.",
            success=True,
            source="ai",
            payload_debug=[debug_entry],
            http_status=200,
            endpoint_host=endpoint_host,
            duration_ms=duration_ms,
            finish_reason=finish_reason,
            truncated=truncated,
        )

    except ValueError as exc:
        # JSON parse errors, truncation, empty response, no recommendations —
        # these are AI-content errors, not transport errors.
        duration_ms = int((time.perf_counter() - start_t) * 1000)
        duration_str = f"{duration_ms / 1000.0:.2f}s"
        safe_err = sanitize_error_message(str(exc), config.api_key)
        logger.warning("AI analysis content error (%s); not presenting fallback as AI-generated.", safe_err)

        debug_entry = {
            "request_index": 1,
            "model": config.model_name.strip(),
            "endpoint_host": endpoint_host,
            "duration_ms": duration_ms,
            "duration_str": duration_str,
            "http_status": None,
            "status": "content_error",
            "status_description": f"AI content error in {duration_str}: {safe_err}",
            "sanitized_error_details": safe_err,
            "raw_reply_preview": sanitize_error_message(raw_reply, config.api_key)[:500] if raw_reply else None,
            "token_usage": token_usage,
            "payload": request_payload,
        }

        # Generate grounded rule-based recommendations (clearly NOT AI-generated).
        grounded_recs = generate_grounded_recommendations(profile, target_workspace, dialect)
        return AIAnalysisResult(
            table_name=profile.table_name,
            column_name=profile.column_name,
            workspace_table=target_workspace,
            dialect=dialect,
            recommendations=grounded_recs,
            summary_narrative=(
                f"AI analysis produced unusable output: {safe_err}. "
                f"Generated {len(grounded_recs)} rule-based recommendations (not AI-generated)."
            ),
            success=False,
            error_message=f"Content error: {safe_err}",
            source="rules_fallback",
            payload_debug=[debug_entry],
            http_status=None,
            endpoint_host=endpoint_host,
            duration_ms=duration_ms,
            finish_reason=finish_reason,
            truncated=truncated,
        )

    except Exception as exc:
        # Transport-level errors (network, HTTP 4xx/5xx, auth, etc.)
        duration_ms = int((time.perf_counter() - start_t) * 1000)
        duration_str = f"{duration_ms / 1000.0:.2f}s"
        http_status = getattr(exc, "status_code", None)
        safe_err = sanitize_error_message(str(exc), config.api_key)

        if not http_status:
            m = re.search(r"\b(4\d\d|5\d\d)\b", safe_err)
            if m:
                http_status = int(m.group(1))

        status_label = f"HTTP {http_status}" if http_status else "Request Error"
        logger.warning("AI query transport error (%s); not presenting fallback as AI-generated.", safe_err)

        debug_entry = {
            "request_index": 1,
            "model": config.model_name.strip(),
            "endpoint_host": endpoint_host,
            "duration_ms": duration_ms,
            "duration_str": duration_str,
            "http_status": status_label,
            "status": "transport_error",
            "status_description": f"Request failed in {duration_str} ({status_label}): {safe_err}",
            "sanitized_error_details": safe_err,
            "token_usage": token_usage,
            "payload": request_payload,
        }

        # Generate grounded rule-based recommendations (clearly NOT AI-generated).
        grounded_recs = generate_grounded_recommendations(profile, target_workspace, dialect)
        return AIAnalysisResult(
            table_name=profile.table_name,
            column_name=profile.column_name,
            workspace_table=target_workspace,
            dialect=dialect,
            recommendations=grounded_recs,
            summary_narrative=(
                f"AI analysis transport error ({status_label}): {safe_err}. "
                f"Generated {len(grounded_recs)} rule-based recommendations (not AI-generated)."
            ),
            success=False,
            error_message=f"{status_label}: {safe_err}",
            source="rules_fallback",
            payload_debug=[debug_entry],
            http_status=http_status,
            endpoint_host=endpoint_host,
            duration_ms=duration_ms,
        )

