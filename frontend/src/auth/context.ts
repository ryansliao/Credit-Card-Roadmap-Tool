import { createContext } from 'react'
import type { AuthUser } from '../api/client'

export interface AuthState {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  needsUsername: boolean
  signIn: (credential: string) => Promise<void>
  login: (email: string, password: string) => Promise<void>
  register: (username: string, email: string, password: string) => Promise<void>
  setUsername: (username: string) => Promise<void>
  signOut: () => void
}

export const AuthContext = createContext<AuthState | null>(null)
