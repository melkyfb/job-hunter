from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

router = APIRouter(prefix="/application", tags=["application"])


class ApplicationPackage(BaseModel):
    job_id: UUID
    resume_pdf_base64: str
    cover_letter_text: str
    cover_letter_pdf_base64: str


@router.post(
    "/generate",
    response_model=ApplicationPackage,
    summary="Generate a tailored resume + cover letter for a specific job",
)
async def generate_application(job_id: UUID) -> ApplicationPackage:
    # TODO (Phase 5): DynamicResumeAgent + CoverLetterAgent
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="Application generation not yet implemented (Phase 5).",
    )
