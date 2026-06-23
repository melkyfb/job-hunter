from __future__ import annotations

from playwright.sync_api import sync_playwright


def render_html_to_pdf(html: str) -> bytes:
    """Convert an HTML string to PDF bytes using Playwright + Chromium."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf = page.pdf(format="A4", print_background=True)
        browser.close()
    return pdf
