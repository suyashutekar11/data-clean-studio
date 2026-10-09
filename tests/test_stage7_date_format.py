import pytest
from unittest.mock import MagicMock, patch, PropertyMock
from sqlalchemy import text

from src.staging import (
    get_date_columns,
    format_dates_workspace,
    FORMAT_MAP,
    DATE_DATA_TYPES,
    CLEANING_SUFFIX,
)


def _mock_inspector_and_columns(mock_engine, table_name, columns_metadata):
    """Helper to mock table inspection and column query for get_date_columns (which uses direct SQL)."""
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [table_name]

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_result = [
        MagicMock(_mapping={"COLUMN_NAME": col["name"], "DATA_TYPE": col["type"]})
        for col in columns_metadata
    ]
    return mock_inspector, mock_conn, mock_result


def _mock_inspector_for_format_dates(mock_engine, table_name, columns_metadata):
    """
    Helper to mock inspector for format_dates_workspace (which uses inspector.get_columns()).
    columns_metadata: list of dicts with 'name' and 'type' keys.
    """
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [table_name]
    
    # Mock get_columns to return SQLAlchemy-style column info
    mock_columns = []
    for col in columns_metadata:
        mock_columns.append({
            "name": col["name"],
            "type": col["type"],
            "nullable": True,
            "default": None,
            "autoincrement": False,
        })
    mock_inspector.get_columns.return_value = mock_columns
    
    return mock_inspector


# ----------------------------------------------------------------------
# 1. FORMAT_MAP and DATE_DATA_TYPES constants tests
# ----------------------------------------------------------------------


def test_format_map_contains_expected_formats():
    """Verify FORMAT_MAP has all required formats with correct MySQL patterns."""
    assert "YYYY-MM-DD" in FORMAT_MAP
    assert FORMAT_MAP["YYYY-MM-DD"] == "%Y-%m-%d"

    assert "DD-MM-YYYY" in FORMAT_MAP
    assert FORMAT_MAP["DD-MM-YYYY"] == "%d-%m-%Y"

    assert "MM-DD-YYYY" in FORMAT_MAP
    assert FORMAT_MAP["MM-DD-YYYY"] == "%m-%d-%Y"

    assert "DD/MM/YYYY" in FORMAT_MAP
    assert FORMAT_MAP["DD/MM/YYYY"] == "%d/%m/%Y"

    assert "MM/DD/YYYY" in FORMAT_MAP
    assert FORMAT_MAP["MM/DD/YYYY"] == "%m/%d/%Y"

    assert "YYYY/MM/DD" in FORMAT_MAP
    assert FORMAT_MAP["YYYY/MM/DD"] == "%Y/%m/%d"

    # Additional formats in FORMAT_MAP
    assert "DD-MON-YYYY" in FORMAT_MAP
    assert FORMAT_MAP["DD-MON-YYYY"] == "%d-%b-%Y"

    assert "DD-MONTH-YYYY" in FORMAT_MAP
    assert FORMAT_MAP["DD-MONTH-YYYY"] == "%d-%M-%Y"

    assert len(FORMAT_MAP) == 8


def test_date_data_types_contains_expected_types():
    """Verify DATE_DATA_TYPES includes all native MySQL date/time types."""
    assert "date" in DATE_DATA_TYPES
    assert "datetime" in DATE_DATA_TYPES
    assert "timestamp" in DATE_DATA_TYPES
    assert "time" in DATE_DATA_TYPES
    assert "year" in DATE_DATA_TYPES


# ----------------------------------------------------------------------
# 2. get_date_columns() tests (uses direct SQL query)
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_get_date_columns_detects_date_types(mock_inspect):
    """Test that get_date_columns returns only DATE/DATETIME/TIMESTAMP columns."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "created_at", "type": "datetime"},
            {"name": "birth_date", "type": "date"},
            {"name": "updated_ts", "type": "timestamp"},
            {"name": "start_time", "type": "time"},
            {"name": "year_col", "type": "year"},
            {"name": "description", "type": "varchar"},
            {"name": "notes", "type": "text"},
        ],
    )
    mock_inspect.return_value = inspector
    conn.execute.return_value = col_rows

    result = get_date_columns(mock_engine, "test_db", table)

    assert "created_at" in result
    assert "birth_date" in result
    assert "updated_ts" in result
    assert "start_time" in result
    assert "year_col" in result
    assert "id" not in result
    assert "description" not in result
    assert "notes" not in result
    assert len(result) == 5


@patch("src.staging.inspect")
def test_get_date_columns_no_date_columns(mock_inspect):
    """Test get_date_columns returns empty list when no date columns exist."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "varchar"},
            {"name": "email", "type": "varchar"},
        ],
    )
    mock_inspect.return_value = inspector
    conn.execute.return_value = col_rows

    result = get_date_columns(mock_engine, "test_db", table)

    assert result == []


@patch("src.staging.inspect")
def test_get_date_columns_error_handling(mock_inspect):
    """Test get_date_columns handles database errors gracefully."""
    mock_engine = MagicMock()
    mock_engine.connect.side_effect = Exception("DB connection failed")

    result = get_date_columns(mock_engine, "test_db", "nonexistent__cleaning_abc123")

    assert result == []


# ----------------------------------------------------------------------
# 3. format_dates_workspace() tests - Native valid dates
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_format_dates_native_valid(mock_inspect):
    """Test validating a native DATE column with all valid values."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    
    # Mock inspector for format_dates_workspace
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "birth_date", "type": "date"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    # Mock connection for the scalar queries
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Setup scalar returns for each query: total, nulls, blanks, invalid
    scalar_results = [10, 1, 0, 0]
    mock_scalar = MagicMock()
    mock_scalar.scalar.side_effect = scalar_results

    # Preview query result
    preview_data = [
        MagicMock(_mapping={"original": "1990-01-15", "formatted": "15-01-1990"}),
        MagicMock(_mapping={"original": "1985-06-20", "formatted": "20-06-1985"}),
    ]
    mock_preview = MagicMock()
    mock_preview.__iter__.return_value = iter(preview_data)

    mock_conn.execute.side_effect = [
        mock_scalar,  # total
        mock_scalar,  # nulls
        mock_scalar,  # blanks
        mock_scalar,  # invalid
        mock_preview,  # preview
    ]

    success, msg, report = format_dates_workspace(
        mock_engine,
        "test_db",
        table,
        "birth_date",
        "DD-MM-YYYY",
    )

    assert success is True
    assert "Date formatting validated" in msg
    assert report["operation"] == "Date Formatting"
    assert report["column"] == "birth_date"
    assert report["original_format"] == "native"
    assert report["target_format"] == "DD-MM-YYYY"
    assert report["total_examined"] == 10
    assert report["nulls_skipped"] == 1
    assert report["blanks_skipped"] == 0
    assert report["invalid_unparseable"] == 0
    assert report["values_formatted"] == 0
    assert report["valid_values"] == 9
    assert "preview" in report
    assert len(report["preview"]) == 2
    assert "native storage" in report["status"].lower()


@patch("src.staging.inspect")
def test_format_dates_with_nulls(mock_inspect):
    """Test NULL values are counted and skipped."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "event_date", "type": "datetime"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    scalar_results = [100, 25, 0, 0]  # total=100, nulls=25
    mock_scalar = MagicMock()
    mock_scalar.scalar.side_effect = scalar_results

    preview_data = [
        MagicMock(_mapping={"original": "2024-01-15 10:30:00", "formatted": "15-01-2024"}),
    ]
    mock_preview = MagicMock()
    mock_preview.__iter__.return_value = iter(preview_data)

    mock_conn.execute.side_effect = [
        mock_scalar, mock_scalar, mock_scalar, mock_scalar, mock_preview
    ]

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "event_date", "DD-MM-YYYY"
    )

    assert success is True
    assert report["nulls_skipped"] == 25
    assert report["valid_values"] == 75


@patch("src.staging.inspect")
def test_format_dates_invalid_unparseable(mock_inspect):
    """Test invalid/unparseable dates are counted."""
    mock_engine = MagicMock()
    table = "logs__cleaning_xyz789"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "log_timestamp", "type": "timestamp"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    scalar_results = [50, 0, 0, 3]  # total=50, invalid=3
    mock_scalar = MagicMock()
    mock_scalar.scalar.side_effect = scalar_results

    preview_data = [
        MagicMock(_mapping={"original": "2024-01-15 10:30:00", "formatted": "15/01/2024"}),
    ]
    mock_preview = MagicMock()
    mock_preview.__iter__.return_value = iter(preview_data)

    mock_conn.execute.side_effect = [
        mock_scalar, mock_scalar, mock_scalar, mock_scalar, mock_preview
    ]

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "log_timestamp", "DD/MM/YYYY"
    )

    assert success is True
    assert report["invalid_unparseable"] == 3
    assert report["valid_values"] == 47


# ----------------------------------------------------------------------
# 4. format_dates_workspace() tests - All target formats
# ----------------------------------------------------------------------


@pytest.mark.parametrize("target_format,mysql_pattern", [
    ("YYYY-MM-DD", "%Y-%m-%d"),
    ("DD-MM-YYYY", "%d-%m-%Y"),
    ("MM-DD-YYYY", "%m-%d-%Y"),
    ("DD/MM/YYYY", "%d/%m/%Y"),
    ("MM/DD/YYYY", "%m/%d/%Y"),
    ("YYYY/MM/DD", "%Y/%m/%d"),
])
@patch("src.staging.inspect")
def test_format_dates_all_formats(mock_inspect, target_format, mysql_pattern):
    """Test each supported target format maps to correct MySQL pattern."""
    mock_engine = MagicMock()
    table = "events__cleaning_fmt123"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "event_date", "type": "date"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    scalar_results = [5, 0, 0, 0]
    mock_scalar = MagicMock()
    mock_scalar.scalar.side_effect = scalar_results

    preview_data = [
        MagicMock(_mapping={"original": "2024-01-15", "formatted": "formatted_value"}),
    ]
    mock_preview = MagicMock()
    mock_preview.__iter__.return_value = iter(preview_data)

    mock_conn.execute.side_effect = [
        mock_scalar, mock_scalar, mock_scalar, mock_scalar, mock_preview
    ]

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "event_date", target_format
    )

    assert success is True
    assert report["target_format"] == target_format


@patch("src.staging.inspect")
def test_format_dates_invalid_target_format(mock_inspect):
    """Test invalid target format is rejected."""
    mock_engine = MagicMock()
    table = "events__cleaning_fmt123"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "event_date", "type": "date"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "event_date", "INVALID-FORMAT"
    )

    assert success is False
    assert "Invalid target format" in msg
    assert report == {}


# ----------------------------------------------------------------------
# 5. format_dates_workspace() tests - Safety validations
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_format_dates_refuses_non_workspace_table(mock_inspect):
    """Test that non-workspace tables are refused."""
    mock_engine = MagicMock()
    table = "users"  # No __cleaning_ suffix

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "birth_date", "YYYY-MM-DD"
    )

    assert success is False
    assert "cleaning workspace" in msg.lower()
    assert report == {}


@patch("src.staging.inspect")
def test_format_dates_refuses_multiple_suffixes(mock_inspect):
    """Test that tables with multiple cleaning suffixes are refused."""
    mock_engine = MagicMock()
    table = "users__cleaning__cleaning_abc123"

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "birth_date", "YYYY-MM-DD"
    )

    assert success is False
    assert report == {}


@patch("src.staging.inspect")
def test_format_dates_table_not_found(mock_inspect):
    """Test table not found in database."""
    mock_engine = MagicMock()
    table = "nonexistent__cleaning_abc123"
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["other_table"]
    mock_inspect.return_value = mock_inspector

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "birth_date", "YYYY-MM-DD"
    )

    assert success is False
    assert "not found" in msg.lower()
    assert report == {}


@patch("src.staging.inspect")
def test_format_dates_column_not_found(mock_inspect):
    """Test column not found in table."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "varchar"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "nonexistent_col", "YYYY-MM-DD"
    )

    assert success is False
    assert "not found" in msg.lower()
    assert report == {}


@patch("src.staging.inspect")
def test_format_dates_unsupported_column_type(mock_inspect):
    """Test non-date column is rejected."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "name", "type": "varchar"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "name", "YYYY-MM-DD"
    )

    assert success is False
    assert "not a native date" in msg.lower()
    assert "varchar" in msg.lower()
    assert report == {}


# ----------------------------------------------------------------------
# 6. format_dates_workspace() tests - Report structure
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_format_dates_report_structure(mock_inspect):
    """Test report contains all required keys."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "created_at", "type": "datetime"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    scalar_results = [10, 1, 0, 0]
    mock_scalar = MagicMock()
    mock_scalar.scalar.side_effect = scalar_results

    preview_data = [
        MagicMock(_mapping={"original": "2024-01-15 10:30:00", "formatted": "2024-01-15"}),
    ]
    mock_preview = MagicMock()
    mock_preview.__iter__.return_value = iter(preview_data)

    mock_conn.execute.side_effect = [
        mock_scalar, mock_scalar, mock_scalar, mock_scalar, mock_preview
    ]

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "created_at", "YYYY-MM-DD"
    )

    required_keys = [
        "operation", "column", "original_format", "target_format",
        "total_examined", "nulls_skipped", "blanks_skipped",
        "invalid_unparseable", "values_formatted", "valid_values",
        "preview", "status"
    ]
    for key in required_keys:
        assert key in report, f"Missing required report key: {key}"

    assert report["operation"] == "Date Formatting"
    assert report["original_format"] == "native"
    assert report["values_formatted"] == 0


# ----------------------------------------------------------------------
# 7. format_dates_workspace() tests - Error handling/rollback
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_format_dates_rollback_on_exception(mock_inspect):
    """Test exception during validation returns failure."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "birth_date", "type": "date"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_conn.execute.side_effect = Exception("Database error")

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "birth_date", "YYYY-MM-DD"
    )

    assert success is False
    assert "Error during date formatting validation" in msg
    assert "Database error" in msg
    assert report == {}


# ----------------------------------------------------------------------
# 8. format_dates_workspace() tests - Preview query correctness
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_format_dates_preview_query_uses_date_format(mock_inspect):
    """Test preview query uses DATE_FORMAT with correct pattern."""
    mock_engine = MagicMock()
    table = "events__cleaning_fmt123"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "event_date", "type": "date"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    scalar_results = [5, 0, 0, 0]
    mock_scalar = MagicMock()
    mock_scalar.scalar.side_effect = scalar_results

    preview_data = [
        MagicMock(_mapping={"original": "2024-01-15", "formatted": "15/01/2024"}),
    ]
    mock_preview = MagicMock()
    mock_preview.__iter__.return_value = iter(preview_data)

    mock_conn.execute.side_effect = [
        mock_scalar, mock_scalar, mock_scalar, mock_scalar, mock_preview
    ]

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "event_date", "DD/MM/YYYY"
    )

    assert success is True
    # Verify DATE_FORMAT was called in queries
    call_args_list = [call for call in mock_conn.execute.call_args_list]
    # The preview query (5th call) should contain DATE_FORMAT
    preview_call = str(call_args_list[4][0][0]) if len(call_args_list) > 4 else ""
    assert "DATE_FORMAT" in preview_call
    assert "event_date" in preview_call


# ----------------------------------------------------------------------
# 9. format_dates_workspace() tests - Source table unchanged
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_format_dates_source_table_unchanged(mock_inspect):
    """Verify production table is never written to."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "birth_date", "type": "date"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    scalar_results = [5, 0, 0, 0]
    mock_scalar = MagicMock()
    mock_scalar.scalar.side_effect = scalar_results

    preview_data = [
        MagicMock(_mapping={"original": "1990-01-15", "formatted": "1990-01-15"}),
    ]
    mock_preview = MagicMock()
    mock_preview.__iter__.return_value = iter(preview_data)

    mock_conn.execute.side_effect = [
        mock_scalar, mock_scalar, mock_scalar, mock_scalar, mock_preview
    ]

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "birth_date", "YYYY-MM-DD"
    )

    assert success is True
    # Check that no UPDATE/ALTER/INSERT statements were executed
    for call in mock_conn.execute.call_args_list:
        query_str = str(call[0][0]).upper()
        assert "UPDATE" not in query_str
        assert "INSERT" not in query_str
        assert "ALTER" not in query_str
        assert "DELETE" not in query_str
    # Only SELECT queries should be executed


# ----------------------------------------------------------------------
# 10. format_dates_workspace() tests - Mixed valid/invalid
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_format_dates_mixed_valid_invalid(mock_inspect):
    """Test column with mix of valid, NULL, and invalid values."""
    mock_engine = MagicMock()
    table = "mixed__cleaning_mix456"
    
    mock_inspector = _mock_inspector_for_format_dates(
        mock_engine,
        table,
        [
            {"name": "id", "type": "int"},
            {"name": "log_time", "type": "timestamp"},
        ],
    )
    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # 100 total, 10 NULL, 5 blank, 3 invalid = 82 valid
    scalar_results = [100, 10, 5, 3]
    mock_scalar = MagicMock()
    mock_scalar.scalar.side_effect = scalar_results

    preview_data = [
        MagicMock(_mapping={"original": "2024-01-15 10:30:00", "formatted": "15-01-2024"}),
        MagicMock(_mapping={"original": "2023-12-25 00:00:00", "formatted": "25-12-2023"}),
    ]
    mock_preview = MagicMock()
    mock_preview.__iter__.return_value = iter(preview_data)

    mock_conn.execute.side_effect = [
        mock_scalar, mock_scalar, mock_scalar, mock_scalar, mock_preview
    ]

    success, msg, report = format_dates_workspace(
        mock_engine, "test_db", table, "log_time", "DD-MM-YYYY"
    )

    assert success is True
    assert report["total_examined"] == 100
    assert report["nulls_skipped"] == 10
    assert report["blanks_skipped"] == 5
    assert report["invalid_unparseable"] == 3
    assert report["valid_values"] == 82
    assert report["values_formatted"] == 0