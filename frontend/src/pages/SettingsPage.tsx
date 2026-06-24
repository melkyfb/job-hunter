// frontend/src/pages/SettingsPage.tsx
import { useEffect, useState } from 'react'
import { loadConfig, saveConfig, DEFAULT_CONFIG, type AppConfig, type LLMProvider } from '../store/appConfig'
import { updateConfig } from '../api/client'

interface Props {
  onBack: () => void
}

const PAGE_BG: React.CSSProperties = {
  background: 'var(--blue-gradient)',
  minHeight: '100svh',
  padding: '32px 24px',
  colorScheme: 'light' as const,
  overflowY: 'auto' as const,
}

const NEUMO_PANEL: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '24px 28px',
  marginBottom: 20,
}

const NEUMO_INSET: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-inset)',
  border: 'none',
  borderRadius: 10,
  padding: '9px 14px',
  fontSize: 14,
  color: 'var(--neumo-text)',
  width: '100%',
  boxSizing: 'border-box' as const,
  fontFamily: 'inherit',
}

const SECTION_TITLE: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 800,
  textTransform: 'uppercase' as const,
  letterSpacing: '0.8px',
  color: 'var(--blue-primary)',
  borderBottom: '2px solid var(--blue-border)',
  paddingBottom: 6,
  marginBottom: 16,
  marginTop: 0,
}

const LABEL: React.CSSProperties = {
  fontSize: 12,
  fontWeight: 600,
  color: 'var(--neumo-text-s)',
  marginBottom: 4,
  display: 'block',
}

const FIELD: React.CSSProperties = { marginBottom: 14 }

const HELP_LINK: React.CSSProperties = {
  fontSize: 11,
  color: 'var(--blue-primary)',
  marginTop: 4,
  display: 'block',
}

const BTN_PRIMARY: React.CSSProperties = {
  padding: '10px 24px',
  background: 'var(--blue-primary)',
  color: 'white',
  border: 'none',
  borderRadius: 10,
  fontWeight: 700,
  cursor: 'pointer',
  fontSize: 14,
  boxShadow: 'var(--neumo-raised-sm)',
}

const BTN_GHOST: React.CSSProperties = {
  padding: '10px 20px',
  background: 'var(--neumo-bg)',
  color: 'var(--neumo-text)',
  border: 'none',
  borderRadius: 10,
  fontWeight: 700,
  cursor: 'pointer',
  fontSize: 14,
  boxShadow: 'var(--neumo-raised-sm)',
}

const PROVIDER_LINKS: Record<LLMProvider, { label: string; url: string }> = {
  openai: { label: 'Get API key at platform.openai.com', url: 'https://platform.openai.com/api-keys' },
  ollama: { label: 'Download Ollama at ollama.ai', url: 'https://ollama.ai' },
  lmstudio: { label: 'Download LM Studio at lmstudio.ai', url: 'https://lmstudio.ai' },
  groq: { label: 'Get API key at console.groq.com', url: 'https://console.groq.com/keys' },
  mistral: { label: 'Get API key at console.mistral.ai', url: 'https://console.mistral.ai/api-keys' },
  compatible: { label: 'Any OpenAI-compatible endpoint', url: 'https://platform.openai.com/docs/api-reference' },
}

const PROVIDER_DEFAULT_MODELS: Record<LLMProvider, string> = {
  openai: 'gpt-4o-mini',
  ollama: 'llama3.2',
  lmstudio: 'local-model',
  groq: 'llama-3.1-70b-versatile',
  mistral: 'mistral-small-latest',
  compatible: 'local-model',
}

const PROVIDER_DEFAULT_URLS: Record<LLMProvider, string> = {
  openai: '',
  ollama: 'http://localhost:11434/v1',
  lmstudio: 'http://localhost:1234/v1',
  groq: 'https://api.groq.com/openai/v1',
  mistral: 'https://api.mistral.ai/v1',
  compatible: 'http://localhost:8080/v1',
}

const LANGUAGES = [
  'English', 'Português', 'Deutsch', 'Español', 'Français', 'Italiano',
  'Nederlands', 'Polski', 'Svenska', 'Norsk', 'Dansk', 'Suomi',
  'Čeština', 'Magyar', 'Română', 'Slovenčina', 'Hrvatski', 'Srpski',
  'Türkçe', '日本語', '中文（简体）', '中文（繁體）', '한국어', 'العربية',
  'हिन्दी', 'Русский', 'Українська', 'Bahasa Indonesia', 'Bahasa Melayu', 'Tiếng Việt',
]

const ADZUNA_COUNTRIES = [
  { code: 'de', label: 'Germany (DE)' },
  { code: 'gb', label: 'United Kingdom (GB)' },
  { code: 'us', label: 'United States (US)' },
  { code: 'au', label: 'Australia (AU)' },
  { code: 'ca', label: 'Canada (CA)' },
  { code: 'at', label: 'Austria (AT)' },
  { code: 'be', label: 'Belgium (BE)' },
  { code: 'br', label: 'Brazil (BR)' },
  { code: 'fr', label: 'France (FR)' },
  { code: 'in', label: 'India (IN)' },
  { code: 'it', label: 'Italy (IT)' },
  { code: 'mx', label: 'Mexico (MX)' },
  { code: 'nl', label: 'Netherlands (NL)' },
  { code: 'nz', label: 'New Zealand (NZ)' },
  { code: 'pl', label: 'Poland (PL)' },
  { code: 'ru', label: 'Russia (RU)' },
  { code: 'sg', label: 'Singapore (SG)' },
  { code: 'za', label: 'South Africa (ZA)' },
]

export function SettingsPage({ onBack }: Props) {
  const [cfg, setCfg] = useState<AppConfig>(DEFAULT_CONFIG)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    loadConfig().then(setCfg)
  }, [])

  function set<K extends keyof AppConfig>(key: K, value: AppConfig[K]) {
    setCfg(prev => ({ ...prev, [key]: value }))
  }

  function handleProviderChange(provider: LLMProvider) {
    setCfg(prev => ({
      ...prev,
      llmProvider: provider,
      llmModel: PROVIDER_DEFAULT_MODELS[provider],
      llmBaseUrl: PROVIDER_DEFAULT_URLS[provider],
    }))
  }

  async function handleSave() {
    setSaving(true)
    try {
      await saveConfig(cfg)
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
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } finally {
      setSaving(false)
    }
  }

  const providerLink = PROVIDER_LINKS[cfg.llmProvider]
  const needsApiKey = cfg.llmProvider === 'openai' || cfg.llmProvider === 'groq' || cfg.llmProvider === 'mistral'
  const needsUrl = cfg.llmProvider !== 'openai'

  return (
    <div style={PAGE_BG}>
      <div style={{ maxWidth: 680, margin: '0 auto' }}>

        {/* Header */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 24 }}>
          <button
            onClick={onBack}
            style={BTN_GHOST}
            onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            ← Back
          </button>
          <h1 style={{ margin: 0, fontSize: 22, color: 'var(--neumo-text)', fontWeight: 700 }}>Settings</h1>
        </div>

        {/* LLM Provider */}
        <div style={NEUMO_PANEL}>
          <p style={SECTION_TITLE}>LLM Provider</p>
          <div style={FIELD}>
            <label style={LABEL}>Provider</label>
            <select
              value={cfg.llmProvider}
              onChange={e => handleProviderChange(e.target.value as LLMProvider)}
              style={NEUMO_INSET}
            >
              <option value="ollama">Ollama (local)</option>
              <option value="lmstudio">LM Studio (local)</option>
              <option value="openai">OpenAI</option>
              <option value="groq">Groq</option>
              <option value="mistral">Mistral</option>
              <option value="compatible">OpenAI-compatible</option>
            </select>
            <a href={providerLink.url} target="_blank" rel="noreferrer" style={HELP_LINK}>
              ↗ {providerLink.label}
            </a>
          </div>
          {needsApiKey && (
            <div style={FIELD}>
              <label style={LABEL}>API Key</label>
              <input
                type="password"
                value={cfg.llmApiKey}
                onChange={e => set('llmApiKey', e.target.value)}
                placeholder="sk-..."
                style={NEUMO_INSET}
              />
            </div>
          )}
          {needsUrl && (
            <div style={FIELD}>
              <label style={LABEL}>Base URL</label>
              <input
                type="text"
                value={cfg.llmBaseUrl}
                onChange={e => set('llmBaseUrl', e.target.value)}
                placeholder="http://localhost:11434/v1"
                style={NEUMO_INSET}
              />
            </div>
          )}
          <div style={FIELD}>
            <label style={LABEL}>Model</label>
            <input
              type="text"
              value={cfg.llmModel}
              onChange={e => set('llmModel', e.target.value)}
              placeholder="llama3.2"
              style={NEUMO_INSET}
            />
          </div>
        </div>

        {/* Adzuna */}
        <div style={NEUMO_PANEL}>
          <p style={SECTION_TITLE}>Job Search — Adzuna</p>
          <div style={FIELD}>
            <label style={LABEL}>App ID</label>
            <input type="text" value={cfg.adzunaAppId} onChange={e => set('adzunaAppId', e.target.value)} style={NEUMO_INSET} placeholder="xxxxxxxx" />
          </div>
          <div style={FIELD}>
            <label style={LABEL}>API Key</label>
            <input type="password" value={cfg.adzunaApiKey} onChange={e => set('adzunaApiKey', e.target.value)} style={NEUMO_INSET} placeholder="xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx" />
          </div>
          <div style={FIELD}>
            <label style={LABEL}>Country</label>
            <select value={cfg.adzunaCountry} onChange={e => set('adzunaCountry', e.target.value)} style={NEUMO_INSET}>
              {ADZUNA_COUNTRIES.map(c => (
                <option key={c.code} value={c.code}>{c.label}</option>
              ))}
            </select>
          </div>
          <a href="https://developer.adzuna.com/overview" target="_blank" rel="noreferrer" style={HELP_LINK}>
            ↗ Create Adzuna API key at developer.adzuna.com
          </a>
        </div>

        {/* Prompts */}
        <div style={NEUMO_PANEL}>
          <p style={SECTION_TITLE}>Default Prompts</p>
          <div style={FIELD}>
            <label style={LABEL}>CV / Resume Prompt</label>
            <p style={{ fontSize: 11, color: 'var(--neumo-text-s)', margin: '0 0 8px' }}>
              Use <code style={{ background: 'rgba(0,0,0,0.07)', padding: '1px 4px', borderRadius: 3 }}>{'{JOB_DESCRIPTION}'}</code> as placeholder for the job posting.
              Leave empty to use the built-in default.
            </p>
            <textarea
              value={cfg.cvPrompt}
              onChange={e => set('cvPrompt', e.target.value)}
              placeholder="Leave empty to use built-in default prompt..."
              rows={6}
              style={{ ...NEUMO_INSET, resize: 'vertical' as const, lineHeight: 1.5 }}
            />
          </div>
          <div style={FIELD}>
            <label style={LABEL}>Cover Letter Prompt</label>
            <textarea
              value={cfg.clPrompt}
              onChange={e => set('clPrompt', e.target.value)}
              placeholder="Leave empty to use built-in default prompt..."
              rows={6}
              style={{ ...NEUMO_INSET, resize: 'vertical' as const, lineHeight: 1.5 }}
            />
          </div>
        </div>

        {/* Language */}
        <div style={NEUMO_PANEL}>
          <p style={SECTION_TITLE}>Output Language</p>
          <p style={{ fontSize: 12, color: 'var(--neumo-text-s)', marginTop: 0, marginBottom: 16 }}>
            The LLM will generate the CV and cover letter in the selected language.
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            <div style={FIELD}>
              <label style={LABEL}>CV / Resume Language</label>
              <select value={cfg.cvLanguage} onChange={e => set('cvLanguage', e.target.value)} style={NEUMO_INSET}>
                {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
            <div style={FIELD}>
              <label style={LABEL}>Cover Letter Language</label>
              <select value={cfg.clLanguage} onChange={e => set('clLanguage', e.target.value)} style={NEUMO_INSET}>
                {LANGUAGES.map(l => <option key={l} value={l}>{l}</option>)}
              </select>
            </div>
          </div>
        </div>

        {/* Save */}
        <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{ ...BTN_PRIMARY, opacity: saving ? 0.7 : 1 }}
            onMouseDown={e => { if (!saving) e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            {saving ? 'Saving…' : 'Save Settings'}
          </button>
          {saved && <span style={{ fontSize: 13, color: 'var(--color-success)', fontWeight: 600 }}>✓ Saved</span>}
        </div>

      </div>
    </div>
  )
}
