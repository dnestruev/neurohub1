"""High-level NeuroHub client."""

from __future__ import annotations

from collections.abc import AsyncIterator, Sequence

from .config import ProviderConfig, load_config
from .models import ChatMessage, ChatResponse, StreamChunk
from .providers import create_provider


class NeuroClient:
    """Unified async client for supported chat providers."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config
        self._provider = create_provider(config)

    @classmethod
    def from_env(cls, provider: str | None = None, model: str | None = None) -> "NeuroClient":
        return cls(load_config(provider=provider, model=model))

    async def ask(self, prompt: str | Sequence[ChatMessage], *, system: str | None = None) -> str:
        response = await self.complete(prompt, system=system)
        return response.content

    async def complete(
        self,
        prompt: str | Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> ChatResponse:
        return await self._provider.ask(self._messages(prompt, system=system))

    async def stream(
        self,
        prompt: str | Sequence[ChatMessage],
        *,
        system: str | None = None,
    ) -> AsyncIterator[StreamChunk]:
        async for chunk in self._provider.stream(self._messages(prompt, system=system)):
            yield chunk

    @staticmethod
    def _messages(prompt: str | Sequence[ChatMessage], *, system: str | None = None) -> list[ChatMessage]:
        if isinstance(prompt, str):
            messages: list[ChatMessage] = []
            if system:
                messages.append(ChatMessage("system", system))
            messages.append(ChatMessage("user", prompt))
            return messages
        if system:
            return [ChatMessage("system", system), *prompt]
        return list(prompt)
