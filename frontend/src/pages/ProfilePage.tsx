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

const LEVEL_DOTS: Record<string, number> = {
  beginner: 1, intermediate: 2, advanced: 3, expert: 4,
}

function SkillBadge({ skill }: { skill: Skill }) {
  const filled = LEVEL_DOTS[skill.level] ?? 2
  return (
    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, padding: '3px 10px', borderRadius: 20, border: '1px solid var(--border)', fontSize: 12, color: 'var(--text)' }}>
      {skill.name}
      <span style={{ display: 'flex', gap: 2 }}>
        {[1, 2, 3, 4].map(i => (
          <span key={i} style={{ width: 5, height: 5, borderRadius: '50%', background: i <= filled ? 'var(--accent)' : 'var(--border)' }} />
        ))}
      </span>
    </span>
  )
}

function XYZBullet({ action, metric, context }: { action: string; metric: string; context: string }) {
  return (
    <li style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.6, marginBottom: 4 }}>
      <span style={{ color: 'var(--text-h)', fontWeight: 500 }}>{action}</span>
      {' '}<span style={{ color: 'var(--accent)' }}>{metric}</span>
      {' '}<span>{context}</span>
    </li>
  )
}

function ExperienceCard({ exp }: { exp: WorkExperience }) {
  const start = new Date(exp.start_date).toLocaleDateString('en', { month: 'short', year: 'numeric' })
  const end = exp.is_current ? 'Present' : exp.end_date ? new Date(exp.end_date).toLocaleDateString('en', { month: 'short', year: 'numeric' }) : ''
  return (
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline', gap: 8, flexWrap: 'wrap' }}>
        <div>
          <span style={{ fontWeight: 600, fontSize: 14, color: 'var(--text-h)' }}>{exp.role}</span>
          <span style={{ fontSize: 13, color: 'var(--text)', marginLeft: 6 }}>@ {exp.company}</span>
          {exp.location && <span style={{ fontSize: 12, color: 'var(--text)', marginLeft: 4 }}>· {exp.location}</span>}
        </div>
        <span style={{ fontSize: 11, color: 'var(--text)', whiteSpace: 'nowrap' }}>{start} – {end}</span>
      </div>
      <ul style={{ margin: '6px 0 0 0', paddingLeft: 16 }}>
        {exp.achievements.map((a, i) => (
          <XYZBullet key={i} action={a.action} metric={a.metric} context={a.context} />
        ))}
      </ul>
      {exp.technologies.length > 0 && (
        <div style={{ marginTop: 6, display: 'flex', flexWrap: 'wrap', gap: 4 }}>
          {exp.technologies.map(t => (
            <span key={t} style={{ fontSize: 11, padding: '1px 7px', borderRadius: 4, background: 'var(--code-bg)', color: 'var(--text)' }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  )
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase', color: 'var(--accent)', margin: '0 0 12px', borderBottom: '1px solid var(--border)', paddingBottom: 6 }}>
        {title}
      </h2>
      {children}
    </section>
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
    <div style={{ marginBottom: 20 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 6 }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: 'var(--text-h)' }}>{label}</span>
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          {saved && <span style={{ fontSize: 11, color: 'var(--accent)' }}>Saved ✓</span>}
          <button
            onClick={handleReset}
            style={{ fontSize: 11, padding: '3px 10px', borderRadius: 5, border: '1px solid var(--border)', background: 'var(--bg)', color: 'var(--text)', cursor: 'pointer' }}
          >
            Reset to default
          </button>
          <button
            onClick={handleSave}
            disabled={saving}
            style={{ fontSize: 11, padding: '3px 10px', borderRadius: 5, border: 'none', background: 'var(--accent)', color: 'white', cursor: saving ? 'default' : 'pointer' }}
          >
            {saving ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
      <textarea
        value={value}
        onChange={e => onChange(e.target.value)}
        rows={18}
        style={{
          width: '100%', fontFamily: 'monospace', fontSize: 11,
          padding: '10px 12px', borderRadius: 6, border: '1px solid var(--border)',
          background: 'var(--code-bg)', color: 'var(--text)', resize: 'vertical',
          boxSizing: 'border-box',
        }}
      />
      {saveError && (
        <p style={{ fontSize: 11, color: '#ef4444', margin: '4px 0 0' }}>{saveError}</p>
      )}
    </div>
  )
}

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
    <div style={{ maxWidth: 720, textAlign: 'left' }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, margin: '0 0 4px', color: 'var(--text-h)' }}>{c.full_name}</h1>
        <p style={{ fontSize: 13, color: 'var(--text)', margin: '0 0 12px' }}>
          {[c.email, c.phone, c.location].filter(Boolean).join('  ·  ')}
          {c.linkedin_url && <> · <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>LinkedIn</a></>}
          {c.github_url && <> · <a href={c.github_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>GitHub</a></>}
        </p>

        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            onClick={onSearchJobs}
            style={{ padding: '8px 18px', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: 7, fontWeight: 600, cursor: 'pointer', fontSize: 13, position: 'relative' }}
          >
            Search Jobs
            {profile.job_suggestions.length > 0 && (
              <span style={{
                marginLeft: 6, background: 'white', color: 'var(--accent)',
                borderRadius: '50%', fontSize: 10, fontWeight: 700,
                padding: '1px 5px', verticalAlign: 'middle',
              }}>
                {profile.job_suggestions.length}
              </span>
            )}
          </button>
          {profile.job_suggestions.length > 0 && (
            <button
              onClick={onAutoSearch}
              style={{ padding: '8px 18px', background: 'none', color: 'var(--accent)', border: '1px solid var(--accent-border)', borderRadius: 7, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}
            >
              ⚡ Auto Search
              {(autoSearchBadge ?? 0) > 0 && (
                <span style={{ marginLeft: 6, background: '#ef4444', color: 'white', borderRadius: '50%', fontSize: 10, fontWeight: 700, padding: '1px 5px', verticalAlign: 'middle' }}>
                  {autoSearchBadge}
                </span>
              )}
            </button>
          )}
          <button
            onClick={handleDownload}
            disabled={downloading}
            style={{ padding: '8px 18px', background: 'none', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 7, cursor: 'pointer', fontSize: 13 }}
          >
            {downloading ? 'Generating…' : 'Download Resume PDF'}
          </button>
          <button
            onClick={onReimport}
            style={{ padding: '8px 18px', background: 'none', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 7, cursor: 'pointer', fontSize: 13 }}
          >
            Re-import documents
          </button>
        </div>
      </div>

      {/* ── Summary ── */}
      {profile.summary && (
        <Section title="Summary">
          <p style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.7, margin: 0 }}>{profile.summary}</p>
        </Section>
      )}

      {/* ── Experience ── */}
      {profile.work_experiences.length > 0 && (
        <Section title="Experience">
          {profile.work_experiences.map(exp => <ExperienceCard key={exp.id} exp={exp} />)}
        </Section>
      )}

      {/* ── Skills ── */}
      {profile.skills.length > 0 && (
        <Section title="Skills">
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
            {profile.skills.map(s => <SkillBadge key={s.name} skill={s} />)}
          </div>
        </Section>
      )}

      {/* ── Education ── */}
      {profile.education.length > 0 && (
        <Section title="Education">
          {profile.education.map(edu => (
            <div key={edu.id} style={{ marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 600, color: 'var(--text-h)' }}>
                {edu.degree} in {edu.field_of_study}
              </span>
              <span style={{ fontSize: 13, color: 'var(--text)' }}> — {edu.institution}</span>
              {edu.end_date && <span style={{ fontSize: 12, color: 'var(--text)', marginLeft: 6 }}>({new Date(edu.end_date).getFullYear()})</span>}
            </div>
          ))}
        </Section>
      )}

      {/* ── Languages ── */}
      {profile.languages.length > 0 && (
        <Section title="Languages">
          <p style={{ fontSize: 13, color: 'var(--text)', margin: 0 }}>
            {profile.languages.map(l => `${l.name} (${l.proficiency})`).join('  ·  ')}
          </p>
        </Section>
      )}

      {/* ── Generation Prompts ── */}
      <Section title="Generation Prompts">
        <p style={{ fontSize: 12, color: 'var(--text)', marginBottom: 16 }}>
          These prompts are sent to the AI when generating your resume and cover letter PDFs.
          Use <code style={{ fontSize: 11, background: 'var(--code-bg)', padding: '1px 4px', borderRadius: 3 }}>{'{JOB_DESCRIPTION}'}</code> as placeholder — it's replaced automatically with the job details.
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
      </Section>
    </div>
  )
}
