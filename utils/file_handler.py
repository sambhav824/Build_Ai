"""
file_handler.py — File Upload Validation Utilities for BuildSmartAI
====================================================================
Validates uploaded files (type, size, name sanitisation) before they are
processed by the Site Monitoring Agent or any other component.

All checks are defensive and advisory — they do NOT replace virus scanning
or server-level file-type enforcement.
"""

import os
import re
import hashlib
from pathlib import Path
from typing import Tuple, Optional


# ---------------------------------------------------------------------------
# Allowed upload profiles
# ---------------------------------------------------------------------------

ALLOWED_IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp"}
ALLOWED_BLUEPRINT_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
ALLOWED_DOCUMENT_EXTENSIONS = {".pdf", ".xlsx", ".xls", ".csv", ".docx"}

# Magic-byte signatures for common image formats (first N bytes)
_IMAGE_MAGIC: dict = {
    b"\xff\xd8\xff": "JPEG",
    b"\x89PNG\r\n\x1a\n": "PNG",
    b"BM": "BMP",
    b"II*\x00": "TIFF-LE",
    b"MM\x00*": "TIFF-BE",
    b"RIFF": "WEBP",  # partial — full check: bytes[8:12] == b'WEBP'
    b"%PDF": "PDF",
}

# Max file sizes
MAX_IMAGE_SIZE_MB = 20
MAX_DOCUMENT_SIZE_MB = 50


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_site_image(file_path: str) -> Tuple[bool, str]:
    """
    Validate a site photograph for use by the Site Monitoring Agent.

    Parameters
    ----------
    file_path : str
        Absolute or relative path to the uploaded file.

    Returns
    -------
    (is_valid, message) : (bool, str)
    """
    path = Path(file_path)

    if not path.exists():
        return False, f"File not found: {file_path}"

    # Extension check
    ext = path.suffix.lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        return False, (
            f"Unsupported image type '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_IMAGE_EXTENSIONS))}"
        )

    # Size check
    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        return False, f"Image too large ({size_mb:.1f} MB). Maximum: {MAX_IMAGE_SIZE_MB} MB."

    # Magic-byte check
    detected = _detect_magic(path)
    if detected is None:
        return False, "File header does not match any known image format."

    return True, f"Valid site image ({detected}, {size_mb:.2f} MB)."


def validate_blueprint_upload(file_path: str) -> Tuple[bool, str]:
    """
    Validate a blueprint / floor-plan upload for the Design Agent (Mode B).

    Returns
    -------
    (is_valid, message) : (bool, str)
    """
    path = Path(file_path)

    if not path.exists():
        return False, f"File not found: {file_path}"

    ext = path.suffix.lower()
    if ext not in ALLOWED_BLUEPRINT_EXTENSIONS:
        return False, (
            f"Unsupported blueprint type '{ext}'. "
            f"Allowed: {', '.join(sorted(ALLOWED_BLUEPRINT_EXTENSIONS))}"
        )

    size_mb = path.stat().st_size / (1024 * 1024)
    if size_mb > MAX_IMAGE_SIZE_MB:
        return False, f"Blueprint too large ({size_mb:.1f} MB). Maximum: {MAX_IMAGE_SIZE_MB} MB."

    return True, f"Valid blueprint upload ({ext.lstrip('.')}, {size_mb:.2f} MB)."


def sanitize_filename(filename: str) -> str:
    """
    Return a filesystem-safe version of *filename*.

    Strips path traversal sequences, control characters and reserved names.
    Replaces spaces and special characters with underscores.
    Preserves the file extension.
    """
    # Remove path components
    name = Path(filename).name

    # Strip null bytes and control chars
    name = re.sub(r"[\x00-\x1f\x7f]", "", name)

    # Reject path traversal
    if ".." in name or name.startswith("/") or name.startswith("\\"):
        name = "upload"

    # Replace problematic chars
    stem, *ext_parts = name.rsplit(".", 1)
    stem = re.sub(r"[^\w\-]", "_", stem)
    stem = stem[:100]  # max 100-char stem

    ext = f".{ext_parts[0].lower()}" if ext_parts else ""
    safe = f"{stem}{ext}" if stem else f"upload{ext}"
    return safe


def compute_file_hash(file_path: str, algorithm: str = "sha256") -> Optional[str]:
    """
    Return the hex digest of *file_path* using *algorithm* (default sha256).
    Returns ``None`` if the file cannot be read.
    """
    try:
        h = hashlib.new(algorithm)
        with open(file_path, "rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
        return h.hexdigest()
    except (OSError, IOError):
        return None


def save_upload(
    content: bytes,
    original_filename: str,
    dest_dir: str = "uploads"
) -> Tuple[str, str]:
    """
    Write *content* to *dest_dir* using a sanitized filename.

    Returns
    -------
    (absolute_path, sanitized_filename) : (str, str)
    """
    os.makedirs(dest_dir, exist_ok=True)
    safe_name = sanitize_filename(original_filename)
    dest_path = os.path.join(dest_dir, safe_name)

    # Avoid overwriting existing files by appending a counter
    base, ext = os.path.splitext(dest_path)
    counter = 1
    while os.path.exists(dest_path):
        dest_path = f"{base}_{counter}{ext}"
        counter += 1

    with open(dest_path, "wb") as fh:
        fh.write(content)

    return os.path.abspath(dest_path), safe_name


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _detect_magic(path: Path) -> Optional[str]:
    """Read up to 12 bytes and match known magic signatures."""
    try:
        header = path.read_bytes()[:12]
        for magic, name in _IMAGE_MAGIC.items():
            if header.startswith(magic):
                # Extra WEBP check
                if name == "WEBP" and header[8:12] != b"WEBP":
                    continue
                return name
    except OSError:
        pass
    return None
