from datetime import datetime
from uuid import UUID

from app.models.auto_search import (
    AutoSearchConfig,
    JobStatus,
    JobStatusEntry,
    SavedJob,
    SavedJobWithStatus,
    SearchEntry,
    AutoSearchSummary,
    AutoSearchResultsPage,
)
from app.models.jobs import JobPosting, MatchScore


def _make_posting() -> JobPosting:
    return JobPosting(
        title="Backend Engineer",
        company="Acme",
        location="Berlin",
        description="We need a python dev",
        url="https://acme.com/jobs/1",
        source="mock",
    )


def _make_match(posting: JobPosting) -> MatchScore:
    return MatchScore(
        job_id=posting.id,
        score=82,
        keywords_found=["python"],
        keywords_missing=[],
        justification="Good match.",
    )


def test_search_entry_defaults():
    entry = SearchEntry(title="SWE", keywords=["python"])
    assert entry.active is True
    assert entry.custom is False
    assert len(entry.id) == 36  # uuid4


def test_auto_search_config_defaults():
    cfg = AutoSearchConfig()
    assert cfg.enabled is True
    assert cfg.interval_hours == 2
    assert cfg.page_size == 10
    assert cfg.entries == []


def test_job_status_enum_values():
    assert JobStatus.NONE == "NONE"
    assert JobStatus.NOT_INTERESTED == "NOT_INTERESTED"
    assert JobStatus.APPLIED == "APPLIED"
    assert JobStatus.INTERVIEWING == "INTERVIEWING"
    assert JobStatus.OFFER_RECEIVED == "OFFER_RECEIVED"


def test_saved_job_roundtrip():
    p = _make_posting()
    m = _make_match(p)
    now = datetime.now()
    job = SavedJob(
        posting=p,
        match=m,
        found_at=now,
        last_seen_at=now,
        found_via="SWE",
        run_id="run-1",
    )
    restored = SavedJob.model_validate_json(job.model_dump_json())
    assert restored.found_via == "SWE"
    assert isinstance(restored.posting.id, UUID)


def test_auto_search_summary_defaults():
    s = AutoSearchSummary(enabled=True)
    assert s.new_count == 0
    assert s.last_run_at is None
