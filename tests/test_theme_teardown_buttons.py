"""
Unit tests for Teardown Workspace button styling in ui.theme.
Verifies that all teardown workspace buttons are styled with solid red background,
crisp white text, and maximum contrast/visibility according to design requirements.
"""

import pytest
from ui.theme import _build_css


def test_teardown_buttons_css_present():
    css = _build_css()
    assert "Teardown Workspace Buttons" in css


def test_teardown_buttons_all_keys_targeted():
    css = _build_css()
    expected_keys = [
        "st-key-teardown_ws_btn_from_source",
        "st-key-hub_teardown_ws_btn",
        "st-key-hub_teardown_confirm_btn",
        "st-key-del_single_ws_btn",
        "st-key-del_multi_ws_btn",
        "st-key-del_all_tbl_ws_btn",
        "st-key-ws_view_del_single_btn",
        "st-key-ws_view_del_multi_btn",
        "st-key-ws_view_del_all_btn",
    ]
    for key in expected_keys:
        assert key in css, f"Missing key {key} in teardown button CSS"


def test_teardown_buttons_red_background_and_white_text():
    css = _build_css()
    # Check for vibrant red background
    assert "#DC2626" in css
    assert "#B91C1C" in css
    # Check for pure white text on teardown buttons
    assert "#FFFFFF !important" in css
    # Check for text-shadow for crisp legibility
    assert "text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35) !important;" in css
    # Check for bold font-weight
    assert "font-weight: 700 !important;" in css


def test_cancel_button_not_styled_red():
    css = _build_css()
    # Cancel button must have neutral/white background protection
    assert "st-key-hub_teardown_cancel_btn" in css
    assert "background: #FFFFFF" in css or "background-color: #FFFFFF" in css


def test_table_and_dataframe_headers_styled_distinct_color():
    css = _build_css()
    # Check that dataframe and table header styles are distinct from plain white cells
    assert "--gdg-bg-header: #D1EBE7" in css
    assert "thead th" in css
    assert "background-color: #D1EBE7" in css
    assert "color: #0F172A" in css

