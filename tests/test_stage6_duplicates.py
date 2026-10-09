import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine, text

from src.staging import (
    detect_duplicates_workspace,
    remove_duplicates_workspace,
    remove_duplicates_by_row_ids,
    init_duplicate_row_actions,
    set_group_row_action,
    apply_select_all_action,
    toggle_row_remove_action,
    is_group_all_removed,
    format_row_compact_summary,
)


def _mock_inspector_and_columns(
    mock_engine, table_name, columns_metadata, pk_cols=None
):
    """Helper to mock table inspection, column query, and primary key constraints."""
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = [table_name]
    mock_inspector.get_columns.return_value = [
        {"name": col["name"], "type": col["type"]} for col in columns_metadata
    ]
    mock_inspector.get_pk_constraint.return_value = {
        "constrained_columns": pk_cols or []
    }

    mock_conn = MagicMock()
    mock_engine.connect.return_value.__enter__.return_value = mock_conn

    mock_result = [
        MagicMock(_mapping={"COLUMN_NAME": col["name"], "DATA_TYPE": col["type"]})
        for col in columns_metadata
    ]
    return mock_inspector, mock_conn, mock_result


# ----------------------------------------------------------------------
# 1. Safety Validations
# ----------------------------------------------------------------------


def test_source_table_rejection_safety():
    """Verify non-workspace / source tables are strictly rejected by both functions."""
    mock_engine = MagicMock()
    for bad_tbl in ["users", "users__cleaning", "users__cleaning_1__cleaning_2", ""]:
        ok_d, msg_d, rep_d = detect_duplicates_workspace(
            mock_engine, "test_db", bad_tbl, ["email"]
        )
        assert ok_d is False
        assert "Refusing to inspect" in msg_d

        ok_r, msg_r, rep_r = remove_duplicates_workspace(
            mock_engine, "test_db", bad_tbl, ["email"]
        )
        assert ok_r is False
        assert "Refusing to clean" in msg_r


def test_reject_empty_keys_or_invalid_column():
    """Verify empty duplicate keys or non-existent columns are rejected."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"

    # Empty list
    ok, msg, _ = detect_duplicates_workspace(mock_engine, "test_db", table, [])
    assert ok is False
    assert "at least one duplicate key column" in msg

    # Invalid column
    with patch("src.staging.inspect") as mock_inspect:
        inspector, conn, _ = _mock_inspector_and_columns(
            mock_engine,
            table,
            [{"name": "id", "type": "int"}, {"name": "email", "type": "varchar"}],
        )
        mock_inspect.return_value = inspector
        ok2, msg2, _ = detect_duplicates_workspace(
            mock_engine, "test_db", table, ["non_existent"]
        )
        assert ok2 is False
        assert "not found in table" in msg2


def test_reject_invalid_retention_strategy():
    """Verify invalid retention strategy is rejected."""
    mock_engine = MagicMock()
    table = "users__cleaning_abc123"
    with patch("src.staging.inspect") as mock_inspect:
        inspector, conn, _ = _mock_inspector_and_columns(
            mock_engine,
            table,
            [{"name": "id", "type": "int"}, {"name": "email", "type": "varchar"}],
        )
        mock_inspect.return_value = inspector
        ok, msg, _ = detect_duplicates_workspace(
            mock_engine, "test_db", table, ["email"], retention_strategy="Keep Middle"
        )
        assert ok is False
        assert "Invalid retention strategy" in msg


# ----------------------------------------------------------------------
# 2. In-Memory SQLite Unit & Integration Tests
# ----------------------------------------------------------------------


@pytest.fixture
def sqlite_engine():
    """Create an in-memory SQLite engine with a workspace table."""
    engine = create_engine("sqlite:///:memory:")
    return engine


def test_detect_duplicates_single_column(sqlite_engine):
    """Test duplicate detection on a single column with correct counts."""
    table = "customers__cleaning_t1"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT,
                name TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email, name) VALUES
            (1, 'a@gmail.com', 'Alice 1'),
            (2, 'b@gmail.com', 'Bob'),
            (3, 'a@gmail.com', 'Alice 2'),
            (4, 'c@gmail.com', 'Charlie'),
            (5, 'a@gmail.com', 'Alice 3')
        """))

    ok, msg, report = detect_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], "Keep First"
    )

    assert ok is True
    assert report["duplicate_group_count"] == 1  # only a@gmail.com
    assert report["duplicate_row_count"] == 3  # 3 rows with a@gmail.com
    assert report["rows_to_remove"] == 2  # 3 - 1 = 2
    assert report["retention_strategy"] == "Keep First"
    assert report["has_primary_key"] is True
    assert report["primary_key_columns"] == ["id"]
    assert len(report["preview_rows"]) == 3
    # Check preview row actions
    actions = [r["__action"] for r in report["preview_rows"]]
    assert actions == ["Keep", "Remove", "Remove"]


def test_detect_duplicates_multi_column(sqlite_engine):
    """Test multi-column duplicate key detection."""
    table = "contacts__cleaning_t2"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT,
                phone TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email, phone) VALUES
            (1, 'a@gmail.com', '111'),
            (2, 'a@gmail.com', '222'),
            (3, 'a@gmail.com', '111'),
            (4, 'b@gmail.com', '111')
        """))

    # Only rows 1 and 3 match on BOTH email and phone
    ok, msg, report = detect_duplicates_workspace(
        sqlite_engine, "main", table, ["email", "phone"]
    )
    assert ok is True
    assert report["duplicate_group_count"] == 1
    assert report["duplicate_row_count"] == 2
    assert report["rows_to_remove"] == 1


def test_detect_duplicates_no_duplicates(sqlite_engine):
    """Test detection when all rows are unique."""
    table = "items__cleaning_t3"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                code TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, code) VALUES
            (1, 'A'),
            (2, 'B'),
            (3, 'C')
        """))

    ok, msg, report = detect_duplicates_workspace(
        sqlite_engine, "main", table, ["code"]
    )
    assert ok is True
    assert report["duplicate_group_count"] == 0
    assert report["duplicate_row_count"] == 0
    assert report["rows_to_remove"] == 0
    assert report["preview_rows"] == []
    assert "No duplicate records detected" in msg


def test_detect_duplicates_all_rows_duplicates(sqlite_engine):
    """Test detection when all rows share the same duplicate key."""
    table = "logs__cleaning_t4"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                status TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, status) VALUES
            (1, 'active'),
            (2, 'active'),
            (3, 'active'),
            (4, 'active')
        """))

    ok, msg, report = detect_duplicates_workspace(
        sqlite_engine, "main", table, ["status"]
    )
    assert ok is True
    assert report["duplicate_group_count"] == 1
    assert report["duplicate_row_count"] == 4
    assert report["rows_to_remove"] == 3


def test_detect_duplicates_single_row_and_empty_table(sqlite_engine):
    """Test edge cases: single row table and empty table."""
    # Empty table
    tbl_empty = "empty__cleaning_t5"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {tbl_empty} (id INT, val TEXT)"))

    ok, _, rep = detect_duplicates_workspace(sqlite_engine, "main", tbl_empty, ["val"])
    assert ok is True
    assert rep["rows_to_remove"] == 0

    # Single row table
    tbl_single = "single__cleaning_t6"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {tbl_single} (id INT, val TEXT)"))
        conn.execute(text(f"INSERT INTO {tbl_single} VALUES (1, 'only')"))

    ok2, _, rep2 = detect_duplicates_workspace(
        sqlite_engine, "main", tbl_single, ["val"]
    )
    assert ok2 is True
    assert rep2["rows_to_remove"] == 0


def test_null_handling_in_duplicate_keys(sqlite_engine):
    """Verify SQL NULL values are treated as equal for grouping, and unique NULLs are kept."""
    table = "nulls__cleaning_t7"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT,
                dept TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email, dept) VALUES
            (1, NULL, 'sales'),
            (2, NULL, 'sales'),
            (3, NULL, 'hr'),
            (4, 'abc@gmail.com', 'sales')
        """))

    # When key is (email, dept): rows 1 and 2 share (NULL, 'sales') -> duplicates!
    # Row 3 has (NULL, 'hr') -> unique!
    ok, msg, report = detect_duplicates_workspace(
        sqlite_engine, "main", table, ["email", "dept"]
    )
    assert ok is True
    assert report["duplicate_group_count"] == 1
    assert report["duplicate_row_count"] == 2
    assert report["rows_to_remove"] == 1


def test_empty_string_handling_in_duplicate_keys(sqlite_engine):
    """Verify empty string values '' are treated as equal duplicates."""
    table = "blanks__cleaning_t8"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                code TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, code) VALUES
            (1, ''),
            (2, ''),
            (3, 'VALID')
        """))

    ok, msg, report = detect_duplicates_workspace(
        sqlite_engine, "main", table, ["code"]
    )
    assert ok is True
    assert report["duplicate_group_count"] == 1
    assert report["duplicate_row_count"] == 2
    assert report["rows_to_remove"] == 1


def test_remove_duplicates_keep_first_with_pk(sqlite_engine):
    """Verify Keep First preserves lowest primary key and removes subsequent duplicates."""
    table = "users__cleaning_kf"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT,
                score INT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email, score) VALUES
            (1, 'dup@test.com', 10),
            (2, 'unique@test.com', 50),
            (3, 'dup@test.com', 20),
            (4, 'dup@test.com', 30)
        """))

    ok, msg, report = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], "Keep First"
    )

    assert ok is True
    assert report["rows_removed"] == 2
    assert report["remaining_rows"] == 2
    assert report["duplicate_groups"] == 1

    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT id, email, score FROM {table} ORDER BY id")
        ).fetchall()
        data = {r[0]: (r[1], r[2]) for r in rows}
        # Row 1 kept (first row with dup@test.com), Row 2 kept (unique)
        assert 1 in data
        assert 2 in data
        assert 3 not in data
        assert 4 not in data
        assert data[1] == ("dup@test.com", 10)


def test_remove_duplicates_keep_last_with_pk(sqlite_engine):
    """Verify Keep Last preserves highest primary key and removes earlier duplicates."""
    table = "users__cleaning_kl"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT,
                score INT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email, score) VALUES
            (1, 'dup@test.com', 10),
            (2, 'dup@test.com', 20),
            (3, 'dup@test.com', 30),
            (4, 'unique@test.com', 99)
        """))

    ok, msg, report = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], "Keep Last"
    )

    assert ok is True
    assert report["rows_removed"] == 2
    assert report["remaining_rows"] == 2

    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT id, email, score FROM {table} ORDER BY id")
        ).fetchall()
        data = {r[0]: (r[1], r[2]) for r in rows}
        # Row 3 kept (highest PK for dup@test.com), Row 4 kept (unique)
        assert 1 not in data
        assert 2 not in data
        assert 3 in data
        assert 4 in data
        assert data[3] == ("dup@test.com", 30)


def test_remove_duplicates_composite_pk(sqlite_engine):
    """Verify removal with composite primary key."""
    table = "orders__cleaning_cpk"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                tenant_id INT,
                order_id INT,
                customer_email TEXT,
                PRIMARY KEY (tenant_id, order_id)
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (tenant_id, order_id, customer_email) VALUES
            (10, 1, 'c1@test.com'),
            (10, 2, 'c1@test.com'),
            (10, 3, 'c2@test.com')
        """))

    ok, msg, report = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["customer_email"], "Keep First"
    )
    assert ok is True
    assert report["rows_removed"] == 1
    assert report["remaining_rows"] == 2

    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT tenant_id, order_id FROM {table} ORDER BY order_id")
        ).fetchall()
        assert rows == [(10, 1), (10, 3)]


def test_remove_duplicates_no_pk_table(sqlite_engine):
    """Verify deduplication works on a table without any Primary Key."""
    table = "legacy__cleaning_nopk"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                name TEXT,
                email TEXT,
                city TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (name, email, city) VALUES
            ('Alice', 'a@test.com', 'New York'),
            ('Alice', 'a@test.com', 'New York'),
            ('Bob', 'b@test.com', 'Chicago'),
            ('Alice 2', 'a@test.com', 'Boston')
        """))

    # Key = email, Keep First
    ok, msg, report = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], "Keep First"
    )
    assert ok is True
    assert report["rows_removed"] == 2
    assert report["remaining_rows"] == 2
    assert report["has_primary_key"] is False
    assert report["warning"] is not None

    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT name, email FROM {table} ORDER BY email")
        ).fetchall()
        # Should have exactly 1 record for a@test.com and 1 for b@test.com
        emails = [r[1] for r in rows]
        assert emails == ["a@test.com", "b@test.com"]


def test_remove_duplicates_zero_duplicates_workspace_unaltered(sqlite_engine):
    """Verify that if zero duplicates exist, workspace is not modified."""
    table = "clean__cleaning_zero"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                val TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} VALUES (1, 'X'), (2, 'Y')
        """))

    ok, msg, report = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["val"], "Keep First"
    )
    assert ok is True
    assert report["rows_removed"] == 0
    assert report["remaining_rows"] == 2
    assert "No duplicate records found" in msg


def test_failed_deletion_atomic_rollback(sqlite_engine):
    """Verify rollback if an exception occurs during deletion."""
    table = "fault__cleaning_err"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                val TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} VALUES (1, 'A'), (2, 'A')
        """))

    # Simulate database failure during delete statement execution
    with patch.object(sqlite_engine, "begin") as mock_begin:
        mock_conn = MagicMock()
        mock_conn.execute.side_effect = RuntimeError("Simulated DB error")
        mock_begin.return_value.__enter__.return_value = mock_conn

        ok, msg, rep = remove_duplicates_workspace(
            sqlite_engine, "main", table, ["val"]
        )
        assert ok is False
        assert "Simulated DB error" in msg

    # Ensure original rows in table are intact
    with sqlite_engine.connect() as conn:
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        assert cnt == 2


# ----------------------------------------------------------------------
# 3. Record-Level Decision Making Unit & Integration Tests
# ----------------------------------------------------------------------


def test_detect_duplicates_returns_structured_groups(sqlite_engine):
    """Verify detect_duplicates_workspace returns structured duplicate groups with default KEEP."""
    table = "users__cleaning_struct"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                name TEXT,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, name, email) VALUES
            (8, 'Pooja More', 'pooja@gmail.com'),
            (14, 'Pooja More', 'pooja@gmail.com')
        """))

    ok, msg, report = detect_duplicates_workspace(
        sqlite_engine, "main", table, ["email"]
    )
    assert ok is True
    assert "groups" in report
    assert len(report["groups"]) == 1

    group = report["groups"][0]
    assert group["group_id"] == "group_1"
    assert group["group_num"] == 1
    assert group["key_values"] == {"email": "pooja@gmail.com"}
    assert group["default_keep_id"] == 8
    assert len(group["rows"]) == 2

    r1, r2 = group["rows"]
    assert r1["row_id"] == 8
    assert r1["is_default"] is True
    assert r2["row_id"] == 14
    assert r2["is_default"] is False


def test_remove_duplicates_user_selects_first_record(sqlite_engine):
    """Verify user can explicitly select the first record (order_id 8) to KEEP."""
    table = "orders__cleaning_sel1"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (order_id, customer_name, email) VALUES
            (8, 'Pooja More', 'pooja@gmail.com'),
            (14, 'Pooja More', 'pooja@gmail.com')
        """))

    # User explicitly selects order_id 8 to KEEP
    keep_selections = {"group_1": 8}
    ok, msg, report = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], keep_selections=keep_selections
    )

    assert ok is True
    assert report["rows_removed"] == 1
    assert report["rows_kept"] == 1
    assert len(report["group_decisions"]) == 1
    assert report["group_decisions"][0]["kept_id"] == 8
    assert report["group_decisions"][0]["removed_ids"] == [14]

    with sqlite_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT order_id FROM {table}")).fetchall()
        assert rows == [(8,)]


def test_remove_duplicates_user_selects_second_record(sqlite_engine):
    """Verify user can explicitly select the second record (order_id 14) to KEEP."""
    table = "orders__cleaning_sel2"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (order_id, customer_name, email) VALUES
            (8, 'Pooja More', 'pooja@gmail.com'),
            (14, 'Pooja More', 'pooja@gmail.com')
        """))

    # User explicitly selects order_id 14 to KEEP
    keep_selections = {"group_1": 14}
    ok, msg, report = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], keep_selections=keep_selections
    )

    assert ok is True
    assert report["rows_removed"] == 1
    assert report["rows_kept"] == 1
    assert len(report["group_decisions"]) == 1
    assert report["group_decisions"][0]["kept_id"] == 14
    assert report["group_decisions"][0]["removed_ids"] == [8]

    with sqlite_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT order_id FROM {table}")).fetchall()
        assert rows == [(14,)]


def test_remove_duplicates_independent_group_selections(sqlite_engine):
    """
    Verify different duplicate groups have independent user decisions:
    Group 1 (Pooja): order_id 8 KEEP, order_id 14 REMOVE
    Group 2 (Priya): order_id 2 REMOVE, order_id 12 KEEP
    """
    table = "customers__cleaning_indep"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (order_id, customer_name, email) VALUES
            (8, 'Pooja More', 'pooja@gmail.com'),
            (14, 'Pooja More', 'pooja@gmail.com'),
            (2, 'Priya Patil', 'priya@gmail.com'),
            (12, 'Priya Patil', 'priya@gmail.com'),
            (99, 'Unique User', 'unique@gmail.com')
        """))

    # Pre-check detection preview does not modify the table
    ok_d, _, rep_d = detect_duplicates_workspace(
        sqlite_engine, "main", table, ["email"]
    )
    assert ok_d is True
    assert rep_d["duplicate_group_count"] == 2
    assert rep_d["rows_to_remove"] == 2
    with sqlite_engine.connect() as conn:
        assert conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar() == 5

    # Determine group_ids for Pooja and Priya
    groups = rep_d["groups"]
    pooja_group = next(
        g for g in groups if g["key_values"]["email"] == "pooja@gmail.com"
    )
    priya_group = next(
        g for g in groups if g["key_values"]["email"] == "priya@gmail.com"
    )

    # Independent decisions:
    # Pooja -> KEEP 8 (REMOVE 14)
    # Priya -> KEEP 12 (REMOVE 2)
    keep_selections = {
        pooja_group["group_id"]: 8,
        priya_group["group_id"]: 12,
    }

    ok_r, msg_r, rep_r = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], keep_selections=keep_selections
    )

    assert ok_r is True
    assert rep_r["rows_removed"] == 2
    assert rep_r["rows_kept"] == 2
    assert rep_r["remaining_rows"] == 3

    with sqlite_engine.connect() as conn:
        rows = conn.execute(
            text(f"SELECT order_id, email FROM {table} ORDER BY order_id")
        ).fetchall()
        assert rows == [
            (8, "pooja@gmail.com"),
            (12, "priya@gmail.com"),
            (99, "unique@gmail.com"),
        ]

    # Verify per-group decision summary in audit report
    decisions = rep_r["group_decisions"]
    assert len(decisions) == 2
    pooja_dec = next(
        d for d in decisions if d["key_values"]["email"] == "pooja@gmail.com"
    )
    assert pooja_dec["kept_id"] == 8
    assert pooja_dec["removed_ids"] == [14]

    priya_dec = next(
        d for d in decisions if d["key_values"]["email"] == "priya@gmail.com"
    )
    assert priya_dec["kept_id"] == 12
    assert priya_dec["removed_ids"] == [2]


def test_remove_duplicates_rejects_missing_group_selection(sqlite_engine):
    """Verify rejection when a duplicate group has no KEEP selection."""
    table = "users__cleaning_miss"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email) VALUES
            (1, 'a@test.com'), (2, 'a@test.com'),
            (3, 'b@test.com'), (4, 'b@test.com')
        """))

    # Only 1 group has a selection provided
    keep_selections = {"group_1": 1}
    ok, msg, _ = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], keep_selections=keep_selections
    )
    assert ok is False
    assert "Missing KEEP selection for duplicate group #2" in msg


def test_remove_duplicates_rejects_multiple_selections_in_group(sqlite_engine):
    """Verify rejection when multiple KEEP selections are given for a single-PK group."""
    table = "users__cleaning_multi"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email) VALUES
            (1, 'a@test.com'), (2, 'a@test.com')
        """))

    # User provided a list with both 1 and 2
    keep_selections = {"group_1": [1, 2]}
    ok, msg, _ = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], keep_selections=keep_selections
    )
    assert ok is False
    assert "Multiple KEEP selections provided" in msg


def test_remove_duplicates_rejects_nonexistent_record_id(sqlite_engine):
    """Verify rejection when the selected KEEP record ID does not exist in that group."""
    table = "users__cleaning_badid"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email) VALUES
            (1, 'a@test.com'), (2, 'a@test.com')
        """))

    keep_selections = {"group_1": 999}
    ok, msg, _ = remove_duplicates_workspace(
        sqlite_engine, "main", table, ["email"], keep_selections=keep_selections
    )
    assert ok is False
    assert "Selected KEEP record '999' was not found" in msg


def test_remove_duplicates_composite_pk_with_selections(sqlite_engine):
    """Verify composite primary key record-level selection works correctly."""
    table = "orders__cleaning_cpk_sel"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                tenant_id INT,
                order_id INT,
                customer_email TEXT,
                PRIMARY KEY (tenant_id, order_id)
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (tenant_id, order_id, customer_email) VALUES
            (10, 1, 'c1@test.com'),
            (10, 2, 'c1@test.com')
        """))

    # Select composite PK (10, 2) to KEEP
    keep_selections = {"group_1": (10, 2)}
    ok, msg, report = remove_duplicates_workspace(
        sqlite_engine,
        "main",
        table,
        ["customer_email"],
        keep_selections=keep_selections,
    )

    assert ok is True
    assert report["rows_removed"] == 1
    assert report["rows_kept"] == 1

    with sqlite_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT tenant_id, order_id FROM {table}")).fetchall()
        assert rows == [(10, 2)]


# ----------------------------------------------------------------------
# 4. Row-Level KEEP / REMOVE (remove_duplicates_by_row_ids) Tests
# ----------------------------------------------------------------------


def test_row_level_safety_rejects_non_workspace(sqlite_engine):
    """remove_duplicates_by_row_ids must reject tables without CLEANING_SUFFIX."""
    for bad_tbl in ["users", "users__cleaning", ""]:
        ok, msg, _ = remove_duplicates_by_row_ids(
            sqlite_engine, "main", bad_tbl, ["email"], {1: "REMOVE"}
        )
        assert ok is False
        assert "Refusing to clean" in msg


def test_row_level_invalid_action_rejected(sqlite_engine):
    """remove_duplicates_by_row_ids must reject actions other than KEEP / REMOVE."""
    table = "items__cleaning_inv_act"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, val TEXT)"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'A'), (2, 'A')"))

    ok, msg, _ = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["val"], {1: "SKIP", 2: "REMOVE"}
    )
    assert ok is False
    assert "Invalid action" in msg


def test_row_level_no_remove_is_noop(sqlite_engine):
    """When no rows are marked REMOVE, workspace is untouched and success is returned."""
    table = "items__cleaning_noop"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"CREATE TABLE {table} (id INTEGER PRIMARY KEY, val TEXT)"))
        conn.execute(text(f"INSERT INTO {table} VALUES (1, 'A'), (2, 'A')"))

    ok, msg, report = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["val"], {1: "KEEP", 2: "KEEP"}
    )
    assert ok is True
    assert report["rows_removed"] == 0
    assert "not modified" in msg.lower()

    with sqlite_engine.connect() as conn:
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
        assert cnt == 2


def test_row_level_single_remove(sqlite_engine):
    """Basic single-REMOVE: row_id 2 is deleted, row_id 1 stays."""
    table = "dup__cleaning_single_rem"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email) VALUES
            (1, 'a@test.com'), (2, 'a@test.com')
        """))

    ok, msg, report = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["email"], {1: "KEEP", 2: "REMOVE"}
    )
    assert ok is True
    assert report["rows_removed"] == 1
    assert report["rows_kept"] == 1
    assert report["remaining_rows"] == 1

    with sqlite_engine.connect() as conn:
        rows = conn.execute(text(f"SELECT id FROM {table}")).fetchall()
        assert rows == [(1,)]


def test_row_level_multiple_keeps_per_group(sqlite_engine):
    """
    3 duplicate rows: KEEP row 1, KEEP row 2, REMOVE row 3.
    Result: 2 rows kept, 1 removed.
    """
    table = "dup__cleaning_multi_keep"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email) VALUES
            (1, 'x@test.com'), (2, 'x@test.com'), (3, 'x@test.com')
        """))

    ok, msg, report = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["email"], {1: "KEEP", 2: "KEEP", 3: "REMOVE"}
    )
    assert ok is True
    assert report["rows_removed"] == 1
    assert report["rows_kept"] == 2
    assert report["remaining_rows"] == 2

    with sqlite_engine.connect() as conn:
        ids = [
            r[0]
            for r in conn.execute(
                text(f"SELECT id FROM {table} ORDER BY id")
            ).fetchall()
        ]
        assert ids == [1, 2]


def test_row_level_multiple_removes_per_group(sqlite_engine):
    """
    4 duplicate rows: KEEP row 1, REMOVE rows 2, 3, 4.
    Result: 1 row kept, 3 removed.
    """
    table = "dup__cleaning_multi_rem"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email) VALUES
            (1, 'y@test.com'), (2, 'y@test.com'),
            (3, 'y@test.com'), (4, 'y@test.com')
        """))

    ok, msg, report = remove_duplicates_by_row_ids(
        sqlite_engine,
        "main",
        table,
        ["email"],
        {1: "KEEP", 2: "REMOVE", 3: "REMOVE", 4: "REMOVE"},
    )
    assert ok is True
    assert report["rows_removed"] == 3
    assert report["rows_kept"] == 1
    assert report["remaining_rows"] == 1

    with sqlite_engine.connect() as conn:
        ids = [r[0] for r in conn.execute(text(f"SELECT id FROM {table}")).fetchall()]
        assert ids == [1]


def test_row_level_mixed_keep_remove_5_records(sqlite_engine):
    """
    5 duplicate records: KEEP rows 1, 3, 5 and REMOVE rows 2, 4.
    Result: 3 kept, 2 removed.
    """
    table = "dup__cleaning_mix5"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                name TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, name) VALUES
            (1, 'Alice'), (2, 'Alice'), (3, 'Alice'),
            (4, 'Alice'), (5, 'Alice')
        """))

    ok, msg, report = remove_duplicates_by_row_ids(
        sqlite_engine,
        "main",
        table,
        ["name"],
        {1: "KEEP", 2: "REMOVE", 3: "KEEP", 4: "REMOVE", 5: "KEEP"},
    )
    assert ok is True
    assert report["rows_removed"] == 2
    assert report["rows_kept"] == 3
    assert report["remaining_rows"] == 3

    with sqlite_engine.connect() as conn:
        ids = sorted(
            r[0] for r in conn.execute(text(f"SELECT id FROM {table}")).fetchall()
        )
        assert ids == [1, 3, 5]


def test_row_level_independent_two_groups(sqlite_engine):
    """
    Two separate duplicate groups, each with independent row-level decisions.
    Group A (bob@): row 10 KEEP, row 20 REMOVE
    Group B (ann@): row 30 REMOVE, row 40 KEEP, row 50 REMOVE
    Unique row 99 must be untouched.
    """
    table = "dup__cleaning_two_grps"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (id, email) VALUES
            (10, 'bob@test.com'), (20, 'bob@test.com'),
            (30, 'ann@test.com'), (40, 'ann@test.com'), (50, 'ann@test.com'),
            (99, 'unique@test.com')
        """))

    row_actions = {
        10: "KEEP",
        20: "REMOVE",  # Group bob@: 1 kept, 1 removed
        30: "REMOVE",
        40: "KEEP",
        50: "REMOVE",  # Group ann@: 1 kept, 2 removed
    }
    ok, msg, report = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["email"], row_actions
    )
    assert ok is True
    assert report["rows_removed"] == 3
    assert report["rows_kept"] == 2
    assert report["remaining_rows"] == 3  # id 10, 40, 99

    with sqlite_engine.connect() as conn:
        ids = sorted(
            r[0] for r in conn.execute(text(f"SELECT id FROM {table}")).fetchall()
        )
        assert ids == [10, 40, 99]


def test_row_level_source_table_never_modified(sqlite_engine):
    """Source (non-workspace) table must NEVER be modified — safety test."""
    source_tbl = "orders"
    # Source table with no CLEANING_SUFFIX
    with sqlite_engine.begin() as conn:
        conn.execute(
            text(f"CREATE TABLE {source_tbl} (id INTEGER PRIMARY KEY, email TEXT)")
        )
        conn.execute(
            text(f"INSERT INTO {source_tbl} VALUES (1, 'a@t.com'), (2, 'a@t.com')")
        )

    ok, msg, _ = remove_duplicates_by_row_ids(
        sqlite_engine, "main", source_tbl, ["email"], {1: "KEEP", 2: "REMOVE"}
    )
    assert ok is False, "Must reject non-workspace tables"
    assert "Refusing" in msg

    # Verify source table is intact
    with sqlite_engine.connect() as conn:
        cnt = conn.execute(text(f"SELECT COUNT(*) FROM {source_tbl}")).scalar()
        assert cnt == 2


# ----------------------------------------------------------------------
# 5. Section 7 Explicit Requirements Unit & Integration Tests
# ----------------------------------------------------------------------


def test_keep_automatically_marks_other_rows_in_group_remove(sqlite_engine):
    """
    Test: When KEEP is selected for a row (or auto-initialized), all OTHER rows
    in that same duplicate group are automatically marked REMOVE.
    """
    table = "users__cleaning_auto_rem"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (order_id, customer_name, email) VALUES
            (8, 'Pooja More', 'pooja@gmail.com'),
            (14, 'Pooja More', 'pooja@gmail.com'),
            (21, 'Pooja More', 'pooja@gmail.com')
        """))

    ok, msg, rep = detect_duplicates_workspace(sqlite_engine, "main", table, ["email"])
    assert ok is True
    groups = rep["groups"]
    assert len(groups) == 1
    g1 = groups[0]

    # 1. Automatic initialization sets first row to KEEP, others to REMOVE
    actions = init_duplicate_row_actions(groups)
    assert actions[8] == "KEEP"
    assert actions[14] == "REMOVE"
    assert actions[21] == "REMOVE"

    # 2. Selecting KEEP on another row with auto_remove_others=True automatically sets all other rows to REMOVE
    actions_after = set_group_row_action(
        actions,
        g1["rows"],
        target_row_id=14,
        new_action="KEEP",
        auto_remove_others=True,
    )
    assert actions_after[14] == "KEEP"
    assert actions_after[8] == "REMOVE"
    assert actions_after[21] == "REMOVE"


def test_user_can_manually_change_another_row_back_to_keep(sqlite_engine):
    """
    Test: User can manually change another row back to KEEP after automatic REMOVE,
    so that both rows are marked KEEP.
    """
    table = "users__cleaning_man_keep"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (order_id, customer_name, email) VALUES
            (8, 'Pooja More', 'pooja@gmail.com'),
            (14, 'Pooja More', 'pooja@gmail.com'),
            (20, 'Pooja More', 'pooja@gmail.com')
        """))

    ok, _, rep = detect_duplicates_workspace(sqlite_engine, "main", table, ["email"])
    assert ok is True
    groups = rep["groups"]
    g1 = groups[0]

    # Initial state: Row 8 is KEEP, Row 14 and Row 20 are REMOVE
    actions = init_duplicate_row_actions(groups)
    assert actions[8] == "KEEP"
    assert actions[14] == "REMOVE"
    assert actions[20] == "REMOVE"

    # User manually changes Row 14 back to KEEP (auto_remove_others=False)
    actions = set_group_row_action(
        actions,
        g1["rows"],
        target_row_id=14,
        new_action="KEEP",
        auto_remove_others=False,
    )
    # Both row 8 and row 14 are now KEEP!
    assert actions[8] == "KEEP"
    assert actions[14] == "KEEP"
    assert actions[20] == "REMOVE"


def test_multiple_keep_records_allowed(sqlite_engine):
    """
    Test: Multiple KEEP records in a group are accepted and preserved,
    deleting ONLY the rows explicitly marked REMOVE.
    """
    table = "users__cleaning_multi_allow"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (order_id, customer_name, email) VALUES
            (8, 'Pooja More', 'pooja@gmail.com'),
            (14, 'Pooja More', 'pooja@gmail.com'),
            (20, 'Pooja More', 'pooja@gmail.com')
        """))

    # Actions: Row 8 -> KEEP, Row 14 -> KEEP, Row 20 -> REMOVE
    row_actions = {8: "KEEP", 14: "KEEP", 20: "REMOVE"}
    ok, msg, rep = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["email"], row_actions
    )

    assert ok is True
    assert rep["rows_kept"] == 2
    assert rep["rows_removed"] == 1
    assert rep["remaining_rows"] == 2

    # Verify rows 8 and 14 are in DB, row 20 is removed
    with sqlite_engine.connect() as conn:
        remaining_ids = [
            r[0]
            for r in conn.execute(
                text(f"SELECT order_id FROM {table} ORDER BY order_id")
            ).fetchall()
        ]
        assert remaining_ids == [8, 14]


def test_groups_remain_independent(sqlite_engine):
    """
    Test: Actions in Group #1 do not affect Group #2.
    Group 1 (Pooja): 8 KEEP, 14 KEEP (both kept)
    Group 2 (Rahul): 30 KEEP, 31 REMOVE (1 kept, 1 removed)
    """
    table = "users__cleaning_grp_indep"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} (order_id, customer_name, email) VALUES
            (8, 'Pooja More', 'pooja@gmail.com'),
            (14, 'Pooja More', 'pooja@gmail.com'),
            (30, 'Rahul Sen', 'rahul@gmail.com'),
            (31, 'Rahul Sen', 'rahul@gmail.com')
        """))

    ok, _, rep = detect_duplicates_workspace(sqlite_engine, "main", table, ["email"])
    assert ok is True
    assert rep["duplicate_group_count"] == 2

    actions = init_duplicate_row_actions(rep["groups"])
    # Initially: 8 KEEP, 14 REMOVE, 30 KEEP, 31 REMOVE
    assert actions == {8: "KEEP", 14: "REMOVE", 30: "KEEP", 31: "REMOVE"}

    # User modifies Group 1: changes 14 to KEEP without affecting Group 2
    g1 = rep["groups"][0]
    actions = set_group_row_action(
        actions,
        g1["rows"],
        target_row_id=14,
        new_action="KEEP",
        auto_remove_others=False,
    )
    assert actions == {8: "KEEP", 14: "KEEP", 30: "KEEP", 31: "REMOVE"}

    # Execute deletion
    ok_del, _, rep_del = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["email"], actions
    )
    assert ok_del is True
    assert rep_del["rows_removed"] == 1
    assert rep_del["rows_kept"] == 3

    with sqlite_engine.connect() as conn:
        remaining = [
            r[0]
            for r in conn.execute(
                text(f"SELECT order_id FROM {table} ORDER BY order_id")
            ).fetchall()
        ]
        assert remaining == [8, 14, 30]


def test_eye_button_expands_complete_record(sqlite_engine):
    """
    Test: Verifies that duplicate row data includes all columns for comparison,
    and format_row_compact_summary generates the compact identifying row string.
    """
    table = "orders__cleaning_eye_exp"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                order_id INTEGER PRIMARY KEY,
                customer_name TEXT,
                email TEXT,
                phone TEXT,
                city TEXT,
                product_name TEXT,
                category TEXT,
                price REAL
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} VALUES
            (8, 'Pooja More', 'pooja@gmail.com', '9876543217', 'Dombivli', 'Smart Watch', 'Electronics', 4500.0),
            (14, 'Pooja More', 'pooja@gmail.com', '9876543218', 'Mumbai', 'Smart Watch Pro', 'Electronics', 5500.0)
        """))

    ok, _, rep = detect_duplicates_workspace(sqlite_engine, "main", table, ["email"])
    assert ok is True
    group = rep["groups"][0]
    row1 = group["rows"][0]

    # Compact summary contains primary key and identifying values
    compact = format_row_compact_summary(
        row1["row_data"], pk_cols=["order_id"], duplicate_keys=["email"]
    )
    assert "order_id: 8" in compact
    assert "pooja@gmail.com" in compact
    assert "Pooja More" in compact

    # Expanded complete record: all columns are present and unhidden
    row1_data = row1["row_data"]
    expected_cols = [
        "order_id",
        "customer_name",
        "email",
        "phone",
        "city",
        "product_name",
        "category",
        "price",
    ]
    for col in expected_cols:
        assert col in row1_data
        assert row1_data[col] is not None


def test_correct_rows_deleted_based_on_final_selections(sqlite_engine):
    """
    Test: 5 duplicate records with mixed selections:
    Record 1 -> KEEP
    Record 2 -> REMOVE
    Record 3 -> KEEP
    Record 4 -> REMOVE
    Record 5 -> KEEP
    Result: 3 rows kept, 2 rows removed.
    """
    table = "items__cleaning_mix_final"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                item_code TEXT,
                version INT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} VALUES
            (1, 'ITEM_A', 1),
            (2, 'ITEM_A', 2),
            (3, 'ITEM_A', 3),
            (4, 'ITEM_A', 4),
            (5, 'ITEM_A', 5)
        """))

    row_actions = {
        1: "KEEP",
        2: "REMOVE",
        3: "KEEP",
        4: "REMOVE",
        5: "KEEP",
    }
    ok, msg, rep = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["item_code"], row_actions
    )
    assert ok is True
    assert rep["rows_removed"] == 2
    assert rep["rows_kept"] == 3
    assert rep["remaining_rows"] == 3

    with sqlite_engine.connect() as conn:
        remaining_ids = [
            r[0]
            for r in conn.execute(
                text(f"SELECT id FROM {table} ORDER BY id")
            ).fetchall()
        ]
        assert remaining_ids == [1, 3, 5]


def test_change_remove_to_keep_switches_previous_keep_to_remove():
    """
    Test: When any row is changed from REMOVE -> KEEP, the previous KEEP row
    in the same duplicate group immediately switches to REMOVE, while other
    duplicate groups remain completely unaffected.
    """
    # Group 1: rows 101, 102, 103
    g1_rows = [{"row_id": 101}, {"row_id": 102}, {"row_id": 103}]
    # Group 2: rows 201, 202
    g2_rows = [{"row_id": 201}, {"row_id": 202}]

    # Initial actions: 101=KEEP, 102=REMOVE, 103=REMOVE, 201=KEEP, 202=REMOVE
    actions = {
        101: "KEEP",
        102: "REMOVE",
        103: "REMOVE",
        201: "KEEP",
        202: "REMOVE",
    }

    # User changes row 102 from REMOVE -> KEEP
    actions = set_group_row_action(
        actions, g1_rows, target_row_id=102, new_action="KEEP", auto_remove_others=True
    )

    # In Group 1: 102 is now KEEP, previous KEEP 101 is now REMOVE, 103 is REMOVE
    assert actions[102] == "KEEP"
    assert actions[101] == "REMOVE"
    assert actions[103] == "REMOVE"

    # Group 2 is completely unchanged and independent
    assert actions[201] == "KEEP"
    assert actions[202] == "REMOVE"

    # Now user changes row 103 from REMOVE -> KEEP
    actions = set_group_row_action(
        actions, g1_rows, target_row_id=103, new_action="KEEP", auto_remove_others=True
    )
    assert actions[103] == "KEEP"
    assert actions[102] == "REMOVE"
    assert actions[101] == "REMOVE"
    assert actions[201] == "KEEP"
    assert actions[202] == "REMOVE"


def test_checkbox_selection_checked_is_remove_unchecked_is_keep():
    """
    Test: CHECKED = REMOVE, UNCHECKED = KEEP
    - Checking a row sets action to REMOVE.
    - Unchecking a row sets action to KEEP.
    - Other rows are NOT affected.
    """
    actions = {1: "KEEP", 2: "REMOVE", 3: "REMOVE"}

    # Uncheck row 2 -> KEEP
    updated = toggle_row_remove_action(actions, target_row_id=2, is_remove=False)
    assert updated[2] == "KEEP"
    assert updated[1] == "KEEP"
    assert updated[3] == "REMOVE"

    # Check row 1 -> REMOVE
    updated2 = toggle_row_remove_action(updated, target_row_id=1, is_remove=True)
    assert updated2[1] == "REMOVE"
    assert updated2[2] == "KEEP"
    assert updated2[3] == "REMOVE"


def test_select_all_checkbox_behavior():
    """
    Test Select All checkbox:
    - If Select All is checked -> ALL rows in that duplicate group are marked REMOVE.
    - If Select All is unchecked -> ALL rows in that duplicate group are marked KEEP.
    - Does NOT modify other groups.
    """
    actions = {101: "KEEP", 102: "REMOVE", 103: "REMOVE", 201: "KEEP", 202: "REMOVE"}
    g1_rids = [101, 102, 103]

    # Select All checked -> all in group 1 marked REMOVE
    sel_all_checked = apply_select_all_action(actions, g1_rids, select_all=True)
    assert sel_all_checked[101] == "REMOVE"
    assert sel_all_checked[102] == "REMOVE"
    assert sel_all_checked[103] == "REMOVE"
    # Group 2 untouched
    assert sel_all_checked[201] == "KEEP"
    assert sel_all_checked[202] == "REMOVE"

    # Select All unchecked -> all in group 1 marked KEEP
    sel_all_unchecked = apply_select_all_action(actions, g1_rids, select_all=False)
    assert sel_all_unchecked[101] == "KEEP"
    assert sel_all_unchecked[102] == "KEEP"
    assert sel_all_unchecked[103] == "KEEP"
    # Group 2 untouched
    assert sel_all_unchecked[201] == "KEEP"
    assert sel_all_unchecked[202] == "REMOVE"


def test_select_all_synchronization_with_individual_checkboxes():
    """
    Test sync between individual checkboxes and Select All:
    - If any row is KEEP, Select All is False.
    - If all rows are REMOVE, Select All is True.
    """
    g_rids = [1, 2, 3]

    # All REMOVE -> is_group_all_removed is True
    actions_all_rem = {1: "REMOVE", 2: "REMOVE", 3: "REMOVE"}
    assert is_group_all_removed(actions_all_rem, g_rids) is True

    # One row is KEEP -> is_group_all_removed is False
    actions_mixed = {1: "KEEP", 2: "REMOVE", 3: "REMOVE"}
    assert is_group_all_removed(actions_mixed, g_rids) is False

    # All KEEP -> is_group_all_removed is False
    actions_all_keep = {1: "KEEP", 2: "KEEP", 3: "KEEP"}
    assert is_group_all_removed(actions_all_keep, g_rids) is False


def test_no_restriction_on_keep_remove_combinations():
    """
    Test: There must be NO restriction on how many records can be kept or removed.
    Example with 5 duplicate records:
    Row 1: CHECKED (REMOVE)
    Row 2: UNCHECKED (KEEP)
    Row 3: CHECKED (REMOVE)
    Row 4: UNCHECKED (KEEP)
    Row 5: UNCHECKED (KEEP)
    Total: 2 REMOVE, 3 KEEP.
    """
    g_rids = [1, 2, 3, 4, 5]
    actions = {1: "KEEP", 2: "REMOVE", 3: "REMOVE", 4: "REMOVE", 5: "REMOVE"}

    # Set exact combination:
    actions = toggle_row_remove_action(actions, 1, is_remove=True)  # REMOVE
    actions = toggle_row_remove_action(actions, 2, is_remove=False)  # KEEP
    actions = toggle_row_remove_action(actions, 3, is_remove=True)  # REMOVE
    actions = toggle_row_remove_action(actions, 4, is_remove=False)  # KEEP
    actions = toggle_row_remove_action(actions, 5, is_remove=False)  # KEEP

    assert actions[1] == "REMOVE"
    assert actions[2] == "KEEP"
    assert actions[3] == "REMOVE"
    assert actions[4] == "KEEP"
    assert actions[5] == "KEEP"

    keep_count = sum(1 for rid in g_rids if actions[rid] == "KEEP")
    remove_count = sum(1 for rid in g_rids if actions[rid] == "REMOVE")
    assert keep_count == 3
    assert remove_count == 2
    assert is_group_all_removed(actions, g_rids) is False


def test_independent_duplicate_groups_checkbox_workflow(sqlite_engine):
    """
    Test multiple duplicate groups with checkbox selection:
    - Group 1 has 3 records: user removes rows 2 and 3, keeps row 1.
    - Group 2 has 2 records: user uses Select All to remove both, then unchecks row 2 to keep row 2.
    - Database deletion removes only checked rows.
    """
    table = "users__cleaning_chk_groups"
    with sqlite_engine.begin() as conn:
        conn.execute(text(f"""
            CREATE TABLE {table} (
                id INTEGER PRIMARY KEY,
                email TEXT,
                name TEXT
            )
        """))
        conn.execute(text(f"""
            INSERT INTO {table} VALUES
            (1, 'group1@test.com', 'Alice 1'),
            (2, 'group1@test.com', 'Alice 2'),
            (3, 'group1@test.com', 'Alice 3'),
            (4, 'group2@test.com', 'Bob 1'),
            (5, 'group2@test.com', 'Bob 2')
        """))

    g1_rids = [1, 2, 3]
    g2_rids = [4, 5]

    # Initial seeding: row 0 KEEP, others REMOVE
    actions = {1: "KEEP", 2: "REMOVE", 3: "REMOVE", 4: "KEEP", 5: "REMOVE"}

    # User uses Select All on Group 2
    actions = apply_select_all_action(actions, g2_rids, select_all=True)
    assert actions[4] == "REMOVE"
    assert actions[5] == "REMOVE"
    assert is_group_all_removed(actions, g2_rids) is True
    # Group 1 unaffected
    assert actions[1] == "KEEP"
    assert actions[2] == "REMOVE"
    assert actions[3] == "REMOVE"

    # User unchecks row 5 in Group 2 (wants to KEEP row 5 instead)
    actions = toggle_row_remove_action(actions, 5, is_remove=False)
    assert actions[5] == "KEEP"
    assert actions[4] == "REMOVE"
    assert is_group_all_removed(actions, g2_rids) is False

    # Execute deletion
    ok, msg, rep = remove_duplicates_by_row_ids(
        sqlite_engine, "main", table, ["email"], row_actions=actions
    )
    assert ok is True
    assert rep["rows_removed"] == 3  # rows 2, 3, and 4
    assert rep["rows_kept"] == 2  # rows 1 and 5
    assert rep["remaining_rows"] == 2

    with sqlite_engine.connect() as conn:
        surviving = [
            r[0]
            for r in conn.execute(
                text(f"SELECT id FROM {table} ORDER BY id")
            ).fetchall()
        ]
        assert surviving == [1, 5]
