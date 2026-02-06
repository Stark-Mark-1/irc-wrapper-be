from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx

from app.config import settings
from app.llm_services.llm_service import LlmService


class ZaiService(LlmService):
    """
    Z.ai API service implementation.

    Uses httpx to call the Z.ai API endpoint.
    Note: Z.ai API is non-streaming, but we wrap the response as a stream
    for consistency with the LlmService interface.
    """

    ZAI_API_URL = "https://api.z.ai/api/paas/v4/chat/completions"

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str = "zai-1.0",
        master_prompt: str | None = None,
    ) -> None:
        self._api_key = api_key or settings.zai_api_key
        if not self._api_key:
            raise RuntimeError("ZAI_API_KEY is required to use ZaiService.")
        self._model = model
        self._master_prompt = master_prompt or settings.master_prompt

    def llm_name(self) -> str:
        return "zai"

    def model_name(self) -> str:
        return self._model

    def custom_prompt(self) -> str:
        return self._master_prompt

    def _with_master_prompt(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Prepend the master prompt as a system message."""
        return [{"role": "system", "content": self._master_prompt}, *messages]

    async def generate_response_stream(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        """
        Generate a response from Z.ai API.

        Note: Z.ai is non-streaming, so we yield the full response at once.
        """
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(
                self.ZAI_API_URL,
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self._model,
                    "messages": self._with_master_prompt(messages),
                    "stream": False,
                },
            )
            response.raise_for_status()
            data = response.json()

            # Extract the assistant message content
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
            if content:
                yield content
