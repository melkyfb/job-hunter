from __future__ import annotations

from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest

from app.models.jobs import JobPosting, MatchScore, RankedJob
from app.models.profile import (
    ContactInfo,
    ProfileMaster,
    Skill,
    SkillLevel,
    WorkExperience,
    XYZExperience,
)
from app.services.match_scoring import score_match
from app.services.job_search import MockProvider
from app.services.job_pipeline import run_pipeline
from tests.conftest import make_llm_mock


_PROFILE = ProfileMaster(
    contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com"),
    skills=[
        Skill(name="Python", level=SkillLevel.EXPERT),
        Skill(name="FastAPI", level=SkillLevel.ADVANCED),
    ],
    work_experiences=[
        WorkExperience(
            company="TechCorp",
            role="Senior Backend Engineer",
            start_date=date(2020, 1, 1),
            is_current=True,
            achievements=[
                XYZExperience(
                    action="Reduced API latency",
                    metric="by 40%",
                    context="by implementing Redis caching",
                )
            ],
            technologies=["Python", "FastAPI", "Redis", "PostgreSQL"],
        )
    ],
)

_JOB = JobPosting(
    id=uuid4(),
    title="Senior Python Engineer",
    company="Acme GmbH",
    location="Munich, Germany",
    description="Looking for Python expert with FastAPI and Redis experience.",
    url="https://example.com/job/1",
    source="mock",
)


# ── MockProvider ──────────────────────────────────────────────────────────────

def test_mock_provider_returns_jobs():
    provider = MockProvider()
    jobs = provider.search("Python", "Munich", max_results=3)
    assert len(jobs) == 3
    assert all(j.source == "mock" for j in jobs)
    assert all(j.title for j in jobs)


def test_mock_provider_respects_max_results():
    provider = MockProvider()
    assert len(MockProvider().search("x", "y", max_results=1)) == 1
    assert len(MockProvider().search("x", "y", max_results=10)) == 5  # only 5 mock jobs


# ── MatchScoringAgent ─────────────────────────────────────────────────────────

def test_score_match_returns_valid_score():
    match_json = MatchScore(
        job_id=_JOB.id,
        score=85,
        keywords_found=["Python", "FastAPI", "Redis"],
        keywords_missing=["Kubernetes"],
        justification="Strong Python and FastAPI match. Missing K8s experience.",
    ).model_dump_json()

    mock_client = make_llm_mock(match_json)
    with patch("app.services.match_scoring.get_llm_client", return_value=mock_client):
        result = score_match(_PROFILE, _JOB)

    assert result.score == 85
    assert "Python" in result.keywords_found
    assert "Kubernetes" in result.keywords_missing
    assert result.job_id == _JOB.id


def test_score_match_retries_on_bad_json():
    valid_json = MatchScore(
        job_id=_JOB.id,
        score=70,
        keywords_found=["Python"],
        keywords_missing=[],
        justification="Good match.",
    ).model_dump_json()

    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        return make_llm_mock("not json" if call_count == 1 else valid_json).chat.completions.create(**kwargs)

    mock_client = make_llm_mock(valid_json)
    mock_client.chat.completions.create.side_effect = side_effect

    with patch("app.services.match_scoring.get_llm_client", return_value=mock_client):
        result = score_match(_PROFILE, _JOB)

    assert result.score == 70
    assert call_count == 2


# ── Full pipeline ─────────────────────────────────────────────────────────────

def test_pipeline_returns_ranked_jobs():
    mock_score = MatchScore(
        job_id=uuid4(),
        score=80,
        keywords_found=["Python"],
        keywords_missing=[],
        justification="Good match.",
    )

    with patch("app.services.job_pipeline.get_search_provider") as mock_provider, \
         patch("app.services.job_pipeline.score_match", return_value=mock_score):
        mock_provider.return_value.search.return_value = [_JOB]
        results = run_pipeline(_PROFILE, "Python Engineer", "Munich", max_results=5)

    assert len(results) == 1
    assert results[0].match.score == 80
    assert results[0].posting.title == _JOB.title


def test_pipeline_filters_low_scores():
    low_score = MatchScore(
        job_id=uuid4(),
        score=20,  # below _MIN_SCORE=30
        keywords_found=[],
        keywords_missing=["Python"],
        justification="Poor match.",
    )

    with patch("app.services.job_pipeline.get_search_provider") as mock_provider, \
         patch("app.services.job_pipeline.score_match", return_value=low_score):
        mock_provider.return_value.search.return_value = [_JOB]
        results = run_pipeline(_PROFILE, "Python Engineer", "Munich")

    assert results == []


def test_pipeline_sorts_by_score_descending():
    job_a = _JOB.model_copy(update={"id": uuid4(), "title": "Job A"})
    job_b = _JOB.model_copy(update={"id": uuid4(), "title": "Job B"})

    scores = {job_a.id: 90, job_b.id: 60}

    def fake_score(profile, job):
        return MatchScore(
            job_id=job.id,
            score=scores[job.id],
            keywords_found=[],
            keywords_missing=[],
            justification="",
        )

    with patch("app.services.job_pipeline.get_search_provider") as mock_provider, \
         patch("app.services.job_pipeline.score_match", side_effect=fake_score):
        mock_provider.return_value.search.return_value = [job_b, job_a]  # unsorted
        results = run_pipeline(_PROFILE, "Engineer", "Munich")

    assert results[0].posting.title == "Job A"  # score 90 first
    assert results[1].posting.title == "Job B"  # score 60 second


def test_pipeline_survives_partial_scoring_failure():
    """Pipeline should return successfully scored jobs even if some fail."""
    job_ok = _JOB.model_copy(update={"id": uuid4(), "title": "Good Job"})
    job_fail = _JOB.model_copy(update={"id": uuid4(), "title": "Broken Job"})

    good_score = MatchScore(
        job_id=job_ok.id, score=75,
        keywords_found=["Python"], keywords_missing=[], justification="ok",
    )

    def fake_score(profile, job):
        if job.id == job_fail.id:
            raise ValueError("LLM failed")
        return good_score

    with patch("app.services.job_pipeline.get_search_provider") as mock_provider, \
         patch("app.services.job_pipeline.score_match", side_effect=fake_score):
        mock_provider.return_value.search.return_value = [job_ok, job_fail]
        results = run_pipeline(_PROFILE, "Engineer", "Munich")

    assert len(results) == 1
    assert results[0].posting.title == "Good Job"
