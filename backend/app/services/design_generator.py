from __future__ import annotations

import json
import re
from textwrap import dedent
from typing import Optional

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.profile import ProfileMaster
from app.services.playwright_renderer import (
    build_dummy_context,
    build_dummy_cover_letter_context,
    render_template_to_html,
)

_MAX_RETRIES = 3

_RESUME_SYSTEM_PROMPT = dedent("""
    You are an expert resume designer. Generate a complete Jinja2 HTML template for an A4 resume PDF.

    JINJA2 CONTEXT — all values are plain strings or lists of dicts:
    profile.contact.full_name, .email, .phone, .location, .linkedin_url, .github_url  → str (empty string if not set)
    profile.summary  → str (empty string if not set)

    profile.work_experiences  → list of dicts with keys:
      role, company, location, start_date, end_date  → str
      is_current  → bool
      achievements  → list of str  (already formatted "action metric context")
      technologies  → list of str

    profile.skills  → list of dicts: name (str), level (str: beginner/intermediate/advanced/expert)
    profile.education  → list of dicts: degree, field_of_study, institution, end_year  → str
    profile.languages  → list of dicts: name, proficiency  → str

    HTML REQUIREMENTS:
    1. Complete self-contained HTML with DOCTYPE
    2. CSS must include: @page { size: A4; margin: 0; }
    3. Inline CSS only — no <link> tags, no @import, no Google Fonts. Use system fonts only:
       Arial, Helvetica, Georgia, 'Times New Roman', Courier, Verdana, or 'Segoe UI'
    4. Add: -webkit-print-color-adjust: exact; print-color-adjust: exact  (preserve background colours)
    5. Render ALL profile sections. Use {% if %} only for optional string fields (phone, location, etc.)
    6. Never add placeholder or fake text — only Jinja2 template variables
    7. Keep body width within 210mm for A4

    OUTPUT FORMAT: Return only a JSON object: {"html_template": "...complete HTML string..."}
    No markdown fences. No explanation. Only JSON.
""").strip()

_COVER_LETTER_SYSTEM_PROMPT = dedent("""
    You are an expert cover letter designer. Generate a complete Jinja2 HTML template for an A4 cover letter PDF.

    JINJA2 CONTEXT:
    profile.contact.full_name, .email, .phone, .location  → str
    letter_body  → str, multi-paragraph, split with: letter_body.split('\\n\\n')
    job.title, job.company  → str

    HTML REQUIREMENTS: same as resume — A4, inline CSS, system fonts, self-contained, no external resources.

    OUTPUT FORMAT: {"html_template": "..."}
""").strip()


def _extract_html_template(raw: str) -> str:
    """Parse JSON wrapper and return the html_template string."""
    try:
        data = json.loads(raw)
        return data["html_template"]
    except (json.JSONDecodeError, KeyError):
        # Fallback: try to extract raw HTML if model forgot JSON wrapper
        match = re.search(r"<!DOCTYPE html>.*</html>", raw, re.DOTALL | re.IGNORECASE)
        if match:
            return match.group(0)
        raise ValueError(f"Could not parse html_template from LLM response: {raw[:200]}")


def _validate_template(template: str, dummy_context: dict) -> Optional[str]:
    """Returns an error string if the template is invalid, None if OK."""
    try:
        render_template_to_html(template, dummy_context)
        return None
    except Exception as exc:
        return str(exc)


def generate_resume_template(prompt: str, profile: ProfileMaster) -> str:
    """
    Call the LLM to generate a Jinja2 HTML resume template from a user's prompt.
    Validates the template renders without errors; self-corrects up to _MAX_RETRIES times.
    Raises RuntimeError if all retries fail.
    """
    client = get_llm_client()
    dummy_ctx = build_dummy_context()
    messages: list[dict] = [
        {"role": "system", "content": _RESUME_SYSTEM_PROMPT},
        {"role": "user", "content": f"Design brief: {prompt}"},
    ]

    last_error = ""
    last_raw = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        if attempt > 1:
            messages.append({"role": "assistant", "content": last_raw})
            messages.append({
                "role": "user",
                "content": (
                    f"The template failed validation with this error:\n{last_error}\n\n"
                    "Fix the Jinja2 syntax and return the corrected JSON."
                ),
            })

        response = client.chat.completions.create(
            model=settings.active_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        last_raw = response.choices[0].message.content or ""

        try:
            template = _extract_html_template(last_raw)
        except ValueError as exc:
            last_error = str(exc)
            continue

        error = _validate_template(template, dummy_ctx)
        if error is None:
            return template
        last_error = error

    raise RuntimeError(f"LLM failed to generate a valid resume template after {_MAX_RETRIES} attempts: {last_error}")


def generate_cover_letter_template(
    prompt: str,
    profile: ProfileMaster,
    inherit_from_html: Optional[str],
) -> str:
    """
    Generate a Jinja2 HTML cover letter template.
    If inherit_from_html is provided, the LLM receives the resume's <style> block
    as a visual baseline to maintain design consistency.
    """
    client = get_llm_client()
    dummy_ctx = build_dummy_cover_letter_context()

    base_css_note = ""
    if inherit_from_html:
        match = re.search(r"<style[^>]*>(.*?)</style>", inherit_from_html, re.DOTALL | re.IGNORECASE)
        if match:
            base_css = match.group(1).strip()
            base_css_note = (
                f"\n\nINHERIT THIS CSS from the user's resume design (adapt it for a letter layout):\n"
                f"<style>\n{base_css}\n</style>"
            )

    messages: list[dict] = [
        {"role": "system", "content": _COVER_LETTER_SYSTEM_PROMPT},
        {"role": "user", "content": f"Design brief: {prompt}{base_css_note}"},
    ]

    last_error = ""
    last_raw = ""
    for attempt in range(1, _MAX_RETRIES + 1):
        if attempt > 1:
            messages.append({"role": "assistant", "content": last_raw})
            messages.append({
                "role": "user",
                "content": f"Validation error: {last_error}\nFix and return corrected JSON.",
            })

        response = client.chat.completions.create(
            model=settings.active_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        last_raw = response.choices[0].message.content or ""

        try:
            template = _extract_html_template(last_raw)
        except ValueError as exc:
            last_error = str(exc)
            continue

        error = _validate_template(template, dummy_ctx)
        if error is None:
            return template
        last_error = error

    raise RuntimeError(f"LLM failed to generate a valid cover letter template after {_MAX_RETRIES} attempts: {last_error}")
