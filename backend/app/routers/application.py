from __future__ import annotations

import asyncio
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel

from app.models.jobs import JobPosting, MatchScore
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services.application import generate_application_package, generate_master_resume

router = APIRouter(prefix="/application", tags=["application"])

_repo = ProfileRepository()


class ApplicationPackage(BaseModel):
    job_id: UUID
    resume_pdf_base64: str
    cover_letter_text: str
    cover_letter_pdf_base64: str


class GenerateRequest(BaseModel):
    job: JobPosting
    match: MatchScore
    resume_design_id: Optional[str] = None
    cover_letter_design_id: Optional[str] = None


@router.post(
    "/generate",
    response_model=ApplicationPackage,
    summary="Generate a tailored resume + cover letter for a specific job",
)
async def generate_application(req: GenerateRequest) -> ApplicationPackage:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload your resume first.",
        )

    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_application_package(
                profile, req.job, req.match,
                resume_design_id=req.resume_design_id,
                cover_letter_design_id=req.cover_letter_design_id,
            )
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {exc}",
        )

    return ApplicationPackage(**result)


@router.get(
    "/master-resume",
    summary="Download the master resume PDF (not tailored to any specific job)",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_master_resume() -> Response:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload your resume first.",
        )

    pdf_bytes = await asyncio.get_event_loop().run_in_executor(
        None, generate_master_resume, profile
    )

    filename = f"{profile.contact.full_name.replace(' ', '_')}_Resume.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
