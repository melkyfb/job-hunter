from __future__ import annotations

from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.models.jobs import JobPosting, MatchScore, RankedJob

_JOB = JobPosting(
    id=uuid4(), title="Backend Engineer", company="Acme", location="Munich",
    description="Python FastAPI", url="https://example.com/1", source="mock",
)
_MATCH = MatchScore(
    job_id=_JOB.id, score=80, keywords_found=["Python"], keywords_missing=[],
    justification="Good match.",
)
_RESULT = [RankedJob(posting=_JOB, match=_MATCH)]


def test_cache_miss_on_empty(tmp_path):
    with patch("app.services.search_cache._CACHE_DIR", tmp_path):
        from app.services.search_cache import get_cached
        assert get_cached("Python", "Munich", 10) is None


def test_cache_roundtrip(tmp_path):
    with patch("app.services.search_cache._CACHE_DIR", tmp_path):
        from app.services.search_cache import get_cached, set_cache
        set_cache("Python", "Munich", 10, _RESULT)
        hit = get_cached("Python", "Munich", 10)
        assert hit is not None
        results, cached_at = hit
        assert len(results) == 1
        assert results[0].posting.title == "Backend Engineer"


def test_cache_key_is_case_insensitive(tmp_path):
    with patch("app.services.search_cache._CACHE_DIR", tmp_path):
        from app.services.search_cache import get_cached, set_cache
        set_cache("Python Backend", "munich, germany", 10, _RESULT)
        # Different casing should still hit
        hit = get_cached("PYTHON BACKEND", "Munich, Germany", 10)
        assert hit is not None


def test_cache_miss_after_ttl_zero(tmp_path):
    """TTL=0 means cache is disabled."""
    with patch("app.services.search_cache._CACHE_DIR", tmp_path), \
         patch("app.services.search_cache.settings") as mock_settings:
        mock_settings.search_cache_ttl_hours = 0
        from app.services import search_cache
        # Force reload of _ttl by calling directly
        import importlib
        importlib.reload(search_cache)
        # With ttl=0, set_cache should be a no-op
        search_cache.set_cache("Python", "Munich", 10, _RESULT)
        assert not list(tmp_path.glob("*.json"))


def test_cache_expired(tmp_path):
    from datetime import datetime, timedelta
    import json

    with patch("app.services.search_cache._CACHE_DIR", tmp_path):
        from app.services.search_cache import get_cached, _cache_key
        # Write an entry with a timestamp 3 hours ago
        key = _cache_key("Python", "Munich", 10)
        old_time = (datetime.now() - timedelta(hours=3)).isoformat()
        payload = {
            "cached_at": old_time,
            "query": "Python",
            "location": "Munich",
            "results": [r.model_dump(mode="json") for r in _RESULT],
        }
        (tmp_path / f"{key}.json").write_text(json.dumps(payload))
        # Default TTL is 2h, so 3h old should be expired
        assert get_cached("Python", "Munich", 10) is None
