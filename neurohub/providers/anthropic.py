"""Anthropic Claude provider."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from neurohub.models import ChatMessage, ChatResponse, StreamChunk

from .base import Provider


class AnthropicProvider(Provider):
    """Provider implementation for Anthropic Messages API."""

    _url = "https://api.anthropic.com/v1/messages"

    async def _ask(self, messages: Sequence[ChatMessage]) -> ChatResponse:
        system, chat_messages = self._split_system(messages)
        payload: dict[str, object] = {
            "model": self.config.model,
            "max_tokens": 4096,
            "messages": chat_messages,
        }
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(self._url, headers=self._headers(), json=payload)
            response.raise_for_status()
            data = response.json()
        usage = data.get("usage") or {}
        text = "".join(part.get("text", "") for part in data.get("content", []) if part.get("type") == "text")
        return ChatResponse(text, data.get("model", self.config.model), self.config.provider, usage.get("input_tokens"), usage.get("output_tokens"))

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[StreamChunk]:
        system, chat_messages = self._split_system(messages)
        payload: dict[str, object] = {
            "model": self.config.model,
            "max_tokens": 4096,
            "messages": chat_messages,
            "stream": True,
        }
        if system:
            payload["system"] = system
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream("POST", self._url, headers=self._headers(), json=payload) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    data = json.loads(line.removeprefix("data: "))
                    if data.get("type") == "content_block_delta":
                        text = data.get("delta", {}).get("text", "")
                        if text:
                            yield StreamChunk(text, self.config.model, self.config.provider)
                    elif data.get("type") == "message_stop":
                        yield StreamChunk("", self.config.model, self.config.provider, done=True)

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self.config.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    @staticmethod
    def _split_system(messages: Sequence[ChatMessage]) -> tuple[str, list[dict[str, str]]]:
        system_parts = [message.content for message in messages if message.role == "system"]
        chat = [message.as_dict() for message in messages if message.role != "system"]
        return "\n\n".join(system_parts), chat
