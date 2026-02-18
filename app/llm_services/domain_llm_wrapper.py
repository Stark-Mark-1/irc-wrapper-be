from __future__ import annotations

import base64
import ipaddress
import socket
from collections.abc import AsyncIterator
from typing import Any, Literal
from urllib.parse import urlparse



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


from app.llm_services.zai_service import ZaiService


class DomainLlmWrapper:
    """
    A wrapper that delegates to ZaiService for "ZAI only" mode.
    Maintains the interface expected by strategies.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        text_model: str | None = None,
        vision_model: str | None = None,
        master_prompt: str | None = None,
    ) -> None:
        self._service = ZaiService(
            api_key=api_key,
            model=text_model or "glm-4-plus",
            master_prompt=master_prompt
        )

    def llm_name(self) -> str:
        return self._service.llm_name()

    def text_model_name(self) -> str:
        return self._service.model_name()

    def vision_model_name(self) -> str:
        return self._service.model_name()

    def master_prompt(self) -> str:
        return self._service.custom_prompt()

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        async for chunk in self._service.generate_response_stream(messages):
            yield chunk

    async def stream_image_analysis(
        self,
        *,
        prompt: str,
        image_url: str | None = None,
        image_base64: str | None = None,
        prior_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        # ZaiService doesn't support image analysis in the current implementation
        # check if Zai supports vision, if not yield a placeholder or error
        yield "Image analysis is not supported by the current Zai configuration."

