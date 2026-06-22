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


def _run() -> str:
    """Background thread body: run pipeline for each active entry and upsert results.
    Returns a human-readable summary message."""
    try:
        config = load_config()
        if not config.enabled:
            return "Busca automática desativada. Ative nas configurações para buscar vagas."
        if not config.entries:
            return "Nenhuma vaga configurada. Adicione títulos de vagas nas configurações."

        from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
        from app.services.job_pipeline import run_pipeline
        from app.services.job_search import get_multi_provider

        try:
            profile = ProfileRepository().load()
        except ProfileNotFoundError:
            logger.warning("Auto-search: no profile found, skipping run")
            return "Nenhum perfil encontrado. Importe seu currículo primeiro."

        multi = get_multi_provider(config.providers)

        run_id = f"auto-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        total_new = 0
        active_entries = [e for e in config.entries if e.active]
        if not active_entries:
            return "Nenhuma vaga ativa. Ative ao menos uma vaga nas configurações."

        for entry in active_entries:
            query = f"{entry.title} {' '.join(entry.keywords)}"
            try:
                results = run_pipeline(profile, query, config.location, max_results=20, provider=multi)
                new = upsert_jobs(results, run_id=run_id, found_via=entry.title)
                total_new += new
                logger.info("Auto-search '%s': %d results, %d new", entry.title, len(results), new)
            except Exception as exc:
                logger.warning("Auto-search entry '%s' failed: %s", entry.title, exc)

        now = datetime.now(timezone.utc)
        next_run = now + timedelta(hours=config.interval_hours)
        update_run_times(last_run_at=now, next_run_at=next_run)
        return f"Busca concluída! {total_new} nova{'s' if total_new != 1 else ''} vaga{'s' if total_new != 1 else ''} encontrada{'s' if total_new != 1 else ''}."
    except Exception as exc:
        logger.error("Auto-search _run() error: %s", exc, exc_info=True)
        raise


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
            summary = _run()
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message=summary,
                progress=100,
            )
        except Exception as exc:
            store.update_job(job_id, status="failed", step="error", message=str(exc), progress=0)

    threading.Thread(target=_wrapped, daemon=True).start()
