from __future__ import annotations

from uuid import uuid4

import pytest

from app.models.jobs import JobPosting


def _make_posting(url: str = "https://example.com/job") -> JobPosting:
    return JobPosting(
        id=uuid4(),
        title="Python Dev",
        company="Acme",
        location="Munich",
        description="Great role",
        url=url,
        source="mock",
    )


# ── AdzunaProvider ────────────────────────────────────────────────────────────

def test_adzuna_provider_builds_correct_url():
    from app.services.providers.adzuna import AdzunaProvider
    provider = AdzunaProvider()
    assert hasattr(provider, "_BASE")
    assert "adzuna.com" in provider._BASE


def test_adzuna_provider_to_posting_maps_fields():
    from app.services.providers.adzuna import AdzunaProvider
    raw = {
        "title": "Backend Dev",
        "company": {"display_name": "TechCo"},
        "location": {"display_name": "Munich"},
        "description": "Great job",
        "redirect_url": "https://adzuna.com/jobs/1",
        "salary_min": 70000,
        "salary_max": 90000,
        "contract_type": "permanent",
        "created": "2026-06-22T10:00:00Z",
    }
    posting = AdzunaProvider._to_posting(raw)
    assert posting.title == "Backend Dev"
    assert posting.company == "TechCo"
    assert posting.source == "adzuna"
    assert "70,000" in posting.salary_range
    assert posting.employment_type == "permanent"


# ── MockProvider ──────────────────────────────────────────────────────────────

def test_mock_provider_returns_job_postings():
    from app.services.providers.mock import MockProvider
    provider = MockProvider()
    results = provider.search("python", "Munich", 3)
    assert len(results) == 3
    assert all(isinstance(r, JobPosting) for r in results)
    assert all(r.source == "mock" for r in results)


def test_mock_provider_respects_max_results():
    from app.services.providers.mock import MockProvider
    results = MockProvider().search("python", "Munich", 1)
    assert len(results) == 1


# ── MultiProvider ─────────────────────────────────────────────────────────────

from unittest.mock import Mock


def test_multi_provider_merges_results_from_all_providers():
    from app.services.job_search import MultiProvider

    p1 = Mock()
    p1.search.return_value = [_make_posting("https://site-a.com/1")]
    p2 = Mock()
    p2.search.return_value = [_make_posting("https://site-b.com/1")]

    multi = MultiProvider([p1, p2])
    results = multi.search("python", "Munich", 5)

    assert len(results) == 2
    urls = {r.url for r in results}
    assert "https://site-a.com/1" in urls
    assert "https://site-b.com/1" in urls


def test_multi_provider_deduplicates_by_url():
    from app.services.job_search import MultiProvider

    same_url = "https://same.com/job/1"
    p1 = Mock()
    p1.search.return_value = [_make_posting(same_url)]
    p2 = Mock()
    p2.search.return_value = [_make_posting(same_url)]

    multi = MultiProvider([p1, p2])
    results = multi.search("python", "Munich", 5)

    assert len(results) == 1
    assert results[0].url == same_url


def test_multi_provider_continues_when_one_provider_fails():
    from app.services.job_search import MultiProvider

    bad = Mock()
    bad.search.side_effect = RuntimeError("rate limited")
    good = Mock()
    good.search.return_value = [_make_posting("https://good.com/job/1")]

    multi = MultiProvider([bad, good])
    results = multi.search("python", "Munich", 5)

    assert len(results) == 1
    assert results[0].url == "https://good.com/job/1"


def test_get_multi_provider_falls_back_to_mock_when_empty():
    from app.services.job_search import get_multi_provider
    from app.services.providers.mock import MockProvider

    multi = get_multi_provider([])
    # Should still be usable — delegate to MockProvider
    results = multi.search("python", "Munich", 2)
    assert len(results) == 2


def test_get_multi_provider_skips_unknown_names():
    from app.services.job_search import get_multi_provider

    # Should not raise — unknown name is skipped
    multi = get_multi_provider(["nonexistent_provider", "mock"])
    results = multi.search("python", "Munich", 1)
    assert len(results) >= 1


# ── run_pipeline provider param ───────────────────────────────────────────────

def test_run_pipeline_uses_injected_provider():
    from unittest.mock import patch
    from app.models.profile import ProfileMaster, ContactInfo
    from app.services.job_pipeline import run_pipeline

    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))
    mock_provider = Mock()
    mock_provider.search.return_value = []  # empty → pipeline returns []

    result = run_pipeline(profile, "python", "Munich", max_results=5, provider=mock_provider)

    mock_provider.search.assert_called_once_with("python", "Munich", 5)
    assert result == []


# ── JobSpyProvider ────────────────────────────────────────────────────────────

def test_jobspy_provider_maps_dataframe_row_to_posting():
    import pandas as pd
    from unittest.mock import patch
    from app.services.providers.jobspy_prov import JobSpyProvider

    mock_df = pd.DataFrame([{
        "title": "Python Engineer",
        "company": "TechCo GmbH",
        "location": "Munich, Germany",
        "description": "Build great things with Python",
        "job_url": "https://linkedin.com/jobs/123",
        "date_posted": None,
        "min_amount": 70000.0,
        "max_amount": 90000.0,
        "currency": "EUR",
        "job_type": "fulltime",
    }])

    with patch("app.services.providers.jobspy_prov.scrape_jobs", return_value=mock_df):
        results = JobSpyProvider("linkedin").search("python", "Munich", 5)

    assert len(results) == 1
    assert results[0].title == "Python Engineer"
    assert results[0].company == "TechCo GmbH"
    assert results[0].source == "linkedin"
    assert results[0].url == "https://linkedin.com/jobs/123"
    assert "70" in results[0].salary_range
    assert results[0].employment_type == "fulltime"


def test_jobspy_provider_returns_empty_on_empty_dataframe():
    import pandas as pd
    from unittest.mock import patch
    from app.services.providers.jobspy_prov import JobSpyProvider

    with patch("app.services.providers.jobspy_prov.scrape_jobs", return_value=pd.DataFrame()):
        results = JobSpyProvider("indeed").search("python", "Munich", 5)

    assert results == []


def test_jobspy_provider_calls_scrape_jobs_with_correct_args():
    import pandas as pd
    from unittest.mock import patch, call
    from app.services.providers.jobspy_prov import JobSpyProvider

    with patch("app.services.providers.jobspy_prov.scrape_jobs", return_value=pd.DataFrame()) as mock_scrape:
        JobSpyProvider("google").search("python developer", "Munich", 10)

    mock_scrape.assert_called_once_with(
        site_name=["google"],
        search_term="python developer",
        location="Munich",
        results_wanted=10,
        hours_old=72,
        verbose=0,
    )


# ── StepstoneScraper ──────────────────────────────────────────────────────────

from unittest.mock import AsyncMock


def _make_async_text_el(text: str):
    el = AsyncMock()
    el.inner_text.return_value = text
    return el


def _make_async_link_el(href: str):
    el = AsyncMock()
    el.get_attribute.return_value = href
    return el


def test_stepstone_card_to_posting_maps_fields():
    import asyncio
    from app.services.providers.stepstone import _stepstone_card_to_posting

    card = AsyncMock()
    card.query_selector.side_effect = lambda sel: {
        '[data-at="job-item-title"]': _make_async_text_el("Python Engineer"),
        '[data-at="job-item-company-name"]': _make_async_text_el("TechCo GmbH"),
        '[data-at="job-item-location"]': _make_async_text_el("Munich, Germany"),
        'a[data-at="job-item-title"]': _make_async_link_el("/jobs/python-engineer-123"),
        'time[datetime]': None,
    }.get(sel)

    posting = asyncio.run(_stepstone_card_to_posting(card))

    assert posting.title == "Python Engineer"
    assert posting.company == "TechCo GmbH"
    assert posting.location == "Munich, Germany"
    assert posting.source == "stepstone"
    assert posting.url == "https://www.stepstone.de/jobs/python-engineer-123"


def test_stepstone_card_to_posting_handles_absolute_url():
    import asyncio
    from app.services.providers.stepstone import _stepstone_card_to_posting

    card = AsyncMock()
    card.query_selector.side_effect = lambda sel: {
        '[data-at="job-item-title"]': _make_async_text_el("Dev"),
        '[data-at="job-item-company-name"]': _make_async_text_el("Co"),
        '[data-at="job-item-location"]': _make_async_text_el("Munich"),
        'a[data-at="job-item-title"]': _make_async_link_el("https://www.stepstone.de/jobs/abc-123"),
        'time[datetime]': None,
    }.get(sel)

    posting = asyncio.run(_stepstone_card_to_posting(card))
    assert posting.url == "https://www.stepstone.de/jobs/abc-123"


# ── XingScraper ───────────────────────────────────────────────────────────────

def test_xing_card_to_posting_maps_fields():
    import asyncio
    from app.services.providers.xing import _xing_card_to_posting

    card = AsyncMock()
    card.query_selector.side_effect = lambda sel: {
        '[data-testid="job-listing-item-title"]': _make_async_text_el("Backend Dev"),
        '[data-testid="job-listing-item-company-name"]': _make_async_text_el("StartupAG"),
        '[data-testid="job-listing-item-location"]': _make_async_text_el("Munich"),
        'a[data-testid="job-listing-item-title-link"]': _make_async_link_el("https://www.xing.com/jobs/123"),
    }.get(sel)

    posting = asyncio.run(_xing_card_to_posting(card))

    assert posting.title == "Backend Dev"
    assert posting.company == "StartupAG"
    assert posting.source == "xing"
    assert posting.url == "https://www.xing.com/jobs/123"


# ── AutoSearchConfig.providers ────────────────────────────────────────────────

def test_auto_search_config_providers_default():
    from app.models.auto_search import AutoSearchConfig

    config = AutoSearchConfig()
    assert "linkedin" in config.providers
    assert "indeed" in config.providers
    assert "google" in config.providers
    assert "stepstone" in config.providers
    assert "xing" in config.providers


def test_auto_search_config_providers_json_roundtrip():
    from app.models.auto_search import AutoSearchConfig

    config = AutoSearchConfig(providers=["linkedin", "stepstone"])
    json_str = config.model_dump_json()
    loaded = AutoSearchConfig.model_validate_json(json_str)
    assert loaded.providers == ["linkedin", "stepstone"]


def test_auto_search_config_without_providers_field_uses_default():
    """Old JSON files without 'providers' key should load with defaults."""
    import json
    from app.models.auto_search import AutoSearchConfig

    old_json = json.dumps({
        "enabled": True,
        "interval_hours": 2,
        "location": "Munich",
        "page_size": 10,
        "entries": [],
    })
    config = AutoSearchConfig.model_validate_json(old_json)
    assert len(config.providers) == 5
