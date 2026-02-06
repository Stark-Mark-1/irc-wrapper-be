from __future__ import annotations

import pytest

from app.llm_services.domain_llm_wrapper import (
    validate_image_content,
    validate_image_url,
)
from app.utils.jwtutils import extract_bearer_token, validate_token


class TestImageUrlValidation:
    """Tests for SSRF protection in image URL validation."""

    def test_rejects_http_url(self) -> None:
        """Test that HTTP URLs are rejected."""
        with pytest.raises(ValueError, match="Only HTTPS URLs are allowed"):
            validate_image_url("http://example.com/image.jpg")

    def test_accepts_https_url(self) -> None:
        """Test that HTTPS URLs are accepted."""
        # This will fail with DNS resolution error for fake domain
        # but won't raise the HTTPS error
        try:
            validate_image_url("https://example.com/image.jpg")
        except ValueError as e:
            assert "HTTPS" not in str(e)

    def test_rejects_missing_hostname(self) -> None:
        """Test that URLs without hostname are rejected."""
        with pytest.raises(ValueError, match="missing hostname"):
            validate_image_url("https:///path/to/image.jpg")

    def test_rejects_localhost(self) -> None:
        """Test that localhost URLs are rejected."""
        with pytest.raises(ValueError, match="private/internal IP"):
            validate_image_url("https://localhost/image.jpg")

    def test_rejects_private_ip(self) -> None:
        """Test that private IPs are rejected."""
        with pytest.raises(ValueError, match="private/internal IP"):
            validate_image_url("https://192.168.1.1/image.jpg")

        with pytest.raises(ValueError, match="private/internal IP"):
            validate_image_url("https://10.0.0.1/image.jpg")

        with pytest.raises(ValueError, match="private/internal IP"):
            validate_image_url("https://172.16.0.1/image.jpg")


class TestImageContentValidation:
    """Tests for image content type validation."""

    def test_validates_jpeg(self) -> None:
        """Test JPEG magic bytes detection."""
        jpeg_header = b"\xff\xd8\xff\xe0\x00\x10JFIF"
        assert validate_image_content(jpeg_header) == "image/jpeg"

    def test_validates_png(self) -> None:
        """Test PNG magic bytes detection."""
        png_header = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        assert validate_image_content(png_header) == "image/png"

    def test_validates_gif(self) -> None:
        """Test GIF magic bytes detection."""
        gif87_header = b"GIF87a\x00\x00\x00\x00"
        assert validate_image_content(gif87_header) == "image/gif"

        gif89_header = b"GIF89a\x00\x00\x00\x00"
        assert validate_image_content(gif89_header) == "image/gif"

    def test_validates_webp(self) -> None:
        """Test WebP magic bytes detection."""
        webp_header = b"RIFF\x00\x00\x00\x00WEBP"
        assert validate_image_content(webp_header) == "image/webp"

    def test_rejects_invalid_format(self) -> None:
        """Test rejection of non-image content."""
        with pytest.raises(ValueError, match="Invalid image format"):
            validate_image_content(b"Not an image content")

        with pytest.raises(ValueError, match="Invalid image format"):
            validate_image_content(b"<html><body>Hello</body></html>")


class TestJwtUtils:
    """Tests for JWT utilities."""

    def test_extract_bearer_token_valid(self) -> None:
        """Test extracting valid bearer token."""
        token = extract_bearer_token("Bearer my-token-123")
        assert token == "my-token-123"

    def test_extract_bearer_token_case_insensitive(self) -> None:
        """Test bearer prefix is case insensitive."""
        token = extract_bearer_token("bearer my-token")
        assert token == "my-token"

        token = extract_bearer_token("BEARER my-token")
        assert token == "my-token"

    def test_extract_bearer_token_none(self) -> None:
        """Test None header."""
        token = extract_bearer_token(None)
        assert token is None

    def test_extract_bearer_token_empty(self) -> None:
        """Test empty header."""
        token = extract_bearer_token("")
        assert token is None

    def test_extract_bearer_token_no_bearer_prefix(self) -> None:
        """Test token without Bearer prefix."""
        token = extract_bearer_token("just-a-token")
        assert token is None

    def test_validate_token_invalid(self) -> None:
        """Test that invalid tokens return None."""
        result = validate_token("invalid-token")
        assert result is None

    def test_validate_token_expired(self) -> None:
        """Test that expired tokens return None."""
        # This is an expired JWT (exp in the past)
        expired_token = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJ1c2VySWQiOiIxMjMiLCJleHAiOjB9.invalid"
        result = validate_token(expired_token)
        assert result is None
