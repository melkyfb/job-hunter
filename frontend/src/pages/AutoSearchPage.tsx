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

function ScoreBadge({ score }: { score: number }) {
  const bg = score >= 75 ? '#22c55e' : score >= 50 ? '#f59e0b' : '#ef4444'
  return (
    <span style={{
      display: 'inline-block', minWidth: 36, textAlign: 'center',
      padding: '2px 8px', borderRadius: 12, fontSize: 12, fontWeight: 700,
      color: 'white', background: bg,
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
    <div style={{ border: '1px solid var(--border)', borderRadius: 10, padding: '12px 14px', marginBottom: 8, background: 'var(--bg)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
            <ScoreBadge score={m.score} />
            <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-h)' }}>{p.title}</span>
            {job.status !== 'NONE' && (
              <span style={{
                fontSize: 10, padding: '1px 6px', borderRadius: 4,
                background: 'var(--accent-bg)', color: 'var(--accent)',
                border: '1px solid var(--accent-border)',
              }}>
                {STATUS_LABELS[job.status]}
              </span>
            )}
          </div>
          <div style={{ fontSize: 12, color: 'var(--text)', marginTop: 3 }}>
            {p.company} · {p.location}
            {p.salary_range && <span> · {p.salary_range}</span>}
            <span style={{ marginLeft: 8, color: 'var(--text)', opacity: 0.7 }}>{timeAgo(job.found_at)}</span>
          </div>
          <div style={{ fontSize: 11, color: 'var(--text)', marginTop: 2, opacity: 0.8 }}>
            via: {job.found_via}
          </div>
        </div>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0 }}>
          <button
            onClick={() => setExpanded(v => !v)}
            style={{ fontSize: 12, color: 'var(--accent)', background: 'none', border: 'none', cursor: 'pointer', padding: 0 }}
          >
            {expanded ? 'fechar' : 'ver mais'}
          </button>
          <JobStatusMenu job={job} onStatusChanged={onStatusChanged} />
        </div>
      </div>

      {expanded && (
        <div style={{ marginTop: 10, paddingTop: 10, borderTop: '1px solid var(--border)' }}>
          <p style={{ fontSize: 12, color: 'var(--text)', whiteSpace: 'pre-wrap', margin: '0 0 10px' }}>
            {p.description.slice(0, 600)}{p.description.length > 600 ? '…' : ''}
          </p>
          {m.keywords_found.length > 0 && (
            <div style={{ marginBottom: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--text)', fontWeight: 600 }}>Match: </span>
              {m.keywords_found.map(k => (
                <span key={k} style={{ fontSize: 11, padding: '1px 5px', borderRadius: 4, background: 'rgba(34,197,94,0.12)', color: '#16a34a', marginRight: 4 }}>{k}</span>
              ))}
            </div>
          )}
          <a href={p.url} target="_blank" rel="noopener noreferrer" style={{ fontSize: 12, color: 'var(--accent)' }}>
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

function pageBtn(active: boolean): React.CSSProperties {
  return {
    padding: '4px 10px', borderRadius: 5, fontSize: 13, cursor: 'pointer',
    border: `1px solid ${active ? 'var(--accent)' : 'var(--border)'}`,
    background: active ? 'var(--accent)' : 'var(--bg)',
    color: active ? 'white' : 'var(--text-h)',
  }
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

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

  return (
    <div style={{ maxWidth: 800, margin: '0 auto', padding: '24px 16px' }}>

      {/* Header */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 12 }}>
        <div>
          <h2 style={{ margin: 0, fontSize: 18, fontWeight: 700, color: 'var(--text-h)' }}>⚡ Auto Busca de Vagas</h2>
          {config && (
            <p style={{ margin: '2px 0 0', fontSize: 12, color: 'var(--text)' }}>
              {config.enabled ? `Busca a cada ${config.interval_hours}h` : 'Busca desativada'}
            </p>
          )}
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button
            onClick={handleRunNow}
            disabled={running}
            style={{
              padding: '7px 14px', background: running ? 'var(--border)' : 'var(--accent)',
              color: 'white', border: 'none', borderRadius: 7, fontWeight: 600,
              cursor: running ? 'default' : 'pointer', fontSize: 13,
            }}
          >
            {running ? '🔄 Buscando…' : '▶ Buscar agora'}
          </button>
          <button onClick={onBack} style={{ padding: '7px 14px', background: 'none', border: '1px solid var(--border)', borderRadius: 7, cursor: 'pointer', fontSize: 13, color: 'var(--text)' }}>
            ← Voltar
          </button>
        </div>
      </div>

      {running && runProgress && (
        <p style={{ fontSize: 12, color: 'var(--accent)', marginBottom: 12 }}>{runProgress}</p>
      )}
      {!running && runResult && (
        <p style={{ fontSize: 12, color: runResult.ok ? 'var(--accent)' : '#ef4444', marginBottom: 12 }}>
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

      {/* Tabs */}
      <div style={{ display: 'flex', borderBottom: '1px solid var(--border)', marginBottom: 14, gap: 0 }}>
        {(['new', 'pipeline', 'not_interested'] as Tab[]).map(t => {
          const labels: Record<Tab, string> = {
            new: 'Novas vagas',
            pipeline: 'Pipeline',
            not_interested: 'Sem interesse',
          }
          return (
            <button
              key={t}
              onClick={() => handleTabChange(t)}
              style={{
                padding: '8px 16px', fontSize: 13, fontWeight: tab === t ? 700 : 400,
                background: 'none', border: 'none', cursor: 'pointer',
                borderBottom: tab === t ? '2px solid var(--accent)' : '2px solid transparent',
                color: tab === t ? 'var(--accent)' : 'var(--text)',
                marginBottom: -1,
              }}
            >
              {labels[t]}
            </button>
          )
        })}
      </div>

      {/* Results controls */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 10 }}>
        <span style={{ fontSize: 12, color: 'var(--text)' }}>
          {resultsPage ? `${resultsPage.total} vagas · pág ${resultsPage.page}/${resultsPage.total_pages}` : '…'}
        </span>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
          <select
            value={sort}
            onChange={e => { setSort(e.target.value as 'score' | 'recent'); setPage(1) }}
            style={{ padding: '4px 8px', borderRadius: 5, border: '1px solid var(--border)', fontSize: 12, background: 'var(--bg)', color: 'var(--text-h)' }}
          >
            <option value="score">Score ↓</option>
            <option value="recent">Mais recentes</option>
          </select>
          <button
            onClick={() => setShowCleanup(true)}
            style={{ fontSize: 12, background: 'none', border: '1px solid var(--border)', borderRadius: 5, padding: '4px 10px', cursor: 'pointer', color: 'var(--text)' }}
          >
            🧹 Limpar
          </button>
        </div>
      </div>

      {/* Results */}
      {loading && <p style={{ fontSize: 13, color: 'var(--text)' }}>Carregando…</p>}
      {!loading && resultsPage?.jobs.length === 0 && (
        <div style={{ padding: '40px 0', textAlign: 'center', color: 'var(--text)' }}>
          <p style={{ fontSize: 14 }}>Nenhuma vaga nesta aba.</p>
          {tab === 'new' && (
            <p style={{ fontSize: 12 }}>Clique em "Buscar agora" para atualizar.</p>
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
        <p style={{ fontSize: 12, color: 'var(--accent)', marginTop: 8 }}>{cleanupMsg}</p>
      )}

      {/* Cleanup modal */}
      {showCleanup && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.4)', zIndex: 200,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
        }}>
          <div style={{
            background: 'var(--bg)', border: '1px solid var(--border)', borderRadius: 10,
            padding: '20px 24px', minWidth: 320, maxWidth: 400,
          }}>
            <h3 style={{ margin: '0 0 14px', fontSize: 15, color: 'var(--text-h)' }}>🧹 Limpar vagas</h3>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 10, fontSize: 13, color: 'var(--text)' }}>
              <input
                type="checkbox"
                checked={cleanupOpts.remove_not_interested}
                onChange={e => setCleanupOpts(o => ({ ...o, remove_not_interested: e.target.checked }))}
              />
              Remover vagas marcadas como "Sem interesse"
            </label>
            <label style={{ display: 'flex', gap: 8, alignItems: 'center', marginBottom: 16, fontSize: 13, color: 'var(--text)' }}>
              <input
                type="checkbox"
                checked={cleanupOpts.remove_unavailable}
                onChange={e => setCleanupOpts(o => ({ ...o, remove_unavailable: e.target.checked }))}
              />
              Remover vagas que não aparecem mais nas buscas
            </label>
            <div style={{ display: 'flex', gap: 8 }}>
              <button onClick={handleCleanup} style={{ padding: '7px 16px', background: '#ef4444', color: 'white', border: 'none', borderRadius: 6, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
                Limpar
              </button>
              <button onClick={() => setShowCleanup(false)} style={{ padding: '7px 12px', background: 'none', border: '1px solid var(--border)', borderRadius: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text)' }}>
                Cancelar
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
