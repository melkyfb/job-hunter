from __future__ import annotations

import json
import logging
from textwrap import dedent

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.profile import JobSuggestion, ProfileMaster

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


class _SuggestionsResponse(BaseModel):
    suggestions: list[JobSuggestion]


_SYSTEM_PROMPT = dedent("""
    You are a career advisor. Given a candidate's profile, generate job search suggestions.
    Return ONLY a JSON object with a "suggestions" array. No markdown, no explanation.
    Each suggestion must have "title" (string) and "keywords" (array of 3-5 strings).
""").strip()


def _build_profile_summary(profile: ProfileMaster) -> str:
    roles = [f"{e.role} at {e.company}" for e in profile.work_experiences]
    skills = [s.name for s in profile.skills[:15]]
    techs = list({t for e in profile.work_experiences for t in e.technologies})[:15]
    return dedent(f"""
        Roles: {', '.join(roles)}
        Skills: {', '.join(skills)}
        Technologies: {', '.join(techs)}
        Summary: {profile.summary or 'Not provided'}
    """).strip()


def generate_suggestions(profile: ProfileMaster) -> list[JobSuggestion]:
    """
    Generates up to 20 job title + keyword suggestions from the profile.
    Uses the same self-correction pattern as IngestionService.
    Falls back to an empty list on failure (non-critical path).
    """
    client = get_llm_client()
    profile_summary = _build_profile_summary(profile)

    user_prompt = dedent(f"""
        Generate 20 job search suggestions for this candidate.
        Each must have a "title" and "keywords" (3-5 ATS-relevant terms for that title).

        Candidate profile:
        {profile_summary}

        Return JSON: {{"suggestions": [{{"title": "...", "keywords": ["...", "..."]}}]}}
    """).strip()

    messages: list[dict] = [
        {"role": "system", "content": _SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    last_raw = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        if attempt > 1:
            messages.append({"role": "assistant", "content": last_raw})
            messages.append({
                "role": "user",
                "content": f"That response was invalid. Fix it and return only the JSON object. Error: {last_error}",
            })

        try:
            response = client.chat.completions.create(
                model=settings.active_model,
                messages=messages,
                response_format={"type": "json_object"},
                temperature=0.3,
            )
            last_raw = response.choices[0].message.content or ""
            data = json.loads(last_raw)
            result = _SuggestionsResponse.model_validate(data)
            logger.info("SuggestionsAgent generated %d suggestions", len(result.suggestions))
            return result.suggestions
        except (json.JSONDecodeError, ValidationError) as exc:
            last_error = str(exc)
            logger.warning("SuggestionsAgent attempt %d failed: %s", attempt, last_error)

    logger.error("SuggestionsAgent failed after %d attempts — returning empty list", _MAX_RETRIES)
    return []
