import { useState } from 'react'
import { resolveHITL, getIngestStatus, type HITLRequest, type IngestionResponse } from '../api/client'

interface Props {
  request: HITLRequest
  onResolved: (response: IngestionResponse) => void
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div style={{ width: '100%', height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', marginTop: 12 }}>
      <div style={{
        height: '100%', borderRadius: 2, background: 'var(--accent)',
        width: `${value}%`, transition: 'width 0.4s ease',
      }} />
    </div>
  )
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}

export function HITLForm({ request, onResolved }: Props) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(request.missing_fields.map((f) => [f.field_path, '']))
  )
  const [submitting, setSubmitting] = useState(false)
  const [progress, setProgress] = useState(0)
  const [progressMsg, setProgressMsg] = useState('')
  const [error, setError] = useState('')

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    setSubmitting(true)
    setError('')

    try {
      const { job_id } = await resolveHITL({
        ingestion_id: request.ingestion_id,
        resolved_fields: values,
      })

      // Poll until suggestions are done
      while (true) {
        const status = await getIngestStatus(job_id)
        setProgress(status.progress)
        setProgressMsg(status.message)

        if (status.status === 'processing') {
          await sleep(1000)
          continue
        }

        if (status.status === 'completed') {
          onResolved(status.result as IngestionResponse)
          return
        }

        setError((status.result as IngestionResponse)?.error ?? status.message)
        setSubmitting(false)
        return
      }
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Submission failed.')
      setSubmitting(false)
    }
  }

  return (
    <div style={{ maxWidth: 600 }}>
      <h2 style={{ fontSize: 18, marginBottom: 4, color: 'var(--text-h)' }}>Almost there!</h2>
      <p style={{ color: 'var(--text)', fontSize: 14, marginBottom: 20 }}>
        {request.message} The AI couldn't find exact metrics for the fields below.
        Adding real numbers will make your resume much stronger.
      </p>

      <form onSubmit={handleSubmit}>
        {request.missing_fields.map((field) => (
          <div key={field.field_path} style={{ marginBottom: 20 }}>
            <label style={{ display: 'block', fontSize: 13, fontWeight: 600, marginBottom: 4, color: 'var(--text-h)' }}>
              {field.llm_suggestion ?? field.field_path}
            </label>
            <p style={{ fontSize: 12, color: 'var(--text)', margin: '0 0 6px' }}>{field.reason}</p>
            <input
              type="text"
              required
              disabled={submitting}
              placeholder='e.g. "by 40%, from 800ms to 480ms"'
              value={values[field.field_path]}
              onChange={(e) =>
                setValues((v) => ({ ...v, [field.field_path]: e.target.value }))
              }
              style={{
                width: '100%',
                padding: '8px 12px',
                borderRadius: 6,
                border: '1px solid var(--border)',
                fontSize: 14,
                boxSizing: 'border-box',
                background: 'var(--bg)',
                color: 'var(--text-h)',
              }}
            />
          </div>
        ))}

        {submitting && (
          <div style={{ marginBottom: 16 }}>
            <p style={{ fontSize: 13, color: 'var(--text-h)', margin: 0 }}>{progressMsg}</p>
            <ProgressBar value={progress} />
          </div>
        )}

        {error && <p style={{ color: '#ef4444', fontSize: 13 }}>{error}</p>}

        <button
          type="submit"
          disabled={submitting}
          style={{
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            borderRadius: 8,
            padding: '10px 24px',
            fontWeight: 600,
            cursor: submitting ? 'wait' : 'pointer',
            fontSize: 14,
          }}
        >
          {submitting ? 'Saving…' : 'Save and continue'}
        </button>
      </form>
    </div>
  )
}
