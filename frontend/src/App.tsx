import { Component, type ErrorInfo, type ReactNode, useEffect, useRef } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes, Navigate } from 'react-router-dom'
import WalletTool from './pages/WalletTool/index'
import { AuthProvider, useAuth } from './auth/AuthContext'

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: {
            client_id: string
            callback: (response: { credential: string }) => void
            auto_select?: boolean
          }) => void
          renderButton: (
            parent: HTMLElement,
            options: {
              theme?: string
              size?: string
              type?: string
              shape?: string
              width?: number
            },
          ) => void
        }
      }
    }
  }
}

interface ErrorBoundaryState {
  hasError: boolean
  error: Error | null
}

class ErrorBoundary extends Component<{ children: ReactNode }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, error: null }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error('Unhandled render error:', error, info)
  }

  render() {
    if (this.state.hasError) {
      return (
        <div className="p-8 text-center">
          <h2 className="text-xl font-bold text-red-400 mb-2">Something went wrong</h2>
          <p className="text-slate-400 text-sm mb-4">{this.state.error?.message}</p>
          <button
            className="px-4 py-2 bg-slate-700 rounded text-sm hover:bg-slate-600"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Try again
          </button>
        </div>
      )
    }
    return this.props.children
  }
}

const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 30_000 } },
})

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''

function GoogleSignInButton() {
  const { signIn } = useAuth()
  const buttonRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!window.google || !buttonRef.current) return
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: (response) => {
        signIn(response.credential)
      },
    })
    window.google.accounts.id.renderButton(buttonRef.current, {
      theme: 'filled_black',
      size: 'medium',
      type: 'standard',
      shape: 'rectangular',
    })
  }, [signIn])

  return <div ref={buttonRef} />
}

function Nav() {
  const { user, isAuthenticated, isLoading, signOut } = useAuth()

  return (
    <nav className="bg-slate-900 border-b border-slate-700 px-6 py-3 flex items-center gap-2">
      <span className="text-white font-bold text-lg mr-6">Credit Card Optimizer</span>
      <div className="flex-1" />
      {!isLoading && (
        isAuthenticated && user ? (
          <div className="flex items-center gap-3">
            {user.picture && (
              <img
                src={user.picture}
                alt=""
                className="w-7 h-7 rounded-full"
                referrerPolicy="no-referrer"
              />
            )}
            <span className="text-slate-300 text-sm hidden sm:inline">{user.name}</span>
            <button
              type="button"
              onClick={signOut}
              className="text-slate-400 hover:text-slate-200 text-sm ml-2"
            >
              Sign out
            </button>
          </div>
        ) : (
          <GoogleSignInButton />
        )
      )}
    </nav>
  )
}

function AuthGate({ children }: { children: ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth()

  if (isLoading) {
    return (
      <div className="text-center text-slate-400 py-20">Loading...</div>
    )
  }

  if (!isAuthenticated) {
    return (
      <div className="max-w-md mx-auto mt-32 text-center">
        <h2 className="text-2xl font-bold text-white mb-3">Welcome</h2>
        <p className="text-slate-400 mb-6">
          Sign in with Google to access your credit card wallets.
        </p>
        <div className="flex justify-center">
          <GoogleSignInButton />
        </div>
      </div>
    )
  }

  return <>{children}</>
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <div className="h-dvh min-h-0 flex flex-col overflow-hidden bg-slate-950 text-slate-100">
            <Nav />
            <main className="flex-1 min-h-0 p-6 flex flex-col overflow-hidden">
              <ErrorBoundary>
                <div className="flex-1 min-h-0 min-w-0 flex flex-col">
                  <Routes>
                    <Route
                      path="/"
                      element={
                        <AuthGate>
                          <WalletTool />
                        </AuthGate>
                      }
                    />
                    <Route
                      path="/wallets/:walletId"
                      element={
                        <AuthGate>
                          <WalletTool />
                        </AuthGate>
                      }
                    />
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </div>
              </ErrorBoundary>
            </main>
          </div>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
