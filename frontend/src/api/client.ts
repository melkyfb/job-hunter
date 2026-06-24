/**
 * Typed API client wrapping fetch.
 * All requests go through Vite's proxy (/api → http://localhost:8000).
 *
 * Run `npm run api:types` (with the backend running) to regenerate schema.d.ts
 * from the live OpenAPI spec — any backend model change will surface as a TS error here.
 */

import { invoke } from '@tauri-apps/api/core'
import { fetch as tauriFetch } from '@tauri-apps/plugin-http'

// In Tauri (dev or prod) go directly to the sidecar via the HTTP plugin.
// In plain browser (dev without Tauri), use Vite's proxy.
const isTauri = typeof window !== 'undefined' && '__TAURI_INTERNALS__' in window
const BASE = import.meta.env.VITE_API_BASE ?? (isTauri ? 'http://localhost:8000' : '/api')

/** Build a multipart/form-data body as Uint8Array so tauriFetch can serialize it. */
async function buildMultipart(form: FormData): Promise<{ body: Uint8Array; contentType: string }> {
  const boundary = `----TauriBoundary${Math.random().toString(36).slice(2)}`
  const enc = new TextEncoder()
  const chunks: Uint8Array[] = []

  for (const [name, value] of form.entries()) {
    chunks.push(enc.encode(`--${boundary}\r\n`))
    if (value instanceof File) {
      const fname = value.name
      const mime = value.type || 'application/octet-stream'
      chunks.push(enc.encode(
        `Content-Disposition: form-data; name="${name}"; filename="${fname}"\r\n` +
        `Content-Type: ${mime}\r\n\r\n`
      ))
      chunks.push(new Uint8Array(await value.arrayBuffer()))
      chunks.push(enc.encode('\r\n'))
    } else {
      chunks.push(enc.encode(`Content-Disposition: form-data; name="${name}"\r\n\r\n${value}\r\n`))
    }
  }
  chunks.push(enc.encode(`--${boundary}--\r\n`))

  const total = chunks.reduce((n, c) => n + c.length, 0)
  const body = new Uint8Array(total)
  let off = 0
  for (const c of chunks) { body.set(c, off); off += c.length }
  return { body, contentType: `multipart/form-data; boundary=${boundary}` }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const isFormData = init?.body instanceof FormData
  let body: RequestInit['body'] = init?.body
  let contentType = isFormData ? undefined : 'application/json'

  if (isTauri && isFormData) {
    // tauriFetch can't serialize File objects — build raw multipart bytes instead.
    const mp = await buildMultipart(init!.body as FormData)
    body = mp.body as unknown as BodyInit
    contentType = mp.contentType
  }

  const fetchFn = isTauri ? (tauriFetch as unknown as typeof fetch) : fetch
  const headers = contentType
    ? { 'Content-Type': contentType, ...init?.headers }
    : { ...init?.headers }

  const res = await fetchFn(`${BASE}${path}`, { ...init, body, headers })
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

export async function ingestProfile(files: File[]) {
  const form = new FormData()
  for (const file of files) {
    form.append('files', file)
  }
  return request<AsyncJobStart>('/profile/ingest', {
    method: 'POST',
    headers: {},
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

export async function updatePrompts(data: { cv_prompt?: string; cover_letter_prompt?: string }) {
  return request<ProfileMaster>('/profile/prompts', {
    method: 'PATCH',
    body: JSON.stringify(data),
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

// ── Auto Search ────────────────────────────────────────────────────────────────

export async function getAutoSearchConfig() {
  return request<AutoSearchConfig>('/auto-search/config')
}

export async function saveAutoSearchConfig(config: AutoSearchConfig) {
  return request<AutoSearchConfig>('/auto-search/config', {
    method: 'PUT',
    body: JSON.stringify(config),
  })
}

export async function getAutoSearchSummary() {
  return request<AutoSearchSummary>('/auto-search/summary')
}

export async function triggerAutoSearchRun() {
  return request<AutoSearchRunStart>('/auto-search/run', { method: 'POST' })
}

export async function getAutoSearchResults(
  page: number,
  pageSize: number,
  statusFilter: string,
  sort: 'score' | 'recent' = 'score',
) {
  const params = new URLSearchParams({
    page: String(page),
    page_size: String(pageSize),
    status_filter: statusFilter,
    sort,
  })
  return request<AutoSearchResultsPage>(`/auto-search/results?${params}`)
}

export async function markAutoSearchSeen() {
  return request<void>('/auto-search/mark-seen', { method: 'POST' })
}

export async function setJobStatus(urlHash: string, status: JobStatus, notes?: string) {
  return request<{ url_hash: string; status: JobStatus }>(`/auto-search/jobs/${urlHash}/status`, {
    method: 'PATCH',
    body: JSON.stringify({ status, notes: notes ?? null }),
  })
}

export async function cleanupAutoSearch(params: {
  before_date?: string
  remove_not_interested?: boolean
  remove_unavailable?: boolean
}) {
  const q = new URLSearchParams()
  if (params.before_date) q.set('before_date', params.before_date)
  if (params.remove_not_interested) q.set('remove_not_interested', 'true')
  if (params.remove_unavailable) q.set('remove_unavailable', 'true')
  return request<{ removed: number }>(`/auto-search/cleanup?${q}`, { method: 'DELETE' })
}

// ── Application ───────────────────────────────────────────────────────────────

export async function generateApplication(job: JobPosting, match: MatchScore) {
  return request<ApplicationPackage>('/application/generate', {
    method: 'POST',
    body: JSON.stringify({ job, match }),
  })
}

export async function getMasterResumeHtml(): Promise<string> {
  const data = await request<{ html: string }>('/application/master-resume')
  return data.html
}

export async function openCvPreview(html: string): Promise<void> {
  await invoke('open_cv_preview', { html })
}

// ── Config ────────────────────────────────────────────────────────────────────

export async function getLLMConfig() {
  return request<LLMConfigView>('/config/llm')
}

export interface ConfigUpdatePayload {
  llm_provider: string
  llm_model: string
  llm_base_url?: string
  llm_api_key?: string
  llm_temperature: number
  adzuna_app_id?: string
  adzuna_api_key?: string
  adzuna_country: string
  search_provider: string
  cv_prompt?: string
  cl_prompt?: string
  cv_language: string
  cl_language: string
}

export async function updateConfig(payload: ConfigUpdatePayload): Promise<void> {
  await request<{ ok: boolean }>('/config/update', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
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
  reference_text: string
  cv_prompt: string
  cover_letter_prompt: string
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

// ── Auto Search ──────────────────────────────────────────────────────────────

export type JobStatus =
  | 'NONE'
  | 'NOT_INTERESTED'
  | 'APPLIED'
  | 'INTERVIEWING'
  | 'OFFER_RECEIVED'

export interface SearchEntry {
  id: string
  title: string
  keywords: string[]
  active: boolean
  custom: boolean
}

export interface AutoSearchConfig {
  enabled: boolean
  interval_hours: number
  location: string
  page_size: number
  providers: string[]
  entries: SearchEntry[]
}

export interface AutoSearchSummary {
  enabled: boolean
  last_run_at: string | null
  next_run_at: string | null
  new_count: number
  total_count: number
}

export interface SavedJobWithStatus {
  url_hash: string
  posting: JobPosting
  match: MatchScore
  found_at: string
  last_seen_at: string
  found_via: string
  status: JobStatus
  notes: string | null
}

export interface AutoSearchResultsPage {
  jobs: SavedJobWithStatus[]
  total: number
  page: number
  page_size: number
  total_pages: number
}

export interface AutoSearchRunStart {
  job_id: string
  status: 'processing'
}

export interface ApplicationPackage {
  job_id: string
  resume_html: string
  cover_letter_html: string
  cover_letter_text: string
}

export interface LLMConfigView {
  provider: 'openai' | 'local'
  model: string
  base_url?: string
  temperature: number
  max_retries: number
  api_key_set: boolean
}
