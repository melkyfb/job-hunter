from __future__ import annotations

import asyncio
import re
import threading
import threading as _threading
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from app.models.design import DesignVersion
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services import job_store as store
from app.services.default_designs import seed_default_designs
from app.services.design_generator import generate_cover_letter_template, generate_resume_template
from app.services.playwright_renderer import (
    build_jinja_context,
    render_cover_letter_template_to_html,
    render_html_to_pdf,
    render_template_to_html,
)

router = APIRouter(prefix="/profile/design", tags=["design"])

_repo = ProfileRepository()
_profile_lock = _threading.Lock()


# ── Request / Response models ─────────────────────────────────────────────────

class GenerateResumeDesignRequest(BaseModel):
    prompt: str
    name: str = "My Design"


class GenerateCoverLetterDesignRequest(BaseModel):
    prompt: str
    name: str = "My Cover Letter Design"
    inherit_from_design_id: Optional[str] = None


class DesignPatchRequest(BaseModel):
    name: Optional[str] = None
    is_default: Optional[bool] = None


class AsyncDesignStart(BaseModel):
    job_id: str
    status: Literal["processing"] = "processing"


# ── Helper ────────────────────────────────────────────────────────────────────

def _find_version(profile: Any, design_id: str) -> DesignVersion:
    for v in profile.design_versions:
        if v.id == design_id:
            return v
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Design '{design_id}' not found.")


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/resume", response_model=AsyncDesignStart, status_code=status.HTTP_202_ACCEPTED)
async def generate_resume_design(req: GenerateResumeDesignRequest) -> AsyncDesignStart:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="No profile found.")

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, step="generating", message="Generating your resume design…", progress=20)

    name = req.name
    prompt = req.prompt

    def _run() -> None:
        try:
            html_template = generate_resume_template(prompt)
            version = DesignVersion(
                name=name,
                prompt=prompt,
                type="resume",
                html_template=html_template,
            )
            with _profile_lock:
                p = _repo.load()
                p.design_versions.append(version)
                _repo.save(p)
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Design ready!",
                progress=100,
                result=version.model_dump(mode="json"),
            )
        except Exception as exc:
            store.update_job(job_id, status="failed", step="error", message=str(exc), progress=0)

    threading.Thread(target=_run, daemon=True).start()
    return AsyncDesignStart(job_id=job_id)


@router.post("/cover-letter", response_model=AsyncDesignStart, status_code=status.HTTP_202_ACCEPTED)
async def generate_cover_letter_design(req: GenerateCoverLetterDesignRequest) -> AsyncDesignStart:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="No profile found.")

    inherit_html: Optional[str] = None
    if req.inherit_from_design_id:
        for v in profile.design_versions:
            if v.id == req.inherit_from_design_id and v.type == "resume":
                inherit_html = v.html_template
                break

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, step="generating", message="Generating your cover letter design…", progress=20)

    name = req.name
    prompt = req.prompt
    inherit_from_design_id = req.inherit_from_design_id

    def _run() -> None:
        try:
            html_template = generate_cover_letter_template(prompt, profile, inherit_html)
            version = DesignVersion(
                name=name,
                prompt=prompt,
                type="cover_letter",
                html_template=html_template,
                inherit_from_design_id=inherit_from_design_id,
            )
            with _profile_lock:
                p = _repo.load()
                p.design_versions.append(version)
                _repo.save(p)
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Cover letter design ready!",
                progress=100,
                result=version.model_dump(mode="json"),
            )
        except Exception as exc:
            store.update_job(job_id, status="failed", step="error", message=str(exc), progress=0)

    threading.Thread(target=_run, daemon=True).start()
    return AsyncDesignStart(job_id=job_id)


# ── Helper: is this a default (numbered) design name? ────────────────────────

_DEFAULT_NAME_RE = re.compile(r"^\d+\. ")


# ── New endpoints ─────────────────────────────────────────────────────────────

@router.post("/seed-defaults", response_model=AsyncDesignStart, status_code=status.HTTP_202_ACCEPTED)
async def seed_default_designs_endpoint() -> AsyncDesignStart:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="No profile found.")

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, step="designs", message="Gerando designs padrão…", progress=5)

    def _run() -> None:
        try:
            def _progress(done: int, total: int) -> None:
                store.update_job(
                    job_id,
                    step="designs",
                    message=f"Gerando designs padrão… ({done}/{total})",
                    progress=int(done / total * 90),
                )

            new_designs = seed_default_designs(progress_fn=_progress)

            with _profile_lock:
                p = _repo.load()
                # Remove existing default (numbered) designs
                p.design_versions = [v for v in p.design_versions if not _DEFAULT_NAME_RE.match(v.name)]
                p.design_versions.extend(new_designs)
                if new_designs:
                    p.active_resume_design_id = new_designs[0].id
                _repo.save(p)

            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Designs padrão gerados!",
                progress=100,
                result=[v.model_dump(mode="json") for v in new_designs],
            )
        except Exception as exc:
            store.update_job(job_id, status="failed", step="error", message=str(exc), progress=0)

    threading.Thread(target=_run, daemon=True).start()
    return AsyncDesignStart(job_id=job_id)


@router.post("/{design_id}/regenerate", response_model=AsyncDesignStart, status_code=status.HTTP_202_ACCEPTED)
async def regenerate_design(design_id: str) -> AsyncDesignStart:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="No profile found.")

    version = _find_version(profile, design_id)
    if not version.prompt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="This design has no stored prompt and cannot be regenerated.",
        )

    prompt = version.prompt

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, step="generating", message="Regenerating design…", progress=20)

    def _run() -> None:
        try:
            new_html = generate_resume_template(prompt, skip_intent_check=True)
            with _profile_lock:
                p = _repo.load()
                target = _find_version(p, design_id)
                target.html_template = new_html
                _repo.save(p)
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Design regenerated!",
                progress=100,
                result={"design_id": design_id},
            )
        except Exception as exc:
            store.update_job(job_id, status="failed", step="error", message=str(exc), progress=0)

    threading.Thread(target=_run, daemon=True).start()
    return AsyncDesignStart(job_id=job_id)


@router.get("/{design_id}/preview-html", response_class=HTMLResponse)
async def preview_design_html(design_id: str) -> HTMLResponse:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="No profile found.")

    version = _find_version(profile, design_id)
    ctx = build_jinja_context(profile)
    html = render_template_to_html(version.html_template, ctx)
    return HTMLResponse(content=html)


@router.get("/{design_id}/pdf", response_class=Response)
async def download_design_pdf(design_id: str) -> Response:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="No profile found.")

    version = _find_version(profile, design_id)
    ctx = build_jinja_context(profile)
    html = render_template_to_html(version.html_template, ctx)
    loop = asyncio.get_running_loop()
    pdf = await loop.run_in_executor(None, render_html_to_pdf, html)
    filename = f"{profile.contact.full_name.replace(' ', '_')}_{version.name.replace(' ', '_')}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.patch("/{design_id}", response_model=DesignVersion)
async def update_design(design_id: str, req: DesignPatchRequest) -> DesignVersion:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="No profile found.")

    version = _find_version(profile, design_id)
    if req.name is not None:
        version.name = req.name
    if req.is_default is not None:
        if req.is_default:
            for v in profile.design_versions:
                if v.type == version.type:
                    v.is_default = False
        version.is_default = req.is_default
        if req.is_default:
            if version.type == "resume":
                profile.active_resume_design_id = version.id
            else:
                profile.active_cover_letter_design_id = version.id

    _repo.save(profile)
    return version


@router.delete("/{design_id}", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_design(design_id: str) -> None:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=404, detail="No profile found.")

    _find_version(profile, design_id)  # raises 404 if not found
    profile.design_versions = [v for v in profile.design_versions if v.id != design_id]
    if profile.active_resume_design_id == design_id:
        profile.active_resume_design_id = None
    if profile.active_cover_letter_design_id == design_id:
        profile.active_cover_letter_design_id = None
    _repo.save(profile)
