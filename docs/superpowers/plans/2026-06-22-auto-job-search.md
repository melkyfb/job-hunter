# Auto Busca de Vagas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a background scheduler that searches for compatible jobs every N hours, persists results locally, tracks a job application pipeline, and presents a paginated/filterable UI with a new-jobs badge on the profile page.

**Architecture:** APScheduler `BackgroundScheduler` runs `run_pipeline()` for each active search entry every N hours; results are deduped by URL hash and persisted in `~/.job_hunter/auto_search_results.json` + `~/.job_hunter/job_status.json`; a FastAPI lifespan event starts/stops the scheduler; the frontend polls a lightweight summary endpoint every 60 s and shows a badge; `AutoSearchPage` is fully redesigned with 3 tabs (new / pipeline / not-interested), pagination, and per-card status menus.

**Tech Stack:** Python 3.12 + FastAPI + Pydantic v2 + APScheduler 3.x, React + TypeScript (`erasableSyntaxOnly: true`), Vite, CSS variables

## Global Constraints

- Python 3.12, Pydantic v2 — `model.model_dump()` / `model.model_dump_json()`, never `model.dict()`
- `from __future__ import annotations` at the top of every new Python file
- TypeScript `erasableSyntaxOnly: true` — no parameter properties in class constructors
- All frontend UI colours via CSS variables (`var(--accent)`, `var(--border)`, `var(--bg)`, `var(--text)`, `var(--text-h)`); `#ef4444` accepted for error/danger red
- APScheduler version: `APScheduler>=3.10,<4` — API differs significantly in v4
- Storage dir: `Path.home() / ".job_hunter"` — follow pattern from `profile_repository.py`
- Async job pattern for manual run: create job in `app.services.job_store`, run in `threading.Thread(daemon=True)`, poll via existing `GET /profile/ingest/{job_id}`
- No breaking changes to existing `AutoSearchPage` import path in `App.tsx`

---

## File Map

**New backend files:**
- `backend/app/models/auto_search.py` — all Pydantic models for this feature
- `backend/app/services/auto_search_store.py` — CRUD for the 3 JSON storage files
- `backend/app/services/auto_search_scheduler.py` — APScheduler wrapper
- `backend/app/routers/auto_search.py` — 8 REST endpoints

**Modified backend files:**
- `backend/requirements.txt` — add `APScheduler>=3.10,<4`
- `backend/app/main.py` — add lifespan handler + register `auto_search` router

**New frontend files:**
- `frontend/src/components/AutoSearchConfig.tsx` — collapsible config panel
- `frontend/src/components/JobStatusMenu.tsx` — per-card `⋮` dropdown

**Modified frontend files:**
- `frontend/src/api/client.ts` — new TS types + 8 new API functions
- `frontend/src/pages/AutoSearchPage.tsx` — full redesign (3 tabs, pagination, status)
- `frontend/src/pages/ProfilePage.tsx` — badge on Auto Search button
- `frontend/src/App.tsx` — poll summary every 60 s, pass badge count

---

## Task 1: Data models + APScheduler dependency

**Files:**
- Create: `backend/app/models/auto_search.py`
- Modify: `backend/requirements.txt`
- Test: `backend/tests/test_models/test_auto_search.py`

**Interfaces:**
- Produces: `SearchEntry`, `AutoSearchConfig`, `JobStatus`, `JobStatusEntry`, `SavedJob`, `SavedJobWithStatus`, `AutoSearchSummary`, `AutoSearchResultsPage` — imported by Tasks 2, 3, 4

- [ ] **Step 1: Add APScheduler to requirements.txt**

Append to `backend/requirements.txt`:
```
APScheduler>=3.10,<4
```

- [ ] **Step 2: Write the failing tests**

Create `backend/tests/test_models/test_auto_search.py`:

```python
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
```

- [ ] **Step 3: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_models/test_auto_search.py -v
```
Expected: `ImportError: cannot import name 'SearchEntry' from 'app.models.auto_search'`

- [ ] **Step 4: Create `backend/app/models/auto_search.py`**

```python
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Optional
from uuid import uuid4

from pydantic import BaseModel, Field

from app.models.jobs import JobPosting, MatchScore


class SearchEntry(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    title: str
    keywords: list[str]
    active: bool = True
    custom: bool = False


class AutoSearchConfig(BaseModel):
    enabled: bool = True
    interval_hours: int = Field(default=2, ge=1, le=168)
    location: str = "Munich, Germany"
    page_size: int = Field(default=10, ge=5, le=50)
    entries: list[SearchEntry] = Field(default_factory=list)


class JobStatus(str, Enum):
    NONE = "NONE"
    NOT_INTERESTED = "NOT_INTERESTED"
    APPLIED = "APPLIED"
    INTERVIEWING = "INTERVIEWING"
    OFFER_RECEIVED = "OFFER_RECEIVED"


class JobStatusEntry(BaseModel):
    status: JobStatus = JobStatus.NONE
    updated_at: datetime = Field(default_factory=datetime.now)
    notes: Optional[str] = None


class SavedJob(BaseModel):
    posting: JobPosting
    match: MatchScore
    found_at: datetime
    last_seen_at: datetime
    found_via: str
    run_id: str


class SavedJobWithStatus(BaseModel):
    url_hash: str
    posting: JobPosting
    match: MatchScore
    found_at: datetime
    last_seen_at: datetime
    found_via: str
    status: JobStatus = JobStatus.NONE
    notes: Optional[str] = None


class AutoSearchSummary(BaseModel):
    enabled: bool
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    new_count: int = 0
    total_count: int = 0


class AutoSearchResultsPage(BaseModel):
    jobs: list[SavedJobWithStatus]
    total: int
    page: int
    page_size: int
    total_pages: int
```

- [ ] **Step 5: Install APScheduler locally**

```
cd backend && pip install "APScheduler>=3.10,<4"
```

- [ ] **Step 6: Run tests to verify they pass**

```
cd backend && python -m pytest tests/test_models/test_auto_search.py -v
```
Expected: 5 PASSED

- [ ] **Step 7: Commit**

```
git add backend/app/models/auto_search.py backend/requirements.txt backend/tests/test_models/test_auto_search.py
git commit -m "feat: add auto-search data models and APScheduler dependency"
```

---

## Task 2: `auto_search_store.py` — persistent storage CRUD

**Files:**
- Create: `backend/app/services/auto_search_store.py`
- Test: `backend/tests/test_services/test_auto_search_store.py`

**Interfaces:**
- Consumes: `AutoSearchConfig`, `SavedJob`, `SavedJobWithStatus`, `JobStatus`, `JobStatusEntry`, `AutoSearchSummary`, `AutoSearchResultsPage` (Task 1); `RankedJob` from `app.models.jobs`
- Produces:
  - `load_config() -> AutoSearchConfig`
  - `save_config(config: AutoSearchConfig) -> None`
  - `upsert_jobs(jobs: list[RankedJob], run_id: str, found_via: str) -> int` (returns new_jobs count)
  - `get_results_page(page: int, page_size: int, status_filter: list[str], sort: str) -> AutoSearchResultsPage`
  - `get_summary() -> AutoSearchSummary`
  - `set_job_status(url_hash: str, status: JobStatus, notes: str | None) -> None`
  - `mark_seen() -> None`
  - `update_run_times(last_run_at: datetime, next_run_at: datetime) -> None`
  - `cleanup(before_date: datetime | None, remove_not_interested: bool, remove_unavailable: bool) -> int`
  - `url_to_hash(url: str) -> str`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_services/test_auto_search_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_services/test_auto_search_store.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `backend/app/services/auto_search_store.py`**

```python
from __future__ import annotations

import hashlib
import json
import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

from app.models.auto_search import (
    AutoSearchConfig,
    AutoSearchResultsPage,
    AutoSearchSummary,
    JobStatus,
    JobStatusEntry,
    SavedJob,
    SavedJobWithStatus,
)
from app.models.jobs import RankedJob

logger = logging.getLogger(__name__)

_STORAGE_DIR = Path.home() / ".job_hunter"
_CONFIG_PATH = _STORAGE_DIR / "auto_search_config.json"
_RESULTS_PATH = _STORAGE_DIR / "auto_search_results.json"
_STATUS_PATH = _STORAGE_DIR / "job_status.json"

_lock = threading.Lock()


# ── URL hashing ──────────────────────────────────────────────────────────────

def url_to_hash(url: str) -> str:
    return hashlib.sha256(url.strip().lower().encode()).hexdigest()[:16]


# ── Config ────────────────────────────────────────────────────────────────────

def load_config() -> AutoSearchConfig:
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    if _CONFIG_PATH.exists():
        try:
            return AutoSearchConfig.model_validate_json(_CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning("Config read error: %s — using defaults", exc)

    # First run: seed from profile suggestions if available
    entries = []
    try:
        from app.models.auto_search import SearchEntry
        from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
        profile = ProfileRepository().load()
        entries = [
            SearchEntry(title=s.title, keywords=s.keywords, custom=False)
            for s in profile.job_suggestions
        ]
    except Exception:
        pass

    cfg = AutoSearchConfig(entries=entries)
    save_config(cfg)
    return cfg


def save_config(config: AutoSearchConfig) -> None:
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_PATH.write_text(config.model_dump_json(indent=2), encoding="utf-8")


# ── Results storage helpers ───────────────────────────────────────────────────

def _load_raw() -> dict:
    if not _RESULTS_PATH.exists():
        return {"last_run_at": None, "next_run_at": None, "new_count": 0, "jobs": {}}
    try:
        return json.loads(_RESULTS_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {"last_run_at": None, "next_run_at": None, "new_count": 0, "jobs": {}}


def _save_raw(data: dict) -> None:
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    _RESULTS_PATH.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def _load_statuses() -> dict[str, JobStatusEntry]:
    if not _STATUS_PATH.exists():
        return {}
    try:
        raw = json.loads(_STATUS_PATH.read_text(encoding="utf-8"))
        return {k: JobStatusEntry.model_validate(v) for k, v in raw.items()}
    except Exception:
        return {}


def _save_statuses(statuses: dict[str, JobStatusEntry]) -> None:
    _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    _STATUS_PATH.write_text(
        json.dumps({k: json.loads(v.model_dump_json()) for k, v in statuses.items()}, indent=2),
        encoding="utf-8",
    )


# ── Public API ────────────────────────────────────────────────────────────────

def upsert_jobs(jobs: list[RankedJob], run_id: str, found_via: str) -> int:
    """Insert new jobs, update last_seen_at for existing ones. Returns count of brand-new jobs."""
    with _lock:
        data = _load_raw()
        stored = data.setdefault("jobs", {})
        new_count = 0
        now = datetime.now().isoformat()

        for rj in jobs:
            h = url_to_hash(rj.posting.url)
            if h in stored:
                # Update last_seen_at and score (keep max)
                stored[h]["last_seen_at"] = now
                old_score = stored[h].get("match", {}).get("score", 0)
                new_score = rj.match.score
                if new_score > old_score:
                    stored[h]["match"] = json.loads(rj.match.model_dump_json())
            else:
                stored[h] = {
                    "posting": json.loads(rj.posting.model_dump_json()),
                    "match": json.loads(rj.match.model_dump_json()),
                    "found_at": now,
                    "last_seen_at": now,
                    "found_via": found_via,
                    "run_id": run_id,
                }
                data["new_count"] = data.get("new_count", 0) + 1
                new_count += 1

        _save_raw(data)
    return new_count


def get_results_page(
    page: int,
    page_size: int,
    status_filter: list[str],
    sort: str,
) -> AutoSearchResultsPage:
    with _lock:
        data = _load_raw()
        statuses = _load_statuses()

    jobs_raw = data.get("jobs", {})
    status_set = set(status_filter)

    # Build SavedJobWithStatus list
    results: list[SavedJobWithStatus] = []
    for url_hash, raw in jobs_raw.items():
        status_entry = statuses.get(url_hash)
        status = status_entry.status if status_entry else JobStatus.NONE
        if status.value not in status_set:
            continue
        try:
            results.append(SavedJobWithStatus(
                url_hash=url_hash,
                posting=raw["posting"],
                match=raw["match"],
                found_at=raw["found_at"],
                last_seen_at=raw["last_seen_at"],
                found_via=raw.get("found_via", ""),
                status=status,
                notes=status_entry.notes if status_entry else None,
            ))
        except Exception as exc:
            logger.warning("Skipping malformed job %s: %s", url_hash, exc)

    # Sort
    if sort == "recent":
        results.sort(key=lambda j: (j.found_at,), reverse=True)
    else:  # score (default): score desc, then found_at desc
        results.sort(key=lambda j: (j.match.score, j.found_at), reverse=True)

    total = len(results)
    total_pages = max(1, (total + page_size - 1) // page_size)
    start = (page - 1) * page_size
    page_jobs = results[start: start + page_size]

    return AutoSearchResultsPage(
        jobs=page_jobs,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages,
    )


def get_summary() -> AutoSearchSummary:
    with _lock:
        data = _load_raw()
        cfg = load_config()
    return AutoSearchSummary(
        enabled=cfg.enabled,
        last_run_at=data.get("last_run_at"),
        next_run_at=data.get("next_run_at"),
        new_count=data.get("new_count", 0),
        total_count=len(data.get("jobs", {})),
    )


def set_job_status(url_hash: str, status: JobStatus, notes: Optional[str]) -> None:
    with _lock:
        statuses = _load_statuses()
        statuses[url_hash] = JobStatusEntry(status=status, notes=notes)
        _save_statuses(statuses)


def mark_seen() -> None:
    with _lock:
        data = _load_raw()
        data["new_count"] = 0
        _save_raw(data)


def update_run_times(last_run_at: datetime, next_run_at: datetime) -> None:
    with _lock:
        data = _load_raw()
        data["last_run_at"] = last_run_at.isoformat()
        data["next_run_at"] = next_run_at.isoformat()
        _save_raw(data)


def cleanup(
    before_date: Optional[datetime],
    remove_not_interested: bool,
    remove_unavailable: bool,
) -> int:
    with _lock:
        data = _load_raw()
        statuses = _load_statuses()
        jobs = data.get("jobs", {})
        last_run_str = data.get("last_run_at")
        last_run = datetime.fromisoformat(last_run_str) if last_run_str else None

        to_remove: set[str] = set()

        for url_hash, raw in jobs.items():
            found_at = datetime.fromisoformat(raw["found_at"])
            last_seen = datetime.fromisoformat(raw["last_seen_at"])
            status_entry = statuses.get(url_hash)
            status = status_entry.status if status_entry else JobStatus.NONE

            if before_date and found_at < before_date:
                to_remove.add(url_hash)
            elif remove_not_interested and status == JobStatus.NOT_INTERESTED:
                to_remove.add(url_hash)
            elif remove_unavailable and last_run and last_seen < last_run:
                to_remove.add(url_hash)

        for h in to_remove:
            jobs.pop(h, None)
            statuses.pop(h, None)

        _save_raw(data)
        _save_statuses(statuses)

    return len(to_remove)
```

- [ ] **Step 4: Run tests**

```
cd backend && python -m pytest tests/test_services/test_auto_search_store.py -v
```
Expected: 11 PASSED

- [ ] **Step 5: Commit**

```
git add backend/app/services/auto_search_store.py backend/tests/test_services/test_auto_search_store.py
git commit -m "feat: add auto_search_store service (persistent JSON storage with dedup + cleanup)"
```

---

## Task 3: `auto_search_scheduler.py` — APScheduler wrapper

**Files:**
- Create: `backend/app/services/auto_search_scheduler.py`
- Test: `backend/tests/test_services/test_auto_search_scheduler.py`

**Interfaces:**
- Consumes: `load_config()`, `save_config()`, `upsert_jobs()`, `update_run_times()` (Task 2); `run_pipeline()` from `app.services.job_pipeline`; `ProfileRepository` from `app.repositories.profile_repository`
- Produces:
  - `start_scheduler(interval_hours: int) -> None`
  - `shutdown_scheduler() -> None`
  - `reschedule(new_interval_hours: int) -> None`
  - `trigger_now(job_id: str) -> None` — runs `_run()` in a daemon thread, updates job_store with progress

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_services/test_auto_search_scheduler.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.services.auto_search_scheduler import reschedule, shutdown_scheduler, start_scheduler


def test_start_and_shutdown_scheduler():
    """Scheduler starts and shuts down without errors."""
    start_scheduler(interval_hours=999)  # very long interval to avoid firing
    shutdown_scheduler()


def test_reschedule_changes_interval():
    start_scheduler(interval_hours=999)
    try:
        # Should not raise — just updates the trigger
        reschedule(new_interval_hours=888)
    finally:
        shutdown_scheduler()


def test_trigger_now_runs_in_thread():
    """trigger_now should fire _run in a background thread, not block."""
    import threading
    import time

    ran = threading.Event()

    def fake_run():
        ran.set()

    with (
        patch("app.services.auto_search_scheduler._run", side_effect=fake_run),
        patch("app.services.auto_search_store.update_run_times"),
        patch("app.services.job_store.create_job"),
        patch("app.services.job_store.update_job"),
    ):
        from app.services.auto_search_scheduler import trigger_now
        trigger_now(job_id="test-job-id")
        ran.wait(timeout=3.0)
        assert ran.is_set(), "_run was not called within 3 seconds"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_services/test_auto_search_scheduler.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `backend/app/services/auto_search_scheduler.py`**

```python
from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.background import BackgroundScheduler

from app.services import job_store as store
from app.services.auto_search_store import load_config, update_run_times, upsert_jobs

logger = logging.getLogger(__name__)

_scheduler = BackgroundScheduler(timezone="UTC")
_JOB_ID = "auto_search"


def _run() -> None:
    """Background thread body: run pipeline for each active entry and upsert results."""
    try:
        config = load_config()
        if not config.enabled or not config.entries:
            return

        from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
        from app.services.job_pipeline import run_pipeline

        try:
            profile = ProfileRepository().load()
        except ProfileNotFoundError:
            logger.warning("Auto-search: no profile found, skipping run")
            return

        run_id = f"auto-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        for entry in config.entries:
            if not entry.active:
                continue
            query = f"{entry.title} {' '.join(entry.keywords)}"
            try:
                results = run_pipeline(profile, query, config.location, max_results=20)
                new = upsert_jobs(results, run_id=run_id, found_via=entry.title)
                logger.info("Auto-search '%s': %d results, %d new", entry.title, len(results), new)
            except Exception as exc:
                logger.warning("Auto-search entry '%s' failed: %s", entry.title, exc)

        now = datetime.now(timezone.utc)
        next_run = now + timedelta(hours=config.interval_hours)
        update_run_times(last_run_at=now, next_run_at=next_run)
    except Exception as exc:
        logger.error("Auto-search _run() error: %s", exc, exc_info=True)


def start_scheduler(interval_hours: int = 2) -> None:
    if not _scheduler.running:
        _scheduler.add_job(
            _run,
            trigger="interval",
            hours=interval_hours,
            id=_JOB_ID,
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("Auto-search scheduler started (interval=%dh)", interval_hours)


def shutdown_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("Auto-search scheduler stopped")


def reschedule(new_interval_hours: int) -> None:
    _scheduler.reschedule_job(
        _JOB_ID,
        trigger="interval",
        hours=new_interval_hours,
    )
    logger.info("Auto-search scheduler rescheduled to %dh", new_interval_hours)


def trigger_now(job_id: str) -> None:
    """Fire _run() immediately in a daemon thread; track progress via job_store."""
    store.create_job(job_id)
    store.update_job(job_id, step="searching", message="Buscando vagas…", progress=10)

    def _wrapped():
        try:
            _run()
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Busca concluída!",
                progress=100,
            )
        except Exception as exc:
            store.update_job(job_id, status="failed", step="error", message=str(exc), progress=0)

    threading.Thread(target=_wrapped, daemon=True).start()
```

- [ ] **Step 4: Run tests**

```
cd backend && python -m pytest tests/test_services/test_auto_search_scheduler.py -v
```
Expected: 3 PASSED

- [ ] **Step 5: Commit**

```
git add backend/app/services/auto_search_scheduler.py backend/tests/test_services/test_auto_search_scheduler.py
git commit -m "feat: add auto_search_scheduler (APScheduler wrapper with trigger_now)"
```

---

## Task 4: `auto_search.py` router + `main.py` lifespan

**Files:**
- Create: `backend/app/routers/auto_search.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_routers/test_auto_search.py`

**Interfaces:**
- Consumes: all store functions (Task 2), `start_scheduler`, `shutdown_scheduler`, `reschedule`, `trigger_now` (Task 3), all models (Task 1)
- Produces: REST endpoints consumed by the frontend (Tasks 5–8)

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_routers/test_auto_search.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && python -m pytest tests/test_routers/test_auto_search.py -v
```
Expected: `ImportError` (router not created yet)

- [ ] **Step 3: Create `backend/app/routers/auto_search.py`**

```python
from __future__ import annotations

import uuid
from typing import Literal, Optional

from fastapi import APIRouter, status
from pydantic import BaseModel

from app.models.auto_search import (
    AutoSearchConfig,
    AutoSearchResultsPage,
    AutoSearchSummary,
    JobStatus,
)
from app.services.auto_search_scheduler import reschedule, trigger_now
from app.services.auto_search_store import (
    cleanup,
    get_results_page,
    get_summary,
    load_config,
    mark_seen,
    save_config,
    set_job_status,
)

router = APIRouter(prefix="/auto-search", tags=["auto-search"])


class RunStart(BaseModel):
    job_id: str
    status: Literal["processing"] = "processing"


class SetStatusRequest(BaseModel):
    status: JobStatus
    notes: Optional[str] = None


class CleanupResult(BaseModel):
    removed: int


# ── Config ────────────────────────────────────────────────────────────────────

@router.get("/config", response_model=AutoSearchConfig)
async def get_config() -> AutoSearchConfig:
    return load_config()


@router.put("/config", response_model=AutoSearchConfig)
async def put_config(new_config: AutoSearchConfig) -> AutoSearchConfig:
    old = load_config()
    save_config(new_config)
    if new_config.interval_hours != old.interval_hours:
        reschedule(new_config.interval_hours)
    return new_config


# ── Summary (lightweight, polled every 60 s) ─────────────────────────────────

@router.get("/summary", response_model=AutoSearchSummary)
async def get_auto_summary() -> AutoSearchSummary:
    return get_summary()


# ── Manual trigger ────────────────────────────────────────────────────────────

@router.post("/run", response_model=RunStart, status_code=status.HTTP_202_ACCEPTED)
async def run_now() -> RunStart:
    job_id = str(uuid.uuid4())
    trigger_now(job_id)
    return RunStart(job_id=job_id)


# ── Results ───────────────────────────────────────────────────────────────────

@router.get("/results", response_model=AutoSearchResultsPage)
async def get_results(
    page: int = 1,
    page_size: int = 10,
    status_filter: str = "NONE",
    sort: str = "score",
) -> AutoSearchResultsPage:
    filters = [s.strip() for s in status_filter.split(",") if s.strip()]
    return get_results_page(page=page, page_size=page_size, status_filter=filters, sort=sort)


@router.post("/mark-seen", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def post_mark_seen() -> None:
    mark_seen()


# ── Job status ────────────────────────────────────────────────────────────────

@router.patch("/jobs/{url_hash}/status", status_code=status.HTTP_200_OK)
async def patch_job_status(url_hash: str, req: SetStatusRequest) -> dict:
    set_job_status(url_hash, req.status, req.notes)
    return {"url_hash": url_hash, "status": req.status}


# ── Cleanup ───────────────────────────────────────────────────────────────────

@router.delete("/cleanup", response_model=CleanupResult)
async def delete_cleanup(
    before_date: Optional[str] = None,
    remove_not_interested: bool = False,
    remove_unavailable: bool = False,
) -> CleanupResult:
    from datetime import datetime
    bd = datetime.fromisoformat(before_date) if before_date else None
    removed = cleanup(
        before_date=bd,
        remove_not_interested=remove_not_interested,
        remove_unavailable=remove_unavailable,
    )
    return CleanupResult(removed=removed)
```

- [ ] **Step 4: Update `backend/app/main.py`**

Replace the entire file:

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import application, auto_search, config, design, jobs, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.auto_search_scheduler import shutdown_scheduler, start_scheduler
    from app.services.auto_search_store import load_config
    cfg = load_config()
    start_scheduler(interval_hours=cfg.interval_hours)
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Job Hunter Assistant",
    description="Agentic career assistant for tech job applications",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(application.router)
app.include_router(config.router)
app.include_router(design.router)
app.include_router(auto_search.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}
```

- [ ] **Step 5: Run tests**

```
cd backend && python -m pytest tests/test_routers/test_auto_search.py -v
```
Expected: 8 PASSED

- [ ] **Step 6: Run full backend test suite to check for regressions**

```
cd backend && python -m pytest tests/ -v --tb=short 2>&1 | tail -10
```
Expected: 52+ passed, same 3 pre-existing failures in `test_profile.py` (unrelated timing issues)

- [ ] **Step 7: Commit**

```
git add backend/app/routers/auto_search.py backend/app/main.py backend/tests/test_routers/test_auto_search.py
git commit -m "feat: add auto_search router + FastAPI lifespan (APScheduler start/stop)"
```

---

## Task 5: Frontend API — new types and client functions

**Files:**
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Produces: `SearchEntry`, `AutoSearchConfig`, `AutoSearchSummary`, `SavedJobWithStatus`, `AutoSearchResultsPage`, `JobStatus` types; 8 new API functions consumed by Tasks 6–8

- [ ] **Step 1: Add types to `frontend/src/api/client.ts`**

After the existing `DesignVersion` interface block, add:

```typescript
// ── Auto Search ──────────────────────────────────────────────────────────────

export type JobStatus =
  | 'NONE'
  | 'NOT_INTERESTED'
  | 'APPLIED'
  | 'INTERVIEWING'
  | 'OFFER_RECEIVED'

export interface SearchEntry {
  id: string
  title: string
  keywords: string[]
  active: boolean
  custom: boolean
}

export interface AutoSearchConfig {
  enabled: boolean
  interval_hours: number
  location: string
  page_size: number
  entries: SearchEntry[]
}

export interface AutoSearchSummary {
  enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  new_count: number
  total_count: number
}

export interface SavedJobWithStatus {
  url_hash: string
  posting: JobPosting
  match: MatchScore
  found_at: string
  last_seen_at: string
  found_via: string
  status: JobStatus
  notes: string | null
}

export interface AutoSearchResultsPage {
  jobs: SavedJobWithStatus[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AutoSearchRunStart {
  job_id: string
  status: 'processing'
}
```

- [ ] **Step 2: Add API functions to `frontend/src/api/client.ts`**

After the existing `deleteDesign` function block, add:

```typescript
// ── Auto Search API ───────────────────────────────────────────────────────────

export async function getAutoSearchConfig() {
  return request<AutoSearchConfig>('/auto-search/config')
}

export async function saveAutoSearchConfig(config: AutoSearchConfig) {
  return request<AutoSearchConfig>('/auto-search/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  })
}

export async function getAutoSearchSummary() {
  return request<AutoSearchSummary>('/auto-search/summary')
}

export async function triggerAutoSearchRun() {
  return request<AutoSearchRunStart>('/auto-search/run', { method: 'POST' })
}

export async function getAutoSearchResults(
  page: number,
  pageSize: number,
  statusFilter: string,
  sort: 'score' | 'recent' = 'score',
) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    status_filter: statusFilter,
    sort,
  })
  return request<AutoSearchResultsPage>(`/auto-search/results?${params}`)
}

export async function markAutoSearchSeen() {
  return request<void>('/auto-search/mark-seen', { method: 'POST' })
}

export async function setJobStatus(urlHash: string, status: JobStatus, notes?: string) {
  return request<{ url_hash: string; status: JobStatus }>(`/auto-search/jobs/${urlHash}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status, notes: notes ?? null }),
  })
}

export async function cleanupAutoSearch(params: {
  before_date?: string
  remove_not_interested?: boolean
  remove_unavailable?: boolean
}) {
  const q = new URLSearchParams()
  if (params.before_date) q.set('before_date', params.before_date)
  if (params.remove_not_interested) q.set('remove_not_interested', 'true')
  if (params.remove_unavailable) q.set('remove_unavailable', 'true')
  return request<{ removed: number }>(`/auto-search/cleanup?${q}`, { method: 'DELETE' })
}
```

- [ ] **Step 3: TypeScript check**

```
cd frontend && npx tsc -b 2>&1
```
Expected: no errors

- [ ] **Step 4: Commit**

```
git add frontend/src/api/client.ts
git commit -m "feat: add auto-search API types and client functions"
```

---

## Task 6: `AutoSearchConfig.tsx` — collapsible configuration panel

**Files:**
- Create: `frontend/src/components/AutoSearchConfig.tsx`

**Interfaces:**
- Consumes: `AutoSearchConfig`, `SearchEntry`, `saveAutoSearchConfig` (Task 5)
- Produces: `<AutoSearchConfig config={...} onSaved={(c) => void} />` — used by Task 7

- [ ] **Step 1: Create `frontend/src/components/AutoSearchConfig.tsx`**

```tsx
import { useState } from 'react'
import {
  saveAutoSearchConfig,
  type AutoSearchConfig,
  type SearchEntry,
} from '../api/client'

interface Props {
  config: AutoSearchConfig
  onSaved: (updated: AutoSearchConfig) => void
}

const INTERVAL_OPTIONS = [1, 2, 4, 8, 12, 24]

function KeywordChips({
  keywords,
  onChange,
}: {
  keywords: string[]
  onChange: (kws: string[]) => void
}) {
  const [draft, setDraft] = useState('')

  function add() {
    const kw = draft.trim()
    if (kw && !keywords.includes(kw)) onChange([...keywords, kw])
    setDraft('')
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
      {keywords.map(kw => (
        <span
          key={kw}
          style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 10,
            background: 'var(--accent-bg)', color: 'var(--accent)',
            border: '1px solid var(--accent-border)', display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          {kw}
          <button
            onClick={() => onChange(keywords.filter(k => k !== kw))}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--accent)', fontSize: 11, lineHeight: 1 }}
          >
            ×
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() } }}
        onBlur={add}
        placeholder="+ keyword"
        style={{
          border: 'none', outline: 'none', fontSize: 11, background: 'transparent',
          color: 'var(--text-h)', minWidth: 80,
        }}
      />
    </div>
  )
}

export function AutoSearchConfigPanel({ config, onSaved }: Props) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<AutoSearchConfig>(config)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function updateEntry(id: string, patch: Partial<SearchEntry>) {
    setDraft(d => ({
      ...d,
      entries: d.entries.map(e => e.id === id ? { ...e, ...patch } : e),
    }))
  }

  function removeEntry(id: string) {
    setDraft(d => ({ ...d, entries: d.entries.filter(e => e.id !== id) }))
  }

  function addCustomEntry() {
    const newEntry: SearchEntry = {
      id: crypto.randomUUID(),
      title: '',
      keywords: [],
      active: true,
      custom: true,
    }
    setDraft(d => ({ ...d, entries: [...d.entries, newEntry] }))
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const saved = await saveAutoSearchConfig(draft)
      onSaved(saved)
      setOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, marginBottom: 16, overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', padding: '10px 14px', display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', background: 'var(--bg)', border: 'none', cursor: 'pointer',
          fontSize: 13, fontWeight: 600, color: 'var(--text-h)',
        }}
      >
        <span>⚙️ Configuração da busca</span>
        <span style={{ fontSize: 11, color: 'var(--text)' }}>{open ? '▲ fechar' : '▼ expandir'}</span>
      </button>

      {open && (
        <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)', background: 'var(--bg)' }}>

          {/* Top controls */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text)' }}>
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={e => setDraft(d => ({ ...d, enabled: e.target.checked }))}
              />
              Ativada
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text)' }}>
              Intervalo:
              <select
                value={draft.interval_hours}
                onChange={e => setDraft(d => ({ ...d, interval_hours: Number(e.target.value) }))}
                style={{ padding: '3px 6px', borderRadius: 5, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg)', color: 'var(--text-h)' }}
              >
                {INTERVAL_OPTIONS.map(h => (
                  <option key={h} value={h}>{h}h</option>
                ))}
              </select>
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text)', flex: 1 }}>
              Local:
              <input
                value={draft.location}
                onChange={e => setDraft(d => ({ ...d, location: e.target.value }))}
                style={{
                  flex: 1, padding: '4px 8px', borderRadius: 5, border: '1px solid var(--border)',
                  fontSize: 12, background: 'var(--bg)', color: 'var(--text-h)',
                }}
              />
            </label>
          </div>

          {/* Entries */}
          <div style={{ marginBottom: 10 }}>
            <p style={{ fontSize: 12, color: 'var(--text)', margin: '0 0 8px', fontWeight: 600 }}>Buscas:</p>
            {draft.entries.map(entry => (
              <div
                key={entry.id}
                style={{
                  display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 8,
                  alignItems: 'start', marginBottom: 8, padding: '8px 10px',
                  border: '1px solid var(--border)', borderRadius: 6, background: 'rgba(0,0,0,0.02)',
                }}
              >
                <input
                  type="checkbox"
                  checked={entry.active}
                  onChange={e => updateEntry(entry.id, { active: e.target.checked })}
                  style={{ marginTop: 3 }}
                />
                <div>
                  <input
                    value={entry.title}
                    onChange={e => updateEntry(entry.id, { title: e.target.value })}
                    placeholder="Título do cargo"
                    style={{
                      width: '100%', padding: '4px 8px', borderRadius: 5,
                      border: '1px solid var(--border)', fontSize: 12,
                      background: 'var(--bg)', color: 'var(--text-h)', marginBottom: 6,
                      boxSizing: 'border-box',
                    }}
                  />
                  <KeywordChips
                    keywords={entry.keywords}
                    onChange={kws => updateEntry(entry.id, { keywords: kws })}
                  />
                </div>
                {entry.custom && (
                  <button
                    onClick={() => removeEntry(entry.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', fontSize: 16, padding: 0 }}
                  >
                    ×
                  </button>
                )}
                {!entry.custom && <div />}
              </div>
            ))}
            <button
              onClick={addCustomEntry}
              style={{
                fontSize: 12, color: 'var(--accent)', background: 'none',
                border: '1px dashed var(--accent-border)', borderRadius: 6,
                padding: '5px 12px', cursor: 'pointer', width: '100%',
              }}
            >
              + Adicionar título customizado
            </button>
          </div>

          {error && <p style={{ fontSize: 12, color: '#ef4444', margin: '0 0 8px' }}>{error}</p>}

          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '7px 18px', background: saving ? 'var(--border)' : 'var(--accent)',
              color: 'white', border: 'none', borderRadius: 6, fontWeight: 600,
              cursor: saving ? 'default' : 'pointer', fontSize: 13,
            }}
          >
            {saving ? 'Salvando…' : 'Salvar configurações'}
          </button>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```
cd frontend && npx tsc -b 2>&1
```
Expected: no errors

- [ ] **Step 3: Commit**

```
git add frontend/src/components/AutoSearchConfig.tsx
git commit -m "feat: add AutoSearchConfig component (collapsible config panel)"
```

---

## Task 7: `AutoSearchPage.tsx` — full redesign

**Files:**
- Create: `frontend/src/components/JobStatusMenu.tsx`
- Modify: `frontend/src/pages/AutoSearchPage.tsx`

**Interfaces:**
- Consumes: `AutoSearchConfig`, `AutoSearchConfigPanel` (Task 6); `getAutoSearchResults`, `markAutoSearchSeen`, `setJobStatus`, `triggerAutoSearchRun`, `getIngestStatus`, `cleanupAutoSearch` (Task 5); `SavedJobWithStatus`, `JobStatus` types
- Produces: redesigned `AutoSearchPage` with 3 tabs, pagination, status actions

- [ ] **Step 1: Create `frontend/src/components/JobStatusMenu.tsx`**

```tsx
import { useEffect, useRef, useState } from 'react'
import { setJobStatus, type JobStatus, type SavedJobWithStatus } from '../api/client'

interface Props {
  job: SavedJobWithStatus
  onStatusChanged: (urlHash: string, newStatus: JobStatus) => void
}

const STATUS_OPTIONS: { status: JobStatus; label: string }[] = [
  { status: 'NOT_INTERESTED', label: '👎 Sem interesse' },
  { status: 'APPLIED', label: '📨 Currículo enviado' },
  { status: 'INTERVIEWING', label: '🗓 Em processo' },
  { status: 'OFFER_RECEIVED', label: '🎉 Oferta recebida' },
  { status: 'NONE', label: '↩ Desfazer' },
]

export function JobStatusMenu({ job, onStatusChanged }: Props) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  async function handleSelect(newStatus: JobStatus) {
    setOpen(false)
    setBusy(true)
    try {
      await setJobStatus(job.url_hash, newStatus)
      onStatusChanged(job.url_hash, newStatus)
    } finally {
      setBusy(false)
    }
  }

  const options = STATUS_OPTIONS.filter(o => o.status !== job.status)

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(v => !v)}
        disabled={busy}
        style={{
          background: 'none', border: '1px solid var(--border)', borderRadius: 5,
          padding: '3px 8px', cursor: busy ? 'default' : 'pointer',
          fontSize: 14, color: 'var(--text)', lineHeight: 1,
        }}
        title="Atualizar status"
      >
        {busy ? '…' : '⋮'}
      </button>

      {open && (
        <div style={{
          position: 'absolute', right: 0, top: '110%', zIndex: 100,
          background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          minWidth: 180, overflow: 'hidden',
        }}>
          {options.map(o => (
            <button
              key={o.status}
              onClick={() => handleSelect(o.status)}
              style={{
                display: 'block', width: '100%', padding: '8px 14px',
                textAlign: 'left', background: 'none', border: 'none',
                cursor: 'pointer', fontSize: 13, color: 'var(--text-h)',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent-bg)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'none')}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Rewrite `frontend/src/pages/AutoSearchPage.tsx`**

```tsx
import { useEffect, useState } from 'react'
import {
  cleanupAutoSearch,
  getAutoSearchConfig,
  getAutoSearchResults,
  getIngestStatus,
  markAutoSearchSeen,
  triggerAutoSearchRun,
  type AutoSearchConfig,
  type AutoSearchResultsPage,
  type DesignVersion,
  type JobStatus,
  type SavedJobWithStatus,
} from '../api/client'
import { ApplicationGenerator } from '../components/ApplicationGenerator'
import { AutoSearchConfigPanel } from '../components/AutoSearchConfig'
import { JobStatusMenu } from '../components/JobStatusMenu'

interface Props {
  onBack: () => void
  designs?: DesignVersion[]
}

type Tab = 'new' | 'pipeline' | 'not_interested'

const TAB_FILTERS: Record<Tab, string> = {
  new: 'NONE',
  pipeline: 'APPLIED,INTERVIEWING,OFFER_RECEIVED',
  not_interested: 'NOT_INTERESTED',
}

const STATUS_LABELS: Record<string, string> = {
  APPLIED: 'Enviado',
  INTERVIEWING: 'Em processo',
  OFFER_RECEIVED: 'Oferta',
  NOT_INTERESTED: 'Sem interesse',
  NONE: '',
}

function ScoreBadge({ score }: { score: number }) {
  const bg = score >= 75 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <span style={{
      display: 'inline-block', minWidth: 36, textAlign: 'center',
      padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 700,
      color: 'white', background: bg,
    }}>
      {score}
    </span>
  )
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  const m = Math.floor(diff / 60_000)
  if (h >= 48) return `${Math.floor(h / 24)}d atrás`
  if (h >= 1) return `${h}h atrás`
  return `${m}m atrás`
}

function JobCard({ job, designs = [], onStatusChanged }: {
  job: SavedJobWithStatus
  designs?: DesignVersion[]
  onStatusChanged: (urlHash: string, newStatus: JobStatus) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const p = job.posting
  const m = job.match

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '12px 14px', marginBottom: 8, background: 'var(--bg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <ScoreBadge score={m.score} />
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-h)' }}>{p.title}</span>
            {job.status !== 'NONE' && (
              <span style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 4,
                background: 'var(--accent-bg)', color: 'var(--accent)',
                border: '1px solid var(--accent-border)',
              }}>
                {STATUS_LABELS[job.status]}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 3 }}>
            {p.company} · {p.location}
            {p.salary_range && <span> · {p.salary_range}</span>}
            <span style={{ marginLeft: 8, color: 'var(--text)', opacity: 0.7 }}>{timeAgo(job.found_at)}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text)', marginTop: 2, opacity: 0.8 }}>
            via: {job.found_via}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          <button
            onClick={() => setExpanded(v => !v)}
            style={{ fontSize: 12, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            {expanded ? 'fechar' : 'ver mais'}
          </button>
          <JobStatusMenu job={job} onStatusChanged={onStatusChanged} />
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
          <p style={{ fontSize: 12, color: 'var(--text)', whiteSpace: 'pre-wrap', margin: '0 0 10px' }}>
            {p.description.slice(0, 600)}{p.description.length > 600 ? '…' : ''}
          </p>
          {m.keywords_found.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>Match: </span>
              {m.keywords_found.map(k => (
                <span key={k} style={{ fontSize: 11, padding: '1px 5px', borderRadius: 4, background: 'rgba(34,197,94,0.12)', color: '#16a34a', marginRight: 4 }}>{k}</span>
              ))}
            </div>
          )}
          <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--accent)' }}>
            Ver vaga ↗
          </a>
          <ApplicationGenerator job={p} match={m} designs={designs} />
        </div>
      )}
    </div>
  )
}

function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  if (totalPages <= 1) return null
  const pages = Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
    if (totalPages <= 7) return i + 1
    if (i === 0) return 1
    if (i === 6) return totalPages
    return page + i - 3
  }).filter(p => p >= 1 && p <= totalPages)

  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: 4, marginTop: 16 }}>
      <button onClick={() => onChange(page - 1)} disabled={page <= 1} style={pageBtn(false)}>‹</button>
      {pages.map(p => (
        <button key={p} onClick={() => onChange(p)} style={pageBtn(p === page)}>{p}</button>
      ))}
      <button onClick={() => onChange(page + 1)} disabled={page >= totalPages} style={pageBtn(false)}>›</button>
    </div>
  )
}

function pageBtn(active: boolean): React.CSSProperties {
  return {
    padding: '4px 10px', borderRadius: 5, fontSize: 13, cursor: 'pointer',
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    background: active ? 'var(--accent)' : 'var(--bg)',
    color: active ? 'white' : 'var(--text-h)',
  }
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

export function AutoSearchPage({ onBack, designs = [] }: Props) {
  const [config, setConfig] = useState<AutoSearchConfig | null>(null)
  const [tab, setTab] = useState<Tab>('new')
  const [sort, setSort] = useState<'score' | 'recent'>('score')
  const [page, setPage] = useState(1)
  const [resultsPage, setResultsPage] = useState<AutoSearchResultsPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [runProgress, setRunProgress] = useState('')
  const [showCleanup, setShowCleanup] = useState(false)
  const [cleanupOpts, setCleanupOpts] = useState({ remove_not_interested: false, remove_unavailable: false })
  const [cleanupMsg, setCleanupMsg] = useState('')

  const pageSize = config?.page_size ?? 10

  useEffect(() => {
    getAutoSearchConfig().then(setConfig).catch(console.error)
  }, [])

  useEffect(() => {
    if (tab === 'new') markAutoSearchSeen().catch(() => {})
  }, [tab])

  useEffect(() => {
    if (!config) return
    loadResults()
  }, [tab, page, sort, config])

  async function loadResults() {
    setLoading(true)
    try {
      const res = await getAutoSearchResults(page, pageSize, TAB_FILTERS[tab], sort)
      setResultsPage(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  function handleTabChange(t: Tab) {
    setTab(t)
    setPage(1)
    setResultsPage(null)
  }

  function handleStatusChanged(urlHash: string, newStatus: JobStatus) {
    setResultsPage(prev => {
      if (!prev) return prev
      return { ...prev, jobs: prev.jobs.filter(j => j.url_hash !== urlHash) }
    })
  }

  async function handleRunNow() {
    setRunning(true)
    setRunProgress('Iniciando busca…')
    try {
      const { job_id } = await triggerAutoSearchRun()
      while (true) {
        const status = await getIngestStatus(job_id)
        setRunProgress(status.message)
        if (status.status !== 'processing') break
        await sleep(1500)
      }
      await loadResults()
    } catch (err) {
      setRunProgress('Erro ao executar busca.')
    } finally {
      setRunning(false)
      setRunProgress('')
    }
  }

  async function handleCleanup() {
    try {
      const result = await cleanupAutoSearch(cleanupOpts)
      setCleanupMsg(`${result.removed} vagas removidas.`)
      setShowCleanup(false)
      setPage(1)
      await loadResults()
    } catch {
      setCleanupMsg('Erro ao limpar.')
    }
  }

  const tabCount = (t: Tab) => {
    if (!resultsPage || tab === t) return resultsPage?.total ?? '…'
    return '…'
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-h)' }}>⚡ Auto Busca de Vagas</h2>
          {config && (
            <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text)' }}>
              {config.enabled ? `Busca a cada ${config.interval_hours}h` : 'Busca desativada'}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={handleRunNow}
            disabled={running}
            style={{
              padding: '7px 14px', background: running ? 'var(--border)' : 'var(--accent)',
              color: 'white', border: 'none', borderRadius: 7, fontWeight: 600,
              cursor: running ? 'default' : 'pointer', fontSize: 13,
            }}
          >
            {running ? '🔄 Buscando…' : '▶ Buscar agora'}
          </button>
          <button onClick={onBack} style={{ padding: '7px 14px', background: 'none', border: '1px solid var(--border)', borderRadius: 7, cursor: 'pointer', fontSize: 13, color: 'var(--text)' }}>
            ← Voltar
          </button>
        </div>
      </div>

      {running && runProgress && (
        <p style={{ fontSize: 12, color: 'var(--accent)', marginBottom: 12 }}>{runProgress}</p>
      )}

      {/* Config panel */}
      {config && (
        <AutoSearchConfigPanel
          config={config}
          onSaved={updated => { setConfig(updated); setPage(1) }}
        />
      )}

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 14, gap: 0 }}>
        {(['new', 'pipeline', 'not_interested'] as Tab[]).map(t => {
          const labels: Record<Tab, string> = {
            new: 'Novas vagas',
            pipeline: 'Pipeline',
            not_interested: 'Sem interesse',
          }
          return (
            <button
              key={t}
              onClick={() => handleTabChange(t)}
              style={{
                padding: '8px 16px', fontSize: 13, fontWeight: tab === t ? 700 : 400,
                background: 'none', border: 'none', cursor: 'pointer',
                borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
                color: tab === t ? 'var(--accent)' : 'var(--text)',
                marginBottom: -1,
              }}
            >
              {labels[t]}
            </button>
          )
        })}
      </div>

      {/* Results controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: 12, color: 'var(--text)' }}>
          {resultsPage ? `${resultsPage.total} vagas · pág ${resultsPage.page}/${resultsPage.total_pages}` : '…'}
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select
            value={sort}
            onChange={e => { setSort(e.target.value as 'score' | 'recent'); setPage(1) }}
            style={{ padding: '4px 8px', borderRadius: 5, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg)', color: 'var(--text-h)' }}
          >
            <option value="score">Score ↓</option>
            <option value="recent">Mais recentes</option>
          </select>
          <button
            onClick={() => setShowCleanup(true)}
            style={{ fontSize: 12, background: 'none', border: '1px solid var(--border)', borderRadius: 5, padding: '4px 10px', cursor: 'pointer', color: 'var(--text)' }}
          >
            🧹 Limpar
          </button>
        </div>
      </div>

      {/* Results */}
      {loading && <p style={{ fontSize: 13, color: 'var(--text)' }}>Carregando…</p>}
      {!loading && resultsPage?.jobs.length === 0 && (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text)' }}>
          <p style={{ fontSize: 14 }}>Nenhuma vaga nesta aba.</p>
          {tab === 'new' && (
            <p style={{ fontSize: 12 }}>Clique em "Buscar agora" para atualizar.</p>
          )}
        </div>
      )}
      {!loading && resultsPage?.jobs.map(job => (
        <JobCard
          key={job.url_hash}
          job={job}
          designs={designs}
          onStatusChanged={handleStatusChanged}
        />
      ))}

      {resultsPage && (
        <Pagination page={page} totalPages={resultsPage.total_pages} onChange={setPage} />
      )}

      {cleanupMsg && (
        <p style={{ fontSize: 12, color: 'var(--accent)', marginTop: 8 }}>{cleanupMsg}</p>
      )}

      {/* Cleanup modal */}
      {showCleanup && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 200,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10,
            padding: '20px 24px', minWidth: 320, maxWidth: 400,
          }}>
            <h3 style={{ margin: '0 0 14px', fontSize: 15, color: 'var(--text-h)' }}>🧹 Limpar vagas</h3>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, fontSize: 13, color: 'var(--text)' }}>
              <input
                type="checkbox"
                checked={cleanupOpts.remove_not_interested}
                onChange={e => setCleanupOpts(o => ({ ...o, remove_not_interested: e.target.checked }))}
              />
              Remover vagas marcadas como "Sem interesse"
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16, fontSize: 13, color: 'var(--text)' }}>
              <input
                type="checkbox"
                checked={cleanupOpts.remove_unavailable}
                onChange={e => setCleanupOpts(o => ({ ...o, remove_unavailable: e.target.checked }))}
              />
              Remover vagas que não aparecem mais nas buscas
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleCleanup} style={{ padding: '7px 16px', background: '#ef4444', color: 'white', border: 'none', borderRadius: 6, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
                Limpar
              </button>
              <button onClick={() => setShowCleanup(false)} style={{ padding: '7px 12px', background: 'none', border: '1px solid var(--border)', borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)' }}>
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
```

- [ ] **Step 3: TypeScript check**

```
cd frontend && npx tsc -b 2>&1
```
Expected: no errors

- [ ] **Step 4: Commit**

```
git add frontend/src/components/JobStatusMenu.tsx frontend/src/pages/AutoSearchPage.tsx
git commit -m "feat: redesign AutoSearchPage (3 tabs, pagination, status menu, config panel)"
```

---

## Task 8: Badge in `App.tsx` + `ProfilePage.tsx`

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/pages/ProfilePage.tsx`

**Interfaces:**
- Consumes: `getAutoSearchSummary` (Task 5)
- Produces: badge count passed to `ProfilePage`, displayed on the "Auto Search" button

- [ ] **Step 1: Read current `App.tsx` and `ProfilePage.tsx`**

Read both files before making changes:
```
C:\Users\itsal\ClaudeWorkspace\job-hunter\frontend\src\App.tsx
C:\Users\itsal\ClaudeWorkspace\job-hunter\frontend\src\pages\ProfilePage.tsx
```

Find: where `auto_search` state is rendered (the `AutoSearchPage` render) and where the "⚡ Auto Search" button is rendered in ProfilePage (look for `onAutoSearch`).

- [ ] **Step 2: Add summary polling to `App.tsx`**

In `App.tsx`, add a new state and polling effect:

```typescript
const [autoSearchBadge, setAutoSearchBadge] = useState(0)

useEffect(() => {
  // Poll auto-search summary every 60 seconds for new-jobs badge
  async function checkSummary() {
    try {
      const summary = await getAutoSearchSummary()
      setAutoSearchBadge(summary.new_count)
    } catch {
      // silently ignore — badge is cosmetic
    }
  }
  checkSummary()
  const id = setInterval(checkSummary, 60_000)
  return () => clearInterval(id)
}, [])
```

Add `getAutoSearchSummary` to the import from `'./api/client'`.

Pass `autoSearchBadge` to `ProfilePage` as a new prop: `<ProfilePage ... autoSearchBadge={autoSearchBadge} />`.

Also clear the badge when the user navigates to the auto_search state:
```typescript
function handleAutoSearch() {
  setAutoSearchBadge(0)
  setAppState('auto_search')
}
```
Replace `onAutoSearch={() => setAppState('auto_search')}` with `onAutoSearch={handleAutoSearch}`.

- [ ] **Step 3: Add `autoSearchBadge` prop to `ProfilePage.tsx`**

In `ProfilePage.tsx`, add `autoSearchBadge?: number` to the Props interface.

Find the "⚡ Auto Search" button (the one that calls `onAutoSearch`). Update it to show the badge when `autoSearchBadge > 0`:

```tsx
<button onClick={onAutoSearch} style={{ /* existing styles */ }}>
  ⚡ Auto Search
  {(autoSearchBadge ?? 0) > 0 && (
    <span style={{
      marginLeft: 6, background: '#ef4444', color: 'white',
      borderRadius: '50%', fontSize: 10, fontWeight: 700,
      padding: '1px 5px', verticalAlign: 'middle',
    }}>
      {autoSearchBadge}
    </span>
  )}
</button>
```

- [ ] **Step 4: TypeScript check + production build**

```
cd frontend && npx tsc -b && npx vite build 2>&1 | tail -5
```
Expected: no errors, `✓ built in Xs`

- [ ] **Step 5: Run full backend test suite**

```
cd backend && python -m pytest tests/ --tb=short 2>&1 | tail -8
```
Expected: same pass/fail ratio as before (60+ passing)

- [ ] **Step 6: Commit**

```
git add frontend/src/App.tsx frontend/src/pages/ProfilePage.tsx
git commit -m "feat: add new-jobs badge on profile page (polls /auto-search/summary every 60s)"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| APScheduler runs every N hours | Task 3 (`start_scheduler`) |
| Config: interval, location, keywords, toggle per entry, custom entries | Task 6 (`AutoSearchConfigPanel`) |
| Results persisted in `auto_search_results.json` + `job_status.json` | Task 2 |
| Dedup by URL hash, preserve `found_at`, max score | Task 2 (`upsert_jobs`) |
| `new_count` tracks unseen jobs | Task 2 (`upsert_jobs` + `mark_seen`) |
| GET /results paginated, `status_filter` comma-separated | Task 4 |
| Sort by score (default) or recency | Task 4 + Task 7 |
| 10 per page default (configurable in config) | Task 1 (`page_size`) + Task 2 (`get_results_page`) |
| 3 tabs: Novas vagas / Pipeline / Sem interesse | Task 7 |
| Job status pipeline: NONE → APPLIED → INTERVIEWING → OFFER | Task 1 + Task 7 (`JobStatusMenu`) |
| NOT_INTERESTED filtered from main view | Task 7 (TAB_FILTERS) |
| Badge on ProfilePage, polls every 60s | Task 8 |
| Manual "Buscar agora" with progress | Task 7 (polls job_store via getIngestStatus) |
| Cleanup: by date, by not-interested, by unavailable | Task 2 (`cleanup`) + Task 7 (modal) |
| `PUT /config` reschedules APScheduler if interval changed | Task 4 |
| `POST /mark-seen` zeros new_count | Task 2 + Task 4 |
| Lifespan starts/stops scheduler | Task 4 (`main.py`) |
| Config seeded from `profile.job_suggestions` on first run | Task 2 (`load_config`) |

**All spec requirements covered. No placeholders found. Type consistency verified: `url_hash: str` used consistently across Task 2 store, Task 4 router, Task 5 client, Task 7 components.**
