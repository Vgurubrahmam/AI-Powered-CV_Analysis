import { api } from '@/lib/fetch-client'
import type { UserRead, UserUpdate } from '@/types/user'

export const usersApi = {
  getMe: () => api.get<UserRead>('/api/v1/users/me'),
  updateMe: (data: UserUpdate) => api.put<UserRead>('/api/v1/users/me', data),
}
