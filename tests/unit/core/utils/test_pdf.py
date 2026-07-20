"""
Unit tests for the stateless PDF rendering utilities.
"""
import sys
from unittest.mock import patch

import pytest

from lys.core.utils import pdf as pdf_module
from lys.core.utils.pdf import (
    PdfRenderError,
    markdown_to_html,
    render_html_to_pdf,
    render_markdown_to_pdf,
    render_markdown_to_pdf_async,
)


@pytest.fixture(autouse=True)
def _reset_template_env():
    """Reset the cached Jinja2 environment around each test.

    The environment is resolved from settings/cwd and cached module-side, so tests
    that change either must start from a clean cache.
    """
    pdf_module._template_env = None
    yield
    pdf_module._template_env = None


class TestMarkdownToHtml:
    """Tests for markdown_to_html()."""

    def test_renders_table(self):
        html = markdown_to_html("| a | b |\n|---|---|\n| 1 | 2 |")
        assert "<table>" in html
        assert "<td>1</td>" in html

    def test_renders_fenced_code(self):
        html = markdown_to_html("```python\nx = 1\n```")
        assert "<pre>" in html
        assert "<code" in html

    def test_missing_extra_raises_pdf_render_error(self):
        with patch.dict(sys.modules, {"markdown": None}):
            with pytest.raises(PdfRenderError) as exc_info:
                markdown_to_html("# hi")
        assert "pdf" in str(exc_info.value).lower()
        assert not isinstance(exc_info.value, ImportError)


class TestRenderHtmlToPdf:
    """Tests for render_html_to_pdf()."""

    def test_returns_pdf_bytes(self):
        pdf = render_html_to_pdf("<h1>Hello</h1>")
        assert pdf[:5] == b"%PDF-"

    def test_inline_stylesheet_string(self):
        pdf = render_html_to_pdf("<h1>Hello</h1>", stylesheets=["h1 { color: red; }"])
        assert pdf[:5] == b"%PDF-"

    def test_missing_extra_raises_pdf_render_error(self):
        with patch.dict(sys.modules, {"weasyprint": None}):
            with pytest.raises(PdfRenderError):
                render_html_to_pdf("<h1>hi</h1>")


class TestRenderMarkdownToPdf:
    """Tests for render_markdown_to_pdf()."""

    def test_default_template_returns_pdf(self):
        pdf = render_markdown_to_pdf(
            "# Title\n\n| a | b |\n|---|---|\n| 1 | 2 |",
            context={"title": "Doc"},
        )
        assert pdf[:5] == b"%PDF-"

    def test_missing_extra_raises_pdf_render_error(self):
        with patch.dict(sys.modules, {"markdown": None}):
            with pytest.raises(PdfRenderError):
                render_markdown_to_pdf("# hi")

    def test_falls_back_to_lys_default_template(self, tmp_path, monkeypatch):
        """With no application template dir, the lys built-in default.html is used."""
        from lys.core.configs import settings

        monkeypatch.chdir(tmp_path)  # cwd has no templates/pdf directory
        monkeypatch.setattr(settings.pdf, "template_path", "/templates/pdf")
        pdf_module._template_env = None

        rendered = pdf_module.get_template_env().get_template("default.html").render(
            body="<p>body-content</p>", title="T"
        )
        assert "<p>body-content</p>" in rendered
        assert "@page" in rendered  # default.css is inlined via {% include %}

    def test_application_template_overrides_lys_default(self, tmp_path, monkeypatch):
        """A default.html in the application template dir takes precedence over lys's."""
        from lys.core.configs import settings

        monkeypatch.chdir(tmp_path)
        template_dir = tmp_path / "templates" / "pdf"
        template_dir.mkdir(parents=True)
        (template_dir / "default.html").write_text("APP_OVERRIDE {{ body }}")
        monkeypatch.setattr(settings.pdf, "template_path", "/templates/pdf")
        pdf_module._template_env = None

        rendered = pdf_module.get_template_env().get_template("default.html").render(body="X")
        assert rendered == "APP_OVERRIDE X"


class TestRenderMarkdownToPdfAsync:
    """Tests for the async wrapper."""

    @pytest.mark.asyncio
    async def test_returns_pdf_bytes(self):
        pdf = await render_markdown_to_pdf_async("# hi", context={"title": "Doc"})
        assert pdf[:5] == b"%PDF-"
