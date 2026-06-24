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

from app.core.paths import DATA_DIR

_STORAGE_DIR = DATA_DIR
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
    cfg = load_config()  # read-only, separate file, no lock needed
    with _lock:
        data = _load_raw()
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
