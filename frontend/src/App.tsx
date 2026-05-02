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
        <div className="max-w-md mx-auto py-20 text-center space-y-4">
          <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-neg/10 text-neg">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="8" x2="12" y2="12" />
              <line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
          </div>
          <Heading level={3}>Something went wrong</Heading>
          <p className="text-ink-muted text-sm">{this.state.error?.message ?? 'Unknown error'}</p>
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
      <Button
        variant="secondary"
        size="sm"
        onClick={() => { setOpen(!open); resetForm() }}
      >
        Sign in
      </Button>
      {open && (
        <div className="absolute right-0 mt-2 w-80 bg-surface rounded-xl shadow-modal z-50 overflow-hidden">
          <div className="flex border-b border-divider">
            <button
              type="button"
              onClick={() => { setTab('signin'); setError('') }}
              className={`relative flex-1 text-sm py-3 font-medium transition-colors ${
                tab === 'signin' ? 'text-ink' : 'text-ink-faint hover:text-ink'
              }`}
            >
              Sign in
              {tab === 'signin' && (
                <span aria-hidden="true" className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
              )}
            </button>
            <button
              type="button"
              onClick={() => { setTab('signup'); setError('') }}
              className={`relative flex-1 text-sm py-3 font-medium transition-colors ${
                tab === 'signup' ? 'text-ink' : 'text-ink-faint hover:text-ink'
              }`}
            >
              Create account
              {tab === 'signup' && (
                <span aria-hidden="true" className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
              )}
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
            {error && <p className="text-[11px] text-neg">{error}</p>}
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
              <span className="text-[11px] uppercase tracking-wider text-ink-faint font-medium">or</span>
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
        <form onSubmit={handleSubmit} className="space-y-4">
          <p className="text-ink-muted text-sm">Pick a username to finish setting up your account.</p>
          <Field label="Username" hint="3–30 characters: letters, numbers, underscores">
            <Input
              type="text"
              placeholder="username"
              value={value}
              onChange={(e) => setValue(e.target.value)}
              required
              minLength={3}
              maxLength={30}
              pattern="[a-zA-Z0-9_]{3,30}"
              autoFocus
            />
          </Field>
          {error && <p className="text-[11px] text-neg">{error}</p>}
          <Button variant="primary" type="submit" className="w-full" loading={loading}>
            Continue
          </Button>
        </form>
      </ModalBody>
    </Modal>
  )
}

function Nav() {
  const { user, isAuthenticated, isLoading, signOut } = useAuth()

  return (
    <nav className="bg-surface border-b border-divider px-6 h-14 flex items-center gap-2">
      <Link to="/" className="text-base font-bold text-ink hover:text-accent transition-colors mr-6">
        CardSolver
      </Link>
      {isAuthenticated && (
        <NavLink
          to="/roadmap-tool"
          className={({ isActive }) =>
            `relative text-sm font-medium px-1 py-4 transition-colors ${
              isActive ? 'text-ink' : 'text-ink-faint hover:text-ink'
            }`
          }
        >
          {({ isActive }) => (
            <>
              Roadmap Tool
              {isActive && (
                <span aria-hidden="true" className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
              )}
            </>
          )}
        </NavLink>
      )}
      <div className="flex-1" />
      {!isLoading && (
        isAuthenticated && user ? (
          <div className="flex items-center gap-2">
            <Link
              to="/profile"
              className="flex items-center gap-2 px-2 py-1.5 rounded-md text-ink-faint hover:text-ink hover:bg-surface-2 transition-colors"
            >
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
            <Button variant="ghost" size="sm" onClick={signOut}>
              Sign out
            </Button>
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
      <div className="text-center text-ink-faint py-20 text-sm">Loading…</div>
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
