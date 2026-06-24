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
