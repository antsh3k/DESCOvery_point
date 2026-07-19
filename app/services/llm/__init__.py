"""LLM client factory. Provider selected by settings; key required at call time."""

from __future__ import annotations

from app.config import Settings, get_settings
from app.enums import LLMProvider
from app.services.llm.base import LLMClient, LLMError

__all__ = ["LLMClient", "LLMError", "get_llm_client"]


def get_llm_client(settings: Settings | None = None) -> LLMClient:
    """Build the configured LLM client, or raise if its API key is missing."""
    settings = settings or get_settings()
    provider = settings.llm_provider.lower()

    if provider == LLMProvider.anthropic:
        if not settings.anthropic_api_key:
            raise LLMError("ANTHROPIC_API_KEY is not set")
        from app.services.llm.anthropic_client import AnthropicClient

        return AnthropicClient(settings.anthropic_api_key, settings.anthropic_model)

    if provider == LLMProvider.openai:
        if not settings.openai_api_key:
            raise LLMError("OPENAI_API_KEY is not set")
        from app.services.llm.openai_client import OpenAIClient

        return OpenAIClient(settings.openai_api_key, settings.openai_model)

    raise LLMError(f"Unknown LLM provider: {settings.llm_provider!r}")
