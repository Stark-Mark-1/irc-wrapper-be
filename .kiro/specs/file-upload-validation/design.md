# Design Document: File Upload Validation

## Overview

This design implements comprehensive file upload validation for the chat file analysis endpoint. The solution adds a dedicated validation module that checks file format, size, and PDF page count before files are sent to the Zai API. This prevents API errors and provides clear user feedback.

## Architecture

The validation system follows a layered approach:

1. **Router Layer** (`chat_router.py`): Receives file uploads and delegates to validator
2. **Validation Layer** (`file_validator.py`): New module containing all validation logic
3. **Strategy Layer** (`file_analysis_strategy.py`): Receives pre-validated files
4. **LLM Service Layer** (`domain_llm_wrapper.py`, `zai_service.py`): Processes validated files

The validation layer acts as a gatekeeper, ensuring only valid files reach downstream components.

## Components and Interfaces

### FileValidator Class

A new utility class that encapsulates all file validation logic:

```python
class FileValidator:
    """Validates uploaded files for Zai API compatibility."""
    
    # Constants
    MAX_IMAGE_SIZE_MB = 10
    MAX_PDF_SIZE_MB = 50
    MAX_PDF_PAGES = 100
    SUPPORTED_FORMATS = {"pdf", "jpg", "jpeg", "png"}
    
    @staticmethod
    def validate_file(
        file_bytes: bytes,
        filename: str
    ) -> tuple[str, str | None]:
        """
        Validate file format, size, and content.
        
        Returns:
            tuple[str, str | None]: (normalized_file_type, error_message)
            If validation passes, error_message is None
            If validation fails, error_message contains the reason
        """
        pass
    
    @staticmethod
    def _validate_extension(filename: str) -> tuple[str | None, str | None]:
        """Extract and validate file extension."""
        pass
    
    @staticmethod
    def _validate_size(file_bytes: bytes, file_type: str) -> str | None:
        """Validate file size against format-specific limits."""
        pass
    
    @staticmethod
    def _validate_magic_bytes(file_bytes: bytes, file_type: str) -> str | None:
        """Validate file content matches declared format using magic bytes."""
        pass
    
    @staticmethod
    def _validate_pdf_pages(file_bytes: bytes) -> str | None:
        """Validate PDF page count is within limits."""
        pass
```

### Magic Bytes Mapping

```python
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
```

### Router Integration

The `/chat/file` endpoint will be updated to use the validator:

```python
@router.post("/chat/file")
async def chat_file(...):
    # ... existing session validation ...
    
    if not file:
        raise HTTPException(status_code=400, detail="file is required")
    
    file_bytes = await file.read()
    
    # NEW: Use FileValidator
    file_type, error = FileValidator.validate_file(file_bytes, file.filename or "")
    if error:
        raise HTTPException(status_code=400, detail=error)
    
    # Continue with validated file...
```

## Data Models

### Validation Result

The validator returns a tuple representing the validation outcome:

```python
ValidationResult = tuple[str, str | None]
# (normalized_file_type, error_message)
# Examples:
# ("jpg", None) - Valid JPG file
# ("pdf", None) - Valid PDF file  
# (None, "File size exceeds 10MB limit for images") - Invalid
```

### File Type Normalization

File types are normalized to match Zai API expectations:
- "jpeg" → "jpg"
- "JPG", "JPEG", "Jpg" → "jpg"
- "PDF", "Pdf" → "pdf"
- "PNG", "Png" → "png"

## Correctness Properties

A property is a characteristic or behavior that should hold true across all valid executions of a system—essentially, a formal statement about what the system should do. Properties serve as the bridge between human-readable specifications and machine-verifiable correctness guarantees.

### Property Reflection

After analyzing all acceptance criteria, I identified the following redundancies:
- Properties 1.1 and 1.3 both test extension validation - can be combined into one property about rejecting unsupported extensions
- Properties 1.2 and 1.4 both test magic byte validation - can be combined into one property about content/extension mismatches
- Properties 2.1, 2.2, and 2.3 all test size validation - can be combined into one property about size limits per format
- Properties 3.1 and 3.2 both test PDF page validation - can be combined into one property
- Properties 4.1, 4.2, and 4.4 all test error response format - can be combined into one comprehensive property
- Properties 5.1 and 5.2 both test validation ordering - can be combined into one property about fail-fast behavior
- Properties 6.1 and 6.2 both test integration behavior - can be combined into one property about valid/invalid file handling

### Core Properties

Property 1: Extension validation rejects unsupported formats
*For any* filename with an extension not in {pdf, jpg, jpeg, png}, the validator should return an error indicating unsupported format
**Validates: Requirements 1.1, 1.3**

Property 2: Content validation detects format mismatches
*For any* file where the magic bytes don't match the declared extension, the validator should return an error indicating format mismatch
**Validates: Requirements 1.2, 1.4**

Property 3: Size validation enforces format-specific limits
*For any* file, if it's an image (jpg/png) exceeding 10MB or a PDF exceeding 50MB, the validator should return an error with the specific size limit
**Validates: Requirements 2.1, 2.2, 2.3**

Property 4: PDF page count validation enforces 100-page limit
*For any* PDF file with more than 100 pages, the validator should return an error indicating the page limit
**Validates: Requirements 3.1, 3.2**

Property 5: Validation fails fast in order
*For any* file with multiple validation issues, the validator should return an error for the first issue encountered following the order: extension, size, magic bytes, PDF pages
**Validates: Requirements 5.1, 5.2**

Property 6: Error responses are descriptive and consistent
*For any* validation failure, the error message should specify the failure reason, include supported formats/limits, and return HTTP 400 status
**Validates: Requirements 4.1, 4.2, 4.3, 4.4**

Property 7: Valid files pass through to processing
*For any* file that passes all validations, the validator should return the normalized file type with no error, and the file should be passed to the analysis strategy
**Validates: Requirements 6.1, 6.2**

Property 8: Validation failures are logged
*For any* validation failure, the system should create a log entry containing the failure reason and file metadata
**Validates: Requirements 6.3, 6.4**

## Error Handling

### Validation Errors

All validation errors return HTTP 400 with descriptive messages:

```python
# Extension validation
"Unsupported file type '.{ext}'. Supported formats: PDF, JPG, JPEG, PNG"

# Size validation  
"File size ({size}MB) exceeds {limit}MB limit for {format} files"

# Magic bytes validation
"File content does not match declared format. Expected {format} but detected {actual}"

# PDF page count validation
"PDF has {count} pages, exceeding the 100-page limit"

# Corrupted file
"Invalid or corrupted {format} file"
```

### Downstream API Errors

If Zai API returns a format error despite validation passing, the system logs the discrepancy:

```python
logger.error(
    "Zai API rejected file despite validation passing",
    extra={
        "file_type": file_type,
        "file_size": len(file_bytes),
        "zai_error": error_message,
        "file_hash": hashlib.sha256(file_bytes).hexdigest()
    }
)
```

## Testing Strategy

### Unit Tests

Unit tests will verify specific validation scenarios:

1. Valid files of each supported format pass validation
2. Files with unsupported extensions are rejected
3. Files with mismatched content/extension are rejected
4. Oversized files are rejected with correct limits
5. PDFs with too many pages are rejected
6. Corrupted PDFs are handled gracefully
7. Extension normalization (jpeg → jpg) works correctly
8. Error messages contain required information

### Property-Based Tests

Property-based tests will use the Hypothesis library to verify universal properties across many generated inputs. Each test will run a minimum of 100 iterations.

1. **Property 1 Test**: Generate random filenames with various extensions, verify unsupported ones are rejected
   - **Feature: file-upload-validation, Property 1**: Extension validation rejects unsupported formats

2. **Property 2 Test**: Generate files with mismatched magic bytes and extensions, verify all are rejected
   - **Feature: file-upload-validation, Property 2**: Content validation detects format mismatches

3. **Property 3 Test**: Generate files of various sizes, verify size limits are enforced per format
   - **Feature: file-upload-validation, Property 3**: Size validation enforces format-specific limits

4. **Property 4 Test**: Generate PDFs with various page counts, verify 100-page limit is enforced
   - **Feature: file-upload-validation, Property 4**: PDF page count validation enforces 100-page limit

5. **Property 5 Test**: Generate files with multiple issues, verify first issue is reported
   - **Feature: file-upload-validation, Property 5**: Validation fails fast in order

6. **Property 6 Test**: Generate various invalid files, verify error messages are descriptive
   - **Feature: file-upload-validation, Property 6**: Error responses are descriptive and consistent

7. **Property 7 Test**: Generate valid files, verify they pass through to processing
   - **Feature: file-upload-validation, Property 7**: Valid files pass through to processing

8. **Property 8 Test**: Trigger validation failures, verify log entries are created
   - **Feature: file-upload-validation, Property 8**: Validation failures are logged

### Integration Tests

Integration tests will verify the complete flow:

1. Upload valid files through the endpoint and verify successful processing
2. Upload invalid files and verify appropriate error responses
3. Verify logging integration works correctly
4. Test with actual Zai API to ensure validated files are accepted

## Implementation Notes

### Dependencies

The implementation requires:
- `PyPDF2` or `pypdf` for PDF page counting
- Standard library modules: `os`, `hashlib`, `logging`
- Existing FastAPI and HTTPException infrastructure

### Performance Considerations

1. Magic byte checking reads only the first 8 bytes of files
2. Size checking uses `len(file_bytes)` which is O(1) for bytes objects
3. PDF page counting only occurs for PDF files that pass earlier validations
4. Validation order ensures fast failure for common issues (extension, size)

### Backward Compatibility

This change is backward compatible:
- Existing valid file uploads continue to work
- New validation catches files that would have failed at the Zai API
- Error messages are more descriptive than before
- No changes to API contract or response format for successful uploads
