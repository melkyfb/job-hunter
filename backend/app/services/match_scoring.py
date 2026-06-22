from __future__ import annotations

import json
from textwrap import dedent

from pydantic import ValidationError

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ProfileMaster


def _build_profile_summary(profile: ProfileMaster) -> str:
    """Compact text representation of the profile sent to the LLM."""
    skills = ", ".join(s.name for s in profile.skills)
    languages = ", ".join(f"{l.name} ({l.proficiency})" for l in profile.languages)

    experiences = []
    for exp in profile.work_experiences:
        bullets = " ".join(a.as_bullet for a in exp.achievements)
        techs = ", ".join(exp.technologies)
        experiences.append(
            f"- {exp.role} at {exp.company}: {bullets} | Tech: {techs}"
        )

    return dedent(f"""
        Name: {profile.contact.full_name}
        Skills: {skills}
        Languages: {languages}
        Experience:
        {chr(10).join(experiences)}
    """).strip()


_SCHEMA = MatchScore.model_json_schema()

_SYSTEM_PROMPT = dedent("""
    You are an expert ATS (Applicant Tracking System) analyst.
    Given a candidate profile and a job description, evaluate compatibility.

    Return a single JSON object with these fields:
    - score (int 0–100): overall ATS compatibility
    - keywords_found (list[str]): keywords from the job that appear in the profile
    - keywords_missing (list[str]): important keywords in the job absent from the profile
    - justification (str): 2–3 sentence explanation of the score

    Be precise. Do not invent keywords. Only include a keyword in keywords_found
    if it genuinely appears in the candidate's profile.
    Return ONLY valid JSON. No markdown, no explanation outside the object.
""").strip()


def score_match(profile: ProfileMaster, job: JobPosting) -> MatchScore:
    """
    Calls the LLM to score how well the candidate's profile matches a job posting.
    Uses the same self-correction pattern as ingestion: retries on ValidationError.
    """
    profile_summary = _build_profile_summary(profile)
    user_message = dedent(f"""
        Candidate Profile:
        {profile_summary}

        Job Title: {job.title}
        Company: {job.company}
        Job Description:
        {job.description}

        Required schema:
        {json.dumps(_SCHEMA, indent=2)}
    """).strip()

    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_message},
    ]

    client = get_llm_client()
    last_error = ""
    last_raw = ""

    for attempt in range(1, settings.llm_max_retries + 1):
        if attempt > 1:
            messages.append({"role": "assistant", "content": last_raw})
            messages.append({
                "role": "user",
                "content": (
                    f"Your response failed validation: {last_error}\n"
                    "Fix the JSON and return only the corrected object."
                ),
            })

        response = client.chat.completions.create(
            model=settings.active_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0,
        )
        last_raw = response.choices[0].message.content or "{}"

        try:
            data = json.loads(last_raw)
            data["job_id"] = str(job.id)
            return MatchScore.model_validate(data)
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)

    raise ValueError(
        f"MatchScoringAgent failed after {settings.llm_max_retries} attempts "
        f"for job '{job.title}': {last_error}"
    )
