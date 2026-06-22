from __future__ import annotations

import logging
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.models.ingestion import HITLResolution, IngestionResponse, IngestionStatus
from app.models.profile import ProfileMaster
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services.default_designs import seed_default_designs
from app.services.extractors import extract_text
from app.services.ingestion import IngestionService
from app.services import job_store as store
from app.services.suggestions import generate_suggestions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])

_repo = ProfileRepository()
_ingestion = IngestionService()

_SUPPORTED_EXTENSIONS = (".pdf", ".docx", ".html", ".htm")


# ── Shared async-job response schema ─────────────────────────────────────────

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


def _job_to_response(job: store.AsyncJob) -> AsyncJobStatus:
    return AsyncJobStatus(
        job_id=job.job_id,
        status=job.status,
        step=job.step,
        message=job.message,
        progress=job.progress,
        result=job.result,
    )


# ── Helper: run suggestions and finalise a completed ingest job ───────────────

def _finalise_with_suggestions(job_id: str, profile: ProfileMaster) -> None:
    store.update_job(job_id, step="suggestions", message="Generating job suggestions…", progress=80)
    suggestions = generate_suggestions(profile)
    profile.job_suggestions = suggestions
    _repo.save(profile)
    store.update_job(job_id, status="completed", step="done", message="Profile ready!", progress=100)


# ── Ingest ────────────────────────────────────────────────────────────────────

@router.post(
    "/ingest",
    response_model=AsyncJobStart,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload a resume and start ingestion in the background",
)
async def ingest_resume(file: UploadFile) -> AsyncJobStart:
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

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, step="extracting", message="Extracting text from your file…", progress=10)

    filename = file.filename  # capture before thread

    def _run() -> None:
        def ingest_progress(step: str, message: str, pct: int) -> None:
            store.update_job(job_id, step=step, message=message, progress=pct)

        result = _ingestion.run(filename, resume_text, ingest_progress)

        if result.status == IngestionStatus.COMPLETED and result.profile:
            _repo.delete_partial()
            # Run suggestions + template seeding concurrently
            with ThreadPoolExecutor(max_workers=2) as pool:
                suggestions_future = pool.submit(generate_suggestions, result.profile)
                templates_future = pool.submit(seed_default_designs)
            suggestions = suggestions_future.result()
            try:
                templates = templates_future.result()
            except Exception as exc:
                logger.warning("seed_default_designs failed: %s", exc)
                templates = []
            store.update_job(job_id, step="suggestions", message="Generating job suggestions…", progress=80)
            result.profile.job_suggestions = suggestions
            if templates:
                result.profile.design_versions = templates
                result.profile.active_resume_design_id = templates[0].id
            _repo.save(result.profile)
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Profile ready!",
                progress=100,
                result=result.model_dump(mode="json"),
            )
        elif result.status == IngestionStatus.HITL_REQUIRED and result.hitl_request:
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


# ── HITL resolve ──────────────────────────────────────────────────────────────

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

    _repo.delete_partial()

    job_id = str(uuid.uuid4())
    ingestion_id = resolution.ingestion_id
    store.create_job(job_id)
    store.update_job(job_id, step="suggestions", message="Generating job suggestions…", progress=20)

    def _run() -> None:
        # Run suggestions + template seeding concurrently
        with ThreadPoolExecutor(max_workers=2) as pool:
            suggestions_future = pool.submit(generate_suggestions, profile)
            templates_future = pool.submit(seed_default_designs)

        suggestions = suggestions_future.result()
        try:
            templates = templates_future.result()
        except Exception as exc:
            logger.warning("seed_default_designs failed in resolve: %s", exc)
            templates = []

        profile.job_suggestions = suggestions
        if templates:
            profile.design_versions = templates
            profile.active_resume_design_id = templates[0].id

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


# ── Profile CRUD ──────────────────────────────────────────────────────────────

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
