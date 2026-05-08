import { api } from '@/lib/fetch-client'
import type { LoginRequest, SignupRequest, TokenPair } from '@/types/auth'
import type { UserRead } from '@/types/user'

export const authApi = {
  signup: (data: SignupRequest) =>
    api.post<UserRead>('/api/v1/auth/register', data, { skipAuth: true }),

  login: (data: LoginRequest) =>
    api.post<TokenPair>('/api/v1/auth/login', data, { skipAuth: true }),

  refresh: (refresh_token: string) =>
    api.post<TokenPair>('/api/v1/auth/refresh', { refresh_token }, { skipAuth: true }),

  logout: () =>
    api.delete<{ message: string }>('/api/v1/auth/logout'),
}
