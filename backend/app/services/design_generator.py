from __future__ import annotations

import json
import re
from textwrap import dedent
from typing import Optional

from pydantic import BaseModel, ValidationError, field_validator

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.profile import ProfileMaster
from app.services.playwright_renderer import (
    build_dummy_context,
    build_dummy_cover_letter_context,
    render_template_to_html,
)

_MAX_RETRIES = 3

# ── Pydantic models for LLM responses ────────────────────────────────────────

class DesignGenerationResponse(BaseModel):
    html_template: str

    @field_validator("html_template")
    @classmethod
    def must_be_valid_html(cls, v: str) -> str:
        v = v.strip()
        required_tags = ["<!doctype", "<html", "<head", "<body", "</html>"]
        missing = [tag for tag in required_tags if tag not in v.lower()]
        if missing:
            raise ValueError(f"HTML incompleto — faltando: {missing}")
        if len(v) < 500:
            raise ValueError(
                f"HTML muito curto para ser um template completo: {len(v)} chars (mínimo 500)"
            )
        if "<meta charset" not in v.lower() and "utf-8" not in v.lower():
            raise ValueError('HTML deve incluir <meta charset="UTF-8"> no <head>')
        return v


class DesignIntentResponse(BaseModel):
    is_design_prompt: bool
    hint: str = ""


# ── System prompts ────────────────────────────────────────────────────────────

_OUTPUT_RULES = dedent("""
    CRITICAL OUTPUT RULES — violating any rule causes immediate rejection and retry:
    1. Return ONLY a JSON object: {"html_template": "..."}. No markdown fences. No explanation.
    2. html_template MUST be a complete HTML document starting with <!DOCTYPE html>.
    3. Include <meta charset="UTF-8"> inside <head>.
    4. The HTML MUST contain <html>, <head>, <body>, and </html> tags.
    5. Minimum length: 500 characters of HTML content. Do NOT truncate.
    6. If the design brief is vague, apply sensible professional defaults — always return complete HTML.
    7. Never return partial HTML. If the response would be cut off, simplify the design instead.
    8. Do NOT insert escape sequences like \\n or \\r in text content. Use HTML tags (<br>, <p>) for line breaks.
    9. Do NOT add excessive blank lines between HTML elements. One blank line between logical blocks at most.
""").strip()

_RESUME_SYSTEM_PROMPT = dedent(f"""
    {_OUTPUT_RULES}

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
    1. Complete self-contained HTML with DOCTYPE and <meta charset="UTF-8">
    2. CSS must include: @page {{ size: A4; margin: 0; }}
    3. Inline CSS only — no <link> tags, no @import, no Google Fonts. Use system fonts only:
       Arial, Helvetica, Georgia, 'Times New Roman', Courier, Verdana, or 'Segoe UI'
    4. Add: -webkit-print-color-adjust: exact; print-color-adjust: exact  (preserve background colours)
    5. Render ALL profile sections. Use {{% if %}} only for optional string fields (phone, location, etc.)
    6. Never add placeholder or fake text — only Jinja2 template variables
    7. Keep body width within 210mm for A4
""").strip()

_COVER_LETTER_SYSTEM_PROMPT = dedent(f"""
    {_OUTPUT_RULES}

    You are an expert cover letter designer. Generate a complete Jinja2 HTML template for an A4 cover letter PDF.

    JINJA2 CONTEXT:
    profile.contact.full_name, .email, .phone, .location  → str
    letter_body  → str, multi-paragraph, split with: letter_body.split('\\n\\n')
    job.title, job.company  → str

    HTML REQUIREMENTS: same as resume — A4, inline CSS only, system fonts, self-contained,
    <meta charset="UTF-8">, no external resources, minimum 500 characters.
""").strip()

_INTENT_SYSTEM_PROMPT = dedent("""
    You are a strict classifier. Determine if the user's text is a resume or cover letter design brief.
    A design brief describes visual aspects: layout, colors, fonts, columns, sections, style, or aesthetic.
    Examples of design briefs: "sidebar azul escuro à esquerda", "two-column modern layout", "minimalist black and white".
    Examples of non-design input: "olá", "qualquer coisa", "faça bonito", "test", "ok".

    Return ONLY a JSON object — no markdown, no explanation:
    {"is_design_prompt": true, "hint": ""}
    If it IS a design brief → is_design_prompt=true, hint="".
    If it is NOT a design brief → is_design_prompt=false, hint="<short Portuguese suggestion>".
    The hint must be a helpful suggestion in Portuguese telling the user what to describe,
    e.g.: "Descreva o visual: cores, fontes, layout de colunas, estilo profissional ou criativo."
""").strip()


# ── Intent check ──────────────────────────────────────────────────────────────

def _check_design_intent(prompt: str) -> None:
    """Raises ValueError with a hint if the prompt is not a design brief."""
    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.active_model,
        messages=[
            {"role": "system", "content": _INTENT_SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.0,
    )
    raw = response.choices[0].message.content or "{}"
    try:
        result = DesignIntentResponse.model_validate_json(raw)
    except (ValidationError, Exception):
        # If the classifier itself fails, allow generation to proceed
        return
    if not result.is_design_prompt:
        hint = result.hint or (
            "Descreva o visual do currículo: cores, fontes, número de colunas, "
            "estilo (moderno, clássico, criativo) e seções desejadas."
        )
        raise ValueError(hint)


# ── HTML post-processing ──────────────────────────────────────────────────────

def _clean_html(html: str) -> str:
    """Remove control characters and collapse excessive whitespace from generated HTML."""
    import re
    # Remove non-printable control characters except tab (\x09) and newline (\x0a)
    html = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f\x7f]", "", html)
    # Replace literal escape sequences \n and \r that the LLM may have written as text
    html = html.replace("\\n", " ").replace("\\r", "")
    # Collapse 3+ consecutive newlines to 2 (one blank line max)
    html = re.sub(r"\n{3,}", "\n\n", html)
    return html


# ── Generation helpers ────────────────────────────────────────────────────────

def _parse_and_validate(raw: str, dummy_ctx: dict) -> tuple[str, str]:
    """
    Returns (template, error_message).
    template is set and error_message is "" on success.
    template is "" and error_message is set on failure.
    """
    try:
        parsed = DesignGenerationResponse.model_validate_json(raw)
    except (ValidationError, Exception) as exc:
        return "", str(exc)

    template = _clean_html(parsed.html_template)

    try:
        render_template_to_html(template, dummy_ctx)
    except Exception as exc:
        return "", f"Jinja2 render error: {exc}"

    return template, ""


# ── Public API ────────────────────────────────────────────────────────────────

def generate_resume_template(prompt: str, profile: ProfileMaster) -> str:
    """
    Call the LLM to generate a Jinja2 HTML resume template from a user's prompt.
    Raises ValueError immediately if the prompt is not a design brief.
    Validates with Pydantic + Jinja2; self-corrects up to _MAX_RETRIES times.
    Raises RuntimeError if all retries fail.
    """
    _check_design_intent(prompt)

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
                    f"Your response was rejected. Reason:\n{last_error}\n\n"
                    'Fix the issue and return a corrected JSON object: {"html_template": "...complete HTML..."}\n'
                    "Remember: complete HTML document, <!DOCTYPE html>, <meta charset=\"UTF-8\">, "
                    "minimum 500 characters, no truncation."
                ),
            })

        response = client.chat.completions.create(
            model=settings.active_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        last_raw = response.choices[0].message.content or ""

        template, last_error = _parse_and_validate(last_raw, dummy_ctx)
        if not last_error:
            return template

    raise RuntimeError(
        f"LLM failed to generate a valid resume template after {_MAX_RETRIES} attempts: {last_error}"
    )


def generate_cover_letter_template(
    prompt: str,
    profile: ProfileMaster,
    inherit_from_html: Optional[str],
) -> str:
    """
    Generate a Jinja2 HTML cover letter template.
    Raises ValueError immediately if the prompt is not a design brief.
    If inherit_from_html is provided, the LLM receives the resume's <style> block
    as a visual baseline to maintain design consistency.
    """
    _check_design_intent(prompt)

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
                "content": (
                    f"Your response was rejected. Reason:\n{last_error}\n\n"
                    'Fix the issue and return a corrected JSON object: {"html_template": "...complete HTML..."}\n'
                    "Remember: complete HTML document, <!DOCTYPE html>, <meta charset=\"UTF-8\">, "
                    "minimum 500 characters, no truncation."
                ),
            })

        response = client.chat.completions.create(
            model=settings.active_model,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.4,
        )
        last_raw = response.choices[0].message.content or ""

        template, last_error = _parse_and_validate(last_raw, dummy_ctx)
        if not last_error:
            return template

    raise RuntimeError(
        f"LLM failed to generate a valid cover letter template after {_MAX_RETRIES} attempts: {last_error}"
    )
