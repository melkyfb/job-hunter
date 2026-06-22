from __future__ import annotations

import time
from unittest.mock import patch

import uuid
from fastapi.testclient import TestClient

from app.main import app
from app.models.design import DesignVersion
from app.models.ingestion import HITLResolution, IngestionResponse, IngestionStatus
from app.models.profile import ContactInfo, ProfileMaster

client = TestClient(app)

_PROFILE = ProfileMaster(contact=ContactInfo(full_name="Test User", email="t@t.com"))

_DUMMY_DESIGNS = [
    DesignVersion(id=f"d{i}", name=f"{i}. Design", prompt="p", type="resume", html_template="<html><head><meta charset='UTF-8'></head><body></body></html>", is_default=(i == 1))
    for i in range(1, 4)
]

_TEST_UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def _make_ingest_result(profile: ProfileMaster) -> IngestionResponse:
    return IngestionResponse(
        ingestion_id=_TEST_UUID,
        status=IngestionStatus.COMPLETED,
        profile=profile,
    )


def test_ingest_attaches_designs_to_profile():
    """After ingest completes, profile.design_versions contains seeded templates."""
    saved_profiles: list[ProfileMaster] = []

    def fake_save(p: ProfileMaster) -> None:
        saved_profiles.append(p.model_copy(deep=True))

    with (
        patch("app.routers.profile._repo.delete_partial"),
        patch("app.routers.profile._repo.save", side_effect=fake_save),
        patch("app.routers.profile.extract_text", return_value="resume text"),
        patch(
            "app.routers.profile._ingestion.run",
            return_value=_make_ingest_result(_PROFILE),
        ),
        patch("app.routers.profile.generate_suggestions", return_value=[]),
        patch(
            "app.routers.profile.seed_default_designs",
            return_value=_DUMMY_DESIGNS,
        ),
    ):
        r = client.post("/profile/ingest", files={"file": ("cv.pdf", b"%PDF-1", "application/pdf")})
        assert r.status_code == 202
        job_id = r.json()["job_id"]

        # Poll until done
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)

    assert status["status"] == "completed"
    # The saved profile should contain designs
    last_saved = saved_profiles[-1]
    assert len(last_saved.design_versions) == 3
    assert last_saved.active_resume_design_id == "d1"


def test_ingest_completes_even_if_seed_returns_empty():
    """Ingest succeeds when seed_default_designs returns [] (all templates failed)."""
    with (
        patch("app.routers.profile._repo.delete_partial"),
        patch("app.routers.profile._repo.save"),
        patch("app.routers.profile.extract_text", return_value="resume text"),
        patch("app.routers.profile._ingestion.run", return_value=_make_ingest_result(_PROFILE)),
        patch("app.routers.profile.generate_suggestions", return_value=[]),
        patch("app.routers.profile.seed_default_designs", return_value=[]),
    ):
        r = client.post("/profile/ingest", files={"file": ("cv.pdf", b"%PDF-1", "application/pdf")})
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)
    assert status["status"] == "completed"


def test_ingest_hitl_does_not_seed_designs():
    """HITL path: templates are not generated (seed not called)."""
    from app.models.ingestion import HITLField, HITLRequest
    hitl_result = IngestionResponse(
        ingestion_id=_TEST_UUID,
        status=IngestionStatus.HITL_REQUIRED,
        hitl_request=HITLRequest(
            ingestion_id=_TEST_UUID,
            partial_profile=_PROFILE,
            missing_fields=[HITLField(field_path="x", reason="missing")],
            message="Review needed",
        ),
    )
    seed_calls: list = []
    with (
        patch("app.routers.profile.extract_text", return_value="resume text"),
        patch("app.routers.profile._ingestion.run", return_value=hitl_result),
        patch("app.routers.profile._repo.save_partial"),
        patch("app.routers.profile.seed_default_designs", side_effect=lambda **kw: seed_calls.append(1) or []),
    ):
        r = client.post("/profile/ingest", files={"file": ("cv.pdf", b"%PDF-1", "application/pdf")})
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)
    assert status["status"] == "hitl_required"
    assert seed_calls == [], "seed must not be called on HITL path"


def test_resolve_attaches_designs():
    """After HITL resolve, profile contains seeded templates."""
    resolution = HITLResolution(ingestion_id=_TEST_UUID, resolved_fields={})
    saved: list[ProfileMaster] = []

    with (
        patch("app.routers.profile._repo.partial_exists", return_value=True),
        patch("app.routers.profile._repo.load_partial", return_value=_PROFILE),
        patch("app.routers.profile._repo.delete_partial"),
        patch("app.routers.profile._repo.save", side_effect=lambda p: saved.append(p.model_copy(deep=True))),
        patch("app.routers.profile.generate_suggestions", return_value=[]),
        patch("app.routers.profile.seed_default_designs", return_value=_DUMMY_DESIGNS),
    ):
        r = client.post("/profile/ingest/resolve", json=resolution.model_dump(mode="json"))
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)

    assert status["status"] == "completed"
    assert len(saved[-1].design_versions) == 3
    assert saved[-1].active_resume_design_id == "d1"
