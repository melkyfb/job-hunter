from __future__ import annotations

from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.models.auto_search import AutoSearchConfig, AutoSearchResultsPage, AutoSearchSummary, JobStatus, SearchEntry

client = TestClient(app)

_DEFAULT_CONFIG = AutoSearchConfig(
    enabled=True,
    interval_hours=2,
    location="Berlin",
    entries=[SearchEntry(title="SWE", keywords=["python"])],
)

_DEFAULT_SUMMARY = AutoSearchSummary(enabled=True, new_count=3, total_count=10)

_EMPTY_PAGE = AutoSearchResultsPage(jobs=[], total=0, page=1, page_size=10, total_pages=1)


def test_get_config():
    with patch("app.routers.auto_search.load_config", return_value=_DEFAULT_CONFIG):
        r = client.get("/auto-search/config")
    assert r.status_code == 200
    assert r.json()["interval_hours"] == 2
    assert r.json()["entries"][0]["title"] == "SWE"


def test_put_config_saves_and_reschedules():
    new_cfg = _DEFAULT_CONFIG.model_copy(update={"interval_hours": 4})
    with (
        patch("app.routers.auto_search.save_config") as mock_save,
        patch("app.routers.auto_search.reschedule") as mock_reschedule,
        patch("app.routers.auto_search.load_config", return_value=_DEFAULT_CONFIG),
    ):
        r = client.put("/auto-search/config", json=new_cfg.model_dump())
    assert r.status_code == 200
    mock_save.assert_called_once()
    mock_reschedule.assert_called_once_with(4)


def test_get_summary():
    with patch("app.routers.auto_search.get_summary", return_value=_DEFAULT_SUMMARY):
        r = client.get("/auto-search/summary")
    assert r.status_code == 200
    assert r.json()["new_count"] == 3


def test_post_run_returns_job_id():
    with patch("app.routers.auto_search.trigger_now"):
        r = client.post("/auto-search/run")
    assert r.status_code == 202
    assert "job_id" in r.json()


def test_get_results():
    with patch("app.routers.auto_search.get_results_page", return_value=_EMPTY_PAGE):
        r = client.get("/auto-search/results?page=1&page_size=10&status_filter=NONE&sort=score")
    assert r.status_code == 200
    assert r.json()["total"] == 0


def test_mark_seen():
    with patch("app.routers.auto_search.mark_seen") as mock_seen:
        r = client.post("/auto-search/mark-seen")
    assert r.status_code == 204
    mock_seen.assert_called_once()


def test_patch_job_status():
    with patch("app.routers.auto_search.set_job_status") as mock_set:
        r = client.patch(
            "/auto-search/jobs/abc123/status",
            json={"status": "APPLIED", "notes": "sent via email"},
        )
    assert r.status_code == 200
    mock_set.assert_called_once_with("abc123", JobStatus.APPLIED, "sent via email")


def test_delete_cleanup():
    with patch("app.routers.auto_search.cleanup", return_value=5) as mock_clean:
        r = client.delete("/auto-search/cleanup?remove_not_interested=true")
    assert r.status_code == 200
    assert r.json()["removed"] == 5
