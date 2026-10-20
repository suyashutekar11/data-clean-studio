"""
Tests for AI Column Configuration Helper Module
tests/test_ai_column_config.py
"""

from unittest.mock import MagicMock, patch
import os
import tempfile
from pathlib import Path
import pytest
import dotenv

from src.ai_column_config import (
    AIColumnConfig,
    load_ai_column_config,
    validate_ai_column_config,
    save_ai_column_config,
    test_simple_ai_connectivity,
    test_ai_column_connection,
    sanitize_error_message,
    ENV_KEY_API_KEY,
    ENV_KEY_BASE_URL,
    ENV_KEY_MODEL_NAME,
)


@pytest.fixture
def temp_env_file(tmp_path, monkeypatch):
    """Provides an isolated temporary .env file and cleans up os.environ."""
    monkeypatch.delenv(ENV_KEY_API_KEY, raising=False)
    monkeypatch.delenv(ENV_KEY_BASE_URL, raising=False)
    monkeypatch.delenv(ENV_KEY_MODEL_NAME, raising=False)
    env_file = tmp_path / ".env"
    return env_file


def test_load_config_when_env_missing(tmp_path):
    """Verify loading from non-existent .env file returns empty unconfigured config without crashing."""
    missing_file = tmp_path / "non_existent.env"
    cfg = load_ai_column_config(missing_file)
    assert isinstance(cfg, AIColumnConfig)
    assert cfg.is_configured is False
    assert cfg.base_url == ""
    assert cfg.model_name == ""
    assert cfg.api_key == ""


def test_load_config_from_valid_env(temp_env_file):
    """Verify values are correctly read from .env."""
    content = (
        "OTHER_VAR=important_value\n"
        "AI_BASE_URL=https://integrate.api.nvidia.com/v1\n"
        "AI_MODEL_NAME=nvidia/nemotron-3.5-super-vl-120b-a12b\n"
        "AI_API_KEY=nvapi-secret-1234567890\n"
    )
    temp_env_file.write_text(content, encoding="utf-8")

    cfg = load_ai_column_config(temp_env_file)
    assert cfg.is_configured is True
    assert cfg.base_url == "https://integrate.api.nvidia.com/v1"
    assert cfg.model_name == "nvidia/nemotron-3.5-super-vl-120b-a12b"
    assert cfg.api_key == "nvapi-secret-1234567890"
    assert cfg.masked_key != "nvapi-secret-1234567890"
    assert "secret" not in cfg.masked_key


def test_validate_base_url():
    """Verify Base URL validation rules."""
    # Missing URL
    ok, err = validate_ai_column_config("", "model-x", "key-123")
    assert ok is False
    assert "Base URL is required" in err

    # Invalid URL scheme
    ok, err = validate_ai_column_config("ftp://example.com", "model-x", "key-123")
    assert ok is False
    assert "must start with 'http://' or 'https://'" in err

    # Missing host
    ok, err = validate_ai_column_config("https://", "model-x", "key-123")
    assert ok is False
    assert "valid host" in err


def test_validate_model_name():
    """Verify Model Name validation rules."""
    # Missing model
    ok, err = validate_ai_column_config("https://api.example.com/v1", "", "key-123")
    assert ok is False
    assert "Model Name is required" in err

    # Too short
    ok, err = validate_ai_column_config("https://api.example.com/v1", "a", "key-123")
    assert ok is False
    assert "at least 2 characters" in err


def test_validate_api_key_scenarios():
    """Verify API key validation when new key is provided vs when existing key is present."""
    # No new key, no existing key
    ok, err = validate_ai_column_config("https://api.example.com/v1", "model-x", "", existing_key="")
    assert ok is False
    assert "API Key is required" in err

    # No new key, but valid existing key in .env
    ok, err = validate_ai_column_config("https://api.example.com/v1", "model-x", "", existing_key="nvapi-existing")
    assert ok is True
    assert err == ""

    # New key provided
    ok, err = validate_ai_column_config("https://api.example.com/v1", "model-x", "nvapi-new-key", existing_key="")
    assert ok is True
    assert err == ""


def test_save_config_creates_env_and_preserves_other_keys(temp_env_file):
    """Verify saving creates file, updates AI keys, and preserves unrelated keys."""
    # Write unrelated setting first
    temp_env_file.write_text("DATABASE_PORT=3306\nSECRET_FLAG=keep_me\n", encoding="utf-8")

    ok, msg = save_ai_column_config(
        base_url="https://api.groq.com/openai/v1",
        model_name="llama-3.3-70b-versatile",
        api_key="gsk-testkey1234567890",
        env_path=temp_env_file,
    )
    assert ok is True
    assert "saved securely" in msg

    # Verify updated .env content
    values = dotenv.dotenv_values(temp_env_file)
    assert values["DATABASE_PORT"] == "3306"
    assert values["SECRET_FLAG"] == "keep_me"
    assert values[ENV_KEY_BASE_URL] == "https://api.groq.com/openai/v1"
    assert values[ENV_KEY_MODEL_NAME] == "llama-3.3-70b-versatile"
    assert values[ENV_KEY_API_KEY] == "gsk-testkey1234567890"


def test_save_config_preserves_existing_api_key_when_empty_input(temp_env_file):
    """Verify that leaving the API key empty does not overwrite the existing saved key."""
    temp_env_file.write_text("AI_API_KEY=nvapi-super-secret-key\n", encoding="utf-8")

    ok, msg = save_ai_column_config(
        base_url="https://integrate.api.nvidia.com/v1",
        model_name="nvidia/nemotron-3.5-super-vl-120b-a12b",
        api_key="",  # User didn't type a new key
        env_path=temp_env_file,
    )
    assert ok is True

    values = dotenv.dotenv_values(temp_env_file)
    assert values[ENV_KEY_API_KEY] == "nvapi-super-secret-key"
    assert values[ENV_KEY_BASE_URL] == "https://integrate.api.nvidia.com/v1"
    assert values[ENV_KEY_MODEL_NAME] == "nvidia/nemotron-3.5-super-vl-120b-a12b"


def test_api_key_never_exposed_in_error_message():
    """Verify validation and error messages do not reveal API keys."""
    secret = "nvapi-very-confidential-secret-key"
    ok, err = validate_ai_column_config("invalid-url", "model", secret)
    assert ok is False
    assert secret not in err


def test_simple_ai_connectivity_success():
    """Verify test_simple_ai_connectivity succeeds on HTTP 200 response."""
    cfg = AIColumnConfig(
        base_url="https://integrate.api.nvidia.com/v1",
        model_name="nvidia/nemotron-3.5-super-vl-120b-a12b",
        api_key="nvapi-test-secret-123",
    )

    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="OK, I am ready."))]

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_resp

        res = test_simple_ai_connectivity(cfg, timeout=5.0)
        assert res["success"] is True
        assert res["http_status"] == 200
        assert "integrate.api.nvidia.com" in res["endpoint_host"]
        assert res["duration_ms"] is not None
        assert "OK, I am ready." in (res.get("reply") or "")
        assert "HTTP 200 OK" in res["message"]


def test_simple_ai_connectivity_http_error():
    """Verify test_simple_ai_connectivity extracts HTTP status and sanitizes errors."""
    cfg = AIColumnConfig(
        base_url="https://integrate.api.nvidia.com/v1",
        model_name="nvidia/nemotron-3.5-super-vl-120b-a12b",
        api_key="nvapi-test-secret-123",
    )

    err = Exception("Error code: 500 - {'error': {'message': 'Failed to generate completions'}}")
    setattr(err, "status_code", 500)

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.side_effect = err

        res = test_simple_ai_connectivity(cfg, timeout=5.0)
        assert res["success"] is False
        assert res["http_status"] == 500
        assert "HTTP 500" in res["message"]
        assert "Failed to generate completions" in res["message"]
        assert "nvapi-test-secret-123" not in res["message"]


def test_simple_ai_connectivity_unconfigured():
    """Verify test_simple_ai_connectivity fails fast when credentials are not configured."""
    cfg = AIColumnConfig(base_url="", model_name="", api_key="")
    res = test_simple_ai_connectivity(cfg)
    assert res["success"] is False
    assert "required" in res["message"].lower()
    assert res["http_status"] is None


def test_ai_column_connection_wrapper():
    """Verify test_ai_column_connection returns tuple of (bool, str)."""
    cfg = AIColumnConfig(
        base_url="https://api.openai.com/v1",
        model_name="gpt-4o",
        api_key="sk-test-key",
    )
    mock_resp = MagicMock()
    mock_resp.choices = [MagicMock(message=MagicMock(content="OK"))]

    with patch("openai.OpenAI") as mock_openai_cls:
        mock_client = MagicMock()
        mock_openai_cls.return_value = mock_client
        mock_client.chat.completions.create.return_value = mock_resp

        ok, msg = test_ai_column_connection(cfg)
        assert ok is True
        assert "HTTP 200 OK" in msg
