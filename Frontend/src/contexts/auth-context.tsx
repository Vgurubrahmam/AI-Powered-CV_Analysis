import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi } from '@/api/auth'
import { usersApi } from '@/api/users'
import { tokenStorage } from '@/lib/fetch-client'
import { queryClient } from '@/lib/query-client'
import type { UserRead } from '@/types/user'

interface AuthContextValue {
  user: UserRead | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<void>
  signup: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useState<UserRead | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // On mount: if we have a token, fetch current user
  useEffect(() => {
    const token = tokenStorage.getAccess()
    if (!token) {
      setIsLoading(false)
      return
    }
    usersApi
      .getMe()
      .then(setUser)
      .catch(() => tokenStorage.clear())
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    const pair = await authApi.login({ email, password })
    tokenStorage.set(pair.access_token, pair.refresh_token)
    const me = await usersApi.getMe()
    setUser(me)
  }, [])

  const signup = useCallback(async (email: string, password: string) => {
    // Register the account, then immediately log in
    await authApi.signup({ email, password })
    const pair = await authApi.login({ email, password })
    tokenStorage.set(pair.access_token, pair.refresh_token)
    const me = await usersApi.getMe()
    setUser(me)
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // best-effort
    } finally {
      tokenStorage.clear()
      queryClient.clear()
      setUser(null)
    }
  }, [])

  return (
    <AuthContext.Provider
      value={{ user, isAuthenticated: !!user, isLoading, login, signup, logout }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
