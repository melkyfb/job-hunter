import { useEffect, useState } from 'react'
import { autoSearchJobs, type AutoSearchResponse, type RankedJob, type DesignVersion } from '../api/client'
import { ApplicationGenerator } from '../components/ApplicationGenerator'

interface Props {
  onBack: () => void
  designs?: DesignVersion[]
}

function ScoreBadge({ score }: { score: number }) {
  const color = score >= 75 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <span style={{
      display: 'inline-block', minWidth: 36, textAlign: 'center',
      padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 700,
      color: 'white', background: color,
    }}>
      {score}
    </span>
  )
}

function JobCard({ job, designs = [] }: { job: RankedJob; designs?: DesignVersion[] }) {
  const [expanded, setExpanded] = useState(false)
  const p = job.posting
  const m = job.match

  return (
    <div style={{
      border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px',
      marginBottom: 10, background: 'var(--bg)',
    }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-h)' }}>{p.title}</span>
            {job.found_via && (
              <span style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 4,
                background: 'var(--accent-bg)', color: 'var(--accent)',
                border: '1px solid var(--accent-border)',
              }}>
                via: {job.found_via}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 2 }}>
            {p.company} · {p.location}
            {p.salary_range && <span> · {p.salary_range}</span>}
          </div>
        </div>
        <ScoreBadge score={m.score} />
      </div>

      <p style={{ fontSize: 12, color: 'var(--text)', margin: '8px 0 0', lineHeight: 1.5 }}>
        {m.justification}
      </p>

      {m.keywords_found.length > 0 && (
        <div style={{ marginTop: 8, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {m.keywords_found.slice(0, 6).map(k => (
            <span key={k} style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(34,197,94,0.1)', color: '#16a34a' }}>✓ {k}</span>
          ))}
          {m.keywords_missing.slice(0, 4).map(k => (
            <span key={k} style={{ fontSize: 10, padding: '1px 6px', borderRadius: 4, background: 'rgba(239,68,68,0.1)', color: '#dc2626' }}>✗ {k}</span>
          ))}
        </div>
      )}

      <div style={{ marginTop: 10, display: 'flex', gap: 8, alignItems: 'center' }}>
        <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--accent)' }}>
          View posting →
        </a>
        <button
          onClick={() => setExpanded(!expanded)}
          style={{ fontSize: 12, background: 'none', border: '1px solid var(--border)', borderRadius: 5, padding: '2px 8px', cursor: 'pointer', color: 'var(--text)' }}
        >
          {expanded ? 'Hide application' : 'Generate application'}
        </button>
      </div>

      {expanded && (
        <div style={{ marginTop: 12, borderTop: '1px solid var(--border)', paddingTop: 12 }}>
          <ApplicationGenerator job={p} match={m} designs={designs} />
        </div>
      )}
    </div>
  )
}

// ── Main ─────────────────────────────────────────────────────────────────────

type PageState = 'idle' | 'running' | 'done' | 'error'

export function AutoSearchPage({ onBack, designs = [] }: Props) {
  const [state, setState] = useState<PageState>('running')
  const [data, setData] = useState<AutoSearchResponse | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [elapsed, setElapsed] = useState(0)

  useEffect(() => {
    const start = Date.now()
    const ticker = setInterval(() => setElapsed(Math.floor((Date.now() - start) / 1000)), 500)

    autoSearchJobs()
      .then(res => { setData(res); setState('done') })
      .catch(err => { setError(err.message ?? 'Auto search failed'); setState('error') })
      .finally(() => clearInterval(ticker))

    return () => clearInterval(ticker)
  }, [])

  return (
    <div style={{ maxWidth: 720, textAlign: 'left' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: 20 }}>
        <button
          onClick={onBack}
          style={{ background: 'none', border: '1px solid var(--border)', borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontSize: 13, color: 'var(--text)' }}
        >
          ← Back
        </button>
        <h1 style={{ fontSize: 20, margin: 0, color: 'var(--text-h)' }}>Auto Search</h1>
      </div>

      {state === 'running' && (
        <div style={{
          padding: '24px', borderRadius: 10, border: '1px solid var(--border)',
          textAlign: 'center',
        }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>🔍</div>
          <p style={{ fontSize: 14, color: 'var(--text-h)', margin: '0 0 4px', fontWeight: 500 }}>
            Finding the best jobs for your profile…
          </p>
          <p style={{ fontSize: 12, color: 'var(--text)', margin: 0 }}>
            Running up to 5 searches in parallel · {elapsed}s elapsed
          </p>
        </div>
      )}

      {state === 'error' && (
        <div style={{ padding: 16, borderRadius: 8, background: 'rgba(239,68,68,0.1)', border: '1px solid rgba(239,68,68,0.4)', color: '#dc2626', fontSize: 13 }}>
          {error}
        </div>
      )}

      {state === 'done' && data && (
        <>
          <div style={{
            padding: '10px 14px', borderRadius: 8, marginBottom: 16,
            background: 'var(--accent-bg)', border: '1px solid var(--accent-border)',
            fontSize: 12, color: 'var(--text)',
          }}>
            Found <strong style={{ color: 'var(--text-h)' }}>{data.results.length} jobs</strong> across{' '}
            <strong style={{ color: 'var(--text-h)' }}>{data.queries_used.length} searches</strong>:{' '}
            {data.queries_used.join(', ')}
          </div>

          {data.results.length === 0 ? (
            <p style={{ fontSize: 13, color: 'var(--text)' }}>No jobs found above the compatibility threshold. Try a manual search with different keywords.</p>
          ) : (
            data.results.map(job => <JobCard key={job.posting.id} job={job} designs={designs} />)
          )}
        </>
      )}
    </div>
  )
}
