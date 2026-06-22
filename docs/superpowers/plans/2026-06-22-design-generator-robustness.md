# Design Generator Robustness — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Harden `design_generator.py` so it (1) rejects non-design prompts before spending tokens, (2) validates LLM output with Pydantic before accepting a generated HTML template, and (3) strips control characters and excessive whitespace from the generated HTML before returning it.

**Architecture:** Two sequential changes to a single file. Task 1 replaces the brittle `_extract_html_template` + `_validate_template` pair with a Pydantic model (`DesignGenerationResponse`), strengthens the system prompts, and adds a `_clean_html()` post-processing step that collapses excessive newlines and removes non-printable control characters. Task 2 adds a lightweight intent-classification call (`_check_design_intent`) that runs before generation and raises `ValueError` with a Portuguese hint if the user's input isn't a design brief.

**Tech Stack:** Python 3.12, Pydantic v2, OpenAI client, Jinja2

## Global Constraints

- Only `backend/app/services/design_generator.py` and `backend/tests/test_services/test_design_generator.py` are modified
- `from __future__ import annotations` stays at top of every Python file
- Pydantic v2: `model_validate_json()`, `model_dump_json()` — never `.dict()`
- `_MAX_RETRIES = 3` stays unchanged
- Existing 5 tests in `test_design_generator.py` must keep passing (fixtures need updating to satisfy new Pydantic rules)
- `response_format={"type": "json_object"}` kept on all LLM calls
- Run tests from `backend/` directory: `cd backend && python -m pytest tests/test_services/test_design_generator.py -v`

---

## File Map

**Modified only:**
- `backend/app/services/design_generator.py` — add `DesignGenerationResponse`, `DesignIntentResponse`, `_check_design_intent()`, `_clean_html()`, update prompts, replace `_extract_html_template`/`_validate_template`, wire intent check and HTML sanitization
- `backend/tests/test_services/test_design_generator.py` — update fixtures to pass new validation rules, add 7 new tests

---

## Task 1: Pydantic validation model + stronger system prompts

**Files:**
- Modify: `backend/app/services/design_generator.py`
- Test: `backend/tests/test_services/test_design_generator.py`

**Interfaces:**
- Removes: `_extract_html_template(raw: str) -> str` (deleted)
- Removes: `_validate_template(template: str, dummy_context: dict) -> Optional[str]` (deleted)
- Adds: `DesignGenerationResponse(BaseModel)` — internal class, not exported
- The public API (`generate_resume_template`, `generate_cover_letter_template`) is unchanged

- [ ] **Step 1: Update test fixtures to satisfy new Pydantic rules**

The existing `_VALID_RESUME_HTML` and `_VALID_CL_HTML` fixtures are too short (< 500 chars) and missing `<meta charset="UTF-8">`. Replace both at the top of `backend/tests/test_services/test_design_generator.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.design_generator import generate_cover_letter_template, generate_resume_template

_VALID_RESUME_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 20mm; }
body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; margin: 0; padding: 0; }
h1 { font-size: 22pt; font-weight: bold; color: #1a3a5c; margin-bottom: 4px; }
h2 { font-size: 13pt; color: #1a3a5c; border-bottom: 1px solid #ccc; padding-bottom: 2px; }
.contact { font-size: 10pt; color: #555; margin-bottom: 12px; }
.section { margin-bottom: 16px; }
.role { font-weight: bold; }
.dates { font-size: 10pt; color: #777; float: right; }
ul { margin: 4px 0; padding-left: 18px; }
li { margin-bottom: 2px; }
.skill-list { display: flex; flex-wrap: wrap; gap: 6px; }
.skill { background: #e8f0fe; padding: 2px 8px; border-radius: 4px; font-size: 10pt; }
</style>
</head>
<body>
<h1>{{ profile.contact.full_name }}</h1>
<div class="contact">
{{ profile.contact.email }}{% if profile.contact.phone %} · {{ profile.contact.phone }}{% endif %}
{% if profile.contact.location %} · {{ profile.contact.location }}{% endif %}
</div>
{% if profile.summary %}<div class="section"><p>{{ profile.summary }}</p></div>{% endif %}
<div class="section">
<h2>Experience</h2>
{% for exp in profile.work_experiences %}
<div>
<span class="role">{{ exp.role }}</span> — {{ exp.company }}
<span class="dates">{{ exp.start_date }} – {{ "Present" if exp.is_current else exp.end_date }}</span>
<ul>{% for a in exp.achievements %}<li>{{ a }}</li>{% endfor %}</ul>
</div>
{% endfor %}
</div>
<div class="section">
<h2>Skills</h2>
<div class="skill-list">{% for sk in profile.skills %}<span class="skill">{{ sk.name }}</span>{% endfor %}</div>
</div>
<div class="section">
<h2>Education</h2>
{% for edu in profile.education %}<p>{{ edu.degree }} — {{ edu.institution }}, {{ edu.end_year }}</p>{% endfor %}
</div>
<div class="section">
<h2>Languages</h2>
{% for lang in profile.languages %}<span>{{ lang.name }} ({{ lang.proficiency }})</span>{% endfor %}
</div>
</body>
</html>"""

_VALID_CL_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
@page { size: A4; margin: 25mm; }
body { font-family: Arial, sans-serif; font-size: 11pt; color: #222; }
h1 { font-size: 18pt; color: #1a3a5c; }
.contact { font-size: 10pt; color: #555; margin-bottom: 20px; }
.header { border-bottom: 2px solid #1a3a5c; padding-bottom: 8px; margin-bottom: 16px; }
.body-text p { margin-bottom: 12px; line-height: 1.6; }
.signature { margin-top: 24px; }
</style>
</head>
<body>
<div class="header">
<h1>{{ profile.contact.full_name }}</h1>
<div class="contact">
{{ profile.contact.email }}{% if profile.contact.phone %} · {{ profile.contact.phone }}{% endif %}
</div>
</div>
<div class="body-text">
{% for para in letter_body.split('\\n\\n') %}<p>{{ para }}</p>{% endfor %}
</div>
<div class="signature"><p>Atenciosamente,<br>{{ profile.contact.full_name }}</p></div>
</body>
</html>"""


def _make_mock_client(html: str):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({"html_template": html})
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client
```

- [ ] **Step 2: Run existing tests to see current baseline**

```
cd backend && python -m pytest tests/test_services/test_design_generator.py -v
```
Expected: 5 passed (all existing tests pass before any changes to the implementation).

- [ ] **Step 3: Write new failing tests for Pydantic validation**

Append these tests to `backend/tests/test_services/test_design_generator.py`:

```python
# ── DesignGenerationResponse Pydantic validation ──────────────────────────────

def test_pydantic_rejects_missing_doctype():
    from pydantic import ValidationError
    from app.services.design_generator import DesignGenerationResponse
    with pytest.raises(ValidationError, match="HTML incompleto"):
        DesignGenerationResponse(html_template="<html><head><meta charset='UTF-8'></head><body>hello world this is a long enough string to pass the length check but missing doctype tag completely</body></html>")


def test_pydantic_rejects_missing_charset():
    from pydantic import ValidationError
    from app.services.design_generator import DesignGenerationResponse
    # Build HTML > 500 chars but without charset meta
    long_html = "<!DOCTYPE html><html><head><style>body{font-family:Arial;}</style></head><body>" + "x" * 450 + "</body></html>"
    with pytest.raises(ValidationError, match="UTF-8"):
        DesignGenerationResponse(html_template=long_html)


def test_pydantic_rejects_too_short():
    from pydantic import ValidationError
    from app.services.design_generator import DesignGenerationResponse
    short_html = '<!DOCTYPE html><html><head><meta charset="UTF-8"></head><body>hi</body></html>'
    with pytest.raises(ValidationError, match="500"):
        DesignGenerationResponse(html_template=short_html)


def test_pydantic_accepts_valid_html():
    from app.services.design_generator import DesignGenerationResponse
    result = DesignGenerationResponse(html_template=_VALID_RESUME_HTML)
    assert "<!DOCTYPE" in result.html_template


def test_clean_html_collapses_excessive_newlines():
    from app.services.design_generator import _clean_html
    dirty = "<!DOCTYPE html>\n\n\n\n\n<html>\n\n\n<body>hello</body></html>"
    result = _clean_html(dirty)
    assert "\n\n\n" not in result
    assert "<!DOCTYPE html>" in result


def test_clean_html_removes_literal_escape_sequences():
    from app.services.design_generator import _clean_html
    dirty = "<!DOCTYPE html><html><body>line1\\nline2\\nline3</body></html>"
    result = _clean_html(dirty)
    assert "\\n" not in result


def test_retry_uses_informative_message_on_pydantic_failure():
    """When Pydantic validation fails, the retry message includes the specific error."""
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    # First response: HTML that fails Pydantic (too short, missing charset)
    bad_html = "<html><head></head><body>short</body></html>"
    mock_client = MagicMock()
    responses = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": bad_html})))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": _VALID_RESUME_HTML})))]),
    ]
    mock_client.chat.completions.create.side_effect = responses

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client):
        result = generate_resume_template("Blue sidebar", profile)

    assert mock_client.chat.completions.create.call_count == 2
    # The second call's messages should contain the error from the first attempt
    second_call_messages = mock_client.chat.completions.create.call_args_list[1][1]["messages"]
    # Find the user correction message
    correction_msgs = [m for m in second_call_messages if m["role"] == "user" and "rejected" in m["content"]]
    assert len(correction_msgs) == 1
```

- [ ] **Step 4: Run new tests to verify they fail**

```
cd backend && python -m pytest tests/test_services/test_design_generator.py::test_pydantic_rejects_missing_doctype tests/test_services/test_design_generator.py::test_pydantic_rejects_missing_charset tests/test_services/test_design_generator.py::test_pydantic_rejects_too_short tests/test_services/test_design_generator.py::test_pydantic_accepts_valid_html tests/test_services/test_design_generator.py::test_retry_uses_informative_message_on_pydantic_failure -v
```
Expected: `ImportError: cannot import name 'DesignGenerationResponse'`

- [ ] **Step 5: Implement the changes in `design_generator.py`**

Replace the entire file content with:

```python
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
```

- [ ] **Step 6: Run all tests**

```
cd backend && python -m pytest tests/test_services/test_design_generator.py -v
```
Expected: 12 PASSED (5 existing + 7 new: 4 Pydantic + 2 clean_html + 1 retry message)

- [ ] **Step 7: Commit**

```
git add backend/app/services/design_generator.py backend/tests/test_services/test_design_generator.py
git commit -m "feat: replace _extract_html_template with DesignGenerationResponse Pydantic validation + stronger prompts"
```

---

## Task 2: Intent check integration

**Files:**
- Modify: `backend/tests/test_services/test_design_generator.py` (add 3 new tests)
- No implementation needed — `_check_design_intent` was already implemented in Task 1

**Interfaces:**
- Consumes: `_check_design_intent(prompt: str) -> None` (Task 1), `DesignIntentResponse` (Task 1)
- The intent check is already wired into both `generate_resume_template` and `generate_cover_letter_template` from Task 1

Note: `_check_design_intent` and `DesignIntentResponse` were implemented together with the Pydantic changes in Task 1 because they live in the same file and the generation loop depends on both. Task 2 is the test-only task that verifies the intent-check behavior end-to-end.

- [ ] **Step 1: Write failing tests for intent check behavior**

Append to `backend/tests/test_services/test_design_generator.py`:

```python
# ── Intent check integration ──────────────────────────────────────────────────

def _make_intent_mock(is_design: bool, hint: str = "") -> MagicMock:
    """Returns a mock LLM client whose first call returns an intent response."""
    mock_client = MagicMock()
    intent_response = MagicMock()
    intent_response.choices[0].message.content = json.dumps({
        "is_design_prompt": is_design,
        "hint": hint,
    })
    mock_client.chat.completions.create.return_value = intent_response
    return mock_client


def test_intent_check_rejects_non_design_prompt():
    """generate_resume_template raises ValueError with hint when prompt is not a design brief."""
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    hint = "Descreva o visual: cores, fontes, layout de colunas, estilo profissional ou criativo."
    mock_client = _make_intent_mock(is_design=False, hint=hint)

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client):
        with pytest.raises(ValueError, match="Descreva o visual"):
            generate_resume_template("olá", profile)

    # Only ONE LLM call made (the intent check) — generation was never started
    assert mock_client.chat.completions.create.call_count == 1


def test_intent_check_passes_design_prompt():
    """When intent check approves, generation proceeds normally."""
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    mock_client = MagicMock()
    # First call: intent check returns True
    intent_resp = MagicMock()
    intent_resp.choices[0].message.content = json.dumps({"is_design_prompt": True, "hint": ""})
    # Second call: generation returns valid HTML
    gen_resp = MagicMock()
    gen_resp.choices[0].message.content = json.dumps({"html_template": _VALID_RESUME_HTML})
    mock_client.chat.completions.create.side_effect = [intent_resp, gen_resp]

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client):
        result = generate_resume_template("Sidebar azul escuro, fonte sans-serif, layout limpo", profile)

    assert "<!DOCTYPE" in result
    assert mock_client.chat.completions.create.call_count == 2  # intent + generation


def test_intent_check_cover_letter_rejects_non_design():
    """generate_cover_letter_template also raises ValueError on non-design input."""
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    hint = "Descreva o visual da carta: cores, fontes, estilo."
    mock_client = _make_intent_mock(is_design=False, hint=hint)

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client):
        with pytest.raises(ValueError, match="Descreva o visual"):
            generate_cover_letter_template("test", profile, inherit_from_html=None)

    assert mock_client.chat.completions.create.call_count == 1
```

- [ ] **Step 2: Run new tests to verify they fail**

```
cd backend && python -m pytest tests/test_services/test_design_generator.py::test_intent_check_rejects_non_design_prompt tests/test_services/test_design_generator.py::test_intent_check_passes_design_prompt tests/test_services/test_design_generator.py::test_intent_check_cover_letter_rejects_non_design -v
```
Expected: 3 FAILED (the implementation from Task 1 is already there, but these are the tests verifying behavior — they should PASS because Task 1 already wired the intent check)

> Note: If all 3 already PASS (because Task 1 implemented `_check_design_intent` correctly), that is the expected outcome. The "failing" step here validates the test structure, not a missing implementation.

- [ ] **Step 3: Run the full test suite**

```
cd backend && python -m pytest tests/test_services/test_design_generator.py -v
```
Expected: 15 PASSED (5 original + 7 from Task 1 + 3 new)

- [ ] **Step 4: Commit**

```
git add backend/tests/test_services/test_design_generator.py
git commit -m "test: add intent check + Pydantic validation integration tests for design_generator"
```

---

## Self-Review

**Spec coverage:**

| Spec requirement | Task |
|---|---|
| Intent check rejects non-design prompts | Task 1 (`_check_design_intent`) + Task 2 (tests) |
| Intent check returns Portuguese hint | Task 1 (`_INTENT_SYSTEM_PROMPT` + fallback hint) |
| Intent check raises `ValueError(hint)` | Task 1 (wired in both public functions) |
| `DesignGenerationResponse` Pydantic model | Task 1 |
| Validates `<!DOCTYPE`, `<html`, `<head`, `<body`, `</html>` | Task 1 (`must_be_valid_html` validator) |
| Validates min 500 chars | Task 1 |
| Validates UTF-8 meta tag | Task 1 |
| Removes `_extract_html_template` | Task 1 (deleted, replaced by `_parse_and_validate`) |
| Removes `_validate_template` | Task 1 (deleted, merged into `_parse_and_validate`) |
| Stronger system prompts with OUTPUT RULES | Task 1 (`_OUTPUT_RULES` constant) |
| Informative retry message with specific error | Task 1 (retry message includes `last_error`) |
| Jinja2 validation still runs | Task 1 (`_parse_and_validate` calls `render_template_to_html`) |
| Existing tests keep passing | Task 1 (fixtures updated to pass new rules) |
| `response_format={"type": "json_object"}` on intent call | Task 1 |

All spec requirements covered. No placeholders. Type consistency: `_check_design_intent` takes `str`, returns `None`, raises `ValueError` — consistent across Task 1 implementation and Task 2 tests.
