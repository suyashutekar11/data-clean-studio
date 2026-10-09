import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, text

from src.staging import (
    to_title_case,
    count_text_casing_changes,
    normalize_text_case_workspace,
)


def _mock_inspector_and_columns(mock_engine, table_name, columns_metadata):
    """Helper to mock table inspection and column query."""
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [table_name]

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_result = [
        MagicMock(_mapping={"COLUMN_NAME": col["name"], "DATA_TYPE": col["type"]})
        for col in columns_metadata
    ]
    return mock_inspector, mock_conn, mock_result


# ----------------------------------------------------------------------
# 1. Helper function tests (word boundary, whitespace preservation)
# ----------------------------------------------------------------------


def test_to_title_case_helper():
    """Verify title case transformation behavior on strings, spaces, and edge cases."""
    assert to_title_case("john doe") == "John Doe"
    assert to_title_case("John DOE") == "John Doe"
    assert to_title_case("JOHN DOE") == "John Doe"
    assert to_title_case("  JOHN DOE  ") == "  John Doe  "
    assert to_title_case("o'connor") == "O'Connor"
    assert to_title_case("") == ""
    assert to_title_case("   ") == "   "
    assert to_title_case(None) is None
    assert to_title_case("customer_name") == "Customer_Name"
    assert to_title_case("alpha123beta") == "Alpha123Beta"


# ----------------------------------------------------------------------
# 2. Lowercase transformation tests
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_normalize_casing_lowercase(mock_inspect):
    """Test normalizing a text column to lowercase."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "id", "type": "int"}, {"name": "full_name", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector

    count_mock = MagicMock()
    count_mock.scalar.return_value = 5
    conn.execute.side_effect = [col_rows, count_mock]

    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    success, msg, report = normalize_text_case_workspace(
        mock_engine,
        "test_db",
        table,
        "full_name",
        "lowercase",
    )

    assert success is True
    assert "Successfully normalized 5 value(s)" in msg
    assert report["operation"] == "Text Casing"
    assert report["column"] == "full_name"
    assert report["case_type"] == "lowercase"
    assert report["values_changed"] == 5

    assert begin_conn.execute.called
    query_str = str(begin_conn.execute.call_args[0][0])
    assert "UPDATE `test_db`.`users__cleaning_abc123`" in query_str
    assert "SET `full_name` = LOWER(`full_name`)" in query_str


# ----------------------------------------------------------------------
# 3. UPPERCASE transformation tests
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_normalize_casing_uppercase(mock_inspect):
    """Test normalizing a text column to UPPERCASE."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "city", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector

    count_mock = MagicMock()
    count_mock.scalar.return_value = 8
    conn.execute.side_effect = [col_rows, count_mock]

    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    success, msg, report = normalize_text_case_workspace(
        mock_engine,
        "test_db",
        table,
        "city",
        "UPPERCASE",
    )

    assert success is True
    assert "Successfully normalized 8 value(s)" in msg
    assert report["operation"] == "Text Casing"
    assert report["case_type"] == "UPPERCASE"
    assert report["values_changed"] == 8

    query_str = str(begin_conn.execute.call_args[0][0])
    assert "SET `city` = UPPER(`city`)" in query_str


# ----------------------------------------------------------------------
# 4. Title Case transformation tests
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_normalize_casing_title_case(mock_inspect):
    """Test normalizing a text column to Title Case."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "city", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector

    # Mock grouped query: row 1 changes ('new york' -> 'New York', count 4), row 2 already title ('Chicago', count 2)
    group_row1 = MagicMock(_mapping={"val": "new york", "cnt": 4})
    group_row2 = MagicMock(_mapping={"val": "Chicago", "cnt": 2})
    group_res = [group_row1, group_row2]

    conn.execute.side_effect = [col_rows, group_res]

    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    success, msg, report = normalize_text_case_workspace(
        mock_engine,
        "test_db",
        table,
        "city",
        "Title Case",
    )

    assert success is True
    assert report["values_changed"] == 4
    assert report["case_type"] == "Title Case"

    assert begin_conn.execute.called
    stmt_call = begin_conn.execute.call_args
    assert "UPDATE `test_db`.`users__cleaning_abc123`" in str(stmt_call[0][0])
    # Parameterized batch check
    params = stmt_call[0][1]
    assert len(params) == 1
    assert params[0]["old_val"] == "new york"
    assert params[0]["new_val"] == "New York"


# ----------------------------------------------------------------------
# 5. Already normalized values not counted
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_already_normalized_values_not_counted(mock_inspect):
    """Test that zero rows are modified if all values are already normalized."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "status", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector

    count_mock = MagicMock()
    count_mock.scalar.return_value = 0
    conn.execute.side_effect = [col_rows, count_mock]

    success, msg, report = normalize_text_case_workspace(
        mock_engine,
        "test_db",
        table,
        "status",
        "lowercase",
    )

    assert success is True
    assert report["values_changed"] == 0
    assert "All values in column 'status' are already lowercase" in msg
    assert not mock_engine.begin.called


# ----------------------------------------------------------------------
# 6. Safety validations: invalid columns, types, case formats, source tables
# ----------------------------------------------------------------------


def test_source_table_rejection_safety():
    """Verify non-workspace / source tables are strictly rejected."""
    mock_engine = MagicMock()
    for bad_tbl in [
        "users",
        "users__cleaning",
        "users__cleaning_123__cleaning_456",
        "",
    ]:
        success, msg, report = normalize_text_case_workspace(
            mock_engine, "db", bad_tbl, "name", "lowercase"
        )
        assert success is False
        assert "Refusing to clean" in msg
        assert report == {}


@patch("src.staging.inspect")
def test_reject_numeric_column(mock_inspect):
    """Verify numeric columns are rejected."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "salary", "type": "int"}],
    )
    mock_inspect.return_value = inspector
    conn.execute.return_value = col_rows

    success, msg, report = normalize_text_case_workspace(
        mock_engine, "db", table, "salary", "lowercase"
    )
    assert success is False
    assert "not a supported text/string column" in msg


@patch("src.staging.inspect")
def test_reject_missing_column(mock_inspect):
    """Verify non-existent column names are rejected."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [{"name": "city", "type": "varchar"}],
    )
    mock_inspect.return_value = inspector
    conn.execute.return_value = col_rows

    success, msg, report = normalize_text_case_workspace(
        mock_engine, "db", table, "non_existent", "lowercase"
    )
    assert success is False
    assert "Column 'non_existent' not found" in msg


def test_reject_invalid_case_option():
    """Verify invalid casing formats are rejected."""
    mock_engine = MagicMock()
    success, msg, report = normalize_text_case_workspace(
        mock_engine, "db", "tbl__cleaning_123", "col", "camelCase"
    )
    assert success is False
    assert "Invalid case format 'camelCase'" in msg


# ----------------------------------------------------------------------
# 7. In-Memory SQLite End-to-End Tests (preserves NULLs, blanks, spaces)
# ----------------------------------------------------------------------


def test_sqlite_integration_preserves_nulls_blanks_and_whitespace():
    """Full database lifecycle test verifying lowercase, UPPERCASE, Title Case, whitespace preservation, NULLs, and empty strings."""
    engine = create_engine("sqlite:///:memory:")
    table_name = "customers__cleaning_xyz"

    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table_name} (id, name) VALUES
            (1, 'John DOE'),
            (2, 'john doe'),
            (3, 'JOHN DOE'),
            (4, ''),
            (5, NULL),
            (6, '  JOHN DOE  '),
            (7, 'Alice Smith')
        """))

    # Mock information_schema for SQLite test
    col_metadata = [{"name": "id", "type": "int"}, {"name": "name", "type": "text"}]

    with patch("src.staging.inspect") as mock_inspect, patch(
        "src.staging.get_text_columns"
    ) as mock_get_text_cols:

        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = [table_name]
        mock_inspect.return_value = mock_inspector
        mock_get_text_cols.return_value = ["name"]

        with patch.object(engine, "connect", wraps=engine.connect) as mock_conn_method:
            # We patch execute on the connection to handle information_schema.columns query
            orig_connect = engine.connect

            def patched_connect():
                c = orig_connect()
                orig_exec = c.execute

                def patched_exec(statement, parameters=None, *args, **kwargs):
                    if "INFORMATION_SCHEMA.COLUMNS" in str(statement):
                        res = MagicMock()
                        res.__iter__.return_value = [
                            MagicMock(
                                _mapping={
                                    "COLUMN_NAME": c["name"],
                                    "DATA_TYPE": c["type"],
                                }
                            )
                            for c in col_metadata
                        ]
                        return res
                    return orig_exec(statement, parameters, *args, **kwargs)

                c.execute = patched_exec
                return c

            engine.connect = patched_connect

            # 1. Preview changes for Title Case
            preview_count = count_text_casing_changes(
                engine, "main", table_name, "name", "Title Case"
            )
            # In the table:
            # 1: 'John DOE' -> 'John Doe' (changes)
            # 2: 'john doe' -> 'John Doe' (changes)
            # 3: 'JOHN DOE' -> 'John Doe' (changes)
            # 4: '' -> '' (no change)
            # 5: NULL -> NULL (no change)
            # 6: '  JOHN DOE  ' -> '  John Doe  ' (changes)
            # 7: 'Alice Smith' -> 'Alice Smith' (no change)
            # Total should be 4
            assert preview_count == 4

            # 2. Run Title Case
            ok, msg, report = normalize_text_case_workspace(
                engine, "main", table_name, "name", "Title Case"
            )
            assert ok is True
            assert report["values_changed"] == 4

            # Verify table contents
            with engine.connect() as conn:
                rows = conn.execute(
                    text(f"SELECT id, name FROM {table_name} ORDER BY id")
                ).fetchall()
                data = {r[0]: r[1] for r in rows}

                assert data[1] == "John Doe"
                assert data[2] == "John Doe"
                assert data[3] == "John Doe"
                assert data[4] == ""  # Empty string preserved!
                assert data[5] is None  # NULL preserved!
                assert data[6] == "  John Doe  "  # Whitespace preserved!
                assert data[7] == "Alice Smith"

            # 3. Preview changes for lowercase:
            # All 5 non-empty non-null rows have uppercase letters, so all 5 will change to lower
            lower_preview = count_text_casing_changes(
                engine, "main", table_name, "name", "lowercase"
            )
            assert lower_preview == 5

            ok, msg, report = normalize_text_case_workspace(
                engine, "main", table_name, "name", "lowercase"
            )
            assert ok is True
            assert report["values_changed"] == 5

            with engine.connect() as conn:
                rows = conn.execute(
                    text(f"SELECT id, name FROM {table_name} ORDER BY id")
                ).fetchall()
                data = {r[0]: r[1] for r in rows}
                assert data[1] == "john doe"
                assert data[4] == ""
                assert data[5] is None
                assert data[6] == "  john doe  "  # Whitespace preserved in lowercase!
                assert data[7] == "alice smith"

            # 4. Preview changes for UPPERCASE:
            upper_preview = count_text_casing_changes(
                engine, "main", table_name, "name", "UPPERCASE"
            )
            assert upper_preview == 5

            ok, msg, report = normalize_text_case_workspace(
                engine, "main", table_name, "name", "UPPERCASE"
            )
            assert ok is True
            assert report["values_changed"] == 5

            with engine.connect() as conn:
                rows = conn.execute(
                    text(f"SELECT id, name FROM {table_name} ORDER BY id")
                ).fetchall()
                data = {r[0]: r[1] for r in rows}
                assert data[1] == "JOHN DOE"
                assert data[4] == ""
                assert data[5] is None
                assert data[6] == "  JOHN DOE  "
                assert data[7] == "ALICE SMITH"


# ----------------------------------------------------------------------
# 8. Multi-Column Text Casing Normalization Tests
# ----------------------------------------------------------------------


@patch("src.staging.inspect")
def test_count_text_casing_changes_multi_column(mock_inspect):
    """Verify count_text_casing_changes calculates aggregated changes across multiple columns."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [
            {"name": "first_name", "type": "varchar"},
            {"name": "last_name", "type": "varchar"},
        ],
    )
    mock_inspect.return_value = inspector

    # For first_name count = 3, for last_name count = 5
    m1 = MagicMock()
    m1.scalar.return_value = 3
    m2 = MagicMock()
    m2.scalar.return_value = 5
    conn.execute.side_effect = [col_rows, m1, col_rows, m2]

    total_changes = count_text_casing_changes(
        mock_engine,
        "test_db",
        table,
        ["first_name", "last_name"],
        "lowercase",
    )

    assert total_changes == 8


@patch("src.staging.inspect")
def test_normalize_casing_multi_column_atomic(mock_inspect):
    """Verify normalize_text_case_workspace executes across multiple columns in one atomic transaction."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    inspector, conn, col_rows = _mock_inspector_and_columns(
        mock_engine,
        table,
        [
            {"name": "first_name", "type": "varchar"},
            {"name": "last_name", "type": "varchar"},
        ],
    )
    mock_inspect.return_value = inspector

    begin_conn = MagicMock()
    mock_engine.begin.return_value.__enter__.return_value = begin_conn

    # Counts on conn.execute, updates on begin_conn.execute
    c1 = MagicMock()
    c1.scalar.return_value = 4
    c2 = MagicMock()
    c2.scalar.return_value = 6
    conn.execute.side_effect = [col_rows, c1, c2]

    success, msg, report = normalize_text_case_workspace(
        mock_engine,
        "test_db",
        table,
        ["first_name", "last_name"],
        "UPPERCASE",
    )

    assert success is True
    assert "Successfully normalized 10 value(s) across 2 column(s)" in msg
    assert report["columns"] == ["first_name", "last_name"]
    assert report["column"] == "first_name, last_name"
    assert report["values_changed"] == 10
    assert report["case_type"] == "UPPERCASE"
    assert len(report["columns_affected"]) == 2
    assert report["columns_affected"][0] == {
        "column": "first_name",
        "values_changed": 4,
    }
    assert report["columns_affected"][1] == {"column": "last_name", "values_changed": 6}


def test_sqlite_integration_multi_column_casing():
    """End-to-end integration test verifying multi-column normalization in one go with SQLite."""
    engine = create_engine("sqlite:///:memory:")
    table_name = "employees__cleaning_mcol"

    with engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table_name} (
                id INTEGER PRIMARY KEY,
                first_name TEXT,
                last_name TEXT,
                department TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table_name} (id, first_name, last_name, department) VALUES
            (1, 'john', 'DOE', 'sales'),
            (2, 'Jane', 'smith', 'ENGINEERING'),
            (3, '', NULL, 'hr'),
            (4, '  bob  ', 'ROSS', 'support')
        """))

    col_metadata = [
        {"name": "id", "type": "int"},
        {"name": "first_name", "type": "text"},
        {"name": "last_name", "type": "text"},
        {"name": "department", "type": "text"},
    ]

    with patch("src.staging.inspect") as mock_inspect, patch(
        "src.staging.get_text_columns"
    ) as mock_get_text_cols:

        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = [table_name]
        mock_inspect.return_value = mock_inspector
        mock_get_text_cols.return_value = ["first_name", "last_name", "department"]

        orig_connect = engine.connect

        def patched_connect():
            c = orig_connect()
            orig_exec = c.execute

            def patched_exec(statement, parameters=None, *args, **kwargs):
                if "INFORMATION_SCHEMA.COLUMNS" in str(statement):
                    res = MagicMock()
                    res.__iter__.return_value = [
                        MagicMock(
                            _mapping={
                                "COLUMN_NAME": col["name"],
                                "DATA_TYPE": col["type"],
                            }
                        )
                        for col in col_metadata
                    ]
                    return res
                return orig_exec(statement, parameters, *args, **kwargs)

            c.execute = patched_exec
            return c

        engine.connect = patched_connect

        # 1. Preview changes across 3 columns for Title Case
        target_cols = ["first_name", "last_name", "department"]
        preview = count_text_casing_changes(
            engine, "main", table_name, target_cols, "Title Case"
        )
        # first_name: 'john' -> 'John' (1), '  bob  ' -> '  Bob  ' (1) => 2
        # last_name: 'DOE' -> 'Doe' (1), 'smith' -> 'Smith' (1), 'ROSS' -> 'Ross' (1) => 3
        # department: 'sales' -> 'Sales' (1), 'ENGINEERING' -> 'Engineering' (1), 'hr' -> 'Hr' (1), 'support' -> 'Support' (1) => 4
        # Total = 2 + 3 + 4 = 9
        assert preview == 9

        # 2. Execute Title Case normalization across all 3 columns in one go
        ok, msg, report = normalize_text_case_workspace(
            engine, "main", table_name, target_cols, "Title Case"
        )
        assert ok is True
        assert report["values_changed"] == 9
        assert len(report["columns_affected"]) == 3

        # Verify data in table
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id, first_name, last_name, department FROM {table_name} ORDER BY id"
                )
            ).fetchall()
            data = {r[0]: (r[1], r[2], r[3]) for r in rows}

            # row 1: 'John', 'Doe', 'Sales'
            assert data[1] == ("John", "Doe", "Sales")
            # row 2: 'Jane', 'Smith', 'Engineering'
            assert data[2] == ("Jane", "Smith", "Engineering")
            # row 3: '', None, 'Hr' (empty string and NULL preserved!)
            assert data[3] == ("", None, "Hr")
            # row 4: '  Bob  ', 'Ross', 'Support' (whitespace preserved!)
            assert data[4] == ("  Bob  ", "Ross", "Support")

        # 3. Apply lowercase across 2 columns: first_name and department
        ok_lower, msg_lower, rep_lower = normalize_text_case_workspace(
            engine, "main", table_name, ["first_name", "department"], "lowercase"
        )
        assert ok_lower is True
        # Verify first_name and department became lowercase, last_name stayed Title Case
        with engine.connect() as conn:
            rows = conn.execute(
                text(
                    f"SELECT id, first_name, last_name, department FROM {table_name} ORDER BY id"
                )
            ).fetchall()
            data2 = {r[0]: (r[1], r[2], r[3]) for r in rows}
            assert data2[1] == ("john", "Doe", "sales")
            assert data2[4] == ("  bob  ", "Ross", "support")
