from __future__ import annotations

import pytest

from neurohub.config import ConfigError, clean_env_value, provider_from_mapping, validate_url


def test_clean_env_value_removes_hidden_control_characters() -> None:
    assert clean_env_value("\x16 https://api.example.com/v1 \x16") == "https://api.example.com/v1"


def test_validate_url_rejects_non_url() -> None:
    with pytest.raises(ConfigError, match="valid http"):
        validate_url("not a url", name="OPENAI_BASE_URL")


def test_provider_config_sanitizes_base_url_and_key() -> None:
    config = provider_from_mapping(
        {
            "OPENAI_API_KEY": "\x16sk-test\x16",
            "OPENAI_BASE_URL": "https://api.example.com/v1\x16",
        },
        "openai",
    )

    assert config.api_key == "sk-test"
    assert config.base_url == "https://api.example.com/v1"
