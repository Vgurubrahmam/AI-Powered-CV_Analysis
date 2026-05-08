// Shared API response types mirroring backend schemas

export interface APIResponseMeta {
  request_id: string
  timestamp: string
  version: string
}

export interface APIResponseError {
  code: string
  message: string
  details: Record<string, unknown>
}

export interface APIResponse<T> {
  data: T | null
  error: APIResponseError | null
  meta: APIResponseMeta
}

export interface CursorPage<T> {
  items: T[]
  total_count: number
  has_more: boolean
}

export type SortOrder = 'asc' | 'desc'
