from __future__ import annotations

import logging
from urllib.parse import quote_plus
from uuid import uuid4

from playwright.sync_api import sync_playwright

from app.models.jobs import JobPosting

logger = logging.getLogger(__name__)

_TIMEOUT = 30_000
_MAX_SCROLLS = 3
_SCROLL_WAIT = 1500


class XingScraper:
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        url = (
            f"https://www.xing.com/jobs/search"
            f"?keywords={quote_plus(query)}&location={quote_plus(location)}"
        )
        results: list[JobPosting] = []

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            try:
                page.goto(url, timeout=_TIMEOUT)
                try:
                    page.click('[data-testid="cookie-consent-button-accept"]', timeout=3000)
                except Exception:
                    pass

                for _ in range(_MAX_SCROLLS):
                    cards = page.query_selector_all('[data-testid="job-listing-item"]')
                    if len(cards) >= max_results:
                        break
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(_SCROLL_WAIT)

                cards = page.query_selector_all('[data-testid="job-listing-item"]')[:max_results]
                for card in cards:
                    try:
                        results.append(_xing_card_to_posting(card))
                    except Exception as exc:
                        logger.debug("Xing card parse error: %s", exc)
            finally:
                browser.close()

        return results


def _xing_card_to_posting(card) -> JobPosting:
    title_el = card.query_selector('[data-testid="job-listing-item-title"]')
    company_el = card.query_selector('[data-testid="job-listing-item-company-name"]')
    location_el = card.query_selector('[data-testid="job-listing-item-location"]')
    link_el = card.query_selector('a[data-testid="job-listing-item-title-link"]')

    title = title_el.inner_text().strip() if title_el else ""
    company = company_el.inner_text().strip() if company_el else ""
    loc = location_el.inner_text().strip() if location_el else ""
    url = link_el.get_attribute("href") if link_el else ""

    return JobPosting(
        id=uuid4(),
        title=title,
        company=company,
        location=loc,
        description="",
        url=url or "",
        source="xing",
    )
