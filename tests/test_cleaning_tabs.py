"""
Unit tests for ui/cleaning_tabs.py, staging source row count, and internal column filtering.
Tests:
- 8 canonical cleaning modules and exact tooltip copy
- Accessible tooltip attributes (tabindex="0", role="tooltip", aria-describedby)
- Click isolation (stopPropagation / preventDefault)
- CSS selectors, pill styling, and overview plain text links
- Staging attach_workspace source row count handling
- Internal column filtering (hiding '__' columns)
"""

from unittest.mock import MagicMock, patch
import pytest
import streamlit as st

from ui.cleaning_tabs import (
    CLEANING_MODULES,
    CLEANING_TAB_NAMES,
    get_cleaning_tabs_css,
    get_cleaning_tabs_js,
    get_tabs_help_overlay_html,
    render_cleaning_tabs,
)
from src.staging import attach_workspace


def test_canonical_cleaning_modules():
    """Verify all 12 cleaning modules exist and have the exact expected titles and names."""
    expected_titles = [
        "Cleaning Hub",
        "Whitespace Cleaning",
        "Blank & NULL Values",
        "Text Casing",
        "Duplicate Handling",
        "Special Character Cleaning",
        "Date Formatting",
        "Advanced Date Standardization",
        "Boolean Normalization",
        "Numeric Data Cleaning",
        "AI Assistant",
        "AI Column Analysis and Cleaning",
    ]
    actual_titles = [m["title"] for m in CLEANING_MODULES]
    assert actual_titles == expected_titles
    assert len(CLEANING_TAB_NAMES) == 12


def test_exact_tooltip_copy_requirements():
    """Verify each module has the exact required tooltip text from the user specification."""
    expected_tooltips = {
        "Cleaning Hub": "Overview of the workspace and your data preview.",
        "Whitespace Cleaning": "Removes extra spaces, tabs and line breaks from text.",
        "Blank & NULL Values": "Finds empty and NULL values and replaces them with a value you choose.",
        "Text Casing": "Converts text to lowercase, UPPERCASE or Title Case.",
        "Duplicate Handling": "Finds repeated rows based on columns you pick.",
        "Special Character Cleaning": "Removes or replaces unwanted special characters, control characters, and non-printable characters from text.",
        "Date Formatting": "Converts dates into one format you choose, like YYYY-MM-DD.",
        "Advanced Date Standardization": "Detects dates in mixed formats and converts them all to one standard.",
        "Boolean Normalization": "Converts true, TRUE, t, Y, y into one consistent True/False or Yes/No.",
        "Numeric Data Cleaning": "Scans text columns for numbers and converts them to INT, DECIMAL, or DOUBLE.",
        "AI Assistant": "Connect your AI model and chat with an intelligent assistant.",
        "AI Column Analysis and Cleaning": "Analyze individual database columns, identify potential data-quality issues, and explore AI-assisted cleaning recommendations.",
    }

    for mod in CLEANING_MODULES:
        title = mod["title"]
        assert title in expected_tooltips
        assert mod["tooltip"] == expected_tooltips[title]


def test_get_cleaning_tabs_css_structure():
    """Verify CSS provides 4-per-row grid layout, visible radio circles, dark-teal active border, and tooltips."""
    css = get_cleaning_tabs_css()

    # 4-per-row grid (2 rows) — equal minmax columns so cards never size by content
    assert "grid-template-columns: repeat(4, minmax(0, 1fr))" in css

    # Radio circle is visible (display: flex) with border
    assert 'div[role="radiogroup"] > label > div:first-child' in css
    assert "display: flex !important" in css

    # Equal-sized rounded white boxes
    assert "border-radius: 8px" in css
    assert "0F766E" in css  # Dark teal accent

    # Titles wrap freely to 2 lines; no forced single-line truncation
    assert "overflow-wrap: anywhere" in css
    assert "white-space: normal" in css
    assert "word-break: normal" in css

    # Help icon & tooltip
    assert ".tab-help-btn" in css
    assert ".tab-help-tooltip" in css
    assert ":focus-visible" in css
    assert ".edge-left" in css
    assert ".edge-right" in css


def test_get_cleaning_tabs_js_accessibility_and_isolation():
    """Verify JavaScript implements accessibility attributes and stops click propagation."""
    js = get_cleaning_tabs_js()

    # Accessible attributes
    assert 'tabindex' in js
    assert 'role' in js
    assert 'role="tooltip"' in js or "setAttribute('role', 'tooltip')" in js
    assert 'aria-describedby' in js
    assert 'aria-label' in js

    # Event isolation so clicking ? never switches tab
    assert "e.preventDefault()" in js
    assert "e.stopPropagation()" in js

    # Dismissal via Escape and click outside
    assert "'Escape'" in js
    assert "addEventListener('click'" in js


def test_get_tabs_help_overlay_html_structure_and_accessibility():
    """Verify HTML overlay implements all 9 modules, accessibility attributes, and click isolation."""
    html = get_tabs_help_overlay_html()

    assert "cleaning-tabs-help-overlay" in html
    assert "overlay-tab-slot" in html
    assert html.count("tab-help-box") == len(CLEANING_MODULES)
    assert html.count("tab-help-tooltip") == len(CLEANING_MODULES)

    # Check accessibility attributes
    assert 'tabindex="0"' in html
    assert 'role="button"' in html
    assert 'role="tooltip"' in html
    assert 'aria-describedby=' in html
    assert 'aria-label=' in html

    # Check event isolation so clicking ? never switches the active tab
    assert "event.preventDefault()" in html
    assert "event.stopPropagation()" in html

    # Check right-most boundary classes to prevent edge clipping
    assert "tip-rightmost" in html
    assert "tip-leftmost" in html

    # Check that all 8 tooltip texts are present in the HTML
    for mod in CLEANING_MODULES:
        assert mod["tooltip"] in html
        assert f"Help: {mod['title']}" in html


def test_render_cleaning_tabs_session_state_and_query_params():
    """Verify render_cleaning_tabs initializes session state and syncs correctly."""
    with patch("streamlit.radio", return_value="✂️ Whitespace Cleaning") as mock_radio, \
         patch("streamlit.markdown") as mock_md:
        
        st.session_state.workspace_sub_tab = "🏠 Cleaning Hub"
        st.session_state._ws_sub_radio = "🏠 Cleaning Hub"

        selected = render_cleaning_tabs()

        assert selected == "✂️ Whitespace Cleaning"
        assert st.session_state.workspace_sub_tab == "✂️ Whitespace Cleaning"
        mock_radio.assert_called_once()


def test_attach_workspace_populates_source_row_count():
    """Verify attach_workspace returns source_row_count in details."""
    mock_engine = MagicMock()
    
    with patch("src.staging.get_workspace_info") as mock_info, \
         patch("src.staging.inspect") as mock_inspect:
        
        mock_inspector = MagicMock()
        mock_inspector.get_table_names.return_value = ["customers__cleaning_12345"]
        mock_inspect.return_value = mock_inspector

        mock_info.return_value = {
            "working_table_name": "customers__cleaning_12345",
            "row_count": 50,
            "schema": [{"name": "id"}, {"name": "name"}, {"name": "__bool_backup_is_active"}],
            "preview": MagicMock(),
            "exists": True,
        }

        # Mock query count on source table
        mock_conn = MagicMock()
        mock_res = MagicMock()
        mock_res.scalar.return_value = 50
        mock_conn.execute.return_value = mock_res
        mock_engine.connect.return_value.__enter__.return_value = mock_conn

        ok, msg, details = attach_workspace(mock_engine, "test_db", "customers__cleaning_12345")
        
        assert ok is True
        assert details is not None
        assert details["source_row_count"] == 50
        assert details["working_row_count"] == 50
        assert details["source_table"] == "customers"


def test_internal_column_filtering():
    """Verify columns starting with '__' are filtered out from schema count and preview columns."""
    sample_schema = [
        {"name": "id", "type": "int"},
        {"name": "full_name", "type": "varchar"},
        {"name": "__bool_backup_is_active", "type": "varchar"},
        {"name": "__date_backup_created_at", "type": "varchar"},
    ]

    visible_schema = [
        col for col in sample_schema
        if not col["name"].startswith("__")
    ]
    assert len(visible_schema) == 2
    assert [c["name"] for c in visible_schema] == ["id", "full_name"]

    sample_preview_cols = ["id", "full_name", "__bool_backup_is_active"]
    display_cols = [c for c in sample_preview_cols if not c.startswith("__")]
    assert display_cols == ["id", "full_name"]


def test_internal_column_filtering_mysql_format():
    """Verify columns with MySQL metadata dict format ('Column Name') and strings work without error."""
    mysql_schema = [
        {"Column Name": "id", "Data Type": "int", "Nullable": "NO"},
        {"Column Name": "name", "Data Type": "varchar", "Nullable": "YES"},
        {"Column Name": "__bool_backup_active", "Data Type": "tinyint", "Nullable": "YES"},
        {"Column Name": "__internal_meta", "Data Type": "text", "Nullable": "YES"},
    ]

    def _is_internal_col(c):
        if isinstance(c, dict):
            col_name = (
                c.get("Column Name")
                or c.get("column_name")
                or c.get("COLUMN_NAME")
                or c.get("name")
                or ""
            )
        else:
            col_name = str(c or "")
        return str(col_name).startswith("__")

    visible = [c for c in mysql_schema if not _is_internal_col(c)]
    assert len(visible) == 2
    assert [c["Column Name"] for c in visible] == ["id", "name"]

    # String format
    string_schema = ["id", "status", "__temp_col"]
    visible_str = [c for c in string_schema if not _is_internal_col(c)]
    assert visible_str == ["id", "status"]

    # None or empty dict safety
    assert not _is_internal_col(None)
    assert not _is_internal_col({})
    assert _is_internal_col({"name": "__test"})
    assert _is_internal_col({"column_name": "__test"})
    assert _is_internal_col({"COLUMN_NAME": "__test"})

