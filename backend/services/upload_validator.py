"""
RecruitIQ - Upload Validation & Security Module
Validates file sizes, allowed extensions, and magic-byte signatures
to prevent denial-of-service, buffer overruns, and malicious file uploads.
"""

from fastapi import HTTPException, UploadFile

MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024  # 10 MB
MIN_FILE_SIZE_BYTES = 20                 # Empty or corrupt file detection
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc"}

# Magic byte signatures for authorized file types
MAGIC_SIGNATURES = {
    "pdf": b"%PDF",
    "docx": b"PK\x03\x04",
    "doc": b"\xd0\xcf\x11\xe0",
}


def validate_uploaded_file(
    file: UploadFile,
    file_bytes: bytes,
    max_bytes: int = MAX_FILE_SIZE_BYTES,
    entity_name: str = "Document",
) -> None:
    """
    Validate uploaded file size, extension, and content magic bytes.
    Raises HTTPException(400) or HTTPException(413) if invalid.
    """
    if not file_bytes or len(file_bytes) < MIN_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=400,
            detail=f"{entity_name} file is empty or corrupted (size < {MIN_FILE_SIZE_BYTES} bytes)."
        )

    if len(file_bytes) > max_bytes:
        max_mb = max_bytes / (1024 * 1024)
        actual_mb = len(file_bytes) / (1024 * 1024)
        raise HTTPException(
            status_code=413,
            detail=f"{entity_name} exceeds maximum allowed size of {max_mb:.1f} MB (uploaded: {actual_mb:.1f} MB)."
        )

    filename = file.filename or ""
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(sorted(ALLOWED_EXTENSIONS))}."
        )

    # Magic byte verification
    header = file_bytes[:8]
    is_valid_magic = False

    if ext == ".pdf" and header.startswith(MAGIC_SIGNATURES["pdf"]):
        is_valid_magic = True
    elif ext == ".docx" and header.startswith(MAGIC_SIGNATURES["docx"]):
        is_valid_magic = True
    elif ext == ".doc" and (header.startswith(MAGIC_SIGNATURES["doc"]) or header.startswith(MAGIC_SIGNATURES["docx"])):
        is_valid_magic = True

    if not is_valid_magic:
        raise HTTPException(
            status_code=400,
            detail=f"{entity_name} file content does not match its '{ext}' extension signature."
        )
