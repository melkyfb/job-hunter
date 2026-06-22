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
