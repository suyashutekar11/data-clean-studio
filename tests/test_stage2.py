"""Stage 2 tests for MySQL Data Quality & Cleaning Platform.

Tests for workspace/staging table creation, deletion, and safety checks.
"""

from unittest.mock import MagicMock, patch

import pandas as pd

from src.staging import (
    create_workspace,
    delete_workspace,
    get_workspace_info,
    _generate_working_table_name,
    _make_safe_table_name,
)


def test_make_safe_table_name_basic():
    """Test basic safe table name generation."""
    assert _make_safe_table_name("employees") == "employees"
    assert _make_safe_table_name("my-table") == "my_table"
    assert _make_safe_table_name("table with spaces") == "table_with_spaces"
    assert _make_safe_table_name("1table") == "_table"
    assert _make_safe_table_name("") == "cleaning_table"


def test_make_safe_table_name_with_special_chars():
    """Test safe table name with various special characters."""
    assert _make_safe_table_name("test@table#1") == "test_table_1"
    assert _make_safe_table_name("a.b.c") == "a_b_c"
    assert _make_safe_table_name("table$name%") == "table_name_"


@patch("src.staging.inspect")
def test_create_workspace_source_not_found(mock_inspect):
    """Test workspace creation fails when source table doesn't exist."""
    mock_engine = MagicMock()

    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = []

    mock_inspect.return_value = mock_inspector

    success, message, details = create_workspace(
        mock_engine,
        "test_db",
        "nonexistent_table",
    )

    assert success is False
    assert "not found" in message.lower()
    assert details is None


@patch("src.staging.inspect")
def test_delete_workspace_success(mock_inspect):
    """Test successful workspace deletion."""
    mock_engine = MagicMock()

    mock_inspector = MagicMock()

    # After deletion, workspace should no longer exist.
    mock_inspector.get_table_names.return_value = []

    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    success, message = delete_workspace(
        mock_engine,
        "test_db",
        "employees__cleaning_abc123def456",
    )

    assert success is True
    assert "deleted successfully" in message.lower()

    # Verify a DROP TABLE was executed.
    executed_sql = str(mock_conn.execute.call_args[0][0])

    assert "DROP TABLE IF EXISTS" in executed_sql.upper()
    assert "`test_db`.`employees__cleaning_abc123def456`" in executed_sql


@patch("src.staging.inspect")
def test_delete_workspace_still_exists(mock_inspect):
    """Test deletion failure when the workspace still exists."""
    mock_engine = MagicMock()

    mock_inspector = MagicMock()

    # Simulate the workspace still being present after DROP.
    mock_inspector.get_table_names.return_value = [
        "employees__cleaning_abc123def456"
    ]

    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    success, message = delete_workspace(
        mock_engine,
        "test_db",
        "employees__cleaning_abc123def456",
    )

    assert success is False
    assert "still exists" in message.lower()


def test_delete_workspace_rejects_production_table():
    """Production tables must never be eligible for workspace deletion."""
    mock_engine = MagicMock()

    success, message = delete_workspace(
        mock_engine,
        "test_db",
        "employees",
    )

    assert success is False
    assert "cleaning workspace" in message.lower()

    # No database operation should occur.
    mock_engine.connect.assert_not_called()


@patch("src.staging.inspect")
@patch("src.staging.MySQLMetadataInspector.get_table_schema")
def test_get_workspace_info_exists(
    mock_get_schema,
    mock_inspect,
):
    """Test getting workspace info when table exists."""
    mock_engine = MagicMock()

    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [
        "employees__cleaning_abc123def456"
    ]

    mock_inspect.return_value = mock_inspector

    mock_schema = [
        {
            "Column Name": "id",
            "Data Type": "INT",
            "Nullable": "NO",
            "Key Info": "PRIMARY KEY",
            "Default": "None",
        },
    ]

    mock_get_schema.return_value = mock_schema

    mock_conn = MagicMock()

    count_result = MagicMock()
    count_result.scalar.return_value = 50

    mock_conn.execute.return_value = count_result

    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_preview = pd.DataFrame(
        {
            "id": [1, 2],
            "name": ["Alice", "Bob"],
        }
    )

    with patch(
        "pandas.read_sql_query",
        return_value=mock_preview,
    ):
        info = get_workspace_info(
            mock_engine,
            "test_db",
            "employees__cleaning_abc123def456",
        )

    assert info is not None
    assert info["row_count"] == 50
    assert info["exists"] is True
    assert info["schema"] == mock_schema
    assert isinstance(info["preview"], pd.DataFrame)


@patch("src.staging.inspect")
def test_get_workspace_info_not_exists(mock_inspect):
    """Test getting workspace info when table doesn't exist."""
    mock_engine = MagicMock()

    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = []

    mock_inspect.return_value = mock_inspector

    info = get_workspace_info(
        mock_engine,
        "test_db",
        "nonexistent_table",
    )

    assert info is None


def test_generate_working_table_name():
    """Test workspace name generation."""
    name = _generate_working_table_name(
        "test_db",
        "orders",
        "abc123def456",
    )

    assert name == "orders__cleaning_abc123def456"
    assert name.count("__cleaning_") == 1


@patch("src.staging.inspect")
def test_production_table_safety_not_affected(mock_inspect):
    """
    Test that workspace creation does not modify the production table.

    The only write operations allowed are:
        CREATE TABLE <workspace>
        INSERT INTO <workspace>

    The source table must only appear in read operations.
    """
    mock_engine = MagicMock()

    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["employees"]

    mock_inspect.return_value = mock_inspector

    mock_conn = MagicMock()

    executed_queries = []

    def mock_execute(sql_text):
        sql = str(sql_text)
        executed_queries.append(sql)

        result = MagicMock()

        upper_sql = sql.upper()

        if upper_sql.startswith("SELECT COUNT"):
            result.scalar.return_value = 100

        elif upper_sql.startswith("SHOW CREATE TABLE"):
            result.fetchone.return_value = (
                "employees",
                "CREATE TABLE `employees` (id INT)",
            )

        else:
            result.scalar.return_value = 100

        return result

    mock_conn.execute.side_effect = mock_execute

    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    success, message, details = create_workspace(
        mock_engine,
        "test_db",
        "employees",
    )

    assert success is True
    assert details is not None
    assert details["source_row_count"] == 100
    assert details["working_row_count"] == 100

    working_name = details["working_table_name"]

    # Find the actual CREATE TABLE statement.
    create_queries = [
        q
        for q in executed_queries
        if "CREATE TABLE" in q.upper()
        and "SHOW CREATE TABLE" not in q.upper()
    ]

    assert len(create_queries) == 1

    create_sql = create_queries[0]

    # Workspace must be the CREATE target.
    expected_target = f"`test_db`.`{working_name}`"

    assert expected_target in create_sql

    # Production table must not be the CREATE target.
    assert "CREATE TABLE `test_db`.`employees`" not in create_sql

    # No dangerous modification of production table.
    dangerous_operations = [
        "UPDATE",
        "DELETE",
        "ALTER TABLE",
        "DROP TABLE",
        "TRUNCATE TABLE",
        "RENAME TABLE",
    ]

    for operation in dangerous_operations:
        assert not (
            operation in create_sql.upper()
            and "`employees`" in create_sql
        )


@patch("src.staging.inspect")
def test_create_workspace_exact_sql_target(mock_inspect):
    """
    Test that workspace creation generates the CREATE TABLE statement
    with the cleaning suffix exactly once.
    """
    mock_engine = MagicMock()

    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["orders"]

    mock_inspect.return_value = mock_inspector

    executed_queries = []

    def mock_execute(sql_text):
        sql = str(sql_text)
        executed_queries.append(sql)

        result = MagicMock()

        upper_sql = sql.upper()

        if upper_sql.startswith("SHOW CREATE TABLE"):
            result.fetchone.return_value = (
                "orders",
                "CREATE TABLE `orders` "
                "(`id` int, `orders` varchar(255))",
            )

        elif upper_sql.startswith("SELECT COUNT"):
            result.scalar.return_value = 10

        else:
            result.scalar.return_value = 10

        return result

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = mock_execute

    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    success, message, details = create_workspace(
        mock_engine,
        "ecommerce_db",
        "orders",
    )

    assert success is True
    assert details is not None

    working_name = details["working_table_name"]

    # Exclude SHOW CREATE TABLE.
    create_queries = [
        q
        for q in executed_queries
        if "CREATE TABLE" in q.upper()
        and "SHOW CREATE TABLE" not in q.upper()
    ]

    assert len(create_queries) == 1

    create_sql = create_queries[0]

    expected_target = (
        f"`ecommerce_db`.`{working_name}`"
    )

    assert expected_target in create_sql

    # Exactly one cleaning suffix.
    assert create_sql.count("__cleaning_") == 1

    # The source table must not be the CREATE target.
    assert (
        "CREATE TABLE `ecommerce_db`.`orders`"
        not in create_sql
    )