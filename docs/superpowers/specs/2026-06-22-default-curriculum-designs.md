# Default Curriculum Designs — Spec

**Date:** 2026-06-22
**Status:** Approved for implementation

---

## Overview

During CV import (onboarding), 15 pre-built resume HTML templates are generated in parallel with CV analysis and attached to the profile. Each template is a full Jinja2 HTML document produced by the LLM from a predefined design prompt. The user can select their preferred template on the profile page or during job application package generation. Individual templates can be regenerated on demand; all 15 can be re-seeded at any time.

---

## 1. Template Catalogue

All 15 prompts are stored as constants in `backend/app/services/default_designs.py`. Names follow the pattern `"N. Name"` where N is 1–15.

| # | Name |
|---|---|
| 1 | Professional Equilibrium |
| 2 | Editorial Design |
| 3 | Techno Minimalism |
| 4 | Interface Aesthetic |
| 5 | Swiss Style |
| 6 | Fancy Dark Mode |
| 7 | Classic Modernism |
| 8 | Gently Neobrutalism |
| 9 | Inclusive Design |
| 10 | Dynamic Monocolor |
| 11 | The Time of Experience |
| 12 | The Lines of Evolution |
| 13 | Future Now |
| 14 | Charm of Last Century |
| 15 | Journalism is Now |

Full prompts are reproduced verbatim in `DEFAULT_TEMPLATES: list[tuple[str, str]]` (name, prompt).

---

## 2. Architecture

### 2.1 Template generation is profile-independent

`generate_resume_template` does not use the `ProfileMaster` parameter — it uses an internal `build_dummy_context()` for Jinja2 validation and hardcoded context docs in the system prompt. The generated templates are pure Jinja2 (`{{ profile.contact.full_name }}`, `{% for exp in profile.work_experiences %}`) rendered at PDF time with the real profile.

**Breaking change:** Remove unused `profile: ProfileMaster` parameter from `generate_resume_template(prompt: str, profile: ProfileMaster) -> str`. New signature: `generate_resume_template(prompt: str) -> str`. Update the single caller in `routers/design.py`.

### 2.2 Parallel seeding during ingest

`POST /profile/ingest` background thread runs two tasks concurrently via `ThreadPoolExecutor`:

```
POST /profile/ingest
└── outer ThreadPoolExecutor(max_workers=2)
    ├── ingest_future   → IngestionService.run() → IngestionResponse
    └── templates_future → seed_default_designs() → list[DesignVersion]

barrier: both futures resolved
├── if ingest failed/HITL → save partial, set job status, ignore templates
├── if ingest succeeded:
│   profile.design_versions = generated_templates
│   if generated_templates:
│       generated_templates[0].is_default = True
│       profile.active_resume_design_id = generated_templates[0].id
│   _repo.save(profile)
│   store.update_job(job_id, status="completed", ...)
```

HITL path: if ingest returns `HITL_REQUIRED`, templates are discarded. They will be generated after HITL resolution completes (same barrier pattern in the resolve thread).

### 2.3 `seed_default_designs()` function

File: `backend/app/services/default_designs.py`

```python
DEFAULT_TEMPLATES: list[tuple[str, str]] = [
    ("1. Professional Equilibrium", "<full prompt text>"),
    ...  # all 15
]

def seed_default_designs(progress_fn: Callable[[int, int], None] | None = None) -> list[DesignVersion]:
    """
    Generates all 15 default resume templates in parallel.
    Individual failures are logged and skipped — never propagated.
    Returns successfully generated templates in definition order.
    First element gets is_default=True (caller must set active_resume_design_id).
    progress_fn(completed, total) called after each template finishes.
    """
    ordered: dict[int, DesignVersion | None] = {}
    completed_count = 0

    with ThreadPoolExecutor(max_workers=15) as pool:
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
                progress_fn(completed_count, len(DEFAULT_TEMPLATES))

    results = [v for i in sorted(ordered) if (v := ordered[i]) is not None]
    if results:
        results[0].is_default = True
    return results


def _generate_one(name: str, prompt: str) -> DesignVersion:
    html_template = generate_resume_template(prompt)
    return DesignVersion(name=name, prompt=prompt, type="resume", html_template=html_template)
```

---

## 3. API Endpoints

### Existing (modified)

`POST /profile/ingest` — seeds 15 templates in parallel with CV analysis (see §2.2).

`POST /profile/ingest/resolve` — seeds 15 templates after HITL resolution (same pattern).

`POST /profile/design/resume` — updated to call `generate_resume_template(prompt)` without profile param.

### New

#### `POST /profile/design/seed-defaults`

Re-generates all 15 default templates and replaces any existing default designs (those whose `name` matches `"N. ..."` pattern OR all `design_versions` with `is_default=True` of type `resume`). User-created custom designs are preserved.

Response: `AsyncDesignStart { job_id: str, status: "processing" }`

Job progress: `step="designs"`, `message="Gerando designs padrão… (N/15)"`, `progress=N/15*100`

When complete: result contains list of generated `DesignVersion` objects.

#### `POST /profile/design/{design_id}/regenerate`

Re-generates a single existing template using its stored `prompt`. Overwrites `html_template` in the same `DesignVersion` (preserves `id`, `name`, `is_default`, `created_at`).

Response: `AsyncDesignStart { job_id: str, status: "processing" }`

Error 404: design not found.
Error 422: design has no stored prompt.

---

## 4. Progress Reporting

The ingest job reports a unified progress stream covering both phases:

| step | message | progress |
|---|---|---|
| `extracting` | Extracting text… | 5% |
| `analyzing` | Sending to AI for analysis… | 20% |
| `validating` | Validating structured output… | 40% |
| `suggestions` | Generating job suggestions… | 50% |
| `designs` | Generating default designs… (N/15) | 55–90% |
| `done` | Profile ready! | 100% |

The `designs` step increments as each template completes. Frontend `STEP_LABELS` maps `"designs"` to a Portuguese label.

---

## 5. Data Model

`DesignVersion` (existing, no changes needed):

```python
class DesignVersion(BaseModel):
    id: str                              # UUID, preserved on regenerate
    name: str                            # "1. Professional Equilibrium"
    prompt: str                          # stored — used by /regenerate
    type: Literal["resume", "cover_letter"]
    html_template: str                   # Jinja2 HTML, overwritten on regenerate
    inherit_from_design_id: Optional[str]
    created_at: datetime
    is_default: bool                     # True for active default
```

`ProfileMaster` (existing, no changes needed):
- `design_versions: list[DesignVersion]` — holds all designs including the 15 defaults
- `active_resume_design_id: Optional[str]` — set to `design_versions[0].id` after seeding

---

## 6. Frontend Changes

### `frontend/src/api/client.ts`

Two new functions:

```typescript
// Re-seed all 15 default designs
export async function seedDefaultDesigns(): Promise<{ job_id: string }>

// Regenerate a single template using its stored prompt
export async function regenerateDesign(designId: string): Promise<{ job_id: string }>
```

Both return a job_id polled via the existing `getDesignJobStatus` / `getIngestStatus` mechanism.

### `frontend/src/components/ResumeUpload.tsx`

Add to `STEP_LABELS`:
```typescript
designs: 'Gerando designs padrão…',
```

### `frontend/src/components/DesignGallery.tsx`

Each design card gains a "Regenerar" button:
- Visible only on cards that have a stored `prompt` (all default designs do)
- Click: calls `regenerateDesign(design.id)` → receives `job_id`
- Card enters `regenerating` state: spinner overlay, button disabled
- Polls job status; on completion: updates card's `html_template` in local state (or refreshes profile)
- On error: shows inline error message on card, button re-enabled

### `frontend/src/pages/ProfilePage.tsx`

"Regenerar todos os designs" button in the designs section:
- Calls `seedDefaultDesigns()` → `job_id`
- Shows full-width progress bar while polling
- Step message from job: "Gerando designs padrão… (N/15)"
- On completion: reloads profile (`GET /profile/`) to refresh `design_versions`

### `frontend/src/components/ApplicationGenerator.tsx` / `DesignSelector.tsx`

No changes required. `DesignSelector` already renders all `design_versions` and uses `active_resume_design_id` as the default selection. With 15 templates now available, they appear automatically.

---

## 7. Error Handling

| Scenario | Behaviour |
|---|---|
| Individual template generation fails (LLM error, Pydantic reject) | Logged as WARNING, skipped. Other templates unaffected. |
| All 15 fail | `design_versions = []`, `active_resume_design_id = None`. Ingest still completes normally. User can retry via "Regenerar todos". |
| Ingest fails (FAILED status) | Templates discarded. Not saved. |
| HITL required | Templates discarded on ingest thread. Re-seeded after HITL resolution. |
| Regenerate single: LLM fails | Job marked `failed`. `html_template` unchanged. |
| seed-defaults while designs exist | Replaces existing default designs (by name pattern match). Preserves user custom designs. |

---

## 8. Out of Scope

- Cover letter default templates (only resume templates in this story)
- Thumbnails / visual previews in the gallery (existing iframe preview is sufficient)
- Ordering / drag-and-drop of the 15 templates
- Editing prompt before regenerating (use the stored prompt as-is; custom prompts go through `POST /profile/design/resume`)
- Rate limiting on seed-defaults endpoint
