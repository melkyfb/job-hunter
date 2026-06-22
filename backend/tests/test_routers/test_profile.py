from __future__ import annotations

import io
import json
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
                    metric="by 60%",
                    context="by migrating CI to GitHub Actions",
                )
            ],
        )
    ],
)


@pytest.fixture
def client_with_tmp_repo(tmp_path: Path):
    """TestClient wired to an isolated profile repository."""
    repo = ProfileRepository(
        path=tmp_path / "profile.json",
        partial_path=tmp_path / "profile_partial.json",
    )
    with patch("app.routers.profile._repo", repo):
        yield TestClient(app), repo


# ── GET /profile/ ─────────────────────────────────────────────────────────────

def test_get_profile_404_when_missing(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    resp = client.get("/profile/")
    assert resp.status_code == 404
    assert "Upload a resume" in resp.json()["detail"]


def test_get_profile_returns_saved_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.get("/profile/")
    assert resp.status_code == 200
    assert resp.json()["contact"]["full_name"] == "Ada Lovelace"


# ── PUT /profile/ ─────────────────────────────────────────────────────────────

def test_put_profile_persists_and_returns(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    payload = json.loads(_VALID_PROFILE.model_dump_json())
    resp = client.put("/profile/", json=payload)
    assert resp.status_code == 200
    assert repo.exists()
    assert repo.load().contact.email == "ada@example.com"


# ── DELETE /profile/ ─────────────────────────────────────────────────────────

def test_delete_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.delete("/profile/")
    assert resp.status_code == 204
    assert not repo.exists()


# ── POST /profile/ingest ──────────────────────────────────────────────────────

def test_ingest_rejects_unsupported_format(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    resp = client.post(
        "/profile/ingest",
        files={"file": ("resume.txt", b"some text", "text/plain")},
    )
    assert resp.status_code == 422


def test_ingest_completed_saves_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    mock_client = make_llm_mock(_VALID_PROFILE.model_dump_json())

    with patch("app.routers.profile._ingestion.run") as mock_run:
        from app.models.ingestion import IngestionResponse
        import uuid
        mock_run.return_value = IngestionResponse(
            ingestion_id=uuid.uuid4(),
            status=IngestionStatus.COMPLETED,
            profile=_VALID_PROFILE,
        )
        resp = client.post(
            "/profile/ingest",
            files={"file": ("resume.html", b"<p>Ada Lovelace</p>", "text/html")},
        )

    assert resp.status_code == 202
    data = resp.json()
    assert data["status"] == "completed"
    assert data["profile"]["contact"]["full_name"] == "Ada Lovelace"
    assert repo.exists()


def test_ingest_hitl_saves_partial_and_not_final(client_with_tmp_repo):
    client, repo = client_with_tmp_repo

    from app.models.ingestion import HITLField, HITLRequest, IngestionResponse
    import uuid

    hitl_id = uuid.uuid4()
    hitl_response = IngestionResponse(
        ingestion_id=hitl_id,
        status=IngestionStatus.HITL_REQUIRED,
        hitl_request=HITLRequest(
            ingestion_id=hitl_id,
            partial_profile=_VALID_PROFILE,
            missing_fields=[
                HITLField(
                    field_path="work_experiences.0.achievements.0.metric",
                    llm_suggestion="How much did deploy time reduce?",
                    reason="No metric found.",
                )
            ],
        ),
    )

    with patch("app.routers.profile.extract_text", return_value="Ada resume text"), \
         patch("app.routers.profile._ingestion.run", return_value=hitl_response):
        resp = client.post(
            "/profile/ingest",
            files={"file": ("resume.pdf", b"%PDF-1.4", "application/pdf")},
        )

    assert resp.status_code == 202
    assert resp.json()["status"] == "hitl_required"
    assert not repo.exists()         # final profile NOT saved yet
    assert repo.partial_exists()     # partial IS saved so resolve can find it


def test_resolve_hitl_completes_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo

    # Pre-seed the partial profile (simulates what /ingest just saved)
    repo.save_partial(_VALID_PROFILE)

    import json, uuid
    resolution = {
        "ingestion_id": str(uuid.uuid4()),
        "resolved_fields": {
            "work_experiences.0.achievements.0.metric": "by 60%, from 30 to 12 minutes"
        },
    }
    resp = client.post("/profile/ingest/resolve", json=resolution)

    assert resp.status_code == 200
    assert resp.json()["status"] == "completed"
    assert repo.exists()          # final profile saved
    assert not repo.partial_exists()  # partial cleaned up
