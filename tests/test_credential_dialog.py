"""
Unit tests for Credential Error Detection and Animated Dialog Box.
"""

import pytest
from ui.credential_dialog import (
    is_credential_error,
    build_credential_dialog_html,
    EXACT_CREDENTIAL_ERROR_MESSAGE,
)
from app import parse_connection_error


def test_exact_error_message_constant():
    """Verify the exact required error message."""
    assert EXACT_CREDENTIAL_ERROR_MESSAGE == "Your credentials are wrong. Please check your credentials."


def test_is_credential_error_detects_mysql_1045():
    """Verify detection of standard MySQL 1045 access denied errors."""
    assert is_credential_error("Access Denied: Invalid username or password.")
    assert is_credential_error("1045 (28000): Access denied for user 'root'@'localhost' (using password: YES)")
    assert is_credential_error("OperationalError: (1045, \"Access denied for user 'admin'@'%' (using password: YES)\")")
    assert is_credential_error("Access denied for user 'guest'@'192.168.1.10'")


def test_is_credential_error_detects_mysql_1698():
    """Verify detection of MySQL 1698 access denied without password."""
    assert is_credential_error("1698 (28000): Access denied for user 'root'@'localhost'")


def test_is_credential_error_detects_generic_credential_phrases():
    """Verify detection of generic auth/credential phrases."""
    assert is_credential_error("Invalid credentials provided.")
    assert is_credential_error("Wrong credentials. Please try again.")
    assert is_credential_error("Invalid username or password.")
    assert is_credential_error("Authentication failed for user dbadmin.")
    assert is_credential_error("Either username or password is wrong.")


def test_is_credential_error_rejects_network_and_server_errors():
    """Verify rejection of network, unreachable, and server faults."""
    # 2003 - Host unreachable
    assert not is_credential_error("Connection Failed: Cannot reach MySQL server at 'localhost:3306'.")
    assert not is_credential_error("2003 (HY000): Can't connect to MySQL server on '127.0.0.1' (10061)")
    
    # 2002 - Socket / local connection fault
    assert not is_credential_error("2002: Can't connect to local MySQL server through socket '/tmp/mysql.sock'")
    
    # Connection refused / host down
    assert not is_credential_error("Connection refused: target machine actively refused it.")
    assert not is_credential_error("No route to host.")


def test_is_credential_error_rejects_database_not_found():
    """Verify rejection of database-not-found errors (MySQL 1049)."""
    assert not is_credential_error("Database Error: Database 'analytics_db' does not exist on this server.")
    assert not is_credential_error("1049 (42000): Unknown database 'my_clean_db'")


def test_is_credential_error_rejects_timeout_errors():
    """Verify rejection of connection timeouts."""
    assert not is_credential_error("Connection Timeout: Server took too long to respond.")
    assert not is_credential_error("OperationalError: Connection timed out after 5000ms.")


def test_is_credential_error_rejects_ssl_errors():
    """Verify rejection of SSL/TLS certificate errors."""
    assert not is_credential_error("SSL/TLS Error: certificate verify failed.")
    assert not is_credential_error("SSL connection error: handshake failed.")


def test_is_credential_error_handles_empty_inputs():
    """Verify graceful handling of empty or None inputs."""
    assert not is_credential_error("")
    assert not is_credential_error(None)


def test_dialog_html_contains_exact_message():
    """Verify the generated dialog HTML contains the exact message."""
    html = build_credential_dialog_html()
    assert "Your credentials are wrong. Please check your credentials." in html
    assert "Authentication Failed" in html


def test_dialog_html_layout_and_positioning():
    """Verify dialog viewport centering and z-index specifications."""
    html = build_credential_dialog_html()
    
    # Overlay styling: fixed positioning, flex center, high z-index
    assert "position: fixed !important;" in html
    assert "justify-content: center !important;" in html
    assert "align-items: center !important;" in html
    assert "z-index: 99999999 !important;" in html
    assert "z-index: 100000000 !important;" in html
    
    # Responsive constraints
    assert "max-width: 440px !important;" in html
    assert "width: 90% !important;" in html


def test_dialog_html_animations_and_duration():
    """Verify keyframes for 3s display duration and smooth entry/exit."""
    html = build_credential_dialog_html()
    
    # Animation names and exact 3-second duration
    assert "credBoxAnim" in html
    assert "credOverlayAnim" in html
    assert "3000ms" in html
    assert "forwards !important;" in html
    
    # Countdown progress bar
    assert "credProgressBar" in html
    assert "2400ms 240ms linear forwards" in html
    
    # Dismiss button and container ID
    assert "cred-dialog-close-btn" in html
    assert "credential-error-dialog-container" in html


def test_parse_connection_error_integration():
    """Verify parse_connection_error returns exact message for credential faults."""
    title, msg = parse_connection_error("1045: Access denied for user 'alice'@'localhost'")
    assert title == "Invalid Credentials"
    assert msg == "Your credentials are wrong. Please check your credentials."

    # Non-credential error should preserve distinct title and message
    title, msg = parse_connection_error("2003: Can't connect to server")
    assert title == "Cannot Reach Server"
    assert "Unable to connect to MySQL server" in msg


def test_dialog_dismiss_toggle_elements_and_css():
    """Verify instant dismissal toggle, backdrop dismiss, and pure CSS hide rules."""
    html = build_credential_dialog_html()
    assert 'id="cred-dialog-toggle"' in html
    assert 'class="cred-dialog-toggle-input"' in html
    assert 'class="cred-dialog-backdrop-dismiss"' in html
    assert 'for="cred-dialog-toggle"' in html
    assert ".cred-dialog-toggle-input:checked ~ .cred-dialog-overlay" in html
    assert "display: none !important;" in html


def test_keyframes_have_no_invalid_important_declarations():
    """Verify CSS keyframes follow W3C spec and do not contain invalid !important declarations."""
    import re
    html = build_credential_dialog_html()
    # Find all @keyframes blocks
    keyframes_blocks = re.findall(r"@keyframes\s+\w+\s*\{([^}]+\{[^}]+\}[^}]*)\}", html)
    assert len(keyframes_blocks) > 0
    for block in keyframes_blocks:
        assert "!important" not in block, f"Keyframe block contains invalid !important: {block}"


def test_repeated_dialog_invocations_generate_fresh_instances():
    """Verify consecutive credential failures generate unique render instances to restart animations."""
    html1 = build_credential_dialog_html()
    html2 = build_credential_dialog_html()
    assert html1 != html2, "Consecutive dialog renders must produce unique HTML to force React/Streamlit remount"
    assert "data-render-id=" in html1
    assert "data-render-id=" in html2



