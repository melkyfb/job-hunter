import { useEffect, useRef, useState } from 'react'
import { setJobStatus, type JobStatus, type SavedJobWithStatus } from '../api/client'

interface Props {
  job: SavedJobWithStatus
  onStatusChanged: (urlHash: string, newStatus: JobStatus) => void
}

const STATUS_OPTIONS: { status: JobStatus; label: string }[] = [
  { status: 'NOT_INTERESTED', label: '👎 Sem interesse' },
  { status: 'APPLIED', label: '📨 Currículo enviado' },
  { status: 'INTERVIEWING', label: '🗓 Em processo' },
  { status: 'OFFER_RECEIVED', label: '🎉 Oferta recebida' },
  { status: 'NONE', label: '↩ Desfazer' },
]

export function JobStatusMenu({ job, onStatusChanged }: Props) {
  const [open, setOpen] = useState(false)
  const [busy, setBusy] = useState(false)
  const ref = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function close(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false)
    }
    document.addEventListener('mousedown', close)
    return () => document.removeEventListener('mousedown', close)
  }, [open])

  async function handleSelect(newStatus: JobStatus) {
    setOpen(false)
    setBusy(true)
    try {
      await setJobStatus(job.url_hash, newStatus)
      onStatusChanged(job.url_hash, newStatus)
    } finally {
      setBusy(false)
    }
  }

  const options = STATUS_OPTIONS.filter(o => o.status !== job.status)

  return (
    <div ref={ref} style={{ position: 'relative' }}>
      <button
        onClick={() => setOpen(v => !v)}
        disabled={busy}
        style={{
          background: 'none', border: '1px solid var(--border)', borderRadius: 5,
          padding: '3px 8px', cursor: busy ? 'default' : 'pointer',
          fontSize: 14, color: 'var(--text)', lineHeight: 1,
        }}
        title="Atualizar status"
      >
        {busy ? '…' : '⋮'}
      </button>

      {open && (
        <div style={{
          position: 'absolute', right: 0, top: '110%', zIndex: 100,
          background: 'var(--bg)', border: '1px solid var(--border)',
          borderRadius: 8, boxShadow: '0 4px 16px rgba(0,0,0,0.12)',
          minWidth: 180, overflow: 'hidden',
        }}>
          {options.map(o => (
            <button
              key={o.status}
              onClick={() => handleSelect(o.status)}
              style={{
                display: 'block', width: '100%', padding: '8px 14px',
                textAlign: 'left', background: 'none', border: 'none',
                cursor: 'pointer', fontSize: 13, color: 'var(--text-h)',
              }}
              onMouseEnter={e => (e.currentTarget.style.background = 'var(--accent-bg)')}
              onMouseLeave={e => (e.currentTarget.style.background = 'none')}
            >
              {o.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}
