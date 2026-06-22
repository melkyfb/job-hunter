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
        from app.services.job_search import get_multi_provider   # NEW

        try:
            profile = ProfileRepository().load()
        except ProfileNotFoundError:
            logger.warning("Auto-search: no profile found, skipping run")
            return

        multi = get_multi_provider(config.providers)   # NEW — build once per run

        run_id = f"auto-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        for entry in config.entries:
            if not entry.active:
                continue
            query = f"{entry.title} {' '.join(entry.keywords)}"
            try:
                results = run_pipeline(profile, query, config.location, max_results=20, provider=multi)
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
