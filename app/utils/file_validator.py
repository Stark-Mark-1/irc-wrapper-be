"""File validation utilities for uploaded files."""

import os
from io import BytesIO


class FileValidator:
    """Validates uploaded files for Zai API compatibility."""
    
    # Constants
    MAX_IMAGE_SIZE_MB = 10
    MAX_PDF_SIZE_MB = 50
    MAX_PDF_PAGES = 100
    SUPPORTED_FORMATS = {"pdf", "jpg", "jpeg", "png"}
    
    # Magic bytes for file format detection
    MAGIC_BYTES = {
        "jpg": [
            b"\xff\xd8\xff\xe0",  # JFIF
            b"\xff\xd8\xff\xe1",  # EXIF
            b"\xff\xd8\xff\xe2",  # Canon
            b"\xff\xd8\xff\xe3",  # Samsung
            b"\xff\xd8\xff\xe8",  # SPIFF
        ],
        "png": [b"\x89PNG\r\n\x1a\n"],
        "pdf": [b"%PDF-"],
    }
    
    @staticmethod
    def validate_file(
        file_bytes: bytes,
        filename: str
    ) -> tuple[str, str | None]:
        """
        Validate file format, size, and content.
        
        Args:
            file_bytes: The file content as bytes
            filename: The original filename
            
        Returns:
            tuple[str, str | None]: (normalized_file_type, error_message)
            If validation passes, error_message is None
            If validation fails, error_message contains the reason
        """
        # Validation order: extension, size, magic bytes, PDF pages
        
        # 1. Validate extension
        file_type, error = FileValidator._validate_extension(filename)
        if error:
            return (None, error)
        
        # 2. Validate size
        error = FileValidator._validate_size(file_bytes, file_type)
        if error:
            return (None, error)
        
        # 3. Validate magic bytes
        error = FileValidator._validate_magic_bytes(file_bytes, file_type)
        if error:
            return (None, error)
        
        # 4. Validate PDF pages (only for PDFs)
        if file_type == "pdf":
            error = FileValidator._validate_pdf_pages(file_bytes)
            if error:
                return (None, error)
        
        return (file_type, None)

    
    @staticmethod
    def _validate_extension(filename: str) -> tuple[str | None, str | None]:
        """
        Extract and validate file extension.
        
        Args:
            filename: The original filename
            
        Returns:
            tuple[str | None, str | None]: (normalized_extension, error_message)
        """
        if not filename:
            return (None, "Filename is required")
        
        # Extract extension
        _, ext = os.path.splitext(filename)
        if not ext:
            return (None, "File must have an extension. Supported formats: PDF, JPG, JPEG, PNG")
        
        # Remove leading dot and normalize to lowercase
        ext = ext.lstrip('.').lower()
        
        # Check if supported
        if ext not in FileValidator.SUPPORTED_FORMATS:
            return (None, f"Unsupported file type '.{ext}'. Supported formats: PDF, JPG, JPEG, PNG")
        
        # Normalize jpeg to jpg
        if ext == "jpeg":
            ext = "jpg"
        
        return (ext, None)
