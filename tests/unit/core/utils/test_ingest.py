"""
Unit tests for lys.core.utils.ingest — pure logic, ai_service/subprocess mocked.
"""
import subprocess
from unittest.mock import MagicMock, patch

import pytest

from lys.core.utils.ingest import (
    DEFAULT_PDFTOTEXT_TIMEOUT,
    UnsupportedDocumentError,
    _has_font_layer,
    _pdftotext,
    extract_text,
)


def _ai_service(ocr_text: str = "ocr text") -> MagicMock:
    mock = MagicMock()
    mock.ocr_sync.return_value = ocr_text
    return mock


def _completed(stdout: str = "", returncode: int = 0, stderr: str = "") -> MagicMock:
    return MagicMock(stdout=stdout, returncode=returncode, stderr=stderr)


class TestIngestImages:
    def test_image_mime_goes_straight_to_ocr(self):
        ai_service = _ai_service("scanned photo text")
        result = extract_text(b"bytes", "image/png", ai_service, "ocr-config")
        assert result == "scanned photo text"
        ai_service.ocr_sync.assert_called_once_with(b"bytes", "image/png", "ocr-config")

    def test_image_mime_case_insensitive(self):
        ai_service = _ai_service()
        extract_text(b"bytes", "IMAGE/JPEG", ai_service, "ocr-config")
        ai_service.ocr_sync.assert_called_once()


class TestIngestPdf:
    @patch("lys.core.utils.ingest._has_font_layer")
    @patch("lys.core.utils.ingest._pdftotext")
    def test_pdf_with_good_text_layer_skips_ocr(self, mock_pdftotext, mock_has_fonts):
        mock_pdftotext.return_value = "a" * 100
        mock_has_fonts.return_value = True
        ai_service = _ai_service()
        result = extract_text(b"bytes", "application/pdf", ai_service, "ocr-config")
        assert result == "a" * 100
        ai_service.ocr_sync.assert_not_called()

    @patch("lys.core.utils.ingest._has_font_layer")
    @patch("lys.core.utils.ingest._pdftotext")
    def test_pdf_with_sparse_text_layer_falls_back_to_ocr(self, mock_pdftotext, mock_has_fonts):
        mock_pdftotext.return_value = "short"
        mock_has_fonts.return_value = True
        ai_service = _ai_service("ocr result")
        result = extract_text(b"bytes", "application/pdf", ai_service, "ocr-config")
        assert result == "ocr result"
        ai_service.ocr_sync.assert_called_once_with(b"bytes", "application/pdf", "ocr-config")

    @patch("lys.core.utils.ingest._has_font_layer")
    @patch("lys.core.utils.ingest._pdftotext")
    def test_pdf_with_empty_text_layer_falls_back_to_ocr(self, mock_pdftotext, mock_has_fonts):
        mock_pdftotext.return_value = ""
        mock_has_fonts.return_value = True
        ai_service = _ai_service("ocr result")
        result = extract_text(b"bytes", "application/pdf", ai_service, "ocr-config")
        assert result == "ocr result"

    @patch("lys.core.utils.ingest._has_font_layer")
    @patch("lys.core.utils.ingest._pdftotext")
    def test_min_text_chars_override_keeps_short_text_layer(self, mock_pdftotext, mock_has_fonts):
        mock_pdftotext.return_value = "short"
        mock_has_fonts.return_value = True
        ai_service = _ai_service()
        result = extract_text(b"bytes", "application/pdf", ai_service, "ocr-config", min_text_chars=3)
        assert result == "short"
        ai_service.ocr_sync.assert_not_called()

    @patch("lys.core.utils.ingest._has_font_layer")
    @patch("lys.core.utils.ingest._pdftotext")
    def test_pdftotext_timeout_is_forwarded(self, mock_pdftotext, mock_has_fonts):
        mock_pdftotext.return_value = "a" * 100
        mock_has_fonts.return_value = True
        extract_text(b"bytes", "application/pdf", _ai_service(), "ocr-config", pdftotext_timeout=5)
        assert mock_pdftotext.call_args.kwargs["timeout"] == 5

    @patch("lys.core.utils.ingest._has_font_layer")
    @patch("lys.core.utils.ingest._pdftotext")
    def test_no_font_layer_falls_back_to_ocr_even_with_enough_chars(self, mock_pdftotext, mock_has_fonts):
        """A many-page scan can accumulate enough page-break artifacts to clear
        min_text_chars while carrying zero real text — pdffonts catches this
        independently of the character count."""
        mock_pdftotext.return_value = "a" * 100
        mock_has_fonts.return_value = False
        ai_service = _ai_service("ocr result")
        result = extract_text(b"bytes", "application/pdf", ai_service, "ocr-config")
        assert result == "ocr result"
        ai_service.ocr_sync.assert_called_once_with(b"bytes", "application/pdf", "ocr-config")

    @patch("lys.core.utils.ingest._has_font_layer")
    @patch("lys.core.utils.ingest._pdftotext")
    def test_has_font_layer_timeout_is_forwarded(self, mock_pdftotext, mock_has_fonts):
        mock_pdftotext.return_value = "a" * 100
        mock_has_fonts.return_value = True
        extract_text(b"bytes", "application/pdf", _ai_service(), "ocr-config", pdftotext_timeout=5)
        assert mock_has_fonts.call_args.kwargs["timeout"] == 5


class TestIngestUnsupported:
    def test_unsupported_mime_raises(self):
        ai_service = _ai_service()
        with pytest.raises(UnsupportedDocumentError):
            extract_text(b"bytes", "application/vnd.ms-excel", ai_service, "ocr-config")
        ai_service.ocr_sync.assert_not_called()

    def test_empty_mime_raises(self):
        ai_service = _ai_service()
        with pytest.raises(UnsupportedDocumentError):
            extract_text(b"bytes", "", ai_service, "ocr-config")


class TestPdftotext:
    @patch("lys.core.utils.ingest.subprocess.run")
    def test_returns_stripped_stdout(self, mock_run):
        mock_run.return_value = _completed(stdout="  extracted text  \n")
        assert _pdftotext(b"pdf bytes") == "extracted text"

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_decodes_as_utf8_not_process_locale(self, mock_run):
        """Explicit UTF-8: the process locale would raise on accented text under C locale."""
        mock_run.return_value = _completed(stdout="café résumé")
        assert _pdftotext(b"pdf bytes") == "café résumé"
        args, kwargs = mock_run.call_args
        assert args[0][:3] == ["pdftotext", "-layout", "-q"]
        assert args[0][-1] == "-"
        assert kwargs["encoding"] == "utf-8"
        assert kwargs["errors"] == "replace"
        assert kwargs["timeout"] == DEFAULT_PDFTOTEXT_TIMEOUT

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_custom_timeout_is_passed_to_subprocess(self, mock_run):
        mock_run.return_value = _completed(stdout="text")
        _pdftotext(b"pdf bytes", timeout=7)
        assert mock_run.call_args.kwargs["timeout"] == 7

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_non_zero_exit_discards_partial_output(self, mock_run):
        """Partial stdout must not pass the text-layer threshold and skip a needed OCR pass."""
        mock_run.return_value = _completed(stdout="partial output", returncode=1, stderr="broken xref")
        assert _pdftotext(b"pdf bytes") == ""

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_non_zero_exit_logs_a_warning(self, mock_run, caplog):
        mock_run.return_value = _completed(stdout="partial", returncode=1, stderr="broken xref")
        with caplog.at_level("WARNING", logger="lys.core.utils.ingest"):
            _pdftotext(b"pdf bytes")
        assert any(r.levelname == "WARNING" and "broken xref" in r.message for r in caplog.records)

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_missing_poppler_returns_empty_string(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert _pdftotext(b"pdf bytes") == ""

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_missing_poppler_logs_a_warning_not_just_info(self, mock_run, caplog):
        """A missing binary is an infra misconfig affecting every PDF — must not hide at INFO."""
        mock_run.side_effect = FileNotFoundError()
        with caplog.at_level("WARNING", logger="lys.core.utils.ingest"):
            _pdftotext(b"pdf bytes")
        assert any(r.levelname == "WARNING" and "poppler-utils" in r.message for r in caplog.records)

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_subprocess_error_returns_empty_string(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pdftotext", timeout=120)
        assert _pdftotext(b"pdf bytes") == ""

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_subprocess_error_logs_a_warning(self, mock_run, caplog):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pdftotext", timeout=120)
        with caplog.at_level("WARNING", logger="lys.core.utils.ingest"):
            _pdftotext(b"pdf bytes")
        assert any(r.levelname == "WARNING" for r in caplog.records)


class TestHasFontLayer:
    # pdffonts always prints a 2-line header (column names + a "---" separator),
    # even for a PDF with zero embedded fonts.
    _HEADER_ONLY = "name  type  encoding  emb  sub  uni  object ID\n------  ----  --------  ---  ---  ---  ---------\n"

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_empty_font_table_means_no_text_layer(self, mock_run):
        mock_run.return_value = _completed(stdout=self._HEADER_ONLY)
        assert _has_font_layer(b"pdf bytes") is False

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_at_least_one_font_means_text_layer_present(self, mock_run):
        mock_run.return_value = _completed(
            stdout=self._HEADER_ONLY + "Helvetica  Type1  Custom  yes  no  no  5\n"
        )
        assert _has_font_layer(b"pdf bytes") is True

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_non_zero_exit_fails_open(self, mock_run):
        mock_run.return_value = _completed(stdout="", returncode=1, stderr="broken xref")
        assert _has_font_layer(b"pdf bytes") is True

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_custom_timeout_is_passed_to_subprocess(self, mock_run):
        mock_run.return_value = _completed(stdout=self._HEADER_ONLY)
        _has_font_layer(b"pdf bytes", timeout=7)
        assert mock_run.call_args.kwargs["timeout"] == 7

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_missing_poppler_fails_open(self, mock_run):
        mock_run.side_effect = FileNotFoundError()
        assert _has_font_layer(b"pdf bytes") is True

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_missing_poppler_logs_a_warning(self, mock_run, caplog):
        mock_run.side_effect = FileNotFoundError()
        with caplog.at_level("WARNING", logger="lys.core.utils.ingest"):
            _has_font_layer(b"pdf bytes")
        assert any(r.levelname == "WARNING" and "pdffonts" in r.message for r in caplog.records)

    @patch("lys.core.utils.ingest.subprocess.run")
    def test_subprocess_error_fails_open(self, mock_run):
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="pdffonts", timeout=120)
        assert _has_font_layer(b"pdf bytes") is True
