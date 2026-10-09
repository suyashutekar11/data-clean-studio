"""Stage 3 tests for data profiling."""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.profiling import (
    _quote_identifier,
    _quote_table,
    profile_workspace,
)


def test_quote_identifier():
    assert _quote_identifier("orders") == "`orders`"
    assert _quote_identifier("my`table") == "`my``table`"


def test_quote_table():
    assert _quote_table("ecommerce_db", "orders") == "`ecommerce_db`.`orders`"


def test_profile_workspace_missing_table():
    mock_engine = MagicMock()

    with patch(
        "src.profiling._get_columns",
        return_value=[],
    ):
        success, message, profile = profile_workspace(
            mock_engine,
            "test_db",
            "missing_table",
        )

    assert success is False
    assert "not found" in message.lower()
    assert profile is None


@patch("src.profiling._get_columns")
def test_profile_workspace_basic(mock_get_columns):
    mock_engine = MagicMock()

    mock_get_columns.return_value = [
        {
            "COLUMN_NAME": "id",
            "DATA_TYPE": "int",
            "IS_NULLABLE": "NO",
        },
        {
            "COLUMN_NAME": "name",
            "DATA_TYPE": "varchar",
            "IS_NULLABLE": "YES",
        },
    ]

    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "name": ["Alice", " Bob ", None],
        }
    )

    with patch(
        "src.profiling.pd.read_sql_query",
        return_value=df,
    ):
        success, message, profile = profile_workspace(
            mock_engine,
            "test_db",
            "employees__cleaning_abc123",
        )

    assert success is True
    assert profile is not None

    assert profile["row_count"] == 3
    assert profile["column_count"] == 2
    assert profile["duplicate_row_count"] == 0

    column_profile = profile["column_profiles"]

    name_profile = column_profile[column_profile["Column"] == "name"].iloc[0]

    assert name_profile["Null Count"] == 1
    assert name_profile["Null %"] == 33.33
    assert name_profile["Whitespace Issues"] == 1


@patch("src.profiling._get_columns")
def test_profile_detects_duplicates(mock_get_columns):
    mock_engine = MagicMock()

    mock_get_columns.return_value = [
        {
            "COLUMN_NAME": "id",
            "DATA_TYPE": "int",
            "IS_NULLABLE": "NO",
        },
        {
            "COLUMN_NAME": "name",
            "DATA_TYPE": "varchar",
            "IS_NULLABLE": "YES",
        },
    ]

    df = pd.DataFrame(
        {
            "id": [1, 1, 2],
            "name": ["Alice", "Alice", "Bob"],
        }
    )

    with patch(
        "src.profiling.pd.read_sql_query",
        return_value=df,
    ):
        success, message, profile = profile_workspace(
            mock_engine,
            "test_db",
            "employees__cleaning_abc123",
        )

    assert success is True
    assert profile is not None

    assert profile["duplicate_group_count"] == 1
    assert profile["duplicate_row_count"] == 2

    duplicate_findings = [
        finding
        for finding in profile["findings"]
        if finding["Type"] == "Duplicate Rows"
    ]

    assert len(duplicate_findings) == 1


@patch("src.profiling._get_columns")
def test_profile_numeric_statistics(mock_get_columns):
    mock_engine = MagicMock()

    mock_get_columns.return_value = [
        {
            "COLUMN_NAME": "quantity",
            "DATA_TYPE": "int",
            "IS_NULLABLE": "NO",
        },
    ]

    df = pd.DataFrame(
        {
            "quantity": [10, 20, 30],
        }
    )

    with patch(
        "src.profiling.pd.read_sql_query",
        return_value=df,
    ):
        success, message, profile = profile_workspace(
            mock_engine,
            "test_db",
            "orders__cleaning_abc123",
        )

    assert success is True
    assert profile is not None

    quantity_profile = profile["column_profiles"].iloc[0]

    assert quantity_profile["Min"] == 10
    assert quantity_profile["Max"] == 30
    assert quantity_profile["Average"] == 20.0


@patch("src.profiling._get_columns")
def test_profile_empty_strings(mock_get_columns):
    mock_engine = MagicMock()

    mock_get_columns.return_value = [
        {
            "COLUMN_NAME": "city",
            "DATA_TYPE": "varchar",
            "IS_NULLABLE": "YES",
        },
    ]

    df = pd.DataFrame(
        {
            "city": ["Mumbai", "", "   ", None],
        }
    )

    with patch(
        "src.profiling.pd.read_sql_query",
        return_value=df,
    ):
        success, message, profile = profile_workspace(
            mock_engine,
            "test_db",
            "customers__cleaning_abc123",
        )

    assert success is True
    assert profile is not None

    city_profile = profile["column_profiles"].iloc[0]

    assert city_profile["Null Count"] == 1
    assert city_profile["Empty Strings"] == 2


@patch("src.profiling._get_columns")
def test_profile_source_table_counts_and_findings(mock_get_columns):
    """Test that profile_source_table returns correct counts, blanks, nulls, duplicates, and findings."""
    from src.profiling import profile_source_table

    mock_engine = MagicMock()
    mock_get_columns.return_value = [
        {"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO"},
        {"COLUMN_NAME": "email", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES"},
        {"COLUMN_NAME": "name", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES"},
    ]

    df = pd.DataFrame(
        {
            "id": [1, 2, 3, 3],
            "email": ["user@test.com", "", None, "user@test.com"],
            "name": [" Alice ", "Bob", "", "Charlie"],
        }
    )

    with patch("src.profiling.pd.read_sql_query", return_value=df):
        success, message, profile = profile_source_table(
            mock_engine,
            "production_db",
            "users",  # Original source table
        )

    assert success is True
    assert profile is not None
    assert profile["row_count"] == 4
    assert profile["column_count"] == 3
    assert (
        profile["duplicate_row_count"] == 0
    )  # No exact duplicate rows across all cols

    col_profiles = profile["column_profiles"].set_index("Column")

    # Check NULL counts
    assert col_profiles.loc["email", "Null Count"] == 1

    # Check Blank/Empty counts
    assert col_profiles.loc["email", "Empty Strings"] == 1
    assert col_profiles.loc["name", "Empty Strings"] == 1

    # Check Whitespace issues
    assert col_profiles.loc["name", "Whitespace Issues"] == 1

    # Quality findings generated
    findings = profile["findings"]
    assert len(findings) > 0
    finding_types = [f["Type"] for f in findings]
    assert "Missing Values" in finding_types
    assert "Empty Values" in finding_types
    assert "Whitespace" in finding_types


@patch("src.profiling._get_columns")
def test_profile_source_table_read_only_safety(mock_get_columns):
    """Test that profiling a source table executes strictly read-only SELECT queries and no data modifications."""
    from src.profiling import profile_source_table

    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_get_columns.return_value = [
        {"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO"}
    ]

    df = pd.DataFrame({"id": [1, 2, 3]})

    with patch("src.profiling.pd.read_sql_query", return_value=df) as mock_read_sql:
        success, message, profile = profile_source_table(
            mock_engine,
            "production_db",
            "customers",
        )

        assert success is True
        # Verify read_sql_query called with SELECT statement targeting the table
        executed_query = str(mock_read_sql.call_args[0][0])
        assert "SELECT * FROM `production_db`.`customers`" in executed_query

        # Assert no modifying queries were called on connection directly
        for call_arg in mock_conn.execute.call_args_list:
            sql_text = str(call_arg[0][0]).upper()
            assert "UPDATE" not in sql_text
            assert "DELETE" not in sql_text
            assert "INSERT" not in sql_text
            assert "ALTER" not in sql_text
            assert "DROP" not in sql_text
            assert "TRUNCATE" not in sql_text


@patch("src.profiling._get_columns")
def test_profile_source_table_reflects_new_rows(mock_get_columns):
    """Test that running source profile again after new rows are added reflects the updated row count."""
    from src.profiling import profile_source_table

    mock_engine = MagicMock()
    mock_get_columns.return_value = [
        {"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO"}
    ]

    df_initial = pd.DataFrame({"id": list(range(100))})
    df_updated = pd.DataFrame({"id": list(range(120))})

    # Run 1: 100 rows
    with patch("src.profiling.pd.read_sql_query", return_value=df_initial):
        ok1, msg1, prof1 = profile_source_table(mock_engine, "db", "source_tbl")
        assert ok1 is True
        assert prof1["row_count"] == 100

    # Run 2: 120 rows (database updated)
    with patch("src.profiling.pd.read_sql_query", return_value=df_updated):
        ok2, msg2, prof2 = profile_source_table(mock_engine, "db", "source_tbl")
        assert ok2 is True
        assert prof2["row_count"] == 120


@patch("src.profiling._get_columns")
def test_existing_workspace_profiling_still_works(mock_get_columns):
    """Ensure existing profile_workspace continues to work without breaking."""
    from src.profiling import profile_workspace

    mock_engine = MagicMock()
    mock_get_columns.return_value = [
        {"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO"}
    ]

    df = pd.DataFrame({"id": [10, 20]})

    with patch("src.profiling.pd.read_sql_query", return_value=df):
        ok, msg, prof = profile_workspace(mock_engine, "db", "tbl__cleaning_xyz")
        assert ok is True
        assert prof["row_count"] == 2
        assert prof["table_name"] == "tbl__cleaning_xyz"


def test_calculate_health_score_clean_and_empty():
    """Verify health score calculations for empty and clean tables."""
    from app import calculate_health_score

    empty_prof = {"row_count": 0, "column_count": 0}
    score, label, color = calculate_health_score(empty_prof)
    assert score == 100
    assert "Clean" in label

    clean_prof = {
        "row_count": 100,
        "column_count": 4,
        "duplicate_row_count": 0,
        "findings": [],
        "column_profiles": pd.DataFrame(
            {
                "Null Count": [0, 0, 0, 0],
                "Empty Strings": [0, 0, 0, 0],
                "Whitespace Issues": [0, 0, 0, 0],
            }
        ),
    }
    score, label, color = calculate_health_score(clean_prof)
    assert score == 100
    assert label == "Excellent Health"


@patch("src.profiling._get_columns")
def test_source_vs_workspace_profiles_differ_after_cleaning(mock_get_columns):
    """
    Test that the Source Table profile retains the uncleaned baseline metrics
    while the Workspace profile reflects deduplicated/cleaned metrics.
    """
    from src.profiling import profile_source_table, profile_workspace
    from app import calculate_health_score

    mock_engine = MagicMock()
    mock_get_columns.return_value = [
        {"COLUMN_NAME": "id", "DATA_TYPE": "int", "IS_NULLABLE": "NO"},
        {"COLUMN_NAME": "name", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES"},
    ]

    # Source table has 5 rows with 2 duplicates (id=2 repeated)
    df_source = pd.DataFrame(
        {
            "id": [1, 2, 2, 3, 4],
            "name": ["Alice", "Bob", "Bob", "Charlie", "David"],
        }
    )
    # Workspace table has duplicates cleaned (4 unique rows)
    df_workspace = pd.DataFrame(
        {
            "id": [1, 2, 3, 4],
            "name": ["Alice", "Bob", "Charlie", "David"],
        }
    )

    with patch("src.profiling.pd.read_sql_query", return_value=df_source):
        ok_src, msg_src, prof_src = profile_source_table(
            mock_engine, "store_db", "customers"
        )
        assert ok_src is True
        assert prof_src["row_count"] == 5
        assert prof_src["duplicate_row_count"] == 2
        score_src, _, _ = calculate_health_score(prof_src)

    with patch("src.profiling.pd.read_sql_query", return_value=df_workspace):
        ok_ws, msg_ws, prof_ws = profile_workspace(
            mock_engine, "store_db", "customers__cleaning_xyz"
        )
        assert ok_ws is True
        assert prof_ws["row_count"] == 4
        assert prof_ws["duplicate_row_count"] == 0
        score_ws, _, _ = calculate_health_score(prof_ws)

    # Verify that source remains unchanged/dirty while workspace shows improvement
    assert prof_src["duplicate_row_count"] > prof_ws["duplicate_row_count"]
    assert score_ws > score_src


def test_data_profile_state_keys():
    """Verify DEFAULT_STATE includes active_profile_target and dialog control."""
    from app import DEFAULT_STATE

    assert "active_profile_target" in DEFAULT_STATE
    assert DEFAULT_STATE["active_profile_target"] == "source"
    assert "source_profile_result" in DEFAULT_STATE
    assert "profile_result" in DEFAULT_STATE
    assert "show_profile_dialog" in DEFAULT_STATE
    assert DEFAULT_STATE["show_profile_dialog"] is False
