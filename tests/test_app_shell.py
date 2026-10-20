"""
Unit tests for DataClean Studio modern SaaS App Shell and Navigation.
Tests:
- render_saas_breadcrumb: single-line non-truncating breadcrumb, links, active page, Lucide icons
- render_module_header: back navigation, safe sandbox status badge, module title & description
- render_sandbox_banner: table copy action, source table attribution, comma-formatted row count
- _generate_tab_icon_css: data URI generation for all 10 module vector icons
"""

from unittest.mock import patch, MagicMock
import pytest
import streamlit as st

from ui.components import (
    render_saas_breadcrumb,
    render_module_header,
    render_sandbox_banner,
)
from ui.cleaning_tabs import _generate_tab_icon_css, CLEANING_MODULES
from ui.icons import get_icon_svg


def test_generate_tab_icon_css_covers_all_modules():
    """Verify that _generate_tab_icon_css produces valid CSS rules for all module tabs."""
    css = _generate_tab_icon_css()
    assert len(CLEANING_MODULES) == 12
    for idx, mod in enumerate(CLEANING_MODULES, 1):
        assert f":nth-of-type({idx})" in css
        assert "data:image/svg+xml" in css


def test_render_saas_breadcrumb_html_structure():
    """Verify render_saas_breadcrumb builds semantic nav, active class, and query param links."""
    items = [
        {"label": "DataClean Studio", "icon": "home", "url": "?bc_nav=home", "active": False},
        {"label": "ecom_db", "icon": "database", "url": "?bc_nav=db", "active": False},
        {"label": "orders", "icon": "table", "url": None, "active": True},
    ]

    with patch.object(st, "markdown") as mock_markdown:
        render_saas_breadcrumb(items)
        assert mock_markdown.called
        rendered_html = mock_markdown.call_args[0][0]

        assert 'class="dc-breadcrumb"' in rendered_html
        assert 'href="?bc_nav=home"' in rendered_html
        assert 'href="?bc_nav=db"' in rendered_html
        assert 'DataClean Studio' in rendered_html
        assert 'ecom_db' in rendered_html
        assert 'orders' in rendered_html
        assert 'class="dc-bc-item active"' in rendered_html
        assert 'class="dc-bc-sep"' in rendered_html


def test_render_module_header_button_and_badge():
    """Verify render_module_header renders the back button, title, and status pill."""
    with patch.object(st, "button", return_value=False) as mock_btn, \
         patch.object(st, "markdown") as mock_markdown:
        clicked = render_module_header(
            title="Whitespace Normalization",
            subtitle="Remove extra spaces",
            badge_text="Safe Sandbox",
            badge_type="brand",
            back_label="Back to Cleaning Hub",
            back_key="test_ws_back_btn",
        )
        assert clicked is False
        assert mock_btn.called
        assert mock_btn.call_args[1]["key"] == "test_ws_back_btn"
        assert "Back to Cleaning Hub" in mock_btn.call_args[0][0]

        # Check markdown calls for badge and module title
        all_rendered = "".join(call[0][0] for call in mock_markdown.call_args_list)
        assert "Whitespace Normalization" in all_rendered
        assert "Remove extra spaces" in all_rendered
        assert "Safe Sandbox" in all_rendered
        assert "dc-module-title" in all_rendered


def test_render_module_header_click_event():
    """Verify render_module_header returns True when the user clicks the back button."""
    with patch.object(st, "button", return_value=True), \
         patch.object(st, "markdown"):
        clicked = render_module_header(
            title="Duplicate Handling",
            back_key="test_dup_back",
        )
        assert clicked is True


def test_render_sandbox_banner_formatting():
    """Verify render_sandbox_banner formats table names, source attribution, and row counts."""
    with patch.object(st, "markdown") as mock_markdown:
        render_sandbox_banner(
            working_table="orders__cleaning_abc123",
            source_table="ecom_db.orders",
            row_count=1254300,
        )
        assert mock_markdown.called
        banner_html = mock_markdown.call_args[0][0]

        assert "orders__cleaning_abc123" in banner_html
        assert "ecom_db.orders" in banner_html
        assert "1,254,300 rows" in banner_html
        assert "Sandbox active" in banner_html
        assert "dc-sandbox-strip" in banner_html
