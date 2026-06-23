import { useState } from 'react'
import { downloadMasterResume, updatePrompts, type ProfileMaster, type WorkExperience, type Skill } from '../api/client'
import { DEFAULT_CV_PROMPT, DEFAULT_CL_PROMPT } from '../constants/promptDefaults'

interface Props {
  profile: ProfileMaster
  onSearchJobs: () => void
  onAutoSearch: () => void
  onReimport: () => void
  onProfileUpdated: (p: ProfileMaster) => void
  autoSearchBadge?: number
}

// ── Style constants ────────────────────────────────────────────────────────
const PAGE_BG: React.CSSProperties = {
  background: 'var(--blue-gradient)',
  minHeight: '100svh',
  padding: '0 0 48px',
  colorScheme: 'light' as const,
}

const ACTION_BAR: React.CSSProperties = {
  position: 'sticky',
  top: 0,
  zIndex: 50,
  background: 'var(--glass-bg)',
  backdropFilter: 'var(--glass-blur)',
  WebkitBackdropFilter: 'var(--glass-blur)',
  borderBottom: '1px solid var(--glass-border)',
  boxShadow: 'var(--glass-shadow)',
  willChange: 'transform',
  padding: '10px 24px',
  display: 'flex',
  gap: 8,
  alignItems: 'center',
  flexWrap: 'wrap' as const,
}

const CONTENT_WRAP: React.CSSProperties = {
  maxWidth: 720,
  margin: '28px auto',
  padding: '0 24px',
}

const NEUMO_PANEL: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised)',
  borderRadius: 16,
  padding: '20px 24px',
  marginBottom: 20,
}

const NEUMO_CARD_SM: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-raised-sm)',
  borderRadius: 12,
  padding: '14px 16px',
  marginBottom: 12,
}

const NEUMO_INSET: React.CSSProperties = {
  background: 'var(--neumo-bg)',
  boxShadow: 'var(--neumo-inset)',
  borderRadius: 10,
  border: 'none',
  padding: '12px 14px',
  width: '100%',
  resize: 'vertical' as const,
  color: 'var(--neumo-text)',
  fontFamily: 'var(--mono)',
  fontSize: 12,
  boxSizing: 'border-box' as const,
}

const BTN_PRIMARY: React.CSSProperties = {
  padding: '8px 18px',
  background: 'var(--blue-primary)',
  color: 'white',
  border: 'none',
  borderRadius: 10,
  fontWeight: 700,
  cursor: 'pointer',
  fontSize: 13,
  boxShadow: 'var(--neumo-raised-sm)',
  position: 'relative' as const,
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

const SECTION_TITLE: React.CSSProperties = {
  fontSize: 11,
  fontWeight: 700,
  letterSpacing: 1,
  textTransform: 'uppercase' as const,
  color: 'var(--blue-primary)',
  margin: '0 0 14px',
  borderBottom: '2px solid var(--blue-border)',
  paddingBottom: 6,
}

// ── Sub-components ─────────────────────────────────────────────────────────

const LEVEL_DOTS: Record<string, number> = {
  beginner: 1, intermediate: 2, advanced: 3, expert: 4,
}

function SkillBadge({ skill }: { skill: Skill }) {
  const filled = LEVEL_DOTS[skill.level] ?? 2
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 20, border: '1px solid var(--blue-border)', fontSize: 12, color: 'var(--neumo-text)', background: 'var(--neumo-bg)', boxShadow: 'var(--neumo-raised-sm)' }}>
      {skill.name}
      <span style={{ display: 'flex', gap: 2 }}>
        {[1, 2, 3, 4].map(i => (
          <span key={i} style={{ width: 5, height: 5, borderRadius: '50%', background: i <= filled ? 'var(--blue-primary)' : 'var(--neumo-shadow-dark)' }} />
        ))}
      </span>
    </span>
  )
}

function XYZBullet({ action, metric, context }: { action: string; metric: string; context: string }) {
  return (
    <li style={{ fontSize: 13, color: 'var(--neumo-text)', lineHeight: 1.6, marginBottom: 4 }}>
      <span style={{ color: 'var(--neumo-text)', fontWeight: 500 }}>{action}</span>
      {' '}<span style={{ color: 'var(--blue-medium)', fontWeight: 600 }}>{metric}</span>
      {' '}<span>{context}</span>
    </li>
  )
}

function ExperienceCard({ exp }: { exp: WorkExperience }) {
  const start = new Date(exp.start_date).toLocaleDateString('en', { month: 'short', year: 'numeric' })
  const end = exp.is_current ? 'Present' : exp.end_date ? new Date(exp.end_date).toLocaleDateString('en', { month: 'short', year: 'numeric' }) : ''
  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <div>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--neumo-text)' }}>{exp.role}</span>
          <span style={{ fontSize: 13, color: 'var(--neumo-text-s)', marginLeft: 6 }}>@ {exp.company}</span>
          {exp.location && <span style={{ fontSize: 12, color: 'var(--neumo-text-s)', marginLeft: 4 }}>· {exp.location}</span>}
        </div>
        <span style={{ fontSize: 11, color: 'var(--neumo-text-s)', whiteSpace: 'nowrap' }}>{start} – {end}</span>
      </div>
      <ul style={{ margin: '6px 0 0 0', paddingLeft: 16 }}>
        {exp.achievements.map((a, i) => (
          <XYZBullet key={i} action={a.action} metric={a.metric} context={a.context} />
        ))}
      </ul>
      {exp.technologies.length > 0 && (
        <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {exp.technologies.map(t => (
            <span key={t} style={{ fontSize: 11, padding: '1px 7px', borderRadius: 4, background: 'var(--blue-light)', color: 'var(--blue-primary)', border: '1px solid var(--blue-border)' }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  )
}

interface PromptEditorProps {
  label: string
  value: string
  defaultValue: string
  onChange: (v: string) => void
  onSave: () => Promise<void>
}

function PromptEditor({ label, value, defaultValue, onChange, onSave }: PromptEditorProps) {
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [saveError, setSaveError] = useState('')

  async function handleSave() {
    setSaving(true)
    setSaveError('')
    try {
      await onSave()
      setSaved(true)
      setTimeout(() => setSaved(false), 2000)
    } catch (err: unknown) {
      setSaveError(err instanceof Error ? err.message : 'Erro ao salvar.')
    } finally {
      setSaving(false)
    }
  }

  function handleReset() {
    onChange(defaultValue)
  }

  return (
    <div style={{ marginBottom: 24 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
        <span style={{ fontSize: 12, fontWeight: 700, color: 'var(--neumo-text)', letterSpacing: 0.5 }}>{label}</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {saved && <span style={{ fontSize: 11, color: 'var(--blue-primary)', fontWeight: 600 }}>Saved ✓</span>}
          <button
            onClick={handleReset}
            style={BTN_GHOST}
            onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            Reset
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{ ...BTN_PRIMARY, opacity: saving ? 0.7 : 1, cursor: saving ? 'default' : 'pointer' }}
            onMouseDown={e => { if (!saving) e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        rows={18}
        style={NEUMO_INSET}
      />
      {saveError && (
        <p style={{ fontSize: 11, color: 'var(--color-error)', margin: '4px 0 0' }}>{saveError}</p>
      )}
    </div>
  )
}

// ── Main component ─────────────────────────────────────────────────────────

export function ProfilePage({ profile, onSearchJobs, onAutoSearch, onReimport, onProfileUpdated, autoSearchBadge }: Props) {
  const [downloading, setDownloading] = useState(false)
  const [cvPrompt, setCvPrompt] = useState(profile.cv_prompt)
  const [clPrompt, setClPrompt] = useState(profile.cover_letter_prompt)

  async function handleDownload() {
    setDownloading(true)
    try {
      const blob = await downloadMasterResume()
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${profile.contact.full_name.replace(/ /g, '_')}_MasterResume.pdf`
      a.click()
      URL.revokeObjectURL(url)
    } finally {
      setDownloading(false)
    }
  }

  async function saveCvPrompt() {
    const updated = await updatePrompts({ cv_prompt: cvPrompt })
    onProfileUpdated(updated)
  }

  async function saveClPrompt() {
    const updated = await updatePrompts({ cover_letter_prompt: clPrompt })
    onProfileUpdated(updated)
  }

  const c = profile.contact

  return (
    <div style={PAGE_BG}>

      {/* ── Glass ActionBar ── */}
      <div style={ACTION_BAR}>
        <button
          onClick={onSearchJobs}
          style={BTN_PRIMARY}
          onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
          onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
        >
          Search Jobs
          {profile.job_suggestions.length > 0 && (
            <span style={{ marginLeft: 6, background: 'white', color: 'var(--blue-primary)', borderRadius: '50%', fontSize: 10, fontWeight: 700, padding: '1px 5px', verticalAlign: 'middle' }}>
              {profile.job_suggestions.length}
            </span>
          )}
        </button>

        {profile.job_suggestions.length > 0 && (
          <button
            onClick={onAutoSearch}
            style={BTN_GHOST}
            onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
            onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
            onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          >
            ⚡ Auto Search
            {(autoSearchBadge ?? 0) > 0 && (
              <span style={{ marginLeft: 6, background: 'var(--color-error)', color: 'white', borderRadius: '50%', fontSize: 10, fontWeight: 700, padding: '1px 5px', verticalAlign: 'middle' }}>
                {autoSearchBadge}
              </span>
            )}
          </button>
        )}

        <button
          onClick={handleDownload}
          disabled={downloading}
          style={{ ...BTN_GHOST, opacity: downloading ? 0.6 : 1, cursor: downloading ? 'default' : 'pointer' }}
          onMouseDown={e => { if (!downloading) e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
          onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
        >
          {downloading ? 'Generating…' : 'Download Resume PDF'}
        </button>

        <button
          onClick={onReimport}
          style={BTN_GHOST}
          onMouseDown={e => { e.currentTarget.style.boxShadow = 'var(--neumo-pressed)' }}
          onMouseUp={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
          onMouseLeave={e => { e.currentTarget.style.boxShadow = 'var(--neumo-raised-sm)' }}
        >
          Re-import
        </button>
      </div>

      <div style={CONTENT_WRAP}>

        {/* ── Neumo: contact header ── */}
        <div style={NEUMO_PANEL}>
          <h1 style={{ fontSize: 24, margin: '0 0 4px', color: 'var(--neumo-text)', fontWeight: 700 }}>{c.full_name}</h1>
          <p style={{ fontSize: 13, color: 'var(--neumo-text-s)', margin: '0 0 0' }}>
            {[c.email, c.phone, c.location].filter(Boolean).join('  ·  ')}
            {c.linkedin_url && <> · <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--blue-primary)' }}>LinkedIn</a></>}
            {c.github_url && <> · <a href={c.github_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--blue-primary)' }}>GitHub</a></>}
          </p>
        </div>

        {/* ── Neumo: summary ── */}
        {profile.summary && (
          <div style={NEUMO_PANEL}>
            <h2 style={SECTION_TITLE}>Summary</h2>
            <p style={{ fontSize: 13, color: 'var(--neumo-text)', lineHeight: 1.7, margin: 0, borderLeft: '3px solid var(--blue-primary)', paddingLeft: 12 }}>
              {profile.summary}
            </p>
          </div>
        )}

        {/* ── Neumo: experience ── */}
        {profile.work_experiences.length > 0 && (
          <div style={NEUMO_PANEL}>
            <h2 style={SECTION_TITLE}>Experience</h2>
            {profile.work_experiences.map((exp, i) => (
              <div key={exp.id} style={{ ...NEUMO_CARD_SM, marginBottom: i === profile.work_experiences.length - 1 ? 0 : 12 }}>
                <ExperienceCard exp={exp} />
              </div>
            ))}
          </div>
        )}

        {/* ── Neumo: skills ── */}
        {profile.skills.length > 0 && (
          <div style={NEUMO_PANEL}>
            <h2 style={SECTION_TITLE}>Skills</h2>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {profile.skills.map(s => <SkillBadge key={s.name} skill={s} />)}
            </div>
          </div>
        )}

        {/* ── Neumo: education ── */}
        {profile.education.length > 0 && (
          <div style={NEUMO_PANEL}>
            <h2 style={SECTION_TITLE}>Education</h2>
            {profile.education.map(edu => (
              <div key={edu.id} style={{ marginBottom: 10 }}>
                <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--neumo-text)' }}>
                  {edu.degree} in {edu.field_of_study}
                </span>
                <span style={{ fontSize: 13, color: 'var(--neumo-text-s)' }}> — {edu.institution}</span>
                {edu.end_date && <span style={{ fontSize: 12, color: 'var(--neumo-text-s)', marginLeft: 6 }}>({new Date(edu.end_date).getFullYear()})</span>}
              </div>
            ))}
          </div>
        )}

        {/* ── Neumo: languages ── */}
        {profile.languages.length > 0 && (
          <div style={NEUMO_PANEL}>
            <h2 style={SECTION_TITLE}>Languages</h2>
            <p style={{ fontSize: 13, color: 'var(--neumo-text)', margin: 0 }}>
              {profile.languages.map(l => `${l.name} (${l.proficiency})`).join('  ·  ')}
            </p>
          </div>
        )}

        {/* ── Neumo: generation prompts ── */}
        <div style={NEUMO_PANEL}>
          <h2 style={SECTION_TITLE}>Generation Prompts</h2>
          <p style={{ fontSize: 12, color: 'var(--neumo-text-s)', marginBottom: 16, lineHeight: 1.6 }}>
            Sent to the AI when generating resume and cover letter PDFs.
            Use <code style={{ fontSize: 11, background: 'var(--blue-light)', color: 'var(--blue-primary)', padding: '1px 4px', borderRadius: 3, border: '1px solid var(--blue-border)' }}>{'{JOB_DESCRIPTION}'}</code> as placeholder — replaced automatically with job details.
          </p>
          <PromptEditor
            label="Resume Prompt"
            value={cvPrompt}
            defaultValue={DEFAULT_CV_PROMPT}
            onChange={setCvPrompt}
            onSave={saveCvPrompt}
          />
          <PromptEditor
            label="Cover Letter Prompt"
            value={clPrompt}
            defaultValue={DEFAULT_CL_PROMPT}
            onChange={setClPrompt}
            onSave={saveClPrompt}
          />
        </div>

      </div>
    </div>
  )
}
