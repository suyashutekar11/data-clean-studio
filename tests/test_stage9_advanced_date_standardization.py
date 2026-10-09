"""
Comprehensive test suite for Stage 9: Advanced Date Standardization (Deterministic Rules 1 & 2).
Validates all Section 20 mandatory test cases, output formats, scan percentages, collision-safe
column generation, preview, database writer, and original-column preservation.
"""

import pytest
from unittest.mock import MagicMock, patch

from src.advanced_date_standardization import (
    SUPPORTED_OUTPUT_FORMATS,
    ALLOWED_SCAN_PERCENTAGES,
    validate_date,
    extract_four_digit_year,
    parse_text_month_date,
    parse_numeric_date,
    format_standardized_date,
    parse_and_standardize_record,
    detect_date_like_value,
    get_safe_output_column_name,
    detect_date_columns,
    preview_column_standardization,
    standardize_column,
)


# ============================================================
# 1. Section 20: Text Month Cases (Rule 1)
# ============================================================

@pytest.mark.parametrize(
    "raw_input,expected",
    [
        ("15 August 2026", "2026-08-15"),
        ("15 August 2025", "2025-08-15"),
        ("25 December 2026", "2026-12-25"),
        ("Aug-15-2026", "2026-08-15"),
        ("15-Nov-2026", "2026-11-15"),
        ("2026-Nov-25", "2026-11-25"),
        ("25 Dec 2026", "2026-12-25"),
        ("  15   JANUARY   2026  ", "2026-01-15"),
        ("Sept 09, 2026", "2026-09-09"),
        ("29 February 2024", "2024-02-29"),  # valid leap year
    ],
)
def test_rule1_text_month_cases(raw_input, expected):
    assert parse_and_standardize_record(raw_input, "YYYY-MM-DD") == expected


# ============================================================
# 2. Section 20: Numeric Date Cases (Rule 2)
# ============================================================

@pytest.mark.parametrize(
    "raw_input,expected",
    [
        ("15/08/2026", "2026-08-15"),
        ("15-08-2026", "2026-08-15"),
        ("15.08.2026", "2026-08-15"),
        ("2026/08/15", "2026-08-15"),
        ("2026-25-03", "2026-03-25"),
        ("2026.12.25", "2026-12-25"),
    ],
)
def test_rule2_numeric_date_cases(raw_input, expected):
    assert parse_and_standardize_record(raw_input, "YYYY-MM-DD") == expected


# ============================================================
# 3. Section 20: Ambiguous Cases -> Must Return None (NULL)
# ============================================================

@pytest.mark.parametrize(
    "ambiguous_input",
    [
        "05/06/2026",
        "06/05/2026",
        "01-02-2026",
        "12.12.2026",
        "2026-05-06",
        "2026/11/12",
    ],
)
def test_ambiguous_dates_return_null(ambiguous_input):
    assert parse_and_standardize_record(ambiguous_input, "YYYY-MM-DD") is None


# ============================================================
# 4. Section 20: Invalid & Unconvertible Cases -> Must Return None (NULL)
# ============================================================

@pytest.mark.parametrize(
    "invalid_input",
    [
        "31/02/2026",
        "29/02/2026",  # 2026 is not a leap year
        "32/01/2026",
        "15/13/2026",
        "00/12/2026",
        "15/00/2026",
        "31 April 2026",
        "31 Feb 2026",
        "hello",
        "abc",
        "not a date",
        "12345",
        "",
        "   ",
        None,
    ],
)
def test_invalid_and_non_date_values_return_null(invalid_input):
    assert parse_and_standardize_record(invalid_input, "YYYY-MM-DD") is None


# ============================================================
# 5. Section 8: All Output Formats
# ============================================================

@pytest.mark.parametrize(
    "fmt,expected",
    [
        ("YYYY-MM-DD", "2026-08-15"),
        ("DD-MM-YYYY", "15-08-2026"),
        ("MM-DD-YYYY", "08-15-2026"),
        ("DD/MM/YYYY", "15/08/2026"),
        ("MM/DD/YYYY", "08/15/2026"),
        ("YYYY/MM/DD", "2026/08/15"),
        ("YYYY.MM.DD", "2026.08.15"),
    ],
)
def test_all_supported_output_formats(fmt, expected):
    assert parse_and_standardize_record("15 August 2026", output_format=fmt) == expected
    assert parse_and_standardize_record("15/08/2026", output_format=fmt) == expected


# ============================================================
# 6. Section 9: Safe Output Column Naming & Collision Protection
# ============================================================

def test_safe_output_column_name_collision_handling():
    existing = ["id", "order_date"]
    assert get_safe_output_column_name(existing, "order_date") == "order_date_standardized"

    # If order_date_standardized already exists, should create order_date_standardized_2
    existing_with_std = ["id", "order_date", "order_date_standardized"]
    assert get_safe_output_column_name(existing_with_std, "order_date") == "order_date_standardized_2"

    # Never allow overwriting source column even if user passes source column name
    assert get_safe_output_column_name(existing, "order_date", "order_date") == "order_date_standardized"


# ============================================================
# 7. Section 4, 5, 16, 17: Column Scanning & Scan Percentages (20%, 30%, 40%, 80%)
# ============================================================

@pytest.mark.parametrize("scan_pct", [20, 30, 40, 80])
def test_detect_date_columns_with_scan_percentages(scan_pct):
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    def execute_side_effect(stmt, params=None):
        sql = str(stmt)
        res = MagicMock()
        if "SELECT COUNT(*)" in sql:
            res.scalar.return_value = 100
        elif "order_date_text" in sql:
            limit = (params or {}).get("sample_limit", 20)
            rows = []
            for i in range(limit):
                r = MagicMock()
                r._mapping = {"val": "15/08/2026" if i % 5 != 0 else "25 December 2026"}
                rows.append(r)
            res.fetchall.return_value = rows
        elif "customer_name" in sql:
            limit = (params or {}).get("sample_limit", 20)
            rows = []
            for _ in range(limit):
                r = MagicMock()
                r._mapping = {"val": "John Mumbai ABC123"}
                rows.append(r)
            res.fetchall.return_value = rows
        return res

    mock_conn.execute.side_effect = execute_side_effect

    with patch("src.staging.get_text_columns", return_value=["order_date_text", "customer_name"]):
        detected = detect_date_columns(
            mock_engine,
            "test_db",
            "orders__cleaning_ws",
            scan_percentage=scan_pct,
        )

    assert len(detected) == 1
    assert detected[0]["column"] == "order_date_text"
    assert detected[0]["scan_percentage"] == scan_pct
    assert detected[0]["sample_size"] == scan_pct  # 20, 30, 40, or 80 out of 100
    assert detected[0]["date_like_percentage"] == 100.0


# ============================================================
# 8. Section 18, 19, 21, 22: Preview & Standardization Execution
# ============================================================

def test_preview_and_standardize_column_preserves_original_and_writes_new_column():
    sample_values = [
        "15/08/2026",
        "25 December 2026",
        "Aug-15-2026",
        "05/06/2026",  # ambiguous -> NULL
        "31/02/2026",  # invalid -> NULL
        "hello",       # non-date -> NULL
        None,          # NULL -> NULL
    ]

    mock_engine = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["orders__cleaning_ws"]
    mock_inspector.get_columns.return_value = [
        {"name": "id", "type": "INT"},
        {"name": "order_date_text", "type": "VARCHAR(50)"},
    ]

    executed_sql = []

    def execute_side_effect(stmt, params=None):
        sql = str(stmt)
        executed_sql.append((sql, params))
        res = MagicMock()
        if "SELECT" in sql:
            rows = []
            for v in sample_values:
                r = MagicMock()
                r._mapping = {"val": v}
                rows.append(r)
            res.fetchall.return_value = rows
        return res

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = execute_side_effect
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    with patch("src.advanced_date_standardization.inspect", return_value=mock_inspector):
        # 1. Verify Preview
        prev = preview_column_standardization(
            mock_engine,
            "test_db",
            "orders__cleaning_ws",
            "order_date_text",
            output_format="YYYY-MM-DD",
        )
        assert prev["total_records"] == 7
        assert prev["successfully_converted"] == 3
        assert prev["unconverted"] == 4
        assert prev["proposed_output_column"] == "order_date_text_standardized"

        # 2. Verify Standardization Execution
        ok, msg, report = standardize_column(
            mock_engine,
            "test_db",
            "orders__cleaning_ws",
            "order_date_text",
            output_format="YYYY-MM-DD",
        )

    assert ok is True
    assert report["source_column"] == "order_date_text"
    assert report["output_column"] == "order_date_text_standardized"
    assert report["total_records"] == 7
    assert report["successfully_converted"] == 3
    assert report["unconverted"] == 4
    assert report["conversion_rate"] == round((3 / 7) * 100.0, 1)

    # Ensure ALTER TABLE ADD COLUMN `order_date_text_standardized` was executed
    # and source column `order_date_text` was NEVER altered or overwritten
    alter_sqls = [sql for sql, _ in executed_sql if "ALTER TABLE" in sql]
    assert len(alter_sqls) == 1
    assert "ADD COLUMN `order_date_text_standardized`" in alter_sqls[0]

    update_sqls = [(sql, p) for sql, p in executed_sql if "UPDATE" in sql]
    assert len(update_sqls) == 1
    assert "SET `order_date_text_standardized` = :std_val" in update_sqls[0][0]
