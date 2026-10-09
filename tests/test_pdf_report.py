"""
Unit tests for src/pdf_report.py module.
Validates professional PDF report generation, styling, and robustness.
"""

import pandas as pd
import pytest
from src.pdf_report import generate_executive_profile_pdf, sanitize_pdf_text, hex_to_rgb


def test_sanitize_pdf_text():
    """Verify Unicode characters are cleanly mapped to ASCII/Latin-1 safe equivalents."""
    raw = "⚡ Table ➔ Orders (✓ verified) — “Quotes” & ⚠️ warnings…"
    sanitized = sanitize_pdf_text(raw)
    assert "➔" not in sanitized
    assert "->" in sanitized
    assert "✓" not in sanitized
    assert "[v]" in sanitized
    assert "⚡" not in sanitized
    assert "“" not in sanitized
    # Must be encodable to latin-1 without throwing
    sanitized.encode("latin-1")


def test_hex_to_rgb():
    """Verify hex to RGB conversion."""
    assert hex_to_rgb("#10B981") == (16, 185, 129)
    assert hex_to_rgb("#EF4444") == (239, 68, 68)
    assert hex_to_rgb("") == (16, 185, 129)
    assert hex_to_rgb("invalid") == (16, 185, 129)


def test_generate_executive_profile_pdf_source():
    """Verify PDF generation for source table baseline."""
    col_profiles = pd.DataFrame(
        [
            {
                "Column": "id",
                "Data Type": "INT",
                "Null Count": 0,
                "Null %": 0.0,
                "Unique Values": 100,
            },
            {
                "Column": "email",
                "Data Type": "VARCHAR",
                "Null Count": 12,
                "Null %": 12.0,
                "Unique Values": 88,
            },
        ]
    )
    findings = [
        {
            "Column": "email",
            "Issue": "Null values found",
            "Count": 12,
            "Severity": "Medium",
        },
    ]
    profile_data = {
        "row_count": 100,
        "column_count": 2,
        "duplicate_row_count": 0,
        "findings": findings,
        "column_profiles": col_profiles,
    }

    pdf_bytes = generate_executive_profile_pdf(
        db_name="ecommerce_db",
        target_tbl_name="customers",
        is_workspace=False,
        score=92,
        score_label="Excellent Health",
        score_color_hex="#10B981",
        profile_data=profile_data,
        delta_callout="",
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_generate_executive_profile_pdf_workspace_with_delta():
    """Verify PDF generation for workspace table with baseline comparison."""
    col_profiles = pd.DataFrame(
        [
            {
                "Column": "id",
                "Data Type": "INT",
                "Null Count": 0,
                "Null %": 0.0,
                "Unique Values": 90,
            },
            {
                "Column": "name",
                "Data Type": "VARCHAR",
                "Null Count": 0,
                "Null %": 0.0,
                "Unique Values": 90,
            },
        ]
    )
    profile_data = {
        "row_count": 90,
        "column_count": 2,
        "duplicate_row_count": 0,
        "findings": [],
        "column_profiles": col_profiles,
    }
    delta = "Source Health: 75/100 ➔ Workspace Health: 95/100 (+20 pts) | Duplicates: -10 duplicates cleaned"

    pdf_bytes = generate_executive_profile_pdf(
        db_name="ecommerce_db",
        target_tbl_name="customers__cleaning_xyz",
        is_workspace=True,
        score=95,
        score_label="Excellent Health",
        score_color_hex="#10B981",
        profile_data=profile_data,
        delta_callout=delta,
    )

    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 1000
    assert pdf_bytes.startswith(b"%PDF-")


def test_generate_executive_profile_pdf_empty_and_edge_cases():
    """Verify PDF generation handles empty findings and missing fields gracefully."""
    profile_data = {
        "row_count": 0,
        "column_count": 0,
        "duplicate_row_count": 0,
        "findings": [],
        "column_profiles": pd.DataFrame(),
    }

    pdf_bytes = generate_executive_profile_pdf(
        db_name="empty_db",
        target_tbl_name="empty_table",
        is_workspace=False,
        score=100,
        score_label="Clean / Empty Table",
        score_color_hex="#10B981",
        profile_data=profile_data,
        delta_callout="",
    )

    assert isinstance(pdf_bytes, bytes)
    assert pdf_bytes.startswith(b"%PDF-")
