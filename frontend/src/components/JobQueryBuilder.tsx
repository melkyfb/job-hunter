import { useState } from 'react'
import type { JobSuggestion } from '../api/client'

interface Props {
  suggestions: JobSuggestion[]
  onSearch: (query: string, keywords: string[]) => void
  loading: boolean
}

export function JobQueryBuilder({ suggestions, onSearch, loading }: Props) {
  const [selectedTitle, setSelectedTitle] = useState<JobSuggestion | null>(null)
  const [selectedKeywords, setSelectedKeywords] = useState<Set<string>>(new Set())
  const [customQuery, setCustomQuery] = useState('')

  function selectSuggestion(s: JobSuggestion) {
    if (selectedTitle?.title === s.title) {
      // deselect
      setSelectedTitle(null)
      setSelectedKeywords(new Set())
    } else {
      setSelectedTitle(s)
      setSelectedKeywords(new Set(s.keywords))
      setCustomQuery('')
    }
  }

  function toggleKeyword(kw: string) {
    setSelectedKeywords(prev => {
      const next = new Set(prev)
      next.has(kw) ? next.delete(kw) : next.add(kw)
      return next
    })
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    const query = customQuery.trim() || selectedTitle?.title || ''
    if (!query) return
    onSearch(query, [...selectedKeywords])
  }

  const hasSuggestions = suggestions.length > 0

  return (
    <form onSubmit={handleSubmit}>
      {hasSuggestions ? (
        <>
          <p style={{ fontSize: 13, color: 'var(--text)', marginBottom: 10 }}>
            Suggested roles based on your profile — click to select:
          </p>

          {/* Title chips */}
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 14 }}>
            {suggestions.map(s => {
              const active = selectedTitle?.title === s.title
              return (
                <button
                  key={s.title}
                  type="button"
                  onClick={() => selectSuggestion(s)}
                  style={{
                    padding: '5px 12px',
                    borderRadius: 20,
                    fontSize: 12,
                    fontWeight: active ? 600 : 400,
                    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
                    background: active ? 'var(--accent-bg)' : 'transparent',
                    color: active ? 'var(--accent)' : 'var(--text)',
                    cursor: 'pointer',
                    transition: 'all 0.12s',
                  }}
                >
                  {s.title}
                </button>
              )
            })}
          </div>

          {/* Keyword chips — show when a title is selected */}
          {selectedTitle && (
            <div style={{ marginBottom: 14 }}>
              <p style={{ fontSize: 12, color: 'var(--text)', marginBottom: 6 }}>
                Keywords for <strong style={{ color: 'var(--text-h)' }}>{selectedTitle.title}</strong> — toggle to refine:
              </p>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                {selectedTitle.keywords.map(kw => {
                  const on = selectedKeywords.has(kw)
                  return (
                    <button
                      key={kw}
                      type="button"
                      onClick={() => toggleKeyword(kw)}
                      style={{
                        padding: '3px 10px',
                        borderRadius: 4,
                        fontSize: 11,
                        border: `1px solid ${on ? '#22c07a' : 'var(--border)'}`,
                        background: on ? 'rgba(34,192,122,0.12)' : 'transparent',
                        color: on ? '#22c07a' : 'var(--text)',
                        cursor: 'pointer',
                        transition: 'all 0.1s',
                      }}
                    >
                      {kw}
                    </button>
                  )
                })}
              </div>
            </div>
          )}

          {/* Divider */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
            <span style={{ fontSize: 11, color: 'var(--text)' }}>or type a custom query</span>
            <div style={{ flex: 1, height: 1, background: 'var(--border)' }} />
          </div>
        </>
      ) : null}

      {/* Custom query input — always visible */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
        <input
          value={customQuery}
          onChange={e => {
            setCustomQuery(e.target.value)
            if (e.target.value) {
              setSelectedTitle(null)
              setSelectedKeywords(new Set())
            }
          }}
          placeholder={selectedTitle ? `Or override: ${selectedTitle.title}` : 'Job title or keywords'}
          style={{
            flex: 1,
            minWidth: 200,
            padding: '8px 12px',
            borderRadius: 6,
            border: '1px solid var(--border)',
            fontSize: 14,
            background: 'var(--bg)',
            color: 'var(--text-h)',
          }}
        />
        <button
          type="submit"
          disabled={loading || (!selectedTitle && !customQuery.trim())}
          style={{
            padding: '8px 20px',
            background: 'var(--accent)',
            color: 'white',
            border: 'none',
            borderRadius: 6,
            fontWeight: 600,
            cursor: loading ? 'wait' : 'pointer',
            fontSize: 14,
            opacity: (!selectedTitle && !customQuery.trim()) ? 0.5 : 1,
          }}
        >
          {loading ? 'Scoring…' : 'Search'}
        </button>
      </div>
    </form>
  )
}
