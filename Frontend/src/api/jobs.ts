import { api } from '@/lib/fetch-client'
import type { JDCreate, JDRead, ParsedJDRead } from '@/types/job'
import type { CursorPage } from '@/types/common'

export const jobsApi = {
  create: (data: JDCreate) =>
    api.post<JDRead>('/api/v1/jobs', data),

  get: (jobId: string) =>
    api.get<JDRead>(`/api/v1/jobs/${jobId}`),

  getParsed: (jobId: string) =>
    api.get<ParsedJDRead>(`/api/v1/jobs/${jobId}/parsed`),

  list: (limit = 20, offset = 0) =>
    api.get<CursorPage<JDRead>>(`/api/v1/jobs?limit=${limit}&offset=${offset}`),
}
