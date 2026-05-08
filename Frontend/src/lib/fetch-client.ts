import type { APIResponse } from '@/types/common'
import { ApiError } from '@/lib/query-client'

const TOKEN_KEY = 'cv_access_token'
const REFRESH_KEY = 'cv_refresh_token'

// ─── Token helpers ───────────────────────────────────────────────────────────

export const tokenStorage = {
  getAccess: () => localStorage.getItem(TOKEN_KEY),
  getRefresh: () => localStorage.getItem(REFRESH_KEY),
  set: (access: string, refresh: string) => {
    localStorage.setItem(TOKEN_KEY, access)
    localStorage.setItem(REFRESH_KEY, refresh)
  },
  clear: () => {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(REFRESH_KEY)
  },
}

// ─── Refresh lock (prevent parallel refresh storms) ──────────────────────────

let refreshPromise: Promise<void> | null = null

async function doRefresh(): Promise<void> {
  const refresh_token = tokenStorage.getRefresh()
  if (!refresh_token) throw new Error('No refresh token')

  const res = await fetch('/api/v1/auth/refresh', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ refresh_token }),
  })

  if (!res.ok) {
    tokenStorage.clear()
    window.location.href = '/login'
    throw new Error('Refresh failed')
  }

  const json: APIResponse<{ access_token: string; refresh_token: string; token_type: string }> =
    await res.json()
  tokenStorage.set(json.data.access_token, json.data.refresh_token)
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

  if (!skipAuth) {
    const token = tokenStorage.getAccess()
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }

  const res = await fetch(path, { ...init, headers })

  // Auto-refresh on 401
  if (res.status === 401 && !isRetry && !skipAuth) {
    await refreshOnce()
    return apiFetch<T>(path, { ...options, isRetry: true })
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
  return json.data
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
