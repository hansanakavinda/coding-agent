"""Base interface for model providers."""

from abc import ABC, abstractmethod
from typing import Any

from core.types import ProviderResponse


class LLMProvider(ABC):
    """Abstract interface for LLM providers."""

    @abstractmethod
    def complete(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]] | None = None,
    ) -> ProviderResponse:
        """Send chat messages and tool definitions to the provider.

        Args:
            messages: OpenAI-style list of message dicts (role, content, etc.).
            tools: OpenAI-style list of tool schema dicts.

        Returns:
            ProviderResponse containing content, tool_calls, and model used.
        """
