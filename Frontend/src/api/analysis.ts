import { api } from '@/lib/fetch-client'
import type {
  AnalysisRequest,
  AnalysisCreateResponse,
  AnalysisRead,
  AnalysisResultRead,
  FeedbackItemRead,
  RewriteRequest,
  RewriteResult,
} from '@/types/analysis'
import type { CursorPage } from '@/types/common'

export const analysisApi = {
  create: (data: AnalysisRequest) =>
    api.post<AnalysisCreateResponse>('/api/v1/analysis', data),

  get: (analysisId: string) =>
    api.get<AnalysisRead>(`/api/v1/analysis/${analysisId}`),

  getScore: (analysisId: string) =>
    api.get<AnalysisResultRead>(`/api/v1/analysis/${analysisId}/score`),

  getFeedback: (analysisId: string) =>
    api.get<FeedbackItemRead[]>(`/api/v1/analysis/${analysisId}/feedback`),

  rewrite: (analysisId: string, data: RewriteRequest) =>
    api.post<RewriteResult>(`/api/v1/analysis/${analysisId}/rewrite`, data),

  list: (limit = 20, offset = 0) =>
    api.get<CursorPage<AnalysisRead>>(`/api/v1/analysis?limit=${limit}&offset=${offset}`),

  stats: () =>
    api.get<{ total_analyses: number; avg_score: number | null }>('/api/v1/analysis/stats'),
}
