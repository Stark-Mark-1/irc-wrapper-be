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
        """
        Analyze an image with the LLM.
        """
        if not image_url and not image_base64:
            yield "Image analysis requires either image_url or image_base64."
            return
        
        if image_url:
            validate_image_url(image_url)
        
        messages: list[dict[str, Any]] = []
        if prior_messages:
            messages.extend(prior_messages)
        
        # Zhipu/GLM format: content is a list of objects
        content: list[dict[str, Any]] = [
            {"type": "text", "text": prompt}
        ]
        
        if image_url:
            content.append({
                "type": "image_url",
                "image_url": {"url": image_url}
            })
        elif image_base64:
            # Most modern endpoints (including OpenAI and GLM) prefer data URIs for raw base64
            # We skip validation here as it's done earlier in the DTO or by the LLM
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}
            })
        
        messages.append({"role": "user", "content": content})
        
        async for token in self._service.generate_response_stream(messages):
            yield token

    async def stream_file_analysis(
        self,
        *,
        prompt: str,
        file_bytes: bytes | None = None,
        file_type: str | None = None,
        prior_messages: list[dict[str, Any]] | None = None,
    ) -> AsyncIterator[str]:
        """
        Analyze a file (PDF, JPEG, PNG, etc.) with the LLM.
        """
        if not file_bytes or not file_type:
            yield "File analysis requires both file_bytes and file_type."
            return
        
        file_type = file_type.lower().replace("jpg", "jpeg")
        
        # Check if the file is an image. If so, use image analysis path.
        is_image = file_type in ["jpeg", "png", "webp", "gif"]
        
        if is_image:
            import base64
            file_base64 = base64.b64encode(file_bytes).decode("utf-8")
            async for token in self.stream_image_analysis(
                prompt=prompt,
                image_base64=file_base64,
                prior_messages=prior_messages
            ):
                yield token
            return

        # For non-image files (like PDF), use a structured text prompt for now
        # OR if the model supports document input (GLM-4-plus does), we could use document format
        # However, for maximum compatibility, we'll use a better-formatted text wrapper
        import base64
        file_base64 = base64.b64encode(file_bytes).decode("utf-8")
        
        messages: list[dict[str, Any]] = []
        if prior_messages:
            messages.extend(prior_messages)
        
        # For PDF, GLM-4-plus often prefers specific document tags or simply text context
        # We'll stick to a slightly improved version of the previous implementation
        # but warn that PDF is best handled by specific document models if possible.
        messages.append({
            "role": "user",
            "content": (
                f"I have attached a {file_type.upper()} file for your analysis. "
                "Please process the content and answer my request.\n\n"
                f"[{file_type.upper()}_FILE_CONTENT_BASE64_START]\n"
                f"{file_base64[:500]}... (truncated for brevity in logs) ...{file_base64[-500:] if len(file_base64) > 1000 else ''}\n"
                f"[{file_type.upper()}_FILE_CONTENT_BASE64_END]\n\n"
                f"User Request: {prompt}"
            )
        })
        
        # Note: We don't actually truncate the base64 above in the REAL message sent to LLM
        # I just wrote it that way in the comment/plan. Let's fix it to send FULL content.
        messages[-1]["content"] = (
            f"Please analyze the following {file_type.upper()} file (base64 encoded):\n\n"
            f"[{file_type.upper()}_FILE_START]\n{file_base64}\n[{file_type.upper()}_FILE_END]\n\n"
            f"User request: {prompt}"
        )

        async for token in self._service.generate_response_stream(messages):
            yield token

