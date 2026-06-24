# backend/app/services/application.py
from __future__ import annotations

import logging
import re

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ProfileMaster
from app.services.prompt_defaults import DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT as DEFAULT_COVER_LETTER_PROMPT

logger = logging.getLogger(__name__)


def _extract_text_from_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _generate_html(profile: ProfileMaster, job: JobPosting, prompt: str, language: str) -> str:
    """Send reference_text + filled prompt to LLM; return raw HTML string."""
    job_desc = f"{job.title} at {job.company}\n\n{job.description or ''}\n\nURL: {job.url or ''}"
    filled = prompt.replace("{JOB_DESCRIPTION}", job_desc)
    if language and language != "English":
        filled = f"Generate the output in {language}.\n\n" + filled

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
        temperature=settings.llm_temperature,
    )
    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    return raw.strip()


def _get_cv_prompt(profile: ProfileMaster) -> str:
    """Returns the active CV prompt: runtime override > profile prompt > module default."""
    return settings.cv_prompt_override or profile.cv_prompt or DEFAULT_CV_PROMPT


def _get_cl_prompt(profile: ProfileMaster) -> str:
    return settings.cl_prompt_override or profile.cover_letter_prompt or DEFAULT_COVER_LETTER_PROMPT


def generate_application_package(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
) -> dict:
    resume_html = _generate_html(profile, job, _get_cv_prompt(profile), settings.cv_language)
    cl_html = _generate_html(profile, job, _get_cl_prompt(profile), settings.cl_language)

    return {
        "job_id": str(job.id),
        "resume_html": resume_html,
        "cover_letter_html": cl_html,
        "cover_letter_text": _extract_text_from_html(cl_html),
    }


def generate_master_resume_html(profile: ProfileMaster) -> str:
    """Generate a general-purpose resume HTML without tailoring to a specific job."""
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
    return _generate_html(profile, generic_job, _get_cv_prompt(profile), settings.cv_language)
