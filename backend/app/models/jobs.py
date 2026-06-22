from __future__ import annotations

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class JobPosting(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    title: str
    company: str
    location: str
    description: str
    url: str
    source: str = Field(description="E.g.: 'serpapi', 'linkedin_rss', 'adzuna'")
    posted_at: Optional[datetime] = None
    salary_range: Optional[str] = None
    required_skills: list[str] = Field(default_factory=list)
    employment_type: Optional[str] = None


class MatchScore(BaseModel):
    job_id: UUID
    score: int = Field(ge=0, le=100, description="ATS compatibility score 0–100")
    keywords_found: list[str] = Field(
        description="Keywords from the job that match the candidate's profile"
    )
    keywords_missing: list[str] = Field(
        description="Keywords required by the job that are absent from the profile"
    )
    justification: str = Field(
        description="LLM explanation of the score in 2–3 sentences"
    )


class RankedJob(BaseModel):
    posting: JobPosting
    match: MatchScore
    found_via: Optional[str] = Field(
        default=None,
        description="Query that produced this job (populated by auto-search)",
    )
