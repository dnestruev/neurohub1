"""Configuration loading and sanitising helpers."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlsplit

from dotenv import load_dotenv

DEFAULT_MODELS: dict[str, str] = {
    "openai": "gpt-4o-mini",
    "anthropic": "claude-3-5-sonnet-20241022",
    "gemini": "gemini-2.0-flash",
    "openrouter": "openai/gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "groq": "llama-3.3-70b-versatile",
}

DEFAULT_BASE_URLS: dict[str, str] = {
    "openai": "https://api.openai.com/v1",
    "openrouter": "https://openrouter.ai/api/v1",
    "deepseek": "https://api.deepseek.com",
    "groq": "https://api.groq.com/openai/v1",
}

API_KEY_ENV: dict[str, str] = {
    "openai": "OPENAI_API_KEY",
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GEMINI_API_KEY",
    "openrouter": "OPENROUTER_API_KEY",
    "deepseek": "DEEPSEEK_API_KEY",
    "groq": "GROQ_API_KEY",
}

_CONTROL_TRANSLATION = {ord(char): None for char in map(chr, range(32)) if char not in "\t\n\r"}


class ConfigError(ValueError):
    """Raised when NeuroHub configuration is invalid."""


def clean_env_value(value: str | None) -> str:
    """Strip quotes/space and remove hidden control characters from env values.

    Copy-pasting keys or URLs from chats and web pages can introduce bytes such as
    ``\x16``. httpx then raises ``InvalidURL: Invalid non-printable ASCII`` before
    a request is made. Cleaning values at the config boundary keeps the CLI usable
    and lets us show a targeted error message for malformed URLs.
    """

    if value is None:
        return ""
    cleaned = value.translate(_CONTROL_TRANSLATION).strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        cleaned = cleaned[1:-1].strip()
    return cleaned


def validate_url(url: str, *, name: str) -> str:
    """Return a sanitized URL or raise a helpful configuration error."""

    url = clean_env_value(url)
    if not url:
        raise ConfigError(f"{name} is empty")
    if any((ord(ch) < 32) or (ord(ch) == 127) for ch in url):
        raise ConfigError(f"{name} contains hidden control characters")
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError(f"{name} must be a valid http(s) URL, got: {url!r}")
    return url.rstrip("/")


@dataclass(frozen=True, slots=True)
class ProviderConfig:
    provider: str
    api_key: str
    model: str
    base_url: str | None = None
    timeout: float = 120.0
    max_retries: int = 3


def load_config(provider: str | None = None, model: str | None = None) -> ProviderConfig:
    """Load provider settings from environment and ``.env``."""

    load_dotenv()
    provider_name = clean_env_value(provider or os.getenv("NEUROHUB_DEFAULT_PROVIDER") or "openai").lower()
    if provider_name not in API_KEY_ENV:
        supported = ", ".join(sorted(API_KEY_ENV))
        raise ConfigError(f"Unknown provider {provider_name!r}. Supported: {supported}")

    api_key = clean_env_value(os.getenv(API_KEY_ENV[provider_name]))
    if not api_key:
        raise ConfigError(f"Missing API key: set {API_KEY_ENV[provider_name]} in .env")

    selected_model = clean_env_value(model or os.getenv("NEUROHUB_DEFAULT_MODEL") or "")
    if not selected_model:
        selected_model = DEFAULT_MODELS[provider_name]

    base_url = None
    env_name = f"{provider_name.upper()}_BASE_URL"
    raw_base_url = os.getenv(env_name) or DEFAULT_BASE_URLS.get(provider_name)
    if raw_base_url:
        base_url = validate_url(raw_base_url, name=env_name)

    timeout = float(clean_env_value(os.getenv("NEUROHUB_TIMEOUT")) or 120)
    max_retries = int(clean_env_value(os.getenv("NEUROHUB_MAX_RETRIES")) or 3)

    return ProviderConfig(
        provider=provider_name,
        api_key=api_key,
        model=selected_model,
        base_url=base_url,
        timeout=timeout,
        max_retries=max_retries,
    )


def provider_from_mapping(values: Mapping[str, str], provider: str) -> ProviderConfig:
    """Build config from a mapping; used by tests and embedding applications."""

    old = os.environ.copy()
    try:
        os.environ.clear()
        os.environ.update(values)
        return load_config(provider)
    finally:
        os.environ.clear()
        os.environ.update(old)
