import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  type ReactNode,
} from 'react'
import {
  authApi,
  setAuthToken,
  clearAuthToken,
  getAuthToken,
  type AuthUser,
} from '../api/client'

interface AuthState {
  user: AuthUser | null
  isAuthenticated: boolean
  isLoading: boolean
  signIn: (credential: string) => Promise<void>
  signOut: () => void
}

const AuthContext = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  // On mount, validate existing token
  useEffect(() => {
    const token = getAuthToken()
    if (!token) {
      setIsLoading(false)
      return
    }
    authApi
      .me()
      .then(setUser)
      .catch(() => {
        clearAuthToken()
      })
      .finally(() => setIsLoading(false))
  }, [])

  const signIn = useCallback(async (credential: string) => {
    const result = await authApi.googleSignIn(credential)
    if (result.token) {
      setAuthToken(result.token)
    }
    setUser(result)
  }, [])

  const signOut = useCallback(() => {
    clearAuthToken()
    setUser(null)
    window.location.href = '/'
  }, [])

  return (
    <AuthContext.Provider
      value={{
        user,
        isAuthenticated: user !== null,
        isLoading,
        signIn,
        signOut,
      }}
    >
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth(): AuthState {
  const ctx = useContext(AuthContext)
  if (!ctx) throw new Error('useAuth must be used within AuthProvider')
  return ctx
}
