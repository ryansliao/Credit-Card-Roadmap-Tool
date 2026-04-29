import { Component, type ErrorInfo, type FormEvent, type ReactNode, useEffect, useRef, useState } from 'react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Route, Routes, Navigate, NavLink, Link } from 'react-router-dom'
import RoadmapTool from './pages/RoadmapTool/index'
import Home from './pages/Home'
import Profile from './pages/Profile'
import Styleguide from './pages/Styleguide'
import { AuthProvider } from './auth/AuthContext'
import { useAuth } from './auth/useAuth'
import { ToastProvider } from './components/ui/Toast'
import { Button } from './components/ui/Button'
import { Input } from './components/ui/Input'
import { Field } from './components/ui/Field'
import { Modal, ModalHeader, ModalBody } from './components/ui/Modal'
import { Heading } from './components/ui/Heading'

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
          <h2 className="text-xl font-bold text-neg mb-2">Something went wrong</h2>
          <p className="text-ink-muted text-sm mb-4">{this.state.error?.message}</p>
          <Button
            variant="secondary"
            onClick={() => this.setState({ hasError: false, error: null })}
          >
            Try again
          </Button>
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
  // Sign-in keys off this single field — username or email both match.
  const [identifier, setIdentifier] = useState('')
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
    setIdentifier('')
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
        // Treat blank email as "not provided" so the backend stores NULL
        // instead of an empty string (which would fail EmailStr validation).
        const trimmed = email.trim()
        await register(username, trimmed === '' ? null : trimmed, password)
      } else {
        await login(identifier.trim(), password)
      }
      setOpen(false)
      resetForm()
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : 'Something went wrong')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="relative" ref={dropdownRef}>
      <button
        type="button"
        onClick={() => { setOpen(!open); resetForm() }}
        className="text-sm font-medium px-5 py-2 rounded-full opacity-75 hover:opacity-100 hover:bg-black/15 transition-colors"
      >
        Sign in
      </button>
      {open && (
        <div className="absolute right-0 mt-2 w-72 bg-surface border border-divider rounded-xl shadow-xl z-50">
          <div className="flex border-b border-divider">
            <button
              type="button"
              onClick={() => { setTab('signin'); setError('') }}
              className={`flex-1 text-sm py-2.5 font-medium transition-colors ${
                tab === 'signin'
                  ? 'text-ink border-b-2 border-accent'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              Sign in
            </button>
            <button
              type="button"
              onClick={() => { setTab('signup'); setError('') }}
              className={`flex-1 text-sm py-2.5 font-medium transition-colors ${
                tab === 'signup'
                  ? 'text-ink border-b-2 border-accent'
                  : 'text-ink-muted hover:text-ink'
              }`}
            >
              Sign up
            </button>
          </div>

          <form onSubmit={handleSubmit} className="p-4 space-y-3">
            {tab === 'signup' ? (
              <>
                <Input
                  type="text"
                  placeholder="Username"
                  value={username}
                  onChange={(e) => setLocalUsername(e.target.value)}
                  required
                  minLength={3}
                  maxLength={30}
                />
                <Input
                  type="email"
                  placeholder="Email (optional)"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                />
              </>
            ) : (
              <Input
                type="text"
                placeholder="Username or email"
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                required
                autoComplete="username"
              />
            )}
            <Input
              type="password"
              placeholder="Password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              minLength={tab === 'signup' ? 8 : undefined}
            />
            {error && <p className="text-neg text-xs">{error}</p>}
            <Button
              variant="primary"
              type="submit"
              className="w-full"
              loading={loading}
            >
              {tab === 'signin' ? 'Sign in' : 'Create account'}
            </Button>
          </form>

          <div className="px-4 pb-4">
            <div className="flex items-center gap-3 mb-3">
              <div className="flex-1 border-t border-divider" />
              <span className="text-ink-faint text-xs">or</span>
              <div className="flex-1 border-t border-divider" />
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
    <Modal open={true} onClose={() => undefined} dismissible={false} size="xs">
      <ModalHeader>
        <Heading level={3}>Choose a username</Heading>
      </ModalHeader>
      <ModalBody>
        <form onSubmit={handleSubmit} className="space-y-3">
          <p className="text-ink-muted text-sm">Pick a username to finish setting up your account.</p>
          <Field label="Username">
            <Input
              type="text"
              placeholder="Username"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
              minLength={3}
              maxLength={30}
              pattern="[a-zA-Z0-9_]{3,30}"
              title="3-30 characters: letters, numbers, underscores"
              autoFocus
            />
          </Field>
          {error && <p className="text-neg text-xs mt-2">{error}</p>}
          <Button variant="primary" type="submit" className="w-full" loading={loading}>
            {loading ? '...' : 'Continue'}
          </Button>
        </form>
      </ModalBody>
    </Modal>
  )
}

function Nav() {
  const { user, isAuthenticated, isLoading, signOut } = useAuth()

  return (
    <nav className="bg-accent text-on-accent px-6 py-2.5 flex items-center gap-2">
      <Link to="/" className="font-bold text-lg mr-6 hover:opacity-80 transition-opacity">
        CardSolver
      </Link>
      {isAuthenticated && (
        <NavLink
          to="/roadmap-tool"
          className={({ isActive }) =>
            `text-sm font-medium px-5 py-2 rounded-full transition-colors ${
              isActive
                ? 'bg-black/20'
                : 'opacity-75 hover:opacity-100 hover:bg-black/15'
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
            <Link to="/profile" className="flex items-center gap-2 px-3 py-1 rounded-full opacity-75 hover:opacity-100 hover:bg-black/15 transition-colors -mr-2">
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
              className="text-sm font-medium px-5 py-2 rounded-full opacity-75 hover:opacity-100 hover:bg-black/15 transition-colors ml-2"
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
        <ToastProvider>
          <div className="h-dvh min-h-0 flex flex-col overflow-hidden bg-page text-ink">
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
                      path="/roadmap-tool/scenarios/:scenarioId"
                      element={
                        <AuthGate>
                          <RoadmapTool />
                        </AuthGate>
                      }
                    />
                    {import.meta.env.VITE_SHOW_STYLEGUIDE === '1' && (
                      <Route path="/styleguide" element={<Styleguide />} />
                    )}
                    <Route path="*" element={<Navigate to="/" replace />} />
                  </Routes>
                </div>
              </ErrorBoundary>
            </main>
          </div>
        </ToastProvider>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  )
}
