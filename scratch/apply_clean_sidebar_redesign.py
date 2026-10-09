import sys

with open("app.py", "r", encoding="utf-8") as f:
    lines = f.readlines()

print(f"Read {len(lines)} lines from app.py")

# 1. Locate the Sidebar CSS block in inject_global_css
# Line ~287 (starts with '    /* Sidebar: Glassmorphism panel') to line ~560 (ends with '    .sidebar-status-meta')
css_start = -1
css_end = -1
for i, line in enumerate(lines[:650]):
    if "/* Sidebar: Glassmorphism panel" in line or "/* Sidebar: Solid surface" in line:
        css_start = i
        break

if css_start == -1:
    print("ERROR: Could not locate Sidebar CSS start line")
    sys.exit(1)

for i in range(css_start, min(css_start + 350, len(lines))):
    if ".sidebar-status-meta" in lines[i]:
        # find closing brace of .sidebar-status-meta
        for j in range(i, min(i + 15, len(lines))):
            if lines[j].strip() == "}}":
                css_end = j + 1
                break
        if css_end != -1:
            break

if css_end == -1:
    print("ERROR: Could not locate Sidebar CSS end line")
    sys.exit(1)

print(f"Sidebar CSS located at lines {css_start + 1} to {css_end}")

new_sidebar_css = """    /* Sidebar: Premium Glassmorphism panel, fixed 300px desktop width */
    [data-testid="stSidebar"] {{
        min-width: 300px !important;
        max-width: 300px !important;
        width: 300px !important;
        background: 
            radial-gradient(circle at 15% 10%, rgba(59, 130, 246, 0.16), transparent 35%),
            radial-gradient(circle at 85% 85%, rgba(37, 99, 235, 0.10), transparent 40%),
            rgba(13, 27, 52, 0.65) !important;
        backdrop-filter: blur(24px) saturate(140%) !important;
        -webkit-backdrop-filter: blur(24px) saturate(140%) !important;
        border-right: 1px solid rgba(148, 163, 184, 0.16) !important;
        border-radius: 0 !important;
        margin: 0 !important;
        box-shadow: 4px 0 28px rgba(0, 0, 0, 0.28) !important;
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
        font-size: 13px !important;
        font-weight: 500 !important;
        color: #CBD5E1 !important;
        margin: 0 !important;
        line-height: 22px !important;
    }}

    [data-testid="stSidebar"] [data-testid="stWidgetLabel"] {{
        display: flex !important;
        align-items: center !important;
        justify-content: space-between !important;
        width: 100% !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTooltipIcon"] {{
        margin-left: auto !important;
        color: #64748B !important;
    }}

    [data-testid="stSidebar"] [data-baseweb="input"] {{
        height: 40px !important;
        min-height: 40px !important;
        border-radius: 8px !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTextInput"] input,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input {{
        height: 40px !important;
        min-height: 40px !important;
        line-height: 40px !important;
        background: rgba(22, 33, 58, 0.65) !important;
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        border-radius: 8px !important;
        color: #E8ECF4 !important;
        font-size: 13.5px !important;
        padding: 0 10px !important;
        transition: border-color 150ms ease, box-shadow 150ms ease !important;
    }}

    [data-testid="stSidebar"] [data-testid="stTextInput"] input:focus,
    [data-testid="stSidebar"] [data-testid="stNumberInput"] input:focus {{
        border-color: #3B82F6 !important;
        box-shadow: 0 0 0 3px rgba(59, 130, 246, 0.25) !important;
        outline: none !important;
    }}

    [data-testid="stSidebar"] [data-testid="stNumberInput"] [data-testid="stNumberInputContainer"] {{
        height: 40px !important;
        min-height: 40px !important;
        border-radius: 8px !important;
        background: rgba(22, 33, 58, 0.65) !important;
        border: 1px solid rgba(148, 163, 184, 0.18) !important;
        overflow: hidden !important;
    }}

    [data-testid="stSidebar"] [data-testid="stNumberInput"] button {{
        display: none !important;
    }}

    /* Sidebar Expander */
    [data-testid="stSidebar"] [data-testid="stExpander"] {{
        border: 1px solid rgba(148, 163, 184, 0.16) !important;
        border-radius: 8px !important;
        background: rgba(22, 33, 58, 0.45) !important;
        margin-top: 14px !important;
        margin-bottom: 14px !important;
        box-shadow: none !important;
        overflow: hidden !important;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] details {{
        border: none !important;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] summary {{
        padding: 10px 14px !important;
        font-size: 13px !important;
        color: #94A3B8 !important;
        font-weight: 500 !important;
        border: none !important;
    }}

    [data-testid="stSidebar"] [data-testid="stExpander"] summary:hover {{
        color: #E8ECF4 !important;
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
"""

# Replace CSS lines
lines = lines[:css_start] + [new_sidebar_css] + lines[css_end:]
print(f"Replaced CSS lines, total lines now: {len(lines)}")

# 2. Locate the with st.sidebar block
sb_start = -1
sb_end = -1
for i, line in enumerate(lines):
    if line.startswith("with st.sidebar:"):
        sb_start = i
        break

if sb_start == -1:
    print("ERROR: Could not locate with st.sidebar start")
    sys.exit(1)

for i in range(sb_start, len(lines)):
    if "connection_watchdog()" in lines[i]:
        # Walk back to find end of sidebar block
        # The line before '# === Inactivity Watchdog Fragment'
        for j in range(i, sb_start, -1):
            if "# Inactivity Watchdog Fragment" in lines[j]:
                # find blank line before header comment
                for k in range(j, sb_start, -1):
                    if lines[k].startswith("# ===================="):
                        sb_end = k
                        break
                break
        break

if sb_end == -1:
    print("ERROR: Could not locate with st.sidebar end")
    sys.exit(1)

print(f"with st.sidebar located at lines {sb_start + 1} to {sb_end}")

new_sidebar_python = """with st.sidebar:
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
                    type="primary",
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
        render_html(\"\"\"
        <div class="sidebar-section-header" style="margin-top: 18px;">📊 Data Profiling</div>
        <div class="sidebar-section-desc">Generate deep quality audits across raw source data and isolated sandbox workspaces.</div>
        \"\"\")

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
    else:
        # ── Full connection form (disconnected) ──────────────────
        render_html(\"\"\"
        <div class="sidebar-section-header">🗄️ Database Connection</div>
        <div class="sidebar-section-desc">Connect to your MySQL database to manage and clean data.</div>
        \"\"\")

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
                type="primary",
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
                st.error(f"Connection failed: {msg}")

"""

lines = lines[:sb_start] + [new_sidebar_python] + lines[sb_end:]
print(f"Replaced with st.sidebar block, total lines now: {len(lines)}")

with open("app.py", "w", encoding="utf-8") as f:
    f.writelines(lines)

print("SUCCESSFULLY APPLIED SIDEBAR REDESIGN!")

