// Typed client for the FastAPI backend (backend/app/api.py). Shapes mirror its JSON exactly.

export type ReqType = 'must' | 'nice'

export interface Requirement {
  id?: number
  text: string
  type: ReqType
  weight: number
}

export interface Job {
  id: number
  name: string
  status: 'draft' | 'confirmed'
  created_at: string
  requirements?: Requirement[]
}

export interface Status {
  done: number
  total: number
}

export interface RankRow {
  id: number
  job_id: number
  filename: string
  status: 'queued' | 'done' | 'failed'
  error: string | null
  score: number | null
  must_met: number | null
  must_total: number | null
  flagged: boolean | null
  rank: number | null
}

export interface ReqResult {
  requirement_id: number
  text: string
  type: ReqType
  weight: number
  probability: number
  evidence: string
}

export interface ApplicantDetail extends Omit<RankRow, 'rank'> {
  results: ReqResult[]
}

export interface UploadResult {
  accepted: { id: number; filename: string }[]
  rejected: { filename: string; reason: string }[]
}

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init)
  if (!res.ok) {
    let message = `Request failed (${res.status})`
    try {
      const body = await res.json()
      if (typeof body.detail === 'string') message = body.detail
      else if (Array.isArray(body.detail)) message = body.detail.map((d: { msg: string }) => d.msg).join('; ')
    } catch {
      // not JSON; keep the status message
    }
    throw new Error(message)
  }
  return res.status === 204 ? (undefined as T) : res.json()
}

export const listJobs = () => request<Job[]>('/api/jobs')
export const getJob = (id: number) => request<Job>(`/api/jobs/${id}`)

export function createJob(name: string, file: File) {
  const form = new FormData()
  form.append('name', name)
  form.append('file', file)
  return request<{ job: Job; warning: string | null }>('/api/jobs', { method: 'POST', body: form })
}

export const saveRequirements = (jobId: number, reqs: Requirement[]) =>
  request<Job>(`/api/jobs/${jobId}/requirements`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(reqs.map(({ text, type, weight }) => ({ text, type, weight }))),
  })

export function uploadResumes(jobId: number, files: File[]) {
  const form = new FormData()
  files.forEach((f) => form.append('files', f))
  return request<UploadResult>(`/api/jobs/${jobId}/resumes`, { method: 'POST', body: form })
}

export const getStatus = (jobId: number) => request<Status>(`/api/jobs/${jobId}/status`)
export const getRanking = (jobId: number) => request<RankRow[]>(`/api/jobs/${jobId}/ranking`)
export const getApplicant = (id: number) => request<ApplicantDetail>(`/api/applicants/${id}`)
export const deleteJob = (id: number) => request<void>(`/api/jobs/${id}`, { method: 'DELETE' })
export const exportUrl = (jobId: number) => `/api/jobs/${jobId}/export.csv`
