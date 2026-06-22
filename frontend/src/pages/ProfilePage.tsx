import { useState } from 'react'
import { downloadMasterResume, seedDefaultDesigns, getIngestStatus, getProfile, type ProfileMaster, type WorkExperience, type Skill, type DesignVersion } from '../api/client'
import { DesignEditor } from '../components/DesignEditor'
import { DesignGallery } from '../components/DesignGallery'

interface Props {
  profile: ProfileMaster
  onSearchJobs: () => void
  onAutoSearch: () => void
  onReimport: () => void
  onProfileUpdated: (p: ProfileMaster) => void
  autoSearchBadge?: number
}

// ── Skill level visual ────────────────────────────────────────────────────────

const LEVEL_DOTS: Record<string, number> = {
  beginner: 1, intermediate: 2, advanced: 3, expert: 4,
}

function SkillBadge({ skill }: { skill: Skill }) {
  const filled = LEVEL_DOTS[skill.level] ?? 2
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 20,
      border: '1px solid var(--border)', fontSize: 12, color: 'var(--text)',
    }}>
      {skill.name}
      <span style={{ display: 'flex', gap: 2 }}>
        {[1, 2, 3, 4].map(i => (
          <span key={i} style={{
            width: 5, height: 5, borderRadius: '50%',
            background: i <= filled ? 'var(--accent)' : 'var(--border)',
          }} />
        ))}
      </span>
    </span>
  )
}

// ── XYZ bullet ───────────────────────────────────────────────────────────────

function XYZBullet({ action, metric, context }: { action: string; metric: string; context: string }) {
  return (
    <li style={{ fontSize: 13, color: 'var(--text)', lineHeight: 1.6, marginBottom: 4 }}>
      <span style={{ color: 'var(--text-h)', fontWeight: 500 }}>{action}</span>
      {' '}<span style={{ color: 'var(--accent)' }}>{metric}</span>
      {' '}<span>{context}</span>
    </li>
  )
}

// ── Work experience card ──────────────────────────────────────────────────────

function ExperienceCard({ exp }: { exp: WorkExperience }) {
  const start = new Date(exp.start_date).toLocaleDateString('en', { month: 'short', year: 'numeric' })
  const end = exp.is_current
    ? 'Present'
    : exp.end_date
      ? new Date(exp.end_date).toLocaleDateString('en', { month: 'short', year: 'numeric' })
      : ''

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
            <span key={t} style={{
              fontSize: 11, padding: '1px 7px', borderRadius: 4,
              background: 'var(--code-bg)', color: 'var(--text)',
            }}>{t}</span>
          ))}
        </div>
      )}
    </div>
  )
}

// ── Section heading ───────────────────────────────────────────────────────────

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section style={{ marginBottom: 28 }}>
      <h2 style={{
        fontSize: 11, fontWeight: 700, letterSpacing: 1, textTransform: 'uppercase',
        color: 'var(--accent)', margin: '0 0 12px', borderBottom: '1px solid var(--border)', paddingBottom: 6,
      }}>
        {title}
      </h2>
      {children}
    </section>
  )
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function ProfilePage({ profile, onSearchJobs, onAutoSearch, onReimport, onProfileUpdated, autoSearchBadge }: Props) {
  const [downloading, setDownloading] = useState(false)
  const [seedingAll, setSeedingAll] = useState(false)
  const [seedAllMsg, setSeedAllMsg] = useState('')
  const [seedAllError, setSeedAllError] = useState('')

  function handleDesignSaved(version: DesignVersion) {
    onProfileUpdated({ ...profile, design_versions: [...profile.design_versions, version] })
  }

  function handleDesignUpdated(updated: DesignVersion) {
    onProfileUpdated({
      ...profile,
      design_versions: profile.design_versions.map(v => v.id === updated.id ? updated : v),
      active_resume_design_id: updated.is_default && updated.type === 'resume' ? updated.id : profile.active_resume_design_id,
      active_cover_letter_design_id: updated.is_default && updated.type === 'cover_letter' ? updated.id : profile.active_cover_letter_design_id,
    })
  }

  function handleDesignDeleted(id: string) {
    onProfileUpdated({
      ...profile,
      design_versions: profile.design_versions.filter(v => v.id !== id),
      active_resume_design_id: profile.active_resume_design_id === id ? null : profile.active_resume_design_id,
      active_cover_letter_design_id: profile.active_cover_letter_design_id === id ? null : profile.active_cover_letter_design_id,
    })
  }

  async function handleSeedAll() {
    setSeedingAll(true)
    setSeedAllMsg('Iniciando…')
    setSeedAllError('')
    try {
      const { job_id } = await seedDefaultDesigns()
      while (true) {
        const status = await getIngestStatus(job_id)
        setSeedAllMsg(status.message)
        if (status.status === 'completed') {
          const updated = await getProfile()
          onProfileUpdated(updated)
          setSeedingAll(false)
          setSeedAllMsg('')
          return
        }
        if (status.status === 'failed') {
          setSeedAllError(status.message || 'Failed to regenerate designs.')
          setSeedingAll(false)
          return
        }
        await new Promise(r => setTimeout(r, 1000))
      }
    } catch (err: unknown) {
      setSeedAllError(err instanceof Error ? err.message : 'Failed.')
      setSeedingAll(false)
    }
  }

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

  const c = profile.contact

  return (
    <div style={{ maxWidth: 720, textAlign: 'left' }}>

      {/* ── Header ── */}
      <div style={{ marginBottom: 24 }}>
        <h1 style={{ fontSize: 24, margin: '0 0 4px', color: 'var(--text-h)' }}>
          {c.full_name}
        </h1>
        <p style={{ fontSize: 13, color: 'var(--text)', margin: '0 0 12px' }}>
          {[c.email, c.phone, c.location].filter(Boolean).join('  ·  ')}
          {c.linkedin_url && <> · <a href={c.linkedin_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>LinkedIn</a></>}
          {c.github_url && <> · <a href={c.github_url} target="_blank" rel="noopener noreferrer" style={{ color: 'var(--accent)' }}>GitHub</a></>}
        </p>

        {/* Action buttons */}
        <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
          <button
            onClick={onSearchJobs}
            style={{ padding: '8px 18px', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: 7, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}
          >
            Search Jobs
          </button>
          {profile.job_suggestions.length > 0 && (
            <button
              onClick={onAutoSearch}
              style={{ padding: '8px 18px', background: 'none', color: 'var(--accent)', border: '1px solid var(--accent-border)', borderRadius: 7, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}
            >
              ⚡ Auto Search
              {(autoSearchBadge ?? 0) > 0 && (
                <span style={{
                  marginLeft: 6, background: '#ef4444', color: 'white',
                  borderRadius: '50%', fontSize: 10, fontWeight: 700,
                  padding: '1px 5px', verticalAlign: 'middle',
                }}>
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
            Re-import resume
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
              {edu.end_date && (
                <span style={{ fontSize: 12, color: 'var(--text)', marginLeft: 6 }}>
                  ({new Date(edu.end_date).getFullYear()})
                </span>
              )}
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

      {/* ── Job suggestions hint ── */}
      {profile.job_suggestions.length > 0 && (
        <div style={{
          marginTop: 8, padding: '10px 14px', borderRadius: 8,
          background: 'var(--accent-bg)', border: '1px solid var(--accent-border)',
          fontSize: 12, color: 'var(--text)',
        }}>
          <strong style={{ color: 'var(--accent)' }}>{profile.job_suggestions.length} job roles</strong> identified from your profile.
          {' '}
          <button
            onClick={onSearchJobs}
            style={{ background: 'none', border: 'none', color: 'var(--accent)', cursor: 'pointer', fontSize: 12, fontWeight: 600, padding: 0 }}
          >
            Search Jobs →
          </button>
        </div>
      )}

      {/* ── Resume Design ── */}
      <Section title="Resume Design">
        {/* Regenerar todos button */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
          <button
            onClick={handleSeedAll}
            disabled={seedingAll}
            style={{
              fontSize: 12, padding: '4px 12px', borderRadius: 6,
              border: '1px solid var(--border)', background: 'var(--bg)',
              color: 'var(--text)', cursor: seedingAll ? 'default' : 'pointer',
            }}
          >
            {seedingAll ? 'Gerando…' : 'Regenerar todos os designs'}
          </button>
          {seedingAll && (
            <span style={{ fontSize: 11, color: 'var(--text)' }}>{seedAllMsg}</span>
          )}
        </div>
        {seedAllError && (
          <p style={{ fontSize: 12, color: '#ef4444', marginBottom: 8 }}>{seedAllError}</p>
        )}
        <DesignGallery
          versions={profile.design_versions}
          type="resume"
          activeId={profile.active_resume_design_id}
          onUpdated={handleDesignUpdated}
          onDeleted={handleDesignDeleted}
          onRegenerated={async () => {
            const updated = await getProfile()
            onProfileUpdated(updated)
          }}
        />
        <DesignEditor
          type="resume"
          profile={profile}
          onSaved={handleDesignSaved}
        />
      </Section>

      {/* ── Cover Letter Design ── */}
      <Section title="Cover Letter Design">
        <DesignGallery
          versions={profile.design_versions}
          type="cover_letter"
          activeId={profile.active_cover_letter_design_id}
          onUpdated={handleDesignUpdated}
          onDeleted={handleDesignDeleted}
        />
        <DesignEditor
          type="cover_letter"
          profile={profile}
          inheritFromDesignId={profile.active_resume_design_id ?? undefined}
          onSaved={handleDesignSaved}
        />
        {profile.design_versions.some(v => v.type === 'resume') && (
          <p style={{ fontSize: 12, color: 'var(--text)', marginTop: 8 }}>
            Tip: your active resume design will be offered as a base style for the cover letter.
          </p>
        )}
      </Section>
    </div>
  )
}
