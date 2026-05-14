import type { APIResponse } from '@/types/common'
import { ApiError } from '@/lib/query-client'

// Base URL for API calls — empty in dev (Vite proxy handles /api), full URL in production
const API_BASE = import.meta.env.VITE_API_URL ?? ''

// ─── Refresh lock (prevent parallel refresh storms) ──────────────────────────

let refreshPromise: Promise<void> | null = null

async function doRefresh(): Promise<void> {
  const res = await fetch(`${API_BASE}/api/v1/auth/refresh`, {
    method: 'POST',
    credentials: 'include',  // send refresh_token cookie
  })

  if (!res.ok) {
    // Refresh failed — session expired. Don't redirect here;
    // let the caller handle it (auth context will show login page).
    throw new Error('Session expired')
  }
  // New cookies are set automatically by the response Set-Cookie headers
}

async function refreshOnce(): Promise<void> {
  if (!refreshPromise) {
    refreshPromise = doRefresh().finally(() => {
      refreshPromise = null
    })
  }
  return refreshPromise
}

// ─── Core fetch wrapper ──────────────────────────────────────────────────────

interface FetchOptions extends RequestInit {
  skipAuth?: boolean
  isRetry?: boolean
}

async function apiFetch<T>(path: string, options: FetchOptions = {}): Promise<T> {
  const { skipAuth = false, isRetry = false, ...init } = options

  const headers = new Headers(init.headers)
  if (!headers.has('Content-Type') && !(init.body instanceof FormData)) {
    headers.set('Content-Type', 'application/json')
  }

  // Cookies are sent automatically via credentials: 'include'
  // No need to manually attach Authorization headers
  const url = path.startsWith('http') ? path : `${API_BASE}${path}`
  const res = await fetch(url, {
    ...init,
    headers,
    credentials: 'include',  // always send cookies cross-origin
  })

  // Auto-refresh on 401 (only if auth is expected and not already retried)
  if (res.status === 401 && !isRetry && !skipAuth) {
    try {
      await refreshOnce()
      return apiFetch<T>(path, { ...options, isRetry: true })
    } catch {
      // Refresh failed — throw the original 401 so callers can handle it
    }
  }

  if (!res.ok) {
    let message = res.statusText
    let errors: string[] | undefined
    try {
      const body = await res.json()
      // Backend sends: { error: { code, message, details }, data: null, meta: ... }
      if (body.error?.message) {
        message = body.error.message
        errors = [body.error.message]
      } else if (body.errors?.length) {
        // Fallback for array-style errors
        message = body.errors[0]
        errors = body.errors
      }
    } catch {
      // ignore parse error
    }
    throw new ApiError(res.status, message, errors)
  }

  const json: APIResponse<T> = await res.json()
  return json.data as T
}

// ─── Exported helpers ────────────────────────────────────────────────────────

export const api = {
  get: <T>(path: string, opts?: FetchOptions) =>
    apiFetch<T>(path, { method: 'GET', ...opts }),

  post: <T>(path: string, body?: unknown, opts?: FetchOptions) =>
    apiFetch<T>(path, {
      method: 'POST',
      body: body instanceof FormData ? body : JSON.stringify(body),
      ...opts,
    }),

  put: <T>(path: string, body?: unknown, opts?: FetchOptions) =>
    apiFetch<T>(path, {
      method: 'PUT',
      body: JSON.stringify(body),
      ...opts,
    }),

  delete: <T>(path: string, opts?: FetchOptions) =>
    apiFetch<T>(path, { method: 'DELETE', ...opts }),
}
