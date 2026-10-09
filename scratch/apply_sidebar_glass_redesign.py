import re

with open("app.py", "r", encoding="utf-8") as f:
    content = f.read()

# ----------------------------------------------------------------------
# 1. Update CSS in inject_global_css
# ----------------------------------------------------------------------

sidebar_css = """    /* Sidebar: Premium Glassmorphism panel, fixed 300px desktop width */
    [data-testid="stSidebar"] {
        min-width: 300px !important;
        max-width: 300px !important;
        width: 300px !important;
        background: 
            radial-gradient(circle at 20% 10%, rgba(59, 130, 246, 0.16), transparent 35%),
            radial-gradient(circle at 90% 80%, rgba(37, 99, 235, 0.10), transparent 40%),
            rgba(13, 27, 52, 0.62) !important;
        backdrop-filter: blur(24px) saturate(140%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(140%) !important;
        border-right: 1px solid rgba(148, 163, 184, 0.16) !important;
        border-radius: 0 !important;
        margin: 0 !important;
        box-shadow: 0 20px 50px rgba(0, 0, 0, 0.30) !important;
        transition: width 280ms ease, min-width 280ms ease, max-width 280ms ease !important;
    }

    [data-testid="stSidebar"] > div:first-child {
        padding: 20px 20px 28px 20px !important;
        height: 100vh !important;
        overflow-y: auto !important;
        box-sizing: border-box !important;
    }

    /* Thin unobtrusive scrollbar */
    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar {
        width: 5px !important;
    }

    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-track {
        background: transparent !important;
    }

    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb {
        background: rgba(148, 163, 184, 0.20) !important;
        border-radius: 9999px !important;
    }

    [data-testid="stSidebar"] > div:first-child::-webkit-scrollbar-thumb:hover {
        background: rgba(59, 130, 246, 0.40) !important;
    }

    /* Reset nested container padding/borders to prevent box-inside-box */
    [data-testid="stSidebar"] [data-testid="stVerticalBlockBorderWrapper"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        padding: 0 !important;
        margin: 0 !important;
    }

    /* Sidebar Header & Brand */
    .sidebar-header-row {
        display: flex;
        align-items: center;
        gap: 12px;
        padding-bottom: 16px;
    }

    .sidebar-brand-icon {
        display: flex;
        align-items: center;
        justify-content: center;
        width: 36px;
        height: 36px;
        border-radius: 10px;
        background: rgba(59, 130, 246, 0.14);
        border: 1px solid rgba(59, 130, 246, 0.28);
        font-size: 1.25rem;
        flex-shrink: 0;
    }

    .sidebar-brand-title {
        font-size: 16px;
        font-weight: 600;
        color: #E8ECF4;
        line-height: 1.2;
    }

    .sidebar-brand-sub {
        font-size: 12px;
        color: #94A3B8;
        margin-top: 2px;
    }

    .sidebar-header-divider {
        height: 1px;
        background: rgba(148, 163, 184, 0.14);
        margin-bottom: 20px;
        width: 100%;
    }

    /* Floating Glass Collapse Button */
    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarHeader"] button {
        width: 32px !important;
        height: 32px !important;
        min-height: 32px !important;
        border-radius: 8px !important;
        background: rgba(59, 130, 246, 0.08) !important;
        border: 1px solid rgba(148, 163, 184, 0.12) !important;
        color: #B4BFD3 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
        padding: 0 !important;
        transition: all 150ms ease !important;
    }

    [data-testid="stSidebarCollapseButton"] button:hover,
    [data-testid="stSidebarHeader"] button:hover {
        background: rgba(59, 130, 246, 0.18) !important;
        border-color: rgba(59, 130, 246, 0.35) !important;
        color: #FFFFFF !important;
    }

    [data-testid="stSidebarCollapsedControl"] button {
        width: 36px !important;
        height: 36px !important;
        border-radius: 8px !important;
        background: rgba(13, 27, 52, 0.85) !important;
        border: 1px solid rgba(148, 163, 184, 0.20) !important;
        backdrop-filter: blur(12px) !important;
        color: #5B9BFF !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.35) !important;
        transition: all 150ms ease !important;
    }

    [data-testid="stSidebarCollapsedControl"] button:hover {
        background: rgba(30, 52, 86, 0.90) !important;
        border-color: rgba(59, 130, 246, 0.50) !important;
        color: #FFFFFF !important;
        transform: scale(1.05) !important;
    }

    /* Section Headings */
    .sidebar-section-header {
        font-size: 14px !important;
        font-weight: 600 !important;
        color: #E8ECF4 !important;
        margin-top: 4px !important;
        margin-bottom: 4px !important;
        display: flex !important;
        align-items: center !important;
        gap: 6px !important;
    }

    .sidebar-section-desc {
        font-size: 11px !important;
        color: #94A3B8 !important;
        line-height: 1.45 !important;
        margin-bottom: 14px !important;
    }

    /* Unified Form Elements Grid & Perfect Baseline Alignment */
    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"] {
        align-items: flex-start !important;
        gap: 10px !important;
        margin-bottom: 0 !important;
    }

    [data-testid="stSidebar"] [data-testid="stColumn"] {
        vertical-align: top !important;
        padding: 0 !important;
    }

    [data-testid="stSidebar"] [data-testid="stColumn"] > div {
        padding-top: 0 !important;
        margin-top: 0 !important;
    }

    [data-testid="stSidebar"] [data-testid="stTextInput"],
    [data-testid="stSidebar"] [data-testid="stNumberInput"] {
        margin-top: 0 !important;
        padding-top: 0 !important;
        margin-bottom: 14px !important;
    }

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        width: 100% !important;
        height: 22px !important;
        min-height: 22px !important;
        margin-top: 0 !important;
        margin-bottom: 6px !important;
    }

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] label,
    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] p {
        font-size: 12px !important;
        font-weight: 500 !important;
        color: #E8ECF4 !important;
        line-height: 22px !important;
        margin: 0 !important;
        padding: 0 !important;
    }

    [data-testid="stSidebar"] [data-testid="stTooltipIcon"] {
        margin-left: auto !important;
        color: #64748B !important;
    }

    /* Inputs: 40px Glass Container */
    [data-testid="stSidebar"] [data-testid="stTextInput"] div[data-baseweb="input"],
    [data-testid="stSidebar"] [data-testid="stNumberInput"] [data-testid="stNumberInputContainer"] {
        height: 40px !important;
        min-height: 40px !important;
        max-height: 40px !important;
        background: rgba(30, 52, 86, 0.55) !important;
        border: 1px solid rgba(148, 163, 184, 0.16) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border-radius: 8px !important;
        box-sizing: border-box !important;
        transition: border-color 150ms ease, box-shadow 150ms ease !important;
        overflow: hidden !important;
    }

    [data-testid="stSidebar"] [data-testid="stTextInput"] div[data-baseweb="input"]:focus-within,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] [data-testid="stNumberInputContainer"]:focus-within {
        border-color: rgba(59, 130, 246, 0.70) !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.12) !important;
    }

    [data-testid="stSidebar"] [data-testid="stTextInput"] input,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input {
        height: 38px !important;
        min-height: 38px !important;
        max-height: 38px !important;
        line-height: 38px !important;
        background: transparent !important;
        border: none !important;
        color: #E8ECF4 !important;
        font-size: 13px !important;
        padding: 0 10px !important;
        box-shadow: none !important;
        outline: none !important;
        box-sizing: border-box !important;
    }

    /* Hide stepper buttons in sidebar for sleek clean numeric alignment */
    [data-testid="stSidebar"] [data-testid="stNumberInput"] button {
        display: none !important;
    }

    /* Expander: Clean 1-border glass surface */
    [data-testid="stSidebar"] [data-testid="stExpander"] {
        width: 100% !important;
        border: 1px solid rgba(148, 163, 184, 0.16) !important;
        border-radius: 8px !important;
        background: rgba(30, 52, 86, 0.35) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        margin-top: 10px !important;
        margin-bottom: 14px !important;
        box-shadow: none !important;
        overflow: hidden !important;
    }

    [data-testid="stSidebar"] [data-testid="stExpander"] details {
        border: none !important;
    }

    [data-testid="stSidebar"] [data-testid="stExpander"] summary {
        min-height: 42px !important;
        padding: 8px 12px !important;
        font-size: 13px !important;
        color: #B4BFD3 !important;
        font-weight: 500 !important;
        border: none !important;
        display: flex !important;
        align-items: center !important;
    }

    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {
        color: #E8ECF4 !important;
        background: rgba(59, 130, 246, 0.08) !important;
    }

    /* Action Buttons: Equal 42px Height, Equal Width, Complete Visible Labels */
    div[class*="st-key-sb_test"] button,
    div[class*="st-key-sb_connect"] button {
        height: 42px !important;
        min-height: 42px !important;
        font-size: 12.5px !important;
        font-weight: 600 !important;
        border-radius: 9px !important;
        white-space: nowrap !important;
        text-overflow: clip !important;
        transition: all 150ms ease !important;
        padding: 0 4px !important;
        box-sizing: border-box !important;
        width: 100% !important;
    }

    div[class*="st-key-sb_test"] button {
        background: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%) !important;
        background-image: linear-gradient(135deg, #2563EB 0%, #3B82F6 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(59, 130, 246, 0.40) !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.25) !important;
    }

    div[class*="st-key-sb_test"] button:hover {
        filter: brightness(1.10) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.35) !important;
    }

    div[class*="st-key-sb_test"] button:active {
        transform: translateY(1px) scale(0.98) !important;
    }

    div[class*="st-key-sb_connect"] button {
        background: linear-gradient(135deg, #3B82F6 0%, #6366F1 100%) !important;
        background-image: linear-gradient(135deg, #3B82F6 0%, #6366F1 100%) !important;
        border: 1px solid rgba(99, 102, 241, 0.40) !important;
        color: #FFFFFF !important;
        box-shadow: 0 4px 14px rgba(59, 130, 246, 0.25) !important;
    }

    div[class*="st-key-sb_connect"] button:hover {
        filter: brightness(1.10) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px rgba(59, 130, 246, 0.35) !important;
    }

    div[class*="st-key-sb_connect"] button:active {
        transform: translateY(1px) scale(0.98) !important;
    }

    /* Sidebar Data Profiling Buttons */
    div[class*="st-key-sb_prof_"] button {
        height: 40px !important;
        min-height: 40px !important;
        font-size: 12.5px !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        white-space: nowrap !important;
        text-overflow: clip !important;
        padding: 0 8px !important;
        margin-bottom: 8px !important;
        background: linear-gradient(135deg, #1E3A8A 0%, #2563EB 100%) !important;
        color: #FFFFFF !important;
        border: 1px solid rgba(59, 130, 246, 0.30) !important;
        box-shadow: 0 4px 14px rgba(37, 99, 235, 0.20) !important;
        transition: all 150ms ease !important;
    }

    div[class*="st-key-sb_prof_"] button:hover:not(:disabled) {
        filter: brightness(1.12) !important;
        transform: translateY(-1px) !important;
        box-shadow: 0 6px 18px rgba(37, 99, 235, 0.30) !important;
    }

    /* Sidebar Status Card */
    .sidebar-status-card {
        width: 100% !important;
        box-sizing: border-box !important;
        margin-top: 16px !important;
        margin-bottom: 16px !important;
        padding: 14px 16px !important;
        background: rgba(20, 40, 70, 0.42) !important;
        border: 1px solid rgba(148, 163, 184, 0.14) !important;
        border-radius: 14px !important;
        backdrop-filter: blur(12px) !important;
        -webkit-backdrop-filter: blur(12px) !important;
        box-shadow: 0 4px 16px rgba(0, 0, 0, 0.20) !important;
    }

    .sidebar-status-header {
        display: flex;
        align-items: center;
        gap: 8px;
        font-size: 13px;
        font-weight: 600;
    }

    .sidebar-status-title-connected {
        color: #22C55E;
        font-size: 13px;
        font-weight: 600;
    }

    .sidebar-status-title-disconnected {
        color: #EF4444;
        font-size: 13px;
        font-weight: 600;
    }

    .sidebar-status-dot {
        width: 8px;
        height: 8px;
        border-radius: 50%;
        display: inline-block;
        flex-shrink: 0;
    }

    .sidebar-status-dot.dot-connected {
        background: #22C55E;
        box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
        animation: pulseStatusGreen 2.5s infinite;
    }

    .sidebar-status-dot.dot-disconnected {
        background: #EF4444;
        box-shadow: 0 0 6px rgba(239, 68, 68, 0.45);
    }

    .sidebar-status-chip {
        margin-left: auto;
        font-size: 10px;
        font-weight: 600;
        padding: 2px 7px;
        border-radius: 4px;
        background: rgba(34, 197, 94, 0.15);
        color: #22C55E;
        border: 1px solid rgba(34, 197, 94, 0.25);
        text-transform: uppercase;
    }

    .sidebar-status-meta {
        font-size: 12px;
        color: #94A3B8;
        margin-top: 8px;
        line-height: 1.5;
    }"""

# Replace lines 287 to 560
old_sidebar_css_pattern = r'/\* Sidebar: Solid surface, 320px anchored panel \*/.*?\.sidebar-status-meta \{\s+font-size: 13px;.*?\n\s+\}'
if not re.search(old_sidebar_css_pattern, content, re.DOTALL):
    # Try alternative matching
    old_sidebar_css_pattern = r'/\* Sidebar: Glassmorphism panel, 300px width \*/.*?\.sidebar-status-meta \{\s+font-size: 13px;.*?\n\s+\}'
assert re.search(old_sidebar_css_pattern, content, re.DOTALL), "Sidebar CSS pattern not found"
content = re.sub(old_sidebar_css_pattern, sidebar_css, content, flags=re.DOTALL)

# ----------------------------------------------------------------------
# 2. Update render_sidebar_brand()
# ----------------------------------------------------------------------

old_brand_pattern = r'def render_sidebar_brand\(\) -> None:.*?render_html\("""\s+<div class="sidebar-brand-block">.*?</div>\s+"""\)'
new_brand_fn = '''def render_sidebar_brand() -> None:
    """Renders HTML for the top brand header block in the sidebar."""
    render_html("""
    <div class="sidebar-header-row">
        <div class="sidebar-brand-icon">🛡️</div>
        <div>
            <div class="sidebar-brand-title">DataClean Studio</div>
            <div class="sidebar-brand-sub">Connection Manager</div>
        </div>
    </div>
    <div class="sidebar-header-divider"></div>
    """)'''
assert re.search(old_brand_pattern, content, re.DOTALL), "Brand pattern not found"
content = re.sub(old_brand_pattern, new_brand_fn, content, flags=re.DOTALL)

# ----------------------------------------------------------------------
# 3. Update with st.sidebar block (lines ~2240 to ~2560)
# ----------------------------------------------------------------------

old_sidebar_block_pattern = r'with st\.sidebar:\s+render_sidebar_brand\(\).*?if has_selected_table:.*?nav_to_view\("Source Table"\)\s+st\.rerun\(\)\s+except Exception as e:\s+st\.error\(f"Profiling error: \{str\(e\)\}"\)'

new_sidebar_block = '''with st.sidebar:
    render_sidebar_brand()

    if st.session_state.connected:
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

        if st.button("Disconnect", use_container_width=True, type="primary", key="sb_disconnect_btn"):
            remove_connection_session()
            st.session_state.active_view = "Source Table"
            st.rerun()

        with st.expander("🔁 Switch Connection", expanded=False):
            col_sh, col_sp = st.columns([2.8, 1.2], gap="small", vertical_alignment="top")
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
                value="Suyash@para9",
                placeholder="(default: Suyash@para9)",
                key="sb_pass_input",
            )
            with st.expander("⚙️ Advanced Options", expanded=False):
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
                    use_container_width=True,
                    key="sb_connect_btn",
                )

        render_sidebar_status_card(
            connected=True,
            host=f"{_c_host}:{_c_port}",
            username=_c_user,
            server_ver=_server_ver,
        )

        # ── Data Profiling Section ──────────────────────────────
        render_html("""
        <div class="sidebar-section-header" style="margin-top: 18px;">📊 Data Profiling</div>
        <div class="sidebar-section-desc">Generate deep quality audits across raw source data and isolated sandbox workspaces.</div>
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
                    st.error(sp_msg)

            # 2. Data Profile for Workspace Table
            if active_ws_table:
                is_ws_active = (
                    st.session_state.get("show_profile_dialog")
                    and st.session_state.get("active_profile_target") == "workspace"
                )
                if st.button(
                    "Data Profile for Workspace",
                    use_container_width=True,
                    type="primary" if is_ws_active else "secondary",
                    key="sb_prof_ws_btn",
                    help=f"Open floating Data Quality Profile window for staged workspace table `{db_for_prof}`.`{active_ws_table}`.",
                ):
                    with st.spinner(
                        f"Auditing workspace table `{db_for_prof}`.`{active_ws_table}`..."
                    ):
                        wp_ok, wp_msg, wp_profile = profile_workspace_table(
                            st.session_state.engine,
                            db_for_prof,
                            active_ws_table,
                        )
                    if wp_ok:
                        st.session_state.profile_result = wp_profile
                        st.session_state.active_profile_target = "workspace"
                        st.session_state.show_profile_dialog = True
                        st.rerun()
                    else:
                        st.error(wp_msg)
            else:
                st.button(
                    "Data Profile for Workspace",
                    use_container_width=True,
                    disabled=True,
                    key="sb_prof_ws_btn_no_ws",
                    help="No active workspace found for this table. Create one in the Table Explorer to profile staged data.",
                )
    else:
        # ── Full connection form (disconnected) ──────────────────
        render_html("""
        <div class="sidebar-section-header">🗄️ Database Connection</div>
        <div class="sidebar-section-desc">Connect to your MySQL database to manage and clean data.</div>
        """)

        # Host & Port on one row with 70/30 ratio and aligned top baseline
        col_host, col_port = st.columns([2.8, 1.2], gap="small", vertical_alignment="top")
        with col_host:
            host = st.text_input(
                "Host / IP Address",
                value=st.session_state.conn_config.get("host", "localhost"),
                placeholder="localhost",
                key="sb_host_input_main",
                help="Host domain or IP address of your MySQL database server.",
            )
        with col_port:
            port = st.number_input(
                "Port",
                value=st.session_state.conn_config.get("port", 3306),
                step=1,
                help="Default MySQL server port is 3306.",
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
            value=st.session_state.conn_config.get("password", "Suyash@para9"),
            placeholder="(default: Suyash@para9)",
            key="sb_pass_input_main",
        )

        with st.expander("⚙️ Advanced Connection Options", expanded=False):
            include_system_dbs = st.checkbox(
                "Include System Databases",
                value=False,
                help="Show internal schemas like mysql, sys, performance_schema.",
                key="sb_adv_sys_dbs_main",
            )
            st.caption("Auto‑idle session timeout: **20 minutes**")

        st.markdown('<div style="height: 6px;"></div>', unsafe_allow_html=True)

        # Action Buttons: equal two columns (42px height, no text truncation)
        col_test, col_connect = st.columns(2, gap="small")
        with col_test:
            test_btn = st.button(
                "Test Connection",
                use_container_width=True,
                key="sb_test_main_btn",
            )
        with col_connect:
            connect_btn = st.button(
                "Connect Database",
                use_container_width=True,
                key="sb_connect_main_btn",
            )

        # Pinned Connection Status Card
        render_sidebar_status_card(connected=False)

    # ── Dark Mode Toggle at Bottom ──────────────────────────────
    theme_toggle()

    # --------------------------------------------------------
    # Action Handlers: Test Connection
    # --------------------------------------------------------
    if test_btn:
        if not host or not username:
            st.error("Host and Username are required.")
            st.toast("Host and Username are required.", icon="⚠️")
        else:
            with st.spinner("Testing connection..."):
                success, msg = MySQLConnectionManager.test_connection(
                    host, int(port), username, password
                )
            if success:
                st.toast("Connection successful!", icon="✅")
                st.success(f"{msg}")
            else:
                st.toast("Connection test failed.", icon="❌")
                st.error(f"{msg}")

    # --------------------------------------------------------
    # Action Handlers: Connect
    # --------------------------------------------------------
    if connect_btn:
        if not host or not username:
            st.error("Host and Username are required.")
            st.toast("Host and Username are required.", icon="⚠️")
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
                    st.query_params["connection_token"] = token
                    st.session_state.selected_db = None
                    st.session_state.selected_table = None
                    reset_workspace_state()
                    st.session_state.active_view = "Source Table"
                    st.toast("Connected to MySQL instance!", icon="🚀")
                    st.success("Successfully connected!")
                    st.rerun()
                except Exception as e:
                    st.session_state.connected = False
                    st.toast("Failed to initialize engine.", icon="❌")
                    st.error(f"Failed to initialize engine: {str(e)}")
            else:
                st.session_state.connected = False
                st.toast("Connection failed.", icon="❌")
                st.error(f"Connection failed: {msg}")'''

assert re.search(old_sidebar_block_pattern, content, re.DOTALL), "Sidebar block pattern not matched"
content = re.sub(old_sidebar_block_pattern, new_sidebar_block, content, flags=re.DOTALL)

with open("app.py", "w", encoding="utf-8") as f:
    f.write(content)

print("SUCCESSFULLY APPLIED SIDEBAR GLASS REDESIGN")

