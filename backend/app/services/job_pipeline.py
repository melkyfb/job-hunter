from __future__ import annotations

import logging
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Callable, Optional

from app.models.jobs import JobPosting, RankedJob
from app.models.profile import ProfileMaster
from app.services.job_search import SearchProvider, get_search_provider
from app.services.match_scoring import score_match

logger = logging.getLogger(__name__)

_MIN_SCORE = 30

ProgressFn = Callable[[str, str, int], None]  # (step, message, progress 0-100)


def run_pipeline(
    profile: ProfileMaster,
    query: str,
    location: str,
    max_results: int = 20,
    progress_fn: Optional[ProgressFn] = None,
    provider: Optional[SearchProvider] = None,   # NEW — injected by scheduler
) -> list[RankedJob]:
    """
    Agentic pipeline:
      1. SearchAgent   → fetches job postings from the configured provider
      2. ScoringAgent  → scores each job against the profile (parallel threads)
      3. Rank          → sort by score desc, filter below threshold
    """
    def _p(step: str, message: str, pct: int) -> None:
        if progress_fn:
            progress_fn(step, message, pct)

    # Step 1 — Search
    _p("searching", f'Searching for "{query}" in {location}…', 10)
    _provider = provider if provider is not None else get_search_provider()
    postings: list[JobPosting] = _provider.search(query, location, max_results)
    logger.info("SearchAgent found %d postings", len(postings))

    if not postings:
        _p("done", "No jobs found.", 100)
        return []

    n = len(postings)
    _p("scoring", f"Found {n} jobs. Scoring each against your profile…", 20)

    # Step 2 — Score in parallel (LLM calls are I/O-bound, threads are fine)
    ranked: list[RankedJob] = []
    failed = 0
    completed_count = 0
    count_lock = threading.Lock()

    with ThreadPoolExecutor(max_workers=min(n, 5)) as executor:
        future_to_job = {
            executor.submit(score_match, profile, job): job
            for job in postings
        }
        for future in as_completed(future_to_job):
            job = future_to_job[future]
            try:
                match = future.result()
                ranked.append(RankedJob(posting=job, match=match))
            except Exception as exc:
                failed += 1
                logger.warning("Scoring failed for '%s': %s", job.title, exc)
            with count_lock:
                completed_count += 1
                pct = 20 + int(70 * completed_count / n)
            _p("scoring", f"Scored {completed_count}/{n} jobs…", pct)

    if failed:
        logger.warning("Scoring failed for %d/%d jobs", failed, n)

    # Step 3 — Filter and rank
    ranked = [r for r in ranked if r.match.score >= _MIN_SCORE]
    ranked.sort(key=lambda r: r.match.score, reverse=True)

    _p("done", f"Done! Showing {len(ranked)} compatible jobs.", 100)
    logger.info("Pipeline complete: %d ranked jobs (min score %d)", len(ranked), _MIN_SCORE)
    return ranked
