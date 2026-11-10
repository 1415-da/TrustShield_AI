"""Provider factory. Falls back to the mock provider when no API key is configured."""

from __future__ import annotations

from app.core.config import get_settings
from app.services.llm.base import LLMError, LLMProvider, LLMResponse
from app.services.llm.mock import MockProvider
from app.services.llm.openai_compat import AzureOpenAIProvider, OpenAICompatibleProvider

_override: LLMProvider | None = None


def set_provider_override(provider: LLMProvider | None) -> None:
    """Test hook: force a specific provider instance."""
    global _override
    _override = provider


def get_provider() -> LLMProvider:
    if _override is not None:
        return _override
    s = get_settings()
    kind = s.effective_llm_provider
    if kind == "openai":
        return OpenAICompatibleProvider(s.openai_api_key, s.openai_model, s.openai_base_url, s.llm_timeout_seconds)
    if kind == "azure":
        return AzureOpenAIProvider(s.openai_api_key, s.openai_model, s.openai_base_url, s.azure_openai_api_version, s.llm_timeout_seconds)
    return MockProvider()


__all__ = ["LLMError", "LLMProvider", "LLMResponse", "MockProvider", "get_provider", "set_provider_override"]
