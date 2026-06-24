# Tauri 2.0 Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate Job Hunter Assistant from Docker-based web app to Tauri 2.0 desktop app with bundled Python FastAPI sidecar, in-app settings UI replacing `.env`, and GitHub Actions cross-platform release pipeline.

**Architecture:** Tauri 2.0 shell wraps the existing React frontend as a WebView and launches the existing Python FastAPI backend as a PyInstaller-compiled sidecar on `localhost:8000`. Config (LLM keys, Adzuna keys, prompts, language) is persisted via `@tauri-apps/plugin-store` and POSTed to the backend on startup and change. Playwright is removed; CV/resume HTML is opened in a native Tauri window so the user prints-to-PDF themselves.

**Tech Stack:** Tauri 2.0, Rust (minimal), React 19 + TypeScript (existing), Python 3.12 + FastAPI (existing), PyInstaller 6.x, `@tauri-apps/plugin-store` v2, `@tauri-apps/api` v2, GitHub Actions `tauri-apps/tauri-action`

## Global Constraints

- Tauri version: **2.0** (not v1 — APIs differ significantly)
- Python backend: no logic rewrite — only additions (`POST /config/update`, `paths.py`) and deletions (Playwright)
- No `.env` files in shipped app — all config persists via Tauri Store (`plugin-store`)
- `docker-compose.yml` and `backend/Dockerfile` deleted after migration
- `playwright>=1.44` removed from `requirements.txt`; `playwright_renderer.py` deleted
- CV/resume preview: Tauri native window (HTML), user saves PDF via OS print dialog (Ctrl+P)
- PyInstaller: `onefile=True` binary per platform
- GitHub Actions: build on `ubuntu-latest`, `windows-latest`, `macos-latest`; trigger on git tag `v*.*.*`
- Landing page: single `landing/index.html`, no framework, no build step
- Backend: `localhost:8000` fixed port
- Frontend `BASE` URL: `import.meta.env.VITE_API_BASE ?? '/api'` (Tauri build sets `VITE_API_BASE=http://localhost:8000`)
- Data files stored in OS app data dir via `JH_DATA_DIR` env var (set by Tauri on sidecar launch):
  - Windows: `%APPDATA%\job-hunter\`
  - Linux: `~/.local/share/job-hunter/`
  - macOS: `~/Library/Application Support/job-hunter/`
- Three backend files currently use `Path.home() / ".job_hunter"` — all migrate to `DATA_DIR`: `profile_repository.py`, `auto_search_store.py`, `search_cache.py`
- `ApplicationPackage` changes: remove `resume_pdf_base64` + `cover_letter_pdf_base64`, add `resume_html` + `cover_letter_html`; keep `cover_letter_text`
- `GET /application/master-resume` changes: was PDF bytes, now returns `{ "html": "..." }` JSON
- LLM providers in settings UI: `openai`, `ollama`, `lmstudio`, `groq`, `mistral`, `compatible`
- Language dropdown: exactly 30 languages (listed verbatim in Task 3)

---

## File Map

**Created:**
- `backend/app/core/paths.py` — `DATA_DIR` singleton
- `backend/run.py` — PyInstaller entry point (uvicorn launcher)
- `backend/backend.spec` — PyInstaller build spec
- `src-tauri/Cargo.toml`
- `src-tauri/build.rs`
- `src-tauri/tauri.conf.json`
- `src-tauri/capabilities/default.json`
- `src-tauri/src/main.rs`
- `src-tauri/src/lib.rs`
- `frontend/src/store/appConfig.ts`
- `frontend/src/pages/SettingsPage.tsx`
- `frontend/src/components/SettingsButton.tsx`
- `.github/workflows/release.yml`
- `landing/index.html`

**Modified:**
- `backend/app/repositories/profile_repository.py` — use `DATA_DIR`
- `backend/app/services/auto_search_store.py` — use `DATA_DIR`
- `backend/app/services/search_cache.py` — use `DATA_DIR`
- `backend/app/core/config.py` — add `cv_language`, `cl_language`, `cv_prompt_override`, `cl_prompt_override` fields; add `update_from_config()` method; keep `LLMProvider` enum
- `backend/app/routers/config.py` — add `POST /config/update`
- `backend/app/services/application.py` — remove `_html_to_pdf`, inject language into prompt, return HTML
- `backend/app/routers/application.py` — update `ApplicationPackage` model + `master-resume` endpoint
- `backend/requirements.txt` — remove `playwright>=1.44`
- `frontend/vite.config.ts` — add `VITE_API_BASE` env + Tauri `server.clearScreen: false`
- `frontend/package.json` — add `@tauri-apps/api`, `@tauri-apps/plugin-store`, `@tauri-apps/cli` devDep; add `tauri` script
- `frontend/src/api/client.ts` — `BASE` from env var, `updateConfig()`, new `ApplicationPackage` type, `openCvPreview()` Tauri command, `getMasterResumeHtml()`
- `frontend/src/components/ApplicationGenerator.tsx` — open Tauri windows instead of PDF downloads
- `frontend/src/pages/ProfilePage.tsx` — settings gear button; "Download Resume PDF" → Tauri window preview
- `frontend/src/pages/IngestPage.tsx` — config-incomplete warning banner
- `frontend/src/App.tsx` — add `'settings'` state; config boot on mount

**Deleted:**
- `backend/app/services/playwright_renderer.py`
- `docker-compose.yml`
- `backend/Dockerfile`

---

### Task 1: Backend Changes — Data Dir, Config Endpoint, Remove Playwright, HTML Returns

**Files:**
- Create: `backend/app/core/paths.py`
- Modify: `backend/app/repositories/profile_repository.py`
- Modify: `backend/app/services/auto_search_store.py`
- Modify: `backend/app/services/search_cache.py`
- Modify: `backend/app/core/config.py`
- Modify: `backend/app/routers/config.py`
- Modify: `backend/app/services/application.py`
- Modify: `backend/app/routers/application.py`
- Modify: `backend/requirements.txt`
- Delete: `backend/app/services/playwright_renderer.py`
- Test: `backend/tests/test_routers/test_config.py` (extend existing)

**Interfaces:**
- Produces: `POST /config/update` accepts `ConfigUpdate` body → `{"ok": true}`
- Produces: `POST /application/generate` returns `ApplicationPackage` with `resume_html`, `cover_letter_html`, `cover_letter_text` (no PDF base64)
- Produces: `GET /application/master-resume` returns `{"html": "..."}` JSON (was PDF bytes)
- Produces: `settings.update_from_config(body: ConfigUpdate)` mutates global settings in memory

- [ ] **Step 1: Create `backend/app/core/paths.py`**

```python
# backend/app/core/paths.py
from __future__ import annotations

import os
import pathlib

DATA_DIR: pathlib.Path = pathlib.Path(
    os.environ.get(
        "JH_DATA_DIR",
        pathlib.Path.home() / ".local" / "share" / "job-hunter",
    )
)
DATA_DIR.mkdir(parents=True, exist_ok=True)
```

- [ ] **Step 2: Update `backend/app/repositories/profile_repository.py`**

Replace the `_STORAGE_DIR` line (currently `Path.home() / ".job_hunter"`) and its dependents:

```python
# backend/app/repositories/profile_repository.py
from __future__ import annotations

import json
from pathlib import Path

from pydantic import ValidationError

from app.core.paths import DATA_DIR
from app.models.profile import ProfileMaster

_PROFILE_PATH = DATA_DIR / "profile_master.json"
_PARTIAL_PATH = DATA_DIR / "profile_partial.json"


class ProfileNotFoundError(Exception):
    pass


class ProfileRepository:
    def __init__(self, path: Path = _PROFILE_PATH, partial_path: Path = _PARTIAL_PATH) -> None:
        self._partial_path = partial_path
        self._path = path
        self._path.parent.mkdir(parents=True, exist_ok=True)

    def save(self, profile: ProfileMaster) -> None:
        self._path.write_text(
            profile.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )

    def load(self) -> ProfileMaster:
        if not self._path.exists():
            raise ProfileNotFoundError(
                f"No profile found at {self._path}. "
                "Upload a resume to create your profile."
            )
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
            return ProfileMaster.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Stored profile is corrupted: {exc}") from exc

    def exists(self) -> bool:
        return self._path.exists()

    def delete(self) -> None:
        if self._path.exists():
            self._path.unlink()

    def save_partial(self, profile: ProfileMaster) -> None:
        self._partial_path.parent.mkdir(parents=True, exist_ok=True)
        self._partial_path.write_text(
            profile.model_dump_json(indent=2, exclude_none=True),
            encoding="utf-8",
        )

    def load_partial(self) -> ProfileMaster:
        if not self._partial_path.exists():
            raise ProfileNotFoundError("No partial profile found. Run /ingest first.")
        try:
            data = json.loads(self._partial_path.read_text(encoding="utf-8"))
            return ProfileMaster.model_validate(data)
        except ValidationError as exc:
            raise ValueError(f"Partial profile is corrupted: {exc}") from exc

    def partial_exists(self) -> bool:
        return self._partial_path.exists()

    def delete_partial(self) -> None:
        if self._partial_path.exists():
            self._partial_path.unlink()
```

- [ ] **Step 3: Update `backend/app/services/auto_search_store.py`**

Replace the three `_STORAGE_DIR` / `_CONFIG_PATH` / `_RESULTS_PATH` / `_STATUS_PATH` lines at the top of the file:

```python
# Replace lines 24-27 (the four path constants) with:
from app.core.paths import DATA_DIR

_STORAGE_DIR = DATA_DIR
_CONFIG_PATH = _STORAGE_DIR / "auto_search_config.json"
_RESULTS_PATH = _STORAGE_DIR / "auto_search_results.json"
_STATUS_PATH = _STORAGE_DIR / "job_status.json"
```

Keep all other code in `auto_search_store.py` unchanged.

- [ ] **Step 4: Update `backend/app/services/search_cache.py`**

Replace `_CACHE_DIR = Path.home() / ".job_hunter" / "search_cache"` with:

```python
from app.core.paths import DATA_DIR

_CACHE_DIR = DATA_DIR / "search_cache"
```

Remove the `from pathlib import Path` import if it's only used for that line (keep it if used elsewhere in the file).

- [ ] **Step 5: Add fields and `update_from_config` to `backend/app/core/config.py`**

Add new optional fields and the `update_from_config` method to the `Settings` class. The new complete file:

```python
# backend/app/core/config.py
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class LLMProvider(str, Enum):
    OPENAI = "openai"
    LOCAL = "local"  # Any OpenAI-compatible endpoint (Ollama, LM Studio, vLLM, …)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── Provider ──────────────────────────────────────────────────────────────
    llm_provider: LLMProvider = Field(default=LLMProvider.LOCAL)

    # ── OpenAI ────────────────────────────────────────────────────────────────
    openai_api_key: Optional[str] = Field(default=None)
    openai_model: str = Field(default="gpt-4o-mini")

    # ── Local / OpenAI-compatible ─────────────────────────────────────────────
    local_base_url: str = Field(default="http://localhost:11434/v1")
    local_api_key: str = Field(default="ollama")
    local_model: str = Field(default="llama3.2")

    # ── Job Search ────────────────────────────────────────────────────────────
    search_provider: str = Field(default="mock")
    adzuna_app_id: Optional[str] = Field(default=None)
    adzuna_api_key: Optional[str] = Field(default=None)
    adzuna_country: str = Field(default="de")

    # ── Search cache ──────────────────────────────────────────────────────────
    search_cache_ttl_hours: int = Field(default=2, ge=0)

    # ── Shared parameters ─────────────────────────────────────────────────────
    llm_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    llm_max_retries: int = Field(default=3, ge=1, le=10)

    # ── Output language (set via POST /config/update from frontend) ───────────
    cv_language: str = Field(default="English")
    cl_language: str = Field(default="English")

    # ── Prompt overrides (None = use prompt_defaults module values) ────────────
    cv_prompt_override: Optional[str] = Field(default=None)
    cl_prompt_override: Optional[str] = Field(default=None)

    # ── Validation ────────────────────────────────────────────────────────────
    @model_validator(mode="after")
    def require_api_key_for_openai(self) -> Settings:
        if self.llm_provider == LLMProvider.OPENAI and not self.openai_api_key:
            # In Tauri mode config comes via POST /config/update — skip .env validation
            pass
        return self

    # ── Convenience properties ────────────────────────────────────────────────
    @property
    def active_model(self) -> str:
        return (
            self.openai_model
            if self.llm_provider == LLMProvider.OPENAI
            else self.local_model
        )

    @property
    def active_base_url(self) -> Optional[str]:
        return None if self.llm_provider == LLMProvider.OPENAI else self.local_base_url

    @property
    def active_api_key(self) -> str:
        return (
            self.openai_api_key or ""
            if self.llm_provider == LLMProvider.OPENAI
            else self.local_api_key
        )

    # ── Runtime mutation (called by POST /config/update) ─────────────────────
    def update_from_config(
        self,
        *,
        llm_provider: str,
        llm_model: str,
        llm_api_key: Optional[str],
        llm_base_url: Optional[str],
        llm_temperature: float,
        adzuna_app_id: Optional[str],
        adzuna_api_key: Optional[str],
        adzuna_country: str,
        search_provider: str,
        cv_prompt: Optional[str],
        cl_prompt: Optional[str],
        cv_language: str,
        cl_language: str,
    ) -> None:
        provider = LLMProvider(llm_provider)
        self.llm_provider = provider
        if provider == LLMProvider.OPENAI:
            if llm_api_key:
                self.openai_api_key = llm_api_key
            if llm_model:
                self.openai_model = llm_model
        else:
            self.local_model = llm_model or self.local_model
            self.local_base_url = llm_base_url or self.local_base_url
            self.local_api_key = llm_api_key or self.local_api_key
        self.llm_temperature = llm_temperature
        self.adzuna_app_id = adzuna_app_id or self.adzuna_app_id
        self.adzuna_api_key = adzuna_api_key or self.adzuna_api_key
        self.adzuna_country = adzuna_country or self.adzuna_country
        self.search_provider = search_provider
        self.cv_prompt_override = cv_prompt or None
        self.cl_prompt_override = cl_prompt or None
        self.cv_language = cv_language or "English"
        self.cl_language = cl_language or "English"


settings = Settings()
```

- [ ] **Step 6: Add `POST /config/update` to `backend/app/routers/config.py`**

```python
# backend/app/routers/config.py
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

from app.core.config import LLMProvider, settings

router = APIRouter(prefix="/config", tags=["system"])


class LLMConfigView(BaseModel):
    provider: LLMProvider
    model: str
    base_url: Optional[str]
    temperature: float
    max_retries: int
    api_key_set: bool


class ConfigUpdate(BaseModel):
    llm_provider: str = "local"
    llm_model: str = "llama3.2"
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_temperature: float = 0.0
    adzuna_app_id: Optional[str] = None
    adzuna_api_key: Optional[str] = None
    adzuna_country: str = "de"
    search_provider: str = "mock"
    cv_prompt: Optional[str] = None
    cl_prompt: Optional[str] = None
    cv_language: str = "English"
    cl_language: str = "English"


@router.get("/llm", response_model=LLMConfigView)
async def get_llm_config() -> LLMConfigView:
    return LLMConfigView(
        provider=settings.llm_provider,
        model=settings.active_model,
        base_url=settings.active_base_url,
        temperature=settings.llm_temperature,
        max_retries=settings.llm_max_retries,
        api_key_set=bool(settings.active_api_key),
    )


@router.post("/update", status_code=200)
async def update_config(body: ConfigUpdate) -> dict:
    settings.update_from_config(
        llm_provider=body.llm_provider,
        llm_model=body.llm_model,
        llm_api_key=body.llm_api_key,
        llm_base_url=body.llm_base_url,
        llm_temperature=body.llm_temperature,
        adzuna_app_id=body.adzuna_app_id,
        adzuna_api_key=body.adzuna_api_key,
        adzuna_country=body.adzuna_country,
        search_provider=body.search_provider,
        cv_prompt=body.cv_prompt,
        cl_prompt=body.cl_prompt,
        cv_language=body.cv_language,
        cl_language=body.cl_language,
    )
    return {"ok": True}
```

- [ ] **Step 7: Write test for `POST /config/update`**

Add to `backend/tests/test_routers/test_config.py` (create file if it doesn't exist):

```python
# backend/tests/test_routers/test_config.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.core.config import settings, LLMProvider


@pytest.mark.asyncio
async def test_get_llm_config_returns_current_settings():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/config/llm")
    assert resp.status_code == 200
    data = resp.json()
    assert "provider" in data
    assert "model" in data
    assert "api_key_set" in data


@pytest.mark.asyncio
async def test_update_config_changes_language():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/config/update", json={
            "llm_provider": "local",
            "llm_model": "llama3.2",
            "cv_language": "Deutsch",
            "cl_language": "Deutsch",
        })
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}
    assert settings.cv_language == "Deutsch"
    assert settings.cl_language == "Deutsch"


@pytest.mark.asyncio
async def test_update_config_sets_search_provider():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/config/update", json={
            "llm_provider": "local",
            "llm_model": "llama3.2",
            "search_provider": "adzuna",
            "adzuna_app_id": "test_id",
            "adzuna_api_key": "test_key",
        })
    assert resp.status_code == 200
    assert settings.search_provider == "adzuna"
    assert settings.adzuna_app_id == "test_id"
```

- [ ] **Step 8: Run backend tests**

```bash
cd backend
pytest tests/test_routers/test_config.py -v
```

Expected: 3 tests PASS

- [ ] **Step 9: Update `backend/app/services/application.py`**

Remove `_html_to_pdf`, inject language into prompts, return HTML strings:

```python
# backend/app/services/application.py
from __future__ import annotations

import logging
import re

from app.core.config import settings
from app.core.llm import get_llm_client
from app.models.jobs import JobPosting, MatchScore
from app.models.profile import ProfileMaster
from app.services.prompt_defaults import DEFAULT_CV_PROMPT, DEFAULT_COVER_LETTER_PROMPT

logger = logging.getLogger(__name__)


def _extract_text_from_html(html: str) -> str:
    return re.sub(r"<[^>]+>", " ", html).strip()


def _generate_html(profile: ProfileMaster, job: JobPosting, prompt: str, language: str) -> str:
    """Send reference_text + filled prompt to LLM; return raw HTML string."""
    job_desc = f"{job.title} at {job.company}\n\n{job.description or ''}\n\nURL: {job.url or ''}"
    filled = prompt.replace("{JOB_DESCRIPTION}", job_desc)
    if language and language != "English":
        filled = f"Generate the output in {language}.\n\n" + filled

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
        temperature=settings.llm_temperature,
    )
    raw = (response.choices[0].message.content or "").strip()
    if raw.startswith("```"):
        raw = "\n".join(raw.split("\n")[1:])
    if raw.endswith("```"):
        raw = "\n".join(raw.split("\n")[:-1])
    return raw.strip()


def _get_cv_prompt(profile: ProfileMaster) -> str:
    """Returns the active CV prompt: runtime override > profile prompt > module default."""
    return settings.cv_prompt_override or profile.cv_prompt or DEFAULT_CV_PROMPT


def _get_cl_prompt(profile: ProfileMaster) -> str:
    return settings.cl_prompt_override or profile.cover_letter_prompt or DEFAULT_COVER_LETTER_PROMPT


def generate_application_package(
    profile: ProfileMaster,
    job: JobPosting,
    match: MatchScore,
) -> dict:
    resume_html = _generate_html(profile, job, _get_cv_prompt(profile), settings.cv_language)
    cl_html = _generate_html(profile, job, _get_cl_prompt(profile), settings.cl_language)

    return {
        "job_id": str(job.id),
        "resume_html": resume_html,
        "cover_letter_html": cl_html,
        "cover_letter_text": _extract_text_from_html(cl_html),
    }


def generate_master_resume_html(profile: ProfileMaster) -> str:
    """Generate a general-purpose resume HTML without tailoring to a specific job."""
    from uuid import uuid4
    from app.models.jobs import JobPosting
    generic_job = JobPosting(
        id=uuid4(),
        title="General Application",
        company="",
        location="",
        description="General purpose — showcase all experience and skills.",
        url="",
        source="master",
    )
    return _generate_html(profile, generic_job, _get_cv_prompt(profile), settings.cv_language)
```

- [ ] **Step 10: Update `backend/app/routers/application.py`**

```python
# backend/app/routers/application.py
from __future__ import annotations

import asyncio

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel

from app.models.jobs import JobPosting, MatchScore
from app.repositories.profile_repository import ProfileNotFoundError, ProfileRepository
from app.services.application import generate_application_package, generate_master_resume_html

router = APIRouter(prefix="/application", tags=["application"])

_repo = ProfileRepository()


class ApplicationPackage(BaseModel):
    job_id: str
    resume_html: str
    cover_letter_html: str
    cover_letter_text: str


class MasterResumeResponse(BaseModel):
    html: str


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
        result = await asyncio.get_running_loop().run_in_executor(
            None,
            lambda: generate_application_package(profile, req.job, req.match),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Generation failed: {exc}",
        )
    return ApplicationPackage(**result)


@router.get("/master-resume", response_model=MasterResumeResponse)
async def download_master_resume() -> MasterResumeResponse:
    try:
        profile = _repo.load()
    except ProfileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="No profile found.")

    html = await asyncio.get_running_loop().run_in_executor(
        None, generate_master_resume_html, profile
    )
    return MasterResumeResponse(html=html)
```

- [ ] **Step 11: Delete `backend/app/services/playwright_renderer.py`**

```bash
rm backend/app/services/playwright_renderer.py
```

- [ ] **Step 12: Remove playwright from `backend/requirements.txt`**

Remove the line `playwright>=1.44` from `backend/requirements.txt`. Verify the file still has all other deps.

- [ ] **Step 13: Run full backend test suite**

```bash
cd backend
pytest -x -q
```

Expected: all tests pass. If any test imports `playwright_renderer` or uses old `ApplicationPackage` fields (`resume_pdf_base64`, `cover_letter_pdf_base64`), update those tests to use the new `resume_html` / `cover_letter_html` fields.

- [ ] **Step 14: Commit**

```bash
git add backend/app/core/paths.py \
        backend/app/core/config.py \
        backend/app/routers/config.py \
        backend/app/routers/application.py \
        backend/app/services/application.py \
        backend/app/repositories/profile_repository.py \
        backend/app/services/auto_search_store.py \
        backend/app/services/search_cache.py \
        backend/requirements.txt \
        backend/tests/test_routers/test_config.py
git rm backend/app/services/playwright_renderer.py
git commit -m "feat: backend — data dir migration, POST /config/update, remove Playwright, HTML returns"
```

---

### Task 2: Tauri Scaffold — `src-tauri/`, sidecar launch, CV preview window

**Files:**
- Create: `src-tauri/Cargo.toml`
- Create: `src-tauri/build.rs`
- Create: `src-tauri/tauri.conf.json`
- Create: `src-tauri/capabilities/default.json`
- Create: `src-tauri/src/main.rs`
- Create: `src-tauri/src/lib.rs`
- Create: `src-tauri/icons/` (placeholder icons — real icons can be added later)
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/package.json`

**Interfaces:**
- Consumes: sidecar binary at `src-tauri/binaries/job-hunter-backend-{triple}` (present in CI; in dev, start backend manually)
- Produces: Tauri command `open_cv_preview(html: String)` callable from frontend via `invoke('open_cv_preview', { html })`
- Produces: `tauri dev` starts the app in development mode (WebView + sidecar)
- Produces: `tauri build` produces platform installer

- [ ] **Step 1: Install Tauri CLI and dependencies**

```bash
# In the repo root
cargo install tauri-cli --version "^2.0" --locked
```

```bash
# In frontend/
cd frontend
pnpm add @tauri-apps/api@^2 @tauri-apps/plugin-store@^2
pnpm add -D @tauri-apps/cli@^2
```

- [ ] **Step 2: Create `src-tauri/Cargo.toml`**

```toml
[package]
name = "job-hunter"
version = "0.1.0"
description = "Job Hunter Assistant"
authors = ["you"]
edition = "2021"

[lib]
name = "job_hunter_lib"
crate-type = ["staticlib", "cdylib", "rlib"]

[[bin]]
name = "job-hunter"
path = "src/main.rs"

[build-dependencies]
tauri-build = { version = "2", features = [] }

[dependencies]
tauri = { version = "2", features = [] }
tauri-plugin-shell = "2"
tauri-plugin-store = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"

[profile.release]
panic = "abort"
codegen-units = 1
lto = true
opt-level = "s"
strip = true
```

- [ ] **Step 3: Create `src-tauri/build.rs`**

```rust
fn main() {
    tauri_build::build()
}
```

- [ ] **Step 4: Create `src-tauri/tauri.conf.json`**

```json
{
  "productName": "Job Hunter Assistant",
  "version": "0.1.0",
  "identifier": "com.jobhunter.app",
  "build": {
    "frontendDist": "../frontend/dist",
    "devUrl": "http://localhost:5173",
    "beforeDevCommand": "cd ../frontend && pnpm dev",
    "beforeBuildCommand": "cd ../frontend && pnpm build"
  },
  "app": {
    "windows": [
      {
        "title": "Job Hunter Assistant",
        "width": 1200,
        "height": 800,
        "minWidth": 900,
        "minHeight": 600
      }
    ],
    "security": {
      "csp": null
    }
  },
  "bundle": {
    "active": true,
    "targets": "all",
    "icon": [
      "icons/32x32.png",
      "icons/128x128.png",
      "icons/128x128@2x.png",
      "icons/icon.icns",
      "icons/icon.ico"
    ],
    "externalBin": ["binaries/job-hunter-backend"]
  }
}
```

- [ ] **Step 5: Create `src-tauri/capabilities/default.json`**

```json
{
  "$schema": "../node_modules/@tauri-apps/cli/schema/acl/capability.schema.json",
  "identifier": "default",
  "description": "Default capabilities for Job Hunter Assistant",
  "platforms": ["linux", "macOS", "windows"],
  "windows": ["main", "cv-preview"],
  "permissions": [
    "core:default",
    "core:window:allow-create",
    "core:window:allow-close",
    "shell:allow-spawn",
    "shell:allow-execute",
    "store:allow-load",
    "store:allow-get",
    "store:allow-set",
    "store:allow-save",
    "store:allow-entries"
  ]
}
```

- [ ] **Step 6: Create `src-tauri/src/main.rs`**

```rust
// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

fn main() {
    job_hunter_lib::run();
}
```

- [ ] **Step 7: Create `src-tauri/src/lib.rs`**

```rust
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_shell::ShellExt;

#[tauri::command]
fn open_cv_preview(app: tauri::AppHandle, html: String) -> Result<(), String> {
    // Write to a temp file — data URIs have size limits in some WebViews
    let tmp = std::env::temp_dir().join("jh-cv-preview.html");
    std::fs::write(&tmp, html.as_bytes()).map_err(|e| e.to_string())?;
    let url_str = format!(
        "file://{}",
        tmp.to_str().unwrap_or_default().replace('\\', "/")
    );
    let url: tauri::utils::config::WebviewUrl = url_str.parse().map_err(|e: url::ParseError| e.to_string())?;
    WebviewWindowBuilder::new(&app, "cv-preview", WebviewUrl::External(url_str.parse().map_err(|e: url::ParseError| e.to_string())?))
        .title("CV Preview — press Ctrl+P to save as PDF")
        .width(900)
        .height(1200)
        .build()
        .map_err(|e| e.to_string())?;
    Ok(())
}

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_store::Builder::new().build())
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;

            // In dev mode, sidecar may not exist — skip gracefully
            let sidecar_result = app
                .shell()
                .sidecar("job-hunter-backend")
                .map(|cmd| cmd.env("JH_DATA_DIR", data_dir.to_str().unwrap_or_default()))
                .and_then(|cmd| cmd.spawn());

            match sidecar_result {
                Ok((_rx, child)) => {
                    app.manage(child);
                }
                Err(e) => {
                    eprintln!("Sidecar not found (dev mode?): {e}");
                }
            }
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![open_cv_preview])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

- [ ] **Step 8: Generate placeholder icons**

Tauri requires icon files. Install and generate:

```bash
cd src-tauri
cargo tauri icon ../frontend/public/vite.svg  # or any 512x512 PNG you have
```

If `cargo tauri icon` fails without a high-res PNG, create a minimal `icons/` directory:

```bash
mkdir -p src-tauri/icons
# Tauri will fail to build without icons — use tauri-cli to generate from any 512x512 PNG:
# cargo tauri icon path/to/512x512.png
# For now, copy the placeholder approach:
```

**Important:** You need at least a 512x512 PNG to generate all icon formats. If none exists, create one:

```bash
# On Linux/Mac with ImageMagick:
convert -size 512x512 xc:#1E4D9E src-tauri/icons/app-icon.png
cargo tauri icon src-tauri/icons/app-icon.png

# On Windows without ImageMagick, download any 512x512 PNG and run:
cargo tauri icon path\to\icon.png
```

This creates `icons/32x32.png`, `icons/128x128.png`, `icons/128x128@2x.png`, `icons/icon.icns`, `icons/icon.ico`.

- [ ] **Step 9: Update `frontend/vite.config.ts`**

```typescript
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const host = process.env.TAURI_DEV_HOST

export default defineConfig({
  plugins: [react()],
  clearScreen: false,
  server: {
    port: 5173,
    strictPort: true,
    host: host || false,
    hmr: host
      ? {
          protocol: 'ws',
          host,
          port: 5183,
        }
      : undefined,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  envPrefix: ['VITE_', 'TAURI_'],
  build: {
    target: process.env.TAURI_ENV_PLATFORM === 'windows' ? 'chrome105' : 'safari13',
    minify: !process.env.TAURI_ENV_DEBUG ? 'esbuild' : false,
    sourcemap: !!process.env.TAURI_ENV_DEBUG,
  },
})
```

- [ ] **Step 10: Update `frontend/package.json` scripts**

Add Tauri scripts (merge with existing):

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc -b && vite build",
    "lint": "eslint .",
    "preview": "vite preview",
    "tauri": "tauri",
    "api:types": "openapi-typescript http://localhost:8000/openapi.json -o src/api/schema.d.ts"
  }
}
```

- [ ] **Step 11: Verify Tauri builds (without sidecar in dev)**

```bash
cd frontend
pnpm tauri dev
```

Expected: app window opens showing the React frontend. Console may log "Sidecar not found (dev mode?)" — this is correct. The WebView should show the app UI (may show errors about backend not available, which is expected without the sidecar running).

If `cargo` compilation errors occur in `lib.rs`, fix them. The most common issue is the `WebviewUrl` type path — adjust the import if needed:

```rust
// Alternative URL construction if parse() fails:
let url = tauri::WebviewUrl::External(
    url::Url::parse(&url_str).map_err(|e| e.to_string())?
);
```

- [ ] **Step 12: Commit**

```bash
git add src-tauri/ frontend/vite.config.ts frontend/package.json frontend/pnpm-lock.yaml
git commit -m "feat: Tauri 2.0 scaffold — sidecar launch, CV preview window command"
```

---

### Task 3: Frontend — Config Store, SettingsPage, App.tsx wiring, ApplicationGenerator

**Files:**
- Create: `frontend/src/store/appConfig.ts`
- Create: `frontend/src/pages/SettingsPage.tsx`
- Create: `frontend/src/components/SettingsButton.tsx`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/components/ApplicationGenerator.tsx`
- Modify: `frontend/src/pages/ProfilePage.tsx`
- Modify: `frontend/src/pages/IngestPage.tsx`
- Modify: `frontend/src/App.tsx`

**Interfaces:**
- Consumes: `invoke('open_cv_preview', { html })` from Task 2
- Consumes: `POST /config/update` from Task 1
- Consumes: new `ApplicationPackage` type (`resume_html`, `cover_letter_html`) from Task 1
- Consumes: `GET /application/master-resume` returns `{ html }` from Task 1
- Produces: `AppState` includes `'settings'`
- Produces: `SettingsPage` rendered when `appState === 'settings'`

- [ ] **Step 1: Create `frontend/src/store/appConfig.ts`**

```typescript
// frontend/src/store/appConfig.ts
import { load } from '@tauri-apps/plugin-store'

export type LLMProvider = 'openai' | 'ollama' | 'lmstudio' | 'groq' | 'mistral' | 'compatible'

export interface AppConfig {
  llmProvider: LLMProvider
  llmApiKey: string
  llmModel: string
  llmBaseUrl: string
  llmTemperature: number
  adzunaAppId: string
  adzunaApiKey: string
  adzunaCountry: string
  cvPrompt: string
  clPrompt: string
  cvLanguage: string
  clLanguage: string
}

export const DEFAULT_CONFIG: AppConfig = {
  llmProvider: 'ollama',
  llmApiKey: '',
  llmModel: 'llama3.2',
  llmBaseUrl: 'http://localhost:11434/v1',
  llmTemperature: 0,
  adzunaAppId: '',
  adzunaApiKey: '',
  adzunaCountry: 'de',
  cvPrompt: '',
  clPrompt: '',
  cvLanguage: 'English',
  clLanguage: 'English',
}

async function getStore() {
  return load('config.json', { autoSave: true })
}

export async function loadConfig(): Promise<AppConfig> {
  const store = await getStore()
  const result: Partial<AppConfig> = {}
  for (const key of Object.keys(DEFAULT_CONFIG) as (keyof AppConfig)[]) {
    const val = await store.get<AppConfig[typeof key]>(key)
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    ;(result as any)[key] = val ?? DEFAULT_CONFIG[key]
  }
  return result as AppConfig
}

export async function saveConfig(cfg: AppConfig): Promise<void> {
  const store = await getStore()
  for (const [key, val] of Object.entries(cfg)) {
    await store.set(key, val)
  }
  await store.save()
}

export function configIsComplete(cfg: AppConfig): boolean {
  const needsApiKey = cfg.llmProvider === 'openai' || cfg.llmProvider === 'groq' || cfg.llmProvider === 'mistral'
  if (needsApiKey && !cfg.llmApiKey) return false
  return true
}
```

- [ ] **Step 2: Update `frontend/src/api/client.ts`**

Change `BASE`, add `updateConfig()`, change `ApplicationPackage`, add `openCvPreview()`, change `getMasterResumeHtml()`:

```typescript
// Replace the top of client.ts:
import { invoke } from '@tauri-apps/api/core'

const BASE = import.meta.env.VITE_API_BASE ?? '/api'
```

Add `updateConfig` function (after `getLLMConfig`):

```typescript
export interface ConfigUpdatePayload {
  llm_provider: string
  llm_model: string
  llm_base_url?: string
  llm_api_key?: string
  llm_temperature: number
  adzuna_app_id?: string
  adzuna_api_key?: string
  adzuna_country: string
  search_provider: string
  cv_prompt?: string
  cl_prompt?: string
  cv_language: string
  cl_language: string
}

export async function updateConfig(payload: ConfigUpdatePayload): Promise<void> {
  await request<{ ok: boolean }>('/config/update', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}
```

Replace `ApplicationPackage` interface:

```typescript
export interface ApplicationPackage {
  job_id: string
  resume_html: string
  cover_letter_html: string
  cover_letter_text: string
}
```

Replace `downloadMasterResume` with `getMasterResumeHtml`:

```typescript
export async function getMasterResumeHtml(): Promise<string> {
  const data = await request<{ html: string }>('/application/master-resume')
  return data.html
}
```

Add `openCvPreview` Tauri command wrapper at the bottom:

```typescript
export async function openCvPreview(html: string): Promise<void> {
  await invoke('open_cv_preview', { html })
}
```

- [ ] **Step 3: Update `frontend/src/components/ApplicationGenerator.tsx`**

Replace the entire file with NeuGlass-styled version that opens Tauri windows:

```typescript
// frontend/src/components/ApplicationGenerator.tsx
import { useState } from 'react'
import { generateApplication, openCvPreview, type JobPosting, type MatchScore, type ApplicationPackage } from '../api/client'

interface Props {
  job: JobPosting
  match: MatchScore
}

const BTN: React.CSSProperties = {
  padding: '7px 16px',
  background: 'var(--blue-primary)',
  color: 'white',
  border: 'none',
  borderRadius: 10,
  fontWeight: 700,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
}

const BTN_GHOST: React.CSSProperties = {
  padding: '7px 16px',
  background: 'var(--neumo-bg)',
  color: 'var(--neumo-text)',
  border: 'none',
  borderRadius: 10,
  fontWeight: 700,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
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

  if (pkg) {
    return (
      <div style={{ marginTop: 12, padding: '12px 14px', borderRadius: 12, background: 'var(--neumo-bg)', boxShadow: 'var(--neumo-raised-sm)' }}>
        <p style={{ margin: '0 0 10px', fontSize: 12, color: 'var(--neumo-text)', fontWeight: 700 }}>
          Application package ready
        </p>
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' as const, marginBottom: 10 }}>
          <button
            onClick={() => openCvPreview(pkg.resume_html)}
            style={BTN}
            onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            Preview Resume (Ctrl+P to save PDF)
          </button>
          <button
            onClick={() => openCvPreview(pkg.cover_letter_html)}
            style={{ ...BTN, background: 'var(--color-success)' }}
            onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            Preview Cover Letter (Ctrl+P to save PDF)
          </button>
          <button
            onClick={() => setShowLetter(v => !v)}
            style={BTN_GHOST}
            onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            {showLetter ? 'Hide' : 'Preview'} letter text
          </button>
        </div>
        {showLetter && (
          <pre style={{ margin: 0, fontSize: 12, color: 'var(--neumo-text)', background: 'rgba(0,0,0,0.04)', padding: '10px 12px', borderRadius: 6, whiteSpace: 'pre-wrap' as const, lineHeight: 1.6 }}>
            {pkg.cover_letter_text}
          </pre>
        )}
      </div>
    )
  }

  return (
    <div style={{ marginTop: 10 }}>
      {error && <p style={{ fontSize: 12, color: 'var(--color-error)', margin: '0 0 6px' }}>{error}</p>}
      <button
        onClick={handleGenerate}
        disabled={loading}
        style={{ ...BTN, opacity: loading ? 0.6 : 1, cursor: loading ? 'not-allowed' : 'pointer' }}
        onMouseDown={e => { if (!loading) e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
        onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
        onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
      >
        {loading ? 'Generating…' : 'Generate Application Package'}
      </button>
      {loading && (
        <p style={{ fontSize: 11, color: 'var(--neumo-text-s)', marginTop: 4 }}>
          Writing tailored resume + cover letter with AI — takes 2-5min
        </p>
      )}
    </div>
  )
}
```

- [ ] **Step 4: Create `frontend/src/components/SettingsButton.tsx`**

```typescript
// frontend/src/components/SettingsButton.tsx
import React from 'react'

interface Props {
  onClick: () => void
  label?: string
}

export function SettingsButton({ onClick, label }: Props) {
  return (
    <button
      onClick={onClick}
      title="Settings"
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 6,
        padding: '6px 14px',
        background: 'var(--neumo-bg)',
        color: 'var(--neumo-text-s)',
        border: 'none',
        borderRadius: 10,
        cursor: 'pointer',
        fontSize: 13,
        fontWeight: 600,
        boxShadow: 'var(--neumo-raised-sm)',
      }}
      onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
      onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
      onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
    >
      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
        <circle cx="12" cy="12" r="3"/>
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
      </svg>
      {label && <span>{label}</span>}
    </button>
  )
}
```

- [ ] **Step 5: Create `frontend/src/pages/SettingsPage.tsx`**

```typescript
// frontend/src/pages/SettingsPage.tsx
import { useEffect, useState } from 'react'
import { loadConfig, saveConfig, DEFAULT_CONFIG, type AppConfig, type LLMProvider } from '../store/appConfig'
import { updateConfig } from '../api/client'

interface Props {
  onBack: () => void
}

const PAGE_BG: React.CSSProperties = {
  background: 'var(--blue-gradient)',
  minHeight: '100svh',
  padding: '32px 24px',
  colorScheme: 'light' as const,
  overflowY: 'auto' as const,
}

const NEUMO_PANEL: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '24px 28px',
  marginBottom: 20,
}

const NEUMO_INSET: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-inset)',
  border: 'none',
  borderRadius: 10,
  padding: '9px 14px',
  fontSize: 14,
  color: 'var(--neumo-text)',
  width: '100%',
  boxSizing: 'border-box' as const,
  fontFamily: 'inherit',
}

const SECTION_TITLE: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 800,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.8px',
  color: 'var(--blue-primary)',
  borderBottom: '2px solid var(--blue-border)',
  paddingBottom: 6,
  marginBottom: 16,
  marginTop: 0,
}

const LABEL: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--neumo-text-s)',
  marginBottom: 4,
  display: 'block',
}

const FIELD: React.CSSProperties = { marginBottom: 14 }

const HELP_LINK: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--blue-primary)',
  marginTop: 4,
  display: 'block',
}

const BTN_PRIMARY: React.CSSProperties = {
  padding: '10px 24px',
  background: 'var(--blue-primary)',
  color: 'white',
  border: 'none',
  borderRadius: 10,
  fontWeight: 700,
  cursor: 'pointer',
  fontSize: 14,
  boxShadow: 'var(--neumo-raised-sm)',
}

const BTN_GHOST: React.CSSProperties = {
  padding: '10px 20px',
  background: 'var(--neumo-bg)',
  color: 'var(--neumo-text)',
  border: 'none',
  borderRadius: 10,
  fontWeight: 700,
  cursor: 'pointer',
  fontSize: 14,
  boxShadow: 'var(--neumo-raised-sm)',
}

const PROVIDER_LINKS: Record<LLMProvider, { label: string; url: string }> = {
  openai: { label: 'Get API key at platform.openai.com', url: 'https://platform.openai.com/api-keys' },
  ollama: { label: 'Download Ollama at ollama.ai', url: 'https://ollama.ai' },
  lmstudio: { label: 'Download LM Studio at lmstudio.ai', url: 'https://lmstudio.ai' },
  groq: { label: 'Get API key at console.groq.com', url: 'https://console.groq.com/keys' },
  mistral: { label: 'Get API key at console.mistral.ai', url: 'https://console.mistral.ai/api-keys' },
  compatible: { label: 'Any OpenAI-compatible endpoint', url: 'https://platform.openai.com/docs/api-reference' },
}

const PROVIDER_DEFAULT_MODELS: Record<LLMProvider, string> = {
  openai: 'gpt-4o-mini',
  ollama: 'llama3.2',
  lmstudio: 'local-model',
  groq: 'llama-3.1-70b-versatile',
  mistral: 'mistral-small-latest',
  compatible: 'local-model',
}

const PROVIDER_DEFAULT_URLS: Record<LLMProvider, string> = {
  openai: '',
  ollama: 'http://localhost:11434/v1',
  lmstudio: 'http://localhost:1234/v1',
  groq: 'https://api.groq.com/openai/v1',
  mistral: 'https://api.mistral.ai/v1',
  compatible: 'http://localhost:8080/v1',
}

const LANGUAGES = [
  'English', 'Português', 'Deutsch', 'Español', 'Français', 'Italiano',
  'Nederlands', 'Polski', 'Svenska', 'Norsk', 'Dansk', 'Suomi',
  'Čeština', 'Magyar', 'Română', 'Slovenčina', 'Hrvatski', 'Srpski',
  'Türkçe', '日本語', '中文（简体）', '中文（繁體）', '한국어', 'العربية',
  'हिन्दी', 'Русский', 'Українська', 'Bahasa Indonesia', 'Bahasa Melayu', 'Tiếng Việt',
]

const ADZUNA_COUNTRIES = [
  { code: 'de', label: 'Germany (DE)' },
  { code: 'gb', label: 'United Kingdom (GB)' },
  { code: 'us', label: 'United States (US)' },
  { code: 'au', label: 'Australia (AU)' },
  { code: 'ca', label: 'Canada (CA)' },
  { code: 'at', label: 'Austria (AT)' },
  { code: 'be', label: 'Belgium (BE)' },
  { code: 'br', label: 'Brazil (BR)' },
  { code: 'fr', label: 'France (FR)' },
  { code: 'in', label: 'India (IN)' },
  { code: 'it', label: 'Italy (IT)' },
  { code: 'mx', label: 'Mexico (MX)' },
  { code: 'nl', label: 'Netherlands (NL)' },
  { code: 'nz', label: 'New Zealand (NZ)' },
  { code: 'pl', label: 'Poland (PL)' },
  { code: 'ru', label: 'Russia (RU)' },
  { code: 'sg', label: 'Singapore (SG)' },
  { code: 'za', label: 'South Africa (ZA)' },
]

export function SettingsPage({ onBack }: Props) {
  const [cfg, setCfg] = useState<AppConfig>(DEFAULT_CONFIG)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    loadConfig().then(setCfg)
  }, [])

  function set<K extends keyof AppConfig>(key: K, value: AppConfig[K]) {
    setCfg(prev => ({ ...prev, [key]: value }))
  }

  function handleProviderChange(provider: LLMProvider) {
    setCfg(prev => ({
      ...prev,
      llmProvider: provider,
      llmModel: PROVIDER_DEFAULT_MODELS[provider],
      llmBaseUrl: PROVIDER_DEFAULT_URLS[provider],
    }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await saveConfig(cfg)
      await updateConfig({
        llm_provider: cfg.llmProvider === 'ollama' || cfg.llmProvider === 'lmstudio' || cfg.llmProvider === 'compatible' ? 'local' : cfg.llmProvider,
        llm_model: cfg.llmModel,
        llm_base_url: cfg.llmBaseUrl || undefined,
        llm_api_key: cfg.llmApiKey || undefined,
        llm_temperature: cfg.llmTemperature,
        adzuna_app_id: cfg.adzunaAppId || undefined,
        adzuna_api_key: cfg.adzunaApiKey || undefined,
        adzuna_country: cfg.adzunaCountry,
        search_provider: cfg.adzunaAppId && cfg.adzunaApiKey ? 'adzuna' : 'mock',
        cv_prompt: cfg.cvPrompt || undefined,
        cl_prompt: cfg.clPrompt || undefined,
        cv_language: cfg.cvLanguage,
        cl_language: cfg.clLanguage,
      })
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const providerLink = PROVIDER_LINKS[cfg.llmProvider]
  const needsApiKey = cfg.llmProvider === 'openai' || cfg.llmProvider === 'groq' || cfg.llmProvider === 'mistral'
  const needsUrl = cfg.llmProvider !== 'openai'

  return (
    <div style={PAGE_BG}>
      <div style={{ maxWidth: 680, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
          <button
            onClick={onBack}
            style={BTN_GHOST}
            onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            ← Back
          </button>
          <h1 style={{ margin: 0, fontSize: 22, color: 'var(--neumo-text)', fontWeight: 700 }}>Settings</h1>
        </div>

        {/* LLM Provider */}
        <div style={NEUMO_PANEL}>
          <p style={SECTION_TITLE}>LLM Provider</p>
          <div style={FIELD}>
            <label style={LABEL}>Provider</label>
            <select
              value={cfg.llmProvider}
              onChange={e => handleProviderChange(e.target.value as LLMProvider)}
              style={NEUMO_INSET}
            >
              <option value="ollama">Ollama (local)</option>
              <option value="lmstudio">LM Studio (local)</option>
              <option value="openai">OpenAI</option>
              <option value="groq">Groq</option>
              <option value="mistral">Mistral</option>
              <option value="compatible">OpenAI-compatible</option>
            </select>
            <a href={providerLink.url} target="_blank" rel="noreferrer" style={HELP_LINK}>
              ↗ {providerLink.label}
            </a>
          </div>
          {needsApiKey && (
            <div style={FIELD}>
              <label style={LABEL}>API Key</label>
              <input
                type="password"
                value={cfg.llmApiKey}
                onChange={e => set('llmApiKey', e.target.value)}
                placeholder="sk-..."
                style={NEUMO_INSET}
              />
            </div>
          )}
          {needsUrl && (
            <div style={FIELD}>
              <label style={LABEL}>Base URL</label>
              <input
                type="text"
                value={cfg.llmBaseUrl}
                onChange={e => set('llmBaseUrl', e.target.value)}
                placeholder="http://localhost:11434/v1"
                style={NEUMO_INSET}
              />
            </div>
          )}
          <div style={FIELD}>
            <label style={LABEL}>Model</label>
            <input
              type="text"
              value={cfg.llmModel}
              onChange={e => set('llmModel', e.target.value)}
              placeholder="llama3.2"
              style={NEUMO_INSET}
            />
          </div>
        </div>

        {/* Adzuna */}
        <div style={NEUMO_PANEL}>
          <p style={SECTION_TITLE}>Job Search — Adzuna</p>
          <div style={FIELD}>
            <label style={LABEL}>App ID</label>
            <input type="text" value={cfg.adzunaAppId} onChange={e => set('adzunaAppId', e.target.value)} style={NEUMO_INSET} placeholder="xxxxxxxx" />
          </div>
          <div style={FIELD}>
            <label style={LABEL}>API Key</label>
            <input type="password" value={cfg.adzunaApiKey} onChange={e => set('adzunaApiKey', e.target.value)} style={NEUMO_INSET} placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" />
          </div>
          <div style={FIELD}>
            <label style={LABEL}>Country</label>
            <select value={cfg.adzunaCountry} onChange={e => set('adzunaCountry', e.target.value)} style={NEUMO_INSET}>
              {ADZUNA_COUNTRIES.map(c => (
                <option key={c.code} value={c.code}>{c.label}</option>
              ))}
            </select>
          </div>
          <a href="https://developer.adzuna.com/overview" target="_blank" rel="noreferrer" style={HELP_LINK}>
            ↗ Create Adzuna API key at developer.adzuna.com
          </a>
        </div>

        {/* Prompts */}
        <div style={NEUMO_PANEL}>
          <p style={SECTION_TITLE}>Default Prompts</p>
          <div style={FIELD}>
            <label style={LABEL}>CV / Resume Prompt</label>
            <p style={{ fontSize: 11, color: 'var(--neumo-text-s)', margin: '0 0 8px' }}>
              Use <code style={{ background: 'rgba(0,0,0,0.07)', padding: '1px 4px', borderRadius: 3 }}>{'{JOB_DESCRIPTION}'}</code> as placeholder for the job posting.
              Leave empty to use the built-in default.
            </p>
            <textarea
              value={cfg.cvPrompt}
              onChange={e => set('cvPrompt', e.target.value)}
              placeholder="Leave empty to use built-in default prompt..."
              rows={6}
              style={{ ...NEUMO_INSET, resize: 'vertical' as const, lineHeight: 1.5 }}
            />
          </div>
          <div style={FIELD}>
            <label style={LABEL}>Cover Letter Prompt</label>
            <textarea
              value={cfg.clPrompt}
              onChange={e => set('clPrompt', e.target.value)}
              placeholder="Leave empty to use built-in default prompt..."
              rows={6}
              style={{ ...NEUMO_INSET, resize: 'vertical' as const, lineHeight: 1.5 }}
            />
          </div>
        </div>

        {/* Language */}
        <div style={NEUMO_PANEL}>
          <p style={SECTION_TITLE}>Output Language</p>
          <p style={{ fontSize: 12, color: 'var(--neumo-text-s)', marginTop: 0, marginBottom: 16 }}>
            The LLM will generate the CV and cover letter in the selected language.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div style={FIELD}>
              <label style={LABEL}>CV / Resume Language</label>
              <select value={cfg.cvLanguage} onChange={e => set('cvLanguage', e.target.value)} style={NEUMO_INSET}>
                {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div style={FIELD}>
              <label style={LABEL}>Cover Letter Language</label>
              <select value={cfg.clLanguage} onChange={e => set('clLanguage', e.target.value)} style={NEUMO_INSET}>
                {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>
        </div>

        {/* Save */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{ ...BTN_PRIMARY, opacity: saving ? 0.7 : 1 }}
            onMouseDown={e => { if (!saving) e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
          {saved && <span style={{ fontSize: 13, color: 'var(--color-success)', fontWeight: 600 }}>✓ Saved</span>}
        </div>

      </div>
    </div>
  )
}
```

- [ ] **Step 6: Update `frontend/src/App.tsx`**

```typescript
// frontend/src/App.tsx
import { useCallback, useEffect, useRef, useState } from 'react'
import { getProfile, getAutoSearchSummary, updateConfig, type ProfileMaster } from './api/client'
import { loadConfig, configIsComplete } from './store/appConfig'
import { IngestPage } from './pages/IngestPage'
import { JobSearchPage } from './pages/JobSearchPage'
import { AutoSearchPage } from './pages/AutoSearchPage'
import { ProfilePage } from './pages/ProfilePage'
import { SettingsPage } from './pages/SettingsPage'

type AppState = 'loading' | 'no_profile' | 'has_profile' | 'job_search' | 'auto_search' | 'settings'

export default function App() {
  const [appState, setAppState] = useState<AppState>('loading')
  const [profile, setProfile] = useState<ProfileMaster | null>(null)
  const [autoSearchBadge, setAutoSearchBadge] = useState(0)
  const [configComplete, setConfigComplete] = useState(true)
  const prevStateRef = useRef<AppState>('loading')

  // Push stored config to backend on startup
  useEffect(() => {
    async function bootConfig() {
      try {
        const cfg = await loadConfig()
        setConfigComplete(configIsComplete(cfg))
        await updateConfig({
          llm_provider: cfg.llmProvider === 'ollama' || cfg.llmProvider === 'lmstudio' || cfg.llmProvider === 'compatible' ? 'local' : cfg.llmProvider,
          llm_model: cfg.llmModel,
          llm_base_url: cfg.llmBaseUrl || undefined,
          llm_api_key: cfg.llmApiKey || undefined,
          llm_temperature: cfg.llmTemperature,
          adzuna_app_id: cfg.adzunaAppId || undefined,
          adzuna_api_key: cfg.adzunaApiKey || undefined,
          adzuna_country: cfg.adzunaCountry,
          search_provider: cfg.adzunaAppId && cfg.adzunaApiKey ? 'adzuna' : 'mock',
          cv_prompt: cfg.cvPrompt || undefined,
          cl_prompt: cfg.clPrompt || undefined,
          cv_language: cfg.cvLanguage,
          cl_language: cfg.clLanguage,
        })
      } catch {
        // Backend not yet ready — ignore (sidecar may still be starting)
      }
    }
    bootConfig()
  }, [])

  useEffect(() => {
    async function checkSummary() {
      try {
        const summary = await getAutoSearchSummary()
        setAutoSearchBadge(summary.new_count)
      } catch { /* silently ignore */ }
    }
    checkSummary()
    const id = setInterval(checkSummary, 60_000)
    return () => clearInterval(id)
  }, [])

  function handleAutoSearch() {
    setAutoSearchBadge(0)
    setAppState('auto_search')
  }

  const loadProfile = useCallback(() => {
    return getProfile().then(p => { setProfile(p); setAppState('has_profile') })
  }, [])

  useEffect(() => {
    loadProfile().catch(() => setAppState('no_profile'))
  }, [loadProfile])

  function goToSettings() {
    prevStateRef.current = appState
    setAppState('settings')
  }

  function backFromSettings() {
    // After saving config, re-check completeness
    loadConfig().then(cfg => setConfigComplete(configIsComplete(cfg)))
    setAppState(prevStateRef.current === 'settings' ? 'no_profile' : prevStateRef.current)
  }

  if (appState === 'settings') {
    return <SettingsPage onBack={backFromSettings} />
  }

  if (appState === 'loading') {
    return <p style={{ padding: 32, color: 'var(--neumo-text)' }}>Loading…</p>
  }

  if (appState === 'no_profile') {
    return <IngestPage onProfileReady={() => loadProfile()} onOpenSettings={goToSettings} configComplete={configComplete} />
  }

  if (appState === 'job_search') {
    return (
      <JobSearchPage
        onBack={() => setAppState('has_profile')}
        suggestions={profile?.job_suggestions ?? []}
      />
    )
  }

  if (appState === 'auto_search') {
    return <AutoSearchPage onBack={() => setAppState('has_profile')} />
  }

  return profile ? (
    <ProfilePage
      profile={profile}
      onSearchJobs={() => setAppState('job_search')}
      onAutoSearch={handleAutoSearch}
      onReimport={() => setAppState('no_profile')}
      onProfileUpdated={p => setProfile(p)}
      autoSearchBadge={autoSearchBadge}
      onOpenSettings={goToSettings}
    />
  ) : null
}
```

- [ ] **Step 7: Update `frontend/src/pages/IngestPage.tsx`**

Add `onOpenSettings` and `configComplete` props. Add warning banner when config is incomplete:

```typescript
// frontend/src/pages/IngestPage.tsx
import { useState } from 'react'
import { ResumeUpload } from '../components/ResumeUpload'
import { HITLForm } from '../components/HITLForm'
import { SettingsButton } from '../components/SettingsButton'
import { type IngestionResponse } from '../api/client'

interface Props {
  onProfileReady: () => void
  onOpenSettings: () => void
  configComplete: boolean
}

const PAGE_BG: React.CSSProperties = {
  background: 'var(--blue-gradient)',
  minHeight: '100svh',
  display: 'flex',
  alignItems: 'center',
  justifyContent: 'center',
  padding: '32px 24px',
  colorScheme: 'light' as const,
}

const NEUMO_PANEL: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '28px 32px',
  width: '100%',
  maxWidth: 520,
  boxSizing: 'border-box' as const,
}

const BTN_GHOST: React.CSSProperties = {
  padding: '8px 18px',
  background: 'var(--neumo-bg)',
  color: 'var(--neumo-text)',
  border: 'none',
  borderRadius: 10,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
}

export function IngestPage({ onProfileReady, onOpenSettings, configComplete }: Props) {
  const [ingestion, setIngestion] = useState<IngestionResponse | null>(null)

  function handleIngestionResult(response: IngestionResponse) {
    setIngestion(response)
    if (response.status === 'completed') {
      onProfileReady()
    }
  }

  if (ingestion?.status === 'failed') {
    return (
      <div style={PAGE_BG}>
        <div style={NEUMO_PANEL}>
          <h2 style={{ fontSize: 18, margin: '0 0 8px', color: 'var(--neumo-text)', fontWeight: 700 }}>Something went wrong</h2>
          <p style={{ color: 'var(--color-error)', fontSize: 14, margin: '0 0 16px', lineHeight: 1.5 }}>{ingestion.error}</p>
          <button
            onClick={() => setIngestion(null)}
            style={BTN_GHOST}
            onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            Try again
          </button>
        </div>
      </div>
    )
  }

  if (ingestion?.status === 'hitl_required' && ingestion.hitl_request) {
    return (
      <div style={PAGE_BG}>
        <div style={{ ...NEUMO_PANEL, maxWidth: 640 }}>
          <HITLForm
            request={ingestion.hitl_request}
            onResolved={handleIngestionResult}
          />
        </div>
      </div>
    )
  }

  return (
    <div style={PAGE_BG}>
      <div style={NEUMO_PANEL}>
        {!configComplete && (
          <div style={{
            background: 'rgba(245,158,11,0.12)',
            border: '1px solid var(--color-warning)',
            borderRadius: 10,
            padding: '10px 14px',
            marginBottom: 20,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'space-between',
            gap: 12,
          }}>
            <span style={{ fontSize: 13, color: 'var(--neumo-text)', fontWeight: 600 }}>
              ⚠️ Configure LLM before uploading
            </span>
            <SettingsButton onClick={onOpenSettings} label="Configure" />
          </div>
        )}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 8 }}>
          <h1 style={{ fontSize: 22, margin: 0, color: 'var(--neumo-text)', fontWeight: 700 }}>Import your resume</h1>
          <SettingsButton onClick={onOpenSettings} />
        </div>
        <p style={{ color: 'var(--neumo-text-s)', fontSize: 14, margin: '0 0 24px', lineHeight: 1.6 }}>
          Your resume will be parsed and structured using the Google XYZ formula.
          Metrics that are missing will be flagged for your review — we never invent numbers.
        </p>
        <ResumeUpload onCompleted={handleIngestionResult} />
      </div>
    </div>
  )
}
```

- [ ] **Step 8: Update `frontend/src/pages/ProfilePage.tsx`**

Add `onOpenSettings` prop. In the glass ActionBar, add `<SettingsButton onClick={onOpenSettings} />` to the right side. Replace `downloadMasterResume` with `getMasterResumeHtml` + `openCvPreview`.

Find the `ProfilePage` component Props interface and add:

```typescript
interface Props {
  // ... existing props ...
  onOpenSettings: () => void
}
```

In the ActionBar JSX, add SettingsButton import and the button at the right of the bar:

```typescript
import { SettingsButton } from '../components/SettingsButton'
import { getMasterResumeHtml, openCvPreview, /* existing imports */ } from '../api/client'
```

Find `downloadMasterResume` usage (around line 250) and replace:

```typescript
// Before:
const blob = await downloadMasterResume()
const url = URL.createObjectURL(blob)
const a = document.createElement('a')
a.href = url
a.download = `${profile.contact.full_name.replace(/ /g, '_')}_MasterResume.pdf`
a.click()
URL.revokeObjectURL(url)

// After:
const html = await getMasterResumeHtml()
await openCvPreview(html)
```

Find the button label "Download Resume PDF" and change to "Preview Master Resume":

```typescript
// Before:
{downloading ? 'Generating…' : 'Download Resume PDF'}

// After:
{downloading ? 'Generating…' : 'Preview Master Resume'}
```

In the ActionBar `<div>`, add `<SettingsButton onClick={onOpenSettings} />` at the right end.

- [ ] **Step 9: Run TypeScript check**

```bash
cd frontend
npx tsc --noEmit
```

Expected: 0 errors. Fix any type errors that arise (most common: missing props, wrong types on the new `ApplicationPackage`).

- [ ] **Step 10: Commit**

```bash
git add frontend/src/store/appConfig.ts \
        frontend/src/pages/SettingsPage.tsx \
        frontend/src/components/SettingsButton.tsx \
        frontend/src/api/client.ts \
        frontend/src/components/ApplicationGenerator.tsx \
        frontend/src/pages/ProfilePage.tsx \
        frontend/src/pages/IngestPage.tsx \
        frontend/src/App.tsx \
        frontend/package.json \
        frontend/pnpm-lock.yaml
git commit -m "feat: frontend — Tauri Store config, SettingsPage, ApplicationGenerator Tauri windows"
```

---

### Task 4: PyInstaller Spec + GitHub Actions + Delete Docker Files

**Files:**
- Create: `backend/run.py`
- Create: `backend/backend.spec`
- Create: `.github/workflows/release.yml`
- Delete: `docker-compose.yml`
- Delete: `backend/Dockerfile`

**Interfaces:**
- Produces: `pyinstaller backend/backend.spec` → `backend/dist/job-hunter-backend[.exe]` single-file binary
- Produces: GitHub release on `v*.*.*` tag with `.msi`, `.AppImage`, `.dmg` artifacts
- Consumes: Tauri sidecar config from Task 2 (`bundle.externalBin: ["binaries/job-hunter-backend"]`)

- [ ] **Step 1: Create `backend/run.py`**

```python
# backend/run.py
"""
PyInstaller entry point.
Runs the FastAPI backend as a subprocess-friendly uvicorn server.
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, log_level="warning")
```

- [ ] **Step 2: Create `backend/backend.spec`**

```python
# backend/backend.spec
# -*- mode: python ; coding: utf-8 -*-
import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    ['run.py'],
    pathex=[str(Path.cwd())],
    binaries=[],
    datas=[],
    hiddenimports=[
        # uvicorn internals
        'uvicorn.logging',
        'uvicorn.loops',
        'uvicorn.loops.auto',
        'uvicorn.loops.asyncio',
        'uvicorn.protocols',
        'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto',
        'uvicorn.protocols.http.h11_impl',
        'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto',
        'uvicorn.lifespan',
        'uvicorn.lifespan.on',
        # FastAPI / pydantic
        'fastapi',
        'pydantic',
        'pydantic_settings',
        # Schedulers
        'apscheduler',
        'apscheduler.schedulers',
        'apscheduler.schedulers.background',
        'apscheduler.executors',
        'apscheduler.executors.pool',
        'apscheduler.jobstores',
        'apscheduler.jobstores.memory',
        'apscheduler.triggers',
        'apscheduler.triggers.interval',
        # PDF / document parsing
        'pdfplumber',
        'pdfminer',
        'pdfminer.high_level',
        'reportlab',
        'reportlab.platypus',
        'reportlab.lib',
        'reportlab.lib.pagesizes',
        'docx',
        # HTML parsing
        'bs4',
        'lxml',
        'lxml.etree',
        'lxml._elementpath',
        # HTTP
        'httpx',
        'httpcore',
        # Multipart
        'multipart',
        'python_multipart',
        # jobspy
        'jobspy',
    ],
    excludes=[
        'playwright',
        'pytest',
        'tests',
        'tkinter',
        '_tkinter',
        'matplotlib',
        'numpy',
        'pandas',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='job-hunter-backend',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,   # True so uvicorn logs appear during dev; set False for production
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    onefile=True,
)
```

- [ ] **Step 3: Test PyInstaller locally**

```bash
cd backend
pip install pyinstaller
pyinstaller backend.spec
# Creates dist/job-hunter-backend[.exe]
```

Run the binary to verify it starts:

```bash
# Linux/Mac:
./dist/job-hunter-backend &
sleep 3
curl http://localhost:8000/health
# Expected: {"status":"ok","version":"0.1.0"}
kill %1

# Windows:
Start-Process .\dist\job-hunter-backend.exe
Start-Sleep 3
Invoke-WebRequest http://localhost:8000/health
Stop-Process -Name "job-hunter-backend"
```

If binary fails to start, add missing modules to `hiddenimports` in the spec. Common missing imports to add: any module that FastAPI's import machinery finds via string-based imports at runtime.

- [ ] **Step 4: Copy sidecar to Tauri binaries dir for local testing**

```bash
# Linux/Mac:
mkdir -p src-tauri/binaries
TARGET=$(rustc -vV | grep 'host:' | awk '{print $2}')
cp backend/dist/job-hunter-backend src-tauri/binaries/job-hunter-backend-$TARGET

# Windows PowerShell:
$TARGET = (rustc -vV | Select-String 'host:').ToString().Split(' ')[1].Trim()
New-Item -ItemType Directory -Force src-tauri/binaries
Copy-Item backend\dist\job-hunter-backend.exe "src-tauri\binaries\job-hunter-backend-$TARGET.exe"
```

- [ ] **Step 5: Test full Tauri app with sidecar**

```bash
cd frontend
pnpm tauri dev
```

Expected: app opens. Backend should start automatically (no "Sidecar not found" log). `http://localhost:8000/health` should respond. Upload a resume to test end-to-end flow.

- [ ] **Step 6: Create `.github/workflows/release.yml`**

```yaml
# .github/workflows/release.yml
name: Release

on:
  push:
    tags:
      - 'v*.*.*'

jobs:
  release:
    permissions:
      contents: write
    strategy:
      fail-fast: false
      matrix:
        include:
          - platform: ubuntu-22.04
            target: x86_64-unknown-linux-gnu
            sidecar-name: job-hunter-backend
            sidecar-ext: ''
          - platform: windows-latest
            target: x86_64-pc-windows-msvc
            sidecar-name: job-hunter-backend
            sidecar-ext: '.exe'
          - platform: macos-latest
            target: aarch64-apple-darwin
            sidecar-name: job-hunter-backend
            sidecar-ext: ''

    runs-on: ${{ matrix.platform }}

    steps:
      - uses: actions/checkout@v4

      # ── Python + PyInstaller ──────────────────────────────────────────────
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install Python dependencies + PyInstaller
        run: pip install -r backend/requirements.txt pyinstaller

      - name: Build Python sidecar
        working-directory: backend
        run: pyinstaller backend.spec

      - name: Stage sidecar for Tauri
        shell: bash
        run: |
          mkdir -p src-tauri/binaries
          cp "backend/dist/${{ matrix.sidecar-name }}${{ matrix.sidecar-ext }}" \
             "src-tauri/binaries/${{ matrix.sidecar-name }}-${{ matrix.target }}${{ matrix.sidecar-ext }}"

      # ── Node + pnpm ───────────────────────────────────────────────────────
      - uses: pnpm/action-setup@v4
        with:
          version: 9

      - uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'pnpm'
          cache-dependency-path: frontend/pnpm-lock.yaml

      - name: Install frontend dependencies
        working-directory: frontend
        run: pnpm install

      # ── Rust ─────────────────────────────────────────────────────────────
      - uses: dtolnay/rust-toolchain@stable
        with:
          targets: ${{ matrix.target }}

      # ── Linux system deps ─────────────────────────────────────────────────
      - name: Install Linux system dependencies
        if: matrix.platform == 'ubuntu-22.04'
        run: |
          sudo apt-get update
          sudo apt-get install -y libwebkit2gtk-4.1-dev libappindicator3-dev \
            librsvg2-dev patchelf libgtk-3-dev libsoup-3.0-dev

      # ── Tauri build + release ─────────────────────────────────────────────
      - uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          VITE_API_BASE: 'http://localhost:8000'
        with:
          tagName: ${{ github.ref_name }}
          releaseName: 'Job Hunter Assistant ${{ github.ref_name }}'
          releaseBody: |
            ## What's New
            See [CHANGELOG](https://github.com/${{ github.repository }}/blob/main/CHANGELOG.md) for details.

            ## Downloads
            - **Windows**: `.msi` installer
            - **Linux**: `.AppImage` (portable) or `.deb`
            - **macOS**: `.dmg`
          releaseDraft: true
          prerelease: false
          projectPath: '.'
          tauriScript: 'pnpm tauri'
          args: '--target ${{ matrix.target }}'
```

- [ ] **Step 7: Delete Docker files**

```bash
git rm docker-compose.yml backend/Dockerfile
```

- [ ] **Step 8: Commit**

```bash
git add backend/run.py backend/backend.spec .github/workflows/release.yml
git commit -m "feat: PyInstaller spec, GitHub Actions release pipeline, remove Docker"
```

---

### Task 5: Landing Page

**Files:**
- Create: `landing/index.html`

**Interfaces:**
- Produces: `landing/index.html` served by GitHub Pages from `main` branch `/landing` folder
- Links point to `https://github.com/melkyfb/job-hunter/releases/latest`

- [ ] **Step 1: Create `landing/index.html`**

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Job Hunter Assistant — AI-powered job application tool</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }

    :root {
      --blue: #1E4D9E;
      --blue-dark: #163d80;
      --blue-light: #EBF1FB;
      --bg: #dde4f0;
      --border: #C3D4EF;
      --text: #2d3a52;
      --text-s: #5a6a82;
    }

    body {
      font-family: system-ui, 'Segoe UI', Roboto, sans-serif;
      background: linear-gradient(135deg, #dde4f0 0%, #c8d8ee 55%, #d5dff0 100%);
      color: var(--text);
      min-height: 100vh;
    }

    .hero {
      text-align: center;
      padding: 80px 24px 60px;
    }

    .logo {
      display: inline-flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 24px;
    }

    .logo svg { width: 48px; height: 48px; }

    .logo-text {
      font-size: 28px;
      font-weight: 800;
      color: var(--blue);
      letter-spacing: -0.5px;
    }

    .tagline {
      font-size: 18px;
      color: var(--text-s);
      max-width: 520px;
      margin: 0 auto 16px;
      line-height: 1.6;
    }

    .sub {
      font-size: 14px;
      color: var(--text-s);
      margin-bottom: 48px;
    }

    .downloads {
      display: flex;
      gap: 14px;
      justify-content: center;
      flex-wrap: wrap;
      margin-bottom: 16px;
    }

    .dl-btn {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 13px 24px;
      background: var(--blue);
      color: white;
      text-decoration: none;
      border-radius: 12px;
      font-weight: 700;
      font-size: 15px;
      box-shadow: 6px 6px 16px rgba(163,177,198,0.5), -6px -6px 16px rgba(255,255,255,0.8);
      transition: background 0.15s, transform 0.1s;
    }

    .dl-btn:hover { background: var(--blue-dark); transform: translateY(-1px); }

    .dl-btn.secondary {
      background: #dde4f0;
      color: var(--blue);
      border: 1.5px solid var(--border);
    }

    .dl-btn.secondary:hover { background: #c8d8ee; }

    .version-note {
      font-size: 12px;
      color: var(--text-s);
      margin-bottom: 64px;
    }

    .features {
      display: grid;
      grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
      gap: 20px;
      max-width: 900px;
      margin: 0 auto;
      padding: 0 24px 80px;
    }

    .feature-card {
      background: #dde4f0;
      border-radius: 16px;
      padding: 28px 24px;
      box-shadow: 8px 8px 20px rgba(163,177,198,0.65), -8px -8px 20px rgba(255,255,255,0.85);
      text-align: left;
    }

    .feature-icon { font-size: 32px; margin-bottom: 12px; }

    .feature-title {
      font-size: 16px;
      font-weight: 700;
      color: var(--text);
      margin-bottom: 8px;
    }

    .feature-desc {
      font-size: 13px;
      color: var(--text-s);
      line-height: 1.6;
    }

    .footer {
      text-align: center;
      padding: 24px;
      border-top: 1px solid var(--border);
      font-size: 13px;
      color: var(--text-s);
    }

    .footer a { color: var(--blue); text-decoration: none; }
    .footer a:hover { text-decoration: underline; }
  </style>
</head>
<body>

  <div class="hero">
    <div class="logo">
      <svg viewBox="0 0 48 48" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect width="48" height="48" rx="12" fill="#1E4D9E"/>
        <path d="M12 34V16a2 2 0 012-2h20a2 2 0 012 2v18l-4-3-4 3-4-3-4 3-4-3-4 3z" fill="white" opacity="0.9"/>
        <rect x="17" y="20" width="14" height="2" rx="1" fill="#1E4D9E"/>
        <rect x="17" y="24" width="10" height="2" rx="1" fill="#1E4D9E"/>
        <rect x="17" y="28" width="7" height="2" rx="1" fill="#1E4D9E"/>
      </svg>
      <span class="logo-text">Job Hunter Assistant</span>
    </div>

    <p class="tagline">
      AI-powered job application tool. Tailored CVs and cover letters in seconds. Runs 100% on your machine.
    </p>

    <p class="sub">Your data never leaves your computer — no cloud, no subscriptions.</p>

    <div class="downloads">
      <a id="dl-windows" href="https://github.com/melkyfb/job-hunter/releases/latest" class="dl-btn">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M0 3.449L9.75 2.1v9.451H0m10.949-9.602L24 0v11.549H10.949M0 12.6h9.75v9.451L0 20.699M10.949 12.6H24V24l-12.9-1.801"/></svg>
        Download for Windows
      </a>
      <a id="dl-linux" href="https://github.com/melkyfb/job-hunter/releases/latest" class="dl-btn">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M12 0a12 12 0 100 24A12 12 0 0012 0zm0 2c5.514 0 10 4.486 10 10S17.514 22 12 22 2 17.514 2 12 6.486 2 12 2zm0 2a8 8 0 100 16A8 8 0 0012 4z"/></svg>
        Download for Linux
      </a>
      <a id="dl-mac" href="https://github.com/melkyfb/job-hunter/releases/latest" class="dl-btn secondary">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor"><path d="M18.71 19.5c-.83 1.24-1.71 2.45-3.05 2.47-1.34.03-1.77-.79-3.29-.79-1.53 0-2 .77-3.27.82-1.31.05-2.3-1.32-3.14-2.53C4.25 17 2.94 12.45 4.7 9.39c.87-1.52 2.43-2.48 4.12-2.51 1.28-.02 2.5.87 3.29.87.78 0 2.26-1.07 3.8-.91.65.03 2.47.26 3.64 1.98-.09.06-2.17 1.28-2.15 3.81.03 3.02 2.65 4.03 2.68 4.04-.03.07-.42 1.44-1.38 2.83M13 3.5c.73-.83 1.94-1.46 2.94-1.5.13 1.17-.34 2.35-1.04 3.19-.69.85-1.83 1.51-2.95 1.42-.15-1.15.41-2.35 1.05-3.11z"/></svg>
        Download for macOS
      </a>
    </div>

    <p class="version-note" id="version-note">
      Latest release — <a href="https://github.com/melkyfb/job-hunter/releases" style="color: var(--blue);">all versions</a>
    </p>
  </div>

  <div class="features">
    <div class="feature-card">
      <div class="feature-icon">🤖</div>
      <div class="feature-title">AI-Generated CVs</div>
      <div class="feature-desc">
        Upload your resume once. The LLM tailors a CV and cover letter for each job posting using the Google XYZ formula.
        Works with OpenAI, Ollama, LM Studio, Groq, Mistral, or any OpenAI-compatible endpoint.
      </div>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🔍</div>
      <div class="feature-title">Automated Job Search</div>
      <div class="feature-desc">
        Connects to Adzuna to find relevant jobs automatically. Scores each posting against your profile.
        Pipeline view to track applications from first contact to offer.
      </div>
    </div>
    <div class="feature-card">
      <div class="feature-icon">🔒</div>
      <div class="feature-title">100% Local</div>
      <div class="feature-desc">
        No cloud, no account, no subscription. Your resume, API keys, and application history stay on your machine.
        Use a local LLM (Ollama) and your data never leaves your computer.
      </div>
    </div>
  </div>

  <div class="footer">
    <p>
      <a href="https://github.com/melkyfb/job-hunter">GitHub</a> ·
      MIT License ·
      Built with Tauri, React, Python
    </p>
  </div>

  <script>
    // Attempt to get latest release version from GitHub API
    // Falls back to /releases/latest redirect (no JS required)
    fetch('https://api.github.com/repos/melkyfb/job-hunter/releases/latest')
      .then(r => r.json())
      .then(data => {
        const tag = data.tag_name
        if (!tag) return
        const assets = data.assets || []

        const find = (keyword) => {
          const a = assets.find(a => a.name.toLowerCase().includes(keyword))
          return a ? a.browser_download_url : null
        }

        const msi = find('.msi') || find('_x64_en-us.msi') || find('windows')
        const appimage = find('.appimage') || find('linux')
        const dmg = find('.dmg') || find('macos') || find('apple')

        if (msi) document.getElementById('dl-windows').href = msi
        if (appimage) document.getElementById('dl-linux').href = appimage
        if (dmg) document.getElementById('dl-mac').href = dmg

        document.getElementById('version-note').innerHTML =
          `Version ${tag} — <a href="https://github.com/melkyfb/job-hunter/releases" style="color: var(--blue);">all versions</a>`
      })
      .catch(() => { /* keep fallback links */ })
  </script>
</body>
</html>
```

- [ ] **Step 2: Verify locally**

Open `landing/index.html` directly in a browser:

```bash
# Linux/Mac:
open landing/index.html
# Windows:
start landing/index.html
```

Expected: landing page renders correctly with three download buttons, three feature cards, footer. Download links fall back to `/releases/latest` if the GitHub API call fails (no releases yet = expected).

- [ ] **Step 3: Commit**

```bash
git add landing/
git commit -m "feat: landing page for GitHub Pages"
```

---

## Self-Review

**Spec coverage check:**

| Spec requirement | Covered by |
|-----------------|-----------|
| Tauri 2.0 shell | Task 2 |
| Python sidecar (PyInstaller) | Tasks 1, 4 |
| No .env | Tasks 1 (backend reads from memory), 3 (Tauri Store) |
| POST /config/update | Task 1 Step 6 |
| DATA_DIR migration (3 files) | Task 1 Steps 2-4 |
| Remove Playwright | Task 1 Steps 11-12 |
| CV preview via Tauri window | Tasks 2, 3 |
| `open_cv_preview` Rust command | Task 2 Step 7 |
| `AppConfig` Tauri Store wrapper | Task 3 Step 1 |
| SettingsPage (6 providers, 30 languages, Adzuna, prompts) | Task 3 Step 5 |
| SettingsButton (two placements) | Tasks 3 Steps 4, 7, 8 |
| App.tsx config boot on mount | Task 3 Step 6 |
| IngestPage config-incomplete warning | Task 3 Step 7 |
| ProfilePage gear icon + master resume → HTML | Task 3 Step 8 |
| ApplicationGenerator → Tauri windows | Task 3 Step 3 |
| `ApplicationPackage` type change | Tasks 1, 3 |
| `master-resume` → HTML | Tasks 1, 3 |
| GitHub Actions (3 platforms, tag trigger) | Task 4 Step 6 |
| Delete Docker files | Task 4 Step 7 |
| Landing page (single HTML, 3 features, 3 download buttons) | Task 5 |
| Language dropdown 30 languages | Task 3 Step 5 (LANGUAGES array has exactly 30) |

**Type consistency check:**
- `ConfigUpdate` (Python, Task 1) ↔ `ConfigUpdatePayload` (TS, Task 3): field names use snake_case in Python, camelCase → snake_case mapping in `handleSave()` — consistent ✓
- `ApplicationPackage` Python model fields (`resume_html`, `cover_letter_html`, `cover_letter_text`) ↔ TS interface in Task 3 — consistent ✓
- `MasterResumeResponse.html` (Python) ↔ `getMasterResumeHtml()` returns `string` (TS) — consistent ✓
- `open_cv_preview` Rust command name ↔ `invoke('open_cv_preview', { html })` in TS — consistent ✓
- `onOpenSettings` prop added to both `IngestPage` and `ProfilePage`, consumed by `App.tsx` — consistent ✓
