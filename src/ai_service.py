"""
DataClean Studio — AI Service Layer
src/ai_service.py

Modular, secure AI provider integration supporting:
- OpenAI (GPT-4o, GPT-4o-mini, GPT-4-turbo, GPT-3.5-turbo, etc.)
- Google Gemini (Gemini 2.5 Flash, Gemini 2.5 Pro, Gemini 1.5 Flash, etc.)
- Anthropic Claude (Claude 3.5 Sonnet, Claude 3.5 Haiku, Claude 3 Opus, etc.)
- OpenAI-Compatible / Local (Ollama, Groq, Together, vLLM, OpenRouter, etc.)

Security & Safety Guarantees:
- Zero hardcoded keys or persistent disk storage of credentials.
- API keys masked in UI; never exposed in logs, exceptions, or responses.
- In-memory session-based storage only.
- Strict isolation: AI service CANNOT access MySQL database, execute SQL, or modify data.
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from urllib.parse import urlparse

import requests


# ─────────────────────────────────────────────────────────────
# 1. Provider Definitions & Catalog
# ─────────────────────────────────────────────────────────────

SUPPORTED_PROVIDERS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "name": "OpenAI",
        "default_models": [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-3.5-turbo",
        ],
        "default_base_url": "https://api.openai.com/v1",
        "requires_key": True,
        "supports_custom_url": True,
        "doc_hint": "Enter your OpenAI API key starting with 'sk-'.",
    },
    "google_gemini": {
        "name": "Google Gemini",
        "default_models": [
            "gemini-2.5-flash",
            "gemini-2.5-pro",
            "gemini-1.5-flash",
            "gemini-1.5-pro",
        ],
        "default_base_url": "https://generativelanguage.googleapis.com",
        "requires_key": True,
        "supports_custom_url": False,
        "doc_hint": "Enter your Google AI Studio API key.",
    },
    "anthropic": {
        "name": "Anthropic Claude",
        "default_models": [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
        ],
        "default_base_url": "https://api.anthropic.com/v1",
        "requires_key": True,
        "supports_custom_url": False,
        "doc_hint": "Enter your Anthropic API key starting with 'sk-ant-'.",
    },
    "groq": {
        "name": "Groq Cloud",
        "default_models": [
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "mixtral-8x7b-32768",
            "gemma2-9b-it",
        ],
        "default_base_url": "https://api.groq.com/openai/v1",
        "requires_key": True,
        "supports_custom_url": False,
        "doc_hint": "Enter your Groq API key starting with 'gsk_'.",
    },
    "openai_compatible": {
        "name": "OpenAI-Compatible / Local (Ollama, vLLM)",
        "default_models": [
            "llama3.2",
            "mistral",
            "llama-3.1-70b-versatile",
            "qwen2.5",
        ],
        "default_base_url": "http://localhost:11434/v1",
        "requires_key": False,
        "supports_custom_url": True,
        "doc_hint": "Point to a local Ollama/vLLM server or 3rd-party provider (OpenRouter, LM Studio).",
    },
}


@dataclass
class AIProviderConfig:
    """Encapsulates configuration for an AI model provider."""
    provider: str
    api_key: str = ""
    model: str = ""
    base_url: Optional[str] = None
    temperature: float = 0.7
    max_tokens: int = 1500

    def get_effective_base_url(self) -> Optional[str]:
        if self.base_url and self.base_url.strip():
            return self.base_url.strip().rstrip("/")
        provider_info = SUPPORTED_PROVIDERS.get(self.provider, {})
        return provider_info.get("default_base_url")


@dataclass
class ChatMessage:
    """Single chat message with role and content."""
    role: str  # 'user', 'assistant', 'system'
    content: str
    timestamp: str = field(default_factory=lambda: time.strftime("%H:%M"))


# ─────────────────────────────────────────────────────────────
# 2. Security & Redaction Utilities
# ─────────────────────────────────────────────────────────────

def mask_api_key(key: Optional[str]) -> str:
    """
    Returns a masked version of an API key for safe UI display.
    Never exposes the full key.
    """
    if not key or not isinstance(key, str):
        return ""
    key = key.strip()
    if len(key) <= 8:
        return "•" * len(key)

    if key.startswith("sk-"):
        prefix = "sk-"
        remainder = key[3:]
        if len(remainder) <= 6:
            return prefix + ("•" * len(remainder))
        return f"{prefix}••••••••••••{remainder[-4:]}"

    return f"{key[:3]}••••••••••••{key[-4:]}"


def sanitize_error_message(err_msg: str, api_key: Optional[str] = None) -> str:
    """
    Strips raw API keys or sensitive auth tokens from exception messages.
    """
    msg = str(err_msg)
    if api_key and len(api_key) > 5:
        msg = msg.replace(api_key, "[REDACTED_API_KEY]")
    # Strip standard token patterns (sk-..., Bearer ...)
    msg = re.sub(r'sk-[a-zA-Z0-9_-]{20,}', '[REDACTED_KEY]', msg)
    msg = re.sub(r'Bearer\s+[a-zA-Z0-9_\-\.]{20,}', 'Bearer [REDACTED_TOKEN]', msg, flags=re.I)
    return msg


def validate_ai_config(config: AIProviderConfig) -> Tuple[bool, str]:
    """Validates configuration parameters before attempting calls."""
    if not config.provider or config.provider not in SUPPORTED_PROVIDERS:
        return False, f"Unsupported provider: '{config.provider}'. Select a supported provider."

    prov_meta = SUPPORTED_PROVIDERS[config.provider]
    if prov_meta.get("requires_key"):
        if not config.api_key or not config.api_key.strip():
            return False, f"API key is required for {prov_meta['name']}."

    if not config.model or not config.model.strip():
        return False, "Model name cannot be empty."

    if config.base_url and config.base_url.strip():
        b_url = config.base_url.strip().lower()
        if not (b_url.startswith("http://") or b_url.startswith("https://")):
            return False, "Custom Base URL must start with http:// or https://"

    return True, "Configuration valid."


# ─────────────────────────────────────────────────────────────
# 3. Connection Testing
# ─────────────────────────────────────────────────────────────

def test_ai_connection(config: AIProviderConfig, timeout: float = 15.0) -> Tuple[bool, str]:
    """
    Tests the configured AI endpoint with a minimal ping request.
    Returns (success: bool, message: str).
    """
    val_ok, val_msg = validate_ai_config(config)
    if not val_ok:
        return False, val_msg

    provider = config.provider
    start_t = time.time()

    try:
        if provider in ("openai", "openai_compatible", "groq"):
            return _test_openai_connection(config, timeout, start_t)
        elif provider == "google_gemini":
            return _test_gemini_connection(config, timeout, start_t)
        elif provider == "anthropic":
            return _test_anthropic_connection(config, timeout, start_t)
        else:
            return False, f"No connection tester implemented for {provider}."
    except Exception as e:
        latency = int((time.time() - start_t) * 1000)
        clean_err = sanitize_error_message(str(e), config.api_key)
        return False, f"Connection test failed ({latency}ms): {clean_err}"


def _test_openai_connection(config: AIProviderConfig, timeout: float, start_t: float) -> Tuple[bool, str]:
    try:
        from openai import OpenAI
    except ImportError:
        return False, "OpenAI Python library is not installed in the environment."

    base_url = config.get_effective_base_url()
    api_key = config.api_key.strip() if config.api_key else "not-needed"

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url if base_url != "https://api.openai.com/v1" else None,
            timeout=timeout,
            max_retries=0,
        )
        # Minimal non-streaming test ping
        response = client.chat.completions.create(
            model=config.model.strip(),
            messages=[{"role": "user", "content": "Respond with the word 'OK'."}],
            max_tokens=5,
        )
        latency = int((time.time() - start_t) * 1000)
        if response and response.choices:
            reply = response.choices[0].message.content or ""
            return True, f"Connection verified in {latency}ms! Model: {config.model}."
        return True, f"Connection successful ({latency}ms)."
    except Exception as exc:
        latency = int((time.time() - start_t) * 1000)
        err = sanitize_error_message(str(exc), config.api_key)
        # Make specific error suggestions
        if "401" in err or "Incorrect API key" in err:
            return False, f"Authentication failed (401): The provided API key is invalid ({latency}ms)."
        if "404" in err or "model_not_found" in err:
            return False, f"Model not found (404): '{config.model}' was not recognized by the provider ({latency}ms)."
        if "429" in err or "quota" in err.lower():
            return False, f"Rate limit / Quota exceeded (429): Check your provider billing or limits ({latency}ms)."
        return False, f"OpenAI connection error ({latency}ms): {err}"


def _test_gemini_connection(config: AIProviderConfig, timeout: float, start_t: float) -> Tuple[bool, str]:
    try:
        from google import genai
    except ImportError:
        return False, "google-genai Python library is not installed in the environment."

    try:
        client = genai.Client(api_key=config.api_key.strip())
        response = client.models.generate_content(
            model=config.model.strip(),
            contents="Respond with the word 'OK'.",
        )
        latency = int((time.time() - start_t) * 1000)
        if response and response.text:
            return True, f"Connection verified in {latency}ms! Gemini Model: {config.model}."
        return True, f"Connection successful ({latency}ms)."
    except Exception as exc:
        latency = int((time.time() - start_t) * 1000)
        err = sanitize_error_message(str(exc), config.api_key)
        if "API_KEY_INVALID" in err or "400" in err:
            return False, f"Invalid Google Gemini API key ({latency}ms)."
        if "404" in err or "not found" in err.lower():
            return False, f"Gemini model '{config.model}' not found ({latency}ms)."
        return False, f"Gemini connection error ({latency}ms): {err}"


def _test_anthropic_connection(config: AIProviderConfig, timeout: float, start_t: float) -> Tuple[bool, str]:
    headers = {
        "x-api-key": config.api_key.strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": config.model.strip(),
        "max_tokens": 5,
        "messages": [{"role": "user", "content": "Respond with 'OK'."}],
    }
    url = "https://api.anthropic.com/v1/messages"
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
        latency = int((time.time() - start_t) * 1000)
        if resp.status_code == 200:
            return True, f"Connection verified in {latency}ms! Model: {config.model}."
        elif resp.status_code == 401:
            return False, f"Authentication failed (401): Invalid Anthropic API key ({latency}ms)."
        elif resp.status_code == 404:
            return False, f"Model '{config.model}' not found (404) ({latency}ms)."
        elif resp.status_code == 429:
            return False, f"Rate limit / Usage limit exceeded (429) ({latency}ms)."
        else:
            data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
            err_msg = data.get("error", {}).get("message", resp.text)
            return False, f"Anthropic error ({resp.status_code}): {sanitize_error_message(err_msg, config.api_key)}"
    except Exception as exc:
        latency = int((time.time() - start_t) * 1000)
        return False, f"Anthropic connection error ({latency}ms): {sanitize_error_message(str(exc), config.api_key)}"


# ─────────────────────────────────────────────────────────────
# 5. AI API Connectivity Test (Temporary Test Mode)
# ─────────────────────────────────────────────────────────────

# TEMPORARY MODE FLAG:
# When True, table analysis / SQL recommendation generation (including the
# rule-engine fallback) are disabled so only the connectivity test can run.
# Set to False to re-enable the original analysis functionality.
TEMP_DISABLE_AI_ANALYSIS = True

# TEMPORARY MODE FLAG:
# When True, column-level AI analysis ("Analyze with AI") is disabled.
# Set to False to enable only the column-level AI analysis entry point.
# Table-level analysis ("Analyze Table", "Refresh Profiling") and
# "Ask AI about column" remain controlled by TEMP_DISABLE_AI_ANALYSIS above.
TEMP_DISABLE_COLUMN_AI_ANALYSIS = False


def _endpoint_host_from_config(config: AIProviderConfig) -> str:
    """Returns the host portion of the configured base URL, or an empty string."""
    base_url = config.get_effective_base_url() or ""
    if not base_url:
        return ""
    try:
        parsed = urlparse(base_url)
        return parsed.netloc or base_url
    except Exception:
        return base_url


def _build_api_test_result(
    test_message: str,
    start_t: float,
    start_ts: str,
    model: str,
    endpoint_host: str,
    status: str,
    *,
    http_status: Optional[int] = None,
    response_text: Optional[str] = None,
    error_details: Optional[str] = None,
    response_body: Optional[str] = None,
) -> Dict[str, Any]:
    """Builds a diagnostic record for a single connectivity test attempt."""
    end_t = time.perf_counter()
    end_ts = time.strftime("%Y-%m-%d %H:%M:%S")
    duration_ms = (end_t - start_t) * 1000.0
    return {
        "test_message": test_message,
        "start_timestamp": start_ts,
        "end_timestamp": end_ts,
        "duration_ms": round(duration_ms, 2),
        "duration_seconds": round(duration_ms / 1000.0, 4),
        "http_status": http_status,
        "model": model,
        "endpoint_host": endpoint_host,
        "status": status,
        "response_text": response_text,
        "error_details": error_details,
        "response_body": response_body,
    }


def _extract_status_and_body(
    exc: Exception, api_key: Optional[str]
) -> Tuple[Optional[int], Optional[str], str]:
    """Extracts HTTP status and raw body from a provider exception without exposing keys."""
    http_status = getattr(exc, "status_code", None)
    response_body = None
    body = getattr(exc, "body", None)
    if body is not None:
        try:
            response_body = (
                body.decode("utf-8", errors="replace")
                if isinstance(body, (bytes, bytearray))
                else str(body)
            )
        except Exception:
            response_body = str(body)
    if http_status is None:
        m = re.search(r"\b(4\d\d|5\d\d)\b", str(exc))
        if m:
            http_status = int(m.group(1))
    clean_err = sanitize_error_message(str(exc), api_key)
    clean_body = sanitize_error_message(response_body, api_key) if response_body is not None else None
    return http_status, clean_body, clean_err


def test_ai_api_connectivity(
    config: AIProviderConfig,
    test_message: str,
    timeout: float = 30.0,
) -> Dict[str, Any]:
    """
    Sends a single test message to the configured AI endpoint and captures
    full request/response diagnostics: timing, HTTP status, model, host,
    response text, and sanitized error details.
    Reuses the configured provider client and authentication mechanism.
    Never falls back to the rule engine and never exposes API keys.
    """
    model = (config.model or "").strip()
    endpoint_host = _endpoint_host_from_config(config)

    # Local (non-HTTP) validation happens before timing starts.
    val_ok, val_msg = validate_ai_config(config)
    if not val_ok:
        now_ts = time.strftime("%Y-%m-%d %H:%M:%S")
        return {
            "test_message": test_message,
            "start_timestamp": now_ts,
            "end_timestamp": now_ts,
            "duration_ms": 0.0,
            "duration_seconds": 0.0,
            "http_status": None,
            "model": model,
            "endpoint_host": endpoint_host,
            "status": "failed",
            "response_text": None,
            "error_details": val_msg,
            "response_body": None,
        }

    # Monotonic timer started immediately before the HTTP request.
    start_t = time.perf_counter()
    start_ts = time.strftime("%Y-%m-%d %H:%M:%S")

    try:
        if config.provider in ("openai", "openai_compatible", "groq"):
            return _test_openai_api_message(
                config, test_message, timeout, start_t, start_ts, model, endpoint_host
            )
        elif config.provider == "google_gemini":
            return _test_gemini_api_message(
                config, test_message, timeout, start_t, start_ts, model, endpoint_host
            )
        elif config.provider == "anthropic":
            return _test_anthropic_api_message(
                config, test_message, timeout, start_t, start_ts, model, endpoint_host
            )
        else:
            return _build_api_test_result(
                test_message,
                start_t,
                start_ts,
                model,
                endpoint_host,
                "failed",
                error_details=f"No connectivity tester implemented for provider '{config.provider}'.",
            )
    except Exception as exc:
        clean_err = sanitize_error_message(str(exc), config.api_key)
        return _build_api_test_result(
            test_message,
            start_t,
            start_ts,
            model,
            endpoint_host,
            "failed",
            error_details=f"Unexpected error: {clean_err}",
        )


def _test_openai_api_message(
    config: AIProviderConfig,
    test_message: str,
    timeout: float,
    start_t: float,
    start_ts: str,
    model: str,
    endpoint_host: str,
) -> Dict[str, Any]:
    try:
        from openai import OpenAI
    except ImportError:
        return _build_api_test_result(
            test_message,
            start_t,
            start_ts,
            model,
            endpoint_host,
            "failed",
            error_details="OpenAI Python library is not installed in the environment.",
        )

    base_url = config.get_effective_base_url()
    api_key = config.api_key.strip() if config.api_key else "not-needed"

    try:
        client = OpenAI(
            api_key=api_key,
            base_url=base_url if base_url != "https://api.openai.com/v1" else None,
            timeout=timeout,
            max_retries=0,
        )
        # HTTP request happens here; start_t was recorded immediately before.
        response = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": test_message}],
            max_tokens=config.max_tokens,
            temperature=config.temperature,
        )
    except Exception as exc:
        http_status, response_body, clean_err = _extract_status_and_body(exc, config.api_key)
        return _build_api_test_result(
            test_message,
            start_t,
            start_ts,
            model,
            endpoint_host,
            "failed",
            http_status=http_status,
            error_details=clean_err,
            response_body=response_body,
        )

    reply = ""
    if response and response.choices and response.choices[0].message:
        msg = response.choices[0].message
        reply = (msg.content or getattr(msg, "reasoning_content", "") or "").strip()

    http_status = None
    transport = getattr(response, "_response", None)
    if transport is not None:
        http_status = getattr(transport, "status_code", None)

    return _build_api_test_result(
        test_message,
        start_t,
        start_ts,
        model,
        endpoint_host,
        "success",
        http_status=http_status,
        response_text=reply or None,
    )


def _test_gemini_api_message(
    config: AIProviderConfig,
    test_message: str,
    timeout: float,
    start_t: float,
    start_ts: str,
    model: str,
    endpoint_host: str,
) -> Dict[str, Any]:
    try:
        from google import genai
    except ImportError:
        return _build_api_test_result(
            test_message,
            start_t,
            start_ts,
            model,
            endpoint_host,
            "failed",
            error_details="google-genai Python library is not installed in the environment.",
        )

    try:
        client = genai.Client(api_key=config.api_key.strip())
        # HTTP request happens here; start_t was recorded immediately before.
        response = client.models.generate_content(model=model, contents=test_message)
    except Exception as exc:
        http_status, response_body, clean_err = _extract_status_and_body(exc, config.api_key)
        return _build_api_test_result(
            test_message,
            start_t,
            start_ts,
            model,
            endpoint_host,
            "failed",
            http_status=http_status,
            error_details=clean_err,
            response_body=response_body,
        )

    reply = (response.text or "").strip() if response else ""
    return _build_api_test_result(
        test_message,
        start_t,
        start_ts,
        model,
        endpoint_host,
        "success",
        response_text=reply or None,
    )


def _test_anthropic_api_message(
    config: AIProviderConfig,
    test_message: str,
    timeout: float,
    start_t: float,
    start_ts: str,
    model: str,
    endpoint_host: str,
) -> Dict[str, Any]:
    headers = {
        "x-api-key": config.api_key.strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": model,
        "max_tokens": config.max_tokens,
        "messages": [{"role": "user", "content": test_message}],
    }
    url = "https://api.anthropic.com/v1/messages"
    try:
        # HTTP request happens here; start_t was recorded immediately before.
        resp = requests.post(url, headers=headers, json=payload, timeout=timeout)
    except Exception as exc:
        clean_err = sanitize_error_message(str(exc), config.api_key)
        return _build_api_test_result(
            test_message,
            start_t,
            start_ts,
            model,
            endpoint_host,
            "failed",
            error_details=clean_err,
        )

    # Capture HTTP status and the raw response body before attempting to parse JSON.
    http_status = resp.status_code
    response_body = resp.text
    # Never store raw secrets: sanitize the body before recording it.
    clean_body = sanitize_error_message(response_body, config.api_key)

    if http_status == 200:
        reply = ""
        try:
            data = resp.json()
            content_blocks = data.get("content", [])
            text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
            reply = "".join(text_parts).strip()
        except Exception:
            reply = ""
        if reply:
            return _build_api_test_result(
                test_message,
                start_t,
                start_ts,
                model,
                endpoint_host,
                "success",
                http_status=http_status,
                response_text=reply,
            )
        return _build_api_test_result(
            test_message,
            start_t,
            start_ts,
            model,
            endpoint_host,
            "failed",
            http_status=http_status,
            error_details="Empty response received.",
            response_body=clean_body,
        )

    err_msg = response_body
    try:
        if (resp.headers.get("content-type") or "").startswith("application/json"):
            data = resp.json()
            err_msg = data.get("error", {}).get("message", response_body)
    except Exception:
        pass
    clean_err = sanitize_error_message(err_msg, config.api_key)
    return _build_api_test_result(
        test_message,
        start_t,
        start_ts,
        model,
        endpoint_host,
        "failed",
        http_status=http_status,
        error_details=f"HTTP {http_status}: {clean_err}",
        response_body=clean_body,
    )


# ─────────────────────────────────────────────────────────────
# 4. Multi-Turn Chat Messaging
# ─────────────────────────────────────────────────────────────

def send_chat_message(
    config: AIProviderConfig,
    messages: List[ChatMessage],
    system_prompt: Optional[str] = None,
    timeout: float = 35.0,
) -> Tuple[bool, str]:
    """
    Dispatches conversation messages to the configured AI model provider.
    Maintains complete conversation history for multi-turn context.
    Returns (success: bool, response_or_error: str).
    """
    val_ok, val_msg = validate_ai_config(config)
    if not val_ok:
        return False, val_msg

    if not messages:
        return False, "No messages provided to send."

    provider = config.provider
    try:
        if provider in ("openai", "openai_compatible", "groq"):
            return _send_openai_chat(config, messages, system_prompt, timeout)
        elif provider == "google_gemini":
            return _send_gemini_chat(config, messages, system_prompt, timeout)
        elif provider == "anthropic":
            return _send_anthropic_chat(config, messages, system_prompt, timeout)
        else:
            return False, f"Unsupported provider: {provider}."
    except Exception as exc:
        clean_err = sanitize_error_message(str(exc), config.api_key)
        return False, f"AI generation error: {clean_err}"


def _send_openai_chat(
    config: AIProviderConfig,
    messages: List[ChatMessage],
    system_prompt: Optional[str],
    timeout: float,
) -> Tuple[bool, str]:
    from openai import OpenAI

    base_url = config.get_effective_base_url()
    api_key = config.api_key.strip() if config.api_key else "not-needed"

    client = OpenAI(
        api_key=api_key,
        base_url=base_url if base_url != "https://api.openai.com/v1" else None,
        timeout=timeout,
    )

    formatted_msgs = []
    if system_prompt:
        formatted_msgs.append({"role": "system", "content": system_prompt})

    for m in messages:
        # Standardize role for OpenAI
        r = "user" if m.role == "user" else ("assistant" if m.role == "assistant" else "system")
        formatted_msgs.append({"role": r, "content": m.content})

    response = client.chat.completions.create(
        model=config.model.strip(),
        messages=formatted_msgs,
        temperature=config.temperature,
        max_tokens=config.max_tokens,
    )

    if response and response.choices and response.choices[0].message:
        reply = response.choices[0].message.content or ""
        return True, reply
    return False, "No text response was returned by the OpenAI model."


def _send_gemini_chat(
    config: AIProviderConfig,
    messages: List[ChatMessage],
    system_prompt: Optional[str],
    timeout: float,
) -> Tuple[bool, str]:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=config.api_key.strip())

    # Build Gemini content list preserving multi-turn history
    gemini_contents = []
    for m in messages:
        role = "user" if m.role == "user" else "model"
        gemini_contents.append(
            types.Content(
                role=role,
                parts=[types.Part.from_text(text=m.content)]
            )
        )

    config_params = types.GenerateContentConfig(
        temperature=config.temperature,
        max_output_tokens=config.max_tokens,
    )
    if system_prompt:
        config_params.system_instruction = system_prompt

    response = client.models.generate_content(
        model=config.model.strip(),
        contents=gemini_contents,
        config=config_params,
    )

    if response and response.text:
        return True, response.text
    return False, "No text response was returned by Google Gemini."


def _send_anthropic_chat(
    config: AIProviderConfig,
    messages: List[ChatMessage],
    system_prompt: Optional[str],
    timeout: float,
) -> Tuple[bool, str]:
    headers = {
        "x-api-key": config.api_key.strip(),
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    anthropic_msgs = []
    for m in messages:
        r = "user" if m.role == "user" else "assistant"
        anthropic_msgs.append({"role": r, "content": m.content})

    payload = {
        "model": config.model.strip(),
        "max_tokens": config.max_tokens,
        "temperature": config.temperature,
        "messages": anthropic_msgs,
    }
    if system_prompt:
        payload["system"] = system_prompt

    url = "https://api.anthropic.com/v1/messages"
    resp = requests.post(url, headers=headers, json=payload, timeout=timeout)

    if resp.status_code == 200:
        data = resp.json()
        content_blocks = data.get("content", [])
        text_parts = [b.get("text", "") for b in content_blocks if b.get("type") == "text"]
        reply = "".join(text_parts).strip()
        return True, reply if reply else "Empty response received."

    data = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
    err_msg = data.get("error", {}).get("message", resp.text)
    return False, f"Anthropic error ({resp.status_code}): {sanitize_error_message(err_msg, config.api_key)}"
