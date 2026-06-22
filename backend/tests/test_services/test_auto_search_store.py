from __future__ import annotations

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.models.jobs import JobPosting, MatchScore, RankedJob
from app.models.auto_search import AutoSearchConfig, JobStatus, SearchEntry


def _make_ranked_job(url: str = "https://acme.com/1", score: int = 80) -> RankedJob:
    posting = JobPosting(
        title="SWE", company="Acme", location="Berlin",
        description="desc", url=url, source="mock",
    )
    match = MatchScore(
        job_id=posting.id, score=score,
        keywords_found=["python"], keywords_missing=[],
        justification="ok",
    )
    return RankedJob(posting=posting, match=match)


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """Patch the store's storage dir to a temp directory."""
    import app.services.auto_search_store as s
    monkeypatch.setattr(s, "_STORAGE_DIR", tmp_path)
    monkeypatch.setattr(s, "_CONFIG_PATH", tmp_path / "auto_search_config.json")
    monkeypatch.setattr(s, "_RESULTS_PATH", tmp_path / "auto_search_results.json")
    monkeypatch.setattr(s, "_STATUS_PATH", tmp_path / "job_status.json")
    return s


def test_load_config_creates_default_when_missing(store):
    cfg = store.load_config()
    assert isinstance(cfg, AutoSearchConfig)
    assert cfg.enabled is True
    assert cfg.entries == []  # no profile to pull from in test env


def test_save_and_load_config(store):
    cfg = AutoSearchConfig(
        enabled=False,
        interval_hours=4,
        entries=[SearchEntry(title="SWE", keywords=["python"])],
    )
    store.save_config(cfg)
    loaded = store.load_config()
    assert loaded.enabled is False
    assert loaded.interval_hours == 4
    assert loaded.entries[0].title == "SWE"


def test_upsert_jobs_returns_new_count(store):
    jobs = [_make_ranked_job("https://a.com/1"), _make_ranked_job("https://a.com/2")]
    count = store.upsert_jobs(jobs, run_id="r1", found_via="SWE")
    assert count == 2


def test_upsert_jobs_deduplicates(store):
    job = _make_ranked_job("https://a.com/1")
    store.upsert_jobs([job], run_id="r1", found_via="SWE")
    count = store.upsert_jobs([job], run_id="r2", found_via="SWE")
    assert count == 0  # already seen


def test_upsert_preserves_found_at(store):
    job = _make_ranked_job("https://a.com/1")
    store.upsert_jobs([job], run_id="r1", found_via="SWE")
    data = json.loads((store._RESULTS_PATH).read_text())
    url_hash = store.url_to_hash("https://a.com/1")
    first_found = data["jobs"][url_hash]["found_at"]

    import time; time.sleep(0.01)
    store.upsert_jobs([job], run_id="r2", found_via="SWE")
    data2 = json.loads((store._RESULTS_PATH).read_text())
    assert data2["jobs"][url_hash]["found_at"] == first_found  # unchanged


def test_get_results_page_pagination(store):
    for i in range(15):
        store.upsert_jobs([_make_ranked_job(f"https://a.com/{i}")], run_id="r", found_via="SWE")
    page = store.get_results_page(page=1, page_size=10, status_filter=["NONE"], sort="score")
    assert len(page.jobs) == 10
    assert page.total == 15
    assert page.total_pages == 2

    page2 = store.get_results_page(page=2, page_size=10, status_filter=["NONE"], sort="score")
    assert len(page2.jobs) == 5


def test_set_job_status(store):
    job = _make_ranked_job("https://a.com/1")
    store.upsert_jobs([job], run_id="r", found_via="SWE")
    url_hash = store.url_to_hash("https://a.com/1")
    store.set_job_status(url_hash, JobStatus.APPLIED, notes="sent via email")
    page = store.get_results_page(1, 10, ["APPLIED"], "score")
    assert len(page.jobs) == 1
    assert page.jobs[0].notes == "sent via email"


def test_get_results_page_filters_by_status(store):
    store.upsert_jobs([_make_ranked_job("https://a.com/1")], run_id="r", found_via="SWE")
    store.upsert_jobs([_make_ranked_job("https://a.com/2")], run_id="r", found_via="SWE")
    url_hash = store.url_to_hash("https://a.com/1")
    store.set_job_status(url_hash, JobStatus.NOT_INTERESTED, notes=None)
    none_page = store.get_results_page(1, 10, ["NONE"], "score")
    assert len(none_page.jobs) == 1
    ni_page = store.get_results_page(1, 10, ["NOT_INTERESTED"], "score")
    assert len(ni_page.jobs) == 1


def test_mark_seen_zeros_new_count(store):
    store.upsert_jobs([_make_ranked_job("https://a.com/1")], run_id="r", found_via="SWE")
    summary = store.get_summary()
    assert summary.new_count == 1
    store.mark_seen()
    assert store.get_summary().new_count == 0


def test_cleanup_removes_old_jobs(store):
    store.upsert_jobs([_make_ranked_job("https://a.com/old")], run_id="r", found_via="SWE")
    cutoff = datetime.now() + timedelta(seconds=1)
    removed = store.cleanup(before_date=cutoff, remove_not_interested=False, remove_unavailable=False)
    assert removed == 1
    page = store.get_results_page(1, 10, ["NONE"], "score")
    assert len(page.jobs) == 0


def test_cleanup_removes_not_interested(store):
    store.upsert_jobs([_make_ranked_job("https://a.com/1")], run_id="r", found_via="SWE")
    url_hash = store.url_to_hash("https://a.com/1")
    store.set_job_status(url_hash, JobStatus.NOT_INTERESTED, notes=None)
    removed = store.cleanup(before_date=None, remove_not_interested=True, remove_unavailable=False)
    assert removed == 1
