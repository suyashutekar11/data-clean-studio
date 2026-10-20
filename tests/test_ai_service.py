"""
Unit and integration tests for DataClean Studio AI Assistant.
Tests:
- Provider catalog completeness (OpenAI, Gemini, Anthropic, Groq, OpenAI-compatible)
- Configuration validation (missing keys, custom base URLs, invalid providers)
- Security & Key masking (never exposing full keys, format-specific masking)
- Error message sanitization (redacting raw API keys, bearer tokens)
- Connection testing for providers (mocked success, mocked errors, timeout handling)
- Multi-turn conversation handling and context preservation
- Absence of database access/SQL execution in AI module
- UI integration, module cards, and tab exports
"""

from unittest.mock import MagicMock, patch
import pytest
import streamlit as st

from src.ai_service import (
    AIProviderConfig,
    ChatMessage,
    SUPPORTED_PROVIDERS,
    mask_api_key,
    sanitize_error_message,
    validate_ai_config,
    test_ai_connection as perform_test_ai_connection,
    send_chat_message,
)
from ui.cleaning_tabs import (
    CLEANING_MODULES,
    CLEANING_TAB_NAMES,
    _CARD_DESCRIPTIONS,
)
from ui.ai_assistant_view import (
    init_ai_session_state,
    render_ai_config_sidebar,
    render_ai_assistant_main,
    render_ai_assistant_page,
)


# ─────────────────────────────────────────────────────────────
# 1. Provider Catalog & Configuration Validation Tests
# ─────────────────────────────────────────────────────────────

def test_supported_providers_catalog():
    """Verify all expected AI providers are present with correct metadata."""
    expected_providers = ["openai", "google_gemini", "anthropic", "groq", "openai_compatible"]
    for prov in expected_providers:
        assert prov in SUPPORTED_PROVIDERS
        meta = SUPPORTED_PROVIDERS[prov]
        assert "name" in meta
        assert "default_models" in meta
        assert len(meta["default_models"]) > 0
        assert "default_base_url" in meta
        assert "requires_key" in meta


def test_validate_ai_config_valid_openai():
    """Valid OpenAI config passes validation."""
    cfg = AIProviderConfig(
        provider="openai",
        api_key="sk-test-valid-key-12345",
        model="gpt-4o",
    )
    ok, msg = validate_ai_config(cfg)
    assert ok is True
    assert msg == "Configuration valid."


def test_validate_ai_config_missing_provider():
    """Invalid or unsupported provider fails validation."""
    cfg = AIProviderConfig(
        provider="unsupported_ai_provider",
        api_key="sk-test",
        model="test-model",
    )
    ok, msg = validate_ai_config(cfg)
    assert ok is False
    assert "Unsupported provider" in msg


def test_validate_ai_config_missing_required_key():
    """Providers requiring keys fail if key is empty."""
    cfg = AIProviderConfig(
        provider="openai",
        api_key="   ",
        model="gpt-4o",
    )
    ok, msg = validate_ai_config(cfg)
    assert ok is False
    assert "API key is required" in msg


def test_validate_ai_config_optional_key_local():
    """Local / OpenAI-compatible allows empty key."""
    cfg = AIProviderConfig(
        provider="openai_compatible",
        api_key="",
        model="llama3.2",
        base_url="http://localhost:11434/v1",
    )
    ok, msg = validate_ai_config(cfg)
    assert ok is True


def test_validate_ai_config_missing_model():
    """Empty model name fails validation."""
    cfg = AIProviderConfig(
        provider="openai",
        api_key="sk-test-12345",
        model="",
    )
    ok, msg = validate_ai_config(cfg)
    assert ok is False
    assert "Model name cannot be empty" in msg


def test_validate_ai_config_invalid_base_url():
    """Custom base URL without http:// or https:// fails validation."""
    cfg = AIProviderConfig(
        provider="openai_compatible",
        api_key="",
        model="llama3.2",
        base_url="ftp://invalid-url.com",
    )
    ok, msg = validate_ai_config(cfg)
    assert ok is False
    assert "must start with http:// or https://" in msg


# ─────────────────────────────────────────────────────────────
# 2. Security & Redaction Tests
# ─────────────────────────────────────────────────────────────

def test_mask_api_key_empty_or_none():
    """Empty or None keys return empty string."""
    assert mask_api_key(None) == ""
    assert mask_api_key("") == ""
    assert mask_api_key("   ") == ""


def test_mask_api_key_short():
    """Short keys are completely masked."""
    assert mask_api_key("12345") == "•••••"
    assert mask_api_key("12345678") == "••••••••"


def test_mask_api_key_openai_format():
    """sk- prefixed keys preserve prefix and mask middle."""
    raw = "sk-proj-1234567890abcdefghijklmnopqrstuvwxyz9999"
    masked = mask_api_key(raw)
    assert masked.startswith("sk-")
    assert masked.endswith("9999")
    assert "••••" in masked
    assert "1234567890" not in masked


def test_mask_api_key_general_format():
    """Standard keys preserve first 3 and last 4 characters."""
    raw = "AIzaSyABCDEFGHIJKLMN1234567890XYZ"
    masked = mask_api_key(raw)
    assert masked.startswith("AIz")
    assert masked.endswith("0XYZ")
    assert "••••" in masked
    assert "ABCDEFGHIJKLMN" not in masked


def test_sanitize_error_message_strips_key():
    """Raw API key in exception message is redacted."""
    raw_key = "sk-1234567890secretkeyvalue"
    err = f"Failed to authenticate with key {raw_key}: Invalid key."
    cleaned = sanitize_error_message(err, raw_key)
    assert raw_key not in cleaned
    assert "[REDACTED_API_KEY]" in cleaned or "[REDACTED_KEY]" in cleaned


def test_sanitize_error_message_strips_bearer_token():
    """Bearer tokens in error messages are stripped."""
    err = "Authorization failed for Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.xyz"
    cleaned = sanitize_error_message(err)
    assert "Bearer [REDACTED_TOKEN]" in cleaned


# ─────────────────────────────────────────────────────────────
# 3. Connection Testing Tests (Mocked)
# ─────────────────────────────────────────────────────────────

def test_test_openai_connection_success():
    """Successful OpenAI connection test ping."""
    cfg = AIProviderConfig(provider="openai", api_key="sk-test", model="gpt-4o-mini")

    mock_choice = MagicMock()
    mock_choice.message.content = "OK"
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("openai.OpenAI", return_value=mock_client):
        ok, msg = perform_test_ai_connection(cfg, timeout=5.0)
        assert ok is True
        assert "Connection verified" in msg
        assert "gpt-4o-mini" in msg


def test_test_openai_connection_401():
    """OpenAI 401 returns user-friendly auth failure."""
    cfg = AIProviderConfig(provider="openai", api_key="sk-bad", model="gpt-4o-mini")

    with patch("openai.OpenAI", side_effect=Exception("Error code 401 - Incorrect API key")):
        ok, msg = perform_test_ai_connection(cfg, timeout=5.0)
        assert ok is False
        assert "Authentication failed (401)" in msg


def test_test_anthropic_connection_success():
    """Successful Anthropic connection test ping."""
    cfg = AIProviderConfig(provider="anthropic", api_key="sk-ant-test", model="claude-3-5-haiku-20241022")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("requests.post", return_value=mock_resp):
        ok, msg = perform_test_ai_connection(cfg, timeout=5.0)
        assert ok is True
        assert "Connection verified" in msg


def test_test_anthropic_connection_401():
    """Anthropic 401 returns clear authentication error."""
    cfg = AIProviderConfig(provider="anthropic", api_key="sk-ant-bad", model="claude-3-5-haiku-20241022")

    mock_resp = MagicMock()
    mock_resp.status_code = 401

    with patch("requests.post", return_value=mock_resp):
        ok, msg = perform_test_ai_connection(cfg, timeout=5.0)
        assert ok is False
        assert "Authentication failed (401)" in msg


def test_test_gemini_connection_success():
    """Successful Google Gemini connection test."""
    cfg = AIProviderConfig(provider="google_gemini", api_key="AIzaSyTest", model="gemini-2.5-flash")

    mock_resp = MagicMock()
    mock_resp.text = "OK"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_resp

    with patch("google.genai.Client", return_value=mock_client):
        ok, msg = perform_test_ai_connection(cfg, timeout=5.0)
        assert ok is True
        assert "Connection verified" in msg


# ─────────────────────────────────────────────────────────────
# 4. Multi-Turn Chat Messaging Tests
# ─────────────────────────────────────────────────────────────

def test_send_chat_message_preserves_multiturn_history():
    """Verify earlier conversation turns are included in API dispatch."""
    cfg = AIProviderConfig(provider="openai", api_key="sk-test", model="gpt-4o")

    history = [
        ChatMessage(role="user", content="What is TRIM in SQL?"),
        ChatMessage(role="assistant", content="TRIM removes spaces."),
        ChatMessage(role="user", content="Give me an example."),
    ]

    mock_choice = MagicMock()
    mock_choice.message.content = "For example: SELECT TRIM('  abc  ');"
    mock_resp = MagicMock()
    mock_resp.choices = [mock_choice]

    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = mock_resp

    with patch("openai.OpenAI", return_value=mock_client):
        ok, reply = send_chat_message(cfg, messages=history, system_prompt="You are an expert.")
        assert ok is True
        assert "SELECT TRIM" in reply

        # Check call arguments to verify history was passed
        mock_client.chat.completions.create.assert_called_once()
        call_kwargs = mock_client.chat.completions.create.call_args[1]
        sent_msgs = call_kwargs["messages"]

        assert len(sent_msgs) == 4  # 1 system + 3 turns
        assert sent_msgs[0]["role"] == "system"
        assert sent_msgs[1]["content"] == "What is TRIM in SQL?"
        assert sent_msgs[2]["content"] == "TRIM removes spaces."
        assert sent_msgs[3]["content"] == "Give me an example."


def test_send_chat_message_empty_messages():
    """Empty message list returns error."""
    cfg = AIProviderConfig(provider="openai", api_key="sk-test", model="gpt-4o")
    ok, msg = send_chat_message(cfg, messages=[])
    assert ok is False
    assert "No messages provided" in msg


# ─────────────────────────────────────────────────────────────
# 5. Database Isolation & Safety Verification
# ─────────────────────────────────────────────────────────────

def test_ai_service_has_zero_db_dependencies():
    """Verify ai_service does not import SQLAlchemy or connection engines."""
    import src.ai_service as ai_mod
    imported_names = dir(ai_mod)
    assert "create_engine" not in imported_names
    assert "MySQLConnectionManager" not in imported_names
    assert "execute_query" not in imported_names
    assert "delete_workspace" not in imported_names


# ─────────────────────────────────────────────────────────────
# 6. UI Integration & Cleaning Hub Card Tests
# ─────────────────────────────────────────────────────────────

def test_ai_assistant_card_in_cleaning_hub():
    """Verify AI Assistant card exists in CLEANING_MODULES with exact expected copy."""
    ai_mods = [m for m in CLEANING_MODULES if m["id"] == "ai_assistant"]
    assert len(ai_mods) == 1
    mod = ai_mods[0]
    assert mod["title"] == "AI Assistant"
    assert mod["name"] == "🤖 AI Assistant"
    assert mod["icon"] == "bot"
    assert mod["description"] == "Connect your AI model and chat with an intelligent assistant."
    assert mod["tooltip"] == "Connect your AI model and chat with an intelligent assistant."
    assert _CARD_DESCRIPTIONS["ai_assistant"] == "Connect your AI model and chat with an intelligent assistant."


def test_init_ai_session_state():
    """Verify AI Assistant session state keys are safely initialized."""
    with patch.dict(st.session_state, {}, clear=True):
        init_ai_session_state()
        assert "ai_config" in st.session_state
        assert "ai_config_saved" in st.session_state
        assert "ai_test_status" in st.session_state
        assert "ai_chat_messages" in st.session_state
        assert "ai_is_processing" in st.session_state


def test_ai_assistant_sidebar_button_state_safe():
    """Verify default connection button states are defined and safe."""
    import app
    assert hasattr(app, "test_btn")
    assert hasattr(app, "connect_btn")
    assert app.test_btn is False
    assert app.connect_btn is False

