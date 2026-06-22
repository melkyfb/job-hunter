from __future__ import annotations

import json
import tempfile
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.profile import (
    ContactInfo,
    Language,
    ProfileMaster,
    Skill,
    SkillLevel,
    WorkExperience,
    XYZExperience,
)
from app.repositories.profile_repository import ProfileRepository


# ── HTTP client ───────────────────────────────────────────────────────────────

@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


# ── Isolated profile repository ───────────────────────────────────────────────

@pytest.fixture
def tmp_profile_path(tmp_path: Path) -> Path:
    return tmp_path / "profile_master.json"


@pytest.fixture
def repo(tmp_profile_path: Path) -> ProfileRepository:
    return ProfileRepository(path=tmp_profile_path)


# ── Sample domain objects ─────────────────────────────────────────────────────

@pytest.fixture
def sample_profile() -> ProfileMaster:
    return ProfileMaster(
        contact=ContactInfo(
            full_name="Ada Lovelace",
            email="ada@example.com",
            location="Munich, Germany",
            linkedin_url="https://linkedin.com/in/ada",
        ),
        summary="Backend engineer with 5 years in Python.",
        work_experiences=[
            WorkExperience(
                company="TechCorp GmbH",
                role="Senior Backend Engineer",
                start_date=date(2021, 3, 1),
                is_current=True,
                achievements=[
                    XYZExperience(
                        action="Reduced API response time",
                        metric="by 40%, from 800ms to 480ms",
                        context="by implementing a Redis caching layer",
                    ),
                ],
                technologies=["Python", "FastAPI", "Redis"],
            )
        ],
        skills=[Skill(name="Python", level=SkillLevel.EXPERT, years_of_experience=6)],
        languages=[Language(name="Portuguese", proficiency="Native")],
    )


@pytest.fixture
def sample_profile_json(sample_profile: ProfileMaster) -> str:
    return sample_profile.model_dump_json()


# ── LLM mock factory ──────────────────────────────────────────────────────────

def make_llm_mock(response_json: str) -> MagicMock:
    """Build a mock OpenAI client that returns a fixed JSON string."""
    message = MagicMock()
    message.content = response_json

    choice = MagicMock()
    choice.message = message

    completion = MagicMock()
    completion.choices = [choice]

    client = MagicMock()
    client.chat.completions.create.return_value = completion
    return client
