"""
DataClean Studio — Main Navigation Component
ui/main_navigation.py

Enterprise-grade redesign of the top-level View Selector (Source Table vs Cleaning Workspace).
Features:
- Professional heading section with vertical teal accent bar and subtitle.
- Wide, rounded container hosting responsive two-column card options.
- Option 1 (Source Table): Database icon in teal badge, bold dark navy title,
  description "View and manage source data", teal border & tint when active, clean radio indicator.
- Option 2 (Cleaning Workspace): Broom/cleaning icon in warm-amber badge, bold dark navy title,
  description "Clean and transform your data", clean radio indicator.
- 100% synchronized with st.session_state.active_view, st.query_params["active_view"], and callbacks.
"""

from __future__ import annotations

import streamlit as st
from typing import List

NAV_OPTIONS: List[str] = [
    "Source Table",
    "🧹 Cleaning Workspace",
]


def get_main_nav_css() -> str:
    """Returns the scoped CSS rules for the redesigned Main Navigation component."""
    return """
    /* ═══════════════════════════════════════════════════════════════
       MAIN NAVIGATION REDESIGN — Scoped to div.st-key-_main_nav_radio
       =============================================================== */

    /* Heading section */
    .main-nav-header {
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        margin-top: 14px !important;
        margin-bottom: 12px !important;
    }

    .main-nav-accent-bar {
        width: 3.5px !important;
        height: 32px !important;
        background: #0F766E !important;
        border-radius: 3px !important;
        flex-shrink: 0 !important;
    }

    .main-nav-title {
        font-size: 15.5px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin: 0 !important;
        line-height: 1.2 !important;
        letter-spacing: -0.01em !important;
    }

    .main-nav-subtitle {
        font-size: 12.5px !important;
        color: #64748B !important;
        margin: 3px 0 0 0 !important;
        line-height: 1.3 !important;
    }

    /* Outer Navigation Container */
    div.st-key-_main_nav_radio {
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        margin-top: 4px !important;
        margin-bottom: 16px !important;
        box-shadow: none !important;
        box-sizing: border-box !important;
        width: 100% !important;
    }

    /* Completely hide Streamlit's internal widget label */
    div.st-key-_main_nav_radio [data-testid="stWidgetLabel"],
    div.st-key-_main_nav_radio > label,
    div.st-key-_main_nav_radio label[data-testid="stWidgetLabel"] {
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        opacity: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
        border: none !important;
        box-shadow: none !important;
    }

    /* Inner 2-column grid container: two equal segments */
    div.st-key-_main_nav_radio div[role="radiogroup"] {
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 12px !important;
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }

    /* Base Option Card (label): 64px high equal-width segments */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: flex-start !important;
        flex: unset !important;
        min-width: unset !important;
        width: 100% !important;
        padding: 12px 48px 12px 16px !important;
        border-radius: 10px !important;
        border: 1px solid #E2E8F0 !important;
        background: #FFFFFF !important;
        cursor: pointer !important;
        height: 64px !important;
        min-height: 64px !important;
        max-height: 64px !important;
        gap: 12px !important;
        position: relative !important;
        box-sizing: border-box !important;
        user-select: none !important;
        transition: border-color 150ms ease, background-color 150ms ease, box-shadow 150ms ease !important;
    }

    /* ── Hide native radio circles completely ── */
    div.st-key-_main_nav_radio div[role="radiogroup"] label div:has(> [data-testid="stMarkdownContainer"]) > div:first-child,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] div:has(> [data-testid="stMarkdownContainer"]) > div:first-child,
    div.st-key-_main_nav_radio label [class*="eqiohyi4"],
    div.st-key-_main_nav_radio label div:has(> [data-testid="stMarkdownContainer"]) > div:not([data-testid="stMarkdownContainer"]),
    div.st-key-_main_nav_radio div[role="radiogroup"] > label > div:first-child,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] > div:first-child {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        min-width: 0 !important;
        max-width: 0 !important;
        opacity: 0 !important;
        visibility: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        position: absolute !important;
        pointer-events: none !important;
    }

    /* Text Container on the right (order: 2) — title + description stacked as one tight vertically centered group */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label > div,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] > div,
    div.st-key-_main_nav_radio div[role="radiogroup"] > label > div[data-testid="stMarkdownContainer"],
    div.st-key-_main_nav_radio label[data-baseweb="radio"] > div[data-testid="stMarkdownContainer"] {
        order: 2 !important;
        display: flex !important;
        flex-direction: column !important;
        align-items: flex-start !important;
        justify-content: center !important;
        flex: 1 1 auto !important;
        min-width: 0 !important;
        text-align: left !important;
        gap: 2px !important;
    }

    div.st-key-_main_nav_radio div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] p,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] [data-testid="stMarkdownContainer"] p {
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.3 !important;
        color: #64748B !important;
        font-size: 13px !important;
        font-weight: 400 !important;
        text-align: left !important;
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
    }

    div.st-key-_main_nav_radio div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] strong,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] [data-testid="stMarkdownContainer"] strong {
        display: block !important;
        font-size: 14.5px !important;
        font-weight: 600 !important;
        color: #0F172A !important;
        letter-spacing: -0.01em !important;
        margin: 0 !important;
        line-height: 1.25 !important;
    }

    /* Icon Tile on the left (order: 1): 36px rounded tile */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label::before,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]::before {
        content: "" !important;
        order: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 36px !important;
        height: 36px !important;
        min-width: 36px !important;
        border-radius: 8px !important;
        flex-shrink: 0 !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: 18px 18px !important;
        transition: all 150ms ease !important;
    }

    /* Option 1: Source Table Icon (Teal tinted badge) */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label:nth-of-type(1)::before,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:nth-of-type(1)::before {
        background-color: rgba(15, 118, 110, 0.10) !important;
        border: 1px solid rgba(15, 118, 110, 0.20) !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%230F766E' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cellipse cx='12' cy='5' rx='9' ry='3'/%3E%3Cpath d='M3 5V19A9 3 0 0 0 21 19V5'/%3E%3Cpath d='M3 12A9 3 0 0 0 21 12'/%3E%3C/svg%3E") !important;
    }

    /* Option 2: Cleaning Workspace Icon (Warm amber tinted badge) */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label:nth-of-type(2)::before,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:nth-of-type(2)::before {
        background-color: rgba(217, 119, 6, 0.10) !important;
        border: 1px solid rgba(217, 119, 6, 0.22) !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23D97706' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m18 2 4 4'/%3E%3Cpath d='m15 5 4 4'/%3E%3Cpath d='M13 7 4 16l-1 5 5-1L17 11'/%3E%3Cpath d='M14 14.5a3.5 3.5 0 0 0-5 0'/%3E%3C/svg%3E") !important;
    }

    /* Unselected: 1px slate-200 border, darker on hover */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label:not(:has(input:checked)),
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:not(:has(input:checked)) {
        border: 1px solid #E2E8F0 !important;
        background: #FFFFFF !important;
    }

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:not(:has(input:checked)):hover,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:not(:has(input:checked)):hover {
        border-color: #94A3B8 !important;
        background: #F8FAFC !important;
    }

    /* Default unselected ::after is hidden */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label::after,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]::after {
        content: "" !important;
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        border: none !important;
    }

    /* Selected State: 1.5px teal border + light teal tint + check icon top-right edge */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input[type="radio"]:checked),
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input[type="radio"]:checked) {
        background: #F0FDFA !important;
        border: 1.5px solid #0F766E !important;
        box-shadow: 0 1px 3px rgba(15, 118, 110, 0.08) !important;
    }

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input[type="radio"]:checked) strong,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input[type="radio"]:checked) strong {
        color: #0F766E !important;
    }

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input[type="radio"]:checked)::after,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input[type="radio"]:checked)::after {
        content: "" !important;
        display: block !important;
        position: absolute !important;
        top: 50% !important;
        right: 16px !important;
        transform: translateY(-50%) !important;
        width: 18px !important;
        height: 18px !important;
        border: none !important;
        border-radius: 0 !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: 18px 18px !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%230F766E' stroke-width='2.25' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpolyline points='20 6 9 17 4 12'/%3E%3C/svg%3E") !important;
    }

    /* Visible focus ring on keyboard navigation */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input:focus-visible),
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input:focus-visible),
    :focus-visible {
        outline: 2px solid #0F766E !important;
        outline-offset: 1px !important;
    }

    /* Responsive Tablet Adjustments */
    @media (max-width: 900px) {
        div.st-key-_main_nav_radio div[role="radiogroup"] > label,
        div.st-key-_main_nav_radio label[data-baseweb="radio"] {
            padding: 12px 42px 12px 14px !important;
            gap: 12px !important;
            min-height: 64px !important;
            height: 64px !important;
        }
        div.st-key-_main_nav_radio div[role="radiogroup"] > label::before,
        div.st-key-_main_nav_radio label[data-baseweb="radio"]::before {
            width: 36px !important;
            height: 36px !important;
            min-width: 36px !important;
            background-size: 18px 18px !important;
        }
        div.st-key-_main_nav_radio div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] strong,
        div.st-key-_main_nav_radio label[data-baseweb="radio"] [data-testid="stMarkdownContainer"] strong {
            font-size: 14px !important;
        }
        div.st-key-_main_nav_radio div[role="radiogroup"] > label [data-testid="stMarkdownContainer"] p,
        div.st-key-_main_nav_radio label[data-baseweb="radio"] [data-testid="stMarkdownContainer"] p {
            font-size: 12.5px !important;
        }
    }

    /* Responsive Mobile Stacking */
    @media (max-width: 640px) {
        div.st-key-_main_nav_radio div[role="radiogroup"] {
            grid-template-columns: 1fr !important;
            gap: 8px !important;
        }
        div.st-key-_main_nav_radio div[role="radiogroup"] > label,
        div.st-key-_main_nav_radio label[data-baseweb="radio"] {
            padding: 12px 40px 12px 14px !important;
            min-height: 64px !important;
            height: 64px !important;
        }
    }
    """


def render_main_navigation() -> str:
    """
    Renders the modern enterprise Main Navigation component.
    Returns the currently active view ('Source Table' or '🧹 Cleaning Workspace').
    """
    # Ensure styles are injected
    st.markdown(f"<style>{get_main_nav_css()}</style>", unsafe_allow_html=True)

    # Default to Cleaning Workspace (second option) if not set
    if "active_view" not in st.session_state or st.session_state.active_view not in NAV_OPTIONS:
        st.session_state.active_view = NAV_OPTIONS[1]

    current_view = st.session_state.active_view

    # Ensure the radio key in session_state matches active_view
    if st.session_state.get("_main_nav_radio") != current_view:
        st.session_state._main_nav_radio = current_view

    def _on_main_nav_change() -> None:
        chosen = st.session_state.get("_main_nav_radio")
        if chosen and chosen in NAV_OPTIONS:
            st.session_state.active_view = chosen
            st.query_params["active_view"] = chosen

    def _format_nav_option(opt: str) -> str:
        if opt == "Source Table":
            return "**Source Table**  \nView and manage source data"
        elif "Cleaning Workspace" in opt:
            return "**Cleaning Workspace**  \nClean and transform your data"
        return opt

    # Render the styled radio widget inside its key wrapper
    selected_view = st.radio(
        "Main Navigation",
        options=NAV_OPTIONS,
        index=NAV_OPTIONS.index(current_view),
        format_func=_format_nav_option,
        key="_main_nav_radio",
        on_change=_on_main_nav_change,
        horizontal=True,
        label_visibility="collapsed",
    )

    if selected_view != current_view:
        st.session_state.active_view = selected_view
        st.query_params["active_view"] = selected_view
        st.rerun()

    return st.session_state.active_view
