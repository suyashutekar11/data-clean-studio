"""
DataClean Studio — Glass Design System
src/ui/theme.py

Single source of truth for all visual styling.
Call `inject_glass_theme(dark=True)` once at the top of app.py, *after*
`st.set_page_config()` and before any other UI code.

Streamlit version notes
-----------------------
• Tested against Streamlit ≥ 1.25.
• `[data-testid="stVerticalBlockBorderWrapper"]` targets `st.container(border=True)`;
  the testid was added in Streamlit 1.24.  On older versions those containers
  will be unstyled — harmless.
• `st.dialog` / `@st.dialog` (used in app.py) was added in Streamlit 1.32.
  On 1.25–1.31 the modal fallback selector `div[role="dialog"]` still applies.
• `-webkit-backdrop-filter` is included for Safari / iOS support.
• A `@supports (backdrop-filter: blur(1px))` guard wraps every blur rule so
  browsers without support (Firefox < 103) get a solid semi-opaque fallback.
"""

from __future__ import annotations

import streamlit as st


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def inject_glass_theme(dark: bool = True) -> None:
    """
    Inject the complete glassmorphism design system into the Streamlit page.

    Parameters
    ----------
    dark : bool
        True  → deep-space dark theme (default).
        False → frosted-glass light theme.

    Call once per page run, immediately after `st.set_page_config()`.
    Example::

        st.set_page_config(...)          # must be first Streamlit call
        from src.ui.theme import inject_glass_theme
        inject_glass_theme(dark=(st.session_state.get("ui_theme") != "light"))
    """
    css = _build_css(dark=dark)
    st.markdown(f"<style>\n{css}\n</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _tokens(dark: bool) -> str:
    """Return CSS custom-property declarations for the chosen theme."""
    if dark:
        return """
    /* ── Dark theme tokens ── */
    --glass-bg:           rgba(255, 255, 255, 0.06);
    --glass-bg-elevated:  rgba(255, 255, 255, 0.09);
    --glass-bg-input:     rgba(255, 255, 255, 0.07);
    --glass-border:       1px solid rgba(255, 255, 255, 0.12);
    --glass-border-raw:   rgba(255, 255, 255, 0.12);
    --glass-blur:         16px;
    --glass-saturate:     140%;
    --glass-shadow:
        0 4px 6px  rgba(0, 0, 0, 0.25),
        0 12px 32px rgba(0, 0, 0, 0.28),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
    --glass-shadow-lg:
        0 8px 16px rgba(0, 0, 0, 0.35),
        0 24px 56px rgba(0, 0, 0, 0.40),
        inset 0 1px 0 rgba(255, 255, 255, 0.08);
    --glass-highlight:    inset 0 1px 0 rgba(255, 255, 255, 0.08);
    --glass-fallback-bg:  rgba(15, 22, 40, 0.82);

    /* Backgrounds */
    --dq-bg:              #080d1a;
    --dq-surface:         rgba(255, 255, 255, 0.06);
    --dq-surface2:        rgba(255, 255, 255, 0.04);
    --dq-bg-soft:         rgba(255, 255, 255, 0.03);

    /* Text */
    --dq-text-primary:    #edf2fb;
    --dq-text-secondary:  #b0bcda;
    --dq-text-muted:      #7a8ba8;

    /* Borders */
    --dq-border:          rgba(255, 255, 255, 0.12);
    --dq-border-hover:    rgba(255, 255, 255, 0.26);

    /* Accent — blue/indigo */
    --dq-accent:          #6199ff;
    --dq-accent-end:      #8b7fff;
    --dq-accent-gradient: linear-gradient(135deg, #6199ff 0%, #8b7fff 100%);
    --dq-accent-glow:     rgba(97, 153, 255, 0.18);
    --dq-accent-focus:    rgba(97, 153, 255, 0.38);
    --dq-accent-border:   rgba(97, 153, 255, 0.35);
    --dq-accent-btn-glow: 0 0 20px rgba(97, 153, 255, 0.50), 0 4px 14px rgba(97, 153, 255, 0.30);

    /* Semantic palette */
    --dq-success:         #22c55e;
    --dq-success-bg:      rgba(34, 197, 94, 0.14);
    --dq-success-border:  rgba(34, 197, 94, 0.28);
    --dq-success-glow:    rgba(34, 197, 94, 0.40);

    --dq-warning:         #f59e0b;
    --dq-warning-bg:      rgba(245, 158, 11, 0.14);
    --dq-warning-border:  rgba(245, 158, 11, 0.35);

    --dq-danger:          #ef4444;
    --dq-danger-bg:       rgba(239, 68, 68, 0.14);
    --dq-danger-border:   rgba(239, 68, 68, 0.35);
    --dq-danger-glow:     rgba(239, 68, 68, 0.45);

    /* Misc */
    --dq-shadow:          0 4px 16px rgba(0, 0, 0, 0.28);
    --dq-shadow-hover:    0 8px 28px rgba(0, 0, 0, 0.42);
    --dq-slate:           #b0bcda;
    --dq-slate-muted:     #7a8ba8;
    --dq-slate-text:      #edf2fb;
        """
    else:
        return """
    /* ── Light theme tokens ── */
    --glass-bg:           rgba(255, 255, 255, 0.55);
    --glass-bg-elevated:  rgba(255, 255, 255, 0.72);
    --glass-bg-input:     rgba(255, 255, 255, 0.70);
    --glass-border:       1px solid rgba(0, 0, 0, 0.08);
    --glass-border-raw:   rgba(0, 0, 0, 0.08);
    --glass-blur:         16px;
    --glass-saturate:     140%;
    --glass-shadow:
        0 4px 6px  rgba(0, 0, 0, 0.06),
        0 12px 32px rgba(0, 0, 0, 0.08),
        inset 0 1px 0 rgba(255, 255, 255, 0.90);
    --glass-shadow-lg:
        0 8px 16px rgba(0, 0, 0, 0.10),
        0 24px 56px rgba(0, 0, 0, 0.12),
        inset 0 1px 0 rgba(255, 255, 255, 0.90);
    --glass-highlight:    inset 0 1px 0 rgba(255, 255, 255, 0.90);
    --glass-fallback-bg:  rgba(240, 244, 252, 0.92);

    /* Backgrounds */
    --dq-bg:              #dde8f7;
    --dq-surface:         rgba(255, 255, 255, 0.55);
    --dq-surface2:        rgba(255, 255, 255, 0.40);
    --dq-bg-soft:         rgba(0, 0, 0, 0.025);

    /* Text */
    --dq-text-primary:    #111827;
    --dq-text-secondary:  #374151;
    --dq-text-muted:      #6b7280;

    /* Borders */
    --dq-border:          rgba(0, 0, 0, 0.08);
    --dq-border-hover:    rgba(0, 0, 0, 0.18);

    /* Accent */
    --dq-accent:          #2563eb;
    --dq-accent-end:      #4f46e5;
    --dq-accent-gradient: linear-gradient(135deg, #2563eb 0%, #4f46e5 100%);
    --dq-accent-glow:     rgba(37, 99, 235, 0.10);
    --dq-accent-focus:    rgba(37, 99, 235, 0.32);
    --dq-accent-border:   rgba(37, 99, 235, 0.30);
    --dq-accent-btn-glow: 0 0 20px rgba(37, 99, 235, 0.35), 0 4px 14px rgba(37, 99, 235, 0.22);

    /* Semantic palette */
    --dq-success:         #16a34a;
    --dq-success-bg:      rgba(22, 163, 74, 0.10);
    --dq-success-border:  rgba(22, 163, 74, 0.25);
    --dq-success-glow:    rgba(22, 163, 74, 0.35);

    --dq-warning:         #d97706;
    --dq-warning-bg:      rgba(217, 119, 6, 0.10);
    --dq-warning-border:  rgba(217, 119, 6, 0.30);

    --dq-danger:          #dc2626;
    --dq-danger-bg:       rgba(220, 38, 38, 0.10);
    --dq-danger-border:   rgba(220, 38, 38, 0.30);
    --dq-danger-glow:     rgba(220, 38, 38, 0.40);

    /* Misc */
    --dq-shadow:          0 4px 16px rgba(0, 0, 0, 0.08);
    --dq-shadow-hover:    0 8px 28px rgba(0, 0, 0, 0.12);
    --dq-slate:           #374151;
    --dq-slate-muted:     #6b7280;
    --dq-slate-text:      #111827;
        """


def _build_css(dark: bool) -> str:
    """Assemble the full CSS string for the given theme."""
    tok = _tokens(dark)

    # Background gradient direction differs per theme so blobs are readable
    bg_gradient = (
        "linear-gradient(135deg, #060d1f 0%, #0b1630 50%, #07101e 100%)"
        if dark else
        "linear-gradient(135deg, #c8daef 0%, #dce9f9 50%, #e8f0fa 100%)"
    )

    # Blob colours
    blob1_colour = "rgba(79, 70, 229, 0.22)" if dark else "rgba(79, 70, 229, 0.12)"
    blob2_colour = "rgba(6, 182, 212, 0.16)"  if dark else "rgba(6, 182, 212, 0.10)"
    blob3_colour = "rgba(139, 92, 246, 0.14)" if dark else "rgba(139, 92, 246, 0.08)"

    return f"""
/* ============================================================
   DataClean Studio — Glass Design System
   src/ui/theme.py → inject_glass_theme()
   Grouped: Reset · Tokens · Background · Layout · Sidebar ·
            Widgets · Inputs · Buttons · Cards · Typography ·
            Animations · Reduced-Motion · Fallbacks
   ============================================================ */

/* ── Google Fonts ─────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:ital,opsz,wght@0,14..32,300..900;1,14..32,300..900&family=JetBrains+Mono:wght@400;500;600&display=swap');

/* ── Design tokens ────────────────────────────────────────── */
:root {{
    {tok}

    /* Radius scale */
    --r-sm:   8px;
    --r-md:   12px;
    --r-lg:   16px;
    --r-xl:   24px;
    --r-pill: 9999px;

    /* Spacing scale (use as margin/padding helpers) */
    --sp-1: 4px;
    --sp-2: 8px;
    --sp-3: 12px;
    --sp-4: 16px;
    --sp-5: 20px;
    --sp-6: 24px;

    /* Typography scale */
    --fs-xs:   11px;
    --fs-sm:   12px;
    --fs-base: 13.5px;
    --fs-md:   15px;
    --fs-lg:   17px;
    --fs-xl:   22px;
    --fs-2xl:  30px;

    /* Transition */
    --t-fast:   120ms ease;
    --t-normal: 180ms ease;
    --t-slow:   260ms ease;

    /* Mono font */
    --font-mono: 'JetBrains Mono', 'Fira Code', Menlo, Monaco, Consolas, monospace;
}}

/* ── Global reset / base ──────────────────────────────────── */
html, body, .stApp {{
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
    font-size: var(--fs-md) !important;
    line-height: 1.6 !important;
    color: var(--dq-text-primary) !important;
    -webkit-font-smoothing: antialiased;
    -moz-osx-font-smoothing: grayscale;
}}

code, .mono {{
    font-family: var(--font-mono) !important;
    font-size: 0.875em;
}}

/* Boost tiny system text so nothing dips below 12 px */
small, .caption, [data-testid="stCaptionContainer"] p,
[data-testid="stWidgetLabel"] small {{
    font-size: var(--fs-sm) !important;
}}

/* Improve contrast for helper / muted text */
[data-testid="stHelp"], .stCaption,
[data-testid="stCaptionContainer"] {{
    color: var(--dq-text-muted) !important;
    font-size: var(--fs-sm) !important;
}}

/* ── Streamlit chrome ─────────────────────────────────────── */
[data-testid="stHeader"],
[data-testid="stToolbar"],
.stAppToolbar {{
    background: transparent !important;
    box-shadow: none !important;
}}

footer, #MainMenu {{ display: none !important; visibility: hidden !important; }}

.main {{ background: transparent !important; }}

/* ── Animated background & colour blobs ───────────────────── */
/* Layer order (bottom → top): gradient · blob1 · blob2 · blob3 · page content */

[data-testid="stAppViewContainer"] {{
    background: {bg_gradient} !important;
    background-attachment: fixed !important;
    position: relative !important;
    isolation: isolate !important;
}}

/* Blob pseudo-elements live on the scroll container that wraps app content */
[data-testid="stAppViewContainer"]::before,
[data-testid="stAppViewContainer"]::after {{
    content: '';
    position: fixed;
    border-radius: 50%;
    filter: blur(80px);
    pointer-events: none;
    z-index: 0;
}}

/* Blob 1 — indigo, top-left */
[data-testid="stAppViewContainer"]::before {{
    width: 55vw;
    height: 55vw;
    top: -15vw;
    left: -10vw;
    background: {blob1_colour};
    animation: blobDrift1 28s ease-in-out infinite alternate;
}}

/* Blob 2 — cyan, bottom-right */
[data-testid="stAppViewContainer"]::after {{
    width: 50vw;
    height: 50vw;
    bottom: -15vw;
    right: -8vw;
    background: {blob2_colour};
    animation: blobDrift2 24s ease-in-out infinite alternate;
}}

/* Blob 3 — violet, centre — injected via a real element (pseudo can't add a third) */
.dq-blob3 {{
    position: fixed;
    width: 40vw;
    height: 40vw;
    top: 35vh;
    left: 40vw;
    background: {blob3_colour};
    border-radius: 50%;
    filter: blur(90px);
    pointer-events: none;
    z-index: 0;
    animation: blobDrift3 32s ease-in-out infinite alternate;
}}

@keyframes blobDrift1 {{
    0%   {{ transform: translate(0, 0) scale(1); }}
    50%  {{ transform: translate(5vw, 6vh) scale(1.08); }}
    100% {{ transform: translate(-3vw, -4vh) scale(0.95); }}
}}
@keyframes blobDrift2 {{
    0%   {{ transform: translate(0, 0) scale(1); }}
    50%  {{ transform: translate(-6vw, -5vh) scale(1.06); }}
    100% {{ transform: translate(4vw, 5vh) scale(0.96); }}
}}
@keyframes blobDrift3 {{
    0%   {{ transform: translate(0, 0) scale(1); }}
    50%  {{ transform: translate(3vw, -4vh) scale(1.10); }}
    100% {{ transform: translate(-4vw, 3vh) scale(0.92); }}
}}

/* Ensure page content sits above blobs */
[data-testid="stMain"],
[data-testid="stSidebar"],
[data-testid="stHeader"] {{
    position: relative;
    z-index: 1;
}}

/* ── Reusable .glass utility class ───────────────────────────
   Apply this to any custom HTML element you want glassed.
   Streamlit native widgets are targeted directly below.   */
.glass {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--glass-shadow) !important;
}}

@supports (backdrop-filter: blur(1px)) {{
    .glass {{
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
    }}
}}

/* ── SIDEBAR ──────────────────────────────────────────────── */
[data-testid="stSidebar"] {{
    background: var(--glass-bg) !important;
    border-right: var(--glass-border) !important;
    border-radius: 0 !important;
    box-shadow: var(--glass-shadow-lg) !important;
}}

@supports (backdrop-filter: blur(1px)) {{
    [data-testid="stSidebar"] {{
        backdrop-filter: blur(24px) saturate(160%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
    }}
}}
@supports not (backdrop-filter: blur(1px)) {{
    [data-testid="stSidebar"] {{
        background: var(--glass-fallback-bg) !important;
    }}
}}

[data-testid="stSidebar"] > div:first-child {{
    padding: 28px 20px 32px 20px !important;
    height: 100vh !important;
    overflow-y: auto !important;
    box-sizing: border-box !important;
}}

/* Thin scrollbar */
[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar {{ width: 4px !important; }}
[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-track {{ background: transparent !important; }}
[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb {{
    background: rgba(148, 163, 184, 0.20) !important;
    border-radius: var(--r-pill) !important;
}}
[data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb:hover {{
    background: var(--dq-accent-glow) !important;
}}

/* Collapse/expand buttons */
[data-testid="stSidebarCollapseButton"] button,
[data-testid="stSidebarExpandButton"] button {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--dq-text-muted) !important;
    box-shadow: var(--glass-shadow) !important;
    transition: all var(--t-normal) !important;
}}
[data-testid="stSidebarCollapseButton"] button:hover,
[data-testid="stSidebarExpandButton"] button:hover {{
    background: var(--dq-accent-glow) !important;
    color: var(--dq-accent) !important;
    border-color: var(--dq-accent-border) !important;
    transform: scale(1.04) !important;
}}

/* Suppress default nested container boxes inside sidebar */
[data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {{
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}}

/* Sidebar section headers */
.sidebar-section-header {{
    font-size: var(--fs-xs) !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.07em !important;
    color: var(--dq-text-muted) !important;
    margin-top: 22px !important;
    margin-bottom: 10px !important;
}}

/* Sidebar labels */
[data-testid="stSidebar"] label p {{
    font-size: var(--fs-sm) !important;
    font-weight: 500 !important;
    color: var(--dq-text-secondary) !important;
    margin-bottom: 4px !important;
}}

/* ── EXPANDERS ────────────────────────────────────────────── */
[data-testid="stExpander"] {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--glass-shadow) !important;
    overflow: hidden !important;
}}

@supports (backdrop-filter: blur(1px)) {{
    [data-testid="stExpander"] {{
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
    }}
}}
@supports not (backdrop-filter: blur(1px)) {{
    [data-testid="stExpander"] {{
        background: var(--glass-fallback-bg) !important;
    }}
}}

[data-testid="stExpander"] details {{ border: none !important; }}
[data-testid="stExpander"] summary {{
    padding: 12px 16px !important;
    font-size: var(--fs-base) !important;
    font-weight: 500 !important;
    color: var(--dq-text-secondary) !important;
    border: none !important;
    transition: color var(--t-fast) !important;
}}
[data-testid="stExpander"] summary:hover {{ color: var(--dq-text-primary) !important; }}

/* Sidebar-specific expander (tighter, no blur dupe) */
[data-testid="stSidebar"] [data-testid="stExpander"] {{
    background: rgba(255, 255, 255, 0.04) !important;
    border: var(--glass-border) !important;
    margin-top: 8px !important;
}}
[data-testid="stSidebar"] [data-testid="stExpander"] summary {{
    background: transparent !important;
    font-size: var(--fs-sm) !important;
}}

/* ── BORDERED CONTAINERS (st.container(border=True)) ─────── */
[data-testid="stVerticalBlockBorderWrapper"] {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--glass-shadow) !important;
    padding: 20px !important;
}}

@supports (backdrop-filter: blur(1px)) {{
    [data-testid="stVerticalBlockBorderWrapper"] {{
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
    }}
}}
@supports not (backdrop-filter: blur(1px)) {{
    [data-testid="stVerticalBlockBorderWrapper"] {{
        background: var(--glass-fallback-bg) !important;
    }}
}}

/* ── METRIC CARDS ─────────────────────────────────────────── */
[data-testid="stMetric"] {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--glass-shadow) !important;
    padding: 16px 18px !important;
}}

@supports (backdrop-filter: blur(1px)) {{
    [data-testid="stMetric"] {{
        backdrop-filter: blur(12px) saturate(130%) !important;
        -webkit-backdrop-filter: blur(12px) saturate(130%) !important;
    }}
}}

[data-testid="stMetricLabel"] {{
    color: var(--dq-text-muted) !important;
    font-size: var(--fs-sm) !important;
    font-weight: 600 !important;
    text-transform: uppercase !important;
    letter-spacing: 0.05em !important;
}}
[data-testid="stMetricValue"] {{
    color: var(--dq-text-primary) !important;
    font-weight: 800 !important;
}}
[data-testid="stMetricDelta"] {{ font-size: var(--fs-sm) !important; }}

/* ── DATAFRAMES ───────────────────────────────────────────── */
[data-testid="stDataFrame"] {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-md) !important;
    overflow: hidden !important;
    box-shadow: var(--glass-shadow) !important;
}}

/* ── TABS ─────────────────────────────────────────────────── */
[data-testid="stTabs"] [data-baseweb="tab-list"] {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-md) !important;
    padding: 4px !important;
    gap: 4px !important;
    box-shadow: var(--glass-shadow) !important;
}}

@supports (backdrop-filter: blur(1px)) {{
    [data-testid="stTabs"] [data-baseweb="tab-list"] {{
        backdrop-filter: blur(12px) saturate(130%) !important;
        -webkit-backdrop-filter: blur(12px) saturate(130%) !important;
    }}
}}

[data-testid="stTabs"] [data-baseweb="tab"] {{
    background: transparent !important;
    border: 1px solid transparent !important;
    border-radius: var(--r-sm) !important;
    color: var(--dq-text-secondary) !important;
    font-size: var(--fs-base) !important;
    font-weight: 500 !important;
    padding: 8px 16px !important;
    transition: all var(--t-fast) !important;
}}
[data-testid="stTabs"] [data-baseweb="tab"]:hover {{
    background: var(--dq-accent-glow) !important;
    color: var(--dq-accent) !important;
    border-color: var(--dq-accent-border) !important;
}}
[data-testid="stTabs"] [aria-selected="true"] {{
    background: var(--dq-accent) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-color: transparent !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.20) !important;
}}
/* Hide the default underline indicator */
[data-testid="stTabs"] [data-baseweb="tab-highlight"] {{
    display: none !important;
}}

/* ── RADIO / SEGMENTED CONTROLS ───────────────────────────── */
div[data-testid="stRadio"] > div {{
    display: flex !important;
    flex-direction: row !important;
    flex-wrap: wrap !important;
    gap: 4px !important;
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-md) !important;
    padding: 4px !important;
    width: 100% !important;
    box-shadow: var(--glass-shadow) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    div[data-testid="stRadio"] > div {{
        backdrop-filter: blur(10px) saturate(120%) !important;
        -webkit-backdrop-filter: blur(10px) saturate(120%) !important;
    }}
}}
div[data-testid="stRadio"] label {{
    display: inline-flex !important;
    align-items: center !important;
    justify-content: center !important;
    flex: 1 !important;
    min-width: 72px !important;
    padding: 7px 12px !important;
    border-radius: var(--r-sm) !important;
    cursor: pointer !important;
    font-size: var(--fs-sm) !important;
    font-weight: 600 !important;
    color: var(--dq-text-secondary) !important;
    white-space: nowrap !important;
    transition: all var(--t-fast) !important;
    margin: 0 !important;
    background: transparent !important;
    border: 1px solid transparent !important;
}}
div[data-testid="stRadio"] label > div:first-child {{ display: none !important; }}
div[data-testid="stRadio"] label:hover {{
    background: var(--dq-accent-glow) !important;
    color: var(--dq-accent) !important;
    border-color: var(--dq-accent-border) !important;
}}
div[data-testid="stRadio"] label:has(input[type="radio"]:checked) {{
    background: var(--dq-accent) !important;
    color: #ffffff !important;
    font-weight: 700 !important;
    border-color: transparent !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.22) !important;
}}

/* Workspace sub-tab grid (4-column) */
div.st-key-_ws_sub_radio > div[data-testid="stRadio"] > div {{
    display: grid !important;
    grid-template-columns: repeat(4, 1fr) !important;
    gap: 6px !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}}
div.st-key-_ws_sub_radio > div[data-testid="stRadio"] label {{
    flex-direction: column !important;
    gap: 4px !important;
    flex: unset !important;
    min-width: unset !important;
    width: 100% !important;
    padding: 10px 8px !important;
    border-radius: var(--r-md) !important;
    border: var(--glass-border) !important;
    background: var(--glass-bg) !important;
    font-size: 11px !important;
    white-space: normal !important;
    text-align: center !important;
    line-height: 1.3 !important;
}}
div.st-key-_ws_sub_radio > div[data-testid="stRadio"] label:hover {{
    border-color: var(--dq-accent-border) !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.12) !important;
}}
div.st-key-_ws_sub_radio > div[data-testid="stRadio"] label:has(input[type="radio"]:checked) {{
    background: var(--dq-accent) !important;
    border-color: transparent !important;
    transform: translateY(-1px) !important;
    box-shadow: 0 4px 14px var(--dq-accent-focus) !important;
}}
@media (max-width: 860px) {{
    div.st-key-_ws_sub_radio > div[data-testid="stRadio"] > div {{
        grid-template-columns: repeat(2, 1fr) !important;
    }}
}}

/* ── SELECTBOX ────────────────────────────────────────────── */
[data-testid="stSelectbox"] [data-baseweb="select"] > div,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div {{
    background: var(--glass-bg-input) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--dq-text-primary) !important;
    transition: border-color var(--t-fast), box-shadow var(--t-fast) !important;
    min-height: 40px !important;
}}
[data-testid="stSelectbox"] [data-baseweb="select"] > div:hover,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div:hover {{
    border-color: var(--dq-border-hover) !important;
}}
[data-testid="stSelectbox"] [data-baseweb="select"] > div:focus-within,
[data-testid="stMultiSelect"] [data-baseweb="select"] > div:focus-within {{
    border-color: var(--dq-accent) !important;
    box-shadow: 0 0 0 3px var(--dq-accent-focus) !important;
}}

/* Dropdown popover */
[data-baseweb="popover"] [data-baseweb="menu"] {{
    background: var(--glass-fallback-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--glass-shadow-lg) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    [data-baseweb="popover"] [data-baseweb="menu"] {{
        backdrop-filter: blur(24px) saturate(160%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
    }}
}}

/* ── TEXT INPUTS ──────────────────────────────────────────── */
[data-testid="stTextInput"] input,
[data-testid="stNumberInput"] input,
[data-testid="stTextArea"] textarea {{
    background: var(--glass-bg-input) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--dq-text-primary) !important;
    font-size: var(--fs-base) !important;
    transition: border-color var(--t-fast), box-shadow var(--t-fast), background var(--t-fast) !important;
    min-height: 40px !important;
    padding: 0 12px !important;
}}
[data-testid="stTextInput"] input:focus,
[data-testid="stNumberInput"] input:focus,
[data-testid="stTextArea"] textarea:focus {{
    border-color: var(--dq-accent) !important;
    box-shadow: 0 0 0 3px var(--dq-accent-focus) !important;
    outline: none !important;
    background: var(--glass-bg-elevated) !important;
}}
[data-testid="stTextInput"] input::placeholder,
[data-testid="stNumberInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{
    color: var(--dq-text-muted) !important;
    opacity: 0.75 !important;
}}

/* Sidebar-specific inputs */
[data-testid="stSidebar"] [data-testid="stTextInput"] input,
[data-testid="stSidebar"] [data-testid="stNumberInput"] input {{
    min-height: 44px !important;
    height: 44px !important;
    padding: 0 14px !important;
}}

/* Number input stepper buttons hidden */
[data-testid="stSidebar"] [data-testid="stNumberInput"] button {{
    display: none !important;
}}

/* ── TOGGLE ───────────────────────────────────────────────── */
[data-testid="stToggle"] {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-sm) !important;
    padding: 8px 14px !important;
    transition: border-color var(--t-fast) !important;
}}
[data-testid="stToggle"] label {{ color: var(--dq-text-secondary) !important; font-size: var(--fs-sm) !important; }}
[data-testid="stToggle"]:has(input:checked) {{
    border-color: var(--dq-accent-border) !important;
    background: var(--dq-accent-glow) !important;
}}

/* ── ALERTS / TOASTS ──────────────────────────────────────── */
div[data-testid="stAlert"] {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-sm) !important;
    color: var(--dq-text-primary) !important;
    box-shadow: var(--glass-shadow) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    div[data-testid="stAlert"] {{
        backdrop-filter: blur(10px) saturate(120%) !important;
        -webkit-backdrop-filter: blur(10px) saturate(120%) !important;
    }}
}}

[data-testid="stToast"] {{
    background: var(--glass-fallback-bg) !important;
    border: var(--glass-border) !important;
    color: var(--dq-text-primary) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--glass-shadow-lg) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    [data-testid="stToast"] {{
        backdrop-filter: blur(24px) saturate(160%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(160%) !important;
    }}
}}

/* ── DIALOG / MODAL ───────────────────────────────────────── */
/* Streamlit 1.32+ uses @st.dialog which renders as [data-testid="stModal"].
   The div[role="dialog"] selector handles Streamlit 1.25–1.31 as well. */
div[data-testid="stModal"] > div:first-child,
div[role="dialog"] {{
    background: var(--glass-fallback-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-xl) !important;
    box-shadow: var(--glass-shadow-lg) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    div[data-testid="stModal"] > div:first-child,
    div[role="dialog"] {{
        backdrop-filter: blur(28px) saturate(170%) !important;
        -webkit-backdrop-filter: blur(28px) saturate(170%) !important;
    }}
}}
/* Dim overlay */
div[data-testid="stModalOverlay"],
[data-baseweb="dialog"] [data-baseweb="backdrop"] {{
    background: rgba(0, 0, 0, 0.55) !important;
    backdrop-filter: blur(4px) !important;
    -webkit-backdrop-filter: blur(4px) !important;
}}

/* ── SPINNERS ─────────────────────────────────────────────── */
[data-testid="stSpinner"] {{ color: var(--dq-accent) !important; }}

/* ── BUTTONS ──────────────────────────────────────────────── */
/* All buttons share base transition */
.stButton > button, button[data-testid^="stBaseButton"] {{
    border-radius: var(--r-sm) !important;
    font-weight: 600 !important;
    font-size: var(--fs-base) !important;
    transition: transform var(--t-fast), box-shadow var(--t-fast), background var(--t-fast), border-color var(--t-fast), filter var(--t-fast) !important;
    cursor: pointer !important;
}}

/* ── PRIMARY button — gradient accent + glow on hover ── */
button[data-testid="stBaseButton-primary"],
button[kind="primary"],
div[class*="st-key-sb_connect"] button,
div[class*="st-key-hub_open_"] button,
div[class*="st-key-open_ws_btn"] button {{
    background: var(--dq-accent-gradient) !important;
    border: 1px solid rgba(255,255,255,0.18) !important;
    color: #ffffff !important;
    box-shadow: 0 2px 8px rgba(0,0,0,0.20) !important;
}}
button[data-testid="stBaseButton-primary"]:hover,
button[kind="primary"]:hover,
div[class*="st-key-sb_connect"] button:hover,
div[class*="st-key-hub_open_"] button:hover,
div[class*="st-key-open_ws_btn"] button:hover {{
    filter: brightness(1.12) !important;
    box-shadow: var(--dq-accent-btn-glow) !important;
    transform: translateY(-1px) !important;
}}
button[data-testid="stBaseButton-primary"]:active,
button[kind="primary"]:active {{
    transform: translateY(1px) scale(0.98) !important;
    box-shadow: 0 2px 6px rgba(0,0,0,0.20) !important;
}}

/* ── SECONDARY button — glass outline ── */
button[data-testid="stBaseButton-secondary"],
button[kind="secondary"] {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    color: var(--dq-text-primary) !important;
    box-shadow: var(--glass-shadow) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    button[data-testid="stBaseButton-secondary"],
    button[kind="secondary"] {{
        backdrop-filter: blur(8px) !important;
        -webkit-backdrop-filter: blur(8px) !important;
    }}
}}
button[data-testid="stBaseButton-secondary"]:hover,
button[kind="secondary"]:hover {{
    background: var(--dq-accent-glow) !important;
    border-color: var(--dq-accent-border) !important;
    color: var(--dq-accent) !important;
    transform: translateY(-1px) !important;
}}

/* ── Test-connection button — glass secondary, sidebar-scoped ── */
div[class*="st-key-sb_test"] button {{
    background: var(--glass-bg) !important;
    border: 1.5px solid var(--dq-border) !important;
    color: var(--dq-text-secondary) !important;
    box-shadow: none !important;
}}
div[class*="st-key-sb_test"] button:hover {{
    border-color: var(--dq-accent-border) !important;
    color: var(--dq-accent) !important;
    transform: translateY(-1px) !important;
}}

/* ── DANGER buttons (Disconnect / Teardown / Download PDF) ── */
/*
   These are targeted by their stable st-key-* selectors.
   Translucent red at rest → solid red on hover.
*/
div[class*="st-key-sb_disconnect"] button,
div[class*="st-key-hub_drop_"] button,
div[class*="st-key-drop_sb_btn"] button,
div[class*="st-key-disc_btn"] button {{
    background: var(--dq-danger-bg) !important;
    background-image: none !important;
    border: 1.5px solid var(--dq-danger-border) !important;
    color: var(--dq-danger) !important;
    box-shadow: none !important;
}}
div[class*="st-key-sb_disconnect"] button:hover,
div[class*="st-key-hub_drop_"] button:hover,
div[class*="st-key-drop_sb_btn"] button:hover,
div[class*="st-key-disc_btn"] button:hover {{
    background: var(--dq-danger) !important;
    background-image: none !important;
    border-color: var(--dq-danger) !important;
    color: #ffffff !important;
    box-shadow: 0 0 18px var(--dq-danger-glow) !important;
    transform: translateY(-1px) !important;
}}

/* PDF download button */
div[class*="st-key-dl_pdf"] button {{
    background: var(--dq-danger-bg) !important;
    border: 1.5px solid var(--dq-danger-border) !important;
    color: var(--dq-danger) !important;
    box-shadow: none !important;
}}
div[class*="st-key-dl_pdf"] button:hover {{
    background: var(--dq-danger) !important;
    border-color: var(--dq-danger) !important;
    color: #ffffff !important;
    transform: translateY(-1px) !important;
}}

/* ── Floating theme toggle — remove fixed overlay, keep in sidebar only ── */
/* The old floating pill is hidden via this rule; the sidebar toggle remains. */
div.st-key-floating_theme_toggle {{
    display: none !important;
}}

/* ── TOP HEADER CARD ──────────────────────────────────────── */
.app-top-header {{
    max-width: 1100px;
    width: 100%;
    margin: 0 auto 28px auto;
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 24px;
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--glass-shadow) !important;
    box-sizing: border-box;
}}
@supports (backdrop-filter: blur(1px)) {{
    .app-top-header {{
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
    }}
}}

.app-top-brand {{ display: flex; align-items: center; gap: 14px; }}
.app-top-logo {{
    display: flex; align-items: center; justify-content: center;
    width: 42px; height: 42px;
    border-radius: var(--r-md);
    background: var(--dq-accent-glow);
    border: 1px solid var(--dq-accent-border);
    font-size: 1.3rem; flex-shrink: 0;
}}
.app-top-title   {{ font-size: var(--fs-lg); font-weight: 700; color: var(--dq-text-primary); line-height: 1.2; }}
.app-top-tagline {{ font-size: var(--fs-sm); color: var(--dq-text-secondary); margin-top: 2px; }}
.app-top-meta    {{ display: flex; align-items: center; gap: 10px; }}

/* Status pills */
.status-pill {{
    display: inline-flex; align-items: center; gap: 6px;
    padding: 5px 12px;
    border-radius: var(--r-pill);
    font-size: var(--fs-sm);
    font-weight: 500;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
}}
.status-pill.status-connected    {{ background: var(--dq-success-bg); color: var(--dq-success); border: 1px solid var(--dq-success-border); }}
.status-pill.status-disconnected {{ background: var(--dq-danger-bg);  color: var(--dq-danger);  border: 1px solid var(--dq-danger-border); }}
.status-pill-dot {{ width: 7px; height: 7px; border-radius: 50%; background: currentColor; display: inline-block; }}
.status-pill.status-connected .status-pill-dot {{ animation: pulseStatusGreen 2.5s infinite; }}

/* Version / theme badge */
.version-tag, .theme-badge {{
    font-size: var(--fs-sm);
    font-weight: 500;
    padding: 4px 10px;
    border-radius: var(--r-sm);
    background: var(--glass-bg);
    border: var(--glass-border);
    color: var(--dq-text-secondary);
    display: inline-flex; align-items: center; gap: 4px;
}}

/* ── FEATURE CARDS ────────────────────────────────────────── */
.feature-card {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-lg) !important;
    padding: 24px 22px !important;
    display: flex; flex-direction: column; height: 100%;
    box-shadow: var(--glass-shadow) !important;
    position: relative; overflow: hidden;
    transition: transform var(--t-slow), border-color var(--t-slow), box-shadow var(--t-slow) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    .feature-card {{
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
    }}
}}
.feature-card:hover {{
    transform: translateY(-4px) !important;
    border-color: var(--dq-accent-border) !important;
    box-shadow: var(--glass-shadow-lg) !important;
}}
.feature-top-accent {{
    position: absolute; top: 0; left: 0; right: 0; height: 3px;
    background: var(--dq-accent-gradient);
}}
.feature-icon-tile {{
    width: 44px; height: 44px; border-radius: var(--r-md);
    display: inline-flex; align-items: center; justify-content: center;
    font-size: 1.35rem; margin-bottom: 16px;
    background: var(--dq-accent-glow); border: 1px solid var(--dq-accent-border);
}}
.feature-title {{ font-size: var(--fs-lg); font-weight: 600; color: var(--dq-text-primary); margin-bottom: 8px; }}
.feature-desc  {{ font-size: 14px; color: var(--dq-text-secondary); line-height: 1.6; margin: 0 0 16px 0; flex-grow: 1; }}
.feature-micro-link {{ font-size: var(--fs-sm); font-weight: 600; color: var(--dq-accent); display: inline-flex; align-items: center; gap: 4px; margin-top: auto; }}

/* Steps timeline */
.steps-timeline-container {{
    max-width: 1100px; width: 100%; margin: 0 auto;
    padding: 20px 28px;
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-lg) !important;
    box-shadow: var(--glass-shadow) !important;
    display: flex; align-items: center; justify-content: space-between; gap: 16px; box-sizing: border-box;
}}
@supports (backdrop-filter: blur(1px)) {{
    .steps-timeline-container {{
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
    }}
}}

/* ── KPI CARDS ────────────────────────────────────────────── */
.kpi-card {{
    background: var(--glass-bg);
    border: var(--glass-border);
    border-radius: var(--r-md);
    padding: 1rem 1.25rem;
    box-shadow: var(--glass-shadow);
    position: relative; overflow: hidden;
}}
@supports (backdrop-filter: blur(1px)) {{
    .kpi-card {{
        backdrop-filter: blur(12px) saturate(130%);
        -webkit-backdrop-filter: blur(12px) saturate(130%);
    }}
}}
.kpi-card::before {{ content: ''; position: absolute; top: 0; left: 0; width: 4px; height: 100%; background: var(--dq-accent); }}
.kpi-card-success::before {{ background: var(--dq-success); }}
.kpi-card-warning::before {{ background: var(--dq-warning); }}
.kpi-card-danger::before  {{ background: var(--dq-danger);  }}
.kpi-label   {{ font-size: var(--fs-xs); font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; color: var(--dq-text-secondary) !important; margin-bottom: 4px; }}
.kpi-value   {{ font-size: 1.85rem; font-weight: 800; color: var(--dq-text-primary) !important; line-height: 1.15; }}
.kpi-subtext {{ font-size: var(--fs-sm); color: var(--dq-text-muted) !important; margin-top: 4px; }}

/* Sidebar status card */
.sidebar-status-card {{
    margin-top: 20px !important;
    padding: 16px 18px !important;
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-md) !important;
    box-shadow: var(--glass-shadow) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    .sidebar-status-card {{
        backdrop-filter: blur(12px) saturate(130%) !important;
        -webkit-backdrop-filter: blur(12px) saturate(130%) !important;
    }}
}}
.sidebar-status-header {{ display: flex; align-items: center; gap: 10px; }}
.sidebar-status-dot {{ width: 10px; height: 10px; border-radius: 50%; display: inline-block; }}
.sidebar-status-dot.dot-connected    {{ background: var(--dq-success); box-shadow: 0 0 10px var(--dq-success-glow); animation: pulseStatusGreen 2.5s infinite; }}
.sidebar-status-dot.dot-disconnected {{ background: var(--dq-danger);  box-shadow: 0 0 8px var(--dq-danger-glow); }}
.sidebar-status-title-connected    {{ font-weight: 600; font-size: var(--fs-base); color: var(--dq-success); }}
.sidebar-status-title-disconnected {{ font-weight: 600; font-size: var(--fs-base); color: var(--dq-text-primary); }}
.sidebar-status-chip {{
    margin-left: auto; font-size: var(--fs-xs); font-weight: 600;
    padding: 2px 7px; border-radius: 4px;
    background: var(--dq-success-bg); color: var(--dq-success); border: 1px solid var(--dq-success-border);
    text-transform: uppercase;
}}
.sidebar-status-meta {{ font-size: var(--fs-sm); color: var(--dq-text-muted); margin-top: 8px; line-height: 1.5; }}

/* ── SIDEBAR BRAND BLOCK ──────────────────────────────────── */
.sidebar-brand-block {{
    display: flex; align-items: center; gap: 12px;
    padding-bottom: 16px; margin-bottom: 20px;
    border-bottom: 1px solid var(--dq-border);
}}
.sidebar-brand-icon {{
    display: flex; align-items: center; justify-content: center;
    width: 42px; height: 42px; border-radius: var(--r-md);
    background: var(--dq-accent-glow); border: 1px solid var(--dq-accent-border);
    font-size: 1.4rem; flex-shrink: 0;
    box-shadow: 0 2px 10px rgba(0,0,0,0.15);
}}
.sidebar-brand-title {{ font-size: var(--fs-md); font-weight: 700; color: var(--dq-text-primary); letter-spacing: -0.01em; }}
.sidebar-brand-sub   {{ font-size: var(--fs-sm); color: var(--dq-text-secondary); margin-top: 2px; }}

/* ── TYPOGRAPHY HELPERS ───────────────────────────────────── */
.dq-eyebrow {{
    font-size: var(--fs-xs) !important; font-weight: 600 !important;
    text-transform: uppercase !important; letter-spacing: 0.08em !important;
    color: var(--dq-text-muted) !important; margin-bottom: 4px !important;
}}
.dq-section-title {{
    font-size: 1.05rem !important; font-weight: 700 !important;
    color: var(--dq-text-primary) !important; letter-spacing: -0.01em !important;
    margin-bottom: 4px !important; line-height: 1.3 !important;
}}
.dq-section-caption {{
    font-size: 0.85rem !important; color: var(--dq-text-muted) !important;
    margin-bottom: 14px !important; line-height: 1.5 !important;
}}
.gradient-text {{
    background: var(--dq-accent-gradient);
    -webkit-background-clip: text; -webkit-text-fill-color: transparent; display: inline;
}}

/* ── BADGES ───────────────────────────────────────────────── */
.badge-pill {{
    display: inline-flex; align-items: center; gap: 4px;
    padding: 2px 10px; border-radius: var(--r-pill);
    font-size: var(--fs-xs); font-weight: 600; line-height: 1.6; white-space: nowrap;
}}
.badge-info    {{ background: var(--dq-accent-glow);  color: var(--dq-accent);  border: 1px solid var(--dq-accent-border);   }}
.badge-warning {{ background: var(--dq-warning-bg);   color: var(--dq-warning); border: 1px solid var(--dq-warning-border); }}
.badge-success {{ background: var(--dq-success-bg);   color: var(--dq-success); border: 1px solid var(--dq-success-border); }}
.badge-neutral {{ background: var(--dq-bg-soft);      color: var(--dq-slate);   border: 1px solid var(--dq-border);         }}

/* ── SAFETY BANNERS ───────────────────────────────────────── */
.safety-banner {{
    display: flex; align-items: flex-start; gap: 12px;
    padding: 14px 18px; border-radius: var(--r-sm);
    background: var(--dq-warning-bg); border: 1px solid var(--dq-warning-border);
    margin-bottom: 14px;
}}
.safety-banner-icon {{ font-size: 1.2rem; flex-shrink: 0; margin-top: 2px; }}
.safety-banner-content {{ font-size: 0.85rem; color: var(--dq-slate-text); line-height: 1.55; }}

/* ── EMPTY STATE ──────────────────────────────────────────── */
.empty-state-card {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    gap: 10px; padding: 40px 24px;
    border-radius: var(--r-md); border: 1.5px dashed var(--dq-border);
    background: var(--dq-bg-soft); text-align: center; margin: 16px 0;
}}
.es-title {{ font-size: 1rem; font-weight: 700; color: var(--dq-text-primary); }}
.es-desc  {{ font-size: 0.85rem; color: var(--dq-text-muted); max-width: 380px; line-height: 1.55; }}

/* ── HEALTH SCORE ─────────────────────────────────────────── */
.health-score-container {{
    display: flex; align-items: center; gap: 20px;
    background: var(--glass-bg); border: var(--glass-border);
    border-radius: var(--r-lg); padding: 20px 24px;
    margin-bottom: 20px; box-shadow: var(--glass-shadow);
}}
@supports (backdrop-filter: blur(1px)) {{
    .health-score-container {{
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate));
    }}
}}
.health-score-dial {{
    display: flex; flex-direction: column; align-items: center; justify-content: center;
    width: 95px; height: 95px; border-radius: 50%;
    background: var(--glass-bg); box-shadow: var(--glass-shadow);
    border: 4px solid var(--dq-accent); flex-shrink: 0;
}}
.health-score-number {{ font-size: 1.75rem; font-weight: 800; line-height: 1; color: var(--dq-text-primary); }}
.health-score-pct    {{ font-size: var(--fs-sm); font-weight: 700; color: var(--dq-text-muted) !important; }}

/* ── ANIMATIONS ───────────────────────────────────────────── */
@keyframes pulseStatusGreen {{
    0%   {{ opacity: 1; transform: scale(1); }}
    50%  {{ opacity: 0.55; transform: scale(1.20); }}
    100% {{ opacity: 1; transform: scale(1); }}
}}
@keyframes pageFadeIn {{
    from {{ opacity: 0; transform: translateY(8px); }}
    to   {{ opacity: 1; transform: translateY(0); }}
}}
@keyframes hintBounce {{
    0%, 100% {{ transform: translateX(0); }}
    50%       {{ transform: translateX(-4px); }}
}}
.page-fade-in {{ animation: pageFadeIn 300ms cubic-bezier(0.16, 1, 0.3, 1) forwards; }}
.hero-cta-arrow {{ animation: hintBounce 1.8s infinite ease-in-out; }}

/* ── REDUCED MOTION override ──────────────────────────────── */
@media (prefers-reduced-motion: reduce) {{
    *, *::before, *::after {{
        animation-duration: 0.01ms !important;
        animation-iteration-count: 1 !important;
        transition-duration: 0.01ms !important;
    }}
    /* Blobs still present but static */
    [data-testid="stAppViewContainer"]::before,
    [data-testid="stAppViewContainer"]::after,
    .dq-blob3 {{ animation: none !important; }}
}}

/* ── Misc layout helpers ──────────────────────────────────── */
.content-wrapper {{ max-width: 1100px; width: 100%; margin-left: auto; margin-right: auto; box-sizing: border-box; }}

.db-conn-panel {{
    background: var(--glass-bg) !important;
    border: var(--glass-border) !important;
    border-radius: var(--r-lg) !important;
    padding: 20px 20px 16px 20px !important;
    margin-top: 8px !important;
    box-shadow: var(--glass-shadow) !important;
}}
@supports (backdrop-filter: blur(1px)) {{
    .db-conn-panel {{
        backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
        -webkit-backdrop-filter: blur(var(--glass-blur)) saturate(var(--glass-saturate)) !important;
    }}
}}

/* Breadcrumb */
.breadcrumb-bar {{ display: flex; align-items: center; flex-wrap: wrap; gap: 4px; margin-bottom: 16px; }}
.bc-item {{ font-size: var(--fs-sm); font-weight: 500; color: var(--dq-slate-muted); cursor: default; }}
.bc-item.active {{ color: var(--dq-text-primary); font-weight: 600; }}
.bc-sep {{ font-size: var(--fs-sm); color: var(--dq-border); user-select: none; }}

/* Step timeline */
.step-card {{ display: flex; align-items: center; gap: 14px; flex: 1; }}
.step-number {{
    width: 36px; height: 36px; border-radius: 50%;
    background: var(--dq-accent-glow); border: 1.5px solid var(--dq-accent);
    color: var(--dq-accent); font-size: 15px; font-weight: 700;
    display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}}
.step-content {{ display: flex; flex-direction: column; }}
.step-title {{ font-size: 14px; font-weight: 600; color: var(--dq-text-primary); }}
.step-desc  {{ font-size: var(--fs-sm); color: var(--dq-text-secondary); margin-top: 2px; }}
.step-arrow {{ color: var(--dq-text-muted); font-size: 18px; font-weight: 600; display: flex; align-items: center; justify-content: center; padding: 0 4px; }}

/* Hero */
.hero-container {{ max-width: 1100px; width: 100%; margin: 0 auto; padding: 44px 24px; box-sizing: border-box; display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; }}
.hero-badge-tile {{ display: inline-flex; align-items: center; justify-content: center; width: 56px; height: 56px; border-radius: var(--r-lg); background: var(--dq-accent-glow); border: 1px solid var(--dq-accent-border); box-shadow: var(--glass-shadow); font-size: 1.85rem; margin-bottom: 16px; }}
.hero-headline {{ font-size: 38px !important; font-weight: 700 !important; color: var(--dq-text-primary); letter-spacing: -0.025em; line-height: 1.15 !important; margin: 0 0 16px 0; }}
.hero-subtitle {{ font-size: var(--fs-md); color: var(--dq-text-secondary); max-width: 820px; margin: 0 0 24px 0; line-height: 1.55; }}
.hero-cta-hint {{ display: inline-flex; align-items: center; gap: 8px; background: var(--glass-bg); border: var(--glass-border); color: var(--dq-text-primary); padding: 8px 18px; border-radius: var(--r-pill); font-size: var(--fs-base); margin-bottom: 24px; box-shadow: var(--glass-shadow); }}
.hero-cta-hint strong {{ color: var(--dq-accent); }}
.hero-trust-row {{ display: flex; align-items: center; justify-content: center; gap: 28px; flex-wrap: wrap; margin-top: 8px; margin-bottom: 32px; }}
.trust-item {{ display: flex; align-items: center; gap: 8px; font-size: var(--fs-base); font-weight: 500; color: var(--dq-text-secondary); }}
.trust-icon {{ font-size: 15px; }}

/* Footer */
.app-footer-line {{ max-width: 1100px; width: 100%; margin: 36px auto 16px auto; text-align: center; font-size: var(--fs-sm); color: var(--dq-text-muted); letter-spacing: 0.02em; box-sizing: border-box; }}

@media (max-width: 900px) {{
    .features-grid {{ grid-template-columns: 1fr; }}
    .steps-timeline-container {{ flex-direction: column; align-items: flex-start; gap: 16px; }}
    .step-arrow {{ display: none !important; }}
}}

/* Misc layout */
.health-score-details {{ display: flex; flex-direction: column; gap: 8px; }}
.features-grid {{ max-width: 1100px; width: 100%; margin: 0 auto 32px auto; display: grid; grid-template-columns: repeat(3, 1fr); gap: 24px; box-sizing: border-box; }}
"""
