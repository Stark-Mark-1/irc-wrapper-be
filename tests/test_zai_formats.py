import pytest
import base64
from unittest.mock import AsyncMock, patch
from app.llm_services.domain_llm_wrapper import DomainLlmWrapper

@pytest.mark.asyncio
async def test_image_analysis_message_format():
    wrapper = DomainLlmWrapper(api_key="test-key")
    
    # Mock the internal ZaiService.generate_response_stream
    with patch("app.llm_services.zai_service.ZaiService.generate_response_stream") as mock_gen:
        mock_gen.return_value.__aiter__.return_value = ["response"]
        
        prompt = "Describe this image"
        image_b64 = "YmFzZTY0ZGF0YQ==" # "base64data"
        
        async for _ in wrapper.stream_image_analysis(
            prompt=prompt,
            image_base64=image_b64
        ):
            pass
        
        # Verify the message structure
        args, _ = mock_gen.call_args
        messages = args[0]
        
        assert len(messages) == 1
        user_msg = messages[0]
        assert user_msg["role"] == "user"
        content = user_msg["content"]
        assert isinstance(content, list)
        assert content[0] == {"type": "text", "text": prompt}
        assert content[1]["type"] == "image_url"
        assert content[1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        assert image_b64 in content[1]["image_url"]["url"]

@pytest.mark.asyncio
async def test_file_analysis_image_redirect():
    wrapper = DomainLlmWrapper(api_key="test-key")
    
    with patch("app.llm_services.zai_service.ZaiService.generate_response_stream") as mock_gen:
        mock_gen.return_value.__aiter__.return_value = ["response"]
        
        prompt = "Analyze this file"
        file_bytes = b"fake-image-bytes"
        file_type = "png"
        
        async for _ in wrapper.stream_file_analysis(
            prompt=prompt,
            file_bytes=file_bytes,
            file_type=file_type
        ):
            pass
        
        # Verify it redirected to image analysis format
        args, _ = mock_gen.call_args
        messages = args[0]
        
        user_msg = messages[0]
        content = user_msg["content"]
        assert isinstance(content, list)
        assert content[1]["type"] == "image_url"
        assert "image/jpeg" in content[1]["image_url"]["url"] # We used jpeg in wrapper as default mime
        
@pytest.mark.asyncio
async def test_file_analysis_pdf_format():
    wrapper = DomainLlmWrapper(api_key="test-key")
    
    with patch("app.llm_services.zai_service.ZaiService.generate_response_stream") as mock_gen:
        mock_gen.return_value.__aiter__.return_value = ["response"]
        
        prompt = "Analyze this PDF"
        file_bytes = b"fake-pdf-bytes"
        file_type = "pdf"
        
        async for _ in wrapper.stream_file_analysis(
            prompt=prompt,
            file_bytes=file_bytes,
            file_type=file_type
        ):
            pass
        
        # Verify it uses the text format for PDF
        args, _ = mock_gen.call_args
        messages = args[0]
        
        user_msg = messages[0]
        assert isinstance(user_msg["content"], str)
        assert "[PDF_FILE_START]" in user_msg["content"]
        assert prompt in user_msg["content"]
