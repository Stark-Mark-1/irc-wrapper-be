from __future__ import annotations

import base64
from collections.abc import AsyncIterator
from typing import Any, Literal

from openai import AsyncOpenAI

from app.config import settings

Role = Literal["system", "developer", "user", "assistant"]


class DomainLlmWrapper:
    """
    A single wrapper that:
    - injects a master (domain) prompt for every request
    - normalizes responses to AsyncIterator[str] (streaming)
    - supports both normal chat and image analysis
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        text_model: str | None = None,
        vision_model: str | None = None,
        master_prompt: str | None = None,
    ) -> None:
        key = api_key or settings.openai_api_key
        if not key:
            raise RuntimeError("OPENAI_API_KEY is required to use DomainLlmWrapper.")
        self._client = AsyncOpenAI(api_key=key)
        self._text_model = text_model or settings.default_text_model
        self._vision_model = vision_model or settings.default_vision_model
        self._master_prompt = master_prompt or settings.master_prompt

    def llm_name(self) -> str:
        return "openai"

    def master_prompt(self) -> str:
        return self._master_prompt

    def _with_master_prompt(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        # Put master prompt up front so it dominates behavior.
        return [{"role": "developer", "content": self._master_prompt}, *messages]

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        stream = await self._client.chat.completions.create(
            model=self._text_model,
            messages=self._with_master_prompt(messages),
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

    async def stream_image_analysis(
        self,
        *,
        prompt: str,
        image_url: str | None = None,
        image_base64: str | None = None,
        prior_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        if bool(image_url) == bool(image_base64):
            raise ValueError("Provide exactly one of image_url or image_base64.")

        image_part: dict[str, Any]
        if image_url:
            image_part = {"type": "image_url", "image_url": {"url": image_url}}
        else:
            # Accept raw base64 and convert to a data URL.
            # If caller already sends a data URL, preserve it.
            b64 = image_base64 or ""
            if b64.startswith("data:"):
                data_url = b64
            else:
                # Validate base64 without fully decoding to bytes in memory-heavy ways
                try:
                    base64.b64decode(b64, validate=True)
                except Exception as e:  # noqa: BLE001
                    raise ValueError("image_base64 must be valid base64 or a data URL.") from e
                data_url = f"data:image/jpeg;base64,{b64}"
            image_part = {"type": "image_url", "image_url": {"url": data_url}}

        msgs: list[dict[str, Any]] = []
        if prior_messages:
            msgs.extend(prior_messages)
        msgs.append(
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    image_part,
                ],
            }
        )

        stream = await self._client.chat.completions.create(
            model=self._vision_model,
            messages=self._with_master_prompt(msgs),
            stream=True,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta
            if delta and delta.content:
                yield delta.content

