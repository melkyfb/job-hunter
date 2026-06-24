from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from app.core.config import settings
from app.core.paths import DATA_DIR
from app.models.jobs import RankedJob

logger = logging.getLogger(__name__)

_CACHE_DIR = DATA_DIR / "search_cache"


def _cache_key(query: str, location: str, max_results: int) -> str:
    raw = f"{query.lower().strip()}|{location.lower().strip()}|{max_results}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _ttl() -> Optional[timedelta]:
    hours = settings.search_cache_ttl_hours
    return timedelta(hours=hours) if hours > 0 else None


def get_cached(
    query: str, location: str, max_results: int
) -> tuple[list[RankedJob], datetime] | None:
    """
    Returns (results, cached_at) if a valid non-expired cache entry exists, else None.
    """
    ttl = _ttl()
    if ttl is None:
        return None

    key = _cache_key(query, location, max_results)
    path = _CACHE_DIR / f"{key}.json"

    if not path.exists():
        return None

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        cached_at = datetime.fromisoformat(data["cached_at"])
        if datetime.now() - cached_at > ttl:
            logger.debug("Cache expired for key %s", key)
            return None
        results = [RankedJob.model_validate(r) for r in data["results"]]
        logger.info("Cache hit for '%s' (%d results, cached %s)", query, len(results), cached_at)
        return results, cached_at
    except Exception as exc:
        logger.warning("Cache read error for key %s: %s", key, exc)
        return None


def set_cache(query: str, location: str, max_results: int, results: list[RankedJob]) -> None:
    """Persists results to disk cache."""
    if _ttl() is None:
        return

    key = _cache_key(query, location, max_results)
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = _CACHE_DIR / f"{key}.json"

    try:
        payload = {
            "cached_at": datetime.now().isoformat(),
            "query": query,
            "location": location,
            "results": [r.model_dump(mode="json") for r in results],
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        logger.info("Cached %d results for '%s' → %s", len(results), query, key)
    except Exception as exc:
        logger.warning("Cache write error for key %s: %s", key, exc)
