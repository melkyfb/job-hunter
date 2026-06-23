from __future__ import annotations

import json
from datetime import date
from unittest.mock import patch

import pytest

from app.models.ingestion import IngestionStatus
from app.models.profile import (
    ContactInfo,
    Language,
    ProfileMaster,
    Skill,
    SkillLevel,
    WorkExperience,
    XYZExperience,
)
from app.services.ingestion import IngestionService
from tests.conftest import make_llm_mock

_VALID_PROFILE = ProfileMaster(
    contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com"),
    work_experiences=[
        WorkExperience(
            company="TechCorp",
            role="Engineer",
            start_date=date(2020, 1, 1),
            is_current=True,
            achievements=[
                XYZExperience(
                    action="Reduced deploy time",
                    metric="by 60%, from 30 to 12 minutes",
                    context="by migrating CI to GitHub Actions",
                )
            ],
        )
    ],
)

_PROFILE_WITH_UNKNOWN_METRIC = ProfileMaster(
    contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com"),
    work_experiences=[
        WorkExperience(
            company="TechCorp",
            role="Engineer",
            start_date=date(2020, 1, 1),
            is_current=True,
            achievements=[
                XYZExperience(
                    action="Improved system performance",
                    metric="__UNKNOWN__",
                    context="by refactoring the database layer",
                )
            ],
        )
    ],
)


# ── Happy path ────────────────────────────────────────────────────────────────

def test_ingestion_completed_on_valid_llm_response():
    mock_client = make_llm_mock(_VALID_PROFILE.model_dump_json())
    with patch("app.services.ingestion.get_llm_client", return_value=mock_client):
        result = IngestionService().run("Ada Lovelace, Engineer at TechCorp")

    assert result.status == IngestionStatus.COMPLETED
    assert result.profile is not None
    assert result.profile.contact.full_name == "Ada Lovelace"
    assert result.hitl_request is None


# ── HITL detection ────────────────────────────────────────────────────────────

def test_ingestion_pauses_when_metric_is_unknown():
    mock_client = make_llm_mock(_PROFILE_WITH_UNKNOWN_METRIC.model_dump_json())
    with patch("app.services.ingestion.get_llm_client", return_value=mock_client):
        result = IngestionService().run("Ada Lovelace resume text")

    assert result.status == IngestionStatus.HITL_REQUIRED
    assert result.hitl_request is not None
    assert len(result.hitl_request.missing_fields) == 1
    field = result.hitl_request.missing_fields[0]
    assert "metric" in field.field_path
    assert result.profile is None


# ── Self-correction loop ──────────────────────────────────────────────────────

def test_ingestion_self_corrects_on_invalid_json():
    """First call returns garbage JSON, second call returns valid profile."""
    valid_json = _VALID_PROFILE.model_dump_json()

    call_count = 0

    def side_effect(**kwargs):
        nonlocal call_count
        call_count += 1
        mock = make_llm_mock("{invalid json!!!" if call_count == 1 else valid_json)
        return mock.chat.completions.create(**kwargs)

    mock_client = make_llm_mock(valid_json)
    mock_client.chat.completions.create.side_effect = side_effect

    with patch("app.services.ingestion.get_llm_client", return_value=mock_client):
        result = IngestionService().run("resume text")

    assert result.status == IngestionStatus.COMPLETED
    assert call_count == 2  # proved the retry happened


def test_ingestion_self_corrects_on_schema_violation():
    """First call omits required fields, second call returns valid profile."""
    bad_json = json.dumps({"contact": {"full_name": "Ada"}})  # missing email
    valid_json = _VALID_PROFILE.model_dump_json()

    responses = iter([bad_json, valid_json])

    mock_client = make_llm_mock(valid_json)
    mock_client.chat.completions.create.side_effect = (
        lambda **_: make_llm_mock(r).chat.completions.create() for r in responses
    )

    calls = iter([bad_json, valid_json])

    def side_effect(**kwargs):
        return make_llm_mock(next(calls)).chat.completions.create(**kwargs)

    mock_client.chat.completions.create.side_effect = side_effect

    with patch("app.services.ingestion.get_llm_client", return_value=mock_client):
        result = IngestionService().run("resume text")

    assert result.status == IngestionStatus.COMPLETED


# ── Max retries exhausted ─────────────────────────────────────────────────────

def test_ingestion_fails_after_max_retries():
    mock_client = make_llm_mock("not json at all")
    with patch("app.services.ingestion.get_llm_client", return_value=mock_client):
        result = IngestionService().run("resume text")

    assert result.status == IngestionStatus.FAILED
    assert result.error is not None
    assert "3 attempts" in result.error
    # LLM was called exactly max_retries times
    assert mock_client.chat.completions.create.call_count == 3
