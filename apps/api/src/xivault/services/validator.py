"""File content and path validation services."""

import mimetypes
import os
import posixpath

from xivault.exceptions import FileTooLargeException, ValidationException

# Max file size: exactly 1 MiB (1,048,576 bytes)
MAX_FILE_BYTES = 1048576

# Max full-text index size: 256 KiB (262,144 bytes)
MAX_INDEX_BYTES = 262144

# Extension to language map
EXTENSION_TO_LANGUAGE: dict[str, tuple[str, str]] = {
    ".py": ("python", "text/x-python"),
    ".ts": ("typescript", "text/x-typescript"),
    ".tsx": ("typescriptreact", "text/x-typescript"),
    ".js": ("javascript", "text/javascript"),
    ".jsx": ("javascriptreact", "text/javascript"),
    ".json": ("json", "application/json"),
    ".md": ("markdown", "text/markdown"),
    ".sql": ("sql", "text/x-sql"),
    ".html": ("html", "text/html"),
    ".css": ("css", "text/css"),
    ".rs": ("rust", "text/x-rust"),
    ".go": ("go", "text/x-go"),
    ".java": ("java", "text/x-java"),
    ".c": ("c", "text/x-c"),
    ".cpp": ("cpp", "text/x-c++"),
    ".h": ("c", "text/x-c"),
    ".hpp": ("cpp", "text/x-c++"),
    ".sh": ("shellscript", "text/x-shellscript"),
    ".yaml": ("yaml", "text/yaml"),
    ".yml": ("yaml", "text/yaml"),
    ".toml": ("toml", "text/x-toml"),
    ".xml": ("xml", "text/xml"),
    ".txt": ("plaintext", "text/plain"),
}


def validate_display_path(raw_path: str) -> str:
    """Normalize and validate workspace-relative display path."""
    if not raw_path or not raw_path.strip():
        raise ValidationException(code="invalid_path", message="File path cannot be empty.")

    clean_path = raw_path.replace("\\", "/").strip()

    # Reject null characters and control characters
    if any(ord(c) < 32 for c in clean_path):
        raise ValidationException(code="invalid_path", message="File path contains invalid characters.")

    # Reject absolute paths (POSIX / or Windows drive C:)
    if clean_path.startswith("/") or (len(clean_path) > 1 and clean_path[1] == ":"):
        raise ValidationException(code="invalid_path", message="Absolute paths are not permitted.")

    # Reject directory traversal
    parts = clean_path.split("/")
    if ".." in parts or "." in parts:
        raise ValidationException(code="invalid_path", message="Path traversal (..) is not permitted.")

    normalized = posixpath.normpath(clean_path)
    if normalized.startswith("../") or normalized == "..":
        raise ValidationException(code="invalid_path", message="Path traversal is not permitted.")

    return normalized


def validate_source_content(display_path: str, data: bytes) -> tuple[str, str, str | None]:
    """Validate file bytes for size, UTF-8 validity, language, and index eligibility."""
    size = len(data)
    if size == 0:
        raise ValidationException(code="invalid_path", message="Uploaded file cannot be empty.")

    if size > MAX_FILE_BYTES:
        raise FileTooLargeException("File size exceeds maximum allowed 1 MiB limit.")

    # Reject binary content (NUL bytes)
    if b"\x00" in data:
        raise ValidationException(
            code="invalid_text_encoding",
            message="Binary files and control characters are strictly rejected.",
        )

    # Validate UTF-8 decoding
    try:
        text_content = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ValidationException(
            code="invalid_text_encoding",
            message="Uploaded file is not valid UTF-8 text.",
        ) from None

    # Validate file extension and determine language / content-type
    _, ext = os.path.splitext(display_path.lower())
    if ext not in EXTENSION_TO_LANGUAGE:
        guess_type, _ = mimetypes.guess_type(display_path)
        if not guess_type or not guess_type.startswith("text/"):
            raise ValidationException(
                code="unsupported_file_type",
                message=f"File extension '{ext}' is not supported.",
            )
        language = "plaintext"
        content_type = guess_type
    else:
        language, content_type = EXTENSION_TO_LANGUAGE[ext]

    # Index limit: max 256 KiB
    indexed_content: str | None = text_content if size <= MAX_INDEX_BYTES else None

    return language, content_type, indexed_content
