"""
Unit and Integration Tests for AI-Powered Data Profiling Engine
tests/test_ai_profiling.py

Tests generic pattern detection, anonymization, quality scoring,
compact summary generation, and read-only safety guarantees.
"""

import pytest
import pandas as pd
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine

from src.ai_profiling import (
    anonymize_sample_value,
    analyze_column_generic_patterns,
    build_table_ai_profile,
    format_compact_ai_summary,
    format_column_drilldown_prompt,
    CURRENCY_SYMBOLS,
)


class TestValueAnonymization:
    """Verifies that suspicious values are sanitized before reaching LLM or reports."""

    def test_anonymize_email(self):
        raw = "alice.smith@corporate-domain.com"
        anon = anonymize_sample_value(raw)
        assert "@" in anon
        assert "corporate-domain" in anon
        assert "alice" not in anon
        assert "smith" not in anon

    def test_anonymize_credit_card(self):
        raw = "4111 2222 3333 4444"
        anon = anonymize_sample_value(raw)
        assert "4111" not in anon
        assert "****-****-****-****" in anon

    def test_anonymize_ssn(self):
        raw = "123-45-6789"
        anon = anonymize_sample_value(raw)
        assert "123" not in anon
        assert "***-**-****" in anon

    def test_anonymize_phone(self):
        raw = "(555) 234-5678"
        anon = anonymize_sample_value(raw)
        assert "234" not in anon
        assert "***-***-****" in anon

    def test_anonymize_truncation_and_newlines(self):
        long_val = "This is an extremely long string that exceeds the forty character sample limit by quite a lot\nand has newlines"
        anon = anonymize_sample_value(long_val, max_len=30)
        assert len(anon) <= 30
        assert "\n" not in anon
        assert anon.endswith("...")

    def test_anonymize_empty_and_null(self):
        assert anonymize_sample_value(None) == "NULL"
        assert anonymize_sample_value("") == '""'
        assert anonymize_sample_value("   ") == '""'


class TestColumnGenericPatterns:
    """Tests domain-agnostic pattern discovery across messy column data."""

    def test_detects_currency_and_recommends_numeric_cleaning(self):
        series = pd.Series(["$100.50", "€200", "₹5,000", "$45.00", "12.30", None], name="revenue")
        res = analyze_column_generic_patterns(series, "varchar", total_table_rows=6)

        assert res["null_count"] == 1
        assert res["null_pct"] == 16.67
        assert res["numeric_patterns"]["currency_count"] >= 4
        assert "$" in res["numeric_patterns"]["currencies_found"]
        assert "€" in res["numeric_patterns"]["currencies_found"]
        assert "₹" in res["numeric_patterns"]["currencies_found"]
        assert res["logical_type"] == "NUMERIC (TEXT)"
        assert res["recommended_tool"] == "Numeric Data Cleaning"

    def test_detects_mixed_alphanumeric_codes(self):
        series = pd.Series(["100kg", "50kg", "ORD-101", "25kg", "invalid"], name="spec")
        res = analyze_column_generic_patterns(series, "varchar", total_table_rows=5)

        assert res["numeric_patterns"]["mixed_alphanumeric_count"] >= 4
        assert len(res["suspicious_samples"]) > 0

    def test_detects_mixed_date_formats_and_recommends_advanced_dates(self):
        series = pd.Series([
            "2023-05-14",
            "14/05/2023",
            "2023-11-20",
            "01/12/2023",
            "15/08/2023",
        ], name="order_date")
        res = analyze_column_generic_patterns(series, "varchar", total_table_rows=5)

        assert res["logical_type"] == "DATE / DATETIME"
        assert res["date_patterns"]["is_mixed_date_formats"] is True
        assert res["recommended_tool"] == "Advanced Date Standardization"
        assert res["recommended_tool_id"] == "adv_dates"

    def test_detects_boolean_representations_and_recommends_normalization(self):
        series = pd.Series(["Y", "N", "YES", "NO", "y", "n", "True"], name="is_active")
        res = analyze_column_generic_patterns(series, "varchar", total_table_rows=7)

        assert res["logical_type"] == "BOOLEAN"
        assert res["boolean_patterns"]["is_boolean_like"] is True
        assert res["recommended_tool"] == "Boolean Normalization"

    def test_detects_whitespace_and_casing_breakdown(self):
        series = pd.Series(["  NEW YORK  ", "london", "Paris", "TOKYO\t"], name="city")
        res = analyze_column_generic_patterns(series, "varchar", total_table_rows=4)

        assert res["whitespace_issues"] >= 2
        cb = res["casing_breakdown"]
        assert cb["upper"] >= 1  # NEW YORK
        assert cb["lower"] >= 1  # london
        assert cb["title"] >= 1  # Paris

    def test_detects_special_and_control_characters(self):
        series = pd.Series(["Item\x00One", "Item\x1fTwo", "NormalItem"], name="item_name")
        res = analyze_column_generic_patterns(series, "varchar", total_table_rows=3)

        assert res["special_char_issues"]["control_char_count"] == 2
        assert res["recommended_tool"] in ["Special Character Cleaning", "Whitespace Cleaning"]

    def test_numeric_native_column(self):
        series = pd.Series([10.5, 20.0, None, 45.2], name="amount")
        res = analyze_column_generic_patterns(series, "decimal", total_table_rows=4)

        assert res["logical_type"] == "NUMERIC"
        assert res["null_count"] == 1
        assert res["min_val"] == 10.5
        assert res["max_val"] == 45.2


class TestTableProfilingAndSummary:
    """Verifies table profile assembly and compact summary formatting."""

    def test_compact_summary_formatting(self):
        sample_profile = {
            "database": "sales_db",
            "table_name": "customer_records",
            "table_type_label": "Source Table (Strict Read-Only)",
            "row_count": 1250,
            "column_count": 3,
            "quality_score": 78,
            "duplicate_groups": 14,
            "severity_summary": {"high": 1, "medium": 2, "low": 1},
            "columns": [
                {
                    "name": "cust_id",
                    "physical_type": "int",
                    "logical_type": "NUMERIC",
                    "null_count": 0,
                    "null_pct": 0.0,
                    "empty_count": 0,
                    "unique_count": 1236,
                    "whitespace_issues": 0,
                    "recommended_tool": None,
                    "suspicious_samples": [],
                },
                {
                    "name": "signup_date",
                    "physical_type": "varchar",
                    "logical_type": "DATE / DATETIME",
                    "null_count": 50,
                    "null_pct": 4.0,
                    "empty_count": 10,
                    "unique_count": 400,
                    "whitespace_issues": 12,
                    "date_patterns": {"total_date_like": 1190, "is_mixed_date_formats": True, "iso_date_count": 800, "slash_date_count": 390},
                    "recommended_tool": "Advanced Date Standardization",
                    "suspicious_samples": [{"value": "14/05/2023", "count": 25}],
                },
            ],
        }

        summary = format_compact_ai_summary(sample_profile)

        # Asserts on factual evidence representation
        assert "Table `sales_db.customer_records`" in summary
        assert "Health Score: 78/100" in summary
        assert "Duplicate Rows Detected: 14" in summary
        assert "signup_date" in summary
        assert "Mixed date formats detected" in summary
        assert "Advanced Date Standardization" in summary
        assert "14/05/2023" in summary

    def test_column_drilldown_prompt_generation(self):
        col = {"name": "join_date", "logical_type": "DATE"}
        prompt = format_column_drilldown_prompt(col, "employees")
        assert "join_date" in prompt
        assert "employees" in prompt
        assert "DataClean Studio tool" in prompt

    def test_build_table_ai_profile_with_mock_engine(self):
        # Create an in-memory SQLite database to simulate engine operations safely
        engine = create_engine("sqlite:///:memory:")
        df_test = pd.DataFrame({
            "id": [1, 2, 3, 3],
            "price": ["$10.00", "$20.00", "€30.00", "€30.00"],
            "date": ["2023-01-01", "02/02/2023", "2023-03-01", "2023-03-01"],
        })
        df_test.to_sql("orders", engine, index=False)

        with patch("src.ai_profiling._quote_table", return_value="orders"), \
             patch("src.ai_profiling._get_columns", return_value=[
                 {"COLUMN_NAME": "id", "DATA_TYPE": "integer"},
                 {"COLUMN_NAME": "price", "DATA_TYPE": "varchar"},
                 {"COLUMN_NAME": "date", "DATA_TYPE": "varchar"},
             ]):
            success, msg, profile = build_table_ai_profile(
                engine=engine,
                database="test_db",
                table_name="orders",
                is_workspace=False,
            )

            assert success is True
            assert profile is not None
            assert profile["row_count"] == 4
            assert profile["column_count"] == 3
            assert profile["duplicate_groups"] == 1  # row 3 is duplicate of row 1/price+date
            assert len(profile["columns"]) == 3
            assert "compact_summary" in profile
            assert profile["table_type_label"] == "Source Table (Strict Read-Only)"

    def test_build_table_ai_profile_missing_engine_or_table(self):
        ok, msg, prof = build_table_ai_profile(None, "db", "tbl")
        assert ok is False
        assert "No active database connection" in msg

        ok, msg, prof = build_table_ai_profile(MagicMock(), "", "")
        assert ok is False
        assert "must be specified" in msg
