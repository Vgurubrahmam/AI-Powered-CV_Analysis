import React, { createContext, useCallback, useContext, useEffect, useState } from 'react'
import { authApi } from '@/api/auth'
import { usersApi } from '@/api/users'
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

  // On mount: try fetching current user (cookie is sent automatically)
  // If the cookie is valid, we get the user profile. If not, we're logged out.
  useEffect(() => {
    usersApi
      .getMe()
      .then(setUser)
      .catch(() => {
        // No valid cookie — user is not logged in
        setUser(null)
      })
      .finally(() => setIsLoading(false))
  }, [])

  const login = useCallback(async (email: string, password: string) => {
    // Backend sets HttpOnly cookies via Set-Cookie headers
    await authApi.login({ email, password })
    // Now fetch the user profile (cookie is already set)
    const me = await usersApi.getMe()
    setUser(me)
  }, [])

  const signup = useCallback(async (email: string, password: string) => {
    // Register the account, then log in (which sets cookies)
    await authApi.signup({ email, password })
    await authApi.login({ email, password })
    const me = await usersApi.getMe()
    setUser(me)
  }, [])

  const logout = useCallback(async () => {
    try {
      await authApi.logout()
    } catch {
      // best-effort
    } finally {
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
