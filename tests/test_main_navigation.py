"""
Unit tests for ui/main_navigation.py
Tests:
- CSS generation and tokens
- Option definitions and formatting
- Session state synchronization and default values
- Export integrity from ui package
"""

from unittest.mock import MagicMock, patch
import pytest
import streamlit as st

from ui import render_main_navigation, get_main_nav_css
from ui.main_navigation import NAV_OPTIONS


def test_nav_options_constants():
    """Verify NAV_OPTIONS contains the canonical view strings expected by app.py."""
    assert "Source Table" in NAV_OPTIONS
    assert "🧹 Cleaning Workspace" in NAV_OPTIONS
    assert len(NAV_OPTIONS) == 2


def test_get_main_nav_css_structure():
    """Verify get_main_nav_css returns all required selectors, SVG icons, and media queries."""
    css = get_main_nav_css()

    # Heading section classes
    assert ".main-nav-header" in css
    assert ".main-nav-accent-bar" in css
    assert ".main-nav-title" in css
    assert ".main-nav-subtitle" in css

    # Scoped radio container and widget label suppression
    assert "div.st-key-_main_nav_radio" in css
    assert "stWidgetLabel" in css
    assert 'div[role="radiogroup"]' in css
    assert "grid-template-columns: 1fr 1fr" in css

    # Option 1: Teal badge and database icon SVG
    assert "label:nth-of-type(1)::before" in css
    assert "0F766E" in css  # Teal accent color
    assert "ellipse" in css  # Database SVG ellipse tag

    # Option 2: Warm-amber badge and cleaning icon SVG
    assert "label:nth-of-type(2)::before" in css
    assert "D97706" in css  # Warm amber accent

    # Radio selection indicator
    assert "label::after" in css
    assert "label:has(input[type=\"radio\"]:checked)::after" in css

    # Accessibility & keyboard navigation
    assert ":focus-visible" in css

    # Responsiveness
    assert "@media (max-width: 900px)" in css
    assert "@media (max-width: 640px)" in css
    assert "grid-template-columns: 1fr" in css


def test_render_main_navigation_default_state():
    """Verify render_main_navigation initializes default active_view to '🧹 Cleaning Workspace'."""
    # Clear active_view from session state
    if "active_view" in st.session_state:
        del st.session_state["active_view"]
    if "_main_nav_radio" in st.session_state:
        del st.session_state["_main_nav_radio"]

    with patch("streamlit.markdown") as mock_markdown, \
         patch("streamlit.radio", return_value="🧹 Cleaning Workspace") as mock_radio:
        result = render_main_navigation()

        assert result == "🧹 Cleaning Workspace"
        assert st.session_state.active_view == "🧹 Cleaning Workspace"
        assert st.session_state._main_nav_radio == "🧹 Cleaning Workspace"

        # Verify radio widget called with collapsed label and format_func
        mock_radio.assert_called_once()
        _, kwargs = mock_radio.call_args
        assert kwargs["key"] == "_main_nav_radio"
        assert kwargs["label_visibility"] == "collapsed"
        assert kwargs["horizontal"] is True

        # Verify format_func produces bold title and supporting descriptions
        format_func = kwargs["format_func"]
        formatted_src = format_func("Source Table")
        assert "**Source Table**" in formatted_src
        assert "View and manage source data" in formatted_src

        formatted_ws = format_func("🧹 Cleaning Workspace")
        assert "**Cleaning Workspace**" in formatted_ws
        assert "Clean and transform your data" in formatted_ws


def test_render_main_navigation_workspace_selected():
    """Verify render_main_navigation respects when '🧹 Cleaning Workspace' is active."""
    st.session_state.active_view = "🧹 Cleaning Workspace"
    st.session_state._main_nav_radio = "🧹 Cleaning Workspace"

    with patch("streamlit.markdown") as mock_markdown, \
         patch("streamlit.radio", return_value="🧹 Cleaning Workspace") as mock_radio:
        result = render_main_navigation()

        assert result == "🧹 Cleaning Workspace"
        _, kwargs = mock_radio.call_args
        assert kwargs["index"] == 1  # 2nd option
