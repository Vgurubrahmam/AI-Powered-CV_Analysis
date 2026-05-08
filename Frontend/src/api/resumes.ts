import { api } from '@/lib/fetch-client'
import type { ResumeRead, ResumeUploadResponse, ParsedResumeRead } from '@/types/resume'
import type { CursorPage } from '@/types/common'

export const resumesApi = {
  upload: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return api.post<ResumeUploadResponse>('/api/v1/resumes/upload', form)
  },

  get: (resumeId: string) =>
    api.get<ResumeRead>(`/api/v1/resumes/${resumeId}`),

  getParsed: (resumeId: string) =>
    api.get<ParsedResumeRead>(`/api/v1/resumes/${resumeId}/parsed`),

  delete: (resumeId: string) =>
    api.delete<{ deleted: boolean; resume_id: string }>(`/api/v1/resumes/${resumeId}`),

  list: (limit = 20, offset = 0) =>
    api.get<CursorPage<ResumeRead>>(`/api/v1/resumes?limit=${limit}&offset=${offset}`),
}
