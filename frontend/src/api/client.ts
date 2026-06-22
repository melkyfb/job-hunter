/**
 * Typed API client wrapping fetch.
 * All requests go through Vite's proxy (/api → http://localhost:8000).
 *
 * Run `npm run api:types` (with the backend running) to regenerate schema.d.ts
 * from the live OpenAPI spec — any backend model change will surface as a TS error here.
 */

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...init?.headers },
    ...init,
  })
  if (!res.ok) {
    const body = await res.json().catch(() => ({ detail: res.statusText }))
    throw new ApiError(res.status, body.detail ?? 'Unknown error')
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

// ── Profile ───────────────────────────────────────────────────────────────────

export async function getProfile() {
  return request<ProfileMaster>('/profile/')
}

export async function updateProfile(profile: ProfileMaster) {
  return request<ProfileMaster>('/profile/', {
    method: 'PUT',
    body: JSON.stringify(profile),
  })
}

export async function deleteProfile() {
  return request<void>('/profile/', { method: 'DELETE' })
}

export async function ingestResume(file: File) {
  const form = new FormData()
  form.append('file', file)
  return request<AsyncJobStart>('/profile/ingest', {
    method: 'POST',
    headers: {},  // let browser set multipart boundary
    body: form,
  })
}

export async function getIngestStatus(jobId: string) {
  return request<AsyncJobStatus>(`/profile/ingest/${jobId}`)
}

export async function resolveHITL(resolution: HITLResolution) {
  return request<AsyncJobStart>('/profile/ingest/resolve', {
    method: 'POST',
    body: JSON.stringify(resolution),
  })
}

// ── Jobs ──────────────────────────────────────────────────────────────────────

// ── Async job types ───────────────────────────────────────────────────────────

export interface AsyncJobStart {
  job_id: string
  status: 'processing'
}

export interface AsyncJobStatus {
  job_id: string
  status: 'processing' | 'completed' | 'hitl_required' | 'failed'
  step: string
  message: string
  progress: number
  result?: unknown  // IngestionResponse when done
}

export interface AsyncSearchStart {
  search_id: string
  status: 'processing' | 'completed'
  cached: boolean
  cached_at: string | null
}

export interface AsyncSearchStatus {
  search_id: string
  status: 'processing' | 'completed' | 'failed'
  step: string
  message: string
  progress: number
  result?: unknown  // JobSearchResponse when done
}

export interface JobSearchRequest {
  query: string
  location?: string
  max_results?: number
  force_refresh?: boolean
}

export interface JobSearchResponse {
  results: RankedJob[]
  cached: boolean
  cached_at: string | null
}

export async function searchJobs(req: JobSearchRequest) {
  return request<AsyncSearchStart>('/jobs/search', {
    method: 'POST',
    body: JSON.stringify(req),
  })
}

export async function getSearchStatus(searchId: string) {
  return request<AsyncSearchStatus>(`/jobs/search/${searchId}`)
}

export async function autoSearchJobs(location?: string) {
  const params = location ? `?location=${encodeURIComponent(location)}` : ''
  return request<AutoSearchResponse>(`/jobs/auto-search${params}`, { method: 'POST' })
}

export async function startGenerateResumeDesign(prompt: string, name: string) {
  return request<AsyncJobStart>('/profile/design/resume', {
    method: 'POST',
    body: JSON.stringify({ prompt, name }),
  })
}

export async function startGenerateCoverLetterDesign(
  prompt: string,
  name: string,
  inheritFromDesignId?: string,
) {
  return request<AsyncJobStart>('/profile/design/cover-letter', {
    method: 'POST',
    body: JSON.stringify({ prompt, name, inherit_from_design_id: inheritFromDesignId }),
  })
}

export async function updateDesign(designId: string, patch: { name?: string; is_default?: boolean }) {
  return request<DesignVersion>(`/profile/design/${designId}`, {
    method: 'PATCH',
    body: JSON.stringify(patch),
  })
}

export async function deleteDesign(designId: string) {
  return request<void>(`/profile/design/${designId}`, { method: 'DELETE' })
}

export function getDesignPreviewUrl(designId: string) {
  return `/api/profile/design/${designId}/preview-html`
}

export function getDesignPdfUrl(designId: string) {
  return `/api/profile/design/${designId}/pdf`
}

// ── Application ───────────────────────────────────────────────────────────────

export async function generateApplication(
  job: JobPosting,
  match: MatchScore,
  resumeDesignId?: string | null,
  coverLetterDesignId?: string | null,
) {
  return request<ApplicationPackage>('/application/generate', {
    method: 'POST',
    body: JSON.stringify({
      job,
      match,
      resume_design_id: resumeDesignId ?? null,
      cover_letter_design_id: coverLetterDesignId ?? null,
    }),
  })
}

export async function downloadMasterResume(): Promise<Blob> {
  const res = await fetch(`${BASE}/application/master-resume`)
  if (!res.ok) throw new ApiError(res.status, 'Failed to download resume')
  return res.blob()
}

// ── Config ────────────────────────────────────────────────────────────────────

export async function getLLMConfig() {
  return request<LLMConfigView>('/config/llm')
}

// ── Local types (mirrors Pydantic models — regenerate with npm run api:types) ─

export interface XYZExperience {
  action: string
  metric: string
  context: string
}

export interface WorkExperience {
  id: string
  company: string
  role: string
  start_date: string
  end_date?: string
  is_current: boolean
  location?: string
  achievements: XYZExperience[]
  technologies: string[]
}

export interface Education {
  id: string
  institution: string
  degree: string
  field_of_study: string
  start_date: string
  end_date?: string
  grade?: string
  relevant_courses: string[]
}

export interface Skill {
  name: string
  level: 'beginner' | 'intermediate' | 'advanced' | 'expert'
  years_of_experience?: number
}

export interface Language {
  name: string
  proficiency: string
}

export interface ContactInfo {
  full_name: string
  email: string
  phone?: string
  location?: string
  linkedin_url?: string
  github_url?: string
  portfolio_url?: string
}

export interface JobSuggestion {
  title: string
  keywords: string[]
}

export interface ProfileMaster {
  id: string
  contact: ContactInfo
  summary?: string
  work_experiences: WorkExperience[]
  education: Education[]
  skills: Skill[]
  languages: Language[]
  certifications: string[]
  job_suggestions: JobSuggestion[]
  design_versions: DesignVersion[]
  active_resume_design_id: string | null
  active_cover_letter_design_id: string | null
}

export interface HITLField {
  field_path: string
  current_value?: string
  llm_suggestion?: string
  reason: string
}

export interface HITLRequest {
  ingestion_id: string
  partial_profile: ProfileMaster
  missing_fields: HITLField[]
  message: string
}

export interface HITLResolution {
  ingestion_id: string
  resolved_fields: Record<string, string>
}

export interface IngestionResponse {
  ingestion_id: string
  status: 'processing' | 'completed' | 'hitl_required' | 'failed'
  profile?: ProfileMaster
  hitl_request?: HITLRequest
  error?: string
}

export interface JobPosting {
  id: string
  title: string
  company: string
  location: string
  description: string
  url: string
  source: string
  posted_at?: string
  salary_range?: string
  employment_type?: string
  required_skills: string[]
}

export interface MatchScore {
  job_id: string
  score: number
  keywords_found: string[]
  keywords_missing: string[]
  justification: string
}

export interface RankedJob {
  posting: JobPosting
  match: MatchScore
  found_via?: string
}

export interface AutoSearchResponse {
  results: RankedJob[]
  queries_used: string[]
}

export interface DesignVersion {
  id: string
  name: string
  prompt: string
  type: 'resume' | 'cover_letter'
  html_template: string
  inherit_from_design_id?: string
  created_at: string
  is_default: boolean
}

export interface ApplicationPackage {
  job_id: string
  resume_pdf_base64: string
  cover_letter_text: string
  cover_letter_pdf_base64: string
}

export interface LLMConfigView {
  provider: 'openai' | 'local'
  model: string
  base_url?: string
  temperature: number
  max_retries: number
  api_key_set: boolean
}
