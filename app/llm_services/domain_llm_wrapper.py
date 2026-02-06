from __future__ import annotations

import base64
import ipaddress
import socket
from collections.abc import AsyncIterator
from typing import Any, Literal
from urllib.parse import urlparse

from openai import AsyncOpenAI

from app.config import settings

Role = Literal["system", "developer", "user", "assistant"]


def _is_private_ip(ip_str: str) -> bool:
    """Check if an IP address is private/internal."""
    try:
        ip = ipaddress.ip_address(ip_str)
        return (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
        )
    except ValueError:
        return False


# Magic bytes for common image formats
IMAGE_MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpeg",
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",  # WebP starts with RIFF....WEBP
}


def validate_image_content(data: bytes) -> str:
    """
    Validate that the given bytes represent a valid image.

    Returns:
        The detected MIME type if valid

    Raises:
        ValueError if the content is not a recognized image format
    """
    for magic, mime_type in IMAGE_MAGIC_BYTES.items():
        if data.startswith(magic):
            return mime_type

    # Special check for WebP (RIFF....WEBP)
    if data[:4] == b"RIFF" and len(data) > 12 and data[8:12] == b"WEBP":
        return "image/webp"

    raise ValueError("Invalid image format. Supported formats: JPEG, PNG, GIF, WebP")


def validate_image_url(url: str) -> None:
    """
    Validate an image URL for SSRF protection.
    Raises ValueError if the URL is unsafe.
    """
    parsed = urlparse(url)

    # Enforce HTTPS only
    if parsed.scheme.lower() != "https":
        raise ValueError("Only HTTPS URLs are allowed for image_url.")

    hostname = parsed.hostname
    if not hostname:
        raise ValueError("Invalid URL: missing hostname.")

    # Resolve hostname to check for private IPs
    try:
        resolved_ips = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC, socket.SOCK_STREAM)
        for _, _, _, _, sockaddr in resolved_ips:
            ip_str = sockaddr[0]
            if _is_private_ip(ip_str):
                raise ValueError("URL resolves to a private/internal IP address.")
    except socket.gaierror:
        raise ValueError(f"Could not resolve hostname: {hostname}")


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

    def text_model_name(self) -> str:
        return self._text_model

    def vision_model_name(self) -> str:
        return self._vision_model

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
            validate_image_url(image_url)
            image_part = {"type": "image_url", "image_url": {"url": image_url}}
        else:
            # Accept raw base64 and convert to a data URL.
            # If caller already sends a data URL, preserve it.
            b64 = image_base64 or ""
            if b64.startswith("data:"):
                data_url = b64
            else:
                # Validate base64 and check image format
                try:
                    decoded = base64.b64decode(b64, validate=True)
                    # Validate it's actually an image (check magic bytes)
                    mime_type = validate_image_content(decoded[:16])
                except ValueError:
                    raise
                except Exception as e:  # noqa: BLE001
                    raise ValueError("image_base64 must be valid base64 or a data URL.") from e
                data_url = f"data:{mime_type};base64,{b64}"
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

