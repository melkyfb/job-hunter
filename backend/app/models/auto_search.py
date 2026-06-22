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
