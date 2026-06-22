from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

import pytest

from app.models.jobs import JobPosting, MatchScore
from app.models.profile import (
    ContactInfo,
    Education,
    Language,
    ProfileMaster,
    Skill,
    SkillLevel,
    WorkExperience,
    XYZExperience,
)
from app.services.resume_renderer import render_resume_pdf
from app.services.application import generate_master_resume, generate_application_package
from tests.conftest import make_llm_mock


_PROFILE = ProfileMaster(
    contact=ContactInfo(
        full_name="Ada Lovelace",
        email="ada@example.com",
        location="Munich, Germany",
        linkedin_url="https://linkedin.com/in/ada",
    ),
    summary="Backend engineer with 5 years in Python and distributed systems.",
    work_experiences=[
        WorkExperience(
            company="TechCorp GmbH",
            role="Senior Backend Engineer",
            start_date=date(2021, 3, 1),
            end_date=date(2024, 1, 1),
            achievements=[
                XYZExperience(
                    action="Reduced API response time",
                    metric="by 40%, from 800ms to 480ms",
                    context="by implementing a Redis caching layer",
                ),
                XYZExperience(
                    action="Increased test coverage",
                    metric="from 42% to 87%",
                    context="by introducing pytest fixtures and contract testing",
                ),
            ],
            technologies=["Python", "FastAPI", "Redis", "PostgreSQL"],
        )
    ],
    education=[
        Education(
            institution="TU Munich",
            degree="M.Sc.",
            field_of_study="Computer Science",
            start_date=date(2018, 10, 1),
            end_date=date(2020, 9, 30),
        )
    ],
    skills=[
        Skill(name="Python", level=SkillLevel.EXPERT, years_of_experience=6),
        Skill(name="FastAPI", level=SkillLevel.ADVANCED),
        Skill(name="Docker", level=SkillLevel.INTERMEDIATE),
    ],
    languages=[
        Language(name="Portuguese", proficiency="Native"),
        Language(name="English", proficiency="C1"),
        Language(name="German", proficiency="B2"),
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

_MATCH = MatchScore(
    job_id=_JOB.id,
    score=85,
    keywords_found=["Python", "FastAPI", "Redis"],
    keywords_missing=["Kubernetes"],
    justification="Strong match on Python and FastAPI stack.",
)


# ── PDF rendering ─────────────────────────────────────────────────────────────

def test_render_resume_pdf_returns_bytes():
    pdf = render_resume_pdf(_PROFILE)
    assert isinstance(pdf, bytes)
    assert pdf[:4] == b"%PDF"  # valid PDF magic bytes


def test_render_resume_pdf_with_highlights():
    pdf = render_resume_pdf(_PROFILE, highlight_keywords=["Python", "FastAPI"])
    assert isinstance(pdf, bytes)
    assert len(pdf) > 1000


def test_master_resume_generates_pdf():
    pdf = generate_master_resume(_PROFILE)
    assert pdf[:4] == b"%PDF"


# ── Cover letter ──────────────────────────────────────────────────────────────

def test_cover_letter_uses_two_llm_turns():
    """CoT requires exactly 2 completions: reasoning turn + writing turn."""
    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        text = "Step 1: They need Python. Step 2: Use Redis achievement. READY TO WRITE" \
               if call_count == 1 else \
               "Dear Acme team,\n\nI reduced API response time by 40%...\n\nBest,\nAda Lovelace"
        return make_llm_mock(text).chat.completions.create(**kwargs)

    mock_client = make_llm_mock("placeholder")
    mock_client.chat.completions.create.side_effect = side_effect

    with patch("app.services.cover_letter.get_llm_client", return_value=mock_client):
        from app.services.cover_letter import generate_cover_letter
        result = generate_cover_letter(_PROFILE, _JOB)

    assert call_count == 2
    assert "Ada Lovelace" in result


# ── Full package ──────────────────────────────────────────────────────────────

def test_generate_application_package_structure():
    cover_text = "Dear Acme team,\n\nI am a great fit.\n\nBest,\nAda Lovelace"

    def side_effect(**kwargs):
        return make_llm_mock(cover_text).chat.completions.create(**kwargs)

    mock_client = make_llm_mock(cover_text)
    mock_client.chat.completions.create.side_effect = side_effect

    with patch("app.services.cover_letter.get_llm_client", return_value=mock_client):
        package = generate_application_package(_PROFILE, _JOB, _MATCH)

    assert package["job_id"] == _JOB.id
    assert package["cover_letter_text"] == cover_text
    # Both PDFs should be non-empty base64
    import base64
    resume_bytes = base64.b64decode(package["resume_pdf_base64"])
    letter_bytes = base64.b64decode(package["cover_letter_pdf_base64"])
    assert resume_bytes[:4] == b"%PDF"
    assert letter_bytes[:4] == b"%PDF"
