import { useEffect, useRef, useState } from 'react'
import {
  cleanupAutoSearch,
  getAutoSearchConfig,
  getAutoSearchResults,
  getIngestStatus,
  markAutoSearchSeen,
  triggerAutoSearchRun,
  type AutoSearchConfig,
  type AutoSearchResultsPage,
  type JobStatus,
  type SavedJobWithStatus,
} from '../api/client'
import { ApplicationGenerator } from '../components/ApplicationGenerator'
import { AutoSearchConfigPanel } from '../components/AutoSearchConfig'
import { JobStatusMenu } from '../components/JobStatusMenu'

interface Props {
  onBack: () => void
}

type Tab = 'new' | 'pipeline' | 'not_interested'

const TAB_FILTERS: Record<Tab, string> = {
  new: 'NONE',
  pipeline: 'APPLIED,INTERVIEWING,OFFER_RECEIVED',
  not_interested: 'NOT_INTERESTED',
}

const STATUS_LABELS: Record<string, string> = {
  APPLIED: 'Enviado',
  INTERVIEWING: 'Em processo',
  OFFER_RECEIVED: 'Oferta',
  NOT_INTERESTED: 'Sem interesse',
  NONE: '',
}

// ── Style constants ────────────────────────────────────────────────────────

const PAGE_BG: React.CSSProperties = {
  background: 'var(--blue-gradient)',
  minHeight: '100svh',
  padding: '0 0 48px',
  colorScheme: 'light' as const,
}

const CONTENT_WRAP: React.CSSProperties = {
  maxWidth: 800,
  margin: '0 auto',
  padding: '24px 16px',
}

const NEUMO_PANEL: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '16px 20px',
  marginBottom: 16,
}

const NEUMO_CARD_SM: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised-sm)',
  borderRadius: 12,
  padding: '12px 14px',
  marginBottom: 8,
}

const BTN_PRIMARY: React.CSSProperties = {
  padding: '7px 14px',
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
  padding: '7px 14px',
  background: 'var(--neumo-bg)',
  color: 'var(--neumo-text)',
  border: 'none',
  borderRadius: 10,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
}

const BTN_DANGER: React.CSSProperties = {
  padding: '7px 16px',
  background: 'var(--color-error)',
  color: 'white',
  border: 'none',
  borderRadius: 10,
  fontWeight: 600,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
}

// ── Sub-components ─────────────────────────────────────────────────────────

function ScoreBadge({ score }: { score: number }) {
  const bg = score >= 75 ? 'var(--color-success)' : score >= 50 ? 'var(--color-warning)' : 'var(--color-error)'
  return (
    <span style={{
      display: 'inline-block', minWidth: 36, textAlign: 'center' as const,
      padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 700,
      color: 'white', background: bg, boxShadow: 'var(--neumo-raised-sm)',
    }}>
      {score}
    </span>
  )
}

function timeAgo(iso: string): string {
  const diff = Date.now() - new Date(iso).getTime()
  const h = Math.floor(diff / 3_600_000)
  const m = Math.floor(diff / 60_000)
  if (h >= 48) return `${Math.floor(h / 24)}d atrás`
  if (h >= 1) return `${h}h atrás`
  return `${m}m atrás`
}

function JobCard({ job, onStatusChanged }: {
  job: SavedJobWithStatus
  onStatusChanged: (urlHash: string, newStatus: JobStatus) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const p = job.posting
  const m = job.match

  return (
    <div style={NEUMO_CARD_SM}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const }}>
            <ScoreBadge score={m.score} />
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--neumo-text)' }}>{p.title}</span>
            {job.status !== 'NONE' && (
              <span style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 4,
                background: 'var(--blue-light)', color: 'var(--blue-primary)',
                border: '1px solid var(--blue-border)',
              }}>
                {STATUS_LABELS[job.status]}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--neumo-text-s)', marginTop: 3 }}>
            {p.company} · {p.location}
            {p.salary_range && <span> · {p.salary_range}</span>}
            <span style={{ marginLeft: 8, opacity: 0.7 }}>{timeAgo(job.found_at)}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--neumo-text-s)', marginTop: 2, opacity: 0.8 }}>
            via: {job.found_via}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          <button
            onClick={() => setExpanded(v => !v)}
            style={{ fontSize: 12, color: 'var(--blue-primary)', background: 'none', border: 'none', cursor: 'pointer', padding: 0, fontWeight: 600 }}
          >
            {expanded ? 'fechar' : 'ver mais'}
          </button>
          <JobStatusMenu job={job} onStatusChanged={onStatusChanged} />
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--blue-border)' }}>
          <p style={{ fontSize: 12, color: 'var(--neumo-text-s)', whiteSpace: 'pre-wrap', margin: '0 0 10px' }}>
            {p.description.slice(0, 600)}{p.description.length > 600 ? '…' : ''}
          </p>
          {m.keywords_found.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--color-success)', fontWeight: 600 }}>Match: </span>
              {m.keywords_found.map(k => (
                <span key={k} style={{ fontSize: 11, padding: '1px 5px', borderRadius: 4, background: 'rgba(34,197,94,0.12)', color: 'var(--color-success)', marginRight: 4 }}>{k}</span>
              ))}
            </div>
          )}
          <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--blue-primary)', fontWeight: 600 }}>
            Ver vaga ↗
          </a>
          <ApplicationGenerator job={p} match={m} />
        </div>
      )}
    </div>
  )
}

function Pagination({ page, totalPages, onChange }: { page: number; totalPages: number; onChange: (p: number) => void }) {
  if (totalPages <= 1) return null
  const pages = Array.from({ length: Math.min(totalPages, 7) }, (_, i) => {
    if (totalPages <= 7) return i + 1
    if (i === 0) return 1
    if (i === 6) return totalPages
    return page + i - 3
  }).filter(p => p >= 1 && p <= totalPages)

  const pageBtn = (active: boolean): React.CSSProperties => ({
    padding: '4px 10px', borderRadius: 8, fontSize: 13, cursor: 'pointer',
    border: 'none',
    background: active ? 'var(--blue-primary)' : 'var(--neumo-bg)',
    color: active ? 'white' : 'var(--neumo-text)',
    boxShadow: 'var(--neumo-raised-sm)',
    fontWeight: active ? 700 : 400,
  })

  return (
    <div style={{ display: 'flex', justifyContent: 'center', gap: 4, marginTop: 16 }}>
      <button onClick={() => onChange(page - 1)} disabled={page <= 1} style={pageBtn(false)}>‹</button>
      {pages.map(p => (
        <button key={p} onClick={() => onChange(p)} style={pageBtn(p === page)}>{p}</button>
      ))}
      <button onClick={() => onChange(page + 1)} disabled={page >= totalPages} style={pageBtn(false)}>›</button>
    </div>
  )
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

// ── Main component ─────────────────────────────────────────────────────────

export function AutoSearchPage({ onBack }: Props) {
  const [config, setConfig] = useState<AutoSearchConfig | null>(null)
  const [tab, setTab] = useState<Tab>('new')
  const [sort, setSort] = useState<'score' | 'recent'>('score')
  const [page, setPage] = useState(1)
  const [resultsPage, setResultsPage] = useState<AutoSearchResultsPage | null>(null)
  const [loading, setLoading] = useState(false)
  const [running, setRunning] = useState(false)
  const [runProgress, setRunProgress] = useState('')
  const [runResult, setRunResult] = useState<{ ok: boolean; msg: string } | null>(null)
  const [showCleanup, setShowCleanup] = useState(false)
  const [cleanupOpts, setCleanupOpts] = useState({ remove_not_interested: false, remove_unavailable: false })
  const [cleanupMsg, setCleanupMsg] = useState('')

  const mountedRef = useRef(true)
  useEffect(() => {
    mountedRef.current = true
    return () => { mountedRef.current = false }
  }, [])

  const pageSize = config?.page_size ?? 10

  useEffect(() => {
    getAutoSearchConfig().then(setConfig).catch(console.error)
  }, [])

  useEffect(() => {
    if (tab === 'new') markAutoSearchSeen().catch(() => {})
  }, [tab])

  useEffect(() => {
    if (!config) return
    loadResults()
  }, [tab, page, sort, config])

  async function loadResults() {
    setLoading(true)
    try {
      const res = await getAutoSearchResults(page, pageSize, TAB_FILTERS[tab], sort)
      setResultsPage(res)
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  function handleTabChange(t: Tab) {
    setTab(t)
    setPage(1)
    setResultsPage(null)
  }

  function handleStatusChanged(urlHash: string, _newStatus: JobStatus) {
    setResultsPage(prev => {
      if (!prev) return prev
      return { ...prev, jobs: prev.jobs.filter(j => j.url_hash !== urlHash) }
    })
  }

  async function handleRunNow() {
    if (!mountedRef.current) return
    setRunning(true)
    setRunResult(null)
    setRunProgress('Iniciando busca…')
    try {
      const { job_id } = await triggerAutoSearchRun()
      let lastStatus = 'processing'
      let lastMessage = ''
      while (mountedRef.current) {
        const status = await getIngestStatus(job_id)
        if (!mountedRef.current) break
        setRunProgress(status.message)
        lastStatus = status.status
        lastMessage = status.message
        if (status.status !== 'processing') break
        await sleep(1500)
      }
      if (mountedRef.current) {
        await loadResults()
        if (lastStatus === 'completed') {
          setRunResult({ ok: true, msg: lastMessage || 'Busca concluída!' })
        } else if (lastStatus === 'failed') {
          setRunResult({ ok: false, msg: lastMessage || 'Busca falhou.' })
        }
      }
    } catch (err: unknown) {
      if (mountedRef.current) {
        const msg = err instanceof Error ? err.message : 'Erro ao executar busca.'
        setRunResult({ ok: false, msg })
      }
    } finally {
      if (mountedRef.current) {
        setRunning(false)
        setRunProgress('')
      }
    }
  }

  async function handleCleanup() {
    try {
      const result = await cleanupAutoSearch(cleanupOpts)
      setCleanupMsg(`${result.removed} vagas removidas.`)
      setShowCleanup(false)
      setPage(1)
      await loadResults()
    } catch {
      setCleanupMsg('Erro ao limpar.')
    }
  }

  const TAB_LABELS: Record<Tab, string> = {
    new: 'Novas vagas',
    pipeline: 'Pipeline',
    not_interested: 'Sem interesse',
  }

  return (
    <div style={PAGE_BG}>
      <div style={CONTENT_WRAP}>

        {/* Header panel */}
        <div style={NEUMO_PANEL}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 8, flexWrap: 'wrap' as const }}>
            <div>
              <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--neumo-text)' }}>⚡ Auto Busca de Vagas</h2>
              {config && (
                <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--neumo-text-s)' }}>
                  {config.enabled ? `Busca a cada ${config.interval_hours}h` : 'Busca desativada'}
                </p>
              )}
            </div>
            <div style={{ display: 'flex', gap: 8 }}>
              <button
                onClick={handleRunNow}
                disabled={running}
                style={{ ...BTN_PRIMARY, opacity: running ? 0.6 : 1, cursor: running ? 'default' : 'pointer' }}
                onMouseDown={e => { if (!running) e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
                onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
              >
                {running ? '🔄 Buscando…' : '▶ Buscar agora'}
              </button>
              <button
                onClick={onBack}
                style={BTN_GHOST}
                onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
                onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
              >
                ← Voltar
              </button>
            </div>
          </div>
        </div>

        {/* Run status */}
        {running && runProgress && (
          <p style={{ fontSize: 12, color: 'var(--blue-primary)', marginBottom: 12 }}>{runProgress}</p>
        )}
        {!running && runResult && (
          <p style={{ fontSize: 12, color: runResult.ok ? 'var(--blue-primary)' : 'var(--color-error)', marginBottom: 12 }}>
            {runResult.msg}
          </p>
        )}

        {/* Config panel */}
        {config && (
          <AutoSearchConfigPanel
            config={config}
            onSaved={updated => { setConfig(updated); setPage(1) }}
          />
        )}

        {/* Tab bar */}
        <div style={{ display: 'flex', borderBottom: '2px solid var(--blue-border)', marginBottom: 14, gap: 0 }}>
          {(['new', 'pipeline', 'not_interested'] as Tab[]).map(t => (
            <button
              key={t}
              onClick={() => handleTabChange(t)}
              style={{
                padding: '8px 16px', fontSize: 13, fontWeight: tab === t ? 700 : 400,
                background: 'var(--neumo-bg)', border: 'none', cursor: 'pointer',
                borderBottom: tab === t ? '2px solid var(--blue-primary)' : '2px solid transparent',
                color: tab === t ? 'var(--blue-primary)' : 'var(--neumo-text-s)',
                marginBottom: -2,
                boxShadow: tab === t ? 'var(--neumo-raised-sm)' : 'none',
                borderRadius: '8px 8px 0 0',
              }}
            >
              {TAB_LABELS[t]}
            </button>
          ))}
        </div>

        {/* Results controls */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
          <span style={{ fontSize: 12, color: 'var(--neumo-text-s)' }}>
            {resultsPage ? `${resultsPage.total} vagas · pág ${resultsPage.page}/${resultsPage.total_pages}` : '…'}
          </span>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            <select
              value={sort}
              onChange={e => { setSort(e.target.value as 'score' | 'recent'); setPage(1) }}
              style={{
                padding: '4px 8px', borderRadius: 8, border: 'none', fontSize: 12,
                background: 'var(--neumo-bg)', color: 'var(--neumo-text)',
                boxShadow: 'var(--neumo-inset)', cursor: 'pointer',
              }}
            >
              <option value="score">Score ↓</option>
              <option value="recent">Mais recentes</option>
            </select>
            <button
              onClick={() => setShowCleanup(true)}
              style={BTN_GHOST}
              onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
              onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
              onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            >
              🧹 Limpar
            </button>
          </div>
        </div>

        {/* Results */}
        {loading && <p style={{ fontSize: 13, color: 'var(--neumo-text-s)' }}>Carregando…</p>}
        {!loading && resultsPage?.jobs.length === 0 && (
          <div style={{ ...NEUMO_PANEL, textAlign: 'center' as const, padding: '40px 20px' }}>
            <p style={{ fontSize: 14, color: 'var(--neumo-text-s)', margin: '0 0 4px' }}>Nenhuma vaga nesta aba.</p>
            {tab === 'new' && (
              <p style={{ fontSize: 12, color: 'var(--neumo-text-s)', margin: 0 }}>Clique em "Buscar agora" para atualizar.</p>
            )}
          </div>
        )}
        {!loading && resultsPage?.jobs.map(job => (
          <JobCard
            key={job.url_hash}
            job={job}
            onStatusChanged={handleStatusChanged}
          />
        ))}

        {resultsPage && (
          <Pagination page={page} totalPages={resultsPage.total_pages} onChange={setPage} />
        )}

        {cleanupMsg && (
          <p style={{ fontSize: 12, color: 'var(--blue-primary)', marginTop: 8 }}>{cleanupMsg}</p>
        )}

        {/* Cleanup modal */}
        {showCleanup && (
          <div style={{
            position: 'fixed' as const, inset: 0,
            background: 'rgba(30, 77, 158, 0.18)',
            backdropFilter: 'var(--glass-blur)',
            WebkitBackdropFilter: 'var(--glass-blur)',
            zIndex: 200,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
          }}>
            <div style={{
              background: 'var(--neumo-bg)',
              boxShadow: 'var(--neumo-raised)',
              borderRadius: 16,
              padding: '20px 24px', minWidth: 320, maxWidth: 400,
            }}>
              <h3 style={{ margin: '0 0 14px', fontSize: 15, color: 'var(--neumo-text)', fontWeight: 700 }}>🧹 Limpar vagas</h3>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, fontSize: 13, color: 'var(--neumo-text)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={cleanupOpts.remove_not_interested}
                  onChange={e => setCleanupOpts(o => ({ ...o, remove_not_interested: e.target.checked }))}
                />
                Remover vagas marcadas como "Sem interesse"
              </label>
              <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16, fontSize: 13, color: 'var(--neumo-text)', cursor: 'pointer' }}>
                <input
                  type="checkbox"
                  checked={cleanupOpts.remove_unavailable}
                  onChange={e => setCleanupOpts(o => ({ ...o, remove_unavailable: e.target.checked }))}
                />
                Remover vagas que não aparecem mais nas buscas
              </label>
              <div style={{ display: 'flex', gap: 8 }}>
                <button
                  onClick={handleCleanup}
                  style={BTN_DANGER}
                  onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
                  onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                  onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                >
                  Limpar
                </button>
                <button
                  onClick={() => setShowCleanup(false)}
                  style={BTN_GHOST}
                  onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
                  onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                  onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
                >
                  Cancelar
                </button>
              </div>
            </div>
          </div>
        )}

      </div>
    </div>
  )
}
