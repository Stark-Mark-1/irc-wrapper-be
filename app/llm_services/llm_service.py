from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from typing import Any


class LlmService(ABC):
    """Abstract base class for LLM service implementations."""

    @abstractmethod
    async def generate_response_stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        """
        Generate a streaming response from the LLM.

        Args:
            messages: List of message dictionaries with 'role' and 'content' keys

        Yields:
            String tokens as they are generated
        """
        ...

    @abstractmethod
    def custom_prompt(self) -> str:
        """
        Return the system/developer prompt for this service.

        Returns:
            The custom prompt string
        """
        ...

    @abstractmethod
    def llm_name(self) -> str:
        """
        Return the name/identifier of this LLM service.

        Returns:
            The LLM name (e.g., "openai", "zai")
        """
        ...

    @abstractmethod
    def model_name(self) -> str:
        """
        Return the specific model being used.

        Returns:
            The model name (e.g., "gpt-4o-mini")
        """
        ...
