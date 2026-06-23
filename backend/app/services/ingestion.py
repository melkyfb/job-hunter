from __future__ import annotations

import json
import uuid
from textwrap import dedent
from typing import Callable, Optional

from pydantic import ValidationError

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.ingestion import (
    HITLField,
    HITLRequest,
    IngestionResponse,
    IngestionStatus,
)
from app.models.profile import ProfileMaster

ProgressFn = Callable[[str, str, int], None]

_UNKNOWN = "__UNKNOWN__"
_MAX_RETRIES = 3

_SYSTEM_PROMPT = dedent(f"""
    You are a resume parser. Extract the candidate's information from the raw text
    and return it as a single JSON object that strictly follows the given schema.

    Rules:
    1. For each work experience, rewrite every achievement using the XYZ formula:
       "[Action] [Metric] [Context]"
       - action: what was accomplished (e.g. "Reduced API response time")
       - metric: how it was measured (e.g. "by 40%, from 800ms to 480ms")
       - context: how it was done (e.g. "by implementing a Redis caching layer")
    2. If a metric is missing from the original text, set metric to "{_UNKNOWN}".
       Do NOT invent numbers.
    3. All dates must be in ISO 8601 format: YYYY-MM-DD.
    4. Return ONLY the JSON object. No markdown fences, no explanation.
""").strip()

_SCHEMA_HINT = ProfileMaster.model_json_schema()


def _build_user_message(reference_text: str) -> str:
    return dedent(f"""
        Schema to follow:
        {json.dumps(_SCHEMA_HINT, indent=2)}

        Candidate documents:
        {reference_text}
    """).strip()


def _build_correction_message(previous_json: str, error: str) -> str:
    return dedent(f"""
        Your previous response failed validation with this error:
        {error}

        Your previous response was:
        {previous_json}

        Fix the JSON so it matches the schema exactly and return only the corrected object.
    """).strip()


def _call_llm(messages: list[dict]) -> str:
    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.active_model,
        messages=messages,
        response_format={"type": "json_object"},
        temperature=0,
    )
    return response.choices[0].message.content or ""


def _detect_hitl_fields(profile: ProfileMaster) -> list[HITLField]:
    missing: list[HITLField] = []
    for exp_idx, exp in enumerate(profile.work_experiences):
        for ach_idx, ach in enumerate(exp.achievements):
            if _UNKNOWN in ach.metric:
                missing.append(
                    HITLField(
                        field_path=f"work_experiences.{exp_idx}.achievements.{ach_idx}.metric",
                        current_value=None,
                        llm_suggestion=f'What metric quantifies "{ach.action}" at {exp.company}?',
                        reason="No measurable metric found in the original resume text.",
                    )
                )
    return missing


class IngestionService:
    def run(
        self,
        reference_text: str,
        progress_fn: Optional[ProgressFn] = None,
    ) -> IngestionResponse:
        def _p(step: str, message: str, pct: int) -> None:
            if progress_fn:
                progress_fn(step, message, pct)

        ingestion_id = uuid.uuid4()
        _p("analyzing", "Sending to AI for analysis…", 20)

        messages: list[dict] = [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": _build_user_message(reference_text)},
        ]

        last_raw = ""
        last_error = ""

        for attempt in range(1, _MAX_RETRIES + 1):
            if attempt > 1:
                _p("analyzing", f"Retrying analysis (attempt {attempt}/{_MAX_RETRIES})…", 20 + attempt * 8)
                messages.append({"role": "assistant", "content": last_raw})
                messages.append(
                    {"role": "user", "content": _build_correction_message(last_raw, last_error)}
                )

            last_raw = _call_llm(messages)

            try:
                data = json.loads(last_raw)
                profile = ProfileMaster.model_validate(data)
            except (json.JSONDecodeError, ValidationError) as exc:
                last_error = str(exc)
                if attempt == _MAX_RETRIES:
                    return IngestionResponse(
                        ingestion_id=ingestion_id,
                        status=IngestionStatus.FAILED,
                        error=f"Model failed to produce a valid profile after {_MAX_RETRIES} attempts: {last_error}",
                    )
                continue

            _p("validating", "Validating structured output…", 70)

            hitl_fields = _detect_hitl_fields(profile)
            if hitl_fields:
                _p("hitl", "Missing metrics found — please review.", 85)
                return IngestionResponse(
                    ingestion_id=ingestion_id,
                    status=IngestionStatus.HITL_REQUIRED,
                    hitl_request=HITLRequest(
                        ingestion_id=ingestion_id,
                        partial_profile=profile,
                        missing_fields=hitl_fields,
                    ),
                )

            _p("saving", "Finalizing profile…", 90)
            return IngestionResponse(
                ingestion_id=ingestion_id,
                status=IngestionStatus.COMPLETED,
                profile=profile,
            )

        return IngestionResponse(
            ingestion_id=ingestion_id,
            status=IngestionStatus.FAILED,
            error="Unexpected end of ingestion loop.",
        )
