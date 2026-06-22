import { useState } from 'react'
import {
  saveAutoSearchConfig,
  type AutoSearchConfig,
  type SearchEntry,
} from '../api/client'

interface Props {
  config: AutoSearchConfig
  onSaved: (updated: AutoSearchConfig) => void
}

const INTERVAL_OPTIONS = [1, 2, 4, 8, 12, 24]

const ALL_PROVIDERS: { id: string; label: string }[] = [
  { id: 'linkedin',  label: 'LinkedIn'    },
  { id: 'indeed',    label: 'Indeed'      },
  { id: 'google',    label: 'Google Jobs' },
  { id: 'stepstone', label: 'Stepstone'   },
  { id: 'xing',      label: 'Xing'        },
]

function KeywordChips({
  keywords,
  onChange,
}: {
  keywords: string[]
  onChange: (kws: string[]) => void
}) {
  const [draft, setDraft] = useState('')

  function add() {
    const kw = draft.trim()
    if (kw && !keywords.includes(kw)) onChange([...keywords, kw])
    setDraft('')
  }

  return (
    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, alignItems: 'center' }}>
      {keywords.map(kw => (
        <span
          key={kw}
          style={{
            fontSize: 11, padding: '2px 8px', borderRadius: 10,
            background: 'var(--accent-bg)', color: 'var(--accent)',
            border: '1px solid var(--accent-border)', display: 'flex', alignItems: 'center', gap: 4,
          }}
        >
          {kw}
          <button
            onClick={() => onChange(keywords.filter(k => k !== kw))}
            style={{ background: 'none', border: 'none', cursor: 'pointer', padding: 0, color: 'var(--accent)', fontSize: 11, lineHeight: 1 }}
          >
            ×
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={e => setDraft(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' || e.key === ',') { e.preventDefault(); add() } }}
        onBlur={add}
        placeholder="+ keyword"
        style={{
          border: 'none', outline: 'none', fontSize: 11, background: 'transparent',
          color: 'var(--text-h)', minWidth: 80,
        }}
      />
    </div>
  )
}

export function AutoSearchConfigPanel({ config, onSaved }: Props) {
  const [open, setOpen] = useState(false)
  const [draft, setDraft] = useState<AutoSearchConfig>({
    ...config,
    providers: config.providers ?? ['linkedin', 'indeed', 'google', 'stepstone', 'xing'],
  })
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')

  function updateEntry(id: string, patch: Partial<SearchEntry>) {
    setDraft(d => ({
      ...d,
      entries: d.entries.map(e => e.id === id ? { ...e, ...patch } : e),
    }))
  }

  function removeEntry(id: string) {
    setDraft(d => ({ ...d, entries: d.entries.filter(e => e.id !== id) }))
  }

  function addCustomEntry() {
    const newEntry: SearchEntry = {
      id: crypto.randomUUID(),
      title: '',
      keywords: [],
      active: true,
      custom: true,
    }
    setDraft(d => ({ ...d, entries: [...d.entries, newEntry] }))
  }

  async function handleSave() {
    setSaving(true)
    setError('')
    try {
      const saved = await saveAutoSearchConfig(draft)
      onSaved(saved)
      setOpen(false)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao salvar.')
    } finally {
      setSaving(false)
    }
  }

  return (
    <div style={{ border: '1px solid var(--border)', borderRadius: 8, marginBottom: 16, overflow: 'hidden' }}>
      <button
        onClick={() => setOpen(v => !v)}
        style={{
          width: '100%', padding: '10px 14px', display: 'flex', justifyContent: 'space-between',
          alignItems: 'center', background: 'var(--bg)', border: 'none', cursor: 'pointer',
          fontSize: 13, fontWeight: 600, color: 'var(--text-h)',
        }}
      >
        <span>⚙️ Configuração da busca</span>
        <span style={{ fontSize: 11, color: 'var(--text)' }}>{open ? '▲ fechar' : '▼ expandir'}</span>
      </button>

      {open && (
        <div style={{ padding: '12px 14px', borderTop: '1px solid var(--border)', background: 'var(--bg)' }}>

          {/* Top controls */}
          <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', marginBottom: 14 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text)' }}>
              <input
                type="checkbox"
                checked={draft.enabled}
                onChange={e => setDraft(d => ({ ...d, enabled: e.target.checked }))}
              />
              Ativada
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text)' }}>
              Intervalo:
              <select
                value={draft.interval_hours}
                onChange={e => setDraft(d => ({ ...d, interval_hours: Number(e.target.value) }))}
                style={{ padding: '3px 6px', borderRadius: 5, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg)', color: 'var(--text-h)' }}
              >
                {INTERVAL_OPTIONS.map(h => (
                  <option key={h} value={h}>{h}h</option>
                ))}
              </select>
            </label>

            <label style={{ display: 'flex', alignItems: 'center', gap: 6, fontSize: 13, color: 'var(--text)', flex: 1 }}>
              Local:
              <input
                value={draft.location}
                onChange={e => setDraft(d => ({ ...d, location: e.target.value }))}
                style={{
                  flex: 1, padding: '4px 8px', borderRadius: 5, border: '1px solid var(--border)',
                  fontSize: 12, background: 'var(--bg)', color: 'var(--text-h)',
                }}
              />
            </label>
          </div>

          {/* Providers */}
          <div style={{ marginBottom: '12px' }}>
            <label style={{ display: 'block', fontSize: '11px', color: 'var(--text-h)', marginBottom: '6px', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
              Providers
            </label>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px' }}>
              {ALL_PROVIDERS.map(({ id, label }) => {
                const checked = (draft.providers ?? []).includes(id)
                return (
                  <label key={id} style={{ display: 'flex', alignItems: 'center', gap: '4px', fontSize: '13px', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={checked}
                      onChange={() => {
                        const current = draft.providers ?? []
                        const next = checked
                          ? current.filter(p => p !== id)
                          : [...current, id]
                        setDraft(d => ({ ...d, providers: next }))
                      }}
                    />
                    {label}
                  </label>
                )
              })}
            </div>
          </div>

          {/* Entries */}
          <div style={{ marginBottom: 10 }}>
            <p style={{ fontSize: 12, color: 'var(--text)', margin: '0 0 8px', fontWeight: 600 }}>Buscas:</p>
            {draft.entries.map(entry => (
              <div
                key={entry.id}
                style={{
                  display: 'grid', gridTemplateColumns: 'auto 1fr auto', gap: 8,
                  alignItems: 'start', marginBottom: 8, padding: '8px 10px',
                  border: '1px solid var(--border)', borderRadius: 6, background: 'rgba(0,0,0,0.02)',
                }}
              >
                <input
                  type="checkbox"
                  checked={entry.active}
                  onChange={e => updateEntry(entry.id, { active: e.target.checked })}
                  style={{ marginTop: 3 }}
                />
                <div>
                  <input
                    value={entry.title}
                    onChange={e => updateEntry(entry.id, { title: e.target.value })}
                    placeholder="Título do cargo"
                    style={{
                      width: '100%', padding: '4px 8px', borderRadius: 5,
                      border: '1px solid var(--border)', fontSize: 12,
                      background: 'var(--bg)', color: 'var(--text-h)', marginBottom: 6,
                      boxSizing: 'border-box',
                    }}
                  />
                  <KeywordChips
                    keywords={entry.keywords}
                    onChange={kws => updateEntry(entry.id, { keywords: kws })}
                  />
                </div>
                {entry.custom && (
                  <button
                    onClick={() => removeEntry(entry.id)}
                    style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#ef4444', fontSize: 16, padding: 0 }}
                  >
                    ×
                  </button>
                )}
                {!entry.custom && <div />}
              </div>
            ))}
            <button
              onClick={addCustomEntry}
              style={{
                fontSize: 12, color: 'var(--accent)', background: 'none',
                border: '1px dashed var(--accent-border)', borderRadius: 6,
                padding: '5px 12px', cursor: 'pointer', width: '100%',
              }}
            >
              + Adicionar título customizado
            </button>
          </div>

          {error && <p style={{ fontSize: 12, color: '#ef4444', margin: '0 0 8px' }}>{error}</p>}

          <button
            onClick={handleSave}
            disabled={saving}
            style={{
              padding: '7px 18px', background: saving ? 'var(--border)' : 'var(--accent)',
              color: 'white', border: 'none', borderRadius: 6, fontWeight: 600,
              cursor: saving ? 'default' : 'pointer', fontSize: 13,
            }}
          >
            {saving ? 'Salvando…' : 'Salvar configurações'}
          </button>
        </div>
      )}
    </div>
  )
}
