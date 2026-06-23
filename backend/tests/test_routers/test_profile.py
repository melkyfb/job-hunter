from __future__ import annotations

import io
import json
import uuid
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.ingestion import IngestionStatus
from app.models.profile import (
    ContactInfo,
    ProfileMaster,
    WorkExperience,
    XYZExperience,
)
from app.repositories.profile_repository import ProfileRepository
from app.services.prompt_defaults import DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT

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
                    metric="by 60%",
                    context="by migrating CI to GitHub Actions",
                )
            ],
        )
    ],
)


@pytest.fixture
def client_with_tmp_repo(tmp_path: Path):
    repo = ProfileRepository(
        path=tmp_path / "profile.json",
        partial_path=tmp_path / "profile_partial.json",
    )
    with patch("app.routers.profile._repo", repo):
        yield TestClient(app), repo


def test_get_profile_404_when_missing(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    resp = client.get("/profile/")
    assert resp.status_code == 404


def test_get_profile_returns_saved_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.get("/profile/")
    assert resp.status_code == 200
    assert resp.json()["contact"]["full_name"] == "Ada Lovelace"


def test_put_profile_persists_and_returns(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    payload = json.loads(_VALID_PROFILE.model_dump_json())
    resp = client.put("/profile/", json=payload)
    assert resp.status_code == 200
    assert repo.exists()


def test_delete_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.delete("/profile/")
    assert resp.status_code == 204
    assert not repo.exists()


def test_ingest_rejects_too_many_files(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    files = [("files", (f"f{i}.txt", b"content", "text/plain")) for i in range(21)]
    resp = client.post("/profile/ingest", files=files)
    assert resp.status_code == 422
    assert "Maximum 20" in resp.json()["detail"]


def test_ingest_accepted_returns_job_id(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    with patch("app.routers.profile._ingestion.run") as mock_run, \
         patch("app.services.suggestions.generate_suggestions", return_value=[]), \
         patch("app.services.file_processor.compile_reference_text", return_value="Relevant content"):
        from app.models.ingestion import IngestionResponse
        mock_run.return_value = IngestionResponse(
            ingestion_id=uuid.uuid4(),
            status=IngestionStatus.COMPLETED,
            profile=_VALID_PROFILE,
        )
        resp = client.post(
            "/profile/ingest",
            files=[("files", ("resume.pdf", b"%PDF-1.4", "application/pdf"))],
        )
    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_patch_prompts_updates_cv_prompt(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.patch("/profile/prompts", json={"cv_prompt": "My custom prompt {JOB_DESCRIPTION}"})
    assert resp.status_code == 200
    assert repo.load().cv_prompt == "My custom prompt {JOB_DESCRIPTION}"


def test_patch_prompts_updates_cover_letter_prompt(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.patch("/profile/prompts", json={"cover_letter_prompt": "Custom CL {JOB_DESCRIPTION}"})
    assert resp.status_code == 200
    assert repo.load().cover_letter_prompt == "Custom CL {JOB_DESCRIPTION}"


def test_patch_prompts_partial_update(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    original_cl = repo.load().cover_letter_prompt
    client.patch("/profile/prompts", json={"cv_prompt": "New CV"})
    updated = repo.load()
    assert updated.cv_prompt == "New CV"
    assert updated.cover_letter_prompt == original_cl  # unchanged


def test_patch_prompts_404_when_no_profile(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    resp = client.patch("/profile/prompts", json={"cv_prompt": "x"})
    assert resp.status_code == 404


def test_resolve_hitl_completes_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save_partial(_VALID_PROFILE)
    resolution = {
        "ingestion_id": str(uuid.uuid4()),
        "resolved_fields": {
            "work_experiences.0.achievements.0.metric": "by 60%, from 30 to 12 minutes"
        },
    }
    with patch("app.services.suggestions.generate_suggestions", return_value=[]):
        resp = client.post("/profile/ingest/resolve", json=resolution)
    assert resp.status_code == 202
