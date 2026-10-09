import pytest
import pandas as pd
from unittest.mock import MagicMock, patch

from src.staging import (
    evaluate_boolean_series,
    detect_boolean_like_columns,
    analyze_boolean_column,
    preview_boolean_normalization,
    transform_boolean_column,
    undo_boolean_normalization,
)
from src.profiling import profile_table


def test_case_1_varchar_yes_no():
    res = evaluate_boolean_series(
        column_name="IsActive",
        declared_dtype="VARCHAR(20)",
        value_counts={"Yes": 25, "No": 20, "YES": 15, "NO": 15, "Y": 10, "N": 15},
        null_count=0,
    )
    assert res["is_boolean_like"] is True
    assert res["detected_type"] == "Boolean-like"
    assert res["confidence_level"] == "HIGH"
    assert res["true_count"] == 50
    assert res["false_count"] == 50
    assert res["needs_normalization"] is True


def test_case_2_varchar_true_false():
    res = evaluate_boolean_series(
        column_name="is_verified",
        declared_dtype="VARCHAR(20)",
        value_counts={"true": 10, "false": 10, "TRUE": 10, "FALSE": 10, "T": 5, "F": 5},
        null_count=0,
    )
    assert res["is_boolean_like"] is True
    assert res["detected_type"] == "Boolean-like"
    assert res["confidence_level"] == "HIGH"
    assert res["true_count"] == 25
    assert res["false_count"] == 25


def test_case_3_mixed_representations_and_whitespace():
    res = evaluate_boolean_series(
        column_name="Status",
        declared_dtype="VARCHAR(50)",
        value_counts={
            "YES": 10,
            " YES ": 5,
            "No": 10,
            "true": 10,
            "false": 10,
            "1": 8,
            "0": 7,
            "Y": 5,
            " y ": 3,
            "N": 5,
        },
        null_count=0,
    )
    assert res["is_boolean_like"] is True
    assert res["detected_type"] == "Boolean-like"
    assert res["confidence_level"] == "HIGH"
    assert res["true_count"] == 41
    assert res["false_count"] == 32
    assert res["unknown_count"] == 0


def test_case_4_boolean_with_null_values():
    res = evaluate_boolean_series(
        column_name="has_discount",
        declared_dtype="VARCHAR(10)",
        value_counts={"YES": 30, "NO": 30, "Y": 10, "N": 10},
        null_count=20,
    )
    assert res["is_boolean_like"] is True
    assert res["detected_type"] == "Boolean-like"
    assert res["null_count"] == 20
    assert res["non_null_count"] == 80
    assert res["total_rows"] == 100


def test_case_5_boolean_with_invalid_values():
    res_small = evaluate_boolean_series(
        column_name="Status",
        declared_dtype="VARCHAR(20)",
        value_counts={"YES": 45, "NO": 45, "Y": 4, "N": 4, "Maybe": 1, "Unknown": 1},
        null_count=0,
    )
    assert res_small["is_boolean_like"] is True
    assert res_small["detected_type"] == "Boolean-like"
    assert res_small["unknown_count"] == 2
    assert set(res_small["unrecognized_values"]) == {"Maybe", "Unknown"}

    res_large = evaluate_boolean_series(
        column_name="IsActive",
        declared_dtype="VARCHAR(20)",
        value_counts={"YES": 5000, "NO": 4780, "Maybe": 12, "Unknown": 8},
        null_count=200,
    )
    assert res_large["is_boolean_like"] is True
    assert res_large["total_rows"] == 10000
    assert res_large["non_null_count"] == 9800
    assert res_large["recognized_count"] == 9780
    assert res_large["unknown_count"] == 20
    assert res_large["null_count"] == 200


def test_case_6_normal_text_column_not_detected():
    res1 = evaluate_boolean_series(
        column_name="order_status",
        declared_dtype="VARCHAR(30)",
        value_counts={"Pending": 25, "Approved": 25, "Rejected": 25, "Cancelled": 25},
        null_count=0,
    )
    assert res1["is_boolean_like"] is False
    assert res1["confidence_level"] == "NOT_BOOLEAN"

    res2 = evaluate_boolean_series(
        column_name="city_or_flag",
        declared_dtype="VARCHAR(30)",
        value_counts={"YES": 10, "NO": 10, "Mumbai": 20, "Delhi": 20, "London": 20, "New York": 20},
        null_count=0,
    )
    assert res2["is_boolean_like"] is False
    assert res2["confidence_level"] == "NOT_BOOLEAN"


def test_case_7_numeric_column_not_detected():
    res_multi = evaluate_boolean_series(
        column_name="CustomerID",
        declared_dtype="INTEGER",
        value_counts={0: 10, 1: 10, 2: 10, 3: 10, 4: 10, 5: 10},
        null_count=0,
    )
    assert res_multi["is_boolean_like"] is False
    assert res_multi["detected_type"] == "Numeric"

    res_neg_name = evaluate_boolean_series(
        column_name="quantity",
        declared_dtype="INT",
        value_counts={0: 50, 1: 50},
        null_count=0,
    )
    assert res_neg_name["is_boolean_like"] is False
    assert res_neg_name["confidence_level"] == "LOW"

    res_neutral = evaluate_boolean_series(
        column_name="StatusCode",
        declared_dtype="VARCHAR(10)",
        value_counts={"0": 50, "1": 50},
        null_count=0,
    )
    assert res_neutral["is_boolean_like"] is True
    assert res_neutral["confidence_level"] == "MEDIUM"

    res_pos = evaluate_boolean_series(
        column_name="is_active",
        declared_dtype="INT",
        value_counts={0: 50, 1: 50},
        null_count=0,
    )
    assert res_pos["is_boolean_like"] is True
    assert res_pos["confidence_level"] == "HIGH"


def _build_mock_engine_for_transform(
    column_name="IsActive",
    col_type="VARCHAR(20)",
    value_counts=None,
    null_count=1,
):
    if value_counts is None:
        value_counts = {"YES": 10, "Y": 5, "NO": 8, "N": 4}

    mock_engine = MagicMock()
    mock_inspector = MagicMock()
    mock_inspector.get_table_names.return_value = ["orders__cleaning_ws"]
    mock_inspector.get_columns.return_value = [
        {"name": "id", "type": "INT"},
        {"name": column_name, "type": col_type},
    ]

    executed_sqls = []

    def execute_side_effect(stmt, *args, **kwargs):
        sql = str(stmt)
        executed_sqls.append(sql)
        res = MagicMock()
        if "COUNT(*)" in sql and "IS NULL" in sql:
            res.scalar.return_value = null_count
        elif "GROUP BY" in sql:
            rows = []
            for k, v in value_counts.items():
                r = MagicMock()
                r._mapping = {"val": k, "cnt": v}
                rows.append(r)
            res.fetchall.return_value = rows
        else:
            res.rowcount = sum(value_counts.values())
        return res

    mock_conn = MagicMock()
    mock_conn.execute.side_effect = execute_side_effect
    mock_engine.connect.return_value.__enter__.return_value = mock_conn
    mock_engine.begin.return_value.__enter__.return_value = mock_conn

    return mock_engine, mock_inspector, executed_sqls


def test_case_8_convert_to_true_false():
    engine, inspector, executed_sqls = _build_mock_engine_for_transform(
        column_name="IsActive",
        value_counts={"YES": 10, "Y": 5, "NO": 8, "N": 4},
        null_count=2,
    )
    with patch("src.staging.inspect", return_value=inspector):
        ok, msg, report = transform_boolean_column(
            engine,
            "test_db",
            "orders__cleaning_ws",
            "IsActive",
            target_format="TRUE_FALSE",
            in_place=True,
        )

    assert ok is True
    assert report["true_target"] == "TRUE"
    assert report["false_target"] == "FALSE"
    assert report["rows_converted"] == 27
    assert report["null_count"] == 2
    assert report["in_place"] is True
    assert any("THEN 'TRUE'" in s and "THEN 'FALSE'" in s for s in executed_sqls)
    assert any("__bool_backup_IsActive" in s for s in executed_sqls)


def test_case_9_convert_to_yes_no():
    engine, inspector, executed_sqls = _build_mock_engine_for_transform(
        column_name="Flag",
        value_counts={"true": 6, "false": 6, "1": 4, "0": 4},
        null_count=0,
    )
    with patch("src.staging.inspect", return_value=inspector):
        ok, msg, report = transform_boolean_column(
            engine,
            "test_db",
            "orders__cleaning_ws",
            "Flag",
            target_format="YES_NO",
            in_place=True,
        )

    assert ok is True
    assert report["true_target"] == "YES"
    assert report["false_target"] == "NO"
    assert report["rows_converted"] == 20
    assert any("THEN 'YES'" in s and "THEN 'NO'" in s for s in executed_sqls)


def test_case_10_convert_to_1_0():
    engine, inspector, executed_sqls = _build_mock_engine_for_transform(
        column_name="IsVerified",
        value_counts={"YES": 10, "NO": 10, "true": 5, "false": 5},
        null_count=0,
    )
    with patch("src.staging.inspect", return_value=inspector):
        ok, msg, report = transform_boolean_column(
            engine,
            "test_db",
            "orders__cleaning_ws",
            "IsVerified",
            target_format="1_0",
            in_place=True,
        )

    assert ok is True
    assert report["true_target"] == "1"
    assert report["false_target"] == "0"
    assert report["rows_converted"] == 30
    assert any("THEN '1'" in s and "THEN '0'" in s for s in executed_sqls)


def test_unrecognized_values_never_silently_converted_to_false():
    engine, inspector, executed_sqls = _build_mock_engine_for_transform(
        column_name="Status",
        value_counts={"YES": 20, "NO": 20, "Maybe": 2, "Unknown": 1},
        null_count=0,
    )
    with patch("src.staging.inspect", return_value=inspector):
        ok, msg, report = transform_boolean_column(
            engine,
            "test_db",
            "orders__cleaning_ws",
            "Status",
            target_format="TRUE_FALSE",
            unrecognized_action="keep_original",
        )

    assert ok is True
    assert report["rows_converted"] == 40
    assert report["exceptions"] == 3
    update_sqls = [s for s in executed_sqls if "CASE" in s]
    assert len(update_sqls) == 1
    assert "ELSE CAST(`Status` AS CHAR)" in update_sqls[0]


def test_custom_mapping_and_undo():
    engine, inspector, executed_sqls = _build_mock_engine_for_transform(
        column_name="AccountState",
        value_counts={"YES": 15, "NO": 10},
        null_count=0,
    )
    with patch("src.staging.inspect", return_value=inspector):
        ok, msg, report = transform_boolean_column(
            engine,
            "test_db",
            "orders__cleaning_ws",
            "AccountState",
            target_format="custom",
            true_value="Active",
            false_value="Inactive",
            in_place=True,
        )
        assert ok is True
        assert report["true_target"] == "Active"
        assert report["false_target"] == "Inactive"

        inspector.get_columns.return_value = [
            {"name": "id", "type": "INT"},
            {"name": "AccountState", "type": "VARCHAR(20)"},
            {"name": "__bool_backup_AccountState", "type": "TEXT"},
        ]
        u_ok, u_msg = undo_boolean_normalization(
            engine, "test_db", "orders__cleaning_ws", "AccountState"
        )
        assert u_ok is True
        assert "Reverted column 'AccountState'" in u_msg


def test_profiler_physical_vs_logical_type_integration():
    df_sample = pd.DataFrame({
        "IsActive": ["YES", "No", "Y", "N", "true", "false", None],
        "City": ["Mumbai", "Delhi", "London", "New York", "Tokyo", "Paris", "Berlin"],
    })
    mock_engine = MagicMock()
    cols_meta = [
        {"COLUMN_NAME": "IsActive", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES"},
        {"COLUMN_NAME": "City", "DATA_TYPE": "varchar", "IS_NULLABLE": "YES"},
    ]
    with patch("src.profiling._get_columns", return_value=cols_meta), \
         patch("src.profiling.pd.read_sql_query", return_value=df_sample):
        ok, msg, prof = profile_table(mock_engine, "test_db", "users")

    assert ok is True
    cp_df = prof["column_profiles"]
    is_active_row = cp_df[cp_df["Column"] == "IsActive"].iloc[0]
    city_row = cp_df[cp_df["Column"] == "City"].iloc[0]

    assert is_active_row["Data Type"] == "varchar"
    assert is_active_row["Logical Type"] == "Boolean-like"
    assert "HIGH" in is_active_row["Boolean Confidence"]

    assert city_row["Data Type"] == "varchar"
    assert city_row["Logical Type"] == "VARCHAR"

    bool_findings = [f for f in prof["findings"] if f["Type"] == "Boolean Inconsistency"]
    assert len(bool_findings) == 1
    assert bool_findings[0]["Column"] == "IsActive"
