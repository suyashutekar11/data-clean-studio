"""
DataClean Studio — Enterprise Landing Page & Header
ui/welcome_view.py

Provides responsive rendering for the DataClean Studio landing page,
integrating the official database security illustration SVG from the SVG folder:
1. Top pill navigation bar (DataClean Studio, Not Connected status pill, v1.2 Standard badge)
2. 2-column Hero section with typography, CTA button, and the existing SVG/dataclean_database_illustration.svg asset
3. Three feature cards (Non-Destructive Staging, Deep Data Profiling, Automated Cleaning)
4. "How It Works" workflow stepper with connecting lines
5. Centered security footer
"""

from __future__ import annotations

import pathlib
from typing import Optional, Union
import streamlit as st
import streamlit.components.v1 as components
from ui.components import render_html

# Locate the exact SVG file inside the SVG folder
_SVG_ASSET_PATH = (
    pathlib.Path(__file__).resolve().parent.parent
    / "SVG"
    / "dataclean_database_illustration.svg"
)


def load_database_illustration_svg() -> str:
    """
    Loads and returns the high-quality database illustration SVG from
    the SVG/dataclean_database_illustration.svg file.
    Preserves all vector graphics, gradients, filters, and feature callouts.
    """
    if _SVG_ASSET_PATH.exists():
        svg_content = _SVG_ASSET_PATH.read_text(encoding="utf-8")
    else:
        fallback = pathlib.Path("SVG/dataclean_database_illustration.svg")
        if fallback.exists():
            svg_content = fallback.read_text(encoding="utf-8")
        else:
            return ""

    # Ensure responsive class is attached to the root <svg> element
    if "<svg" in svg_content:
        first_tag_end = svg_content.find(">")
        svg_tag = svg_content[:first_tag_end]
        if "class=" not in svg_tag:
            svg_content = svg_content.replace("<svg", '<svg class="hero-database-svg"', 1)
        else:
            svg_content = svg_content.replace('class="', 'class="hero-database-svg ', 1)

    return svg_content


def render_app_header(
    connected: bool = False,
    host: str = "",
    port: Union[str, int] = "",
    version: str = "v1.2 Standard",
    theme: str = "light",
    database: Optional[str] = None,
    table: Optional[str] = None,
    module: Optional[str] = None,
) -> None:
    """
    Renders the slim 64px navy top bar:
    - Left: Breadcrumb (Database / Table / Module) in light text on navy
    - Right: Connection chip (Connected localhost:3306 with green dot)
    - Routed through render_html() to prevent raw HTML code blocks
    """
    import html as html_lib

    # Determine breadcrumb items
    db_val = database or st.session_state.get("selected_db") or ""
    if db_val == "-- Select Database --":
        db_val = ""

    tbl_val = table or st.session_state.get("selected_table") or ""
    if tbl_val == "-- Select Table --":
        tbl_val = ""

    mod_val = module or ""
    if not mod_val:
        act_view = st.session_state.get("active_view", "")
        ws_tbl = st.session_state.get("working_table_name")
        if "Cleaning Workspace" in act_view and ws_tbl:
            sub = st.session_state.get("workspace_sub_tab", "")
            if sub:
                # Strip leading emoji if present
                parts = sub.split(" ", 1)
                mod_val = parts[-1] if len(parts) > 1 and not parts[0].isalnum() else sub

    # Build breadcrumb HTML
    crumbs_html = []
    if not db_val:
        crumbs_html.append('<span class="landing-hdr-bc-last">DataClean Studio</span>')
    elif db_val and not tbl_val:
        crumbs_html.append(f'<span class="landing-hdr-bc-last">{html_lib.escape(str(db_val))}</span>')
    elif db_val and tbl_val and not mod_val:
        crumbs_html.append(f'<a href="?bc_nav=db" target="_self" class="landing-hdr-bc-muted">{html_lib.escape(str(db_val))}</a>')
        crumbs_html.append('<span class="landing-hdr-bc-sep">/</span>')
        crumbs_html.append(f'<span class="landing-hdr-bc-last">{html_lib.escape(str(tbl_val))}</span>')
    else:
        crumbs_html.append(f'<a href="?bc_nav=db" target="_self" class="landing-hdr-bc-muted">{html_lib.escape(str(db_val))}</a>')
        crumbs_html.append('<span class="landing-hdr-bc-sep">/</span>')
        crumbs_html.append(f'<a href="?bc_nav=table" target="_self" class="landing-hdr-bc-muted" title="{html_lib.escape(str(tbl_val))}">{html_lib.escape(str(tbl_val))}</a>')
        crumbs_html.append('<span class="landing-hdr-bc-sep">/</span>')
        crumbs_html.append(f'<span class="landing-hdr-bc-last">{html_lib.escape(str(mod_val))}</span>')

    breadcrumb_markup = f"""
    <div class="landing-hdr-breadcrumb">
        {''.join(crumbs_html)}
    </div>
    """

    # Build connection chip HTML
    if connected:
        h_str = str(host or "localhost")
        p_str = str(port or "3306")
        status_html = f"""
        <div class="landing-hdr-pill connected">
            <span class="landing-hdr-dot dot-online"></span>
            <span>Connected &middot; {html_lib.escape(h_str)}:{html_lib.escape(p_str)}</span>
        </div>
        """
    else:
        status_html = """
        <div class="landing-hdr-pill disconnected">
            <span class="landing-hdr-dot dot-offline"></span>
            <span>Not Connected</span>
        </div>
        """

    header_content = f"""
    <div class="landing-header-wrapper">
        <style>
        .landing-header-wrapper {{
            width: 100%;
            margin: 0 0 16px 0;
            box-sizing: border-box;
        }}
        .landing-hdr-bar {{
            background: #072635 !important;
            border-radius: 12px !important;
            height: 64px !important;
            min-height: 64px !important;
            max-height: 64px !important;
            padding: 0 20px !important;
            display: flex !important;
            align-items: center !important;
            justify-content: space-between !important;
            box-shadow: 0 2px 8px rgba(7, 38, 53, 0.18) !important;
            box-sizing: border-box !important;
        }}
        .landing-hdr-breadcrumb {{
            display: flex !important;
            align-items: center !important;
            gap: 8px !important;
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif !important;
            font-size: 13.5px !important;
            line-height: 1 !important;
            overflow: hidden !important;
            white-space: nowrap !important;
            text-overflow: ellipsis !important;
        }}
        .landing-hdr-bc-muted {{
            color: #94A3B8 !important;
            text-decoration: none !important;
            font-weight: 400 !important;
            transition: color 150ms ease !important;
        }}
        .landing-hdr-bc-muted:hover {{
            color: #CBD5E1 !important;
            text-decoration: underline !important;
        }}
        .landing-hdr-bc-sep {{
            color: #64748B !important;
            font-size: 13px !important;
            user-select: none !important;
        }}
        .landing-hdr-bc-last {{
            color: #FFFFFF !important;
            font-weight: 500 !important;
        }}
        .landing-hdr-meta {{
            display: flex !important;
            align-items: center !important;
            gap: 10px !important;
            flex-shrink: 0 !important;
        }}
        .landing-hdr-pill {{
            background: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 9999px !important;
            padding: 6px 14px !important;
            font-family: 'Inter', sans-serif !important;
            font-size: 12px !important;
            font-weight: 600 !important;
            display: inline-flex !important;
            align-items: center !important;
            gap: 8px !important;
            box-shadow: 0 1px 2px rgba(15, 23, 42, 0.05) !important;
            white-space: nowrap !important;
        }}
        .landing-hdr-pill.disconnected {{
            color: #E11D48 !important;
        }}
        .landing-hdr-pill.connected {{
            color: #166534 !important;
        }}
        .landing-hdr-dot {{
            width: 8px !important;
            height: 8px !important;
            border-radius: 50% !important;
            display: inline-block !important;
            flex-shrink: 0 !important;
        }}
        .landing-hdr-dot.dot-offline {{
            background: #E11D48 !important;
            box-shadow: 0 0 0 2px rgba(225, 29, 72, 0.2) !important;
        }}
        .landing-hdr-dot.dot-online {{
            background: #10B981 !important;
            box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2) !important;
        }}
        @media (max-width: 640px) {{
            .landing-hdr-bar {{
                padding: 0 12px !important;
            }}
            .landing-hdr-breadcrumb {{
                font-size: 12px !important;
                gap: 6px !important;
            }}
        }}
        </style>

        <div class="landing-hdr-bar">
            {breadcrumb_markup}
            <div class="landing-hdr-meta">
                {status_html}
            </div>
        </div>
    </div>
    """
    render_html(header_content)


def get_animated_hero_graphic_html() -> str:
    """
    Returns a self-contained, animated HTML/CSS/SVG component matching the
    modern central database graphic inside the top-right hero card:
    - Central 3D Cylinder Stack: 3-tier deep-blue and cyan database stack with
      floating/levitation bobbing animation (translateY continuous bobbing) +
      dark-blue & cyan security shield badge in the front foreground with checkmark.
    - Orbiting Orbital Rings: Two concentric elliptical orbit paths tilted at an
      isometric perspective angle (rotateX(65deg)).
    - Continuous Revolving Motion: Outer (clockwise) and inner (counter-clockwise)
      rings revolving smoothly via CSS @keyframes rotation.
    - Glow & Particle Accents: Small glowing cyan/teal data nodes traveling along
      the ring paths and soft pulsing radial cyan glow under the base cylinder on
      an isometric platform foundation.
    - Surrounding Feature Badges: 'Clean Data', 'Quality Checks', 'No Production Changes',
      and 'Staging Sandbox' in the 4 perimeter corners with crisp iconography.
    """
    return """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}
body {
    background: transparent;
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    display: flex;
    align-items: center;
    justify-content: center;
    height: 100vh;
    overflow: hidden;
}

/* ── Hero Card Container ── */
.hero-card-container {
    position: relative;
    width: 100%;
    max-width: 580px;
    height: 300px;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    overflow: visible;
    margin: 0 auto;
}

/* Hide artificial box dots to seamlessly blend with website Background.png */
.hero-card-bg-dots {
    display: none !important;
}

/* Ambient soft cyan backdrop glow radiating naturally into Background.png */
.hero-card-backdrop-glow {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 380px;
    height: 260px;
    transform: translate(-50%, -50%);
    background: radial-gradient(ellipse, rgba(105, 231, 220, 0.38) 0%, rgba(105, 231, 220, 0) 70%);
    pointer-events: none;
    border-radius: 50%;
    filter: blur(10px);
}

/* ── Surrounding Feature Badges ── */
.badge-pill {
    position: absolute;
    z-index: 10;
    background: rgba(255, 255, 255, 0.92);
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    border: 1px solid rgba(226, 232, 240, 0.75);
    border-radius: 14px;
    padding: 8px 12px;
    box-shadow: 0 4px 16px rgba(15, 23, 42, 0.06);
    display: flex;
    align-items: center;
    gap: 9px;
    pointer-events: none;
    user-select: none;
}
.badge-icon {
    width: 28px;
    height: 28px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}
.badge-text-col {
    display: flex;
    flex-direction: column;
    gap: 2px;
}
.badge-title {
    font-size: 12px;
    font-weight: 700;
    color: #0B183A;
    line-height: 1.2;
    white-space: nowrap;
}
.badge-bars {
    display: flex;
    flex-direction: column;
    gap: 3px;
    margin-top: 2px;
}
.badge-bar {
    height: 4px;
    background: #DCE7F5;
    border-radius: 2px;
}

/* Badge 1: Top-Left "Clean Data" */
.badge-clean-data {
    top: 16px;
    left: 18px;
}
.badge-clean-data .badge-icon {
    background: #2AC5AD;
}

/* Badge 2: Top-Right "Quality Checks" */
.badge-quality-checks {
    top: 16px;
    right: 18px;
}
.badge-quality-checks .bar-chart-icon {
    display: flex;
    align-items: flex-end;
    gap: 2px;
    height: 18px;
    padding-bottom: 2px;
}
.bar-chart-icon span {
    width: 4px;
    border-radius: 1.5px;
    background: #28C5E9;
}
.bar-chart-icon span:nth-child(1) { height: 9px; }
.bar-chart-icon span:nth-child(2) { height: 14px; background: #18B9EE; }
.bar-chart-icon span:nth-child(3) { height: 18px; background: #26B9F3; }

/* Badge 3: Bottom-Left "No Production Changes" */
.badge-no-prod {
    bottom: 16px;
    left: 18px;
}
.badge-no-prod .mini-db-icon {
    width: 24px;
    height: 24px;
}

/* Badge 4: Bottom-Right "Staging Sandbox" */
.badge-staging-sandbox {
    bottom: 16px;
    right: 18px;
}
.badge-staging-sandbox .mini-db-icon {
    width: 24px;
    height: 24px;
}

/* ── Central Stage (Isometric Scene) ── */
.central-stage {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 280px;
    height: 240px;
    transform: translate(-50%, -50%);
    display: flex;
    align-items: center;
    justify-content: center;
    perspective: 700px;
}

/* Soft base platform glow */
.base-cyan-glow {
    position: absolute;
    bottom: 22px;
    left: 50%;
    width: 200px;
    height: 56px;
    transform: translateX(-50%);
    background: radial-gradient(ellipse, rgba(105, 231, 220, 0.65) 0%, rgba(32, 247, 220, 0.28) 45%, rgba(105, 231, 220, 0) 75%);
    border-radius: 50%;
    filter: blur(6px);
    pointer-events: none;
    animation: baseGlowPulse 4s ease-in-out infinite;
}
@keyframes baseGlowPulse {
    0%, 100% {
        opacity: 0.85;
        transform: translateX(-50%) scale(1);
    }
    50% {
        opacity: 0.45;
        transform: translateX(-50%) scale(0.9);
    }
}

/* Isometric platform foundation */
.base-platform-svg {
    position: absolute;
    bottom: 26px;
    left: 50%;
    transform: translateX(-50%);
    width: 220px;
    height: 64px;
    pointer-events: none;
}

/* ── Orbit System (Isometric Perspective rotateX(65deg)) ── */
.orbit-perspective-wrapper {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 290px;
    height: 290px;
    margin-left: -145px;
    margin-top: -145px;
    transform-style: preserve-3d;
    pointer-events: none;
}

/* Outer Orbit Ring: Revolves Clockwise */
.orbit-ring-outer {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 280px;
    height: 280px;
    margin-left: -140px;
    margin-top: -140px;
    border-radius: 50%;
    border: 1.3px dashed rgba(59, 185, 197, 0.65);
    box-shadow: 0 0 10px rgba(59, 185, 197, 0.2);
    transform-style: preserve-3d;
    animation: revolveClockwise 22s linear infinite;
}

/* Inner Orbit Ring: Revolves Counter-Clockwise */
.orbit-ring-inner {
    position: absolute;
    top: 50%;
    left: 50%;
    width: 205px;
    height: 205px;
    margin-left: -102.5px;
    margin-top: -102.5px;
    border-radius: 50%;
    border: 1.6px solid rgba(0, 189, 169, 0.7);
    box-shadow: 0 0 12px rgba(0, 189, 169, 0.25);
    transform-style: preserve-3d;
    animation: revolveCounter 14s linear infinite;
}

@keyframes revolveClockwise {
    from {
        transform: rotateX(65deg) rotateZ(0deg);
    }
    to {
        transform: rotateX(65deg) rotateZ(360deg);
    }
}

@keyframes revolveCounter {
    from {
        transform: rotateX(65deg) rotateZ(360deg);
    }
    to {
        transform: rotateX(65deg) rotateZ(0deg);
    }
}

/* Glowing data nodes on the outer ring */
.node-outer {
    position: absolute;
    border-radius: 50%;
    background: #00D9BD;
    box-shadow: 0 0 8px #00D9BD, 0 0 16px rgba(0, 217, 189, 0.9);
}
.node-outer-1 {
    width: 9px;
    height: 9px;
    top: -4.5px;
    left: 50%;
    margin-left: -4.5px;
}
.node-outer-2 {
    width: 8px;
    height: 8px;
    bottom: -4px;
    left: 50%;
    margin-left: -4px;
    background: #20F7DC;
    box-shadow: 0 0 8px #20F7DC, 0 0 14px rgba(32, 247, 220, 0.9);
}
.node-outer-3 {
    width: 7px;
    height: 7px;
    top: 50%;
    right: -3.5px;
    margin-top: -3.5px;
    background: #38BDF8;
    box-shadow: 0 0 8px #38BDF8, 0 0 14px rgba(56, 189, 248, 0.9);
}

/* Glowing data nodes on the inner ring */
.node-inner {
    position: absolute;
    border-radius: 50%;
    background: #20F7DC;
    box-shadow: 0 0 9px #20F7DC, 0 0 16px rgba(32, 247, 220, 0.95);
}
.node-inner-1 {
    width: 8px;
    height: 8px;
    top: -4px;
    left: 50%;
    margin-left: -4px;
}
.node-inner-2 {
    width: 7px;
    height: 7px;
    bottom: -3.5px;
    left: 50%;
    margin-left: -3.5px;
    background: #00BDA0;
    box-shadow: 0 0 8px #00BDA0, 0 0 14px rgba(0, 189, 160, 0.9);
}

/* ── Central 3D Database Stack (Floating / Levitation Bobbing) ── */
.database-stack-group {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    width: 145px;
    height: 160px;
    margin-top: -10px;
    animation: databaseLevitate 4s ease-in-out infinite;
    pointer-events: none;
}

@keyframes databaseLevitate {
    0%, 100% {
        transform: translate(-50%, -50%) translateY(0px);
    }
    50% {
        transform: translate(-50%, -50%) translateY(-9px);
    }
}

.db-svg-render {
    width: 100%;
    height: 100%;
    filter: drop-shadow(0 10px 14px rgba(6, 38, 78, 0.22));
}
</style>
</head>
<body>

<div class="hero-card-container">
    <!-- Background dots & ambient glow -->
    <div class="hero-card-bg-dots"></div>
    <div class="hero-card-backdrop-glow"></div>

    <!-- 1. Surrounding Feature Badges -->
    <!-- Top-Left: Clean Data -->
    <div class="badge-pill badge-clean-data">
        <div class="badge-icon">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#FFFFFF" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                <polyline points="20 6 9 17 4 12"></polyline>
            </svg>
        </div>
        <div class="badge-text-col">
            <span class="badge-title">Clean Data</span>
            <div class="badge-bars">
                <span class="badge-bar" style="width: 52px;"></span>
                <span class="badge-bar" style="width: 34px;"></span>
            </div>
        </div>
    </div>

    <!-- Top-Right: Quality Checks -->
    <div class="badge-pill badge-quality-checks">
        <div class="bar-chart-icon">
            <span></span>
            <span></span>
            <span></span>
        </div>
        <div class="badge-text-col">
            <span class="badge-title">Quality Checks</span>
            <div class="badge-bars">
                <span class="badge-bar" style="width: 58px;"></span>
                <span class="badge-bar" style="width: 38px;"></span>
            </div>
        </div>
    </div>

    <!-- Bottom-Left: No Production Changes -->
    <div class="badge-pill badge-no-prod">
        <div class="mini-db-icon">
            <svg width="24" height="24" viewBox="0 0 50 50" fill="none">
                <ellipse cx="25" cy="14" rx="18" ry="7" fill="#348EFF"/>
                <path d="M7 14 V32 C7 39 43 39 43 32 V14 Z" fill="#0061D7"/>
                <ellipse cx="25" cy="23" rx="18" ry="7" fill="#0051B5"/>
                <ellipse cx="25" cy="32" rx="18" ry="7" fill="#348EFF"/>
                <ellipse cx="25" cy="32" rx="15" ry="5.5" fill="#49B9FF"/>
            </svg>
        </div>
        <div class="badge-text-col">
            <span class="badge-title">No Production<br>Changes</span>
            <div class="badge-bars">
                <span class="badge-bar" style="width: 54px;"></span>
                <span class="badge-bar" style="width: 36px;"></span>
            </div>
        </div>
    </div>

    <!-- Bottom-Right: Staging Sandbox -->
    <div class="badge-pill badge-staging-sandbox">
        <div class="mini-db-icon">
            <svg width="24" height="24" viewBox="0 0 50 50" fill="none">
                <ellipse cx="25" cy="14" rx="18" ry="7" fill="#14BBA9"/>
                <path d="M7 14 V32 C7 39 43 39 43 32 V14 Z" fill="#008C83"/>
                <ellipse cx="25" cy="23" rx="18" ry="7" fill="#0A7A72"/>
                <ellipse cx="25" cy="32" rx="18" ry="7" fill="#14BBA9"/>
                <circle cx="34" cy="30" r="7" fill="#10B981"/>
                <polyline points="31 30 33 32 37 28" stroke="#FFFFFF" stroke-width="1.8" fill="none"/>
            </svg>
        </div>
        <div class="badge-text-col">
            <span class="badge-title">Staging Sandbox</span>
            <div class="badge-bars">
                <span class="badge-bar" style="width: 58px;"></span>
                <span class="badge-bar" style="width: 36px;"></span>
            </div>
        </div>
    </div>

    <!-- 2. Central Stage -->
    <div class="central-stage">
        <!-- Soft Cyan Radial Glow -->
        <div class="base-cyan-glow"></div>

        <!-- Base Platform Foundation -->
        <svg class="base-platform-svg" viewBox="0 0 210 60" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M15 28 L95 10 Q105 8 115 10 L195 28 Q205 31 195 34 L115 52 Q105 54 95 52 L15 34 Q5 31 15 28 Z" fill="url(#plat-grad)" opacity="0.9"/>
            <path d="M15 28 L95 44 Q105 46 115 44 L195 28 L195 35 Q195 41 185 43 L115 54 Q105 56 95 54 L15 36 Z" fill="#75D5D7" opacity="0.6"/>
            <defs>
                <linearGradient id="plat-grad" x1="0" y1="0" x2="1" y2="1">
                    <stop stop-color="#FFFFFF"/>
                    <stop offset="0.55" stop-color="#D9FBFF"/>
                    <stop offset="1" stop-color="#6BD7D0"/>
                </linearGradient>
            </defs>
        </svg>

        <!-- Orbit System with Counter-Revolving Motions -->
        <div class="orbit-perspective-wrapper">
            <!-- Outer Ring (revolves clockwise) -->
            <div class="orbit-ring-outer">
                <span class="node-outer node-outer-1"></span>
                <span class="node-outer node-outer-2"></span>
                <span class="node-outer node-outer-3"></span>
            </div>

            <!-- Inner Ring (revolves counter-clockwise) -->
            <div class="orbit-ring-inner">
                <span class="node-inner node-inner-1"></span>
                <span class="node-inner node-inner-2"></span>
            </div>
        </div>

        <!-- 3. Central 3D Cylinder Stack with continuous floating bobbing & security shield -->
        <div class="database-stack-group">
            <svg class="db-svg-render" viewBox="0 0 288 320" fill="none" xmlns="http://www.w3.org/2000/svg">
                <defs>
                    <linearGradient id="dbSideGrad" x1="0" y1="0" x2="1" y2="0">
                        <stop stop-color="#1269BD"/>
                        <stop offset="0.24" stop-color="#39A9EE"/>
                        <stop offset="0.48" stop-color="#06437E"/>
                        <stop offset="0.72" stop-color="#06264E"/>
                        <stop offset="1" stop-color="#008B83"/>
                    </linearGradient>
                    <linearGradient id="dbTopGrad" x1="0" y1="0" x2="1" y2="1">
                        <stop stop-color="#49B9FF"/>
                        <stop offset="0.45" stop-color="#1764A8"/>
                        <stop offset="1" stop-color="#082E60"/>
                    </linearGradient>
                    <linearGradient id="shieldGrad" x1="0" y1="0" x2="1" y2="0">
                        <stop stop-color="#00A99D"/>
                        <stop offset="0.5" stop-color="#073D61"/>
                        <stop offset="1" stop-color="#061D3D"/>
                    </linearGradient>
                    <linearGradient id="miniShieldGrad" x1="0" y1="0" x2="1" y2="0">
                        <stop stop-color="#24F0EE"/>
                        <stop offset="0.5" stop-color="#1F7DE5"/>
                        <stop offset="1" stop-color="#0B57B9"/>
                    </linearGradient>
                    <filter id="softGlow" x="-20%" y="-20%" width="140%" height="140%">
                        <feDropShadow dx="0" dy="6" stdDeviation="8" flood-color="#06264E" flood-opacity="0.35"/>
                    </filter>
                </defs>

                <!-- ── Tier 3: Lower Cylinder ── -->
                <g filter="url(#softGlow)">
                    <path d="M20 200 C20 182 75 168 144 168 C213 168 268 182 268 200 L268 245 C268 265 213 282 144 282 C75 282 20 265 20 245 Z" fill="url(#dbSideGrad)"/>
                    <ellipse cx="144" cy="200" rx="124" ry="29" fill="url(#dbTopGrad)" stroke="#36D9F0" stroke-width="2.5"/>
                    <path d="M20 200 C20 216 75 230 144 230 C213 230 268 216 268 200" fill="none" stroke="#76DFFF" stroke-width="2.5" opacity="0.85"/>
                    <path d="M20 245 C20 261 75 275 144 275 C213 275 268 261 268 245" fill="none" stroke="#0A2551" stroke-width="4.5" opacity="0.65"/>
                </g>

                <!-- ── Tier 2: Middle Cylinder ── -->
                <g filter="url(#softGlow)">
                    <path d="M20 120 C20 102 75 88 144 88 C213 88 268 102 268 120 L268 165 C268 185 213 202 144 202 C75 202 20 185 20 165 Z" fill="url(#dbSideGrad)"/>
                    <ellipse cx="144" cy="120" rx="124" ry="29" fill="url(#dbTopGrad)" stroke="#3CE2F0" stroke-width="2.5"/>
                    <path d="M20 120 C20 136 75 150 144 150 C213 150 268 136 268 120" fill="none" stroke="#72DDFF" stroke-width="2.5" opacity="0.85"/>
                    <path d="M20 165 C20 181 75 195 144 195 C213 195 268 181 268 165" fill="none" stroke="#071D42" stroke-width="5" opacity="0.85"/>
                </g>

                <!-- ── Tier 1: Top Cylinder ── -->
                <g filter="url(#softGlow)">
                    <path d="M20 28 C20 12 75 0 144 0 C213 0 268 12 268 28 L268 85 C268 104 213 121 144 121 C75 121 20 104 20 85 Z" fill="url(#dbSideGrad)"/>
                    <path d="M20 28 C20 12 75 0 144 0 C213 0 268 12 268 28 L268 41 C268 56 213 69 144 69 C75 69 20 56 20 41 Z" fill="#1681C8" opacity="0.25"/>
                    <ellipse cx="144" cy="28" rx="124" ry="27" fill="url(#dbTopGrad)" stroke="#32F6F0" stroke-width="4"/>
                    <ellipse cx="144" cy="28" rx="102" ry="20" fill="#0A3264" opacity="0.9"/>
                    <path d="M21 29 C21 46 75 60 144 60 C213 60 267 46 267 29" fill="none" stroke="#71E6FA" stroke-width="2.2"/>
                    <path d="M21 85 C21 103 75 118 144 118 C213 118 267 103 267 85" fill="none" stroke="#08244D" stroke-width="6" opacity="0.9"/>
                    <circle cx="248" cy="60" r="2.5" fill="#20F7DC"/>
                </g>

                <!-- ── Foreground Security Shield Badge ── -->
                <g filter="url(#softGlow)">
                    <!-- Outer Shield -->
                    <path d="M236 150 L263 165 L290 168 L289 210 Q286 247 236 284 Q186 248 181 210 L181 168 Q210 165 236 150 Z" fill="url(#shieldGrad)" stroke="#E9FFFF" stroke-width="6" stroke-linejoin="round"/>
                    <path d="M236 160 L280 177 L279 210 Q275 240 236 270 Z" fill="#061F3C" opacity="0.7"/>
                    <!-- Inner Shield with Checkmark -->
                    <path d="M236 195 L258 206 L258 225 Q255 241 236 252 Q217 240 215 225 L215 206 Z" fill="url(#miniShieldGrad)" stroke="#D8FFFF" stroke-width="1.8"/>
                    <path d="M236 195 L236 252 Q255 240 258 225 L258 206 Z" fill="#176DE0" opacity="0.55"/>
                    <polyline points="228 223 234 229 245 218" fill="none" stroke="#FFFFFF" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"/>
                </g>
            </svg>
        </div>
    </div>
</div>

</body>
</html>
"""


def _render_html(raw_html: str) -> None:
    """Helper to strip leading indentation so Streamlit does not parse HTML as markdown code blocks."""
    lines = [line.strip() for line in raw_html.strip().splitlines() if line.strip()]
    st.markdown("\n".join(lines), unsafe_allow_html=True)


def render_hero_welcome() -> None:
    """
    Renders the complete landing page matching the user's reference image:
    1. Top navigation pill header
    2. 2-column Hero: Typography, CTA button, and animated database hero card embedded via components.html()
    3. Three feature cards: Non-Destructive Staging (highlighted cyan border), Deep Data Profiling, Automated Cleaning
    4. Workflow stepper card: How It Works with 3 connected steps
    5. Centered security footer
    """
    # ── 1. Page Styles ──
    styles = """
    <style>
    /* ── Base Container & App Shell Clean-Up ── */
    .landing-page-root {
        width: 100%;
        max-width: 1140px;
        margin: 0 auto;
        box-sizing: border-box;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
        padding: 0 12px;
    }

    /* Clean Streamlit block container padding accounting for sidebar */
    .block-container {
        padding-top: 20px !important;
        padding-bottom: 28px !important;
        max-width: 1180px !important;
        margin: 0 auto !important;
    }

    /* Streamlit header transparency */
    header[data-testid="stHeader"] {
        background: transparent !important;
    }

    /* ── 1. Hero 2-Column Section ── */
    .hero-left-content {
        padding-right: 12px;
        box-sizing: border-box;
        display: flex;
        flex-direction: column;
        justify-content: center;
        height: 100%;
        min-height: 300px;
    }

    /* Main Headline */
    .hero-main-title {
        font-size: 40px !important;
        font-weight: 800 !important;
        color: #0F172A !important;
        line-height: 1.15 !important;
        letter-spacing: -0.025em !important;
        margin: 0 0 18px 0 !important;
    }

    /* Primary CTA Button */
    .hero-cta-btn {
        background: linear-gradient(135deg, #0A726D 0%, #075E59 100%) !important;
        color: #FFFFFF !important;
        border: none !important;
        border-radius: 8px !important;
        padding: 12px 22px !important;
        font-size: 14.5px !important;
        font-weight: 600 !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 10px !important;
        cursor: pointer !important;
        box-shadow: 0 4px 14px rgba(10, 114, 109, 0.25) !important;
        transition: transform 120ms ease, box-shadow 120ms ease !important;
        width: fit-content !important;
        margin-top: 4px !important;
        text-decoration: none !important;
    }
    .hero-cta-btn:hover {
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px rgba(10, 114, 109, 0.35) !important;
        background: linear-gradient(135deg, #0B7E79 0%, #086963 100%) !important;
    }

    /* Custom Component iframe centering */
    div[data-testid="stCustomComponentV1"] {
        display: flex !important;
        justify-content: center !important;
        align-items: center !important;
        width: 100% !important;
    }
    div[data-testid="stCustomComponentV1"] iframe {
        display: block !important;
        margin: 0 auto !important;
        border: none !important;
    }

    /* ── 2. Three Feature Cards ── */
    .features-triplet-grid {
        display: grid !important;
        grid-template-columns: repeat(3, 1fr) !important;
        gap: 20px !important;
        margin-top: 10px !important;
        margin-bottom: 26px !important;
        box-sizing: border-box !important;
    }

    .feat-card-box {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-top: 2.5px solid #00D5B5 !important;
        border-radius: 16px !important;
        padding: 24px 22px 22px 22px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04) !important;
        display: flex !important;
        flex-direction: column !important;
        justify-content: space-between !important;
        height: 100% !important;
        box-sizing: border-box !important;
        transition: transform 150ms ease, box-shadow 150ms ease !important;
    }
    .feat-card-box:hover {
        transform: translateY(-2px) !important;
        box-shadow: 0 8px 20px rgba(15, 23, 42, 0.07) !important;
    }
    /* Highlighted first card with full cyan border */
    .feat-card-box.highlight-teal {
        border: 2px solid #00D5B5 !important;
    }

    .feat-icon-sq {
        width: 44px;
        height: 44px;
        border-radius: 10px;
        display: flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 14px;
        flex-shrink: 0;
    }
    .feat-icon-sq.mint {
        background: #E6FFFA;
        border: 1px solid #CCFBF1;
    }
    .feat-icon-sq.blue {
        background: #EFF6FF;
        border: 1px solid #DBEAFE;
    }
    .feat-icon-sq.amber {
        background: #FFFBEB;
        border: 1px solid #FEF3C7;
    }

    .feat-title {
        font-size: 15.5px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin: 0 0 8px 0 !important;
        line-height: 1.25 !important;
    }
    .feat-desc {
        font-size: 13px !important;
        color: #64748B !important;
        line-height: 1.55 !important;
        margin: 0 0 16px 0 !important;
        flex-grow: 1 !important;
    }

    /* ── 3. How It Works Stepper Card ── */
    .how-workflow-card {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 16px !important;
        padding: 24px 28px 26px 28px !important;
        margin-bottom: 24px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, 0.04) !important;
        box-sizing: border-box !important;
    }
    .how-header {
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        margin-bottom: 22px !important;
    }
    .how-gear-icon {
        width: 34px;
        height: 34px;
        background: #E6FFFA;
        border: 1px solid #CCFBF1;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .how-title {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        line-height: 1.2 !important;
    }
    .how-sub {
        font-size: 12.5px !important;
        color: #64748B !important;
        margin-top: 2px !important;
    }

    .how-steps-row {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        gap: 8px !important;
    }
    .how-step-item {
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        flex: 1 1 auto !important;
        min-width: 0 !important;
    }
    .how-num-badge {
        font-size: 11.5px !important;
        font-weight: 700 !important;
        color: #0D9488 !important;
        background: #CCFBF1 !important;
        width: 22px !important;
        height: 22px !important;
        border-radius: 50% !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        flex-shrink: 0 !important;
    }
    .how-step-icon {
        width: 36px;
        height: 36px;
        border-radius: 8px;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .how-step-icon.mint {
        background: #E6FFFA;
        border: 1px solid #CCFBF1;
    }
    .how-step-icon.blue {
        background: #EFF6FF;
        border: 1px solid #DBEAFE;
    }
    .how-step-icon.amber {
        background: #FFFBEB;
        border: 1px solid #FEF3C7;
    }
    .how-step-texts {
        min-width: 0;
    }
    .how-step-name {
        font-size: 13.5px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        line-height: 1.25 !important;
    }
    .how-step-hint {
        font-size: 11.5px !important;
        color: #64748B !important;
        margin-top: 2px !important;
        line-height: 1.35 !important;
    }

    .how-connector-bar {
        display: flex !important;
        align-items: center !important;
        flex: 0 1 60px !important;
        padding: 0 4px !important;
    }
    .how-line {
        height: 1.5px !important;
        background: #CBD5E1 !important;
        flex-grow: 1 !important;
    }
    .how-line-dot {
        width: 5px !important;
        height: 5px !important;
        background: #94A3B8 !important;
        border-radius: 50% !important;
        margin-left: -2px !important;
    }

    /* ── 4. Centered Security Footer ── */
    .landing-footer-line {
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 16px !important;
        margin: 20px auto 10px auto !important;
        max-width: 600px !important;
        color: #64748B !important;
        font-size: 12px !important;
    }
    .footer-rule {
        flex: 1 !important;
        height: 1px !important;
        background: #E2E8F0 !important;
    }
    .footer-tag-content {
        display: flex !important;
        align-items: center !important;
        gap: 6px !important;
        white-space: nowrap !important;
    }

    /* ── Responsive Rules ── */
    @media (max-width: 900px) {
        .features-triplet-grid {
            grid-template-columns: 1fr !important;
            gap: 16px !important;
        }
        .how-steps-row {
            flex-direction: column !important;
            align-items: flex-start !important;
            gap: 16px !important;
        }
        .how-connector-bar {
            display: none !important;
        }
    }

    @media (max-width: 600px) {
        .hero-main-title {
            font-size: 28px !important;
        }
        .hero-cta-btn {
            width: 100% !important;
            justify-content: center !important;
        }
        .how-workflow-card {
            padding: 18px 18px !important;
        }
    }

    /* ── Professional Wave Entrance Transition from Side ── */
    .hero-title-line {
        display: block !important;
        overflow: visible !important;
        white-space: nowrap !important;
    }

    .wave-word {
        display: inline-block !important;
        will-change: transform, opacity, filter;
        animation: sideWaveEntrance 0.85s cubic-bezier(0.16, 1, 0.3, 1) both !important;
        animation-delay: calc(var(--w-idx) * 115ms) !important;
    }

    @keyframes sideWaveEntrance {
        0% {
            opacity: 0;
            transform: translateX(-48px) translateY(18px) rotate(-2.5deg);
            filter: blur(6px);
        }
        42% {
            opacity: 0.9;
            transform: translateX(-7px) translateY(-9px) rotate(1.2deg);
            filter: blur(0.5px);
        }
        72% {
            transform: translateX(2px) translateY(2.5px) rotate(-0.3deg);
            filter: blur(0);
        }
        88% {
            transform: translateX(-0.5px) translateY(-0.8px) rotate(0.1deg);
        }
        100% {
            opacity: 1;
            transform: translateX(0) translateY(0) rotate(0deg);
            filter: blur(0);
        }
    }

    @media (max-width: 480px) {
        .hero-title-line {
            white-space: normal !important;
        }
    }

    @media (prefers-reduced-motion: reduce) {
        .wave-word {
            opacity: 1 !important;
            transform: none !important;
            filter: none !important;
            animation: none !important;
        }
    }
    </style>
    """
    _render_html(styles)

    # ── 2. Hero 2-Column Row ──
    col_hero_left, col_hero_right = st.columns([1.05, 0.95], gap="large")

    with col_hero_left:
        hero_left_html = """
        <div class="hero-left-content">
<h1 class="hero-main-title" id="hero-title" aria-label="Enterprise Data Quality & Cleaning">
                <span class="hero-title-line">
                    <span class="wave-word" style="--w-idx: 0;">Enterprise</span>
                    <span class="wave-word" style="--w-idx: 1;">Data</span>
                </span>
                <span class="hero-title-line">
                    <span class="wave-word" style="--w-idx: 2;">Quality</span>
                    <span class="wave-word" style="--w-idx: 3;">&</span>
                    <span class="wave-word" style="--w-idx: 4;">Cleaning</span>
                </span>
            </h1>
        </div>
        """
        _render_html(hero_left_html)

    with col_hero_right:
        components.html(get_animated_hero_graphic_html(), height=310, scrolling=False)

    # ── 3. Features Triplet, Stepper & Security Footer ──
    body_html = """
    <div class="landing-page-root">
        <!-- 2. THREE FEATURE CARDS -->
        <div class="features-triplet-grid">
            <!-- Card 1: Non-Destructive Staging (Highlighted Cyan Border) -->
            <div class="feat-card-box highlight-teal">
                <div class="feat-icon-sq mint">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#0D9488" stroke-width="2">
                        <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                        <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                        <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                    </svg>
                </div>
                <div>
                    <div class="feat-title">Non-Destructive Staging</div>
                    <div class="feat-desc">
                        Run every operation in isolated staging workspaces. Production tables stay untouched.
                    </div>
                </div>
            </div>

            <!-- Card 2: Deep Data Profiling -->
            <div class="feat-card-box">
                <div class="feat-icon-sq blue">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2">
                        <rect x="3" y="12" width="4" height="9" rx="1"></rect>
                        <rect x="10" y="7" width="4" height="14" rx="1"></rect>
                        <rect x="17" y="3" width="4" height="18" rx="1"></rect>
                    </svg>
                </div>
                <div>
                    <div class="feat-title">Deep Data Profiling</div>
                    <div class="feat-desc">
                        Discover NULLs, duplicates, type issues, and outliers with exportable quality reports.
                    </div>
                </div>
            </div>

            <!-- Card 3: Automated Cleaning -->
            <div class="feat-card-box">
                <div class="feat-icon-sq amber">
                    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2">
                        <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"></path>
                    </svg>
                </div>
                <div>
                    <div class="feat-title">Automated Cleaning</div>
                    <div class="feat-desc">
                        Apply reusable rules for normalization, duplicate resolution, and audited transformations.
                    </div>
                </div>
            </div>
        </div>

        <!-- 3. HOW IT WORKS STEPPER CARD -->
        <div class="how-workflow-card">
            <div class="how-header">
                <div class="how-gear-icon">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0D9488" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <circle cx="12" cy="12" r="3"></circle>
                        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                    </svg>
                </div>
                <div>
                    <div class="how-title">How It Works</div>
                    <div class="how-sub">A simple and safe workflow for clean, reliable data.</div>
                </div>
            </div>

            <div class="how-steps-row">
                <!-- Step 01 -->
                <div class="how-step-item">
                    <div class="how-num-badge">01</div>
                    <div class="how-step-icon mint">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#0D9488" stroke-width="2">
                            <ellipse cx="12" cy="5" rx="9" ry="3"></ellipse>
                            <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"></path>
                            <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"></path>
                        </svg>
                    </div>
                    <div class="how-step-texts">
                        <div class="how-step-name">Connect instance</div>
                        <div class="how-step-hint">Authenticate securely and browse schemas.</div>
                    </div>
                </div>

                <!-- Connector 1 -->
                <div class="how-connector-bar">
                    <div class="how-line"></div>
                    <div class="how-line-dot"></div>
                </div>

                <!-- Step 02 -->
                <div class="how-step-item">
                    <div class="how-num-badge">02</div>
                    <div class="how-step-icon blue">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#2563EB" stroke-width="2">
                            <rect x="3" y="12" width="4" height="9" rx="1"></rect>
                            <rect x="10" y="7" width="4" height="14" rx="1"></rect>
                            <rect x="17" y="3" width="4" height="18" rx="1"></rect>
                        </svg>
                    </div>
                    <div class="how-step-texts">
                        <div class="how-step-name">Profile tables</div>
                        <div class="how-step-hint">Review data quality issues and types.</div>
                    </div>
                </div>

                <!-- Connector 2 -->
                <div class="how-connector-bar">
                    <div class="how-line"></div>
                    <div class="how-line-dot"></div>
                </div>

                <!-- Step 03 -->
                <div class="how-step-item">
                    <div class="how-num-badge">03</div>
                    <div class="how-step-icon amber">
                        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#D97706" stroke-width="2">
                            <path d="M12 2l2.4 7.2L22 12l-7.6 2.8L12 22l-2.4-7.2L2 12l7.6-2.8z"></path>
                        </svg>
                    </div>
                    <div class="how-step-texts">
                        <div class="how-step-name">Stage &amp; clean safely</div>
                        <div class="how-step-hint">Preview fixes before applying them in a sandbox.</div>
                    </div>
                </div>
            </div>
        </div>

        <!-- 4. CENTERED SECURITY FOOTER -->
        <div class="landing-footer-line">
            <div class="footer-rule"></div>
            <div class="footer-tag-content">
                <svg width="14" height="16" viewBox="0 0 24 26" fill="none" stroke="#64748B" stroke-width="1.8">
                    <path d="M12 1L2 5.5V12C2 18.5 6.3 24.3 12 25.8C17.7 24.3 22 18.5 22 12V5.5L12 1Z"/>
                </svg>
                <span>DataClean Studio &middot; Your data stays on your server</span>
            </div>
            <div class="footer-rule"></div>
        </div>
    </div>
    """
    _render_html(body_html)
