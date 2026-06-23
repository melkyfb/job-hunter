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
          Writing tailored resume + cover letter with AI — takes 2-5min
        </p>
      )}
    </div>
  )
}

function btnStyle(bg: string, border?: string, color?: string): React.CSSProperties {
  return { padding: '6px 14px', background: bg, color: color ?? 'white', border: `1px solid ${border ?? bg}`, borderRadius: 6, fontSize: 12, fontWeight: 600, cursor: 'pointer' }
}
