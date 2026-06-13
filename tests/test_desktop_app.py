from __future__ import annotations

import pytest

from neurohub.desktop_app import DesktopConfigError, DesktopSettings, build_provider_config


def test_desktop_config_rejects_placeholder_key() -> None:
    settings = DesktopSettings(api_keys={"openai": "sk-..."})

    with pytest.raises(DesktopConfigError, match="настоящий API ключ"):
        build_provider_config(settings)


def test_desktop_config_builds_sanitized_provider_config() -> None:
    settings = DesktopSettings(
        provider="openai",
        model="gpt-4o-mini",
        base_url="https://api.example.com/v1\x16",
        api_keys={"openai": "\x16sk-real\x16"},
    )

    config = build_provider_config(settings)

    assert config.api_key == "sk-real"
    assert config.base_url == "https://api.example.com/v1"
