"""
Stateless PDF rendering utilities.

Renders PDF documents from HTML/CSS (via WeasyPrint) and, as a convenience, from
Markdown (via Python-Markdown + an optional Jinja2 layout). This is a cross-cutting
capability used by several apps, so it lives in ``lys.core`` and owns no entities,
persists nothing, and knows nothing about versioning, storage, or HTTP.

WeasyPrint and the Markdown parser are optional dependencies exposed through the
``pdf`` extra. They are imported lazily inside the functions so that lys consumers
which never render PDFs are not forced to install them. If the extra is missing, a
:class:`PdfRenderError` is raised instead of a bare ``ImportError``.

WeasyPrint output is not guaranteed byte-identical across environments or library
versions (embedded metadata timestamps, font subsetting). Consumers that hash the
output must render once and freeze the artifact and its hash.
"""
import asyncio
import functools
import logging
import pathlib
from typing import Optional

from jinja2 import ChoiceLoader, Environment, FileSystemLoader, PackageLoader

logger = logging.getLogger(__name__)

# Python-Markdown extensions: tables/fenced-code (extra), heading anchors (toc),
# predictable list nesting (sane_lists).
_MARKDOWN_EXTENSIONS = ["extra", "toc", "sane_lists"]

# Built-in fallback layout used when render_markdown_to_pdf is called with template=None.
_DEFAULT_TEMPLATE = "default.html"

_MISSING_EXTRA_MESSAGE = (
    "PDF rendering requires the 'pdf' extra: pip install runid-lys[pdf]"
)

# Cached Jinja2 environment (see get_template_env), mirroring EmailingService.
_template_env: Optional[Environment] = None


class PdfRenderError(Exception):
    """Raised when PDF rendering fails.

    Covers both the missing-``pdf``-extra case and rendering failures. This is a
    plain domain exception (like ``StorageError`` / ``ZipExtractionError``), not a
    ``LysError``: a stateless util must not couple itself to the HTTP layer.
    Translating this into an HTTP error is the consumer's responsibility, at the
    webservice boundary.
    """
    pass


def get_template_env() -> Environment:
    """Get or create the cached Jinja2 environment for PDF layout templates.

    Uses a ``ChoiceLoader`` so application templates take precedence over the lys
    built-in fallback:

    1. ``FileSystemLoader`` on ``settings.pdf.template_path`` — application templates.
    2. ``PackageLoader`` on ``lys.core.utils/pdf_templates`` — lys built-in fallback.

    Returns:
        The cached Jinja2 environment.
    """
    global _template_env
    if _template_env is None:
        from lys.core.configs import settings

        app_template_path = pathlib.Path().resolve() / settings.pdf.template_path.lstrip("/")

        _template_env = Environment(
            loader=ChoiceLoader([
                FileSystemLoader(str(app_template_path)),
                PackageLoader("lys.core.utils", "pdf_templates"),
            ]),
            autoescape=True,
        )
    return _template_env


def markdown_to_html(md: str) -> str:
    """Render a Markdown string to an HTML fragment (body only).

    Args:
        md: Markdown source.

    Returns:
        The rendered HTML fragment.

    Raises:
        PdfRenderError: If the ``pdf`` extra is not installed.
    """
    try:
        import markdown
    except ImportError as exc:
        raise PdfRenderError(_MISSING_EXTRA_MESSAGE) from exc

    return markdown.markdown(md, extensions=_MARKDOWN_EXTENSIONS)


def render_html_to_pdf(
    html: str,
    *,
    base_url: Optional[str] = None,
    stylesheets: Optional[list[str]] = None,
) -> bytes:
    """Render full HTML + CSS to PDF bytes.

    Args:
        html: Full HTML document (with its own ``<style>``/``<link>`` styling).
        base_url: Base URL used to resolve relative asset paths (fonts, images, CSS)
            referenced by the HTML.
        stylesheets: Extra CSS passed to WeasyPrint on top of what the HTML links.
            Each item is a CSS string or a file path.

    Returns:
        The rendered PDF as bytes.

    Raises:
        PdfRenderError: If the ``pdf`` extra is not installed, or rendering fails.
    """
    try:
        from weasyprint import CSS, HTML
    except ImportError as exc:
        raise PdfRenderError(_MISSING_EXTRA_MESSAGE) from exc

    try:
        css = [CSS(filename=sheet) if pathlib.Path(sheet).is_file() else CSS(string=sheet)
               for sheet in (stylesheets or [])]
        return HTML(string=html, base_url=base_url).write_pdf(stylesheets=css or None)
    except PdfRenderError:
        raise
    except Exception as exc:
        raise PdfRenderError(f"Failed to render HTML to PDF: {exc}") from exc


def render_markdown_to_pdf(
    md: str,
    *,
    template: Optional[str] = None,
    context: Optional[dict] = None,
    base_url: Optional[str] = None,
) -> bytes:
    """Render Markdown to PDF through an optional Jinja2 layout.

    Pipeline: Markdown -> HTML body -> Jinja2 ``template`` (with ``context``, the body
    injected as ``body``) -> WeasyPrint -> PDF.

    Args:
        md: Markdown source for the document body.
        template: Name of the Jinja2 layout template to wrap the body. When ``None``,
            the lys built-in ``default.html`` layout is used.
        context: Extra values passed to the template alongside ``body``.
        base_url: Base URL used to resolve relative asset paths referenced by the
            template.

    Returns:
        The rendered PDF as bytes.

    Raises:
        PdfRenderError: If the ``pdf`` extra is not installed, or rendering fails.
    """
    body = markdown_to_html(md)

    try:
        jinja_template = get_template_env().get_template(template or _DEFAULT_TEMPLATE)
        full_html = jinja_template.render(body=body, **(context or {}))
    except PdfRenderError:
        raise
    except Exception as exc:
        raise PdfRenderError(f"Failed to render PDF template: {exc}") from exc

    return render_html_to_pdf(full_html, base_url=base_url)


async def render_markdown_to_pdf_async(
    md: str,
    *,
    template: Optional[str] = None,
    context: Optional[dict] = None,
    base_url: Optional[str] = None,
) -> bytes:
    """Async wrapper around :func:`render_markdown_to_pdf`.

    WeasyPrint is CPU-bound and synchronous; async callers (e.g. GraphQL webservices)
    must offload it to a worker thread to avoid blocking the event loop. This wrapper
    does that via ``asyncio.to_thread`` and adds no new behaviour.
    """
    return await asyncio.to_thread(
        functools.partial(
            render_markdown_to_pdf,
            md,
            template=template,
            context=context,
            base_url=base_url,
        )
    )
