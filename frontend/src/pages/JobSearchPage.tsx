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
              onMouseDown={e => { e.currentTarget.style.color = 'var(--blue-medium)' }}
              onMouseUp={e => { e.currentTarget.style.color = 'var(--blue-primary)' }}
              onMouseLeave={e => { e.currentTarget.style.color = 'var(--blue-primary)' }}
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
