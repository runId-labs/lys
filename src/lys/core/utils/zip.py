"""
Secure ZIP extraction utilities.

Provides safe ZIP file extraction with protection against:
- ZIP Slip (path traversal via crafted filenames)
- ZIP bombs (decompression bombs that exhaust memory)
- Hidden/metadata files (__MACOSX, dot-prefixed)
"""
import io
import logging
import os
import zipfile
from typing import Generator

logger = logging.getLogger(__name__)

# Default limits
DEFAULT_MAX_FILES = 100
DEFAULT_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB per file
DEFAULT_MAX_TOTAL_SIZE = 500 * 1024 * 1024  # 500 MB total


class ZipExtractionError(Exception):
    """Raised when ZIP extraction fails due to security or size constraints."""
    pass


def extract_zip_files(
    zip_content: bytes,
    max_files: int = DEFAULT_MAX_FILES,
    max_file_size: int = DEFAULT_MAX_FILE_SIZE,
    max_total_size: int = DEFAULT_MAX_TOTAL_SIZE,
) -> Generator[tuple[str, bytes], None, None]:
    """
    Safely extract files from a ZIP archive.

    Yields (filename, content) tuples for each valid file in the archive.
    Skips directories, hidden files, macOS metadata, and files with
    suspicious paths. Enforces size limits to prevent ZIP bombs.

    Args:
        zip_content: Raw bytes of the ZIP file.
        max_files: Maximum number of files to extract.
        max_file_size: Maximum decompressed size per file in bytes.
        max_total_size: Maximum total decompressed size in bytes.

    Yields:
        Tuple of (sanitized_filename, file_content_bytes).

    Raises:
        ZipExtractionError: If the archive exceeds file count or total size limits.
        zipfile.BadZipFile: If the content is not a valid ZIP file.
    """
    with zipfile.ZipFile(io.BytesIO(zip_content), "r") as zf:
        file_count = 0
        total_size = 0

        for file_info in zf.infolist():
            if file_info.is_dir():
                continue

            raw_filename = file_info.filename

            # Skip hidden files and macOS metadata
            if raw_filename.startswith("__MACOSX") or os.path.basename(raw_filename).startswith("."):
                continue

            # Sanitize filename to prevent path traversal (ZIP Slip)
            filename = os.path.basename(raw_filename)
            if not filename:
                continue

            if ".." in raw_filename:
                logger.warning(f"Skipping file with path traversal attempt: {raw_filename}")
                continue

            # Enforce file count limit
            file_count += 1
            if file_count > max_files:
                raise ZipExtractionError(
                    f"ZIP contains too many files (>{max_files})"
                )

            # Enforce per-file size limit (check declared size before reading)
            if file_info.file_size > max_file_size:
                logger.warning(
                    f"Skipping file {filename}: declared size {file_info.file_size} "
                    f"exceeds limit {max_file_size}"
                )
                continue

            # Read file content
            content = zf.read(file_info.filename)

            # Verify actual size (defense against lying headers)
            if len(content) > max_file_size:
                logger.warning(
                    f"Skipping file {filename}: actual size {len(content)} "
                    f"exceeds limit {max_file_size}"
                )
                continue

            # Enforce total size limit using actual decompressed size
            total_size += len(content)
            if total_size > max_total_size:
                raise ZipExtractionError(
                    f"Total decompressed size exceeds limit ({max_total_size} bytes)"
                )

            yield filename, content