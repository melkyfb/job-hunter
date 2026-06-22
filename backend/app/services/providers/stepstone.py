from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone
from urllib.parse import quote_plus
from uuid import uuid4

from playwright.async_api import async_playwright

from app.models.jobs import JobPosting

logger = logging.getLogger(__name__)

_TIMEOUT = 30_000  # ms
_MAX_SCROLLS = 3
_SCROLL_WAIT = 1500  # ms


class StepstoneScraper:
    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        return asyncio.run(self._async_search(query, location, max_results))

    async def _async_search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        url = (
            f"https://www.stepstone.de/jobs/{quote_plus(query)}"
            f"?where={quote_plus(location)}"
        )
        results: list[JobPosting] = []

        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await page.goto(url, timeout=_TIMEOUT)
                try:
                    await page.click('[data-at="cookie-consent-accept-all"]', timeout=3000)
                except Exception:
                    pass

                for _ in range(_MAX_SCROLLS):
                    cards = await page.query_selector_all('article[data-at="job-item"]')
                    if len(cards) >= max_results:
                        break
                    await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    await page.wait_for_timeout(_SCROLL_WAIT)

                cards = (await page.query_selector_all('article[data-at="job-item"]'))[:max_results]
                for card in cards:
                    try:
                        results.append(await _stepstone_card_to_posting(card))
                    except Exception as exc:
                        logger.debug("Stepstone card parse error: %s", exc)
            finally:
                await browser.close()

        return results


async def _stepstone_card_to_posting(card) -> JobPosting:
    title_el = await card.query_selector('[data-at="job-item-title"]')
    company_el = await card.query_selector('[data-at="job-item-company-name"]')
    location_el = await card.query_selector('[data-at="job-item-location"]')
    link_el = await card.query_selector('a[data-at="job-item-title"]')
    time_el = await card.query_selector('time[datetime]')

    title = (await title_el.inner_text()).strip() if title_el else ""
    company = (await company_el.inner_text()).strip() if company_el else ""
    loc = (await location_el.inner_text()).strip() if location_el else ""

    url = ""
    if link_el:
        href = await link_el.get_attribute("href") or ""
        url = href if href.startswith("http") else f"https://www.stepstone.de{href}"

    posted_at: datetime | None = None
    if time_el:
        dt_str = await time_el.get_attribute("datetime")
        if dt_str:
            try:
                dt = datetime.fromisoformat(dt_str)
                posted_at = dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
            except ValueError:
                pass

    return JobPosting(
        id=uuid4(),
        title=title,
        company=company,
        location=loc,
        description="",
        url=url,
        source="stepstone",
        posted_at=posted_at,
    )
