# Resume & Cover Letter Design Customization — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Allow users to describe their desired resume/cover letter design in natural language; the AI generates a Jinja2 HTML+CSS template that Playwright renders to PDF, with multiple saved versions selectable per-job.

**Architecture:** User enters a free-form prompt → backend LLM call generates a complete Jinja2 HTML template (self-contained, A4, inline CSS) → template stored in `ProfileMaster.design_versions[]` → Playwright renders HTML to PDF at download time; preview is served as raw HTML via API.

**Tech Stack:** FastAPI + Pydantic v2, Jinja2, Playwright (Python), ReportLab (existing fallback), React + TypeScript, Vite.

## Global Constraints

- Python 3.12, Pydantic v2 — no `model.dict()`, use `model.model_dump()`
- TypeScript `erasableSyntaxOnly: true` — no parameter properties in constructors; declare class fields explicitly
- All CSS in frontend components must use CSS variables (`var(--accent)`, `var(--border)`, etc.) — no hardcoded hex for UI colours
- Playwright HTML templates: inline CSS only, no external stylesheets, no Google Fonts
- Async job pattern: POST → `{job_id}`, poll `GET /profile/ingest/{job_id}` — reuse existing `job_store.py`
- No breaking changes to existing ReportLab fallback; it remains active when no custom design exists
- Backend working dir: `C:\Users\itsal\ClaudeWorkspace\job-hunter\backend`
- Frontend working dir: `C:\Users\itsal\ClaudeWorkspace\job-hunter\frontend`

---

## File Map

**New backend files:**
- `backend/app/models/design.py` — `DesignVersion` Pydantic model
- `backend/app/services/playwright_renderer.py` — Jinja2 context builder + HTML render + Playwright PDF
- `backend/app/services/design_generator.py` — LLM → Jinja2 template (resume + cover letter, with self-correction)
- `backend/app/routers/design.py` — 6 REST endpoints for design CRUD + preview

**Modified backend files:**
- `backend/app/models/profile.py` — add `design_versions`, `active_resume_design_id`, `active_cover_letter_design_id`
- `backend/app/services/application.py` — accept optional design IDs, use Playwright when present
- `backend/app/routers/application.py` — forward optional design IDs from request body
- `backend/requirements.txt` — add `playwright>=1.44`, `jinja2>=3.1`
- `backend/Dockerfile` — add `RUN playwright install chromium --with-deps`
- `backend/app/main.py` — register `design` router

**New frontend files:**
- `frontend/src/components/DesignEditor.tsx` — prompt textarea + polling progress + iframe preview
- `frontend/src/components/DesignGallery.tsx` — saved versions grid with scaled iFrame thumbnails
- `frontend/src/components/DesignSelector.tsx` — dropdown for choosing design when generating package

**Modified frontend files:**
- `frontend/src/api/client.ts` — `DesignVersion` type, new API functions
- `frontend/src/pages/ProfilePage.tsx` — design editor/gallery sections
- `frontend/src/components/ApplicationGenerator.tsx` — design selector dropdowns

---

## Task 1: Data model + dependencies

**Files:**
- Create: `backend/app/models/design.py`
- Modify: `backend/app/models/profile.py`
- Modify: `backend/requirements.txt`
- Modify: `backend/Dockerfile`
- Test: `backend/tests/test_models/test_design.py`

**Interfaces:**
- Produces: `DesignVersion` (imported by Tasks 2, 3, 4, 5), `ProfileMaster.design_versions: list[DesignVersion]`

- [ ] **Step 1: Create `backend/app/models/design.py`**

```python
from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


class DesignVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str
    prompt: str
    type: Literal["resume", "cover_letter"]
    html_template: str
    inherit_from_design_id: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
    is_default: bool = False
```

- [ ] **Step 2: Write the failing test**

Create `backend/tests/test_models/test_design.py` (create `__init__.py` in the directory if missing):

```python
from app.models.design import DesignVersion


def test_design_version_defaults():
    dv = DesignVersion(
        name="Tech Modern",
        prompt="Clean modern blue",
        type="resume",
        html_template="<html></html>",
    )
    assert dv.id  # uuid assigned
    assert len(dv.id) == 36
    assert dv.is_default is False
    assert dv.inherit_from_design_id is None
    assert dv.created_at is not None


def test_design_version_json_roundtrip():
    dv = DesignVersion(
        name="Cover Blue",
        prompt="Elegant cover letter",
        type="cover_letter",
        html_template="<html><body>{{ letter_body }}</body></html>",
        inherit_from_design_id="abc-123",
        is_default=True,
    )
    restored = DesignVersion.model_validate_json(dv.model_dump_json())
    assert restored.name == "Cover Blue"
    assert restored.inherit_from_design_id == "abc-123"
    assert restored.is_default is True
```

- [ ] **Step 3: Run test to verify it fails**

```
cd backend && pytest tests/test_models/test_design.py -v
```
Expected: `ImportError: cannot import name 'DesignVersion'` (file not created yet — run AFTER Step 1 to confirm it passes).

- [ ] **Step 4: Extend `ProfileMaster` in `backend/app/models/profile.py`**

Add at the top of the imports:
```python
from app.models.design import DesignVersion
```

Add these three fields to `ProfileMaster` (after `job_suggestions`):
```python
design_versions: list[DesignVersion] = Field(
    default_factory=list,
    description="Saved resume and cover letter HTML design templates",
)
active_resume_design_id: Optional[str] = Field(
    default=None,
    description="ID of the DesignVersion used by default for resume generation",
)
active_cover_letter_design_id: Optional[str] = Field(
    default=None,
    description="ID of the DesignVersion used by default for cover letter generation",
)
```

- [ ] **Step 5: Run tests to verify both pass**

```
cd backend && pytest tests/test_models/test_design.py -v
```
Expected: 2 PASSED

- [ ] **Step 6: Add dependencies to `backend/requirements.txt`**

Append two lines:
```
playwright>=1.44
jinja2>=3.1
```

- [ ] **Step 7: Update `backend/Dockerfile`**

After `RUN pip install --no-cache-dir -r requirements.txt`, add:
```dockerfile
RUN playwright install chromium --with-deps
```

Full file after change:
```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium --with-deps

COPY . .

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 8: Install dependencies locally**

```
cd backend && pip install playwright>=1.44 jinja2>=3.1
playwright install chromium
```

- [ ] **Step 9: Commit**

```
git add backend/app/models/design.py backend/app/models/profile.py backend/requirements.txt backend/Dockerfile backend/tests/test_models/test_design.py
git commit -m "feat: add DesignVersion model and ProfileMaster design fields"
```

---

## Task 2: `playwright_renderer.py` — Jinja2 context builder + HTML/PDF render

**Files:**
- Create: `backend/app/services/playwright_renderer.py`
- Test: `backend/tests/test_services/test_playwright_renderer.py`

**Interfaces:**
- Consumes: `ProfileMaster` (Task 1)
- Produces:
  - `build_jinja_context(profile: ProfileMaster) -> dict`
  - `build_dummy_context() -> dict`
  - `build_dummy_cover_letter_context() -> dict`
  - `render_template_to_html(template: str, context: dict) -> str`
  - `render_html_to_pdf(html: str) -> bytes`
  - `render_cover_letter_template_to_html(template: str, profile: ProfileMaster, letter_body: str, job_title: str, job_company: str) -> str`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_services/test_playwright_renderer.py`:

```python
from unittest.mock import MagicMock, patch

from app.services.playwright_renderer import (
    build_dummy_context,
    build_dummy_cover_letter_context,
    render_template_to_html,
    render_html_to_pdf,
    render_cover_letter_template_to_html,
)


def test_render_template_to_html_simple():
    template = "<h1>{{ profile.contact.full_name }}</h1>"
    ctx = build_dummy_context()
    html = render_template_to_html(template, ctx)
    assert "John Doe" in html


def test_render_template_to_html_loop():
    template = "{% for exp in profile.work_experiences %}{{ exp.role }}{% endfor %}"
    ctx = build_dummy_context()
    html = render_template_to_html(template, ctx)
    assert "Engineer" in html


def test_render_cover_letter_template_to_html():
    template = "<p>{{ job.company }}</p>{% for para in letter_body.split('\\n\\n') %}<p>{{ para }}</p>{% endfor %}"
    ctx = build_dummy_cover_letter_context()
    html = render_cover_letter_template_to_html(
        template,
        letter_body="Dear team,\n\nI am excited.",
        job_title="Engineer",
        job_company="Acme",
        contact_name="John Doe",
        contact_email="john@example.com",
    )
    assert "Acme" in html
    assert "excited" in html


def test_render_html_to_pdf_calls_playwright():
    fake_pdf = b"%PDF-fake"
    with patch("app.services.playwright_renderer.sync_playwright") as mock_pw:
        mock_ctx = MagicMock()
        mock_pw.return_value.__enter__.return_value = mock_ctx
        mock_browser = MagicMock()
        mock_ctx.chromium.launch.return_value = mock_browser
        mock_page = MagicMock()
        mock_browser.new_page.return_value = mock_page
        mock_page.pdf.return_value = fake_pdf

        result = render_html_to_pdf("<html></html>")
        assert result == fake_pdf
        mock_page.set_content.assert_called_once()
        mock_page.pdf.assert_called_once_with(format="A4", print_background=True)
        mock_browser.close.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

```
cd backend && pytest tests/test_services/test_playwright_renderer.py -v
```
Expected: `ImportError` (module not yet created)

- [ ] **Step 3: Create `backend/app/services/playwright_renderer.py`**

```python
from __future__ import annotations

from typing import Any

from jinja2 import BaseLoader, Environment, StrictUndefined

from app.models.profile import ProfileMaster


def build_jinja_context(profile: ProfileMaster) -> dict[str, Any]:
    """Converts ProfileMaster into plain-dict context safe for Jinja2 templates."""
    c = profile.contact
    return {
        "profile": {
            "contact": {
                "full_name": c.full_name,
                "email": c.email,
                "phone": c.phone or "",
                "location": c.location or "",
                "linkedin_url": c.linkedin_url or "",
                "github_url": c.github_url or "",
            },
            "summary": profile.summary or "",
            "work_experiences": [
                {
                    "role": exp.role,
                    "company": exp.company,
                    "location": exp.location or "",
                    "start_date": exp.start_date.strftime("%b %Y"),
                    "end_date": "Present" if exp.is_current else (
                        exp.end_date.strftime("%b %Y") if exp.end_date else ""
                    ),
                    "is_current": exp.is_current,
                    "achievements": [ach.as_bullet for ach in exp.achievements],
                    "technologies": exp.technologies,
                }
                for exp in profile.work_experiences
            ],
            "skills": [
                {"name": sk.name, "level": sk.level.value}
                for sk in profile.skills
            ],
            "education": [
                {
                    "degree": edu.degree,
                    "field_of_study": edu.field_of_study,
                    "institution": edu.institution,
                    "end_year": edu.end_date.strftime("%Y") if edu.end_date else "Present",
                }
                for edu in profile.education
            ],
            "languages": [
                {"name": lang.name, "proficiency": lang.proficiency}
                for lang in profile.languages
            ],
        }
    }


def build_dummy_context() -> dict[str, Any]:
    """Minimal fake context for template validation without a real profile."""
    return {
        "profile": {
            "contact": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+49 123 456",
                "location": "Berlin, Germany",
                "linkedin_url": "linkedin.com/in/johndoe",
                "github_url": "github.com/johndoe",
            },
            "summary": "Senior software engineer with 8 years building scalable backends.",
            "work_experiences": [
                {
                    "role": "Senior Backend Engineer",
                    "company": "Acme Corp",
                    "location": "Berlin",
                    "start_date": "Jan 2021",
                    "end_date": "Present",
                    "is_current": True,
                    "achievements": [
                        "Reduced API latency by 40% from 800ms to 480ms by implementing Redis caching.",
                        "Increased test coverage from 42% to 87% by introducing pytest fixtures.",
                    ],
                    "technologies": ["Python", "FastAPI", "Redis", "PostgreSQL"],
                }
            ],
            "skills": [
                {"name": "Python", "level": "expert"},
                {"name": "FastAPI", "level": "advanced"},
            ],
            "education": [
                {
                    "degree": "BSc",
                    "field_of_study": "Computer Science",
                    "institution": "TU Berlin",
                    "end_year": "2016",
                }
            ],
            "languages": [
                {"name": "English", "proficiency": "C1"},
                {"name": "German", "proficiency": "B2"},
            ],
        }
    }


def build_dummy_cover_letter_context() -> dict[str, Any]:
    return {
        "profile": {
            "contact": {
                "full_name": "John Doe",
                "email": "john@example.com",
                "phone": "+49 123 456",
                "location": "Berlin, Germany",
            }
        },
        "letter_body": "Dear Acme team,\n\nI am excited to apply for the Senior Engineer role.\n\nSincerely,\nJohn Doe",
        "job": {"title": "Senior Engineer", "company": "Acme Corp"},
    }


def render_template_to_html(template: str, context: dict[str, Any]) -> str:
    """Render a Jinja2 HTML template string with the given context dict."""
    env = Environment(loader=BaseLoader(), undefined=StrictUndefined)
    t = env.from_string(template)
    return t.render(**context)


def render_cover_letter_template_to_html(
    template: str,
    letter_body: str,
    job_title: str,
    job_company: str,
    contact_name: str,
    contact_email: str,
    contact_phone: str = "",
    contact_location: str = "",
) -> str:
    """Render a cover letter Jinja2 template with letter-specific context."""
    ctx = {
        "profile": {
            "contact": {
                "full_name": contact_name,
                "email": contact_email,
                "phone": contact_phone,
                "location": contact_location,
            }
        },
        "letter_body": letter_body,
        "job": {"title": job_title, "company": job_company},
    }
    return render_template_to_html(template, ctx)


def render_html_to_pdf(html: str) -> bytes:
    """Convert an HTML string to PDF bytes using Playwright + Chromium."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf = page.pdf(format="A4", print_background=True)
        browser.close()
    return pdf
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && pytest tests/test_services/test_playwright_renderer.py -v
```
Expected: 4 PASSED

- [ ] **Step 5: Commit**

```
git add backend/app/services/playwright_renderer.py backend/tests/test_services/test_playwright_renderer.py
git commit -m "feat: add playwright_renderer service (Jinja2 + Playwright PDF)"
```

---

## Task 3: `design_generator.py` — LLM template generation with self-correction

**Files:**
- Create: `backend/app/services/design_generator.py`
- Test: `backend/tests/test_services/test_design_generator.py`

**Interfaces:**
- Consumes: `build_dummy_context()`, `build_dummy_cover_letter_context()`, `render_template_to_html()` (Task 2), `DesignVersion` (Task 1), LLM client
- Produces:
  - `generate_resume_template(prompt: str, profile: ProfileMaster) -> str`
  - `generate_cover_letter_template(prompt: str, profile: ProfileMaster, inherit_from_html: Optional[str]) -> str`

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_services/test_design_generator.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest

from app.services.design_generator import generate_resume_template, generate_cover_letter_template


_VALID_RESUME_HTML = """<!DOCTYPE html><html><head><style>
@page { size: A4; margin: 0; }
body { font-family: Arial; }
</style></head><body>
<h1>{{ profile.contact.full_name }}</h1>
<p>{{ profile.contact.email }}</p>
{% for exp in profile.work_experiences %}
<h2>{{ exp.role }} at {{ exp.company }}</h2>
{% for b in exp.achievements %}<p>{{ b }}</p>{% endfor %}
{% endfor %}
{% for sk in profile.skills %}<span>{{ sk.name }}</span>{% endfor %}
{% for edu in profile.education %}<p>{{ edu.degree }}</p>{% endfor %}
{% for lang in profile.languages %}<p>{{ lang.name }}</p>{% endfor %}
</body></html>"""

_VALID_CL_HTML = """<!DOCTYPE html><html><head><style>
@page { size: A4; margin: 0; }
</style></head><body>
<h1>{{ profile.contact.full_name }}</h1>
{% for para in letter_body.split('\\n\\n') %}<p>{{ para }}</p>{% endfor %}
</body></html>"""


def _make_mock_client(html: str):
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.choices[0].message.content = json.dumps({"html_template": html})
    mock_client.chat.completions.create.return_value = mock_response
    return mock_client


def test_generate_resume_template_returns_valid_html():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    with patch("app.services.design_generator.get_llm_client", return_value=_make_mock_client(_VALID_RESUME_HTML)):
        result = generate_resume_template("Modern blue tech resume", profile)

    assert "<!DOCTYPE html>" in result
    assert "{{ profile.contact.full_name }}" in result


def test_generate_resume_template_self_corrects_on_bad_jinja():
    """First response has broken Jinja2; second response is valid."""
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    bad_html = "<html>{% broken %}</html>"
    mock_client = MagicMock()
    responses = [
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": bad_html})))]),
        MagicMock(choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": _VALID_RESUME_HTML})))]),
    ]
    mock_client.chat.completions.create.side_effect = responses

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client):
        result = generate_resume_template("Modern blue", profile)

    assert mock_client.chat.completions.create.call_count == 2
    assert "<!DOCTYPE html>" in result


def test_generate_resume_template_raises_after_max_retries():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    bad_html = "<html>{% broken %}</html>"
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": bad_html})))]
    )

    with patch("app.services.design_generator.get_llm_client", return_value=mock_client):
        with pytest.raises(RuntimeError, match="failed to generate a valid"):
            generate_resume_template("Modern blue", profile)

    assert mock_client.chat.completions.create.call_count == 3


def test_generate_cover_letter_template_basic():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    with patch("app.services.design_generator.get_llm_client", return_value=_make_mock_client(_VALID_CL_HTML)):
        result = generate_cover_letter_template("Elegant letter", profile, inherit_from_html=None)

    assert "letter_body" in result


def test_generate_cover_letter_template_with_inherited_css():
    from app.models.profile import ProfileMaster, ContactInfo
    profile = ProfileMaster(contact=ContactInfo(full_name="Ada", email="ada@example.com"))

    resume_html = "<html><head><style>.sidebar { background: blue; }</style></head><body></body></html>"

    with patch("app.services.design_generator.get_llm_client", return_value=_make_mock_client(_VALID_CL_HTML)):
        result = generate_cover_letter_template("Match resume", profile, inherit_from_html=resume_html)

    # The inherited CSS is passed to the LLM (we can't assert it's in the output,
    # but we can verify the function completes without error)
    assert result
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && pytest tests/test_services/test_design_generator.py -v
```
Expected: `ImportError`

- [ ] **Step 3: Create `backend/app/services/design_generator.py`**

```python
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
    for attempt in range(1, _MAX_RETRIES + 1):
        if attempt > 1:
            messages.append({"role": "assistant", "content": last_raw})  # type: ignore[possibly-unbound]
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
    for attempt in range(1, _MAX_RETRIES + 1):
        if attempt > 1:
            messages.append({"role": "assistant", "content": last_raw})  # type: ignore[possibly-unbound]
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
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd backend && pytest tests/test_services/test_design_generator.py -v
```
Expected: 5 PASSED

- [ ] **Step 5: Commit**

```
git add backend/app/services/design_generator.py backend/tests/test_services/test_design_generator.py
git commit -m "feat: add design_generator service (LLM → Jinja2 HTML template)"
```

---

## Task 4: `design.py` router — all endpoints

**Files:**
- Create: `backend/app/routers/design.py`
- Modify: `backend/app/main.py`
- Test: `backend/tests/test_routers/test_design.py`

**Interfaces:**
- Consumes: `DesignVersion` (Task 1), `generate_resume_template`, `generate_cover_letter_template` (Task 3), `render_template_to_html`, `render_html_to_pdf`, `build_jinja_context`, `render_cover_letter_template_to_html` (Task 2), `job_store` (existing)
- Produces: REST endpoints consumed by frontend (Tasks 6–9)

- [ ] **Step 1: Write failing tests**

Create `backend/tests/test_routers/test_design.py`:

```python
import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.design import DesignVersion
from app.models.profile import ContactInfo, ProfileMaster

client = TestClient(app)

_PROFILE = ProfileMaster(
    contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com")
)

_VALID_HTML = """<!DOCTYPE html><html><head><style>@page{size:A4;margin:0}</style></head>
<body><h1>{{ profile.contact.full_name }}</h1>
{% for exp in profile.work_experiences %}<p>{{ exp.role }}</p>{% endfor %}
{% for sk in profile.skills %}<span>{{ sk.name }}</span>{% endfor %}
{% for edu in profile.education %}<p>{{ edu.degree }}</p>{% endfor %}
{% for lang in profile.languages %}<p>{{ lang.name }}</p>{% endfor %}
</body></html>"""


def test_post_resume_design_returns_job_id():
    with (
        patch("app.routers.design._repo.load", return_value=_PROFILE),
        patch("app.routers.design._repo.save"),
        patch("app.services.design_generator.get_llm_client", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(create=MagicMock(
                return_value=MagicMock(choices=[MagicMock(message=MagicMock(
                    content=json.dumps({"html_template": _VALID_HTML})
                ))])
            )))
        )),
    ):
        r = client.post("/profile/design/resume", json={"prompt": "Modern blue"})
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "processing"


def test_get_preview_html_returns_rendered_html():
    import time
    from app.services import job_store as store

    version = DesignVersion(
        id="test-id-preview",
        name="Test",
        prompt="Blue",
        type="resume",
        html_template=_VALID_HTML,
    )
    profile_with_design = _PROFILE.model_copy(update={"design_versions": [version]})

    with patch("app.routers.design._repo.load", return_value=profile_with_design):
        r = client.get("/profile/design/test-id-preview/preview-html")
    assert r.status_code == 200
    assert "Ada Lovelace" in r.text
    assert r.headers["content-type"].startswith("text/html")


def test_delete_design_removes_version():
    version = DesignVersion(
        id="test-id-delete",
        name="To Delete",
        prompt="Blue",
        type="resume",
        html_template=_VALID_HTML,
    )
    profile_with_design = _PROFILE.model_copy(update={"design_versions": [version]})

    with (
        patch("app.routers.design._repo.load", return_value=profile_with_design),
        patch("app.routers.design._repo.save") as mock_save,
    ):
        r = client.delete("/profile/design/test-id-delete")
    assert r.status_code == 204
    saved_profile = mock_save.call_args[0][0]
    assert len(saved_profile.design_versions) == 0


def test_patch_design_updates_name():
    version = DesignVersion(
        id="test-id-patch",
        name="Old Name",
        prompt="Blue",
        type="resume",
        html_template=_VALID_HTML,
    )
    profile_with_design = _PROFILE.model_copy(update={"design_versions": [version]})

    with (
        patch("app.routers.design._repo.load", return_value=profile_with_design),
        patch("app.routers.design._repo.save") as mock_save,
    ):
        r = client.patch("/profile/design/test-id-patch", json={"name": "New Name"})
    assert r.status_code == 200
    assert r.json()["name"] == "New Name"


def test_get_preview_html_404_on_unknown_id():
    with patch("app.routers.design._repo.load", return_value=_PROFILE):
        r = client.get("/profile/design/nonexistent-id/preview-html")
    assert r.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd backend && pytest tests/test_routers/test_design.py -v
```
Expected: `ImportError` or 404 errors (router not registered yet)

- [ ] **Step 3: Create `backend/app/routers/design.py`**

```python
from __future__ import annotations

import threading
import uuid
from typing import Any, Literal, Optional

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from app.models.design import DesignVersion
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services import job_store as store
from app.services.design_generator import generate_cover_letter_template, generate_resume_template
from app.services.playwright_renderer import (
    build_jinja_context,
    render_cover_letter_template_to_html,
    render_html_to_pdf,
    render_template_to_html,
)

router = APIRouter(prefix="/profile/design", tags=["design"])

_repo = ProfileRepository()


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

def _find_version(profile, design_id: str) -> DesignVersion:
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
            html_template = generate_resume_template(prompt, profile)
            version = DesignVersion(
                name=name,
                prompt=prompt,
                type="resume",
                html_template=html_template,
            )
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
    pdf = render_html_to_pdf(html)
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
        # Clear other defaults of same type
        if req.is_default:
            for v in profile.design_versions:
                if v.type == version.type:
                    v.is_default = False
        version.is_default = req.is_default
        # Sync active_*_design_id
        if req.is_default:
            if version.type == "resume":
                profile.active_resume_design_id = version.id
            else:
                profile.active_cover_letter_design_id = version.id

    _repo.save(profile)
    return version


@router.delete("/{design_id}", status_code=status.HTTP_204_NO_CONTENT)
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
```

- [ ] **Step 4: Register router in `backend/app/main.py`**

```python
from app.routers import application, config, design, jobs, profile

# add after existing includes:
app.include_router(design.router)
```

- [ ] **Step 5: Run tests**

```
cd backend && pytest tests/test_routers/test_design.py -v
```
Expected: 5 PASSED

- [ ] **Step 6: Commit**

```
git add backend/app/routers/design.py backend/app/main.py backend/tests/test_routers/test_design.py
git commit -m "feat: add design router (resume/cover-letter generate, preview, PDF, CRUD)"
```

---

## Task 5: Wire optional design IDs into application generation

**Files:**
- Modify: `backend/app/services/application.py`
- Modify: `backend/app/routers/application.py`

**Interfaces:**
- Consumes: `render_template_to_html`, `build_jinja_context`, `render_html_to_pdf`, `render_cover_letter_template_to_html` (Task 2)
- Produces: `generate_application_package` accepts `resume_design_id`, `cover_letter_design_id`

- [ ] **Step 1: Modify `backend/app/services/application.py`**

Replace the entire file with:

```python
from __future__ import annotations

import base64
from typing import Optional
from uuid import UUID

from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ProfileMaster
from app.services.cover_letter import generate_cover_letter
from app.services.resume_renderer import render_resume_pdf


def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def generate_application_package(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
    resume_design_id: Optional[str] = None,
    cover_letter_design_id: Optional[str] = None,
) -> dict:
    """
    Generates resume PDF + cover letter PDF.
    If design IDs are provided, uses Playwright + Jinja2 HTML templates.
    Falls back to ReportLab for any missing design.
    """
    resume_pdf = _render_resume(profile, job, match, resume_design_id)
    cover_letter_text = generate_cover_letter(profile, job)
    cover_letter_pdf = _render_cover_letter(
        cover_letter_text, profile, job, cover_letter_design_id
    )

    return {
        "job_id": job.id,
        "resume_pdf_base64": _to_b64(resume_pdf),
        "cover_letter_text": cover_letter_text,
        "cover_letter_pdf_base64": _to_b64(cover_letter_pdf),
    }


def _render_resume(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
    design_id: Optional[str],
) -> bytes:
    """Use custom HTML design if available; fall back to ReportLab."""
    version = _find_design(profile, design_id, "resume")
    if version:
        try:
            from app.services.playwright_renderer import (
                build_jinja_context,
                render_html_to_pdf,
                render_template_to_html,
            )
            ctx = build_jinja_context(profile)
            html = render_template_to_html(version.html_template, ctx)
            return render_html_to_pdf(html)
        except Exception:
            pass  # fall through to ReportLab

    return render_resume_pdf(profile, highlight_keywords=match.keywords_found)


def _render_cover_letter(
    text: str,
    profile: ProfileMaster,
    job: JobPosting,
    design_id: Optional[str],
) -> bytes:
    """Use custom HTML design if available; fall back to ReportLab."""
    version = _find_design(profile, design_id, "cover_letter")
    if version:
        try:
            from app.services.playwright_renderer import (
                render_cover_letter_template_to_html,
                render_html_to_pdf,
            )
            c = profile.contact
            html = render_cover_letter_template_to_html(
                template=version.html_template,
                letter_body=text,
                job_title=job.title,
                job_company=job.company,
                contact_name=c.full_name,
                contact_email=c.email,
                contact_phone=c.phone or "",
                contact_location=c.location or "",
            )
            return render_html_to_pdf(html)
        except Exception:
            pass

    return _render_cover_letter_pdf_reportlab(text, profile)


def _find_design(profile: ProfileMaster, design_id: Optional[str], design_type: str):
    """Find a DesignVersion by ID, or return None."""
    if design_id:
        for v in profile.design_versions:
            if v.id == design_id and v.type == design_type:
                return v
    # Try active default
    active_id = (
        profile.active_resume_design_id
        if design_type == "resume"
        else profile.active_cover_letter_design_id
    )
    if active_id:
        for v in profile.design_versions:
            if v.id == active_id:
                return v
    return None


def generate_master_resume(profile: ProfileMaster, design_id: Optional[str] = None) -> bytes:
    """Generate master resume PDF, using custom design if provided."""
    version = _find_design(profile, design_id, "resume")
    if version:
        try:
            from app.services.playwright_renderer import (
                build_jinja_context,
                render_html_to_pdf,
                render_template_to_html,
            )
            ctx = build_jinja_context(profile)
            html = render_template_to_html(version.html_template, ctx)
            return render_html_to_pdf(html)
        except Exception:
            pass
    return render_resume_pdf(profile, highlight_keywords=None)


def _render_cover_letter_pdf_reportlab(text: str, profile: ProfileMaster) -> bytes:
    from io import BytesIO
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buf = BytesIO()
    doc = SimpleDocTemplate(buf, pagesize=A4, leftMargin=25*mm, rightMargin=25*mm,
                            topMargin=25*mm, bottomMargin=25*mm)
    accent = colors.HexColor("#4f6ef7")
    body_style = ParagraphStyle("body", fontSize=10, fontName="Helvetica",
                                textColor=colors.HexColor("#1a1a1a"), leading=15, spaceAfter=10)
    header_style = ParagraphStyle("header", fontSize=11, fontName="Helvetica-Bold",
                                  textColor=accent, spaceAfter=16)
    story = [
        Paragraph(profile.contact.full_name, header_style),
        Paragraph(profile.contact.email, body_style),
        Spacer(1, 6*mm),
    ]
    for para in text.split("\n\n"):
        para = para.strip()
        if para:
            story.append(Paragraph(para.replace("\n", "<br/>"), body_style))
    doc.build(story)
    return buf.getvalue()
```

- [ ] **Step 2: Modify `backend/app/routers/application.py`**

Add `resume_design_id` and `cover_letter_design_id` to `GenerateRequest`:

```python
class GenerateRequest(BaseModel):
    job: JobPosting
    match: MatchScore
    resume_design_id: Optional[str] = None
    cover_letter_design_id: Optional[str] = None
```

Update the `generate_application` endpoint call:

```python
result = await asyncio.get_event_loop().run_in_executor(
    None,
    lambda: generate_application_package(
        profile, req.job, req.match,
        resume_design_id=req.resume_design_id,
        cover_letter_design_id=req.cover_letter_design_id,
    )
)
```

Add `Optional` import at top: `from typing import Optional`

- [ ] **Step 3: Verify Python syntax**

```
cd backend && python -m py_compile app/services/application.py app/routers/application.py && echo OK
```
Expected: `OK`

- [ ] **Step 4: Commit**

```
git add backend/app/services/application.py backend/app/routers/application.py
git commit -m "feat: wire optional design IDs into application generation (Playwright fallback)"
```

---

## Task 6: `DesignEditor.tsx` — prompt UI + polling + iframe preview

**Files:**
- Create: `frontend/src/components/DesignEditor.tsx`
- Modify: `frontend/src/api/client.ts` — add types + functions

**Interfaces:**
- Consumes: `AsyncJobStart`, `AsyncJobStatus`, polling infrastructure (already used by ResumeUpload)
- Produces: `DesignEditor` component, `DesignVersion` TS type, `startGenerateResumeDesign`, `startGenerateCoverLetterDesign`, `updateDesign`, `deleteDesign`, `getDesignPdfUrl`

- [ ] **Step 1: Add types and API functions to `frontend/src/api/client.ts`**

Add after `AutoSearchResponse`:

```typescript
export interface DesignVersion {
  id: string
  name: string
  prompt: string
  type: 'resume' | 'cover_letter'
  html_template: string
  inherit_from_design_id?: string
  created_at: string
  is_default: boolean
}
```

Update `ProfileMaster` interface — add three fields:
```typescript
  design_versions: DesignVersion[]
  active_resume_design_id: string | null
  active_cover_letter_design_id: string | null
```

Add API functions after `autoSearchJobs`:
```typescript
export async function startGenerateResumeDesign(prompt: string, name: string) {
  return request<AsyncJobStart>('/profile/design/resume', {
    method: 'POST',
    body: JSON.stringify({ prompt, name }),
  })
}

export async function startGenerateCoverLetterDesign(
  prompt: string,
  name: string,
  inheritFromDesignId?: string,
) {
  return request<AsyncJobStart>('/profile/design/cover-letter', {
    method: 'POST',
    body: JSON.stringify({ prompt, name, inherit_from_design_id: inheritFromDesignId }),
  })
}

export async function updateDesign(designId: string, patch: { name?: string; is_default?: boolean }) {
  return request<DesignVersion>(`/profile/design/${designId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function deleteDesign(designId: string) {
  return request<void>(`/profile/design/${designId}`, { method: 'DELETE' })
}

export function getDesignPreviewUrl(designId: string) {
  return `/api/profile/design/${designId}/preview-html`
}

export function getDesignPdfUrl(designId: string) {
  return `/api/profile/design/${designId}/pdf`
}
```

- [ ] **Step 2: Create `frontend/src/components/DesignEditor.tsx`**

```tsx
import { useState } from 'react'
import {
  startGenerateResumeDesign,
  startGenerateCoverLetterDesign,
  updateDesign,
  getDesignPreviewUrl,
  getIngestStatus,
  type DesignVersion,
  type ProfileMaster,
} from '../api/client'

interface Props {
  type: 'resume' | 'cover_letter'
  profile: ProfileMaster
  inheritFromDesignId?: string
  onSaved: (version: DesignVersion) => void
}

const RESUME_PLACEHOLDER = (profile: ProfileMaster) => {
  const role = profile.work_experiences[0]?.role ?? 'professional'
  return `Create a modern, clean resume for a ${role}. Use a two-column layout with a dark left sidebar (deep blue #1e3a5f) showing name, contact, and skills in white. Right side shows experience with bold company names and XYZ bullet points. Section headings in the accent colour. Use Arial font, compact spacing.`
}

const COVER_LETTER_PLACEHOLDER = `Elegant single-column letter on white background. Name and contact at top in a thin header band. Body text in Georgia 11pt with generous line spacing. Subtle bottom border in the accent colour. Professional and warm.`

function ProgressBar({ value }: { value: number }) {
  return (
    <div style={{ width: '100%', height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', marginTop: 8 }}>
      <div style={{ height: '100%', borderRadius: 2, background: 'var(--accent)', width: `${value}%`, transition: 'width 0.4s ease' }} />
    </div>
  )
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

export function DesignEditor({ type, profile, inheritFromDesignId, onSaved }: Props) {
  const [prompt, setPrompt] = useState('')
  const [draftName, setDraftName] = useState('')
  const [state, setState] = useState<'idle' | 'generating' | 'preview'>('idle')
  const [progress, setProgress] = useState(0)
  const [progressMsg, setProgressMsg] = useState('')
  const [previewDesignId, setPreviewDesignId] = useState<string | null>(null)
  const [pendingVersion, setPendingVersion] = useState<DesignVersion | null>(null)
  const [error, setError] = useState('')

  const placeholder = type === 'resume' ? RESUME_PLACEHOLDER(profile) : COVER_LETTER_PLACEHOLDER

  async function handleGenerate() {
    if (!prompt.trim()) return
    setState('generating')
    setError('')
    setProgress(5)
    setProgressMsg('Starting design generation…')

    try {
      const nameToUse = draftName.trim() || (type === 'resume' ? 'My Resume Design' : 'My Cover Letter Design')
      const start = type === 'resume'
        ? await startGenerateResumeDesign(prompt, nameToUse)
        : await startGenerateCoverLetterDesign(prompt, nameToUse, inheritFromDesignId)

      while (true) {
        const status = await getIngestStatus(start.job_id)
        setProgress(status.progress)
        setProgressMsg(status.message)

        if (status.status === 'processing') { await sleep(1500); continue }

        if (status.status === 'completed' && status.result) {
          const version = status.result as DesignVersion
          setPendingVersion(version)
          setPreviewDesignId(version.id)
          setDraftName(version.name)
          setState('preview')
          return
        }

        setError(status.message)
        setState('idle')
        return
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed.')
      setState('idle')
    }
  }

  async function handleSave() {
    if (!pendingVersion) return
    if (draftName.trim() && draftName !== pendingVersion.name) {
      await updateDesign(pendingVersion.id, { name: draftName })
    }
    onSaved({ ...pendingVersion, name: draftName })
    setState('idle')
    setPrompt('')
    setDraftName('')
    setPendingVersion(null)
    setPreviewDesignId(null)
  }

  if (state === 'generating') {
    return (
      <div style={{ padding: '16px 0' }}>
        <p style={{ fontSize: 13, color: 'var(--text-h)', margin: '0 0 4px' }}>{progressMsg}</p>
        <ProgressBar value={progress} />
      </div>
    )
  }

  if (state === 'preview' && previewDesignId) {
    return (
      <div>
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', marginBottom: 12, height: 480 }}>
          <iframe
            src={getDesignPreviewUrl(previewDesignId)}
            style={{ width: '100%', height: '100%', border: 'none' }}
            title="Design preview"
          />
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            value={draftName}
            onChange={e => setDraftName(e.target.value)}
            placeholder="Design name"
            style={{ flex: 1, minWidth: 160, maxWidth: 240, padding: '7px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, background: 'var(--bg)', color: 'var(--text-h)' }}
          />
          <button onClick={handleSave} style={{ padding: '7px 16px', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: 6, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
            Save version
          </button>
          <button onClick={() => setState('idle')} style={{ padding: '7px 12px', background: 'none', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
            Discard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        placeholder={placeholder}
        rows={4}
        style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, background: 'var(--bg)', color: 'var(--text-h)', resize: 'vertical', lineHeight: 1.5, boxSizing: 'border-box' }}
      />
      {error && <p style={{ fontSize: 12, color: '#ef4444', margin: '4px 0' }}>{error}</p>}
      <button
        onClick={handleGenerate}
        disabled={!prompt.trim()}
        style={{ marginTop: 8, padding: '8px 18px', background: prompt.trim() ? 'var(--accent)' : 'var(--border)', color: 'white', border: 'none', borderRadius: 7, fontWeight: 600, cursor: prompt.trim() ? 'pointer' : 'default', fontSize: 13 }}
      >
        Generate Design
      </button>
    </div>
  )
}
```

- [ ] **Step 3: TypeScript check**

```
cd frontend && npx tsc -b 2>&1
```
Expected: no errors

- [ ] **Step 4: Commit**

```
git add frontend/src/api/client.ts frontend/src/components/DesignEditor.tsx
git commit -m "feat: add DesignEditor component + design API functions"
```

---

## Task 7: `DesignGallery.tsx` — saved versions grid

**Files:**
- Create: `frontend/src/components/DesignGallery.tsx`

**Interfaces:**
- Consumes: `DesignVersion` type, `updateDesign`, `deleteDesign`, `getDesignPreviewUrl`, `getDesignPdfUrl` (Task 6)
- Produces: `DesignGallery` component

- [ ] **Step 1: Create `frontend/src/components/DesignGallery.tsx`**

```tsx
import { useState } from 'react'
import { updateDesign, deleteDesign, getDesignPreviewUrl, getDesignPdfUrl, type DesignVersion } from '../api/client'

interface Props {
  versions: DesignVersion[]
  type: 'resume' | 'cover_letter'
  activeId: string | null
  onUpdated: (version: DesignVersion) => void
  onDeleted: (id: string) => void
}

function DesignCard({ version, isActive, onSetDefault, onDelete }: {
  version: DesignVersion
  isActive: boolean
  onSetDefault: () => void
  onDelete: () => void
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <div style={{
      border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: 10, overflow: 'hidden', background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
    }}>
      {/* Scaled iframe thumbnail */}
      <div style={{ height: 140, overflow: 'hidden', position: 'relative', background: '#f5f5f5' }}>
        <iframe
          src={getDesignPreviewUrl(version.id)}
          title={version.name}
          style={{
            width: '550%',
            height: '550%',
            border: 'none',
            transform: 'scale(0.18)',
            transformOrigin: 'top left',
            pointerEvents: 'none',
          }}
        />
      </div>

      <div style={{ padding: '8px 10px', flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-h)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {version.name}
          </span>
          {isActive && (
            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--accent-bg)', color: 'var(--accent)', border: '1px solid var(--accent-border)', whiteSpace: 'nowrap' }}>
              ★ default
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <a
            href={getDesignPdfUrl(version.id)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 11, color: 'var(--accent)', textDecoration: 'none' }}
          >
            PDF ↗
          </a>
          {!isActive && (
            <button onClick={onSetDefault} style={{ fontSize: 11, background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', padding: 0 }}>
              Set default
            </button>
          )}
          {confirmDelete ? (
            <>
              <button onClick={onDelete} style={{ fontSize: 11, background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: 0 }}>Confirm</button>
              <button onClick={() => setConfirmDelete(false)} style={{ fontSize: 11, background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', padding: 0 }}>Cancel</button>
            </>
          ) : (
            <button onClick={() => setConfirmDelete(true)} style={{ fontSize: 11, background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', padding: 0 }}>
              Delete
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export function DesignGallery({ versions, type, activeId, onUpdated, onDeleted }: Props) {
  const filtered = versions.filter(v => v.type === type)

  if (filtered.length === 0) return null

  async function handleSetDefault(version: DesignVersion) {
    const updated = await updateDesign(version.id, { is_default: true })
    onUpdated(updated)
  }

  async function handleDelete(id: string) {
    await deleteDesign(id)
    onDeleted(id)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 16 }}>
      {filtered.map(v => (
        <DesignCard
          key={v.id}
          version={v}
          isActive={v.id === activeId}
          onSetDefault={() => handleSetDefault(v)}
          onDelete={() => handleDelete(v.id)}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: TypeScript check**

```
cd frontend && npx tsc -b 2>&1
```
Expected: no errors

- [ ] **Step 3: Commit**

```
git add frontend/src/components/DesignGallery.tsx
git commit -m "feat: add DesignGallery component (version grid with iframe thumbnails)"
```

---

## Task 8: `DesignSelector.tsx` + `ApplicationGenerator.tsx` update

**Files:**
- Create: `frontend/src/components/DesignSelector.tsx`
- Modify: `frontend/src/components/ApplicationGenerator.tsx`
- Modify: `frontend/src/api/client.ts` — update `generateApplication` signature

**Interfaces:**
- Consumes: `DesignVersion`, `generateApplication`
- Produces: `DesignSelector` component; `generateApplication` accepts optional design IDs

- [ ] **Step 1: Create `frontend/src/components/DesignSelector.tsx`**

```tsx
import { type DesignVersion } from '../api/client'

interface Props {
  versions: DesignVersion[]
  type: 'resume' | 'cover_letter'
  selectedId: string | null
  onChange: (id: string | null) => void
  label: string
  allowInherit?: boolean  // for cover_letter: "Same as resume"
}

export function DesignSelector({ versions, type, selectedId, onChange, label, allowInherit }: Props) {
  const filtered = versions.filter(v => v.type === type)
  if (filtered.length === 0) return null

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--text)', whiteSpace: 'nowrap', minWidth: 120 }}>{label}:</label>
      <select
        value={selectedId ?? ''}
        onChange={e => onChange(e.target.value || null)}
        style={{ flex: 1, padding: '5px 8px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg)', color: 'var(--text-h)' }}
      >
        <option value="">Default (Classic)</option>
        {allowInherit && <option value="__inherit__">Same as resume</option>}
        {filtered.map(v => (
          <option key={v.id} value={v.id}>{v.name}{v.is_default ? ' ★' : ''}</option>
        ))}
      </select>
    </div>
  )
}
```

- [ ] **Step 2: Update `generateApplication` in `frontend/src/api/client.ts`**

Replace the existing `generateApplication` function:
```typescript
export async function generateApplication(
  job: JobPosting,
  match: MatchScore,
  resumeDesignId?: string | null,
  coverLetterDesignId?: string | null,
) {
  return request<ApplicationPackage>('/application/generate', {
    method: 'POST',
    body: JSON.stringify({
      job,
      match,
      resume_design_id: resumeDesignId ?? null,
      cover_letter_design_id: coverLetterDesignId ?? null,
    }),
  })
}
```

- [ ] **Step 3: Update `frontend/src/components/ApplicationGenerator.tsx`**

Add `designs` prop and two selectors. Replace the entire file:

```tsx
import { useState } from 'react'
import { generateApplication, type JobPosting, type MatchScore, type ApplicationPackage, type DesignVersion } from '../api/client'
import { DesignSelector } from './DesignSelector'

interface Props {
  job: JobPosting
  match: MatchScore
  designs?: DesignVersion[]
}

function b64ToBlob(b64: string, type: string): Blob {
  const bytes = Uint8Array.from(atob(b64), c => c.charCodeAt(0))
  return new Blob([bytes], { type })
}

function triggerDownload(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

export function ApplicationGenerator({ job, match, designs = [] }: Props) {
  const [loading, setLoading] = useState(false)
  const [pkg, setPkg] = useState<ApplicationPackage | null>(null)
  const [error, setError] = useState('')
  const [showLetter, setShowLetter] = useState(false)
  const [resumeDesignId, setResumeDesignId] = useState<string | null>(null)
  const [coverLetterDesignId, setCoverLetterDesignId] = useState<string | null>(null)

  const hasDesigns = designs.length > 0

  async function handleGenerate() {
    setLoading(true)
    setError('')
    try {
      const result = await generateApplication(job, match, resumeDesignId, coverLetterDesignId)
      setPkg(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed.')
    } finally {
      setLoading(false)
    }
  }

  function downloadResume() {
    if (!pkg) return
    triggerDownload(b64ToBlob(pkg.resume_pdf_base64, 'application/pdf'), `Resume_${job.company}.pdf`)
  }

  function downloadCoverLetter() {
    if (!pkg) return
    triggerDownload(b64ToBlob(pkg.cover_letter_pdf_base64, 'application/pdf'), `CoverLetter_${job.company}.pdf`)
  }

  if (pkg) {
    return (
      <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'var(--bg)' }}>
        <p style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--text)', fontWeight: 600 }}>Application package ready</p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 10 }}>
          <button onClick={downloadResume} style={btnStyle('var(--accent)')}>Download Resume PDF</button>
          <button onClick={downloadCoverLetter} style={btnStyle('#22c07a')}>Download Cover Letter PDF</button>
          <button onClick={() => setShowLetter(v => !v)} style={btnStyle('transparent', 'var(--border)', 'var(--text)')}>
            {showLetter ? 'Hide' : 'Preview'} letter
          </button>
        </div>
        {showLetter && (
          <pre style={{ margin: 0, fontSize: 12, color: 'var(--text)', background: 'rgba(0,0,0,0.04)', padding: '10px 12px', borderRadius: 6, whiteSpace: 'pre-wrap', lineHeight: 1.6 }}>
            {pkg.cover_letter_text}
          </pre>
        )}
      </div>
    )
  }

  return (
    <div style={{ marginTop: 10 }}>
      {hasDesigns && (
        <div style={{ marginBottom: 8, padding: '8px 10px', borderRadius: 6, border: '1px solid var(--border)', background: 'var(--code-bg)' }}>
          <DesignSelector
            versions={designs}
            type="resume"
            selectedId={resumeDesignId}
            onChange={setResumeDesignId}
            label="Resume design"
          />
          <DesignSelector
            versions={designs}
            type="cover_letter"
            selectedId={coverLetterDesignId}
            onChange={setCoverLetterDesignId}
            label="Cover letter design"
          />
        </div>
      )}
      {error && <p style={{ fontSize: 12, color: '#ef4444', margin: '0 0 6px' }}>{error}</p>}
      <button onClick={handleGenerate} disabled={loading} style={btnStyle(loading ? 'var(--border)' : 'var(--accent)')}>
        {loading ? 'Generating package…' : 'Generate Application Package'}
      </button>
      {loading && (
        <p style={{ fontSize: 11, color: 'var(--text)', marginTop: 4 }}>
          Writing tailored resume + cover letter with AI — takes ~20s
        </p>
      )}
    </div>
  )
}

function btnStyle(bg: string, border?: string, color?: string): React.CSSProperties {
  return { padding: '6px 14px', background: bg, color: color ?? 'white', border: `1px solid ${border ?? bg}`, borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer' }
}
```

- [ ] **Step 4: TypeScript check**

```
cd frontend && npx tsc -b 2>&1
```
Expected: no errors

- [ ] **Step 5: Commit**

```
git add frontend/src/components/DesignSelector.tsx frontend/src/components/ApplicationGenerator.tsx frontend/src/api/client.ts
git commit -m "feat: add DesignSelector + wire design IDs into ApplicationGenerator"
```

---

## Task 9: Integrate into `ProfilePage.tsx` + pass designs to job results

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`
- Modify: `frontend/src/pages/JobSearchPage.tsx`
- Modify: `frontend/src/pages/AutoSearchPage.tsx`

**Interfaces:**
- Consumes: `DesignEditor`, `DesignGallery`, `DesignVersion`, `ProfileMaster.design_versions`

- [ ] **Step 1: Update `frontend/src/pages/ProfilePage.tsx`**

Add these imports at the top:
```tsx
import { DesignEditor } from '../components/DesignEditor'
import { DesignGallery } from '../components/DesignGallery'
import { type DesignVersion } from '../api/client'
```

Add a `useState` for tracking a refresh counter (to reload profile after design saved):

In the `ProfilePage` component body, add:
```tsx
const [, setRefreshTick] = useState(0)

function handleDesignSaved(_version: DesignVersion) {
  // Signal parent to reload profile from API
  onProfileUpdated({ ...profile, design_versions: [...profile.design_versions, _version] })
}

function handleDesignUpdated(updated: DesignVersion) {
  onProfileUpdated({
    ...profile,
    design_versions: profile.design_versions.map(v => v.id === updated.id ? updated : v),
    active_resume_design_id: updated.is_default && updated.type === 'resume' ? updated.id : profile.active_resume_design_id,
    active_cover_letter_design_id: updated.is_default && updated.type === 'cover_letter' ? updated.id : profile.active_cover_letter_design_id,
  })
}

function handleDesignDeleted(id: string) {
  onProfileUpdated({
    ...profile,
    design_versions: profile.design_versions.filter(v => v.id !== id),
    active_resume_design_id: profile.active_resume_design_id === id ? null : profile.active_resume_design_id,
    active_cover_letter_design_id: profile.active_cover_letter_design_id === id ? null : profile.active_cover_letter_design_id,
  })
}
```

After the existing `{/* ── Job suggestions hint ── */}` block, add a `{/* ── Design sections ── */}` block:

```tsx
      {/* ── Resume Design ── */}
      <Section title="Resume Design">
        <DesignGallery
          versions={profile.design_versions}
          type="resume"
          activeId={profile.active_resume_design_id}
          onUpdated={handleDesignUpdated}
          onDeleted={handleDesignDeleted}
        />
        <DesignEditor
          type="resume"
          profile={profile}
          onSaved={handleDesignSaved}
        />
      </Section>

      {/* ── Cover Letter Design ── */}
      <Section title="Cover Letter Design">
        <DesignGallery
          versions={profile.design_versions}
          type="cover_letter"
          activeId={profile.active_cover_letter_design_id}
          onUpdated={handleDesignUpdated}
          onDeleted={handleDesignDeleted}
        />
        <DesignEditor
          type="cover_letter"
          profile={profile}
          inheritFromDesignId={profile.active_resume_design_id ?? undefined}
          onSaved={handleDesignSaved}
        />
        {profile.design_versions.some(v => v.type === 'resume') && (
          <p style={{ fontSize: 12, color: 'var(--text)', marginTop: 8 }}>
            Tip: your active resume design will be offered as a base style for the cover letter.
          </p>
        )}
      </Section>
```

- [ ] **Step 2: Pass `designs` prop to `ApplicationGenerator` in `JobSearchPage.tsx`**

In `JobSearchPage`, add `designs` prop to the interface and pass it down to `ApplicationGenerator`:

```tsx
interface Props {
  onBack: () => void
  suggestions: JobSuggestion[]
  designs: DesignVersion[]  // add this
}
```

And pass it in App.tsx when rendering JobSearchPage:
```tsx
<JobSearchPage
  onBack={() => setAppState('has_profile')}
  suggestions={profile?.job_suggestions ?? []}
  designs={profile?.design_versions ?? []}
/>
```

In `JobSearchPage.tsx`, pass to `ApplicationGenerator`:
```tsx
<ApplicationGenerator job={posting} match={match} designs={designs} />
```

- [ ] **Step 3: Add `designs` prop to `AutoSearchPage.tsx`**

In `AutoSearchPage.tsx`, add prop interface entry and pass to `ApplicationGenerator`:
```tsx
interface Props {
  onBack: () => void
  designs?: DesignVersion[]
}

// in JobCard:
<ApplicationGenerator job={p} match={m} designs={designs} />
```

Pass from `App.tsx`:
```tsx
<AutoSearchPage onBack={() => setAppState('has_profile')} designs={profile?.design_versions ?? []} />
```

- [ ] **Step 4: TypeScript check + production build**

```
cd frontend && npx tsc -b && npx vite build 2>&1 | tail -5
```
Expected: `✓ built in Xs`

- [ ] **Step 5: Commit**

```
git add frontend/src/pages/ProfilePage.tsx frontend/src/pages/JobSearchPage.tsx frontend/src/pages/AutoSearchPage.tsx frontend/src/App.tsx
git commit -m "feat: integrate DesignEditor/Gallery into ProfilePage; pass designs to ApplicationGenerator"
```

---

## Self-Review Checklist

**Spec coverage:**
- ✅ Story 1 — resume design via prompt: Tasks 1–4, 6–7, 9
- ✅ Story 2 — cover letter design + inherit from resume: Tasks 3 (`generate_cover_letter_template`), 4 (`/cover-letter` endpoint), 6 (`DesignEditor type=cover_letter`), 9 (ProfilePage cover letter section)
- ✅ Story 3 — multiple saved versions + select at package generation: Tasks 7 (`DesignGallery`), 8 (`DesignSelector` in `ApplicationGenerator`), 5 (application router accepts design IDs)
- ✅ Fallback to ReportLab when no design exists: Task 5 (`_find_design` returns None → ReportLab)
- ✅ Playwright installed in Docker: Task 1 (Dockerfile)
- ✅ `is_default` + `active_*_design_id` sync: Task 4 (`PATCH /{id}` endpoint), Task 9 (`handleDesignUpdated`)

**Type consistency check:**
- `DesignVersion.id` is `str` everywhere (backend: `str = Field(default_factory=lambda: str(uuid4()))`; frontend: `id: string`) ✅
- `generate_resume_template(prompt: str, profile: ProfileMaster) -> str` — used identically in Task 3 definition and Task 4 router call ✅
- `render_template_to_html(template: str, context: dict) -> str` — defined Task 2, called Task 4 with `build_jinja_context(profile)` which returns `dict` ✅
- `render_cover_letter_template_to_html(template, letter_body, job_title, job_company, contact_name, contact_email, contact_phone, contact_location)` — defined Task 2, called Task 5 with named args ✅
- `getIngestStatus` reused in `DesignEditor` — correct, both ingest and design jobs use the same `job_store` and the same polling endpoint ✅
