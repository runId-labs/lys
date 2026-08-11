"""
Document-to-text extraction: raw bytes -> text, OCR only when needed.

- PDF: text layer via ``pdftotext`` (poppler); falls back to OCR when the layer
  is too sparse (scanned PDF) or pdftotext is unavailable.
- image: OCR via the AI app (``ai_service.ocr_sync``).
- spreadsheet / other: UnsupportedDocumentError (not handled yet).

Plain functions, not a service: no app_manager state, no registry override use case
— ai_service/ocr_config are passed in by the caller instead of resolved here, so
this module stays usable without the ai app being loaded.

RUNTIME DEPENDENCY: the ``pdftotext`` binary (poppler-utils) must be installed in
any image that calls ``extract_text`` on PDFs. This is a Dockerfile line in the consuming
service, not a lys concern, same as the WeasyPrint native libraries required by
``lys.core.utils.pdf`` (see ``docs/FRS/_core/pdf.md``). Without it, every PDF
silently falls back to OCR (slower, costs money) — hence the WARNING logged below.

CALLER RESPONSIBILITIES: this module trusts its inputs. ``content`` is held fully
in memory and written to a temporary file, and ``mime_type`` is used as declared
(no magic-byte sniffing). Callers exposing user uploads must enforce a size limit
and verify the declared MIME type upstream, otherwise a mislabelled file routes
straight to the billed OCR endpoint.
"""
from __future__ import annotations

import logging
import subprocess
import tempfile
from typing import Any, Protocol

logger = logging.getLogger(__name__)

# Below this, a PDF "text layer" is treated as empty (scanned) -> OCR.
DEFAULT_MIN_TEXT_CHARS = 40

# Wall-clock bound for a single pdftotext run, in seconds.
DEFAULT_PDFTOTEXT_TIMEOUT = 120

PDF_MIME = "application/pdf"


class OcrService(Protocol):
    """Minimal contract required from the AI service (``lys.apps.ai`` satisfies it)."""

    def ocr_sync(self, content: bytes, mime_type: str, config: Any) -> str:
        """Extract text from a document via an OCR provider."""
        ...


class UnsupportedDocumentError(Exception):
    """Raised for document formats not handled here (e.g. spreadsheets)."""


def _pdftotext(content: bytes, timeout: int = DEFAULT_PDFTOTEXT_TIMEOUT) -> str:
    """Extract a PDF's text layer with pdftotext. Returns '' if it fails.

    Args:
        content: Raw PDF bytes.
        timeout: Wall-clock bound for the pdftotext run, in seconds.

    Output is decoded as UTF-8 explicitly (pdftotext's default output encoding)
    rather than through the process locale, which would raise on non-ASCII text
    when the container runs under the C locale.

    The failure modes are logged distinctly on purpose: a missing binary is an
    infra misconfiguration (every PDF pays for OCR until it's fixed — WARNING, so it
    doesn't hide in normal log volume), while a subprocess failure or a non-zero exit
    on one specific file is more localized but still means this file didn't get free
    extraction.
    """
    try:
        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp:
            tmp.write(content)
            tmp.flush()
            out = subprocess.run(
                ["pdftotext", "-layout", "-q", tmp.name, "-"],
                capture_output=True,
                encoding="utf-8",
                errors="replace",
                timeout=timeout,
            )
    except FileNotFoundError:
        logger.warning(
            "pdftotext binary not found (poppler-utils not installed in this image?) "
            "-> falling back to OCR for every PDF"
        )
        return ""
    except subprocess.SubprocessError as exc:
        logger.warning("pdftotext failed (%s) -> OCR fallback for this file", exc)
        return ""

    if out.returncode != 0:
        # Partial stdout on a failed run must not be trusted: it could pass the
        # text-layer threshold and skip an OCR pass the document actually needs.
        logger.warning(
            "pdftotext exited with code %d (%s) -> OCR fallback for this file",
            out.returncode,
            (out.stderr or "").strip() or "no stderr",
        )
        return ""

    return (out.stdout or "").strip()


def extract_text(
    content: bytes,
    mime_type: str,
    ai_service: OcrService,
    ocr_config: Any,
    min_text_chars: int = DEFAULT_MIN_TEXT_CHARS,
    pdftotext_timeout: int = DEFAULT_PDFTOTEXT_TIMEOUT,
) -> str:
    """Return the textual content of a document (bytes -> text).

    Args:
        content: Raw document bytes (e.g. from StoredFileService.download_sync).
        mime_type: MIME type of the document (e.g. from StoredFile.mime_type).
        ai_service: lys AI service (for ``ocr_sync``) — passed in, not resolved
            here, so this module has no hard dependency on the ai app.
        ocr_config: resolved endpoint config (``ai_service.get_endpoint("ocr")``).
        min_text_chars: PDF text layers shorter than this are treated as empty
            (scanned document) and sent to OCR.
        pdftotext_timeout: Wall-clock bound for the pdftotext run, in seconds.

    Raises:
        UnsupportedDocumentError: format not handled here (e.g. a spreadsheet).
    """
    mime = (mime_type or "").lower()

    if mime.startswith("image/"):
        return ai_service.ocr_sync(content, mime_type, ocr_config)

    if mime == PDF_MIME:
        text = _pdftotext(content, timeout=pdftotext_timeout)
        if len(text) < min_text_chars:
            logger.info("PDF text layer sparse (%d chars) -> OCR", len(text))
            return ai_service.ocr_sync(content, PDF_MIME, ocr_config)
        return text

    raise UnsupportedDocumentError(
        f"Unsupported document type (PDF/images only): {mime_type!r}"
    )
