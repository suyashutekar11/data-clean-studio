"""
DataClean Studio — AI Column Configuration Helper Module
src/ai_column_config.py

Handles secure loading, validation, masking, and persistence of AI model
configuration (Base URL, Model Name, and API Key) stored in the project's .env file.
Preserves existing/unrelated environment variables and ensures the API key
is never logged, printed in plain text, or exposed in error messages.
"""

from __future__ import annotations

import os
import re
import time
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple, Union, Dict, Any
from urllib.parse import urlparse

import dotenv

from src.ai_service import mask_api_key, sanitize_error_message

logger = logging.getLogger(__name__)

# Key names in .env
ENV_KEY_API_KEY = "AI_API_KEY"
ENV_KEY_BASE_URL = "AI_BASE_URL"
ENV_KEY_MODEL_NAME = "AI_MODEL_NAME"


def get_default_env_path() -> Path:
    """Returns the absolute Path to the project root .env file."""
    # src/ is one level below project root
    return Path(__file__).resolve().parent.parent / ".env"


@dataclass
class AIColumnConfig:
    """Encapsulates configuration settings for AI Column Analysis and Cleaning."""
    base_url: str = ""
    model_name: str = ""
    api_key: str = ""

    @property
    def is_configured(self) -> bool:
        """Returns True if Base URL, Model Name, and API Key are all populated."""
        return bool(self.base_url.strip() and self.model_name.strip() and self.api_key.strip())

    @property
    def masked_key(self) -> str:
        """Returns a safe, masked representation of the API key."""
        return mask_api_key(self.api_key)


def load_ai_column_config(env_path: Optional[Union[str, Path]] = None) -> AIColumnConfig:
    """
    Loads AI Column configuration values from the .env file.
    Falls back to os.environ if present.
    """
    target_path = Path(env_path) if env_path else get_default_env_path()
    env_values: Dict[str, Optional[str]] = {}

    if target_path.exists():
        try:
            env_values = dotenv.dotenv_values(target_path)
        except Exception as e:
            logger.warning("Could not parse .env file at %s: %s", target_path, sanitize_error_message(str(e)))

    # If an explicit env_path was passed (e.g. in tests or custom path),
    # strictly read from that file. Only use os.getenv fallback when using default root .env.
    if env_path is not None:
        api_key = (env_values.get(ENV_KEY_API_KEY) or "").strip()
        base_url = (env_values.get(ENV_KEY_BASE_URL) or "").strip()
        model_name = (env_values.get(ENV_KEY_MODEL_NAME) or "").strip()
    else:
        api_key = (env_values.get(ENV_KEY_API_KEY) or os.getenv(ENV_KEY_API_KEY) or "").strip()
        base_url = (env_values.get(ENV_KEY_BASE_URL) or os.getenv(ENV_KEY_BASE_URL) or "").strip()
        model_name = (env_values.get(ENV_KEY_MODEL_NAME) or os.getenv(ENV_KEY_MODEL_NAME) or "").strip()

    return AIColumnConfig(
        base_url=base_url,
        model_name=model_name,
        api_key=api_key,
    )


def validate_ai_column_config(
    base_url: str,
    model_name: str,
    api_key: str,
    existing_key: Optional[str] = None,
) -> Tuple[bool, str]:
    """
    Validates Base URL, Model Name, and API Key.
    Does NOT make network or API requests.
    Never exposes raw API keys in validation error messages.
    """
    clean_url = (base_url or "").strip()
    clean_model = (model_name or "").strip()
    clean_key = (api_key or "").strip()
    effective_key = clean_key or (existing_key or "").strip()

    # 1. Base URL Validation
    if not clean_url:
        return False, "Base URL is required. Please provide a valid API endpoint (e.g., https://api.example.com/v1)."

    parsed = urlparse(clean_url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return False, "Invalid Base URL. The URL must start with 'http://' or 'https://' and include a valid host."

    # 2. Model Name Validation
    if not clean_model:
        return False, "Model Name is required. Please provide the model identifier (e.g., nvidia/nemotron-3.5-super-vl-120b-a12b)."

    if len(clean_model) < 2:
        return False, "Model Name must be at least 2 characters long."

    # 3. API Key Validation
    if not effective_key:
        return False, "API Key is required. Please enter an API key to save in .env."

    return True, ""


def save_ai_column_config(
    base_url: str,
    model_name: str,
    api_key: Optional[str] = None,
    env_path: Optional[Union[str, Path]] = None,
) -> Tuple[bool, str]:
    """
    Saves AI Column configuration into the local .env file.
    - Preserves all other existing environment variables and comments in .env.
    - Safely creates .env if it does not already exist.
    - If api_key is empty or omitted, preserves the existing AI_API_KEY from .env.
    - Updates os.environ so runtime changes take effect immediately.
    - Never leaks the API key in success or error messages.
    """
    target_path = Path(env_path) if env_path else get_default_env_path()

    clean_url = (base_url or "").strip()
    clean_model = (model_name or "").strip()
    raw_key = (api_key or "").strip()

    # Read existing key to allow keeping it if left blank
    existing_key = ""
    if target_path.exists():
        try:
            curr_values = dotenv.dotenv_values(target_path)
            existing_key = (curr_values.get(ENV_KEY_API_KEY) or "").strip()
        except Exception:
            existing_key = (os.getenv(ENV_KEY_API_KEY) or "").strip()
    else:
        existing_key = (os.getenv(ENV_KEY_API_KEY) or "").strip()

    effective_key = raw_key if raw_key else existing_key

    # Validate inputs
    is_valid, val_msg = validate_ai_column_config(
        base_url=clean_url,
        model_name=clean_model,
        api_key=raw_key,
        existing_key=existing_key,
    )
    if not is_valid:
        return False, val_msg

    try:
        # Ensure parent directory exists
        target_path.parent.mkdir(parents=True, exist_ok=True)

        # Create file if not existing
        if not target_path.exists():
            target_path.touch(mode=0o600, exist_ok=True)

        # Persist Base URL and Model Name
        dotenv.set_key(str(target_path), ENV_KEY_BASE_URL, clean_url, quote_mode="always")
        dotenv.set_key(str(target_path), ENV_KEY_MODEL_NAME, clean_model, quote_mode="always")

        # Persist API Key
        dotenv.set_key(str(target_path), ENV_KEY_API_KEY, effective_key, quote_mode="always")

        # Synchronize os.environ for current runtime session
        os.environ[ENV_KEY_BASE_URL] = clean_url
        os.environ[ENV_KEY_MODEL_NAME] = clean_model
        os.environ[ENV_KEY_API_KEY] = effective_key

        return True, "AI configuration saved securely to local .env."

    except Exception as e:
        safe_err = sanitize_error_message(str(e), api_key=effective_key)
        logger.error("Failed to save AI configuration to %s: %s", target_path, safe_err)
        return False, f"Failed to save configuration to .env: {safe_err}"


def test_simple_ai_connectivity(config: AIColumnConfig, timeout: float = 15.0) -> Dict[str, Any]:
    """
    Executes a minimal test ping against the configured AI endpoint using a minimal prompt.
    Records model, endpoint host, request duration, HTTP status, and sanitized error details.
    Never exposes raw API keys.
    """
    clean_url = (config.base_url or "").strip()
    clean_model = (config.model_name or "").strip()
    clean_key = (config.api_key or "").strip()

    endpoint_host = urlparse(clean_url).netloc or clean_url

    if not clean_url:
        return {
            "success": False,
            "http_status": None,
            "model": clean_model,
            "endpoint_host": endpoint_host,
            "duration_ms": 0,
            "error_details": "Base URL is required to test connection.",
            "message": "Base URL is required to test connection.",
        }
    if not clean_model:
        return {
            "success": False,
            "http_status": None,
            "model": clean_model,
            "endpoint_host": endpoint_host,
            "duration_ms": 0,
            "error_details": "Model Name is required to test connection.",
            "message": "Model Name is required to test connection.",
        }
    if not clean_key:
        return {
            "success": False,
            "http_status": None,
            "model": clean_model,
            "endpoint_host": endpoint_host,
            "duration_ms": 0,
            "error_details": "API Key is required to test connection.",
            "message": "API Key is required to test connection.",
        }

    start_t = time.time()
    try:
        from openai import OpenAI

        base_url = clean_url
        if "api.openai.com" in base_url and base_url.endswith("/v1"):
            base_url = None

        client = OpenAI(
            api_key=clean_key,
            base_url=base_url,
            timeout=timeout,
            max_retries=0,
        )

        response = client.chat.completions.create(
            model=clean_model,
            messages=[{"role": "user", "content": "Respond with the word OK."}],
            max_tokens=50,
            temperature=0.1,
        )

        duration_ms = int((time.time() - start_t) * 1000)
        reply = ""
        if response and response.choices and response.choices[0].message:
            msg = response.choices[0].message
            reply = (msg.content or getattr(msg, "reasoning_content", "") or "").strip()

        return {
            "success": True,
            "http_status": 200,
            "model": clean_model,
            "endpoint_host": endpoint_host,
            "duration_ms": duration_ms,
            "error_details": None,
            "message": f"Connection verified in {duration_ms}ms (HTTP 200 OK)! Model: {clean_model}.",
            "reply": reply[:100],
        }

    except Exception as exc:
        duration_ms = int((time.time() - start_t) * 1000)
        http_status = getattr(exc, "status_code", None)
        safe_err = sanitize_error_message(str(exc), clean_key)

        if not http_status:
            m = re.search(r"\b(4\d\d|5\d\d)\b", safe_err)
            if m:
                http_status = int(m.group(1))

        status_prefix = f"HTTP {http_status}" if http_status else "Connection Failed"
        return {
            "success": False,
            "http_status": http_status,
            "model": clean_model,
            "endpoint_host": endpoint_host,
            "duration_ms": duration_ms,
            "error_details": safe_err,
            "message": f"{status_prefix} ({duration_ms}ms): {safe_err}",
        }


def test_ai_column_connection(config: AIColumnConfig, timeout: float = 15.0) -> Tuple[bool, str]:
    """
    Tests live connectivity to the configured AI model endpoint.
    Uses standard OpenAI-compatible client interface supported by NVIDIA, OpenAI, Groq, Ollama, etc.
    Returns (success: bool, message: str).
    """
    res = test_simple_ai_connectivity(config, timeout=timeout)
    return res["success"], res["message"]


# Mark non-test helper functions so pytest does not treat them as tests when imported
test_simple_ai_connectivity.__test__ = False
test_ai_column_connection.__test__ = False

