import { createContext, useContext, useCallback, type ReactNode } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { fetchMe, login as apiLogin, logout as apiLogout, type User } from '../api/auth'

interface AuthContextValue {
  user: User | null
  isLoading: boolean
  login: (loginStr: string, password: string) => Promise<User>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthContextValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient()

  const { data: user, isLoading } = useQuery({
    queryKey: ['auth', 'me'],
    queryFn: fetchMe,
    retry: false,
    staleTime: 1000 * 60 * 5,
  })

  const login = useCallback(async (loginStr: string, password: string) => {
    const u = await apiLogin(loginStr, password)
    queryClient.setQueryData(['auth', 'me'], u)
    return u
  }, [queryClient])

  const logout = useCallback(async () => {
    await apiLogout()
    queryClient.setQueryData(['auth', 'me'], null)
    queryClient.removeQueries({ queryKey: ['auth'] })
  }, [queryClient])

  return (
    <AuthContext.Provider value={{ user: user ?? null, isLoading, login, logout }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
