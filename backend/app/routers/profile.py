from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, UploadFile, status

from app.models.ingestion import HITLResolution, IngestionResponse, IngestionStatus
from app.models.profile import ProfileMaster
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services.extractors import extract_text
from app.services.ingestion import IngestionService

router = APIRouter(prefix="/profile", tags=["profile"])

_repo = ProfileRepository()
_ingestion = IngestionService()

_SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".html", ".htm")


@router.post(
    "/ingest",
    response_model=IngestionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a resume (PDF, DOCX, or HTML) and start the ingestion pipeline",
)
async def ingest_resume(file: UploadFile) -> IngestionResponse:
    if not file.filename or not file.filename.lower().endswith(_SUPPORTED_EXTENSIONS):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Unsupported file type. Accepted: {', '.join(_SUPPORTED_EXTENSIONS)}",
        )

    content = await file.read()
    try:
        resume_text = extract_text(file.filename, content)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Run the blocking LLM calls in a thread so the event loop stays free
    result = await asyncio.get_event_loop().run_in_executor(
        None, _ingestion.run, file.filename, resume_text
    )

    if result.status == IngestionStatus.COMPLETED and result.profile:
        _repo.save(result.profile)

    return result


@router.post(
    "/ingest/resolve",
    response_model=IngestionResponse,
    summary="Submit human-provided values to complete a paused ingestion",
)
async def resolve_hitl(resolution: HITLResolution) -> IngestionResponse:
    """
    Applies the user's metric corrections to the partial profile stored in the
    HITL request, re-validates, and persists if successful.
    """
    if not _repo.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No partial profile found. Run /ingest first.",
        )

    profile = _repo.load()

    for field_path, value in resolution.resolved_fields.items():
        parts = field_path.split(".")
        # Navigate to the parent object and set the leaf field
        obj: object = profile
        for part in parts[:-1]:
            if part.isdigit():
                obj = obj[int(part)]  # type: ignore[index]
            else:
                obj = getattr(obj, part)
        leaf = parts[-1]
        if leaf.isdigit():
            obj[int(leaf)] = value  # type: ignore[index]
        else:
            setattr(obj, leaf, value)

    _repo.save(profile)
    return IngestionResponse(
        ingestion_id=resolution.ingestion_id,
        status=IngestionStatus.COMPLETED,
        profile=profile,
    )


@router.get(
    "/",
    response_model=ProfileMaster,
    summary="Return the current master profile",
)
async def get_profile() -> ProfileMaster:
    try:
        return _repo.load()
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put(
    "/",
    response_model=ProfileMaster,
    summary="Replace the master profile (used after HITL editing in the UI)",
)
async def update_profile(profile: ProfileMaster) -> ProfileMaster:
    _repo.save(profile)
    return profile


@router.delete(
    "/",
    status_code=status.HTTP_204_NO_CONTENT,
    response_model=None,
    summary="Delete the stored profile",
)
async def delete_profile() -> None:
    _repo.delete()
