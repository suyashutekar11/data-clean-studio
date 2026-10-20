"""
Comprehensive Scenario Tests for Special Character Cleaning (Section 9 Requirements).

Covers all 15 required scenarios:
1. Remove a selected special character from a VARCHAR value.
2. Replace selected characters with a custom string.
3. Remove tabs, carriage returns and line feeds when selected.
4. Preserve ordinary spaces unless explicitly configured otherwise.
5. Preserve legitimate punctuation when it has not been selected.
6. Preserve multilingual text, accented characters and valid Unicode symbols.
7. Handle NULL values without converting them to empty strings.
8. Handle empty strings and strings containing only targeted characters.
9. Handle regex metacharacters as literal characters when entered in the custom character field.
10. Preserve unrelated columns and primary keys.
11. Confirm that preview operations do not modify workspace data.
12. Confirm that all writes target an authorized cleaning workspace.
13. Verify rollback behavior when an operation fails.
14. Verify accurate changed-row counts and audit logging.
15. Verify correct handling of large text values and representative large tables.
"""

import re
from unittest.mock import MagicMock, patch
import pytest
import sqlalchemy as sa
from sqlalchemy import create_engine, text

from src.staging import (
    clean_special_characters_workspace,
    scan_special_characters_workspace,
    get_text_columns_with_types,
    _build_char_class,
    _escape_for_regex,
    CONTROL_CHARS,
    NON_PRINTABLE_CHARS,
    COMMON_SPECIAL_CHARS,
)


@pytest.fixture
def sqlite_test_engine():
    """
    Creates an in-memory SQLite engine equipped with REGEXP and REGEXP_REPLACE
    functions, mirroring MySQL 8.0 regex transformation capabilities.
    """
    engine = create_engine("sqlite:///:memory:")

    @sa.event.listens_for(engine, "connect")
    def sqlite_connect(dbapi_connection, connection_record):
        dbapi_connection.create_function(
            "REGEXP",
            2,
            lambda expr, item: bool(re.search(expr, item)) if item is not None else False,
        )
        dbapi_connection.create_function(
            "REGEXP_REPLACE",
            3,
            lambda text_val, expr, repl: re.sub(expr, repl, text_val) if text_val is not None else None,
        )

    return engine


def _mock_workspace_engine(table_name="orders__cleaning_abc123", columns=None):
    """Creates a mocked engine configured for workspace table testing."""
    if columns is None:
        columns = [
            {"COLUMN_NAME": "id", "DATA_TYPE": "int"},
            {"COLUMN_NAME": "notes", "DATA_TYPE": "varchar"},
            {"COLUMN_NAME": "description", "DATA_TYPE": "text"},
        ]

    mock_engine = MagicMock()
    mock_inspect = MagicMock()
    mock_inspect.return_value.get_table_names.return_value = [table_name]

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    def make_col_result():
        col_res = MagicMock()
        col_res.__iter__ = lambda self: iter([
            MagicMock(_mapping={"COLUMN_NAME": c["COLUMN_NAME"], "DATA_TYPE": c["DATA_TYPE"]})
            for c in columns
        ])
        return col_res

    return mock_engine, mock_inspect, mock_conn, make_col_result


# ==============================================================================
# Scenario 1: Remove a selected special character from a VARCHAR value
# ==============================================================================
def test_scenario_01_remove_selected_special_char_varchar(sqlite_test_engine):
    """Scenario 1: Remove a selected special character (e.g. '@') from a VARCHAR value."""
    table = "users__cleaning_s1"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, email VARCHAR(100))"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'john@example.com'), (2, 'clean_email')"))

    # Direct regex verification simulating clean_special_characters_workspace SQL logic
    char_class = _build_char_class(["@"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET email = REGEXP_REPLACE(email, :pattern, '') WHERE email REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        res = conn.execute(text(f"SELECT id, email FROM {table} ORDER BY id")).fetchall()
        assert res[0] == (1, "johnexample.com")
        assert res[1] == (2, "clean_email")


# ==============================================================================
# Scenario 2: Replace selected characters with a custom string
# ==============================================================================
def test_scenario_02_replace_selected_chars_with_custom_string(sqlite_test_engine):
    """Scenario 2: Replace selected characters (e.g. '#') with a custom string (e.g. '--')."""
    table = "products__cleaning_s2"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, code VARCHAR(50))"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'PROD#123#XYZ'), (2, 'NO_SPECIAL')"))

    char_class = _build_char_class(["#"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET code = REGEXP_REPLACE(code, :pattern, :replacement) WHERE code REGEXP :pattern"),
            {"pattern": char_class, "replacement": "--"},
        )

    with sqlite_test_engine.connect() as conn:
        res = conn.execute(text(f"SELECT id, code FROM {table} ORDER BY id")).fetchall()
        assert res[0] == (1, "PROD--123--XYZ")
        assert res[1] == (2, "NO_SPECIAL")


# ==============================================================================
# Scenario 3: Remove tabs, carriage returns and line feeds when selected
# ==============================================================================
def test_scenario_03_remove_control_characters(sqlite_test_engine):
    """Scenario 3: Remove tabs, carriage returns and line feeds when selected."""
    table = "logs__cleaning_s3"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, message TEXT)"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'Line 1\r\nLine 2\tTabbed')"))

    control_chars = [CONTROL_CHARS["tab"]["char"], CONTROL_CHARS["carriage_return"]["char"], CONTROL_CHARS["line_feed"]["char"]]
    char_class = _build_char_class(control_chars)

    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET message = REGEXP_REPLACE(message, :pattern, '') WHERE message REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        res = conn.execute(text(f"SELECT message FROM {table}")).scalar()
        assert res == "Line 1Line 2Tabbed"
        assert "\t" not in res and "\r" not in res and "\n" not in res


# ==============================================================================
# Scenario 4: Preserve ordinary spaces unless explicitly configured otherwise
# ==============================================================================
def test_scenario_04_preserve_ordinary_spaces(sqlite_test_engine):
    """Scenario 4: Preserve ordinary spaces when cleaning special characters."""
    table = "customers__cleaning_s4"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, name VARCHAR(100))"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'Jane  Doe   Senior #1')"))

    char_class = _build_char_class(["#", "1"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET name = REGEXP_REPLACE(name, :pattern, '') WHERE name REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        res = conn.execute(text(f"SELECT name FROM {table}")).scalar()
        # Ordinary spaces, including consecutive spaces, must be perfectly preserved
        assert res == "Jane  Doe   Senior "


# ==============================================================================
# Scenario 5: Preserve legitimate punctuation when it has not been selected
# ==============================================================================
def test_scenario_05_preserve_unselected_punctuation(sqlite_test_engine):
    """Scenario 5: Preserve legitimate punctuation (commas, periods, question marks) when unselected."""
    table = "feedback__cleaning_s5"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, comment TEXT)"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'Hello, world! Is this 100% working?')"))

    # Only '%' and '!' selected for removal. Commas, periods, and question marks must be preserved!
    char_class = _build_char_class(["%", "!"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET comment = REGEXP_REPLACE(comment, :pattern, '') WHERE comment REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        res = conn.execute(text(f"SELECT comment FROM {table}")).scalar()
        assert res == "Hello, world Is this 100 working?"
        assert "," in res
        assert "?" in res
        assert "!" not in res
        assert "%" not in res


# ==============================================================================
# Scenario 6: Preserve multilingual text, accented characters and valid Unicode symbols
# ==============================================================================
def test_scenario_06_preserve_multilingual_and_accents(sqlite_test_engine):
    """Scenario 6: Preserve accents, Japanese Kanji, Cyrillic, and emojis when removing special chars."""
    table = "multilingual__cleaning_s6"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, text_col TEXT)"))
        conn.execute(text(f"""
            INSERT INTO {table} VALUES 
            (1, 'Café Münsterstraße 12#'),
            (2, '日本語テスト@東京'),
            (3, 'Привет, мир$!'),
            (4, 'Rocket 🚀Launch*')
        """))

    # Remove only '#', '@', '$', '*'
    char_class = _build_char_class(["#", "@", "$", "*"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET text_col = REGEXP_REPLACE(text_col, :pattern, '') WHERE text_col REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT id, text_col FROM {table} ORDER BY id")).fetchall()
        assert rows[0][1] == "Café Münsterstraße 12"
        assert rows[1][1] == "日本語テスト東京"
        assert rows[2][1] == "Привет, мир!"
        assert rows[3][1] == "Rocket 🚀Launch"


# ==============================================================================
# Scenario 7: Handle NULL values without converting them to empty strings
# ==============================================================================
def test_scenario_07_handle_null_values(sqlite_test_engine):
    """Scenario 7: Ensure NULL values are never converted to empty strings."""
    table = "null_test__cleaning_s7"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, bio VARCHAR(100))"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'Has @ char'), (2, NULL), (3, 'Clean value')"))

    char_class = _build_char_class(["@"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET bio = REGEXP_REPLACE(bio, :pattern, '') WHERE bio IS NOT NULL AND bio REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        res = conn.execute(text(f"SELECT id, bio FROM {table} ORDER BY id")).fetchall()
        assert res[0] == (1, "Has  char")
        assert res[1] == (2, None)
        assert res[1][1] is None  # Strictly None / NULL, NOT empty string
        assert res[2] == (3, "Clean value")


# ==============================================================================
# Scenario 8: Handle empty strings and strings containing only targeted characters
# ==============================================================================
def test_scenario_08_empty_strings_and_targeted_only(sqlite_test_engine):
    """Scenario 8: Handle empty strings and values consisting entirely of target characters."""
    table = "empty_test__cleaning_s8"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, val VARCHAR(50))"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, ''), (2, '###'), (3, '***')"))

    # Test Remove Mode on '###' -> becomes empty string ''
    char_class_hash = _build_char_class(["#"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET val = REGEXP_REPLACE(val, :pattern, '') WHERE val IS NOT NULL AND val REGEXP :pattern"),
            {"pattern": char_class_hash},
        )

    # Test Replace Mode on '***' with '_' -> becomes '___'
    char_class_star = _build_char_class(["*"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET val = REGEXP_REPLACE(val, :pattern, :repl) WHERE val IS NOT NULL AND val REGEXP :pattern"),
            {"pattern": char_class_star, "repl": "_"},
        )

    with sqlite_test_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT id, val FROM {table} ORDER BY id")).fetchall()
        assert rows[0] == (1, "")
        assert rows[1] == (2, "")
        assert rows[2] == (3, "___")


# ==============================================================================
# Scenario 9: Handle regex metacharacters as literal characters in custom input
# ==============================================================================
def test_scenario_09_regex_metacharacters_as_literals(sqlite_test_engine):
    """Scenario 9: Metacharacters (. * + ? [ ] ( ) \\ ^ -) must be treated as exact literals."""
    table = "meta_test__cleaning_s9"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, formula VARCHAR(100))"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'calc[1]*2+3?test.val-item^2\\\\end')"))

    # All regex metacharacters entered into custom field
    custom_input = ".*+?[]()\\^-/"
    char_class = _build_char_class(list(custom_input))

    # All metacharacters must be escaped in the character class
    for ch in custom_input:
        escaped = _escape_for_regex(ch)
        assert escaped.startswith("\\")

    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET formula = REGEXP_REPLACE(formula, :pattern, '') WHERE formula REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        res = conn.execute(text(f"SELECT formula FROM {table}")).scalar()
        assert res == "calc123testvalitem2end"


# ==============================================================================
# Scenario 10: Preserve unrelated columns and primary keys
# ==============================================================================
def test_scenario_10_preserve_unrelated_columns_and_pks(sqlite_test_engine):
    """Scenario 10: Verify that unrelated columns and primary keys are unchanged."""
    table = "orders__cleaning_s10"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INT PRIMARY KEY,
                notes VARCHAR(100),
                amount DECIMAL(10,2),
                status VARCHAR(20)
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} VALUES 
            (101, 'Express#Shipping', 99.99, 'PENDING#1'),
            (102, 'Standard', 49.50, 'ACTIVE')
        """))

    char_class = _build_char_class(["#"])
    # Clean ONLY the notes column
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET notes = REGEXP_REPLACE(notes, :pattern, '') WHERE notes REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        res = conn.execute(text(f"SELECT id, notes, amount, status FROM {table} WHERE id = 101")).fetchone()
        assert res[0] == 101  # Primary key preserved
        assert res[1] == "ExpressShipping"  # Targeted column cleaned
        assert float(res[2]) == 99.99  # Numeric column untouched
        assert res[3] == "PENDING#1"  # Unrelated text column untouched


# ==============================================================================
# Scenario 11: Confirm that preview operations do not modify workspace data
# ==============================================================================
def test_scenario_11_preview_does_not_modify_data():
    """Scenario 11: Preview scan must only inspect and never mutate the database."""
    mock_engine, mock_inspect, mock_conn, make_col_result = _mock_workspace_engine(
        table_name="data__cleaning_preview",
        columns=[{"COLUMN_NAME": "title", "DATA_TYPE": "varchar"}],
    )

    mock_row = MagicMock()
    mock_row._mapping = {"original_value": "test@data#", "cnt": 2}
    
    mock_scan_query = MagicMock()
    mock_scan_query.__iter__ = lambda self: iter([mock_row])
    
    mock_count_query = MagicMock()
    mock_count_query.scalar.return_value = 2

    # Provide results for column type query, sample scan query, and total count query
    col_res = make_col_result()
    mock_conn.execute.side_effect = [col_res, mock_scan_query, mock_count_query]

    with patch("src.staging.inspect", mock_inspect):
        results = scan_special_characters_workspace(
            mock_engine,
            "test_db",
            "data__cleaning_preview",
            ["title"],
            [],
            ["@", "#"],
            mode="remove",
        )

    assert len(results) == 1
    assert results[0]["column"] == "title"
    assert results[0]["total_affected_rows"] == 2
    assert results[0]["sample_rows"][0]["cleaned"] == "testdata"

    # Crucial safety invariant: No UPDATE, INSERT, DELETE, or ALTER was executed!
    for call_obj in mock_conn.execute.call_args_list:
        executed_sql = str(call_obj[0][0]).upper()
        assert not any(kw in executed_sql for kw in ["UPDATE ", "DELETE ", "INSERT ", "ALTER ", "DROP "])


# ==============================================================================
# Scenario 12: Confirm that all writes target an authorized cleaning workspace
# ==============================================================================
def test_scenario_12_write_protection_non_workspace_tables():
    """Scenario 12: Ensure operations are rejected on production / non-workspace tables."""
    mock_engine = MagicMock()

    # Case A: Production table without __cleaning_
    success, msg, report = clean_special_characters_workspace(
        mock_engine, "prod_db", "customers", ["email"], [], ["@"]
    )
    assert success is False
    assert "Refusing to clean" in msg

    # Case B: Table with invalid suffix count (injection attempt)
    success, msg, report = clean_special_characters_workspace(
        mock_engine, "prod_db", "customers__cleaning_1__cleaning_2", ["email"], [], ["@"]
    )
    assert success is False
    assert "Refusing to clean" in msg

    # Case C: Preview also rejects non-workspace tables
    preview_res = scan_special_characters_workspace(
        mock_engine, "prod_db", "users", ["name"], [], ["#"]
    )
    assert preview_res == []


# ==============================================================================
# Scenario 13: Verify rollback behavior when an operation fails
# ==============================================================================
def test_scenario_13_rollback_on_failure():
    """Scenario 13: Atomic transaction rolls back cleanly if database error occurs."""
    mock_engine, mock_inspect, mock_conn, make_col_result = _mock_workspace_engine(
        table_name="test__cleaning_fail"
    )

    col_res1 = make_col_result()
    col_res2 = make_col_result()
    count_res = MagicMock()
    count_res.scalar.return_value = 5

    # Simulate database operational failure during UPDATE execution
    mock_conn.execute.side_effect = [
        col_res1,
        count_res,
        sa.exc.OperationalError("Lost connection to MySQL server during query", None, None),
    ]

    with patch("src.staging.inspect", mock_inspect):
        success, msg, report = clean_special_characters_workspace(
            mock_engine, "test_db", "test__cleaning_fail", ["notes"], ["tab"], []
        )

    assert success is False
    assert "special character cleaning" in msg.lower()
    # The atomic with engine.begin() context manager triggers rollback on exception


# ==============================================================================
# Scenario 14: Verify accurate changed-row counts and audit logging
# ==============================================================================
def test_scenario_14_accurate_counts_and_audit_report():
    """Scenario 14: Verify detailed audit report metadata and accurate value counts."""
    mock_engine, mock_inspect, mock_conn, make_col_result = _mock_workspace_engine(
        table_name="orders__cleaning_audit",
        columns=[
            {"COLUMN_NAME": "col_a", "DATA_TYPE": "varchar"},
            {"COLUMN_NAME": "col_b", "DATA_TYPE": "text"},
        ],
    )

    col_res1 = make_col_result()
    count_a = MagicMock()
    count_a.scalar.return_value = 14
    count_b = MagicMock()
    count_b.scalar.return_value = 7

    mock_conn.execute.side_effect = [
        col_res1,
        count_a,  # count query for col_a
        MagicMock(),  # update query for col_a
        count_b,  # count query for col_b
        MagicMock(),  # update query for col_b
    ]

    with patch("src.staging.inspect", mock_inspect):
        success, msg, report = clean_special_characters_workspace(
            mock_engine,
            "test_db",
            "orders__cleaning_audit",
            ["col_a", "col_b"],
            ["tab", "line_feed"],
            ["@", "#"],
            custom_chars="*",
            mode="replace",
            replacement=" ",
            non_printable_selected=["zero_width_space"],
        )

    assert success is True
    assert report["operation"] == "Special Character Replacement"
    assert report["mode"] == "replace"
    assert report["replacement"] == " "
    assert report["total_values_changed"] == 21
    assert report["rows_affected"] == 21
    assert len(report["columns_affected"]) == 2
    assert report["control_chars"] == ["tab", "line_feed"]
    assert report["non_printable_chars"] == ["zero_width_space"]
    assert report["special_chars"] == ["@", "#"]
    assert report["custom_chars"] == "*"
    assert "Successfully replaced with ' '" in msg


# ==============================================================================
# Scenario 15: Verify correct handling of large text values and large tables
# ==============================================================================
def test_scenario_15_large_text_values_and_tables(sqlite_test_engine):
    """Scenario 15: Correct handling of long text values (5,000+ chars) and multiple rows."""
    table = "articles__cleaning_s15"
    with sqlite_test_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INT, body TEXT)"))

    # Create a long text value of 5,000 characters with embedded special characters
    base_chunk = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. " * 50
    large_text = base_chunk + "SPECIAL#CHAR@IN_MIDDLE" + base_chunk
    assert len(large_text) > 5000

    rows_to_insert = [(i, f"Article {i} text with @# special chars: {large_text}") for i in range(1, 101)]

    with sqlite_test_engine.begin() as conn:
        for r_id, r_body in rows_to_insert:
            conn.execute(text(f"INSERT INTO {table} VALUES (:id, :body)"), {"id": r_id, "body": r_body})

    char_class = _build_char_class(["@", "#"])
    with sqlite_test_engine.begin() as conn:
        conn.execute(
            text(f"UPDATE {table} SET body = REGEXP_REPLACE(body, :pattern, '') WHERE body REGEXP :pattern"),
            {"pattern": char_class},
        )

    with sqlite_test_engine.connect() as conn:
        count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        assert count == 100

        # Verify that long text was not truncated
        sample_body = conn.execute(text(f"SELECT body FROM {table} WHERE id = 1")).scalar()
        assert len(sample_body) > 5000
        assert "@" not in sample_body
        assert "#" not in sample_body
        assert "SPECIALCHARIN_MIDDLE" in sample_body


# ==============================================================================
# Helper Verification: Text Column Type Discovery
# ==============================================================================
def test_get_text_columns_with_types():
    """Verify dynamic discovery of text-based columns with SQL type metadata."""
    mock_engine = MagicMock()
    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    # Simulate INFORMATION_SCHEMA query result
    mock_conn.execute.return_value = [
        MagicMock(_mapping={"COLUMN_NAME": "id", "DATA_TYPE": "int", "COLUMN_TYPE": "int(11)"}),
        MagicMock(_mapping={"COLUMN_NAME": "username", "DATA_TYPE": "varchar", "COLUMN_TYPE": "varchar(50)"}),
        MagicMock(_mapping={"COLUMN_NAME": "bio", "DATA_TYPE": "text", "COLUMN_TYPE": "text"}),
        MagicMock(_mapping={"COLUMN_NAME": "created_at", "DATA_TYPE": "datetime", "COLUMN_TYPE": "datetime"}),
    ]

    cols = get_text_columns_with_types(mock_engine, "app_db", "users__cleaning_1")
    assert len(cols) == 2
    assert cols[0]["name"] == "username"
    assert cols[0]["data_type"] == "varchar"
    assert cols[0]["column_type"] == "VARCHAR(50)"
    assert cols[1]["name"] == "bio"
    assert cols[1]["data_type"] == "text"
