# backend/app/routers/application.py
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.jobs import JobPosting, MatchScore
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services.application import generate_application_package, generate_master_resume_html

router = APIRouter(prefix="/application", tags=["application"])

_repo = ProfileRepository()


class ApplicationPackage(BaseModel):
    job_id: str
    resume_html: str
    cover_letter_html: str
    cover_letter_text: str


class MasterResumeResponse(BaseModel):
    html: str


class GenerateRequest(BaseModel):
    job: JobPosting
    match: MatchScore


@router.post("/generate", response_model=ApplicationPackage)
async def generate_application(req: GenerateRequest) -> ApplicationPackage:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload your resume first.",
        )
    try:
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: generate_application_package(profile, req.job, req.match),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {exc}",
        )
    return ApplicationPackage(**result)


@router.get("/master-resume", response_model=MasterResumeResponse)
async def download_master_resume() -> MasterResumeResponse:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile found.")

    html = await asyncio.get_running_loop().run_in_executor(
        None, generate_master_resume_html, profile
    )
    return MasterResumeResponse(html=html)
