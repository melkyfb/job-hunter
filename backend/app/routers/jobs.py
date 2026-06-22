from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.jobs import RankedJob

router = APIRouter(prefix="/jobs", tags=["jobs"])


class JobSearchRequest(BaseModel):
    query: str
    location: str = "Munich, Germany"
    max_results: int = 20


@router.post(
    "/search",
    response_model=list[RankedJob],
    summary="Search for jobs and return them ranked by profile compatibility",
)
async def search_jobs(request: JobSearchRequest) -> list[RankedJob]:
    # TODO (Phase 4): SearchAgent + MatchScoringAgent
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Job search not yet implemented (Phase 4).",
    )
