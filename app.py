import html
import re
import streamlit as st
import pandas as pd
import time
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy import inspect, text
from fpdf import FPDF

from src.connection import MySQLConnectionManager
from src.metadata import MySQLMetadataInspector
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
    create_workspace,
    delete_workspace,
    get_workspace_info,
    remove_whitespace_workspace,
    replace_blank_values_workspace,
    replace_missing_values_workspace,
    scan_missing_values,
    _quote_identifier,
    _quote_table,
    normalize_text_case_workspace,
    count_text_casing_changes,
    get_text_columns,
    get_text_columns_with_types,
    scan_special_characters_workspace,
    clean_special_characters_workspace,
    CONTROL_CHARS,
    NON_PRINTABLE_CHARS,
    COMMON_SPECIAL_CHARS,
    get_date_columns,
    detect_date_like_columns,
    analyze_date_column,
    format_dates_workspace,
    apply_date_formatting_workspace,
    FORMAT_MAP,
    count_blank_values_in_column,
    scan_blank_and_null_columns,
    list_workspaces_for_table,
    list_all_workspaces,
    attach_workspace,
    delete_all_workspaces,
    detect_date_columns_rule_based,
    analyze_column_date_formats_rule_based,
    transform_advanced_date_column_rule_based,
    detect_boolean_like_columns,
    analyze_boolean_column,
    preview_boolean_normalization,
    transform_boolean_column,
    undo_boolean_normalization,
    ADV_DATE_OUTPUT_FORMATS,
    ALLOWED_SCAN_PERCENTAGES,
    detect_date_columns,
    preview_column_standardization,
    standardize_column,
    get_safe_output_column_name,
    NumericNormalizationConfig,
    ValueValidationResult,
    NumericColumnAnalysis,
    NumericDetectionClassification,
    SUPPORTED_NUMERIC_TYPES,
    NUMBER_FORMATS,
    get_eligible_text_columns,
    analyze_numeric_column,
    scan_table_numeric_candidates,
    convert_column_to_numeric_workspace,
)
from src.profiling import profile_source_table, profile_workspace
from src.pdf_report import generate_executive_profile_pdf
from ui.theme import inject_theme
from ui.main_navigation import render_main_navigation
from ui.credential_dialog import is_credential_error, render_credential_error_dialog
from ui.sidebar_view import (
    get_sidebar_css,
    render_sidebar_brand_redesign,
    render_sidebar_promo_card,
    render_sidebar_section_heading,
    render_sidebar_status_card_redesign,
    render_sidebar_bottom_waves,
)
from ui.components import (
    render_sandbox_banner,
    render_alert,
    render_page_header,
    render_badge,
    render_metric_card,
    render_saas_breadcrumb,
    render_module_header,
    render_section_header,
    render_data_table,
)
from ui.ai_assistant_view import (
    render_ai_assistant_page,
    render_ai_config_sidebar,
    render_ai_assistant_main,
)
from ui.ai_column_cleaning_view import render_ai_column_cleaning_view

# ============================================================
# Page Configuration
# ============================================================

st.set_page_config(
    page_title="DataClean Studio | MySQL Quality Platform",
    page_icon=None,
    layout="wide",
    initial_sidebar_state="expanded",
)

# ============================================================
# Design System & UI/UX Styling (Enterprise Soft Dark / Light System)
# ============================================================
import base64
import pathlib


def render_html(html: str, **kwargs) -> None:
    """Cleans each line's leading/trailing whitespace, strips blank lines, and renders HTML via st.markdown."""
    lines = [line.strip() for line in html.strip().splitlines() if line.strip()]
    cleaned = chr(10).join(lines)
    st.markdown(cleaned, unsafe_allow_html=True)


@st.cache_data
def get_background_base64() -> str:
    """Loads and caches the background image as base64."""
    bg_file = pathlib.Path(__file__).parent / "Background.png"
    if not bg_file.exists():
        bg_file = pathlib.Path(__file__).parent / "img" / "Background.png"
    if bg_file.exists():
        return base64.b64encode(bg_file.read_bytes()).decode()
    return ""


def set_background(theme: str = "dark") -> str:
    """Generates CSS background rule with base64 Background.png and theme-specific overlay."""
    bg_b64 = get_background_base64()
    if theme == "light":
        overlay = "rgba(244, 246, 250, 0.90)"
        fallback_bg = "#F4F6FA"
    else:
        overlay = "rgba(15, 22, 35, 0.72)"
        fallback_bg = "#0F1623"

    if bg_b64:
        return f"""
        [data-testid="stAppViewContainer"] {{
            background-color: {fallback_bg} !important;
            background-image: linear-gradient(180deg, {overlay} 0%, {overlay} 100%), url("data:image/png;base64,{bg_b64}") !important;
            background-size: cover !important;
            background-position: center !important;
            background-attachment: fixed !important;
            background-repeat: no-repeat !important;
        }}
        """
    else:
        return f"""
        [data-testid="stAppViewContainer"] {{
            background-color: {fallback_bg} !important;
        }}
        """


def theme_toggle() -> str:
    """Renders theme toggle at the bottom of the sidebar and manages state."""
    if "ui_theme" not in st.session_state:
        st.session_state.ui_theme = "dark"
    if "ui_theme_toggle" not in st.session_state:
        st.session_state.ui_theme_toggle = st.session_state.ui_theme == "dark"

    def _on_theme_toggle_change():
        st.session_state.ui_theme = (
            "dark" if st.session_state.ui_theme_toggle else "light"
        )

    render_html(
        '<div style="margin-top: 20px; border-top: 1px solid var(--dq-border); padding-top: 14px;"></div>'
    )
    st.toggle(
        "Dark mode",
        key="ui_theme_toggle",
        on_change=_on_theme_toggle_change,
        help="Switch between Dark and Light interface themes",
    )
    return st.session_state.ui_theme


# ============================================================
# Professional Alert Modal System
# ============================================================

def show_alert(
    title: str,
    message: str,
    alert_type: str = "error",
    key: str = "dq_alert",
    on_dismiss: str = None,
    auto_dismiss: bool = True,
    auto_dismiss_delay: int = 3000
) -> None:
    """
    Display a professional animated alert modal in the center of the screen.
    
    Parameters
    ----------
    title : str
        Alert title (e.g., "Connection Failed", "Invalid Credentials")
    message : str
        Detailed message for the user
    alert_type : str
        One of: "error", "warning", "info", "success"
    key : str
        Unique key for this alert (used in session_state)
    on_dismiss : str, optional
        Session state key to set True when dismissed
    auto_dismiss : bool
        If True, auto-dismiss after auto_dismiss_delay milliseconds
    auto_dismiss_delay : int
        Delay in milliseconds before auto-dismiss (default 3000 = 3 seconds)
    """
    alert_key = f"{key}_visible"
    if alert_key not in st.session_state:
        st.session_state[alert_key] = True
    
    if not st.session_state[alert_key]:
        return
    
    # Monoline SVG Icon mapping (18px, 1.75px stroke)
    icons = {
        "error": get_icon_svg("alert_circle", size=20, stroke_width=2.0),
        "warning": get_icon_svg("alert_triangle", size=20, stroke_width=2.0),
        "info": get_icon_svg("info", size=20, stroke_width=2.0),
        "success": get_icon_svg("check_circle_2", size=20, stroke_width=2.0),
    }
    close_icon_svg = get_icon_svg("x", size=14, stroke_width=2.0)
    
    # Accessible role descriptions
    role_desc = {
        "error": "Error alert",
        "warning": "Warning alert", 
        "info": "Information alert",
        "success": "Success alert"
    }
    
    icon = icons.get(alert_type, get_icon_svg("info", size=20, stroke_width=2.0))
    role = role_desc.get(alert_type, "Alert")
    
    render_html(f"""
    <div class="dq-alert-overlay" id="dq-alert-overlay-{key}" role="alertdialog" aria-labelledby="dq-alert-title-{key}" aria-describedby="dq-alert-message-{key}" aria-modal="true">
        <div class="dq-alert-modal" id="dq-alert-modal-{key}">
            <div class="dq-alert-header">
                <div class="dq-alert-icon {alert_type}" aria-hidden="true">{icon}</div>
                <h3 class="dq-alert-title" id="dq-alert-title-{key}">{title}</h3>
                <button class="dq-alert-close" onclick="closeAlert('{key}')" aria-label="Dismiss {role.lower()}">{close_icon_svg}</button>
            </div>
            <div class="dq-alert-body">
                <p class="dq-alert-message" id="dq-alert-message-{key}">{message}</p>
            </div>
            <div class="dq-alert-actions">
                <button class="dq-alert-btn primary" onclick="closeAlert('{key}')" autofocus>OK</button>
            </div>
        </div>
    </div>

    <script>
    // Close function - sets a flag that Streamlit can detect via a hidden checkbox
    window.closeAlert = function(key) {{
        const overlay = document.getElementById('dq-alert-overlay-' + key);
        const modal = document.getElementById('dq-alert-modal-' + key);
        if (overlay && modal) {{
            overlay.classList.add('closing');
            modal.classList.add('closing');
            setTimeout(() => {{
                overlay.remove();
            }}, 200);
        }}
        
        // Trigger Streamlit rerun by checking the hidden checkbox
        setTimeout(() => {{
            const checkbox = document.getElementById('dq_alert_dismiss_' + key);
            if (checkbox && !checkbox.checked) {{
                checkbox.click();
            }}
        }}, 50);
    }};
    
    // Close on overlay click
    document.getElementById('dq-alert-overlay-{key}').addEventListener('click', function(e) {{
        if (e.target === this) {{
            closeAlert('{key}');
        }}
    }});
    
    // Close on Escape key
    document.addEventListener('keydown', function handler(e) {{
        if (e.key === 'Escape') {{
            closeAlert('{key}');
            document.removeEventListener('keydown', handler);
        }}
    }});

    // Auto-dismiss after {auto_dismiss_delay}ms
    {f"setTimeout(() => closeAlert('{key}'), {auto_dismiss_delay});" if auto_dismiss else ""}
    </script>
    """)
    
    # Dismiss checkbox - hidden but accessible to JavaScript
    dismissed = st.checkbox(
        "Dismiss alert",
        key=f"dq_alert_dismiss_{key}",
        label_visibility="collapsed",
        value=False
    )
    if dismissed:
        st.session_state[alert_key] = False
        st.rerun()
    
    # Hide checkbox visually but keep it in DOM for JavaScript
    render_html(f"""
    <style>
    div[data-testid="stCheckbox"]:has(input[id="dq_alert_dismiss_{key}"]) {{
        position: fixed !important;
        left: -9999px !important;
        top: -9999px !important;
        width: 1px !important;
        height: 1px !important;
        opacity: 0 !important;
        pointer-events: none !important;
        z-index: -1 !important;
    }}
    </style>
    """)


def parse_connection_error(error_msg: str) -> tuple[str, str]:
    """
    Parse MySQL connection error and return user-friendly (title, message).
    
    Returns
    -------
    tuple: (title, message) - both user-friendly strings
    """
    error_lower = error_msg.lower()
    
    # Access denied - wrong credentials
    if "1045" in error_msg or "access denied" in error_lower or is_credential_error(error_msg):
        return (
            "Invalid Credentials",
            "Your credentials are wrong. Please check your credentials."
        )
    
    # Cannot connect to server
    elif "2003" in error_msg or "2002" in error_msg or "can't connect" in error_lower or "cannot reach" in error_lower:
        return (
            "Cannot Reach Server",
            "Unable to connect to MySQL server. Please check the host address, port, and network/firewall settings."
        )
    
    # Database doesn't exist
    elif "1049" in error_msg or "unknown database" in error_lower:
        return (
            "Database Not Found",
            "The specified database does not exist on this server. Please check the database name."
        )
    
    # Timeout
    elif "timeout" in error_lower or "timed out" in error_lower:
        return (
            "Connection Timeout",
            "The server took too long to respond. Please verify the host and port are correct and reachable."
        )
    
    # SSL/TLS issues
    elif "ssl" in error_lower or "tls" in error_lower or "certificate" in error_lower:
        return (
            "SSL/TLS Error",
            "There's an SSL certificate issue. Try connecting without SSL or check your certificate configuration."
        )
    
    # Generic fallback
    else:
        return (
            "Connection Failed",
            f"Unable to establish connection: {error_msg}"
        )


def inject_global_css(palette: str = "dark") -> None:
    """Injects global enterprise design system tokens and styling rules based on selected palette."""
    is_light = palette == "light"

    if is_light:
        tokens = """
        --dq-bg: #F4F6FA;
        --dq-surface: #FFFFFF;
        --dq-surface2: #EEF2F8;
        --dq-surface-elevated: #FFFFFF;
        --dq-text-primary: #111827;
        --dq-text-secondary: #4B5563;
        --dq-text-muted: #6B7280;
        --dq-border: #D8DEE9;
        --dq-border-hover: #B8C2D4;
        --dq-accent-start: #2563EB;
        --dq-accent-end: #4F46E5;
        --dq-accent-gradient: linear-gradient(135deg, #2563EB 0%, #4F46E5 100%);
        --dq-accent: #2563EB;
        --dq-accent-glow: rgba(37, 99, 235, 0.12);
        --dq-accent-focus: rgba(37, 99, 235, 0.35);
        --dq-success: #16A34A;
        --dq-success-bg: rgba(22, 163, 74, 0.12);
        --dq-danger: #DC2626;
        --dq-danger-bg: rgba(220, 38, 38, 0.12);
        --dq-warning: #D97706;
        --dq-warning-bg: rgba(217, 119, 6, 0.12);
        --dq-shadow: 0 4px 16px rgba(0, 0, 0, 0.06);
        --dq-shadow-hover: 0 8px 24px rgba(0, 0, 0, 0.10);
        --dq-bg-soft: rgba(0, 0, 0, 0.03);
        --dq-slate: #4B5563;
        --dq-slate-muted: #6B7280;
        --dq-slate-text: #111827;
        --dq-warning-border: rgba(217, 119, 6, 0.35);
        --dq-success-border: rgba(22, 163, 74, 0.28);
        --dq-accent-border: rgba(37, 99, 235, 0.35);
        """
    else:
        tokens = """
        --dq-bg: #0F1623;
        --dq-surface: #172033;
        --dq-surface2: #1D2940;
        --dq-surface-elevated: #1D2940;
        --dq-text-primary: #E8ECF4;
        --dq-text-secondary: #B4BFD3;
        --dq-text-muted: #8B98B0;
        --dq-border: rgba(255, 255, 255, 0.12);
        --dq-border-hover: rgba(255, 255, 255, 0.24);
        --dq-accent-start: #5B9BFF;
        --dq-accent-end: #7C83FF;
        --dq-accent-gradient: linear-gradient(135deg, #5B9BFF 0%, #7C83FF 100%);
        --dq-accent: #5B9BFF;
        --dq-accent-glow: rgba(91, 155, 255, 0.18);
        --dq-accent-focus: rgba(91, 155, 255, 0.35);
        --dq-success: #22C55E;
        --dq-success-bg: rgba(34, 197, 94, 0.15);
        --dq-danger: #EF4444;
        --dq-danger-bg: rgba(239, 68, 68, 0.15);
        --dq-warning: #F59E0B;
        --dq-warning-bg: rgba(245, 158, 11, 0.15);
        --dq-shadow: 0 4px 16px rgba(0, 0, 0, 0.18);
        --dq-shadow-hover: 0 8px 24px rgba(0, 0, 0, 0.26);
        --dq-bg-soft: rgba(255, 255, 255, 0.04);
        --dq-slate: #B4BFD3;
        --dq-slate-muted: #8B98B0;
        --dq-slate-text: #E8ECF4;
        --dq-warning-border: rgba(245, 158, 11, 0.35);
        --dq-success-border: rgba(34, 197, 94, 0.28);
        --dq-accent-border: rgba(91, 155, 255, 0.35);
        """

    bg_rule = set_background(palette)

    css = f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

    :root {{
        {tokens}
        --dq-radius-card: 12px;
        --dq-radius-btn: 8px;
        --dq-radius-pill: 9999px;
        --dq-transition: 150ms ease;
        --font-mono: 'JetBrains Mono', 'Fira Code', Menlo, Monaco, Consolas, monospace;
    }}

    html, body, [class*="css"], .stApp {{
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif !important;
        font-size: 15px !important;
        color: var(--dq-text-primary) !important;
        line-height: 1.6 !important;
    }}

    {bg_rule}

    .main {{
        background: transparent !important;
        min-height: 100vh;
    }}

    [data-testid="stHeader"] {{
        background: transparent !important;
    }}

    footer {{
        display: none !important;
    }}

    #MainMenu {{
        visibility: hidden !important;
    }}

    .stAppToolbar {{
        background: transparent !important;
        box-shadow: none !important;
        top: 0.5rem !important;
        right: 1rem !important;
    }}

    code, .mono {{
        font-family: var(--font-mono) !important;
        font-size: 0.9em;
    }}

    /* Global Container Grid Alignment */
    .content-wrapper {{
        max-width: 1100px;
        width: 100%;
        margin-left: auto;
        margin-right: auto;
        box-sizing: border-box;
    }}

    .page-fade-in {{
        animation: pageFadeIn 300ms cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }}

    @keyframes pageFadeIn {{
        from {{
            opacity: 0;
            transform: translateY(6px);
        }}
        to {{
            opacity: 1;
            transform: translateY(0);
        }}
    }}

    /* Sidebar: Premium Glassmorphism panel, adjustable width - Black Theme */
    [data-testid="stSidebar"] {{
        background: 
            radial-gradient(circle at 15% 10%, rgba(30,30,30,0.30), transparent 35%),
            radial-gradient(circle at 85% 85%, rgba(60,60,60,0.20), transparent 40%),
            rgba(0, 0, 0, 0.65) !important;
        backdrop-filter: blur(24px) saturate(140%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(140%) !important;
        border-right: 1px solid rgba(255, 255, 255, 0.10) !important;
        border-radius: 0 !important;
        margin: 0 !important;
        box-shadow: 4px 0 28px rgba(0, 0, 0, 0.40) !important;
        transition: width 280ms cubic-bezier(0.16, 1, 0.3, 1), transform 280ms cubic-bezier(0.16, 1, 0.3, 1) !important;
    }}

    [data-testid="stSidebar"] > div:first-child {{
        padding: 20px 20px 28px 20px !important;
        height: 100vh !important;
        overflow-y: auto !important;
        box-sizing: border-box !important;
    }}

    /* Thin unobtrusive scrollbar */
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar {{
        width: 5px !important;
    }}

    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-track {{
        background: transparent !important;
    }}

    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb {{
        background: rgba(148, 163, 184, 0.20) !important;
        border-radius: 9999px !important;
    }}

    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb:hover {{
        background: rgba(59, 130, 246, 0.40) !important;
    }}

    /* Floating glass collapse & expand buttons */
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarExpandButton"] button {{
        background: rgba(15, 23, 42, 0.75) !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        border: 1px solid rgba(148, 163, 184, 0.20) !important;
        border-radius: 8px !important;
        color: #94A3B8 !important;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25) !important;
        transition: all 200ms ease !important;
    }}

    [data-testid="stSidebarCollapseButton"] button:hover,
    [data-testid="stSidebarExpandButton"] button:hover {{
        background: rgba(59, 130, 246, 0.20) !important;
        color: #60A5FA !important;
        border-color: rgba(59, 130, 246, 0.45) !important;
        transform: scale(1.04) !important;
    }}

    /* Reset nested container padding/borders to prevent box-inside-box */
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }}

    /* Sidebar Header & Brand */
    .sidebar-brand-block {{
        display: flex;
        align-items: center;
        gap: 12px;
        padding-bottom: 14px;
        margin-bottom: 18px;
        border-bottom: 1px solid rgba(148, 163, 184, 0.14);
    }}

    .sidebar-brand-icon {{
        display: flex;
        align-items: center;
        justify-content: center;
        width: 38px;
        height: 38px;
        border-radius: 10px;
        background: rgba(59, 130, 246, 0.14);
        border: 1px solid rgba(59, 130, 246, 0.28);
        font-size: 1.25rem;
        flex-shrink: 0;
    }}

    .sidebar-brand-title {{
        font-size: 16px;
        font-weight: 700;
        color: #E8ECF4;
        line-height: 1.2;
    }}

    .sidebar-brand-sub {{
        font-size: 12px;
        color: #94A3B8;
        margin-top: 2px;
    }}

    .sidebar-section-header {{
        font-size: 12px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.06em !important;
        color: #94A3B8 !important;
        margin-top: 14px !important;
        margin-bottom: 4px !important;
        display: flex !important;
        align-items: center !important;
        gap: 6px !important;
    }}

    .sidebar-section-desc {{
        font-size: 12px !important;
        color: #64748B !important;
        margin-bottom: 12px !important;
        line-height: 1.4 !important;
    }}

    /* Input styling & Perfect Host / Port Alignment */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {{
        align-items: flex-start !important;
    }}

    [data-testid="stSidebar"] label {{
        height: 22px !important;
        min-height: 22px !important;
        line-height: 22px !important;
        margin: 0 0 6px 0 !important;
        display: flex !important;
        align-items: center !important;
    }}

    [data-testid="stSidebar"] label p {{
        font-size: 12px !important;
        font-weight: 500 !important;
        color: #94A3B8 !important;
        margin: 0 0 6px 0 !important;
        line-height: 1.4 !important;
        letter-spacing: 0.01em !important;
        text-transform: none !important;
    }}

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{
        display: flex !important;
        flex-direction: column !important;
        align-items: flex-start !important;
        width: 100% !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTooltipIcon"] {{
        margin-left: auto !important;
        color: #64748B !important;
        opacity: 0.7 !important;
        transition: opacity 150ms ease !important;
    }}
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"]:hover {{
        opacity: 1 !important;
    }}

    [data-testid="stSidebar"] [data-baseweb="input"] {{
        height: 44px !important;
        min-height: 44px !important;
        border-radius: 10px !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTextInput"] input,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input {{
        height: 44px !important;
        min-height: 44px !important;
        line-height: 44px !important;
        background: rgba(15, 23, 42, 0.55) !important;
        border: 1px solid rgba(148, 163, 184, 0.22) !important;
        border-radius: 10px !important;
        color: #E8ECF4 !important;
        font-size: 14px !important;
        padding: 0 14px !important;
        transition: all 180ms ease !important;
        box-shadow: 
            0 1px 2px rgba(0, 0, 0, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.02) !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTextInput"] input:hover,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input:hover {{
        border-color: rgba(148, 163, 184, 0.35) !important;
        background: rgba(15, 23, 42, 0.65) !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTextInput"] input:focus,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input:focus {{
        border-color: #3B82F6 !important;
        box-shadow: 
            0 0 0 3px rgba(59, 130, 246, 0.25),
            0 2px 8px rgba(0, 0, 0, 0.20),
            inset 0 1px 0 rgba(255, 255, 255, 0.03) !important;
        background: rgba(15, 23, 42, 0.75) !important;
        outline: none !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTextInput"] input::placeholder,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input::placeholder {{
        color: #64748B !important;
        opacity: 0.8 !important;
        font-weight: 400 !important;
        font-style: normal !important;
    }}

    [data-testid="stSidebar"] [data-testid="stNumberInput"] [data-testid="stNumberInputContainer"] {{
        height: 44px !important;
        min-height: 44px !important;
        border-radius: 10px !important;
        background: rgba(15, 23, 42, 0.55) !important;
        border: 1px solid rgba(148, 163, 184, 0.22) !important;
        overflow: hidden !important;
        box-shadow: 
            0 1px 2px rgba(0, 0, 0, 0.15),
            inset 0 1px 0 rgba(255, 255, 255, 0.02) !important;
    }}

    [data-testid="stSidebar"] [data-testid="stNumberInput"] [data-testid="stNumberInputContainer"]:focus-within {{
        border-color: #3B82F6 !important;
        box-shadow: 
            0 0 0 3px rgba(59, 130, 246, 0.25),
            0 2px 8px rgba(0, 0, 0, 0.20),
            inset 0 1px 0 rgba(255, 255, 255, 0.03) !important;
        background: rgba(15, 23, 42, 0.75) !important;
    }}

    [data-testid="stSidebar"] [data-testid="stNumberInput"] button {{
        display: none !important;
    }}

    /* Sidebar Expander */
    [data-testid="stSidebar"] [data-testid="stExpander"] {{
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        border-radius: 10px !important;
        background: rgba(15, 23, 42, 0.40) !important;
        margin-top: 16px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15) !important;
        overflow: hidden !important;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] details {{
        border: none !important;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        padding: 12px 16px !important;
        font-size: 13px !important;
        color: #94A3B8 !important;
        font-weight: 500 !important;
        border: none !important;
        background: rgba(15, 23, 42, 0.30) !important;
        transition: all 150ms ease !important;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
        color: #E8ECF4 !important;
        background: rgba(15, 23, 42, 0.50) !important;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] summary:focus {{
        outline: none !important;
        box-shadow: inset 0 0 0 2px rgba(59, 130, 246, 0.5) !important;
    }}

    /* Sidebar Action Buttons: 42px height, no text truncation */
    div[class*="st-key-sb_test"] button,
    div[class*="st-key-sb_connect"] button {{
        height: 42px !important;
        min-height: 42px !important;
        font-size: 12.5px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        white-space: nowrap !important;
        text-overflow: clip !important;
        transition: all 150ms ease !important;
        padding: 0 6px !important;
        box-sizing: border-box !important;
    }}

    div[class*="st-key-sb_test"] button {{
        background: rgba(59, 130, 246, 0.08) !important;
        background-image: none !important;
        border: 1.5px solid rgba(59, 130, 246, 0.45) !important;
        color: #60A5FA !important;
        box-shadow: none !important;
    }}

    div[class*="st-key-sb_test"] button:hover {{
        background: rgba(59, 130, 246, 0.16) !important;
        border-color: #60A5FA !important;
        color: #93C5FD !important;
        transform: translateY(-1px) !important;
    }}

    div[class*="st-key-sb_connect"] button {{
        background: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important;
        background-image: linear-gradient(135deg, #3B82F6 0%, #2563EB 100%) !important;
        border: 1px solid rgba(96, 165, 250, 0.3) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.35) !important;
    }}

    div[class*="st-key-sb_connect"] button:hover {{
        background: linear-gradient(135deg, #60A5FA 0%, #3B82F6 100%) !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.45) !important;
        transform: translateY(-1px) !important;
    }}

    div[class*="st-key-sb_connect"] button:active {{
        transform: translateY(1px) scale(0.98) !important;
    }}

    div[class*="st-key-sb_disconnect"] button {{
        height: 38px !important;
        min-height: 38px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        background: rgba(239, 68, 68, 0.10) !important;
        border: 1px solid rgba(239, 68, 68, 0.35) !important;
        color: #F87171 !important;
        transition: all 150ms ease !important;
    }}

    div[class*="st-key-sb_disconnect"] button:hover {{
        background: rgba(239, 68, 68, 0.20) !important;
        border-color: rgba(239, 68, 68, 0.60) !important;
        color: #FFFFFF !important;
        transform: translateY(-1px) !important;
    }}

    /* Sidebar Status Card */
    .sidebar-status-card {{
        margin-top: 16px !important;
        margin-bottom: 14px !important;
        padding: 14px 16px !important;
        background: rgba(15, 23, 42, 0.55) !important;
        border: 1px solid rgba(148, 163, 184, 0.14) !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.20) !important;
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
    }}

    .sidebar-status-header {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13.5px;
        font-weight: 600;
    }}

    .sidebar-status-title-connected {{
        color: #22C55E;
        font-size: 13.5px;
        font-weight: 600;
    }}

    .sidebar-status-title-disconnected {{
        color: #EF4444;
        font-size: 13.5px;
        font-weight: 600;
    }}

    .sidebar-status-dot {{
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
    }}

    .sidebar-status-dot.dot-connected {{
        background: #22C55E;
        box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
        animation: pulseStatusGreen 2.5s infinite;
    }}

    .sidebar-status-dot.dot-disconnected {{
        background: #EF4444;
        box-shadow: 0 0 6px rgba(239, 68, 68, 0.4);
    }}

    .sidebar-status-chip {{
        margin-left: auto;
        font-size: 10.5px;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 4px;
        background: rgba(34, 197, 94, 0.15);
        color: #22C55E;
        border: 1px solid rgba(34, 197, 94, 0.25);
        text-transform: uppercase;
    }}

    .sidebar-status-meta {{
        font-size: 12px;
        color: #94A3B8;
        margin-top: 8px;
        line-height: 1.5;
    }}

    /* Top Bar Navigation Header */
    .app-top-header {{
        max-width: 1100px;
        width: 100%;
        margin: 0 auto 32px auto;
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 16px 24px;
        background: var(--dq-surface);
        border: 1px solid var(--dq-border);
        border-radius: var(--dq-radius-card);
        box-shadow: var(--dq-shadow);
        box-sizing: border-box;
    }}

    .app-top-brand {{
        display: flex;
        align-items: center;
        gap: 14px;
    }}

    .app-top-logo {{
        display: flex;
        align-items: center;
        justify-content: center;
        width: 40px;
        height: 40px;
        border-radius: 10px;
        background: var(--dq-surface2);
        border: 1px solid var(--dq-border);
        font-size: 1.25rem;
        flex-shrink: 0;
    }}

    .app-top-title {{
        font-size: 17px;
        font-weight: 700;
        color: var(--dq-text-primary);
        line-height: 1.2;
    }}

    .app-top-tagline {{
        font-size: 14px;
        color: var(--dq-text-secondary);
        margin-top: 2px;
    }}

    .app-top-meta {{
        display: flex;
        align-items: center;
        gap: 10px;
    }}

    .status-pill {{
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 5px 12px;
        border-radius: var(--dq-radius-pill);
        font-size: 13px;
        font-weight: 500;
    }}

    .status-pill.status-connected {{
        background: var(--dq-success-bg);
        color: var(--dq-success);
        border: 1px solid rgba(34, 197, 94, 0.28);
    }}

    .status-pill.status-disconnected {{
        background: var(--dq-danger-bg);
        color: var(--dq-danger);
        border: 1px solid rgba(239, 68, 68, 0.28);
    }}

    .status-pill-dot {{
        width: 7px;
        height: 7px;
        border-radius: 50%;
        background: currentColor;
        display: inline-block;
    }}

    .status-pill.status-connected .status-pill-dot {{
        animation: pulseStatusGreen 2.5s infinite;
    }}

    @keyframes pulseStatusGreen {{
        0% {{ opacity: 1; transform: scale(1); }}
        50% {{ opacity: 0.55; transform: scale(1.15); }}
        100% {{ opacity: 1; transform: scale(1); }}
    }}

    .version-tag {{
        font-size: 12px;
        color: var(--dq-text-secondary);
        background: var(--dq-surface2);
        border: 1px solid var(--dq-border);
        padding: 4px 10px;
        border-radius: var(--dq-radius-btn);
        font-weight: 500;
    }}

    .theme-badge {{
        font-size: 12px;
        color: var(--dq-text-secondary);
        background: var(--dq-surface2);
        border: 1px solid var(--dq-border);
        padding: 4px 10px;
        border-radius: var(--dq-radius-btn);
        font-weight: 500;
        display: inline-flex;
        align-items: center;
        gap: 4px;
    }}

    /* Hero Section (Centered, balanced spacing) */
    .hero-container {{
        max-width: 1100px;
        width: 100%;
        margin: 0 auto;
        padding: 44px 24px;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        text-align: center;
    }}

    .hero-badge-tile {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 56px;
        height: 56px;
        border-radius: 14px;
        background: var(--dq-surface);
        border: 1px solid var(--dq-border);
        box-shadow: var(--dq-shadow);
        font-size: 1.85rem;
        margin-bottom: 16px;
    }}

    .hero-headline {{
        font-size: 38px !important;
        font-weight: 700 !important;
        color: var(--dq-text-primary);
        letter-spacing: -0.025em;
        line-height: 1.15 !important;
        margin: 0 0 16px 0;
    }}

    .gradient-text {{
        background: var(--dq-accent-gradient);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        display: inline;
    }}

    .hero-subtitle {{
        font-size: 16px;
        color: var(--dq-text-secondary);
        max-width: 820px;
        margin: 0 0 24px 0;
        line-height: 1.55;
    }}

    .hero-cta-hint {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        background: var(--dq-surface2);
        border: 1px solid var(--dq-border);
        color: var(--dq-text-primary);
        padding: 8px 18px;
        border-radius: var(--dq-radius-pill);
        font-size: 13.5px;
        margin-bottom: 24px;
        box-shadow: var(--dq-shadow);
    }}

    .hero-cta-hint strong {{
        color: var(--dq-accent);
    }}

    .hero-cta-arrow {{
        font-size: 16px;
        color: var(--dq-accent);
        display: inline-block;
        animation: hintBounce 1.8s infinite ease-in-out;
    }}

    @keyframes hintBounce {{
        0%, 100% {{ transform: translateX(0); }}
        50% {{ transform: translateX(-4px); }}
    }}

    .hero-trust-row {{
        display: flex;
        align-items: center;
        justify-content: center;
        gap: 28px;
        flex-wrap: wrap;
        margin-top: 8px;
        margin-bottom: 32px;
    }}

    .trust-item {{
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13.5px;
        font-weight: 500;
        color: var(--dq-text-secondary);
    }}

    .trust-icon {{
        font-size: 15px;
    }}

    /* Feature Cards: 3 equal columns, 24px gap */
    .features-grid {{
        max-width: 1100px;
        width: 100%;
        margin: 0 auto 32px auto;
        display: grid;
        grid-template-columns: repeat(3, 1fr);
        gap: 24px;
        box-sizing: border-box;
    }}

    @media (max-width: 900px) {{
        .features-grid {{
            grid-template-columns: 1fr;
        }}
    }}

    .feature-card {{
        background: var(--dq-surface) !important;
        border: 1px solid var(--dq-border) !important;
        border-radius: var(--dq-radius-card) !important;
        padding: 24px 22px !important;
        display: flex;
        flex-direction: column;
        height: 100%;
        box-shadow: var(--dq-shadow);
        box-sizing: border-box;
        position: relative;
        overflow: hidden;
        transition: transform var(--dq-transition), border-color var(--dq-transition), box-shadow var(--dq-transition);
    }}

    .feature-top-accent {{
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: var(--dq-accent-gradient);
    }}

    .feature-card:hover {{
        transform: translateY(-4px);
        border-color: var(--dq-accent) !important;
        box-shadow: var(--dq-shadow-hover);
    }}

    .feature-icon-tile {{
        width: 44px;
        height: 44px;
        border-radius: 10px;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        font-size: 1.35rem;
        margin-bottom: 16px;
        background: var(--dq-surface2);
        border: 1px solid var(--dq-border);
    }}

    .feature-title {{
        font-size: 17px;
        font-weight: 600;
        color: var(--dq-text-primary);
        margin-bottom: 8px;
    }}

    .feature-desc {{
        font-size: 14px;
        color: var(--dq-text-secondary);
        line-height: 1.6;
        margin: 0 0 16px 0;
        flex-grow: 1;
    }}

    .feature-micro-link {{
        font-size: 13px;
        font-weight: 600;
        color: var(--dq-accent);
        display: inline-flex;
        align-items: center;
        gap: 4px;
        margin-top: auto;
    }}

    /* Steps Strip (Visual Timeline) */
    .steps-timeline-container {{
        max-width: 1100px;
        width: 100%;
        margin: 0 auto;
        padding: 20px 28px;
        background: var(--dq-surface);
        border: 1px solid var(--dq-border);
        border-radius: var(--dq-radius-card);
        box-shadow: var(--dq-shadow);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 16px;
        box-sizing: border-box;
    }}

    @media (max-width: 900px) {{
        .steps-timeline-container {{
            flex-direction: column;
            align-items: flex-start;
            gap: 16px;
        }}
        .step-arrow {{
            display: none !important;
        }}
    }}

    .step-card {{
        display: flex;
        align-items: center;
        gap: 14px;
        flex: 1;
    }}

    .step-number {{
        width: 36px;
        height: 36px;
        border-radius: 50%;
        background: var(--dq-surface2);
        border: 1.5px solid var(--dq-accent);
        color: var(--dq-accent);
        font-size: 15px;
        font-weight: 700;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }}

    .step-content {{
        display: flex;
        flex-direction: column;
    }}

    .step-title {{
        font-size: 14px;
        font-weight: 600;
        color: var(--dq-text-primary);
    }}

    .step-desc {{
        font-size: 13px;
        color: var(--dq-text-secondary);
        margin-top: 2px;
    }}

    .step-arrow {{
        color: var(--dq-text-muted);
        font-size: 18px;
        font-weight: 600;
        display: flex;
        align-items: center;
        justify-content: center;
        padding: 0 4px;
    }}

    /* Footer line */
    .app-footer-line {{
        max-width: 1100px;
        width: 100%;
        margin: 36px auto 16px auto;
        text-align: center;
        font-size: 13px;
        color: var(--dq-text-muted);
        letter-spacing: 0.02em;
        box-sizing: border-box;
    }}

    /* Global Streamlit Widgets Styling */
    div[data-testid="stAlert"] {{
        background: var(--dq-surface) !important;
        border: 1px solid var(--dq-border) !important;
        border-radius: var(--dq-radius-btn) !important;
        color: var(--dq-text-primary) !important;
        box-shadow: var(--dq-shadow) !important;
    }}

    [data-testid="stToast"] {{
        background: var(--dq-surface) !important;
        border: 1px solid var(--dq-border) !important;
        color: var(--dq-text-primary) !important;
        border-radius: var(--dq-radius-btn) !important;
        box-shadow: var(--dq-shadow-hover) !important;
    }}

    [data-testid="stSpinner"] {{
        color: var(--dq-accent) !important;
    }}

    [data-testid="stDataFrame"] {{
        background: var(--dq-surface) !important;
        border: 1px solid var(--dq-border) !important;
        border-radius: var(--dq-radius-btn) !important;
    }}

    div[data-testid="stModal"] > div:first-child,
    div[role="dialog"] {{
        border-radius: var(--dq-radius-card) !important;
        border: 1px solid var(--dq-border) !important;
        background: var(--dq-surface) !important;
    }}

    /* ============================================================
       Professional Alert Modal System (Custom)
       ============================================================ */
    .dq-alert-overlay {{
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        width: 100vw !important;
        height: 100vh !important;
        background: rgba(0, 0, 0, 0.55) !important;
        backdrop-filter: blur(6px) !important;
        -webkit-backdrop-filter: blur(6px) !important;
        z-index: 99999 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 24px !important;
        box-sizing: border-box !important;
        animation: dqAlertFadeIn 200ms cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
    }}

    .dq-alert-modal {{
        background: var(--dq-surface) !important;
        border: 1px solid var(--dq-border) !important;
        border-radius: 16px !important;
        box-shadow: 
            0 24px 48px rgba(0, 0, 0, 0.25),
            0 0 0 1px rgba(255, 255, 255, 0.05) inset !important;
        max-width: 440px !important;
        width: 100% !important;
        overflow: hidden !important;
        animation: dqAlertSlideUp 300ms cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
        transform-origin: center center !important;
    }}

    @supports (backdrop-filter: blur(1px)) {{
        .dq-alert-modal {{
            backdrop-filter: blur(24px) saturate(160%) !important;
            -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
        }}
    }}

    .dq-alert-header {{
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        padding: 20px 24px 12px 24px !important;
        border-bottom: 1px solid var(--dq-border) !important;
    }}

    .dq-alert-icon {{
        flex-shrink: 0 !important;
        width: 40px !important;
        height: 40px !important;
        border-radius: 10px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        font-size: 18px !important;
    }}

    .dq-alert-icon.error {{
        background: rgba(185, 28, 28, 0.12) !important;
        color: #B91C1C !important;
        border: 1px solid rgba(185, 28, 28, 0.25) !important;
    }}

    .dq-alert-icon.warning {{
        background: rgba(180, 83, 9, 0.12) !important;
        color: #B45309 !important;
        border: 1px solid rgba(180, 83, 9, 0.25) !important;
    }}

    .dq-alert-icon.info {{
        background: rgba(30, 58, 138, 0.12) !important;
        color: #1E3A8A !important;
        border: 1px solid rgba(30, 58, 138, 0.25) !important;
    }}

    .dq-alert-icon.success {{
        background: rgba(21, 128, 61, 0.12) !important;
        color: #15803D !important;
        border: 1px solid rgba(21, 128, 61, 0.25) !important;
    }}

    .dq-alert-title {{
        font-size: 16px !important;
        font-weight: 600 !important;
        color: var(--dq-text-primary) !important;
        line-height: 1.3 !important;
        margin: 0 !important;
        flex: 1 !important;
    }}

    .dq-alert-close {{
        flex-shrink: 0 !important;
        width: 32px !important;
        height: 32px !important;
        border-radius: 8px !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        background: transparent !important;
        border: none !important;
        color: var(--dq-text-muted) !important;
        cursor: pointer !important;
        transition: all 150ms ease !important;
        font-size: 18px !important;
        line-height: 1 !important;
    }}

    .dq-alert-close:hover {{
        background: var(--dq-bg-soft) !important;
        color: var(--dq-text-primary) !important;
    }}

    .dq-alert-body {{
        padding: 20px 24px !important;
    }}

    .dq-alert-message {{
        font-size: 14px !important;
        color: var(--dq-text-secondary) !important;
        line-height: 1.6 !important;
        margin: 0 !important;
    }}

    .dq-alert-message strong {{
        color: var(--dq-text-primary) !important;
        font-weight: 600 !important;
    }}

    .dq-alert-actions {{
        display: flex !important;
        justify-content: flex-end !important;
        gap: 10px !important;
        padding: 16px 24px 20px 24px !important;
        border-top: 1px solid var(--dq-border) !important;
        background: var(--dq-bg-soft) !important;
    }}

    .dq-alert-btn {{
        min-width: 96px !important;
        height: 40px !important;
        border-radius: 10px !important;
        font-size: 13.5px !important;
        font-weight: 600 !important;
        cursor: pointer !important;
        transition: all 150ms ease !important;
        border: none !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
    }}

    .dq-alert-btn.primary {{
        background: linear-gradient(135deg, #1E293B 0%, #0F172A 100%) !important;
        color: #FFFFFF !important;
        box-shadow: 0 2px 8px rgba(15, 23, 42, 0.3) !important;
    }}

    .dq-alert-btn.primary:hover {{
        filter: brightness(1.1) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.4) !important;
    }}

    .dq-alert-btn.secondary {{
        background: var(--dq-surface) !important;
        color: var(--dq-text-primary) !important;
        border: 1px solid var(--dq-border) !important;
    }}

    .dq-alert-btn.secondary:hover {{
        background: var(--dq-bg-soft) !important;
        border-color: var(--dq-border-hover) !important;
    }}

    @keyframes dqAlertFadeIn {{
        from {{
            opacity: 0 !important;
        }}
        to {{
            opacity: 1 !important;
        }}
    }}

    @keyframes dqAlertSlideUp {{
        from {{
            opacity: 0 !important;
            transform: scale(0.94) translateY(16px) !important;
        }}
        to {{
            opacity: 1 !important;
            transform: scale(1) translateY(0) !important;
        }}
    }}

    @keyframes dqAlertSlideDown {{
        from {{
            opacity: 1 !important;
            transform: scale(1) translateY(0) !important;
        }}
        to {{
            opacity: 0 !important;
            transform: scale(0.94) translateY(16px) !important;
        }}
    }}

    .dq-alert-modal.closing {{
        animation: dqAlertSlideDown 200ms cubic-bezier(0.4, 0, 0.6, 1) forwards !important;
    }}

    .dq-alert-overlay.closing {{
        animation: dqAlertFadeIn 200ms cubic-bezier(0.4, 0, 0.6, 1) reverse forwards !important;
    }}

    /* Reduced motion */
    @media (prefers-reduced-motion: reduce) {{
        .dq-alert-overlay,
        .dq-alert-modal {{
            animation: none !important;
        }}
    }}

    /* Normal (#2563EB) vs Destructive (#DC2626) Action Buttons */
    button[kind="secondary"],
    button[data-testid="stBaseButton-secondary"],
    .stButton > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]):not([class*="sb_test"]):not([class*="sb_connect"]),
    div[class*="st-key-hub_open_"] button,
    div[class*="st-key-open_ws_btn"] button {{
        background-color: #2563EB !important;
        background-image: linear-gradient(180deg, #3B82F6 0%, #2563EB 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid #1D4ED8 !important;
        border-radius: var(--dq-radius-btn) !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 6px rgba(37, 99, 235, 0.25) !important;
        transition: all var(--dq-transition) !important;
    }}

    button[kind="secondary"]:hover,
    button[data-testid="stBaseButton-secondary"]:hover,
    .stButton > button:not([kind="primary"]):not([data-testid="stBaseButton-primary"]):not([class*="sb_test"]):not([class*="sb_connect"]):hover,
    div[class*="st-key-hub_open_"] button:hover,
    div[class*="st-key-open_ws_btn"] button:hover {{
        background-color: #1D4ED8 !important;
        background-image: linear-gradient(180deg, #2563EB 0%, #1D4ED8 100%) !important;
        border-color: #1E40AF !important;
        transform: translateY(-1px) !important;
    }}

    button[kind="primary"],
    button[data-testid="stBaseButton-primary"],
    div[class*="st-key-hub_drop_"] button,
    div[class*="st-key-drop_sb_btn"] button,
    div[class*="st-key-disc_btn"] button {{
        background-color: #DC2626 !important;
        background-image: linear-gradient(180deg, #EF4444 0%, #DC2626 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid #B91C1C !important;
        border-radius: var(--dq-radius-btn) !important;
        font-weight: 600 !important;
        box-shadow: 0 2px 6px rgba(220, 38, 38, 0.25) !important;
        transition: all var(--dq-transition) !important;
    }}

    button[kind="primary"]:hover,
    button[data-testid="stBaseButton-primary"]:hover,
    div[class*="st-key-hub_drop_"] button:hover,
    div[class*="st-key-drop_sb_btn"] button:hover,
    div[class*="st-key-disc_btn"] button:hover {{
        background-color: #B91C1C !important;
        background-image: linear-gradient(180deg, #DC2626 0%, #B91C1C 100%) !important;
        border-color: #991B1B !important;
        transform: translateY(-1px) !important;
    }}

    /* KPI Cards in Data Profiling Dialog */
    .kpi-card {{
        background: var(--dq-surface);
        border: 1px solid var(--dq-border);
        border-radius: var(--dq-radius-card);
        padding: 1rem 1.25rem;
        box-shadow: var(--dq-shadow);
        position: relative;
        overflow: hidden;
    }}

    .kpi-card::before {{
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 4px;
        height: 100%;
        background: var(--dq-accent);
    }}

    .kpi-card-success::before {{ background: var(--dq-success); }}
    .kpi-card-warning::before {{ background: var(--dq-warning); }}
    .kpi-card-danger::before {{ background: var(--dq-danger); }}

    .kpi-label {{
        font-size: 12px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        color: var(--dq-text-secondary) !important;
        margin-bottom: 4px;
    }}

    .kpi-value {{
        font-size: 1.85rem;
        font-weight: 800;
        color: var(--dq-text-primary) !important;
        line-height: 1.15;
    }}

    .kpi-subtext {{
        font-size: 13px;
        color: var(--dq-text-muted) !important;
        margin-top: 4px;
    }}

    /* Data Quality Health Dial */
    .health-score-container {{
        display: flex;
        align-items: center;
        gap: 20px;
        background: var(--dq-surface);
        border: 1px solid var(--dq-border);
        border-radius: var(--dq-radius-card);
        padding: 20px 24px;
        margin-bottom: 20px;
        box-shadow: var(--dq-shadow);
    }}

    .health-score-dial {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        width: 95px;
        height: 95px;
        border-radius: 50%;
        background: var(--dq-surface2);
        box-shadow: var(--dq-shadow);
        border: 4px solid var(--dq-accent);
        flex-shrink: 0;
    }}

    .health-score-number {{
        font-size: 1.75rem;
        font-weight: 800;
        line-height: 1;
        color: var(--dq-text-primary);
    }}

    .health-score-pct {{
        font-size: 12px;
        font-weight: 700;
        color: var(--dq-text-muted) !important;
    }}

    /* ── Generic radio (non-workspace) — minimal pill bar ───────── */
    div[data-testid="stRadio"] > div {{
        display: flex !important;
        flex-direction: row !important;
        flex-wrap: wrap !important;
        gap: 4px !important;
        background: var(--dq-surface) !important;
        border: 1px solid var(--dq-border) !important;
        border-radius: 10px !important;
        padding: 4px !important;
        width: 100% !important;
    }}

    div[data-testid="stRadio"] label {{
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        flex: 1 !important;
        min-width: 80px !important;
        padding: 7px 12px !important;
        border-radius: var(--dq-radius-btn) !important;
        cursor: pointer !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: var(--dq-text-secondary) !important;
        white-space: nowrap !important;
        transition: background 150ms ease, color 150ms ease, border-color 150ms ease !important;
        margin: 0 !important;
        background: transparent !important;
        border: 1px solid transparent !important;
    }}

    div[data-testid="stRadio"] label > div:first-child {{
        display: none !important;
    }}

    div[data-testid="stRadio"] label:hover {{
        background: var(--dq-accent-glow) !important;
        color: var(--dq-accent) !important;
        border-color: var(--dq-accent-border) !important;
    }}

    div[data-testid="stRadio"] label:has(input[type="radio"]:checked) {{
        background: var(--dq-accent) !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        box-shadow: 0 2px 8px rgba(0,0,0,0.22) !important;
        border-color: var(--dq-accent) !important;
    }}

    /* ═══════════════════════════════════════════════════════════════
       MAIN NAVIGATION REDESIGN — Scoped to div.st-key-_main_nav_radio
       =============================================================== */
    .main-nav-header {{
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        margin-top: 14px !important;
        margin-bottom: 12px !important;
    }}
    .main-nav-accent-bar {{
        width: 3.5px !important;
        height: 32px !important;
        background: #0F766E !important;
        border-radius: 3px !important;
        flex-shrink: 0 !important;
    }}
    .main-nav-title {{
        font-size: 15.5px !important;
        font-weight: 700 !important;
        color: var(--dq-text-primary) !important;
        margin: 0 !important;
        line-height: 1.2 !important;
        letter-spacing: -0.01em !important;
    }}
    .main-nav-subtitle {{
        font-size: 12.5px !important;
        color: var(--dq-text-secondary) !important;
        margin: 3px 0 0 0 !important;
        line-height: 1.3 !important;
    }}
    div.st-key-_main_nav_radio {{
        background: #F1F5F9 !important;
        background: linear-gradient(180deg, #F8FAFC 0%, #EEF2F6 100%) !important;
        border: 1px solid var(--dq-border) !important;
        border-radius: 16px !important;
        padding: 10px !important;
        margin-bottom: 22px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
        box-sizing: border-box !important;
        width: 100% !important;
    }}

    /* Completely hide Streamlit's internal widget label so 'Main Navigation' is never a card inside the box */
    div.st-key-_main_nav_radio [data-testid="stWidgetLabel"],
    div.st-key-_main_nav_radio > label,
    div.st-key-_main_nav_radio label[data-testid="stWidgetLabel"] {{
        display: none !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        opacity: 0 !important;
        visibility: hidden !important;
        pointer-events: none !important;
        border: none !important;
        box-shadow: none !important;
    }}

    /* Inner 2-column grid container */
    div.st-key-_main_nav_radio div[role="radiogroup"] {{
        display: grid !important;
        grid-template-columns: 1fr 1fr !important;
        gap: 12px !important;
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }}

    /* Base Option Card (label) */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] {{
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: flex-start !important;
        flex: unset !important;
        min-width: unset !important;
        width: 100% !important;
        padding: 16px 20px !important;
        border-radius: 12px !important;
        border: 1px solid var(--dq-border) !important;
        background: var(--dq-surface2) !important;
        cursor: pointer !important;
        min-height: 82px !important;
        gap: 14px !important;
        position: relative !important;
        box-sizing: border-box !important;
        user-select: none !important;
        transition: all 180ms cubic-bezier(0.4, 0, 0.2, 1) !important;
    }}

    /* Hide native radio input/circle container */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label > div:first-child,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] > div:first-child {{
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        opacity: 0 !important;
        visibility: hidden !important;
        margin: 0 !important;
        padding: 0 !important;
    }}

    /* Text Container */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label > div[data-testid="stMarkdownContainer"],
    div.st-key-_main_nav_radio label[data-baseweb="radio"] > div[data-testid="stMarkdownContainer"] {{
        order: 2 !important;
        flex: 1 1 auto !important;
        min-width: 0 !important;
        text-align: left !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label > div[data-testid="stMarkdownContainer"] p,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] > div[data-testid="stMarkdownContainer"] p {{
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.35 !important;
        color: var(--dq-text-secondary) !important;
        font-size: 12.5px !important;
        font-weight: 400 !important;
        text-align: left !important;
        white-space: normal !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label > div[data-testid="stMarkdownContainer"] strong,
    div.st-key-_main_nav_radio label[data-baseweb="radio"] > div[data-testid="stMarkdownContainer"] strong {{
        display: block !important;
        font-size: 15px !important;
        font-weight: 700 !important;
        color: var(--dq-text-primary) !important;
        letter-spacing: -0.01em !important;
        margin-bottom: 2px !important;
        line-height: 1.25 !important;
    }}

    /* Icon Containers via ::before (order: 1, on the left) */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label::before,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]::before {{
        content: "" !important;
        order: 1 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        width: 44px !important;
        height: 44px !important;
        min-width: 44px !important;
        border-radius: 10px !important;
        flex-shrink: 0 !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: 22px 22px !important;
        transition: all 180ms ease !important;
    }}

    /* Option 1: Source Table Icon (Teal tinted badge) */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label:nth-of-type(1)::before,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:nth-of-type(1)::before {{
        background-color: rgba(15, 118, 110, 0.10) !important;
        border: 1px solid rgba(15, 118, 110, 0.22) !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%230F766E' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cellipse cx='12' cy='5' rx='9' ry='3'/%3E%3Cpath d='M3 5V19A9 3 0 0 0 21 19V5'/%3E%3Cpath d='M3 12A9 3 0 0 0 21 12'/%3E%3C/svg%3E") !important;
    }}

    /* Option 2: Cleaning Workspace Icon (Warm amber tinted badge) */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label:nth-of-type(2)::before,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:nth-of-type(2)::before {{
        background-color: rgba(217, 119, 6, 0.12) !important;
        border: 1px solid rgba(217, 119, 6, 0.26) !important;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='24' height='24' viewBox='0 0 24 24' fill='none' stroke='%23D97706' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='m18 2 4 4'/%3E%3Cpath d='m15 5 4 4'/%3E%3Cpath d='M13 7 4 16l-1 5 5-1L17 11'/%3E%3Cpath d='M14 14.5a3.5 3.5 0 0 0-5 0'/%3E%3C/svg%3E") !important;
    }}

    /* Custom Radio Selection Indicator via ::after (order: 3, on the right) */
    div.st-key-_main_nav_radio div[role="radiogroup"] > label::after,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]::after {{
        content: "" !important;
        order: 3 !important;
        margin-left: auto !important;
        width: 20px !important;
        height: 20px !important;
        min-width: 20px !important;
        border-radius: 50% !important;
        border: 2px solid var(--dq-border) !important;
        background: #FFFFFF !important;
        box-sizing: border-box !important;
        flex-shrink: 0 !important;
        transition: all 180ms ease !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:not(:has(input:checked)):hover,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:not(:has(input:checked)):hover {{
        background: var(--dq-surface) !important;
        border-color: var(--dq-accent-border) !important;
        transform: translateY(-1.5px) !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.08) !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:not(:has(input:checked)):hover::after,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:not(:has(input:checked)):hover::after {{
        border-color: #0F766E !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input[type="radio"]:checked),
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input[type="radio"]:checked) {{
        background: #FFFFFF !important;
        background: linear-gradient(135deg, #FFFFFF 0%, #F0FDFA 100%) !important;
        border: 1.8px solid #0F766E !important;
        border-bottom: 1.8px solid #0F766E !important;
        box-shadow: 0 4px 16px rgba(15, 118, 110, 0.12), 0 1px 3px rgba(0, 0, 0, 0.04) !important;
        transform: translateY(-1px) !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input[type="radio"]:checked)::after,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input[type="radio"]:checked)::after {{
        border-color: #0F766E !important;
        background: #0F766E !important;
        box-shadow: inset 0 0 0 3.5px #FFFFFF, 0 0 0 3px rgba(15, 118, 110, 0.20) !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input[type="radio"]:checked) > div[data-testid="stMarkdownContainer"] strong,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input[type="radio"]:checked) > div[data-testid="stMarkdownContainer"] strong {{
        color: var(--dq-text-primary) !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input[type="radio"]:checked) > div[data-testid="stMarkdownContainer"] p,
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input[type="radio"]:checked) > div[data-testid="stMarkdownContainer"] p {{
        color: var(--dq-text-secondary) !important;
    }}

    div.st-key-_main_nav_radio div[role="radiogroup"] > label:has(input:focus-visible),
    div.st-key-_main_nav_radio label[data-baseweb="radio"]:has(input:focus-visible) {{
        outline: 2px solid #0F766E !important;
        outline-offset: 2px !important;
    }}

    @media (max-width: 900px) {{
        div.st-key-_main_nav_radio div[role="radiogroup"] > label,
        div.st-key-_main_nav_radio label[data-baseweb="radio"] {{
            padding: 14px 16px !important;
            gap: 12px !important;
            min-height: 76px !important;
        }}
        div.st-key-_main_nav_radio div[role="radiogroup"] > label::before,
        div.st-key-_main_nav_radio label[data-baseweb="radio"]::before {{
            width: 38px !important;
            height: 38px !important;
            min-width: 38px !important;
            background-size: 20px 20px !important;
        }}
        div.st-key-_main_nav_radio div[role="radiogroup"] > label > div[data-testid="stMarkdownContainer"] strong,
        div.st-key-_main_nav_radio label[data-baseweb="radio"] > div[data-testid="stMarkdownContainer"] strong {{
            font-size: 14px !important;
        }}
        div.st-key-_main_nav_radio div[role="radiogroup"] > label > div[data-testid="stMarkdownContainer"] p,
        div.st-key-_main_nav_radio label[data-baseweb="radio"] > div[data-testid="stMarkdownContainer"] p {{
            font-size: 12px !important;
        }}
    }}

    @media (max-width: 680px) {{
        div.st-key-_main_nav_radio div[role="radiogroup"] {{
            grid-template-columns: 1fr !important;
            gap: 8px !important;
        }}
        div.st-key-_main_nav_radio div[role="radiogroup"] > label,
        div.st-key-_main_nav_radio label[data-baseweb="radio"] {{
            padding: 14px 16px !important;
            min-height: 72px !important;
        }}
    }}

    /* ═══════════════════════════════════════════════════════════════
       WORKSPACE SUB-TAB BAR  — scoped to key "_ws_sub_radio"
       Primary card styling is dynamically managed by ui.cleaning_tabs
    ═══════════════════════════════════════════════════════════════ */

    /* Outer wrapper: transparent, no card strip or blank box */
    div.st-key-_ws_sub_radio {{
        background: transparent !important;
        border: none !important;
        border-radius: 0 !important;
        padding: 0 !important;
        margin: 0 0 20px 0 !important;
        box-shadow: none !important;
        width: 100% !important;
        position: relative !important;
    }}

    /* Completely hide the widget label strip */
    div.st-key-_ws_sub_radio [data-testid="stWidgetLabel"],
    div.st-key-_ws_sub_radio label[data-testid="stWidgetLabel"],
    div.st-key-_ws_sub_radio > div[data-testid="stRadio"] > label:first-child:not([data-baseweb="radio"]) {{
        display: none !important;
        height: 0 !important;
        min-height: 0 !important;
        max-height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        line-height: 0 !important;
        font-size: 0 !important;
        visibility: hidden !important;
        overflow: hidden !important;
        border: none !important;
    }}

    div.st-key-_ws_sub_radio > div[data-testid="stRadio"] {{
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        background: transparent !important;
    }}

    @media (prefers-reduced-motion: reduce) {{
        *, *::before, *::after {{
            animation-duration: 0.01ms !important;
            animation-iteration-count: 1 !important;
            transition-duration: 0.01ms !important;
        }}
        .page-fade-in {{
            animation: none !important;
        }}
        .hero-cta-arrow {{
            animation: none !important;
        }}
        .sidebar-status-dot.dot-connected,
        .status-pill.status-connected .status-pill-dot {{
            animation: none !important;
        }}
    }}

    /* Align Host and Port inputs side‑by‑side in the sidebar */
    [data-testid="stSidebar"] .stColumn > div {{
        display: flex;
        flex-direction: column;
    }}
    [data-testid="stSidebar"] [data-testid="stNumberInput"] {{
        margin-top: 0 !important;
    }}
    [data-testid="stSidebar"] [data-testid="stNumberInput"] > div {{
        margin-top: 0 !important;
    }}

    /* Floating theme toggle button (top‑right) */
    div.st-key-floating_theme_toggle {{
        position: fixed !important;
        top: 1rem !important;
        right: 1rem !important;
        z-index: 9999 !important;
    }}
    div.st-key-floating_theme_toggle button {{
        height: 44px !important;
        border-radius: 9999px !important;
        background: var(--dq-surface) !important;
        border: 1px solid var(--dq-border) !important;
        color: var(--dq-text-primary) !important;
        font-size: 0.9rem !important;
        font-weight: 600 !important;
        box-shadow: var(--dq-shadow) !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 0.5rem !important;
        padding: 0 1rem !important;
        white-space: nowrap !important;
    }}
    div.st-key-floating_theme_toggle button:hover {{
        background: var(--dq-accent-glow) !important;
        border-color: var(--dq-accent) !important;
        color: var(--dq-accent) !important;
    }}

    /* Glassmorphism Sidebar Redesign - Black Theme */
    /* Overall sidebar inner padding */
    [data-testid="stSidebar"] > div:first-child {{
        padding: 28px 22px 32px 22px !important;
    }}

    /* Branding block */
    .sidebar-brand-block {{
        display:flex; align-items:center; gap:14px; padding-bottom:18px; margin-bottom:22px;
        border-bottom:1px solid rgba(255,255,255,0.08);
    }}
    .sidebar-brand-icon {{
        width:46px; height:46px; border-radius:12px;
        background: linear-gradient(135deg, rgba(30,30,30,0.30), rgba(60,60,60,0.18));
        border:1px solid rgba(255,255,255,0.15);
        display:flex; align-items:center; justify-content:center; font-size:1.5rem;
        box-shadow: 0 2px 10px rgba(0,0,0,0.25);
    }}
    .sidebar-brand-title {{ font-size:16px; font-weight:700; color:var(--dq-text-primary); letter-spacing:-0.01em; }}
    .sidebar-brand-sub {{ font-size:12px; color:var(--dq-text-secondary); margin-top:2px; }}

    /* Section header */
    .sidebar-section-header {{
        font-size:11px !important; font-weight:600 !important; text-transform:uppercase;
        letter-spacing:0.08em; color:var(--dq-text-muted) !important;
        margin-top:26px !important; margin-bottom:12px !important;
    }}

    /* Database Connection panel glass */
    .db-conn-panel {{
        background: rgba(20, 20, 20, 0.55) !important;
        backdrop-filter: blur(14px) !important;
        -webkit-backdrop-filter: blur(14px) !important;
        border:1px solid rgba(255,255,255,0.10) !important;
        border-radius:16px !important;
        padding:20px 20px 16px 20px !important;
        margin-top:8px !important;
        box-shadow: 0 8px 24px rgba(0,0,0,0.18), inset 0 0 0 1px rgba(255,255,255,0.04) !important;
    }}
    .db-conn-title {{ font-size:14px; font-weight:700; color:var(--dq-text-primary); margin-bottom:4px; }}
    .db-conn-desc {{ font-size:11px; color:var(--dq-text-muted); margin-bottom:18px; }}

    /* Form layout: Host & Port on same row */
    .db-conn-row {{
        display:flex; gap:12px; margin-bottom:14px;
    }}
    .db-conn-row > div {{
        flex:1;
    }}
    .db-conn-row .port-field {{ flex:0 0 90px; }}

    /* Inputs */
    [data-testid="stSidebar"] [data-testid="stTextInput"] input,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input {{
        height:44px !important;
        background: rgba(30, 30, 30, 0.60) !important;
        border:1px solid rgba(255,255,255,0.15) !important;
        border-radius:10px !important;
        color:var(--dq-text-primary) !important;
        font-size:13px !important;
        padding:0 14px !important;
        transition: border-color .2s, box-shadow .2s, background .2s !important;
    }}
    [data-testid="stSidebar"] [data-testid="stTextInput"] input:focus,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input:focus {{
        border-color: #444 !important;
        box-shadow: 0 0 0 3px rgba(0,0,0,0.40) !important;
        background: rgba(30, 30, 30, 0.80) !important;
        outline:none !important;
    }}
    [data-testid="stSidebar"] label p {{
        font-size:12px !important; font-weight:500 !important; color:var(--dq-text-secondary) !important;
        margin-bottom:4px !important;
    }}

    /* Advanced options expander */
    [data-testid="stSidebar"] [data-testid="stExpander"] {{
        background: transparent !important;
        border:none !important;
        box-shadow:none !important;
        margin-top:10px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        background: rgba(20,20,20,0.45) !important;
        border:1px solid rgba(255,255,255,0.08) !important;
        border-radius:10px !important;
        padding:10px 14px !important;
        font-size:12px !important; font-weight:600 !important;
        color:var(--dq-text-secondary) !important;
        cursor:pointer;
    }}
    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
        color:var(--dq-text-primary) !important;
        border-color: rgba(255,255,255,0.30) !important;
    }}

    /* Buttons */
    [data-testid="stSidebar"] .stButton > button {{
        height:44px !important; border-radius:10px !important;
        font-size:13px !important; font-weight:600 !important;
        transition: all .2s !important;
        width:100% !important;
    }}
    /* Test button - outlined */
    [data-testid="stSidebar"] .stButton > button[key*="test"] {{
        background: transparent !important; border:1.5px solid #444 !important;
        color:#888 !important; box-shadow:none !important;
    }}
    [data-testid="stSidebar"] .stButton > button[key*="test"]:hover {{
        background: rgba(255,255,255,0.05) !important; color:#aaa !important;
    }}
    /* Connect button - primary gradient (black) */
    [data-testid="stSidebar"] .stButton > button[key*="connect"] {{
        background: linear-gradient(135deg, #111 0%, #333 100%) !important;
        border:none !important; color:#fff !important;
        box-shadow: 0 4px 16px rgba(0,0,0,0.40) !important;
    }}
    [data-testid="stSidebar"] .stButton > button[key*="connect"]:hover {{
        filter: brightness(1.05) !important; box-shadow: 0 6px 22px rgba(0,0,0,0.50) !important;
    }}

    /* Status panel glass */
    .sidebar-status-card {{
        background: rgba(0, 0, 0, 0.70) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border:1px solid rgba(255,255,255,0.08) !important;
        border-radius:14px !important;
        padding:16px 18px !important;
        margin-top:22px !important;
        box-shadow: 0 6px 20px rgba(0,0,0,0.22) !important;
    }}
    .sidebar-status-header {{ display:flex; align-items:center; gap:10px; }}
    .sidebar-status-dot {{
        width:10px; height:10px; border-radius:50%; display:inline-block;
    }}
    .sidebar-status-dot.dot-connected {{ background:#22C55E; box-shadow:0 0 10px #22C55E; }}
    .sidebar-status-dot.dot-disconnected {{ background:#EF4444; box-shadow:0 0 10px #EF4444; }}
    .sidebar-status-title-connected {{ font-weight:600; color:var(--dq-text-primary); }}
    .sidebar-status-title-disconnected {{ font-weight:600; color:var(--dq-text-primary); }}
    .sidebar-status-meta {{ font-size:11px; color:var(--dq-text-muted); margin-top:6px; line-height:1.5; }}

    /* Dark mode toggle */
    [data-testid="stSidebar"] [data-testid="stToggle"] {{
        background: rgba(30,30,30,0.45) !important;
        border:1px solid rgba(255,255,255,0.10) !important;
        border-radius:10px !important;
        padding:8px 14px !important;
        margin-top:18px !important;
    }}
    [data-testid="stSidebar"] [data-testid="stToggle"] label {{ color:var(--dq-text-secondary) !important; font-size:12px !important; }}
    [data-testid="stSidebar"] [data-testid="stToggle"]:has(input:checked) {{
        border-color: #444 !important;
        background: rgba(255,255,255,0.05) !important;
    }}

    /* Remove default vertical block borders */
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
    }}

    /* ── Section typography helpers ──────────────────────────────── */
    .dq-eyebrow {{
        font-size: 11px !important;
        font-weight: 600 !important;
        text-transform: uppercase !important;
        letter-spacing: 0.08em !important;
        color: var(--dq-text-muted) !important;
        margin-bottom: 6px !important;
    }}
    .dq-section-title {{
        font-size: 1.05rem !important;
        font-weight: 700 !important;
        color: var(--dq-text-primary) !important;
        letter-spacing: -0.01em !important;
        margin-bottom: 4px !important;
        line-height: 1.3 !important;
    }}
    .dq-section-caption {{
        font-size: 0.85rem !important;
        color: var(--dq-text-muted) !important;
        margin-bottom: 14px !important;
        line-height: 1.5 !important;
    }}

    /* ── Badge / pill labels ──────────────────────────────────────── */
    .badge-pill {{
        display: inline-flex;
        align-items: center;
        gap: 4px;
        padding: 2px 10px;
        border-radius: 9999px;
        font-size: 11px;
        font-weight: 600;
        line-height: 1.6;
        white-space: nowrap;
    }}
    .badge-info {{
        background: var(--dq-accent-glow);
        color: var(--dq-accent);
        border: 1px solid var(--dq-accent-border);
    }}
    .badge-warning {{
        background: var(--dq-warning-bg);
        color: var(--dq-warning);
        border: 1px solid var(--dq-warning-border);
    }}
    .badge-success {{
        background: var(--dq-success-bg);
        color: var(--dq-success);
        border: 1px solid var(--dq-success-border);
    }}
    .badge-neutral {{
        background: var(--dq-bg-soft);
        color: var(--dq-slate);
        border: 1px solid var(--dq-border);
    }}

    /* ── Empty-state card ─────────────────────────────────────────── */
    .empty-state-card {{
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        gap: 10px;
        padding: 40px 24px;
        border-radius: var(--dq-radius-card);
        border: 1.5px dashed var(--dq-border);
        background: var(--dq-bg-soft);
        text-align: center;
        margin: 16px 0;
    }}
    .es-title {{
        font-size: 1rem;
        font-weight: 700;
        color: var(--dq-text-primary);
    }}
    .es-desc {{
        font-size: 0.85rem;
        color: var(--dq-text-muted);
        max-width: 380px;
        line-height: 1.55;
    }}

    /* ── Breadcrumb navigation bar ────────────────────────────────── */
    .breadcrumb-nav {{
        width: 100%;
        margin: 4px 0 16px 0;
        display: block;
    }}
    .breadcrumb-bar {{
        display: inline-flex;
        align-items: center;
        flex-wrap: wrap;
        gap: 4px;
        padding: 6px 12px;
        background: #F8FAFD;
        border: 1px solid #DCE5F0;
        border-radius: 12px;
        box-shadow: 0 1px 3px rgba(37, 99, 235, 0.04), 0 1px 2px rgba(15, 23, 42, 0.03);
        font-family: inherit;
        box-sizing: border-box;
        max-width: 100%;
        line-height: 1;
    }}
    .bc-item {{
        display: inline-flex;
        align-items: center;
        gap: 8px;
        padding: 4px 10px 4px 6px;
        font-size: 13px;
        font-weight: 500;
        color: #172B4D;
        text-decoration: none !important;
        border-radius: 8px;
        border: 1px solid transparent;
        transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease, box-shadow 150ms ease;
        white-space: nowrap;
        user-select: none;
        vertical-align: middle;
    }}
    a.bc-item {{
        cursor: pointer;
    }}
    a.bc-item:hover {{
        background: #EDF4FE !important;
        color: #2563EB !important;
        border-color: rgba(37, 99, 235, 0.15) !important;
        text-decoration: none !important;
    }}
    a.bc-item:focus-visible {{
        outline: 2px solid #2563EB;
        outline-offset: 1px;
    }}
    .bc-item.active {{
        background: #E6F7EF !important;
        color: #0B6E3A !important;
        font-weight: 600 !important;
        border: 1px solid rgba(16, 185, 129, 0.28) !important;
        padding: 4px 12px 4px 6px;
        cursor: default;
    }}
    .bc-icon {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 26px;
        height: 26px;
        border-radius: 6px;
        flex-shrink: 0;
        transition: background-color 150ms ease, color 150ms ease, border-color 150ms ease;
    }}
    .bc-icon svg {{
        display: block;
        width: 14px;
        height: 14px;
        pointer-events: none;
    }}
    .bc-icon.home,
    .bc-icon.folder {{
        background: #EBF3FE;
        color: #2563EB;
        border: 1px solid rgba(37, 99, 235, 0.12);
    }}
    a.bc-item:hover .bc-icon.home,
    a.bc-item:hover .bc-icon.folder {{
        background: #DFEDFE;
        color: #1D4ED8;
        border-color: rgba(37, 99, 235, 0.25);
    }}
    .bc-icon.document {{
        background: #EBF3FE;
        color: #2563EB;
        border: 1px solid rgba(37, 99, 235, 0.12);
    }}
    a.bc-item:hover .bc-icon.document {{
        background: #DFEDFE;
        color: #1D4ED8;
        border-color: rgba(37, 99, 235, 0.25);
    }}
    .bc-item.active .bc-icon.document,
    .bc-item.active .bc-icon.active-icon {{
        background: #D1F2E2 !important;
        color: #0B6E3A !important;
        border: 1px solid rgba(11, 110, 58, 0.18) !important;
    }}
    .bc-sep {{
        display: inline-flex;
        align-items: center;
        justify-content: center;
        width: 16px;
        height: 26px;
        color: #94A3B8;
        user-select: none;
        flex-shrink: 0;
        margin: 0 1px;
    }}
    .bc-sep svg {{
        display: block;
        width: 13px;
        height: 13px;
        stroke: #94A3B8;
        pointer-events: none;
    }}
    .bc-label {{
        display: inline-block;
        max-width: 240px;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
        vertical-align: middle;
        letter-spacing: -0.01em;
    }}
    @media (max-width: 768px) {{
        .breadcrumb-bar {{ padding: 5px 8px; gap: 2px; }}
        .bc-item {{ max-width: 180px; padding: 3px 8px 3px 5px; font-size: 12px; gap: 6px; }}
        .bc-label {{ max-width: 140px; }}
        .bc-icon {{ width: 24px; height: 24px; }}
        .bc-icon svg {{ width: 12px; height: 12px; }}
        .bc-sep {{ width: 14px; }}
        .bc-sep svg {{ width: 11px; height: 11px; }}
    }}
    @media (max-width: 480px) {{
        .bc-label {{ max-width: 100px; }}
        .bc-item {{ max-width: 140px; }}
    }}

    /* ── Teardown Workspace Buttons (Solid Red with Crisp White Text) ── */
    div[class*="st-key-teardown_ws_btn_from_source"] button,
    div[class*="st-key-hub_teardown_ws_btn"] button,
    div[class*="st-key-hub_teardown_confirm_btn"] button,
    div[class*="st-key-del_single_ws_btn"] button,
    div[class*="st-key-del_multi_ws_btn"] button,
    div[class*="st-key-del_all_tbl_ws_btn"] button,
    div[class*="st-key-ws_view_del_single_btn"] button,
    div[class*="st-key-ws_view_del_multi_btn"] button,
    div[class*="st-key-ws_view_del_all_btn"] button,
    div[class*="st-key-teardown_ws"] button,
    div[class*="st-key-hub_teardown_ws"] button,
    div[class*="st-key-hub_teardown_confirm"] button,
    div[class*="st-key-del_single_ws"] button,
    div[class*="st-key-del_multi_ws"] button,
    div[class*="st-key-del_all_tbl_ws"] button,
    div[class*="st-key-ws_view_del_"] button {{
        background: linear-gradient(135deg, #DC2626 0%, #B91C1C 100%) !important;
        background-color: #DC2626 !important;
        border: 1px solid #B91C1C !important;
        color: #FFFFFF !important;
        font-weight: 700 !important;
        font-size: 14px !important;
        letter-spacing: 0.015em !important;
        box-shadow: 0 2px 5px rgba(220, 38, 38, 0.32), 0 1px 2px rgba(0, 0, 0, 0.08) !important;
        opacity: 1 !important;
    }}
    div[class*="st-key-teardown_ws_btn_from_source"] button *,
    div[class*="st-key-hub_teardown_ws_btn"] button *,
    div[class*="st-key-hub_teardown_confirm_btn"] button *,
    div[class*="st-key-del_single_ws_btn"] button *,
    div[class*="st-key-del_multi_ws_btn"] button *,
    div[class*="st-key-del_all_tbl_ws_btn"] button *,
    div[class*="st-key-ws_view_del_single_btn"] button *,
    div[class*="st-key-ws_view_del_multi_btn"] button *,
    div[class*="st-key-ws_view_del_all_btn"] button *,
    div[class*="st-key-teardown_ws"] button *,
    div[class*="st-key-hub_teardown_ws"] button *,
    div[class*="st-key-hub_teardown_confirm"] button *,
    div[class*="st-key-del_single_ws"] button *,
    div[class*="st-key-del_multi_ws"] button *,
    div[class*="st-key-del_all_tbl_ws"] button *,
    div[class*="st-key-ws_view_del_"] button * {{
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
        fill: #FFFFFF !important;
        font-weight: 700 !important;
        text-shadow: 0 1px 2px rgba(0, 0, 0, 0.35) !important;
    }}
    div[class*="st-key-teardown_ws_btn_from_source"] button:hover,
    div[class*="st-key-hub_teardown_ws_btn"] button:hover,
    div[class*="st-key-hub_teardown_confirm_btn"] button:hover,
    div[class*="st-key-del_single_ws_btn"] button:hover,
    div[class*="st-key-del_multi_ws_btn"] button:hover,
    div[class*="st-key-del_all_tbl_ws_btn"] button:hover,
    div[class*="st-key-ws_view_del_single_btn"] button:hover,
    div[class*="st-key-ws_view_del_multi_btn"] button:hover,
    div[class*="st-key-ws_view_del_all_btn"] button:hover,
    div[class*="st-key-teardown_ws"] button:hover,
    div[class*="st-key-hub_teardown_ws"] button:hover,
    div[class*="st-key-hub_teardown_confirm"] button:hover,
    div[class*="st-key-del_single_ws"] button:hover,
    div[class*="st-key-del_multi_ws"] button:hover,
    div[class*="st-key-del_all_tbl_ws"] button:hover,
    div[class*="st-key-ws_view_del_"] button:hover {{
        background: linear-gradient(135deg, #B91C1C 0%, #991B1B 100%) !important;
        background-color: #B91C1C !important;
        border-color: #7F1D1D !important;
        color: #FFFFFF !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 4px 12px rgba(185, 28, 28, 0.45) !important;
        filter: brightness(1.06) !important;
    }}
    div[class*="st-key-teardown_ws_btn_from_source"] button:hover *,
    div[class*="st-key-hub_teardown_ws_btn"] button:hover *,
    div[class*="st-key-hub_teardown_confirm_btn"] button:hover *,
    div[class*="st-key-del_single_ws_btn"] button:hover *,
    div[class*="st-key-del_multi_ws_btn"] button:hover *,
    div[class*="st-key-del_all_tbl_ws_btn"] button:hover *,
    div[class*="st-key-ws_view_del_single_btn"] button:hover *,
    div[class*="st-key-ws_view_del_multi_btn"] button:hover *,
    div[class*="st-key-ws_view_del_all_btn"] button:hover *,
    div[class*="st-key-teardown_ws"] button:hover *,
    div[class*="st-key-hub_teardown_ws"] button:hover *,
    div[class*="st-key-hub_teardown_confirm"] button:hover *,
    div[class*="st-key-del_single_ws"] button:hover *,
    div[class*="st-key-del_multi_ws"] button:hover *,
    div[class*="st-key-del_all_tbl_ws"] button:hover *,
    div[class*="st-key-ws_view_del_"] button:hover * {{
        color: #FFFFFF !important;
        -webkit-text-fill-color: #FFFFFF !important;
    }}
    div[class*="st-key-teardown_ws_btn_from_source"] button:active,
    div[class*="st-key-hub_teardown_ws_btn"] button:active,
    div[class*="st-key-hub_teardown_confirm_btn"] button:active,
    div[class*="st-key-del_single_ws_btn"] button:active,
    div[class*="st-key-del_multi_ws_btn"] button:active,
    div[class*="st-key-del_all_tbl_ws_btn"] button:active,
    div[class*="st-key-ws_view_del_single_btn"] button:active,
    div[class*="st-key-ws_view_del_multi_btn"] button:active,
    div[class*="st-key-ws_view_del_all_btn"] button:active,
    div[class*="st-key-teardown_ws"] button:active,
    div[class*="st-key-hub_teardown_ws"] button:active,
    div[class*="st-key-hub_teardown_confirm"] button:active,
    div[class*="st-key-del_single_ws"] button:active,
    div[class*="st-key-del_multi_ws"] button:active,
    div[class*="st-key-del_all_tbl_ws"] button:active,
    div[class*="st-key-ws_view_del_"] button:active {{
        background: linear-gradient(135deg, #991B1B 0%, #7F1D1D 100%) !important;
        background-color: #991B1B !important;
        border-color: #7F1D1D !important;
        transform: translateY(0px) !important;
        box-shadow: 0 1px 3px rgba(127, 29, 29, 0.4) !important;
    }}
    div[class*="st-key-teardown_ws_btn_from_source"] button:focus,
    div[class*="st-key-hub_teardown_ws_btn"] button:focus,
    div[class*="st-key-hub_teardown_confirm_btn"] button:focus,
    div[class*="st-key-del_single_ws_btn"] button:focus,
    div[class*="st-key-del_multi_ws_btn"] button:focus,
    div[class*="st-key-del_all_tbl_ws_btn"] button:focus,
    div[class*="st-key-ws_view_del_single_btn"] button:focus,
    div[class*="st-key-ws_view_del_multi_btn"] button:focus,
    div[class*="st-key-ws_view_del_all_btn"] button:focus,
    div[class*="st-key-teardown_ws"] button:focus,
    div[class*="st-key-hub_teardown_ws"] button:focus,
    div[class*="st-key-hub_teardown_confirm"] button:focus,
    div[class*="st-key-del_single_ws"] button:focus,
    div[class*="st-key-del_multi_ws"] button:focus,
    div[class*="st-key-del_all_tbl_ws"] button:focus,
    div[class*="st-key-ws_view_del_"] button:focus {{
        box-shadow: 0 0 0 3px rgba(220, 38, 38, 0.45) !important;
        outline: none !important;
    }}

    /* ── Safety / info banners ────────────────────────────────────── */
    .safety-banner {{
        display: flex;
        align-items: flex-start;
        gap: 12px;
        padding: 14px 18px;
        border-radius: 10px;
        background: var(--dq-warning-bg);
        border: 1px solid var(--dq-warning-border);
        margin-bottom: 14px;
    }}
    .safety-banner-icon {{
        font-size: 1.2rem;
        flex-shrink: 0;
        margin-top: 2px;
    }}
    .safety-banner-content {{
        font-size: 0.85rem;
        color: var(--dq-slate-text);
        line-height: 1.55;
    }}

    /* ── Health score details ─────────────────────────────────────── */
    .health-score-details {{
        display: flex;
        flex-direction: column;
        gap: 8px;
    }}

    </style>
    """
    render_html(css)


def render_sidebar_brand() -> None:
    """Renders HTML for the redesigned sidebar brand header block."""
    render_sidebar_brand_redesign()


def render_sidebar_status_card(
    connected: bool = False,
    host: str = "",
    username: str = "",
    server_ver: str = "",
) -> None:
    """Renders HTML for the pinned sidebar connection status card."""
    render_sidebar_status_card_redesign(
        connected=connected,
        host=host,
        username=username,
        server_ver=server_ver,
    )


from ui.welcome_view import (
    render_app_header as _render_app_header_impl,
    render_hero_welcome as _render_hero_welcome_impl,
)


def render_app_header(
    connected: bool = False,
    host: str = "",
    port: str | int = "",
    version: str = "v1.2 Standard",
    theme: str = "light",
    database: Optional[str] = None,
    table: Optional[str] = None,
    module: Optional[str] = None,
) -> None:
    """Renders HTML for the top navigation bar matching the enterprise pill banner."""
    _render_app_header_impl(
        connected=connected,
        host=host,
        port=port,
        version=version,
        theme=theme,
        database=database,
        table=table,
        module=module,
    )


def render_hero_welcome() -> None:
    """Renders HTML for the enterprise landing page with 2-column hero, 3D visual, feature cards, and workflow."""
    _render_hero_welcome_impl()


from ui.cleaning_tabs import (
    render_cleaning_tabs,
    CLEANING_MODULES,
    CLEANING_TAB_NAMES,
)

# Theme resolution & Global CSS rules injection
if "ui_theme" not in st.session_state:
    st.session_state.ui_theme = "light"

inject_theme()


# ============================================================
# Session State Initialization
# ============================================================

DEFAULT_STATE = {
    "ui_theme": "light",
    "connected": False,
    "engine": None,
    "selected_db": None,
    "selected_table": None,
    "conn_config": {},
    "connection_token": None,
    "last_activity": None,
    "working_table_name": None,
    "working_table_status": None,
    "working_table_details": None,
    "source_profile_result": None,
    "profile_result": None,
    "active_profile_target": "source",
    "show_profile_dialog": False,
    "cleaning_report": None,
    "blank_cleaning_report": None,
    "casing_cleaning_report": None,
    "duplicate_cleaning_report": None,
    "duplicate_row_actions": {},
    "numeric_scan_results": None,
    "numeric_column_analyses": {},
    "numeric_selected_col": None,
    "numeric_manual_mode": False,
    "numeric_conversion_report": None,
    "numeric_history": [],
    "active_view": "Source Table",
    "workspace_sub_tab": "🏠 Cleaning Hub",
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ============================================================
# Connection Activity & Inactivity Watchdog
# ============================================================

CONNECTION_IDLE_TIMEOUT_SECONDS = 20 * 60
CONNECTION_HEARTBEAT_SECONDS = 60


def mark_connection_activity():
    """Record normal user interaction as activity."""
    if st.session_state.get("connected"):
        st.session_state.last_activity = time.time()


def nav_to_view(main_view: str, sub_tab: Optional[str] = None):
    """Safely update navigation state across reruns."""
    st.session_state.active_view = main_view
    st.query_params["active_view"] = main_view
    if sub_tab:
        st.session_state.workspace_sub_tab = sub_tab
        st.query_params["workspace_sub_tab"] = sub_tab


def reset_workspace_state():
    """Clear the active cleaning workspace state."""
    st.session_state.working_table_name = None
    st.session_state.working_table_status = None
    st.session_state.working_table_details = None
    st.session_state.profile_result = None
    st.session_state.active_profile_target = "source"
    st.session_state.show_profile_dialog = False
    st.session_state.cleaning_report = None
    st.session_state.blank_cleaning_report = None
    st.session_state.casing_cleaning_report = None
    st.session_state.duplicate_cleaning_report = None
    st.session_state.duplicate_row_actions = {}
    st.session_state.numeric_scan_results = None
    st.session_state.numeric_column_analyses = {}
    st.session_state.numeric_selected_col = None
    st.session_state.numeric_manual_mode = False
    st.session_state.numeric_conversion_report = None
    st.session_state.numeric_history = []
    st.session_state.workspace_sub_tab = "🏠 Cleaning Hub"
    st.query_params["workspace_sub_tab"] = "🏠 Cleaning Hub"
    if "working_table_name" in st.query_params:
        del st.query_params["working_table_name"]


def remove_connection_session():
    """Fully remove the current server-side MySQL connection."""
    MySQLConnectionManager.remove_session(st.session_state.get("connection_token"))

    st.session_state.connected = False
    st.session_state.engine = None
    st.session_state.connection_token = None
    st.session_state.conn_config = {}
    st.session_state.selected_db = None
    st.session_state.selected_table = None
    st.session_state.source_profile_result = None
    st.session_state.profile_result = None
    st.session_state.active_profile_target = "source"
    st.session_state.show_profile_dialog = False
    st.session_state.last_activity = None
    reset_workspace_state()
    st.query_params.clear()


# ============================================================
# Persistent Connection Restore (Stored in st.session_state)
# ============================================================

connection_token = st.session_state.get("connection_token") or st.query_params.get("connection_token")
if isinstance(connection_token, list):
    connection_token = connection_token[0] if connection_token else None

if "connection_token" in st.query_params:
    del st.query_params["connection_token"]

if (
    connection_token
    and not st.session_state.connected
    and st.session_state.engine is None
):
    restored = MySQLConnectionManager.restore_session(connection_token)
    if restored:
        st.session_state.engine = restored["engine"]
        st.session_state.connected = True
        st.session_state.conn_config = {
            "host": restored["host"],
            "port": restored["port"],
            "username": restored["username"],
        }
        st.session_state.connection_token = connection_token
        st.rerun()

# Restore UI state from query_params once per session after connection is restored
# Normalize any session_state or query_params navigation values to canonical tab names
_CANONICAL_NAV_MAP = {
    "Table Explorer & Schema": "📋 Table Explorer & Schema",
    "Cleaning Workspace": "🧹 Cleaning Workspace",
    "Cleaning Hub": "🏠 Cleaning Hub",
    "Whitespace Cleaning": "✂️ Whitespace Cleaning",
    "Blank & NULL Values": "📝 Blank & NULL Values",
    "Text Casing": "🔤 Text Casing",
    "Duplicate Handling": "🔁 Duplicate Handling",
    "Date Formatting": "📅 Date Formatting",
    "Advanced Date Standardization": "🗓️ Advanced Date Standardization",
    "Boolean Normalization": "☑️ Boolean Normalization",
    "Special Character Cleaning": "🔣 Special Character Cleaning",
    "Numeric Data Cleaning": "🔢 Numeric Data Cleaning",
    "AI Assistant": "🤖 AI Assistant",
    "AI Column Analysis and Cleaning": "🧠 AI Column Analysis and Cleaning",
}
for _nav_key in ("active_view", "workspace_sub_tab", "_ws_sub_radio", "_main_nav_radio"):
    if _nav_key in st.session_state and isinstance(st.session_state[_nav_key], str):
        _stripped = re.sub(r"^[\W_]+", "", st.session_state[_nav_key]).strip()
        if _stripped in _CANONICAL_NAV_MAP:
            st.session_state[_nav_key] = _CANONICAL_NAV_MAP[_stripped]

if st.session_state.get("connected") and not st.session_state.get("_qp_restored"):
    if "selected_db" in st.query_params:
        st.session_state.selected_db = st.query_params["selected_db"]
    if "selected_table" in st.query_params:
        st.session_state.selected_table = st.query_params["selected_table"]
    if "working_table_name" in st.query_params:
        st.session_state.working_table_name = st.query_params["working_table_name"]
    if "active_view" in st.query_params:
        st.session_state.active_view = st.query_params["active_view"]
        st.session_state._main_nav_radio = st.query_params["active_view"]
    if "workspace_sub_tab" in st.query_params:
        st.session_state.workspace_sub_tab = st.query_params["workspace_sub_tab"]
        st.session_state._ws_sub_radio = st.query_params["workspace_sub_tab"]
    st.session_state._qp_restored = True

    # Re-attach workspace to get details if we have a working_table_name
    if st.session_state.get("working_table_name") and not st.session_state.get(
        "working_table_details"
    ):
        try:
            ok, msg, details = attach_workspace(
                st.session_state.engine,
                st.session_state.selected_db or "",
                st.session_state.working_table_name,
            )
            if ok:
                st.session_state.working_table_status = details["status"]
                st.session_state.working_table_details = details
        except Exception:
            pass

if st.session_state.get("connected"):
    mark_connection_activity()


# ============================================================
# Data Quality Health Score Calculator
# ============================================================


def calculate_health_score(profile_result: Dict[str, Any]) -> Tuple[int, str, str]:
    """
    Computes a composite data quality health score (0-100%) based on:
    - Missing/Null values density
    - Empty strings density
    - Duplicate rows density
    - Whitespace formatting issues
    - Issue severity weighting
    """
    row_count = profile_result.get("row_count", 0)
    col_count = profile_result.get("column_count", 0)

    if row_count == 0 or col_count == 0:
        return 100, "Clean (Empty Table)", "#15803D"

    total_cells = row_count * col_count
    col_profiles = profile_result.get("column_profiles")

    total_nulls = 0
    total_empties = 0
    total_whitespace = 0

    if isinstance(col_profiles, pd.DataFrame):
        if "Null Count" in col_profiles.columns:
            total_nulls = int(col_profiles["Null Count"].sum())
        if "Empty Strings" in col_profiles.columns:
            total_empties = int(col_profiles["Empty Strings"].sum())
        if "Whitespace Issues" in col_profiles.columns:
            total_whitespace = int(col_profiles["Whitespace Issues"].sum())

    dup_rows = profile_result.get("duplicate_row_count", 0)

    # 1. Null / Empty cell penalty (Max 40 pts)
    null_ratio = min(1.0, (total_nulls + total_empties) / max(1, total_cells))
    null_penalty = null_ratio * 40

    # 2. Duplicate rows penalty (Max 30 pts)
    dup_ratio = min(1.0, dup_rows / max(1, row_count))
    dup_penalty = dup_ratio * 30

    # 3. Whitespace penalty (Max 15 pts)
    ws_ratio = min(1.0, total_whitespace / max(1, total_cells))
    ws_penalty = ws_ratio * 15

    # 4. Severity penalty (Max 15 pts)
    findings = profile_result.get("findings", [])
    high_findings = sum(1 for f in findings if f.get("Severity") == "High")
    findings_penalty = min(15, high_findings * 3)

    raw_score = 100 - (null_penalty + dup_penalty + ws_penalty + findings_penalty)
    score = max(0, min(100, int(round(raw_score))))

    if score >= 90:
        return score, "Excellent Health", "#15803D"
    elif score >= 75:
        return score, "Good Quality", "#15803D"
    elif score >= 50:
        return score, "Fair / Needs Cleaning", "#B45309"
    else:
        return score, "Poor / Critical Issues", "#B91C1C"


# ============================================================
# Floating Window (Modal Dialog): Data Profile Viewer
# ============================================================


def _on_profile_dialog_dismiss():
    """Reset dialog visibility flag when modal is dismissed."""
    st.session_state.show_profile_dialog = False


@st.dialog(
    "Data Quality Profile", width="large", on_dismiss=_on_profile_dialog_dismiss
)
def render_data_profile_dialog(engine, db_name: str, tbl_name: str):
    """
    Renders the Data Profiling view inside an interactive floating window / modal dialog.
    Allows toggling between Source Table and Workspace profiles, refreshing metrics,
    reviewing Health Index, column breakdowns, findings with CSV export, and missingness charts.
    """
    working_tbl = st.session_state.get("working_table_name")
    active_target = st.session_state.get("active_profile_target", "source")

    # If target is workspace but no workspace exists, fallback to source
    if active_target == "workspace" and not working_tbl:
        active_target = "source"
        st.session_state.active_profile_target = "source"

    # ── Top Control Bar: Scope Toggle & Refresh Action ────────────────
    scope_options = [
        "Source Table (Read-Only Baseline)",
        f"Workspace ({'Active Sandbox'if working_tbl else'No Sandbox'})",
    ]
    scope_idx = 0 if active_target == "source" else 1

    ctrl_col1, ctrl_col2 = st.columns([3.5, 1.5])
    with ctrl_col1:
        chosen_scope = st.radio(
            "Profile Target Scope",
            options=scope_options,
            index=scope_idx,
            horizontal=True,
            key="prof_dlg_scope_radio",
            label_visibility="collapsed",
        )
        new_target = "source" if "Source" in chosen_scope else "workspace"
        if new_target != active_target:
            if new_target == "workspace" and not working_tbl:
                st.warning(
                    "No active cleaning workspace. Please create a sandbox workspace first."
                )
            else:
                st.session_state.active_profile_target = new_target
                st.rerun()

    with ctrl_col2:
        if st.button(
            "Refresh Profile",
            type="secondary",
            use_container_width=True,
            key="dlg_refresh_prof_btn",
        ):
            target_to_refresh = tbl_name if active_target == "source" else working_tbl
            with st.spinner(f"Re-auditing `{db_name}`.`{target_to_refresh}`..."):
                if active_target == "workspace":
                    ok, msg, res = profile_workspace(engine, db_name, target_to_refresh)
                    if ok:
                        st.session_state.profile_result = res
                        st.success("Workspace profile refreshed!")
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    ok, msg, res = profile_source_table(
                        engine, db_name, target_to_refresh
                    )
                    if ok:
                        st.session_state.source_profile_result = res
                        st.success("Source profile refreshed!")
                        st.rerun()
                    else:
                        st.error(msg)

    st.markdown("<div style='margin-top: 0.25rem;'></div>", unsafe_allow_html=True)

    # ── Header & Target Identity ─────────────────────────────────────
    if active_target == "source":
        target_tbl_name = tbl_name
        profile_data = st.session_state.get("source_profile_result")
        is_workspace = False
        badge_html = (
            '<span class="badge-pill badge-info">Source Read-Only Baseline</span>'
        )
        caption_text = (
            "Original production table baseline. "
            "Strictly read-only — no production data has been altered."
        )
    else:
        target_tbl_name = working_tbl
        profile_data = st.session_state.get("profile_result")
        is_workspace = True
        badge_html = '<span class="badge-pill badge-warning">Sandbox Workspace (Cleaning Staging)</span>'
        caption_text = (
            "Isolated sandbox table where all cleanings and deduplications are applied. "
            "Your production table remains 100% protected."
        )

    hdr_col1, hdr_col2 = st.columns([3.5, 1.5])
    with hdr_col1:
        st.markdown(
            f"""
            <div>
                <div class="dq-section-title" style="font-size: 1.15rem;">
                    {'Workspace Data Profile'if is_workspace else'Source Table Data Profile'}: 
                    <span class="mono" style="color: var(--dq-accent);">{db_name}.{target_tbl_name}</span>
                </div>
                <div class="dq-section-caption">{caption_text}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    with hdr_col2:
        st.markdown(
            f"<div style='text-align: right; margin-top: 0.2rem;'>{badge_html}</div>",
            unsafe_allow_html=True,
        )

    # ── Empty Profile State (Not generated yet) ──────────────────────
    if not profile_data:
        render_html(f"""
            <div class="safety-banner" style="margin-top: 1rem; border-color: var(--dq-accent-border); background: var(--dq-bg-soft);">
                <div class="safety-banner-icon"></div>
                <div class="safety-banner-content">
                    <h4>No Profile Generated Yet for <code>{db_name}.{target_tbl_name}</code></h4>
                    <p>Click below to perform an automated algorithmic data quality audit on this table.</p>
                </div>
            </div>
            """)
        if st.button(
            f"Generate {'Workspace'if is_workspace else'Source'} Profile",
            type="secondary",
            use_container_width=True,
            key=f"dlg_btn_gen_{active_target}",
        ):
            with st.spinner(f"Auditing `{db_name}`.`{target_tbl_name}`..."):
                if is_workspace:
                    ok, msg, res = profile_workspace(engine, db_name, target_tbl_name)
                    if ok:
                        st.session_state.profile_result = res
                        st.rerun()
                    else:
                        st.error(msg)
                else:
                    ok, msg, res = profile_source_table(
                        engine, db_name, target_tbl_name
                    )
                    if ok:
                        st.session_state.source_profile_result = res
                        st.rerun()
                    else:
                        st.error(msg)
        return

    # ── 1. Composite Health Index ────────────────────────────────────
    score, score_label, score_color = calculate_health_score(profile_data)

    delta_callout = ""
    if is_workspace and st.session_state.get("source_profile_result"):
        src_prof = st.session_state.source_profile_result
        src_score, _, _ = calculate_health_score(src_prof)
        score_diff = score - src_score
        src_dup = src_prof.get("duplicate_row_count", 0)
        ws_dup = profile_data.get("duplicate_row_count", 0)
        dup_diff = src_dup - ws_dup

        diff_badge = (
            f'<span style="color: var(--dq-success); font-weight: 700;">+{score_diff} pts</span>'
            if score_diff > 0
            else f'<span style="color: var(--dq-text-muted);">{score_diff} pts</span>'
        )
        dup_badge = (
            f'<span style="color: var(--dq-success); font-weight: 700;">-{dup_diff} duplicates cleaned</span>'
            if dup_diff > 0
            else "0 change"
        )
        delta_callout = (
            f'<div style="margin-top: 0.5rem; font-size: 0.85rem; color: var(--dq-text-muted);">'
            f"<b>Comparison vs Source Baseline:</b> Source Health: <b>{src_score}/100</b> Workspace Health: <b>{score}/100</b> ({diff_badge}) &nbsp;|&nbsp; Duplicates: {dup_badge}"
            f"</div>"
        )

    score_badge_label = (
        f"{'Workspace' if is_workspace else 'Source'} Score: {score}/100"
    )
    health_card_html = (
        f'<div class="health-score-container" style="border-color: {score_color}40; margin-top: 0.75rem;">'
        f'<div class="health-score-dial" style="border-color: {score_color};">'
        f'<div class="health-score-number" style="color: {score_color};">{score}</div>'
        f'<div class="health-score-pct">HEALTH INDEX</div>'
        f"</div>"
        f'<div class="health-score-details">'
        f'<div style="display: flex; align-items: center; gap: 0.5rem; margin-bottom: 0.25rem;">'
        f'<h4 style="color: {score_color}; margin: 0;">{score_label}</h4>'
        f'<span class="badge-pill" style="background: {score_color}15; color: {score_color}; border: 1px solid {score_color}30;">'
        f"{score_badge_label}"
        f"</span>"
        f"</div>"
        f'<p style="margin: 0.25rem 0 0 0;">Data quality health evaluated across NULL density, blank strings, duplicate row vectors, and detected anomalies.</p>'
        f"{delta_callout}"
        f"</div>"
        f"</div>"
    )
    render_html(health_card_html)

    # ── 2. KPI Overview Cards ────────────────────────────────────────
    render_html("<div style='margin-top: 0.75rem;'></div>")
    with st.container(border=True):
        pk1, pk2, pk3, pk4 = st.columns(4)
        with pk1:
            render_html(f"""
                <div class="kpi-card">
                    <div class="kpi-label">Audited Rows</div>
                    <div class="kpi-value">{profile_data['row_count']:,}</div>
                    <div class="kpi-subtext">Total table records</div>
                </div>
                """)
        with pk2:
            render_html(f"""
                <div class="kpi-card">
                    <div class="kpi-label">Columns</div>
                    <div class="kpi-value">{profile_data['column_count']}</div>
                    <div class="kpi-subtext">Schema dimensions</div>
                </div>
                """)
        with pk3:
            dup_cnt = profile_data.get("duplicate_row_count", 0)
            dup_cls = "kpi-card-danger" if dup_cnt > 0 else "kpi-card-success"
            render_html(f"""
                <div class="kpi-card {dup_cls}">
                    <div class="kpi-label">Duplicate Rows</div>
                    <div class="kpi-value">{dup_cnt:,}</div>
                    <div class="kpi-subtext">{'Redundant records found' if dup_cnt > 0 else 'Zero duplicates'}</div>
                </div>
                """)
        with pk4:
            findings_list = profile_data.get("findings", [])
            f_cnt = len(findings_list)
            find_cls = "kpi-card-warning" if f_cnt > 0 else "kpi-card-success"
            render_html(f"""
                <div class="kpi-card {find_cls}">
                    <div class="kpi-label">Quality Findings</div>
                    <div class="kpi-value">{f_cnt}</div>
                    <div class="kpi-subtext">Anomalies detected</div>
                </div>
                """)

    # ── 3. Detailed Tabs ─────────────────────────────────────────────
    st.markdown("<div style='margin-top: 1.25rem;'></div>", unsafe_allow_html=True)
    p_tab1, p_tab2, p_tab3 = st.tabs(
        [
            "Column Quality Profiles",
            "Detected Findings & Anomalies",
            "Missingness Visualization",
        ]
    )

    with p_tab1:
        col_prof_df = profile_data.get("column_profiles")
        if isinstance(col_prof_df, pd.DataFrame) and not col_prof_df.empty:
            st.dataframe(
                col_prof_df,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Null %": st.column_config.ProgressColumn(
                        "Null %",
                        help="Percentage of NULL values in this column",
                        format="%.1f%%",
                        min_value=0,
                        max_value=100,
                    ),
                    "Unique Values": st.column_config.NumberColumn(
                        "Unique Values",
                        help="Distinct values count",
                        format="%d",
                    ),
                },
            )
        else:
            st.info("No column profile data available.")

    with p_tab2:
        findings = profile_data.get("findings", [])
        if findings:
            f_col1, f_col2 = st.columns([3, 1.2])
            with f_col1:
                st.markdown(
                    f"<div style='margin-bottom: 0.5rem; font-weight: 600;'>Identified <b>{len(findings)}</b> data cleanliness issue(s) on <code>{target_tbl_name}</code>:</div>",
                    unsafe_allow_html=True,
                )
            with f_col2:
                findings_df = pd.DataFrame(findings)
                csv_findings = findings_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    "Export Audit CSV",
                    data=csv_findings,
                    file_name=f"{target_tbl_name}_quality_findings.csv",
                    mime="text/csv",
                    use_container_width=True,
                    key=f"dlg_export_findings_{active_target}_btn",
                )
            st.dataframe(
                pd.DataFrame(findings),
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Severity": st.column_config.TextColumn(
                        "Severity",
                        help="Issue criticality ranking",
                    ),
                },
            )
        else:
            render_html("""
                <div style="text-align: center; padding: 2rem; background: var(--dq-bg-soft); border-radius: 12px; border: 1px solid var(--dq-border);">
                    <div style="font-size: 2rem; margin-bottom: 0.5rem;"></div>
                    <div style="font-weight: 700; font-size: 1.1rem; color: var(--dq-success);">Zero Quality Issues Detected</div>
                    <div style="font-size: 0.86rem; color: var(--dq-slate-muted); max-width: 450px; margin: 0.25rem auto;">
                        This dataset passed all automated quality gates including NULL density, empty strings, and row-level duplicates.
                    </div>
                </div>
                """)

    with p_tab3:
        col_prof_df = profile_data.get("column_profiles")
        if (
            isinstance(col_prof_df, pd.DataFrame)
            and not col_prof_df.empty
            and "Null %" in col_prof_df.columns
            and "Column" in col_prof_df.columns
        ):
            st.markdown("##### Missingness Percentage by Column")
            chart_df = col_prof_df.set_index("Column")[["Null %"]]
            st.bar_chart(chart_df, color="#0F766E")
        else:
            st.info("Insufficient data to plot missingness chart.")

    # ── Executive PDF Export & Close Actions ──────────────────────────
    st.markdown("<div style='margin-top: 1.25rem;'></div>", unsafe_allow_html=True)

    pdf_bytes = generate_executive_profile_pdf(
        db_name=db_name,
        target_tbl_name=target_tbl_name,
        is_workspace=is_workspace,
        score=score,
        score_label=score_label,
        score_color_hex=score_color,
        profile_data=profile_data,
        delta_callout=delta_callout,
    )

    pdf_btn_col1, pdf_btn_col2 = st.columns([1.6, 1])
    with pdf_btn_col1:
        st.download_button(
            "Download Executive Quality Report (PDF)",
            data=pdf_bytes,
            file_name=f"{target_tbl_name}_data_quality_profile.pdf",
            mime="application/pdf",
            use_container_width=True,
            type="primary",
            key=f"dlg_download_pdf_{active_target}_btn",
            help="Download a publication-grade executive audit report in PDF format.",
        )
    with pdf_btn_col2:
        if st.button(
            "Close Window", use_container_width=True, key="dlg_close_window_btn"
        ):
            st.session_state.show_profile_dialog = False
            st.rerun()


# Maintain backwards-compatible function alias
render_data_profile_view = render_data_profile_dialog


# ============================================================
# Global Top Brand Banner (Slim Header with Single-Dot Status Pill)
# ============================================================

connected = st.session_state.get("connected", False)
host_cfg = st.session_state.conn_config.get("host", "")
port_cfg = st.session_state.conn_config.get("port", "")
ui_theme_cfg = st.session_state.get("ui_theme", "dark")

db_crumb = st.session_state.get("selected_db", "")
tbl_crumb = st.session_state.get("selected_table", "")
act_v = st.session_state.get("active_view", "")
mod_crumb = ""
if "Cleaning Workspace" in act_v and st.session_state.get("working_table_name"):
    sub = st.session_state.get("workspace_sub_tab", "")
    parts = sub.split(" ", 1)
    mod_crumb = parts[-1] if len(parts) > 1 and not parts[0].isalnum() else sub

render_app_header(
    connected=connected,
    host=host_cfg,
    port=port_cfg,
    theme=ui_theme_cfg,
    database=db_crumb,
    table=tbl_crumb,
    module=mod_crumb,
)


# ============================================================
# Sidebar - MySQL Connection Hub (320px Enterprise Surface Panel)
# ============================================================

# Default database connection button states and form defaults
test_btn = False
connect_btn = False
host = st.session_state.conn_config.get("host", "localhost")
port = st.session_state.conn_config.get("port", 3306)
username = st.session_state.conn_config.get("username", "root")
password = st.session_state.conn_config.get("password", "")

with st.sidebar:
    st.markdown(get_sidebar_css(), unsafe_allow_html=True)
    render_sidebar_brand()

    if st.session_state.get("workspace_sub_tab") == "🤖 AI Assistant":
        render_ai_config_sidebar(
            on_back_to_hub=lambda: nav_to_view("🧹 Cleaning Workspace", "🏠 Cleaning Hub")
        )
    elif st.session_state.connected:
        # ── Compact connected controls ──────────────────────────
        _c_host = st.session_state.conn_config.get("host", "")
        _c_port = st.session_state.conn_config.get("port", "")
        _c_user = st.session_state.conn_config.get("username", "")

        _server_ver = ""
        if st.session_state.get("engine"):
            try:
                _v = st.session_state.engine.dialect.server_version_info
                if _v:
                    _server_ver = f"MySQL {'.'.join(map(str, _v[:2]))}"
            except Exception:
                pass

        with st.expander("Switch Connection", expanded=False):
            col_sh, col_sp = st.columns(
                [2.8, 1.2], gap="small", vertical_alignment="top"
            )
            with col_sh:
                host = st.text_input(
                    "Host / IP Address",
                    value=st.session_state.conn_config.get("host", "localhost"),
                    placeholder="localhost",
                    key="sb_host_input",
                )
            with col_sp:
                port = st.number_input(
                    "Port",
                    value=st.session_state.conn_config.get("port", 3306),
                    step=1,
                    help="Default MySQL port is 3306",
                    key="sb_port_input",
                )
            username = st.text_input(
                "Username",
                value=st.session_state.conn_config.get("username", "root"),
                placeholder="e.g. root",
                key="sb_user_input",
            )
            password = st.text_input(
                "Password",
                type="password",
                value="",
                placeholder="Enter your database password",
                key="sb_pass_input",
            )
            with st.expander("Advanced Options", expanded=False):
                include_system_dbs = st.checkbox(
                    "Include System Databases",
                    value=False,
                    help="Show internal schemas like mysql, sys, performance_schema.",
                    key="sb_adv_sys_dbs",
                )
                st.caption("Auto‑idle disconnect timeout: **20 minutes**")

            st.markdown('<div style="height: 6px;"></div>', unsafe_allow_html=True)

            sw_col1, sw_col2 = st.columns(2, gap="small")
            with sw_col1:
                test_btn = st.button(
                    "Test Connection", use_container_width=True, key="sb_test_btn"
                )
            with sw_col2:
                connect_btn = st.button(
                    "Connect Database",
                    type="primary",
                    use_container_width=True,
                    key="sb_connect_btn",
                )

        # ── Data Profiling Section ──────────────────────────────
        render_html("""
        <div class="sidebar-section-header">Data profiling</div>
        """)

        has_selected_table = bool(
            st.session_state.get("selected_db")
            and st.session_state.selected_db != "-- Select Database --"
            and st.session_state.get("selected_table")
            and st.session_state.selected_table != "-- Select Table --"
        )
        active_ws_table = st.session_state.get("working_table_name")

        if not has_selected_table:
            st.caption(
                "Select a database and source table on the main page to enable profiling."
            )
            st.button(
                "Data Profile for Source Table",
                use_container_width=True,
                disabled=True,
                key="sb_prof_src_btn_disabled",
            )
            st.button(
                "Data Profile for Workspace",
                use_container_width=True,
                disabled=True,
                key="sb_prof_ws_btn_disabled",
            )
        else:
            db_for_prof = st.session_state.selected_db
            src_tbl_for_prof = st.session_state.selected_table

            # 1. Data Profile for Source Table
            is_src_active = (
                st.session_state.get("show_profile_dialog")
                and st.session_state.get("active_profile_target") == "source"
            )
            if st.button(
                "Data Profile for Source Table",
                use_container_width=True,
                type="primary" if is_src_active else "secondary",
                key="sb_prof_src_btn",
                help=f"Open floating Data Quality Profile window for source table `{db_for_prof}`.`{src_tbl_for_prof}`.",
            ):
                with st.spinner(
                    f"Auditing source table `{db_for_prof}`.`{src_tbl_for_prof}` (read-only)..."
                ):
                    sp_ok, sp_msg, sp_profile = profile_source_table(
                        st.session_state.engine, db_for_prof, src_tbl_for_prof
                    )
                if sp_ok:
                    st.session_state.source_profile_result = sp_profile
                    st.session_state.active_profile_target = "source"
                    st.session_state.show_profile_dialog = True
                    st.rerun()
                else:
                    st.session_state.source_profile_result = None
                    st.sidebar.error(f"{sp_msg}")

            # 2. Data Profile for Workspace Table
            if not active_ws_table:
                st.button(
                    "Data Profile for Workspace",
                    use_container_width=True,
                    disabled=True,
                    key="sb_prof_ws_btn_disabled_no_ws",
                    help="No active sandbox workspace. Create one in the Source Table view to profile sandbox data.",
                )
                st.caption(
                    "No active sandbox workspace. Create a workspace in Source Table to profile sandbox data."
                )
            else:
                is_ws_active = (
                    st.session_state.get("show_profile_dialog")
                    and st.session_state.get("active_profile_target") == "workspace"
                )
                if st.button(
                    "Data Profile for Workspace",
                    use_container_width=True,
                    type="primary" if is_ws_active else "secondary",
                    key="sb_prof_ws_btn",
                    help=f"Open floating Data Quality Profile window for sandbox workspace `{db_for_prof}`.`{active_ws_table}`.",
                ):
                    with st.spinner(
                        f"Auditing workspace sandbox `{db_for_prof}`.`{active_ws_table}`..."
                    ):
                        p_ok, p_msg, p_profile = profile_workspace(
                            st.session_state.engine, db_for_prof, active_ws_table
                        )
                    if p_ok:
                        st.session_state.profile_result = p_profile
                        st.session_state.active_profile_target = "workspace"
                        st.session_state.show_profile_dialog = True
                        st.rerun()
                    else:
                        st.session_state.profile_result = None
                        st.sidebar.error(f"{p_msg}")

        # ── Destructive Disconnect Button (Bottom of Sidebar) ───
        render_html('<div class="sb-disconnect-divider"></div>')
        if st.button(
            "Disconnect",
            use_container_width=True,
            key="sb_disconnect_btn",
        ):
            remove_connection_session()
            st.session_state.active_view = "Source Table"
            st.rerun()
    else:
        # ── Full connection form (disconnected) ──────────────────
        render_sidebar_promo_card()
        render_sidebar_section_heading()

        host = st.text_input(
            "Host / IP Address",
            value=st.session_state.conn_config.get("host", "localhost"),
            placeholder="localhost",
            key="sb_host_input_main",
            help="Host domain or IP address of your MySQL database server.",
        )
        port = st.number_input(
            "Port",
            value=st.session_state.conn_config.get("port", 3306),
            min_value=1,
            max_value=65535,
            step=1,
            placeholder="3306",
            help="MySQL server port (default: 3306)",
            key="sb_port_input_main",
        )

        # Authentication
        username = st.text_input(
            "Username",
            value=st.session_state.conn_config.get("username", "root"),
            placeholder="e.g. root",
            key="sb_user_input_main",
        )
        password = st.text_input(
            "Password",
            type="password",
            value=st.session_state.conn_config.get("password", ""),
            placeholder="Enter your database password",
            key="sb_pass_input_main",
        )

        with st.expander("Advanced Connection Options", expanded=False):
            include_system_dbs = st.checkbox(
                "Include System Databases",
                value=False,
                help="Show internal schemas like mysql, sys, performance_schema.",
                key="sb_adv_sys_dbs_main",
            )
            st.caption("Auto‑idle session timeout: **20 minutes**")

        st.markdown('<div style="height: 6px;"></div>', unsafe_allow_html=True)

        # Action Buttons: equal two columns (40px standard height)
        col_test, col_connect = st.columns(2, gap="small")
        with col_test:
            test_btn = st.button(
                "Test Connection",
                use_container_width=True,
                key="sb_test_main_btn",
            )
        with col_connect:
            connect_btn = st.button(
                "Connect",
                type="primary",
                use_container_width=True,
                key="sb_connect_main_btn",
            )

        render_sidebar_bottom_waves()

    # --------------------------------------------------------
    # Action Handlers: Test Connection
    # --------------------------------------------------------
    if test_btn:
        if not host or not username:
            show_alert(
                "Missing Information",
                "Please enter both Host and Username to test the connection.",
                alert_type="warning",
                key="alert_missing_creds"
            )
        else:
            with st.spinner("Testing connection..."):
                success, msg = MySQLConnectionManager.test_connection(
                    host, int(port), username, password
                )
            if success:
                st.toast("Connection successful!")
                st.success(msg)
            else:
                if is_credential_error(msg):
                    render_credential_error_dialog()
                else:
                    title, message = parse_connection_error(msg)
                    show_alert(
                        title,
                        message,
                        alert_type="error",
                        key="alert_test_failed"
                    )

    # --------------------------------------------------------
    # Action Handlers: Connect
    # --------------------------------------------------------
    if connect_btn:
        if not host or not username:
            show_alert(
                "Missing Information",
                "Please enter both Host and Username to connect.",
                alert_type="warning",
                key="alert_missing_creds_connect"
            )
        else:
            with st.spinner("Connecting to MySQL instance..."):
                success, msg = MySQLConnectionManager.test_connection(
                    host, int(port), username, password
                )

            if success:
                try:
                    token, engine, _ = MySQLConnectionManager.create_session(
                        host, int(port), username, password
                    )
                    st.session_state.engine = engine
                    st.session_state.connected = True
                    st.session_state.connection_token = token
                    st.session_state.conn_config = {
                        "host": host,
                        "port": int(port),
                        "username": username,
                    }
                    if "connection_token" in st.query_params:
                        del st.query_params["connection_token"]
                    st.session_state.selected_db = None
                    st.session_state.selected_table = None
                    reset_workspace_state()
                    st.session_state.active_view = "Source Table"
                    st.toast("Connected to MySQL instance!")
                    st.success("Successfully connected!")
                    st.rerun()
                except Exception as e:
                    st.session_state.connected = False
                    if is_credential_error(str(e)):
                        render_credential_error_dialog()
                    else:
                        title, message = parse_connection_error(str(e))
                        show_alert(
                            title,
                            message,
                            alert_type="error",
                            key="alert_engine_failed"
                        )
            else:
                st.session_state.connected = False
                if is_credential_error(msg):
                    render_credential_error_dialog()
                else:
                    title, message = parse_connection_error(msg)
                    show_alert(
                        title,
                        message,
                        alert_type="error",
                        key="alert_connect_failed"
                    )

# ============================================================
# Inactivity Watchdog Fragment
# ============================================================

if st.session_state.get("connected"):

    @st.fragment(run_every=CONNECTION_HEARTBEAT_SECONDS)
    def connection_watchdog():
        last_activity = st.session_state.get("last_activity")
        if last_activity is None:
            st.session_state.last_activity = time.time()
            return

        idle_seconds = time.time() - last_activity
        if idle_seconds >= CONNECTION_IDLE_TIMEOUT_SECONDS:
            remove_connection_session()
            st.session_state.active_view = "Source Table"
            st.rerun()

    connection_watchdog()


# ============================================================
# Main Application Body
# ============================================================

if not st.session_state.connected:
    # ---------------------------------------------------------
    # Elegant Welcome State when Disconnected
    # ---------------------------------------------------------
    render_hero_welcome()

else:
    engine = st.session_state.engine
    # ── Handle Breadcrumb Navigation Actions ────────────────────
    _bc_action = st.query_params.get("bc_nav")
    if _bc_action:
        if isinstance(_bc_action, list):
            _bc_action = _bc_action[0] if _bc_action else ""
        try:
            del st.query_params["bc_nav"]
        except Exception:
            pass
        if _bc_action == "home":
            st.session_state.selected_db = None
            st.session_state.selected_table = None
            if "selected_db" in st.query_params:
                try:
                    del st.query_params["selected_db"]
                except Exception:
                    pass
            if "selected_table" in st.query_params:
                try:
                    del st.query_params["selected_table"]
                except Exception:
                    pass
            st.session_state.source_profile_result = None
            reset_workspace_state()
            st.session_state.active_view = "Source Table"
            st.query_params["active_view"] = "Source Table"
            st.rerun()
        elif _bc_action == "db":
            st.session_state.selected_table = None
            if "selected_table" in st.query_params:
                try:
                    del st.query_params["selected_table"]
                except Exception:
                    pass
            st.session_state.source_profile_result = None
            reset_workspace_state()
            st.session_state.active_view = "Source Table"
            st.query_params["active_view"] = "Source Table"
            st.rerun()
        elif _bc_action == "table":
            st.session_state.active_view = "Source Table"
            st.query_params["active_view"] = "Source Table"
            st.rerun()


    # ---------------------------------------------------------
    # Database Discovery
    # ---------------------------------------------------------
    try:
        databases = MySQLMetadataInspector.get_databases(
            engine,
            include_system_dbs=(
                include_system_dbs if "include_system_dbs" in locals() else False
            ),
        )
    except Exception as e:
        st.error(f"Error discovering databases: {str(e)}")
        databases = []

    if not databases:
        st.warning(
            "No databases found on this MySQL server or current user lacks database privileges."
        )
    else:
        # =====================================================
        # Step 2: Source Selection Cards
        # =====================================================
        st.markdown(
            '<div class="dq-section-title"> Source Database & Table Selection</div>',
            unsafe_allow_html=True,
        )

        with st.container(border=True):
            sel_col1, sel_col2 = st.columns(2)

            with sel_col1:
                selected_db = st.selectbox(
                    "Database / Schema",
                    options=["-- Select Database --"] + databases,
                    index=(
                        0
                        if (
                            not st.session_state.selected_db
                            or st.session_state.selected_db not in databases
                        )
                        else databases.index(st.session_state.selected_db) + 1
                    ),
                    help="Choose the MySQL database containing your target tables.",
                )

                if (
                    selected_db != "-- Select Database --"
                    and selected_db != st.session_state.selected_db
                ):
                    st.session_state.selected_db = selected_db
                    st.session_state.selected_table = None
                    st.session_state.source_profile_result = None
                    reset_workspace_state()
                    st.session_state.active_view = "Source Table"
                    st.rerun()

            tables = []
            if (
                st.session_state.selected_db
                and st.session_state.selected_db != "-- Select Database --"
            ):
                try:
                    all_tables = MySQLMetadataInspector.get_tables(
                        engine,
                        st.session_state.selected_db,
                    )
                    # Filter internal cleaning workspaces from source list
                    tables = [t for t in all_tables if "__cleaning_" not in t]
                except Exception as e:
                    st.error(f"Error fetching tables: {str(e)}")

            # Persist selected_db and selected_table to query_params for refresh survival
            if st.session_state.get("selected_db"):
                st.query_params["selected_db"] = st.session_state.selected_db
            if st.session_state.get("selected_table"):
                st.query_params["selected_table"] = st.session_state.selected_table
            if st.session_state.get("working_table_name"):
                st.query_params["working_table_name"] = (
                    st.session_state.working_table_name
                )
            if st.session_state.get("active_view"):
                st.query_params["active_view"] = st.session_state.active_view
            if st.session_state.get("workspace_sub_tab"):
                st.query_params["workspace_sub_tab"] = (
                    st.session_state.workspace_sub_tab
                )

            with sel_col2:
                selected_table = st.selectbox(
                    "Source Table",
                    options=["-- Select Table --"] + tables,
                    index=(
                        0
                        if (
                            not st.session_state.selected_table
                            or st.session_state.selected_table not in tables
                        )
                        else tables.index(st.session_state.selected_table) + 1
                    ),
                    help="Choose the table to inspect, profile, or clean.",
                )

                if (
                    selected_table != "-- Select Table --"
                    and selected_table != st.session_state.selected_table
                ):
                    st.session_state.selected_table = selected_table
                    st.session_state.source_profile_result = None
                    reset_workspace_state()
                    st.session_state.active_view = "Source Table"
                    st.rerun()

        # =====================================================
        # View Controller (When Table is Selected)
        # =====================================================
        if (
            st.session_state.selected_db
            and st.session_state.selected_table
            and st.session_state.selected_table != "-- Select Table --"
        ):
            db_name = st.session_state.selected_db
            tbl_name = st.session_state.selected_table

            # Auto-reconnect to existing workspace if exactly one exists in MySQL
            if not st.session_state.working_table_name:
                existing_tbl_workspaces = list_workspaces_for_table(
                    engine, db_name, tbl_name
                )
                if len(existing_tbl_workspaces) == 1:
                    single_ws = existing_tbl_workspaces[0]["working_table_name"]
                    ok, msg, details = attach_workspace(engine, db_name, single_ws)
                    if ok:
                        st.session_state.working_table_name = details[
                            "working_table_name"
                        ]
                        st.session_state.working_table_status = details["status"]
                        st.session_state.working_table_details = details
                        st.query_params["working_table_name"] = details[
                            "working_table_name"
                        ]



            # ── Outer navigation: Redesigned Enterprise Main Navigation ──────
            active_view = render_main_navigation()

            st.markdown(
                "<div style='margin-bottom:0.5rem;'></div>", unsafe_allow_html=True
            )

            # =================================================
            # VIEW: Source Table
            # =================================================
            if active_view == "Source Table":

                st.markdown(
                    f"""
                    <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; margin-bottom: 0.75rem;">
                        <div>
                            <div class="dq-section-title"> Source Table: <span class="mono"style="color: var(--dq-accent);">{db_name}.{tbl_name}</span></div>
                            <div class="dq-section-caption">Original production table. Operating in strict read-only mode to prevent data corruption.</div>
                        </div>
                        <div>
                            <span class="badge-pill badge-info">Source Read-Only</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # =============================================
                # Cleaning Workspace Section
                # =============================================
                st.markdown(
                    '<div class="dq-section-title" style="margin-top: 1.75rem;">'
                    "Cleaning Workspace</div>",
                    unsafe_allow_html=True,
                )

                with st.container(border=True):
                    if st.session_state.working_table_name:
                        working_tbl = st.session_state.working_table_name
                        _ws_details = st.session_state.get("working_table_details") or {}
                        _ws_row_count = _ws_details.get("row_count")
                        render_sandbox_banner(
                            working_table=working_tbl,
                            source_table=f"{db_name}.{tbl_name}",
                            row_count=_ws_row_count,
                        )
                        st.markdown("<div style='margin-bottom: 0.75rem;'></div>", unsafe_allow_html=True)
                        btn_c1, btn_c2 = st.columns([1.5, 1.5])
                        with btn_c1:
                            if st.button(
                                "Open Cleaning Workspace",
                                type="secondary",
                                use_container_width=True,
                                key="open_ws_btn_from_source",
                            ):
                                nav_to_view("🧹 Cleaning Workspace", "🏠 Cleaning Hub")
                                st.rerun()
                        with btn_c2:
                            if st.button(
                                "Teardown Workspace",
                                type="primary",
                                use_container_width=True,
                                key="teardown_ws_btn_from_source",
                            ):
                                with st.spinner("Dropping workspace table..."):
                                    del_ok, del_msg = delete_workspace(
                                        engine, db_name, working_tbl
                                    )
                                if del_ok:
                                    reset_workspace_state()
                                    st.success(del_msg)
                                    st.rerun()
                                else:
                                    st.error(del_msg)
                    else:
                        # Discover if any existing workspaces exist for this source table in MySQL
                        existing_tbl_workspaces = list_workspaces_for_table(
                            engine, db_name, tbl_name
                        )

                        if existing_tbl_workspaces:
                            num_existing = len(existing_tbl_workspaces)
                            st.warning(
                                f"**Existing Workspace Detected in Database ({num_existing})**\n\n"
                                f"An isolated cleaning workspace for `{tbl_name}` was previously created and remains saved in MySQL. "
                                "You can resume it directly or teardown the table."
                            )

                            if num_existing == 1:
                                target_ws = existing_tbl_workspaces[0]
                                ws_target_name = target_ws["working_table_name"]
                                ws_target_rows = target_ws["row_count"]

                                st.markdown(
                                    f"""
                                    <div style="background: var(--dq-bg-soft); border: 1px solid var(--dq-border); border-radius: 8px; padding: 0.75rem 1rem; margin-bottom: 0.75rem;">
                                        <div style="font-size: 0.85rem; color: var(--dq-slate);">
                                            <b>Table:</b> <code class="mono" style="color: var(--dq-accent);">{ws_target_name}</code> &nbsp;|&nbsp; 
                                            <b>Rows:</b> {ws_target_rows:,}
                                        </div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                                col_act1, col_act2, col_act3 = st.columns(
                                    [1.8, 1.4, 1.8]
                                )
                                with col_act1:
                                    if st.button(
                                        "Resume Existing Workspace",
                                        type="secondary",
                                        use_container_width=True,
                                        key="resume_single_ws_btn",
                                    ):
                                        ok, msg, details = attach_workspace(
                                            engine, db_name, ws_target_name
                                        )
                                        if ok:
                                            st.session_state.working_table_name = (
                                                details["working_table_name"]
                                            )
                                            st.session_state.working_table_status = (
                                                details["status"]
                                            )
                                            st.session_state.working_table_details = (
                                                details
                                            )
                                            st.session_state.profile_result = None
                                            st.query_params["working_table_name"] = (
                                                details["working_table_name"]
                                            )
                                            nav_to_view(
                                                "🧹 Cleaning Workspace",
                                                "🏠 Cleaning Hub",
                                            )
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                with col_act2:
                                    if st.button(
                                        "Teardown Workspace",
                                        type="primary",
                                        use_container_width=True,
                                        key="del_single_ws_btn",
                                    ):
                                        with st.spinner(
                                            "Dropping existing workspace..."
                                        ):
                                            del_ok, del_msg = delete_workspace(
                                                engine, db_name, ws_target_name
                                            )
                                        if del_ok:
                                            st.success(del_msg)
                                            st.rerun()
                                        else:
                                            st.error(del_msg)
                                with col_act3:
                                    if st.button(
                                        "Create Fresh Instead",
                                        type="secondary",
                                        use_container_width=True,
                                        key="create_fresh_ws_btn",
                                    ):
                                        with st.spinner(
                                            "Provisioning new workspace copy..."
                                        ):
                                            success, msg, details = create_workspace(
                                                engine, db_name, tbl_name
                                            )
                                        if success:
                                            st.session_state.working_table_name = (
                                                details["working_table_name"]
                                            )
                                            st.session_state.working_table_status = (
                                                details["status"]
                                            )
                                            st.session_state.working_table_details = (
                                                details
                                            )
                                            st.session_state.profile_result = None
                                            st.query_params["working_table_name"] = (
                                                details["working_table_name"]
                                            )
                                            nav_to_view(
                                                "🧹 Cleaning Workspace",
                                                "🏠 Cleaning Hub",
                                            )
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                            else:
                                ws_options = [
                                    w["working_table_name"]
                                    for w in existing_tbl_workspaces
                                ]
                                chosen_ws = st.selectbox(
                                    "Select Existing Workspace Table",
                                    options=ws_options,
                                    key="choose_existing_ws_sel",
                                )
                                col_m1, col_m2, col_m3 = st.columns([1.8, 1.4, 1.8])
                                with col_m1:
                                    if st.button(
                                        "Resume Selected",
                                        type="secondary",
                                        use_container_width=True,
                                        key="resume_multi_ws_btn",
                                    ):
                                        ok, msg, details = attach_workspace(
                                            engine, db_name, chosen_ws
                                        )
                                        if ok:
                                            st.session_state.working_table_name = (
                                                details["working_table_name"]
                                            )
                                            st.session_state.working_table_status = (
                                                details["status"]
                                            )
                                            st.session_state.working_table_details = (
                                                details
                                            )
                                            st.query_params["working_table_name"] = (
                                                details["working_table_name"]
                                            )
                                            st.session_state.profile_result = None
                                            nav_to_view(
                                                "🧹 Cleaning Workspace",
                                                "🏠 Cleaning Hub",
                                            )
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                with col_m2:
                                    if st.button(
                                        "Teardown Selected",
                                        type="primary",
                                        use_container_width=True,
                                        key="del_multi_ws_btn",
                                    ):
                                        del_ok, del_msg = delete_workspace(
                                            engine, db_name, chosen_ws
                                        )
                                        if del_ok:
                                            st.success(del_msg)
                                            st.rerun()
                                        else:
                                            st.error(del_msg)
                                with col_m3:
                                    if st.button(
                                        "Create Fresh Copy",
                                        type="secondary",
                                        use_container_width=True,
                                        key="create_fresh_multi_ws_btn",
                                    ):
                                        with st.spinner(
                                            "Provisioning new workspace copy..."
                                        ):
                                            success, msg, details = create_workspace(
                                                engine, db_name, tbl_name
                                            )
                                        if success:
                                            st.session_state.working_table_name = (
                                                details["working_table_name"]
                                            )
                                            st.session_state.working_table_status = (
                                                details["status"]
                                            )
                                            st.session_state.working_table_details = (
                                                details
                                            )
                                            st.session_state.profile_result = None
                                            st.query_params["working_table_name"] = (
                                                details["working_table_name"]
                                            )
                                            nav_to_view(
                                                "🧹 Cleaning Workspace",
                                                "🏠 Cleaning Hub",
                                            )
                                            st.success(msg)
                                            st.rerun()
                                        else:
                                            st.error(msg)
                                if st.button(
                                    f"Teardown All {num_existing} Workspaces for `{tbl_name}`",
                                    key="del_all_tbl_ws_btn",
                                    type="primary",
                                    use_container_width=True,
                                ):
                                    del_ok, del_msg, del_cnt = delete_all_workspaces(
                                        engine, db_name, source_table=tbl_name
                                    )
                                    st.success(del_msg)
                                    st.rerun()
                        else:
                            st.info(
                                "No cleaning workspace currently exists for this table in MySQL."
                            )
                            st.caption(
                                "Create an isolated sandbox copy to safely clean and transform data without modifying production tables."
                            )
                            if st.button(
                                "Create Cleaning Workspace",
                                type="secondary",
                                use_container_width=False,
                                key="create_ws_btn_from_source",
                            ):
                                with st.spinner(
                                    "Provisioning isolated workspace copy..."
                                ):
                                    success, msg, details = create_workspace(
                                        engine, db_name, tbl_name
                                    )
                                if success:
                                    st.session_state.working_table_name = details[
                                        "working_table_name"
                                    ]
                                    st.session_state.working_table_status = details[
                                        "status"
                                    ]
                                    st.session_state.working_table_details = details
                                    st.query_params["working_table_name"] = details[
                                        "working_table_name"
                                    ]
                                    st.session_state.profile_result = None
                                    nav_to_view(
                                        "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                    )
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)

                # ---------------------------------------------
                # Source Schema & Data Preview Tabs
                # ---------------------------------------------
                st.markdown(
                    '<div class="dq-section-title" style="margin-top: 1.25rem;"> Schema &amp; Data Inspection</div>',
                    unsafe_allow_html=True,
                )

                with st.container(border=True):
                    tab_schema, tab_preview = st.tabs(
                        ["Schema & Structure", "Live Data Preview"]
                    )

                    with tab_schema:
                        try:
                            schema_data = MySQLMetadataInspector.get_table_schema(
                                engine, db_name, tbl_name
                            )
                            schema_df = pd.DataFrame(schema_data)

                            if not schema_df.empty:
                                # Column classification metrics
                                total_cols = len(schema_df)
                                pk_cols = sum(
                                    1
                                    for row in schema_data
                                    if "PRIMARY KEY" in str(row.get("Key", ""))
                                )
                                nullable_cols = sum(
                                    1
                                    for row in schema_data
                                    if str(row.get("Nullable", "")).upper() == "YES"
                                )

                                m1, m2, m3 = st.columns(3)
                                with m1:
                                    st.markdown(
                                        f"""
                                        <div class="kpi-card">
                                            <div class="kpi-label">Total Columns</div>
                                            <div class="kpi-value">{total_cols}</div>
                                            <div class="kpi-subtext">Discovered in schema</div>
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )
                                with m2:
                                    st.markdown(
                                        f"""
                                        <div class="kpi-card">
                                            <div class="kpi-label">Primary Key Columns</div>
                                            <div class="kpi-value">{pk_cols}</div>
                                            <div class="kpi-subtext">Unique identifiers</div>
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )
                                with m3:
                                    st.markdown(
                                        f"""
                                        <div class="kpi-card">
                                            <div class="kpi-label">Nullable Columns</div>
                                            <div class="kpi-value">{nullable_cols}</div>
                                            <div class="kpi-subtext">Can accept NULL values</div>
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )

                                st.markdown(
                                    "<div style='margin-top: 1rem;'></div>",
                                    unsafe_allow_html=True,
                                )
                                st.dataframe(
                                    schema_df,
                                    use_container_width=True,
                                    hide_index=True,
                                )
                            else:
                                st.info("No columns returned for this table.")
                        except Exception as e:
                            st.error(f"Could not load schema: {str(e)}")

                    with tab_preview:
                        try:
                            ctrl_col1, ctrl_col2, ctrl_col3 = st.columns(
                                [1.5, 2.5, 1.2]
                            )
                            with ctrl_col1:
                                preview_limit = st.select_slider(
                                    "Sample Size",
                                    options=[5, 10, 25, 50, 100],
                                    value=10,
                                    help="Limit the number of preview rows loaded from the database.",
                                )

                            preview_df = MySQLMetadataInspector.get_table_preview(
                                engine, db_name, tbl_name, limit=preview_limit
                            )

                            with ctrl_col2:
                                st.markdown(
                                    f"""
                                    <div style="margin-top: 1.85rem;">
                                        <span class="badge-pill badge-info">Displaying {len(preview_df)} sample rows</span>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )

                            with ctrl_col3:
                                if not preview_df.empty:
                                    csv_data = preview_df.to_csv(index=False).encode(
                                        "utf-8"
                                    )
                                    st.download_button(
                                        "Export CSV",
                                        data=csv_data,
                                        file_name=f"{tbl_name}_preview.csv",
                                        mime="text/csv",
                                        use_container_width=True,
                                    )

                            if preview_df.empty:
                                st.info("This table is empty (0 rows found).")
                            else:
                                st.dataframe(
                                    preview_df,
                                    use_container_width=True,
                                    hide_index=True,
                                )
                        except Exception as e:
                            st.error(f"Could not load data preview: {str(e)}")

            # =================================================
            # VIEW: Cleaning Workspace
            # =================================================
            elif active_view == "🧹 Cleaning Workspace":
                if not st.session_state.working_table_name:

                    existing_tbl_workspaces = list_workspaces_for_table(
                        engine, db_name, tbl_name
                    )
                    if existing_tbl_workspaces:
                        num_existing = len(existing_tbl_workspaces)
                        render_html(f"""
                            <div class="safety-banner" style="border-color: var(--dq-warning-border); background: var(--dq-warning-bg); margin-bottom: 1rem;">
                                
                                <div class="safety-banner-content">
                                    <h4 style="color: var(--dq-warning);">Existing Cleaning Workspace Detected in Database ({num_existing})</h4>
                                    <p>An isolated workspace copy for <b><code>{db_name}.{tbl_name}</code></b> was previously created and remains saved in MySQL.</p>
                                </div>
                            </div>
                            """)

                        if num_existing == 1:
                            target_ws = existing_tbl_workspaces[0]
                            ws_target_name = target_ws["working_table_name"]
                            ws_target_rows = target_ws["row_count"]

                            st.markdown(
                                f"""
                                <div style="background: var(--dq-bg-soft); border: 1px solid var(--dq-border); border-radius: 8px; padding: 0.85rem 1.2rem; margin-bottom: 0.75rem;">
                                    <div style="font-size: 0.9rem; color: var(--dq-slate);">
                                        <b>Workspace Table:</b> <code class="mono" style="color: var(--dq-accent); font-size: 0.95rem;">{ws_target_name}</code> &nbsp;|&nbsp; 
                                        <b>Rows:</b> {ws_target_rows:,}
                                    </div>
                                    <div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-top: 0.3rem;">
                                        All transformations and profiles from your prior session are preserved inside this table.
                                    </div>
                                </div>
                                """,
                                unsafe_allow_html=True,
                            )

                            col_act1, col_act2, col_act3 = st.columns([1.8, 1.4, 1.8])
                            with col_act1:
                                if st.button(
                                    "Resume Existing Workspace",
                                    type="secondary",
                                    use_container_width=True,
                                    key="ws_view_resume_single_btn",
                                ):
                                    ok, msg, details = attach_workspace(
                                        engine, db_name, ws_target_name
                                    )
                                    if ok:
                                        st.session_state.working_table_name = details[
                                            "working_table_name"
                                        ]
                                        st.session_state.working_table_status = details[
                                            "status"
                                        ]
                                        st.session_state.working_table_details = details
                                        st.session_state.profile_result = None
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            with col_act2:
                                if st.button(
                                    "Teardown Workspace",
                                    type="primary",
                                    use_container_width=True,
                                    key="ws_view_del_single_btn",
                                ):
                                    with st.spinner("Dropping workspace table..."):
                                        del_ok, del_msg = delete_workspace(
                                            engine, db_name, ws_target_name
                                        )
                                    if del_ok:
                                        reset_workspace_state()
                                        st.success(del_msg)
                                        st.rerun()
                                    else:
                                        st.error(del_msg)
                            with col_act3:
                                if st.button(
                                    "Create Fresh Instead",
                                    type="secondary",
                                    use_container_width=True,
                                    key="ws_view_fresh_single_btn",
                                ):
                                    with st.spinner(
                                        "Provisioning new workspace copy..."
                                    ):
                                        success, msg, details = create_workspace(
                                            engine, db_name, tbl_name
                                        )
                                    if success:
                                        st.session_state.working_table_name = details[
                                            "working_table_name"
                                        ]
                                        st.session_state.working_table_status = details[
                                            "status"
                                        ]
                                        st.session_state.working_table_details = details
                                        st.session_state.profile_result = None
                                        st.rerun()
                                    else:
                                        st.error(msg)
                        else:
                            ws_options = [
                                w["working_table_name"] for w in existing_tbl_workspaces
                            ]
                            chosen_ws = st.selectbox(
                                "Select Existing Workspace Table to Resume",
                                options=ws_options,
                                key="ws_view_multi_sel",
                            )
                            col_m1, col_m2, col_m3 = st.columns([1.8, 1.4, 1.8])
                            with col_m1:
                                if st.button(
                                    "Resume Selected",
                                    type="secondary",
                                    use_container_width=True,
                                    key="ws_view_resume_multi_btn",
                                ):
                                    ok, msg, details = attach_workspace(
                                        engine, db_name, chosen_ws
                                    )
                                    if ok:
                                        st.session_state.working_table_name = details[
                                            "working_table_name"
                                        ]
                                        st.session_state.working_table_status = details[
                                            "status"
                                        ]
                                        st.session_state.working_table_details = details
                                        st.session_state.profile_result = None
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            with col_m2:
                                if st.button(
                                    "Teardown Selected",
                                    type="primary",
                                    use_container_width=True,
                                    key="ws_view_del_multi_btn",
                                ):
                                    del_ok, del_msg = delete_workspace(
                                        engine, db_name, chosen_ws
                                    )
                                    if del_ok:
                                        st.success(del_msg)
                                        st.rerun()
                                    else:
                                        st.error(del_msg)
                            with col_m3:
                                if st.button(
                                    "Create Fresh Copy",
                                    type="secondary",
                                    use_container_width=True,
                                    key="ws_view_fresh_multi_btn",
                                ):
                                    with st.spinner(
                                        "Provisioning new workspace copy..."
                                    ):
                                        success, msg, details = create_workspace(
                                            engine, db_name, tbl_name
                                        )
                                    if success:
                                        st.session_state.working_table_name = details[
                                            "working_table_name"
                                        ]
                                        st.session_state.working_table_status = details[
                                            "status"
                                        ]
                                        st.session_state.working_table_details = details
                                        st.session_state.profile_result = None
                                        st.rerun()
                                    else:
                                        st.error(msg)
                            if st.button(
                                f"Teardown All {num_existing} Workspaces for `{tbl_name}`",
                                key="ws_view_del_all_btn",
                                type="primary",
                                use_container_width=True,
                            ):
                                del_ok, del_msg, del_cnt = delete_all_workspaces(
                                    engine, db_name, source_table=tbl_name
                                )
                                st.success(del_msg)
                                st.rerun()
                    else:
                        render_html(f"""
                            <div class="safety-banner" style="margin-bottom: 1rem;">
                                <div class="safety-banner-icon"></div>
                                <div class="safety-banner-content">
                                    <h4>No Cleaning Workspace Exists Yet for <code>{db_name}.{tbl_name}</code></h4>
                                    <p>Provision an isolated sandbox copy to safely clean and transform data without modifying production tables.</p>
                                </div>
                            </div>
                            """)
                        btn_s1, btn_s2 = st.columns([1.8, 2.5])
                        with btn_s1:
                            if st.button(
                                "Create Cleaning Workspace",
                                type="secondary",
                                use_container_width=True,
                                key="ws_view_create_btn",
                            ):
                                with st.spinner(
                                    "Provisioning isolated workspace copy..."
                                ):
                                    success, msg, details = create_workspace(
                                        engine, db_name, tbl_name
                                    )
                                if success:
                                    st.session_state.working_table_name = details[
                                        "working_table_name"
                                    ]
                                    st.session_state.working_table_status = details[
                                        "status"
                                    ]
                                    st.session_state.working_table_details = details
                                    st.session_state.profile_result = None
                                    st.success(msg)
                                    st.rerun()
                                else:
                                    st.error(msg)
                        with btn_s2:
                            if st.button(
                                "Return to Source Table",
                                type="secondary",
                                use_container_width=False,
                                key="ws_view_back_btn",
                            ):
                                nav_to_view("Source Table")
                                st.rerun()
                else:
                    working_tbl = st.session_state.working_table_name

                    try:
                        workspace_info = get_workspace_info(
                            engine, db_name, working_tbl
                        )
                    except Exception as e:
                        workspace_info = None
                        st.error(f"Error reading workspace: {str(e)}")

                    # ---------------------------------------------
                    # Sandbox Guarantee Banner (Slim Info Strip)
                    # ---------------------------------------------
                    _ws_row_count = workspace_info.get("row_count") if workspace_info else None
                    render_sandbox_banner(
                        working_table=working_tbl,
                        source_table=f"{db_name}.{tbl_name}",
                        row_count=_ws_row_count,
                    )

                    if workspace_info:
                        _ai_page_rendered = False
                        if st.session_state.get("workspace_sub_tab") == "🤖 AI Assistant":
                            render_ai_assistant_main(
                                on_back_to_hub=lambda: nav_to_view("🧹 Cleaning Workspace", "🏠 Cleaning Hub")
                            )
                            _ai_page_rendered = True
                            active_sub = "🤖 AI Assistant"
                        else:
                            active_sub = render_cleaning_tabs()

                        # =========================================
                        # SUB-VIEW 1: Overview & Cleaning Hub
                        # =========================================
                        if active_sub == "🏠 Cleaning Hub":
                            render_section_header("Workspace metrics")

                            details = (
                                st.session_state.get("working_table_details") or {}
                            )
                            src_rows = details.get("source_row_count", 0)
                            # If src_rows <= 0, attempt to query the real source table baseline count
                            if src_rows <= 0 and engine and db_name:
                                try:
                                    src_tbl_guess = details.get("source_table") or tbl_name
                                    q_src = _quote_table(db_name, src_tbl_guess)
                                    with engine.connect() as _c:
                                        _res = _c.execute(text(f"SELECT COUNT(*) FROM {q_src}"))
                                        src_rows = _res.scalar() or 0
                                        details["source_row_count"] = src_rows
                                        st.session_state.working_table_details = details
                                except Exception:
                                    src_rows = 0

                            work_rows = workspace_info.get("row_count", 0)

                            # Hide internal columns starting with '__' (e.g. __bool_backup_is_active)
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

                            visible_schema = [
                                c for c in workspace_info.get("schema", [])
                                if not _is_internal_col(c)
                            ]
                            col_count = len(visible_schema)

                            # If source row count is valid, display all 3 cards; if not available, hide Source Rows
                            if src_rows > 0:
                                k1, k2, k3 = st.columns(3)
                                with k1:
                                    render_metric_card(
                                        "Source Rows",
                                        src_rows,
                                        hint="Original baseline count",
                                    )
                                with k2:
                                    render_metric_card(
                                        "Working Copy Rows",
                                        work_rows,
                                        hint="Active in sandbox",
                                    )
                                with k3:
                                    render_metric_card(
                                        "Schema Columns",
                                        col_count,
                                        hint="Available for transformations",
                                    )
                            else:
                                k1, k2 = st.columns(2)
                                with k1:
                                    render_metric_card(
                                        "Working Copy Rows",
                                        work_rows,
                                        hint="Active in sandbox",
                                    )
                                with k2:
                                    render_metric_card(
                                        "Schema Columns",
                                        col_count,
                                        hint="Available for transformations",
                                    )

                            # Workspace Data Preview
                            prev_col1, prev_col2 = st.columns([3.2, 1.4], vertical_alignment="center")
                            with prev_col1:
                                render_html(
                                    '<div class="dc-preview-header">'
                                    '<h2 class="dc-section-title">Workspace data preview</h2>'
                                    "</div>"
                                )
                            with prev_col2:
                                if st.button(
                                    "Refresh preview",
                                    use_container_width=False,
                                    key="hub_refresh_preview_btn",
                                    help="Re-fetch latest data from workspace after cleaning operations",
                                ):
                                    st.rerun()

                            if not workspace_info["preview"].empty:
                                preview_df = workspace_info["preview"]
                                display_cols = [
                                    c for c in preview_df.columns
                                    if not str(c).startswith("__")
                                ]
                                render_data_table(
                                    preview_df[display_cols],
                                    max_rows=50,
                                    total_rows=work_rows,
                                )
                            else:
                                render_alert(
                                    "info",
                                    "No workspace data",
                                    "The cleaning workspace currently has no rows.",
                                )

                            # Operation 7: Profiler Card
                            with st.container(border=True):
                                prof_col1, prof_col2 = st.columns([2.5, 1.5], vertical_alignment="center")
                                with prof_col1:
                                    badge_markup = (
                                        render_badge("valid", "Profile generated", as_string=True)
                                        if st.session_state.get("profile_result")
                                        else ""
                                    )
                                    badge_html = f'<div class="dc-profiler-badge-wrapper">{badge_markup}</div>' if badge_markup else ""
                                    render_html(f"""
                                        <div class="dc-profiler-header-row">
                                             <div class="dc-profiler-title">Data quality profiler</div>
                                             {badge_html}
                                        </div>
                                        <div class="dc-profiler-desc">
                                             Run in-depth algorithmic quality checks for NULL distributions, duplicate row vectors, formatting anomalies, and statistical ranges inside the sandbox.
                                        </div>
                                    """)
                                with prof_col2:
                                    if st.button(
                                        "View workspace profile",
                                        type="secondary",
                                        use_container_width=False,
                                        key="hub_open_profiler_btn",
                                    ):
                                        st.session_state.active_profile_target = (
                                            "workspace"
                                        )
                                        st.session_state.show_profile_dialog = True
                                        st.rerun()

                            # Danger Zone: Delete Workspace
                            render_section_header("Danger zone")

                            @st.dialog("Delete Cleaning Workspace")
                            def _confirm_delete_workspace_dialog(d_name: str, w_tbl: str):
                                st.markdown(
                                    f"Are you sure you want to delete the cleaning workspace table **`{w_tbl}`**?"
                                )
                                st.markdown(
                                    "This drops the temporary working copy. Your source table is not affected."
                                )
                                d_c1, d_c2 = st.columns(2)
                                with d_c1:
                                    if st.button(
                                        "Delete workspace",
                                        type="primary",
                                        use_container_width=True,
                                        key="hub_teardown_confirm_btn",
                                    ):
                                        with st.spinner("Dropping workspace table..."):
                                            del_ok, del_msg = delete_workspace(
                                                engine, d_name, w_tbl
                                            )
                                        if del_ok:
                                            reset_workspace_state()
                                            st.success(del_msg)
                                            st.rerun()
                                        else:
                                            st.error(del_msg)
                                with d_c2:
                                    if st.button(
                                        "Cancel",
                                        use_container_width=True,
                                        key="hub_teardown_cancel_btn",
                                    ):
                                        st.rerun()

                            with st.container(border=True):
                                dz_col1, dz_col2 = st.columns([2.5, 1.5], vertical_alignment="center")
                                with dz_col1:
                                    render_html(f"""
                                        <div class="dc-danger-card-title">Delete cleaning workspace</div>
                                        <div class="dc-danger-card-desc">
                                            Drops the temporary copy <span class="dc-chip-slate">{html.escape(working_tbl)}</span>. Your source table is not affected.
                                        </div>
                                    """)
                                with dz_col2:
                                    if st.button(
                                        "Delete workspace",
                                        use_container_width=False,
                                        key="hub_teardown_ws_btn",
                                    ):
                                        _confirm_delete_workspace_dialog(db_name, working_tbl)

                        # =========================================
                        # SUB-VIEW 2: Whitespace Cleaning
                        # =========================================
                        elif active_sub == "✂️ Whitespace Cleaning":
                            if render_module_header(
                                title="Whitespace Normalization & Trimming",
                                subtitle="Execute automated whitespace trimming and regex collapsing across string and text columns in the sandbox copy.",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="ws_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                )
                                st.rerun()

                            ws_text_cols = get_text_columns(
                                engine, db_name, working_tbl
                            )
                            if not ws_text_cols:
                                st.info(
                                    "No text/string columns were detected in this table."
                                )
                            else:
                                with st.container(border=True):
                                    st.markdown(
                                        f"""
                                        <div style="font-size: 0.88rem; color: var(--dq-slate); line-height: 1.5;">
                                            <b>Target Text Columns ({len(ws_text_cols)}):</b>
                                        </div>
                                        <div style="margin-top: 0.35rem; display: flex; flex-wrap: wrap; gap: 0.4rem;">
                                            {''.join([f'<span class="badge-pill badge-neutral" style="font-family: var(--font-mono); font-size: 0.8rem;">{c}</span>' for c in ws_text_cols])}
                                        </div>
                                        <div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-top: 0.75rem;">
                                            This transformation runs directly in MySQL using <code>TRIM(REGEXP_REPLACE(col, '[[:space:]]+', ' '))</code>.
                                            Primary keys, indexes, and source production data are strictly protected.
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )

                                    ws_run_btn = st.button(
                                        "Clean Whitespace Across All Text Columns",
                                        type="secondary",
                                        use_container_width=True,
                                        key="run_whitespace_clean_action_btn",
                                    )

                                if ws_run_btn:
                                    with st.spinner(
                                        "Executing whitespace cleaning on text columns..."
                                    ):
                                        success, msg, report = (
                                            remove_whitespace_workspace(
                                                engine, db_name, working_tbl
                                            )
                                        )
                                    if success:
                                        st.session_state.cleaning_report = report
                                        st.session_state.profile_result = None
                                        st.success(f"{msg}")
                                        st.rerun()
                                    else:
                                        st.error(f"{msg}")

                            # Dedicated Executive Whitespace Cleaning Report
                            if st.session_state.get("cleaning_report"):
                                report = st.session_state.cleaning_report
                                total_changed = report.get("total_values_changed", 0)
                                cols_affected = len(report.get("columns_affected", []))
                                rows_affected = report.get("rows_affected", 0)

                                st.markdown(
                                    '<div class="dq-section-title" style="margin-top: 1.5rem;"> Executive Whitespace Cleaning Report</div>',
                                    unsafe_allow_html=True,
                                )

                                with st.container(border=True):
                                    if total_changed == 0:
                                        st.info(
                                            "No whitespace inconsistencies were found. All string columns were already normalized."
                                        )
                                    else:
                                        st.success(
                                            "Whitespace transformation successfully committed to the workspace sandbox."
                                        )
                                        c_kpi1, c_kpi2, c_kpi3 = st.columns(3)
                                        with c_kpi1:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card kpi-card-success">
                                                    <div class="kpi-label">Values Cleaned</div>
                                                    <div class="kpi-value">{total_changed:,}</div>
                                                    <div class="kpi-subtext">Strings normalized</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                        with c_kpi2:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card">
                                                    <div class="kpi-label">Columns Affected</div>
                                                    <div class="kpi-value">{cols_affected}</div>
                                                    <div class="kpi-subtext">Transformed attributes</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                        with c_kpi3:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card">
                                                    <div class="kpi-label">Unique Rows Affected</div>
                                                    <div class="kpi-value">{rows_affected:,}</div>
                                                    <div class="kpi-subtext">Rows updated in sandbox</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )

                                        st.markdown(
                                            "##### Column-Level Impact Breakdown"
                                        )
                                        column_reports = report.get(
                                            "columns_affected", []
                                        )
                                        if column_reports:
                                            rep_df = pd.DataFrame(
                                                column_reports
                                            ).rename(
                                                columns={
                                                    "column": "Column Name",
                                                    "values_changed": "Values Cleaned",
                                                }
                                            )
                                            st.dataframe(
                                                rep_df,
                                                use_container_width=True,
                                                hide_index=True,
                                                column_config={
                                                    "Values Cleaned": st.column_config.ProgressColumn(
                                                        "Values Cleaned",
                                                        help="Number of values normalized in this column",
                                                        format="%d",
                                                        min_value=0,
                                                        max_value=max(
                                                            [
                                                                c["values_changed"]
                                                                for c in column_reports
                                                            ]
                                                            or [10]
                                                        ),
                                                    )
                                                },
                                            )

                                    col_ws_next, _ = st.columns([2, 3])
                                    with col_ws_next:
                                        if st.button(
                                            "Proceed to Blank & NULL Cleaning",
                                            type="secondary",
                                            use_container_width=True,
                                            key="ws_proceed_to_blanks_btn",
                                        ):
                                            nav_to_view(
                                                "🧹 Cleaning Workspace",
                                                "📝 Blank & NULL Values",
                                            )
                                            st.rerun()

                        # =========================================
                        # SUB-VIEW 3: Missing Value Cleaning
                        # =========================================
                        elif active_sub == "📝 Blank & NULL Values":
                            if render_module_header(
                                title="Missing Value Cleaning",
                                subtitle="Scan for NULL / missing values, select columns, then replace them in one operation.",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="ws_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                )
                                st.rerun()

                            # Session state init
                            if "mv_scan_results" not in st.session_state:
                                st.session_state.mv_scan_results = None
                            if "mv_selected_columns" not in st.session_state:
                                st.session_state.mv_selected_columns = []
                            if "mv_scan_done" not in st.session_state:
                                st.session_state.mv_scan_done = False

                            # ---- Scan button ----
                            if not st.session_state.mv_scan_done:
                                if st.button(
                                    "Scan and detect",
                                    type="secondary",
                                    use_container_width=True,
                                    key="mv_scan_btn",
                                ):
                                    with st.spinner(
                                        "Scanning table for missing values..."
                                    ):
                                        st.session_state.mv_scan_results = (
                                            scan_missing_values(
                                                engine, db_name, working_tbl
                                            )
                                        )
                                        st.session_state.mv_scan_done = True
                                        st.session_state.mv_selected_columns = []
                                    st.rerun()
                            else:
                                scan_results = st.session_state.mv_scan_results
                                if not scan_results:
                                    st.info(
                                        "No supported nullable columns found in this table."
                                    )
                                else:
                                    problem_cols = [
                                        c for c in scan_results if c["has_issues"]
                                    ]
                                    total_cols = len(scan_results)

                                    # Summary banner
                                    if problem_cols:
                                        render_html(f"""
                                            <div class="safety-banner" style="border-color: var(--dq-warning-border); background: var(--dq-warning-bg); margin-bottom: 1rem;">
                                                <div class="safety-banner-content">
                                                    <h4 style="color: var(--dq-warning);">{len(problem_cols)} of {total_cols} Column(s) Have Missing Values</h4>
                                                    <p>Columns with NULL / blank / whitespace detected.</p>
                                                </div>
                                            </div>
                                            """)
                                    else:
                                        render_html(f"""
                                            <div class="safety-banner" style="border-color: var(--dq-success-border); background: var(--dq-success-bg); margin-bottom: 1rem;">
                                                <div class="safety-banner-icon"></div>
                                                <div class="safety-banner-content">
                                                    <h4 style="color: var(--dq-success);">All {total_cols} Column(s) Are Clean!</h4>
                                                    <p>Zero missing values detected.</p>
                                                </div>
                                            </div>
                                            """)

                                    # Layout: two vertical sections side by side
                                    left_col, right_col = st.columns(
                                        [1, 1], gap="large"
                                    )

                                    # ---------- LEFT: Columns detected ----------
                                    with left_col:
                                        st.markdown(
                                            "### Columns detected which have null and missing values"
                                        )
                                        # Select all / Deselect all buttons
                                        if problem_cols:
                                            sel_col, desel_col = st.columns(2)
                                            with sel_col:
                                                if st.button(
                                                    "Select All",
                                                    key="mv_select_all_btn",
                                                    use_container_width=True,
                                                ):
                                                    st.session_state.mv_selected_columns = [
                                                        c["column"]
                                                        for c in problem_cols
                                                    ]
                                                    # also tick the checkboxes
                                                    for c in problem_cols:
                                                        st.session_state[
                                                            f"mv_chk_{c['column']}"
                                                        ] = True
                                                    st.rerun()
                                            with desel_col:
                                                if st.button(
                                                    "Deselect All",
                                                    key="mv_deselect_all_btn",
                                                    use_container_width=True,
                                                ):
                                                    st.session_state.mv_selected_columns = (
                                                        []
                                                    )
                                                    for c in problem_cols:
                                                        st.session_state[
                                                            f"mv_chk_{c['column']}"
                                                        ] = False
                                                    st.rerun()

                                        for col_info in problem_cols:
                                            c_name = col_info["column"]
                                            data_type = col_info["data_type"].upper()
                                            type_cat = col_info["type_category"]
                                            n_cnt = col_info["null_count"]
                                            b_cnt = col_info["blank_count"]
                                            tot = col_info["total_missing"]
                                            checked = (
                                                c_name
                                                in st.session_state.mv_selected_columns
                                            )
                                            new_checked = st.checkbox(
                                                f"`{c_name}` ({data_type}) — {tot:,} missing (NULL:{n_cnt:,}"
                                                + (
                                                    f", blank:{b_cnt:,}"
                                                    if type_cat == "text"
                                                    else ""
                                                )
                                                + ")",
                                                value=checked,
                                                key=f"mv_chk_{c_name}",
                                            )
                                            if new_checked != checked:
                                                if new_checked:
                                                    st.session_state.mv_selected_columns.append(
                                                        c_name
                                                    )
                                                else:
                                                    st.session_state.mv_selected_columns.remove(
                                                        c_name
                                                    )
                                                st.rerun()

                                    # ---------- RIGHT: Operational ----------
                                    with right_col:
                                        st.markdown("### Operation")
                                        if st.session_state.mv_selected_columns:
                                            # Show selected columns transparently
                                            st.write("**Selected columns:**")
                                            for (
                                                col_name
                                            ) in st.session_state.mv_selected_columns:
                                                st.markdown(f"- `{col_name}`")
                                            scope = st.radio(
                                                "What to replace",
                                                options=[
                                                    "Missing values only (empty/whitespace)",
                                                    "NULL values only",
                                                    "Both missing and NULL",
                                                ],
                                                key="mv_scope_radio",
                                                horizontal=False,
                                            )
                                            repl_text = st.text_input(
                                                "Replacement value",
                                                value="N/A",
                                                key="mv_repl_text",
                                                help="Examples: N/A, Unknown, 0, 1970-01-01, true",
                                            )
                                            st.caption(
                                                "Examples: `N/A`, `Unknown`, `0`, `1970-01-01`, `true`"
                                            )
                                            if st.button(
                                                "Replace All",
                                                type="primary",
                                                use_container_width=True,
                                                key="mv_replace_all_btn",
                                            ):
                                                # Separate text and non-text columns
                                                text_cols = []
                                                nontext_cols = []
                                                for col_name in list(
                                                    st.session_state.mv_selected_columns
                                                ):
                                                    col_info = next(
                                                        c
                                                        for c in scan_results
                                                        if c["column"] == col_name
                                                    )
                                                    if (
                                                        col_info["type_category"]
                                                        == "text"
                                                    ):
                                                        text_cols.append(col_name)
                                                    else:
                                                        nontext_cols.append(col_name)

                                                all_reports = []

                                                # 1. Process text columns immediately
                                                for col_name in text_cols:
                                                    col_info = next(
                                                        c
                                                        for c in scan_results
                                                        if c["column"] == col_name
                                                    )
                                                    target_mode_map = {
                                                        "Missing values only (empty/whitespace)": "blanks",
                                                        "NULL values only": "nulls",
                                                        "Both missing and NULL": "both",
                                                    }
                                                    target_mode = target_mode_map[scope]
                                                    with st.spinner(
                                                        f"Replacing in `{col_name}`..."
                                                    ):
                                                        ok, msg, report = (
                                                            replace_blank_values_workspace(
                                                                engine,
                                                                db_name,
                                                                working_tbl,
                                                                col_name,
                                                                repl_text,
                                                                target_mode=target_mode,
                                                            )
                                                        )
                                                        if ok:
                                                            all_reports.append(report)
                                                            scope_desc = {
                                                                "Missing values only (empty/whitespace)": "blank/whitespace values",
                                                                "NULL values only": "NULL values",
                                                                "Both missing and NULL": "NULL and blank values",
                                                            }[scope]
                                                            st.success(
                                                                f"`{col_name}`: replaced {report.get('values_replaced',0)} {scope_desc} with `{repl_text}`."
                                                            )
                                                        else:
                                                            st.error(
                                                                f"`{col_name}`: {msg}"
                                                            )

                                                # 2. If there are non‑text columns, ask user what to do with them
                                                if nontext_cols:
                                                    # Store pending state for confirmation step
                                                    st.session_state.mv_nontext_confirm = {
                                                        "cols": nontext_cols,
                                                        "scope": scope,
                                                        "repl_text": repl_text,
                                                        "text_reports": all_reports,
                                                        "step": "awaiting",
                                                    }
                                                    st.rerun()

                                                # 3. No non‑text columns → finalize
                                                if all_reports:
                                                    st.session_state.mv_selected_columns = (
                                                        []
                                                    )
                                                    st.session_state.mv_scan_done = (
                                                        False
                                                    )
                                                    st.session_state.mv_cleaning_report = {
                                                        "columns": all_reports,
                                                        "timestamp": datetime.now().isoformat(),
                                                    }
                                                    st.session_state.profile_result = (
                                                        None
                                                    )
                                                    st.rerun()

                                            # ---- Confirmation UI for non‑text columns ----
                                            if (
                                                "mv_nontext_confirm" in st.session_state
                                                and st.session_state.mv_nontext_confirm.get(
                                                    "step"
                                                )
                                                == "awaiting"
                                            ):
                                                conf = (
                                                    st.session_state.mv_nontext_confirm
                                                )
                                                st.warning(
                                                    "The following columns are not text type. Custom text cannot be used to replace NULL/missing values."
                                                )
                                                decisions = {}
                                                for col_name in conf["cols"]:
                                                    col_info = next(
                                                        c
                                                        for c in scan_results
                                                        if c["column"] == col_name
                                                    )
                                                    dtype = col_info[
                                                        "data_type"
                                                    ].upper()
                                                    st.write(
                                                        f"**{col_name}** ({dtype})"
                                                    )
                                                    choice = st.radio(
                                                        f"Replace NULLs in `{col_name}` with NULL (keep NULL)?",
                                                        options=[
                                                            "Yes – keep NULL (no change)",
                                                            "No – skip this column",
                                                        ],
                                                        key=f"mv_confirm_{col_name}",
                                                        horizontal=True,
                                                    )
                                                    decisions[col_name] = (
                                                        choice
                                                        == "Yes – keep NULL (no change)"
                                                    )
                                                col_decide, col_cancel = st.columns(2)
                                                with col_decide:
                                                    if st.button(
                                                        "Confirm",
                                                        key="mv_confirm_ok_btn",
                                                        type="primary",
                                                    ):
                                                        conf["decisions"] = decisions
                                                        conf["step"] = "confirmed"
                                                        st.rerun()
                                                with col_cancel:
                                                    if st.button(
                                                        "Cancel",
                                                        key="mv_confirm_cancel_btn",
                                                    ):
                                                        # Finalize with only text reports
                                                        text_reports = conf.get(
                                                            "text_reports", []
                                                        )
                                                        st.session_state.mv_selected_columns = (
                                                            []
                                                        )
                                                        st.session_state.mv_scan_done = (
                                                            False
                                                        )
                                                        st.session_state.mv_cleaning_report = {
                                                            "columns": text_reports,
                                                            "timestamp": datetime.now().isoformat(),
                                                        }
                                                        st.session_state.profile_result = (
                                                            None
                                                        )
                                                        del (
                                                            st.session_state.mv_nontext_confirm
                                                        )
                                                        st.rerun()
                                                st.stop()

                                            # ---- Process non‑text columns after confirmation ----
                                            if (
                                                "mv_nontext_confirm" in st.session_state
                                                and st.session_state.mv_nontext_confirm.get(
                                                    "step"
                                                )
                                                == "confirmed"
                                            ):
                                                conf = (
                                                    st.session_state.mv_nontext_confirm
                                                )
                                                decisions = conf.get("decisions", {})
                                                text_reports = conf.get(
                                                    "text_reports", []
                                                )
                                                all_reports = list(text_reports)

                                                for col_name in conf["cols"]:
                                                    keep_null = decisions.get(
                                                        col_name, False
                                                    )
                                                    if keep_null:
                                                        report = {
                                                            "operation": "Missing Value Cleaning",
                                                            "strategy": "keep_null",
                                                            "column": col_name,
                                                            "data_type": next(
                                                                c
                                                                for c in scan_results
                                                                if c["column"]
                                                                == col_name
                                                            )["data_type"],
                                                            "type_category": next(
                                                                c
                                                                for c in scan_results
                                                                if c["column"]
                                                                == col_name
                                                            )["type_category"],
                                                            "values_replaced": 0,
                                                            "total_values_changed": 0,
                                                        }
                                                        all_reports.append(report)
                                                        st.info(
                                                            f"`{col_name}`: kept NULL (no change)."
                                                        )
                                                    else:
                                                        st.warning(
                                                            f"`{col_name}`: skipped as per user choice."
                                                        )

                                                # Finalize
                                                st.session_state.mv_selected_columns = (
                                                    []
                                                )
                                                st.session_state.mv_scan_done = False
                                                st.session_state.mv_cleaning_report = {
                                                    "columns": all_reports,
                                                    "timestamp": datetime.now().isoformat(),
                                                }
                                                st.session_state.profile_result = None
                                                del st.session_state.mv_nontext_confirm
                                                st.rerun()
                                        else:
                                            st.info(
                                                "Select columns on the left to enable replacement options."
                                            )

                            # Dedicated Missing Value Cleaning Audit Report
                            if st.session_state.get("mv_cleaning_report"):
                                mv_rep = st.session_state.mv_cleaning_report
                                st.markdown(
                                    '<div class="dq-section-title" style="margin-top: 1.5rem;"> Missing Value Cleaning Audit Report</div>',
                                    unsafe_allow_html=True,
                                )
                                with st.container(border=True):
                                    if not mv_rep.get("columns"):
                                        st.info("No columns were processed.")
                                    else:
                                        st.success(
                                            f"Value replacement successfully committed to `{working_tbl}`."
                                        )
                                        for rep in mv_rep["columns"]:
                                            st.markdown("---")
                                            st.markdown(
                                                f"#### Column: `{rep.get('column', '')}`"
                                            )
                                            k1, k2, k3, k4 = st.columns(4)
                                            with k1:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card kpi-card-success">
                                                        <div class="kpi-label">Values Replaced</div>
                                                        <div class="kpi-value">{rep.get('values_replaced', 0):,}</div>
                                                        <div class="kpi-subtext">Rows updated in sandbox</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )
                                            with k2:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card">
                                                        <div class="kpi-label">Data Type</div>
                                                        <div class="kpi-value" style="font-size: 1.3rem; font-family: var(--font-mono);">{rep.get('data_type', '').upper()}</div>
                                                        <div class="kpi-subtext">Category: {rep.get('type_category', '')}</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )
                                            with k3:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card">
                                                        <div class="kpi-label">Strategy</div>
                                                        <div class="kpi-value" style="font-size: 1.3rem; font-family: var(--font-mono);">{rep.get('strategy', '').replace('_', ' ').title()}</div>
                                                        <div class="kpi-subtext">Replacement approach</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )
                                            with k4:
                                                repl_val = rep.get(
                                                    "replacement_value", ""
                                                )
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card">
                                                        <div class="kpi-label">Replacement Value</div>
                                                        <div class="kpi-value" style="font-size: 1.3rem; font-family: var(--font-mono); color: var(--dq-accent);">{repl_val}</div>
                                                        <div class="kpi-subtext">Substituted value</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )

                            # Reset scan button
                            if st.session_state.mv_scan_done:
                                if st.button("New Scan", key="mv_new_scan_btn"):
                                    st.session_state.mv_scan_done = False
                                    st.session_state.mv_scan_results = None
                                    st.session_state.mv_selected_columns = []
                                    st.rerun()

                            col_b_next, _ = st.columns([2, 3])
                            with col_b_next:
                                if st.button(
                                    "Proceed to Text Casing",
                                    type="secondary",
                                    key="blanks_proceed_to_casing_btn",
                                ):
                                    st.session_state.workspace_sub_tab = (
                                        "🔤 Text Casing"
                                    )
                                    st.rerun()
                        # =========================================
                        # SUB-VIEW 4: 🔤 Text Casing Normalization
                        # =========================================
                        elif active_sub == "🔤 Text Casing":
                            if render_module_header(
                                title="Text Casing Normalization",
                                subtitle="Standardize text capitalization to lowercase, UPPERCASE, or Title Case across text columns in the sandbox. The original source table is never modified.",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="casing_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                )
                                st.rerun()

                            text_cols = get_text_columns(engine, db_name, working_tbl)

                            if not text_cols:
                                st.markdown(
                                    """
                                    <div class="empty-state-card">
                                        <div class="es-title">No Text Columns Found</div>
                                        <div class="es-desc">This table has no string or text columns eligible for text casing normalization.</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                with st.container(border=True):
                                    cfg_col1, cfg_col2 = st.columns([3, 2])
                                    with cfg_col1:
                                        target_cols = st.multiselect(
                                            "Select Column(s)",
                                            options=text_cols,
                                            default=text_cols,
                                            key="casing_target_cols_select",
                                            help="Select one or more text columns to normalize casing in one go.",
                                        )
                                    with cfg_col2:
                                        casing_format = st.selectbox(
                                            "Case Format",
                                            options=[
                                                "Title Case",
                                                "lowercase",
                                                "UPPERCASE",
                                            ],
                                            key="casing_format_choice_select",
                                            help="Choose target capitalization format.",
                                        )

                                    if not target_cols:
                                        st.markdown(
                                            """
                                            <div class="empty-state-card" style="padding: 1.5rem; margin-top: 0.5rem;">
                                                <div class="es-title">Select at least one column above</div>
                                                <div class="es-desc">Choose one or more text columns to normalize text casing in one go.</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    else:
                                        with st.spinner(
                                            "Calculating values that will change..."
                                        ):
                                            values_to_change = (
                                                count_text_casing_changes(
                                                    engine,
                                                    db_name,
                                                    working_tbl,
                                                    target_cols,
                                                    casing_format,
                                                )
                                            )

                                        change_color = (
                                            "var(--dq-accent)"
                                            if values_to_change > 0
                                            else "var(--dq-success)"
                                        )
                                        change_text = (
                                            f"{values_to_change:,}"
                                            if values_to_change > 0
                                            else "0 (Already normalized)"
                                        )

                                        cols_display = (
                                            f"<code style='font-family: var(--font-mono);'>{target_cols[0]}</code>"
                                            if len(target_cols) == 1
                                            else f"<strong>{len(target_cols)} columns</strong> ({', '.join(target_cols[:3])}{'...' if len(target_cols) > 3 else ''})"
                                        )

                                        st.markdown(
                                            f"""
                                            <div style="background: var(--dq-bg-soft); border: 1px solid var(--dq-border); border-radius: 8px; padding: 0.85rem 1.1rem; margin: 0.85rem 0 1rem 0;">
                                                <div style="font-size: 0.78rem; font-weight: 700; color: var(--dq-slate-muted); text-transform: uppercase; letter-spacing: 0.05em;">
                                                    Operation Preview
                                                </div>
                                                <div style="display: flex; gap: 2rem; margin-top: 0.4rem; flex-wrap: wrap; font-size: 0.9rem;">
                                                    <div><span style="color: var(--dq-slate-muted);">Target Column(s):</span> <span style="color: var(--dq-slate-text);">{cols_display}</span></div>
                                                    <div><span style="color: var(--dq-slate-muted);">Case Format:</span> <strong style="color: var(--dq-slate-text);">{casing_format}</strong></div>
                                                    <div><span style="color: var(--dq-slate-muted);">Values That Will Change:</span> <strong style="color: {change_color}; font-size: 1.05rem;">{change_text}</strong></div>
                                                </div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )

                                        btn_label = (
                                            f"Apply Text Casing to `{target_cols[0]}`"
                                            if len(target_cols) == 1
                                            else f"Apply Text Casing to {len(target_cols)} Column(s)"
                                        )
                                        apply_casing_btn = st.button(
                                            btn_label,
                                            type="secondary",
                                            use_container_width=True,
                                            key="apply_text_casing_btn",
                                        )

                                        if apply_casing_btn:
                                            if values_to_change == 0:
                                                if len(target_cols) == 1:
                                                    st.info(
                                                        f"All values in column `{target_cols[0]}` are already in {casing_format}. No values were changed."
                                                    )
                                                else:
                                                    st.info(
                                                        f"All values across the {len(target_cols)} selected column(s) are already in {casing_format}. No values were changed."
                                                    )
                                            else:
                                                spin_label = (
                                                    f"Normalizing '{target_cols[0]}' to {casing_format}..."
                                                    if len(target_cols) == 1
                                                    else f"Normalizing {len(target_cols)} columns to {casing_format} in one go..."
                                                )
                                                with st.spinner(spin_label):
                                                    c_ok, c_msg, c_report = (
                                                        normalize_text_case_workspace(
                                                            engine,
                                                            db_name,
                                                            working_tbl,
                                                            target_cols,
                                                            casing_format,
                                                        )
                                                    )
                                                if c_ok:
                                                    st.session_state.casing_cleaning_report = (
                                                        c_report
                                                    )
                                                    st.session_state.profile_result = (
                                                        None
                                                    )
                                                    st.success(f"{c_msg}")
                                                    st.rerun()
                                                else:
                                                    st.error(f"{c_msg}")

                            # Dedicated Audit Report
                            if st.session_state.get("casing_cleaning_report"):
                                c_rep = st.session_state.casing_cleaning_report
                                c_col_name = c_rep.get("column", "")
                                c_cols = c_rep.get(
                                    "columns", [c_col_name] if c_col_name else []
                                )
                                c_format = c_rep.get("case_type", "")
                                c_changed = c_rep.get("values_changed", 0)
                                c_affected = c_rep.get("columns_affected", [])

                                st.markdown(
                                    '<div class="dq-section-title" style="margin-top: 1.5rem;"> Text Casing Normalization Audit Report</div>',
                                    unsafe_allow_html=True,
                                )
                                with st.container(border=True):
                                    if c_changed == 0:
                                        if len(c_cols) > 1:
                                            st.info(
                                                f"All values across the {len(c_cols)} selected column(s) were already formatted as {c_format}. No values were changed."
                                            )
                                        else:
                                            st.info(
                                                f"All values in column `{c_col_name}` were already formatted as {c_format}. No values were changed."
                                            )
                                    else:
                                        st.success(
                                            f"Text casing normalization completed across {len(c_cols)} column(s)."
                                            if len(c_cols) > 1
                                            else f"Text casing normalization completed for `{c_col_name}`."
                                        )
                                        ck1, ck2, ck3, ck4 = st.columns(4)
                                        with ck1:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card">
                                                    <div class="kpi-label">Operation</div>
                                                    <div class="kpi-value" style="font-size: 1.2rem;">Text Casing</div>
                                                    <div class="kpi-subtext">Capitalization hygiene</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                        with ck2:
                                            target_val = (
                                                c_col_name
                                                if len(c_cols) <= 1
                                                else f"{len(c_cols)} Columns"
                                            )
                                            sub_val = (
                                                "Target attribute"
                                                if len(c_cols) <= 1
                                                else "Attributes normalized"
                                            )
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card">
                                                    <div class="kpi-label">Target</div>
                                                    <div class="kpi-value" style="font-size: 1.15rem; font-family: var(--font-mono);">{target_val}</div>
                                                    <div class="kpi-subtext">{sub_val}</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                        with ck3:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card">
                                                    <div class="kpi-label">Format</div>
                                                    <div class="kpi-value" style="font-size: 1.25rem;">{c_format}</div>
                                                    <div class="kpi-subtext">Applied casing style</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                        with ck4:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card kpi-card-success">
                                                    <div class="kpi-label">Values Changed</div>
                                                    <div class="kpi-value">{c_changed:,}</div>
                                                    <div class="kpi-subtext">Rows updated in sandbox</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )

                                        if len(c_cols) > 1 and c_affected:
                                            st.markdown(
                                                "##### Column-Level Impact Breakdown"
                                            )
                                            c_df = pd.DataFrame(c_affected).rename(
                                                columns={
                                                    "column": "Column Name",
                                                    "values_changed": "Values Normalized",
                                                }
                                            )
                                            st.dataframe(
                                                c_df,
                                                use_container_width=True,
                                                hide_index=True,
                                            )

                                    st.markdown(
                                        """
                                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 12px; border-top: 1px solid var(--border); padding-top: 8px;">
                                            Production table remains read-only. Changes applied strictly to the cleaning workspace.
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )

                                    col_c_next, _ = st.columns([2, 3])
                                    with col_c_next:
                                        if st.button(
                                            "Proceed to Duplicate Handling",
                                            type="secondary",
                                            key="casing_proceed_to_dup_btn",
                                        ):
                                            st.session_state.workspace_sub_tab = (
                                                "🔁 Duplicate Handling"
                                            )
                                            st.rerun()

                        # =========================================
                        # SUB-VIEW 5: Duplicate Handling
                        # =========================================
                        elif active_sub == "🔁 Duplicate Handling":
                            if render_module_header(
                                title="Duplicate Handling",
                                subtitle="Detect and remove duplicate records based on one or more duplicate key columns. The original source table is never modified.",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="dup_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace",
                                    "🏠 Cleaning Hub",
                                )
                                st.rerun()

                            inspector = inspect(engine)
                            table_cols_info = inspector.get_columns(
                                working_tbl, schema=db_name
                            )
                            all_table_cols = [c["name"] for c in table_cols_info]
                            pk_constraint = (
                                inspector.get_pk_constraint(working_tbl, schema=db_name)
                                or {}
                            )
                            pk_cols = pk_constraint.get("constrained_columns") or []
                            has_pk = bool(pk_cols)

                            if not all_table_cols:
                                st.markdown(
                                    """
                                    <div class="empty-state-card">
                                        <div class="es-title">No Columns Found</div>
                                        <div class="es-desc">This table has no accessible columns for duplicate detection.</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                with st.container(border=True):
                                    target_dup_cols = st.multiselect(
                                        "Duplicate Key Columns",
                                        options=all_table_cols,
                                        default=[all_table_cols[0]],
                                        key="dup_key_cols_select",
                                        help="Select one or more columns defining the duplicate key. Rows matching across all selected columns are grouped as duplicates.",
                                    )

                                    # Explanatory notices
                                    st.markdown(
                                        """
                                        <div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-top: 0.35rem;">
                                             <b>NULL &amp; Empty String Handling:</b> SQL NULL values are treated as equal for grouping. Empty strings (<code>''</code>) are also treated as equal.
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )

                                    if has_pk:
                                        pk_display = ", ".join(
                                            f"<code>{c}</code>" for c in pk_cols
                                        )
                                        st.markdown(
                                            f"""
                                            <div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-top: 0.25rem;">
                                                 <b>Deterministic Ordering:</b> Primary Key detected ({pk_display}). Rows are ordered by Primary Key ascending within each group.
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    else:
                                        st.markdown(
                                            """
                                            <div style="font-size: 0.82rem; color: #b45309; margin-top: 0.25rem;">
                                                 <b>No Primary Key:</b> Ordering uses available table columns as fallback. For completely identical duplicate rows, row retention order cannot be differentiated.
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )

                                    if not target_dup_cols:
                                        st.markdown(
                                            """
                                            <div class="empty-state-card" style="padding: 1.5rem; margin-top: 0.75rem;">
                                                <div class="es-title">Select at least one duplicate key column above</div>
                                                <div class="es-desc">Choose one or more columns to evaluate duplicate records.</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    else:
                                        with st.spinner(
                                            "Analyzing duplicate records in workspace..."
                                        ):
                                            det_ok, det_msg, det_report = (
                                                detect_duplicates_workspace(
                                                    engine,
                                                    db_name,
                                                    working_tbl,
                                                    target_dup_cols,
                                                    retention_strategy="Keep First",
                                                    preview_limit=100,
                                                )
                                            )

                                        if not det_ok:
                                            st.error(f"{det_msg}")
                                        else:
                                            dup_groups = det_report.get(
                                                "duplicate_group_count", 0
                                            )
                                            dup_rows = det_report.get(
                                                "duplicate_row_count", 0
                                            )
                                            detected_groups = det_report.get(
                                                "groups", []
                                            )

                                            keys_display = ", ".join(
                                                f"`{c}`" for c in target_dup_cols
                                            )

                                            if dup_rows == 0:
                                                st.info(
                                                    f"All records in `{working_tbl}` are unique across the selected key ({keys_display}). No duplicate rows were detected."
                                                )
                                            else:
                                                # ──────────────────────────────────────────────────────────
                                                # Checkbox Callbacks for Duplicate Selection
                                                # ──────────────────────────────────────────────────────────
                                                def handle_select_all_change(
                                                    gnum: int, g_rids: list
                                                ) -> None:
                                                    """
                                                    Callback when group-level 'Select All' checkbox toggles:
                                                    - If checked -> mark ALL rows in this group as REMOVE (True)
                                                    - If unchecked -> mark ALL rows in this group as KEEP (False)
                                                    """
                                                    is_sel_all = bool(
                                                        st.session_state.get(
                                                            f"dup_sel_all_{gnum}",
                                                            False,
                                                        )
                                                    )
                                                    st.session_state.duplicate_row_actions = apply_select_all_action(
                                                        st.session_state.duplicate_row_actions,
                                                        g_rids,
                                                        is_sel_all,
                                                    )
                                                    for rid in g_rids:
                                                        st.session_state[
                                                            f"dup_remove_{rid}"
                                                        ] = is_sel_all

                                                def handle_row_checkbox_change(
                                                    gnum: int,
                                                    g_rids: list,
                                                    changed_rid: Any,
                                                ) -> None:
                                                    """
                                                    Callback when an individual row checkbox toggles:
                                                    - CHECKED = REMOVE this record
                                                    - UNCHECKED = KEEP this record
                                                    - Synchronizes Select All checkbox: True if all checked, else False.
                                                    - Does NOT affect any other row.
                                                    """
                                                    is_checked = bool(
                                                        st.session_state.get(
                                                            f"dup_remove_{changed_rid}",
                                                            False,
                                                        )
                                                    )
                                                    st.session_state.duplicate_row_actions = toggle_row_remove_action(
                                                        st.session_state.duplicate_row_actions,
                                                        changed_rid,
                                                        is_checked,
                                                    )
                                                    st.session_state[
                                                        f"dup_sel_all_{gnum}"
                                                    ] = is_group_all_removed(
                                                        st.session_state.duplicate_row_actions,
                                                        g_rids,
                                                    )

                                                # ──────────────────────────────────────────────────────────
                                                # Initialize / align per-row checkbox state:
                                                # Default: row 0 is UNCHECKED (KEEP), rows 1..N are CHECKED (REMOVE)
                                                # ──────────────────────────────────────────────────────────
                                                if (
                                                    "duplicate_row_actions"
                                                    not in st.session_state
                                                    or not isinstance(
                                                        st.session_state.duplicate_row_actions,
                                                        dict,
                                                    )
                                                ):
                                                    st.session_state.duplicate_row_actions = (
                                                        {}
                                                    )

                                                all_detected_rids = {
                                                    r["row_id"]
                                                    for g in detected_groups
                                                    for r in g["rows"]
                                                }
                                                current_rids = set(
                                                    st.session_state.duplicate_row_actions.keys()
                                                )

                                                if current_rids != all_detected_rids:
                                                    st.session_state.duplicate_row_actions = init_duplicate_row_actions(
                                                        detected_groups
                                                    )
                                                    for g in detected_groups:
                                                        gnum = g["group_num"]
                                                        rows = g.get("rows", [])
                                                        for idx, r in enumerate(rows):
                                                            rid = r["row_id"]
                                                            act = st.session_state.duplicate_row_actions.get(
                                                                rid, "REMOVE"
                                                            )
                                                            st.session_state[
                                                                f"dup_remove_{rid}"
                                                            ] = (act == "REMOVE")
                                                        st.session_state[
                                                            f"dup_sel_all_{gnum}"
                                                        ] = is_group_all_removed(
                                                            st.session_state.duplicate_row_actions,
                                                            [r["row_id"] for r in rows],
                                                        )

                                                for g in detected_groups:
                                                    gnum = g["group_num"]
                                                    rows = g.get("rows", [])
                                                    g_rids = [r["row_id"] for r in rows]
                                                    for rid in g_rids:
                                                        if (
                                                            f"dup_remove_{rid}"
                                                            not in st.session_state
                                                        ):
                                                            act = st.session_state.duplicate_row_actions.get(
                                                                rid, "REMOVE"
                                                            )
                                                            st.session_state[
                                                                f"dup_remove_{rid}"
                                                            ] = (act == "REMOVE")
                                                    if (
                                                        f"dup_sel_all_{gnum}"
                                                        not in st.session_state
                                                    ):
                                                        st.session_state[
                                                            f"dup_sel_all_{gnum}"
                                                        ] = is_group_all_removed(
                                                            st.session_state.duplicate_row_actions,
                                                            g_rids,
                                                        )

                                                # Compute live summary counts
                                                total_keep = sum(
                                                    1
                                                    for g in detected_groups
                                                    for r in g["rows"]
                                                    if st.session_state.duplicate_row_actions.get(
                                                        r["row_id"], "KEEP"
                                                    )
                                                    == "KEEP"
                                                )
                                                total_remove = sum(
                                                    1
                                                    for g in detected_groups
                                                    for r in g["rows"]
                                                    if st.session_state.duplicate_row_actions.get(
                                                        r["row_id"], "KEEP"
                                                    )
                                                    == "REMOVE"
                                                )

                                                # ──────────────────────────────────────────────────────────
                                                # KPI summary bar
                                                # ──────────────────────────────────────────────────────────
                                                st.markdown(
                                                    f"""
                                                    <div style="background: var(--dq-bg-soft); border: 1px solid var(--dq-border); border-radius: 8px; padding: 0.85rem 1.1rem; margin: 0.85rem 0 1rem 0;">
                                                        <div style="font-size: 0.78rem; font-weight: 700; color: var(--dq-slate-muted); text-transform: uppercase; letter-spacing: 0.05em;">
                                                            Duplicate Detection &amp; Decision Overview
                                                        </div>
                                                        <div style="display: flex; gap: 2rem; margin-top: 0.4rem; flex-wrap: wrap; font-size: 0.9rem;">
                                                            <div><span style="color: var(--dq-slate-muted);">Duplicate Key:</span> <strong style="font-family: var(--font-mono); color: var(--dq-slate-text);">{keys_display}</strong></div>
                                                            <div><span style="color: var(--dq-slate-muted);">Duplicate Groups:</span> <strong style="color: var(--dq-slate-text);">{dup_groups:,}</strong></div>
                                                            <div><span style="color: var(--dq-slate-muted);">Rows in Duplicate Groups:</span> <strong style="color: var(--dq-slate-text);">{dup_rows:,}</strong></div>
                                                            <div><span style="color: var(--dq-slate-muted);">Rows Selected to Keep:</span> <strong style="color: var(--dq-success);">{total_keep:,}</strong></div>
                                                            <div><span style="color: var(--dq-slate-muted);">Rows Selected for Removal:</span> <strong style="color: var(--dq-danger); font-size: 1.05rem;">{total_remove:,}</strong></div>
                                                        </div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )

                                                st.markdown(
                                                    '<div style="font-size: 0.95rem; font-weight: 700; color: var(--dq-slate); margin: 1.25rem 0 0.5rem 0;">'
                                                    "Duplicate Groups — Select Records to Remove (Checked = REMOVE, Unchecked = KEEP):"
                                                    "</div>",
                                                    unsafe_allow_html=True,
                                                )

                                                # ──────────────────────────────────────────────────────────
                                                # Per-group tables with Remove checkbox, Select All, and Eye button
                                                # ──────────────────────────────────────────────────────────
                                                display_cols = []
                                                for pk in pk_cols:
                                                    if (
                                                        pk not in display_cols
                                                        and pk in all_table_cols
                                                    ):
                                                        display_cols.append(pk)
                                                for k in target_dup_cols:
                                                    if (
                                                        k not in display_cols
                                                        and k in all_table_cols
                                                    ):
                                                        display_cols.append(k)
                                                for c in all_table_cols:
                                                    if c not in display_cols:
                                                        display_cols.append(c)
                                                    if len(display_cols) >= 6:
                                                        break

                                                col_widths = [1.8, 0.6] + [2.2] * len(
                                                    display_cols
                                                )

                                                for g in detected_groups:
                                                    gnum = g["group_num"]
                                                    g_rids = [
                                                        row_item["row_id"]
                                                        for row_item in g["rows"]
                                                    ]
                                                    g_keys_str = " &nbsp;•&nbsp; ".join(
                                                        [
                                                            f"<b>{k}</b> = <code>{v}</code>"
                                                            for k, v in g[
                                                                "key_values"
                                                            ].items()
                                                        ]
                                                    )

                                                    with st.container(border=True):
                                                        st.markdown(
                                                            f"""
                                                            <div style='display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; margin-bottom: 0.2rem;'>
                                                                <div style='font-size: 1.02rem; font-weight: 800; color: var(--dq-slate-text);'>
                                                                    Duplicate Group #{gnum}
                                                                </div>
                                                                <div style='font-size: 0.8rem; color: var(--dq-slate-muted);'>
                                                                     Checked = <b style="color: var(--dq-danger);">REMOVE</b> &nbsp;|&nbsp; Unchecked = <b style="color: var(--dq-success);">KEEP</b>
                                                                </div>
                                                            </div>
                                                            <div style='font-size: 0.83rem; color: var(--dq-slate-muted); margin-bottom: 0.75rem;'>
                                                                <b>Duplicate Key:</b> {g_keys_str}
                                                            </div>
                                                            """,
                                                            unsafe_allow_html=True,
                                                        )

                                                        # Table Header: [Select All checkbox in Remove col] + [Eye / View col] + [Data cols]
                                                        h_cols = st.columns(col_widths)
                                                        with h_cols[0]:
                                                            st.checkbox(
                                                                "Select All",
                                                                key=f"dup_sel_all_{gnum}",
                                                                on_change=handle_select_all_change,
                                                                args=(gnum, g_rids),
                                                                help="Remove column header: Check to mark all rows in this group for REMOVAL; uncheck to KEEP all",
                                                            )
                                                        with h_cols[1]:
                                                            st.markdown(
                                                                "<div style='font-size: 0.82rem; font-weight: 700; color: var(--dq-slate-muted); padding-top: 5px; text-align: center;'></div>",
                                                                unsafe_allow_html=True,
                                                            )
                                                        for idx, c in enumerate(
                                                            display_cols
                                                        ):
                                                            with h_cols[2 + idx]:
                                                                st.markdown(
                                                                    f"<div style='font-size: 0.82rem; font-weight: 700; color: var(--dq-slate-muted); padding-top: 5px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;' title='{c}'>{c}</div>",
                                                                    unsafe_allow_html=True,
                                                                )

                                                        st.markdown(
                                                            "<hr style='margin: 0.25rem 0 0.5rem 0; border: none; border-top: 1px solid var(--dq-border);'>",
                                                            unsafe_allow_html=True,
                                                        )

                                                        # Table Rows
                                                        for r in g["rows"]:
                                                            rid = r["row_id"]
                                                            row_data = dict(
                                                                r["row_data"]
                                                            )
                                                            eye_key = f"dup_exp_{rid}"
                                                            is_exp = bool(
                                                                st.session_state.get(
                                                                    eye_key, False
                                                                )
                                                            )

                                                            r_cols = st.columns(
                                                                col_widths
                                                            )
                                                            with r_cols[0]:
                                                                st.checkbox(
                                                                    "Remove",
                                                                    key=f"dup_remove_{rid}",
                                                                    label_visibility="collapsed",
                                                                    on_change=handle_row_checkbox_change,
                                                                    args=(
                                                                        gnum,
                                                                        g_rids,
                                                                        rid,
                                                                    ),
                                                                    help="Checked = REMOVE, Unchecked = KEEP",
                                                                )
                                                            with r_cols[1]:
                                                                if st.button(
                                                                    "Details",
                                                                    key=f"btn_eye_{rid}",
                                                                    help="Toggle complete record details in scrollable table",
                                                                ):
                                                                    st.session_state[
                                                                        eye_key
                                                                    ] = not is_exp
                                                                    st.rerun()
                                                            for idx, c in enumerate(
                                                                display_cols
                                                            ):
                                                                with r_cols[2 + idx]:
                                                                    val = row_data.get(
                                                                        c
                                                                    )
                                                                    val_display = (
                                                                        '<span style="color: var(--dq-text-muted); font-style: italic;">NULL</span>'
                                                                        if val is None
                                                                        else str(val)
                                                                    )
                                                                    val_title = (
                                                                        str(val)
                                                                        if val
                                                                        is not None
                                                                        else "NULL"
                                                                    )
                                                                    st.markdown(
                                                                        f"<div style='font-size: 0.88rem; font-family: var(--font-mono); color: var(--dq-slate-text); padding-top: 4px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap;' title='{val_title}'>{val_display}</div>",
                                                                        unsafe_allow_html=True,
                                                                    )

                                                            # Expanded complete record view using st.dataframe
                                                            if is_exp:
                                                                df_exp = pd.DataFrame(
                                                                    [row_data]
                                                                )
                                                                st.markdown(
                                                                    f"<div style='font-size: 0.8rem; font-weight: 700; color: var(--dq-slate); margin: 0.35rem 0 0.15rem 0;'> Complete Record Details (All {len(row_data)} columns) — Row ID: <code>{rid}</code></div>",
                                                                    unsafe_allow_html=True,
                                                                )
                                                                st.dataframe(
                                                                    df_exp,
                                                                    use_container_width=True,
                                                                    hide_index=True,
                                                                )

                                                        st.divider()

                                                        # Group-level summary
                                                        g_rem = sum(
                                                            1
                                                            for r in g["rows"]
                                                            if st.session_state.duplicate_row_actions.get(
                                                                r["row_id"], "KEEP"
                                                            )
                                                            == "REMOVE"
                                                        )
                                                        g_keep = len(g["rows"]) - g_rem
                                                        st.markdown(
                                                            f"""
                                                            <div style='display: flex; gap: 1.5rem; font-size: 0.82rem; color: var(--dq-slate-muted);'>
                                                                <span>Group #{gnum} selection:</span>
                                                                <span> <b>{g_keep}</b> KEEP</span>
                                                                <span> <b>{g_rem}</b> REMOVE</span>
                                                            </div>
                                                            """,
                                                            unsafe_allow_html=True,
                                                        )

                                                # Recompute for button label after widgets rendered
                                                rows_to_remove = sum(
                                                    1
                                                    for g in detected_groups
                                                    for r in g["rows"]
                                                    if st.session_state.duplicate_row_actions.get(
                                                        r["row_id"], "KEEP"
                                                    )
                                                    == "REMOVE"
                                                )

                                                rem_dup_btn = st.button(
                                                    f"Remove Selected Duplicates ({rows_to_remove:,} rows)",
                                                    type="primary",
                                                    use_container_width=True,
                                                    key="apply_remove_duplicates_btn",
                                                    disabled=(rows_to_remove == 0),
                                                )

                                                if rem_dup_btn:
                                                    # Build row_actions dict from session state for all dup rows
                                                    row_actions_payload: Dict[
                                                        Any, str
                                                    ] = {}
                                                    for g in detected_groups:
                                                        for r in g["rows"]:
                                                            rid = r["row_id"]
                                                            row_actions_payload[rid] = (
                                                                st.session_state.duplicate_row_actions.get(
                                                                    rid, "KEEP"
                                                                )
                                                            )

                                                    with st.spinner(
                                                        "Executing safe duplicate removal in workspace..."
                                                    ):
                                                        rem_ok, rem_msg, rem_rep = (
                                                            remove_duplicates_by_row_ids(
                                                                engine,
                                                                db_name,
                                                                working_tbl,
                                                                target_dup_cols,
                                                                row_actions=row_actions_payload,
                                                            )
                                                        )

                                                    # Build per-group decision summary for audit report
                                                    group_decisions = []
                                                    for g in detected_groups:
                                                        kept_rows = [
                                                            r
                                                            for r in g["rows"]
                                                            if row_actions_payload.get(
                                                                r["row_id"], "KEEP"
                                                            )
                                                            == "KEEP"
                                                        ]
                                                        rem_rows = [
                                                            r
                                                            for r in g["rows"]
                                                            if row_actions_payload.get(
                                                                r["row_id"], "KEEP"
                                                            )
                                                            == "REMOVE"
                                                        ]
                                                        group_decisions.append(
                                                            {
                                                                "group_num": g[
                                                                    "group_num"
                                                                ],
                                                                "group_id": g[
                                                                    "group_id"
                                                                ],
                                                                "key_values": g[
                                                                    "key_values"
                                                                ],
                                                                "kept_ids": [
                                                                    r["row_id"]
                                                                    for r in kept_rows
                                                                ],
                                                                "kept_labels": [
                                                                    r.get(
                                                                        "display_label",
                                                                        str(
                                                                            r["row_id"]
                                                                        ),
                                                                    )
                                                                    for r in kept_rows
                                                                ],
                                                                "removed_ids": [
                                                                    r["row_id"]
                                                                    for r in rem_rows
                                                                ],
                                                                "removed_labels": [
                                                                    r.get(
                                                                        "display_label",
                                                                        str(
                                                                            r["row_id"]
                                                                        ),
                                                                    )
                                                                    for r in rem_rows
                                                                ],
                                                                "removed_count": len(
                                                                    rem_rows
                                                                ),
                                                                "kept_count": len(
                                                                    kept_rows
                                                                ),
                                                            }
                                                        )

                                                    if rem_ok:
                                                        rem_rep["group_decisions"] = (
                                                            group_decisions
                                                        )
                                                        rem_rep["duplicate_groups"] = (
                                                            len(detected_groups)
                                                        )
                                                        st.session_state.duplicate_cleaning_report = (
                                                            rem_rep
                                                        )
                                                        st.session_state.profile_result = (
                                                            None
                                                        )
                                                        st.session_state.duplicate_row_actions = (
                                                            {}
                                                        )
                                                        for g in detected_groups:
                                                            st.session_state.pop(
                                                                f"dup_sel_all_{g['group_num']}",
                                                                None,
                                                            )
                                                            for r in g["rows"]:
                                                                st.session_state.pop(
                                                                    f"dup_remove_{r['row_id']}",
                                                                    None,
                                                                )
                                                                st.session_state.pop(
                                                                    f"dup_exp_{r['row_id']}",
                                                                    None,
                                                                )
                                                        try:
                                                            ws_fresh = (
                                                                get_workspace_info(
                                                                    engine,
                                                                    db_name,
                                                                    working_tbl,
                                                                )
                                                            )
                                                            if (
                                                                ws_fresh
                                                                and st.session_state.get(
                                                                    "working_table_details"
                                                                )
                                                            ):
                                                                st.session_state.working_table_details[
                                                                    "working_row_count"
                                                                ] = ws_fresh[
                                                                    "row_count"
                                                                ]
                                                        except Exception:
                                                            pass
                                                        st.success(
                                                            f"Duplicate removal completed: {rem_msg}"
                                                        )
                                                        st.rerun()
                                                    else:
                                                        st.error(f"{rem_msg}")

                            # Dedicated Audit Report
                            if st.session_state.get("duplicate_cleaning_report"):
                                d_rep = st.session_state.duplicate_cleaning_report
                                d_keys = d_rep.get("duplicate_key_columns", [])
                                d_removed = d_rep.get("rows_removed", 0)
                                d_groups = d_rep.get("duplicate_groups", 0)
                                d_kept = d_rep.get("rows_kept", d_groups)
                                d_remain = d_rep.get("remaining_rows", 0)
                                d_decisions = d_rep.get("group_decisions", [])

                                st.markdown(
                                    '<div class="dq-section-title" style="margin-top: 1.5rem;"> Duplicate Removal Audit Report</div>',
                                    unsafe_allow_html=True,
                                )
                                with st.container(border=True):
                                    if d_removed == 0:
                                        st.info(
                                            "No duplicate records were removed. The workspace was already deduplicated."
                                        )
                                    else:
                                        st.success(
                                            f"Duplicate removal completed and successfully committed to `{working_tbl}`."
                                        )
                                        dk1, dk2, dk3, dk4 = st.columns(4)
                                        with dk1:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card">
                                                    <div class="kpi-label">Operation</div>
                                                    <div class="kpi-value" style="font-size: 1.2rem;">Duplicates</div>
 
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                        with dk2:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card">
                                                    <div class="kpi-label">Duplicate Key</div>
                                                    <div class="kpi-value" style="font-size: 1.1rem; font-family: var(--font-mono);">{', '.join(d_keys)}</div>
                                                    <div class="kpi-subtext">{d_groups:,} group(s) resolved</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                        with dk3:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card">
                                                    <div class="kpi-label">Rows Kept</div>
                                                    <div class="kpi-value" style="font-size: 1.25rem; color: var(--dq-success);">{d_kept:,}</div>
                                                    <div class="kpi-subtext">User-selected records to keep</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )
                                        with dk4:
                                            st.markdown(
                                                f"""
                                                <div class="kpi-card kpi-card-success">
                                                    <div class="kpi-label">Rows Removed</div>
                                                    <div class="kpi-value">{d_removed:,}</div>
                                                    <div class="kpi-subtext">{d_remain:,} rows remaining</div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )

                                        # Per-group decisions breakdown
                                        if d_decisions:
                                            st.markdown(
                                                '<div style="font-size: 0.9rem; font-weight: 700; color: var(--dq-slate); margin: 1rem 0 0.5rem 0;">'
                                                "Per-Group Decision Summary:"
                                                "</div>",
                                                unsafe_allow_html=True,
                                            )
                                            audit_rows = []
                                            for dec in d_decisions:
                                                key_disp = ", ".join(
                                                    f"{k}={v}"
                                                    for k, v in dec.get(
                                                        "key_values", {}
                                                    ).items()
                                                )
                                                # Support both old (kept_id/kept_label) and new (kept_ids/kept_labels) formats
                                                kept_labels = dec.get(
                                                    "kept_labels"
                                                ) or (
                                                    [dec["kept_label"]]
                                                    if dec.get("kept_label")
                                                    else (
                                                        [str(dec["kept_id"])]
                                                        if dec.get("kept_id")
                                                        is not None
                                                        else []
                                                    )
                                                )
                                                kept_text = (
                                                    f"KEEP → {', '.join(str(x) for x in kept_labels)}"
                                                    if kept_labels
                                                    else "None kept"
                                                )
                                                rem_list = dec.get(
                                                    "removed_labels"
                                                ) or [
                                                    str(x)
                                                    for x in dec.get("removed_ids", [])
                                                ]
                                                rem_text = (
                                                    f"REMOVED → {', '.join(rem_list)}"
                                                    if rem_list
                                                    else "None"
                                                )
                                                audit_rows.append(
                                                    {
                                                        "Duplicate Group": f"Group #{dec.get('group_num')}",
                                                        "Duplicate Key": key_disp,
                                                        "Decision (Keep)": kept_text,
                                                        "Decision (Remove)": rem_text,
                                                        "Removed Count": dec.get(
                                                            "removed_count",
                                                            len(
                                                                dec.get(
                                                                    "removed_ids",
                                                                    [],
                                                                )
                                                            ),
                                                        ),
                                                    }
                                                )
                                            st.dataframe(
                                                pd.DataFrame(audit_rows),
                                                use_container_width=True,
                                                hide_index=True,
                                            )

                                    st.markdown(
                                        """
                                        <div style="font-size: 12px; color: var(--text-muted); margin-top: 12px; border-top: 1px solid var(--border); padding-top: 8px;">
                                            Production table remains read-only. Changes applied strictly to the cleaning workspace.
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )

                                    col_d_next, _ = st.columns([2, 3])
                                    with col_d_next:
                                        if st.button(
                                            "Proceed to Special Character Cleaning",
                                            type="secondary",
                                            use_container_width=True,
                                            key="dup_proceed_to_special_chars_btn",
                                        ):
                                            st.session_state.workspace_sub_tab = (
                                                "🔣 Special Character Cleaning"
                                            )
                                            st.rerun()

                        # =========================================
                        # SUB-VIEW 6: 🔣 Special Character Cleaning
                        # =========================================
                        elif active_sub == "🔣 Special Character Cleaning":
                            if render_module_header(
                                title="Special Character Cleaning",
                                subtitle="Identify and clean unwanted control characters, non-printable characters, and special symbols from text columns. Your original source table is never modified.",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="sc_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                )
                                st.rerun()

                            text_cols_info = get_text_columns_with_types(engine, db_name, working_tbl)
                            text_col_names = [c["name"] for c in text_cols_info]
                            col_type_lookup = {c["name"]: c.get("column_type", c.get("data_type", "TEXT").upper()) for c in text_cols_info}

                            if not text_cols_info:
                                st.markdown(
                                    """
                                    <div class="empty-state-card">
                                        <div class="es-title">No Text Columns Found</div>
                                        <div class="es-desc">This table has no string or text columns eligible for special character cleaning.</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                # Track active working table to reset state when table changes
                                if st.session_state.get("sc_active_table") != working_tbl:
                                    st.session_state.sc_active_table = working_tbl
                                    st.session_state.sc_selected_columns = list(text_col_names)
                                    st.session_state.sc_scan_results = None
                                    st.session_state.sc_scan_executed = False
                                    st.session_state.sc_cleaning_report = None
                                    for c_info in text_cols_info:
                                        st.session_state[f"sc_target_col_{c_info['name']}"] = True

                                # Session state initialization
                                if "sc_selected_columns" not in st.session_state:
                                    st.session_state.sc_selected_columns = list(text_col_names)
                                for c_info in text_cols_info:
                                    k = f"sc_target_col_{c_info['name']}"
                                    if k not in st.session_state:
                                        st.session_state[k] = c_info["name"] in st.session_state.sc_selected_columns

                                if "sc_control_chars" not in st.session_state:
                                    st.session_state.sc_control_chars = []
                                if "sc_non_printable" not in st.session_state:
                                    st.session_state.sc_non_printable = []
                                if "sc_special_chars" not in st.session_state:
                                    st.session_state.sc_special_chars = []
                                if "sc_custom_chars" not in st.session_state:
                                    st.session_state.sc_custom_chars = ""
                                if "sc_mode" not in st.session_state:
                                    st.session_state.sc_mode = "remove"
                                if "sc_replacement" not in st.session_state:
                                    st.session_state.sc_replacement = ""
                                if "sc_scan_results" not in st.session_state:
                                    st.session_state.sc_scan_results = None
                                if "sc_scan_executed" not in st.session_state:
                                    st.session_state.sc_scan_executed = False

                                # Main Configuration Card
                                with st.container(border=True):
                                    st.markdown("#### 1. Target Text Columns")
                                    st.caption("Select one or more eligible text columns to inspect and clean.")

                                    col_btn1, col_btn2, _ = st.columns([1, 1, 4])
                                    with col_btn1:
                                        if st.button("Select All", key="sc_col_select_all_btn", use_container_width=True):
                                            st.session_state.sc_selected_columns = list(text_col_names)
                                            for c_info in text_cols_info:
                                                st.session_state[f"sc_target_col_{c_info['name']}"] = True
                                            st.session_state.sc_scan_executed = False
                                            st.session_state.sc_scan_results = None
                                            st.rerun()
                                    with col_btn2:
                                        if st.button("Deselect All", key="sc_col_deselect_all_btn", use_container_width=True):
                                            st.session_state.sc_selected_columns = []
                                            for c_info in text_cols_info:
                                                st.session_state[f"sc_target_col_{c_info['name']}"] = False
                                            st.session_state.sc_scan_executed = False
                                            st.session_state.sc_scan_results = None
                                            st.rerun()

                                    # Column checkboxes showing MySQL data type
                                    col_grid = st.columns(min(3, max(1, len(text_cols_info))))
                                    for idx, col_info in enumerate(text_cols_info):
                                        c_name = col_info["name"]
                                        c_type = col_info["column_type"]
                                        chk_key = f"sc_target_col_{c_name}"
                                        with col_grid[idx % len(col_grid)]:
                                            st.checkbox(
                                                f"**{c_name}** `({c_type})`",
                                                key=chk_key,
                                            )

                                    # Synchronize sc_selected_columns with checkbox states
                                    current_selected = [
                                        c["name"]
                                        for c in text_cols_info
                                        if st.session_state.get(f"sc_target_col_{c['name']}", False)
                                    ]
                                    if set(current_selected) != set(st.session_state.sc_selected_columns):
                                        st.session_state.sc_selected_columns = current_selected
                                        st.session_state.sc_scan_executed = False
                                        st.session_state.sc_scan_results = None

                                    st.markdown("---")
                                    st.markdown("#### 2. Cleaning Operation & Mode")
                                    
                                    mode_col1, mode_col2 = st.columns([1.5, 2])
                                    with mode_col1:
                                        mode_choice = st.radio(
                                            "Operation Mode",
                                            options=["Remove selected characters", "Replace selected characters"],
                                            index=0 if st.session_state.sc_mode == "remove" else 1,
                                            key="sc_mode_radio_choice",
                                            horizontal=True,
                                        )
                                        new_m = "remove" if mode_choice == "Remove selected characters" else "replace"
                                        if new_m != st.session_state.sc_mode:
                                            st.session_state.sc_mode = new_m
                                            st.session_state.sc_scan_executed = False
                                            st.session_state.sc_scan_results = None
                                            st.rerun()

                                    with mode_col2:
                                        if st.session_state.sc_mode == "replace":
                                            repl_val = st.text_input(
                                                "Replacement string",
                                                value=st.session_state.sc_replacement,
                                                key="sc_replacement_string_input",
                                                help="Each matched character will be replaced with this string (e.g. '_' or a space).",
                                                placeholder="e.g. _ or space",
                                            )
                                            if repl_val != st.session_state.sc_replacement:
                                                st.session_state.sc_replacement = repl_val
                                                st.session_state.sc_scan_executed = False
                                                st.session_state.sc_scan_results = None
                                                st.rerun()

                                    st.markdown("---")
                                    st.markdown("#### 3. Character Selection")
                                    st.caption("Select specific characters or categories to target. Nothing is removed by default.")

                                    # Tabbed interface for character categories
                                    char_tab1, char_tab2, char_tab3, char_tab4 = st.tabs([
                                        "Control Characters",
                                        "Non-Printable Characters",
                                        "Common Special Characters",
                                        "Custom Characters",
                                    ])

                                    with char_tab1:
                                        render_html("""
                                            <div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-bottom: 0.6rem;">
                                                <b>Whitespace Interaction:</b> Control characters like tabs (<code>\\t</code>) and newlines (<code>\\n</code>) are targeted individually without collapsing standard single spaces. For general space trimming, use the <b>Whitespace Cleaning</b> module.
                                            </div>
                                        """)
                                        ctrl_btn1, ctrl_btn2, _ = st.columns([1, 1, 4])
                                        with ctrl_btn1:
                                            if st.button("Select All", key="sc_ctrl_select_all_btn", use_container_width=True):
                                                st.session_state.sc_control_chars = list(CONTROL_CHARS.keys())
                                                for key in CONTROL_CHARS.keys():
                                                    st.session_state[f"sc_ctrl_chk_{key}"] = True
                                                st.session_state.sc_scan_executed = False
                                                st.session_state.sc_scan_results = None
                                                st.rerun()
                                        with ctrl_btn2:
                                            if st.button("Deselect All", key="sc_ctrl_deselect_all_btn", use_container_width=True):
                                                st.session_state.sc_control_chars = []
                                                for key in CONTROL_CHARS.keys():
                                                    st.session_state[f"sc_ctrl_chk_{key}"] = False
                                                st.session_state.sc_scan_executed = False
                                                st.session_state.sc_scan_results = None
                                                st.rerun()

                                        for key in CONTROL_CHARS.keys():
                                            k = f"sc_ctrl_chk_{key}"
                                            if k not in st.session_state:
                                                st.session_state[k] = key in st.session_state.sc_control_chars

                                        ctrl_cols = st.columns(3)
                                        for c_idx, (key, info) in enumerate(CONTROL_CHARS.items()):
                                            with ctrl_cols[c_idx % 3]:
                                                st.checkbox(
                                                    info["display"],
                                                    key=f"sc_ctrl_chk_{key}",
                                                )

                                        current_ctrl = [key for key in CONTROL_CHARS.keys() if st.session_state.get(f"sc_ctrl_chk_{key}", False)]
                                        if set(current_ctrl) != set(st.session_state.sc_control_chars):
                                            st.session_state.sc_control_chars = current_ctrl
                                            st.session_state.sc_scan_executed = False
                                            st.session_state.sc_scan_results = None

                                    with char_tab2:
                                        render_html("""
                                            <div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-bottom: 0.6rem;">
                                                <b>Unicode Preservation:</b> Valid multilingual text (e.g. accented letters, Kanji, Cyrillic, emojis) is strictly preserved. Only explicit invisible control/format codes are cleaned.
                                            </div>
                                        """)
                                        np_btn1, np_btn2, _ = st.columns([1, 1, 4])
                                        with np_btn1:
                                            if st.button("Select All", key="sc_np_select_all_btn", use_container_width=True):
                                                st.session_state.sc_non_printable = list(NON_PRINTABLE_CHARS.keys())
                                                for key in NON_PRINTABLE_CHARS.keys():
                                                    st.session_state[f"sc_np_chk_{key}"] = True
                                                st.session_state.sc_scan_executed = False
                                                st.session_state.sc_scan_results = None
                                                st.rerun()
                                        with np_btn2:
                                            if st.button("Deselect All", key="sc_np_deselect_all_btn", use_container_width=True):
                                                st.session_state.sc_non_printable = []
                                                for key in NON_PRINTABLE_CHARS.keys():
                                                    st.session_state[f"sc_np_chk_{key}"] = False
                                                st.session_state.sc_scan_executed = False
                                                st.session_state.sc_scan_results = None
                                                st.rerun()

                                        for key in NON_PRINTABLE_CHARS.keys():
                                            k = f"sc_np_chk_{key}"
                                            if k not in st.session_state:
                                                st.session_state[k] = key in st.session_state.sc_non_printable

                                        np_cols = st.columns(3)
                                        for np_idx, (key, info) in enumerate(NON_PRINTABLE_CHARS.items()):
                                            with np_cols[np_idx % 3]:
                                                st.checkbox(
                                                    info["display"],
                                                    key=f"sc_np_chk_{key}",
                                                )

                                        current_np = [key for key in NON_PRINTABLE_CHARS.keys() if st.session_state.get(f"sc_np_chk_{key}", False)]
                                        if set(current_np) != set(st.session_state.sc_non_printable):
                                            st.session_state.sc_non_printable = current_np
                                            st.session_state.sc_scan_executed = False
                                            st.session_state.sc_scan_results = None

                                    with char_tab3:
                                        st.caption("Punctuation and symbols are preserved unless explicitly selected below.")
                                        spec_btn1, spec_btn2, _ = st.columns([1, 1, 4])
                                        with spec_btn1:
                                            if st.button("Select All", key="sc_spec_select_all_btn", use_container_width=True):
                                                st.session_state.sc_special_chars = [ch for ch, _ in COMMON_SPECIAL_CHARS]
                                                for s_idx in range(len(COMMON_SPECIAL_CHARS)):
                                                    st.session_state[f"sc_spec_chk_{s_idx}"] = True
                                                st.session_state.sc_scan_executed = False
                                                st.session_state.sc_scan_results = None
                                                st.rerun()
                                        with spec_btn2:
                                            if st.button("Deselect All", key="sc_spec_deselect_all_btn", use_container_width=True):
                                                st.session_state.sc_special_chars = []
                                                for s_idx in range(len(COMMON_SPECIAL_CHARS)):
                                                    st.session_state[f"sc_spec_chk_{s_idx}"] = False
                                                st.session_state.sc_scan_executed = False
                                                st.session_state.sc_scan_results = None
                                                st.rerun()

                                        for s_idx, (ch, _) in enumerate(COMMON_SPECIAL_CHARS):
                                            k = f"sc_spec_chk_{s_idx}"
                                            if k not in st.session_state:
                                                st.session_state[k] = ch in st.session_state.sc_special_chars

                                        spec_cols = st.columns(4)
                                        for s_idx, (ch, desc) in enumerate(COMMON_SPECIAL_CHARS):
                                            with spec_cols[s_idx % 4]:
                                                st.checkbox(
                                                    desc,
                                                    key=f"sc_spec_chk_{s_idx}",
                                                )

                                        current_spec = [ch for s_idx, (ch, _) in enumerate(COMMON_SPECIAL_CHARS) if st.session_state.get(f"sc_spec_chk_{s_idx}", False)]
                                        if set(current_spec) != set(st.session_state.sc_special_chars):
                                            st.session_state.sc_special_chars = current_spec
                                            st.session_state.sc_scan_executed = False
                                            st.session_state.sc_scan_results = None

                                    with char_tab4:
                                        render_html("""
                                            <div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-bottom: 0.6rem;">
                                                <b>Literal Matching:</b> Every character entered here is matched literally. Regex metacharacters (<code>.</code>, <code>*</code>, <code>+</code>, <code>?</code>, <code>[</code>, <code>]</code>, <code>(</code>, <code>)</code>, <code>\\</code>, <code>^</code>, <code>-</code>) are automatically escaped to prevent unintended regex patterns.
                                            </div>
                                        """)
                                        cust_in = st.text_input(
                                            "Custom characters to clean",
                                            value=st.session_state.sc_custom_chars,
                                            key="sc_custom_input_field",
                                            placeholder="e.g. @#$%^&*~|",
                                            help="Enter any literal characters to clean. Each character is evaluated individually.",
                                        )
                                        if cust_in != st.session_state.sc_custom_chars:
                                            st.session_state.sc_custom_chars = cust_in
                                            st.session_state.sc_scan_executed = False
                                            st.session_state.sc_scan_results = None
                                            st.rerun()

                                    st.markdown("---")
                                    # Summary of active rules
                                    total_rules_selected = (
                                        len(st.session_state.sc_control_chars)
                                        + len(st.session_state.sc_non_printable)
                                        + len(st.session_state.sc_special_chars)
                                        + len(st.session_state.sc_custom_chars)
                                    )
                                    selected_cols_count = len(st.session_state.sc_selected_columns)

                                    action_col1, action_col2, _ = st.columns([1.5, 1.2, 3])
                                    with action_col1:
                                        scan_btn = st.button(
                                            "Scan & Preview Changes",
                                            type="secondary",
                                            use_container_width=True,
                                            key="sc_run_scan_action_btn",
                                        )
                                    with action_col2:
                                        if st.button("↺ Reset Configuration", key="sc_reset_config_btn", use_container_width=True):
                                            st.session_state.sc_selected_columns = list(text_col_names)
                                            for c_info in text_cols_info:
                                                st.session_state[f"sc_target_col_{c_info['name']}"] = True
                                            for k in list(st.session_state.keys()):
                                                if k.startswith("sc_ctrl_chk_") or k.startswith("sc_np_chk_") or k.startswith("sc_spec_chk_"):
                                                    st.session_state[k] = False
                                            st.session_state.sc_control_chars = []
                                            st.session_state.sc_non_printable = []
                                            st.session_state.sc_special_chars = []
                                            st.session_state.sc_custom_chars = ""
                                            st.session_state.sc_mode = "remove"
                                            st.session_state.sc_replacement = ""
                                            st.session_state.sc_scan_results = None
                                            st.session_state.sc_scan_executed = False
                                            st.rerun()

                                    if scan_btn:
                                        if selected_cols_count == 0:
                                            st.warning("Please select at least one column to scan.")
                                        elif total_rules_selected == 0:
                                            st.warning("Please select at least one control character, special character, or custom character to clean.")
                                        else:
                                            with st.spinner("Scanning workspace columns for special characters..."):
                                                st.session_state.sc_scan_results = scan_special_characters_workspace(
                                                    engine,
                                                    db_name,
                                                    working_tbl,
                                                    selected_columns=st.session_state.sc_selected_columns,
                                                    control_chars_selected=st.session_state.sc_control_chars,
                                                    special_chars_selected=st.session_state.sc_special_chars,
                                                    custom_chars=st.session_state.sc_custom_chars,
                                                    mode=st.session_state.sc_mode,
                                                    replacement=st.session_state.sc_replacement,
                                                    non_printable_selected=st.session_state.sc_non_printable,
                                                )
                                                st.session_state.sc_scan_executed = True
                                            st.rerun()

                                # ========================================================
                                # Interactive Preview Section (Safe - Never modifies DB)
                                # ========================================================
                                if st.session_state.sc_scan_executed:
                                    scan_results = st.session_state.sc_scan_results or []
                                    st.markdown("### 4. Inspection & Proposed Changes Preview")

                                    if not scan_results:
                                        render_alert(
                                            alert_type="success",
                                            title="No Targeted Characters Detected",
                                            message="None of the selected text columns contain the specified special characters or control codes.",
                                        )
                                    else:
                                        total_aff_rows = sum(r["total_affected_rows"] for r in scan_results)
                                        total_aff_vals = sum(r["total_affected_values"] for r in scan_results)

                                        render_alert(
                                            alert_type="info",
                                            title=f"{len(scan_results)} Column(s) Affected — {total_aff_rows:,} Row(s) Identified",
                                            message=f"Found {total_aff_vals:,} matching value occurrences. Review original vs proposed cleaned values below before confirming execution.",
                                        )

                                        # Column preview expanders
                                        for res in scan_results:
                                            col_n = res["column"]
                                            col_t = res.get("data_type", col_type_lookup.get(col_n, "VARCHAR"))
                                            aff_r = res["total_affected_rows"]
                                            sample_rows = res.get("sample_rows", [])

                                            with st.expander(
                                                f"Column `{col_n}` ({col_t}) — {aff_r:,} row(s) to change",
                                                expanded=True,
                                            ):
                                                chars_desc = ", ".join(res.get("chars_targeted", []))
                                                st.caption(f"Targeted characters in rule: {chars_desc}")

                                                if sample_rows:
                                                    prev_df = pd.DataFrame([
                                                        {
                                                            "Original Value": r["original"],
                                                            "Proposed Cleaned Value": r["cleaned"],
                                                            "Occurrences": r["count"],
                                                        }
                                                        for r in sample_rows[:30]
                                                    ])
                                                    st.dataframe(
                                                        prev_df,
                                                        use_container_width=True,
                                                        hide_index=True,
                                                    )
                                                else:
                                                    st.caption("No sample rows available.")

                                        # Apply Button
                                        st.markdown("---")
                                        act_label = "Remove" if st.session_state.sc_mode == "remove" else f"Replace with '{st.session_state.sc_replacement}'"
                                        apply_btn = st.button(
                                            f"Apply Special Character Cleaning ({act_label}) to {len(scan_results)} Column(s)",
                                            type="primary",
                                            use_container_width=True,
                                            key="sc_apply_transformation_btn",
                                        )

                                        if apply_btn:
                                            with st.spinner("Applying special character cleaning to workspace table..."):
                                                success, msg, report = clean_special_characters_workspace(
                                                    engine,
                                                    db_name,
                                                    working_tbl,
                                                    selected_columns=[r["column"] for r in scan_results],
                                                    control_chars_selected=st.session_state.sc_control_chars,
                                                    special_chars_selected=st.session_state.sc_special_chars,
                                                    custom_chars=st.session_state.sc_custom_chars,
                                                    mode=st.session_state.sc_mode,
                                                    replacement=st.session_state.sc_replacement,
                                                    non_printable_selected=st.session_state.sc_non_printable,
                                                )
                                            if success:
                                                st.session_state.sc_cleaning_report = report
                                                st.session_state.profile_result = None
                                                st.session_state.sc_scan_executed = False
                                                st.session_state.sc_scan_results = None

                                                # Audit logging to session history
                                                if "cleaning_history" not in st.session_state:
                                                    st.session_state.cleaning_history = []
                                                st.session_state.cleaning_history.append({
                                                    "tool": "Special Character Cleaning",
                                                    "mode": st.session_state.sc_mode,
                                                    "columns": [r["column"] for r in scan_results],
                                                    "rows_affected": report.get("rows_affected", 0),
                                                    "values_changed": report.get("total_values_changed", 0),
                                                    "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                    "details": report,
                                                })

                                                st.success(msg)
                                                st.rerun()
                                            else:
                                                st.error(msg)

                                # ========================================================
                                # Executive Cleaning Report (Post-Execution Audit)
                                # ========================================================
                                if st.session_state.get("sc_cleaning_report"):
                                    report = st.session_state.sc_cleaning_report
                                    total_changed = report.get("total_values_changed", 0)
                                    cols_affected = len(report.get("columns_affected", []))
                                    rows_affected = report.get("rows_affected", 0)
                                    op_name = report.get("operation", "Special Character Cleaning")
                                    mode_used = report.get("mode", "remove")

                                    st.markdown(
                                        f'<div class="dq-section-title" style="margin-top: 1.5rem;"> Executive {op_name} Report</div>',
                                        unsafe_allow_html=True,
                                    )

                                    with st.container(border=True):
                                        if total_changed == 0:
                                            st.info(
                                                "Special character cleaning finished. All targeted columns are normalized."
                                            )
                                        else:
                                            st.success(
                                                f"{op_name} successfully committed exclusively to workspace sandbox `{working_tbl}`. "
                                                f"Production source table `{db_name}.{tbl_name}` remains strictly unmodified."
                                            )
                                            c_kpi1, c_kpi2, c_kpi3, c_kpi4 = st.columns(4)
                                            with c_kpi1:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card kpi-card-success">
                                                        <div class="kpi-label">Values Cleaned</div>
                                                        <div class="kpi-value">{total_changed:,}</div>
                                                        <div class="kpi-subtext">Strings transformed</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )
                                            with c_kpi2:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card">
                                                        <div class="kpi-label">Columns Affected</div>
                                                        <div class="kpi-value">{cols_affected}</div>
                                                        <div class="kpi-subtext">Transformed attributes</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )
                                            with c_kpi3:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card">
                                                        <div class="kpi-label">Unique Rows Affected</div>
                                                        <div class="kpi-value">{rows_affected:,}</div>
                                                        <div class="kpi-subtext">Updated in sandbox</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )
                                            with c_kpi4:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card">
                                                        <div class="kpi-label">Operation Mode</div>
                                                        <div class="kpi-value" style="font-size: 1.25rem;">{mode_used.title()}</div>
                                                        <div class="kpi-subtext">Sandbox committed</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )

                                            st.markdown("##### Column-Level Impact Breakdown")
                                            column_reports = report.get("columns_affected", [])
                                            if column_reports:
                                                rep_df = pd.DataFrame(column_reports).rename(
                                                    columns={
                                                        "column": "Column Name",
                                                        "values_changed": "Values Cleaned",
                                                        "rows_affected": "Rows Affected",
                                                    }
                                                )
                                                st.dataframe(
                                                    rep_df,
                                                    use_container_width=True,
                                                    hide_index=True,
                                                    column_config={
                                                        "Values Cleaned": st.column_config.ProgressColumn(
                                                            "Values Cleaned",
                                                            help="Number of values normalized in this column",
                                                            format="%d",
                                                            min_value=0,
                                                            max_value=max(
                                                                [c["values_changed"] for c in column_reports] or [10]
                                                            ),
                                                        )
                                                    },
                                                )

                                        col_sc_next, _ = st.columns([2, 3])
                                        with col_sc_next:
                                            if st.button(
                                                "Proceed to Date Formatting",
                                                type="secondary",
                                                use_container_width=True,
                                                key="sc_proceed_to_datefmt_btn",
                                            ):
                                                st.session_state.workspace_sub_tab = "📅 Date Formatting"
                                                st.rerun()

                        # =========================================
                        # SUB-VIEW 7: Date Formatting
                        # =========================================
                        elif active_sub == "📅 Date Formatting":
                            if render_module_header(
                                title="Date Formatting",
                                subtitle="Validate and preview date formatting for native DATE/DATETIME/TIMESTAMP columns. The original source table is never modified. Native MySQL date storage is binary — display format is applied at query time via DATE_FORMAT().",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="datefmt_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                )
                                st.rerun()

                            date_cols = get_date_columns(engine, db_name, working_tbl)

                            if not date_cols:
                                st.markdown(
                                    """
                                    <div class="empty-state-card">
                                        <div class="es-title">No Date Columns Found</div>
                                        <div class="es-desc">This table has no native DATE, DATETIME, TIMESTAMP, TIME, or YEAR columns eligible for date formatting.</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                with st.container(border=True):
                                    cfg_col1, cfg_col2 = st.columns([3, 2])
                                    with cfg_col1:
                                        target_col = st.selectbox(
                                            "Select Date Column",
                                            options=date_cols,
                                            key="datefmt_target_col_select",
                                            help="Select a native date/date-time column to validate and preview formatting.",
                                        )
                                    with cfg_col2:
                                        format_options = list(FORMAT_MAP.keys())
                                        target_format = st.selectbox(
                                            "Target Format",
                                            options=format_options,
                                            key="datefmt_format_choice_select",
                                            help="Choose target display format for preview.",
                                        )

                                    if target_col:
                                        with st.spinner(
                                            "Analyzing date values and generating preview..."
                                        ):
                                            # Run the backend validation/preview
                                            success, msg, report = (
                                                format_dates_workspace(
                                                    engine,
                                                    db_name,
                                                    working_tbl,
                                                    target_col,
                                                    target_format,
                                                )
                                            )

                                        if not success:
                                            st.error(f"{msg}")
                                        else:
                                            total_examined = report.get(
                                                "total_examined", 0
                                            )
                                            nulls_skipped = report.get(
                                                "nulls_skipped", 0
                                            )
                                            blanks_skipped = report.get(
                                                "blanks_skipped", 0
                                            )
                                            invalid_unparseable = report.get(
                                                "invalid_unparseable", 0
                                            )
                                            valid_values = report.get("valid_values", 0)
                                            preview_rows = report.get("preview", [])

                                            # Preview box
                                            st.markdown(
                                                f"""
                                                <div style="background: var(--dq-bg-soft); border: 1px solid var(--dq-border); border-radius: 8px; padding: 0.85rem 1.1rem; margin: 0.85rem 0 1rem 0;">
                                                    <div style="font-size: 0.78rem; font-weight: 700; color: var(--dq-slate-muted); text-transform: uppercase; letter-spacing: 0.05em;">
                                                        Operation Preview
                                                    </div>
                                                    <div style="display: flex; gap: 2rem; margin-top: 0.4rem; flex-wrap: wrap; font-size: 0.9rem;">
                                                        <div><span style="color: var(--dq-slate-muted);">Target Column:</span> <code style="font-family: var(--font-mono); color: var(--dq-slate-text);">{target_col}</code></div>
                                                        <div><span style="color: var(--dq-slate-muted);">Target Format:</span> <strong style="color: var(--dq-slate-text);">{target_format}</strong></div>
                                                        <div><span style="color: var(--dq-slate-muted);">Total Rows:</span> <strong style="color: var(--dq-slate-text);">{total_examined:,}</strong></div>
                                                        <div><span style="color: var(--dq-slate-muted);">Valid Values:</span> <strong style="color: var(--dq-success); font-size: 1.05rem;">{valid_values:,}</strong></div>
                                                        <div><span style="color: var(--dq-slate-muted);">NULL Values:</span> <strong style="color: var(--dq-warning);">{nulls_skipped:,}</strong></div>
                                                        <div><span style="color: var(--dq-slate-muted);">Blank Values:</span> <strong style="color: var(--dq-warning);">{blanks_skipped:,}</strong></div>
                                                        <div><span style="color: var(--dq-slate-muted);">Invalid/Unparseable:</span> <strong style="color: var(--dq-danger);">{invalid_unparseable:,}</strong></div>
                                                    </div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )

                                            # Sample preview table
                                            if preview_rows:
                                                st.markdown(
                                                    "##### Preview: Original vs Formatted"
                                                )
                                                preview_df = pd.DataFrame(preview_rows)
                                                preview_df = preview_df.rename(
                                                    columns={
                                                        "original": "Original Value",
                                                        "formatted": f"Formatted ({target_format})",
                                                    }
                                                )
                                                st.dataframe(
                                                    preview_df,
                                                    use_container_width=True,
                                                    hide_index=True,
                                                )

                                            # Preview shows original vs formatted - now offer to APPLY the formatting
                                            col_apply1, col_apply2 = st.columns(2)
                                            with col_apply1:
                                                validate_btn = st.button(
                                                    f"Validate Only",
                                                    type="secondary",
                                                    use_container_width=True,
                                                    key="validate_date_formatting_btn",
                                                    help="Only validates and shows preview - does not modify data",
                                                )
                                            with col_apply2:
                                                apply_btn = st.button(
                                                    f"Apply Formatting (Convert to Text)",
                                                    type="primary",
                                                    use_container_width=True,
                                                    key="apply_date_formatting_btn",
                                                    help="Creates a new column with formatted date strings. Original date column preserved.",
                                                )

                                            if validate_btn and success:
                                                st.session_state.date_format_cleaning_report = (
                                                    report
                                                )
                                                st.session_state.profile_result = None
                                                st.success(f"{msg}")
                                                st.rerun()
                                            elif validate_btn and not success:
                                                st.error(f"{msg}")

                                            if apply_btn:
                                                with st.spinner(
                                                    f"Applying date formatting to `{target_col}`..."
                                                ):
                                                    # Ask for new column name
                                                    new_col_name = (
                                                        f"{target_col}_formatted"
                                                    )
                                                    (
                                                        apply_success,
                                                        apply_msg,
                                                        apply_report,
                                                    ) = apply_date_formatting_workspace(
                                                        engine,
                                                        db_name,
                                                        working_tbl,
                                                        target_col,
                                                        target_format,
                                                        new_column_name=new_col_name,
                                                    )
                                                if apply_success:
                                                    st.session_state.date_format_apply_report = (
                                                        apply_report
                                                    )
                                                    st.session_state.profile_result = (
                                                        None
                                                    )
                                                    st.success(f"{apply_msg}")
                                                    st.rerun()
                                                else:
                                                    st.error(f"{apply_msg}")

                            # Dedicated Audit Report
                            if st.session_state.get("date_format_cleaning_report"):
                                df_rep = st.session_state.date_format_cleaning_report
                                df_col = df_rep.get("column", "")
                                df_format = df_rep.get("target_format", "")
                                df_total = df_rep.get("total_examined", 0)
                                df_valid = df_rep.get("valid_values", 0)
                                df_nulls = df_rep.get("nulls_skipped", 0)
                                df_blanks = df_rep.get("blanks_skipped", 0)
                                df_invalid = df_rep.get("invalid_unparseable", 0)
                                df_preview = df_rep.get("preview", [])

                                st.markdown(
                                    '<div class="dq-section-title" style="margin-top: 1.5rem;"> Date Formatting Validation Report</div>',
                                    unsafe_allow_html=True,
                                )
                                with st.container(border=True):
                                    st.success(
                                        f"Date formatting validated for `{df_col}`."
                                    )
                                    dk1, dk2, dk3, dk4 = st.columns(4)
                                    with dk1:
                                        st.markdown(
                                            f"""
                                            <div class="kpi-card">
                                                <div class="kpi-label">Operation</div>
                                                <div class="kpi-value" style="font-size: 1.2rem;">Date Formatting</div>
                                                <div class="kpi-subtext">Format validation & preview</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    with dk2:
                                        st.markdown(
                                            f"""
                                            <div class="kpi-card">
                                                <div class="kpi-label">Target Column</div>
                                                <div class="kpi-value" style="font-size: 1.15rem; font-family: var(--font-mono);">{df_col}</div>
                                                <div class="kpi-subtext">Target format: {df_format}</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    with dk3:
                                        st.markdown(
                                            f"""
                                            <div class="kpi-card">
                                                <div class="kpi-label">Total Examined</div>
                                                <div class="kpi-value" style="font-size: 1.25rem;">{df_total:,}</div>
                                                <div class="kpi-subtext">Rows in workspace</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    with dk4:
                                        st.markdown(
                                            f"""
                                            <div class="kpi-card kpi-card-success">
                                                <div class="kpi-label">Valid Values</div>
                                                <div class="kpi-value" style="font-size: 1.25rem; color: var(--dq-success);">{df_valid:,}</div>
                                                <div class="kpi-subtext">NULL: {df_nulls:,} | Blank: {df_blanks:,} | Invalid: {df_invalid:,}</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )

                                    st.markdown(
                                        """
                                        <div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-top: 0.85rem; border-top: 1px solid var(--dq-border); padding-top: 0.65rem;">
                                             <b>Storage Note:</b> Native MySQL DATE/DATETIME/TIMESTAMP storage is binary. Display format is applied at query time via <code>DATE_FORMAT()</code>. No data conversion or storage change occurs.
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )

                                    col_df_next, _ = st.columns([2, 3])
                                    with col_df_next:
                                        if st.button(
                                            "View Workspace Data Profile",
                                            type="secondary",
                                            key="datefmt_proceed_to_prof_btn",
                                        ):
                                            st.session_state.active_profile_target = (
                                                "workspace"
                                            )
                                            st.session_state.show_profile_dialog = True
                                            st.rerun()

                            # Apply Formatting Report
                            if st.session_state.get("date_format_apply_report"):
                                ar = st.session_state.date_format_apply_report
                                src_col = ar.get("source_column", "")
                                tgt_col = ar.get("target_column", "")
                                tgt_fmt = ar.get("target_format", "")
                                rows = ar.get("rows_formatted", 0)
                                replaced = ar.get("replaced_original", False)

                                st.markdown(
                                    '<div class="dq-section-title" style="margin-top: 1.5rem;"> Date Formatting Applied</div>',
                                    unsafe_allow_html=True,
                                )
                                with st.container(border=True):
                                    st.success(
                                        f"Date formatting applied to `{src_col}` → new column `{tgt_col}`."
                                    )
                                    ak1, ak2, ak3 = st.columns(3)
                                    with ak1:
                                        st.metric("Source Column", src_col)
                                    with ak2:
                                        st.metric("Target Column", tgt_col)
                                    with ak3:
                                        st.metric("Rows Formatted", f"{rows:,}")

                                    st.info(
                                        f"Format: **{tgt_fmt}** | "
                                        f"{'Original column replaced' if replaced else 'Original column preserved'}"
                                    )

                                    col_apply_next, _ = st.columns([2, 3])
                                    with col_apply_next:
                                        if st.button(
                                            "Refresh Workspace Preview",
                                            type="secondary",
                                            key="datefmt_apply_refresh_btn",
                                        ):
                                            st.rerun()

                        elif active_sub == "🗓️ Advanced Date Standardization":
                            if render_module_header(
                                title="Advanced Date Standardization",
                                subtitle="Detect and standardize date-related values stored inside VARCHAR or TEXT columns using strict deterministic rules (Text Month Detection and Numeric Date Detection with 4-digit Year & Day > 12). Always creates a new output column, sets ambiguous or invalid dates to NULL, and preserves the original column completely.",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="adv_date_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                )
                                st.rerun()

                            # Initialize session state for Advanced Date Standardization
                            if "adv_date_scan_results" not in st.session_state:
                                st.session_state.adv_date_scan_results = None
                            if "adv_date_selected_col" not in st.session_state:
                                st.session_state.adv_date_selected_col = None
                            if "adv_date_preview_data" not in st.session_state:
                                st.session_state.adv_date_preview_data = None
                            if "adv_date_std_report" not in st.session_state:
                                st.session_state.adv_date_std_report = None

                            eligible_text_cols = [
                                c
                                for c in get_text_columns(engine, db_name, working_tbl)
                                if not c.startswith("__bool_backup_")
                            ]

                            if not eligible_text_cols:
                                st.markdown(
                                    """
                                    <div class="empty-state-card">
                                        <div class="es-title">No VARCHAR / TEXT Columns Found</div>
                                        <div class="es-desc">This workspace table contains no VARCHAR or TEXT columns eligible for Advanced Date Standardization.</div>
                                    </div>
                                    """,
                                    unsafe_allow_html=True,
                                )
                            else:
                                # ── Step 1: Database Scan & Scan Percentage Slider ──────────────────
                                with st.container(border=True):
                                    st.markdown(
                                        '<div class="dq-section-title">Step 1: Scan Database for Date Columns</div>',
                                        unsafe_allow_html=True,
                                    )
                                    sc_col1, sc_col2 = st.columns([2.2, 1.3])
                                    with sc_col1:
                                        scan_pct = st.select_slider(
                                            "Select Scan Percentage of Column Records",
                                            options=ALLOWED_SCAN_PERCENTAGES,
                                            value=20,
                                            format_func=lambda v: f"{v}%",
                                            key="adv_date_scan_pct_slider",
                                            help="Determines what percentage of records in each VARCHAR/TEXT column is sampled for date detection (20%, 30%, 40%, or 80%).",
                                        )
                                        total_ws_rows = int(
                                            workspace_info.get("row_count", 0)
                                        )
                                        approx_sampled = (
                                            max(
                                                1,
                                                int(
                                                    round(
                                                        total_ws_rows
                                                        * (scan_pct / 100.0)
                                                    )
                                                ),
                                            )
                                            if total_ws_rows > 0
                                            else 0
                                        )
                                        st.caption(
                                            f"Selected Scan Percentage: **{scan_pct}%** "
                                            f"(approx. **{approx_sampled:,}** of **{total_ws_rows:,}** records per column across **{len(eligible_text_cols)}** eligible text column(s))."
                                        )
                                    with sc_col2:
                                        st.write("")
                                        scan_db_btn = st.button(
                                            "Scan Database for Date Columns",
                                            type="secondary",
                                            use_container_width=True,
                                            key="adv_date_scan_db_btn",
                                        )

                                    if scan_db_btn:
                                        with st.spinner(
                                            f"Scanning {len(eligible_text_cols)} VARCHAR/TEXT column(s) at {scan_pct}% sample size..."
                                        ):
                                            detected_cols_list = detect_date_columns(
                                                engine,
                                                db_name,
                                                working_tbl,
                                                scan_percentage=scan_pct,
                                            )
                                            st.session_state.adv_date_scan_results = (
                                                detected_cols_list
                                            )
                                            if detected_cols_list:
                                                st.session_state.adv_date_selected_col = detected_cols_list[
                                                    0
                                                ][
                                                    "column"
                                                ]
                                            st.session_state.adv_date_preview_data = (
                                                None
                                            )
                                            st.rerun()

                                    # Scan Result UI Table (Section 17)
                                    if (
                                        st.session_state.adv_date_scan_results
                                        is not None
                                    ):
                                        scan_res = (
                                            st.session_state.adv_date_scan_results
                                        )
                                        if scan_res:
                                            st.success(
                                                f"Detected {len(scan_res)} date-related VARCHAR/TEXT column(s) at {scan_pct}% scan size."
                                            )
                                            scan_table_rows = [
                                                {
                                                    "Column Name": item["column"],
                                                    "Date-like Records": f"{item['date_like_percentage']:.0f}%",
                                                    "Scan Size": f"{item['scan_percentage']}%",
                                                    "Sampled Records": item[
                                                        "sample_size"
                                                    ],
                                                    "Deterministic Matches": item[
                                                        "convertible_count"
                                                    ],
                                                }
                                                for item in scan_res
                                            ]
                                            st.dataframe(
                                                pd.DataFrame(scan_table_rows),
                                                use_container_width=True,
                                                hide_index=True,
                                            )
                                        else:
                                            st.warning(
                                                "No columns automatically met the date detection threshold. You can still select any VARCHAR/TEXT column using Manual Column Selection below."
                                            )

                                # ── Step 2: Column Selection (Detected + Manual Fallback) ────────────
                                with st.container(border=True):
                                    st.markdown(
                                        '<div class="dq-section-title">Step 2: Select Target Column (Detected or Manual Selection)</div>',
                                        unsafe_allow_html=True,
                                    )
                                    detected_names = (
                                        [
                                            item["column"]
                                            for item in st.session_state.adv_date_scan_results
                                        ]
                                        if st.session_state.adv_date_scan_results
                                        else []
                                    )

                                    sel_c1, sel_c2 = st.columns(2)
                                    with sel_c1:
                                        det_options = [
                                            "-- Select Detected Column --"
                                        ] + detected_names
                                        default_det_idx = (
                                            det_options.index(
                                                st.session_state.adv_date_selected_col
                                            )
                                            if st.session_state.adv_date_selected_col
                                            in det_options
                                            else 0
                                        )
                                        chosen_detected = st.selectbox(
                                            "Detected Date Columns",
                                            options=det_options,
                                            index=default_det_idx,
                                            key="adv_date_detected_dropdown",
                                            help="Automatically detected VARCHAR/TEXT columns containing date-like patterns.",
                                        )
                                    with sel_c2:
                                        man_options = [
                                            "-- Manual Column Selection (All Text Columns) --"
                                        ] + eligible_text_cols
                                        chosen_manual = st.selectbox(
                                            "Manual Column Selection (Fallback)",
                                            options=man_options,
                                            index=0,
                                            key="adv_date_manual_dropdown",
                                            help="Manually select any VARCHAR or TEXT column if automatic detection was not run or did not include your target column.",
                                        )

                                    # Resolve active selected column: Manual selection takes precedence if explicitly chosen;
                                    # otherwise use Detected Column selection
                                    if (
                                        chosen_manual
                                        != "-- Manual Column Selection (All Text Columns) --"
                                    ):
                                        active_target_col = chosen_manual
                                    elif (
                                        chosen_detected
                                        != "-- Select Detected Column --"
                                    ):
                                        active_target_col = chosen_detected
                                    else:
                                        active_target_col = None

                                    st.session_state.adv_date_selected_col = (
                                        active_target_col
                                    )

                                    if active_target_col:
                                        st.markdown(
                                            f"""
                                            <div style="background: var(--dq-accent-soft); border: 1px solid var(--dq-accent-border); border-radius: 8px; padding: 0.75rem 1rem; margin-top: 0.5rem;">
                                                <span style="font-size: 0.82rem; color: var(--dq-slate-muted); text-transform: uppercase; font-weight: 700;">Selected Column:</span>
                                                <code style="font-size: 1rem; font-weight: 700; margin-left: 0.5rem; color: var(--dq-slate);">{active_target_col}</code>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    else:
                                        st.info(
                                            "Select a column from either 'Detected Date Columns' (after scanning) or 'Manual Column Selection' to configure standardization."
                                        )

                                # ── Step 3: Output Format, New Output Column, Preview & Execution ──
                                if active_target_col:
                                    existing_ws_cols = [
                                        (
                                            c.get("column_name")
                                            or c.get("COLUMN_NAME")
                                            or c.get("name")
                                            or ""
                                        )
                                        for c in workspace_info.get("schema", [])
                                        if isinstance(c, dict)
                                    ]
                                    default_safe_out_col = get_safe_output_column_name(
                                        existing_ws_cols, active_target_col
                                    )

                                    with st.container(border=True):
                                        st.markdown(
                                            '<div class="dq-section-title">Step 3: Configure Output Format & Standardize</div>',
                                            unsafe_allow_html=True,
                                        )
                                        fmt_c1, fmt_c2 = st.columns(2)
                                        with fmt_c1:
                                            selected_output_fmt = st.selectbox(
                                                "Output Date Format",
                                                options=list(
                                                    ADV_DATE_OUTPUT_FORMATS.keys()
                                                ),
                                                index=0,
                                                key=f"adv_date_out_fmt_{active_target_col}",
                                                help="Target standardized date string format. The engine extracts (DAY, MONTH, YEAR) first and then formats valid dates into this format.",
                                            )
                                        with fmt_c2:
                                            custom_out_col = st.text_input(
                                                "New Output Column Name (Original column is never modified)",
                                                value=default_safe_out_col,
                                                key=f"adv_date_out_col_{active_target_col}",
                                                help="A new column will be created. If the name collides with an existing column, a numeric suffix is added automatically.",
                                            )
                                            resolved_out_col = (
                                                get_safe_output_column_name(
                                                    existing_ws_cols,
                                                    active_target_col,
                                                    custom_out_col,
                                                )
                                            )
                                            if (
                                                resolved_out_col
                                                != custom_out_col.strip()
                                            ):
                                                st.caption(
                                                    f"Collision protection active: output will be saved to `{resolved_out_col}` to avoid overwriting `{custom_out_col.strip()}`."
                                                )

                                        act_col1, act_col2 = st.columns(2)
                                        with act_col1:
                                            preview_btn = st.button(
                                                "Preview Before Standardization",
                                                type="secondary",
                                                use_container_width=True,
                                                key=f"adv_date_preview_btn_{active_target_col}",
                                            )
                                        with act_col2:
                                            do_std_btn = st.button(
                                                "Do Standardization",
                                                type="secondary",
                                                use_container_width=True,
                                                key=f"adv_date_exec_btn_{active_target_col}",
                                            )

                                        if preview_btn:
                                            with st.spinner(
                                                f"Generating deterministic preview for `{active_target_col}`..."
                                            ):
                                                st.session_state.adv_date_preview_data = preview_column_standardization(
                                                    engine,
                                                    db_name,
                                                    working_tbl,
                                                    active_target_col,
                                                    output_format=selected_output_fmt,
                                                    preview_limit=100,
                                                )

                                        if do_std_btn:
                                            with st.spinner(
                                                f"Standardizing `{active_target_col}` into new column `{resolved_out_col}`..."
                                            ):
                                                ok, msg, rep = standardize_column(
                                                    engine,
                                                    db_name,
                                                    working_tbl,
                                                    active_target_col,
                                                    output_format=selected_output_fmt,
                                                    output_column=resolved_out_col,
                                                )
                                                if ok:
                                                    st.session_state.adv_date_std_report = (
                                                        rep
                                                    )
                                                    st.session_state.adv_date_preview_data = preview_column_standardization(
                                                        engine,
                                                        db_name,
                                                        working_tbl,
                                                        active_target_col,
                                                        output_format=selected_output_fmt,
                                                        preview_limit=100,
                                                    )
                                                    st.session_state.profile_result = (
                                                        None
                                                    )
                                                    st.success(f"{msg}")
                                                    st.rerun()
                                                else:
                                                    st.error(f"{msg}")

                                        # Render Preview Before Standardization (Section 18)
                                        if (
                                            st.session_state.adv_date_preview_data
                                            and st.session_state.adv_date_preview_data.get(
                                                "source_column"
                                            )
                                            == active_target_col
                                        ):
                                            p_data = (
                                                st.session_state.adv_date_preview_data
                                            )
                                            st.markdown("---")
                                            st.markdown(
                                                "##### Preview Before Standardization"
                                            )
                                            pm1, pm2, pm3, pm4 = st.columns(4)
                                            pm1.metric(
                                                "Total Records",
                                                f"{p_data.get('total_records', 0):,}",
                                            )
                                            pm2.metric(
                                                "Successfully Converted",
                                                f"{p_data.get('successfully_converted', 0):,}",
                                            )
                                            pm3.metric(
                                                "NULL / Unconverted",
                                                f"{p_data.get('unconverted', 0):,}",
                                            )
                                            pm4.metric(
                                                "Conversion Rate",
                                                f"{p_data.get('conversion_rate', 0.0):.1f}%",
                                            )

                                            st.dataframe(
                                                pd.DataFrame(
                                                    p_data.get("preview_rows", [])
                                                ),
                                                use_container_width=True,
                                                hide_index=True,
                                            )

                                # ── Step 4: Completion Summary Report (Section 22) ──────────────────
                                if st.session_state.get("adv_date_std_report"):
                                    rep = st.session_state.adv_date_std_report
                                    with st.container(border=True):
                                        st.markdown(
                                            '<div class="dq-section-title">Date Standardization Completed</div>',
                                            unsafe_allow_html=True,
                                        )
                                        r1, r2, r3 = st.columns(3)
                                        with r1:
                                            st.markdown(
                                                f"**Source Column:** `{rep.get('source_column')}`  \n"
                                                f"**Output Column:** `{rep.get('output_column')}`  \n"
                                                f"**Output Format:** `{rep.get('output_format')}`"
                                            )
                                        with r2:
                                            st.markdown(
                                                f"**Total Records:** `{rep.get('total_records', 0):,}`  \n"
                                                f"**Successfully Converted:** `{rep.get('successfully_converted', 0):,}`"
                                            )
                                        with r3:
                                            st.markdown(
                                                f"**Unconverted (NULL):** `{rep.get('unconverted', 0):,}`  \n"
                                                f"**Conversion Rate:** **{rep.get('conversion_rate', 0.0):.1f}%**"
                                            )
                                        st.caption(
                                            "Note: Ambiguous dates (e.g. 05/06/2026), invalid calendar dates (e.g. 31/02/2026), and non-date strings are intentionally set to NULL in the output column while preserving the source column untouched."
                                        )

                        elif active_sub == "☑️ Boolean Normalization":
                            if render_module_header(
                                title="Boolean / Yes-No Normalization",
                                subtitle="Semantic Boolean detection across all columns (both declared Boolean and VARCHAR/Text/Numeric columns). Scans actual column values, distinguishes Physical vs. Logical datatype, computes confidence, previews mappings, and normalizes with full Undo support.",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="bool_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                )
                                st.rerun()

                            schema_cols = workspace_info.get("schema", [])
                            total_scannable = len(schema_cols)
                            st.caption(
                                f"Scanning across **{total_scannable}** workspace column(s) (inspecting actual values, unique representations, frequencies, and column context)."
                            )

                            # Initialize session state
                            if "bool_detection_results" not in st.session_state:
                                st.session_state.bool_detection_results = None
                            if "bool_column_analyses" not in st.session_state:
                                st.session_state.bool_column_analyses = {}
                            if "bool_transform_config" not in st.session_state:
                                st.session_state.bool_transform_config = {}
                            if "bool_preview_results" not in st.session_state:
                                st.session_state.bool_preview_results = {}
                            if "bool_history" not in st.session_state:
                                st.session_state.bool_history = []

                            # Step 1: Scan configuration
                            st.markdown(
                                '<div class="dq-section-title" style="margin-top: 1rem;"> Step 1: Scan Columns for Boolean-like Data</div>',
                                unsafe_allow_html=True,
                            )

                            det_col1, det_col2 = st.columns([2, 2])
                            with det_col1:
                                sample_limit = st.number_input(
                                    "Max Distinct Values to Inspect per Column",
                                    min_value=100,
                                    max_value=10000,
                                    value=2000,
                                    step=100,
                                    key="bool_sample_limit",
                                    help="Maximum distinct values grouped per column when evaluating value distributions.",
                                )
                            with det_col2:
                                confidence_threshold = (
                                    st.slider(
                                        "Confidence Threshold (%)",
                                        min_value=50,
                                        max_value=99,
                                        value=65,
                                        step=5,
                                        key="bool_threshold",
                                        help="Minimum confidence % for a column to be flagged as Boolean or Boolean-like.",
                                    )
                                    / 100.0
                                )

                            detect_btn = st.button(
                                "Scan All Columns for Boolean / Yes-No Values",
                                type="secondary",
                                use_container_width=True,
                                key="bool_detect_btn",
                            )

                            # Scan only when button is explicitly pressed
                            if detect_btn:
                                with st.spinner(
                                    f"Scanning all {total_scannable} columns in `{working_tbl}`..."
                                ):
                                    results = detect_boolean_like_columns(
                                        engine,
                                        db_name,
                                        working_tbl,
                                        sample_limit=sample_limit,
                                        confidence_threshold=confidence_threshold,
                                    )
                                    st.session_state.bool_detection_results = results
                                    st.session_state.bool_scanned_table = working_tbl
                                    for r in results:
                                        col_name = r["column"]
                                        st.session_state.bool_column_analyses[
                                            col_name
                                        ] = analyze_boolean_column(
                                            engine,
                                            db_name,
                                            working_tbl,
                                            col_name,
                                            sample_limit=sample_limit,
                                        )
                                    st.rerun()

                            # Transformation History & Undo Banner
                            if st.session_state.bool_history:
                                with st.container(border=True):
                                    st.markdown(
                                        "##### Boolean Normalization History (Undo Available)"
                                    )
                                    for hist_idx, hist_item in enumerate(
                                        reversed(st.session_state.bool_history)
                                    ):
                                        h_col1, h_col2 = st.columns([3.5, 1])
                                        with h_col1:
                                            st.markdown(
                                                f"**Column `{hist_item['column']}`** → Standardized to `{hist_item['true_target']}` / `{hist_item['false_target']}` "
                                                f"in `{hist_item['target_column']}` ({hist_item['rows_converted']:,} rows updated)"
                                            )
                                        with h_col2:
                                            if st.button(
                                                f"Undo `{hist_item['column']}`",
                                                key=f"bool_undo_{hist_item['column']}_{hist_idx}",
                                                use_container_width=True,
                                            ):
                                                ok, u_msg = undo_boolean_normalization(
                                                    engine,
                                                    db_name,
                                                    working_tbl,
                                                    hist_item["column"],
                                                    target_column=hist_item.get(
                                                        "target_column"
                                                    ),
                                                )
                                                if ok:
                                                    st.success(f"{u_msg}")
                                                    st.session_state.bool_history.remove(
                                                        hist_item
                                                    )
                                                    st.session_state.bool_column_analyses[
                                                        hist_item["column"]
                                                    ] = analyze_boolean_column(
                                                        engine,
                                                        db_name,
                                                        working_tbl,
                                                        hist_item["column"],
                                                        sample_limit=sample_limit,
                                                    )
                                                    st.session_state.profile_result = (
                                                        None
                                                    )
                                                    st.rerun()
                                                else:
                                                    st.error(f"{u_msg}")

                            # Display results
                            if st.session_state.bool_detection_results is not None:
                                results = st.session_state.bool_detection_results

                                if not results:
                                    st.warning(
                                        f"No columns detected as Boolean-like with the current threshold ({confidence_threshold*100:.0f}%). "
                                        "Try lowering the confidence threshold."
                                    )
                                else:
                                    st.success(
                                        f"Detected {len(results)} Boolean / Boolean-like column(s) "
                                        f"(threshold: {confidence_threshold*100:.0f}%)"
                                    )

                                    # Overview Summary Table
                                    det_rows = []
                                    for r in results:
                                        det_rows.append(
                                            {
                                                "Column": r["column"],
                                                "Current Type (Physical)": r.get(
                                                    "current_type", "VARCHAR"
                                                ),
                                                "Detected Type (Logical)": r.get(
                                                    "detected_type", "Boolean-like"
                                                ),
                                                "Confidence Level": r.get(
                                                    "confidence_level", "HIGH"
                                                ),
                                                "Confidence %": float(
                                                    r.get("confidence", 0.0)
                                                ),
                                                "TRUE Values": ", ".join(
                                                    r.get("true_representations", [])[
                                                        :8
                                                    ]
                                                )
                                                or "—",
                                                "FALSE Values": ", ".join(
                                                    r.get("false_representations", [])[
                                                        :8
                                                    ]
                                                )
                                                or "—",
                                                "Unrecognized": r.get(
                                                    "unknown_count", 0
                                                ),
                                                "NULLs": r.get("null_count", 0),
                                            }
                                        )
                                    st.dataframe(
                                        pd.DataFrame(det_rows),
                                        use_container_width=True,
                                        hide_index=True,
                                    )

                                    st.markdown(
                                        '<div class="dq-section-title" style="margin-top: 1.25rem;"> Step 2: Configure, Preview & Normalize Columns</div>',
                                        unsafe_allow_html=True,
                                    )

                                    format_label_map = {
                                        "TRUE / FALSE": ("TRUE_FALSE", "TRUE", "FALSE"),
                                        "true / false (lowercase)": (
                                            "true_false",
                                            "true",
                                            "false",
                                        ),
                                        "YES / NO": ("YES_NO", "YES", "NO"),
                                        "1 / 0 (Binary)": ("1_0", "1", "0"),
                                        "Y / N": ("Y_N", "Y", "N"),
                                        "T / F": ("T_F", "T", "F"),
                                        "Custom (e.g., Active / Inactive)": (
                                            "custom",
                                            "Active",
                                            "Inactive",
                                        ),
                                    }

                                    for r in results:
                                        col = r["column"]
                                        analysis = (
                                            st.session_state.bool_column_analyses.get(
                                                col
                                            )
                                            or r
                                        )
                                        conf_lvl = analysis.get(
                                            "confidence_level", "HIGH"
                                        )
                                        curr_type = analysis.get(
                                            "current_type", "VARCHAR"
                                        )
                                        det_type = analysis.get(
                                            "detected_type", "Boolean-like"
                                        )
                                        true_reps_str = (
                                            ", ".join(
                                                analysis.get("true_representations", [])
                                            )
                                            or "None"
                                        )
                                        false_reps_str = (
                                            ", ".join(
                                                analysis.get(
                                                    "false_representations", []
                                                )
                                            )
                                            or "None"
                                        )
                                        unrec_list = (
                                            analysis.get("unrecognized_samples")
                                            or analysis.get("unrecognized_values")
                                            or []
                                        )

                                        with st.expander(
                                            f"Column: {col} | Current Type: {curr_type} → Detected: {det_type} ({conf_lvl} Confidence)",
                                            expanded=True,
                                        ):
                                            info_c1, info_c2 = st.columns([1.4, 2.2])
                                            with info_c1:
                                                st.markdown(f"""
                                                    **Column:** `{col}`  
                                                    **Current Data Type:** `{curr_type}`  
                                                    **Detected Logical Type:** `{det_type}`  
                                                    **Detection Confidence:** **{conf_lvl}** ({analysis.get('confidence', 0):.1f}%)  
                                                    **Total Non-Null:** `{analysis.get('non_null_count', 0):,}` | **NULL Values:** `{analysis.get('null_count', 0):,}`
                                                    """)
                                            with info_c2:
                                                st.markdown(f"""
                                                    **Detected Representations:**  
                                                    - **TRUE state (`{analysis.get('true_count', 0):,}` rows):** `{true_reps_str}`  
                                                    - **FALSE state (`{analysis.get('false_count', 0):,}` rows):** `{false_reps_str}`  
                                                    - **Unrecognized (`{analysis.get('unknown_count', 0):,}` rows):** `{', '.join(map(str, unrec_list)) if unrec_list else 'None'}`
                                                    """)

                                            # Unrecognized values handling (Requirement 9)
                                            manual_mapping_for_col: Dict[str, str] = {}
                                            unrec_action = "keep_original"
                                            if unrec_list:
                                                st.warning(
                                                    f"Column `{col}` contains {len(unrec_list)} unrecognized distinct value(s):"
                                                    f"{', '.join(repr(u) for u in unrec_list[:10])}. "
                                                    "Unrecognized values are NEVER silently converted to FALSE."
                                                )
                                                unrec_mode_label = st.radio(
                                                    f"How should unrecognized values in `{col}` be handled?",
                                                    options=[
                                                        "Leave Unchanged (Recommended — preserve original values)",
                                                        "Map Manually (assign each unrecognized value to TRUE, FALSE, NULL, or Keep)",
                                                        "Convert Unrecognized to NULL",
                                                    ],
                                                    key=f"bool_unrec_mode_{col}",
                                                    horizontal=False,
                                                )
                                                if "Map Manually" in unrec_mode_label:
                                                    unrec_action = "keep_original"
                                                    st.markdown(
                                                        "**Manual Mapping for Unrecognized Values:**"
                                                    )
                                                    m_cols = st.columns(
                                                        min(3, max(1, len(unrec_list)))
                                                    )
                                                    for idx_u, u_val in enumerate(
                                                        unrec_list[:15]
                                                    ):
                                                        with m_cols[
                                                            idx_u % len(m_cols)
                                                        ]:
                                                            u_choice = st.selectbox(
                                                                f"Map `{u_val}` to:",
                                                                options=[
                                                                    "KEEP",
                                                                    "TRUE",
                                                                    "FALSE",
                                                                    "NULL",
                                                                ],
                                                                key=f"bool_manual_{col}_{idx_u}",
                                                            )
                                                            manual_mapping_for_col[
                                                                str(u_val)
                                                            ] = u_choice
                                                elif "NULL" in unrec_mode_label:
                                                    unrec_action = "set_null"
                                                else:
                                                    unrec_action = "keep_original"

                                            st.markdown("---")
                                            cfg_left, cfg_right = st.columns([1.8, 1.8])
                                            with cfg_left:
                                                chosen_label = st.radio(
                                                    "Standardize As:",
                                                    options=list(
                                                        format_label_map.keys()
                                                    ),
                                                    key=f"bool_std_radio_{col}",
                                                )
                                                fmt_code, default_t, default_f = (
                                                    format_label_map[chosen_label]
                                                )
                                                if fmt_code == "custom":
                                                    cust_c1, cust_c2 = st.columns(2)
                                                    with cust_c1:
                                                        true_value = st.text_input(
                                                            "TRUE value:",
                                                            value="Active",
                                                            key=f"bool_cust_t_{col}",
                                                        )
                                                    with cust_c2:
                                                        false_value = st.text_input(
                                                            "FALSE value:",
                                                            value="Inactive",
                                                            key=f"bool_cust_f_{col}",
                                                        )
                                                else:
                                                    true_value, false_value = (
                                                        default_t,
                                                        default_f,
                                                    )

                                            with cfg_right:
                                                write_mode = st.radio(
                                                    "Output Mode:",
                                                    options=[
                                                        f"Standardize `{col}` In-Place (with automatic Undo backup)",
                                                        f"Write to New Column (`{col}_norm`)",
                                                    ],
                                                    key=f"bool_write_mode_{col}",
                                                )
                                                is_in_place = write_mode.startswith(
                                                    "Standardize"
                                                )
                                                if not is_in_place:
                                                    new_col_name = st.text_input(
                                                        "New Column Name:",
                                                        value=f"{col}_norm",
                                                        key=f"bool_new_col_{col}",
                                                    )
                                                else:
                                                    new_col_name = col

                                                st.caption(
                                                    "NULL values are always preserved as `NULL` and are never converted to FALSE."
                                                )

                                            btn_c1, btn_c2 = st.columns(2)
                                            with btn_c1:
                                                if st.button(
                                                    f"Preview Changes for `{col}`",
                                                    key=f"bool_preview_btn_{col}",
                                                    use_container_width=True,
                                                ):
                                                    prev_data = preview_boolean_normalization(
                                                        engine,
                                                        db_name,
                                                        working_tbl,
                                                        col,
                                                        target_format=fmt_code,
                                                        true_value=true_value,
                                                        false_value=false_value,
                                                        unrecognized_action=unrec_action,
                                                        manual_mapping=manual_mapping_for_col,
                                                    )
                                                    st.session_state.bool_preview_results[
                                                        col
                                                    ] = prev_data

                                            with btn_c2:
                                                if st.button(
                                                    f"Apply Normalization to `{col}`",
                                                    type="secondary",
                                                    key=f"bool_apply_btn_{col}",
                                                    use_container_width=True,
                                                ):
                                                    with st.spinner(
                                                        f"Normalizing `{col}`..."
                                                    ):
                                                        ok, msg, report = (
                                                            transform_boolean_column(
                                                                engine,
                                                                db_name,
                                                                working_tbl,
                                                                col,
                                                                target_format=fmt_code,
                                                                true_value=true_value,
                                                                false_value=false_value,
                                                                new_column_name=(
                                                                    None
                                                                    if is_in_place
                                                                    else new_col_name
                                                                ),
                                                                in_place=is_in_place,
                                                                unrecognized_action=unrec_action,
                                                                manual_mapping=manual_mapping_for_col,
                                                            )
                                                        )
                                                        if ok:
                                                            st.success(f"{msg}")
                                                            st.session_state.bool_history.append(
                                                                {
                                                                    "column": col,
                                                                    "target_column": report.get(
                                                                        "target_column",
                                                                        col,
                                                                    ),
                                                                    "true_target": report.get(
                                                                        "true_target",
                                                                        true_value,
                                                                    ),
                                                                    "false_target": report.get(
                                                                        "false_target",
                                                                        false_value,
                                                                    ),
                                                                    "rows_converted": report.get(
                                                                        "rows_converted",
                                                                        0,
                                                                    ),
                                                                }
                                                            )
                                                            st.session_state.bool_column_analyses[
                                                                col
                                                            ] = analyze_boolean_column(
                                                                engine,
                                                                db_name,
                                                                working_tbl,
                                                                col,
                                                                sample_limit=sample_limit,
                                                            )
                                                            st.session_state.profile_result = (
                                                                None
                                                            )
                                                            st.rerun()
                                                        else:
                                                            st.error(f"{msg}")

                                            # Show Before / After Preview if requested
                                            if (
                                                col
                                                in st.session_state.bool_preview_results
                                            ):
                                                prev = st.session_state.bool_preview_results[
                                                    col
                                                ]
                                                st.markdown(
                                                    "##### Before / After Preview (Read-Only)"
                                                )
                                                p_tab1, p_tab2 = st.tabs(
                                                    [
                                                        "Distinct Value Mapping Table",
                                                        "Sample Row-by-Row Preview",
                                                    ]
                                                )
                                                with p_tab1:
                                                    st.dataframe(
                                                        pd.DataFrame(
                                                            prev.get(
                                                                "mapping_summary", []
                                                            )
                                                        ),
                                                        use_container_width=True,
                                                        hide_index=True,
                                                    )
                                                with p_tab2:
                                                    st.dataframe(
                                                        pd.DataFrame(
                                                            prev.get("row_preview", [])
                                                        ),
                                                        use_container_width=True,
                                                        hide_index=True,
                                                    )

                        # =========================================
                        # SUB-VIEW 10: Intelligent Numeric Data Cleaning
                        # =========================================
                        elif active_sub == "🔢 Numeric Data Cleaning":
                            if render_module_header(
                                title="Intelligent Numeric Data Detection & Conversion",
                                subtitle="Automatically scan MySQL text-based columns (VARCHAR, CHAR, TEXT) for numeric representations, recommend safe types (INT, BIGINT, DECIMAL, DOUBLE), inspect and normalize formatting rules, preview value-level conversions, and safely execute schema type alterations exclusively on the isolated cleaning workspace.",
                                badge_text="Safe Sandbox",
                                badge_type="brand",
                                back_label="Back to Cleaning Hub",
                                back_key="num_back_to_hub_btn",
                            ):
                                nav_to_view(
                                    "🧹 Cleaning Workspace", "🏠 Cleaning Hub"
                                )
                                st.rerun()

                            # Discover eligible columns
                            eligible_text_col_info = get_eligible_text_columns(
                                engine, db_name, working_tbl
                            )
                            eligible_text_cols = [
                                c["name"] if isinstance(c, dict) else str(c)
                                for c in eligible_text_col_info
                                if (isinstance(c, dict) and c.get("name")) or (isinstance(c, str) and c)
                            ]
                            col_type_dict = {
                                c["name"]: c.get("column_type", c.get("data_type", "TEXT"))
                                for c in eligible_text_col_info
                                if isinstance(c, dict) and "name" in c
                            }

                            if not eligible_text_cols:
                                st.info(
                                    f"No VARCHAR, CHAR, or TEXT columns were detected in `{working_tbl}`. "
                                    "Numeric conversion operates on string-based columns containing numeric text representations."
                                )
                            else:
                                # Top Navigation Tabs: Automatic Detection vs. Manual Selection
                                num_tab_auto, num_tab_manual = st.tabs(
                                    [
                                        "Automatic Table Scan & Candidates",
                                        "Select Column Manually",
                                    ]
                                )

                                with num_tab_auto:
                                    st.markdown(
                                        '<div style="font-size: 0.9rem; color: var(--dq-slate); margin-bottom: 0.5rem;">'
                                        '<b>Automatic Schema & Column Inspection</b>'
                                        '</div>'
                                        '<div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-bottom: 1rem;">'
                                        'Scans text columns across the workspace using a representative sample (~50%–60% of table rows), evaluates numeric consistency, identifies decimals vs integers, '
                                        'and protects identifiers (such as postal codes, product codes, or phone numbers) from accidental numeric truncation.'
                                        '</div>',
                                        unsafe_allow_html=True,
                                    )

                                    col_scan_btn, col_scan_opt = st.columns([2, 3])
                                    with col_scan_opt:
                                        c_thr1, c_thr2 = st.columns(2)
                                        with c_thr1:
                                            scan_thresh = st.slider(
                                                "Detection Threshold (%):",
                                                min_value=50,
                                                max_value=100,
                                                value=85,
                                                step=5,
                                                key="num_scan_thresh_slider",
                                                help="Minimum proportion of non-empty values that must be valid numbers for a column to qualify as an automatic numeric candidate.",
                                            )
                                        with c_thr2:
                                            scan_sample_pct = st.slider(
                                                "Sampling Proportion (%):",
                                                min_value=20,
                                                max_value=100,
                                                value=55,
                                                step=5,
                                                key="num_scan_sample_pct_slider",
                                                help="Proportion of rows sampled during scanning (default 55%, roughly 50%-60% of table rows). Small tables scan all available rows.",
                                            )

                                    with col_scan_btn:
                                        st.write("")
                                        st.write("")
                                        run_auto_scan = st.button(
                                            "Run Auto-Scan Across Workspace",
                                            type="primary",
                                            use_container_width=True,
                                            key="num_run_auto_scan_btn",
                                        )

                                    if run_auto_scan:
                                        with st.spinner("Scanning columns for numeric representations..."):
                                            scan_cfg = NumericNormalizationConfig(
                                                detection_threshold=float(scan_thresh),
                                                sample_proportion=float(scan_sample_pct) / 100.0,
                                            )
                                            scan_results = scan_table_numeric_candidates(
                                                engine, db_name, working_tbl, config=scan_cfg
                                            )
                                            st.session_state.numeric_scan_results = scan_results
                                            for res in scan_results:
                                                col_n = res["column"]
                                                st.session_state.numeric_column_analyses[col_n] = res

                                            # Immediately set active column to the first qualifying candidate
                                            qual_cols = [
                                                r["column"] for r in scan_results
                                                if r["classification"] in (
                                                    NumericDetectionClassification.INTEGER_CANDIDATE.value,
                                                    NumericDetectionClassification.DECIMAL_CANDIDATE.value,
                                                )
                                            ]
                                            if qual_cols:
                                                st.session_state.numeric_selected_col = qual_cols[0]
                                                st.session_state.num_active_tab_source = "auto"
                                        st.rerun()

                                    scan_results = st.session_state.get("numeric_scan_results")
                                    if scan_results:
                                        # Only qualifying text-based columns appear in automatic conversion target list
                                        qualifying_candidates = [
                                            r for r in scan_results
                                            if r["classification"] in (
                                                NumericDetectionClassification.INTEGER_CANDIDATE.value,
                                                NumericDetectionClassification.DECIMAL_CANDIDATE.value,
                                            )
                                        ]

                                        if qualifying_candidates:
                                            st.markdown(
                                                f'<div style="font-size: 0.85rem; color: #0F766E; margin-bottom: 0.75rem; font-weight: 600;">'
                                                f'Scan complete: {len(scan_results)} text column(s) evaluated. '
                                                f'Found {len(qualifying_candidates)} qualifying numeric candidate(s) (threshold ≥ {scan_thresh}%).'
                                                f'</div>',
                                                unsafe_allow_html=True,
                                            )

                                            # Build table rows for qualifying candidates
                                            display_rows = []
                                            for r in qualifying_candidates:
                                                display_rows.append({
                                                    "Column Name": r["column"],
                                                    "Current Type": r["current_type"],
                                                    "Classification": r["classification"],
                                                    "Numeric %": f"{r['numeric_percentage']:.1f}%",
                                                    "Valid Numbers": f"{r['valid_count']:,}",
                                                    "Invalid / Ambiguous": f"{r['invalid_count'] + r['ambiguous_count'] + r['potential_identifier_count']:,}",
                                                    "Recommended Type": r["recommended_type"],
                                                    "Suggested Action": r["suggested_action"],
                                                })

                                            st.dataframe(
                                                pd.DataFrame(display_rows),
                                                use_container_width=True,
                                                hide_index=True,
                                            )

                                            # Column selector from ONLY qualifying candidates
                                            candidate_col_options = [r["column"] for r in qualifying_candidates]
                                            st.markdown("##### Select Column to Configure & Convert")
                                            c_sel_col, _ = st.columns([2.5, 2.5])
                                            with c_sel_col:
                                                cur_sel = st.session_state.get("numeric_selected_col")
                                                def_idx = candidate_col_options.index(cur_sel) if cur_sel in candidate_col_options else 0

                                                def _on_auto_picker_change():
                                                    c_val = st.session_state.get("num_auto_col_picker")
                                                    if c_val:
                                                        if isinstance(c_val, dict):
                                                            c_val = c_val.get("name", "")
                                                        st.session_state.numeric_selected_col = str(c_val)
                                                        st.session_state.num_active_tab_source = "auto"

                                                sel_auto_col = st.selectbox(
                                                    "Target Column from Qualifying Scan Results:",
                                                    options=candidate_col_options,
                                                    index=def_idx,
                                                    key="num_auto_col_picker",
                                                    on_change=_on_auto_picker_change,
                                                )
                                                # Synchronize active column directly with auto selectbox
                                                if st.session_state.get("num_active_tab_source", "auto") == "auto" and sel_auto_col:
                                                    st.session_state.numeric_selected_col = str(sel_auto_col)
                                        else:
                                            st.info(
                                                f"ℹ️ No qualifying numeric candidate columns were detected under the current detection threshold ({scan_thresh}%). "
                                                f"Ordinary text and non-numeric columns are excluded from automatic conversion. "
                                                f"If you believe a column was missed, use the **'Select Column Manually'** tab to inspect and convert it."
                                            )

                                with num_tab_manual:
                                    st.markdown(
                                        '<div style="font-size: 0.9rem; color: var(--dq-slate); margin-bottom: 0.5rem;">'
                                        '<b>Manual Column Selection & Deep Numeric Analysis</b>'
                                        '</div>'
                                        '<div style="font-size: 0.82rem; color: var(--dq-slate-muted); margin-bottom: 1rem;">'
                                        'If automatic detection misses a column or classified it as ordinary text, you can manually select '
                                        'any eligible text-based column here to initiate deep numeric compatibility analysis, value validation, and conversion without bypassing safety checks.'
                                        '</div>',
                                        unsafe_allow_html=True,
                                    )

                                    # Show table of all eligible text columns with their automatic detection status
                                    cached_analyses = st.session_state.get("numeric_column_analyses", {})
                                    manual_display_data = []
                                    for cname in eligible_text_cols:
                                        ctype = col_type_dict.get(cname, "TEXT")
                                        if cname in cached_analyses:
                                            det_status = cached_analyses[cname].get("classification", "Scanned")
                                        else:
                                            det_status = "Not Scanned Yet"
                                        manual_display_data.append({
                                            "Column Name": cname,
                                            "Current Data Type": ctype,
                                            "Automatic Detection Status": det_status,
                                        })

                                    with st.expander("All Eligible Text Columns & Detection Status", expanded=False):
                                        st.dataframe(
                                            pd.DataFrame(manual_display_data),
                                            use_container_width=True,
                                            hide_index=True,
                                        )

                                    col_srch, col_pick, col_meta = st.columns([2, 2.5, 1.5])
                                    with col_srch:
                                        m_search = st.text_input(
                                            "Filter columns by name:",
                                            value="",
                                            key="num_manual_search_input",
                                            placeholder="Type column name...",
                                        ).strip().lower()

                                    filtered_manual_cols = [
                                        c for c in eligible_text_cols
                                        if not m_search or m_search in str(c).lower()
                                    ]

                                    with col_pick:
                                        selected_manual_choice = st.selectbox(
                                            "Select Any Column to Analyze:",
                                            options=filtered_manual_cols if filtered_manual_cols else eligible_text_cols,
                                            key="num_manual_dropdown",
                                        )

                                    cur_meta_type = col_type_dict.get(selected_manual_choice, "TEXT")
                                    with col_meta:
                                        st.markdown(
                                            f'<div style="font-size: 0.82rem; padding-top: 1.85rem; color: var(--dq-slate);">'
                                            f'Current Type: <code>{cur_meta_type}</code></div>',
                                            unsafe_allow_html=True,
                                        )

                                    # Run deep analysis button
                                    col_man_btn, _ = st.columns([2, 3])
                                    with col_man_btn:
                                        if st.button(
                                            f"Analyze `{selected_manual_choice}` for Numeric Conversion",
                                            type="primary",
                                            use_container_width=True,
                                            key="num_run_manual_analysis_btn",
                                        ):
                                            if isinstance(selected_manual_choice, dict):
                                                selected_manual_choice = selected_manual_choice.get("name", "")
                                            st.session_state.numeric_selected_col = str(selected_manual_choice)
                                            st.session_state.num_active_tab_source = "manual"
                                            st.rerun()

                                # If a column is selected (via Auto Scan or Manual Selection)
                                active_numeric_col = st.session_state.get("numeric_selected_col")
                                if isinstance(active_numeric_col, dict):
                                    active_numeric_col = active_numeric_col.get("name")
                                if not isinstance(active_numeric_col, str) or not active_numeric_col or active_numeric_col not in eligible_text_cols:
                                    scan_res = st.session_state.get("numeric_scan_results")
                                    if scan_res:
                                        qual_cols = [
                                            r["column"] for r in scan_res
                                            if r["classification"] in (
                                                NumericDetectionClassification.INTEGER_CANDIDATE.value,
                                                NumericDetectionClassification.DECIMAL_CANDIDATE.value,
                                            )
                                        ]
                                        if qual_cols:
                                            active_numeric_col = qual_cols[0]
                                    if not active_numeric_col and eligible_text_cols:
                                        active_numeric_col = eligible_text_cols[0]
                                    elif not active_numeric_col:
                                        active_numeric_col = None
                                st.session_state.numeric_selected_col = active_numeric_col

                                if active_numeric_col:
                                    st.markdown("---")
                                    st.markdown(
                                        f'<div class="dq-section-title">Detailed Value Analysis & Conversion: <code>{active_numeric_col}</code></div>',
                                        unsafe_allow_html=True,
                                    )

                                    # 1. Normalization Config controls (Accordion)
                                    with st.expander("Numeric Normalization Rules", expanded=False):
                                        c_norm1, c_norm2 = st.columns(2)
                                        with c_norm1:
                                            fmt_keys = list(NUMBER_FORMATS.keys())
                                            sel_fmt = st.selectbox(
                                                "Number Formatting Standard:",
                                                options=fmt_keys,
                                                index=0,
                                                format_func=lambda k: NUMBER_FORMATS.get(k, k),
                                                key="num_cfg_format",
                                                help="Specify how commas and dots are interpreted for thousands and decimal marks.",
                                            )
                                            trim_ws = st.checkbox(
                                                "Trim leading & trailing whitespace",
                                                value=True,
                                                key="num_cfg_trim",
                                            )
                                            norm_plus = st.checkbox(
                                                "Normalize leading plus sign (+250 → 250)",
                                                value=True,
                                                key="num_cfg_plus",
                                            )
                                            strip_neg = st.checkbox(
                                                "Strip negative sign / Convert to positive (-500 → 500)",
                                                value=False,
                                                key="num_cfg_neg",
                                                help="When enabled, strips leading negative signs or converts negative values (including accounting parentheses) into positive numbers.",
                                            )
                                            sci_not = st.checkbox(
                                                "Support scientific notation (e.g. 1.5e3 → 1500)",
                                                value=False,
                                                key="num_cfg_sci",
                                            )
                                        with c_norm2:
                                            strip_curr = st.checkbox(
                                                "Strip currency symbols ($, €, £, ¥, ₹, etc.)",
                                                value=False,
                                                key="num_cfg_curr",
                                            )
                                            strip_pct = st.checkbox(
                                                "Strip percentage signs (%)",
                                                value=False,
                                                key="num_cfg_pct",
                                                help="When enabled, removes percentage symbols and preserves numeric percentage-point values (e.g. '15%' becomes 15).",
                                            )
                                            allow_zeros = st.checkbox(
                                                "Allow stripping leading zeros (e.g. '00125' → 125)",
                                                value=False,
                                                key="num_cfg_zeros",
                                                help="Keep unchecked to protect identifier columns like postal codes, product codes, or customer numbers.",
                                            )
                                            inv_res = st.selectbox(
                                                "Action on Invalid / Unresolved Values:",
                                                options=["block", "set_null", "keep_text"],
                                                index=0,
                                                format_func=lambda r: {
                                                    "block": "Block conversion if invalid values exist (Strict Safety)",
                                                    "set_null": "Set invalid and ambiguous values to NULL (Safe Conversion)",
                                                    "keep_text": "Keep column as text (Cancel Conversion)",
                                                }.get(r, r),
                                                key="num_cfg_inv_res",
                                                help="Never silently drops rows. Explicitly configure whether unparseable values abort or are nullified.",
                                            )

                                    active_config = NumericNormalizationConfig(
                                        trim_whitespace=trim_ws,
                                        number_format=sel_fmt,
                                        normalize_plus_sign=norm_plus,
                                        strip_negative_sign=strip_neg,
                                        allow_scientific=sci_not,
                                        strip_currency=strip_curr,
                                        strip_percentage=strip_pct,
                                        allow_leading_zeros=allow_zeros,
                                        invalid_resolution=inv_res,
                                    )

                                    # Run analysis on the selected column with the active config
                                    col_analysis = analyze_numeric_column(
                                        engine, db_name, working_tbl, active_numeric_col, active_config
                                    )
                                    st.session_state.numeric_column_analyses[active_numeric_col] = col_analysis

                                    # KPI summary cards
                                    k_col1, k_col2, k_col3, k_col4 = st.columns(4)
                                    total_r = col_analysis["total_rows"]
                                    valid_r = col_analysis["valid_count"]
                                    compat_pct = col_analysis["numeric_percentage"]
                                    rec_type = col_analysis["recommended_type"]
                                    classif = col_analysis["classification"]

                                    with k_col1:
                                        st.markdown(
                                            f"""
                                            <div class="kpi-card">
                                                <div class="kpi-label">Analyzed Rows</div>
                                                <div class="kpi-value">{total_r:,}</div>
                                                <div class="kpi-subtext">Current type: {col_analysis['current_type']}</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    with k_col2:
                                        kpi_cls = "kpi-card-success" if compat_pct >= 90 else "kpi-card-warning" if compat_pct >= 50 else ""
                                        st.markdown(
                                            f"""
                                            <div class="kpi-card {kpi_cls}">
                                                <div class="kpi-label">Numeric Compatibility</div>
                                                <div class="kpi-value">{compat_pct:.1f}%</div>
                                                <div class="kpi-subtext">{valid_r:,} valid numbers</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    with k_col3:
                                        st.markdown(
                                            f"""
                                            <div class="kpi-card">
                                                <div class="kpi-label">Classification</div>
                                                <div class="kpi-value" style="font-size: 1.05rem; word-break: break-word;">{classif}</div>
                                                <div class="kpi-subtext">Integer digits: {col_analysis['max_integer_digits']} | Scale: {col_analysis['max_scale']}</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )
                                    with k_col4:
                                        st.markdown(
                                            f"""
                                            <div class="kpi-card kpi-card-success">
                                                <div class="kpi-label">Recommended Type</div>
                                                <div class="kpi-value" style="font-size: 1.25rem;">{rec_type}</div>
                                                <div class="kpi-subtext">Zero truncation guarantee</div>
                                            </div>
                                            """,
                                            unsafe_allow_html=True,
                                        )

                                    # Detailed Value Breakdown Chips
                                    inv_cnt = col_analysis["invalid_count"]
                                    ambig_cnt = col_analysis["ambiguous_count"]
                                    ident_cnt = col_analysis["potential_identifier_count"]
                                    null_cnt = col_analysis["null_count"]
                                    empty_cnt = col_analysis["empty_count"]

                                    st.markdown(
                                        f"""
                                        <div style="margin-top: 0.5rem; margin-bottom: 1rem; display: flex; flex-wrap: wrap; gap: 0.5rem;">
                                            <span class="badge-pill badge-neutral">Valid Integers: <b>{col_analysis['integer_count']:,}</b></span>
                                            <span class="badge-pill badge-neutral">Valid Decimals: <b>{col_analysis['decimal_count']:,}</b></span>
                                            <span class="badge-pill badge-neutral">Required Normalization: <b>{col_analysis['normalized_count']:,}</b></span>
                                            <span class="badge-pill {'badge-warning' if inv_cnt > 0 else 'badge-neutral'}">Invalid Values: <b>{inv_cnt:,}</b></span>
                                            <span class="badge-pill {'badge-warning' if ambig_cnt > 0 else 'badge-neutral'}">Ambiguous Formats: <b>{ambig_cnt:,}</b></span>
                                            <span class="badge-pill {'badge-warning' if ident_cnt > 0 else 'badge-neutral'}">Potential Identifiers: <b>{ident_cnt:,}</b></span>
                                            <span class="badge-pill badge-neutral">NULL Values: <b>{null_cnt:,}</b></span>
                                            <span class="badge-pill badge-neutral">Empty / Whitespace: <b>{empty_cnt:,}</b></span>
                                        </div>
                                        """,
                                        unsafe_allow_html=True,
                                    )

                                    # Section 5: Target Numeric Data Type Selection
                                    precision_warnings = []
                                    with st.container(border=True):
                                        st.markdown("##### Target Numeric Data Type")
                                        c_type1, c_type2 = st.columns([2.5, 2])
                                        with c_type1:
                                            # Supported MySQL target types: INT, BIGINT, DECIMAL(p,s), DOUBLE
                                            type_options = ["INT", "BIGINT", "DECIMAL(p,s)", "DOUBLE"]
                                            rec_prefix = rec_type.split("(")[0].strip()
                                            if rec_prefix == "DECIMAL":
                                                default_type_idx = 2
                                            elif rec_prefix == "BIGINT":
                                                default_type_idx = 1
                                            elif rec_prefix == "INT":
                                                default_type_idx = 0
                                            elif rec_prefix == "DOUBLE":
                                                default_type_idx = 3
                                            else:
                                                default_type_idx = 2

                                            selected_target_type = st.selectbox(
                                                "Select Target Data Type:",
                                                options=type_options,
                                                index=default_type_idx,
                                                key="num_target_type_select",
                                                help="Recommended type is based on data profiling. DECIMAL provides exact precision for financial amounts. Integer types suit whole numbers. DOUBLE provides floating-point approximation.",
                                            )

                                            if selected_target_type == "DECIMAL(p,s)":
                                                cd_p, cd_s = st.columns(2)
                                                with cd_p:
                                                    dec_precision = st.number_input(
                                                        "Precision (p)",
                                                        min_value=1,
                                                        max_value=65,
                                                        value=max(col_analysis["max_integer_digits"] + col_analysis["max_scale"] + 2, 10),
                                                        key="num_dec_p",
                                                        help="Total number of significant digits (1-65).",
                                                    )
                                                with cd_s:
                                                    dec_scale = st.number_input(
                                                        "Scale (s)",
                                                        min_value=0,
                                                        max_value=30,
                                                        value=max(col_analysis["max_scale"], 2),
                                                        key="num_dec_s",
                                                        help="Number of digits to the right of the decimal point (0-30).",
                                                    )
                                                target_sql_type = f"DECIMAL({dec_precision}, {dec_scale})"
                                            else:
                                                target_sql_type = selected_target_type

                                            st.caption(f"Recommended: `COLUMN {active_numeric_col} {rec_type}` | Selected: `COLUMN {active_numeric_col} {target_sql_type}`")

                                        with c_type2:
                                            # Type checks & Precision / Truncation / Overflow risk warnings
                                            st.markdown("<div style='font-size: 0.82rem; font-weight: 600; color: var(--dq-slate);'>Precision & Safety Checks:</div>", unsafe_allow_html=True)
                                            if selected_target_type in ("INT", "BIGINT") and col_analysis["decimal_count"] > 0:
                                                warn_msg = f"Fractional Truncation Risk: Column contains {col_analysis['decimal_count']} decimal value(s). Converting to {selected_target_type} will discard fractional components."
                                                precision_warnings.append(warn_msg)
                                                st.warning(warn_msg)
                                            elif selected_target_type == "INT" and col_analysis["max_integer_digits"] > 9:
                                                warn_msg = f"Integer Overflow Risk: Max integer digits is {col_analysis['max_integer_digits']}, which may exceed MySQL INT range (-2.14B to +2.14B). Consider BIGINT."
                                                precision_warnings.append(warn_msg)
                                                st.warning(warn_msg)
                                            elif selected_target_type == "DECIMAL(p,s)":
                                                if dec_scale < col_analysis["max_scale"]:
                                                    warn_msg = f"Fractional Scale Truncation: Configured scale ({dec_scale}) is less than observed decimal scale ({col_analysis['max_scale']})."
                                                    precision_warnings.append(warn_msg)
                                                    st.warning(warn_msg)
                                                if (dec_precision - dec_scale) < col_analysis["max_integer_digits"]:
                                                    warn_msg = f"Decimal Overflow Risk: Integer digits ({dec_precision - dec_scale}) is less than observed integer digits ({col_analysis['max_integer_digits']})."
                                                    precision_warnings.append(warn_msg)
                                                    st.warning(warn_msg)
                                            elif selected_target_type == "DOUBLE" and col_analysis["decimal_count"] > 0:
                                                warn_msg = "Floating-point precision: DOUBLE uses IEEE 754 floating-point representation. For currency/exact financial amounts, DECIMAL(p,s) is recommended."
                                                precision_warnings.append(warn_msg)
                                                st.info(warn_msg)

                                            if not precision_warnings:
                                                st.success("Target type fully accommodates observed numeric range and precision without truncation.")

                                    # Section 6: Choose the Conversion Destination
                                    with st.container(border=True):
                                        st.markdown("##### Application Mode & Destination")
                                        has_unresolved_anomalies = (inv_cnt + ambig_cnt + ident_cnt) > 0

                                        if has_unresolved_anomalies:
                                            st.info(
                                                f"**New-Column Conversion Required:** Column `{active_numeric_col}` contains "
                                                f"**{inv_cnt + ambig_cnt + ident_cnt}** unresolved anomaly/invalid value(s). "
                                                "**'Convert Existing Column' is disabled** because in-place modification would result in permanent data loss or conversion errors. "
                                                "**Creating a new column preserves original values** in your source column and allows valid records to be converted, "
                                                "while unresolved records remain blank (SQL NULL) in the new column."
                                            )
                                            dest_choice = st.radio(
                                                "Conversion Destination:",
                                                options=[
                                                    "Option B: Create a New Column",
                                                ],
                                                index=0,
                                                key="num_dest_radio",
                                                help="Creating a new column preserves original values and allows valid records to be converted while unresolved records remain blank in the new column.",
                                            )
                                            st.caption("*Option A: Convert Existing Column is disabled because the column contains unresolved anomalies.*")
                                        else:
                                            dest_choice = st.radio(
                                                "Conversion Destination:",
                                                options=[
                                                    "Option A: Convert Existing Column",
                                                    "Option B: Create a New Column",
                                                ],
                                                index=0,
                                                key="num_dest_radio",
                                                help="Option A modifies the column in-place in the authorized workspace table. Option B creates a new numeric column and keeps the original text column unchanged.",
                                            )

                                        try:
                                            existing_tbl_cols = [c["name"] for c in inspect(engine).get_columns(working_tbl)]
                                        except Exception:
                                            existing_tbl_cols = []
                                        col_collision_error = None
                                        col_name_invalid_error = None

                                        if "Option A" in dest_choice:
                                            conv_mode = "in_place"
                                            new_col_name = None
                                            st.markdown(
                                                f'<div style="font-size: 0.88rem; color: var(--dq-slate); margin-top: 0.25rem;">'
                                                f'<b>Existing Column:</b> <code>{active_numeric_col}</code>: {col_analysis["current_type"]} → <code>{target_sql_type}</code>'
                                                f'</div>',
                                                unsafe_allow_html=True,
                                            )
                                        else:
                                            conv_mode = "new_column"
                                            c_dest1, c_dest2 = st.columns([2.5, 2.5])
                                            with c_dest1:
                                                proposed_default_name = f"{active_numeric_col}_numeric"
                                                new_col_name = st.text_input(
                                                    "New Target Column Name:",
                                                    value=proposed_default_name,
                                                    key="num_new_col_name_input",
                                                    help="Original text column will remain completely untouched. Enter a valid MySQL identifier for the new column.",
                                                ).strip()

                                            with c_dest2:
                                                # Validate identifier and check collisions
                                                if not new_col_name or not re.match(r"^[a-zA-Z0-9_$]+$", new_col_name) or len(new_col_name) > 64:
                                                    col_name_invalid_error = "Invalid column name. Must contain only alphanumeric characters, underscores, or '$' (max 64 chars)."
                                                    st.error(col_name_invalid_error)
                                                elif new_col_name in existing_tbl_cols:
                                                    col_collision_error = f"Column collision: A column named '{new_col_name}' already exists in table '{working_tbl}'. Please choose a distinct name."
                                                    st.error(col_collision_error)
                                                else:
                                                    st.success(f"Valid destination: `{new_col_name}` ({target_sql_type})")

                                    # Section 7: Final Preview and Confirmation
                                    st.markdown("---")
                                    st.markdown("##### Final Preview and Confirmation Summary")

                                    dest_desc = (
                                        f"Existing Column (`{active_numeric_col}`)"
                                        if conv_mode == "in_place"
                                        else f"New Column (`{new_col_name}`)"
                                    )
                                    norm_rules_summary = (
                                        f"Trim: {'Yes' if trim_ws else 'No'} | "
                                        f"Format: {NUMBER_FORMATS.get(sel_fmt, sel_fmt).split('(')[0].strip()} | "
                                        f"Plus Sign: {'Yes' if norm_plus else 'No'} | "
                                        f"Negative Sign: {'Strip / Positive' if strip_neg else 'Preserve'} | "
                                        f"Percentage (%): {'Preserve Value' if strip_pct else 'No'} | "
                                        f"Currency: {'Yes' if strip_curr else 'No'} | "
                                        f"Leading Zeros: {'Allowed' if allow_zeros else 'Protected'} | "
                                        f"Invalid Action: {inv_res}"
                                    )
                                    warn_summary = " • ".join(precision_warnings) if precision_warnings else "None detected (Clean numeric mapping)"

                                    with st.container(border=True):
                                        c_sum1, c_sum2 = st.columns(2)
                                        with c_sum1:
                                            st.markdown(
                                                f"""
                                                <div style="font-size: 0.85rem; line-height: 1.6; color: var(--dq-slate);">
                                                    <div><b>Selected Table:</b> <code>{working_tbl}</code> <span style="font-size: 0.78rem; color: var(--dq-slate-muted);">(Source: {tbl_name})</span></div>
                                                    <div><b>Selected Source Column:</b> <code>{active_numeric_col}</code></div>
                                                    <div><b>Current Data Type:</b> <code>{col_analysis['current_type']}</code></div>
                                                    <div><b>Target Numeric Type:</b> <code>{target_sql_type}</code></div>
                                                    <div><b>Conversion Destination:</b> {dest_desc}</div>
                                                    <div><b>New Column Name:</b> <code>{new_col_name if new_col_name else 'N/A'}</code></div>
                                                    <div><b>Normalization Rules:</b> <span style="font-size: 0.8rem;">{norm_rules_summary}</span></div>
                                                </div>
                                                    <div><b>Invalid / Unresolved Values:</b> {inv_cnt + ambig_cnt + ident_cnt:,}</div>
                                                    <div><b>NULL Values:</b> {null_cnt:,}</div>
                                                    <div><b>Precision / Data-Loss Warnings:</b> <span style="color: {'#B45309' if precision_warnings else '#0F766E'};">{warn_summary}</span></div>
                                                </div>
                                                """,
                                                unsafe_allow_html=True,
                                            )

                                    # Preview before conversion: Summary Metric Chips
                                    null_or_empty_cnt = null_cnt + col_analysis.get("empty_count", 0)
                                    pm1, pm2, pm3, pm4 = st.columns(4)
                                    with pm1:
                                        st.metric("Successfully Converted", f"{valid_r:,}", help="Count of valid numeric values that will be converted")
                                    with pm2:
                                        st.metric("Invalid Values", f"{inv_cnt:,}", help="Values containing invalid characters or syntax")
                                    with pm3:
                                        st.metric("Ambiguous Values", f"{ambig_cnt + ident_cnt:,}", help="Values with ambiguous separators or protected identifier formats")
                                    with pm4:
                                        st.metric("NULL / Empty Values", f"{null_or_empty_cnt:,}", help="Existing SQL NULLs or empty whitespace strings")

                                    if conv_mode == "new_column":
                                        st.info(
                                            f"**New Column Safe Conversion:** Creating `{new_col_name}` ({target_sql_type}). "
                                            f"Every safely convertible value will be converted according to selected normalization rules. "
                                            f"**Invalid and ambiguous values will become SQL NULL** in the new column, "
                                            f"while their original values remain completely untouched and available in source column `{active_numeric_col}`."
                                        )

                                    # Value-Level Conversion Preview Table (Original value, Proposed numeric value, Conversion status, Reason)
                                    preview_rows = col_analysis.get("sample_preview", [])
                                    if preview_rows:
                                        preview_records = []
                                        for p in preview_rows:
                                            orig_val = p.get("Original value", p.get("original", ""))
                                            is_val = p.get("is_valid", False)
                                            if conv_mode == "new_column" and not is_val:
                                                prop_val = "SQL NULL"
                                            else:
                                                prop_val = p.get("Proposed numeric value", p.get("Proposed value", p.get("normalized", "SQL NULL")))

                                            c_status = p.get("Conversion status", p.get("Status", "Valid" if is_val else "Invalid"))
                                            c_reason = p.get("Reason", p.get("error_reason", "-") if not is_val else "-")
                                            if not c_reason or c_reason == "":
                                                c_reason = "-" if is_val else "Cannot convert safely"

                                            preview_records.append({
                                                "Original value": orig_val,
                                                "Proposed numeric value": prop_val,
                                                "Conversion status": c_status,
                                                "Reason": c_reason,
                                            })

                                        st.markdown("###### Value-Level Conversion Preview")
                                        st.dataframe(
                                            pd.DataFrame(preview_records),
                                            use_container_width=True,
                                            hide_index=True,
                                        )

                                    total_blocking_issues = inv_cnt + ambig_cnt + ident_cnt
                                    is_blocked_by_invalid = (conv_mode == "in_place" and total_blocking_issues > 0 and inv_res == "block")
                                    is_blocked_by_name = (conv_mode == "new_column" and bool(col_name_invalid_error or col_collision_error))
                                    is_blocked = is_blocked_by_invalid or is_blocked_by_name

                                    if is_blocked_by_invalid:
                                        st.warning(
                                            f"**In-Place Conversion Blocked:** `{total_blocking_issues}` value(s) in `{active_numeric_col}` "
                                            f"cannot be converted safely without resolution (invalid characters, ambiguous formatting, or protected identifier). "
                                            f"Please choose **'Option B: Create a New Column'** to preserve original values and leave unresolved records blank (SQL NULL), "
                                            f"or change **Action on Invalid Values** to **'Set invalid and ambiguous values to NULL'** to proceed in-place."
                                        )

                                    if is_blocked_by_name:
                                        st.warning("**Conversion Blocked:** Please resolve the new column name collision or naming syntax error above.")

                                    # Footer Action Bar: Back button on the left, safety note, and Confirm Conversion Primary button on the right
                                    st.markdown('<div class="dc-footer-action-bar" style="margin-top: 20px; padding-top: 16px; border-top: 1px solid var(--border);">', unsafe_allow_html=True)
                                    col_foot_left, col_foot_right = st.columns([1.5, 3.5], vertical_alignment="center")
                                    with col_foot_left:
                                        if st.button("Back to Cleaning Hub", key="num_footer_back_btn"):
                                            nav_to_view("🧹 Cleaning Workspace", "🏠 Cleaning Hub")
                                            st.rerun()
                                    with col_foot_right:
                                        col_note, col_confirm = st.columns([2.3, 1.7], vertical_alignment="center")
                                        with col_note:
                                            st.caption(f"Applies strictly to `{working_tbl}`. Source remains read-only.")
                                        with col_confirm:
                                            execute_btn = st.button(
                                                "Confirm Conversion",
                                                type="primary",
                                                use_container_width=True,
                                                disabled=is_blocked,
                                                key="num_confirm_conversion_btn",
                                                help="Executes schema conversion strictly within the authorized workspace table.",
                                            )
                                    st.markdown('</div>', unsafe_allow_html=True)

                                    if execute_btn:
                                        with st.spinner(f"Converting `{active_numeric_col}` to `{target_sql_type}` in `{working_tbl}`..."):
                                            conv_ok, conv_msg, conv_rep = convert_column_to_numeric_workspace(
                                                engine,
                                                db_name,
                                                working_tbl,
                                                active_numeric_col,
                                                target_sql_type,
                                                config=active_config,
                                                conversion_mode=conv_mode,
                                                new_column_name=new_col_name,
                                            )

                                        if conv_ok:
                                            st.session_state.numeric_conversion_report = conv_rep
                                            st.session_state.numeric_history.append(conv_rep)

                                            # Record in audit log
                                            if "cleaning_history" not in st.session_state:
                                                st.session_state.cleaning_history = []
                                            st.session_state.cleaning_history.append({
                                                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                                                "operation": "Numeric Data Conversion",
                                                "table": working_tbl,
                                                "source_column": active_numeric_col,
                                                "target_type": target_sql_type,
                                                "destination": dest_desc,
                                                "normalization_rules": norm_rules_summary,
                                                "rows_converted": conv_rep.get("rows_converted", 0),
                                                "invalid_nullified": conv_rep.get("invalid_nullified", 0),
                                                "status": "SUCCESS",
                                                "verified_type": conv_rep.get("verified_type"),
                                            })

                                            # Refresh workspace profile and cache
                                            st.session_state.profile_result = None
                                            st.session_state.numeric_scan_results = None
                                            st.success(f"{conv_msg}")
                                            st.rerun()
                                        else:
                                            st.error(f"Conversion Failed: {conv_msg}")

                                    # Post-Conversion Executive Report
                                    if st.session_state.get("numeric_conversion_report"):
                                        c_rep = st.session_state.numeric_conversion_report
                                        st.markdown(
                                            '<div class="dq-section-title" style="margin-top: 1.5rem;">Executive Numeric Conversion Report</div>',
                                            unsafe_allow_html=True,
                                        )
                                        with st.container(border=True):
                                            st.success(
                                                f"Column `{c_rep.get('column_name')}` successfully transformed to `{c_rep.get('target_type')}` "
                                                f"(Verified MySQL Type: `{c_rep.get('verified_type')}`)."
                                            )
                                            rc_k1, rc_k2, rc_k3 = st.columns(3)
                                            with rc_k1:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card kpi-card-success">
                                                        <div class="kpi-label">Rows Converted</div>
                                                        <div class="kpi-value">{c_rep.get('rows_converted', 0):,}</div>
                                                        <div class="kpi-subtext">Values transformed</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )
                                            with rc_k2:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card">
                                                        <div class="kpi-label">Invalid Set to NULL</div>
                                                        <div class="kpi-value">{c_rep.get('invalid_nullified', 0):,}</div>
                                                        <div class="kpi-subtext">Non-numeric records</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )
                                            with rc_k3:
                                                st.markdown(
                                                    f"""
                                                    <div class="kpi-card">
                                                        <div class="kpi-label">Total Table Rows</div>
                                                        <div class="kpi-value">{c_rep.get('total_rows', 0):,}</div>
                                                        <div class="kpi-subtext">Row count preserved</div>
                                                    </div>
                                                    """,
                                                    unsafe_allow_html=True,
                                                )

                        elif active_sub == "🤖 AI Assistant":
                            if not _ai_page_rendered:
                                render_ai_assistant_main(
                                    on_back_to_hub=lambda: nav_to_view("🧹 Cleaning Workspace", "🏠 Cleaning Hub")
                                )

                        elif active_sub == "🧠 AI Column Analysis and Cleaning":
                            render_ai_column_cleaning_view(
                                engine=engine,
                                db_name=db_name,
                                tbl_name=tbl_name,
                                on_back_to_hub=lambda: nav_to_view("🧹 Cleaning Workspace", "🏠 Cleaning Hub")
                            )

            # ── Floating Window (Modal Dialog): Data Profile ────────────────
            if st.session_state.get("show_profile_dialog"):
                render_data_profile_dialog(engine, db_name, tbl_name)

        elif (
            st.session_state.selected_db
            and st.session_state.selected_db != "-- Select Database --"
        ):
            st.info(
                "Please select a source table from the dropdown above to begin schema inspection and data cleaning."
            )
