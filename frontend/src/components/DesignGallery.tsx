import { useState } from 'react'
import {
  updateDesign,
  deleteDesign,
  getDesignPreviewUrl,
  getDesignPdfUrl,
  regenerateDesign,
  getIngestStatus,
  type DesignVersion,
} from '../api/client'

interface Props {
  versions: DesignVersion[]
  type: 'resume' | 'cover_letter'
  activeId: string | null
  onUpdated: (version: DesignVersion) => void
  onDeleted: (id: string) => void
  onRegenerated?: () => void
}

type CardState = 'idle' | 'regenerating' | 'error'

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

function DesignCard({
  version,
  isActive,
  onSetDefault,
  onDelete,
  onRegenerated,
}: {
  version: DesignVersion
  isActive: boolean
  onSetDefault: () => void
  onDelete: () => void
  onRegenerated?: () => void
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)
  const [cardState, setCardState] = useState<CardState>('idle')
  const [regenError, setRegenError] = useState('')

  async function handleRegenerate() {
    setCardState('regenerating')
    setRegenError('')
    try {
      const { job_id } = await regenerateDesign(version.id)
      while (true) {
        const status = await getIngestStatus(job_id)
        if (status.status === 'completed') {
          setCardState('idle')
          onRegenerated?.()
          return
        }
        if (status.status === 'failed') {
          setRegenError(status.message || 'Regeneration failed.')
          setCardState('error')
          return
        }
        await sleep(1000)
      }
    } catch (err: unknown) {
      setRegenError(err instanceof Error ? err.message : 'Regeneration failed.')
      setCardState('error')
    }
  }

  const isRegenerating = cardState === 'regenerating'
  const canRegenerate = !!version.prompt && cardState !== 'regenerating'

  return (
    <div style={{
      border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: 10, overflow: 'hidden', background: 'var(--bg)',
      display: 'flex', flexDirection: 'column', position: 'relative',
    }}>
      {/* Spinner overlay while regenerating */}
      {isRegenerating && (
        <div style={{
          position: 'absolute', inset: 0, background: 'rgba(0,0,0,0.35)',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          zIndex: 10, borderRadius: 10,
        }}>
          <span style={{ color: '#fff', fontSize: 12 }}>Regenerando…</span>
        </div>
      )}

      {/* Scaled iframe thumbnail */}
      <div style={{ height: 140, overflow: 'hidden', position: 'relative', background: '#f5f5f5' }}>
        <iframe
          src={getDesignPreviewUrl(version.id)}
          title={version.name}
          sandbox="allow-same-origin allow-scripts"
          style={{
            width: '550%',
            height: '550%',
            border: 'none',
            transform: 'scale(0.18)',
            transformOrigin: 'top left',
            pointerEvents: 'none',
          }}
        />
      </div>

      <div style={{ padding: '8px 10px', flex: 1 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 6 }}>
          <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-h)', flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            {version.name}
          </span>
          {isActive && (
            <span style={{ fontSize: 10, padding: '1px 6px', borderRadius: 10, background: 'var(--accent-bg)', color: 'var(--accent)', border: '1px solid var(--accent-border)', whiteSpace: 'nowrap' }}>
              ★ default
            </span>
          )}
        </div>

        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          <a
            href={getDesignPdfUrl(version.id)}
            target="_blank"
            rel="noopener noreferrer"
            style={{ fontSize: 11, color: 'var(--accent)', textDecoration: 'none' }}
          >
            PDF ↗
          </a>
          {!isActive && (
            <button onClick={onSetDefault} style={{ fontSize: 11, background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', padding: 0 }}>
              Set default
            </button>
          )}
          {canRegenerate && (
            <button
              onClick={handleRegenerate}
              disabled={isRegenerating}
              style={{ fontSize: 11, background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', padding: 0 }}
            >
              Regenerar
            </button>
          )}
          {confirmDelete ? (
            <>
              <button onClick={onDelete} style={{ fontSize: 11, background: 'none', border: 'none', color: '#ef4444', cursor: 'pointer', padding: 0 }}>Confirm</button>
              <button onClick={() => setConfirmDelete(false)} style={{ fontSize: 11, background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', padding: 0 }}>Cancel</button>
            </>
          ) : (
            <button onClick={() => setConfirmDelete(true)} style={{ fontSize: 11, background: 'none', border: 'none', color: 'var(--text)', cursor: 'pointer', padding: 0 }}>
              Delete
            </button>
          )}
        </div>

        {cardState === 'error' && (
          <p style={{ fontSize: 10, color: '#ef4444', margin: '4px 0 0', lineHeight: 1.3 }}>{regenError}</p>
        )}
      </div>
    </div>
  )
}

export function DesignGallery({ versions, type, activeId, onUpdated, onDeleted, onRegenerated }: Props) {
  const filtered = versions.filter(v => v.type === type)

  if (filtered.length === 0) return null

  async function handleSetDefault(version: DesignVersion) {
    const updated = await updateDesign(version.id, { is_default: true })
    onUpdated(updated)
  }

  async function handleDelete(id: string) {
    await deleteDesign(id)
    onDeleted(id)
  }

  return (
    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(160px, 1fr))', gap: 12, marginBottom: 16 }}>
      {filtered.map(v => (
        <DesignCard
          key={v.id}
          version={v}
          isActive={v.id === activeId}
          onSetDefault={() => handleSetDefault(v)}
          onDelete={() => handleDelete(v.id)}
          onRegenerated={onRegenerated}
        />
      ))}
    </div>
  )
}
