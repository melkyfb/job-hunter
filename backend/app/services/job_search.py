from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable

from app.core.config import settings
from app.models.jobs import JobPosting
from app.services.providers.adzuna import AdzunaProvider
from app.services.providers.base import SearchProvider
from app.services.providers.mock import MockProvider

logger = logging.getLogger(__name__)

__all__ = ["SearchProvider", "MultiProvider", "get_search_provider", "get_multi_provider"]


class MultiProvider:
    """Runs multiple SearchProviders in parallel and deduplicates results by URL."""

    def __init__(self, providers: list[SearchProvider]) -> None:
        self._providers = providers

    def search(self, query: str, location: str, max_results: int) -> list[JobPosting]:
        all_results: list[JobPosting] = []
        with ThreadPoolExecutor(max_workers=max(len(self._providers), 1)) as pool:
            futures = {
                pool.submit(p.search, query, location, max_results): p
                for p in self._providers
            }
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    all_results.extend(future.result())
                except Exception as exc:
                    logger.warning(
                        "Provider %s failed: %s", type(provider).__name__, exc
                    )

        seen: set[str] = set()
        deduped: list[JobPosting] = []
        for posting in all_results:
            if posting.url and posting.url not in seen:
                seen.add(posting.url)
                deduped.append(posting)
        return deduped


_REGISTRY: dict[str, Callable[[], SearchProvider]] = {
    "adzuna": AdzunaProvider,
    "mock": MockProvider,
}


def get_multi_provider(enabled: list[str]) -> MultiProvider:
    """Instantiate and return a MultiProvider for the given provider names."""
    names = enabled if enabled else ["mock"]
    providers: list[SearchProvider] = []
    for name in names:
        factory = _REGISTRY.get(name)
        if factory is None:
            logger.warning("Unknown provider '%s', skipping", name)
            continue
        try:
            providers.append(factory())
        except Exception as exc:
            logger.error("Failed to instantiate provider '%s': %s", name, exc)
    if not providers:
        providers = [MockProvider()]
    return MultiProvider(providers)


def get_search_provider() -> SearchProvider:
    """Backwards-compat shim — returns single provider based on settings."""
    if settings.search_provider == "adzuna":
        return AdzunaProvider()
    return MockProvider()
