from __future__ import annotations

import base64
import logging
import re

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ProfileMaster

logger = logging.getLogger(__name__)


def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _html_to_pdf(html: str) -> bytes:
    from app.services.playwright_renderer import render_html_to_pdf
    return render_html_to_pdf(html)


def _extract_text_from_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _generate_html(profile: ProfileMaster, job: JobPosting, prompt: str) -> str:
    """Send reference_text + filled prompt to LLM; return raw HTML string."""
    job_desc = f"{job.title} at {job.company}\n\n{job.description or ''}\n\nURL: {job.url or ''}"
    filled = prompt.replace("{JOB_DESCRIPTION}", job_desc)

    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.active_model,
        messages=[
            {
                "role": "user",
                "content": (
                    f"=== REFERENCE FILES ===\n{profile.reference_text}\n\n"
                    f"=== INSTRUCTIONS ===\n{filled}"
                ),
            }
        ],
        temperature=0.3,
    )
    raw = (response.choices[0].message.content or "").strip()
    # Strip markdown fences (```html or ```)
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    return raw.strip()


def generate_application_package(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
) -> dict:
    resume_html = _generate_html(profile, job, profile.cv_prompt)
    resume_pdf = _html_to_pdf(resume_html)

    cl_html = _generate_html(profile, job, profile.cover_letter_prompt)
    cl_pdf = _html_to_pdf(cl_html)

    return {
        "job_id": job.id,
        "resume_pdf_base64": _to_b64(resume_pdf),
        "cover_letter_text": _extract_text_from_html(cl_html),
        "cover_letter_pdf_base64": _to_b64(cl_pdf),
    }


def generate_master_resume(profile: ProfileMaster) -> bytes:
    """Generate a general-purpose resume PDF without tailoring to a specific job."""
    from uuid import uuid4
    from app.models.jobs import JobPosting
    generic_job = JobPosting(
        id=uuid4(),
        title="General Application",
        company="",
        location="",
        description="General purpose — showcase all experience and skills.",
        url="",
        source="master",
    )
    html = _generate_html(profile, generic_job, profile.cv_prompt)
    return _html_to_pdf(html)
