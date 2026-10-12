"""
DataClean Studio — Enterprise Solid Light Theme (Teal Edition)
ui/theme.py

Single source of truth for all application styling.
Rule #1: Readability first. Every piece of text sits on a SOLID, OPAQUE surface.
No glassmorphism, no backdrop-filter, no translucent panels behind text.

Call `inject_theme()` once at the top of app.py after `st.set_page_config()`.

Streamlit version notes:
-----------------------
• Targets Streamlit >= 1.25.
• [data-testid="stVerticalBlockBorderWrapper"] handles st.container(border=True) (added in 1.24).
• [data-testid="stModal"] handles @st.dialog (added in 1.32), with div[role="dialog"] fallback for 1.25–1.31.
• [data-baseweb="select"] and [data-baseweb="popover"] ensure dropdowns and options are styled across BaseWeb updates.
• Streamlit's native iframe/canvas dataframes inherit config.toml [theme] base="light".
"""

from __future__ import annotations

import pathlib
import base64

_BG_PATH = pathlib.Path(__file__).resolve().parent.parent / "Background.png"
if not _BG_PATH.exists():
    _BG_PATH = pathlib.Path(__file__).resolve().parent.parent / "img" / "Background.png"

def _get_background_base64() -> str:
    if _BG_PATH.exists():
        return base64.b64encode(_BG_PATH.read_bytes()).decode()
    return ""


import streamlit as st


def inject_theme() -> None:
    """Injects the enterprise solid light design system into the Streamlit application."""
    css = _build_css()
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)


# Backwards compatibility alias
inject_glass_theme = inject_theme


def _build_css() -> str:
    bg_b64 = _get_background_base64()
    css = """
/* ============================================================
   DataClean Studio — Enterprise Solid Light Design System
   ui/theme.py  →  inject_theme()
   ============================================================ */

/* ── Google Fonts: Inter & JetBrains Mono ─────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Design Tokens ────────────────────────────────────────── */
:root {
    /* Background and surfaces */
    --bg-base:          #F4F7FA;
    --bg-gradient:      linear-gradient(160deg, #F4F7FA 0%, #E8EEF4 55%, #E3F1EF 100%);
    --surface:          #FFFFFF;
    --surface-alt:      #F8FAFC;
    --border:           #CBD5E1;
    --border-strong:    #94A3B8;
    --shadow-sm:        0 1px 2px rgba(15, 23, 42, 0.06), 0 1px 3px rgba(15, 23, 42, 0.08);
    --shadow-md:        0 4px 6px rgba(15, 23, 42, 0.05), 0 10px 24px rgba(15, 23, 42, 0.08);

    /* Text */
    --text-primary:     #0F172A;
    --text-secondary:   #334155;
    --text-muted:       #475569;   /* The lightest text allowed anywhere */
    --text-placeholder: #64748B;
    --text-on-accent:   #FFFFFF;

    /* Accent (Deep Teal) */
    --accent:           #0F766E;
    --accent-strong:    #115E59;
    --accent-soft:      #CCFBF1;
    --accent-soft-text: #134E4A;
    --link:             #0E7490;
    --focus-ring:       0 0 0 3px rgba(15, 118, 110, 0.30);

    /* Status — solid tinted fill + dark matching text + 4px left border */
    --status-success-bg:     #DCFCE7;
    --status-success-text:   #166534;
    --status-success-border: #16A34A;

    --status-warning-bg:     #FEF3C7;
    --status-warning-text:   #92400E;
    --status-warning-border: #D97706;

    --status-danger-bg:      #FEE2E2;
    --status-danger-text:    #991B1B;
    --status-danger-border:  #DC2626;

    --status-info-bg:        #CCFBF1;
    --status-info-text:      #134E4A;
    --status-info-border:    #0F766E;

    /* Radius & Spacing */
    --r-sm:   8px;
    --r-md:   12px;
    --r-lg:   16px;
    --r-pill: 9999px;

    /* Fonts */
    --font-sans: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    --font-mono: 'JetBrains Mono', 'Fira Code', Menlo, Monaco, Consolas, monospace;

    /* Transitions */
    --transition: 150ms cubic-bezier(0.4, 0, 0.2, 1);

    /* Legacy mapping helpers so custom HTML continues rendering seamlessly */
    --dq-bg: var(--bg-base);
    --dq-surface: var(--surface);
    --dq-surface2: var(--surface-alt);
    --dq-border: var(--border);
    --dq-border-hover: var(--border-strong);
    --dq-text-primary: var(--text-primary);
    --dq-text-secondary: var(--text-secondary);
    --dq-text-muted: var(--text-muted);
    --dq-slate: var(--text-secondary);
    --dq-slate-muted: var(--text-muted);
    --dq-slate-text: var(--text-primary);
    --dq-accent: var(--accent);
    --dq-accent-glow: rgba(15, 118, 110, 0.12);
    --dq-accent-border: rgba(15, 118, 110, 0.35);
    --dq-accent-focus: rgba(15, 118, 110, 0.30);
    --dq-accent-gradient: linear-gradient(135deg, #0F766E 0%, #115E59 100%);
    --dq-success: var(--status-success-border);
    --dq-success-bg: var(--status-success-bg);
    --dq-success-border: var(--status-success-border);
    --dq-success-text: var(--status-success-text);
    --dq-warning: var(--status-warning-border);
    --dq-warning-bg: var(--status-warning-bg);
    --dq-warning-border: var(--status-warning-border);
    --dq-warning-text: var(--status-warning-text);
    --dq-danger: var(--status-danger-border);
    --dq-danger-bg: var(--status-danger-bg);
    --dq-danger-border: var(--status-danger-border);
    --dq-danger-text: var(--status-danger-text);
    --glass-bg: #FFFFFF;
    --glass-border: 1px solid var(--border);
    --glass-shadow: var(--shadow-sm);
    --glass-shadow-lg: var(--shadow-md);
}

/* ── Global Reset & Base Typography ───────────────────────── */
html, body, .stApp {
    font-family: var(--font-sans) !important;
    font-size: 14px !important;
    line-height: 1.6 !important;
    color: var(--text-primary) !important;
    background: var(--bg-gradient) !important;
    -webkit-font-smoothing: antialiased;
}

code, .mono {
    font-family: var(--font-mono) !important;
    font-size: 0.88em !important;
}

/* Nothing below 12-13px */
small, .caption,
[data-testid="stCaptionContainer"] p,
[data-testid="stWidgetLabel"] small {
    font-size: 13px !important;
}

[data-testid="stHelp"], .stCaption,
[data-testid="stCaptionContainer"] {
    color: var(--text-muted) !important;
    font-size: 13px !important;
}

a {
    color: var(--link) !important;
    text-decoration: underline;
    text-underline-offset: 2px;
}
a:hover {
    color: var(--accent-strong) !important;
}

/* ── Streamlit Chrome Overrides ───────────────────────────── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
.stAppToolbar {
    background: transparent !important;
    box-shadow: none !important;
}

footer, #MainMenu {
    display: none !important;
    visibility: hidden !important;
}
.main {
    background: transparent !important;
}

/* ── Page Background: Blended Background.png ─ */
[data-testid="stAppViewContainer"] {
    background-color: #F8FCFD !important;
    background-image: url("__BG_IMAGE_PLACEHOLDER__") !important;
    background-size: cover !important;
    background-position: center top !important;
    background-repeat: no-repeat !important;
    background-attachment: fixed !important;
    position: relative !important;
    isolation: isolate !important;
}

[data-testid="stAppViewContainer"]::before {
    display: none !important;
}

/* Content layer sits strictly above the background */
[data-testid="stMain"],
[data-testid="stHeader"] {
    position: relative;
    z-index: 1;
}

[data-testid="stSidebar"] {
    position: relative;
    z-index: 100 !important;
}

/* Ensure any container holding the credential dialog rises above all others when active */
[data-testid="stSidebar"]:has(.cred-dialog-overlay:not([style*="display: none"])),
[data-testid="stSidebar"]:has(#credential-error-dialog-container:not([style*="display: none"])),
[data-testid="stMain"]:has(.cred-dialog-overlay:not([style*="display: none"])),
[data-testid="stMain"]:has(#credential-error-dialog-container:not([style*="display: none"])),
[data-testid="stAppViewContainer"]:has(.cred-dialog-overlay:not([style*="display: none"])),
div:has(> .cred-dialog-overlay:not([style*="display: none"])) {
    z-index: 99999999 !important;
}

/* ── 1. SIDEBAR ───────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #FFFFFF 0%, #F1F5F9 100%) !important;
    border-right: 1px solid var(--border) !important;
    box-shadow: var(--shadow-sm) !important;
}
[data-testid="stSidebar"] > div:first-child {
    padding: 24px 18px 32px 18px !important;
    height: 100vh !important;
    overflow-y: auto !important;
    box-sizing: border-box !important;
}
[data-testid="stSidebar"] * {
    color: var(--text-primary);
}

.sidebar-section-header {
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: var(--text-muted) !important;
    margin-top: 22px !important;
    margin-bottom: 8px !important;
}

.sidebar-brand-block {
    display: flex;
    align-items: center;
    gap: 12px;
    padding-bottom: 16px;
    margin-bottom: 20px;
    border-bottom: 2px solid transparent;
    border-image: linear-gradient(90deg, #0F766E 0%, #14B8A6 100%) 1;
}
.sidebar-brand-icon {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 40px; height: 40px;
    border-radius: var(--r-sm);
    background: var(--accent-soft);
    border: 1px solid rgba(15, 118, 110, 0.25);
    font-size: 1.3rem;
    flex-shrink: 0;
}
.sidebar-brand-title {
    font-size: 16px;
    font-weight: 700;
    color: var(--text-primary) !important;
    letter-spacing: -0.01em;
}
.sidebar-brand-sub {
    font-size: 12px;
    color: var(--text-muted) !important;
    margin-top: 2px;
}

/* Sidebar button sizing & layout */
[data-testid="stSidebar"] .stButton > button {
    width: 100% !important;
    white-space: nowrap !important;
    padding: 8px 12px !important;
    font-size: 13.5px !important;
}

/* ── 2. HEADER CARD ───────────────────────────────────────── */
.app-top-header {
    max-width: 1100px;
    width: 100%;
    margin: 0 auto 28px auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: linear-gradient(120deg, #0F172A 0%, #134E4A 100%) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--shadow-md) !important;
    box-sizing: border-box;
}
.app-top-brand {
    display: flex;
    align-items: center;
    gap: 14px;
}
.app-top-logo {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 42px; height: 42px;
    border-radius: var(--r-md);
    background: rgba(255, 255, 255, 0.12);
    border: 1px solid rgba(255, 255, 255, 0.20);
    font-size: 1.3rem;
    flex-shrink: 0;
}
.app-top-title {
    font-size: 18px;
    font-weight: 700;
    color: #FFFFFF !important;
    line-height: 1.2;
}
.app-top-tagline {
    font-size: 13px;
    color: #CBD5E1 !important;
    margin-top: 2px;
}
.app-top-meta {
    display: flex;
    align-items: center;
    gap: 10px;
}

/* Header status pills */
.status-pill {
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 5px 12px;
    border-radius: var(--r-pill);
    font-size: 12px;
    font-weight: 600;
}
.status-pill.status-connected {
    background-color: #DCFCE7 !important;
    color: #166534 !important;
    border: 1px solid #16A34A !important;
}
.status-pill.status-disconnected {
    background-color: #FEE2E2 !important;
    color: #991B1B !important;
    border: 1px solid #DC2626 !important;
}
.status-pill-dot {
    width: 7px; height: 7px;
    border-radius: 50%;
    background: currentColor;
    display: inline-block;
}
.version-tag {
    background-color: #FFFFFF !important;
    color: #0F172A !important;
    border: 1px solid var(--border) !important;
    font-size: 12px;
    font-weight: 600;
    padding: 4px 10px;
    border-radius: 6px;
}
/* Delete/hide any theme pill in header */
.theme-badge,
div.st-key-floating_theme_toggle {
    display: none !important;
}

/* ── 3. HERO TITLE & HIGHLIGHT ────────────────────────────── */
.hero-headline {
    color: var(--text-primary) !important;
    font-size: 38px !important;
    font-weight: 700 !important;
    letter-spacing: -0.025em;
    line-height: 1.15 !important;
    margin: 0 0 16px 0;
}
.gradient-text {
    color: #0F766E !important;
    background: linear-gradient(90deg, #0F766E 0%, #164E63 100%) !important;
    -webkit-background-clip: text !important;
    -webkit-text-fill-color: transparent !important;
    display: inline;
}
.hero-subtitle {
    font-size: 15px;
    color: var(--text-secondary) !important;
    max-width: 820px;
    margin: 0 0 24px 0;
    line-height: 1.55;
}

/* ── 4. CARDS, CONTAINERS & STEP BAR ──────────────────────── */
.feature-card,
[data-testid="stVerticalBlockBorderWrapper"],
.db-conn-panel,
.steps-timeline-container {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--shadow-md) !important;
    position: relative;
    overflow: hidden;
}

/* 3px top accent bar */
.feature-top-accent,
.feature-card::before,
[data-testid="stVerticalBlockBorderWrapper"]::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #0F766E 0%, #14B8A6 100%);
    z-index: 2;
}

.feature-title {
    font-size: 17px;
    font-weight: 700;
    color: var(--text-primary) !important;
    margin-bottom: 8px;
}
.feature-desc {
    font-size: 14px;
    color: var(--text-secondary) !important;
    line-height: 1.6;
    margin: 0 0 16px 0;
}
.feature-micro-link {
    font-size: 13px;
    font-weight: 600;
    color: var(--link) !important;
    display: inline-flex;
    align-items: center;
    gap: 4px;
    text-decoration: none;
}
.feature-micro-link:hover {
    text-decoration: underline;
}

/* Step-number circles: solid teal with white numbers */
.step-number {
    width: 36px; height: 36px;
    border-radius: 50%;
    background-color: var(--accent) !important;
    color: #FFFFFF !important;
    font-size: 15px;
    font-weight: 700;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.step-title {
    font-size: 14px;
    font-weight: 600;
    color: var(--text-primary) !important;
}
.step-desc {
    font-size: 13px;
    color: var(--text-secondary) !important;
    margin-top: 2px;
}

/* ── 5. METRICS ───────────────────────────────────────────── */
[data-testid="stMetric"],
.kpi-card {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-left: 4px solid var(--accent) !important;
    border-radius: var(--r-md) !important;
    padding: 16px 18px !important;
    box-shadow: var(--shadow-sm) !important;
    position: relative;
    overflow: hidden;
}
[data-testid="stMetricLabel"],
.kpi-label {
    color: var(--text-muted) !important;
    font-size: 12px !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}
[data-testid="stMetricValue"],
.kpi-value {
    color: var(--text-primary) !important;
    font-size: 28px !important;
    font-weight: 700 !important;
}
[data-testid="stMetricDelta"],
.kpi-subtext {
    font-size: 13px !important;
    color: var(--text-muted) !important;
}

/* ── 6. INPUTS (Text, Number, Password) ───────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {
    background-color: #FFFFFF !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--r-sm) !important;
    font-size: 14px !important;
    padding: 0 12px !important;
    min-height: 40px !important;
    transition: border-color var(--transition), box-shadow var(--transition) !important;
}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {
    border-color: var(--accent) !important;
    box-shadow: var(--focus-ring) !important;
    outline: none !important;
}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {
    color: var(--text-placeholder) !important;
    opacity: 1 !important;
}
[data-testid="stWidgetLabel"] label,
[data-testid="stWidgetLabel"] p {
    color: var(--text-primary) !important;
    font-size: 13px !important;
    font-weight: 600 !important;
    margin-bottom: 4px !important;
}
[data-testid="stTextInput"] button[aria-label*="password" i],
[data-testid="stTextInput"] svg {
    fill: var(--text-secondary) !important;
    color: var(--text-secondary) !important;
}

/* ── 7. SELECTBOX & DROPDOWNS ─────────────────────────────── */
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {
    background-color: #FFFFFF !important;
    color: var(--text-primary) !important;
    border: 1px solid var(--border-strong) !important;
    border-radius: var(--r-sm) !important;
    min-height: 40px !important;
    transition: border-color var(--transition), box-shadow var(--transition) !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within {
    border-color: var(--accent) !important;
    box-shadow: var(--focus-ring) !important;
}
[data-testid="stSelectbox"] [data-baseweb="select"] span {
    color: var(--text-primary) !important;
}
[data-baseweb="popover"] [data-baseweb="menu"] {
    background-color: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    box-shadow: var(--shadow-md) !important;
    padding: 6px 0 !important;
}
[data-baseweb="popover"] [data-baseweb="menu"] li {
    color: var(--text-primary) !important;
    font-size: 14px !important;
    padding: 8px 14px !important;
    transition: background-color var(--transition) !important;
}
[data-baseweb="popover"] [data-baseweb="menu"] li:hover {
    background-color: #F1F5F9 !important;
}
[data-baseweb="popover"] [data-baseweb="menu"] li[aria-selected="true"] {
    background-color: var(--accent-soft) !important;
    color: var(--accent-soft-text) !important;
    font-weight: 600 !important;
}

/* ── 8. RADIO / SEGMENTED CONTROLS ────────────────────────── */
div[data-testid="stRadio"] > div {
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 4px !important;
    background-color: #E2E8F0 !important;
    border: 1px solid var(--border) !important;
    border-radius: 10px !important;
    padding: 4px !important;
    width: 100% !important;
}
div[data-testid="stRadio"] label {
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex: 1 !important;
    min-width: 72px !important;
    padding: 7px 14px !important;
    border-radius: 6px !important;
    cursor: pointer !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    color: var(--text-secondary) !important;
    background: transparent !important;
    border: none !important;
    transition: all var(--transition) !important;
    margin: 0 !important;
}
/* Hide stray native radio circles */
div[data-testid="stRadio"] label > div:first-child {
    display: none !important;
}
div[data-testid="stRadio"] label:hover {
    color: var(--text-primary) !important;
    background-color: rgba(255, 255, 255, 0.45) !important;
}
div[data-testid="stRadio"] label:has(input[type="radio"]:checked) {
    background-color: #FFFFFF !important;
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    border-bottom: 2px solid var(--accent) !important;
    box-shadow: var(--shadow-sm) !important;
}

/* Workspace 4-col sub tabs */
div.st-key-_ws_sub_radio > div[data-testid="stRadio"] > div {
    display: grid !important;
    grid-template-columns: repeat(4, 1fr) !important;
    gap: 6px !important;
    background: transparent !important;
    border: none !important;
    padding: 0 !important;
}
div.st-key-_ws_sub_radio > div[data-testid="stRadio"] label {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    padding: 10px 8px !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--shadow-sm) !important;
}
div.st-key-_ws_sub_radio > div[data-testid="stRadio"] label:has(input[type="radio"]:checked) {
    border-color: var(--accent) !important;
    border-bottom: 3px solid var(--accent) !important;
}

/* ── 9. TABS ──────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {
    background: transparent !important;
    border-bottom: 1px solid var(--border) !important;
    gap: 8px !important;
    padding-bottom: 2px !important;
}
[data-testid="stTabs"] [data-baseweb="tab"] {
    background: transparent !important;
    border: none !important;
    color: var(--text-muted) !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    transition: color var(--transition) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {
    color: var(--text-primary) !important;
}
[data-testid="stTabs"] [data-baseweb="tab"][aria-selected="true"] {
    color: var(--accent) !important;
    font-weight: 600 !important;
    border-bottom: 3px solid var(--accent) !important;
}
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {
    display: none !important;
}

/* ── 10. BUTTONS ──────────────────────────────────────────── */
.stButton > button,
button[data-testid^="stBaseButton"] {
    border-radius: var(--r-sm) !important;
    font-weight: 600 !important;
    font-size: 14px !important;
    transition: transform var(--transition), box-shadow var(--transition), background-color var(--transition) !important;
    cursor: pointer !important;
}
/* Primary Button */
button[data-testid="stBaseButton-primary"],
button[kind="primary"],
div[class*="st-key-sb_connect"] button,
div[class*="st-key-hub_open_"] button,
div[class*="st-key-open_ws_btn"] button {
    background: linear-gradient(135deg, #0F766E 0%, #115E59 100%) !important;
    border: 1px solid #115E59 !important;
    color: #FFFFFF !important;
    box-shadow: var(--shadow-sm) !important;
}
button[data-testid="stBaseButton-primary"]:hover,
button[kind="primary"]:hover,
div[class*="st-key-sb_connect"] button:hover,
div[class*="st-key-hub_open_"] button:hover,
div[class*="st-key-open_ws_btn"] button:hover {
    transform: translateY(-1px) !important;
    box-shadow: var(--shadow-md) !important;
    filter: brightness(1.08) !important;
}

/* Secondary Button */
button[data-testid="stBaseButton-secondary"],
button[kind="secondary"],
div[class*="st-key-sb_test"] button {
    background-color: #FFFFFF !important;
    border: 1px solid var(--border-strong) !important;
    color: var(--text-primary) !important;
    box-shadow: var(--shadow-sm) !important;
}
button[data-testid="stBaseButton-secondary"]:hover,
button[kind="secondary"]:hover,
div[class*="st-key-sb_test"] button:hover {
    background-color: #F1F5F9 !important;
    border-color: var(--accent) !important;
    color: var(--accent-strong) !important;
    transform: translateY(-1px) !important;
}

/* Danger Button */
div[class*="st-key-sb_disconnect"] button,
div[class*="st-key-hub_drop_"] button,
div[class*="st-key-drop_sb_btn"] button,
div[class*="st-key-disc_btn"] button,
div[class*="st-key-dl_pdf"] button {
    background-color: var(--status-danger-bg) !important;
    border: 1px solid var(--status-danger-border) !important;
    color: var(--status-danger-text) !important;
    box-shadow: none !important;
}
div[class*="st-key-sb_disconnect"] button:hover,
div[class*="st-key-hub_drop_"] button:hover,
div[class*="st-key-drop_sb_btn"] button:hover,
div[class*="st-key-disc_btn"] button:hover,
div[class*="st-key-dl_pdf"] button:hover {
    background-color: #B91C1C !important;
    border-color: #B91C1C !important;
    color: #FFFFFF !important;
    transform: translateY(-1px) !important;
}

/* Disabled */
.stButton > button:disabled,
button[data-testid^="stBaseButton"]:disabled {
    background-color: #E2E8F0 !important;
    color: #475569 !important;
    border-color: var(--border) !important;
    box-shadow: none !important;
    cursor: not-allowed !important;
}

/* ── 11. ALERTS & BANNERS ─────────────────────────────────── */
div[data-testid="stAlert"],
div[data-baseweb="notification"] {
    border-radius: var(--r-md) !important;
    padding: 14px 18px !important;
    box-shadow: var(--shadow-sm) !important;
    background-color: var(--status-info-bg) !important;
    color: var(--status-info-text) !important;
    border: 1px solid var(--status-info-border) !important;
    border-left: 4px solid var(--status-info-border) !important;
}
div[data-testid="stAlert"] p,
div[data-baseweb="notification"] p {
    color: var(--status-info-text) !important;
}

/* st.success */
div[data-testid="stAlert"]:has([data-testid="stAlertSuccess"]),
div[data-testid="stAlertSuccess"],
div[data-baseweb="notification"][kind="positive"] {
    background-color: var(--status-success-bg) !important;
    color: var(--status-success-text) !important;
    border: 1px solid var(--status-success-border) !important;
    border-left: 4px solid var(--status-success-border) !important;
}
div[data-testid="stAlert"]:has([data-testid="stAlertSuccess"]) p {
    color: var(--status-success-text) !important;
}

/* st.warning */
div[data-testid="stAlert"]:has([data-testid="stAlertWarning"]),
div[data-testid="stAlertWarning"],
div[data-baseweb="notification"][kind="warning"] {
    background-color: var(--status-warning-bg) !important;
    color: var(--status-warning-text) !important;
    border: 1px solid var(--status-warning-border) !important;
    border-left: 4px solid var(--status-warning-border) !important;
}
div[data-testid="stAlert"]:has([data-testid="stAlertWarning"]) p {
    color: var(--status-warning-text) !important;
}

/* st.error */
div[data-testid="stAlert"]:has([data-testid="stAlertError"]),
div[data-testid="stAlertError"],
div[data-baseweb="notification"][kind="negative"] {
    background-color: var(--status-danger-bg) !important;
    color: var(--status-danger-text) !important;
    border: 1px solid var(--status-danger-border) !important;
    border-left: 4px solid var(--status-danger-border) !important;
}
div[data-testid="stAlert"]:has([data-testid="stAlertError"]) p {
    color: var(--status-danger-text) !important;
}

/* Custom Safety / Sandbox Banners */
.safety-banner {
    display: flex;
    align-items: flex-start;
    gap: 12px;
    padding: 14px 18px;
    border-radius: var(--r-md);
    background-color: var(--status-success-bg) !important;
    color: var(--status-success-text) !important;
    border: 1px solid var(--status-success-border) !important;
    border-left: 4px solid var(--status-success-border) !important;
    margin-bottom: 14px;
    box-shadow: var(--shadow-sm);
}
.safety-banner h4 {
    color: var(--status-success-text) !important;
    margin: 0 0 4px 0;
}
.safety-banner p {
    color: var(--text-primary) !important;
    margin: 0;
}
.safety-banner-icon {
    font-size: 1.25rem;
    flex-shrink: 0;
    margin-top: 1px;
}
.safety-banner-warning {
    background-color: var(--status-warning-bg) !important;
    color: var(--status-warning-text) !important;
    border: 1px solid var(--status-warning-border) !important;
    border-left: 4px solid var(--status-warning-border) !important;
}
.safety-banner-warning h4 {
    color: var(--status-warning-text) !important;
}

.safety-banner code,
div[data-testid="stAlert"] code {
    background: rgba(15, 23, 42, 0.07) !important;
    color: var(--text-primary) !important;
    font-family: var(--font-mono) !important;
    padding: 2px 6px !important;
    border-radius: 4px !important;
}

/* Sidebar connection status card */
.sidebar-status-card {
    margin-top: 20px !important;
    padding: 16px 18px !important;
    background-color: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--shadow-sm) !important;
}
.sidebar-status-header {
    display: flex;
    align-items: center;
    gap: 10px;
}
.sidebar-status-dot {
    width: 10px; height: 10px;
    border-radius: 50%;
    display: inline-block;
}
.sidebar-status-dot.dot-connected {
    background-color: #16A34A;
}
.sidebar-status-dot.dot-disconnected {
    background-color: #DC2626;
}
.sidebar-status-title-connected {
    font-weight: 600;
    font-size: 14px;
    color: #166534;
}
.sidebar-status-title-disconnected {
    font-weight: 600;
    font-size: 14px;
    color: var(--text-primary);
}
.sidebar-status-chip {
    margin-left: auto;
    font-size: 11px;
    font-weight: 600;
    padding: 2px 7px;
    border-radius: 4px;
    background-color: #DCFCE7;
    color: #166534;
    border: 1px solid #16A34A;
    text-transform: uppercase;
}
.sidebar-status-meta {
    font-size: 13px;
    color: var(--text-muted);
    margin-top: 8px;
    line-height: 1.5;
}

/* ── 12. TABLES & DATAFRAMES ──────────────────────────────── */
[data-testid="stDataFrame"] {
    background-color: var(--surface) !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--shadow-sm) !important;
    overflow-x: auto !important;
}
table {
    width: 100%;
    border-collapse: collapse;
}
thead tr {
    background-color: #F1F5F9 !important;
}
thead th {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    border-bottom: 1px solid var(--border) !important;
}
tbody td {
    color: var(--text-primary) !important;
    font-size: 13px !important;
    padding: 10px 14px !important;
    border-bottom: 1px solid #E2E8F0 !important;
}
tbody tr:nth-child(even) {
    background-color: #F8FAFC !important;
}

/* ── 13. DIALOG / MODAL ───────────────────────────────────── */
div[data-testid="stModalOverlay"],
[data-baseweb="dialog"] [data-baseweb="backdrop"] {
    background: rgba(15, 23, 42, 0.55) !important;
}
div[data-testid="stModal"] > div:first-child,
div[role="dialog"] {
    background-color: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--shadow-md) !important;
    color: var(--text-primary) !important;
}
div[data-testid="stModal"] * {
    color: var(--text-primary);
}

.health-score-container {
    display: flex;
    align-items: center;
    gap: 20px;
    background-color: var(--surface);
    border: 1px solid var(--border);
    border-radius: var(--r-lg);
    padding: 20px 24px;
    margin-bottom: 20px;
    box-shadow: var(--shadow-sm);
}
.health-score-dial {
    width: 95px; height: 95px;
    border-radius: 50%;
    background-color: #FFFFFF !important;
    border: 4px solid var(--accent) !important;
    box-shadow: var(--shadow-sm);
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.health-score-number {
    font-size: 28px;
    font-weight: 800;
    color: var(--text-primary) !important;
    line-height: 1;
}
.health-score-pct {
    font-size: 12px;
    font-weight: 700;
    color: var(--text-muted) !important;
}

/* ── 14. EXPANDERS ────────────────────────────────────────── */
[data-testid="stExpander"] {
    background-color: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--shadow-sm) !important;
    overflow: hidden !important;
}
[data-testid="stExpander"] details {
    border: none !important;
}
[data-testid="stExpander"] summary {
    color: var(--text-primary) !important;
    font-weight: 600 !important;
    padding: 12px 16px !important;
    transition: background-color var(--transition) !important;
}
[data-testid="stExpander"] summary:hover {
    background-color: #F8FAFC !important;
}

/* ── 15. SLIDER & TOGGLE ──────────────────────────────────── */
[data-testid="stSlider"] [data-baseweb="slider"] div[class*="Track"] {
    background-color: #CBD5E1 !important;
}
[data-testid="stSlider"] [data-baseweb="slider"] [role="slider"] {
    background-color: #FFFFFF !important;
    border: 2px solid var(--border-strong) !important;
}
[data-testid="stToggle"] {
    background-color: #FFFFFF !important;
    border: 1px solid var(--border) !important;
    border-radius: var(--r-sm) !important;
    padding: 6px 12px !important;
}
[data-testid="stToggle"] label {
    color: var(--text-primary) !important;
    font-size: 13px !important;
}

/* ── 16. SCROLLBARS ───────────────────────────────────────── */
::-webkit-scrollbar {
    width: 6px !important;
    height: 6px !important;
}
::-webkit-scrollbar-track {
    background: transparent !important;
}
::-webkit-scrollbar-thumb {
    background: #94A3B8 !important;
    border-radius: 9999px !important;
}

/* ── Empty State ──────────────────────────────────────────── */
.empty-state-card {
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: 10px;
    padding: 36px 20px;
    border-radius: var(--r-md);
    border: 1.5px dashed var(--border);
    background-color: var(--surface-alt);
    text-align: center;
    margin: 16px 0;
}
.es-title {
    font-size: 15px;
    font-weight: 700;
    color: var(--text-primary);
}
.es-desc {
    font-size: 13px;
    color: var(--text-muted);
    max-width: 380px;
    line-height: 1.55;
}

/* Content wrapper */
.content-wrapper {
    max-width: 1100px;
    width: 100%;
    margin-left: auto;
    margin-right: auto;
    box-sizing: border-box;
}
.features-grid {
    max-width: 1100px;
    width: 100%;
    margin: 0 auto 32px auto;
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 24px;
    box-sizing: border-box;
}
@media (max-width: 900px) {
    .features-grid {
        grid-template-columns: 1fr;
    }
}

/* ── Credential Error Dialog Modal System ──────────────────── */
.cred-dialog-toggle-input:checked ~ .cred-dialog-overlay,
.cred-dialog-toggle-input:checked + .cred-dialog-overlay {
    display: none !important;
    opacity: 0 !important;
    visibility: hidden !important;
    pointer-events: none !important;
}

.cred-dialog-overlay {
    position: fixed !important;
    top: 0 !important;
    left: 0 !important;
    right: 0 !important;
    bottom: 0 !important;
    width: 100vw !important;
    height: 100vh !important;
    background: rgba(15, 23, 42, 0.45) !important;
    backdrop-filter: blur(4px) !important;
    -webkit-backdrop-filter: blur(4px) !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
    z-index: 99999999 !important;
    padding: 16px !important;
    box-sizing: border-box !important;
    pointer-events: auto !important;
}

.cred-dialog-backdrop-dismiss {
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    width: 100% !important;
    height: 100% !important;
    cursor: pointer !important;
    z-index: 1 !important;
    background: transparent !important;
}

.cred-dialog-box {
    position: relative !important;
    z-index: 100000000 !important;
    background: #FFFFFF !important;
    border: 1px solid #E2E8F0 !important;
    border-radius: 16px !important;
    box-shadow: 
        0 20px 25px -5px rgba(15, 23, 42, 0.15),
        0 8px 10px -6px rgba(15, 23, 42, 0.1),
        0 0 0 1px rgba(15, 23, 42, 0.05) !important;
    width: 90% !important;
    max-width: 440px !important;
    min-width: 280px !important;
    overflow: hidden !important;
    padding: 24px 24px 20px 24px !important;
    box-sizing: border-box !important;
    text-align: center !important;
    transform-origin: center center !important;
    pointer-events: auto !important;
}

.cred-dialog-icon-wrapper {
    display: flex !important;
    justify-content: center !important;
    margin-bottom: 14px !important;
}
.cred-dialog-icon {
    width: 48px !important;
    height: 48px !important;
    border-radius: 12px !important;
    background: #FEE2E2 !important;
    border: 1px solid #FECACA !important;
    display: flex !important;
    align-items: center !important;
    justify-content: center !important;
}

.cred-dialog-title {
    font-family: var(--font-sans) !important;
    font-size: 17px !important;
    font-weight: 700 !important;
    color: #0F172A !important;
    margin: 0 0 8px 0 !important;
    line-height: 1.3 !important;
    letter-spacing: -0.01em !important;
}
.cred-dialog-message {
    font-family: var(--font-sans) !important;
    font-size: 14px !important;
    font-weight: 500 !important;
    line-height: 1.5 !important;
    color: #334155 !important;
    margin: 0 0 16px 0 !important;
}

.cred-dialog-progress-track {
    width: 100% !important;
    height: 3px !important;
    background: #F1F5F9 !important;
    border-radius: 9999px !important;
    overflow: hidden !important;
    margin-top: 4px !important;
}
.cred-dialog-progress-bar {
    height: 100% !important;
    background: linear-gradient(90deg, #DC2626 0%, #EF4444 100%) !important;
    border-radius: 9999px !important;
    transform-origin: left !important;
}

.cred-dialog-close-btn {
    position: absolute !important;
    top: 12px !important;
    right: 14px !important;
    background: transparent !important;
    border: none !important;
    color: #94A3B8 !important;
    font-size: 22px !important;
    line-height: 1 !important;
    cursor: pointer !important;
    padding: 4px 8px !important;
    border-radius: 6px !important;
    transition: color 150ms, background-color 150ms !important;
    user-select: none !important;
    display: inline-block !important;
    z-index: 10 !important;
}
.cred-dialog-close-btn:hover {
    color: #0F172A !important;
    background-color: #F1F5F9 !important;
}

@keyframes credBoxScale {
    0% {
        opacity: 0;
        transform: scale(0.92) translateY(16px);
    }
    8.2% {
        opacity: 1;
        transform: scale(1) translateY(0);
    }
    88% {
        opacity: 1;
        transform: scale(1) translateY(0);
    }
    100% {
        opacity: 0;
        transform: scale(0.92) translateY(-8px);
        visibility: hidden;
        pointer-events: none;
    }
}

@keyframes credOverlayFade {
    0% {
        opacity: 0;
    }
    8.2% {
        opacity: 1;
    }
    88% {
        opacity: 1;
    }
    100% {
        opacity: 0;
        visibility: hidden;
        pointer-events: none;
    }
}

@keyframes credProgressBar {
    0% {
        width: 100%;
    }
    100% {
        width: 0%;
    }
}

@media (prefers-reduced-motion: reduce) {
    .cred-dialog-box {
        animation: credBoxReduced 3000ms ease forwards !important;
    }
    .cred-dialog-overlay {
        animation: credOverlayFade 3000ms ease forwards !important;
    }
}
@keyframes credBoxReduced {
    0% { opacity: 0; }
    8.2% { opacity: 1; }
    88% { opacity: 1; }
    100% { opacity: 0; visibility: hidden; pointer-events: none; }
"""
    if bg_b64:
        css = css.replace("__BG_IMAGE_PLACEHOLDER__", f"data:image/png;base64,{bg_b64}")
    else:
        css = css.replace('background-image: url("__BG_IMAGE_PLACEHOLDER__") !important;', "background: var(--bg-gradient) !important;")
    return css

