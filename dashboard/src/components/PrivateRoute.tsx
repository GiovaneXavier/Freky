import { ReactNode } from 'react'
import { useAuth } from '../hooks/useAuth'
import { LoginPage } from '../pages/LoginPage'

export function PrivateRoute({ children }: { children: ReactNode }) {
  const { user } = useAuth()
  return user ? <>{children}</> : <LoginPage />
}
