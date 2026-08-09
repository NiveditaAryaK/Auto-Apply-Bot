import type { Application, Resume, Run } from './types'

const BASE = '/api'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, init)
  if (!response.ok) {
    let detail = response.statusText
    try {
      const body = await response.json()
      detail = body.detail ?? detail
    } catch {
      // response wasn't JSON -- fall back to statusText
    }
    throw new Error(detail)
  }
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export const api = {
  listResumes: () => request<Resume[]>('/resumes'),
  uploadResume: (file: File, isPrimary: boolean) => {
    const form = new FormData()
    form.append('file', file)
    form.append('is_primary', String(isPrimary))
    return request<Resume>('/resumes', { method: 'POST', body: form })
  },
  setPrimaryResume: (id: number) => request<Resume>(`/resumes/${id}/primary`, { method: 'PATCH' }),
  deleteResume: (id: number) => request<void>(`/resumes/${id}`, { method: 'DELETE' }),

  listApplications: () => request<Application[]>('/applications'),

  triggerRun: () => request<Run>('/runs', { method: 'POST' }),
  getRun: (id: number) => request<Run>(`/runs/${id}`),
  getLatestRun: () => request<Run>('/runs/latest'),
}
