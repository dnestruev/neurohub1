"""Google Gemini provider."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

import httpx

from neurohub.models import ChatMessage, ChatResponse, StreamChunk

from .base import Provider


class GeminiProvider(Provider):
    """Provider implementation for Gemini generateContent API."""

    async def _ask(self, messages: Sequence[ChatMessage]) -> ChatResponse:
        url = self._url(stream=False)
        async with httpx.AsyncClient(timeout=self.config.timeout) as client:
            response = await client.post(url, json=self._payload(messages))
            response.raise_for_status()
            data = response.json()
        return ChatResponse(self._extract_text(data), self.config.model, self.config.provider)

    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[StreamChunk]:
        # Gemini's streaming endpoint returns a JSON array for REST; keep a simple,
        # compatible iterator by yielding the complete answer as one chunk.
        response = await self._ask(messages)
        if response.content:
            yield StreamChunk(response.content, response.model, response.provider)
        yield StreamChunk("", response.model, response.provider, done=True)

    def _url(self, *, stream: bool) -> str:
        method = "streamGenerateContent" if stream else "generateContent"
        return (
            f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{self.config.model}:{method}?key={self.config.api_key}"
        )

    @staticmethod
    def _payload(messages: Sequence[ChatMessage]) -> dict[str, object]:
        contents = []
        system_parts = []
        for message in messages:
            if message.role == "system":
                system_parts.append(message.content)
                continue
            role = "model" if message.role == "assistant" else "user"
            contents.append({"role": role, "parts": [{"text": message.content}]})
        payload: dict[str, object] = {"contents": contents}
        if system_parts:
            payload["system_instruction"] = {"parts": [{"text": "\n\n".join(system_parts)}]}
        return payload

    @staticmethod
    def _extract_text(data: dict[str, object]) -> str:
        candidates = data.get("candidates") or []
        if not candidates:
            return ""
        content = candidates[0].get("content", {})  # type: ignore[index,union-attr]
        parts = content.get("parts", [])  # type: ignore[union-attr]
        return "".join(part.get("text", "") for part in parts)
