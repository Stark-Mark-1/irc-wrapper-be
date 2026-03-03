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


# Magic bytes for common formats
IMAGE_MAGIC_BYTES = {
    b"\xff\xd8\xff": "image/jpg",  # Z.ai OCR specifically asks for JPG, not JPEG
    b"\x89PNG\r\n\x1a\n": "image/png",
    b"GIF87a": "image/gif",
    b"GIF89a": "image/gif",
    b"RIFF": "image/webp",
}


def validate_image_content(data: bytes) -> str:
    """
    Validate that the given bytes represent a valid image or PDF.
    """
    for magic, mime_type in IMAGE_MAGIC_BYTES.items():
        if data.startswith(magic):
            return mime_type

    # WebP check
    if data[:4] == b"RIFF" and len(data) > 12 and data[8:12] == b"WEBP":
        return "image/webp"
    
    # PDF check
    if data.startswith(b"%PDF"):
        return "application/pdf"

    raise ValueError("Invalid format. Supported: JPG, PNG, GIF, WebP, PDF")


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
from app.utils.imagekit_service import imagekit_service


class DomainLlmWrapper:
    """
    A wrapper that delegates to ZaiService (GLM-4) for all modes.
    Now uses ImageKit for hosting visual content for GLM-4.6v.
    """

    def __init__(
        self,
        *,
        api_key: str | None = None,
        text_model: str | None = None,
        vision_model: str | None = None,
        master_prompt: str | None = None,
    ) -> None:
        self._text_service = ZaiService(
            api_key=api_key,
            model=text_model or settings.default_text_model,
            master_prompt=master_prompt
        )
        self._vision_service = ZaiService(
            api_key=api_key,
            model=vision_model or settings.default_vision_model,
            master_prompt=master_prompt
        )

    def llm_name(self) -> str:
        return self._text_service.llm_name()

    def text_model_name(self) -> str:
        return self._text_service.model_name()

    def vision_model_name(self) -> str:
        return self._vision_service.model_name()

    def master_prompt(self) -> str:
        return self._text_service.custom_prompt()

    async def stream_chat(self, messages: list[dict[str, Any]]) -> AsyncIterator[str]:
        async for chunk in self._text_service.generate_response_stream(messages):
            yield chunk

    async def stream_image_analysis(
        self,
        *,
        prompt: str,
        image_url: str | None = None,
        image_base64: str | None = None,
        prior_messages: list[dict[str, Any]] | None = None,
        mime_type: str = "image/jpg",
    ) -> AsyncIterator[str]:
        """
        Analyze an image using GLM's multimodal chat capabilities.
        Uses ImageKit to host the image if only base64 is provided.
        """
        if not image_url and not image_base64:
            yield "Image analysis requires either image_url or image_base64."
            return
        
        final_image_url = image_url
        if not final_image_url and image_base64:
            # Upload base64 to ImageKit
            try:
                # Convert base64 string to bytes
                import base64
                image_bytes = base64.b64decode(image_base64)
                final_image_url = imagekit_service.upload_file(image_bytes, "analysis_image.jpg")
            except Exception as e:
                yield f"Failed to upload image to ImageKit: {str(e)}"
                return

        messages: list[dict[str, Any]] = []
        if prior_messages:
            messages.extend(prior_messages)
            
        content: list[dict[str, Any]] = []
        if final_image_url:
            # Simple heuristic for ImageKit URLs or others
            is_pdf = final_image_url.lower().split("?")[0].endswith(".pdf")
            content_type = "file_url" if is_pdf else "image_url"
            
            # Use multimodal format matching user's example
            content.append({
                "type": content_type,
                content_type: {"url": final_image_url}
            })
        
        content.append({
            "type": "text",
            "text": prompt
        })
        
        messages.append({"role": "user", "content": content})
        
        async for token in self._vision_service.generate_response_stream(messages):
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
        Analyze a file (PDF, JPEG, PNG, etc.) using GLM multimodal chat.
        Files are uploaded to ImageKit first.
        """
        if not file_bytes or not file_type:
            yield "File analysis requires both file_bytes and file_type."
            return
        
        file_type = file_type.lower().replace("jpeg", "jpg")
        
        # Upload to ImageKit
        try:
            file_name = f"analysis_file.{file_type}"
            hosted_url = imagekit_service.upload_file(file_bytes, file_name)
        except Exception as e:
            yield f"Failed to upload file to ImageKit: {str(e)}"
            return
            
        # Delegate to stream_image_analysis using the hosted URL
        async for token in self.stream_image_analysis(
            prompt=prompt,
            image_url=hosted_url,
            prior_messages=prior_messages,
        ):
            yield token
