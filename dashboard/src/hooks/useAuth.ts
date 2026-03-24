import { createContext, useContext, useState, useCallback } from 'react'

const API = import.meta.env.VITE_API_URL ?? 'http://localhost:8000'
const TOKEN_KEY = 'freky_token'

export interface AuthUser {
  username: string
  role: string
}

interface AuthContextValue {
  user: AuthUser | null
  token: string | null
  login: (username: string, password: string) => Promise<void>
  logout: () => void
}

export const AuthContext = createContext<AuthContextValue>({
  user: null,
  token: null,
  login: async () => {},
  logout: () => {},
})

export function useAuth() {
  return useContext(AuthContext)
}

function parseToken(token: string): AuthUser | null {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]))
    return { username: payload.sub, role: payload.role }
  } catch {
    return null
  }
}

export function useAuthState(): AuthContextValue {
  const stored = localStorage.getItem(TOKEN_KEY)
  const [token, setToken] = useState<string | null>(stored)
  const [user, setUser] = useState<AuthUser | null>(stored ? parseToken(stored) : null)

  const login = useCallback(async (username: string, password: string) => {
    const body = new URLSearchParams({ username, password })
    const res = await fetch(`${API}/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
      body,
    })
    if (!res.ok) {
      const err = await res.json().catch(() => ({}))
      throw new Error(err.detail ?? 'Usuário ou senha incorretos')
    }
    const data = await res.json()
    localStorage.setItem(TOKEN_KEY, data.access_token)
    setToken(data.access_token)
    setUser({ username: data.username, role: data.role })
  }, [])

  const logout = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY)
    setToken(null)
    setUser(null)
  }, [])

  return { user, token, login, logout }
}
