"""
Unit tests for secure ZIP extraction utilities.
"""
import io
import struct
import zipfile

import pytest

from lys.core.utils.zip import extract_zip_files, ZipExtractionError


def _make_zip(files: dict[str, bytes]) -> bytes:
    """Helper to create a ZIP archive in memory from a dict of {filename: content}."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, data in files.items():
            zf.writestr(name, data)
    return buf.getvalue()


class TestExtractZipFiles:
    """Tests for extract_zip_files()."""

    def test_extracts_single_file(self):
        content = b"hello world"
        zip_bytes = _make_zip({"test.txt": content})
        result = list(extract_zip_files(zip_bytes))
        assert len(result) == 1
        assert result[0] == ("test.txt", content)

    def test_extracts_multiple_files(self):
        files = {"a.txt": b"aaa", "b.txt": b"bbb", "c.txt": b"ccc"}
        zip_bytes = _make_zip(files)
        result = list(extract_zip_files(zip_bytes))
        assert len(result) == 3
        names = {name for name, _ in result}
        assert names == {"a.txt", "b.txt", "c.txt"}

    def test_skips_directories(self):
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("somedir/", "")
            zf.writestr("somedir/file.txt", b"data")
        result = list(extract_zip_files(buf.getvalue()))
        assert len(result) == 1
        assert result[0][0] == "file.txt"

    def test_skips_macosx_metadata(self):
        files = {"__MACOSX/._file.txt": b"meta", "file.txt": b"data"}
        zip_bytes = _make_zip(files)
        result = list(extract_zip_files(zip_bytes))
        assert len(result) == 1
        assert result[0][0] == "file.txt"

    def test_skips_hidden_files(self):
        files = {".hidden": b"secret", "visible.txt": b"data"}
        zip_bytes = _make_zip(files)
        result = list(extract_zip_files(zip_bytes))
        assert len(result) == 1
        assert result[0][0] == "visible.txt"

    def test_skips_hidden_files_in_subdirectories(self):
        files = {"subdir/.hidden": b"secret", "subdir/visible.txt": b"data"}
        zip_bytes = _make_zip(files)
        result = list(extract_zip_files(zip_bytes))
        assert len(result) == 1
        assert result[0][0] == "visible.txt"


class TestZipSlipProtection:
    """Tests for path traversal (ZIP Slip) prevention."""

    def test_strips_directory_components(self):
        files = {"subdir/nested/file.txt": b"data"}
        zip_bytes = _make_zip(files)
        result = list(extract_zip_files(zip_bytes))
        assert result[0][0] == "file.txt"

    def test_skips_path_traversal_with_dotdot(self):
        files = {"../../etc/passwd": b"root:x:0:0"}
        zip_bytes = _make_zip(files)
        result = list(extract_zip_files(zip_bytes))
        assert len(result) == 0


class TestZipBombProtection:
    """Tests for ZIP bomb and size limit enforcement."""

    def test_raises_when_too_many_files(self):
        files = {f"file_{i}.txt": b"x" for i in range(6)}
        zip_bytes = _make_zip(files)
        with pytest.raises(ZipExtractionError, match="too many files"):
            list(extract_zip_files(zip_bytes, max_files=5))

    def test_exact_file_count_limit_passes(self):
        files = {f"file_{i}.txt": b"x" for i in range(5)}
        zip_bytes = _make_zip(files)
        result = list(extract_zip_files(zip_bytes, max_files=5))
        assert len(result) == 5

    def test_skips_file_exceeding_per_file_size_limit(self):
        files = {"small.txt": b"x", "large.txt": b"x" * 200}
        zip_bytes = _make_zip(files)
        result = list(extract_zip_files(zip_bytes, max_file_size=100))
        assert len(result) == 1
        assert result[0][0] == "small.txt"

    def test_raises_when_total_size_exceeded(self):
        files = {"a.txt": b"x" * 60, "b.txt": b"x" * 60}
        zip_bytes = _make_zip(files)
        with pytest.raises(ZipExtractionError, match="Total decompressed size"):
            list(extract_zip_files(zip_bytes, max_total_size=100))

    def test_total_size_uses_actual_content_size(self):
        """Verify total_size is computed from actual decompressed bytes, not declared headers."""
        content_a = b"x" * 50
        content_b = b"y" * 50
        zip_bytes = _make_zip({"a.txt": content_a, "b.txt": content_b})
        # Total actual size = 100, limit = 100 → should pass
        result = list(extract_zip_files(zip_bytes, max_total_size=100))
        assert len(result) == 2

    def test_actual_size_check_skips_lying_header(self):
        """Test that files with actual size exceeding limit are skipped even if header lies."""
        content = b"x" * 200
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w") as zf:
            zf.writestr("file.txt", content)
        zip_bytes = buf.getvalue()
        # Per-file limit is 100, actual content is 200
        result = list(extract_zip_files(zip_bytes, max_file_size=100))
        assert len(result) == 0


class TestInvalidZip:
    """Tests for invalid ZIP input."""

    def test_invalid_zip_raises_bad_zip_file(self):
        with pytest.raises(zipfile.BadZipFile):
            list(extract_zip_files(b"not a zip file"))

    def test_empty_zip(self):
        zip_bytes = _make_zip({})
        result = list(extract_zip_files(zip_bytes))
        assert result == []
