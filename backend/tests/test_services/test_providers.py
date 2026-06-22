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
