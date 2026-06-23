# Tauri 2.0 Migration Design

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate Job Hunter Assistant from a Docker-based web app to a Tauri 2.0 desktop app with a bundled Python FastAPI sidecar, in-app config UI replacing `.env`, and GitHub Actions cross-platform release pipeline.

**Architecture:** Tauri 2.0 shell wraps the existing React frontend as a WebView and launches the existing Python FastAPI backend as a PyInstaller-compiled sidecar process. Config is stored in Tauri Store (app data dir) instead of `.env`. Playwright is removed; CV preview opens in a native Tauri window so the user saves PDF themselves.

**Tech Stack:** Tauri 2.0, Rust (minimal — sidecar launch + window management), React 19 + TypeScript (existing), Python 3.12 + FastAPI (existing), PyInstaller 6.x, `@tauri-apps/plugin-store`, GitHub Actions (`tauri-apps/tauri-action`)

---

## Global Constraints

- Tauri version: 2.0 (not v1)
- Python backend: keep as-is — no logic rewrite, only additions
- No `.env` files in the shipped app — all user config persists via Tauri Store
- No Docker files remain after migration (`docker-compose.yml`, `backend/Dockerfile` removed)
- Playwright dependency removed from `requirements.txt` and codebase
- CV preview: Tauri native window showing HTML, user saves PDF via OS print dialog
- PyInstaller produces a single-file binary per platform (onefile mode)
- GitHub Actions builds on `ubuntu-latest`, `windows-latest`, `macos-latest`
- Release trigger: git tag matching `v*.*.*`
- Landing page: single `landing/index.html`, no framework, no build step
- GitHub Pages source: `main` branch, `/landing` folder
- All user data (profile JSON, job store, auto-search store) stored in OS app data dir:
  - Windows: `%APPDATA%\job-hunter\`
  - Linux: `~/.local/share/job-hunter/`
  - macOS: `~/Library/Application Support/job-hunter/`
- Backend listens on `localhost:8000` (fixed port, not dynamic)
- Frontend API base URL in Tauri build: `http://localhost:8000`
- LLM providers supported in settings UI: OpenAI, Ollama, LM Studio, Groq, Mistral, OpenAI-compatible
- CV/CL language dropdown: 30 languages minimum (see §4)

---

## §1 — Overall Architecture

```
Tauri 2.0 Shell (Rust)
├── WebView
│   └── React frontend (Vite build, served as static assets)
│       └── HTTP calls → http://localhost:8000
├── Sidecar: job-hunter-backend (.exe / binary)
│   └── Python FastAPI, all existing endpoints
│       └── Config read from memory (seeded by frontend POST on startup)
└── Tauri Store (plugin-store)
    └── config.json in OS app data dir
        └── LLM keys, Adzuna keys, prompts, language
```

**Startup sequence:**
1. Tauri launches → Rust `main.rs` starts sidecar (`job-hunter-backend`)
2. Sidecar boots FastAPI on `localhost:8000`
3. WebView loads React app
4. React app reads Tauri Store → POSTs config to `POST /config/update`
5. App proceeds normally (existing flow unchanged)

**Config change flow:**
1. User opens Settings → modifies fields → clicks Save
2. Frontend writes to Tauri Store
3. Frontend POSTs updated config to `POST /config/update`
4. Backend updates `settings` object in memory — no restart needed

**CV Preview flow:**
1. User clicks "Generate CV" (existing flow in `ApplicationGenerator`)
2. Backend returns HTML string (existing `resume_renderer.py` unchanged)
3. Frontend calls Tauri command `open_cv_preview(html: String)`
4. Rust opens new `WebviewWindow` with the HTML content
5. User sees CV, presses Ctrl+P, saves as PDF
6. Window closes independently

---

## §2 — Repository Structure Changes

```
job-hunter/
├── src-tauri/                    ← NEW: Tauri scaffold
│   ├── Cargo.toml
│   ├── build.rs
│   ├── tauri.conf.json           ← app name, bundle id, sidecar config
│   ├── icons/                    ← app icons (PNG, ICO, ICNS)
│   └── src/
│       ├── main.rs               ← entry point (minimal)
│       └── lib.rs                ← commands: open_cv_preview
├── backend/
│   ├── app/                      ← unchanged
│   ├── backend.spec              ← NEW: PyInstaller spec
│   └── requirements.txt          ← remove playwright, keep rest
├── frontend/
│   └── src/
│       ├── pages/
│       │   └── SettingsPage.tsx  ← NEW
│       ├── components/
│       │   └── SettingsButton.tsx ← NEW (gear icon, reused in two places)
│       ├── store/
│       │   └── appConfig.ts      ← NEW: Tauri Store read/write wrapper
│       └── api/
│           └── client.ts         ← ADD: updateConfig() call
├── landing/
│   └── index.html                ← NEW: GitHub Pages landing page
├── .github/
│   └── workflows/
│       └── release.yml           ← NEW: cross-platform build + release
├── docker-compose.yml            ← DELETE
└── (backend/Dockerfile already in backend/ — DELETE)
```

---

## §3 — Backend Changes

### 3.1 New endpoint: `POST /config/update`

File: `backend/app/routers/config.py` (extend existing)

```python
class ConfigUpdate(BaseModel):
    llm_provider: LLMProvider
    llm_model: str
    llm_base_url: str | None = None
    llm_api_key: str | None = None
    llm_temperature: float = 0.0
    adzuna_app_id: str | None = None
    adzuna_api_key: str | None = None
    adzuna_country: str = "de"
    search_provider: str = "mock"  # "adzuna" when keys present
    cv_prompt: str | None = None   # overrides prompt_defaults if set
    cl_prompt: str | None = None   # overrides prompt_defaults if set
    cv_language: str = "English"
    cl_language: str = "English"

@router.post("/update", status_code=200)
async def update_config(body: ConfigUpdate) -> dict:
    # Mutates the global `settings` object in memory
    # Returns {"ok": true}
```

`settings` object gains a `update_from_config(body)` method that mutates fields in place. `pydantic-settings` model is modified to allow post-init mutation (remove `model_config` frozen constraint if any).

### 3.2 Data directory migration

All files currently written relative to CWD move to an env-var-configurable path:

```python
# backend/app/core/paths.py  ← NEW
import os, pathlib

DATA_DIR = pathlib.Path(
    os.environ.get("JH_DATA_DIR", pathlib.Path.home() / ".local/share/job-hunter")
)
DATA_DIR.mkdir(parents=True, exist_ok=True)
```

Tauri `src-tauri/src/lib.rs` sets `JH_DATA_DIR` env var when launching the sidecar, pointing to the platform app data dir.

Files affected: `job_store.py`, `auto_search_store.py`, `profile.py` router — all currently use relative paths like `"jobs.json"`. Change to `DATA_DIR / "jobs.json"`.

### 3.3 Remove Playwright

- Delete `backend/app/services/playwright_renderer.py`
- Remove `playwright>=1.44` from `requirements.txt`
- Remove any import of `playwright_renderer` (check `resume_renderer.py` and `application.py`)
- The `/application/render` endpoint (or equivalent) now returns raw HTML string — the caller (frontend) opens it in a Tauri window

### 3.4 Prompt + Language support

`prompt_defaults.py` keeps its default strings. When `/config/update` receives `cv_prompt` or `cl_prompt`, backend stores them and uses them instead of the module-level defaults. Language strings are appended to prompt:

```python
# injected at generation time
f"Generate the output in {settings.cv_language}. " + base_prompt
```

---

## §4 — Frontend Changes

### 4.1 Tauri Store wrapper

File: `frontend/src/store/appConfig.ts`

```typescript
import { load } from '@tauri-apps/plugin-store'

export interface AppConfig {
  llmProvider: 'openai' | 'ollama' | 'lmstudio' | 'groq' | 'mistral' | 'compatible'
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

export async function loadConfig(): Promise<AppConfig>
export async function saveConfig(cfg: AppConfig): Promise<void>
export async function pushConfigToBackend(cfg: AppConfig): Promise<void>
```

`pushConfigToBackend` calls `POST http://localhost:8000/config/update`.

Called on app startup (`App.tsx` `useEffect`) and after every Settings save.

### 4.2 SettingsPage.tsx

NeuGlass design (matches existing pages). Structure:

```
SettingsPage
├── Section: LLM Provider
│   ├── <select> provider dropdown (6 options)
│   ├── Conditional fields based on provider:
│   │   ├── OpenAI: API Key input + link
│   │   ├── Ollama: Base URL + Model + "Download Ollama" link
│   │   ├── LM Studio: Base URL + Model + link
│   │   ├── Groq: API Key + Model + link
│   │   ├── Mistral: API Key + Model + link
│   │   └── Compatible: Base URL + API Key + Model
│   └── Help link (dynamic per provider)
├── Section: Job Search (Adzuna)
│   ├── App ID input
│   ├── API Key input
│   ├── Country dropdown (ISO codes)
│   └── Link: console.adzuna.com/overview
├── Section: CV Prompt
│   └── <textarea> (default from backend prompt_defaults)
├── Section: Cover Letter Prompt
│   └── <textarea>
├── Section: Output Language
│   ├── CV Language <select>
│   └── Cover Letter Language <select>
└── [Save] button (neumo press effect)
```

**Language list (30):**
English, Português, Deutsch, Español, Français, Italiano, Nederlands, Polski, Svenska, Norsk, Dansk, Suomi, Čeština, Magyar, Română, Slovenčina, Hrvatski, Srpski, Türkçe, 日本語, 中文（简体）, 中文（繁體）, 한국어, العربية, हिन्दी, Русский, Українська, Bahasa Indonesia, Bahasa Melayu, Tiếng Việt

### 4.3 SettingsButton component

File: `frontend/src/components/SettingsButton.tsx`

Gear icon button (SVG inline). Two placements:
1. **IngestPage** — shown below upload panel when config is missing/empty (Adzuna keys not set OR LLM key not set). Text: "Configurar antes de começar"
2. **ProfilePage ActionBar** — gear icon in the glass action bar, right side

Clicking either → `setAppState('settings')` in `App.tsx`.

### 4.4 App.tsx additions

```typescript
type AppState = 'loading' | 'no_profile' | 'has_profile' | 'job_search' | 'auto_search' | 'settings'
```

On mount: `loadConfig()` → `pushConfigToBackend()`.

Settings state renders `<SettingsPage onBack={() => setAppState(prevState)} />`.

### 4.5 CV Preview Tauri command

In `frontend/src/api/client.ts` or a new `frontend/src/tauri/commands.ts`:

```typescript
import { invoke } from '@tauri-apps/api/core'

export async function openCvPreview(html: string): Promise<void> {
  await invoke('open_cv_preview', { html })
}
```

Called from `ApplicationGenerator` component after receiving the HTML response.

---

## §5 — Tauri Rust Layer (`src-tauri/`)

### 5.1 `tauri.conf.json` (key fields)

```json
{
  "productName": "Job Hunter Assistant",
  "identifier": "com.jobhunter.app",
  "bundle": {
    "active": true,
    "targets": "all",
    "externalBin": ["binaries/job-hunter-backend"]
  },
  "app": {
    "windows": [{
      "title": "Job Hunter Assistant",
      "width": 1200,
      "height": 800,
      "minWidth": 900,
      "minHeight": 600
    }]
  }
}
```

### 5.2 `src/lib.rs`

```rust
use tauri::{Manager, WebviewUrl, WebviewWindowBuilder};

#[tauri::command]
fn open_cv_preview(app: tauri::AppHandle, html: String) -> Result<(), String> {
    // Write HTML to temp file — data URIs have size limits in some WebViews
    let tmp = std::env::temp_dir().join("jh-cv-preview.html");
    std::fs::write(&tmp, html.as_bytes()).map_err(|e| e.to_string())?;
    let url = format!("file://{}", tmp.to_str().unwrap().replace('\\', "/"));
    WebviewWindowBuilder::new(&app, "cv-preview", WebviewUrl::External(url.parse().unwrap()))
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
        .setup(|app| {
            // Launch sidecar
            let data_dir = app.path().app_data_dir()?;
            std::fs::create_dir_all(&data_dir)?;
            let (_rx, child) = app.shell()
                .sidecar("job-hunter-backend")?
                .env("JH_DATA_DIR", data_dir.to_str().unwrap())
                .spawn()?;
            app.manage(child);
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![open_cv_preview])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}
```

### 5.3 `Cargo.toml` dependencies

```toml
[dependencies]
tauri = { version = "2", features = ["shell-open"] }
tauri-plugin-store = "2"
tauri-plugin-shell = "2"
urlencoding = "2"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
```

---

## §6 — PyInstaller Spec (`backend/backend.spec`)

```python
# backend/backend.spec
a = Analysis(
    ['run.py'],           # new entry: uvicorn app:main
    pathex=['.'],
    binaries=[],
    datas=[],
    hiddenimports=[
        'uvicorn.logging', 'uvicorn.loops', 'uvicorn.loops.auto',
        'uvicorn.protocols', 'uvicorn.protocols.http',
        'uvicorn.protocols.http.auto', 'uvicorn.protocols.websockets',
        'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan',
        'uvicorn.lifespan.on', 'apscheduler', 'pdfplumber',
        'reportlab', 'bs4', 'docx',
    ],
    excludes=['playwright', 'pytest', 'tests'],
    ...
)
exe = EXE(a.pure, ..., name='job-hunter-backend', onefile=True, console=False, windowed=True)
```

Entry point `backend/run.py`:
```python
import uvicorn
if __name__ == '__main__':
    uvicorn.run('app.main:app', host='127.0.0.1', port=8000)
```

---

## §7 — GitHub Actions (`.github/workflows/release.yml`)

```yaml
name: Release
on:
  push:
    tags: ['v*.*.*']

jobs:
  release:
    strategy:
      matrix:
        include:
          - os: ubuntu-latest
            python-arch: x86_64
          - os: windows-latest
            python-arch: x86_64
          - os: macos-latest
            python-arch: universal2  # Intel + Apple Silicon universal binary

    runs-on: ${{ matrix.os }}
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with: { python-version: '3.12' }

      - name: Install Python deps + PyInstaller
        run: pip install -r backend/requirements.txt pyinstaller

      - name: Build Python sidecar
        working-directory: backend
        run: pyinstaller backend.spec

      - name: Copy sidecar to Tauri binaries
        shell: bash
        run: |
          mkdir -p src-tauri/binaries
          # Tauri expects: binaries/job-hunter-backend-{target-triple}
          # tauri-action sets TAURI_TARGET_TRIPLE
          cp backend/dist/job-hunter-backend* \
             src-tauri/binaries/job-hunter-backend-${{ matrix.os == 'windows-latest' && 'x86_64-pc-windows-msvc.exe' || matrix.os == 'macos-latest' && 'aarch64-apple-darwin' || 'x86_64-unknown-linux-gnu' }}

      - uses: pnpm/action-setup@v3
        with: { version: 9 }

      - uses: actions/setup-node@v4
        with: { node-version: 20, cache: 'pnpm', cache-dependency-path: frontend/pnpm-lock.yaml }

      - name: Install frontend deps
        working-directory: frontend
        run: pnpm install

      - uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          tagName: ${{ github.ref_name }}
          releaseName: 'Job Hunter Assistant ${{ github.ref_name }}'
          releaseBody: 'See CHANGELOG for details.'
          releaseDraft: true
          prerelease: false
```

---

## §8 — Landing Page (`landing/index.html`)

Single HTML file. Design: NeuGlass palette (`#1E4D9E`, `#dde4f0`, white cards). No framework, no build.

Sections:
1. **Header** — logo text + tagline: "AI-powered job application assistant. Runs locally. Your data stays yours."
2. **Download buttons** — three buttons: Windows (.msi), Linux (.AppImage), macOS (.dmg). Links: `https://github.com/melkyfb/job-hunter/releases/latest/download/Job.Hunter.Assistant_VERSION_x64.msi` (use JS `fetch` against GitHub API to get latest version dynamically, fallback to `/releases/latest` redirect)
3. **3 feature cards** — "CV gerado por IA", "Busca automática de vagas", "Roda 100% local — sem cloud"
4. **GitHub link** — "Ver código no GitHub →"
5. **Footer** — MIT License

GitHub Pages config: repo Settings → Pages → Source: `main` / `/landing`.

---

## §9 — Settings Not Yet Configured (First-Run UX)

On first launch, Tauri Store is empty. `pushConfigToBackend()` sends empty/default values. Backend starts in "mock" mode (existing behavior).

`App.tsx` detects missing config:
```typescript
const configIncomplete = !config.llmApiKey && config.llmProvider !== 'ollama'
    || (config.adzunaAppId === '' && config.adzunaApiKey === '')
```

`IngestPage` shows a yellow warning banner: "Configuração incompleta — configure a LLM e o Adzuna antes de continuar" with a "Configurar agora" button.

After setup, user returns to IngestPage and uploads resume normally.

---

## Decomposition into Implementation Tasks

| Task | Scope | Files |
|------|-------|-------|
| **1** | Backend: `POST /config/update`, data dir migration, remove Playwright | `config.py`, `paths.py`, `job_store.py`, `auto_search_store.py`, `profile.py`, `requirements.txt` |
| **2** | Tauri scaffold: `src-tauri/` + sidecar launch + `open_cv_preview` command | `src-tauri/**`, `Cargo.toml` |
| **3** | Frontend: Tauri Store wrapper + `App.tsx` config boot + `SettingsPage.tsx` + `SettingsButton.tsx` | `appConfig.ts`, `SettingsPage.tsx`, `SettingsButton.tsx`, `App.tsx`, `client.ts` |
| **4** | PyInstaller spec + GitHub Actions release workflow | `backend.spec`, `run.py`, `.github/workflows/release.yml`, delete Docker files |
| **5** | Landing page | `landing/index.html` |
