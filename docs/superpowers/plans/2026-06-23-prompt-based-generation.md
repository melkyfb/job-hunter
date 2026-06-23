# Prompt-Based CV Generation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace Jinja2 template system with LLM-generated HTML, add multi-file upload with per-file relevance extraction, and store editable prompt fields on the profile.

**Architecture:** Each uploaded file is raw-extracted then sent through an LLM relevance filter to strip boilerplate, compiled into `reference_text` stored on `ProfileMaster`. At generation time, the LLM receives `reference_text` + the user's editable prompt (with job data substituted in) and returns complete HTML; Playwright renders it to PDF.

**Tech Stack:** FastAPI, Pydantic v2, Python 3.12, OpenAI-compatible LLM client, Playwright (PDF), React 18, TypeScript

## Global Constraints

- All Python files must start with `from __future__ import annotations`
- Pydantic v2 only: `model_validate()`, `model_dump(mode="json")`, `model_dump_json()`
- `{JOB_DESCRIPTION}` is the internal placeholder string substituted at generation time — NOT the Portuguese version
- Multi-file cap: max 20 files per upload request (422 if exceeded)
- Per-file extraction cap: 4000 chars per file after LLM relevance filtering
- Total `reference_text` cap: 60,000 chars (truncate from end with note if exceeded)
- Always use `rtk` prefix for shell commands
- All tests use `pytest` with `TestClient` (sync) and `unittest.mock.patch`

---

## File Map

### Created
- `backend/app/services/prompt_defaults.py` — DEFAULT_CV_PROMPT + DEFAULT_CL_PROMPT constants
- `backend/app/services/file_processor.py` — per-file LLM relevance extraction + compile_reference_text()
- `frontend/src/constants/promptDefaults.ts` — TS mirror of the two default prompts

### Modified
- `backend/app/models/profile.py` — remove design fields, add reference_text/cv_prompt/cover_letter_prompt
- `backend/app/services/extractors.py` — add TXT/MD support
- `backend/app/services/application.py` — full rewrite to LLM-based generation
- `backend/app/services/playwright_renderer.py` — keep only render_html_to_pdf()
- `backend/app/services/ingestion.py` — accept reference_text instead of filename+text
- `backend/app/routers/profile.py` — multi-file ingest, PATCH /profile/prompts, remove design seeding
- `backend/app/routers/application.py` — remove design IDs from GenerateRequest
- `backend/app/main.py` — remove design router import
- `frontend/src/api/client.ts` — update interfaces + API functions
- `frontend/src/components/ApplicationGenerator.tsx` — remove DesignSelector
- `frontend/src/components/ResumeUpload.tsx` — multi-file upload
- `frontend/src/pages/ProfilePage.tsx` — prompt editor, badge fix, remove design sections

### Deleted
- `backend/app/models/design.py`
- `backend/app/routers/design.py`
- `backend/app/services/design_generator.py`
- `backend/app/services/default_designs.py`
- `backend/app/services/cover_letter.py`
- `backend/tests/test_routers/test_design.py`
- `backend/tests/test_routers/test_profile_designs.py`
- `backend/tests/test_services/test_design_generator.py`
- `backend/tests/test_services/test_default_designs.py`
- `backend/tests/test_services/test_playwright_renderer.py`
- `frontend/src/components/DesignGallery.tsx`
- `frontend/src/components/DesignEditor.tsx`
- `frontend/src/components/DesignSelector.tsx`

---

## Task 1: Prompt Defaults Constants

**Files:**
- Create: `backend/app/services/prompt_defaults.py`
- Create: `frontend/src/constants/promptDefaults.ts`

**Interfaces:**
- Produces: `DEFAULT_CV_PROMPT: str`, `DEFAULT_CL_PROMPT: str` (Python); `DEFAULT_CV_PROMPT: string`, `DEFAULT_CL_PROMPT: string` (TS)

- [ ] **Step 1: Create backend/app/services/prompt_defaults.py**

```python
from __future__ import annotations

DEFAULT_CV_PROMPT: str = """\
baseado nesse arquivo em anexo, crie um curriculum pra mim para esta vaga com o design abaixo:
VAGA:
{JOB_DESCRIPTION}
DESIGN:

## Contexto
Crie um currículum em HTML single-file, otimizado para impressão em A4, com design moderno em duas colunas. O arquivo deve ser autossuficiente (sem dependências externas exceto a fonte via CSS), pronto para abrir no navegador e imprimir/salvar como PDF via Ctrl+P.

---

## Layout Geral

- **Formato:** Página única A4 (`@page { size: A4; margin: 0; }`)
- **Estrutura:** div `.cv-wrap` com:
  1. Header superior (`div.cv-header`) — largura total
  2. Body (`div.cv-body`) com duas colunas lado a lado:
     - **Sidebar esquerda** (`div.sidebar`) — 32% da largura
     - **Coluna principal** (`div.main-col`) — 68% da largura
- **Fonte base:** Arial, sans-serif; `font-size: 9pt`
- **Sem margens** no body (`margin: 0; padding: 0`)
- **Background do body:** `#F0F4FC` (azul muito claro) — transparente no print

```css
@page { size: A4; margin: 0; }
body { font-family: Arial, sans-serif; font-size: 9pt; background: #F0F4FC; color: #1A2332; margin: 0; padding: 0; }
.cv-wrap { width: 210mm; min-height: 297mm; margin: 0 auto; background: #fff; }
.cv-body { display: flex; }
.sidebar { width: 32%; background: #F0F4FC; padding: 16px 14px; border-right: 2px solid #C3D4EF; }
.main-col { width: 68%; padding: 16px 18px; }
```

---

## Header (.cv-header)

- **Background:** `#1E4D9E`
- **Cor do texto:** `#fff`
- **Padding:** `18px 20px 14px`
- **Posição relativa** para conter o SVG decorativo
- Contém: `.cv-name` (18pt, 800), `.cv-role` (10pt, opacity 0.9), `.cv-contacts` (flex, gap 14px, 8pt)

```html
<div class="cv-header" style="position:relative;background:#1E4D9E;color:#fff;padding:18px 20px 14px;">
  <svg xmlns="http://www.w3.org/2000/svg" class="no-print"
    style="position:absolute;top:0;right:0;width:380px;height:110px;pointer-events:none;overflow:visible;"
    viewBox="0 0 380 110">
    <defs>
      <pattern id="dp" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
        <circle cx="2" cy="2" r="1.1" fill="rgba(255,255,255,0.22)"/>
      </pattern>
    </defs>
    <rect x="60" y="-5" width="320" height="120" fill="url(#dp)"/>
    <circle cx="330" cy="18" r="65" fill="rgba(147,197,253,0.07)"/>
    <circle cx="365" cy="85" r="48" fill="rgba(147,197,253,0.06)"/>
    <line x1="380" y1="0" x2="255" y2="110" stroke="rgba(255,255,255,0.07)" stroke-width="1.5"/>
  </svg>
  <div class="cv-name" style="font-size:18pt;font-weight:800;">{{NOME}}</div>
  <div class="cv-role" style="font-size:10pt;opacity:0.9;margin-top:3px;">{{CARGO}}</div>
  <div class="cv-contacts" style="display:flex;flex-wrap:wrap;gap:14px;font-size:8pt;margin-top:10px;">
    <span>{{CIDADE}}, {{PAÍS}}</span>
    <span>{{TELEFONE}}</span>
    <span><a href="mailto:{{EMAIL}}" style="color:rgba(255,255,255,0.85);text-decoration:none;">{{EMAIL}}</a></span>
    <span><a href="{{LINKEDIN}}" style="color:rgba(255,255,255,0.85);text-decoration:none;">{{LINKEDIN_DISPLAY}}</a></span>
  </div>
</div>
```

```css
@media print { .no-print { display: none !important; } }
```

---

## Sidebar

```css
.sec { font-size:8.5pt;font-weight:800;text-transform:uppercase;letter-spacing:0.8px;color:#1E4D9E;border-bottom:2px solid #1E4D9E;padding-bottom:3px;margin:14px 0 8px; }
.sec:first-child { margin-top:0; }
.chip-lbl { font-size:7pt;font-weight:700;text-transform:uppercase;letter-spacing:0.5px;color:#4A5568;margin:6px 0 3px; }
.chips { display:flex;flex-wrap:wrap;gap:3px;margin-bottom:4px; }
.chip { padding:2px 7px;border-radius:10px;font-size:7pt;font-weight:700;border:1px solid;display:inline-block; }
.c-b { background:#DBEAFE;color:#1E40AF;border-color:#93C5FD; }
.c-g { background:#D1FAE5;color:#065F46;border-color:#6EE7B7; }
.c-a { background:#FEF3C7;color:#92400E;border-color:#FCD34D; }
.c-p { background:#EDE9F8;color:#6B21A8;border-color:#C4B5FD; }
.c-s { background:#F1F5F9;color:#475569;border-color:#CBD5E1; }
.cert { margin-bottom:7px; }
.cert strong { font-size:8pt;display:block;color:#1A2332;line-height:1.3; }
.cert .m { font-size:7pt;color:#718096;display:block; }
.cert .ip { font-size:7pt;color:#7A5500;font-weight:700; }
.edu { margin-bottom:8px; }
.edu strong { font-size:8pt;display:block;color:#1A2332; }
.edu .m { font-size:7pt;color:#718096;display:block; }
.lang { margin-bottom:8px; }
.lang-n { font-size:8pt;font-weight:700; }
.lang-l { font-size:7pt;color:#718096;margin-bottom:3px; }
.bar { height:5px;background:#E2E8F0;border-radius:3px;overflow:hidden; }
.bf { height:100%;border-radius:3px;background:linear-gradient(to right,#1E4D9E,#60A5FA); }
```

Larguras de barra de idioma: Nativo=100%, C1=90%, B2=72%, B1=52%, A2=22%, A1=10%

---

## Coluna Principal

```css
.sum-p { font-size:8.5pt;line-height:1.65;color:#1A2332;margin-bottom:4px;border-left:3px solid #1E4D9E;padding-left:10px; }
.job { margin-bottom:14px;padding-bottom:12px;border-bottom:1px solid #C3D4EF; }
.job:last-child { border-bottom:none;margin-bottom:0; }
.jt { display:flex;justify-content:space-between;align-items:flex-start;gap:6px; }
.jtl { font-size:9.5pt;font-weight:700;color:#1A2332; }
.jpr { font-size:7.5pt;font-weight:700;white-space:nowrap;background:#EBF1FB;color:#1E4D9E;padding:1px 8px;border-radius:10px;border:1px solid #C3D4EF; }
.jco { font-size:8.5pt;font-weight:600;color:#1E4D9E;margin:2px 0; }
.jtg { font-size:7pt;color:#718096;font-style:italic;margin-bottom:6px;line-height:1.4; }
.b { padding-left:14px; }
.b li { margin-bottom:4px;font-size:8.5pt;line-height:1.5; }
.b li strong { color:#163d80; }
```

Bullets usam fórmula XYZ do Google: "[Verbo] [Métrica de impacto] ao [tecnologia] — [contexto/resultado]"

---

## Paleta

| Token | Valor | Uso |
|-------|-------|-----|
| primary | #1E4D9E | headers, links, bordas |
| primary-dark | #163d80 | hover, texto forte |
| bg-light | #EBF1FB | badges, sidebar bg |
| border | #C3D4EF | bordas gerais |
| text | #1A2332 | texto principal |
| gray | #718096 | metadados |

RESTRIÇÕES:
1. HTML APENAS, SEM TEXTO EXTRA, SEM EXPLICAÇÕES.
2. FORMATADO PARA IMPRESSÃO, APENAS UMA PÁGINA, SEM RECORTE.
3. TODO O TEXTO EM INGLÊS, SEM PORTUGUÊS OU OUTRA LÍNGUA.
4. CAMPO PROFESSIONAL SUMMARY DEVE SER RELACIONADO E DIRECIONADO À VAGA EM QUESTÃO, COMO UMA MINI CARTA DE APRESENTAÇÃO DO PORQUE O CANDIDATO É BOM.
5. CAMPO SKILLS DEVEM FAZER SENTIDO COM A VAGA, APONTANDO AS SKILLS QUE O CANDIDATO TEM QUE SÃO EXIGIDAS PARA A VAGA.\
"""

DEFAULT_CL_PROMPT: str = """\
baseado nesse arquivo em anexo, crie uma carta de apresentação para esta vaga com o design abaixo:
VAGA:
{JOB_DESCRIPTION}
DESIGN:

## Contexto
Crie uma carta de apresentação em HTML single-file, otimizada para impressão em A4. O arquivo deve ser autossuficiente, pronto para abrir no navegador e imprimir/salvar como PDF via Ctrl+P.

---

## Layout

- **Formato:** Página única A4 (`@page { size: A4; margin: 0; }`)
- **Estrutura:** div `.cv-wrap` com:
  1. Header superior (`div.cv-header`) — IDÊNTICO ao do currículo (mesmo CSS, mesmo SVG decorativo)
  2. Body (`div.cl-body`) — largura total, sem colunas

```css
@page { size: A4; margin: 0; }
body { font-family: Arial, sans-serif; font-size: 9pt; background: #F0F4FC; color: #1A2332; margin: 0; padding: 0; }
.cv-wrap { width: 210mm; min-height: 297mm; margin: 0 auto; background: #fff; }
.cv-header { position: relative; background: #1E4D9E; color: #fff; padding: 18px 20px 14px; }
.cv-name { font-size: 18pt; font-weight: 800; }
.cv-role { font-size: 10pt; opacity: 0.9; margin-top: 3px; }
.cv-contacts { display: flex; flex-wrap: wrap; gap: 14px; font-size: 8pt; margin-top: 10px; }
.cv-contacts a { color: rgba(255,255,255,0.85); text-decoration: none; }
.cl-body { padding: 28px 32px; }
.cl-p { font-size: 9.5pt; line-height: 1.7; color: #1A2332; margin-bottom: 12px; }
.cl-salutation { font-size: 9.5pt; font-weight: 700; color: #1A2332; margin-bottom: 16px; }
.cl-closing { margin-top: 24px; font-size: 9.5pt; color: #1A2332; }
@media print { .no-print { display: none !important; } }
```

## Header (mesmo SVG decorativo do currículo)

```html
<div class="cv-header">
  <svg xmlns="http://www.w3.org/2000/svg" class="no-print"
    style="position:absolute;top:0;right:0;width:380px;height:110px;pointer-events:none;overflow:visible;"
    viewBox="0 0 380 110">
    <defs>
      <pattern id="dp" x="0" y="0" width="20" height="20" patternUnits="userSpaceOnUse">
        <circle cx="2" cy="2" r="1.1" fill="rgba(255,255,255,0.22)"/>
      </pattern>
    </defs>
    <rect x="60" y="-5" width="320" height="120" fill="url(#dp)"/>
    <circle cx="330" cy="18" r="65" fill="rgba(147,197,253,0.07)"/>
    <circle cx="365" cy="85" r="48" fill="rgba(147,197,253,0.06)"/>
    <line x1="380" y1="0" x2="255" y2="110" stroke="rgba(255,255,255,0.07)" stroke-width="1.5"/>
  </svg>
  <div class="cv-name">{{NOME}}</div>
  <div class="cv-role">{{CARGO}}</div>
  <div class="cv-contacts">
    <span>{{CIDADE}}, {{PAÍS}}</span>
    <span><a href="mailto:{{EMAIL}}">{{EMAIL}}</a></span>
    <span><a href="{{LINKEDIN}}">{{LINKEDIN_DISPLAY}}</a></span>
  </div>
</div>
```

## Body (abaixo do header — sem colunas)

```html
<div class="cl-body">
  <div class="cl-salutation">Dear Hiring Manager,</div>
  <p class="cl-p">{{PARÁGRAFO 1 — introdução e fit com a vaga}}</p>
  <p class="cl-p">{{PARÁGRAFO 2 — conquista relevante com métrica}}</p>
  <p class="cl-p">{{PARÁGRAFO 3 — por que esta empresa/vaga}}</p>
  <div class="cl-closing">
    Best regards,<br/>
    <strong>{{NOME}}</strong>
  </div>
</div>
```

RESTRIÇÕES:
1. HTML APENAS, SEM TEXTO EXTRA, SEM EXPLICAÇÕES.
2. FORMATADO PARA IMPRESSÃO, APENAS UMA PÁGINA, SEM RECORTE.
3. TODO O TEXTO EM INGLÊS, SEM PORTUGUÊS OU OUTRA LÍNGUA.
4. CARTA DEVE SER RELACIONADA E DIRECIONADA À VAGA, DESTACANDO PORQUE O CANDIDATO É BOM PARA ELA.
5. USE AS CONQUISTAS DO CANDIDATO COM MÉTRICAS CONCRETAS NO CORPO DA CARTA.\
"""
```

- [ ] **Step 2: Create frontend/src/constants/promptDefaults.ts**

The TS file must mirror the Python defaults exactly (same text, same `{JOB_DESCRIPTION}` placeholder):

```typescript
export const DEFAULT_CV_PROMPT: string = `baseado nesse arquivo em anexo, crie um curriculum pra mim para esta vaga com o design abaixo:
VAGA:
{JOB_DESCRIPTION}
DESIGN:
[... exact same content as Python DEFAULT_CV_PROMPT above ...]`

export const DEFAULT_CL_PROMPT: string = `baseado nesse arquivo em anexo, crie uma carta de apresentação para esta vaga com o design abaixo:
VAGA:
{JOB_DESCRIPTION}
DESIGN:
[... exact same content as Python DEFAULT_CL_PROMPT above ...]`
```

Copy the Python constant string bodies verbatim — no template logic, no interpolation. The backtick TS template literal handles multiline.

- [ ] **Step 3: Verify constants import correctly**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk python -c "from app.services.prompt_defaults import DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT; print('CV len:', len(DEFAULT_CV_PROMPT)); print('CL len:', len(DEFAULT_CL_PROMPT)); assert '{JOB_DESCRIPTION}' in DEFAULT_CV_PROMPT; assert '{JOB_DESCRIPTION}' in DEFAULT_CL_PROMPT; print('OK')"
```

Expected: `CV len: <N>  CL len: <M>  OK`

- [ ] **Step 4: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add backend/app/services/prompt_defaults.py frontend/src/constants/promptDefaults.ts
rtk git commit -m "feat: add DEFAULT_CV_PROMPT and DEFAULT_CL_PROMPT constants"
```

---

## Task 2: ProfileMaster Model Update

**Files:**
- Modify: `backend/app/models/profile.py`
- Delete: `backend/app/models/design.py`

**Interfaces:**
- Consumes: `DEFAULT_CV_PROMPT`, `DEFAULT_CL_PROMPT` from `app.services.prompt_defaults`
- Produces: `ProfileMaster` with fields `reference_text: str`, `cv_prompt: str`, `cover_letter_prompt: str` (no design fields)

- [ ] **Step 1: Write failing test for new ProfileMaster fields**

In `backend/tests/test_models/` (create `test_profile_model.py` if it doesn't exist):

```python
from __future__ import annotations

from app.models.profile import ProfileMaster, ContactInfo
from app.services.prompt_defaults import DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT


def test_profile_has_reference_text_default():
    p = ProfileMaster(contact=ContactInfo(full_name="X", email="x@x.com"))
    assert p.reference_text == ""


def test_profile_has_cv_prompt_default():
    p = ProfileMaster(contact=ContactInfo(full_name="X", email="x@x.com"))
    assert p.cv_prompt == DEFAULT_CV_PROMPT


def test_profile_has_cover_letter_prompt_default():
    p = ProfileMaster(contact=ContactInfo(full_name="X", email="x@x.com"))
    assert p.cover_letter_prompt == DEFAULT_CL_PROMPT


def test_profile_has_no_design_fields():
    p = ProfileMaster(contact=ContactInfo(full_name="X", email="x@x.com"))
    assert not hasattr(p, "design_versions")
    assert not hasattr(p, "active_resume_design_id")
    assert not hasattr(p, "active_cover_letter_design_id")
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest tests/test_models/test_profile_model.py -v
```

Expected: FAIL (AttributeError or ImportError — `prompt_defaults` may not exist yet if Task 1 was skipped, but Task 1 must complete first)

- [ ] **Step 3: Update backend/app/models/profile.py**

Remove the `from app.models.design import DesignVersion` import. Replace the three design fields at the bottom of `ProfileMaster` with the three new fields:

```python
from __future__ import annotations

from datetime import date
from enum import Enum
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, field_validator

from app.services.prompt_defaults import DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT


# ... (all existing classes unchanged: SkillLevel, XYZExperience, WorkExperience,
#      Education, Skill, Language, ContactInfo, JobSuggestion) ...


class ProfileMaster(BaseModel):
    """
    Single Source of Truth (SSOT) for the candidate's profile.
    Persisted locally at .job_hunter/profile_master.json
    """

    id: UUID = Field(default_factory=uuid4)
    contact: ContactInfo
    summary: Optional[str] = Field(
        default=None,
        description="Professional summary — generated or provided by the user",
    )
    work_experiences: list[WorkExperience] = Field(default_factory=list)
    education: list[Education] = Field(default_factory=list)
    skills: list[Skill] = Field(default_factory=list)
    languages: list[Language] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    job_suggestions: list[JobSuggestion] = Field(
        default_factory=list,
        description="Job titles + keywords generated from this profile during ingestion",
    )
    reference_text: str = Field(
        default="",
        description="Compiled text from all uploaded reference files (LLM-filtered)",
    )
    cv_prompt: str = Field(default=DEFAULT_CV_PROMPT)
    cover_letter_prompt: str = Field(default=DEFAULT_CL_PROMPT)
```

- [ ] **Step 4: Delete backend/app/models/design.py**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git rm backend/app/models/design.py
```

- [ ] **Step 5: Run model tests**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest tests/test_models/ -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add backend/app/models/profile.py
rtk git commit -m "feat: replace design fields with reference_text + prompt fields on ProfileMaster"
```

---

## Task 3: Extractors + File Processor Service

**Files:**
- Modify: `backend/app/services/extractors.py` — add TXT/MD support
- Create: `backend/app/services/file_processor.py` — LLM relevance filter + compile
- Test: `backend/tests/test_services/test_extractors.py` (modify)
- Test: `backend/tests/test_services/test_file_processor.py` (create)

**Interfaces:**
- Consumes: `get_llm_client()`, `settings.active_model`
- Produces:
  - `extract_text(filename: str, content: bytes) -> str` (updated — now accepts TXT/MD)
  - `extract_relevant(filename: str, content: bytes) -> str` — calls extractor then LLM filter, returns ≤4000 chars
  - `compile_reference_text(files: list[tuple[str, bytes]]) -> str` — processes all files, returns compiled str ≤60000 chars

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_services/test_file_processor.py
from __future__ import annotations

from unittest.mock import patch, MagicMock

from app.services.file_processor import compile_reference_text, extract_relevant


def _make_llm_mock(response: str) -> MagicMock:
    msg = MagicMock(); msg.content = response
    choice = MagicMock(); choice.message = msg
    completion = MagicMock(); completion.choices = [choice]
    client = MagicMock(); client.chat.completions.create.return_value = completion
    return client


def test_compile_reference_text_concatenates_files():
    mock_client = _make_llm_mock("Relevant: Software Engineer at Acme 2021-2024")
    with patch("app.services.file_processor.get_llm_client", return_value=mock_client):
        result = compile_reference_text([("cv.txt", b"Full resume text here")])
    assert "=== cv.txt ===" in result
    assert "Relevant: Software Engineer" in result


def test_compile_reference_text_caps_at_60k():
    # Each file returns 4000-char extraction; 20 files = 80k total before cap
    long_text = "A" * 4000
    mock_client = _make_llm_mock(long_text)
    files = [(f"file{i}.txt", b"content") for i in range(20)]
    with patch("app.services.file_processor.get_llm_client", return_value=mock_client):
        result = compile_reference_text(files)
    assert len(result) <= 60_100  # 60k + small truncation note
    assert "[truncated" in result


def test_compile_reference_text_skips_failed_extraction():
    def side_effect(**kwargs):
        raise RuntimeError("LLM error")
    mock_client = MagicMock()
    mock_client.chat.completions.create.side_effect = side_effect
    with patch("app.services.file_processor.get_llm_client", return_value=mock_client):
        result = compile_reference_text([("bad.pdf", b"content"), ("ok.txt", b"real text")])
    # Both fail — result may be empty but should not raise
    assert isinstance(result, str)


def test_extract_relevant_caps_at_4000_chars():
    long_extraction = "X" * 5000
    mock_client = _make_llm_mock(long_extraction)
    with patch("app.services.file_processor.get_llm_client", return_value=mock_client):
        result = extract_relevant("doc.txt", b"some content")
    assert len(result) <= 4000
```

Also add to `test_extractors.py`:
```python
def test_extract_text_accepts_txt():
    from app.services.extractors import extract_text
    result = extract_text("resume.txt", b"Plain text resume content")
    assert result == "Plain text resume content"


def test_extract_text_accepts_md():
    from app.services.extractors import extract_text
    result = extract_text("resume.md", b"# John Doe\n\n## Experience")
    assert "John Doe" in result
```

- [ ] **Step 2: Run to verify they fail**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest tests/test_services/test_file_processor.py tests/test_services/test_extractors.py::test_extract_text_accepts_txt tests/test_services/test_extractors.py::test_extract_text_accepts_md -v
```

Expected: FAIL

- [ ] **Step 3: Update extractors.py — add TXT/MD**

```python
from __future__ import annotations

import io
from pathlib import Path

import pdfplumber
from bs4 import BeautifulSoup
from docx import Document


def extract_text(filename: str, content: bytes) -> str:
    """Dispatch to the correct extractor based on file extension."""
    ext = Path(filename).suffix.lower()
    if ext == ".pdf":
        return _from_pdf(content)
    if ext == ".docx":
        return _from_docx(content)
    if ext in (".html", ".htm"):
        return _from_html(content)
    if ext in (".txt", ".md", ".markdown"):
        return content.decode("utf-8", errors="replace")
    raise ValueError(f"Unsupported file type: '{ext}'. Use PDF, DOCX, HTML, TXT, or MD.")


def _from_pdf(content: bytes) -> str:
    text_parts: list[str] = []
    with pdfplumber.open(io.BytesIO(content)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text(x_tolerance=2, y_tolerance=2)
            if page_text:
                text_parts.append(page_text)
    return "\n\n".join(text_parts)


def _from_docx(content: bytes) -> str:
    doc = Document(io.BytesIO(content))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


def _from_html(content: bytes) -> str:
    soup = BeautifulSoup(content, "html.parser")
    for tag in soup(["script", "style", "meta", "head"]):
        tag.decompose()
    return soup.get_text(separator="\n", strip=True)
```

- [ ] **Step 4: Create backend/app/services/file_processor.py**

```python
from __future__ import annotations

import logging
from textwrap import dedent

from app.core.config import settings
from app.core.llm import get_llm_client
from app.services.extractors import extract_text

logger = logging.getLogger(__name__)

_MAX_PER_FILE = 4_000
_MAX_TOTAL = 60_000

_RELEVANCE_SYSTEM = dedent("""\
    You are a career document analyzer. Extract ONLY the career-relevant information from this document.
    Keep: job titles, companies, dates, responsibilities, achievements, skills, technologies, certifications,
          education (degree, institution, dates, relevant courses), languages, and any performance
          or competency assessments.
    Discard: legal boilerplate, company addresses, HR signatures, page numbers, decorative headers,
             privacy notices, and any text not useful for a job application.
    Return the extracted content as clean plain text. If nothing is career-relevant, return an empty string.
    Maximum 4000 characters.
""").strip()


def extract_relevant(filename: str, content: bytes) -> str:
    """Extract raw text from file then filter to career-relevant content via LLM. Returns ≤4000 chars."""
    try:
        raw = extract_text(filename, content)
    except ValueError as exc:
        logger.warning("Skipping %s — unsupported format: %s", filename, exc)
        return ""

    if not raw.strip():
        return ""

    try:
        client = get_llm_client()
        response = client.chat.completions.create(
            model=settings.active_model,
            messages=[
                {"role": "system", "content": _RELEVANCE_SYSTEM},
                {"role": "user", "content": raw[:20_000]},  # protect token budget
            ],
            temperature=0,
        )
        extracted = (response.choices[0].message.content or "").strip()
    except Exception as exc:
        logger.warning("LLM relevance extraction failed for %s: %s", filename, exc)
        return ""

    return extracted[:_MAX_PER_FILE]


def compile_reference_text(files: list[tuple[str, bytes]]) -> str:
    """
    Process each (filename, content) pair through extract_relevant,
    concatenate results, and cap total at 60k chars.
    """
    parts: list[str] = []
    total = 0

    for filename, content in files:
        extracted = extract_relevant(filename, content)
        if not extracted:
            continue
        section = f"=== {filename} ===\n{extracted}\n"
        total += len(section)
        parts.append(section)

    compiled = "\n".join(parts)
    if len(compiled) > _MAX_TOTAL:
        compiled = compiled[:_MAX_TOTAL]
        compiled += f"\n[truncated — {total} chars total across {len(parts)} files]"

    return compiled
```

- [ ] **Step 5: Run tests**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest tests/test_services/test_file_processor.py tests/test_services/test_extractors.py -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add backend/app/services/extractors.py backend/app/services/file_processor.py backend/tests/test_services/test_file_processor.py backend/tests/test_services/test_extractors.py
rtk git commit -m "feat: add TXT/MD extraction + LLM relevance filter + compile_reference_text"
```

---

## Task 4: Ingest Endpoint — Multi-File

**Files:**
- Modify: `backend/app/routers/profile.py`
- Modify: `backend/app/services/ingestion.py`
- Modify: `backend/tests/test_routers/test_profile.py`

**Interfaces:**
- Consumes: `compile_reference_text(files: list[tuple[str, bytes]]) -> str` from Task 3
- Consumes: `IngestionService.run(reference_text: str, progress_fn)` (signature changes)
- `POST /profile/ingest` now accepts `files: list[UploadFile]` (field name `files`, 1–20)

- [ ] **Step 1: Update ingestion.py — accept reference_text directly**

Remove the `filename` parameter. The `resume_text` parameter becomes `reference_text`:

```python
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
```

- [ ] **Step 2: Update routers/profile.py — multi-file ingest**

Replace the `ingest_resume` endpoint and its imports. Key changes:
1. `file: UploadFile` → `files: list[UploadFile] = File(...)`  
2. Max 20 files validation
3. Use `compile_reference_text` to build `reference_text`
4. Store `reference_text` on profile after ingest completes
5. Remove all `seed_default_designs` calls and design template logic

```python
from __future__ import annotations

import logging
import threading
import uuid
from typing import Any, List, Literal, Optional

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from pydantic import BaseModel

from app.models.ingestion import HITLResolution, IngestionResponse, IngestionStatus
from app.models.profile import ProfileMaster
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services.file_processor import compile_reference_text
from app.services.ingestion import IngestionService
from app.services import job_store as store
from app.services.suggestions import generate_suggestions

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/profile", tags=["profile"])

_repo = ProfileRepository()
_ingestion = IngestionService()

_MAX_FILES = 20


class AsyncJobStart(BaseModel):
    job_id: str
    status: Literal["processing"] = "processing"


class AsyncJobStatus(BaseModel):
    job_id: str
    status: str
    step: str
    message: str
    progress: int
    result: Optional[Any] = None


class UpdatePromptsRequest(BaseModel):
    cv_prompt: Optional[str] = None
    cover_letter_prompt: Optional[str] = None


def _job_to_response(job: store.AsyncJob) -> AsyncJobStatus:
    return AsyncJobStatus(
        job_id=job.job_id,
        status=job.status,
        step=job.step,
        message=job.message,
        progress=job.progress,
        result=job.result,
    )


def _finalise_with_suggestions(job_id: str, profile: ProfileMaster, reference_text: str) -> None:
    store.update_job(job_id, step="suggestions", message="Generating job suggestions…", progress=80)
    suggestions = generate_suggestions(profile)
    profile.job_suggestions = suggestions
    profile.reference_text = reference_text
    _repo.save(profile)
    store.update_job(job_id, status="completed", step="done", message="Profile ready!", progress=100)


@router.post(
    "/ingest",
    response_model=AsyncJobStart,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload documents and start ingestion in the background",
)
async def ingest_resume(files: List[UploadFile] = File(...)) -> AsyncJobStart:
    if len(files) > _MAX_FILES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Maximum {_MAX_FILES} files allowed.",
        )
    if not files:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="At least one file is required.",
        )

    # Read all file content eagerly (must happen in async context)
    file_pairs: list[tuple[str, bytes]] = []
    for upload in files:
        content = await upload.read()
        file_pairs.append((upload.filename or "unnamed", content))

    job_id = str(uuid.uuid4())
    store.create_job(job_id)
    store.update_job(job_id, step="extracting", message="Extracting and filtering documents…", progress=5)

    def _run() -> None:
        def ingest_progress(step: str, message: str, pct: int) -> None:
            # Scale to 10–75 to leave room for suggestions step
            scaled = 10 + int(pct * 0.65)
            store.update_job(job_id, step=step, message=message, progress=scaled)

        store.update_job(job_id, step="extracting", message="Filtering documents for relevant content…", progress=10)
        reference_text = compile_reference_text(file_pairs)

        result = _ingestion.run(reference_text, ingest_progress)

        if result.status == IngestionStatus.COMPLETED and result.profile:
            _repo.delete_partial()
            _finalise_with_suggestions(job_id, result.profile, reference_text)
            store.update_job(
                job_id,
                status="completed",
                step="done",
                message="Profile ready!",
                progress=100,
                result=result.model_dump(mode="json"),
            )
        elif result.status == IngestionStatus.HITL_REQUIRED and result.hitl_request:
            result.hitl_request.partial_profile.reference_text = reference_text
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

    threading.Thread(target=_run, daemon=True).start()
    return AsyncJobStart(job_id=job_id)


@router.get(
    "/ingest/{job_id}",
    response_model=AsyncJobStatus,
    summary="Poll the status of a background ingest job",
)
async def get_ingest_status(job_id: str) -> AsyncJobStatus:
    job = store.get_job(job_id)
    if not job:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found or expired.")
    return _job_to_response(job)


@router.post(
    "/ingest/resolve",
    response_model=AsyncJobStart,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Submit human-provided metrics and resume ingestion in the background",
)
async def resolve_hitl(resolution: HITLResolution) -> AsyncJobStart:
    if not _repo.partial_exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No partial profile found. Run /ingest first.",
        )

    profile = _repo.load_partial()

    for field_path, value in resolution.resolved_fields.items():
        parts = field_path.split(".")
        obj: object = profile
        for part in parts[:-1]:
            if part.isdigit():
                obj = obj[int(part)]  # type: ignore[index]
            else:
                obj = getattr(obj, part)
        leaf = parts[-1]
        if leaf.isdigit():
            obj[int(leaf)] = value  # type: ignore[index]
        else:
            setattr(obj, leaf, value)

    reference_text = profile.reference_text  # preserved from ingest step
    _repo.delete_partial()

    job_id = str(uuid.uuid4())
    ingestion_id = resolution.ingestion_id
    store.create_job(job_id)
    store.update_job(job_id, step="suggestions", message="Generating job suggestions…", progress=20)

    def _run() -> None:
        suggestions = generate_suggestions(profile)
        profile.job_suggestions = suggestions
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

    threading.Thread(target=_run, daemon=True).start()
    return AsyncJobStart(job_id=job_id)


@router.get("/", response_model=ProfileMaster)
async def get_profile() -> ProfileMaster:
    try:
        return _repo.load()
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


@router.put("/", response_model=ProfileMaster)
async def update_profile(profile: ProfileMaster) -> ProfileMaster:
    _repo.save(profile)
    return profile


@router.patch("/prompts", response_model=ProfileMaster)
async def update_prompts(req: UpdatePromptsRequest) -> ProfileMaster:
    try:
        profile = _repo.load()
    except ProfileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    if req.cv_prompt is not None:
        profile.cv_prompt = req.cv_prompt
    if req.cover_letter_prompt is not None:
        profile.cover_letter_prompt = req.cover_letter_prompt
    _repo.save(profile)
    return profile


@router.delete("/", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def delete_profile() -> None:
    _repo.delete()
```

- [ ] **Step 3: Update tests/test_routers/test_profile.py**

Replace `test_ingest_rejects_unsupported_format` (`.txt` is now supported) and `test_ingest_completed_saves_profile` (now sends multiple files). Add prompt endpoint tests.

```python
# Replace the entire file:
from __future__ import annotations

import io
import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.ingestion import IngestionStatus
from app.models.profile import (
    ContactInfo,
    ProfileMaster,
    WorkExperience,
    XYZExperience,
)
from app.repositories.profile_repository import ProfileRepository
from app.services.prompt_defaults import DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT

_VALID_PROFILE = ProfileMaster(
    contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com"),
    work_experiences=[
        WorkExperience(
            company="TechCorp",
            role="Engineer",
            start_date=date(2020, 1, 1),
            is_current=True,
            achievements=[
                XYZExperience(
                    action="Reduced deploy time",
                    metric="by 60%",
                    context="by migrating CI to GitHub Actions",
                )
            ],
        )
    ],
)


@pytest.fixture
def client_with_tmp_repo(tmp_path: Path):
    repo = ProfileRepository(
        path=tmp_path / "profile.json",
        partial_path=tmp_path / "profile_partial.json",
    )
    with patch("app.routers.profile._repo", repo):
        yield TestClient(app), repo


def test_get_profile_404_when_missing(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    resp = client.get("/profile/")
    assert resp.status_code == 404


def test_get_profile_returns_saved_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.get("/profile/")
    assert resp.status_code == 200
    assert resp.json()["contact"]["full_name"] == "Ada Lovelace"


def test_put_profile_persists_and_returns(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    payload = json.loads(_VALID_PROFILE.model_dump_json())
    resp = client.put("/profile/", json=payload)
    assert resp.status_code == 200
    assert repo.exists()


def test_delete_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.delete("/profile/")
    assert resp.status_code == 204
    assert not repo.exists()


def test_ingest_rejects_too_many_files(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    files = [("files", (f"f{i}.txt", b"content", "text/plain")) for i in range(21)]
    resp = client.post("/profile/ingest", files=files)
    assert resp.status_code == 422
    assert "Maximum 20" in resp.json()["detail"]


def test_ingest_accepted_returns_job_id(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    with patch("app.services.file_processor.get_llm_client") as mock_fp, \
         patch("app.routers.profile._ingestion.run") as mock_run, \
         patch("app.services.suggestions.generate_suggestions", return_value=[]):
        from app.models.ingestion import IngestionResponse
        import uuid
        mock_fp.return_value = __import__("tests.conftest", fromlist=["make_llm_mock"]).make_llm_mock("Relevant content")
        mock_run.return_value = IngestionResponse(
            ingestion_id=uuid.uuid4(),
            status=IngestionStatus.COMPLETED,
            profile=_VALID_PROFILE,
        )
        resp = client.post(
            "/profile/ingest",
            files=[("files", ("resume.pdf", b"%PDF-1.4", "application/pdf"))],
        )
    assert resp.status_code == 202
    assert "job_id" in resp.json()


def test_patch_prompts_updates_cv_prompt(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.patch("/profile/prompts", json={"cv_prompt": "My custom prompt {JOB_DESCRIPTION}"})
    assert resp.status_code == 200
    assert repo.load().cv_prompt == "My custom prompt {JOB_DESCRIPTION}"


def test_patch_prompts_updates_cover_letter_prompt(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    resp = client.patch("/profile/prompts", json={"cover_letter_prompt": "Custom CL {JOB_DESCRIPTION}"})
    assert resp.status_code == 200
    assert repo.load().cover_letter_prompt == "Custom CL {JOB_DESCRIPTION}"


def test_patch_prompts_partial_update(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save(_VALID_PROFILE)
    original_cl = repo.load().cover_letter_prompt
    client.patch("/profile/prompts", json={"cv_prompt": "New CV"})
    updated = repo.load()
    assert updated.cv_prompt == "New CV"
    assert updated.cover_letter_prompt == original_cl  # unchanged


def test_patch_prompts_404_when_no_profile(client_with_tmp_repo):
    client, _ = client_with_tmp_repo
    resp = client.patch("/profile/prompts", json={"cv_prompt": "x"})
    assert resp.status_code == 404


def test_resolve_hitl_completes_profile(client_with_tmp_repo):
    client, repo = client_with_tmp_repo
    repo.save_partial(_VALID_PROFILE)
    import uuid
    resolution = {
        "ingestion_id": str(uuid.uuid4()),
        "resolved_fields": {
            "work_experiences.0.achievements.0.metric": "by 60%, from 30 to 12 minutes"
        },
    }
    with patch("app.services.suggestions.generate_suggestions", return_value=[]):
        resp = client.post("/profile/ingest/resolve", json=resolution)
    assert resp.status_code == 202
```

- [ ] **Step 4: Run profile router tests**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest tests/test_routers/test_profile.py -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add backend/app/services/ingestion.py backend/app/routers/profile.py backend/tests/test_routers/test_profile.py
rtk git commit -m "feat: multi-file ingest with reference_text + PATCH /profile/prompts"
```

---

## Task 5: Application Service Rewrite

**Files:**
- Modify: `backend/app/services/application.py`
- Modify: `backend/app/services/playwright_renderer.py`
- Modify: `backend/app/routers/application.py`
- Modify: `backend/tests/test_services/test_application.py`

**Interfaces:**
- Consumes: `ProfileMaster` (with `reference_text`, `cv_prompt`, `cover_letter_prompt`)
- Produces: `generate_application_package(profile, job, match) -> dict`
- Produces: `generate_master_resume(profile) -> bytes`

- [ ] **Step 1: Write failing tests**

```python
# backend/tests/test_services/test_application.py (replace file)
from __future__ import annotations

import base64
from datetime import date
from unittest.mock import MagicMock, patch
from uuid import uuid4

from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ContactInfo, ProfileMaster, WorkExperience, XYZExperience
from app.services.application import _generate_html, generate_application_package


def _make_llm_mock(html: str) -> MagicMock:
    msg = MagicMock(); msg.content = html
    choice = MagicMock(); choice.message = msg
    completion = MagicMock(); completion.choices = [choice]
    client = MagicMock(); client.chat.completions.create.return_value = completion
    return client


_PROFILE = ProfileMaster(
    contact=ContactInfo(full_name="Ada Lovelace", email="ada@example.com", location="Munich"),
    reference_text="Ada Lovelace — Senior Engineer at TechCorp 2021-2024. Reduced API latency by 40%.",
    cv_prompt="Create a resume for this job: {JOB_DESCRIPTION}\nDesign: two-column HTML.",
    cover_letter_prompt="Write a cover letter for: {JOB_DESCRIPTION}\nFormat: full-width HTML.",
    work_experiences=[
        WorkExperience(
            company="TechCorp",
            role="Engineer",
            start_date=date(2021, 1, 1),
            is_current=True,
            achievements=[XYZExperience(
                action="Reduced latency", metric="by 40%", context="via Redis"
            )],
        )
    ],
)

_JOB = JobPosting(
    id=uuid4(),
    title="Backend Engineer",
    company="Acme GmbH",
    location="Munich",
    description="Python FastAPI role",
    url="https://example.com/job/1",
    source="mock",
)

_MATCH = MatchScore(
    job_id=_JOB.id,
    score=85,
    keywords_found=["Python"],
    keywords_missing=[],
    justification="Good match.",
)

_FAKE_HTML = "<html><body><h1>Ada Lovelace</h1></body></html>"


def test_generate_html_substitutes_job_description():
    mock_client = _make_llm_mock(_FAKE_HTML)
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        result = _generate_html(_PROFILE, _JOB, _PROFILE.cv_prompt)
    call_kwargs = mock_client.chat.completions.create.call_args
    user_content = call_kwargs.kwargs["messages"][0]["content"]
    assert "Backend Engineer at Acme GmbH" in user_content
    assert "{JOB_DESCRIPTION}" not in user_content


def test_generate_html_includes_reference_text():
    mock_client = _make_llm_mock(_FAKE_HTML)
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        _generate_html(_PROFILE, _JOB, _PROFILE.cv_prompt)
    call_kwargs = mock_client.chat.completions.create.call_args
    user_content = call_kwargs.kwargs["messages"][0]["content"]
    assert "Ada Lovelace" in user_content  # from reference_text
    assert "REFERENCE FILES" in user_content


def test_generate_html_strips_markdown_fences():
    mock_client = _make_llm_mock("```html\n<html><body>test</body></html>\n```")
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        result = _generate_html(_PROFILE, _JOB, _PROFILE.cv_prompt)
    assert result == "<html><body>test</body></html>"
    assert "```" not in result


def test_generate_html_strips_generic_fences():
    mock_client = _make_llm_mock("```\n<html><body>x</body></html>\n```")
    with patch("app.services.application.get_llm_client", return_value=mock_client):
        result = _generate_html(_PROFILE, _JOB, _PROFILE.cv_prompt)
    assert "```" not in result


def test_generate_application_package_structure():
    fake_pdf = b"%PDF-1.4 fake"
    mock_client = _make_llm_mock(_FAKE_HTML)
    with patch("app.services.application.get_llm_client", return_value=mock_client), \
         patch("app.services.application._html_to_pdf", return_value=fake_pdf):
        pkg = generate_application_package(_PROFILE, _JOB, _MATCH)
    assert pkg["job_id"] == _JOB.id
    assert base64.b64decode(pkg["resume_pdf_base64"]) == fake_pdf
    assert base64.b64decode(pkg["cover_letter_pdf_base64"]) == fake_pdf
    assert isinstance(pkg["cover_letter_text"], str)
```

- [ ] **Step 2: Run to verify failure**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest tests/test_services/test_application.py -v
```

- [ ] **Step 3: Rewrite backend/app/services/application.py**

```python
from __future__ import annotations

import base64
import logging
import re

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ProfileMaster

logger = logging.getLogger(__name__)


def _to_b64(data: bytes) -> str:
    return base64.b64encode(data).decode()


def _html_to_pdf(html: str) -> bytes:
    from app.services.playwright_renderer import render_html_to_pdf
    return render_html_to_pdf(html)


def _extract_text_from_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


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
                "content": (
                    f"=== REFERENCE FILES ===\n{profile.reference_text}\n\n"
                    f"=== INSTRUCTIONS ===\n{filled}"
                ),
            }
        ],
        temperature=0.3,
    )
    raw = (response.choices[0].message.content or "").strip()
    # Strip markdown fences (```html or ```)
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    return raw.strip()


def generate_application_package(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
) -> dict:
    resume_html = _generate_html(profile, job, profile.cv_prompt)
    resume_pdf = _html_to_pdf(resume_html)

    cl_html = _generate_html(profile, job, profile.cover_letter_prompt)
    cl_pdf = _html_to_pdf(cl_html)

    return {
        "job_id": job.id,
        "resume_pdf_base64": _to_b64(resume_pdf),
        "cover_letter_text": _extract_text_from_html(cl_html),
        "cover_letter_pdf_base64": _to_b64(cl_pdf),
    }


def generate_master_resume(profile: ProfileMaster) -> bytes:
    """Generate a general-purpose resume PDF without tailoring to a specific job."""
    from app.models.jobs import JobPosting, MatchScore
    from uuid import uuid4
    generic_job = JobPosting(
        id=uuid4(),
        title="General Application",
        company="",
        location="",
        description="General purpose — showcase all experience and skills.",
        url="",
        source="master",
    )
    html = _generate_html(profile, generic_job, profile.cv_prompt)
    return _html_to_pdf(html)
```

- [ ] **Step 4: Simplify playwright_renderer.py — keep only render_html_to_pdf**

```python
from __future__ import annotations

from playwright.sync_api import sync_playwright


def render_html_to_pdf(html: str) -> bytes:
    """Convert an HTML string to PDF bytes using Playwright + Chromium."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        page.set_content(html, wait_until="networkidle")
        pdf = page.pdf(format="A4", print_background=True)
        browser.close()
    return pdf
```

- [ ] **Step 5: Update routers/application.py — remove design IDs**

```python
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel
from uuid import UUID

from app.models.jobs import JobPosting, MatchScore
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services.application import generate_application_package, generate_master_resume

router = APIRouter(prefix="/application", tags=["application"])

_repo = ProfileRepository()


class ApplicationPackage(BaseModel):
    job_id: UUID
    resume_pdf_base64: str
    cover_letter_text: str
    cover_letter_pdf_base64: str


class GenerateRequest(BaseModel):
    job: JobPosting
    match: MatchScore


@router.post("/generate", response_model=ApplicationPackage)
async def generate_application(req: GenerateRequest) -> ApplicationPackage:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No profile found. Upload your resume first.",
        )
    try:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: generate_application_package(profile, req.job, req.match),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {exc}",
        )
    return ApplicationPackage(**result)


@router.get(
    "/master-resume",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_master_resume() -> Response:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile found.")

    pdf_bytes = await asyncio.get_event_loop().run_in_executor(
        None, generate_master_resume, profile
    )
    filename = f"{profile.contact.full_name.replace(' ', '_')}_Resume.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 6: Run application tests**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest tests/test_services/test_application.py -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add backend/app/services/application.py backend/app/services/playwright_renderer.py backend/app/routers/application.py backend/tests/test_services/test_application.py
rtk git commit -m "feat: rewrite application generation to LLM-based HTML, remove design IDs"
```

---

## Task 6: Remove Design System Backend

**Files:**
- Delete: all design-related backend files and tests
- Modify: `backend/app/main.py`

**Interfaces:**
- No new interfaces — pure deletion

- [ ] **Step 1: Delete files**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git rm backend/app/routers/design.py
rtk git rm backend/app/services/design_generator.py
rtk git rm backend/app/services/default_designs.py
rtk git rm backend/app/services/cover_letter.py
rtk git rm backend/tests/test_routers/test_design.py
rtk git rm backend/tests/test_routers/test_profile_designs.py
rtk git rm backend/tests/test_services/test_design_generator.py
rtk git rm backend/tests/test_services/test_default_designs.py
rtk git rm backend/tests/test_services/test_playwright_renderer.py
```

- [ ] **Step 2: Update main.py — remove design router**

```python
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import application, auto_search, config, jobs, profile


@asynccontextmanager
async def lifespan(app: FastAPI):
    from app.services.auto_search_scheduler import shutdown_scheduler, start_scheduler
    from app.services.auto_search_store import load_config
    cfg = load_config()
    start_scheduler(interval_hours=cfg.interval_hours)
    yield
    shutdown_scheduler()


app = FastAPI(
    title="Job Hunter Assistant",
    description="Agentic career assistant for tech job applications",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(profile.router)
app.include_router(jobs.router)
app.include_router(application.router)
app.include_router(config.router)
app.include_router(auto_search.router)


@app.get("/health", tags=["system"])
async def health() -> dict:
    return {"status": "ok", "version": app.version}
```

- [ ] **Step 3: Run full backend test suite to confirm no regressions**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest --tb=short -q
```

Expected: all remaining tests pass (deleted test files no longer run)

- [ ] **Step 4: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add backend/app/main.py
rtk git commit -m "feat: remove design system — routers, services, models, tests"
```

---

## Task 7: Frontend — API Client Update

**Files:**
- Modify: `frontend/src/api/client.ts`

**Interfaces:**
- Produces: `ingestProfile(files: File[]) -> Promise<AsyncJobStart>`
- Produces: `updatePrompts(data: {cv_prompt?: string; cover_letter_prompt?: string}) -> Promise<ProfileMaster>`
- Removes: all design API functions, DesignVersion interface
- Updates: `ProfileMaster` interface (remove design fields, add reference_text/cv_prompt/cover_letter_prompt)
- Updates: `generateApplication(job, match)` — no design ID params

- [ ] **Step 1: Update frontend/src/api/client.ts**

Remove: `startGenerateResumeDesign`, `startGenerateCoverLetterDesign`, `updateDesign`, `deleteDesign`, `seedDefaultDesigns`, `regenerateDesign`, `getDesignPreviewUrl`, `getDesignPdfUrl`, `DesignVersion` interface.

Update `ProfileMaster` interface, `ingestResume` → `ingestProfile`, `generateApplication`.

Add `updatePrompts`.

The complete updated file (only the changed/removed parts shown; paste complete):

```typescript
/**
 * Typed API client wrapping fetch.
 */

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? 'Unknown error')
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// ── Profile ────────────────────────────────────────────────────────────────────

export async function getProfile() {
  return request<ProfileMaster>('/profile/')
}

export async function updateProfile(profile: ProfileMaster) {
  return request<ProfileMaster>('/profile/', { method: 'PUT', body: JSON.stringify(profile) })
}

export async function deleteProfile() {
  return request<void>('/profile/', { method: 'DELETE' })
}

export async function ingestProfile(files: File[]) {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }
  return request<AsyncJobStart>('/profile/ingest', {
    method: 'POST',
    headers: {},
    body: form,
  })
}

export async function getIngestStatus(jobId: string) {
  return request<AsyncJobStatus>(`/profile/ingest/${jobId}`)
}

export async function resolveHITL(resolution: HITLResolution) {
  return request<AsyncJobStart>('/profile/ingest/resolve', {
    method: 'POST',
    body: JSON.stringify(resolution),
  })
}

export async function updatePrompts(data: { cv_prompt?: string; cover_letter_prompt?: string }) {
  return request<ProfileMaster>('/profile/prompts', {
    method: 'PATCH',
    body: JSON.stringify(data),
  })
}

// ── Jobs ───────────────────────────────────────────────────────────────────────

export async function searchJobs(req: JobSearchRequest) {
  return request<AsyncSearchStart>('/jobs/search', { method: 'POST', body: JSON.stringify(req) })
}

export async function getSearchStatus(searchId: string) {
  return request<AsyncSearchStatus>(`/jobs/search/${searchId}`)
}

// ── Auto Search ────────────────────────────────────────────────────────────────

export async function getAutoSearchConfig() {
  return request<AutoSearchConfig>('/auto-search/config')
}

export async function saveAutoSearchConfig(config: AutoSearchConfig) {
  return request<AutoSearchConfig>('/auto-search/config', { method: 'PUT', body: JSON.stringify(config) })
}

export async function getAutoSearchSummary() {
  return request<AutoSearchSummary>('/auto-search/summary')
}

export async function triggerAutoSearchRun() {
  return request<AutoSearchRunStart>('/auto-search/run', { method: 'POST' })
}

export async function getAutoSearchResults(page: number, pageSize: number, statusFilter: string, sort: 'score' | 'recent' = 'score') {
  const params = new URLSearchParams({ page: String(page), page_size: String(pageSize), status_filter: statusFilter, sort })
  return request<AutoSearchResultsPage>(`/auto-search/results?${params}`)
}

export async function markAutoSearchSeen() {
  return request<void>('/auto-search/mark-seen', { method: 'POST' })
}

export async function setJobStatus(urlHash: string, status: JobStatus, notes?: string) {
  return request<{ url_hash: string; status: JobStatus }>(`/auto-search/jobs/${urlHash}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status, notes: notes ?? null }),
  })
}

export async function cleanupAutoSearch(params: { before_date?: string; remove_not_interested?: boolean; remove_unavailable?: boolean }) {
  const q = new URLSearchParams()
  if (params.before_date) q.set('before_date', params.before_date)
  if (params.remove_not_interested) q.set('remove_not_interested', 'true')
  if (params.remove_unavailable) q.set('remove_unavailable', 'true')
  return request<{ removed: number }>(`/auto-search/cleanup?${q}`, { method: 'DELETE' })
}

// ── Application ────────────────────────────────────────────────────────────────

export async function generateApplication(job: JobPosting, match: MatchScore) {
  return request<ApplicationPackage>('/application/generate', {
    method: 'POST',
    body: JSON.stringify({ job, match }),
  })
}

export async function downloadMasterResume(): Promise<Blob> {
  const res = await fetch(`${BASE}/application/master-resume`)
  if (!res.ok) throw new ApiError(res.status, 'Failed to download resume')
  return res.blob()
}

// ── Config ────────────────────────────────────────────────────────────────────

export async function getLLMConfig() {
  return request<LLMConfigView>('/config/llm')
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface AsyncJobStart { job_id: string; status: 'processing' }

export interface AsyncJobStatus {
  job_id: string
  status: 'processing' | 'completed' | 'hitl_required' | 'failed'
  step: string
  message: string
  progress: number
  result?: unknown
}

export interface AsyncSearchStart { search_id: string; status: 'processing' | 'completed'; cached: boolean; cached_at: string | null }

export interface AsyncSearchStatus {
  search_id: string
  status: 'processing' | 'completed' | 'failed'
  step: string; message: string; progress: number; result?: unknown
}

export interface JobSearchRequest { query: string; location?: string; max_results?: number; force_refresh?: boolean }

export interface JobSearchResponse { results: RankedJob[]; cached: boolean; cached_at: string | null }

export interface XYZExperience { action: string; metric: string; context: string }

export interface WorkExperience {
  id: string; company: string; role: string; start_date: string; end_date?: string
  is_current: boolean; location?: string; achievements: XYZExperience[]; technologies: string[]
}

export interface Education {
  id: string; institution: string; degree: string; field_of_study: string
  start_date: string; end_date?: string; grade?: string; relevant_courses: string[]
}

export interface Skill { name: string; level: 'beginner' | 'intermediate' | 'advanced' | 'expert'; years_of_experience?: number }

export interface Language { name: string; proficiency: string }

export interface ContactInfo {
  full_name: string; email: string; phone?: string; location?: string
  linkedin_url?: string; github_url?: string; portfolio_url?: string
}

export interface JobSuggestion { title: string; keywords: string[] }

export interface ProfileMaster {
  id: string
  contact: ContactInfo
  summary?: string
  work_experiences: WorkExperience[]
  education: Education[]
  skills: Skill[]
  languages: Language[]
  certifications: string[]
  job_suggestions: JobSuggestion[]
  reference_text: string
  cv_prompt: string
  cover_letter_prompt: string
}

export interface HITLField { field_path: string; current_value?: string; llm_suggestion?: string; reason: string }

export interface HITLRequest {
  ingestion_id: string; partial_profile: ProfileMaster; missing_fields: HITLField[]; message: string
}

export interface HITLResolution { ingestion_id: string; resolved_fields: Record<string, string> }

export interface IngestionResponse {
  ingestion_id: string
  status: 'processing' | 'completed' | 'hitl_required' | 'failed'
  profile?: ProfileMaster; hitl_request?: HITLRequest; error?: string
}

export interface JobPosting {
  id: string; title: string; company: string; location: string
  description: string; url: string; source: string; posted_at?: string
  salary_range?: string; employment_type?: string; required_skills: string[]
}

export interface MatchScore {
  job_id: string; score: number; keywords_found: string[]
  keywords_missing: string[]; justification: string
}

export interface RankedJob { posting: JobPosting; match: MatchScore; found_via?: string }

export type JobStatus = 'NONE' | 'NOT_INTERESTED' | 'APPLIED' | 'INTERVIEWING' | 'OFFER_RECEIVED'

export interface SearchEntry { id: string; title: string; keywords: string[]; active: boolean; custom: boolean }

export interface AutoSearchConfig {
  enabled: boolean; interval_hours: number; location: string
  page_size: number; providers: string[]; entries: SearchEntry[]
}

export interface AutoSearchSummary {
  enabled: boolean; last_run_at: string | null; next_run_at: string | null
  new_count: number; total_count: number
}

export interface SavedJobWithStatus {
  url_hash: string; posting: JobPosting; match: MatchScore
  found_at: string; last_seen_at: string; found_via: string; status: JobStatus; notes: string | null
}

export interface AutoSearchResultsPage {
  jobs: SavedJobWithStatus[]; total: number; page: number; page_size: number; total_pages: number
}

export interface AutoSearchRunStart { job_id: string; status: 'processing' }

export interface ApplicationPackage {
  job_id: string; resume_pdf_base64: string; cover_letter_text: string; cover_letter_pdf_base64: string
}

export interface LLMConfigView {
  provider: 'openai' | 'local'; model: string; base_url?: string
  temperature: number; max_retries: number; api_key_set: boolean
}
```

- [ ] **Step 2: Run TypeScript type check**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/frontend
rtk tsc --noEmit
```

Expected: 0 errors (or only errors from files that import removed DesignVersion — those are fixed in Task 8)

- [ ] **Step 3: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add frontend/src/api/client.ts
rtk git commit -m "feat: update API client — multi-file ingest, prompt update, remove design API"
```

---

## Task 8: Frontend — Component Cleanup + Delete Design Files

**Files:**
- Modify: `frontend/src/components/ApplicationGenerator.tsx`
- Modify: `frontend/src/components/ResumeUpload.tsx`
- Delete: `frontend/src/components/DesignGallery.tsx`
- Delete: `frontend/src/components/DesignEditor.tsx`
- Delete: `frontend/src/components/DesignSelector.tsx`

**Interfaces:**
- `ApplicationGenerator` props: `{ job: JobPosting; match: MatchScore }` (no `designs`)
- `ResumeUpload` props: unchanged `{ onCompleted: (r: IngestionResponse) => void }`; but now sends multiple files

- [ ] **Step 1: Update ApplicationGenerator.tsx — remove DesignSelector**

```tsx
import { useState } from 'react'
import { generateApplication, type JobPosting, type MatchScore, type ApplicationPackage } from '../api/client'

interface Props {
  job: JobPosting
  match: MatchScore
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

export function ApplicationGenerator({ job, match }: Props) {
  const [loading, setLoading] = useState(false)
  const [pkg, setPkg] = useState<ApplicationPackage | null>(null)
  const [error, setError] = useState('')
  const [showLetter, setShowLetter] = useState(false)

  async function handleGenerate() {
    setLoading(true)
    setError('')
    try {
      const result = await generateApplication(job, match)
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

- [ ] **Step 2: Update ResumeUpload.tsx — multi-file**

```tsx
import { useRef, useState } from 'react'
import { ingestProfile, getIngestStatus, type IngestionResponse } from '../api/client'

interface Props {
  onCompleted: (response: IngestionResponse) => void
}

const STEP_LABELS: Record<string, string> = {
  extracting: 'Filtering documents for relevant content…',
  analyzing: 'Sending to AI for analysis…',
  validating: 'Validating structured output…',
  suggestions: 'Generating job suggestions…',
  saving: 'Finalizing your profile…',
  hitl: 'Missing metrics found — please review.',
  done: 'Profile ready!',
  error: 'Something went wrong.',
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div style={{ width: '100%', height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
      <div style={{ height: '100%', borderRadius: 2, background: 'var(--accent)', width: `${value}%`, transition: 'width 0.4s ease' }} />
    </div>
  )
}

export function ResumeUpload({ onCompleted }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uiState, setUiState] = useState<'idle' | 'uploading' | 'error'>('idle')
  const [selectedFiles, setSelectedFiles] = useState<File[]>([])
  const [message, setMessage] = useState('')
  const [progress, setProgress] = useState(0)
  const [errorMsg, setErrorMsg] = useState('')
  const [dragOver, setDragOver] = useState(false)

  async function handleFiles(files: File[]) {
    if (!files.length) return
    setSelectedFiles(files)
    setUiState('uploading')
    setErrorMsg('')
    setMessage('Uploading your documents…')
    setProgress(5)

    try {
      const { job_id } = await ingestProfile(files)
      await pollIngest(job_id)
    } catch (err: unknown) {
      setUiState('error')
      setErrorMsg(err instanceof Error ? err.message : 'Upload failed.')
    }
  }

  async function pollIngest(jobId: string): Promise<void> {
    while (true) {
      const status = await getIngestStatus(jobId)
      setMessage(STEP_LABELS[status.step] ?? status.message)
      setProgress(status.progress)

      if (status.status === 'processing') {
        await sleep(1000)
        continue
      }

      if (status.status === 'completed' || status.status === 'hitl_required') {
        onCompleted(status.result as IngestionResponse)
        return
      }

      setUiState('error')
      setErrorMsg((status.result as IngestionResponse)?.error ?? status.message)
      return
    }
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(e.target.files ?? [])
    if (files.length) handleFiles(files)
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const files = Array.from(e.dataTransfer.files)
    if (files.length) handleFiles(files)
  }

  const isUploading = uiState === 'uploading'

  return (
    <div>
      <div
        onClick={() => !isUploading && inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        style={{
          border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 12, padding: '2.5rem', textAlign: 'center',
          cursor: isUploading ? 'default' : 'pointer',
          background: dragOver ? 'var(--accent-bg)' : 'transparent',
          transition: 'all 0.15s',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".pdf,.docx,.html,.htm,.txt,.md"
          style={{ display: 'none' }}
          onChange={onInputChange}
        />

        {isUploading ? (
          <div>
            <p style={{ fontSize: 14, color: 'var(--text-h)', margin: '0 0 12px', fontWeight: 500 }}>{message}</p>
            <ProgressBar value={progress} />
            <p style={{ fontSize: 11, color: 'var(--text)', marginTop: 8 }}>{progress}% complete</p>
          </div>
        ) : (
          <>
            <p style={{ fontSize: 32, margin: 0 }}>📄</p>
            <p style={{ fontWeight: 600, marginTop: 8, color: 'var(--text-h)' }}>
              Drop your documents here or click to browse
            </p>
            <p style={{ color: 'var(--text)', fontSize: 13 }}>
              CV, work references (Arbeitszeugnis), transcripts, links — up to 20 files
            </p>
            <p style={{ color: 'var(--text)', fontSize: 12, marginTop: 4 }}>
              PDF, DOCX, HTML, TXT, MD
            </p>
          </>
        )}
      </div>

      {selectedFiles.length > 0 && uiState === 'idle' && (
        <ul style={{ marginTop: 8, fontSize: 12, color: 'var(--text)', listStyle: 'none', padding: 0 }}>
          {selectedFiles.map((f, i) => (
            <li key={i}>{f.name} ({(f.size / 1024).toFixed(1)} KB)</li>
          ))}
        </ul>
      )}

      {uiState === 'error' && (
        <p style={{ color: '#ef4444', marginTop: 8, fontSize: 13 }}>{errorMsg}</p>
      )}
    </div>
  )
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
```

- [ ] **Step 3: Delete design components**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git rm frontend/src/components/DesignGallery.tsx
rtk git rm frontend/src/components/DesignEditor.tsx
rtk git rm frontend/src/components/DesignSelector.tsx
```

- [ ] **Step 4: Run TypeScript check**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/frontend
rtk tsc --noEmit
```

Expected: errors only from ProfilePage.tsx (still imports deleted components) — will be fixed in Task 9

- [ ] **Step 5: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add frontend/src/components/ApplicationGenerator.tsx frontend/src/components/ResumeUpload.tsx
rtk git commit -m "feat: ApplicationGenerator removes design selectors; ResumeUpload goes multi-file"
```

---

## Task 9: Frontend — ProfilePage Redesign

**Files:**
- Modify: `frontend/src/pages/ProfilePage.tsx`

**Interfaces:**
- Consumes: `updatePrompts` from `../api/client`
- Consumes: `DEFAULT_CV_PROMPT`, `DEFAULT_CL_PROMPT` from `../constants/promptDefaults`
- Props unchanged: `{ profile, onSearchJobs, onAutoSearch, onReimport, onProfileUpdated, autoSearchBadge? }`

- [ ] **Step 1: Rewrite ProfilePage.tsx**

Remove: all design imports, DesignEditor, DesignGallery, design-related state/handlers, seedingAll state, job suggestions hint banner.

Add: prompt editor section with two textareas + Save/Reset buttons, badge on Search Jobs button.

```tsx
import { useState } from 'react'
import { downloadMasterResume, updatePrompts, getProfile, type ProfileMaster, type WorkExperience, type Skill } from '../api/client'
import { DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT } from '../constants/promptDefaults'

interface Props {
  profile: ProfileMaster
  onSearchJobs: () => void
  onAutoSearch: () => void
  onReimport: () => void
  onProfileUpdated: (p: ProfileMaster) => void
  autoSearchBadge?: number
}

const LEVEL_DOTS: Record<string, number> = {
  beginner: 1, intermediate: 2, advanced: 3, expert: 4,
}

function SkillBadge({ skill }: { skill: Skill }) {
  const filled = LEVEL_DOTS[skill.level] ?? 2
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 20, border: '1px solid var(--border)', fontSize: 12, color: 'var(--text)' }}>
      {skill.name}
      <span style={{ display: 'flex', gap: 2 }}>
        {[1, 2, 3, 4].map(i => (
          <span key={i} style={{ width: 5, height: 5, borderRadius: '50%', background: i <= filled ? 'var(--accent)' : 'var(--border)' }} />
        ))}
      </span>
    </span>
  )
}

function XYZBullet({ action, metric, context }: { action: string; metric: string; context: string }) {
  return (
    <li style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.6, marginBottom: 4 }}>
      <span style={{ color: 'var(--text-h)', fontWeight: 500 }}>{action}</span>
      {' '}<span style={{ color: 'var(--accent)' }}>{metric}</span>
      {' '}<span>{context}</span>
    </li>
  )
}

function ExperienceCard({ exp }: { exp: WorkExperience }) {
  const start = new Date(exp.start_date).toLocaleDateString('en', { month: 'short', year: 'numeric' })
  const end = exp.is_current ? 'Present' : exp.end_date ? new Date(exp.end_date).toLocaleDateString('en', { month: 'short', year: 'numeric' }) : ''
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <div>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-h)' }}>{exp.role}</span>
          <span style={{ fontSize: 13, color: 'var(--text)', marginLeft: 6 }}>@ {exp.company}</span>
          {exp.location && <span style={{ fontSize: 12, color: 'var(--text)', marginLeft: 4 }}>· {exp.location}</span>}
        </div>
        <span style={{ fontSize: 11, color: 'var(--text)', whiteSpace: 'nowrap' }}>{start} – {end}</span>
      </div>
      <ul style={{ margin: '6px 0 0 0', paddingLeft: 16 }}>
        {exp.achievements.map((a, i) => (
          <XYZBullet key={i} action={a.action} metric={a.metric} context={a.context} />
        ))}
      </ul>
      {exp.technologies.length > 0 && (
        <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {exp.technologies.map(t => (
            <span key={t} style={{ fontSize: 11, padding: '1px 7px', borderRadius: 4, background: 'var(--code-bg)', color: 'var(--text)' }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--accent)', margin: '0 0 12px', borderBottom: '1px solid var(--border)', paddingBottom: 6 }}>
        {title}
      </h2>
      {children}
    </section>
  )
}

interface PromptEditorProps {
  label: string
  value: string
  defaultValue: string
  onChange: (v: string) => void
  onSave: () => Promise<void>
}

function PromptEditor({ label, value, defaultValue, onChange, onSave }: PromptEditorProps) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  async function handleSave() {
    setSaving(true)
    try {
      await onSave()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  function handleReset() {
    onChange(defaultValue)
  }

  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-h)' }}>{label}</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {saved && <span style={{ fontSize: 11, color: 'var(--accent)' }}>Saved ✓</span>}
          <button
            onClick={handleReset}
            style={{ fontSize: 11, padding: '3px 10px', borderRadius: 5, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', cursor: 'pointer' }}
          >
            Reset to default
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{ fontSize: 11, padding: '3px 10px', borderRadius: 5, border: 'none', background: 'var(--accent)', color: 'white', cursor: saving ? 'default' : 'pointer' }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        rows={18}
        style={{
          width: '100%', fontFamily: 'monospace', fontSize: 11,
          padding: '10px 12px', borderRadius: 6, border: '1px solid var(--border)',
          background: 'var(--code-bg)', color: 'var(--text)', resize: 'vertical',
          boxSizing: 'border-box',
        }}
      />
    </div>
  )
}

export function ProfilePage({ profile, onSearchJobs, onAutoSearch, onReimport, onProfileUpdated, autoSearchBadge }: Props) {
  const [downloading, setDownloading] = useState(false)
  const [cvPrompt, setCvPrompt] = useState(profile.cv_prompt)
  const [clPrompt, setClPrompt] = useState(profile.cover_letter_prompt)

  async function handleDownload() {
    setDownloading(true)
    try {
      const blob = await downloadMasterResume()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${profile.contact.full_name.replace(/ /g, '_')}_MasterResume.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  async function saveCvPrompt() {
    const updated = await updatePrompts({ cv_prompt: cvPrompt })
    onProfileUpdated(updated)
  }

  async function saveClPrompt() {
    const updated = await updatePrompts({ cover_letter_prompt: clPrompt })
    onProfileUpdated(updated)
  }

  const c = profile.contact

  return (
    <div style={{ maxWidth: 720, textAlign: 'left' }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, margin: '0 0 4px', color: 'var(--text-h)' }}>{c.full_name}</h1>
        <p style={{ fontSize: 13, color: 'var(--text)', margin: '0 0 12px' }}>
          {[c.email, c.phone, c.location].filter(Boolean).join('  ·  ')}
          {c.linkedin_url && <> · <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>LinkedIn</a></>}
          {c.github_url && <> · <a href={c.github_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>GitHub</a></>}
        </p>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            onClick={onSearchJobs}
            style={{ padding: '8px 18px', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: 7, fontWeight: 600, cursor: 'pointer', fontSize: 13, position: 'relative' }}
          >
            Search Jobs
            {profile.job_suggestions.length > 0 && (
              <span style={{
                marginLeft: 6, background: 'white', color: 'var(--accent)',
                borderRadius: '50%', fontSize: 10, fontWeight: 700,
                padding: '1px 5px', verticalAlign: 'middle',
              }}>
                {profile.job_suggestions.length}
              </span>
            )}
          </button>
          {profile.job_suggestions.length > 0 && (
            <button
              onClick={onAutoSearch}
              style={{ padding: '8px 18px', background: 'none', color: 'var(--accent)', border: '1px solid var(--accent-border)', borderRadius: 7, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}
            >
              ⚡ Auto Search
              {(autoSearchBadge ?? 0) > 0 && (
                <span style={{ marginLeft: 6, background: '#ef4444', color: 'white', borderRadius: '50%', fontSize: 10, fontWeight: 700, padding: '1px 5px', verticalAlign: 'middle' }}>
                  {autoSearchBadge}
                </span>
              )}
            </button>
          )}
          <button
            onClick={handleDownload}
            disabled={downloading}
            style={{ padding: '8px 18px', background: 'none', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 7, cursor: 'pointer', fontSize: 13 }}
          >
            {downloading ? 'Generating…' : 'Download Resume PDF'}
          </button>
          <button
            onClick={onReimport}
            style={{ padding: '8px 18px', background: 'none', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 7, cursor: 'pointer', fontSize: 13 }}
          >
            Re-import documents
          </button>
        </div>
      </div>

      {/* ── Summary ── */}
      {profile.summary && (
        <Section title="Summary">
          <p style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.7, margin: 0 }}>{profile.summary}</p>
        </Section>
      )}

      {/* ── Experience ── */}
      {profile.work_experiences.length > 0 && (
        <Section title="Experience">
          {profile.work_experiences.map(exp => <ExperienceCard key={exp.id} exp={exp} />)}
        </Section>
      )}

      {/* ── Skills ── */}
      {profile.skills.length > 0 && (
        <Section title="Skills">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {profile.skills.map(s => <SkillBadge key={s.name} skill={s} />)}
          </div>
        </Section>
      )}

      {/* ── Education ── */}
      {profile.education.length > 0 && (
        <Section title="Education">
          {profile.education.map(edu => (
            <div key={edu.id} style={{ marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-h)' }}>
                {edu.degree} in {edu.field_of_study}
              </span>
              <span style={{ fontSize: 13, color: 'var(--text)' }}> — {edu.institution}</span>
              {edu.end_date && <span style={{ fontSize: 12, color: 'var(--text)', marginLeft: 6 }}>({new Date(edu.end_date).getFullYear()})</span>}
            </div>
          ))}
        </Section>
      )}

      {/* ── Languages ── */}
      {profile.languages.length > 0 && (
        <Section title="Languages">
          <p style={{ fontSize: 13, color: 'var(--text)', margin: 0 }}>
            {profile.languages.map(l => `${l.name} (${l.proficiency})`).join('  ·  ')}
          </p>
        </Section>
      )}

      {/* ── Generation Prompts ── */}
      <Section title="Generation Prompts">
        <p style={{ fontSize: 12, color: 'var(--text)', marginBottom: 16 }}>
          These prompts are sent to the AI when generating your resume and cover letter PDFs.
          Use <code style={{ fontSize: 11, background: 'var(--code-bg)', padding: '1px 4px', borderRadius: 3 }}>{'{JOB_DESCRIPTION}'}</code> as placeholder — it's replaced automatically with the job details.
        </p>
        <PromptEditor
          label="Resume Prompt"
          value={cvPrompt}
          defaultValue={DEFAULT_CV_PROMPT}
          onChange={setCvPrompt}
          onSave={saveCvPrompt}
        />
        <PromptEditor
          label="Cover Letter Prompt"
          value={clPrompt}
          defaultValue={DEFAULT_CL_PROMPT}
          onChange={setClPrompt}
          onSave={saveClPrompt}
        />
      </Section>
    </div>
  )
}
```

- [ ] **Step 2: Run TypeScript check**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/frontend
rtk tsc --noEmit
```

Expected: 0 errors

- [ ] **Step 3: Check App.tsx or parent for ApplicationGenerator calls using `designs` prop — remove if present**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/frontend
rtk grep "designs=" src/ --include="*.tsx"
```

If any results: remove the `designs` prop from any call site (the prop no longer exists).

- [ ] **Step 4: Final backend test run**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/backend
rtk pytest --tb=short -q
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter
rtk git add frontend/src/pages/ProfilePage.tsx
rtk git commit -m "feat: ProfilePage — prompt editor, Search Jobs badge, remove design sections"
```

---

## Self-Review

### Spec Coverage

| Spec section | Task |
|---|---|
| §1 Remove design system (backend) | Task 6 |
| §1 Remove design system (frontend) | Tasks 7, 8 |
| §1 Remove ProfileMaster design fields | Task 2 |
| §2 Multi-file upload (backend) | Tasks 3, 4 |
| §2 Multi-file upload (frontend) | Tasks 7, 8 |
| §2 Per-file LLM relevance extraction | Task 3 |
| §2 reference_text cap 60k | Task 3 |
| §3 ProfileMaster new fields | Task 2 |
| §4 DEFAULT_CV_PROMPT + DEFAULT_CL_PROMPT | Task 1 |
| §5 Prompt-based application generation | Task 5 |
| §5.1 Master resume generic job | Task 5 |
| §6 PATCH /profile/prompts backend | Task 4 |
| §7 Prompt editor frontend | Task 9 |
| §8 Job suggestions badge | Task 9 |
| §9 ApplicationGenerator simplification | Task 8 |
| §10 Error handling (unsupported files, >20 files) | Tasks 3, 4 |
| §11 Tests | All tasks |

### Placeholder Scan

- Task 1 Step 2: TS `promptDefaults.ts` says "exact same content" — the implementer must copy the Python string verbatim. This is explicit copy instruction, not a vague placeholder. ✓
- No TBD/TODO found in plan.

### Type Consistency

- `ingestProfile(files: File[])` defined in Task 7 → used by `ResumeUpload` in Task 8 as `ingestProfile(files)` ✓
- `generateApplication(job, match)` defined in Task 7 → used in Task 8 `ApplicationGenerator` ✓
- `updatePrompts({cv_prompt?, cover_letter_prompt?})` defined in Task 7 → used in Task 9 ✓
- `ProfileMaster.cv_prompt`, `.cover_letter_prompt`, `.reference_text` defined in Task 2 → consumed in Tasks 5, 9 ✓
- `IngestionService.run(reference_text, progress_fn)` defined in Task 4 → called in updated router Task 4 ✓
- `compile_reference_text(files: list[tuple[str,bytes]])` defined in Task 3 → imported in router Task 4 ✓
