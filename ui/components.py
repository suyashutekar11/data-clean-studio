"""
DataClean Studio — Enterprise SaaS Component Library
ui/components.py

Hand-crafted, modern 2026 SaaS design components:
- Restraint over decoration: solid surfaces, clean borders, no glows or gradient cards.
- Strong hierarchy & typography scale (Inter, tabular numerals).
- Reusable component helpers routed safely through render_html():
    • render_html(html) - Eliminates markdown code block parsing of indented HTML
    • render_page_header(title, subtitle, actions)
    • render_card(title, description, body)
    • render_section_header(title, description)
    • render_alert(type, title, message)
    • render_badge(type, text)
    • render_metric_card(label, value, hint)
    • render_sandbox_banner(working_table, source_table, row_count)
    • render_stepper(steps, current_index)
    • render_data_table(df, max_rows, title) / render_saas_table
    • render_saas_breadcrumb(items)
    • render_module_header(title, subtitle, badge_text, ...)
"""

from __future__ import annotations

import html
import re
import textwrap
from typing import Optional, List, Dict, Any, Union
import pandas as pd
import streamlit as st

from ui.icons import get_icon_svg


# ─────────────────────────────────────────────────────────────
# 0. Canonical HTML Renderer (No Markdown Code-Block Artifacts)
# ─────────────────────────────────────────────────────────────

def render_html(html_str: str) -> None:
    """
    Safely renders HTML via st.markdown by stripping line indentation and joining lines.
    Streamlit markdown parses any HTML line with 4+ spaces of indentation as a
    <pre><code> block. This helper guarantees pure HTML rendering.
    """
    if not html_str:
        return
    dedented = textwrap.dedent(str(html_str))
    lines = [line.strip() for line in dedented.splitlines() if line.strip()]
    single_line = " ".join(lines)
    st.markdown(single_line, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# 1. Page Header & Section Header
# ─────────────────────────────────────────────────────────────

def render_page_header(
    title: str,
    subtitle: Optional[str] = None,
    actions_html: Optional[str] = None,
    back_label: Optional[str] = None,
    back_target: Optional[str] = None,
) -> None:
    """Renders a clean, uncluttered page header with 26px/700 title, optional back link, and actions."""
    back_markup = ""
    if back_label:
        back_icon = get_icon_svg("arrow_left", size=14, stroke_width=2.0)
        back_markup = f"""
        <div class="dc-back-link-wrapper">
            <a href="?ws_sub={back_target or 'hub'}" target="_self" class="dc-back-link">
                {back_icon}
                <span>{html.escape(back_label)}</span>
            </a>
        </div>
        """

    sub_markup = f'<div class="dc-page-subtitle">{html.escape(subtitle)}</div>' if subtitle else ""
    act_markup = f'<div class="dc-page-actions">{actions_html}</div>' if actions_html else ""

    content = f"""
    <div class="dc-page-header">
        {back_markup}
        <div class="dc-page-header-row">
            <div class="dc-page-title-group">
                <h1 class="dc-page-title">{html.escape(title)}</h1>
                {sub_markup}
            </div>
            {act_markup}
        </div>
    </div>
    """
    render_html(content)


def render_section_header(
    title: str,
    description: Optional[str] = None,
    icon: Optional[str] = None,
) -> None:
    """Renders a section header with 18px/600 title and 13px helper text."""
    icon_markup = f'<span class="dc-section-icon">{get_icon_svg(icon, size=18)}</span>' if icon else ""
    desc_markup = f'<div class="dc-section-desc">{html.escape(description)}</div>' if description else ""

    content = f"""
    <div class="dc-section-header">
        <div class="dc-section-title-row">
            {icon_markup}
            <h2 class="dc-section-title">{html.escape(title)}</h2>
        </div>
        {desc_markup}
    </div>
    """
    render_html(content)


# ─────────────────────────────────────────────────────────────
# 2. Cards & Containers
# ─────────────────────────────────────────────────────────────

def render_card(
    title: Optional[str] = None,
    description: Optional[str] = None,
    body_html: Optional[str] = None,
    badge_text: Optional[str] = None,
    badge_type: str = "neutral",
) -> None:
    """Renders a solid white card (1px slate-200 border, 12px radius, subtle shadow)."""
    header_markup = ""
    if title:
        badge_markup = render_badge(badge_type, badge_text, as_string=True) if badge_text else ""
        desc_markup = f'<div class="dc-card-desc">{html.escape(description)}</div>' if description else ""
        header_markup = f"""
        <div class="dc-card-header">
            <div class="dc-card-title-row">
                <h3 class="dc-card-title">{html.escape(title)}</h3>
                {badge_markup}
            </div>
            {desc_markup}
        </div>
        """

    content = f"""
    <div class="dc-card">
        {header_markup}
        <div class="dc-card-body">
            {body_html or ''}
        </div>
    </div>
    """
    render_html(content)


# ─────────────────────────────────────────────────────────────
# 3. Semantic Alerts (info, success, warning, error)
# ─────────────────────────────────────────────────────────────

def render_alert(
    alert_type: str,
    title: str,
    message: Optional[str] = None,
    key: Optional[str] = None,
) -> None:
    """
    Renders a semantic, calm alert with tinted background, 1px border, monoline icon,
    and concise text (max two lines). Never uses brand teal for semantic states.
    Types: 'info', 'success', 'warning', 'error'
    """
    valid_types = {
        "info": ("info", "dc-alert-info"),
        "success": ("check_circle", "dc-alert-success"),
        "warning": ("warning", "dc-alert-warning"),
        "error": ("error", "dc-alert-error"),
    }
    icon_name, css_class = valid_types.get(alert_type.lower(), ("info", "dc-alert-info"))
    icon_svg = get_icon_svg(icon_name, size=18, stroke_width=2.0)

    msg_markup = f'<div class="dc-alert-msg">{html.escape(message)}</div>' if message else ""

    alert_html = f"""
    <div class="dc-alert {css_class}">
        <div class="dc-alert-icon">{icon_svg}</div>
        <div class="dc-alert-content">
            <div class="dc-alert-title">{html.escape(title)}</div>
            {msg_markup}
        </div>
    </div>
    """
    render_html(alert_html)


# ─────────────────────────────────────────────────────────────
# 4. Badges (Valid, Invalid, Empty, Ambiguous, Neutral)
# ─────────────────────────────────────────────────────────────

def render_badge(
    badge_type: str,
    text: str,
    as_string: bool = False,
) -> Optional[str]:
    """
    Renders a small status badge with 6px radius, semantic colors, and tabular numbers.
    Types: 'valid' (green), 'invalid' (red), 'warning'/'ambiguous' (amber),
           'info' (blue), 'neutral'/'empty' (slate), 'brand' (teal).
    """
    type_map = {
        "valid": "dc-badge-valid",
        "invalid": "dc-badge-invalid",
        "error": "dc-badge-invalid",
        "warning": "dc-badge-warning",
        "ambiguous": "dc-badge-warning",
        "empty": "dc-badge-neutral",
        "neutral": "dc-badge-neutral",
        "info": "dc-badge-info",
        "brand": "dc-badge-brand",
    }
    css_class = type_map.get(badge_type.lower(), "dc-badge-neutral")
    badge_html = f'<span class="dc-badge {css_class}">{html.escape(text)}</span>'

    if as_string:
        return badge_html
    render_html(badge_html)
    return None


# ─────────────────────────────────────────────────────────────
# 5. Metric Cards
# ─────────────────────────────────────────────────────────────

def render_metric_card(
    label: str,
    value: Union[str, int, float],
    hint: Optional[str] = None,
    delta: Optional[str] = None,
    delta_type: str = "neutral",
) -> None:
    """
    Renders an equal-height metric card with tabular numerals and non-truncated label:
    Label: 13px slate-600, Value: 28px/700 tabular numerals, Hint: 12px slate-500.
    """
    val_str = f"{value:,}" if isinstance(value, (int, float)) else str(value)
    hint_markup = f'<div class="dc-metric-hint">{html.escape(hint)}</div>' if hint else ""

    delta_markup = ""
    if delta:
        delta_cls = "pos" if delta_type == "positive" else ("neg" if delta_type == "negative" else "neu")
        delta_markup = f'<span class="dc-metric-delta {delta_cls}">{html.escape(delta)}</span>'

    content = f"""
    <div class="dc-metric-card">
        <div class="dc-metric-label">{html.escape(label)}</div>
        <div class="dc-metric-value-row">
            <span class="dc-metric-value">{html.escape(val_str)}</span>
            {delta_markup}
        </div>
        {hint_markup}
    </div>
    """
    render_html(content)


# ─────────────────────────────────────────────────────────────
# 6. Sandbox Banner (Slim Info Strip)
# ─────────────────────────────────────────────────────────────

def render_sandbox_banner(
    working_table: str,
    source_table: Optional[str] = None,
    row_count: Optional[int] = None,
) -> None:
    """
    Renders a 44px high info-style strip for the active workspace:
    - Shield icon
    - 'Sandbox active' (13px, 600, sentence case, not uppercase)
    - Monospace table name with copy button on one line (white-space: nowrap)
    - Single muted line: 'Isolated copy of <source_table> · <row_count> rows'
    """
    shield_icon = get_icon_svg("shield_check", size=16, stroke_width=2.0)
    copy_icon = get_icon_svg("copy", size=13, stroke_width=1.75)

    source_desc = f"of {html.escape(source_table)}" if source_table else ""
    rows_desc = f" · {row_count:,} rows" if row_count is not None else ""
    secondary_text = f"Isolated copy {source_desc}{rows_desc}".strip()

    content = f"""
    <div class="dc-sandbox-strip">
        <div class="dc-sandbox-row">
            <span class="dc-sandbox-icon">{shield_icon}</span>
            <div class="dc-sandbox-text">
                <div class="dc-sandbox-label">Sandbox active</div>
                <div class="dc-sandbox-caption">{secondary_text}</div>
            </div>
            <div class="dc-sandbox-chip-group">
                <span class="dc-sandbox-table">{html.escape(working_table)}</span>
                <button class="dc-copy-btn" onclick="navigator.clipboard.writeText('{html.escape(working_table)}'); this.classList.add('copied'); setTimeout(() => this.classList.remove('copied'), 1500);" title="Copy table name">
                    {copy_icon}
                </button>
            </div>
        </div>
    </div>
    """
    render_html(content)


# ─────────────────────────────────────────────────────────────
# 7. Workflow Stepper
# ─────────────────────────────────────────────────────────────

def render_stepper(
    steps: List[str],
    current_index: int,
) -> None:
    """
    Renders a clean horizontal stepper connected by thin lines.
    Completed steps show check icon, active step in brand color, upcoming in slate.
    """
    items_html = []
    total = len(steps)

    for idx, name in enumerate(steps):
        is_completed = idx < current_index
        is_current = idx == current_index

        if is_completed:
            icon_content = get_icon_svg("check", size=14, stroke_width=2.5)
            circle_cls = "completed"
        elif is_current:
            icon_content = str(idx + 1)
            circle_cls = "current"
        else:
            icon_content = str(idx + 1)
            circle_cls = "upcoming"

        line_markup = '<div class="dc-stepper-line"></div>' if idx < total - 1 else ""

        items_html.append(f"""
        <div class="dc-stepper-step {circle_cls}">
            <div class="dc-stepper-circle">{icon_content}</div>
            <div class="dc-stepper-label">{html.escape(name)}</div>
        </div>
        {line_markup}
        """)

    content = f"""
    <div class="dc-stepper">
        {''.join(items_html)}
    </div>
    """
    render_html(content)


# ─────────────────────────────────────────────────────────────
# 8. Enterprise Data Table
# ─────────────────────────────────────────────────────────────

def _format_cell_whitespace(s_str: str) -> str:
    """Format whitespace so only abnormal whitespace (leading, trailing, or multiple spaces) is marked."""
    l_len = len(s_str) - len(s_str.lstrip(" "))
    r_len = len(s_str) - len(s_str.rstrip(" "))

    # If uniform with single spaces in the middle and no leading/trailing
    if l_len == 0 and r_len == 0 and "  " not in s_str:
        return html.escape(s_str)

    dot = '<span class="dc-ws-dot">·</span>'

    # If the string is all spaces
    if l_len == len(s_str):
        return dot * l_len

    leading = dot * l_len
    trailing = dot * r_len if r_len > 0 else ""
    middle = s_str[l_len : len(s_str) - r_len] if r_len > 0 else s_str[l_len:]

    # In middle, only multiple consecutive spaces (2 or more) get marked
    def _replace_multi_spaces(m: re.Match) -> str:
        return dot * len(m.group(0))

    middle_escaped = html.escape(middle)
    middle_formatted = re.sub(r" {2,}", _replace_multi_spaces, middle_escaped)

    return f"{leading}{middle_formatted}{trailing}"


def render_data_table(
    df: pd.DataFrame,
    title: Optional[str] = None,
    max_rows: int = 50,
    status_col: Optional[str] = None,
    invalid_mask_col: Optional[str] = None,
    total_rows: Optional[int] = None,
) -> None:
    """
    Renders a full-width enterprise table following strict SaaS table rules:
    - Single white container: 1px slate-200 border, 12px radius, no outer tinted wrapper.
    - Never clipped: overflow-x: auto with min-width: max-content on table.
    - Inner padding 12px 16px, 44px row height.
    - Horizontal 1px dividers only (NO vertical gridlines).
    - Sticky header on very light slate fill (#F8FAFC) with 12px medium slate-600 text.
    - Numbers right-aligned in tabular numerals, text left-aligned.
    - Status column uses badge().
    - Blank values display as '(empty)' in muted text.
    - Leading/trailing whitespace rendered visible via middle-dots.
    - Footer inside container: 'Showing X of Y rows, Z columns' with 'Show all rows' ghost button.
    """
    if df is None or df.empty:
        render_html('<div class="dc-table-empty" style="padding: 24px; text-align: center; color: #64748B; background: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px;">No records to display.</div>')
        return

    actual_total = total_rows if total_rows is not None else len(df)
    display_df = df.head(max_rows)
    num_cols = len(display_df.columns)

    title_markup = f'<div class="dc-table-title">{html.escape(title)}</div>' if title else ""

    # Build Header — align header to match cell alignment (true numeric columns right, text left)
    _numeric_cols = {
        col for col in display_df.columns
        if pd.api.types.is_numeric_dtype(display_df[col])
    }
    headers = []
    for col in display_df.columns:
        _cls = "dc-th dc-th-num" if col in _numeric_cols else "dc-th"
        headers.append(f'<th class="{_cls}">{html.escape(str(col))}</th>')
    header_row = f'<tr>{"".join(headers)}</tr>'

    # Build Body Rows
    body_rows = []
    for _, row in display_df.iterrows():
        is_invalid = False
        if invalid_mask_col and invalid_mask_col in row:
            is_invalid = bool(row[invalid_mask_col])

        row_cls = "dc-tr-invalid" if is_invalid else "dc-tr"
        cells = []
        for col_name, val in row.items():
            # Check if this is the status column
            if status_col and col_name == status_col:
                s_val = str(val).strip()
                b_type = "valid" if any(k in s_val.lower() for k in ("valid", "clean", "ok", "pass")) else (
                    "invalid" if any(k in s_val.lower() for k in ("invalid", "fail", "error")) else (
                        "warning" if any(k in s_val.lower() for k in ("ambiguous", "review", "warn")) else "neutral"
                    )
                )
                cell_val = render_badge(b_type, s_val, as_string=True)
                cells.append(f'<td class="dc-td dc-td-status">{cell_val}</td>')
                continue

            if val is None or pd.isna(val) or str(val).strip() == "":
                cells.append('<td class="dc-td dc-td-empty"><span class="dc-empty-val">(empty)</span></td>')
            elif isinstance(val, (int, float)):
                cells.append(f'<td class="dc-td dc-td-num">{val:,}</td>')
            else:
                s_str = str(val)
                # Show whitespace dots only where whitespace actually exists
                # (compare the raw value with its TRIM — never add an extra marker)
                if s_str != s_str.strip() or "  " in s_str:
                    s_disp = _format_cell_whitespace(s_str)
                    cells.append(f'<td class="dc-td dc-td-ws">{s_disp}</td>')
                else:
                    cells.append(f'<td class="dc-td">{html.escape(s_str)}</td>')

        body_rows.append(f'<tr class="{row_cls}">{"".join(cells)}</tr>')

    show_all_btn_markup = (
        '<button type="button" class="dc-table-show-all-btn">Show all rows</button>'
        if actual_total > len(display_df)
        else ""
    )

    footer_markup = f"""
    <div class="dc-table-footer">
        <span>Showing {len(display_df):,} of {actual_total:,} rows, {num_cols} columns</span>
        {show_all_btn_markup}
    </div>
    """

    table_html = f"""
    <div class="dc-table-container">
        {title_markup}
        <div class="dc-table-scroll">
            <table class="dc-table">
                <thead>{header_row}</thead>
                <tbody>{"".join(body_rows)}</tbody>
            </table>
        </div>
        {footer_markup}
    </div>
    """
    render_html(table_html)


# Alias render_saas_table to render_data_table for backwards compatibility
render_saas_table = render_data_table


# ─────────────────────────────────────────────────────────────
# 9. Breadcrumb Navigation Bar (Non-Truncating SaaS Standard)
# ─────────────────────────────────────────────────────────────

def render_saas_breadcrumb(
    items: List[Dict[str, str]],
) -> None:
    """
    Renders a modern, single-line breadcrumb navigation bar:
    Database / Table / Module. Full values with title tooltips; never broken with '...'.
    Each item: {'label': str, 'icon': str, 'active': bool, 'url': Optional[str]}
    """
    crumb_elements = []
    sep_icon = get_icon_svg("chevron_right", size=14, stroke_width=2.0)

    for idx, item in enumerate(items):
        icon_svg = get_icon_svg(item.get("icon", "database"), size=15, stroke_width=1.75)
        label = item["label"]
        active = item.get("active", False)
        url = item.get("url")

        if active:
            crumb_elements.append(
                f'<span class="dc-bc-item active" title="{html.escape(label)}">'
                f'<span class="dc-bc-icon">{icon_svg}</span>'
                f'<span class="dc-bc-label">{html.escape(label)}</span>'
                f'</span>'
            )
        elif url:
            crumb_elements.append(
                f'<a href="{html.escape(url)}" target="_self" class="dc-bc-item" title="{html.escape(label)}">'
                f'<span class="dc-bc-icon">{icon_svg}</span>'
                f'<span class="dc-bc-label">{html.escape(label)}</span>'
                f'</a>'
            )
        else:
            crumb_elements.append(
                f'<span class="dc-bc-item" title="{html.escape(label)}">'
                f'<span class="dc-bc-icon">{icon_svg}</span>'
                f'<span class="dc-bc-label">{html.escape(label)}</span>'
                f'</span>'
            )

        if idx < len(items) - 1:
            crumb_elements.append(f'<span class="dc-bc-sep">{sep_icon}</span>')

    content = f"""
    <nav class="dc-breadcrumb" aria-label="Breadcrumb">
        {''.join(crumb_elements)}
    </nav>
    """
    render_html(content)


# ─────────────────────────────────────────────────────────────
# 10. Module Header with Back Navigation & Sandbox Pill
# ─────────────────────────────────────────────────────────────

def render_module_header(
    title: str,
    subtitle: Optional[str] = None,
    badge_text: Optional[str] = "Safe Sandbox",
    badge_type: str = "brand",
    back_label: str = "Back to Cleaning Hub",
    back_key: Optional[str] = None,
) -> bool:
    """
    Renders a dedicated, modern SaaS module header with:
    - Back button leading to the Cleaning Hub
    - Module title (20px bold) and subtitle
    - Status badge ('Safe Sandbox' / 'Isolated Copy')
    - Subtle bottom separator
    Returns True if the back button was clicked by the user.
    """
    clicked = False

    col_back, col_badge = st.columns([1.5, 3.5], vertical_alignment="center")
    with col_back:
        k = back_key or f"btn_back_mod_{title.lower().replace(' ', '_')}"
        if st.button(f"← {back_label}", key=k, type="secondary"):
            clicked = True
    with col_badge:
        if badge_text:
            badge_html = render_badge(badge_type, badge_text, as_string=True)
            render_html(
                f'<div style="display:flex; justify-content:flex-end; align-items:center;">{badge_html}</div>'
            )

    sub_desc = f'<div class="dc-module-desc">{html.escape(subtitle)}</div>' if subtitle else ""
    render_html(
        f"""
        <div style="margin-top: 6px; margin-bottom: 16px;">
            <div class="dc-module-title">{html.escape(title)}</div>
            {sub_desc}
        </div>
        """
    )
    return clicked
