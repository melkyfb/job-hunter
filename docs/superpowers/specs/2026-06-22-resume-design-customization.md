# Resume & Cover Letter Design Customization

**Date:** 2026-06-22  
**Stories:** STORY-1 (Resume Design), STORY-2 (Cover Letter Design), STORY-3 (Design Versions)  
**Status:** Approved for implementation

---

## Overview

Allow users to customize the visual and structural design of their master resume and cover letter using a free-form natural language prompt. The AI interprets the prompt and generates a complete Jinja2 HTML+CSS template. Playwright renders the template to PDF. Multiple design versions can be saved and selected per-job when generating an application package.

---

## 1. Data Model

### New model: `DesignVersion`

Added to `backend/app/models/profile.py`:

```python
class DesignVersion(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    name: str                              # user-given label, e.g. "Tech Modern Blue"
    prompt: str                            # original free-form prompt
    type: Literal["resume", "cover_letter"]
    html_template: str                     # complete self-contained Jinja2 HTML template
    inherit_from_design_id: Optional[str] = None  # cover letter can inherit CSS from a resume design
    created_at: datetime = Field(default_factory=datetime.now)
    is_default: bool = False
```

### Changes to `ProfileMaster`

```python
design_versions: list[DesignVersion] = Field(default_factory=list)
active_resume_design_id: Optional[str] = None
active_cover_letter_design_id: Optional[str] = None
```

Persisted inside the existing `~/.job_hunter/profile_master.json`. No new files required.

### Jinja2 context available to templates

Every template receives a single `profile` variable of type `ProfileMaster`. Key paths:

| Variable | Type |
|----------|------|
| `profile.contact.full_name` | `str` |
| `profile.contact.email` | `str` |
| `profile.contact.phone` | `Optional[str]` |
| `profile.contact.location` | `Optional[str]` |
| `profile.contact.linkedin_url` | `Optional[str]` |
| `profile.contact.github_url` | `Optional[str]` |
| `profile.summary` | `Optional[str]` |
| `profile.work_experiences` | `list[WorkExperience]` |
| `exp.role`, `exp.company`, `exp.location` | `str` |
| `exp.start_date`, `exp.end_date` | `datetime` |
| `exp.is_current` | `bool` |
| `exp.achievements` | `list[XYZExperience]` |
| `ach.as_bullet` | `str` — formatted "action metric context" |
| `exp.technologies` | `list[str]` |
| `profile.skills` | `list[Skill]` — `.name`, `.level.value` |
| `profile.education` | `list[Education]` — `.degree`, `.field_of_study`, `.institution`, `.end_date` |
| `profile.languages` | `list[Language]` — `.name`, `.proficiency` |

---

## 2. Backend

### 2.1 New service: `design_generator.py`

`backend/app/services/design_generator.py`

**`generate_resume_template(prompt, profile) -> str`**

- LLM system prompt provides: Jinja2 variable reference, HTML constraints (`@page { size: A4; margin: 0 }`, inline CSS only, no external resources), instruction to render all profile sections (summary, experience, skills, education, languages), and prohibition on inventing data.
- LLM user prompt: the user's free-form design description.
- Uses `response_format: json_object` wrapping `{ "html_template": "..." }` to avoid markdown fences.
- Self-correction loop (max 3 retries): validates that the output renders without Jinja2 errors against a dummy profile.
- Returns the raw HTML string.

**`generate_cover_letter_template(prompt, profile, inherit_from) -> str`**

- If `inherit_from` is a `DesignVersion`, extracts the `<style>...</style>` block from its `html_template` and injects it into the LLM context as "base CSS to inherit".
- LLM generates a cover letter HTML template. Jinja2 variables available: `profile.contact.*`, `letter_body` (plain text, injected at render time), `job.title`, `job.company`.
- Same retry/validation loop.

### 2.2 New service: `playwright_renderer.py`

`backend/app/services/playwright_renderer.py`

```python
def render_html_to_pdf(html: str) -> bytes:
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf = page.pdf(format="A4", print_background=True)
        browser.close()
    return pdf

def render_template_to_html(template: str, profile: ProfileMaster) -> str:
    from jinja2 import Environment, BaseLoader
    env = Environment(loader=BaseLoader())
    t = env.from_string(template)
    return t.render(profile=profile)
```

### 2.3 Changes to `application.py`

`generate_application_package(job, match, profile, resume_design_id?, cover_letter_design_id?)`:

- If `resume_design_id` provided: fetch `DesignVersion` from profile, render via `playwright_renderer`; else fall back to existing `render_resume_pdf` (ReportLab).
- If `cover_letter_design_id` provided: render cover letter HTML template with Playwright; else use existing text → ReportLab flow.

### 2.4 New router: `design.py`

`backend/app/routers/design.py`, prefix `/profile/design`

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/resume` | Generate resume design (async job, returns `job_id`) |
| `POST` | `/cover-letter` | Generate cover letter design (async job, returns `job_id`) |
| `GET` | `/{id}/preview-html` | Return rendered HTML string (iframe source) |
| `GET` | `/{id}/pdf` | Return PDF bytes via Playwright |
| `PATCH` | `/{id}` | Update name or `is_default` |
| `DELETE` | `/{id}` | Remove version from profile |

Both `POST` endpoints use the existing async job + polling infrastructure (`job_store.py`). Poll via `GET /profile/ingest/{job_id}` — reuses the same status endpoint.

### 2.5 Dockerfile changes

`backend/Dockerfile` — after `pip install`:
```dockerfile
RUN playwright install chromium --with-deps
```

---

## 3. Frontend

### 3.1 New components

**`DesignEditor.tsx`** (`frontend/src/components/DesignEditor.tsx`)

Props: `type: 'resume' | 'cover_letter'`, `profile: ProfileMaster`, `onSaved: (version: DesignVersion) => void`

States:
1. **idle** — textarea with placeholder prompt example (auto-generated from profile's job area), "Generate Design" button
2. **generating** — reuses existing `ProgressBar` + polling hook
3. **preview** — `<iframe>` pointing to `GET /profile/design/{id}/preview-html`, name input, action buttons: "Save version", "Download PDF", "Regenerate", "Set as default"

The textarea placeholder is a static example tailored to the profile's most recent job role, e.g.:
> *"Modern tech resume with a dark left sidebar showing name, contact and skills in white on deep blue. Right section for experience with bold company names, XYZ bullet points, and technology chips. Clean Inter font throughout. Compact spacing."*

**`DesignGallery.tsx`** (`frontend/src/components/DesignGallery.tsx`)

Props: `versions: DesignVersion[]`, `activeId: string | null`, `onSelect`, `onDelete`, `onSetDefault`

Renders a flex grid of cards. Each card contains:
- A thumbnail: `<iframe>` scaled via `transform: scale(0.18)` pointing to `preview-html`
- Name label
- "★ default" badge if `is_default`
- "Select" / "Delete" buttons

**`DesignSelector.tsx`** (`frontend/src/components/DesignSelector.tsx`)

A reusable `<select>` dropdown populated from `design_versions` filtered by `type`. Used inside `ApplicationGenerator.tsx`.

### 3.2 Changes to `ProfilePage.tsx`

After the existing action buttons, add a collapsible "Resume Design" section containing:
1. `DesignGallery` showing saved resume designs
2. `DesignEditor` for creating a new resume design
3. Separate collapsible "Cover Letter Design" section with its own `DesignGallery` + `DesignEditor` (with "Inherit from resume design" checkbox)

### 3.3 Changes to `ApplicationGenerator.tsx`

Before the "Generate Application Package" button, add two `DesignSelector` dropdowns:
- Resume design (options: "Default (Classic)", ...saved resume versions)
- Cover letter design (options: "Default (Classic)", "Inherit from resume", ...saved cover letter versions)

Selected IDs passed as `resume_design_id` and `cover_letter_design_id` in the generate request body.

### 3.4 API client additions (`client.ts`)

```typescript
interface DesignVersion {
  id: string
  name: string
  prompt: string
  type: 'resume' | 'cover_letter'
  html_template: string
  inherit_from_design_id?: string
  created_at: string
  is_default: boolean
}

// ProfileMaster gains:
design_versions: DesignVersion[]
active_resume_design_id: string | null
active_cover_letter_design_id: string | null

// New functions:
startGenerateResumeDesign(prompt: string) → AsyncJobStart
startGenerateCoverLetterDesign(prompt: string, inheritFromId?: string) → AsyncJobStart
getDesignPreviewUrl(designId: string) → string  // GET /profile/design/{id}/preview-html
getDesignPdf(designId: string) → Promise<Blob>
updateDesign(designId: string, patch: {name?: string, is_default?: boolean}) → Promise<DesignVersion>
deleteDesign(designId: string) → Promise<void>
```

---

## 4. Implementation Order

1. **Data model** — `DesignVersion` + `ProfileMaster` fields (backend + frontend types)
2. **`design_generator.py`** — LLM template generation for resume
3. **`playwright_renderer.py`** — Jinja2 render + Playwright PDF
4. **Dockerfile** — add Playwright + chromium
5. **`design.py` router** — all endpoints
6. **`application.py`** — wire in optional design IDs
7. **`DesignEditor.tsx`** — prompt UI + preview iframe
8. **`DesignGallery.tsx`** — version grid
9. **`DesignSelector.tsx`** — dropdown for ApplicationGenerator
10. **`ProfilePage.tsx`** — integrate editor + gallery
11. **`ApplicationGenerator.tsx`** — add design selectors
12. **Cover letter design** — `generate_cover_letter_template` + `DesignEditor` for type=cover_letter

---

## 5. Fallback Behavior

- If no custom design exists: `application.py` falls back to existing ReportLab renderer (`render_resume_pdf`) and existing cover letter text → PDF flow. No breaking change.
- If Playwright fails: catch exception, fall back to ReportLab, log warning.
- If LLM generates invalid Jinja2: self-correction loop catches the render error and feeds it back to the model.

---

## 6. Out of Scope

- Export/import of design versions between users
- Real-time collaborative editing
- Versioning history within a single design (edit-in-place overwrites)
- Mobile-optimized resume templates
