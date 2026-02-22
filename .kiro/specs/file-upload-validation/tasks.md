# Implementation Plan: File Upload Validation

## Overview

This plan implements comprehensive file upload validation to prevent Zai API errors. The implementation adds a dedicated FileValidator class that checks file format, size, and PDF page count before files reach the API. Tasks are ordered to build incrementally with early validation through tests.

## Tasks

- [-] 1. Create FileValidator utility class with core validation methods
  - Create `app/utils/file_validator.py` module
  - Implement `FileValidator` class with constants (MAX_IMAGE_SIZE_MB, MAX_PDF_SIZE_MB, MAX_PDF_PAGES, SUPPORTED_FORMATS)
  - Implement `validate_file()` method that orchestrates all validations
  - Implement `_validate_extension()` method for extension checking and normalization
  - Implement `_validate_size()` method for format-specific size limits
  - Implement `_validate_magic_bytes()` method for content verification
  - Implement `_validate_pdf_pages()` method for PDF page counting
  - Add magic bytes constants for JPG, PNG, and PDF formats
  - _Requirements: 1.1, 1.2, 1.5, 2.1, 2.2, 3.1, 5.1_

- [ ] 1.1 Write property test for extension validation
  - **Property 1: Extension validation rejects unsupported formats**
  - **Validates: Requirements 1.1, 1.3**

- [ ] 1.2 Write property test for magic bytes validation
  - **Property 2: Content validation detects format mismatches**
  - **Validates: Requirements 1.2, 1.4**

- [ ] 1.3 Write property test for size validation
  - **Property 3: Size validation enforces format-specific limits**
  - **Validates: Requirements 2.1, 2.2, 2.3**

- [ ] 1.4 Write property test for PDF page count validation
  - **Property 4: PDF page count validation enforces 100-page limit**
  - **Validates: Requirements 3.1, 3.2**

- [ ] 1.5 Write property test for fail-fast validation ordering
  - **Property 5: Validation fails fast in order**
  - **Validates: Requirements 5.1, 5.2**

- [ ] 1.6 Write unit tests for FileValidator edge cases
  - Test JPEG to JPG normalization
  - Test corrupted PDF handling
  - Test files with no extension
  - Test empty files
  - _Requirements: 1.5, 3.3_

- [ ] 2. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 3. Integrate FileValidator into chat_router.py
  - Import FileValidator in `app/routers/chat_router.py`
  - Update `chat_file()` endpoint to call `FileValidator.validate_file()`
  - Replace existing extension validation with FileValidator call
  - Handle validation errors by raising HTTPException with error message
  - Pass normalized file_type to downstream components
  - _Requirements: 1.3, 1.4, 2.3, 3.2, 4.4, 6.1, 6.2_

- [ ] 3.1 Write property test for error response format
  - **Property 6: Error responses are descriptive and consistent**
  - **Validates: Requirements 4.1, 4.2, 4.3, 4.4**

- [ ] 3.2 Write property test for valid file pass-through
  - **Property 7: Valid files pass through to processing**
  - **Validates: Requirements 6.1, 6.2**

- [ ] 3.3 Write integration tests for chat_file endpoint
  - Test uploading valid files of each format
  - Test uploading invalid files and verify error responses
  - Test that validated files reach file_analysis_strategy
  - _Requirements: 6.2_

- [ ] 4. Add logging for validation failures
  - Add logger import to `app/routers/chat_router.py`
  - Log validation failures with file metadata (type, size, hash)
  - Log Zai API format errors that occur despite validation passing
  - Include structured logging fields for monitoring
  - _Requirements: 6.3, 6.4_

- [ ] 4.1 Write property test for validation logging
  - **Property 8: Validation failures are logged**
  - **Validates: Requirements 6.3, 6.4**

- [ ] 4.2 Write unit tests for logging behavior
  - Test that validation failures produce log entries
  - Test that log entries contain required metadata
  - Test that Zai API errors are logged with discrepancy information
  - _Requirements: 6.3, 6.4_

- [ ] 5. Update error messages for clarity
  - Review all error messages in FileValidator
  - Ensure error messages include supported formats and limits
  - Ensure error messages are user-friendly and actionable
  - Add examples to error messages where helpful
  - _Requirements: 4.1, 4.2_

- [ ] 5.1 Write unit tests for error message content
  - Test that error messages contain format information
  - Test that error messages contain size limits
  - Test that error messages are descriptive
  - _Requirements: 4.1, 4.2_

- [ ] 6. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Each task references specific requirements for traceability
- Checkpoints ensure incremental validation
- Property tests validate universal correctness properties using Hypothesis library
- Unit tests validate specific examples and edge cases
- The FileValidator is designed to be reusable for other file upload endpoints
- PDF page counting requires PyPDF2 or pypdf library (add to requirements.txt if not present)
