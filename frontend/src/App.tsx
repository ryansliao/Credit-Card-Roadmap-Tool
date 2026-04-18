import { Component, type ErrorInfo, type FormEvent, type ReactNode, useEffect, useRef, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes, Navigate, NavLink, Link } from 'react-router-dom'
import RoadmapTool from './pages/RoadmapTool/index'
import Home from './pages/Home'
import Profile from './pages/Profile'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/useAuth'

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

const GOOGLE_CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID ?? ''

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

function SignInDropdown() {
  const { signIn, login, register } = useAuth()
  const [open, setOpen] = useState(false)
  const [tab, setTab] = useState<'signin' | 'signup'>('signin')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [username, setLocalUsername] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const googleBtnRef = useRef<HTMLDivElement>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open || !window.google || !googleBtnRef.current) return
    window.google.accounts.id.initialize({
      client_id: GOOGLE_CLIENT_ID,
      callback: (response) => {
        signIn(response.credential)
        setOpen(false)
      },
    })
    window.google.accounts.id.renderButton(googleBtnRef.current, {
      theme: 'filled_black',
      size: 'large',
      type: 'standard',
      shape: 'rectangular',
      width: 260,
    })
  }, [open, signIn])

  useEffect(() => {
    if (!open) return
    function handleClick(e: MouseEvent) {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClick)
    return () => document.removeEventListener('mousedown', handleClick)
  }, [open])

  function resetForm() {
    setEmail('')
    setPassword('')
    setLocalUsername('')
    setError('')
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      if (tab === 'signup') {
        await register(username, email, password)
      } else {
        await login(email, password)
      }
      setOpen(false)
      resetForm()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  const inputClass =
    'w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500'

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => { setOpen(!open); resetForm() }}
        className="text-sm font-medium px-5 py-2 rounded-full text-slate-300 hover:text-white hover:bg-slate-800 transition-colors"
      >
        Sign in
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-72 bg-slate-800 border border-slate-700 rounded-xl shadow-xl z-50">
          <div className="flex border-b border-slate-700">
            <button
              type="button"
              onClick={() => { setTab('signin'); setError('') }}
              className={`flex-1 text-sm py-2.5 font-medium transition-colors ${
                tab === 'signin'
                  ? 'text-white border-b-2 border-indigo-500'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => { setTab('signup'); setError('') }}
              className={`flex-1 text-sm py-2.5 font-medium transition-colors ${
                tab === 'signup'
                  ? 'text-white border-b-2 border-indigo-500'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              Sign up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-3">
            {tab === 'signup' && (
              <input
                type="text"
                placeholder="Username"
                value={username}
                onChange={(e) => setLocalUsername(e.target.value)}
                className={inputClass}
                required
                minLength={3}
                maxLength={30}
              />
            )}
            <input
              type="email"
              placeholder="Email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              className={inputClass}
              required
            />
            <input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className={inputClass}
              required
              minLength={tab === 'signup' ? 8 : undefined}
            />
            {error && <p className="text-red-400 text-xs">{error}</p>}
            <button
              type="submit"
              disabled={loading}
              className="w-full text-sm font-medium py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white transition-colors"
            >
              {loading ? '...' : tab === 'signin' ? 'Sign in' : 'Create account'}
            </button>
          </form>

          <div className="px-4 pb-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex-1 border-t border-slate-700" />
              <span className="text-slate-500 text-xs">or</span>
              <div className="flex-1 border-t border-slate-700" />
            </div>
            <div ref={googleBtnRef} />
          </div>
        </div>
      )}
    </div>
  )
}

function UsernamePrompt() {
  const { setUsername } = useAuth()
  const [value, setValue] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  async function handleSubmit(e: FormEvent) {
    e.preventDefault()
    setError('')
    setLoading(true)
    try {
      await setUsername(value)
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60">
      <div className="bg-slate-800 border border-slate-700 rounded-xl shadow-2xl p-6 w-80">
        <h2 className="text-lg font-bold text-white mb-1">Choose a username</h2>
        <p className="text-slate-400 text-sm mb-4">Pick a username to finish setting up your account.</p>
        <form onSubmit={handleSubmit} className="space-y-3">
          <input
            type="text"
            placeholder="Username"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            className="w-full bg-slate-900 border border-slate-600 rounded-lg px-3 py-2 text-sm text-white placeholder-slate-500 focus:outline-none focus:border-indigo-500"
            required
            minLength={3}
            maxLength={30}
            pattern="[a-zA-Z0-9_]{3,30}"
            title="3-30 characters: letters, numbers, underscores"
            autoFocus
          />
          {error && <p className="text-red-400 text-xs">{error}</p>}
          <button
            type="submit"
            disabled={loading}
            className="w-full text-sm font-medium py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white transition-colors"
          >
            {loading ? '...' : 'Continue'}
          </button>
        </form>
      </div>
    </div>
  )
}

function Nav() {
  const { user, isAuthenticated, isLoading, signOut } = useAuth()

  return (
    <nav className="bg-slate-900 border-b border-slate-700 px-6 py-2.5 flex items-center gap-2">
      <Link to="/" className="text-white font-bold text-lg mr-6 hover:text-slate-200 transition-colors">
        CardSolver
      </Link>
      {isAuthenticated && (
        <NavLink
          to="/roadmap-tool"
          className={({ isActive }) =>
            `text-sm font-medium px-5 py-2 rounded-full transition-colors ${
              isActive
                ? 'text-white bg-slate-800'
                : 'text-slate-300 hover:text-white hover:bg-slate-800'
            }`
          }
        >
          Roadmap Tool
        </NavLink>
      )}
      <div className="flex-1" />
      {!isLoading && (
        isAuthenticated && user ? (
          <div className="flex items-center gap-3">
            <Link to="/profile" className="flex items-center gap-2 px-3 py-1 rounded-full text-slate-300 hover:text-white hover:bg-slate-800 transition-colors -mr-2">
              {user.picture && (
                <img
                  src={user.picture}
                  alt=""
                  className="w-7 h-7 rounded-full"
                  referrerPolicy="no-referrer"
                />
              )}
              <span className="text-sm hidden sm:inline">{user.username ?? user.name}</span>
            </Link>
            <button
              type="button"
              onClick={signOut}
              className="text-sm font-medium px-5 py-2 rounded-full text-slate-300 hover:text-white hover:bg-slate-800 transition-colors ml-2"
            >
              Sign out
            </button>
          </div>
        ) : (
          <SignInDropdown />
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
    return <Navigate to="/" replace />
  }

  return <>{children}</>
}

function UsernameGate() {
  const { needsUsername, isAuthenticated } = useAuth()
  if (isAuthenticated && needsUsername) return <UsernamePrompt />
  return null
}

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <BrowserRouter>
          <div className="h-dvh min-h-0 flex flex-col overflow-hidden bg-slate-950 text-slate-100">
            <Nav />
            <UsernameGate />
            <main className="flex-1 min-h-0 p-6 flex flex-col overflow-hidden">
              <ErrorBoundary>
                <div className="flex-1 min-h-0 min-w-0 flex flex-col">
                  <Routes>
                    <Route path="/" element={<Home />} />
                    <Route
                      path="/profile"
                      element={
                        <AuthGate>
                          <Profile />
                        </AuthGate>
                      }
                    />
                    <Route
                      path="/roadmap-tool"
                      element={
                        <AuthGate>
                          <RoadmapTool />
                        </AuthGate>
                      }
                    />
                    <Route
                      path="/roadmap-tool/wallets/:walletId"
                      element={
                        <AuthGate>
                          <RoadmapTool />
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
