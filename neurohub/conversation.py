"""Conversation helper with history and export."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from pathlib import Path

from .client import NeuroClient
from .models import ChatMessage, StreamChunk


class Conversation:
    """Multi-turn chat session."""

    def __init__(
        self,
        client: NeuroClient | None = None,
        *,
        system_prompt: str | None = None,
        provider: str | None = None,
        model: str | None = None,
    ) -> None:
        self.client = client or NeuroClient.from_env(provider=provider, model=model)
        self.messages: list[ChatMessage] = []
        if system_prompt:
            self.messages.append(ChatMessage("system", system_prompt))

    async def send(self, text: str) -> str:
        self.messages.append(ChatMessage("user", text))
        response = await self.client.complete(self.messages)
        self.messages.append(ChatMessage("assistant", response.content))
        return response.content

    async def stream(self, text: str) -> AsyncIterator[StreamChunk]:
        self.messages.append(ChatMessage("user", text))
        answer: list[str] = []
        async for chunk in self.client.stream(self.messages):
            if chunk.content:
                answer.append(chunk.content)
            yield chunk
        self.messages.append(ChatMessage("assistant", "".join(answer)))

    def clear(self, *, keep_system: bool = True) -> None:
        system = [message for message in self.messages if message.role == "system"] if keep_system else []
        self.messages = system[:1]

    def export(self, path: str | Path) -> Path:
        output = Path(path)
        output.write_text(
            json.dumps([message.as_dict() for message in self.messages], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return output
