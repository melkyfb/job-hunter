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
