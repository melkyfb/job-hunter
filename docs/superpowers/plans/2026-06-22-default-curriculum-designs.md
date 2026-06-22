# Default Curriculum Designs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Seed 15 pre-built Jinja2 resume templates during onboarding (parallel with CV analysis), expose per-template regeneration and full re-seed endpoints, and surface them in the frontend gallery and profile page.

**Architecture:** `seed_default_designs()` runs 15 LLM calls in parallel via `ThreadPoolExecutor(max_workers=15)`; during ingest, a second outer executor runs ingest + templates concurrently (barrier pattern). Two new endpoints (`POST /profile/design/seed-defaults`, `POST /profile/design/{id}/regenerate`) return async job IDs polled via the existing `/profile/ingest/{job_id}` mechanism. Frontend adds a "Regenerar" button per gallery card and a "Regenerar todos" button on the profile page.

**Tech Stack:** Python 3.12, FastAPI, Pydantic v2, `concurrent.futures.ThreadPoolExecutor`, React + TypeScript, `getIngestStatus` polling.

## Global Constraints

- Python: `from __future__ import annotations` at top of every new Python file
- Pydantic v2: `model_validate_json()` / `.model_dump(mode="json")` — never `.dict()`
- `generate_resume_template` new signature: `(prompt: str, skip_intent_check: bool = False) -> str` — `profile` param removed
- 15 template names follow pattern `"N. Name"` (e.g. `"1. Professional Equilibrium"`)
- `seed_default_designs()` returns templates in definition order (index-sorted), first gets `is_default=True`
- Individual template failures: log WARNING, skip — never propagate to caller
- Ingest thread: if templates fail entirely, ingest still completes; `design_versions = []`
- HITL path: templates discarded during ingest, re-seeded after resolve
- New endpoints poll via existing `GET /profile/ingest/{job_id}` — no new polling route needed
- Frontend: `designs` step key maps to Portuguese label `'Gerando designs padrão…'`
- TypeScript: no `any`, no new packages

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `backend/app/services/design_generator.py` | Remove `profile` param; add `skip_intent_check` |
| Create | `backend/app/services/default_designs.py` | 15 prompts + `seed_default_designs()` |
| Modify | `backend/app/routers/profile.py` | Barrier pattern in ingest + resolve threads |
| Modify | `backend/app/routers/design.py` | New seed-defaults + regenerate endpoints; update caller |
| Modify | `frontend/src/api/client.ts` | `seedDefaultDesigns()`, `regenerateDesign()` |
| Modify | `frontend/src/components/ResumeUpload.tsx` | Add `designs` to STEP_LABELS |
| Modify | `frontend/src/components/DesignGallery.tsx` | Per-card Regenerar button + spinner |
| Modify | `frontend/src/pages/ProfilePage.tsx` | Regenerar todos button + progress bar |
| Create | `backend/tests/test_services/test_default_designs.py` | Unit tests for seeding service |
| Modify | `backend/tests/test_routers/test_design.py` | Tests for new endpoints |
| Modify | `backend/tests/test_services/test_design_generator.py` | Tests for signature change |

---

### Task 1: Fix `generate_resume_template` — remove `profile` param, add `skip_intent_check`

**Files:**
- Modify: `backend/app/services/design_generator.py:189`
- Modify: `backend/app/routers/design.py:80`
- Modify: `backend/tests/test_services/test_design_generator.py`

**Interfaces:**
- Produces: `generate_resume_template(prompt: str, skip_intent_check: bool = False) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# backend/tests/test_services/test_design_generator.py
# Add these two tests after existing ones:

def test_generate_resume_template_no_profile_param():
    """generate_resume_template must NOT accept a profile positional arg."""
    import inspect
    sig = inspect.signature(generate_resume_template)
    assert "profile" not in sig.parameters


def test_generate_resume_template_skip_intent_check_bypasses_llm_call(mock_llm_response):
    """skip_intent_check=True skips the intent classifier and calls generation directly."""
    intent_calls = []

    def fake_intent_create(**kwargs):
        intent_calls.append(kwargs)
        raise AssertionError("intent check must not be called")

    intent_client = MagicMock()
    intent_client.chat.completions.create.side_effect = fake_intent_create

    gen_client = MagicMock()
    gen_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=json.dumps({"html_template": _VALID_RESUME_HTML})))]
    )

    with patch("app.services.design_generator.get_llm_client", return_value=gen_client):
        result = generate_resume_template("a design brief", skip_intent_check=True)
    assert "<!doctype" in result.lower()
    assert not intent_calls
```

Note: `_VALID_RESUME_HTML` and `mock_llm_response` fixture are defined in the existing test file. Check the file and add the tests at the bottom.

- [ ] **Step 2: Run to verify they fail**

```
cd backend && rtk pytest tests/test_services/test_design_generator.py::test_generate_resume_template_no_profile_param tests/test_services/test_design_generator.py::test_generate_resume_template_skip_intent_check_bypasses_llm_call -v
```

Expected: FAIL — `unexpected keyword argument 'skip_intent_check'` or `unexpected argument 'profile'`.

- [ ] **Step 3: Update `design_generator.py`**

Replace the function signature at line 189:

```python
def generate_resume_template(prompt: str, skip_intent_check: bool = False) -> str:
    """
    Call the LLM to generate a Jinja2 HTML resume template from a user's prompt.
    Set skip_intent_check=True to bypass the intent classifier (used for trusted default prompts).
    Raises ValueError immediately if the prompt is not a design brief (when skip_intent_check=False).
    Validates with Pydantic + Jinja2; self-corrects up to _MAX_RETRIES times.
    Raises RuntimeError if all retries fail.
    """
    if not skip_intent_check:
        _check_design_intent(prompt)
    # rest of function body unchanged (uses build_dummy_context(), not profile)
```

Also remove the `from app.models.profile import ProfileMaster` import if it's no longer needed anywhere else in this file. Check with grep first — if `ProfileMaster` appears only in the old signature, remove the import.

- [ ] **Step 4: Update caller in `design.py`**

Line 80 of `backend/app/routers/design.py`, change:

```python
# OLD
html_template = generate_resume_template(prompt, profile)
# NEW
html_template = generate_resume_template(prompt)
```

- [ ] **Step 5: Run tests**

```
cd backend && rtk pytest tests/test_services/test_design_generator.py -v
```

Expected: All PASS.

- [ ] **Step 6: Commit**

```bash
cd backend && rtk git add app/services/design_generator.py app/routers/design.py tests/test_services/test_design_generator.py
rtk git commit -m "refactor: remove unused profile param from generate_resume_template; add skip_intent_check"
```

---

### Task 2: Create `default_designs.py` service

**Files:**
- Create: `backend/app/services/default_designs.py`
- Create: `backend/tests/test_services/test_default_designs.py`

**Interfaces:**
- Consumes: `generate_resume_template(prompt: str, skip_intent_check: bool = False) -> str` (Task 1)
- Produces:
  - `DEFAULT_TEMPLATES: list[tuple[str, str]]` — 15 (name, prompt) pairs
  - `seed_default_designs(progress_fn: Callable[[int, int], None] | None = None) -> list[DesignVersion]`

- [ ] **Step 1: Write the tests**

Create `backend/tests/test_services/test_default_designs.py`:

```python
from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from app.services.default_designs import DEFAULT_TEMPLATES, seed_default_designs


def _fake_html(name: str) -> str:
    return (
        f'<!DOCTYPE html><html><head><meta charset="UTF-8">'
        f'<style>@page{{size:A4;margin:0}}</style></head>'
        f'<body><h1>{{{{ profile.contact.full_name }}}}</h1>'
        f'<p>{name}</p>'
        f'{{% for exp in profile.work_experiences %}}<div>{{{{ exp.role }}}}</div>{{% endfor %}}'
        f'</body></html>'
    )


def test_default_templates_has_15_entries():
    assert len(DEFAULT_TEMPLATES) == 15


def test_default_templates_names_are_numbered():
    for i, (name, _) in enumerate(DEFAULT_TEMPLATES, start=1):
        assert name.startswith(f"{i}. "), f"Template {i} name must start with '{i}. ', got: {name!r}"


def test_default_templates_prompts_non_empty():
    for name, prompt in DEFAULT_TEMPLATES:
        assert len(prompt) > 30, f"Prompt for '{name}' is too short: {prompt!r}"


def test_seed_default_designs_returns_all_on_success():
    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=lambda prompt, skip_intent_check=False: _fake_html(prompt[:20]),
    ):
        results = seed_default_designs()
    assert len(results) == 15


def test_seed_default_designs_first_is_default():
    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=lambda prompt, skip_intent_check=False: _fake_html(prompt[:20]),
    ):
        results = seed_default_designs()
    assert results[0].is_default is True
    for r in results[1:]:
        assert r.is_default is False


def test_seed_default_designs_preserves_order():
    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=lambda prompt, skip_intent_check=False: _fake_html(prompt[:20]),
    ):
        results = seed_default_designs()
    for i, (expected_name, _) in enumerate(DEFAULT_TEMPLATES):
        assert results[i].name == expected_name


def test_seed_default_designs_skips_failed_template():
    call_count = 0

    def flaky(prompt, skip_intent_check=False):
        nonlocal call_count
        call_count += 1
        if call_count == 3:
            raise RuntimeError("LLM timeout")
        return _fake_html(prompt[:20])

    with patch("app.services.default_designs.generate_resume_template", side_effect=flaky):
        results = seed_default_designs()
    assert len(results) == 14  # one skipped
    # Position 3 (index 2) is missing; result[2] name must be template[3]
    assert results[2].name == DEFAULT_TEMPLATES[3][0]


def test_seed_default_designs_empty_on_all_failures():
    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=RuntimeError("all fail"),
    ):
        results = seed_default_designs()
    assert results == []


def test_seed_default_designs_calls_progress_fn():
    calls: list[tuple[int, int]] = []

    with patch(
        "app.services.default_designs.generate_resume_template",
        side_effect=lambda prompt, skip_intent_check=False: _fake_html(prompt[:20]),
    ):
        seed_default_designs(progress_fn=lambda done, total: calls.append((done, total)))

    assert len(calls) == 15
    totals = {t for _, t in calls}
    assert totals == {15}
    dones = sorted(d for d, _ in calls)
    assert dones == list(range(1, 16))


def test_seed_default_designs_uses_skip_intent_check():
    """Must call generate_resume_template with skip_intent_check=True."""
    captured_kwargs: list[dict] = []

    def fake_gen(prompt, skip_intent_check=False):
        captured_kwargs.append({"skip_intent_check": skip_intent_check})
        return _fake_html(prompt[:20])

    with patch("app.services.default_designs.generate_resume_template", side_effect=fake_gen):
        seed_default_designs()

    assert all(kw["skip_intent_check"] is True for kw in captured_kwargs)
```

- [ ] **Step 2: Run to verify they fail**

```
cd backend && rtk pytest tests/test_services/test_default_designs.py -v
```

Expected: All FAIL — `ModuleNotFoundError: No module named 'app.services.default_designs'`.

- [ ] **Step 3: Create `backend/app/services/default_designs.py`**

```python
from __future__ import annotations

import logging
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed

from app.models.design import DesignVersion
from app.services.design_generator import generate_resume_template

logger = logging.getLogger(__name__)

DEFAULT_TEMPLATES: list[tuple[str, str]] = [
    (
        "1. Professional Equilibrium",
        "Two-column layout: left sidebar (30% width) in slate grey (#2d3748) with name, contact info, skills, and languages in white text. Right column (70%) on white with work experience using blue (#4299e1) timeline dots. Section headings in uppercase tracked letters. Arial 10pt throughout. Clean, balanced, and corporate-modern. Include: @page { size: A4; margin: 0; } in CSS.",
    ),
    (
        "2. Editorial Design",
        "Magazine-inspired single-column layout. Name as display type (Georgia 34pt) top-left. Contact details in a thin full-width horizontal rule band below. Body uses a two-column grid: experience descriptions left, dates right. Bold sans-serif section titles. Black and white with one accent in deep burgundy (#7c2d2d) for section titles and rules. Print-ready A4.",
    ),
    (
        "3. Techno Minimalism",
        "Dark terminal theme: #0d1117 background, #c9d1d9 body text. Monospace font (Courier New) throughout. Name in terminal green (#3fb950) top-left. Work experience bullets prefixed with › symbol. Skills displayed as inline code tags with subtle borders. Section dividers as horizontal rules in #30363d. Dates in muted grey. Developer aesthetic, A4 size.",
    ),
    (
        "4. Interface Aesthetic",
        "Clean UI-card design. Full-width top bar with name in white on light blue (#1d4ed8) background. Each work experience in a card with 1px border (#e5e7eb) and 4px border-radius. Skills as rounded pill badges. Section labels in small uppercase tracking on the left margin. Segoe UI 11pt. White background with subtle card shadows. A4 layout.",
    ),
    (
        "5. Swiss Style",
        "International Typographic Style: mathematical grid precision. Arial/Helvetica throughout with strict typographic hierarchy. Red (#dc2626) for section numbers (01, 02, 03) in large type. Name in bold 26pt top-left. Thin horizontal rules between sections. Experience in a strict three-column grid: date | role/company | bullet achievements. Minimal decoration. A4.",
    ),
    (
        "6. Fancy Dark Mode",
        "Premium dark layout: #1a1a2e background, #e8e8e8 body text. Gold (#c9a84c) accent for name (Georgia 28pt centered), section headings with left gold border rule, and skill badge outlines. Work experience bullets with diamond (◆) markers. Skills in gold-outline pill badges. Elegant and luxury-feel. White dividers at 10% opacity. A4 size.",
    ),
    (
        "7. Classic Modernism",
        "Mid-century modern: clean white with warm beige (#f5f0e8) left sidebar (28% width). Name in bold Verdana 22pt in sidebar. Sidebar contains contact, skills, education, languages. Main area: work experience in clean rows, italic company names, dates right-aligned. Section headings with thick terracotta (#c1440e) left border. Structured and timeless. A4.",
    ),
    (
        "8. Gently Neobrutalism",
        "Bold neobrutalist style: white background, 3px solid black borders around all section blocks. Name in bold Arial 30pt with bright yellow (#facc15) background header strip. Section headings on black background with white text, all caps. High contrast throughout. Dates in pill badges with black border. Intentionally strong visual weight. A4 layout.",
    ),
    (
        "9. Inclusive Design",
        "Accessibility-first high-contrast design. Pure white background, pure black text, minimum 13pt everywhere. Name in 24pt bold, clearly left-aligned. All sections in large readable blocks with clear headings. No decorative elements. Visual hierarchy through size and weight alone — no color distinctions for meaning. One blue (#0000EE) accent for links only. WCAG AAA. Two-column (65/35). A4.",
    ),
    (
        "10. Dynamic Monocolor",
        "Single-hue depth: deep navy (#003366) used at 5 opacity levels. Name/header: 100% navy, white text. Section headings: 80% navy background, white text. Alternating content rows: white and 6% navy tint. Borders at 20% navy. Accent timeline dots at 70% navy. Cohesive, professional, and unified by one color family. Arial 10pt. A4.",
    ),
    (
        "11. The Time of Experience",
        "Timeline-centric layout. Full left column (25% width) is a vertical timeline: years in circles connected by a vertical line in blue (#1565c0). Each work experience block floats right with a horizontal connector line. Education and skills in a compact two-column section at the bottom. Light grey (#f8f9fa) overall background. A4 size, print-ready.",
    ),
    (
        "12. The Lines of Evolution",
        "Geometric line-based design. Name in bold 26pt with a bold diagonal decorative separator below it. Section items separated by thin horizontal rules. Skills displayed as horizontal bar graphs (CSS only, no JS) showing proficiency. Progress lines for language levels. Black, white, and teal (#0d9488). Clean and data-driven aesthetic. A4 layout.",
    ),
    (
        "13. Future Now",
        "Modern sci-fi aesthetic without gimmicks. Name in letter-spacing: 6px, all caps, 20pt. Header in deep dark purple (#1e1b4b) gradient to black. Content in clean white with 1px #6c63ff left border on each section. Section labels in purple, uppercase tracking. Skills with rectangular outline badges in purple. Segoe UI Light throughout. A4.",
    ),
    (
        "14. Charm of Last Century",
        "Art Deco inspired. Warm champagne (#fef3c7) background with deep brown (#3d2b1f) text. Name centered in 26pt Georgia with ornamental horizontal rules above and below (using CSS border patterns). Section headings centered with flanking dash rules. Geometric corner ornament (CSS only) on the outer page border. Elegant and vintage. A4 size.",
    ),
    (
        "15. Journalism is Now",
        "Newspaper broadsheet layout. Name as a masthead in bold 28pt with full-width border below. Two-column body layout for experience descriptions (CSS columns). Dates styled as bylines in italic grey. Skills section formatted as a two-column classified-ad grid. Section headings as newspaper-style headlines with bold rules above. Black and white, high contrast. A4.",
    ),
]


def seed_default_designs(
    progress_fn: Callable[[int, int], None] | None = None,
) -> list[DesignVersion]:
    """
    Generate all 15 default resume templates in parallel.
    Individual failures are logged and skipped — never propagated.
    Returns templates in definition order.
    First element has is_default=True; caller must set active_resume_design_id.
    progress_fn(completed, total) called after each template finishes.
    """
    total = len(DEFAULT_TEMPLATES)
    ordered: dict[int, DesignVersion | None] = {}
    completed_count = 0

    with ThreadPoolExecutor(max_workers=total) as pool:
        futures = {
            pool.submit(_generate_one, name, prompt): idx
            for idx, (name, prompt) in enumerate(DEFAULT_TEMPLATES)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                ordered[idx] = future.result()
            except Exception as exc:
                logger.warning("Default template index %d failed: %s", idx, exc)
                ordered[idx] = None
            completed_count += 1
            if progress_fn:
                progress_fn(completed_count, total)

    results = [v for i in sorted(ordered) if (v := ordered[i]) is not None]
    if results:
        results[0].is_default = True
    return results


def _generate_one(name: str, prompt: str) -> DesignVersion:
    html_template = generate_resume_template(prompt, skip_intent_check=True)
    return DesignVersion(name=name, prompt=prompt, type="resume", html_template=html_template)
```

- [ ] **Step 4: Run tests**

```
cd backend && rtk pytest tests/test_services/test_default_designs.py -v
```

Expected: All 9 PASS.

- [ ] **Step 5: Commit**

```bash
cd backend && rtk git add app/services/default_designs.py tests/test_services/test_default_designs.py
rtk git commit -m "feat: add default_designs service with 15 pre-built resume template prompts"
```

---

### Task 3: Barrier pattern in ingest + resolve threads

**Files:**
- Modify: `backend/app/routers/profile.py`
- Create: `backend/tests/test_routers/test_profile_designs.py`

**Interfaces:**
- Consumes: `seed_default_designs(progress_fn=...) -> list[DesignVersion]` (Task 2)
- Produces: unchanged external API — ingest/resolve responses are identical; profiles now include `design_versions`

- [ ] **Step 1: Write the tests**

Create `backend/tests/test_routers/test_profile_designs.py`:

```python
from __future__ import annotations

import time
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.design import DesignVersion
from app.models.ingestion import HITLResolution, IngestionResponse, IngestionStatus
from app.models.profile import ContactInfo, ProfileMaster

client = TestClient(app)

_PROFILE = ProfileMaster(contact=ContactInfo(full_name="Test User", email="t@t.com"))

_DUMMY_DESIGNS = [
    DesignVersion(id=f"d{i}", name=f"{i}. Design", prompt="p", type="resume", html_template="<html><head><meta charset='UTF-8'></head><body></body></html>", is_default=(i == 1))
    for i in range(1, 4)
]


def _make_ingest_result(profile: ProfileMaster) -> IngestionResponse:
    return IngestionResponse(
        ingestion_id="test-id",
        status=IngestionStatus.COMPLETED,
        profile=profile,
    )


def test_ingest_attaches_designs_to_profile():
    """After ingest completes, profile.design_versions contains seeded templates."""
    saved_profiles: list[ProfileMaster] = []

    def fake_save(p: ProfileMaster) -> None:
        saved_profiles.append(p.model_copy(deep=True))

    with (
        patch("app.routers.profile._repo.delete_partial"),
        patch("app.routers.profile._repo.save", side_effect=fake_save),
        patch("app.services.extractors.extract_text", return_value="resume text"),
        patch(
            "app.routers.profile._ingestion.run",
            return_value=_make_ingest_result(_PROFILE),
        ),
        patch("app.routers.profile.generate_suggestions", return_value=[]),
        patch(
            "app.routers.profile.seed_default_designs",
            return_value=_DUMMY_DESIGNS,
        ),
    ):
        r = client.post("/profile/ingest", files={"file": ("cv.pdf", b"%PDF-1", "application/pdf")})
        assert r.status_code == 202
        job_id = r.json()["job_id"]

        # Poll until done
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)

    assert status["status"] == "completed"
    # The saved profile should contain designs
    last_saved = saved_profiles[-1]
    assert len(last_saved.design_versions) == 3
    assert last_saved.active_resume_design_id == "d1"


def test_ingest_completes_even_if_seed_returns_empty():
    """Ingest succeeds when seed_default_designs returns [] (all templates failed)."""
    with (
        patch("app.routers.profile._repo.delete_partial"),
        patch("app.routers.profile._repo.save"),
        patch("app.services.extractors.extract_text", return_value="resume text"),
        patch("app.routers.profile._ingestion.run", return_value=_make_ingest_result(_PROFILE)),
        patch("app.routers.profile.generate_suggestions", return_value=[]),
        patch("app.routers.profile.seed_default_designs", return_value=[]),
    ):
        r = client.post("/profile/ingest", files={"file": ("cv.pdf", b"%PDF-1", "application/pdf")})
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)
    assert status["status"] == "completed"


def test_ingest_hitl_does_not_seed_designs():
    """HITL path: templates are not generated (seed not called)."""
    from app.models.ingestion import HITLRequest
    hitl_result = IngestionResponse(
        ingestion_id="hitl-id",
        status=IngestionStatus.HITL_REQUIRED,
        hitl_request=HITLRequest(
            ingestion_id="hitl-id",
            partial_profile=_PROFILE,
            missing_fields=[],
            message="Review needed",
        ),
    )
    seed_calls: list = []
    with (
        patch("app.services.extractors.extract_text", return_value="resume text"),
        patch("app.routers.profile._ingestion.run", return_value=hitl_result),
        patch("app.routers.profile._repo.save_partial"),
        patch("app.routers.profile.seed_default_designs", side_effect=lambda **kw: seed_calls.append(1) or []),
    ):
        r = client.post("/profile/ingest", files={"file": ("cv.pdf", b"%PDF-1", "application/pdf")})
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)
    assert status["status"] == "hitl_required"
    assert seed_calls == [], "seed must not be called on HITL path"


def test_resolve_attaches_designs():
    """After HITL resolve, profile contains seeded templates."""
    resolution = HITLResolution(ingestion_id="hitl-id", resolved_fields={})
    saved: list[ProfileMaster] = []

    with (
        patch("app.routers.profile._repo.partial_exists", return_value=True),
        patch("app.routers.profile._repo.load_partial", return_value=_PROFILE),
        patch("app.routers.profile._repo.delete_partial"),
        patch("app.routers.profile._repo.save", side_effect=lambda p: saved.append(p.model_copy(deep=True))),
        patch("app.routers.profile.generate_suggestions", return_value=[]),
        patch("app.routers.profile.seed_default_designs", return_value=_DUMMY_DESIGNS),
    ):
        r = client.post("/profile/ingest/resolve", json=resolution.model_dump())
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)

    assert status["status"] == "completed"
    assert len(saved[-1].design_versions) == 3
    assert saved[-1].active_resume_design_id == "d1"
```

- [ ] **Step 2: Run to verify they fail**

```
cd backend && rtk pytest tests/test_routers/test_profile_designs.py -v
```

Expected: FAIL — `seed_default_designs not imported in profile.py`.

- [ ] **Step 3: Update `backend/app/routers/profile.py`**

Add import near top (after existing imports):

```python
from concurrent.futures import ThreadPoolExecutor

from app.services.default_designs import seed_default_designs
```

Replace the ingest `_run()` function (currently lines 90–130):

```python
    def _run() -> None:
        def ingest_progress(step: str, message: str, pct: int) -> None:
            store.update_job(job_id, step=step, message=message, progress=pct)

        # Run ingest + template seeding concurrently
        with ThreadPoolExecutor(max_workers=2) as pool:
            ingest_future = pool.submit(_ingestion.run, filename, resume_text, ingest_progress)
            templates_future = pool.submit(seed_default_designs)
        # Both done here (executor waited on __exit__)

        result = ingest_future.result()
        try:
            templates = templates_future.result()
        except Exception as exc:
            logger.warning("seed_default_designs failed: %s", exc)
            templates = []

        if result.status == IngestionStatus.COMPLETED and result.profile:
            _repo.delete_partial()
            if templates:
                result.profile.design_versions = templates
                result.profile.active_resume_design_id = templates[0].id
            store.update_job(job_id, step="suggestions", message="Generating job suggestions…", progress=80)
            suggestions = generate_suggestions(result.profile)
            result.profile.job_suggestions = suggestions
            _repo.save(result.profile)
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Profile ready!",
                progress=100,
                result=result.model_dump(mode="json"),
            )
        elif result.status == IngestionStatus.HITL_REQUIRED and result.hitl_request:
            _repo.save_partial(result.hitl_request.partial_profile)
            store.update_job(
                job_id,
                status="hitl_required",
                step="hitl",
                message="Missing metrics found — please review.",
                progress=90,
                result=result.model_dump(mode="json"),
            )
        else:
            store.update_job(
                job_id,
                status="failed",
                step="error",
                message=result.error or "Unknown error",
                progress=0,
                result=result.model_dump(mode="json"),
            )
```

Also add `import logging` to the imports at the top of `profile.py` if not already present, and add:

```python
logger = logging.getLogger(__name__)
```

Replace the resolve `_run()` function (currently lines 185–202):

```python
    def _run() -> None:
        # Run suggestions + template seeding concurrently
        with ThreadPoolExecutor(max_workers=2) as pool:
            suggestions_future = pool.submit(generate_suggestions, profile)
            templates_future = pool.submit(seed_default_designs)

        suggestions = suggestions_future.result()
        try:
            templates = templates_future.result()
        except Exception as exc:
            logger.warning("seed_default_designs failed in resolve: %s", exc)
            templates = []

        profile.job_suggestions = suggestions
        if templates:
            profile.design_versions = templates
            profile.active_resume_design_id = templates[0].id

        _repo.save(profile)
        result = IngestionResponse(
            ingestion_id=ingestion_id,
            status=IngestionStatus.COMPLETED,
            profile=profile,
        )
        store.update_job(
            job_id,
            status="completed",
            step="done",
            message="Profile ready!",
            progress=100,
            result=result.model_dump(mode="json"),
        )
```

- [ ] **Step 4: Run tests**

```
cd backend && rtk pytest tests/test_routers/test_profile_designs.py -v
```

Expected: All 4 PASS.

Also verify existing tests still pass:

```
cd backend && rtk pytest tests/test_routers/test_profile.py -v
```

- [ ] **Step 5: Commit**

```bash
cd backend && rtk git add app/routers/profile.py tests/test_routers/test_profile_designs.py
rtk git commit -m "feat: seed 15 default designs in parallel with CV analysis during ingest and HITL resolve"
```

---

### Task 4: New design endpoints — `seed-defaults` and `{id}/regenerate`

**Files:**
- Modify: `backend/app/routers/design.py`
- Modify: `backend/tests/test_routers/test_design.py`

**Interfaces:**
- Consumes: `seed_default_designs()` (Task 2), `generate_resume_template(prompt, skip_intent_check=True)` (Task 1)
- Produces:
  - `POST /profile/design/seed-defaults` → `AsyncDesignStart { job_id, status: "processing" }`
  - `POST /profile/design/{design_id}/regenerate` → `AsyncDesignStart { job_id, status: "processing" }`

- [ ] **Step 1: Write the tests**

Add to `backend/tests/test_routers/test_design.py`:

```python
# ---------- seed-defaults endpoint ----------

def test_seed_defaults_returns_job_id():
    designs = [
        DesignVersion(id=f"d{i}", name=f"{i}. Design", prompt="p", type="resume",
                      html_template="<html><head><meta charset='UTF-8'></head><body></body></html>",
                      is_default=(i == 1))
        for i in range(1, 3)
    ]
    with (
        patch("app.routers.design._repo.load", return_value=_PROFILE),
        patch("app.routers.design._repo.save"),
        patch("app.routers.design.seed_default_designs", return_value=designs),
    ):
        r = client.post("/profile/design/seed-defaults")
    assert r.status_code == 202
    body = r.json()
    assert "job_id" in body
    assert body["status"] == "processing"


def test_seed_defaults_replaces_existing_default_designs():
    """seed-defaults removes designs matching 'N. ...' name pattern before inserting."""
    existing_default = DesignVersion(
        id="old-default", name="1. Old Design", prompt="old", type="resume",
        html_template="<html><head><meta charset='UTF-8'></head><body>old</body></html>",
        is_default=True,
    )
    custom_design = DesignVersion(
        id="custom-1", name="My Custom Design", prompt="custom", type="resume",
        html_template="<html><head><meta charset='UTF-8'></head><body>custom</body></html>",
    )
    profile_with_designs = _PROFILE.model_copy(update={
        "design_versions": [existing_default, custom_design],
        "active_resume_design_id": "old-default",
    })
    new_design = DesignVersion(
        id="new-1", name="1. Professional Equilibrium", prompt="p", type="resume",
        html_template="<html><head><meta charset='UTF-8'></head><body>new</body></html>",
        is_default=True,
    )
    saved_profiles: list = []

    import time
    with (
        patch("app.routers.design._repo.load", return_value=profile_with_designs),
        patch("app.routers.design._repo.save", side_effect=lambda p: saved_profiles.append(p.model_copy(deep=True))),
        patch("app.routers.design.seed_default_designs", return_value=[new_design]),
    ):
        r = client.post("/profile/design/seed-defaults")
        assert r.status_code == 202
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)

    assert status["status"] == "completed"
    # custom design preserved, old default removed, new default added
    saved = saved_profiles[-1]
    ids = [v.id for v in saved.design_versions]
    assert "custom-1" in ids
    assert "old-default" not in ids
    assert "new-1" in ids


def test_seed_defaults_returns_404_if_no_profile():
    from app.repositories.profile_repository import ProfileNotFoundError
    with patch("app.routers.design._repo.load", side_effect=ProfileNotFoundError("no profile")):
        r = client.post("/profile/design/seed-defaults")
    assert r.status_code == 404


# ---------- regenerate endpoint ----------

_DESIGN_WITH_PROMPT = DesignVersion(
    id="regen-id",
    name="1. Professional Equilibrium",
    prompt="Two-column modern design",
    type="resume",
    html_template="<html><head><meta charset='UTF-8'></head><body>old</body></html>",
)
_PROFILE_WITH_REGEN = _PROFILE.model_copy(update={"design_versions": [_DESIGN_WITH_PROMPT]})

_NEW_HTML = """<!DOCTYPE html><html><head><meta charset="UTF-8"><style>@page{size:A4;margin:0}</style></head>
<body><h1>{{ profile.contact.full_name }}</h1>
{% for exp in profile.work_experiences %}<div>{{ exp.role }}</div>{% endfor %}
</body></html>"""


def test_regenerate_returns_job_id():
    with (
        patch("app.routers.design._repo.load", return_value=_PROFILE_WITH_REGEN),
        patch("app.routers.design._repo.save"),
        patch("app.services.design_generator.get_llm_client", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(create=MagicMock(
                return_value=MagicMock(choices=[MagicMock(message=MagicMock(
                    content=json.dumps({"html_template": _NEW_HTML})
                ))])
            )))
        )),
    ):
        r = client.post("/profile/design/regen-id/regenerate")
    assert r.status_code == 202
    assert "job_id" in r.json()


def test_regenerate_overwrites_html_preserves_id():
    import time
    saved_profiles: list = []

    with (
        patch("app.routers.design._repo.load", return_value=_PROFILE_WITH_REGEN),
        patch("app.routers.design._repo.save", side_effect=lambda p: saved_profiles.append(p.model_copy(deep=True))),
        patch("app.services.design_generator.get_llm_client", return_value=MagicMock(
            chat=MagicMock(completions=MagicMock(create=MagicMock(
                return_value=MagicMock(choices=[MagicMock(message=MagicMock(
                    content=json.dumps({"html_template": _NEW_HTML})
                ))])
            )))
        )),
    ):
        r = client.post("/profile/design/regen-id/regenerate")
        job_id = r.json()["job_id"]
        for _ in range(50):
            status = client.get(f"/profile/ingest/{job_id}").json()
            if status["status"] != "processing":
                break
            time.sleep(0.05)

    assert status["status"] == "completed"
    saved_version = next(v for v in saved_profiles[-1].design_versions if v.id == "regen-id")
    assert saved_version.html_template == _NEW_HTML
    assert saved_version.name == "1. Professional Equilibrium"  # preserved
    assert saved_version.prompt == "Two-column modern design"    # preserved


def test_regenerate_returns_404_for_missing_design():
    with patch("app.routers.design._repo.load", return_value=_PROFILE):
        r = client.post("/profile/design/nonexistent-id/regenerate")
    assert r.status_code == 404


def test_regenerate_returns_422_when_no_prompt():
    no_prompt_design = DesignVersion(
        id="no-prompt-id",
        name="Custom",
        prompt="",
        type="resume",
        html_template="<html><head><meta charset='UTF-8'></head><body></body></html>",
    )
    profile = _PROFILE.model_copy(update={"design_versions": [no_prompt_design]})
    with patch("app.routers.design._repo.load", return_value=profile):
        r = client.post("/profile/design/no-prompt-id/regenerate")
    assert r.status_code == 422
```

- [ ] **Step 2: Run to verify they fail**

```
cd backend && rtk pytest tests/test_routers/test_design.py::test_seed_defaults_returns_job_id tests/test_routers/test_design.py::test_regenerate_returns_job_id -v
```

Expected: FAIL — `404 Not Found` or endpoint not registered.

- [ ] **Step 3: Update `backend/app/routers/design.py`**

Add these imports at the top (after existing imports):

```python
import re

from app.services.default_designs import seed_default_designs
```

Add the two new endpoint functions before the `@router.get("/{design_id}/preview-html")` line:

```python
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
            completed = 0

            def _progress(done: int, total: int) -> None:
                nonlocal completed
                completed = done
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
```

Note: `seed-defaults` must be registered **before** `/{design_id}/...` routes to avoid FastAPI matching `"seed-defaults"` as a path param. Check the route order — the new `@router.post("/seed-defaults", ...)` must appear before `@router.get("/{design_id}/preview-html")`. FastAPI uses declaration order for route matching.

- [ ] **Step 4: Run tests**

```
cd backend && rtk pytest tests/test_routers/test_design.py -v
```

Expected: All tests (existing + new) PASS.

- [ ] **Step 5: Commit**

```bash
cd backend && rtk git add app/routers/design.py tests/test_routers/test_design.py
rtk git commit -m "feat: add seed-defaults and regenerate design endpoints"
```

---

### Task 5: Frontend — client functions + ResumeUpload STEP_LABELS

**Files:**
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/ResumeUpload.tsx`

**Interfaces:**
- Produces:
  - `seedDefaultDesigns(): Promise<AsyncJobStart>`
  - `regenerateDesign(designId: string): Promise<AsyncJobStart>`
  - `STEP_LABELS` in `ResumeUpload.tsx` includes `designs: 'Gerando designs padrão…'`

- [ ] **Step 1: Update `frontend/src/api/client.ts`**

Add after the `deleteDesign` function (around line 161):

```typescript
export async function seedDefaultDesigns() {
  return request<AsyncJobStart>('/profile/design/seed-defaults', { method: 'POST' })
}

export async function regenerateDesign(designId: string) {
  return request<AsyncJobStart>(`/profile/design/${designId}/regenerate`, { method: 'POST' })
}
```

No new types needed — both return `AsyncJobStart` which is already defined.

- [ ] **Step 2: Update `frontend/src/components/ResumeUpload.tsx`**

Add `designs` to `STEP_LABELS` (around line 12):

```typescript
const STEP_LABELS: Record<string, string> = {
  extracting: 'Extracting text from your file…',
  analyzing: 'Sending to AI for analysis…',
  validating: 'Validating structured output…',
  suggestions: 'Generating job suggestions…',
  designs: 'Gerando designs padrão…',
  saving: 'Finalizing your profile…',
  hitl: 'Missing metrics found — please review.',
  done: 'Profile ready!',
  error: 'Something went wrong.',
}
```

- [ ] **Step 3: Build check**

```
cd frontend && rtk tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd frontend && rtk git add src/api/client.ts src/components/ResumeUpload.tsx
rtk git commit -m "feat: add seedDefaultDesigns and regenerateDesign API functions; add designs step label"
```

---

### Task 6: `DesignGallery.tsx` — per-card Regenerar button

**Files:**
- Modify: `frontend/src/components/DesignGallery.tsx`

**Interfaces:**
- Consumes: `regenerateDesign(designId: string): Promise<AsyncJobStart>`, `getIngestStatus(jobId: string): Promise<AsyncJobStatus>` (already in client.ts)
- Produces: `DesignGallery` accepts new optional prop `onRegenerated: (version: DesignVersion) => void`

Note: `DesignGallery` is used in `ProfilePage.tsx`. The `onRegenerated` prop triggers a profile refresh in the parent.

- [ ] **Step 1: Rewrite `DesignGallery.tsx`**

Replace the file contents entirely:

```typescript
import { useState } from 'react'
import {
  updateDesign,
  deleteDesign,
  getDesignPreviewUrl,
  getDesignPdfUrl,
  regenerateDesign,
  getIngestStatus,
  type DesignVersion,
} from '../api/client'

interface Props {
  versions: DesignVersion[]
  type: 'resume' | 'cover_letter'
  activeId: string | null
  onUpdated: (version: DesignVersion) => void
  onDeleted: (id: string) => void
  onRegenerated?: () => void
}

type CardState = 'idle' | 'regenerating' | 'error'

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

function DesignCard({
  version,
  isActive,
  onSetDefault,
  onDelete,
  onRegenerated,
}: {
  version: DesignVersion
  isActive: boolean
  onSetDefault: () => void
  onDelete: () => void
  onRegenerated?: () => void
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [cardState, setCardState] = useState<CardState>('idle')
  const [regenError, setRegenError] = useState('')

  async function handleRegenerate() {
    setCardState('regenerating')
    setRegenError('')
    try {
      const { job_id } = await regenerateDesign(version.id)
      while (true) {
        const status = await getIngestStatus(job_id)
        if (status.status === 'completed') {
          setCardState('idle')
          onRegenerated?.()
          return
        }
        if (status.status === 'failed') {
          setRegenError(status.message || 'Regeneration failed.')
          setCardState('error')
          return
        }
        await sleep(1000)
      }
    } catch (err: unknown) {
      setRegenError(err instanceof Error ? err.message : 'Regeneration failed.')
      setCardState('error')
    }
  }

  const isRegenerating = cardState === 'regenerating'
  const canRegenerate = !!version.prompt && cardState !== 'regenerating'

  return (
    <div style={{
      border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: 10, overflow: 'hidden', background: 'var(--bg)',
      display: 'flex', flexDirection: 'column', position: 'relative',
    }}>
      {/* Spinner overlay while regenerating */}
      {isRegenerating && (
        <div style={{
          position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.35)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 10, borderRadius: 10,
        }}>
          <span style={{ color: '#fff', fontSize: 12 }}>Regenerando…</span>
        </div>
      )}

      {/* Scaled iframe thumbnail */}
      <div style={{ height: 140, overflow: 'hidden', position: 'relative', background: '#f5f5f5' }}>
        <iframe
          src={getDesignPreviewUrl(version.id)}
          title={version.name}
          sandbox="allow-same-origin allow-scripts"
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
          {canRegenerate && (
            <button
              onClick={handleRegenerate}
              disabled={isRegenerating}
              style={{ fontSize: 11, background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', padding: 0 }}
            >
              Regenerar
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

        {cardState === 'error' && (
          <p style={{ fontSize: 10, color: '#ef4444', margin: '4px 0 0', lineHeight: 1.3 }}>{regenError}</p>
        )}
      </div>
    </div>
  )
}

export function DesignGallery({ versions, type, activeId, onUpdated, onDeleted, onRegenerated }: Props) {
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
          onRegenerated={onRegenerated}
        />
      ))}
    </div>
  )
}
```

- [ ] **Step 2: Build check**

```
cd frontend && rtk tsc --noEmit
```

Expected: 0 errors. If `ProfilePage.tsx` passes `onRegenerated` — check the prop is optional (it is, marked with `?`).

- [ ] **Step 3: Commit**

```bash
cd frontend && rtk git add src/components/DesignGallery.tsx
rtk git commit -m "feat: add per-card Regenerar button to DesignGallery with spinner and polling"
```

---

### Task 7: `ProfilePage.tsx` — Regenerar todos button

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`

**Interfaces:**
- Consumes: `seedDefaultDesigns()`, `getIngestStatus()`, `getProfile()` (all in client.ts)
- Consumes: `DesignGallery` now accepts optional `onRegenerated` prop (Task 6)

- [ ] **Step 1: Locate the designs section in `ProfilePage.tsx`**

Read the full file first. The `DesignGallery` component is rendered somewhere after profile data. Find the section (it will be after the profile is displayed, using `profile.design_versions`).

- [ ] **Step 2: Update the designs section**

Find the import block at the top of `ProfilePage.tsx` and add:

```typescript
import { seedDefaultDesigns, getIngestStatus, getProfile } from '../api/client'
```

(Add only what's not already imported — check existing imports first.)

In the component function body, add state near the top:

```typescript
const [seedingAll, setSeedingAll] = useState(false)
const [seedAllMsg, setSeedAllMsg] = useState('')
const [seedAllError, setSeedAllError] = useState('')
```

Add a helper function inside the component (before the JSX return):

```typescript
async function handleSeedAll() {
  setSeedingAll(true)
  setSeedAllMsg('Iniciando…')
  setSeedAllError('')
  try {
    const { job_id } = await seedDefaultDesigns()
    while (true) {
      const status = await getIngestStatus(job_id)
      setSeedAllMsg(status.message)
      if (status.status === 'completed') {
        const updated = await getProfile()
        onProfileUpdated(updated)
        setSeedingAll(false)
        setSeedAllMsg('')
        return
      }
      if (status.status === 'failed') {
        setSeedAllError(status.message || 'Failed to regenerate designs.')
        setSeedingAll(false)
        return
      }
      await new Promise(r => setTimeout(r, 1000))
    }
  } catch (err: unknown) {
    setSeedAllError(err instanceof Error ? err.message : 'Failed.')
    setSeedingAll(false)
  }
}
```

Find the JSX where `DesignGallery` is rendered for `type="resume"`. Add the "Regenerar todos" button and progress indicator directly above or below the gallery. Also pass `onRegenerated` to `DesignGallery`.

The pattern to add (place immediately above the `DesignGallery type="resume"` render):

```tsx
{/* Regenerar todos button */}
<div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
  <button
    onClick={handleSeedAll}
    disabled={seedingAll}
    style={{
      fontSize: 12, padding: '4px 12px', borderRadius: 6,
      border: '1px solid var(--border)', background: 'var(--bg)',
      color: 'var(--text)', cursor: seedingAll ? 'default' : 'pointer',
    }}
  >
    {seedingAll ? 'Gerando…' : 'Regenerar todos os designs'}
  </button>
  {seedingAll && (
    <span style={{ fontSize: 11, color: 'var(--text)' }}>{seedAllMsg}</span>
  )}
</div>
{seedAllError && (
  <p style={{ fontSize: 12, color: '#ef4444', marginBottom: 8 }}>{seedAllError}</p>
)}
```

Update the `DesignGallery` call for `type="resume"` to pass `onRegenerated`:

```tsx
<DesignGallery
  versions={profile.design_versions}
  type="resume"
  activeId={profile.active_resume_design_id}
  onUpdated={handleDesignUpdated}
  onDeleted={handleDesignDeleted}
  onRegenerated={async () => {
    const updated = await getProfile()
    onProfileUpdated(updated)
  }}
/>
```

The `handleDesignUpdated` and `handleDesignDeleted` handlers already exist in the file — leave them unchanged.

- [ ] **Step 3: Build check**

```
cd frontend && rtk tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
cd frontend && rtk git add src/pages/ProfilePage.tsx
rtk git commit -m "feat: add Regenerar todos os designs button to ProfilePage with polling progress"
```

---

## Self-Review

### 1. Spec coverage

| Spec requirement | Task |
|---|---|
| 15 pre-built templates generated on import | Task 2 (service) + Task 3 (ingest wiring) |
| Parallel with CV analysis (barrier) | Task 3 |
| `generate_resume_template` profile param removed | Task 1 |
| `skip_intent_check` for default seeding | Task 1 + Task 2 |
| Templates in definition order, first `is_default=True` | Task 2 |
| Individual failures skip, never propagate | Task 2 |
| HITL path: templates discarded | Task 3 |
| HITL resolve: templates seeded after resolution | Task 3 |
| `POST /profile/design/seed-defaults` | Task 4 |
| `POST /profile/design/{id}/regenerate` | Task 4 |
| Replaces numbered designs, preserves custom | Task 4 |
| 404 if no prompt on regenerate | Task 4 |
| Frontend: `seedDefaultDesigns()`, `regenerateDesign()` | Task 5 |
| `designs` step label in Portuguese | Task 5 |
| Per-card Regenerar button with spinner | Task 6 |
| Regenerar button only on designs with prompt | Task 6 |
| On regenerate success: reload profile | Task 6 (calls `onRegenerated`) + Task 7 |
| ProfilePage: Regenerar todos button | Task 7 |
| Regenerar todos: shows progress, reloads on done | Task 7 |

### 2. Placeholder scan

None found.

### 3. Type consistency

- `seed_default_designs()` → `list[DesignVersion]` — used consistently in Tasks 2, 3, 4.
- `generate_resume_template(prompt: str, skip_intent_check: bool = False) -> str` — defined Task 1, consumed Task 2 and Task 4.
- `AsyncDesignStart` already defined in `design.py` — reused for new endpoints in Task 4.
- `getIngestStatus` used for polling in Tasks 6 and 7 — already returns `AsyncJobStatus` with `.status` field.
- `onRegenerated?: () => void` prop — defined in Task 6, wired in Task 7.
