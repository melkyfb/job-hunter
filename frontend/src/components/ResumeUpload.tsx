import { useRef, useState } from 'react'
import { ingestResume, getIngestStatus, type IngestionResponse } from '../api/client'

interface Props {
  onCompleted: (response: IngestionResponse) => void
}

const STEP_LABELS: Record<string, string> = {
  extracting: 'Extracting text from your file…',
  analyzing: 'Sending to AI for analysis…',
  validating: 'Validating structured output…',
  suggestions: 'Generating job suggestions…',
  designs: 'Gerando designs padrão…',
  saving: 'Finalizing your profile…',
  hitl: 'Missing metrics found — please review.',
  done: 'Profile ready!',
  error: 'Something went wrong.',
}

function ProgressBar({ value }: { value: number }) {
  return (
    <div style={{ width: '100%', height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
      <div style={{
        height: '100%', borderRadius: 2,
        background: 'var(--accent)',
        width: `${value}%`,
        transition: 'width 0.4s ease',
      }} />
    </div>
  )
}

export function ResumeUpload({ onCompleted }: Props) {
  const inputRef = useRef<HTMLInputElement>(null)
  const [uiState, setUiState] = useState<'idle' | 'uploading' | 'error'>('idle')
  const [message, setMessage] = useState('')
  const [progress, setProgress] = useState(0)
  const [errorMsg, setErrorMsg] = useState('')
  const [dragOver, setDragOver] = useState(false)

  async function handleFile(file: File) {
    setUiState('uploading')
    setErrorMsg('')
    setMessage('Uploading your file…')
    setProgress(5)

    try {
      const { job_id } = await ingestResume(file)
      await pollIngest(job_id)
    } catch (err: unknown) {
      setUiState('error')
      setErrorMsg(err instanceof Error ? err.message : 'Upload failed.')
    }
  }

  async function pollIngest(jobId: string): Promise<void> {
    while (true) {
      const status = await getIngestStatus(jobId)
      setMessage(STEP_LABELS[status.step] ?? status.message)
      setProgress(status.progress)

      if (status.status === 'processing') {
        await sleep(1000)
        continue
      }

      if (status.status === 'completed' || status.status === 'hitl_required') {
        onCompleted(status.result as IngestionResponse)
        return
      }

      // failed
      setUiState('error')
      setErrorMsg((status.result as IngestionResponse)?.error ?? status.message)
      return
    }
  }

  function onInputChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) handleFile(file)
  }

  function onDrop(e: React.DragEvent) {
    e.preventDefault()
    setDragOver(false)
    const file = e.dataTransfer.files?.[0]
    if (file) handleFile(file)
  }

  const isUploading = uiState === 'uploading'

  return (
    <div>
      <div
        onClick={() => !isUploading && inputRef.current?.click()}
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true) }}
        onDragLeave={() => setDragOver(false)}
        style={{
          border: `2px dashed ${dragOver ? 'var(--accent)' : 'var(--border)'}`,
          borderRadius: 12,
          padding: '2.5rem',
          textAlign: 'center',
          cursor: isUploading ? 'default' : 'pointer',
          background: dragOver ? 'var(--accent-bg)' : 'transparent',
          transition: 'all 0.15s',
        }}
      >
        <input
          ref={inputRef}
          type="file"
          accept=".pdf,.docx,.html,.htm"
          style={{ display: 'none' }}
          onChange={onInputChange}
        />

        {isUploading ? (
          <div>
            <p style={{ fontSize: 14, color: 'var(--text-h)', margin: '0 0 12px', fontWeight: 500 }}>
              {message}
            </p>
            <ProgressBar value={progress} />
            <p style={{ fontSize: 11, color: 'var(--text)', marginTop: 8 }}>
              {progress}% complete
            </p>
          </div>
        ) : (
          <>
            <p style={{ fontSize: 32, margin: 0 }}>📄</p>
            <p style={{ fontWeight: 600, marginTop: 8, color: 'var(--text-h)' }}>
              Drop your resume here or click to browse
            </p>
            <p style={{ color: 'var(--text)', fontSize: 13 }}>PDF, DOCX or HTML</p>
          </>
        )}
      </div>

      {uiState === 'error' && (
        <p style={{ color: '#ef4444', marginTop: 8, fontSize: 13 }}>{errorMsg}</p>
      )}
    </div>
  )
}

function sleep(ms: number) {
  return new Promise(resolve => setTimeout(resolve, ms))
}
