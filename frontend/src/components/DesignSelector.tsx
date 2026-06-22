import { type DesignVersion } from '../api/client'

interface Props {
  versions: DesignVersion[]
  type: 'resume' | 'cover_letter'
  selectedId: string | null
  onChange: (id: string | null) => void
  label: string
  allowInherit?: boolean
}

export function DesignSelector({ versions, type, selectedId, onChange, label, allowInherit }: Props) {
  const filtered = versions.filter(v => v.type === type)
  if (filtered.length === 0) return null

  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8 }}>
      <label style={{ fontSize: 12, color: 'var(--text)', whiteSpace: 'nowrap', minWidth: 120 }}>{label}:</label>
      <select
        value={selectedId ?? ''}
        onChange={e => onChange(e.target.value || null)}
        style={{ flex: 1, padding: '5px 8px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg)', color: 'var(--text-h)' }}
      >
        <option value="">Default (Classic)</option>
        {allowInherit && <option value="__inherit__">Same as resume</option>}
        {filtered.map(v => (
          <option key={v.id} value={v.id}>{v.name}{v.is_default ? ' ★' : ''}</option>
        ))}
      </select>
    </div>
  )
}
