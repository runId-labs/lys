# Document Text Extraction

Stateless utility that turns a document's raw bytes into text, using OCR only when a
free extraction path is unavailable. It is a cross-cutting capability — any app that
processes uploaded documents needs it — so it lives in `lys.core`, not in any single app.

## Table of Contents

1. [Overview](#overview)
2. [Scope](#scope)
3. [Placement](#placement)
4. [Dependencies](#dependencies)
5. [Extraction pipeline](#extraction-pipeline)
6. [API contract](#api-contract)
7. [Configuration](#configuration)
8. [Errors and failure modes](#errors-and-failure-modes)
9. [Caller responsibilities](#caller-responsibilities)
10. [Consumers](#consumers)
11. [Deployment note](#deployment-note)

## Overview

`extract_text` takes `bytes` plus a declared MIME type and returns a `str`. Its single
design decision is **cost avoidance**: OCR is a billed, slow, remote call, so it is used
only when the document carries no usable text layer.

- A digital PDF (exported from a word processor, an invoicing tool, a browser) already
  embeds its text. `pdftotext` extracts it locally, for free, in milliseconds.
- A scanned PDF is a bitmap wrapped in a PDF container. It has no text layer, so OCR is
  the only option.
- An image is always OCR.

The module is **pure and stateless**: it persists nothing, owns no entities, and is not a
service. The AI service and its resolved OCR endpoint configuration are **passed in by the
caller** rather than resolved through `app_manager`, so the module stays importable and
usable in a deployment where the `ai` app is not loaded.

## Scope

**In scope**
- PDF → text via the embedded text layer (`pdftotext`), with automatic OCR fallback.
- Image → text via OCR.
- The heuristic deciding whether a PDF text layer is usable.

**Out of scope** (belongs to consumers)
- Downloading the bytes (see `file_management` / `StoredFileService.download_sync`).
- Enforcing an upload size limit and verifying the declared MIME type.
- Parsing, structuring, or interpreting the extracted text (LLM extraction, field mapping).
- Spreadsheets and office formats — currently rejected, see
  [Errors](#errors-and-failure-modes).

## Placement

`lys/core/utils/ingest.py` — a stateless helper module alongside `pdf.py`, `zip.py`,
`storage.py`. It is **not** an app (no entities, no registration) and **not** placed inside
a consumer app, so any app can use it without inverted dependencies.

## Dependencies

- **`pdftotext`** (poppler-utils) — an **external binary**, not a Python package, so it
  cannot be declared as an extra in `pyproject.toml`. See
  [Deployment note](#deployment-note). Its absence is non-fatal: extraction degrades to
  OCR.
- **An OCR-capable AI service** — injected, not imported. The module declares the minimal
  structural contract it needs:

  ```python
  class OcrService(Protocol):
      def ocr_sync(self, content: bytes, mime_type: str, config: Any) -> str: ...
  ```

  `lys.apps.ai`'s `AIService` satisfies it (Mistral `/ocr` provider, with the provider
  fallback chain). Any object exposing `ocr_sync` works, which keeps tests mock-friendly
  and leaves consumers free to plug another OCR backend.

## Extraction pipeline

```
bytes + mime_type
   │
   ├── image/*  ──────────────────────────────────► ai_service.ocr_sync()  ──► text
   │
   ├── application/pdf
   │      │  _pdftotext()                    # poppler, local, free, ~ms
   │      ▼
   │   text layer
   │      │
   │      ├── len >= min_text_chars ─────────────────────────────────────► text
   │      │
   │      └── len < min_text_chars ──────────► ai_service.ocr_sync()  ──► text
   │             (scanned doc, empty layer, missing binary, or failed run)
   │
   └── anything else ──────────────────────► UnsupportedDocumentError
```

The threshold is measured on the **whole document**, not per page: a long PDF whose first
page is scanned but whose remainder is digital will pass and skip OCR. This is a deliberate
simplification — per-page detection would mean parsing the PDF structure, which this module
does not do.

## API contract

Module-level functions in `lys/core/utils/ingest.py`. Both are **synchronous**.

```python
def extract_text(
    content: bytes,
    mime_type: str,
    ai_service: OcrService,
    ocr_config: Any,
    min_text_chars: int = DEFAULT_MIN_TEXT_CHARS,
    pdftotext_timeout: int = DEFAULT_PDFTOTEXT_TIMEOUT,
) -> str:
    """Return the textual content of a document. Raises UnsupportedDocumentError for
    formats other than PDF and images."""

def _pdftotext(content: bytes, timeout: int = DEFAULT_PDFTOTEXT_TIMEOUT) -> str:
    """Private. Extract a PDF's text layer with pdftotext; returns '' on any failure."""
```

Typical call site:

```python
ai_service = app_manager.get_service("ai")
text = extract_text(
    content=stored_file_service.download_sync(stored_file),
    mime_type=stored_file.mime_type,
    ai_service=ai_service,
    ocr_config=ai_service.get_endpoint("ocr"),
)
```

### Sync / async

`pdftotext` is a blocking subprocess and `ocr_sync` is a blocking HTTP call, so
`extract_text` is a plain `def`.

- **Sync callers** (Celery tasks — the expected case for document processing) call directly.
- **Async callers** (GraphQL webservices) MUST offload:
  `await asyncio.to_thread(extract_text, content, mime_type, ai_service, ocr_config)`.

## Configuration

No `AppSettings` namespace: the two tunables are per-call arguments, since they depend on
the document being processed rather than on the environment.

| Argument | Default | Meaning |
|---|---|---|
| `min_text_chars` | `DEFAULT_MIN_TEXT_CHARS` = 40 | Below this many characters, a PDF text layer counts as empty and OCR takes over. Raise it for document types that always carry substantial text; lower it for short forms where a handful of extracted characters is legitimate. |
| `pdftotext_timeout` | `DEFAULT_PDFTOTEXT_TIMEOUT` = 120 | Wall-clock bound on the `pdftotext` run, in seconds. Exceeding it is treated as a failure and falls back to OCR. |

Consumers needing environment-driven values wire their own setting into these arguments.

## Errors and failure modes

`UnsupportedDocumentError(Exception)` — raised for any MIME type that is neither
`application/pdf` nor `image/*`. A plain `Exception` subclass, matching the convention of
the other core utils (`PdfRenderError`, `StorageError`, `ZipExtractionError`).
**Not a `LysError`**: that is an `HTTPException`, and a stateless util that knows nothing of
request/response must not couple itself to the HTTP layer. Translating it into an HTTP
error is the consumer's responsibility, at the webservice boundary.

Everything on the `pdftotext` path is **non-fatal by design** — each case returns `""` and
lets the caller fall through to OCR, logged at WARNING so an infra problem does not hide in
normal log volume:

| Situation | Log | Consequence |
|---|---|---|
| Binary missing (poppler not installed) | WARNING, names poppler-utils | **Every** PDF pays for OCR until fixed |
| Run exceeds `pdftotext_timeout`, or any `SubprocessError` | WARNING | This file goes to OCR |
| Non-zero exit code (e.g. corrupt PDF, broken xref) | WARNING with stderr | Partial stdout is **discarded**, this file goes to OCR |

The last case matters: trusting truncated output could push it past `min_text_chars` and
skip an OCR pass the document actually needed, silently yielding an incomplete extraction.

Failures **inside** OCR are not caught here — the AI service's own error (`AIError`, after
its provider fallback chain is exhausted) propagates to the caller.

### Encoding

`pdftotext` output is decoded as UTF-8 explicitly (`encoding="utf-8", errors="replace"`)
rather than via `text=True`, which would use the process locale. A container running under
the `C` locale would otherwise raise `UnicodeDecodeError` on any accented text — an
exception that is neither a `SubprocessError` nor a `FileNotFoundError`, so it would escape
the fallback logic entirely.

## Caller responsibilities

The module **trusts its inputs**. Two implications for anything exposing user uploads:

- **Size.** `content` is held fully in memory and written to a temporary file. There is no
  internal cap; enforce an upload size limit upstream.
- **MIME type.** The declared type is used as-is — no magic-byte sniffing. A mislabelled
  file routes straight to the billed OCR endpoint. Verify the declared type upstream if
  untrusted clients control it.

Note also that `pdftotext` parses untrusted PDF input in an unsandboxed subprocess. The
timeout bounds its duration but not its memory or disk use. Deployments processing
untrusted documents at scale should apply container-level resource limits.

## Consumers

- **Future** — document import pipelines (`file_management`), and any application built on
  lys that extracts text from uploaded documents before structuring it. As a framework
  utility, its primary consumers are the applications depending on lys, not lys itself.

## Deployment note

`pdftotext` ships with **poppler-utils**, an OS package — it cannot be installed through
`pip`, so there is no lys extra covering it. Application container images processing PDFs
must install it:

```dockerfile
RUN apt-get update && apt-get install -y --no-install-recommends poppler-utils \
    && rm -rf /var/lib/apt/lists/*
```

This is a Dockerfile line in the consuming service, not a lys concern, but it is called out
here — as with the WeasyPrint native libraries in [`pdf.md`](pdf.md) — so it is not
discovered in production. Unlike WeasyPrint, a missing binary does not crash: it degrades
silently to OCR, which is slower and billed. The WARNING log is the only signal.
