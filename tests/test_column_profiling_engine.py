"""
Tests for Column Profiling Engine
tests/test_column_profiling_engine.py
"""

import datetime
from decimal import Decimal
import pytest
from sqlalchemy import create_engine, text

from src.column_profiling_engine import (
    ValuePatternCategory,
    CATEGORY_DISPLAY_LABELS,
    classify_value,
    profile_values,
    profile_column,
    ColumnProfileResult,
)


@pytest.fixture
def sqlite_profile_engine():
    """Provides an in-memory SQLite database populated with a test table."""
    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE customers (
                id INTEGER PRIMARY KEY,
                name TEXT,
                balance TEXT,
                signup_date TEXT,
                is_active TEXT,
                code TEXT
            )
        """))
        # Insert 10 records with diverse and repeated patterns
        conn.execute(text("""
            INSERT INTO customers (id, name, balance, signup_date, is_active, code) VALUES
            (1, 'Alice Smith', '1250.50', '2023-01-15', 'true', 'VIP-100'),
            (2, 'Bob Jones', '-45.00', '2023-02-20', 'false', 'REG-200'),
            (3, 'Charlie', '$2,500.00', '15/03/2023', 'yes', 'VIP-100'),
            (4, 'O''Connor', '0', '15-Apr-2023', 'no', '***'),
            (5, 'User123', '100', '2023-05-01', 'TRUE', 'REG-200'),
            (6, 'Diana Prince', '50%', NULL, 'FALSE', '---'),
            (7, '', '99999', '2023-07-04', '1', 'VIP-100'),
            (8, '   ', NULL, '2023-08-10', '0', NULL),
            (9, NULL, '100', '2023-09-12', 'Y', 'CODE_X'),
            (10, 'Eve Adams', '-0.75', '2023-10-31', 'N', 'A1-B2#')
        """))
        conn.commit()
    return engine


def test_category_enum_and_display_labels():
    """Verify all 13 categories are defined in the enum and have human-readable labels."""
    expected_categories = {
        "numeric_only",
        "alphabetic_only",
        "alphanumeric",
        "numeric_special",
        "text_special",
        "mixed",
        "date_like",
        "boolean_like",
        "empty_string",
        "whitespace_only",
        "sql_null",
        "missing_placeholder",
        "other",
    }
    actual_categories = {cat.value for cat in ValuePatternCategory}
    assert actual_categories == expected_categories
    assert len(CATEGORY_DISPLAY_LABELS) == 13
    for cat in ValuePatternCategory:
        assert cat.value in CATEGORY_DISPLAY_LABELS


def test_classify_missing_value_placeholders_and_distinctions():
    """Verify missing placeholders (N/A, NA, etc.) are distinct from SQL NULL, empty strings, and whitespace."""
    # Actual SQL NULL (must NOT be placeholder)
    assert classify_value(None) == ValuePatternCategory.SQL_NULL
    assert classify_value(float("nan")) == ValuePatternCategory.SQL_NULL

    # Empty string (must NOT be placeholder)
    assert classify_value("") == ValuePatternCategory.EMPTY_STRING

    # Whitespace-only (must NOT be placeholder)
    assert classify_value("   ") == ValuePatternCategory.WHITESPACE_ONLY
    assert classify_value("\t\n") == ValuePatternCategory.WHITESPACE_ONLY

    # Configurable missing placeholders: case-insensitive and trimmed
    assert classify_value("N/A") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("n/a") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("  N/A  ") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("NA") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("na") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("Not Applicable") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("not applicable") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("Unknown") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("unknown") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("None") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("none") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("null") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("NaN") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("-") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("--") == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("?") == ValuePatternCategory.MISSING_PLACEHOLDER

    # Ordinary text (must NOT be placeholder)
    assert classify_value("Hello World") == ValuePatternCategory.ALPHABETIC_ONLY
    assert classify_value("Active") == ValuePatternCategory.ALPHABETIC_ONLY
    assert classify_value("Department A") == ValuePatternCategory.ALPHABETIC_ONLY
    assert classify_value("Dept 101") == ValuePatternCategory.ALPHANUMERIC

    # Numeric values (must NOT be placeholder)
    assert classify_value(100) == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value(95.5) == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("100") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("95.5") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("-50") == ValuePatternCategory.NUMERIC_ONLY


def test_classify_missing_value_placeholders_configurable():
    """Verify custom missing placeholder list overrides or configures placeholder recognition."""
    custom_list = ["TBD", "MISSING_VALUE", "NOT_SET"]

    # In custom list
    assert classify_value("TBD", missing_placeholders=custom_list) == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("  tbd  ", missing_placeholders=custom_list) == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("missing_value", missing_placeholders=custom_list) == ValuePatternCategory.MISSING_PLACEHOLDER
    assert classify_value("NOT_SET", missing_placeholders=custom_list) == ValuePatternCategory.MISSING_PLACEHOLDER

    # N/A is not in custom list, so it falls back to text_special (letters + slash)
    assert classify_value("N/A", missing_placeholders=custom_list) == ValuePatternCategory.TEXT_SPECIAL


def test_profile_performance_score_text_24_na_occurrences():
    """Verify performance_score_text classifies 24 occurrences of N/A as placeholders, not SQL NULLs."""
    # 24 occurrences of 'N/A' (placeholders)
    # 5 numeric scores ('95', '88.5', '100', '72', '80')
    # 3 text reviews ('Exceeds Expectations', 'Needs Improvement', 'Solid')
    # 2 SQL NULLs (None)
    # 1 empty string ('')
    # Total = 35 records
    data = (
        ["N/A"] * 24 +
        ["95", "88.5", "100", "72", "80"] +
        ["Exceeds Expectations", "Needs Improvement", "Solid"] +
        [None, None] +
        [""]
    )

    result = profile_values(data, column_name="performance_score_text")

    assert result.total_records == 35
    assert result.column_name == "performance_score_text"

    # Distinct placeholder vs SQL NULL counts
    assert result.counts[ValuePatternCategory.MISSING_PLACEHOLDER.value] == 24
    assert result.counts[ValuePatternCategory.SQL_NULL.value] == 2
    assert result.counts[ValuePatternCategory.EMPTY_STRING.value] == 1
    assert result.counts[ValuePatternCategory.NUMERIC_ONLY.value] == 5
    assert result.counts[ValuePatternCategory.ALPHABETIC_ONLY.value] == 3

    # Properties
    assert result.placeholder_records == 24
    assert result.null_records == 2
    assert result.empty_string_records == 1
    assert result.non_null_records == 33  # 35 - 2 SQL NULLs
    assert result.missing_records == 27   # 2 SQL NULL + 1 empty string + 24 placeholders

    # Exact percentages (denominator = 35 total records scanned)
    expected_placeholder_pct = round((24 / 35) * 100.0, 2)  # 68.57%
    expected_null_pct = round((2 / 35) * 100.0, 2)         # 5.71%
    assert result.percentages[ValuePatternCategory.MISSING_PLACEHOLDER.value] == expected_placeholder_pct
    assert result.percentages[ValuePatternCategory.SQL_NULL.value] == expected_null_pct

    # Dominant pattern is missing_placeholder with 68.57%
    assert result.dominant_pattern == ValuePatternCategory.MISSING_PLACEHOLDER.value
    assert result.dominant_pattern_label == "Missing-Value Placeholders"
    assert result.dominant_pattern_percentage == expected_placeholder_pct

    # Every record belongs to exactly one category
    sum_counts = sum(result.counts.values())
    assert sum_counts == 35


def test_classify_null_empty_and_whitespace():
    """Verify SQL NULL, empty strings, and whitespace-only strings are correctly classified."""
    # SQL NULL
    assert classify_value(None) == ValuePatternCategory.SQL_NULL
    assert classify_value(float("nan")) == ValuePatternCategory.SQL_NULL

    # Empty string
    assert classify_value("") == ValuePatternCategory.EMPTY_STRING

    # Whitespace-only
    assert classify_value(" ") == ValuePatternCategory.WHITESPACE_ONLY
    assert classify_value("   ") == ValuePatternCategory.WHITESPACE_ONLY
    assert classify_value("\t\n") == ValuePatternCategory.WHITESPACE_ONLY


def test_classify_numeric_only():
    """Verify integers, decimals, negative numbers, and scientific notation are classified as numeric only."""
    # Python numeric types
    assert classify_value(42) == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value(-10) == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value(3.14159) == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value(-0.005) == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value(Decimal("123.45")) == ValuePatternCategory.NUMERIC_ONLY

    # Numeric strings
    assert classify_value("123") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("-456") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("+789") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("0") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("3.14") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("-0.50") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("+99.99") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("1e6") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value("-2.5e-3") == ValuePatternCategory.NUMERIC_ONLY


def test_classify_alphabetic_only():
    """Verify pure letters (including spaces between words) are classified as alphabetic only."""
    assert classify_value("hello") == ValuePatternCategory.ALPHABETIC_ONLY
    assert classify_value("John Doe") == ValuePatternCategory.ALPHABETIC_ONLY
    assert classify_value("New York City") == ValuePatternCategory.ALPHABETIC_ONLY
    assert classify_value("ABC") == ValuePatternCategory.ALPHABETIC_ONLY


def test_classify_alphanumeric():
    """Verify values with letters and numbers (no special symbols) are classified as alphanumeric."""
    assert classify_value("User123") == ValuePatternCategory.ALPHANUMERIC
    assert classify_value("Room 402") == ValuePatternCategory.ALPHANUMERIC
    assert classify_value("AB12CD") == ValuePatternCategory.ALPHANUMERIC
    assert classify_value("7UP") == ValuePatternCategory.ALPHANUMERIC


def test_classify_numeric_special():
    """Verify numbers with formatting symbols, currency, and percentages are classified as numeric special."""
    assert classify_value("$1,234.56") == ValuePatternCategory.NUMERIC_SPECIAL
    assert classify_value("1,000,000") == ValuePatternCategory.NUMERIC_SPECIAL
    assert classify_value("45%") == ValuePatternCategory.NUMERIC_SPECIAL
    assert classify_value("-99.9%") == ValuePatternCategory.NUMERIC_SPECIAL
    assert classify_value("(555) 123-4567") == ValuePatternCategory.NUMERIC_SPECIAL
    assert classify_value("+1-800-555-0199") == ValuePatternCategory.NUMERIC_SPECIAL
    assert classify_value("192.168.1.1") == ValuePatternCategory.NUMERIC_SPECIAL


def test_classify_text_special():
    """Verify text with symbols/punctuation (no digits) is classified as text special."""
    assert classify_value("hello-world") == ValuePatternCategory.TEXT_SPECIAL
    assert classify_value("O'Connor") == ValuePatternCategory.TEXT_SPECIAL
    assert classify_value("user@domain") == ValuePatternCategory.TEXT_SPECIAL
    assert classify_value("Hello, World!") == ValuePatternCategory.TEXT_SPECIAL
    assert classify_value("first_name") == ValuePatternCategory.TEXT_SPECIAL


def test_classify_mixed():
    """Verify values containing letters, digits, and special symbols are classified as mixed."""
    assert classify_value("user123@domain.com") == ValuePatternCategory.MIXED
    assert classify_value("VIP-100") == ValuePatternCategory.MIXED
    assert classify_value("Flat#2B") == ValuePatternCategory.MIXED
    assert classify_value("Pass@2024") == ValuePatternCategory.MIXED
    assert classify_value("A1_B2") == ValuePatternCategory.MIXED


def test_classify_date_like():
    """Verify date-like strings and datetime objects are correctly classified."""
    # Python datetime objects
    assert classify_value(datetime.date(2023, 1, 15)) == ValuePatternCategory.DATE_LIKE
    assert classify_value(datetime.datetime(2023, 1, 15, 14, 30)) == ValuePatternCategory.DATE_LIKE

    # ISO date strings
    assert classify_value("2023-01-15") == ValuePatternCategory.DATE_LIKE
    assert classify_value("2023-01-15 10:30:00") == ValuePatternCategory.DATE_LIKE
    assert classify_value("2023/01/15") == ValuePatternCategory.DATE_LIKE
    assert classify_value("2023.01.15") == ValuePatternCategory.DATE_LIKE

    # Separated dates
    assert classify_value("15/03/2023") == ValuePatternCategory.DATE_LIKE
    assert classify_value("03/15/2023") == ValuePatternCategory.DATE_LIKE
    assert classify_value("15-03-2023") == ValuePatternCategory.DATE_LIKE

    # Textual month dates
    assert classify_value("15 Jan 2023") == ValuePatternCategory.DATE_LIKE
    assert classify_value("15-January-2023") == ValuePatternCategory.DATE_LIKE
    assert classify_value("January 15, 2023") == ValuePatternCategory.DATE_LIKE


def test_classify_boolean_like():
    """Verify native booleans and boolean-like strings are correctly classified."""
    # Python bool instances
    assert classify_value(True) == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value(False) == ValuePatternCategory.BOOLEAN_LIKE

    # Canonical string tokens
    assert classify_value("true") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("TRUE") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("false") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("yes") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("NO") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("Y") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("n") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("T") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("f") == ValuePatternCategory.BOOLEAN_LIKE

    # Declared boolean column type with 0 / 1
    assert classify_value("1", declared_type="boolean") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("0", declared_type="tinyint(1)") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value(1, declared_type="bool") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value(0, declared_type="bit(1)") == ValuePatternCategory.BOOLEAN_LIKE

    # In generic VARCHAR/INT columns, 0 and 1 are Numeric Only
    assert classify_value("1", declared_type="varchar(10)") == ValuePatternCategory.NUMERIC_ONLY
    assert classify_value(1, declared_type="int") == ValuePatternCategory.NUMERIC_ONLY


def test_classify_other_unclassified():
    """Verify special characters only or unclassified symbols are categorized as other."""
    assert classify_value("***") == ValuePatternCategory.OTHER
    assert classify_value("---") == ValuePatternCategory.OTHER
    assert classify_value("#@!") == ValuePatternCategory.OTHER
    assert classify_value("///") == ValuePatternCategory.OTHER


def test_date_and_boolean_precedence_over_generic_patterns():
    """Verify dates and booleans are not misclassified as generic numeric, text, or mixed."""
    # "2023-01-15" contains hyphens and numbers, but MUST be date_like, NOT numeric_special
    assert classify_value("2023-01-15") == ValuePatternCategory.DATE_LIKE

    # "15-Jan-2023" contains letters, digits, and hyphen, but MUST be date_like, NOT mixed
    assert classify_value("15-Jan-2023") == ValuePatternCategory.DATE_LIKE

    # "true" contains only letters, but MUST be boolean_like, NOT alphabetic_only
    assert classify_value("true") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("false") == ValuePatternCategory.BOOLEAN_LIKE
    assert classify_value("yes") == ValuePatternCategory.BOOLEAN_LIKE


def test_profile_values_repeated_records_and_distribution():
    """Verify that repeated values are counted and percentages calculated accurately."""
    data = [
        "100", "100", "100", "100",  # 4 Numeric (40%)
        "Hello", "Hello", "World",    # 3 Alphabetic (30%)
        None, None,                    # 2 SQL NULL (20%)
        "",                            # 1 Empty string (10%)
    ]
    res = profile_values(data, column_name="sample_col")

    assert res.total_records == 10
    assert res.non_null_count == 8
    assert res.null_count == 2
    assert res.missing_count == 3  # 2 NULLs + 1 empty string
    assert res.percentage_denominator == "total_records_scanned"

    # Exact counts
    assert res.counts["numeric_only"] == 4
    assert res.counts["alphabetic_only"] == 3
    assert res.counts["sql_null"] == 2
    assert res.counts["empty_string"] == 1
    assert res.counts["date_like"] == 0

    # Exact percentages
    assert res.percentages["numeric_only"] == 40.0
    assert res.percentages["alphabetic_only"] == 30.0
    assert res.percentages["sql_null"] == 20.0
    assert res.percentages["empty_string"] == 10.0

    # Dominant pattern
    assert res.dominant_pattern == "numeric_only"
    assert res.dominant_pattern_label == "Numeric only"
    assert res.dominant_pattern_percentage == 40.0


def test_profile_values_empty_dataset_safe():
    """Verify profiling an empty collection returns zeros and None dominant pattern safely."""
    res = profile_values([], column_name="empty_col")

    assert res.total_records == 0
    assert res.non_null_count == 0
    assert res.null_count == 0
    assert res.missing_count == 0
    assert res.dominant_pattern is None
    assert res.dominant_pattern_label is None
    assert res.dominant_pattern_percentage == 0.0

    for cat in ValuePatternCategory:
        assert res.counts[cat.value] == 0
        assert res.percentages[cat.value] == 0.0


def test_profile_column_sqlite_e2e(sqlite_profile_engine):
    """Verify end-to-end database column profiling with streamed batching on SQLite."""
    # Test 'balance' column
    # Records: '1250.50' (numeric), '-45.00' (numeric), '$2,500.00' (numeric_special),
    #          '0' (numeric), '100' (numeric), '50%' (numeric_special),
    #          '99999' (numeric), NULL (sql_null), '100' (numeric), '-0.75' (numeric)
    # Total = 10 rows:
    # 7 numeric_only ('1250.50', '-45.00', '0', '100', '99999', '100', '-0.75') -> 70.0%
    # 2 numeric_special ('$2,500.00', '50%') -> 20.0%
    # 1 sql_null (NULL) -> 10.0%
    res = profile_column(
        engine=sqlite_profile_engine,
        database=None,
        table_name="customers",
        column_name="balance",
        batch_size=3,  # Intentionally small batch to verify multi-batch streaming
    )

    assert res.success is True
    assert res.error_message is None
    assert res.total_records == 10
    assert res.null_count == 1
    assert res.non_null_count == 9
    assert res.missing_count == 1

    assert res.counts["numeric_only"] == 7
    assert res.percentages["numeric_only"] == 70.0

    assert res.counts["numeric_special"] == 2
    assert res.percentages["numeric_special"] == 20.0

    assert res.counts["sql_null"] == 1
    assert res.percentages["sql_null"] == 10.0

    assert res.dominant_pattern == "numeric_only"
    assert res.dominant_pattern_percentage == 70.0
    assert res.is_exact is True
    assert res.dialect == "sqlite"


def test_profile_column_dates_and_booleans_e2e(sqlite_profile_engine):
    """Verify date_like and boolean_like columns in database table."""
    # Test 'signup_date' column (9 dates, 1 NULL)
    res_date = profile_column(
        engine=sqlite_profile_engine,
        database=None,
        table_name="customers",
        column_name="signup_date",
    )
    assert res_date.success is True
    assert res_date.total_records == 10
    assert res_date.counts["date_like"] == 9
    assert res_date.percentages["date_like"] == 90.0
    assert res_date.counts["sql_null"] == 1
    assert res_date.dominant_pattern == "date_like"

    # Test 'is_active' column (all 10 are boolean-like: true, false, yes, no, TRUE, FALSE, 1, 0, Y, N)
    res_bool = profile_column(
        engine=sqlite_profile_engine,
        database=None,
        table_name="customers",
        column_name="is_active",
    )
    assert res_bool.success is True
    assert res_bool.total_records == 10
    assert res_bool.counts["boolean_like"] == 10
    assert res_bool.percentages["boolean_like"] == 100.0
    assert res_bool.dominant_pattern == "boolean_like"


def test_profile_column_validation_errors(sqlite_profile_engine):
    """Verify clean error results when table or column does not exist or engine is missing."""
    # No engine
    res_no_eng = profile_column(None, None, "customers", "name")
    assert res_no_eng.success is False
    assert "No active database engine" in res_no_eng.error_message

    # Invalid table
    res_bad_tbl = profile_column(sqlite_profile_engine, None, "non_existent_table", "name")
    assert res_bad_tbl.success is False
    assert "Table 'non_existent_table' does not exist" in res_bad_tbl.error_message

    # Invalid column
    res_bad_col = profile_column(sqlite_profile_engine, None, "customers", "non_existent_col")
    assert res_bad_col.success is False
    assert "Column 'non_existent_col' does not exist" in res_bad_col.error_message


def test_result_to_dict_serialization():
    """Verify ColumnProfileResult can be converted to dictionary for UI or JSON export."""
    data = ["test", 123, None]
    res = profile_values(data, column_name="mixed_col")
    d = res.to_dict()

    assert isinstance(d, dict)
    assert d["column_name"] == "mixed_col"
    assert d["total_records"] == 3
    assert "counts" in d
    assert "percentages" in d
    assert d["counts"]["alphabetic_only"] == 1
    assert d["counts"]["numeric_only"] == 1
    assert d["counts"]["sql_null"] == 1


def test_profile_column_db_name_alias(sqlite_profile_engine):
    """Verify profile_column supports db_name keyword argument as an alias for database."""
    res = profile_column(
        engine=sqlite_profile_engine,
        db_name=None,
        table_name="customers",
        column_name="balance",
    )
    assert res.success is True
    assert res.column_name == "balance"
    assert res.total_records == 10

