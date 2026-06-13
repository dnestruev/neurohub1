from __future__ import annotations

import asyncio

import pytest

from neurohub.web_app import ApiError, handle_chat


def test_web_app_rejects_placeholder_key() -> None:
    with pytest.raises(ApiError, match="настоящий API ключ"):
        asyncio.run(
            handle_chat(
                {
                    "provider": "openai",
                    "apiKey": "sk-...",
                    "messages": [{"role": "user", "content": "hello"}],
                }
            )
        )


def test_web_app_rejects_empty_messages() -> None:
    with pytest.raises(ApiError, match="Напиши сообщение"):
        asyncio.run(handle_chat({"provider": "openai", "apiKey": "sk-test", "messages": []}))
