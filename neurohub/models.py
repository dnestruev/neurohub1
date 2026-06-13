"""Shared data models for NeuroHub."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(slots=True)
class ChatMessage:
    """A chat message in provider-neutral form."""

    role: Role
    content: str

    def as_dict(self) -> dict[str, str]:
        return {"role": self.role, "content": self.content}


@dataclass(slots=True)
class ChatResponse:
    """A complete model response."""

    content: str
    model: str
    provider: str
    input_tokens: int | None = None
    output_tokens: int | None = None


@dataclass(slots=True)
class StreamChunk:
    """A streamed response chunk."""

    content: str
    model: str
    provider: str
    done: bool = False
