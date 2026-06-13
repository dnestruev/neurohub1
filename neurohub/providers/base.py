"""Base provider interface."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator, Sequence

from tenacity import retry, stop_after_attempt, wait_exponential

from neurohub.config import ProviderConfig
from neurohub.models import ChatMessage, ChatResponse, StreamChunk


class Provider(ABC):
    """Provider-neutral async chat API."""

    def __init__(self, config: ProviderConfig) -> None:
        self.config = config

    @retry(wait=wait_exponential(multiplier=1, min=1, max=8), stop=stop_after_attempt(3), reraise=True)
    async def ask(self, messages: Sequence[ChatMessage]) -> ChatResponse:
        return await self._ask(messages)

    @abstractmethod
    async def _ask(self, messages: Sequence[ChatMessage]) -> ChatResponse:
        """Send a non-streaming request."""

    @abstractmethod
    async def stream(self, messages: Sequence[ChatMessage]) -> AsyncIterator[StreamChunk]:
        """Send a streaming request."""
