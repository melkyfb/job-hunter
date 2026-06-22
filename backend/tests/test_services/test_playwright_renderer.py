from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.playwright_renderer import (
    build_dummy_context,
    build_dummy_cover_letter_context,
    render_template_to_html,
    render_html_to_pdf,
    render_cover_letter_template_to_html,
)


def test_render_template_to_html_simple():
    template = "<h1>{{ profile.contact.full_name }}</h1>"
    ctx = build_dummy_context()
    html = render_template_to_html(template, ctx)
    assert "John Doe" in html


def test_render_template_to_html_loop():
    template = "{% for exp in profile.work_experiences %}{{ exp.role }}{% endfor %}"
    ctx = build_dummy_context()
    html = render_template_to_html(template, ctx)
    assert "Engineer" in html


def test_render_cover_letter_template_to_html():
    template = "<p>{{ job.company }}</p>{% for para in letter_body.split('\\n\\n') %}<p>{{ para }}</p>{% endfor %}"
    ctx = build_dummy_cover_letter_context()
    html = render_cover_letter_template_to_html(
        template,
        letter_body="Dear team,\n\nI am excited.",
        job_title="Engineer",
        job_company="Acme",
        contact_name="John Doe",
        contact_email="john@example.com",
    )
    assert "Acme" in html
    assert "excited" in html


def test_render_html_to_pdf_calls_playwright():
    fake_pdf = b"%PDF-fake"
    with patch("app.services.playwright_renderer.sync_playwright") as mock_pw:
        mock_ctx = MagicMock()
        mock_pw.return_value.__enter__.return_value = mock_ctx
        mock_browser = MagicMock()
        mock_ctx.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_page.pdf.return_value = fake_pdf

        result = render_html_to_pdf("<html></html>")
        assert result == fake_pdf
        mock_page.set_content.assert_called_once()
        mock_page.pdf.assert_called_once_with(format="A4", print_background=True)
        mock_browser.close.assert_called_once()
