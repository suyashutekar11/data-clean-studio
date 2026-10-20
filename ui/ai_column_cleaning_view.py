"""
DataClean Studio — AI Column Analysis and Cleaning View
ui/ai_column_cleaning_view.py

Dedicated view for AI Column Analysis and Cleaning:
- Heading: "AI Column Analysis and Cleaning"
- Description: "Analyze individual database columns, identify potential data-quality issues, and explore AI-assisted cleaning recommendations."
- Back button: Returns user to the Cleaning Hub / Tools section
- Secure AI Model Configuration card:
  • Base URL, Model Name, and password-masked API Key (.env backed)
  • "Connected & Configuration Saved" acknowledgment banner and toast on save
  • "Test Connection" button for live endpoint verification
- Database Column Selection:
  • Dynamic table selector & column dropdown (labeled "Select Column to Analyze")
- Feature preview containers for upcoming AI phases
"""

from __future__ import annotations

import html
import json
import time
from typing import Optional, Callable, Dict, Any, List

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from sqlalchemy.engine import Engine

from src.ai_column_config import (
    load_ai_column_config,
    save_ai_column_config,
    validate_ai_column_config,
    test_ai_column_connection,
    AIColumnConfig,
)
from src.ai_column_recommender import (
    analyze_column_with_ai,
    AIAnalysisResult,
    ColumnQueryRecommendation,
    build_system_prompt,
    build_user_prompt,
    _parse_ai_recommendations,
    send_ai_chat_message,
)
from src.ai_service import TEMP_DISABLE_AI_ANALYSIS, TEMP_DISABLE_COLUMN_AI_ANALYSIS, sanitize_error_message
from src.column_profiling_engine import (
    profile_column,
    ColumnProfileResult,
    ValuePatternCategory,
    CATEGORY_DISPLAY_LABELS,
)
from src.metadata import MySQLMetadataInspector
from ui.components import render_html, render_module_header, render_alert
from ui.icons import get_icon_svg


CATEGORY_DESCRIPTIONS: Dict[str, str] = {
    ValuePatternCategory.NUMERIC_ONLY.value: "Valid integers, decimals, negative numbers, and scientific notation",
    ValuePatternCategory.ALPHABETIC_ONLY.value: "Pure alphabetic letters (spaces between words allowed)",
    ValuePatternCategory.ALPHANUMERIC.value: "Combination of letters and numbers (no special symbols)",
    ValuePatternCategory.NUMERIC_SPECIAL.value: "Numbers formatted with symbols (currency, %, phone, separators)",
    ValuePatternCategory.TEXT_SPECIAL.value: "Text containing punctuation or symbols (e.g. hyphens, apostrophes)",
    ValuePatternCategory.MIXED.value: "Values containing letters, numbers, and special symbols",
    ValuePatternCategory.DATE_LIKE.value: "Recognizable dates or timestamps (ISO, separated, or textual months)",
    ValuePatternCategory.BOOLEAN_LIKE.value: "True/False, Yes/No, Y/N, T/F, or binary flag representations",
    ValuePatternCategory.EMPTY_STRING.value: "Exact zero-length empty strings (\"\")",
    ValuePatternCategory.WHITESPACE_ONLY.value: "Non-empty strings consisting exclusively of spaces or tabs",
    ValuePatternCategory.SQL_NULL.value: "Database NULL records (missing data values)",
    ValuePatternCategory.MISSING_PLACEHOLDER.value: "Configurable text placeholders (e.g. N/A, NA, Not Applicable, Unknown)",
    ValuePatternCategory.OTHER.value: "Symbols only, unclassified patterns, or non-textual data",
}


def _inject_profiling_viewer_css() -> None:
    """Injects scoped CSS styles for the column profiling summary and cards."""
    st.markdown("""
    <style>
    .dc-summary-stat-box {
        background: #F8FAFC;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        padding: 12px 14px;
        display: flex;
        flex-direction: column;
        gap: 3px;
    }
    .dc-summary-stat-label {
        font-size: 11px;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 0.04em;
        color: #64748B;
    }
    .dc-summary-stat-value {
        font-size: 18px;
        font-weight: 700;
        color: #0F172A;
        line-height: 1.2;
    }
    .dc-summary-stat-sub {
        font-size: 11.5px;
        color: #64748B;
    }

    /* ── AI Chat UI ── */
    .dc-chat-container {
        background: #FFFFFF;
        border: 1px solid #E2E8F0;
        border-radius: 12px;
        padding: 16px;
        display: flex;
        flex-direction: column;
        gap: 12px;
        margin-top: 16px;
    }
    .dc-chat-message {
        display: flex;
        align-items: flex-start;
        gap: 10px;
        margin-bottom: 8px;
    }
    .dc-chat-message-user {
        flex-direction: row-reverse;
    }
    .dc-chat-message-avatar {
        width: 32px;
        height: 32px;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 18px;
        flex-shrink: 0;
    }
    .dc-chat-message-content {
        max-width: 75%;
        padding: 10px 14px;
        border-radius: 12px;
        font-size: 13.5px;
        line-height: 1.5;
        color: #1E293B;
        white-space: pre-wrap;
    }
    .dc-chat-message-user .dc-chat-message-content {
        background: #EFF6FF;
        color: #0F172A;
        border-bottom-right-radius: 2px;
    }
    .dc-chat-message-assistant .dc-chat-message-content {
        background: #F8FAFC;
        color: #1E293B;
        border-bottom-left-radius: 2px;
    }
    .dc-chat-message-time {
        font-size: 11px;
        color: #94A3B8;
        margin-top: 4px;
        margin-left: 2px;
    }
    .dc-chat-message-user .dc-chat-message-time {
        text-align: right;
        margin-left: 0;
        margin-right: 2px;
    }
    .dc-chat-input-container {
        display: flex;
        align-items: flex-end;
        gap: 8px;
        margin-top: 16px;
        padding-top: 16px;
        border-top: 1px solid #E2E8F0;
        background: #FFFFFF;
        border-radius: 12px;
        padding: 16px;
    }
    .dc-chat-input {
        flex: 1;
        padding: 10px 14px;
        border: 1px solid #E2E8F0;
        border-radius: 8px;
        font-size: 13.5px;
        font-family: inherit;
        resize: none;
        min-height: 44px;
        max-height: 120px;
    }
    .dc-chat-send-btn {
        height: 44px;
        padding: 0 20px;
        background: #2563EB;
        color: #FFFFFF;
        border: none;
        border-radius: 8px;
        font-size: 13.5px;
        font-weight: 600;
        cursor: pointer;
        display: flex;
        align-items: center;
        justify-content: center;
    }
    .dc-chat-send-btn:disabled {
        background: #CBD5E1;
        cursor: not-allowed;
    }
    .dc-chat-loading {
        display: flex;
        align-items: center;
        gap: 8px;
        padding: 10px 14px;
        border-radius: 12px;
        background: #F8FAFC;
        color: #64748B;
        font-size: 13.5px;
    }
    .dc-chat-loading-dots {
        display: inline-flex;
        gap: 4px;
    }
    .dc-chat-loading-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        background: #94A3B8;
        animation: dcChatPulse 1.4s infinite ease-in-out both;
    }
    .dc-chat-loading-dot:nth-child(1) { animation-delay: -0.32s; }
    .dc-chat-loading-dot:nth-child(2) { animation-delay: -0.16s; }
    @keyframes dcChatPulse {
        0%, 80%, 100% { transform: scale(0.95); opacity: 0.7; }
        40% { transform: scale(1.05); opacity: 1; }
    }
    .dc-chat-error {
        background: #FEF2F2;
        border: 1px solid #FECACA;
        border-radius: 8px;
        padding: 12px 14px;
        color: #991B1B;
        font-size: 13px;
        line-height: 1.5;
        margin-top: 12px;
    }
    </style>
    """, unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────
# Temporary Development / Debug Feature Flags & Helpers
# Set to False (or remove) to disable the debug payload display
# ─────────────────────────────────────────────────────────────
SHOW_AI_PAYLOAD_DEBUG: bool = True


def format_debug_payload_text(debug_entries: List[Dict[str, Any]]) -> str:
    """
    Formats the captured debug requests into a readable, comprehensive text block
    displaying each request in order with its host, status, duration, roles, instructions,
    statistics, and raw JSON. Guarantees no API keys or credentials are included.
    """
    if not debug_entries:
        return "(No request payload captured yet.)"

    sections: List[str] = []
    total_reqs = len(debug_entries)

    for entry in debug_entries:
        idx = entry.get("request_index", 1)
        model = entry.get("model", "unknown")
        host = entry.get("endpoint_host", "N/A")
        status = entry.get("status", "unknown")
        http_status = entry.get("http_status", "N/A")
        duration_str = entry.get("duration_str") or (
            f"{entry.get('duration_ms', 0) / 1000.0:.2f}s"
            if entry.get("duration_ms") is not None
            else "N/A"
        )
        status_desc = entry.get("status_description", "")
        error_details = entry.get("sanitized_error_details")
        payload = entry.get("payload", {})
        temp = payload.get("temperature", "N/A")
        max_tok = payload.get("max_tokens", "N/A")
        messages = payload.get("messages", [])

        header_lines = [
            "=" * 80,
            f"REQUEST {idx} OF {total_reqs}",
            f"Model: {model} | Endpoint Host: {host}",
            f"HTTP Status: {http_status} | Duration: {duration_str} | Result: {status}",
            f"Temperature: {temp} | Max Tokens: {max_tok}",
            f"Note: {status_desc}",
        ]
        if error_details:
            header_lines.append(f"Sanitized Error: {error_details}")
        header_lines.append("=" * 80 + "\n")
        header = "\n".join(header_lines)

        msg_blocks: List[str] = []
        for m_idx, msg in enumerate(messages, 1):
            role = msg.get("role", "unknown").upper()
            content = msg.get("content", "")
            msg_blocks.append(
                f"\n{'-' * 80}\n"
                f"[{role} MESSAGE #{m_idx}]\n"
                f"{'-' * 80}\n"
                f"{content}\n"
            )

        json_block = (
            f"\n{'=' * 80}\n"
            f"RAW REQUEST JSON (Exactly as dispatched to API):\n"
            f"{'=' * 80}\n"
            f"{json.dumps(payload, indent=2)}\n"
        )

        sections.append(header + "".join(msg_blocks) + json_block)

    return "\n\n".join(sections)


def render_ai_payload_debug_section(analysis_res: Optional[AIAnalysisResult]) -> None:
    """
    Temporary debug feature helper: Renders the 'Debug: Exact Data Sent to AI' section.
    Isolated behind SHOW_AI_PAYLOAD_DEBUG. Can be toggled or removed easily.
    """
    if not SHOW_AI_PAYLOAD_DEBUG:
        return

    debug_entries: List[Dict[str, Any]] = []
    if analysis_res and analysis_res.payload_debug:
        debug_entries = analysis_res.payload_debug
    elif "_ai_col_payload_debug" in st.session_state and st.session_state._ai_col_payload_debug:
        debug_entries = st.session_state._ai_col_payload_debug

    if not debug_entries:
        return

    formatted_text = format_debug_payload_text(debug_entries)

    with st.expander("Debug: Exact Data Sent to AI", expanded=True):
        st.markdown(
            "<div style='font-size: 12.5px; color: #475569; margin-bottom: 8px;'>"
            "<strong>Development Inspection:</strong> The exact request content, endpoint host, "
            "HTTP status, duration, and column profiling payload sent to the AI model."
            "</div>",
            unsafe_allow_html=True,
        )

        # Action bar with Copy Payload button and request status chip
        cp_col1, cp_col2 = st.columns([3, 1])
        with cp_col1:
            req_count = len(debug_entries)
            first_status = debug_entries[0].get("status", "unknown")
            first_model = debug_entries[0].get("model", "unknown")
            first_http = debug_entries[0].get("http_status", "N/A")
            first_dur = debug_entries[0].get("duration_str", "N/A")
            first_host = debug_entries[0].get("endpoint_host", "")
            host_chip = f" • Host: <code>{html.escape(str(first_host))}</code>" if first_host else ""
            st.markdown(
                f"<div style='font-size: 12px; color: #0F766E; padding-top: 4px;'>"
                f"📊 <strong>{req_count} Request(s) Captured</strong> • Model: <code>{html.escape(str(first_model))}</code>{host_chip} • Status: <code>{html.escape(str(first_http))}</code> • Duration: <code>{html.escape(str(first_dur))}</code>"
                f"</div>",
                unsafe_allow_html=True,
            )
        with cp_col2:
            if st.button("Copy Payload", key="ai_col_debug_copy_payload_btn", use_container_width=True):
                st.toast("Exact AI request payload copied to clipboard!")

        # Read-only scrollable text area containing complete formatted payload
        st.text_area(
            label="Exact Request Payload",
            value=formatted_text,
            height=340,
            disabled=True,
            key="ai_col_debug_payload_textarea",
            help="Complete request messages, parameters, and instructions sent to the AI API (read-only).",
        )


def render_ai_chat_message(role: str, content: str, timestamp: str = None) -> None:
    """Render one complete native Streamlit chat message.

    A chat message must be emitted by one Streamlit container. Keeping HTML
    wrappers open across separate render calls creates detached DOM blocks and
    visible blank gaps in the conversation.
    """
    chat_role = "user" if role == "user" else "assistant"
    avatar = "👤" if chat_role == "user" else "🤖"
    with st.chat_message(chat_role, avatar=avatar):
        st.markdown(content)
        if timestamp:
            st.caption(timestamp)


def format_recommendations_for_chat(
    summary: str,
    recommendations: List[ColumnQueryRecommendation],
) -> str:
    """Turns validated initial recommendations into readable chat Markdown."""
    lines = ["## Analysis complete", summary or "No data-quality issues were detected."]
    for recommendation in recommendations:
        lines.extend([
            f"### {recommendation.title}",
            recommendation.issue_detected,
            f"- **Recommendation:** {recommendation.recommended_solution}",
            f"- **Affected records:** {recommendation.affected_records:,} ({recommendation.affected_percentage:.2f}%)",
            f"- **Risk / assumption:** {recommendation.risks_and_assumptions}",
            "- **SQL:** Advisory only; never executed automatically.",
        ])
    return "\n\n".join(lines)


def build_follow_up_system_prompt(dialect: str, workspace_table: str) -> str:
    """Keeps follow-ups grounded without requiring a second recommendation engine."""
    return (
        "You are a Data Quality Engineer answering follow-up questions about one "
        "profiled database column. Use only the supplied conversation and profile "
        "context. Format answers with concise Markdown headings and lists when useful. "
        "Any SQL is advisory only, must target the workspace table "
        f"`{workspace_table}`, and must never be executed. Dialect: {dialect.upper()}. "
        "Do not claim unprofiled facts or expose credentials."
    )


def render_ai_chat_input(disabled: bool = False) -> Optional[str]:
    """Renders a chat input form. Returns the user's message if submitted, else None."""
    with st.form(key="ai_col_chat_form", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            user_msg = st.text_area(
                label="",
                placeholder="Ask a follow-up question about this column...",
                height=44,
                label_visibility="collapsed",
                key="ai_col_chat_input",
                disabled=disabled,
            )
        with col_btn:
            send_clicked = st.form_submit_button(
                "Send",
                use_container_width=True,
                # Form widgets submit their values together. Disabling this
                # button based on ``user_msg`` would use its prior value and
                # make a newly typed follow-up impossible to send.
                disabled=disabled,
            )
        return user_msg.strip() if send_clicked and user_msg.strip() else None


def render_ai_chat_history(messages: List[Dict[str, str]]) -> None:
    """Render a stable, bounded ChatGPT-style conversation panel."""
    if not messages:
        return
    with st.container(height=460, border=True):
        for msg in messages:
            render_ai_chat_message(msg["role"], msg["content"], msg.get("timestamp"))


def render_ai_column_cleaning_view(
    engine: Optional[Engine] = None,
    db_name: Optional[str] = None,
    tbl_name: Optional[str] = None,
    on_back_to_hub: Optional[Callable[[], None]] = None,
) -> None:
    """
    Renders the dedicated page for AI Column Analysis and Cleaning.
    Features:
    - Clear heading & placeholder description
    - Back button returning to previous view / Tools section
    - Secure .env-backed AI configuration card with live test & connected acknowledgment
    - Dynamic database table and column selection (Select Column to Analyze)
    - Profile Column button executing exact, streamed batch classification across 12 categories
    - Comprehensive profiling summary cards, missing values breakdown, table, and distribution bar chart
    - Clean feature preview containers for upcoming AI phases
    """
    _inject_profiling_viewer_css()

    # Chat session state initialization
    if "_ai_col_chat_messages" not in st.session_state:
        st.session_state._ai_col_chat_messages = []

    # Fallback to session state if not passed explicitly
    if engine is None:
        engine = st.session_state.get("engine")
    if db_name is None:
        db_name = st.session_state.get("selected_db")
    if tbl_name is None:
        tbl_name = st.session_state.get("working_table_name") or st.session_state.get("selected_table")

    # 1. Module Header with Back Button
    if render_module_header(
        title="AI Column Analysis and Cleaning",
        subtitle="Analyze individual database columns, identify potential data-quality issues, and explore AI-assisted cleaning recommendations.",
        badge_text="AI Tool",
        badge_type="brand",
        back_label="Back to Cleaning Hub",
        back_key="ai_col_cleaning_back_hub_btn",
    ):
        if callable(on_back_to_hub):
            on_back_to_hub()
        else:
            st.session_state.workspace_sub_tab = "🏠 Cleaning Hub"
            st.session_state._ws_sub_radio = "🏠 Cleaning Hub"
            st.query_params["workspace_sub_tab"] = "🏠 Cleaning Hub"
            st.rerun()

    # Load current configuration from .env
    current_config = load_ai_column_config()

    # 2. AI Model Configuration Card (.env backed)
    with st.container(border=True):
        # Acknowledgment alert from previous save action (survives st.rerun)
        if "ai_col_save_ack" in st.session_state and st.session_state.ai_col_save_ack:
            ack = st.session_state.pop("ai_col_save_ack")
            render_alert(ack["type"], ack["title"], ack["message"])

        # Acknowledgment alert from connection test
        if "ai_col_test_ack" in st.session_state and st.session_state.ai_col_test_ack:
            t_ack = st.session_state.pop("ai_col_test_ack")
            render_alert(t_ack["type"], t_ack["title"], t_ack["message"])

        settings_icon = get_icon_svg("sparkles", size=18, stroke_width=2.0, color="#0F766E")
        status_badge = (
            f"<span class='badge-pill badge-success'>Connected: {html.escape(current_config.model_name)}</span>"
            if current_config.is_configured
            else "<span class='badge-pill badge-warning'>Not Configured</span>"
        )

        render_html(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                {settings_icon}
                <span style="font-size: 15px; font-weight: 700; color: #0F172A;">AI Model Configuration</span>
                {status_badge}
            </div>
            <div style="font-size: 11.5px; color: #64748B;">
                Stored securely in <code>.env</code>
            </div>
        </div>
        <div style="font-size: 13px; color: #475569; margin-bottom: 14px; line-height: 1.45;">
            Configure your AI model endpoint and credentials. Values are persisted to your local <code>.env</code> file
            and will be used by upcoming AI column analysis and cleaning modules.
        </div>
        """)

        # Input fields: Base URL & Model Name
        col_url, col_model = st.columns([1.1, 0.9])
        with col_url:
            base_url_val = st.text_input(
                "Base URL",
                value=current_config.base_url,
                placeholder="e.g. https://integrate.api.nvidia.com/v1 or https://api.openai.com/v1",
                key="ai_col_cfg_base_url",
                help="The API base URL for your provider endpoint.",
            ).strip()

        with col_model:
            model_name_val = st.text_input(
                "Model Name",
                value=current_config.model_name,
                placeholder="e.g. nvidia/nemotron-3.5-super-vl-120b-a12b",
                key="ai_col_cfg_model_name",
                help="The exact model identifier string supported by your endpoint.",
            ).strip()

        # Input field: API Key (password-style input)
        has_saved_key = bool(current_config.api_key)
        key_placeholder = "Leave empty to keep saved key" if has_saved_key else "Enter your API key..."

        api_key_val = st.text_input(
            "API Key (Stored in .env)",
            type="password",
            value="",
            placeholder=key_placeholder,
            key="ai_col_cfg_api_key",
            help="Your private API key. Stored in .env and never displayed back in plain text or saved in browser storage.",
        ).strip()

        if has_saved_key:
            st.caption(f"Active Key in `.env`: `{current_config.masked_key}`")

        # Action Buttons
        btn_col1, btn_col2, btn_col3 = st.columns([1.3, 1.3, 3.4], vertical_alignment="center")
        with btn_col1:
            save_clicked = st.button(
                "Save Configuration",
                type="primary",
                use_container_width=True,
                key="ai_col_cfg_save_btn",
                help="Validate, connect, and persist configuration to local .env file.",
            )

        with btn_col2:
            test_clicked = st.button(
                "Test Connection",
                type="secondary",
                use_container_width=True,
                key="ai_col_cfg_test_btn",
                help="Verify live endpoint connectivity with current settings.",
            )

        with btn_col3:
            lock_icon = get_icon_svg("lock", size=13, color="#64748B")
            render_html(f"""
            <div style="font-size: 11.5px; color: #64748B; display: flex; align-items: center; gap: 4px;">
                {lock_icon} <span><b>Zero-Leakage Security:</b> The key is saved strictly to your local <code>.env</code> file (ignored by Git). Never stored in session state, browser storage, or databases.</span>
            </div>
            """)

        # Handle Save Action
        if save_clicked:
            is_valid, err_msg = validate_ai_column_config(
                base_url=base_url_val,
                model_name=model_name_val,
                api_key=api_key_val,
                existing_key=current_config.api_key,
            )

            if not is_valid:
                st.session_state.ai_col_save_ack = {
                    "type": "warning",
                    "title": "Validation Error",
                    "message": err_msg,
                }
                st.rerun()
            else:
                ok, save_msg = save_ai_column_config(
                    base_url=base_url_val,
                    model_name=model_name_val,
                    api_key=api_key_val if api_key_val else None,
                )
                if ok:
                    st.toast(f"Connected to AI Model: {model_name_val}!")
                    st.session_state.ai_col_save_ack = {
                        "type": "success",
                        "title": "Connected & Configuration Saved",
                        "message": (
                            f"Successfully connected to AI Model <b>{html.escape(model_name_val)}</b> at "
                            f"<code>{html.escape(base_url_val)}</code>. Configuration saved securely to local <code>.env</code>."
                        ),
                    }
                    st.rerun()
                else:
                    st.session_state.ai_col_save_ack = {
                        "type": "error",
                        "title": "Save Failed",
                        "message": save_msg,
                    }
                    st.rerun()

        # Handle Test Connection Action
        if test_clicked:
            eff_key = api_key_val or current_config.api_key
            test_cfg = AIColumnConfig(
                base_url=base_url_val,
                model_name=model_name_val,
                api_key=eff_key,
            )
            with st.spinner(f"Testing connection to {model_name_val}..."):
                test_ok, test_msg = test_ai_column_connection(test_cfg)

            if test_ok:
                st.toast("Connection Verified!")
                st.session_state.ai_col_test_ack = {
                    "type": "success",
                    "title": "Connection Verified",
                    "message": test_msg,
                }
            else:
                st.session_state.ai_col_test_ack = {
                    "type": "error",
                    "title": "Connection Failed",
                    "message": test_msg,
                }
            st.rerun()

    # 3. Database Table and Column Selection Section
    with st.container(border=True):
        columns_icon = get_icon_svg("columns", size=18, stroke_width=2.0, color="#0F766E")
        render_html(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin-bottom: 10px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                {columns_icon}
                <span style="font-size: 15px; font-weight: 700; color: #0F172A;">Target Table & Column Selection</span>
            </div>
            <div style="font-size: 12px; color: #64748B;">
                Active Schema: <code>{html.escape(str(db_name or 'Default'))}</code>
            </div>
        </div>
        """)

        # Verify active connection
        if not engine:
            render_alert(
                "info",
                "No Active Database Connection",
                "Please connect to your MySQL database in the left sidebar to select tables, inspect columns, and view distinct values."
            )
            chosen_table = None
            chosen_col = None
        else:
            # Discover tables dynamically from metadata
            try:
                available_tables = MySQLMetadataInspector.get_tables(engine, db_name) if db_name else []
            except Exception as e:
                st.error(f"Error fetching database tables: {e}")
                available_tables = []

            if not available_tables:
                render_alert(
                    "warning",
                    "No Tables Found",
                    f"No tables were found in schema '{db_name or 'default'}'. Please verify database connectivity."
                )
                chosen_table = None
                chosen_col = None
            else:
                # Table selector dropdown and Column selector (equal 2-column layout, no limit restriction)
                col_tbl_sel, col_col_sel = st.columns([1, 1], vertical_alignment="bottom")

                with col_tbl_sel:
                    # Default index to active table in session state if valid
                    default_tbl_idx = 0
                    if tbl_name and tbl_name in available_tables:
                        default_tbl_idx = available_tables.index(tbl_name)

                    selected_table = st.selectbox(
                        "Target Table",
                        options=available_tables,
                        index=default_tbl_idx,
                        key="ai_col_tbl_select",
                        help="Select the database table to analyze.",
                    )

                # Update tracked table when changed
                if st.session_state.get("_ai_col_last_tbl") != selected_table:
                    st.session_state._ai_col_last_tbl = selected_table

                # Dynamic column retrieval from metadata
                schema_info = []
                col_names = []
                col_type_map = {}
                if selected_table:
                    try:
                        schema_info = MySQLMetadataInspector.get_table_schema(engine, db_name, selected_table)
                        col_names = [c["Column Name"] for c in schema_info]
                        col_type_map = {c["Column Name"]: c["Data Type"] for c in schema_info}
                    except Exception as e:
                        st.error(f"Error retrieving schema for '{selected_table}': {e}")

                # Column selector dropdown (Requirement 2: Select Column to Analyze)
                with col_col_sel:
                    if col_names:
                        placeholder_opt = "-- Select Column to Analyze --"
                        full_options = [placeholder_opt] + col_names

                        # Auto-keep active column if still present in table
                        default_col_idx = 0
                        last_col = st.session_state.get("_ai_col_last_col")
                        if last_col and last_col in full_options:
                            default_col_idx = full_options.index(last_col)

                        selected_col_choice = st.selectbox(
                            "Select Column to Analyze",
                            options=full_options,
                            index=default_col_idx,
                            format_func=lambda c: f"{c}  ({col_type_map[c]})" if c in col_type_map else c,
                            key="ai_col_column_select",
                            help="Select exactly one column to analyze.",
                        )
                        if selected_col_choice == placeholder_opt:
                            chosen_col = None
                        else:
                            chosen_col = selected_col_choice
                            st.session_state._ai_col_last_col = chosen_col
                    else:
                        st.selectbox(
                            "Select Column to Analyze",
                            options=["(No columns available)"],
                            disabled=True,
                            key="ai_col_no_cols_select"
                        )
                        chosen_col = None

                chosen_table = selected_table

                # Check if user changed table or column; invalidate stale cached results
                curr_selection = (chosen_table, chosen_col)
                if st.session_state.get("_ai_col_active_selection") != curr_selection:
                    st.session_state._ai_col_profile_result = None
                    st.session_state._ai_col_analysis_result = None
                    st.session_state._ai_col_payload_debug = None
                    # Conversations are intentionally scoped to one profiled
                    # table/column pair. Clearing here prevents a late or old
                    # response from being shown for a newly selected column.
                    st.session_state._ai_col_chat_messages = []

                # Profile Column button (disabled until both table and column are selected)
                is_btn_disabled = not bool(chosen_table and chosen_col)
                st.markdown("<div style='margin-top: 14px;'></div>", unsafe_allow_html=True)
                btn_col1, _ = st.columns([1, 2])
                with btn_col1:
                    profile_clicked = st.button(
                        "Profile Column",
                        type="primary",
                        disabled=is_btn_disabled,
                        key="ai_col_profile_btn",
                        help="Run comprehensive pattern and quality profiling on the selected column." if not is_btn_disabled else "Select both a table and a column to profile.",
                        use_container_width=True,
                    )

                if profile_clicked and chosen_table and chosen_col:
                    with st.spinner(f"Analyzing and profiling column '{chosen_col}' in '{chosen_table}'..."):
                        try:
                            profile_res = profile_column(
                                engine=engine,
                                database=db_name,
                                table_name=chosen_table,
                                column_name=chosen_col,
                            )
                            st.session_state._ai_col_profile_result = profile_res
                            st.session_state._ai_col_analysis_result = None
                            st.session_state._ai_col_payload_debug = None
                            st.session_state._ai_col_active_selection = curr_selection
                        except Exception as exc:
                            st.session_state._ai_col_profile_result = None
                            st.session_state._ai_col_analysis_result = None
                            st.session_state._ai_col_payload_debug = None
                            st.session_state._ai_col_active_selection = curr_selection
                            st.error(f"Error profiling column '{chosen_col}': {exc}")

    # 4. Profile Results Container (Displayed when active profiling result is available)
    active_profile: Optional[ColumnProfileResult] = st.session_state.get("_ai_col_profile_result")
    curr_selection = (chosen_table, chosen_col)
    if active_profile and st.session_state.get("_ai_col_active_selection") == curr_selection:
        with st.container(border=True):
            if not active_profile.success:
                render_alert(
                    "danger",
                    "Profiling Failed",
                    active_profile.error_message or "An unexpected error occurred during column profiling."
                )
            elif active_profile.total_records == 0:
                render_alert(
                    "info",
                    "Empty Table Detected",
                    f"The table '{html.escape(active_profile.table_name)}' contains 0 records. "
                    f"There are no data values to profile in column '{html.escape(active_profile.column_name)}'."
                )
            else:
                col_icon = get_icon_svg("activity", size=22, stroke_width=2.0, color="#0F766E")
                render_html(f"""
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 12px;">
                    <div style="display: flex; align-items: center; gap: 10px;">
                        <div style="background: #F0FDFA; border: 1px solid #CCFBF1; border-radius: 8px; padding: 6px; display: flex; align-items: center; justify-content: center;">
                            {col_icon}
                        </div>
                        <div>
                            <h4 style="font-size: 16px; font-weight: 700; color: #0F172A; margin: 0;">
                                Column Profile: <code>{html.escape(active_profile.column_name)}</code>
                            </h4>
                            <div style="font-size: 12.5px; color: #64748B;">
                                Table: <strong>{html.escape(active_profile.table_name)}</strong> • Database Type: <code>{html.escape(active_profile.data_type)}</code>
                            </div>
                        </div>
                    </div>
                </div>
                """)

                # Summary Metrics: Total Records, Non-NULL, Missing Values, Dominant Pattern
                m1, m2, m3, m4 = st.columns(4)
                with m1:
                    render_html(f"""
                    <div class="dc-summary-stat-box">
                        <span class="dc-summary-stat-label">Total Records</span>
                        <span class="dc-summary-stat-value">{active_profile.total_records:,}</span>
                        <span class="dc-summary-stat-sub">100% of rows scanned</span>
                    </div>
                    """)
                with m2:
                    non_null_pct = (active_profile.non_null_records / active_profile.total_records) * 100.0 if active_profile.total_records > 0 else 0.0
                    render_html(f"""
                    <div class="dc-summary-stat-box">
                        <span class="dc-summary-stat-label">Non-NULL Records</span>
                        <span class="dc-summary-stat-value">{active_profile.non_null_records:,}</span>
                        <span class="dc-summary-stat-sub">{non_null_pct:.1f}% populated</span>
                    </div>
                    """)
                with m3:
                    missing_pct = (active_profile.missing_records / active_profile.total_records) * 100.0 if active_profile.total_records > 0 else 0.0
                    render_html(f"""
                    <div class="dc-summary-stat-box">
                        <span class="dc-summary-stat-label">Missing Values</span>
                        <span class="dc-summary-stat-value">{active_profile.missing_records:,}</span>
                        <span class="dc-summary-stat-sub">{missing_pct:.1f}% total missing</span>
                    </div>
                    """)
                with m4:
                    render_html(f"""
                    <div class="dc-summary-stat-box">
                        <span class="dc-summary-stat-label">Dominant Pattern</span>
                        <span class="dc-summary-stat-value">{active_profile.dominant_percentage:.1f}%</span>
                        <span class="dc-summary-stat-sub">{html.escape(active_profile.dominant_pattern_label or 'N/A')}</span>
                    </div>
                    """)

                # Missing Values Sub-Breakdown Strip
                sql_null_pct = (active_profile.null_records / active_profile.total_records) * 100.0 if active_profile.total_records > 0 else 0.0
                empty_str_pct = (active_profile.empty_string_records / active_profile.total_records) * 100.0 if active_profile.total_records > 0 else 0.0
                ws_pct = (active_profile.whitespace_records / active_profile.total_records) * 100.0 if active_profile.total_records > 0 else 0.0
                ph_pct = (active_profile.placeholder_records / active_profile.total_records) * 100.0 if active_profile.total_records > 0 else 0.0

                render_html(f"""
                <div style="background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px 16px; margin: 12px 0 16px 0; display: flex; flex-wrap: wrap; gap: 20px; font-size: 12.5px; color: #334155;">
                    <div><strong>Missing Breakdown:</strong> {active_profile.missing_records:,} ({missing_pct:.1f}%)</div>
                    <div>• <strong>SQL NULL:</strong> {active_profile.null_records:,} ({sql_null_pct:.1f}%)</div>
                    <div>• <strong>Empty Strings (""):</strong> {active_profile.empty_string_records:,} ({empty_str_pct:.1f}%)</div>
                    <div>• <strong>Whitespace-Only:</strong> {active_profile.whitespace_records:,} ({ws_pct:.1f}%)</div>
                    <div>• <strong>Placeholders (N/A, etc.):</strong> {active_profile.placeholder_records:,} ({ph_pct:.1f}%)</div>
                </div>
                """)

                # Category Distribution Data & Chart
                table_rows = []
                chart_data = []

                for cat_enum in ValuePatternCategory:
                    cat_key = cat_enum.value
                    count = active_profile.counts.get(cat_key, 0)
                    pct = active_profile.percentages.get(cat_key, 0.0)
                    label = CATEGORY_DISPLAY_LABELS.get(cat_key, cat_key)
                    desc = CATEGORY_DESCRIPTIONS.get(cat_key, "")

                    table_rows.append({
                        "Pattern Category": label,
                        "Description": desc,
                        "Record Count": f"{count:,}",
                        "Distribution (%)": f"{pct:.2f}%",
                    })

                    if count > 0:
                        chart_data.append({
                            "Key": cat_key,
                            "Category": label,
                            "Record Count": count,
                            "Percentage (%)": round(pct, 2),
                        })

                # Visual chart and tabular breakdown
                st.markdown("<hr style='margin: 12px 0 16px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
                with st.container(border=True):
                    render_html(f"""
                    <div style="display: flex; align-items: center; gap: 16px; padding: 8px 4px 16px;">
                        <div style="width: 58px; height: 58px; display: flex; align-items: end; justify-content: center; gap: 5px; padding: 13px; box-sizing: border-box; border-radius: 16px; background: linear-gradient(135deg, #E0F7F7 0%, #F0FDFA 100%);">
                            <span style="width: 8px; height: 18px; border-radius: 3px; background: #0F9B9A;"></span>
                            <span style="width: 8px; height: 29px; border-radius: 3px; background: #0F9B9A;"></span>
                            <span style="width: 8px; height: 38px; border-radius: 3px; background: #0F9B9A;"></span>
                        </div>
                        <div>
                            <div style="font-family: Inter, Segoe UI, sans-serif; font-size: 25px; font-weight: 750; color: #10244A; line-height: 1.15;">Value Pattern Distribution</div>
                            <div style="font-family: Inter, Segoe UI, sans-serif; font-size: 14px; color: #7586A3; margin-top: 5px;">Distribution across {active_profile.total_records:,} scanned records</div>
                        </div>
                    </div>
                    """)

                    if chart_data:
                        chart_data = sorted(
                            chart_data,
                            key=lambda item: item["Percentage (%)"],
                            reverse=True,
                        )
                        percentages = [item["Percentage (%)"] for item in chart_data]
                        counts = [item["Record Count"] for item in chart_data]
                        categories = [item["Category"] for item in chart_data]
                        colors = [
                            "#DC2626"
                            if item["Key"] == ValuePatternCategory.MISSING_PLACEHOLDER.value
                            else "#134E4A"
                            if item["Key"] == active_profile.dominant_pattern
                            else "#0F8D8D"
                            for item in chart_data
                        ]
                        max_percentage = max(percentages, default=0.0)
                        chart_height = max(290, min(440, 100 + len(chart_data) * 50))

                        fig = go.Figure(
                            go.Bar(
                                x=percentages,
                                y=categories,
                                orientation="h",
                                marker_color=colors,
                                text=[
                                    f"{percentage:.1f}% ({count:,})"
                                    for percentage, count in zip(percentages, counts)
                                ],
                                textposition="outside",
                                textfont={"color": colors, "size": 15},
                                cliponaxis=False,
                                customdata=counts,
                                hovertemplate=(
                                    "<b>%{y}</b><br>"
                                    "Record Count: %{customdata:,}<br>"
                                    "Percentage: %{x:.2f}%"
                                    "<extra></extra>"
                                ),
                            )
                        )
                        fig.update_layout(
                            height=chart_height,
                            bargap=0.35,
                            barcornerradius=9,
                            showlegend=False,
                            paper_bgcolor="rgba(0,0,0,0)",
                            plot_bgcolor="rgba(0,0,0,0)",
                            font={
                                "family": "Inter, Segoe UI, sans-serif",
                                "size": 13,
                                "color": "#10244A",
                            },
                            hoverlabel={
                                "bgcolor": "#FFFFFF",
                                "bordercolor": "#D8E2EE",
                                "font": {"color": "#1F2937", "size": 13},
                            },
                            margin={"l": 10, "r": 30, "t": 4, "b": 10},
                        )
                        fig.update_xaxes(
                            range=[0, max(max_percentage * 1.15, 1)],
                            tickformat=".0f",
                            ticksuffix="%",
                            showgrid=True,
                            gridcolor="#D7E3EF",
                            griddash="dot",
                            zeroline=False,
                            showline=True,
                            linecolor="#B7C7DC",
                            tickfont={"size": 12, "color": "#667895"},
                        )
                        fig.update_yaxes(
                            title_text=None,
                            autorange="reversed",
                            showgrid=False,
                            zeroline=False,
                            tickfont={"size": 13, "color": "#10244A"},
                            automargin=True,
                        )
                        st.plotly_chart(
                            fig,
                            use_container_width=True,
                            config={"displayModeBar": False},
                        )

                display_df = pd.DataFrame(table_rows)
                st.markdown("<div style='margin-top: 10px;'></div>", unsafe_allow_html=True)
                st.dataframe(
                    display_df,
                    use_container_width=True,
                    hide_index=True,
                    height=min(480, len(table_rows) * 35 + 38),
                )

                # --- AI Analysis & Recommendations Trigger ---
                st.markdown("<hr style='margin: 20px 0 16px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
                ai_action_hdr_col1, ai_action_hdr_col2 = st.columns([2, 1])
                with ai_action_hdr_col1:
                    st.markdown("##### ✨ AI-Powered Data Analysis & SQL Recommendations")
                    st.markdown(
                        "<p style='font-size: 13px; color: #64748B; margin: 0 0 10px 0;'>"
                        "Analyze this column's pattern distribution and missing-value statistics to generate "
                        "actionable, dialect-safe SQL queries for detected quality issues."
                        "</p>",
                        unsafe_allow_html=True,
                    )
                with ai_action_hdr_col2:
                    st.markdown(
                        "<div style='font-size: 12px; color: #0F766E; background: #F0FDFA; border: 1px solid #CCFBF1; border-radius: 6px; padding: 6px 10px; margin-top: 4px;'>"
                        "🛡️ <strong>Safety Guarantee:</strong> Production tables remain read-only. Transformations target your workspace table."
                        "</div>",
                        unsafe_allow_html=True,
                    )

                ai_btn_col1, ai_btn_col2 = st.columns([1, 2])
                with ai_btn_col1:
                    analyze_btn_clicked = st.button(
                        "✨ Analyze with AI",
                        type="primary",
                        key="ai_col_analyze_btn",
                        disabled=TEMP_DISABLE_COLUMN_AI_ANALYSIS,
                        help="Temporarily disabled during AI API Connectivity Test Mode.",
                        use_container_width=True,
                    )
                with ai_btn_col2:
                    st.caption("Inspects pattern distribution, SQL NULLs, and placeholders without transferring sensitive raw data.")

                if TEMP_DISABLE_COLUMN_AI_ANALYSIS:
                    render_alert(
                        "info",
                        "AI Analysis Temporarily Disabled",
                        "AI-powered column analysis and SQL recommendations are temporarily disabled during "
                        "AI API Connectivity Test Mode. Use the AI API Connectivity Test card to verify your endpoint.",
                    )

                retry_initial_analysis = st.session_state.pop("_ai_col_retry_initial", False)
                if analyze_btn_clicked or retry_initial_analysis:
                    ai_cfg = load_ai_column_config()
                    # A fresh analysis is the start of a fresh, selection-scoped
                    # conversation; do not mix it with an earlier attempt.
                    st.session_state._ai_col_chat_messages = []
                    
                    # Resolve active workspace table
                    active_ws = st.session_state.get("working_table_name")
                    if not active_ws or not active_ws.startswith(active_profile.table_name):
                        active_ws = f"{active_profile.table_name}__cleaning_workspace"

                    # Resolve dialect
                    dialect_name = "mysql"
                    if engine and hasattr(engine, "dialect") and hasattr(engine.dialect, "name"):
                        dialect_name = engine.dialect.name

                    # Build prompts
                    usr_prompt = build_user_prompt(active_profile, active_ws, dialect_name)
                    timestamp = time.strftime("%H:%M")

                    # Add user message to chat history
                    st.session_state._ai_col_chat_messages.append({
                        "role": "user", "content": usr_prompt, "timestamp": timestamp
                    })

                    # Render deltas only while the response is in flight. The
                    # message is committed to history only after strict JSON
                    # validation succeeds below.
                    streaming_placeholder = st.empty()

                    def render_initial_delta(partial_text: str) -> None:
                        streaming_placeholder.markdown("🤖 Generating validated recommendations…\n\n" + partial_text)

                    with st.spinner(f"Analyzing column '{active_profile.column_name}' with AI..."):
                        response_text, error = send_ai_chat_message(
                            profile=active_profile,
                            config=ai_cfg,
                            messages=[{"role": "user", "content": usr_prompt}],
                            dialect=dialect_name,
                            workspace_table=active_ws,
                            on_delta=render_initial_delta,
                        )
                    streaming_placeholder.empty()

                    if error:
                        st.session_state._ai_col_chat_messages.append({
                            "role": "assistant",
                            "content": f"⚠️ Error: {error}",
                            "timestamp": timestamp,
                            "kind": "initial_error",
                        })
                        st.session_state._ai_col_analysis_result = None
                    else:
                        # Parse AI response
                        try:
                            ai_recs, summary = _parse_ai_recommendations(
                                response_text, active_profile, active_ws, dialect_name
                            )
                            analysis_res = AIAnalysisResult(
                                table_name=active_profile.table_name,
                                column_name=active_profile.column_name,
                                workspace_table=active_ws,
                                dialect=dialect_name,
                                recommendations=ai_recs,
                                summary_narrative=summary or f"AI analyzed {len(ai_recs)} data-quality issue(s).",
                                success=True,
                                source="ai",
                                payload_debug=[{
                                    "request_index": 1,
                                    "model": ai_cfg.model_name.strip(),
                                    "endpoint_host": "",
                                    "duration_ms": 0,
                                    "duration_str": "0.00s",
                                    "http_status": "200 OK",
                                    "status": "sent_success",
                                    "payload": {},
                                }],
                                http_status=200,
                                endpoint_host="",
                                duration_ms=0,
                                finish_reason="stop",
                                truncated=False,
                            )
                            st.session_state._ai_col_analysis_result = analysis_res

                            # Add assistant response to chat
                            st.session_state._ai_col_chat_messages.append({
                                "role": "assistant",
                                "content": format_recommendations_for_chat(summary, ai_recs),
                                "timestamp": timestamp,
                            })
                        except ValueError as exc:
                            safe_err = sanitize_error_message(str(exc), ai_cfg.api_key)
                            st.session_state._ai_col_chat_messages.append({
                                "role": "assistant",
                                "content": f"⚠️ Error: {safe_err}",
                                "timestamp": timestamp,
                                "kind": "initial_error",
                            })
                            st.session_state._ai_col_analysis_result = None

    # 5. Temporary Debug Feature: Display Exact Data Sent to AI
    render_ai_payload_debug_section(st.session_state.get("_ai_col_analysis_result"))

    # 6. AI Chat Container (rendered when there's an active profiling result)
    chat_messages = st.session_state.get("_ai_col_chat_messages", [])
    
    if active_profile and chat_messages:
        if any(
            message.get("role") == "assistant"
            and "rule engine generated fallback" in message.get("content", "").lower()
            for message in chat_messages
        ):
            render_alert(
                "info",
                "Grounded Rule Engine Active",
                "The AI endpoint did not complete this response. Any fallback guidance is grounded in the current column profile.",
            )
        # One native, scrollable Streamlit container prevents detached HTML
        # blocks and keeps the send area consistently below the transcript.
        render_ai_chat_history(chat_messages)

        if chat_messages[-1].get("kind") == "initial_error":
            if st.button("Retry analysis", key="ai_col_retry_initial_analysis"):
                st.session_state._ai_col_retry_initial = True
                st.rerun()
        
        # Chat input form
        user_msg = render_ai_chat_input(disabled=not bool(active_profile))
        
        # Process chat input (send to AI)
        if user_msg:
            ai_cfg = load_ai_column_config()
            
            # Resolve active workspace table
            active_ws = st.session_state.get("working_table_name")
            if not active_ws or not active_ws.startswith(active_profile.table_name):
                active_ws = f"{active_profile.table_name}__cleaning_workspace"

            # Resolve dialect
            dialect_name = "mysql"
            if engine and hasattr(engine, "dialect") and hasattr(engine.dialect, "name"):
                dialect_name = engine.dialect.name

            # Store the follow-up before dispatch so both it and the validated
            # initial analysis are retained in the next request.
            st.session_state._ai_col_chat_messages.append({
                "role": "user", "content": user_msg, "timestamp": time.strftime("%H:%M"),
            })

            # Build full message history for context.
            all_messages = [
                {"role": m["role"], "content": m["content"]}
                for m in st.session_state._ai_col_chat_messages
            ]

            streaming_placeholder = st.empty()

            def render_follow_up_delta(partial_text: str) -> None:
                streaming_placeholder.markdown("🤖 " + partial_text)

            with st.spinner("AI is responding..."):
                response_text, error = send_ai_chat_message(
                    profile=active_profile,
                    config=ai_cfg,
                    messages=all_messages,
                    dialect=dialect_name,
                    workspace_table=active_ws,
                    on_delta=render_follow_up_delta,
                    system_prompt=build_follow_up_system_prompt(dialect_name, active_ws),
                )
            streaming_placeholder.empty()

            if error:
                st.session_state._ai_col_chat_messages.append({
                    "role": "assistant",
                    "content": f"⚠️ Error: {error}",
                    "timestamp": time.strftime("%H:%M"),
                })
            else:
                st.session_state._ai_col_chat_messages.append({
                    "role": "assistant",
                    "content": response_text,
                    "timestamp": time.strftime("%H:%M"),
                })
            
            st.rerun()
    
    elif active_profile and not chat_messages:
        # Empty state - prompt user to click Analyze with AI
        render_alert(
            "info",
            "Start a Conversation",
            "Click 'Analyze with AI' to start a conversation about this column. "
            "The assistant can answer follow-up questions about your profiling results.",
        )

    # 6. Feature Status & Workflow Cards Container
    with st.container(border=True):
        info_icon = get_icon_svg("activity", size=22, stroke_width=2.0, color="#0F766E")
        render_html(f"""
        <div style="display: flex; align-items: flex-start; gap: 14px; padding: 4px 0 10px 0;">
            <div style="background: #F0FDFA; border: 1px solid #CCFBF1; border-radius: 10px; padding: 8px; display: flex; align-items: center; justify-content: center;">
                {info_icon}
            </div>
            <div>
                <h3 style="font-size: 15px; font-weight: 700; color: #0F172A; margin: 0 0 4px 0;">
                    AI Column Cleaning Workflow Pipeline
                </h3>
                <p style="font-size: 13px; color: #475569; line-height: 1.4; margin: 0;">
                    Complete end-to-end workflow: In-database column profiling, AI anomaly analysis, and safe staging execution.
                </p>
            </div>
        </div>
        """)

        # Feature Status Cards
        c1, c2, c3 = st.columns(3)
        with c1:
            with st.container(border=True):
                st.markdown("##### 🔍 1. Column Profiling")
                st.caption("Active: In-database pattern detection, missing value distribution, and quality profiling.")
        with c2:
            with st.container(border=True):
                st.markdown("##### ✨ 2. AI Analysis & SQL")
                st.caption("Active: AI diagnosis, grounded SQL cleaning queries, and zero-production-risk validation.")
        with c3:
            with st.container(border=True):
                st.markdown("##### 🚀 3. Staging Execution")
                st.caption("Upcoming: One-click interactive transformation execution on isolated staging tables with audit logging.")

