# PDF Generation

Stateless utility for rendering PDF documents from HTML/CSS (and, as a convenience,
from Markdown). It is a cross-cutting capability — several apps need PDF output — so it
lives in `lys.core`, not in any single app.

> **FRS layout note.** This file inaugurates the foldered FRS convention
> `docs/FRS/<app>/<capability>.md`, with `docs/FRS/_core/` for cross-cutting utilities
> that belong to no single app. Existing flat FRS files and the `Documentation Reference`
> section of `CLAUDE.md` are to be migrated to this layout separately.

## Table of Contents

1. [Overview](#overview)
2. [Scope](#scope)
3. [Placement](#placement)
4. [Dependencies](#dependencies)
5. [Rendering pipeline](#rendering-pipeline)
6. [API contract](#api-contract)
7. [Templates and configuration](#templates-and-configuration)
8. [Determinism](#determinism)
9. [Consumers](#consumers)
10. [Deployment note](#deployment-note)
11. [Implementation notes](#implementation-notes)

## Overview

The utility turns styled HTML into a PDF byte string. Jinja2 (already a lys dependency,
used by emailing) produces the HTML from a template; WeasyPrint converts that HTML + CSS
into the PDF. These are two distinct steps: a template engine yields **text/HTML**, a
rendering engine yields the **PDF binary**. Jinja2 alone cannot produce a PDF.

The utility is **pure and stateless**: input is HTML (or Markdown) plus optional context,
output is `bytes`. It persists nothing, owns no entities, and knows nothing about
versioning, storage, or proof — those concerns belong to its consumers (e.g. the `legal`
app).

## Scope

**In scope**
- `HTML + CSS → PDF` rendering (WeasyPrint).
- `Markdown → HTML` conversion helper (for text-first documents such as legal terms).
- Optional Jinja2 layout wrapping (title page, header/footer, branding) around a body.

**Out of scope** (belongs to consumers)
- Persisting the PDF, computing/storing hashes, versioning, retention.
- Uploading to object storage (see `core/utils/storage.py` and `file_management`).
- Deciding *when* a document is (re)generated.

## Placement

`lys/core/utils/pdf.py` — a stateless helper module alongside `zip.py`, `storage.py`,
`strings.py`. It is **not** an app (no entities, no registration) and **not** placed
inside a consumer app, so any app can use it without inverted dependencies.

## Dependencies

WeasyPrint and the Markdown parser are **optional**, exposed through an extra so they are
not forced on lys consumers that do not render PDFs — consistent with the existing
`mollie` / `storage` / `ai` extras:

```toml
[project.optional-dependencies]
pdf = ["weasyprint>=62", "markdown>=3.6"]
all = [..., "weasyprint>=62", "markdown>=3.6"]
```

The module imports WeasyPrint lazily and raises `PdfRenderError` (see
[Errors](#errors)) if the `pdf` extra is not installed. Jinja2 is already a core
dependency (no extra needed).

## Rendering pipeline

```
Markdown (optional source)
   │  markdown_to_html()            # Markdown → HTML body
   ▼
HTML body
   │  Jinja2 layout (optional)      # inject body into a template: title page, header/
   │                                # footer, logo, CSS
   ▼
Full HTML + CSS
   │  render_html_to_pdf()          # WeasyPrint: layout, fonts, page breaks → PDF
   ▼
PDF bytes
```

For **static** documents (e.g. legal terms with no interpolated values), Jinja2 is only
needed for the presentational wrapper; the body is plain `Markdown → HTML`.

## API contract

Final signatures — module-level functions in `lys/core/utils/pdf.py`. All are
**synchronous** and return `bytes`; see [Implementation notes](#implementation-notes) for
behaviour, configuration, and the sync/async contract.

```python
def markdown_to_html(md: str) -> str:
    """Render a Markdown string to an HTML fragment (body only)."""

def render_html_to_pdf(
    html: str,
    *,
    base_url: str | None = None,
    stylesheets: list[str] | None = None,
) -> bytes:
    """Render full HTML + CSS to PDF bytes. `base_url` resolves relative asset paths
    (fonts, images, CSS) referenced by the HTML. `stylesheets` passes extra CSS to
    WeasyPrint on top of what the HTML links."""

def render_markdown_to_pdf(
    md: str,
    *,
    template: str | None = None,
    context: dict | None = None,
    base_url: str | None = None,
) -> bytes:
    """Convenience: Markdown → HTML body → Jinja2 `template` (with `context`, body
    injected) → PDF. When `template` is None, lys's built-in `default.html` is used."""
```

The utility returns `bytes` so the caller decides what to do with them (store, hash,
stream to a response, attach to an email).

## Templates and configuration

Layout templates follow the **emailing pattern**: the machinery is in lys, the template
**files live in the consuming application** and are loaded from a configured path.

- Emailing precedent: `EmailingService` builds a `FileSystemLoader` from
  `settings.email.template_path` (e.g. the app sets `templates/emails`).
- PDF: an analogous setting points to the PDF layout templates (e.g. `templates/pdf`).
  lys ships a **minimal default layout/CSS** as a fallback; applications override it with
  their own branded templates.

lys therefore provides the rendering and the loader wiring; the application provides the
HTML/CSS templates (and, for document bodies, the Markdown content — which is application
content, not part of lys).

## Determinism

WeasyPrint output is **not guaranteed byte-identical** across environments or library
versions (embedded PDF metadata timestamps, font subsetting). This utility does not
attempt to normalize that.

Consequence for consumers that hash the output (e.g. the `legal` app, to prove which exact
document was accepted): **render once, then freeze the artifact and its hash**; never
re-render a version that has already been published/accepted. The "generate once" policy
is the consumer's responsibility — this utility only renders on demand.

## Consumers

- **`legal`** (`lys.apps.legal`) — renders versioned legal documents (terms of use, sales
  terms, privacy policy) from Markdown to an immutable PDF. First consumer; see
  [`../legal/legal_documents.md`](../legal/legal_documents.md).
- **Future** — invoice/receipt generation (licensing), data-portability export bundles
  (GDPR art. 20), any report export.

## Deployment note

WeasyPrint relies on native system libraries (Cairo, Pango, GDK-PixBuf, and their
dependencies). Application container images that install the `pdf` extra must also install
these OS packages, otherwise import/render fails at runtime. This is a Dockerfile line in
the consuming service, not a lys concern, but it is called out here so it is not
discovered at build time.

## Implementation notes

Design decisions pinned so the module can be implemented without further input. Follow
existing lys conventions where referenced.

### Sync / async

WeasyPrint is CPU-bound and synchronous, so the three functions are plain `def` returning
`bytes`.

- **Async callers** (GraphQL webservices) MUST offload to a worker thread to avoid blocking
  the event loop: `await asyncio.to_thread(render_markdown_to_pdf, md, template=...)`.
- **Sync callers** (Celery tasks) call directly.
- A thin async wrapper `render_markdown_to_pdf_async(...)` built on `asyncio.to_thread`
  MAY be added for ergonomics; it is optional and adds no new behaviour.

### Configuration

New settings class **`PdfSettings(BaseSettings)`** (`core/configs.py`), mirroring
`EmailSettings`, with a single field for now:

- `template_path: str` — default **`"/templates/pdf"`** (leading slash, exactly like
  `EmailSettings.template_path = "/templates/emails"` at `configs.py:141`). Directory where
  the **application's** layout templates live.

Wire it in `AppSettings.__init__` alongside the existing namespaces (`configs.py:238-239`):

```python
self.email: EmailSettings = EmailSettings()
self.ai: AISettings = AISettings()
self.pdf: PdfSettings = PdfSettings()   # ← add
```

Resolution is identical to emailing — `pathlib.Path().resolve() / settings.pdf.template_path.lstrip('/')`
(the `.lstrip('/')` absorbs the leading slash), as in `EmailingService.get_template_env`.

### Template loading and default layout

A single Jinja2 `Environment`, cached like emailing's `_template_env`, built with a
`ChoiceLoader`:

1. `FileSystemLoader(settings.pdf.template_path)` — application templates (take precedence).
2. `PackageLoader("lys.core.utils", "pdf_templates")` — lys built-in fallback.

lys ships `lys/core/utils/pdf_templates/default.html` and `default.css`: a minimal A4
layout with a title block and a `{{ body }}` slot. `render_markdown_to_pdf(template=None)`
uses `default.html`. Templates receive `body` (the rendered HTML) plus any `context` keys.

### Markdown

Python-Markdown with extensions `["extra", "toc", "sane_lists"]`:
- `extra` → tables, fenced code, `attr_list`, `def_list`, etc. (legal terms use tables).
- `toc` → heading anchors / optional table of contents.
- `sane_lists` → predictable list nesting.

### CSS

Styling lives in the layout template (inline `<style>` or `<link href>` resolved via
`base_url`); the utility hardcodes no CSS. `render_html_to_pdf(stylesheets=...)` passes
extra CSS to WeasyPrint (list of CSS strings or file paths) for programmatic overrides.

### Errors

Define a bespoke domain exception **`PdfRenderError(Exception)`** in the module, matching
the convention of the other core utils (`StorageError`, `ZipExtractionError` — plain
`Exception` subclasses). **Do not raise `LysError`**: it is an `HTTPException`
(`core/errors.py:7`), and a pure, stateless util that knows nothing of request/response
must not couple itself to the HTTP layer. Translating a `PdfRenderError` into an HTTP
error (`LysError`) is the **consumer's** responsibility, at the webservice boundary.

- Import WeasyPrint and Markdown **lazily inside the functions**. If the `pdf` extra is
  missing, raise `PdfRenderError` with an actionable message (e.g. *"PDF rendering
  requires the 'pdf' extra: pip install runid-lys[pdf]"*). Never let a bare `ImportError`
  surface.
- Wrap WeasyPrint/rendering failures in `PdfRenderError` as well (as `StorageError` wraps
  backend failures).

### Tests (`pytest`, `dev` extra)

- `render_markdown_to_pdf` on a sample containing a heading and a table → output starts
  with `b"%PDF-"`.
- `markdown_to_html` renders a table and fenced code block (extensions active).
- Missing-extra path (simulate the import failing) → raises `PdfRenderError`, not a bare
  `ImportError`.
- Application-template override beats the lys default (register a dummy template dir and
  assert it is used).
