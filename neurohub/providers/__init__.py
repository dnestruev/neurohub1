"""Provider factory."""

from __future__ import annotations

from neurohub.config import ProviderConfig

from .anthropic import AnthropicProvider
from .base import Provider
from .gemini import GeminiProvider
from .openai_compat import OpenAICompatibleProvider


def create_provider(config: ProviderConfig) -> Provider:
    if config.provider == "anthropic":
        return AnthropicProvider(config)
    if config.provider == "gemini":
        return GeminiProvider(config)
    return OpenAICompatibleProvider(config)
