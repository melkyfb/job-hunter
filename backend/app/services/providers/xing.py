from __future__ import annotations

import asyncio
import logging
from urllib.parse import quote_plus
from uuid import uuid4

from playwright.async_api import async_playwright

from app.models.jobs import JobPosting

logger = logging.getLogger(__name__)

_TIMEOUT = 30_000
_MAX_SCROLLS = 3
_SCROLL_WAIT = 1500


class XingScraper:
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        return asyncio.run(self._async_search(query, location, max_results))

    async def _async_search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        url = (
            f"https://www.xing.com/jobs/search"
            f"?keywords={quote_plus(query)}&location={quote_plus(location)}"
        )
        results: list[JobPosting] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=_TIMEOUT)
                try:
                    await page.click('[data-testid="cookie-consent-button-accept"]', timeout=3000)
                except Exception:
                    pass

                for _ in range(_MAX_SCROLLS):
                    cards = await page.query_selector_all('[data-testid="job-listing-item"]')
                    if len(cards) >= max_results:
                        break
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(_SCROLL_WAIT)

                cards = (await page.query_selector_all('[data-testid="job-listing-item"]'))[:max_results]
                for card in cards:
                    try:
                        results.append(await _xing_card_to_posting(card))
                    except Exception as exc:
                        logger.debug("Xing card parse error: %s", exc)
            finally:
                await browser.close()

        return results


async def _xing_card_to_posting(card) -> JobPosting:
    title_el = await card.query_selector('[data-testid="job-listing-item-title"]')
    company_el = await card.query_selector('[data-testid="job-listing-item-company-name"]')
    location_el = await card.query_selector('[data-testid="job-listing-item-location"]')
    link_el = await card.query_selector('a[data-testid="job-listing-item-title-link"]')

    title = (await title_el.inner_text()).strip() if title_el else ""
    company = (await company_el.inner_text()).strip() if company_el else ""
    loc = (await location_el.inner_text()).strip() if location_el else ""
    href = await link_el.get_attribute("href") if link_el else None
    url = href or ""

    return JobPosting(
        id=uuid4(),
        title=title,
        company=company,
        location=loc,
        description="",
        url=url,
        source="xing",
    )
