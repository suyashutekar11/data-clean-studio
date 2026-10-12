"""
DataClean Studio — Redesigned Connection Manager Sidebar
ui/sidebar_view.py

Provides components and styling for the redesigned sidebar matching the reference design:
1. Header: Shield logo in mint square, title, subtitle, collapse button with « and teal divider.
2. Promotional Card: "Secure Database Connection" with 3D teal database stack & shield.
3. Section Heading: "DATABASE CONNECTION" with purple database badge and horizontal divider.
4. Custom Form Styles: Input compartments, stepper controls, eye toggle, label icons.
5. Action Buttons & Status Card: Disconnected / Connected states.
6. Bottom Decorative Waves: Layered mint/teal waves.
"""

from __future__ import annotations
import streamlit as st


def get_sidebar_css() -> str:
    """Returns CSS targeting the Streamlit sidebar to precisely match the reference design."""
    return """
    <style>
    /* ─── 1. Sidebar Container & Layout ──────────────────────── */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #FFFFFF 0%, #F8FAFC 55%, #F0FDF4 100%) !important;
        border-right: 1px solid #E2E8F0 !important;
        box-shadow: 2px 0 12px rgba(15, 23, 42, 0.03) !important;
        position: relative !important;
        overflow: hidden !important;
        min-width: 326px !important;
        width: 326px !important;
    }

    [data-testid="stSidebar"] > div:first-child,
    [data-testid="stSidebarContent"] {
        padding: 20px 18px 36px 18px !important;
        height: 100vh !important;
        overflow-y: auto !important;
        box-sizing: border-box !important;
        position: static !important;
    }

    [data-testid="stSidebarUserContent"] {
        position: static !important;
    }

    [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] > div:not(:has(.sb-bottom-waves)),
    .sb-brand-wrapper,
    .sb-promo-card,
    .sb-section-heading-row,
    [data-testid="stTextInput"],
    [data-testid="stNumberInput"],
    [data-testid="stExpander"],
    [data-testid="stHorizontalBlock"],
    .sb-status-card {
        position: relative !important;
        z-index: 2 !important;
    }

    /* Unconstrain wrappers around the bottom waves so it anchors to sidebar edges */
    [data-testid="stElementContainer"]:has(.sb-bottom-waves),
    [data-testid="element-container"]:has(.sb-bottom-waves),
    div:has(> .sb-bottom-waves),
    [data-testid="stMarkdown"]:has(.sb-bottom-waves),
    [data-testid="stMarkdownContainer"]:has(.sb-bottom-waves) {
        position: static !important;
        width: 0 !important;
        height: 0 !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        overflow: visible !important;
    }

    /* Hide default Streamlit collapse button visually while keeping it accessible in DOM */
    [data-testid="stSidebarCollapseButton"] {
        opacity: 0 !important;
        position: absolute !important;
        pointer-events: none !important;
        height: 0 !important;
        width: 0 !important;
        overflow: hidden !important;
    }

    /* ─── 2. Header & Branding ──────────────────────────────── */
    .sb-brand-wrapper {
        width: 100%;
        margin-bottom: 16px;
    }
    .sb-brand-row {
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 10px;
    }
    .sb-brand-left {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 0;
    }
    .sb-brand-logo-sq {
        width: 44px;
        height: 44px;
        border-radius: 12px;
        background: #CCFBF1;
        border: 1px solid #99F6E4;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
        box-shadow: 0 2px 6px rgba(13, 148, 136, 0.12);
    }
    .sb-brand-title {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 16px;
        font-weight: 800;
        color: #0F172A !important;
        line-height: 1.2;
        letter-spacing: -0.015em;
        white-space: nowrap !important;
    }
    .sb-brand-sub {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
        font-size: 12px;
        font-weight: 500;
        color: #64748B !important;
        margin-top: 2px;
        white-space: nowrap !important;
    }
    .sb-collapse-btn {
        width: 32px;
        height: 32px;
        border-radius: 8px;
        background: #F1F5F9;
        border: 1px solid #E2E8F0;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        color: #64748B;
        transition: all 140ms ease;
        padding: 0;
        flex-shrink: 0;
    }
    .sb-collapse-btn:hover {
        background: #E2E8F0;
        color: #0F172A;
        border-color: #CBD5E1;
        transform: scale(1.04);
    }
    .sb-header-teal-divider {
        height: 2px;
        background: #0D9488;
        border-radius: 1px;
        margin-top: 14px;
        margin-bottom: 18px;
        width: 100%;
    }

    /* ─── 3. Promotional Card ───────────────────────────────── */
    .sb-promo-card {
        background: linear-gradient(135deg, #F0FDF9 0%, #E6FFFA 100%);
        border: 1px solid #CCFBF1;
        border-radius: 14px;
        padding: 14px 14px 14px 16px;
        margin-bottom: 20px;
        box-shadow: 0 2px 10px rgba(13, 148, 136, 0.05);
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        box-sizing: border-box;
        position: relative;
        overflow: hidden;
    }
    .sb-promo-left {
        flex: 1;
        min-width: 0;
    }
    .sb-promo-icon-badge {
        width: 26px;
        height: 26px;
        border-radius: 7px;
        background: #CCFBF1;
        border: 1px solid #99F6E4;
        display: inline-flex;
        align-items: center;
        justify-content: center;
        margin-bottom: 8px;
    }
    .sb-promo-title {
        font-size: 13px;
        font-weight: 700;
        color: #0F172A;
        line-height: 1.25;
        margin-bottom: 4px;
    }
    .sb-promo-desc {
        font-size: 11px;
        color: #64748B;
        line-height: 1.38;
    }
    .sb-promo-right {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* ─── 4. Section Title Heading ──────────────────────────── */
    .sb-section-heading-row {
        display: flex;
        align-items: center;
        gap: 8px;
        margin-top: 4px;
        margin-bottom: 16px;
        width: 100%;
        box-sizing: border-box;
    }
    .sb-sec-badge {
        width: 18px;
        height: 18px;
        border-radius: 4px;
        background: #7C3AED;
        display: flex;
        align-items: center;
        justify-content: center;
        flex-shrink: 0;
    }
    .sb-sec-text {
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 0.08em;
        color: #475569;
        text-transform: uppercase;
        white-space: nowrap;
    }
    .sb-sec-line {
        flex: 1;
        height: 1px;
        background: #CBD5E1;
    }

    /* ─── 5. Form Labels & Input Compartments ───────────────── */
    [data-testid="stSidebar"] label[data-testid="stWidgetLabel"] {
        display: flex !important;
        flex-direction: row !important;
        align-items: center !important;
        justify-content: space-between !important;
        width: 100% !important;
        margin-bottom: 6px !important;
        min-height: 22px !important;
    }
    [data-testid="stSidebar"] label[data-testid="stWidgetLabel"] p {
        font-size: 13px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        display: inline-flex !important;
        align-items: center !important;
        gap: 8px !important;
        margin: 0 !important;
        line-height: 1.4 !important;
    }

    /* Label Icons via pseudo-element */
    /* Host label: computer monitor */
    [data-testid="stSidebar"] [data-testid="stTextInput"]:has(input[aria-label*="Host" i]) label[data-testid="stWidgetLabel"] p::before {
        content: '';
        display: inline-block;
        width: 16px;
        height: 16px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230F172A' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='3' width='20' height='14' rx='2'%3E%3C/rect%3E%3Cline x1='8' y1='21' x2='16' y2='21'%3E%3C/line%3E%3Cline x1='12' y1='17' x2='12' y2='21'%3E%3C/line%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-size: contain;
    }
    /* Port label: network fork / branch */
    [data-testid="stSidebar"] [data-testid="stNumberInput"] label[data-testid="stWidgetLabel"] p::before {
        content: '';
        display: inline-block;
        width: 16px;
        height: 16px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230F172A' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Ccircle cx='18' cy='5' r='3'%3E%3C/circle%3E%3Ccircle cx='6' cy='12' r='3'%3E%3C/circle%3E%3Ccircle cx='18' cy='19' r='3'%3E%3C/circle%3E%3Cline x1='8.59' y1='13.51' x2='15.42' y2='17.49'%3E%3C/line%3E%3Cline x1='15.41' y1='6.51' x2='8.59' y2='10.49'%3E%3C/line%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-size: contain;
    }
    /* Username label: user person */
    [data-testid="stSidebar"] [data-testid="stTextInput"]:has(input[aria-label*="Username" i]) label[data-testid="stWidgetLabel"] p::before {
        content: '';
        display: inline-block;
        width: 16px;
        height: 16px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230F172A' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2'%3E%3C/path%3E%3Ccircle cx='12' cy='7' r='4'%3E%3C/circle%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-size: contain;
    }
    /* Password label: padlock */
    [data-testid="stSidebar"] [data-testid="stTextInput"]:has(input[aria-label*="Password" i]) label[data-testid="stWidgetLabel"] p::before {
        content: '';
        display: inline-block;
        width: 16px;
        height: 16px;
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='16' height='16' viewBox='0 0 24 24' fill='none' stroke='%230F172A' stroke-width='2.2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='11' width='18' height='11' rx='2' ry='2'%3E%3C/rect%3E%3Cpath d='M7 11V7a5 5 0 0 1 10 0v4'%3E%3C/path%3E%3C/svg%3E");
        background-repeat: no-repeat;
        background-size: contain;
    }

    /* Info Tooltip Icon styling */
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"] {
        margin-left: auto !important;
        color: #475569 !important;
        opacity: 0.9 !important;
    }
    [data-testid="stSidebar"] [data-testid="stTooltipIcon"] svg {
        width: 15px !important;
        height: 15px !important;
        stroke: #475569 !important;
    }

    /* ─── Input Container Boxes (Streamlit React-Aria & BaseWeb) ─── */
    [data-testid="stSidebar"] [data-testid="stTextInputRootElement"],
    [data-testid="stSidebar"] [data-testid="stNumberInputContainer"] {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        height: 42px !important;
        min-height: 42px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
        overflow: hidden !important;
        display: flex !important;
        align-items: center !important;
        transition: border-color 150ms ease, box-shadow 150ms ease !important;
        box-sizing: border-box !important;
    }

    [data-testid="stSidebar"] [data-testid="stTextInputRootElement"]:focus-within,
    [data-testid="stSidebar"] [data-testid="stNumberInputContainer"]:focus-within {
        border-color: #0D9488 !important;
        box-shadow: 0 0 0 3px rgba(13, 148, 136, 0.15) !important;
    }

    /* Left Icon Compartment (44px wide with subtle right border) */
    [data-testid="stSidebar"] [data-testid="stTextInputRootElement"]::before,
    [data-testid="stSidebar"] [data-testid="stNumberInputContainer"]::before {
        content: '' !important;
        width: 44px !important;
        min-width: 44px !important;
        height: 100% !important;
        background-color: #F8FAFC !important;
        border-right: 1px solid #E2E8F0 !important;
        background-repeat: no-repeat !important;
        background-position: center !important;
        background-size: 16px 16px !important;
        flex-shrink: 0 !important;
        box-sizing: border-box !important;
    }

    /* Host input left icon: server rack */
    [data-testid="stSidebar"] [data-testid="stTextInput"]:has(input[aria-label*="Host" i]) [data-testid="stTextInputRootElement"]::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%23475569' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='2' y='2' width='20' height='8' rx='2' ry='2'%3E%3C/rect%3E%3Crect x='2' y='14' width='20' height='8' rx='2' ry='2'%3E%3C/rect%3E%3Cline x1='6' y1='6' x2='6.01' y2='6'%3E%3C/line%3E%3Cline x1='6' y1='18' x2='6.01' y2='18'%3E%3C/line%3E%3C/svg%3E") !important;
    }

    /* Port input left icon: electric plug */
    [data-testid="stSidebar"] [data-testid="stNumberInput"] [data-testid="stNumberInputContainer"]::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%23475569' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M12 22v-5'%3E%3C/path%3E%3Cpath d='M9 8V2'%3E%3C/path%3E%3Cpath d='M15 8V2'%3E%3C/path%3E%3Cpath d='M18 8v5a6 6 0 0 1-12 0V8z'%3E%3C/path%3E%3C/svg%3E") !important;
    }

    /* Username input left icon: user silhouette */
    [data-testid="stSidebar"] [data-testid="stTextInput"]:has(input[aria-label*="Username" i]) [data-testid="stTextInputRootElement"]::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%23475569' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Cpath d='M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2'%3E%3C/path%3E%3Ccircle cx='12' cy='7' r='4'%3E%3C/circle%3E%3C/svg%3E") !important;
    }

    /* Password input left icon: padlock */
    [data-testid="stSidebar"] [data-testid="stTextInput"]:has(input[aria-label*="Password" i]) [data-testid="stTextInputRootElement"]::before {
        background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='18' height='18' viewBox='0 0 24 24' fill='none' stroke='%23475569' stroke-width='2' stroke-linecap='round' stroke-linejoin='round'%3E%3Crect x='3' y='11' width='18' height='11' rx='2' ry='2'%3E%3C/rect%3E%3Cpath d='M7 11V7a5 5 0 0 1 10 0v4'%3E%3C/path%3E%3C/svg%3E") !important;
    }

    /* Actual inputs inside the box */
    [data-testid="stSidebar"] input[data-testid="stTextInputField"],
    [data-testid="stSidebar"] input[data-testid="stNumberInputField"],
    [data-testid="stSidebar"] [data-testid="stTextInputRootElement"] input,
    [data-testid="stSidebar"] [data-testid="stNumberInputContainer"] input {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        outline: none !important;
        height: 100% !important;
        padding: 0 12px !important;
        font-size: 13.5px !important;
        font-weight: 500 !important;
        color: #0F172A !important;
        font-family: 'Inter', -apple-system, sans-serif !important;
    }

    /* Port stepper buttons: minus and plus */
    [data-testid="stSidebar"] [data-testid="stNumberInputStepDown"],
    [data-testid="stSidebar"] [data-testid="stNumberInputStepUp"] {
        background: transparent !important;
        border: none !important;
        border-left: 1px solid #E2E8F0 !important;
        border-radius: 0 !important;
        height: 100% !important;
        width: 30px !important;
        color: #0F172A !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: none !important;
        padding: 0 !important;
        transition: background 120ms ease !important;
    }
    [data-testid="stSidebar"] [data-testid="stNumberInputStepDown"]:hover,
    [data-testid="stSidebar"] [data-testid="stNumberInputStepUp"]:hover {
        background: #F1F5F9 !important;
        color: #0D9488 !important;
    }

    /* Password eye toggle button */
    [data-testid="stSidebar"] [data-testid="stTextInputRootElement"] button[aria-label*="password" i] {
        background: transparent !important;
        border: none !important;
        border-left: 1px solid #E2E8F0 !important;
        border-radius: 0 !important;
        height: 100% !important;
        width: 36px !important;
        color: #475569 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        box-shadow: none !important;
        padding: 0 !important;
        transition: background 120ms ease !important;
    }
    [data-testid="stSidebar"] [data-testid="stTextInputRootElement"] button[aria-label*="password" i]:hover {
        background: #F1F5F9 !important;
        color: #0F172A !important;
    }

    /* ─── 6. Advanced Connection Options ────────────────────── */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        background: #F0F9FF !important;
        border: 1px solid #BAE6FD !important;
        border-radius: 10px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
        margin-top: 14px !important;
        margin-bottom: 14px !important;
        overflow: hidden !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        background: transparent !important;
        padding: 11px 14px !important;
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #0F172A !important;
        display: flex !important;
        align-items: center !important;
        cursor: pointer !important;
        transition: background 140ms ease !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
        background: rgba(186, 230, 253, 0.25) !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary p {
        font-size: 13px !important;
        font-weight: 600 !important;
        color: #0F172A !important;
        margin: 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stExpander"] summary svg {
        color: #475569 !important;
    }

    /* ─── 7. Action Buttons ─────────────────────────────────── */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        gap: 12px !important;
        margin-top: 4px !important;
        margin-bottom: 14px !important;
    }

    /* Test button (White outlined) */
    [data-testid="stSidebar"] button[key*="test" i],
    [data-testid="stSidebar"] .stButton:has(button:contains("Test")) button,
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:first-child button {
        height: 42px !important;
        background: #FFFFFF !important;
        border: 1.5px solid #CBD5E1 !important;
        border-radius: 10px !important;
        color: #0F172A !important;
        font-size: 14px !important;
        font-weight: 700 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.05) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
        transition: all 140ms ease !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:first-child button:hover {
        border-color: #94A3B8 !important;
        background: #F8FAFC !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 3px 8px rgba(15, 23, 42, 0.08) !important;
    }

    /* Connect button (Teal gradient) */
    [data-testid="stSidebar"] button[key*="connect" i],
    [data-testid="stSidebar"] .stButton:has(button:contains("Connect")) button,
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:last-child button {
        height: 42px !important;
        background: linear-gradient(135deg, #0D9488 0%, #0F766E 100%) !important;
        border: none !important;
        border-radius: 10px !important;
        color: #FFFFFF !important;
        font-size: 14px !important;
        font-weight: 700 !important;
        box-shadow: 0 3px 10px rgba(13, 148, 136, 0.28) !important;
        display: inline-flex !important;
        align-items: center !important;
        justify-content: center !important;
        gap: 8px !important;
        transition: all 140ms ease !important;
        width: 100% !important;
    }
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] > div:last-child button:hover {
        background: linear-gradient(135deg, #0F766E 0%, #115E59 100%) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 5px 14px rgba(13, 148, 136, 0.36) !important;
    }

    /* ─── 8. Connection Status Card ─────────────────────────── */
    .sb-status-card {
        border-radius: 14px;
        padding: 14px 16px;
        margin-top: 14px;
        margin-bottom: 18px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        gap: 12px;
        box-sizing: border-box;
    }
    .sb-status-card.disconnected {
        background: #FFF1F2;
        border: 1px solid #FECDD3;
        box-shadow: 0 2px 8px rgba(225, 29, 72, 0.04);
    }
    .sb-status-card.connected {
        background: #F0FDF4;
        border: 1px solid #BBF7D0;
        box-shadow: 0 2px 8px rgba(22, 163, 74, 0.05);
    }
    .sb-status-left {
        display: flex;
        align-items: center;
        gap: 12px;
        min-width: 0;
    }
    .sb-status-dot {
        width: 12px;
        height: 12px;
        border-radius: 50%;
        flex-shrink: 0;
    }
    .sb-status-dot.dot-red {
        background: #E11D48;
        box-shadow: 0 0 0 3px rgba(225, 29, 72, 0.15);
    }
    .sb-status-dot.dot-green {
        background: #10B981;
        box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.15);
    }
    .sb-status-title {
        font-size: 14px;
        font-weight: 700;
        color: #0F172A;
        line-height: 1.25;
    }
    .sb-status-desc {
        font-size: 11.5px;
        color: #64748B;
        margin-top: 2px;
        line-height: 1.35;
    }
    .sb-status-right {
        flex-shrink: 0;
        display: flex;
        align-items: center;
        justify-content: center;
    }

    /* ─── 9. Bottom Layered Teal Waves ──────────────────────── */
    .sb-bottom-waves {
        position: absolute !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        width: 100% !important;
        height: 100px !important;
        z-index: 1 !important;
        pointer-events: none !important;
        margin: 0 !important;
        padding: 0 !important;
        border: none !important;
        border-radius: 0 !important;
        overflow: hidden !important;
        line-height: 0 !important;
        background: transparent !important;
        box-sizing: border-box !important;
    }
    .sb-bottom-waves svg {
        width: 100% !important;
        height: 100% !important;
        display: block !important;
    }
    </style>
    """


def render_sidebar_brand_redesign() -> None:
    """Renders the top branding header with mint square logo, titles, collapse button, and teal divider."""
    html = """
    <div class="sb-brand-wrapper">
        <div class="sb-brand-row">
            <div class="sb-brand-left">
                <div class="sb-brand-logo-sq">
                    <svg width="22" height="24" viewBox="0 0 24 26" fill="none">
                        <path d="M12 1L2 5.5V12C2 18.5 6.3 24.3 12 25.8C17.7 24.3 22 18.5 22 12V5.5L12 1Z" fill="#0284C7" stroke="#38BDF8" stroke-width="1.3"/>
                        <path d="M12 4.5L5 8V12C5 16.5 8 20.8 12 22C16 20.8 19 16.5 19 12V8L12 4.5Z" fill="#38BDF8" fill-opacity="0.4"/>
                    </svg>
                </div>
                <div>
                    <div class="sb-brand-title">DataClean Studio</div>
                    <div class="sb-brand-sub">Connection Manager</div>
                </div>
            </div>
            <button type="button" class="sb-collapse-btn" title="Collapse sidebar" onclick="
                try {
                    var colBtn = window.parent.document.querySelector('[data-testid=\\'stSidebarCollapseButton\\'] button') || document.querySelector('[data-testid=\\'stSidebarCollapseButton\\'] button');
                    if (colBtn) colBtn.click();
                } catch(e) {}
            ">
                <svg width="14" height="14" viewBox="0 0 24 26" fill="none" stroke="#64748B" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="11 17 6 12 11 7"></polyline>
                    <polyline points="18 17 13 12 18 7"></polyline>
                </svg>
            </button>
        </div>
        <div class="sb-header-teal-divider"></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_sidebar_promo_card() -> None:
    """Renders the pale mint promotional card with 3D teal database stack & shield illustration."""
    html = """
    <div class="sb-promo-card">
        <div class="sb-promo-left">
            <div class="sb-promo-icon-badge">
                <svg width="15" height="15" viewBox="0 0 24 24" fill="none">
                    <path d="M12 2C6.48 2 2 4.24 2 7V17C2 19.76 6.48 22 12 22C17.52 22 22 19.76 22 17V7C22 4.24 17.52 2 12 2Z" fill="#CCFBF1" stroke="#0D9488" stroke-width="1.8"/>
                    <path d="M12 11L7 13.5V17C7 20 9.5 21.8 12 22C14.5 21.8 17 20 17 17V13.5L12 11Z" fill="#0D9488"/>
                </svg>
            </div>
            <div class="sb-promo-title">Secure Database Connection</div>
            <div class="sb-promo-desc">Connect to your MySQL database to start cleaning and analyzing your data.</div>
        </div>
        <div class="sb-promo-right">
            <svg width="74" height="66" viewBox="0 0 100 90" fill="none" xmlns="http://www.w3.org/2000/svg">
                <!-- Ground glow -->
                <ellipse cx="50" cy="74" rx="36" ry="12" fill="#99F6E4" fill-opacity="0.45"/>
                <!-- Bottom cylinder -->
                <path d="M22 48 C22 42 78 42 78 48 V62 C78 68 22 68 22 62 Z" fill="url(#db-grad-base)"/>
                <ellipse cx="50" cy="48" rx="28" ry="8" fill="url(#db-grad-top)"/>
                <!-- Middle cylinder -->
                <path d="M22 34 C22 28 78 28 78 34 V48 C78 54 22 54 22 48 Z" fill="url(#db-grad-base)"/>
                <ellipse cx="50" cy="34" rx="28" ry="8" fill="url(#db-grad-top)"/>
                <!-- Top cylinder -->
                <path d="M22 20 C22 14 78 14 78 20 V34 C78 40 22 40 22 34 Z" fill="url(#db-grad-base)"/>
                <ellipse cx="50" cy="20" rx="28" ry="8" fill="url(#db-grad-cap)"/>
                <ellipse cx="50" cy="20" rx="24" ry="6" fill="#5EEAD4" fill-opacity="0.6"/>
                <!-- Grooves -->
                <path d="M22 34 C28 38 72 38 78 34" stroke="#042F2E" stroke-width="1.2" stroke-opacity="0.25"/>
                <path d="M22 48 C28 52 72 52 78 48" stroke="#042F2E" stroke-width="1.2" stroke-opacity="0.25"/>
                <!-- Shield badge on front -->
                <path d="M68 36 L52 42 V54 C52 64 68 70 68 70 C68 70 84 64 84 54 V42 L68 36 Z" fill="url(#shield-grad)"/>
                <path d="M68 38.5 L54.5 43.5 V53.5 C54.5 61.5 68 67 68 67 C68 67 81.5 61.5 81.5 53.5 V43.5 L68 38.5 Z" stroke="#CCFBF1" stroke-width="1.5" fill="none"/>
                <path d="M64 52 L67 55 L73 48" stroke="#FFFFFF" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/>
                <!-- Dots -->
                <circle cx="82" cy="18" r="2.5" fill="#10B981"/>
                <circle cx="88" cy="28" r="1.5" fill="#34D399"/>
                <defs>
                    <linearGradient id="db-grad-base" x1="22" y1="20" x2="78" y2="60" gradientUnits="userSpaceOnUse">
                        <stop stop-color="#0F766E"/>
                        <stop offset="0.5" stop-color="#0D9488"/>
                        <stop offset="1" stop-color="#044E46"/>
                    </linearGradient>
                    <linearGradient id="db-grad-top" x1="22" y1="26" x2="78" y2="26" gradientUnits="userSpaceOnUse">
                        <stop stop-color="#14B8A6"/>
                        <stop offset="0.5" stop-color="#2DD4BF"/>
                        <stop offset="1" stop-color="#0F766E"/>
                    </linearGradient>
                    <linearGradient id="db-grad-cap" x1="22" y1="12" x2="78" y2="12" gradientUnits="userSpaceOnUse">
                        <stop stop-color="#2DD4BF"/>
                        <stop offset="0.5" stop-color="#5EEAD4"/>
                        <stop offset="1" stop-color="#0D9488"/>
                    </linearGradient>
                    <linearGradient id="shield-grad" x1="52" y1="36" x2="84" y2="70" gradientUnits="userSpaceOnUse">
                        <stop stop-color="#0284C7"/>
                        <stop offset="0.5" stop-color="#0369A1"/>
                        <stop offset="1" stop-color="#0C4A6E"/>
                    </linearGradient>
                </defs>
            </svg>
        </div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_sidebar_section_heading() -> None:
    """Renders 'DATABASE CONNECTION' heading with purple database icon and horizontal line."""
    html = """
    <div class="sb-section-heading-row">
        <div class="sb-sec-badge">
            <svg width="12" height="12" viewBox="0 0 20 20" fill="none">
                <rect x="2" y="2" width="16" height="4.5" rx="1.2" fill="#FFFFFF"/>
                <circle cx="5" cy="4.25" r="0.9" fill="#7C3AED"/>
                <rect x="2" y="8" width="16" height="4.5" rx="1.2" fill="#FFFFFF"/>
                <circle cx="5" cy="10.25" r="0.9" fill="#7C3AED"/>
                <rect x="2" y="14" width="16" height="4.5" rx="1.2" fill="#FFFFFF"/>
                <circle cx="5" cy="16.25" r="0.9" fill="#7C3AED"/>
            </svg>
        </div>
        <span class="sb-sec-text">DATABASE CONNECTION</span>
        <div class="sb-sec-line"></div>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)


def render_sidebar_status_card_redesign(
    connected: bool = False,
    host: str = "",
    username: str = "",
    server_ver: str = "",
) -> None:
    """Renders the connection status card (pale pink Disconnected / pale green Connected)."""
    if connected:
        html = f"""
        <div class="sb-status-card connected">
            <div class="sb-status-left">
                <div class="sb-status-dot dot-green"></div>
                <div>
                    <div class="sb-status-title">Connected</div>
                    <div class="sb-status-desc">{host} &bull; {username} {f'&bull; {server_ver}' if server_ver else ''}</div>
                </div>
            </div>
            <div class="sb-status-right">
                <svg width="34" height="34" viewBox="0 0 24 24" fill="none" stroke="#10B981" stroke-width="2">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path>
                    <polyline points="22 4 12 14.01 9 11.01"></polyline>
                </svg>
            </div>
        </div>
        """
    else:
        html = """
        <div class="sb-status-card disconnected">
            <div class="sb-status-left">
                <div class="sb-status-dot dot-red"></div>
                <div>
                    <div class="sb-status-title">Disconnected</div>
                    <div class="sb-status-desc">Not connected to any database</div>
                </div>
            </div>
            <div class="sb-status-right">
                <svg width="42" height="42" viewBox="0 0 60 60" fill="none" xmlns="http://www.w3.org/2000/svg">
                    <path d="M12 36 C12 32 48 32 48 36 V44 C48 48 12 48 12 44 Z" fill="#FECDD3"/>
                    <ellipse cx="30" cy="36" rx="18" ry="5.5" fill="#FFE4E6"/>
                    <path d="M12 25 C12 21 48 21 48 25 V33 C48 37 12 37 12 33 Z" fill="#FECDD3"/>
                    <ellipse cx="30" cy="25" rx="18" ry="5.5" fill="#FFE4E6"/>
                    <path d="M12 14 C12 10 48 10 48 14 V22 C48 26 12 26 12 22 Z" fill="#FECDD3"/>
                    <ellipse cx="30" cy="14" rx="18" ry="5.5" fill="#FFF1F2"/>
                    <ellipse cx="30" cy="14" rx="15" ry="4" fill="#FFFFFF" fill-opacity="0.8"/>
                    <path d="M12 25 C18 28 42 28 48 25" stroke="#F43F5E" stroke-width="0.8" stroke-opacity="0.3"/>
                    <path d="M12 36 C18 39 42 39 48 36" stroke="#F43F5E" stroke-width="0.8" stroke-opacity="0.3"/>
                </svg>
            </div>
        </div>
        """
    st.markdown(html, unsafe_allow_html=True)


def render_sidebar_bottom_waves() -> None:
    """Renders decorative layered mint and teal waves at the bottom of the sidebar."""
    html = """
    <div class="sb-bottom-waves">
        <svg viewBox="0 0 360 100" preserveAspectRatio="none" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M0 28 C65 10 155 58 240 30 C290 14 330 22 360 26 V100 H0 Z" fill="#99F6E4" fill-opacity="0.4"/>
            <path d="M0 45 C80 26 160 66 250 40 C295 28 335 38 360 44 V100 H0 Z" fill="#5EEAD4" fill-opacity="0.5"/>
            <path d="M0 62 C95 45 180 72 270 54 C305 48 335 54 360 58 V100 H0 Z" fill="#2DD4BF" fill-opacity="0.65"/>
            <path d="M0 78 C110 65 200 84 285 72 C320 68 345 71 360 74 V100 H0 Z" fill="#14B8A6" fill-opacity="0.25"/>
        </svg>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)
