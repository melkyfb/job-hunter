import { useState } from 'react'
import { updateDesign, deleteDesign, getDesignPreviewUrl, getDesignPdfUrl, type DesignVersion } from '../api/client'

interface Props {
  versions: DesignVersion[]
  type: 'resume' | 'cover_letter'
  activeId: string | null
  onUpdated: (version: DesignVersion) => void
  onDeleted: (id: string) => void
}

function DesignCard({ version, isActive, onSetDefault, onDelete }: {
  version: DesignVersion
  isActive: boolean
  onSetDefault: () => void
  onDelete: () => void
}) {
  const [confirmDelete, setConfirmDelete] = useState(false)

  return (
    <div style={{
      border: `1px solid ${isActive ? 'var(--accent)' : 'var(--border)'}`,
      borderRadius: 10, overflow: 'hidden', background: 'var(--bg)',
      display: 'flex', flexDirection: 'column',
    }}>
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
      </div>
    </div>
  )
}

export function DesignGallery({ versions, type, activeId, onUpdated, onDeleted }: Props) {
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
        />
      ))}
    </div>
  )
}
