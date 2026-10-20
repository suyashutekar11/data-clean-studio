"""
DataClean Studio — AI Assistant Dedicated View
ui/ai_assistant_view.py

Professional, modern AI Assistant interface featuring:
- Left sidebar: "AI Configuration" panel (provider selector, model selector, masked API key,
  custom base URL, test connection button with feedback, save/clear configuration, security guarantees)
- Main area:
  1. Active Database & Table Context Card (connected host, database switcher, table switcher,
     read-only vs workspace isolation badges, total rows, "Analyze Table" & "Refresh Profile" buttons)
  2. Data Quality & Profiling Overview (health score gauge, KPI cards, severity breakdown,
     AI executive assessment card, confirmed findings vs potential causes)
  3. Interactive Column-by-Column Drilldown (pattern stats, casing, dates, currencies,
     anonymized suspicious samples with frequencies, recommended tools, and "Ask AI about this column" button)
  4. Grounded Chatbot Conversation (multi-turn chat grounded in observable profiling evidence,
     suggested prompt chips, Ctrl+Enter support, strict zero SQL mutation guarantee)
"""

from __future__ import annotations

import html
import time
from typing import Optional, List, Dict, Any, Callable

import streamlit as st

from src.ai_service import (
    AIProviderConfig,
    ChatMessage,
    SUPPORTED_PROVIDERS,
    mask_api_key,
    validate_ai_config,
    test_ai_connection,
    test_ai_api_connectivity,
    TEMP_DISABLE_AI_ANALYSIS,
    send_chat_message,
)
from src.metadata import MySQLMetadataInspector
from src.ai_profiling import (
    build_table_ai_profile,
    format_compact_ai_summary,
    format_column_drilldown_prompt,
)
from ui.icons import get_icon_svg
from ui.components import (
    render_html,
    render_badge,
    render_alert,
    render_module_header,
)


def get_ai_assistant_css() -> str:
    """Scoped CSS for the dedicated AI Assistant page and sidebar configuration."""
    return """
    /* ═══════════════════════════════════════════════════════════════
       AI ASSISTANT DEDICATED VIEW STYLING
       =============================================================== */

    /* Sidebar AI Configuration */
    .dc-ai-sb-header {
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
        margin-top: 10px !important;
        margin-bottom: 4px !important;
    }

    .dc-ai-sb-title {
        font-size: 15px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        letter-spacing: -0.01em !important;
        margin: 0 !important;
    }

    .dc-ai-sb-subtitle {
        font-size: 12px !important;
        color: #64748B !important;
        line-height: 1.4 !important;
        margin: 0 0 12px 0 !important;
    }

    .dc-ai-sec-note {
        font-size: 11px !important;
        color: #64748B !important;
        line-height: 1.4 !important;
        margin-top: 14px !important;
        padding-top: 10px !important;
        border-top: 1px dashed #E2E8F0 !important;
    }

    /* Main Area Chat Header */
    .dc-ai-chat-header-bar {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        padding: 14px 18px !important;
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        margin-bottom: 16px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    }

    .dc-ai-chat-title-group {
        display: flex !important;
        align-items: center !important;
        gap: 12px !important;
        flex-wrap: wrap !important;
    }

    .dc-ai-chat-main-title {
        font-size: 18px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin: 0 !important;
        letter-spacing: -0.01em !important;
    }

    /* Database Context Card */
    .dc-ai-db-card {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 16px 20px !important;
        margin-bottom: 18px !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    }

    .dc-ai-db-header {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        margin-bottom: 10px !important;
        flex-wrap: wrap !important;
        gap: 8px !important;
    }

    .dc-ai-db-title {
        font-size: 14px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin: 0 !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }

    /* Quality Metrics */
    .dc-ai-metrics-grid {
        display: grid !important;
        grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)) !important;
        gap: 12px !important;
        margin-bottom: 16px !important;
    }

    .dc-ai-metric-box {
        background: #F8FAFC !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 10px !important;
        padding: 12px 14px !important;
        text-align: left !important;
    }

    .dc-ai-metric-label {
        font-size: 11.5px !important;
        font-weight: 600 !important;
        color: #64748B !important;
        text-transform: uppercase !important;
        letter-spacing: 0.04em !important;
        margin-bottom: 4px !important;
    }

    .dc-ai-metric-val {
        font-size: 20px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
    }

    .dc-ai-metric-sub {
        font-size: 11.5px !important;
        color: #64748B !important;
        margin-top: 2px !important;
    }

    /* Severity Badges */
    .dc-ai-sev-high {
        background: #FEF2F2 !important;
        color: #DC2626 !important;
        border: 1px solid #FEE2E2 !important;
        padding: 2px 8px !important;
        border-radius: 9999px !important;
        font-size: 11px !important;
        font-weight: 600 !important;
    }

    .dc-ai-sev-med {
        background: #FFFBEB !important;
        color: #D97706 !important;
        border: 1px solid #FEF3C7 !important;
        padding: 2px 8px !important;
        border-radius: 9999px !important;
        font-size: 11px !important;
        font-weight: 600 !important;
    }

    .dc-ai-sev-low {
        background: #EFF6FF !important;
        color: #2563EB !important;
        border: 1px solid #DBEAFE !important;
        padding: 2px 8px !important;
        border-radius: 9999px !important;
        font-size: 11px !important;
        font-weight: 600 !important;
    }

    /* Sample pill */
    .dc-ai-sample-pill {
        display: inline-block !important;
        background: #F1F5F9 !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 6px !important;
        padding: 2px 7px !important;
        font-size: 11.5px !important;
        font-family: monospace !important;
        color: #334155 !important;
        margin-right: 6px !important;
        margin-bottom: 4px !important;
    }

    /* Welcome Box */
    .dc-ai-welcome-box {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        border-radius: 12px !important;
        padding: 24px !important;
        margin-bottom: 20px !important;
        text-align: left !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    }

    .dc-ai-welcome-title {
        font-size: 16px !important;
        font-weight: 700 !important;
        color: #0F172A !important;
        margin-bottom: 8px !important;
        display: flex !important;
        align-items: center !important;
        gap: 8px !important;
    }

    .dc-ai-welcome-text {
        font-size: 13.5px !important;
        color: #475569 !important;
        line-height: 1.55 !important;
        margin: 0 0 14px 0 !important;
    }

    .dc-ai-quick-prompts {
        display: flex !important;
        flex-wrap: wrap !important;
        gap: 8px !important;
        margin-top: 8px !important;
    }

    .dc-ai-prompt-chip {
        display: inline-flex !important;
        align-items: center !important;
        gap: 6px !important;
        font-size: 12px !important;
        font-weight: 500 !important;
        color: #0F766E !important;
        background: #F0FDFA !important;
        border: 1px solid #CCFBF1 !important;
        border-radius: 6px !important;
        padding: 6px 12px !important;
    }

    /* Message Bubbles */
    [data-testid="stChatMessage"] {
        padding: 14px 18px !important;
        border-radius: 12px !important;
        margin-bottom: 14px !important;
        box-sizing: border-box !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-user"]) {
        background: #F8FAFC !important;
        border: 1px solid #E2E8F0 !important;
    }

    [data-testid="stChatMessage"]:has([data-testid="chatAvatarIcon-assistant"]) {
        background: #FFFFFF !important;
        border: 1px solid #E2E8F0 !important;
        box-shadow: 0 1px 3px rgba(15, 23, 42, 0.04) !important;
    }

    /* Keyboard shortcut helper hint */
    .dc-ai-input-hint {
        font-size: 11px !important;
        color: #94A3B8 !important;
        text-align: right !important;
        margin-top: 4px !important;
        margin-right: 4px !important;
    }
    """


def get_ctrl_enter_script() -> str:
    """JavaScript snippet to bind Ctrl+Enter and Cmd+Enter to message submission."""
    return """
    <script>
    (function() {
        function setupCtrlEnter() {
            const textareas = document.querySelectorAll('div[data-testid="stChatInput"] textarea');
            textareas.forEach(function(ta) {
                if (!ta.dataset.ctrlEnterListener) {
                    ta.dataset.ctrlEnterListener = 'true';
                    ta.addEventListener('keydown', function(e) {
                        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
                            e.preventDefault();
                            const sendBtn = ta.closest('div[data-testid="stChatInput"]').querySelector('button');
                            if (sendBtn && !sendBtn.disabled) {
                                sendBtn.click();
                            }
                        }
                    });
                }
            });
        }
        setupCtrlEnter();
        setInterval(setupCtrlEnter, 600);
    })();
    </script>
    """


def init_ai_session_state() -> None:
    """Initializes session state keys for the AI Assistant and Profiling engine."""
    if "ai_config" not in st.session_state:
        st.session_state.ai_config = None
    if "ai_config_saved" not in st.session_state:
        st.session_state.ai_config_saved = False
    if "ai_test_status" not in st.session_state:
        st.session_state.ai_test_status = None
    if "ai_chat_messages" not in st.session_state:
        st.session_state.ai_chat_messages = []
    if "ai_is_processing" not in st.session_state:
        st.session_state.ai_is_processing = False
    if "ai_table_profile" not in st.session_state:
        st.session_state.ai_table_profile = None
    if "ai_table_analysis" not in st.session_state:
        st.session_state.ai_table_analysis = None
    if "ai_is_profiling" not in st.session_state:
        st.session_state.ai_is_profiling = False
    if "ai_connectivity_tests" not in st.session_state:
        st.session_state.ai_connectivity_tests = []


def get_ai_system_prompt_with_evidence(profile: Optional[Dict[str, Any]] = None) -> str:
    """
    Constructs the grounded system prompt for the AI Assistant.
    Injects verifiable profiling evidence, explicit safety guidelines,
    and tool recommendations.
    """
    base = (
        "You are DataClean AI Assistant, an expert data quality architect and cleaning specialist "
        "integrated into DataClean Studio. You assist users with data quality assessments, root-cause "
        "investigation, regex patterns, and data transformation strategies.\n\n"
        "ZERO-PRODUCTION-RISK ARCHITECTURE & SAFETY RULES:\n"
        "- Production source tables remain strictly read-only.\n"
        "- Never propose direct SQL mutations or data modifications on source tables.\n"
        "- All cleaning transformations occur inside isolated workspace tables ({table}__cleaning_{uuid}).\n"
        "- You do NOT execute SQL queries directly."
    )
    if not profile:
        return base

    evidence = profile.get("compact_summary", "")
    tbl_name = profile.get("table_name", "target")
    db_name = profile.get("database", "target_db")

    return (
        f"{base}\n\n"
        f"GROUNDED PROFILING EVIDENCE FOR ACTIVE TABLE `{db_name}.{tbl_name}`:\n"
        f"===========================================================\n"
        f"{evidence}\n"
        f"===========================================================\n\n"
        "INSTRUCTIONS FOR GROUNDED REASONING:\n"
        "1. Base all conclusions strictly on the observable profiling evidence and exact counts above.\n"
        "2. Clearly separate CONFIRMED FINDINGS (exact counts observed in the data) from POTENTIAL CAUSES / HYPOTHESES (system, ETL, or data-entry reasons).\n"
        "3. Do not assume or invent business domain context, column meanings, or row counts not present in the evidence.\n"
        "4. Recommend specific DataClean Studio cleaning features where applicable:\n"
        "   - 'Blank & NULL Values' (for nulls and empty strings)\n"
        "   - 'Whitespace Cleaning' (for leading, trailing, and redundant whitespaces)\n"
        "   - 'Text Casing' (for casing inconsistencies)\n"
        "   - 'Advanced Date Standardization' / 'Date Formatting' (for mixed or malformed dates)\n"
        "   - 'Numeric Data Cleaning' (for currency symbols, units, or non-numeric characters)\n"
        "   - 'Boolean Normalization' (for varied boolean flags like Y/N, 1/0, True/False)\n"
        "   - 'Special Character Cleaning' (for control characters or invalid symbols)\n"
        "   - 'Duplicate Rows & Deduplication' (for duplicate records)\n"
        "5. Keep responses concise, well-structured with bullet points, bold highlights, and actionable advice."
    )


def render_ai_config_sidebar(on_back_to_hub: Optional[Callable[[], None]] = None) -> None:
    """
    Renders the Left Sidebar AI Configuration and Navigation section.
    Provides provider selection, model selection, API key field, base URL,
    test connection, save configuration, clear configuration, and back navigation.
    """
    init_ai_session_state()
    st.markdown(f"<style>{get_ai_assistant_css()}</style>", unsafe_allow_html=True)

    # 1. Back Navigation Button
    if st.button(
        "← Back to Cleaning Hub",
        use_container_width=True,
        type="secondary",
        key="ai_sb_back_hub_btn",
        help="Return to DataClean Studio Cleaning Hub",
    ):
        if callable(on_back_to_hub):
            on_back_to_hub()
        else:
            st.session_state.workspace_sub_tab = "🏠 Cleaning Hub"
            st.session_state._ws_sub_radio = "🏠 Cleaning Hub"
            st.query_params["workspace_sub_tab"] = "🏠 Cleaning Hub"
            st.rerun()

    # 2. Database Connection Context Pill
    if st.session_state.get("connected"):
        db = st.session_state.get("selected_db") or "MySQL"
        tbl = st.session_state.get("working_table_name") or st.session_state.get("selected_table") or ""
        label = f"{db}.{tbl}" if tbl else db
        render_html(f"""
        <div style="font-size: 11.5px; color: #0F766E; background: #F0FDFA; border: 1px solid #CCFBF1; border-radius: 6px; padding: 6px 10px; margin: 8px 0 12px 0;">
            <b>MySQL Connected:</b> <code>{html.escape(label)}</code>
        </div>
        """)

    st.markdown("<hr style='margin: 8px 0 14px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)

    # 3. Section Header
    bot_icon = get_icon_svg("bot", size=18, stroke_width=2.0, color="#0F766E")
    render_html(f"""
    <div class="dc-ai-sb-header">
        {bot_icon}
        <h3 class="dc-ai-sb-title">AI Configuration</h3>
    </div>
    <div class="dc-ai-sb-subtitle">
        Configure your AI model provider and credentials.
    </div>
    """)

    active_config: Optional[AIProviderConfig] = st.session_state.get("ai_config")
    is_saved = st.session_state.get("ai_config_saved", False)

    # Status Pill
    if is_saved and active_config:
        prov_display = SUPPORTED_PROVIDERS.get(active_config.provider, {}).get("name", active_config.provider)
        st.success(f"Configured: **{prov_display}** (`{active_config.model}`)")
    else:
        st.info("No active AI model configured.")

    # 4. Model Provider Selector
    prov_keys = list(SUPPORTED_PROVIDERS.keys())
    default_prov_idx = 0
    if active_config and active_config.provider in prov_keys:
        default_prov_idx = prov_keys.index(active_config.provider)

    selected_prov = st.selectbox(
        "Model Provider",
        options=prov_keys,
        index=default_prov_idx,
        format_func=lambda p: SUPPORTED_PROVIDERS[p]["name"],
        key="ai_sb_prov_selector",
        help="Select the AI provider service or compatible API endpoint.",
    )
    prov_meta = SUPPORTED_PROVIDERS[selected_prov]

    # 5. Model Selector / Input
    default_models = prov_meta.get("default_models", [])
    model_options = list(default_models) + ["Custom model name..."]

    default_model_idx = 0
    if active_config and active_config.model in default_models:
        default_model_idx = default_models.index(active_config.model)
    elif active_config and active_config.model:
        default_model_idx = len(model_options) - 1

    selected_model_choice = st.selectbox(
        "Model",
        options=model_options,
        index=default_model_idx,
        key="ai_sb_model_selector",
        help="Select a standard model or choose custom identifier.",
    )

    if selected_model_choice == "Custom model name...":
        default_custom_val = active_config.model if active_config else ""
        model_name = st.text_input(
            "Custom Model Identifier",
            value=default_custom_val,
            placeholder="e.g. gpt-4o-2024-08-06 or llama3:latest",
            key="ai_sb_custom_model_input",
        ).strip()
    else:
        model_name = selected_model_choice

    # 6. API Key Field
    requires_key = prov_meta.get("requires_key", True)
    label_suffix = " (Required)" if requires_key else " (Optional for local)"

    api_key_val = st.text_input(
        f"API Key{label_suffix}",
        type="password",
        value="",
        placeholder="Paste your API key here..." if not (is_saved and active_config and active_config.api_key) else "Leave empty to keep saved key",
        key="ai_sb_api_key_field",
        help=prov_meta.get("doc_hint", "Enter your provider API key."),
    ).strip()

    # Masked Key Preview if Saved
    if is_saved and active_config and active_config.api_key:
        masked = mask_api_key(active_config.api_key)
        st.caption(f"Active Key: `{masked}`")

    # 7. Optional Custom Base URL
    supports_custom_url = prov_meta.get("supports_custom_url", False)
    custom_base_url = None
    if supports_custom_url:
        default_url = active_config.base_url if (active_config and active_config.base_url) else ""
        custom_base_url = st.text_input(
            "API Base URL (optional)",
            value=default_url,
            placeholder=prov_meta.get("default_base_url", "https://..."),
            key="ai_sb_base_url_field",
            help="Custom endpoint URL for local servers (Ollama, vLLM) or proxies (OpenRouter).",
        ).strip()

    st.markdown("<div style='margin-bottom: 8px;'></div>", unsafe_allow_html=True)

    # 8. Resolve Effective Configuration for actions
    def _get_current_config() -> AIProviderConfig:
        eff_key = api_key_val
        if not eff_key and is_saved and active_config:
            eff_key = active_config.api_key
        return AIProviderConfig(
            provider=selected_prov,
            api_key=eff_key,
            model=model_name,
            base_url=custom_base_url if (custom_base_url and custom_base_url.strip()) else None,
        )

    # 9. Test Connection & Save Config Buttons
    btn_col1, btn_col2 = st.columns([1, 1])
    with btn_col1:
        if st.button(
            "Test Connection",
            use_container_width=True,
            type="secondary",
            key="ai_sb_test_conn_btn",
            help="Send a test ping to verify endpoint and credentials.",
        ):
            test_cfg = _get_current_config()
            with st.spinner("Testing connection..."):
                test_ok, test_msg = test_ai_connection(test_cfg, timeout=12.0)
            st.session_state.ai_test_status = {
                "success": test_ok,
                "message": test_msg,
                "timestamp": time.strftime("%H:%M:%S"),
            }
            st.rerun()

    with btn_col2:
        if st.button(
            "Save Config",
            use_container_width=True,
            type="primary",
            key="ai_sb_save_config_btn",
            help="Save configuration in server-side session state.",
        ):
            save_cfg = _get_current_config()
            val_ok, val_msg = validate_ai_config(save_cfg)
            if not val_ok:
                st.error(val_msg)
            else:
                st.session_state.ai_config = save_cfg
                st.session_state.ai_config_saved = True
                st.session_state.ai_test_status = None
                st.success("Configuration saved for active session!")
                st.rerun()

    # Test Feedback
    if st.session_state.get("ai_test_status"):
        t_res = st.session_state.ai_test_status
        if t_res["success"]:
            render_alert("success", "Connection Verified", t_res["message"])
        else:
            render_alert("error", "Connection Failed", t_res["message"])

    # 10. Clear Configuration Button
    if is_saved or active_config:
        st.markdown("<div style='margin-bottom: 6px;'></div>", unsafe_allow_html=True)
        if st.button(
            "Clear Configuration",
            use_container_width=True,
            type="secondary",
            key="ai_sb_clear_config_btn",
            help="Remove saved credentials and reset AI configuration.",
        ):
            st.session_state.ai_config = None
            st.session_state.ai_config_saved = False
            st.session_state.ai_test_status = None
            st.info("AI configuration cleared.")
            st.rerun()

    # 11. Security Guarantee Note
    lock_icon = get_icon_svg("lock", size=13, color="#64748B")
    render_html(f"""
    <div class="dc-ai-sec-note">
        {lock_icon} <b>Security Guarantee:</b> Credentials are kept strictly in server-side memory for your active session. Never stored to disk, browser storage, or shared with database queries.
    </div>
    """)

    # 12. AI API Connectivity Test (Temporary Test Mode Feature)
    st.markdown("<hr style='margin: 14px 0 8px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
    test_icon = get_icon_svg("refresh", size=16, color="#0F766E")
    render_html(f"""
    <div class="dc-ai-sb-header">
        {test_icon}
        <h3 class="dc-ai-sb-title">AI API Connectivity Test</h3>
    </div>
    <div class="dc-ai-sb-subtitle">
        Send a test message to verify your configured AI endpoint is reachable.
    </div>
    """)

    if "ai_connectivity_tests" not in st.session_state:
        st.session_state.ai_connectivity_tests = []

    default_test_msg = "Hi! Please reply with a short greeting to confirm the API is working."

    test_message = st.text_area(
        "Test Message",
        value=default_test_msg,
        height=90,
        key="ai_conn_test_message",
        help="Message to send to the configured AI model to verify connectivity.",
    ).strip()

    send_clicked = st.button(
        "Send Test Message",
        use_container_width=True,
        type="primary",
        key="ai_conn_send_btn",
        help="Send the test message to the configured AI endpoint.",
    )

    clear_col, _spacer = st.columns([1, 3])
    with clear_col:
        if st.button(
            "Clear Test History",
            use_container_width=True,
            type="secondary",
            key="ai_conn_clear_history_btn",
            help="Clear only the connectivity-test history.",
        ):
            st.session_state.ai_connectivity_tests = []
            st.rerun()

    if send_clicked:
        cfg = _get_current_config()
        with st.spinner("Sending test message to AI endpoint..."):
            result = test_ai_api_connectivity(cfg, test_message, timeout=30.0)
        st.session_state.ai_connectivity_tests.insert(0, result)
        st.rerun()

    # Render latest outcome indicator and full history.
    tests = list(st.session_state.get("ai_connectivity_tests", []))
    if tests:
        latest = tests[0]
        if latest["status"] == "success":
            render_alert(
                "success",
                "Test Message Sent Successfully",
                f"Received a reply from model **{latest['model']}** in {latest['duration_ms']} ms "
                f"({latest['duration_seconds']} s).",
            )
        else:
            render_alert(
                "error",
                "Test Message Failed",
                latest["error_details"] or "Request failed.",
            )

        with st.expander("Test History & Details", expanded=False):
            for t in tests:
                with st.container(border=True):
                    c1, c2, c3 = st.columns([1.2, 1.2, 1.6])
                    with c1:
                        st.caption("Status")
                        badge_css = "dc-badge-valid" if t["status"] == "success" else "dc-badge-invalid"
                        st.markdown(
                            f"<span class='dc-badge {badge_css}'>{t['status'].upper()}</span>",
                            unsafe_allow_html=True,
                        )
                        st.markdown(f"**Model:** {t['model'] or '(not set)'}")
                        st.markdown(f"**Host:** {t['endpoint_host'] or '(default)'}")
                    with c2:
                        st.caption("Timing")
                        st.markdown(f"**Duration:** {t['duration_ms']} ms")
                        st.markdown(f"**Seconds:** {t['duration_seconds']} s")
                        st.markdown(f"**HTTP:** {t['http_status'] if t['http_status'] is not None else '—'}")
                    with c3:
                        st.caption("Timestamps")
                        st.markdown(f"**Start:** {t['start_timestamp']}")
                        st.markdown(f"**End:** {t['end_timestamp']}")
                    st.markdown(f"**Test Message Sent:** {html.escape(t['test_message'])}")
                    if t["status"] == "success" and t["response_text"]:
                        st.markdown("**Response Received:**")
                        st.code(t["response_text"], language=None)
                    elif t["status"] == "failed":
                        if t["error_details"]:
                            st.markdown("**Error Details:**")
                            st.code(t["error_details"], language=None)
                        if t["response_body"]:
                            st.markdown("**Response Body:**")
                            st.code(t["response_body"], language=None)


def render_ai_database_context_card(
    engine,
    active_config: Optional[AIProviderConfig],
) -> Tuple[Optional[str], Optional[str], bool]:
    """
    Renders the active database and table selection section.
    Allows user to switch database and table, displays read-only vs workspace
    isolation status, and triggers Table Analysis.
    
    Returns:
        (selected_db, selected_table, is_workspace)
    """
    if not engine or not st.session_state.get("connected"):
        render_alert(
            "info",
            "No Active Database Connection",
            "Connect to your MySQL database in the main workspace to analyze live tables. "
            "You can still ask general questions about data cleaning techniques, regular expressions, and best practices."
        )
        return None, None, False

    # Retrieve databases
    try:
        databases = MySQLMetadataInspector.get_databases(engine)
    except Exception:
        databases = []

    current_db = st.session_state.get("selected_db")
    if current_db not in databases and databases:
        current_db = databases[0]

    host_val = st.session_state.get("host", "localhost")
    port_val = st.session_state.get("port", 3306)
    user_val = st.session_state.get("username", "root")

    db_icon = get_icon_svg("database", size=16, color="#0F766E")
    shield_icon = get_icon_svg("shield_check", size=14, color="#10B981")

    # Outer Container
    with st.container(border=True):
        render_html(f"""
        <div class="dc-ai-db-header">
            <div class="dc-ai-db-title">
                {db_icon}
                <span>Database & Table Context</span>
            </div>
            <div style="font-size: 12px; color: #64748B;">
                Host: <code>{html.escape(str(host_val))}:{port_val}</code> | User: <code>{html.escape(str(user_val))}</code>
            </div>
        </div>
        """)

        # Dropdowns: Database and Table
        col_db, col_tbl = st.columns([1, 1])

        with col_db:
            db_idx = databases.index(current_db) if current_db in databases else 0
            chosen_db = st.selectbox(
                "Active Database / Schema",
                options=databases if databases else ["(No databases available)"],
                index=db_idx,
                key="ai_ctx_db_selector",
                help="Select the MySQL database to inspect.",
            )
            if chosen_db != current_db and chosen_db in databases:
                st.session_state.selected_db = chosen_db
                st.session_state.selected_table = None
                st.session_state.ai_table_profile = None
                st.session_state.ai_table_analysis = None
                st.rerun()

        # Retrieve tables for chosen database
        tables = []
        if chosen_db and chosen_db in databases:
            try:
                tables = MySQLMetadataInspector.get_tables(engine, chosen_db)
            except Exception as e:
                st.error(f"Error fetching tables: {str(e)}")

        current_table = st.session_state.get("working_table_name") or st.session_state.get("selected_table")
        with col_tbl:
            if tables:
                tbl_idx = tables.index(current_table) if current_table in tables else 0
                chosen_tbl = st.selectbox(
                    "Target Table to Analyze",
                    options=tables,
                    index=tbl_idx,
                    key="ai_ctx_table_selector",
                    help="Select the specific table to profile. Unfamiliar schema supported.",
                )
                if chosen_tbl != current_table:
                    # Update session state table
                    if "__cleaning_" in chosen_tbl:
                        st.session_state.working_table_name = chosen_tbl
                    else:
                        st.session_state.selected_table = chosen_tbl
                    st.session_state.ai_table_profile = None
                    st.session_state.ai_table_analysis = None
                    st.rerun()
            else:
                st.selectbox("Target Table", options=["(No tables found)"], disabled=True, key="ai_ctx_no_tables")
                chosen_tbl = None

        if not chosen_tbl or chosen_tbl == "(No tables found)":
            return chosen_db, None, False

        # Table Type Distinction
        is_workspace = bool("__cleaning_" in chosen_tbl or (st.session_state.get("working_table_name") == chosen_tbl))
        if is_workspace:
            type_badge = "<span class='badge-pill badge-info'>Isolated Cleaning Workspace</span>"
            safety_note = "Transformations and deletions are applied safely on this isolated in-database workspace table."
        else:
            type_badge = "<span class='badge-pill badge-primary'>Source Table (Strict Read-Only)</span>"
            safety_note = "🔒 Production tables stay strictly read-only. Clean copies will be generated in an isolated workspace table."

        # Information bar
        render_html(f"""
        <div style="display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 8px; margin: 10px 0 14px 0; padding: 8px 12px; background: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px;">
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 12.5px; font-weight: 600; color: #0F172A;">Table Type:</span>
                {type_badge}
            </div>
            <div style="font-size: 11.5px; color: #64748B;">
                {safety_note}
            </div>
        </div>
        """)

        # Action Buttons: "Analyze Table" and "Refresh Profile"
        btn_c1, btn_c2 = st.columns([1, 1])
        with btn_c1:
            analyze_clicked = st.button(
                "⚡ Analyze Table",
                use_container_width=True,
                type="primary",
                key="ai_ctx_analyze_btn",
                disabled=TEMP_DISABLE_AI_ANALYSIS,
                help="Temporarily disabled during AI API Connectivity Test Mode.",
            )
        with btn_c2:
            refresh_clicked = st.button(
                "🔄 Refresh Profiling",
                use_container_width=True,
                type="secondary",
                key="ai_ctx_refresh_btn",
                disabled=TEMP_DISABLE_AI_ANALYSIS,
                help="Temporarily disabled during AI API Connectivity Test Mode.",
            )

        if TEMP_DISABLE_AI_ANALYSIS:
            render_alert(
                "info",
                "Table Analysis Temporarily Disabled",
                "Table profiling and AI analysis are temporarily disabled during AI API Connectivity Test Mode. "
                "Use the **AI API Connectivity Test** card in the left sidebar to verify your endpoint.",
            )

        if analyze_clicked or refresh_clicked:
            with st.spinner(f"Inspecting data patterns for `{chosen_db}.{chosen_tbl}`..."):
                ok, msg, profile_res = build_table_ai_profile(
                    engine=engine,
                    database=chosen_db,
                    table_name=chosen_tbl,
                    is_workspace=is_workspace,
                )

            if not ok or not profile_res:
                st.error(msg)
            else:
                st.session_state.ai_table_profile = profile_res
                st.session_state.ai_table_analysis = None

                # Generate AI Executive Assessment if AI provider configured
                if active_config and st.session_state.get("ai_config_saved"):
                    with st.spinner("Generating AI Executive Quality Assessment..."):
                        exec_prompt = (
                            f"Analyze the data quality profiling results for table `{chosen_db}.{chosen_tbl}`. "
                            "Provide a comprehensive, professional executive data quality assessment following this structure:\n"
                            "1. Overall Quality Score & Health Assessment\n"
                            "2. Priority Issues by Severity (High, Medium, Low)\n"
                            "3. Potential Root Causes vs Confirmed Observable Findings\n"
                            "4. Recommended DataClean Studio Cleaning Modules"
                        )
                        grounded_sys_prompt = get_ai_system_prompt_with_evidence(profile_res)
                        ai_ok, ai_res = send_chat_message(
                            config=active_config,
                            messages=[ChatMessage(role="user", content=exec_prompt)],
                            system_prompt=grounded_sys_prompt,
                            timeout=45.0,
                        )
                        if ai_ok:
                            st.session_state.ai_table_analysis = ai_res
                st.rerun()

        return chosen_db, chosen_tbl, is_workspace


def render_ai_profiling_overview(profile: Dict[str, Any], active_config: Optional[AIProviderConfig]) -> None:
    """
    Renders the Overall Data Quality Assessment Card, KPI metrics,
    severity breakdown, and AI Executive Interpretation.
    """
    score = profile.get("quality_score", 100)
    if score >= 80:
        score_color = "#10B981"
        score_badge = "Excellent"
    elif score >= 60:
        score_color = "#F59E0B"
        score_badge = "Fair"
    else:
        score_color = "#EF4444"
        score_badge = "Needs Cleaning"

    rows_str = f"{profile.get('row_count', 0):,}"
    cols_str = f"{profile.get('column_count', 0)}"
    dup_str = f"{profile.get('duplicate_groups', 0):,}"
    sev = profile.get("severity_summary", {"high": 0, "medium": 0, "low": 0})

    render_html(f"""
    <div style="margin: 16px 0 12px 0;">
        <h3 style="font-size: 15px; font-weight: 700; color: #0F172A; margin: 0 0 10px 0;">
            📊 Data Quality Assessment: <code>{html.escape(profile.get('table_name', ''))}</code>
        </h3>
        <div class="dc-ai-metrics-grid">
            <div class="dc-ai-metric-box">
                <div class="dc-ai-metric-label">Quality Score</div>
                <div class="dc-ai-metric-val" style="color: {score_color};">{score}<span style="font-size: 13px; font-weight: 500; color: #64748B;">/100</span></div>
                <div class="dc-ai-metric-sub">{score_badge}</div>
            </div>
            <div class="dc-ai-metric-box">
                <div class="dc-ai-metric-label">Dimensions</div>
                <div class="dc-ai-metric-val">{rows_str} <span style="font-size: 13px; font-weight: 500; color: #64748B;">rows</span></div>
                <div class="dc-ai-metric-sub">{cols_str} columns analyzed</div>
            </div>
            <div class="dc-ai-metric-box">
                <div class="dc-ai-metric-label">Duplicates</div>
                <div class="dc-ai-metric-val">{dup_str}</div>
                <div class="dc-ai-metric-sub">Duplicate occurrences</div>
            </div>
            <div class="dc-ai-metric-box">
                <div class="dc-ai-metric-label">Priority Anomalies</div>
                <div style="margin-top: 4px; display: flex; gap: 6px; flex-wrap: wrap;">
                    <span class="dc-ai-sev-high">{sev['high']} High</span>
                    <span class="dc-ai-sev-med">{sev['medium']} Med</span>
                    <span class="dc-ai-sev-low">{sev['low']} Low</span>
                </div>
                <div class="dc-ai-metric-sub" style="margin-top: 6px;">Categorized by risk</div>
            </div>
        </div>
    </div>
    """)

    # AI Executive Assessment Display
    analysis_text = st.session_state.get("ai_table_analysis")
    if analysis_text:
        with st.expander("🤖 AI Executive Quality Assessment & Recommendations", expanded=True):
            st.markdown(analysis_text)
    elif not active_config or not st.session_state.get("ai_config_saved"):
        render_alert(
            "info",
            "Deterministic Profiling Complete",
            "Observable facts, data patterns, and suspicious value samples are calculated below. "
            "Configure your AI model in the left sidebar to generate automated root-cause interpretations and interactive guidance."
        )


def render_ai_column_drilldown(
    profile: Dict[str, Any],
    active_config: Optional[AIProviderConfig],
) -> None:
    """
    Renders expandable column-by-column breakdown showing pattern detections,
    suspicious values with frequencies, recommended tools, and the
    'Ask AI about this column' action.
    """
    columns = profile.get("columns", [])
    if not columns:
        return

    st.markdown("<div style='height: 8px;'></div>", unsafe_allow_html=True)
    st.markdown("#### 🔍 Column Analysis & Anomaly Drilldown")
    st.caption("Inspect generic pattern detections, whitespace anomalies, date formats, and representative suspicious values for each column.")

    # Sort columns: anomalies first, then alphabetically
    sorted_cols = sorted(columns, key=lambda c: (c.get("anomaly_count", 0), c.get("null_pct", 0)), reverse=True)

    for col in sorted_cols:
        col_name = col.get("name", "")
        log_type = col.get("logical_type", "")
        phys_type = col.get("physical_type", "")
        null_pct = col.get("null_pct", 0.0)
        anom_cnt = col.get("anomaly_count", 0)

        # Expander Header
        warning_icon = "⚠️ " if anom_cnt > 0 or null_pct > 0 else "✓ "
        expander_title = f"{warning_icon}`{col_name}` ({log_type}) — {null_pct}% NULL | {anom_cnt} anomalies"

        with st.expander(expander_title, expanded=False):
            # 1. Metrics summary
            c1, c2, c3, c4 = st.columns(4)
            with c1:
                st.caption("Physical / Logical Type")
                st.markdown(f"**`{phys_type}`** ➔ **`{log_type}`**")
            with c2:
                st.caption("Distinct Values")
                st.markdown(f"**{col.get('unique_count', 0):,}**")
            with c3:
                st.caption("Missing / Empty")
                st.markdown(f"**{col.get('null_count', 0):,}** NULLs ({null_pct}%)<br><small>{col.get('empty_count', 0):,} empty strings</small>", unsafe_allow_html=True)
            with c4:
                st.caption("Whitespace Issues")
                st.markdown(f"**{col.get('whitespace_issues', 0):,}**")

            # 2. Pattern Specifics
            p_details = []
            cb = col.get("casing_breakdown", {})
            if cb and any(cb.values()):
                p_details.append(f"**Text Casing:** {cb.get('upper', 0)} UPPER, {cb.get('lower', 0)} lower, {cb.get('title', 0)} Title, {cb.get('mixed', 0)} Mixed")

            num_p = col.get("numeric_patterns", {})
            if num_p:
                if num_p.get("currencies_found"):
                    p_details.append(f"**Currencies Detected:** {', '.join(num_p['currencies_found'])} ({num_p.get('currency_count', 0)} values)")
                if num_p.get("mixed_alphanumeric_count", 0) > 0:
                    p_details.append(f"**Mixed Alphanumeric:** {num_p['mixed_alphanumeric_count']} values contain both digits and letters")
                if num_p.get("na_string_count", 0) > 0:
                    p_details.append(f"**Text Placeholders:** {num_p['na_string_count']} values like 'N/A', 'null', or '-'")

            dt_p = col.get("date_patterns", {})
            if dt_p and dt_p.get("total_date_like", 0) > 0:
                mixed_warn = " ⚠️ **(Mixed Formats!)**" if dt_p.get("is_mixed_date_formats") else ""
                p_details.append(f"**Date Patterns:** ISO: {dt_p.get('iso_date_count')}, Slash: {dt_p.get('slash_date_count')}, Text Month: {dt_p.get('text_month_count')}{mixed_warn}")

            bool_p = col.get("boolean_patterns", {})
            if bool_p and bool_p.get("is_boolean_like"):
                t_str = "/".join(bool_p.get("true_representations", [])[:3])
                f_str = "/".join(bool_p.get("false_representations", [])[:3])
                p_details.append(f"**Boolean Representations:** True: `[{t_str}]` | False: `[{f_str}]`")

            sp_p = col.get("special_char_issues", {})
            if sp_p and sp_p.get("control_char_count", 0) > 0:
                p_details.append(f"**Special Characters:** {sp_p['control_char_count']} values contain control / non-printable characters")

            if p_details:
                st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px dashed #E2E8F0;'>", unsafe_allow_html=True)
                for det in p_details:
                    st.markdown(f"- {det}")

            # 3. Suspicious Samples
            samples = col.get("suspicious_samples", [])
            if samples:
                st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px dashed #E2E8F0;'>", unsafe_allow_html=True)
                st.markdown("**Representative Suspicious Values (Anonymized):**")
                pills_html = "".join([
                    f"<span class='dc-ai-sample-pill'><code>{html.escape(str(s['value']))}</code> ({s['count']}x)</span>"
                    for s in samples
                ])
                render_html(f"<div>{pills_html}</div>")

            # 4. Recommendation & "Ask AI" Button
            st.markdown("<hr style='margin: 10px 0 12px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
            col_b1, col_b2 = st.columns([2, 1.2], vertical_alignment="center")

            with col_b1:
                rec_tool = col.get("recommended_tool")
                if rec_tool:
                    st.markdown(f"**Recommended Tool:** <span class='badge-pill badge-primary'>{html.escape(rec_tool)}</span>", unsafe_allow_html=True)
                else:
                    st.markdown("<span style='font-size: 12px; color: #10B981;'>✓ No immediate cleaning required for this column.</span>", unsafe_allow_html=True)

            with col_b2:
                ask_btn_key = f"ai_ask_col_{col_name}"
                if st.button(
                    f"💬 Ask AI about `{col_name}`",
                    use_container_width=True,
                    type="secondary",
                    key=ask_btn_key,
                    disabled=TEMP_DISABLE_AI_ANALYSIS,
                    help="Temporarily disabled during AI API Connectivity Test Mode.",
                ):
                    inq_prompt = format_column_drilldown_prompt(col, profile.get("table_name", "target"))
                    user_msg = ChatMessage(role="user", content=inq_prompt, timestamp=time.strftime("%H:%M"))
                    st.session_state.ai_chat_messages.append(user_msg)

                    if active_config and st.session_state.get("ai_config_saved"):
                        with st.spinner(f"Analyzing column `{col_name}` with {active_config.model}..."):
                            grounded_sys = get_ai_system_prompt_with_evidence(profile)
                            ok, ans = send_chat_message(
                                config=active_config,
                                messages=st.session_state.ai_chat_messages,
                                system_prompt=grounded_sys,
                                timeout=35.0,
                            )
                        if ok:
                            bot_msg = ChatMessage(role="assistant", content=ans, timestamp=time.strftime("%H:%M"))
                        else:
                            bot_msg = ChatMessage(role="assistant", content=f"⚠️ {ans}", timestamp=time.strftime("%H:%M"))
                        st.session_state.ai_chat_messages.append(bot_msg)
                    else:
                        # Local deterministic explanation
                        local_exp = (
                            f"### Data Quality Analysis for `{col_name}`\n\n"
                            f"**Confirmed Findings:**\n"
                            f"- **Logical Type:** `{col['logical_type']}` (declared `{col['physical_type']}`)\n"
                            f"- **Missing:** {col['null_count']:,} NULLs ({col['null_pct']}%), {col['empty_count']:,} empty strings\n"
                            f"- **Whitespace Anomalies:** {col['whitespace_issues']:,}\n"
                            f"- **Distinct Cardinality:** {col['unique_count']:,}\n"
                        )
                        if col.get("recommended_tool"):
                            local_exp += f"\n**Recommended Action:** Navigate to the **{col['recommended_tool']}** module in DataClean Studio to standardize this column.\n"
                        local_exp += "\n*Note: Configure your AI provider in the left sidebar to ask natural language questions and investigate potential root causes.*"
                        st.session_state.ai_chat_messages.append(ChatMessage(role="assistant", content=local_exp, timestamp=time.strftime("%H:%M")))

                    st.rerun()


def render_ai_assistant_main(on_back_to_hub: Optional[Callable[[], None]] = None) -> None:
    """
    Renders the Main Content Area AI Assistant interface.
    Features:
    - Main heading "DataClean AI Assistant"
    - Database Context section (connection, table selector, isolation badges, Analyze button)
    - Data Quality Profiling Overview (Score, KPIs, Severities, Executive Assessment)
    - Interactive Column Drilldown with "Ask AI about this column"
    - Scrollable conversation history grounded in profiling evidence
    - Chat input with Ctrl+Enter shortcut
    """
    init_ai_session_state()
    st.markdown(f"<style>{get_ai_assistant_css()}</style>", unsafe_allow_html=True)
    st.markdown(get_ctrl_enter_script(), unsafe_allow_html=True)

    active_config: Optional[AIProviderConfig] = st.session_state.get("ai_config")
    is_saved = st.session_state.get("ai_config_saved", False)
    messages: List[ChatMessage] = st.session_state.get("ai_chat_messages", [])
    engine = st.session_state.get("engine")

    # 1. Chat Header Bar
    h_col1, h_col2, h_col3 = st.columns([3, 1.2, 1.2], vertical_alignment="center")
    with h_col1:
        sparkle_icon = get_icon_svg("sparkles", size=20, color="#0F766E")
        if is_saved and active_config:
            prov_name = SUPPORTED_PROVIDERS.get(active_config.provider, {}).get("name", active_config.provider)
            status_text = f"<span class='badge-pill badge-success'>Active: {prov_name} ({active_config.model})</span>"
        else:
            status_text = "<span class='badge-pill badge-warning'>AI Not Configured</span>"

        render_html(f"""
        <div class="dc-ai-chat-header-bar">
            <div class="dc-ai-chat-title-group">
                {sparkle_icon}
                <h2 class="dc-ai-chat-main-title">DataClean AI Assistant</h2>
                {status_text}
            </div>
        </div>
        """)

    with h_col2:
        if st.button(
            "New conversation",
            use_container_width=True,
            type="secondary",
            key="ai_main_new_chat_btn",
            help="Reset conversation history and start a fresh session.",
        ):
            st.session_state.ai_chat_messages = []
            st.rerun()

    with h_col3:
        if st.button(
            "Back to Hub",
            use_container_width=True,
            type="secondary",
            key="ai_main_back_hub_btn",
            help="Return to DataClean Studio Cleaning Hub",
        ):
            if callable(on_back_to_hub):
                on_back_to_hub()
            else:
                st.session_state.workspace_sub_tab = "🏠 Cleaning Hub"
                st.session_state._ws_sub_radio = "🏠 Cleaning Hub"
                st.query_params["workspace_sub_tab"] = "🏠 Cleaning Hub"
                st.rerun()

    # 2. Database Context Card & Profiling Trigger
    chosen_db, chosen_tbl, is_ws = render_ai_database_context_card(engine, active_config)

    # 3. Profiling Results & Column Drilldown (if profile available)
    profile = st.session_state.get("ai_table_profile")
    if profile:
        render_ai_profiling_overview(profile, active_config)
        render_ai_column_drilldown(profile, active_config)

    # 4. Chatbot Conversation Section
    st.markdown("<hr style='margin: 24px 0 16px 0; border: none; border-top: 1px solid #E2E8F0;'>", unsafe_allow_html=True)
    st.markdown("#### 💬 Intelligent Assistant Chat")

    # Welcome Message Box (shown when conversation is empty)
    if not messages:
        shield_icon = get_icon_svg("shield_check", size=18, color="#0F766E")
        has_profile = profile is not None
        table_label = f"table `{profile['table_name']}`" if has_profile else "your connected data"

        render_html(f"""
        <div class="dc-ai-welcome-box">
            <div class="dc-ai-welcome-title">
                {shield_icon}
                <span>DataClean Intelligent Assistant</span>
            </div>
            <div class="dc-ai-welcome-text">
                Ask questions about data quality issues, cleaning strategies, regular expressions, or transformation rules.
                {f"The assistant is grounded in the active profiling evidence for {table_label}." if has_profile else "Connect to a MySQL database above to analyze live tables."}
            </div>
            <div style="font-size: 12px; font-weight: 600; color: #64748B; margin-top: 8px;">Suggested questions:</div>
            <div class="dc-ai-quick-prompts">
                <span class="dc-ai-prompt-chip">🔍 Which columns have the most missing values?</span>
                <span class="dc-ai-prompt-chip">📊 Why is the overall quality score low?</span>
                <span class="dc-ai-prompt-chip">💡 Which cleaning feature should I run next?</span>
                <span class="dc-ai-prompt-chip">🛡️ How does zero-production-risk data staging work?</span>
            </div>
        </div>
        """)

    # Scrollable Conversation History Area
    chat_container = st.container()
    with chat_container:
        for msg in messages:
            avatar = "👤" if msg.role == "user" else "🤖"
            with st.chat_message(msg.role, avatar=avatar):
                st.markdown(msg.content)
                if msg.timestamp:
                    st.caption(f"Sent at {msg.timestamp}")

    # Message Input at Bottom
    can_chat = bool(is_saved and active_config)
    is_processing = st.session_state.get("ai_is_processing", False)

    if not can_chat:
        st.info("💡 Configure and save your AI provider in the left sidebar to enable live chat.")

    input_placeholder = (
        "Ask a question about this dataset or data cleaning... (Press Enter or Ctrl+Enter)"
        if can_chat
        else "Configure and save your AI provider on the left to start chatting..."
    )

    prompt = st.chat_input(
        placeholder=input_placeholder,
        disabled=(not can_chat or is_processing),
        key="ai_main_chat_input",
    )

    if prompt:
        prompt_text = prompt.strip()
        if prompt_text:
            # Append user message
            user_msg = ChatMessage(role="user", content=prompt_text, timestamp=time.strftime("%H:%M"))
            st.session_state.ai_chat_messages.append(user_msg)

            # Display immediately in chat container
            with chat_container:
                with st.chat_message("user", avatar="👤"):
                    st.markdown(prompt_text)

            # Generate AI response
            st.session_state.ai_is_processing = True
            with chat_container:
                with st.chat_message("assistant", avatar="🤖"):
                    with st.spinner(f"{active_config.model} is responding..."):
                        system_context = get_ai_system_prompt_with_evidence(profile)
                        success, reply_or_err = send_chat_message(
                            config=active_config,
                            messages=st.session_state.ai_chat_messages,
                            system_prompt=system_context,
                            timeout=40.0,
                        )

                    if success:
                        st.markdown(reply_or_err)
                        bot_msg = ChatMessage(role="assistant", content=reply_or_err, timestamp=time.strftime("%H:%M"))
                        st.session_state.ai_chat_messages.append(bot_msg)
                    else:
                        st.error(reply_or_err)
                        err_msg = ChatMessage(
                            role="assistant",
                            content=f"⚠️ **Request Failed:** {reply_or_err}\n\nPlease check your configuration in the sidebar and try again.",
                            timestamp=time.strftime("%H:%M"),
                        )
                        st.session_state.ai_chat_messages.append(err_msg)

            st.session_state.ai_is_processing = False
            st.rerun()


def render_ai_assistant_page(on_back_to_hub: Optional[Callable[[], None]] = None) -> None:
    """
    Renders the dedicated AI Assistant page with:
    - Left sidebar: AI Configuration panel
    - Main content area: AI Chatbot, Database Context, and Profiling Analysis
    """
    with st.sidebar:
        render_ai_config_sidebar(on_back_to_hub=on_back_to_hub)
    render_ai_assistant_main(on_back_to_hub=on_back_to_hub)
