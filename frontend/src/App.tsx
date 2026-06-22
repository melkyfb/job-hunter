import { useEffect, useState } from 'react'
import { getProfile, getAutoSearchSummary, type ProfileMaster } from './api/client'
import { IngestPage } from './pages/IngestPage'
import { JobSearchPage } from './pages/JobSearchPage'
import { AutoSearchPage } from './pages/AutoSearchPage'
import { ProfilePage } from './pages/ProfilePage'
import { ThemeToggle } from './components/ThemeToggle'

type AppState = 'loading' | 'no_profile' | 'has_profile' | 'job_search' | 'auto_search'

function TopBar() {
  return (
    <div style={{ position: 'fixed', top: 12, right: 16, zIndex: 100 }}>
      <ThemeToggle />
    </div>
  )
}

export default function App() {
  const [appState, setAppState] = useState<AppState>('loading')
  const [profile, setProfile] = useState<ProfileMaster | null>(null)
  const [autoSearchBadge, setAutoSearchBadge] = useState(0)

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

  function loadProfile() {
    return getProfile().then(p => { setProfile(p); setAppState('has_profile') })
  }

  useEffect(() => {
    loadProfile().catch(() => setAppState('no_profile'))
  }, [])

  if (appState === 'loading') {
    return (
      <>
        <TopBar />
        <p style={{ padding: 32, color: 'var(--text)' }}>Loading…</p>
      </>
    )
  }

  if (appState === 'no_profile') {
    return (
      <>
        <TopBar />
        <main style={{ padding: '2rem' }}>
          <IngestPage onProfileReady={() => loadProfile()} />
        </main>
      </>
    )
  }

  if (appState === 'job_search') {
    return (
      <>
        <TopBar />
        <main style={{ padding: '2rem' }}>
          <JobSearchPage
            onBack={() => setAppState('has_profile')}
            suggestions={profile?.job_suggestions ?? []}
            designs={profile?.design_versions ?? []}
          />
        </main>
      </>
    )
  }

  if (appState === 'auto_search') {
    return (
      <>
        <TopBar />
        <main style={{ padding: '2rem' }}>
          <AutoSearchPage onBack={() => setAppState('has_profile')} designs={profile?.design_versions ?? []} />
        </main>
      </>
    )
  }

  return (
    <>
      <TopBar />
      <main style={{ padding: '2rem' }}>
        {profile && (
          <ProfilePage
            profile={profile}
            onSearchJobs={() => setAppState('job_search')}
            onAutoSearch={handleAutoSearch}
            onReimport={() => setAppState('no_profile')}
            onProfileUpdated={p => setProfile(p)}
            autoSearchBadge={autoSearchBadge}
          />
        )}
      </main>
    </>
  )
}
