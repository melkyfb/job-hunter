from __future__ import annotations

import copy
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, Field

from app.models.jobs import RankedJob
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services import job_store as store
from app.services.job_pipeline import run_pipeline
from app.services.search_cache import get_cached, set_cache

router = APIRouter(prefix="/jobs", tags=["jobs"])

_repo = ProfileRepository()


class JobSearchRequest(BaseModel):
    query: str = Field(description="Job title or keywords, e.g. 'Python Backend Engineer'")
    location: str = Field(default="Munich, Germany")
    max_results: int = Field(default=10, ge=1, le=50)
    force_refresh: bool = Field(
        default=False,
        description="Ignore cached results and fetch fresh data from the provider.",
    )


class JobSearchResponse(BaseModel):
    results: list[RankedJob]
    cached: bool = Field(description="True if results came from local cache")
    cached_at: Optional[datetime] = Field(
        default=None,
        description="When the cache entry was created (None if not cached)",
    )


# ── Async search job schema ───────────────────────────────────────────────────

class AsyncSearchStart(BaseModel):
    search_id: str
    status: Literal["processing"] = "processing"
    cached: bool = False
    cached_at: Optional[datetime] = None


class AsyncSearchStatus(BaseModel):
    search_id: str
    status: str
    step: str
    message: str
    progress: int
    result: Optional[Any] = None


# ── Search endpoint (now async) ───────────────────────────────────────────────

@router.post(
    "/search",
    response_model=AsyncSearchStart,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start a job search in the background; poll /search/{search_id} for progress",
)
async def search_jobs(request: JobSearchRequest) -> AsyncSearchStart:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload your resume first via POST /profile/ingest.",
        )

    # Cache hit → return immediately (no job needed)
    if not request.force_refresh:
        cached = get_cached(request.query, request.location, request.max_results)
        if cached is not None:
            results, cached_at = cached
            response = JobSearchResponse(results=results, cached=True, cached_at=cached_at)
            search_id = str(uuid.uuid4())
            store.create_job(search_id)
            store.update_job(
                search_id,
                status="completed",
                step="done",
                message="Results loaded from cache.",
                progress=100,
                result=response.model_dump(mode="json"),
            )
            return AsyncSearchStart(search_id=search_id, cached=True, cached_at=cached_at)

    search_id = str(uuid.uuid4())
    store.create_job(search_id)
    store.update_job(
        search_id,
        step="searching",
        message=f'Searching for "{request.query}" in {request.location}…',
        progress=5,
    )

    req = request  # capture for thread

    def _run() -> None:
        def progress(step: str, message: str, pct: int) -> None:
            store.update_job(search_id, step=step, message=message, progress=pct)

        try:
            results = run_pipeline(
                profile,
                req.query,
                req.location,
                req.max_results,
                progress,
            )
        except Exception as exc:
            store.update_job(
                search_id,
                status="failed",
                step="error",
                message=str(exc),
                progress=0,
            )
            return

        set_cache(req.query, req.location, req.max_results, results)
        response = JobSearchResponse(results=results, cached=False, cached_at=None)
        store.update_job(
            search_id,
            status="completed",
            step="done",
            message=f"Done! Showing {len(results)} matching jobs.",
            progress=100,
            result=response.model_dump(mode="json"),
        )

    threading.Thread(target=_run, daemon=True).start()
    return AsyncSearchStart(search_id=search_id)


@router.get(
    "/search/{search_id}",
    response_model=AsyncSearchStatus,
    summary="Poll the progress of a background job search",
)
async def get_search_status(search_id: str) -> AsyncSearchStatus:
    job = store.get_job(search_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Search job not found or expired.")
    return AsyncSearchStatus(
        search_id=job.job_id,
        status=job.status,
        step=job.step,
        message=job.message,
        progress=job.progress,
        result=job.result,
    )


# ── Auto Search ───────────────────────────────────────────────────────────────

_AUTO_SEARCH_MAX_QUERIES = 5
_AUTO_SEARCH_RESULTS_PER_QUERY = 10
_AUTO_SEARCH_DEDUP_BONUS = 10


class AutoSearchResponse(BaseModel):
    results: list[RankedJob]
    queries_used: list[str]


def _run_one(profile, title: str, keywords: list[str], location: str) -> tuple[str, list[RankedJob]]:
    """Run pipeline for a single auto-search query; returns (query_label, results)."""
    query = title
    if keywords:
        query = f"{title} {' '.join(keywords[:3])}"
    results = run_pipeline(profile, query, location, _AUTO_SEARCH_RESULTS_PER_QUERY)
    # Tag each job with its origin
    tagged = []
    for job in results:
        j = copy.copy(job)
        j.found_via = title
        tagged.append(j)
    return title, tagged


def _deduplicate(all_results: list[tuple[str, list[RankedJob]]]) -> list[RankedJob]:
    """Merge results across queries. Deduplicate by URL; give +bonus for duplicates."""
    seen: dict[str, RankedJob] = {}
    for _query, jobs in all_results:
        for job in jobs:
            url = job.posting.url
            if url in seen:
                existing = seen[url]
                # Keep higher score + apply dedup bonus (cap at 100)
                if job.match.score >= existing.match.score:
                    boosted = copy.copy(job)
                    boosted.match = job.match.model_copy(
                        update={"score": min(100, job.match.score + _AUTO_SEARCH_DEDUP_BONUS)}
                    )
                    seen[url] = boosted
                else:
                    existing.match = existing.match.model_copy(
                        update={"score": min(100, existing.match.score + _AUTO_SEARCH_DEDUP_BONUS)}
                    )
            else:
                seen[url] = job
    return sorted(seen.values(), key=lambda j: j.match.score, reverse=True)


@router.post(
    "/auto-search",
    response_model=AutoSearchResponse,
    summary="Automatically search jobs using top suggestions from the master profile",
)
async def auto_search_jobs(location: str = "Munich, Germany") -> AutoSearchResponse:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload your resume first via POST /profile/ingest.",
        )

    suggestions = profile.job_suggestions
    if not suggestions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No job suggestions found in profile. Re-import your resume to generate them.",
        )

    top = suggestions[:_AUTO_SEARCH_MAX_QUERIES]

    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=_AUTO_SEARCH_MAX_QUERIES) as pool:
        futures = {
            pool.submit(_run_one, profile, s.title, s.keywords, location): s.title
            for s in top
        }
        all_results: list[tuple[str, list[RankedJob]]] = []
        for future in as_completed(futures):
            try:
                title, jobs = future.result()
                all_results.append((title, jobs))
            except Exception:
                # One failed query doesn't abort the whole auto-search
                pass

    if not all_results:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="All search queries failed. Check your search provider configuration.",
        )

    deduplicated = _deduplicate(all_results)
    queries_used = [t for t, _ in all_results]
    return AutoSearchResponse(results=deduplicated, queries_used=queries_used)
