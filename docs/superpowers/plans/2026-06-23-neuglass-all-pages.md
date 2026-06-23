# NeuGlass — All Pages Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the NeuGlass design system (already live on ProfilePage) to the remaining three pages: IngestPage, JobSearchPage, and AutoSearchPage.

**Architecture:** Same pattern as ProfilePage: each page gets a `PAGE_BG` gradient wrapper + `colorScheme: 'light'`, content sections become `NEUMO_PANEL`, cards become `NEUMO_CARD_SM`, form inputs become `NEUMO_INSET`. Two additional semantic color tokens (`--color-success`, `--color-warning`) are added to `:root` in Task 1 alongside the IngestPage update.

**Tech Stack:** React 19, TypeScript, Vite, CSS custom properties (all tokens already in `index.css` from prior plan), inline styles only

## Global Constraints

- No new npm dependencies
- Light mode only — `[data-theme="dark"]` and `@media (prefers-color-scheme: dark)` blocks NOT modified
- All inline styles reference CSS custom properties — no hardcoded hex colors (except `rgba()` for keyword chip backgrounds where values are data-semantic: green match, red missing — these are intentional)
- `colorScheme: 'light' as const` on every `PAGE_BG` constant
- `var(--accent)` and `var(--text)` / `var(--text-h)` must NOT appear in updated files — replace with NeuGlass equivalents
- `var(--bg)` and `var(--border)` must NOT appear in updated files — replace with NeuGlass equivalents
- No changes to external sub-components (`ResumeUpload`, `HITLForm`, `ApplicationGenerator`, `JobQueryBuilder`, `AutoSearchConfigPanel`, `JobStatusMenu`)
- No changes to `App.tsx`, backend, or `ProfilePage.tsx`
- `tsc --noEmit` passes with 0 errors after each task

## Token Reference (all already in `index.css`)

| Token | Value | Use |
|-------|-------|-----|
| `--neumo-bg` | `#dde4f0` | Panel/card backgrounds |
| `--neumo-raised` | compound shadow | Section panels |
| `--neumo-raised-sm` | compound shadow (smaller) | Cards, buttons |
| `--neumo-inset` | inset shadow | Inputs, selects, textareas |
| `--neumo-pressed` | inset shadow (smaller) | Button :active |
| `--glass-bg` | `rgba(255,255,255,0.18)` | Glass overlays |
| `--glass-blur` | `blur(14px) saturate(180%)` | Backdrop filter |
| `--glass-border` | `rgba(255,255,255,0.35)` | Glass borders |
| `--glass-shadow` | `0 8px 32px rgba(30,77,158,0.12)` | Glass shadows |
| `--blue-primary` | `#1E4D9E` | CTA buttons, active state, links |
| `--blue-medium` | `#3d6cbf` | Secondary highlights |
| `--blue-light` | `#EBF1FB` | Chip/badge backgrounds |
| `--blue-border` | `#C3D4EF` | Chip/badge borders |
| `--blue-gradient` | `linear-gradient(...)` | Page background |
| `--neumo-text` | `#2d3a52` | Primary text |
| `--neumo-text-s` | `#5a6a82` | Secondary text |
| `--color-error` | `#ef4444` | Error states, destructive buttons |
| `--color-success` | (Task 1 adds) `#22c55e` | Score ≥ 75, match keywords |
| `--color-warning` | (Task 1 adds) `#f59e0b` | Score 50–74 |

## File Map

| File | Change |
|------|--------|
| `frontend/src/index.css` | Add `--color-success` and `--color-warning` to `:root` |
| `frontend/src/pages/IngestPage.tsx` | NeuGlass layout — centered card on gradient |
| `frontend/src/pages/JobSearchPage.tsx` | NeuGlass layout — search panel + result cards |
| `frontend/src/pages/AutoSearchPage.tsx` | NeuGlass layout — header panel, tab bar, job cards, glass modal |

---

### Task 1: Semantic Color Tokens + IngestPage

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/pages/IngestPage.tsx`

**Interfaces:**
- Consumes: `--color-error` (already in `:root`), `--neumo-*`, `--blue-*` (already in `:root`)
- Produces: `--color-success`, `--color-warning` tokens consumed by Tasks 2 and 3

- [ ] **Step 1: Add two tokens to `index.css`**

Find `--color-error:   #ef4444;` in the `:root` block and add two lines immediately after it:

```css
  --color-success: #22c55e;
  --color-warning: #f59e0b;
```

- [ ] **Step 2: Replace `IngestPage.tsx` with NeuGlass version**

Replace the full contents of `frontend/src/pages/IngestPage.tsx`:

```tsx
import { useState } from 'react'
import { ResumeUpload } from '../components/ResumeUpload'
import { HITLForm } from '../components/HITLForm'
import { type IngestionResponse } from '../api/client'

interface Props {
  onProfileReady: () => void
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

export function IngestPage({ onProfileReady }: Props) {
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
        <h1 style={{ fontSize: 22, margin: '0 0 8px', color: 'var(--neumo-text)', fontWeight: 700 }}>Import your resume</h1>
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

- [ ] **Step 3: Verify TypeScript**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/frontend
npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 4: Commit**

```bash
rtk git add frontend/src/index.css frontend/src/pages/IngestPage.tsx
rtk git commit -m "feat: NeuGlass — add semantic color tokens + IngestPage"
```

---

### Task 2: JobSearchPage

**Files:**
- Modify: `frontend/src/pages/JobSearchPage.tsx`

**Interfaces:**
- Consumes: `--color-success`, `--color-warning`, `--color-error` (from Task 1), all `--neumo-*` and `--blue-*` tokens
- Produces: nothing (leaf page)

**Note on keyword chip colors:** `rgba(34,197,94,...)` (green match) and `rgba(239,68,68,...)` (red missing) are intentional semantic colors tied to data meaning. These are NOT design system tokens — keep them as rgba inline values. Only the text colors reference tokens: `var(--color-success)` for match text, `var(--color-error)` for missing text.

- [ ] **Step 1: Replace `JobSearchPage.tsx` with NeuGlass version**

Replace the full contents of `frontend/src/pages/JobSearchPage.tsx`:

```tsx
import { useState } from 'react'
import { searchJobs, getSearchStatus, type RankedJob, type JobSearchResponse, type JobSuggestion } from '../api/client'
import { ApplicationGenerator } from '../components/ApplicationGenerator'
import { JobQueryBuilder } from '../components/JobQueryBuilder'

interface Props {
  onBack: () => void
  suggestions: JobSuggestion[]
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

function timeAgo(isoString: string): string {
  const diffMs = Date.now() - new Date(isoString).getTime()
  const mins = Math.floor(diffMs / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.floor(mins / 60)
  return `${hours}h ago`
}

// ── Style constants ────────────────────────────────────────────────────────

const PAGE_BG: React.CSSProperties = {
  background: 'var(--blue-gradient)',
  minHeight: '100svh',
  padding: '0 0 48px',
  colorScheme: 'light' as const,
}

const CONTENT_WRAP: React.CSSProperties = {
  maxWidth: 680,
  margin: '0 auto',
  padding: '24px 24px',
}

const NEUMO_PANEL: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '20px 24px',
  marginBottom: 20,
}

const NEUMO_CARD_SM: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised-sm)',
  borderRadius: 12,
  padding: '14px 16px',
  marginBottom: 12,
}

const NEUMO_INSET: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-inset)',
  borderRadius: 8,
  border: 'none',
  padding: '6px 12px',
  fontSize: 13,
  color: 'var(--neumo-text)',
  flex: 1,
  maxWidth: 260,
}

const BTN_PRIMARY: React.CSSProperties = {
  padding: '8px 18px',
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
  padding: '7px 14px',
  background: 'var(--neumo-bg)',
  color: 'var(--neumo-text)',
  border: 'none',
  borderRadius: 10,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
}

const SECTION_TITLE: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: 1,
  textTransform: 'uppercase' as const,
  color: 'var(--blue-primary)',
  margin: '0 0 14px',
  borderBottom: '2px solid var(--blue-border)',
  paddingBottom: 6,
}

// ── Sub-components ─────────────────────────────────────────────────────────

function ProgressBar({ value }: { value: number }) {
  return (
    <div style={{ width: '100%', height: 4, background: 'var(--neumo-shadow-dark)', borderRadius: 2, overflow: 'hidden', marginTop: 8 }}>
      <div style={{
        height: '100%', borderRadius: 2,
        background: 'linear-gradient(to right, var(--blue-primary), var(--blue-medium))',
        width: `${value}%`, transition: 'width 0.5s ease',
      }} />
    </div>
  )
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 75 ? 'var(--color-success)' : score >= 50 ? 'var(--color-warning)' : 'var(--color-error)'
  return (
    <div style={{
      background: 'var(--neumo-bg)', color, borderRadius: 10,
      padding: '4px 10px', fontWeight: 700, fontSize: 15, flexShrink: 0,
      border: `1px solid ${color}`, boxShadow: 'var(--neumo-raised-sm)',
    }}>
      {score}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export function JobSearchPage({ onBack, suggestions }: Props) {
  const [location, setLocation] = useState('Munich, Germany')
  const [results, setResults] = useState<RankedJob[] | null>(null)
  const [loading, setLoading] = useState(false)
  const [loadStep, setLoadStep] = useState('')
  const [loadProgress, setLoadProgress] = useState(0)
  const [error, setError] = useState('')
  const [cachedAt, setCachedAt] = useState<string | null>(null)
  const [lastQuery, setLastQuery] = useState('')

  async function doSearch(query: string, forceRefresh = false) {
    setLoading(true)
    setError('')
    setResults(null)
    setCachedAt(null)
    setLastQuery(query)
    setLoadProgress(5)
    setLoadStep(`Searching for "${query}"…`)

    try {
      const start = await searchJobs({ query, location, max_results: 10, force_refresh: forceRefresh })

      if (start.status === 'completed') {
        const job = await getSearchStatus(start.search_id)
        const res = job.result as JobSearchResponse
        setResults(res.results)
        setCachedAt(res.cached ? res.cached_at : null)
        return
      }

      while (true) {
        const status = await getSearchStatus(start.search_id)
        setLoadStep(status.message)
        setLoadProgress(status.progress)

        if (status.status === 'processing') {
          await sleep(1000)
          continue
        }

        if (status.status === 'completed') {
          const res = status.result as JobSearchResponse
          setResults(res.results)
          setCachedAt(res.cached ? res.cached_at : null)
          return
        }

        setError(status.message)
        return
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Search failed.')
    } finally {
      setLoading(false)
      setLoadProgress(0)
    }
  }

  return (
    <div style={PAGE_BG}>
      <div style={CONTENT_WRAP}>

        {/* Back */}
        <button
          onClick={onBack}
          style={{ ...BTN_GHOST, marginBottom: 16, fontSize: 13 }}
          onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
          onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
        >
          ← Back to profile
        </button>

        {/* Search panel */}
        <div style={NEUMO_PANEL}>
          <h2 style={SECTION_TITLE}>Find Jobs</h2>
          <p style={{ color: 'var(--neumo-text-s)', fontSize: 13, margin: '0 0 14px', lineHeight: 1.5 }}>
            Each result is scored against your Master Profile for ATS compatibility.
          </p>

          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
            <label style={{ fontSize: 12, color: 'var(--neumo-text-s)', whiteSpace: 'nowrap' }}>Location:</label>
            <input
              value={location}
              onChange={e => setLocation(e.target.value)}
              placeholder="Munich, Germany"
              style={NEUMO_INSET}
            />
          </div>

          <JobQueryBuilder
            suggestions={suggestions}
            onSearch={(query) => doSearch(query)}
            loading={loading}
          />
        </div>

        {/* Error */}
        {error && <p style={{ color: 'var(--color-error)', fontSize: 13, marginTop: -8, marginBottom: 12 }}>{error}</p>}

        {/* Progress */}
        {loading && (
          <div style={{ ...NEUMO_PANEL, padding: '14px 20px' }}>
            <p style={{ color: 'var(--neumo-text)', fontSize: 13, margin: 0 }}>{loadStep}</p>
            <ProgressBar value={loadProgress} />
          </div>
        )}

        {/* Cache banner */}
        {cachedAt && (
          <div style={{
            display: 'flex', alignItems: 'center', gap: 10,
            fontSize: 12, color: 'var(--neumo-text-s)',
            background: 'var(--blue-light)', border: '1px solid var(--blue-border)',
            borderRadius: 10, padding: '6px 14px', marginBottom: 12,
          }}>
            <span>Cached results · searched {timeAgo(cachedAt)}</span>
            <button
              onClick={() => doSearch(lastQuery, true)}
              style={{ background: 'none', border: 'none', color: 'var(--blue-primary)', cursor: 'pointer', fontSize: 12, fontWeight: 700, padding: 0 }}
            >
              Refresh
            </button>
          </div>
        )}

        {/* Empty state */}
        {results !== null && results.length === 0 && (
          <div style={NEUMO_PANEL}>
            <p style={{ color: 'var(--neumo-text-s)', fontSize: 14, margin: 0 }}>No jobs found above the compatibility threshold.</p>
          </div>
        )}

        {/* Results */}
        {results && results.length > 0 && results.map(({ posting, match }) => (
          <div key={posting.id} style={NEUMO_CARD_SM}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
              <div>
                <a href={posting.url} target="_blank" rel="noopener noreferrer"
                  style={{ fontWeight: 700, fontSize: 15, color: 'var(--neumo-text)', textDecoration: 'none' }}>
                  {posting.title}
                </a>
                <p style={{ margin: '2px 0', fontSize: 13, color: 'var(--neumo-text-s)' }}>
                  {posting.company} · {posting.location}
                  {posting.salary_range && ` · ${posting.salary_range}`}
                </p>
              </div>
              <ScoreBadge score={match.score} />
            </div>

            <p style={{ fontSize: 13, color: 'var(--neumo-text-s)', margin: '10px 0 8px', lineHeight: 1.5 }}>
              {match.justification}
            </p>

            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' as const }}>
              {match.keywords_found.length > 0 && (
                <div>
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-success)', textTransform: 'uppercase' as const, letterSpacing: 0.5 }}>Match </span>
                  {match.keywords_found.map(k => (
                    <span key={k} style={{ fontSize: 11, background: 'rgba(34,197,94,0.12)', color: 'var(--color-success)', borderRadius: 4, padding: '1px 6px', marginRight: 4 }}>{k}</span>
                  ))}
                </div>
              )}
              {match.keywords_missing.length > 0 && (
                <div>
                  <span style={{ fontSize: 11, fontWeight: 700, color: 'var(--color-error)', textTransform: 'uppercase' as const, letterSpacing: 0.5 }}>Missing </span>
                  {match.keywords_missing.map(k => (
                    <span key={k} style={{ fontSize: 11, background: 'rgba(239,68,68,0.12)', color: 'var(--color-error)', borderRadius: 4, padding: '1px 6px', marginRight: 4 }}>{k}</span>
                  ))}
                </div>
              )}
            </div>

            <ApplicationGenerator job={posting} match={match} />
          </div>
        ))}

      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/frontend
npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/pages/JobSearchPage.tsx
rtk git commit -m "feat: NeuGlass — JobSearchPage search panel + result cards"
```

---

### Task 3: AutoSearchPage

**Files:**
- Modify: `frontend/src/pages/AutoSearchPage.tsx`

**Interfaces:**
- Consumes: all `--neumo-*`, `--blue-*`, `--color-*`, `--glass-*` tokens
- Produces: nothing (leaf page)

**Key design decisions:**
- Cleanup modal overlay uses `backdropFilter: 'var(--glass-blur)'` with a blue-tinted rgba background
- Tab bar: active tab gets `var(--blue-primary)` border-bottom and text; inactive gets `var(--neumo-text-s)`
- Status chip on job card: `var(--blue-light)` background, `var(--blue-primary)` text, `var(--blue-border)` border
- ScoreBadge: `var(--color-success)` / `var(--color-warning)` / `var(--color-error)` for dynamic color
- Pagination active: `var(--blue-primary)` bg, white text; inactive: neumo ghost
- `cleanupMsg` shown in `var(--blue-primary)` (confirmation, not error)
- `runResult.ok = false`: `var(--color-error)`; `runResult.ok = true`: `var(--blue-primary)`

- [ ] **Step 1: Replace `AutoSearchPage.tsx` with NeuGlass version**

Replace the full contents of `frontend/src/pages/AutoSearchPage.tsx`:

```tsx
import { useEffect, useRef, useState } from 'react'
import {
  cleanupAutoSearch,
  getAutoSearchConfig,
  getAutoSearchResults,
  getIngestStatus,
  markAutoSearchSeen,
  triggerAutoSearchRun,
  type AutoSearchConfig,
  type AutoSearchResultsPage,
  type JobStatus,
  type SavedJobWithStatus,
} from '../api/client'
import { ApplicationGenerator } from '../components/ApplicationGenerator'
import { AutoSearchConfigPanel } from '../components/AutoSearchConfig'
import { JobStatusMenu } from '../components/JobStatusMenu'

interface Props {
  onBack: () => void
}

type Tab = 'new' | 'pipeline' | 'not_interested'

const TAB_FILTERS: Record<Tab, string> = {
  new: 'NONE',
  pipeline: 'APPLIED,INTERVIEWING,OFFER_RECEIVED',
  not_interested: 'NOT_INTERESTED',
}

const STATUS_LABELS: Record<string, string> = {
  APPLIED: 'Enviado',
  INTERVIEWING: 'Em processo',
  OFFER_RECEIVED: 'Oferta',
  NOT_INTERESTED: 'Sem interesse',
  NONE: '',
}

// ── Style constants ────────────────────────────────────────────────────────

const PAGE_BG: React.CSSProperties = {
  background: 'var(--blue-gradient)',
  minHeight: '100svh',
  padding: '0 0 48px',
  colorScheme: 'light' as const,
}

const CONTENT_WRAP: React.CSSProperties = {
  maxWidth: 800,
  margin: '0 auto',
  padding: '24px 16px',
}

const NEUMO_PANEL: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '16px 20px',
  marginBottom: 16,
}

const NEUMO_CARD_SM: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised-sm)',
  borderRadius: 12,
  padding: '12px 14px',
  marginBottom: 8,
}

const BTN_PRIMARY: React.CSSProperties = {
  padding: '7px 14px',
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
  padding: '7px 14px',
  background: 'var(--neumo-bg)',
  color: 'var(--neumo-text)',
  border: 'none',
  borderRadius: 10,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
}

const BTN_DANGER: React.CSSProperties = {
  padding: '7px 16px',
  background: 'var(--color-error)',
  color: 'white',
  border: 'none',
  borderRadius: 10,
  fontWeight: 600,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
}

// ── Sub-components ─────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const bg = score >= 75 ? 'var(--color-success)' : score >= 50 ? 'var(--color-warning)' : 'var(--color-error)'
  return (
    <span style={{
      display: 'inline-block', minWidth: 36, textAlign: 'center' as const,
      padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 700,
      color: 'white', background: bg, boxShadow: 'var(--neumo-raised-sm)',
    }}>
      {score}
    </span>
  )
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  const m = Math.floor(diff / 60_000)
  if (h >= 48) return `${Math.floor(h / 24)}d atrás`
  if (h >= 1) return `${h}h atrás`
  return `${m}m atrás`
}

function JobCard({ job, onStatusChanged }: {
  job: SavedJobWithStatus
  onStatusChanged: (urlHash: string, newStatus: JobStatus) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const p = job.posting
  const m = job.match

  return (
    <div style={NEUMO_CARD_SM}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const }}>
            <ScoreBadge score={m.score} />
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--neumo-text)' }}>{p.title}</span>
            {job.status !== 'NONE' && (
              <span style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 4,
                background: 'var(--blue-light)', color: 'var(--blue-primary)',
                border: '1px solid var(--blue-border)',
              }}>
                {STATUS_LABELS[job.status]}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--neumo-text-s)', marginTop: 3 }}>
            {p.company} · {p.location}
            {p.salary_range && <span> · {p.salary_range}</span>}
            <span style={{ marginLeft: 8, opacity: 0.7 }}>{timeAgo(job.found_at)}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--neumo-text-s)', marginTop: 2, opacity: 0.8 }}>
            via: {job.found_via}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          <button
            onClick={() => setExpanded(v => !v)}
            style={{ fontSize: 12, color: 'var(--blue-primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontWeight: 600 }}
          >
            {expanded ? 'fechar' : 'ver mais'}
          </button>
          <JobStatusMenu job={job} onStatusChanged={onStatusChanged} />
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--blue-border)' }}>
          <p style={{ fontSize: 12, color: 'var(--neumo-text-s)', whiteSpace: 'pre-wrap', margin: '0 0 10px' }}>
            {p.description.slice(0, 600)}{p.description.length > 600 ? '…' : ''}
          </p>
          {m.keywords_found.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--color-success)', fontWeight: 600 }}>Match: </span>
              {m.keywords_found.map(k => (
                <span key={k} style={{ fontSize: 11, padding: '1px 5px', borderRadius: 4, background: 'rgba(34,197,94,0.12)', color: 'var(--color-success)', marginRight: 4 }}>{k}</span>
              ))}
            </div>
          )}
          <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--blue-primary)', fontWeight: 600 }}>
            Ver vaga ↗
          </a>
          <ApplicationGenerator job={p} match={m} />
        </div>
      )}
    </div>
  )
}

function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  if (totalPages <= 1) return null
  const pages = Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
    if (totalPages <= 7) return i + 1
    if (i === 0) return 1
    if (i === 6) return totalPages
    return page + i - 3
  }).filter(p => p >= 1 && p <= totalPages)

  const pageBtn = (active: boolean): React.CSSProperties => ({
    padding: '4px 10px', borderRadius: 8, fontSize: 13, cursor: 'pointer',
    border: 'none',
    background: active ? 'var(--blue-primary)' : 'var(--neumo-bg)',
    color: active ? 'white' : 'var(--neumo-text)',
    boxShadow: 'var(--neumo-raised-sm)',
    fontWeight: active ? 700 : 400,
  })

  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: 4, marginTop: 16 }}>
      <button onClick={() => onChange(page - 1)} disabled={page <= 1} style={pageBtn(false)}>‹</button>
      {pages.map(p => (
        <button key={p} onClick={() => onChange(p)} style={pageBtn(p === page)}>{p}</button>
      ))}
      <button onClick={() => onChange(page + 1)} disabled={page >= totalPages} style={pageBtn(false)}>›</button>
    </div>
  )
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

// ── Main component ─────────────────────────────────────────────────────────

export function AutoSearchPage({ onBack }: Props) {
  const [config, setConfig] = useState<AutoSearchConfig | null>(null)
  const [tab, setTab] = useState<Tab>('new')
  const [sort, setSort] = useState<'score' | 'recent'>('score')
  const [page, setPage] = useState(1)
  const [resultsPage, setResultsPage] = useState<AutoSearchResultsPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [runProgress, setRunProgress] = useState('')
  const [runResult, setRunResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [showCleanup, setShowCleanup] = useState(false)
  const [cleanupOpts, setCleanupOpts] = useState({ remove_not_interested: false, remove_unavailable: false })
  const [cleanupMsg, setCleanupMsg] = useState('')

  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const pageSize = config?.page_size ?? 10

  useEffect(() => {
    getAutoSearchConfig().then(setConfig).catch(console.error)
  }, [])

  useEffect(() => {
    if (tab === 'new') markAutoSearchSeen().catch(() => {})
  }, [tab])

  useEffect(() => {
    if (!config) return
    loadResults()
  }, [tab, page, sort, config])

  async function loadResults() {
    setLoading(true)
    try {
      const res = await getAutoSearchResults(page, pageSize, TAB_FILTERS[tab], sort)
      setResultsPage(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  function handleTabChange(t: Tab) {
    setTab(t)
    setPage(1)
    setResultsPage(null)
  }

  function handleStatusChanged(urlHash: string, _newStatus: JobStatus) {
    setResultsPage(prev => {
      if (!prev) return prev
      return { ...prev, jobs: prev.jobs.filter(j => j.url_hash !== urlHash) }
    })
  }

  async function handleRunNow() {
    if (!mountedRef.current) return
    setRunning(true)
    setRunResult(null)
    setRunProgress('Iniciando busca…')
    try {
      const { job_id } = await triggerAutoSearchRun()
      let lastStatus = 'processing'
      let lastMessage = ''
      while (mountedRef.current) {
        const status = await getIngestStatus(job_id)
        if (!mountedRef.current) break
        setRunProgress(status.message)
        lastStatus = status.status
        lastMessage = status.message
        if (status.status !== 'processing') break
        await sleep(1500)
      }
      if (mountedRef.current) {
        await loadResults()
        if (lastStatus === 'completed') {
          setRunResult({ ok: true, msg: lastMessage || 'Busca concluída!' })
        } else if (lastStatus === 'failed') {
          setRunResult({ ok: false, msg: lastMessage || 'Busca falhou.' })
        }
      }
    } catch (err: unknown) {
      if (mountedRef.current) {
        const msg = err instanceof Error ? err.message : 'Erro ao executar busca.'
        setRunResult({ ok: false, msg })
      }
    } finally {
      if (mountedRef.current) {
        setRunning(false)
        setRunProgress('')
      }
    }
  }

  async function handleCleanup() {
    try {
      const result = await cleanupAutoSearch(cleanupOpts)
      setCleanupMsg(`${result.removed} vagas removidas.`)
      setShowCleanup(false)
      setPage(1)
      await loadResults()
    } catch {
      setCleanupMsg('Erro ao limpar.')
    }
  }

  const TAB_LABELS: Record<Tab, string> = {
    new: 'Novas vagas',
    pipeline: 'Pipeline',
    not_interested: 'Sem interesse',
  }

  return (
    <div style={PAGE_BG}>
      <div style={CONTENT_WRAP}>

        {/* Header panel */}
        <div style={NEUMO_PANEL}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--neumo-text)' }}>⚡ Auto Busca de Vagas</h2>
              {config && (
                <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--neumo-text-s)' }}>
                  {config.enabled ? `Busca a cada ${config.interval_hours}h` : 'Busca desativada'}
                </p>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={handleRunNow}
                disabled={running}
                style={{ ...BTN_PRIMARY, opacity: running ? 0.6 : 1, cursor: running ? 'default' : 'pointer' }}
                onMouseDown={e => { if (!running) e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
                onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
              >
                {running ? '🔄 Buscando…' : '▶ Buscar agora'}
              </button>
              <button
                onClick={onBack}
                style={BTN_GHOST}
                onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
                onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
              >
                ← Voltar
              </button>
            </div>
          </div>
        </div>

        {/* Run status */}
        {running && runProgress && (
          <p style={{ fontSize: 12, color: 'var(--blue-primary)', marginBottom: 12 }}>{runProgress}</p>
        )}
        {!running && runResult && (
          <p style={{ fontSize: 12, color: runResult.ok ? 'var(--blue-primary)' : 'var(--color-error)', marginBottom: 12 }}>
            {runResult.msg}
          </p>
        )}

        {/* Config panel */}
        {config && (
          <AutoSearchConfigPanel
            config={config}
            onSaved={updated => { setConfig(updated); setPage(1) }}
          />
        )}

        {/* Tab bar */}
        <div style={{ display: 'flex', borderBottom: '2px solid var(--blue-border)', marginBottom: 14, gap: 0 }}>
          {(['new', 'pipeline', 'not_interested'] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => handleTabChange(t)}
              style={{
                padding: '8px 16px', fontSize: 13, fontWeight: tab === t ? 700 : 400,
                background: 'var(--neumo-bg)', border: 'none', cursor: 'pointer',
                borderBottom: tab === t ? '2px solid var(--blue-primary)' : '2px solid transparent',
                color: tab === t ? 'var(--blue-primary)' : 'var(--neumo-text-s)',
                marginBottom: -2,
                boxShadow: tab === t ? 'var(--neumo-raised-sm)' : 'none',
                borderRadius: '8px 8px 0 0',
              }}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>

        {/* Results controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontSize: 12, color: 'var(--neumo-text-s)' }}>
            {resultsPage ? `${resultsPage.total} vagas · pág ${resultsPage.page}/${resultsPage.total_pages}` : '…'}
          </span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select
              value={sort}
              onChange={e => { setSort(e.target.value as 'score' | 'recent'); setPage(1) }}
              style={{
                padding: '4px 8px', borderRadius: 8, border: 'none', fontSize: 12,
                background: 'var(--neumo-bg)', color: 'var(--neumo-text)',
                boxShadow: 'var(--neumo-inset)', cursor: 'pointer',
              }}
            >
              <option value="score">Score ↓</option>
              <option value="recent">Mais recentes</option>
            </select>
            <button
              onClick={() => setShowCleanup(true)}
              style={BTN_GHOST}
              onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
              onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
              onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            >
              🧹 Limpar
            </button>
          </div>
        </div>

        {/* Results */}
        {loading && <p style={{ fontSize: 13, color: 'var(--neumo-text-s)' }}>Carregando…</p>}
        {!loading && resultsPage?.jobs.length === 0 && (
          <div style={{ ...NEUMO_PANEL, textAlign: 'center' as const, padding: '40px 20px' }}>
            <p style={{ fontSize: 14, color: 'var(--neumo-text-s)', margin: '0 0 4px' }}>Nenhuma vaga nesta aba.</p>
            {tab === 'new' && (
              <p style={{ fontSize: 12, color: 'var(--neumo-text-s)', margin: 0 }}>Clique em "Buscar agora" para atualizar.</p>
            )}
          </div>
        )}
        {!loading && resultsPage?.jobs.map(job => (
          <JobCard
            key={job.url_hash}
            job={job}
            onStatusChanged={handleStatusChanged}
          />
        ))}

        {resultsPage && (
          <Pagination page={page} totalPages={resultsPage.total_pages} onChange={setPage} />
        )}

        {cleanupMsg && (
          <p style={{ fontSize: 12, color: 'var(--blue-primary)', marginTop: 8 }}>{cleanupMsg}</p>
        )}

        {/* Cleanup modal */}
        {showCleanup && (
          <div style={{
            position: 'fixed' as const, inset: 0,
            background: 'rgba(30, 77, 158, 0.18)',
            backdropFilter: 'var(--glass-blur)',
            WebkitBackdropFilter: 'var(--glass-blur)',
            zIndex: 200,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              background: 'var(--neumo-bg)',
              boxShadow: 'var(--neumo-raised)',
              borderRadius: 16,
              padding: '20px 24px', minWidth: 320, maxWidth: 400,
            }}>
              <h3 style={{ margin: '0 0 14px', fontSize: 15, color: 'var(--neumo-text)', fontWeight: 700 }}>🧹 Limpar vagas</h3>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, fontSize: 13, color: 'var(--neumo-text)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={cleanupOpts.remove_not_interested}
                  onChange={e => setCleanupOpts(o => ({ ...o, remove_not_interested: e.target.checked }))}
                />
                Remover vagas marcadas como "Sem interesse"
              </label>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16, fontSize: 13, color: 'var(--neumo-text)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={cleanupOpts.remove_unavailable}
                  onChange={e => setCleanupOpts(o => ({ ...o, remove_unavailable: e.target.checked }))}
                />
                Remover vagas que não aparecem mais nas buscas
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={handleCleanup}
                  style={BTN_DANGER}
                  onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
                  onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                  onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                >
                  Limpar
                </button>
                <button
                  onClick={() => setShowCleanup(false)}
                  style={BTN_GHOST}
                  onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
                  onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                  onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                >
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
```

- [ ] **Step 2: Verify TypeScript**

```bash
cd C:/Users/itsal/ClaudeWorkspace/job-hunter/frontend
npx tsc --noEmit
```

Expected: 0 errors.

- [ ] **Step 3: Commit**

```bash
rtk git add frontend/src/pages/AutoSearchPage.tsx
rtk git commit -m "feat: NeuGlass — AutoSearchPage header panel, job cards, glass cleanup modal"
```

---

## Self-Review

**Spec coverage:**

| Requirement | Task |
|-------------|------|
| `--color-success: #22c55e` in `:root` | Task 1 |
| `--color-warning: #f59e0b` in `:root` | Task 1 |
| `IngestPage` — PAGE_BG, NEUMO_PANEL card, `var(--color-error)` | Task 1 |
| `IngestPage` — error + HITL states wrapped in panels | Task 1 |
| `JobSearchPage` — PAGE_BG, search NEUMO_PANEL, result NEUMO_CARD_SM | Task 2 |
| `JobSearchPage` — no `var(--accent)` / `var(--bg)` / `var(--border)` | Task 2 |
| `JobSearchPage` — ScoreBadge uses `--color-success/warning/error` | Task 2 |
| `JobSearchPage` — location input NEUMO_INSET | Task 2 |
| `JobSearchPage` — ProgressBar uses `--blue-primary` gradient | Task 2 |
| `AutoSearchPage` — PAGE_BG, header NEUMO_PANEL, NEUMO_CARD_SM cards | Task 3 |
| `AutoSearchPage` — tab bar `--blue-primary` active | Task 3 |
| `AutoSearchPage` — cleanup modal glass overlay + NEUMO_PANEL dialog | Task 3 |
| `AutoSearchPage` — status chip uses `--blue-light/primary/border` | Task 3 |
| `AutoSearchPage` — no `var(--accent)` / `var(--bg)` / `var(--border)` | Task 3 |
| `colorScheme: 'light' as const` on all PAGE_BG constants | Tasks 1, 2, 3 |
| `tsc --noEmit` 0 errors after each task | All tasks |
| No external sub-component files touched | All tasks |

**Placeholder scan:** None. All code is complete in the steps above.

**Type consistency:** `NEUMO_CARD_SM`, `NEUMO_PANEL`, `BTN_PRIMARY`, `BTN_GHOST`, `BTN_DANGER` defined at module level and used directly — no name divergence between tasks.
