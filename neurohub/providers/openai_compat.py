"""OpenAI-compatible chat provider implementation."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Sequence

import httpx

from neurohub.models import ChatMessage, ChatResponse, StreamChunk

from .base import Provider


class OpenAICompatibleProvider(Provider):
    """Provider for OpenAI, OpenRouter, DeepSeek, Groq and compatible APIs."""

    async def _ask(self, messages: Sequence[ChatMessage]) -> ChatResponse:
        payload = {
            "model": self.config.model,
            "messages": [message.as_dict() for message in messages],
        }
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(
                f"{self.config.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        usage = data.get("usage") or {}
        return ChatResponse(
            content=data["choices"][0]["message"].get("content") or "",
            model=data.get("model", self.config.model),
            provider=self.config.provider,
            input_tokens=usage.get("prompt_tokens"),
            output_tokens=usage.get("completion_tokens"),
        )

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[StreamChunk]:
        payload = {
            "model": self.config.model,
            "messages": [message.as_dict() for message in messages],
            "stream": True,
        }
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            async with client.stream(
                "POST",
                f"{self.config.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as response:
                response.raise_for_status()
                async for line in response.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    raw = line.removeprefix("data: ").strip()
                    if raw == "[DONE]":
                        yield StreamChunk("", self.config.model, self.config.provider, done=True)
                        break
                    data = json.loads(raw)
                    delta = data.get("choices", [{}])[0].get("delta", {})
                    content = delta.get("content") or ""
                    if content:
                        yield StreamChunk(content, data.get("model", self.config.model), self.config.provider)

    def _headers(self) -> dict[str, str]:
        headers = {"Authorization": f"Bearer {self.config.api_key}"}
        if self.config.provider == "openrouter":
            headers.update({"HTTP-Referer": "https://github.com/neurohub", "X-Title": "NeuroHub"})
        return headers
