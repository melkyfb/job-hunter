from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.models.ingestion import HITLResolution, IngestionResponse, IngestionStatus
from app.models.profile import ProfileMaster
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services.file_processor import compile_reference_text
from app.services.ingestion import IngestionService
from app.services import job_store as store
from app.services.suggestions import generate_suggestions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])

_repo = ProfileRepository()
_ingestion = IngestionService()

_MAX_FILES = 20
_MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB per file


class AsyncJobStart(BaseModel):
    job_id: str
    status: Literal["processing"] = "processing"


class AsyncJobStatus(BaseModel):
    job_id: str
    status: str
    step: str
    message: str
    progress: int
    result: Optional[Any] = None


class UpdatePromptsRequest(BaseModel):
    cv_prompt: Optional[str] = None
    cover_letter_prompt: Optional[str] = None


def _job_to_response(job: store.AsyncJob) -> AsyncJobStatus:
    return AsyncJobStatus(
        job_id=job.job_id,
        status=job.status,
        step=job.step,
        message=job.message,
        progress=job.progress,
        result=job.result,
    )


def _finalise_with_suggestions(job_id: str, profile: ProfileMaster, reference_text: str) -> None:
    store.update_job(job_id, step="suggestions", message="Generating job suggestions…", progress=80)
    suggestions = generate_suggestions(profile)
    profile.job_suggestions = suggestions
    profile.reference_text = reference_text
    _repo.save(profile)


@router.post(
    "/ingest",
    response_model=AsyncJobStart,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload documents and start ingestion in the background",
)
async def ingest_resume(files: list[UploadFile] = File(...)) -> AsyncJobStart:
    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum {_MAX_FILES} files allowed.",
        )
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one file is required.",
        )

    # Read all file content eagerly (must happen in async context)
    file_pairs: list[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        file_pairs.append((upload.filename or "unnamed", content))

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, step="extracting", message="Extracting and filtering documents…", progress=5)

    def _run() -> None:
        def ingest_progress(step: str, message: str, pct: int) -> None:
            # Scale to 10–75 to leave room for suggestions step
            scaled = 10 + int(pct * 0.65)
            store.update_job(job_id, step=step, message=message, progress=scaled)

        store.update_job(job_id, step="extracting", message="Filtering documents for relevant content…", progress=10)
        reference_text = compile_reference_text(file_pairs)

        result = _ingestion.run(reference_text, ingest_progress)

        if result.status == IngestionStatus.COMPLETED and result.profile:
            _repo.delete_partial()
            _finalise_with_suggestions(job_id, result.profile, reference_text)
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Profile ready!",
                progress=100,
                result=result.model_dump(mode="json"),
            )
        elif result.status == IngestionStatus.HITL_REQUIRED and result.hitl_request:
            result.hitl_request.partial_profile.reference_text = reference_text
            _repo.save_partial(result.hitl_request.partial_profile)
            store.update_job(
                job_id,
                status="hitl_required",
                step="hitl",
                message="Missing metrics found — please review.",
                progress=90,
                result=result.model_dump(mode="json"),
            )
        else:
            store.update_job(
                job_id,
                status="failed",
                step="error",
                message=result.error or "Unknown error",
                progress=0,
                result=result.model_dump(mode="json"),
            )

    threading.Thread(target=_run, daemon=True).start()
    return AsyncJobStart(job_id=job_id)


@router.get(
    "/ingest/{job_id}",
    response_model=AsyncJobStatus,
    summary="Poll the status of a background ingest job",
)
async def get_ingest_status(job_id: str) -> AsyncJobStatus:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found or expired.")
    return _job_to_response(job)


@router.post(
    "/ingest/resolve",
    response_model=AsyncJobStart,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit human-provided metrics and resume ingestion in the background",
)
async def resolve_hitl(resolution: HITLResolution) -> AsyncJobStart:
    if not _repo.partial_exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No partial profile found. Run /ingest first.",
        )

    profile = _repo.load_partial()

    for field_path, value in resolution.resolved_fields.items():
        parts = field_path.split(".")
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

    reference_text = profile.reference_text  # preserved from ingest step
    _repo.delete_partial()

    job_id = str(uuid.uuid4())
    ingestion_id = resolution.ingestion_id
    store.create_job(job_id)
    store.update_job(job_id, step="suggestions", message="Generating job suggestions…", progress=20)

    def _run() -> None:
        suggestions = generate_suggestions(profile)
        profile.job_suggestions = suggestions
        _repo.save(profile)
        result = IngestionResponse(
            ingestion_id=ingestion_id,
            status=IngestionStatus.COMPLETED,
            profile=profile,
        )
        store.update_job(
            job_id,
            status="completed",
            step="done",
            message="Profile ready!",
            progress=100,
            result=result.model_dump(mode="json"),
        )

    threading.Thread(target=_run, daemon=True).start()
    return AsyncJobStart(job_id=job_id)


@router.get("/", response_model=ProfileMaster)
async def get_profile() -> ProfileMaster:
    try:
        return _repo.load()
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/", response_model=ProfileMaster)
async def update_profile(profile: ProfileMaster) -> ProfileMaster:
    _repo.save(profile)
    return profile


@router.patch("/prompts", response_model=ProfileMaster)
async def update_prompts(req: UpdatePromptsRequest) -> ProfileMaster:
    try:
        profile = _repo.load()
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if req.cv_prompt is not None:
        profile.cv_prompt = req.cv_prompt
    if req.cover_letter_prompt is not None:
        profile.cover_letter_prompt = req.cover_letter_prompt
    _repo.save(profile)
    return profile


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_profile() -> None:
    _repo.delete()
