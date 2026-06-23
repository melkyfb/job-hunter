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

function ProgressBar({ value }: { value: number }) {
  return (
    <div style={{ width: '100%', height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', marginTop: 8 }}>
      <div style={{
        height: '100%', borderRadius: 2, background: 'var(--accent)',
        width: `${value}%`, transition: 'width 0.5s ease',
      }} />
    </div>
  )
}

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

      // Cache hit: immediately resolved
      if (start.status === 'completed') {
        const job = await getSearchStatus(start.search_id)
        const res = job.result as JobSearchResponse
        setResults(res.results)
        setCachedAt(res.cached ? res.cached_at : null)
        return
      }

      // Background job: poll
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
    <div style={{ maxWidth: 680 }}>
      <button
        onClick={onBack}
        style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--accent)', fontSize: 13, padding: 0, marginBottom: 20 }}
      >
        ← Back to profile
      </button>

      <h1 style={{ fontSize: 20, marginBottom: 4, color: 'var(--text-h)' }}>Find Jobs</h1>
      <p style={{ color: 'var(--text)', fontSize: 14, marginBottom: 6 }}>
        Each result is scored against your Master Profile for ATS compatibility.
      </p>

      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <label style={{ fontSize: 12, color: 'var(--text)', whiteSpace: 'nowrap' }}>Location:</label>
        <input
          value={location}
          onChange={e => setLocation(e.target.value)}
          placeholder="Munich, Germany"
          style={{ flex: 1, maxWidth: 260, padding: '6px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, background: 'var(--bg)', color: 'var(--text-h)' }}
        />
      </div>

      <JobQueryBuilder
        suggestions={suggestions}
        onSearch={(query) => doSearch(query)}
        loading={loading}
      />

      {error && <p style={{ color: '#ef4444', fontSize: 13, marginTop: 10 }}>{error}</p>}

      {loading && (
        <div style={{ marginTop: 14 }}>
          <p style={{ color: 'var(--text-h)', fontSize: 13, margin: 0 }}>{loadStep}</p>
          <ProgressBar value={loadProgress} />
        </div>
      )}

      {/* Cache banner */}
      {cachedAt && (
        <div style={{
          display: 'flex', alignItems: 'center', gap: 10,
          fontSize: 12, color: 'var(--text)',
          background: 'var(--accent-bg)', border: '1px solid var(--accent-border)',
          borderRadius: 6, padding: '6px 12px', marginTop: 16, marginBottom: 8,
        }}>
          <span>Cached results · searched {timeAgo(cachedAt)}</span>
          <button
            onClick={() => doSearch(lastQuery, true)}
            style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0 }}
          >
            Refresh
          </button>
        </div>
      )}

      {results !== null && results.length === 0 && (
        <p style={{ color: 'var(--text)', fontSize: 14, marginTop: 16 }}>No jobs found above the compatibility threshold.</p>
      )}

      {results && results.length > 0 && (
        <div style={{ marginTop: 16 }}>
          {results.map(({ posting, match }) => (
            <div key={posting.id} style={{ border: '1px solid var(--border)', borderRadius: 10, padding: 16, marginBottom: 12, background: 'var(--bg)' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                <div>
                  <a href={posting.url} target="_blank" rel="noopener noreferrer"
                    style={{ fontWeight: 700, fontSize: 15, color: 'var(--text-h)', textDecoration: 'none' }}>
                    {posting.title}
                  </a>
                  <p style={{ margin: '2px 0', fontSize: 13, color: 'var(--text)' }}>
                    {posting.company} · {posting.location}
                    {posting.salary_range && ` · ${posting.salary_range}`}
                  </p>
                </div>
                <ScoreBadge score={match.score} />
              </div>

              <p style={{ fontSize: 13, color: 'var(--text)', margin: '10px 0 8px', lineHeight: 1.5 }}>
                {match.justification}
              </p>

              <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
                {match.keywords_found.length > 0 && (
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#22c07a', textTransform: 'uppercase', letterSpacing: 0.5 }}>Match </span>
                    {match.keywords_found.map(k => (
                      <span key={k} style={{ fontSize: 11, background: 'rgba(34,192,122,0.15)', color: '#22c07a', borderRadius: 4, padding: '1px 6px', marginRight: 4 }}>{k}</span>
                    ))}
                  </div>
                )}
                {match.keywords_missing.length > 0 && (
                  <div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: '#ef4444', textTransform: 'uppercase', letterSpacing: 0.5 }}>Missing </span>
                    {match.keywords_missing.map(k => (
                      <span key={k} style={{ fontSize: 11, background: 'rgba(239,68,68,0.15)', color: '#ef4444', borderRadius: 4, padding: '1px 6px', marginRight: 4 }}>{k}</span>
                    ))}
                  </div>
                )}
              </div>

              <ApplicationGenerator job={posting} match={match} />
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 75 ? '#22c07a' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <div style={{ background: 'rgba(0,0,0,0.08)', color, borderRadius: 8, padding: '4px 10px', fontWeight: 700, fontSize: 15, flexShrink: 0, border: `1px solid ${color}` }}>
      {score}
    </div>
  )
}
