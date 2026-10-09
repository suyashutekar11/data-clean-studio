import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import text
import pandas as pd

from src.staging import (
    replace_blank_values_workspace,
    get_text_columns,
    count_blank_values_in_column,
    scan_blank_and_null_columns,
)


def _mock_inspector_and_columns(mock_engine, table_name, columns_metadata):
    """Helper to mock table inspection and column query."""
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [table_name]

    # Mock connection execution for columns and queries
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Setup column query return
    mock_result = [
        MagicMock(_mapping={"COLUMN_NAME": col["name"], "DATA_TYPE": col["type"]})
        for col in columns_metadata
    ]
    return mock_inspector, mock_conn, mock_result


@patch("src.staging.inspect")
def test_replace_blanks_success(mock_inspect):
    """Test replacing blank strings in a text column with a non-empty replacement."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "id", "type": "int"}, {"name": "city", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector

    # Mock count query returning 4 blanks
    count_mock = MagicMock()
    count_mock.scalar.return_value = 4
    conn.execute.side_effect = [col_rows, count_mock]

    # Mock transaction for update
    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        table,
        "city",
        "N/A",
    )

    assert success is True
    assert "Successfully replaced 4 blank value(s)" in msg
    assert report["operation"] == "Blank / Empty Value Replacement"
    assert report["column"] == "city"
    assert report["replacement_value"] == "N/A"
    assert report["values_replaced"] == 4

    # Verify UPDATE query and parameterization
    assert begin_conn.execute.called
    call_args = begin_conn.execute.call_args
    query_str = str(call_args[0][0])
    params = call_args[0][1]
    assert "UPDATE `test_db`.`users__cleaning_abc123`" in query_str
    assert "SET `city` = :replacement" in query_str
    assert "`city` IS NOT NULL" in query_str
    assert "`city` = ''" in query_str
    assert params == {"replacement": "N/A"}


@patch("src.staging.inspect")
def test_replace_blanks_preserves_nulls_and_non_blanks(mock_inspect):
    """Test that the WHERE clause strictly checks IS NOT NULL and = '', protecting NULLs and non-blanks."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "notes", "type": "text"}],
    )
    mock_inspect.return_value = inspector

    count_mock = MagicMock()
    count_mock.scalar.return_value = 2
    conn.execute.side_effect = [col_rows, count_mock]

    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        table,
        "notes",
        "Unknown",
    )

    assert success is True
    call_args = begin_conn.execute.call_args
    query_str = str(call_args[0][0])
    # Must enforce both conditions
    assert "`notes` IS NOT NULL" in query_str
    assert "`notes` = ''" in query_str


@patch("src.staging.inspect")
def test_replace_blanks_zero_found(mock_inspect):
    """Test scenario where 0 blanks exist in the column."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "email", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector

    count_mock = MagicMock()
    count_mock.scalar.return_value = 0
    conn.execute.side_effect = [col_rows, count_mock]

    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        table,
        "email",
        "missing@domain.com",
    )

    assert success is True
    assert "No blank/empty values found" in msg
    assert report["values_replaced"] == 0
    # UPDATE should NOT have been executed
    assert not begin_conn.execute.called


def test_replace_blanks_rejects_empty_replacement():
    """Test that empty string as replacement is rejected."""
    mock_engine = MagicMock()
    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        "users__cleaning_abc123",
        "city",
        "",
    )
    assert success is False
    assert "Replacement value cannot be empty" in msg


def test_replace_blanks_rejects_non_workspace_table():
    """Test that production/source tables without the cleaning suffix are rejected."""
    mock_engine = MagicMock()
    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        "users",  # Production table
        "city",
        "N/A",
    )
    assert success is False
    assert (
        "Refusing to clean a table that is not identified as a cleaning workspace"
        in msg
    )


@patch("src.staging.inspect")
def test_replace_blanks_rejects_non_text_column(mock_inspect):
    """Test that numeric or non-string columns are rejected."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "age", "type": "int"}],
    )
    mock_inspect.return_value = inspector
    conn.execute.return_value = col_rows

    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        table,
        "age",
        "0",
    )
    assert success is False
    assert "is of type 'int', which is not a supported text/string column" in msg


@patch("src.staging.inspect")
def test_replace_blanks_rejects_missing_column(mock_inspect):
    """Test that specifying a column not present in the table is rejected."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "name", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector
    conn.execute.return_value = col_rows

    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        table,
        "non_existent_col",
        "N/A",
    )
    assert success is False
    assert "Column 'non_existent_col' not found" in msg


@patch("src.staging.inspect")
def test_get_text_columns_helper(mock_inspect):
    """Test helper get_text_columns correctly filters for text/string types."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    columns_raw = [
        MagicMock(_mapping={"COLUMN_NAME": "id", "DATA_TYPE": "int"}),
        MagicMock(_mapping={"COLUMN_NAME": "name", "DATA_TYPE": "varchar"}),
        MagicMock(_mapping={"COLUMN_NAME": "created_at", "DATA_TYPE": "datetime"}),
        MagicMock(_mapping={"COLUMN_NAME": "bio", "DATA_TYPE": "text"}),
    ]
    mock_conn.execute.return_value = columns_raw

    text_cols = get_text_columns(mock_engine, "db", "users__cleaning_abc123")
    assert text_cols == ["name", "bio"]


def test_count_blank_values_in_column_helper():
    """Test helper count_blank_values_in_column query construction and execution."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.return_value.scalar.return_value = 7

    count = count_blank_values_in_column(
        mock_engine, "db", "tbl__cleaning_abc", "address"
    )
    assert count == 7

    executed_query = str(mock_conn.execute.call_args[0][0])
    assert "SELECT COUNT(*) AS cnt" in executed_query
    assert "`tbl__cleaning_abc`" in executed_query
    assert "`address` IS NOT NULL" in executed_query
    assert "`address` = ''" in executed_query


def test_replace_blanks_production_table_never_modified():
    """Test that attempting to pass production table name fails and never runs any UPDATE query."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Attempting to call with source table
    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "production_db",
        "customers",
        "email",
        "N/A",
    )
    assert success is False
    assert (
        "Refusing to clean a table that is not identified as a cleaning workspace"
        in msg
    )
    assert not mock_engine.begin.called
    assert not mock_conn.execute.called


@patch("src.staging.inspect")
def test_replace_nulls_target_mode(mock_inspect):
    """Test replace_blank_values_workspace with target_mode='nulls'."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "status", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector

    count_mock = MagicMock()
    count_mock.scalar.return_value = 5
    conn.execute.side_effect = [col_rows, count_mock]

    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        table,
        "status",
        "PENDING",
        target_mode="nulls",
    )

    assert success is True
    assert "Successfully replaced 5 NULL value(s)" in msg
    assert report["operation"] == "NULL Value Replacement"
    assert report["target_mode"] == "nulls"
    assert report["values_replaced"] == 5

    call_args = begin_conn.execute.call_args
    query_str = str(call_args[0][0])
    assert "`status` IS NULL" in query_str


@patch("src.staging.inspect")
def test_replace_both_blanks_and_nulls_target_mode(mock_inspect):
    """Test replace_blank_values_workspace with target_mode='both'."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "category", "type": "text"}],
    )
    mock_inspect.return_value = inspector

    count_mock = MagicMock()
    count_mock.scalar.return_value = 9
    conn.execute.side_effect = [col_rows, count_mock]

    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    success, msg, report = replace_blank_values_workspace(
        mock_engine,
        "test_db",
        table,
        "category",
        "GENERAL",
        target_mode="both",
    )

    assert success is True
    assert "Successfully replaced 9 blank and NULL value(s)" in msg
    assert report["operation"] == "Blank & NULL Value Replacement"
    assert report["target_mode"] == "both"

    call_args = begin_conn.execute.call_args
    query_str = str(call_args[0][0])
    assert "(`category` IS NULL OR `category` = '')" in query_str


@patch("src.staging.get_text_columns")
def test_scan_blank_and_null_columns(mock_get_text_cols):
    """Test scanning text columns for blank and NULL counts."""
    mock_get_text_cols.return_value = ["clean_col", "blank_col", "null_col"]

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Mock single aggregate row with b_0, n_0, b_1, n_1, etc.
    mock_row = MagicMock()
    mock_row._mapping = {
        "b_0": 0,
        "n_0": 0,  # clean_col
        "b_1": 15,
        "n_1": 2,  # blank_col (total 17)
        "b_2": 0,
        "n_2": 4,  # null_col (total 4)
    }
    exec_res = MagicMock()
    exec_res.first.return_value = mock_row
    mock_conn.execute.return_value = exec_res

    results = scan_blank_and_null_columns(
        mock_engine, "test_db", "orders__cleaning_123"
    )

    assert len(results) == 3
    # blank_col should be ranked first because total_missing is 17
    assert results[0]["column"] == "blank_col"
    assert results[0]["blank_count"] == 15
    assert results[0]["null_count"] == 2
    assert results[0]["total_missing"] == 17
    assert results[0]["has_issues"] is True

    # null_col ranked second (total_missing is 4)
    assert results[1]["column"] == "null_col"
    assert results[1]["total_missing"] == 4
    assert results[1]["has_issues"] is True

    # clean_col ranked last
    assert results[2]["column"] == "clean_col"
    assert results[2]["total_missing"] == 0
    assert results[2]["has_issues"] is False
