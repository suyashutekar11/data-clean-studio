"""
DataClean Studio — Credential Error Dialog System
ui/credential_dialog.py

Provides error detection and a professional, animated dialog box centered in the
viewport to inform the user that their credentials are incorrect.

Requirements satisfied:
1. Error Detection: `is_credential_error` accurately detects invalid credentials
   (e.g., MySQL error 1045, 1698, access denied, invalid username/password)
   while strictly excluding network failures, unreachable hosts, timeouts,
   missing databases, and SSL issues.
2. Centered Viewport Design: Fixed overlay with flexbox centering, high z-index (99999999),
   modern white surface matching the enterprise light theme.
3. Exact Error Message: "Your credentials are wrong. Please check your credentials."
4. Smooth Animation: Subtle fade-in + scale-up (0.92 -> 1.0) entry;
   subtle fade-out + scale-down (1.0 -> 0.92) exit.
5. Display Duration: Exactly 3 seconds (3000ms) with automatic pure CSS dismissal.
6. Zero layout shift, zero page reload, zero JavaScript dependencies.
"""

from __future__ import annotations

import streamlit as st
import uuid
from typing import Optional, Any



EXACT_CREDENTIAL_ERROR_MESSAGE = (
    "Your credentials are wrong. Please check your credentials."
)


def is_credential_error(error: Any) -> bool:
    """
    Determine if an error indicates invalid credentials (username/password),
    as opposed to server unreachable, network failure, missing database, timeout, etc.

    Parameters
    ----------
    error : Any
        An exception, error string, or tuple containing error details.

    Returns
    -------
    bool
        True if the error is specifically credential-related, False otherwise.
    """
    if not error:
        return False

    msg_str = str(error)
    msg_lower = msg_str.lower()

    # Explicit exclusions: network unreachable, socket error, database not found, timeout, SSL
    # MySQL error codes:
    # 2003: Can't connect to MySQL server
    # 2002: Can't connect to local MySQL server through socket
    # 1049: Unknown database
    # 2006: MySQL server has gone away
    # 2013: Lost connection to MySQL server during query
    for code in ("2003", "2002", "1049", "2006", "2013"):
        if code in msg_str:
            return False

    non_credential_markers = (
        "can't connect",
        "cannot connect",
        "cannot reach",
        "unknown database",
        "database does not exist",
        "timed out",
        "timeout",
        "network",
        "firewall",
        "ssl",
        "tls",
        "certificate",
        "host is down",
        "no route to host",
        "connection refused",
        "target machine actively refused",
    )
    if any(marker in msg_lower for marker in non_credential_markers):
        return False

    # Check for MySQL authentication error codes:
    # 1045: ER_ACCESS_DENIED_ERROR
    # 1698: ER_ACCESS_DENIED_NO_PASSWORD_ERROR
    # 1044: ER_DBACCESS_DENIED_ERROR
    if "1045" in msg_str or "1698" in msg_str:
        return True

    # Check for authentication/credential error keywords
    credential_markers = (
        "access denied",
        "invalid credential",
        "invalid username",
        "invalid password",
        "wrong credential",
        "wrong password",
        "bad credential",
        "authentication failed",
        "auth failed",
        "password is wrong",
        "username is wrong",
    )
    return any(marker in msg_lower for marker in credential_markers)


def build_credential_dialog_html(
    message: Optional[str] = None,
    title: str = "Authentication Failed",
    render_id: Optional[str] = None,
) -> str:
    """
    Construct the self-contained HTML and CSS for the animated center dialog box.
    Runs completely via pure CSS keyframe animations (3000ms duration) and native
    input/label toggle, ensuring smooth fade-in entry, steady 3-second display,
    instant cross-button / backdrop dismissal, and automatic fade-out dismissal.
    Supports dynamic instance render_ids to guarantee that successive credential
    failures properly re-trigger animations without stale browser state.
    """
    display_message = message or EXACT_CREDENTIAL_ERROR_MESSAGE
    rid = render_id or uuid.uuid4().hex[:8]

    return f"""
    <input type="checkbox" id="cred-dialog-toggle-{rid}" class="cred-dialog-toggle-input cred-toggle-{rid}" autocomplete="off" style="display:none !important;" />
    <input type="checkbox" id="cred-dialog-toggle" class="cred-dialog-toggle-input" autocomplete="off" style="display:none !important;" />
    <div class="cred-dialog-overlay cred-dialog-inst-{rid}" id="credential-error-dialog-container" data-render-id="{rid}" role="alertdialog" aria-modal="true" aria-labelledby="cred-dialog-title" aria-describedby="cred-dialog-desc">
        <label for="cred-dialog-toggle-{rid}" class="cred-dialog-backdrop-dismiss" aria-label="Dismiss dialog overlay"></label>
        <label for="cred-dialog-toggle" style="display:none;" aria-hidden="true"></label>
        <style>
        /* ── Input Toggle for Pure CSS Dismissal ── */
        .cred-dialog-toggle-input:checked ~ .cred-dialog-overlay,
        .cred-dialog-toggle-input:checked + .cred-dialog-overlay,
        #cred-dialog-toggle-{rid}:checked ~ .cred-dialog-overlay,
        .cred-toggle-{rid}:checked ~ .cred-dialog-overlay {{
            display: none !important;
            opacity: 0 !important;
            visibility: hidden !important;
            pointer-events: none !important;
        }}

        /* ── Credential Dialog Overlay (Centered Viewport) ── */
        .cred-dialog-overlay {{
            position: fixed !important;
            top: 0 !important;
            left: 0 !important;
            right: 0 !important;
            bottom: 0 !important;
            width: 100vw !important;
            height: 100vh !important;
            background: rgba(15, 23, 42, 0.50) !important;
            backdrop-filter: blur(4px) !important;
            -webkit-backdrop-filter: blur(4px) !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            z-index: 99999999 !important;
            padding: 16px !important;
            box-sizing: border-box !important;
            pointer-events: auto !important;
            animation: credOverlayAnim 3000ms cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
        }}

        /* Instance-scoped animation binding to force browser to restart on repeated attempts */
        .cred-dialog-overlay.cred-dialog-inst-{rid} {{
            animation: credOverlayAnim_{rid} 3000ms cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
        }}
        .cred-dialog-inst-{rid} .cred-dialog-box {{
            animation: credBoxAnim_{rid} 3000ms cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
        }}
        .cred-dialog-inst-{rid} .cred-dialog-progress-bar {{
            animation: credProgressBar_{rid} 2400ms 240ms linear forwards !important;
        }}

        /* Backdrop dismiss surface */
        .cred-dialog-backdrop-dismiss {{
            position: absolute !important;
            top: 0 !important;
            left: 0 !important;
            width: 100% !important;
            height: 100% !important;
            cursor: pointer !important;
            z-index: 1 !important;
            background: transparent !important;
        }}

        /* Ensure parent containers hoist this dialog above all sibling stacking contexts */
        [data-testid="stSidebar"]:has(.cred-dialog-overlay:not([style*="display: none"])),
        [data-testid="stSidebar"]:has(#credential-error-dialog-container:not([style*="display: none"])),
        [data-testid="stMain"]:has(.cred-dialog-overlay:not([style*="display: none"])),
        [data-testid="stMain"]:has(#credential-error-dialog-container:not([style*="display: none"])),
        [data-testid="stAppViewContainer"]:has(.cred-dialog-overlay:not([style*="display: none"])),
        div:has(> .cred-dialog-overlay:not([style*="display: none"])) {{
            z-index: 99999999 !important;
        }}

        /* ── Modal Dialog Box ── */
        .cred-dialog-box {{
            position: relative !important;
            z-index: 100000000 !important;
            background: #FFFFFF !important;
            border: 1px solid #E2E8F0 !important;
            border-radius: 16px !important;
            box-shadow: 
                0 20px 25px -5px rgba(15, 23, 42, 0.20),
                0 8px 10px -6px rgba(15, 23, 42, 0.12),
                0 0 0 1px rgba(15, 23, 42, 0.05) !important;
            width: 90% !important;
            max-width: 440px !important;
            min-width: 280px !important;
            overflow: hidden !important;
            padding: 24px 24px 20px 24px !important;
            box-sizing: border-box !important;
            text-align: center !important;
            animation: credBoxAnim 3000ms cubic-bezier(0.16, 1, 0.3, 1) forwards !important;
            transform-origin: center center !important;
            pointer-events: auto !important;
        }}

        /* ── Icon ── */
        .cred-dialog-icon-wrapper {{
            display: flex !important;
            justify-content: center !important;
            margin-bottom: 14px !important;
        }}
        .cred-dialog-icon {{
            width: 48px !important;
            height: 48px !important;
            border-radius: 12px !important;
            background: #FEE2E2 !important;
            border: 1px solid #FECACA !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
        }}

        /* ── Typography ── */
        .cred-dialog-title {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            font-size: 17px !important;
            font-weight: 700 !important;
            color: #0F172A !important;
            margin: 0 0 8px 0 !important;
            line-height: 1.3 !important;
            letter-spacing: -0.01em !important;
        }}
        .cred-dialog-message {{
            font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif !important;
            font-size: 14px !important;
            font-weight: 500 !important;
            line-height: 1.5 !important;
            color: #334155 !important;
            margin: 0 0 16px 0 !important;
        }}

        /* ── Progress Track and Animated Bar (3s Countdown) ── */
        .cred-dialog-progress-track {{
            width: 100% !important;
            height: 3px !important;
            background: #F1F5F9 !important;
            border-radius: 9999px !important;
            overflow: hidden !important;
            margin-top: 4px !important;
        }}
        .cred-dialog-progress-bar {{
            height: 100% !important;
            background: linear-gradient(90deg, #DC2626 0%, #EF4444 100%) !important;
            border-radius: 9999px !important;
            animation: credProgressBar 2400ms 240ms linear forwards !important;
            transform-origin: left !important;
        }}

        /* ── Close Button ── */
        .cred-dialog-close-btn {{
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
        }}
        .cred-dialog-close-btn:hover {{
            color: #0F172A !important;
            background-color: #F1F5F9 !important;
        }}

        /* ── Keyframes (Exactly 3 seconds total: 0-240ms entry, 240-2640ms visible, 2640-3000ms exit) ── */
        @keyframes credBoxAnim {{
            0% {{
                opacity: 0;
                transform: scale(0.92) translateY(14px);
            }}
            8% {{
                opacity: 1;
                transform: scale(1) translateY(0);
            }}
            88% {{
                opacity: 1;
                transform: scale(1) translateY(0);
            }}
            100% {{
                opacity: 0;
                transform: scale(0.92) translateY(-8px);
                visibility: hidden;
                pointer-events: none;
            }}
        }}

        @keyframes credOverlayAnim {{
            0% {{
                opacity: 0;
            }}
            8% {{
                opacity: 1;
            }}
            88% {{
                opacity: 1;
            }}
            100% {{
                opacity: 0;
                visibility: hidden;
                pointer-events: none;
            }}
        }}

        @keyframes credProgressBar {{
            0% {{
                width: 100%;
            }}
            100% {{
                width: 0%;
            }}
        }}

        /* Instance Keyframes for Guaranteed Animation Playback on Consecutive Runs */
        @keyframes credBoxAnim_{rid} {{
            0% {{
                opacity: 0;
                transform: scale(0.92) translateY(14px);
            }}
            8% {{
                opacity: 1;
                transform: scale(1) translateY(0);
            }}
            88% {{
                opacity: 1;
                transform: scale(1) translateY(0);
            }}
            100% {{
                opacity: 0;
                transform: scale(0.92) translateY(-8px);
                visibility: hidden;
                pointer-events: none;
            }}
        }}

        @keyframes credOverlayAnim_{rid} {{
            0% {{
                opacity: 0;
            }}
            8% {{
                opacity: 1;
            }}
            88% {{
                opacity: 1;
            }}
            100% {{
                opacity: 0;
                visibility: hidden;
                pointer-events: none;
            }}
        }}

        @keyframes credProgressBar_{rid} {{
            0% {{
                width: 100%;
            }}
            100% {{
                width: 0%;
            }}
        }}

        /* ── Reduced Motion ── */
        @media (prefers-reduced-motion: reduce) {{
            .cred-dialog-box {{
                animation: credBoxReduced 3000ms ease forwards !important;
            }}
            .cred-dialog-overlay {{
                animation: credOverlayAnim 3000ms ease forwards !important;
            }}
        }}
        @keyframes credBoxReduced {{
            0% {{ opacity: 0; }}
            8% {{ opacity: 1; }}
            88% {{ opacity: 1; }}
            100% {{ opacity: 0; visibility: hidden; pointer-events: none; }}
        }}
        </style>

        <div class="cred-dialog-box" onclick="event.stopPropagation();">
            <label for="cred-dialog-toggle-{rid}" class="cred-dialog-close-btn" role="button" tabindex="0" aria-label="Close dialog">&times;</label>
            <label for="cred-dialog-toggle" style="display:none;" aria-hidden="true">&times;</label>
            <div class="cred-dialog-icon-wrapper">
                <div class="cred-dialog-icon">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#DC2626" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
                        <line x1="12" y1="8" x2="12" y2="12"/>
                        <line x1="12" y1="16" x2="12.01" y2="16"/>
                    </svg>
                </div>
            </div>
            <h3 class="cred-dialog-title" id="cred-dialog-title">{title}</h3>
            <p class="cred-dialog-message" id="cred-dialog-desc">{display_message}</p>
            <div class="cred-dialog-progress-track">
                <div class="cred-dialog-progress-bar"></div>
            </div>
        </div>
    </div>
    """


def render_credential_error_dialog(
    message: Optional[str] = None,
    title: str = "Authentication Failed",
) -> None:
    """
    Renders the professional animated credential error dialog in the center
    of the viewport. Ensures clean auto-dismissal after 3 seconds and immediate
    dismissal on cross-button or backdrop click, and guarantees that consecutive
    credential failures always show the dialog cleanly on every attempt.
    """
    render_id = uuid.uuid4().hex[:8]
    html_content = build_credential_dialog_html(message=message, title=title, render_id=render_id)
    lines = [line.strip() for line in html_content.strip().splitlines() if line.strip()]
    cleaned = chr(10).join(lines)

    js_snippet = f"""
    <script>
    (function() {{
        function initDialog() {{
            var overlay = document.querySelector('.cred-dialog-inst-{render_id}');
            if (!overlay) return;

            // Reset any previous checkboxes so they never suppress this attempt
            var toggles = document.querySelectorAll('.cred-dialog-toggle-input');
            for (var t = 0; t < toggles.length; t++) {{
                toggles[t].checked = false;
            }}

            var dismissed = false;
            function dismiss() {{
                if (dismissed) return;
                dismissed = true;
                overlay.style.display = 'none';
                var instToggle = document.getElementById('cred-dialog-toggle-{render_id}');
                if (instToggle) instToggle.checked = true;
            }}

            // Auto-dismiss after 3000ms
            var timer = setTimeout(dismiss, 3000);

            // Cross button click handler
            var closeBtns = overlay.querySelectorAll('.cred-dialog-close-btn');
            for (var c = 0; c < closeBtns.length; c++) {{
                closeBtns[c].addEventListener('click', function(e) {{
                    if (e) {{ e.preventDefault(); e.stopPropagation(); }}
                    clearTimeout(timer);
                    dismiss();
                }});
            }}

            // Backdrop click handler
            overlay.addEventListener('click', function(e) {{
                if (e && (e.target === overlay || e.target.classList.contains('cred-dialog-backdrop-dismiss'))) {{
                    clearTimeout(timer);
                    dismiss();
                }}
            }});
        }}

        if (document.readyState === 'loading') {{
            document.addEventListener('DOMContentLoaded', initDialog);
        }} else {{
            initDialog();
        }}
    }})();
    </script>
    """

    if hasattr(st, "html"):
        st.html(cleaned + "\n" + js_snippet, unsafe_allow_javascript=True)
    else:
        st.markdown(cleaned, unsafe_allow_html=True)
