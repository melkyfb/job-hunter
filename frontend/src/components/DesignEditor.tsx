import { useState } from 'react'
import {
  startGenerateResumeDesign,
  startGenerateCoverLetterDesign,
  updateDesign,
  getDesignPreviewUrl,
  getIngestStatus,
  type DesignVersion,
  type ProfileMaster,
} from '../api/client'

interface Props {
  type: 'resume' | 'cover_letter'
  profile: ProfileMaster
  inheritFromDesignId?: string
  onSaved: (version: DesignVersion) => void
}

const RESUME_PLACEHOLDER = (profile: ProfileMaster) => {
  const role = profile.work_experiences[0]?.role ?? 'professional'
  return `Create a modern, clean resume for a ${role}. Use a two-column layout with a dark left sidebar (deep blue #1e3a5f) showing name, contact, and skills in white. Right side shows experience with bold company names and XYZ bullet points. Section headings in the accent colour. Use Arial font, compact spacing.`
}

const COVER_LETTER_PLACEHOLDER = `Elegant single-column letter on white background. Name and contact at top in a thin header band. Body text in Georgia 11pt with generous line spacing. Subtle bottom border in the accent colour. Professional and warm.`

function ProgressBar({ value }: { value: number }) {
  return (
    <div style={{ width: '100%', height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden', marginTop: 8 }}>
      <div style={{ height: '100%', borderRadius: 2, background: 'var(--accent)', width: `${value}%`, transition: 'width 0.4s ease' }} />
    </div>
  )
}

function sleep(ms: number) { return new Promise(r => setTimeout(r, ms)) }

export function DesignEditor({ type, profile, inheritFromDesignId, onSaved }: Props) {
  const [prompt, setPrompt] = useState('')
  const [draftName, setDraftName] = useState('')
  const [state, setState] = useState<'idle' | 'generating' | 'preview'>('idle')
  const [progress, setProgress] = useState(0)
  const [progressMsg, setProgressMsg] = useState('')
  const [previewDesignId, setPreviewDesignId] = useState<string | null>(null)
  const [pendingVersion, setPendingVersion] = useState<DesignVersion | null>(null)
  const [error, setError] = useState('')

  const placeholder = type === 'resume' ? RESUME_PLACEHOLDER(profile) : COVER_LETTER_PLACEHOLDER

  async function handleGenerate() {
    if (!prompt.trim()) return
    setState('generating')
    setError('')
    setProgress(5)
    setProgressMsg('Starting design generation…')

    try {
      const nameToUse = draftName.trim() || (type === 'resume' ? 'My Resume Design' : 'My Cover Letter Design')
      const start = type === 'resume'
        ? await startGenerateResumeDesign(prompt, nameToUse)
        : await startGenerateCoverLetterDesign(prompt, nameToUse, inheritFromDesignId)

      while (true) {
        const status = await getIngestStatus(start.job_id)
        setProgress(status.progress)
        setProgressMsg(status.message)

        if (status.status === 'processing') { await sleep(1500); continue }

        if (status.status === 'completed' && status.result) {
          const version = status.result as DesignVersion
          setPendingVersion(version)
          setPreviewDesignId(version.id)
          setDraftName(version.name)
          setState('preview')
          return
        }

        setError(status.message)
        setState('idle')
        return
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Generation failed.')
      setState('idle')
    }
  }

  async function handleSave() {
    if (!pendingVersion) return
    if (draftName.trim() && draftName !== pendingVersion.name) {
      await updateDesign(pendingVersion.id, { name: draftName })
    }
    onSaved({ ...pendingVersion, name: draftName })
    setState('idle')
    setPrompt('')
    setDraftName('')
    setPendingVersion(null)
    setPreviewDesignId(null)
  }

  if (state === 'generating') {
    return (
      <div style={{ padding: '16px 0' }}>
        <p style={{ fontSize: 13, color: 'var(--text-h)', margin: '0 0 4px' }}>{progressMsg}</p>
        <ProgressBar value={progress} />
      </div>
    )
  }

  if (state === 'preview' && previewDesignId) {
    return (
      <div>
        <div style={{ border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', marginBottom: 12, height: 480 }}>
          <iframe
            src={getDesignPreviewUrl(previewDesignId)}
            sandbox="allow-same-origin allow-scripts"
            style={{ width: '100%', height: '100%', border: 'none' }}
            title="Design preview"
          />
        </div>
        <div style={{ display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
          <input
            value={draftName}
            onChange={e => setDraftName(e.target.value)}
            placeholder="Design name"
            style={{ flex: 1, minWidth: 160, maxWidth: 240, padding: '7px 10px', borderRadius: 6, border: '1px solid var(--border)', fontSize: 13, background: 'var(--bg)', color: 'var(--text-h)' }}
          />
          <button onClick={handleSave} style={{ padding: '7px 16px', background: 'var(--accent)', color: 'white', border: 'none', borderRadius: 6, fontWeight: 600, cursor: 'pointer', fontSize: 13 }}>
            Save version
          </button>
          <button onClick={() => setState('idle')} style={{ padding: '7px 12px', background: 'none', color: 'var(--text)', border: '1px solid var(--border)', borderRadius: 6, cursor: 'pointer', fontSize: 13 }}>
            Discard
          </button>
        </div>
      </div>
    )
  }

  return (
    <div>
      <textarea
        value={prompt}
        onChange={e => setPrompt(e.target.value)}
        placeholder={placeholder}
        rows={4}
        style={{ width: '100%', padding: '10px 12px', borderRadius: 8, border: '1px solid var(--border)', fontSize: 13, background: 'var(--bg)', color: 'var(--text-h)', resize: 'vertical', lineHeight: 1.5, boxSizing: 'border-box' }}
      />
      {error && <p style={{ fontSize: 12, color: '#ef4444', margin: '4px 0' }}>{error}</p>}
      <button
        onClick={handleGenerate}
        disabled={!prompt.trim()}
        style={{ marginTop: 8, padding: '8px 18px', background: prompt.trim() ? 'var(--accent)' : 'var(--border)', color: 'white', border: 'none', borderRadius: 7, fontWeight: 600, cursor: prompt.trim() ? 'pointer' : 'default', fontSize: 13 }}
      >
        Generate Design
      </button>
    </div>
  )
}
