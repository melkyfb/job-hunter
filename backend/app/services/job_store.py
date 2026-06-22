"""
Thread-safe in-memory store for async background jobs.
Jobs expire after TTL_SECONDS and are purged lazily on next create_job().
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

JobState = Literal["processing", "completed", "hitl_required", "failed"]

TTL_SECONDS = 600  # 10 minutes


@dataclass
class AsyncJob:
    job_id: str
    status: JobState = "processing"
    step: str = "starting"
    message: str = "Starting…"
    progress: int = 0
    result: Optional[Any] = None
    created_at: float = field(default_factory=time.time)


_store: dict[str, AsyncJob] = {}
_lock = threading.Lock()


def create_job(job_id: str) -> AsyncJob:
    job = AsyncJob(job_id=job_id)
    with _lock:
        _purge_expired()
        _store[job_id] = job
    return job


def get_job(job_id: str) -> Optional[AsyncJob]:
    with _lock:
        return _store.get(job_id)


def update_job(job_id: str, **kwargs: Any) -> None:
    with _lock:
        job = _store.get(job_id)
        if job:
            for k, v in kwargs.items():
                setattr(job, k, v)


def _purge_expired() -> None:
    now = time.time()
    expired = [jid for jid, j in _store.items() if now - j.created_at > TTL_SECONDS]
    for jid in expired:
        del _store[jid]
