# Prompt-Based Resume Generation — Spec

**Date:** 2026-06-23
**Status:** Approved for implementation

---

## Overview

Replace the Jinja2 HTML template system with a prompt-based generation approach. The user uploads multiple reference files during onboarding; all are extracted to text and stored on the profile. When generating an application package, the LLM receives the full reference text plus an editable prompt (with the job description substituted in) and returns a complete, ready-to-render HTML document. Two prompts are stored on the profile: one for the resume, one for the cover letter. Both have defaults and are editable in the Profile page with Save and Reset buttons.

Additionally: remove the "N job roles identified" hint banner from ProfilePage and move that count into a badge on the "Search Jobs" button.

---

## 1. What Is Removed

### Backend
- `backend/app/routers/design.py` — entire router
- `backend/app/services/design_generator.py` — entire file
- `backend/app/services/default_designs.py` — entire file
- `backend/app/services/playwright_renderer.py` — keep only `render_html_to_pdf(html: str) -> bytes` and remove all Jinja2/template/context functions (`build_jinja_context`, `render_template_to_html`, `build_dummy_context`, `render_cover_letter_template_to_html`, `build_dummy_cover_letter_context`, `render_html_to_pdf`)
- `backend/app/models/design.py` — entire file
- All design-related registration in `main.py` (router include)
- All design-related seeding in `profile.py` ingest/resolve threads (the `seed_default_designs` calls, executor patterns for designs)
- `backend/tests/test_services/test_design_generator.py`, `test_default_designs.py`
- `backend/tests/test_routers/test_design.py`, `test_profile_designs.py`

### Frontend
- `frontend/src/components/DesignGallery.tsx`
- `frontend/src/components/DesignEditor.tsx`
- `frontend/src/components/DesignSelector.tsx`
- All design-related imports/state/handlers in `ProfilePage.tsx`
- All design-related API functions in `client.ts` (`seedDefaultDesigns`, `regenerateDesign`, `getDesignJobStatus`, `createResumeDesign`, `createCoverLetterDesign`, `updateDesign`, `deleteDesign`, `setActiveDesign`)

### ProfileMaster fields removed
- `design_versions: list[DesignVersion]`
- `active_resume_design_id: Optional[str]`
- `active_cover_letter_design_id: Optional[str]`

---

## 2. Multi-File Upload

### Backend

**`POST /profile/ingest`** now accepts `files: list[UploadFile]` (up to 20) instead of a single `file: UploadFile`.

Supported formats for text extraction: PDF, DOCX, HTML, TXT, MD, and any plain-text format. Unknown binary formats are skipped with a warning. The existing `extractors.py` handles PDF and DOCX; add HTML/TXT/MD extraction (trivial: strip tags for HTML, read raw for TXT/MD).

**Compilation:** all extracted texts are concatenated in upload order with a separator:

```
=== FILE: {original_filename} ===
{extracted_text}

```

Total compiled text is capped at **60,000 characters** (truncated from the end with a note appended: `\n[truncated — total was {N} chars]`).

The compiled text is stored as `profile.reference_text` on `ProfileMaster`.

**Ingestion LLM call:** receives `reference_text` as the user message (instead of the previous single file text). The system prompt and output schema are unchanged — still parses into `ProfileMaster` fields (XYZ experiences, skills, education, languages, job_suggestions).

**`POST /profile/ingest/resolve`** (HITL): unchanged in structure; the `reference_text` is already on the partial profile, so no re-extraction needed.

### Frontend

**`IngestPage.tsx` / `ResumeUpload.tsx`:** change file input to `multiple`. Show list of selected files (filename + size) before upload. Remove any single-file restriction. Send as `multipart/form-data` with field name `files` (array).

**Label change:** "Upload your resume" → "Upload your documents" with subtitle "CV, work references (Arbeitszeugnis), university transcripts, links — up to 20 files".

**`client.ts`:** `ingestProfile(files: File[])` — builds `FormData` with multiple files appended under key `files`.

---

## 3. Profile Data Model Changes

```python
# backend/app/models/profile.py

class ProfileMaster(BaseModel):
    id: UUID = Field(default_factory=uuid4)
    contact: ContactInfo
    summary: Optional[str] = None
    work_experiences: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    job_suggestions: list[JobSuggestion] = Field(default_factory=list)

    # New fields
    reference_text: str = Field(default="", description="Compiled text from all uploaded reference files")
    cv_prompt: str = Field(default=DEFAULT_CV_PROMPT)
    cover_letter_prompt: str = Field(default=DEFAULT_CL_PROMPT)

    # Removed: design_versions, active_resume_design_id, active_cover_letter_design_id
```

`DEFAULT_CV_PROMPT` and `DEFAULT_CL_PROMPT` are module-level constants in a new file `backend/app/services/prompt_defaults.py`.

---

## 4. Prompt Defaults

**File:** `backend/app/services/prompt_defaults.py`

```python
DEFAULT_CV_PROMPT: str = """baseado nesse arquivo em anexo, crie um curriculum pra mim para esta vaga com o design abaixo:
VAGA:
{JOB_DESCRIPTION}
DESIGN:
[... full prompt text as provided by user ...]
RESTRIÇÕES:
1. HTML APENAS, SEM TEXTO EXTRA, SEM EXPLICAÇÕES.
2. FORMATADO PARA IMPRESSÃO, APENAS UMA PÁGINA, SEM RECORTE.
3. TODO O TEXTO EM INGLES, SEM PORTUGUES OU OUTRA LINGUA.
4. CAMPO PROFESSIONAL SUMMARY DEVE SER RELACIONADO E DIRECIONADO À VAGA EM QUESTÃO, COMO UMA MINI CARTA DE APRESENTAÇÃO DO PORQUE O CANDIDATO É BOM.
5. CAMPO SKILLS DEVEM FAZER SENTIDO COM A VAGA, APONTANDO AS SKILLS QUE O CANDIDATO TEM EXIGIDOS PARA A VAGA."""

DEFAULT_CL_PROMPT: str = """baseado nesse arquivo em anexo, crie uma carta de apresentação para esta vaga com o design abaixo:
VAGA:
{JOB_DESCRIPTION}
DESIGN:
[... same header CSS/HTML as resume prompt, but body is full-width single column with letter paragraphs ...]
RESTRIÇÕES:
1. HTML APENAS, SEM TEXTO EXTRA, SEM EXPLICAÇÕES.
2. FORMATADO PARA IMPRESSÃO, APENAS UMA PÁGINA, SEM RECORTE.
3. TODO O TEXTO EM INGLES, SEM PORTUGUES OU OUTRA LINGUA.
4. CARTA DEVE SER RELACIONADA E DIRECIONADA À VAGA, DESTACANDO PORQUE O CANDIDATO É BOM PARA ELA."""
```

The placeholder substituted at generation time is `{JOB_DESCRIPTION}` (not the Portuguese version — internal only). At generation time:

```python
job_desc = f"{job.title} at {job.company}\n\n{job.description or ''}\n\nURL: {job.url or ''}"
final_prompt = profile.cv_prompt.replace("{JOB_DESCRIPTION}", job_desc)
```

**Cover letter prompt HTML structure:** same `cv-header` block (blue header, contact info, SVG decoration), but the body below is:

```html
<div class="cl-body">
  <p class="cl-p">paragraph text...</p>
  ...
</div>
```

With CSS:
```css
.cl-body { padding: 20px 24px; }
.cl-p { font-size: 9.5pt; line-height: 1.7; color: #1A2332; margin-bottom: 10px; }
```

No `.cv-body`, `.sidebar`, `.main-col`.

---

## 5. Prompt-Based Application Generation

### Backend — `backend/app/services/application.py`

**New flow:**

```python
def generate_application_package(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
) -> dict:
    resume_html = _generate_html(profile, job, profile.cv_prompt)
    resume_pdf = _html_to_pdf(resume_html)

    cl_html = _generate_html(profile, job, profile.cover_letter_prompt)
    cl_pdf = _html_to_pdf(cl_html)

    cover_letter_text = _extract_text_from_html(cl_html)  # strip tags for preview

    return {
        "job_id": job.id,
        "resume_pdf_base64": _to_b64(resume_pdf),
        "cover_letter_text": cover_letter_text,
        "cover_letter_pdf_base64": _to_b64(cl_pdf),
    }


def _generate_html(profile: ProfileMaster, job: JobPosting, prompt: str) -> str:
    """Send reference_text + filled prompt to LLM; return raw HTML string."""
    job_desc = f"{job.title} at {job.company}\n\n{job.description or ''}\n\nURL: {job.url or ''}"
    filled = prompt.replace("{JOB_DESCRIPTION}", job_desc)

    client = get_llm_client()
    response = client.chat.completions.create(
        model=settings.active_model,
        messages=[
            {
                "role": "user",
                "content": f"=== REFERENCE FILES ===\n{profile.reference_text}\n\n=== INSTRUCTIONS ===\n{filled}",
            }
        ],
        temperature=0.3,
    )
    raw = response.choices[0].message.content or ""
    # Strip any markdown fences the LLM might add
    raw = raw.strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    return raw.strip()


def _html_to_pdf(html: str) -> bytes:
    from app.services.playwright_renderer import render_html_to_pdf
    return render_html_to_pdf(html)


def _extract_text_from_html(html: str) -> str:
    """Strip HTML tags for plain-text cover letter preview."""
    import re
    return re.sub(r"<[^>]+>", " ", html).strip()
```

**Remove** `resume_design_id` and `cover_letter_design_id` parameters from the router and service. Remove `_find_design`, `_render_resume`, `_render_cover_letter`, `generate_master_resume` (or keep master resume as a simpler call using just cv_prompt with no job substitution — see §5.1).

**Router `GenerateRequest`:**
```python
class GenerateRequest(BaseModel):
    job: JobPosting
    match: MatchScore
    # removed: resume_design_id, cover_letter_design_id
```

#### 5.1 Master Resume Download

`GET /application/master-resume` now calls `_generate_html` with an empty/generic job description:

```python
job_desc = "General purpose — showcase all experience and skills."
filled = profile.cv_prompt.replace("{JOB_DESCRIPTION}", job_desc)
```

Same Playwright → PDF flow.

---

## 6. Prompt Editor — Backend

**`PATCH /profile/prompts`**

```python
class UpdatePromptsRequest(BaseModel):
    cv_prompt: Optional[str] = None
    cover_letter_prompt: Optional[str] = None
```

Merges non-None fields into the profile and saves. Returns updated `ProfileMaster`.

Lives in `backend/app/routers/profile.py` (new endpoint, no new router file).

---

## 7. Prompt Editor — Frontend

**`ProfilePage.tsx`:** replace the entire "Resume Design" and "Cover Letter Design" sections with a single "Generation Prompts" section.

Each prompt block:
```
[Label: "Resume Prompt" | "Cover Letter Prompt"]
<textarea rows=20 style="font-family: monospace; font-size: 11px; width: 100%">
  {current prompt value}
</textarea>
[Save]  [Reset to default]
```

State per block: `{ value: string, saved: bool, saving: bool }`.

- **Save:** `PATCH /profile/prompts` with the changed field. Show "Saved ✓" for 2s.
- **Reset to default:** sets textarea value to the hardcoded default constant (imported from a TS constants file). Does NOT auto-save — user must click Save.

**`client.ts`:**
```typescript
export async function updatePrompts(data: { cv_prompt?: string; cover_letter_prompt?: string }): Promise<ProfileMaster>
```

**`DEFAULT_CV_PROMPT` and `DEFAULT_CL_PROMPT`** exported from `frontend/src/constants/promptDefaults.ts` (mirrors the backend defaults — plain TS string constants).

---

## 8. UX Fix — Job Suggestions Badge

**Remove** the hint banner from `ProfilePage.tsx` (lines 293-309 — the blue `<div>` with "N job roles identified from your profile. Search Jobs →").

**Add** a badge to the "Search Jobs" button showing `profile.job_suggestions.length` when > 0:

```tsx
<button onClick={onSearchJobs} style={...}>
  Search Jobs
  {profile.job_suggestions.length > 0 && (
    <span style={{
      marginLeft: 6,
      background: 'var(--accent)',
      color: 'white',
      borderRadius: '50%',
      fontSize: 10,
      fontWeight: 700,
      padding: '1px 5px',
      verticalAlign: 'middle',
    }}>
      {profile.job_suggestions.length}
    </span>
  )}
</button>
```

---

## 9. ApplicationGenerator.tsx Changes

Remove `DesignSelector` blocks and all design-related state (`resumeDesignId`, `coverLetterDesignId`). The generate button calls:

```typescript
generateApplication(job, match)  // no design IDs
```

The component becomes simpler: just the generate button, loading state, download buttons, letter preview.

---

## 10. Error Handling

| Scenario | Behaviour |
|---|---|
| LLM returns non-HTML | Return 500 with detail "LLM did not return valid HTML" |
| reference_text empty | Warn in logs; proceed with empty context (user may not have uploaded files yet) |
| File extraction fails for one file | Log warning, skip that file, continue with others |
| Unsupported file type | Skip silently |
| Prompt missing `{JOB_DESCRIPTION}` | Substitute nothing (no error) — LLM receives prompt as-is |
| More than 20 files | Return 422 "Maximum 20 files allowed" |

---

## 11. Tests

**Removed:** all design tests listed in §1.

**New / updated:**

- `test_routers/test_profile.py`: ingest accepts multiple files, compiles reference_text, caps at 60k chars
- `test_services/test_application.py`: `_generate_html` substitutes job description into prompt; strips markdown fences from LLM output
- `test_routers/test_application.py`: `POST /application/generate` no longer accepts design IDs; returns resume + cover letter PDFs
- `test_routers/test_profile.py`: `PATCH /profile/prompts` updates cv_prompt and/or cover_letter_prompt

---

## 12. Out of Scope

- Re-extraction of already-uploaded files without re-importing
- Per-job custom prompt overrides at generation time
- Preview of generated HTML before PDF
- Version history of prompts
- LLM retry logic for application generation (single attempt; fallback = error)
