import { api } from '@/lib/fetch-client'
import type { LoginRequest, SignupRequest } from '@/types/auth'
import type { UserRead } from '@/types/user'

export const authApi = {
  signup: (data: SignupRequest) =>
    api.post<UserRead>('/api/v1/auth/register', data, { skipAuth: true }),

  login: (data: LoginRequest) =>
    api.post<{ message: string }>('/api/v1/auth/login', data, { skipAuth: true }),

  refresh: () =>
    api.post<{ message: string }>('/api/v1/auth/refresh', undefined, { skipAuth: true }),

  logout: () =>
    api.delete<{ message: string }>('/api/v1/auth/logout'),
}
