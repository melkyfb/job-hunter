import { useState } from 'react'
import { ResumeUpload } from '../components/ResumeUpload'
import { HITLForm } from '../components/HITLForm'
import { type IngestionResponse } from '../api/client'

interface Props {
  onProfileReady: () => void
}

export function IngestPage({ onProfileReady }: Props) {
  const [ingestion, setIngestion] = useState<IngestionResponse | null>(null)

  function handleIngestionResult(response: IngestionResponse) {
    setIngestion(response)
    if (response.status === 'completed') {
      onProfileReady()
    }
  }

  if (ingestion?.status === 'failed') {
    return (
      <div>
        <h2>Something went wrong</h2>
        <p style={{ color: '#ef4444' }}>{ingestion.error}</p>
        <button onClick={() => setIngestion(null)}>Try again</button>
      </div>
    )
  }

  if (ingestion?.status === 'hitl_required' && ingestion.hitl_request) {
    return (
      <HITLForm
        request={ingestion.hitl_request}
        onResolved={handleIngestionResult}
      />
    )
  }

  return (
    <div style={{ maxWidth: 520 }}>
      <h1 style={{ fontSize: 22, marginBottom: 8 }}>Import your resume</h1>
      <p style={{ color: '#666', fontSize: 14, marginBottom: 24 }}>
        Your resume will be parsed and structured using the Google XYZ formula.
        Metrics that are missing will be flagged for your review — we never invent numbers.
      </p>
      <ResumeUpload onCompleted={handleIngestionResult} />
    </div>
  )
}
