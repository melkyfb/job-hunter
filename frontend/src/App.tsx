import { useCallback, useEffect, useRef, useState } from 'react'
import { getProfile, getAutoSearchSummary, updateConfig, type ProfileMaster } from './api/client'
import { loadConfig, configIsComplete } from './store/appConfig'
import { IngestPage } from './pages/IngestPage'
import { JobSearchPage } from './pages/JobSearchPage'
import { AutoSearchPage } from './pages/AutoSearchPage'
import { ProfilePage } from './pages/ProfilePage'
import { SettingsPage } from './pages/SettingsPage'

type AppState = 'loading' | 'no_profile' | 'has_profile' | 'job_search' | 'auto_search' | 'settings'

export default function App() {
  const [appState, setAppState] = useState<AppState>('loading')
  const [profile, setProfile] = useState<ProfileMaster | null>(null)
  const [autoSearchBadge, setAutoSearchBadge] = useState(0)
  const [configComplete, setConfigComplete] = useState(true)
  const prevStateRef = useRef<AppState>('loading')

  // Push stored config to backend on startup
  useEffect(() => {
    async function bootConfig() {
      try {
        const cfg = await loadConfig()
        setConfigComplete(configIsComplete(cfg))
        await updateConfig({
          llm_provider: cfg.llmProvider === 'ollama' || cfg.llmProvider === 'lmstudio' || cfg.llmProvider === 'compatible' ? 'local' : cfg.llmProvider,
          llm_model: cfg.llmModel,
          llm_base_url: cfg.llmBaseUrl || undefined,
          llm_api_key: cfg.llmApiKey || undefined,
          llm_temperature: cfg.llmTemperature,
          adzuna_app_id: cfg.adzunaAppId || undefined,
          adzuna_api_key: cfg.adzunaApiKey || undefined,
          adzuna_country: cfg.adzunaCountry,
          search_provider: cfg.adzunaAppId && cfg.adzunaApiKey ? 'adzuna' : 'mock',
          cv_prompt: cfg.cvPrompt || undefined,
          cl_prompt: cfg.clPrompt || undefined,
          cv_language: cfg.cvLanguage,
          cl_language: cfg.clLanguage,
        })
      } catch {
        // Backend not yet ready — ignore (sidecar may still be starting)
      }
    }
    bootConfig()
  }, [])

  useEffect(() => {
    async function checkSummary() {
      try {
        const summary = await getAutoSearchSummary()
        setAutoSearchBadge(summary.new_count)
      } catch { /* silently ignore */ }
    }
    checkSummary()
    const id = setInterval(checkSummary, 60_000)
    return () => clearInterval(id)
  }, [])

  function handleAutoSearch() {
    setAutoSearchBadge(0)
    setAppState('auto_search')
  }

  const loadProfile = useCallback(() => {
    return getProfile().then(p => { setProfile(p); setAppState('has_profile') })
  }, [])

  useEffect(() => {
    loadProfile().catch(() => setAppState('no_profile'))
  }, [loadProfile])

  function goToSettings() {
    prevStateRef.current = appState
    setAppState('settings')
  }

  function backFromSettings() {
    // After saving config, re-check completeness
    loadConfig().then(cfg => setConfigComplete(configIsComplete(cfg)))
    setAppState(prevStateRef.current === 'settings' ? 'no_profile' : prevStateRef.current)
  }

  if (appState === 'settings') {
    return <SettingsPage onBack={backFromSettings} />
  }

  if (appState === 'loading') {
    return <p style={{ padding: 32, color: 'var(--neumo-text)' }}>Loading…</p>
  }

  if (appState === 'no_profile') {
    return <IngestPage onProfileReady={() => loadProfile()} onOpenSettings={goToSettings} configComplete={configComplete} />
  }

  if (appState === 'job_search') {
    return (
      <JobSearchPage
        onBack={() => setAppState('has_profile')}
        suggestions={profile?.job_suggestions ?? []}
      />
    )
  }

  if (appState === 'auto_search') {
    return <AutoSearchPage onBack={() => setAppState('has_profile')} />
  }

  return profile ? (
    <ProfilePage
      profile={profile}
      onSearchJobs={() => setAppState('job_search')}
      onAutoSearch={handleAutoSearch}
      onReimport={() => setAppState('no_profile')}
      onProfileUpdated={p => setProfile(p)}
      autoSearchBadge={autoSearchBadge}
      onOpenSettings={goToSettings}
    />
  ) : null
}
