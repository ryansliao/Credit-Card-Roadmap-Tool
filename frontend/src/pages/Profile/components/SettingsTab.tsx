import { useState } from 'react'
import { useAuth } from '../../../auth/useAuth'
import { Button } from '../../../components/ui/Button'

export function SettingsTab() {
  const { user, signOut, setUsername } = useAuth()

  const [usernameDraft, setUsernameDraft] = useState('')
  const [usernameEditing, setUsernameEditing] = useState(false)
  const [usernameError, setUsernameError] = useState<string | null>(null)
  const [usernameSaving, setUsernameSaving] = useState(false)

  if (!user) return null

  function startEditUsername() {
    setUsernameDraft(user!.username ?? '')
    setUsernameError(null)
    setUsernameEditing(true)
  }

  function cancelEditUsername() {
    setUsernameEditing(false)
    setUsernameError(null)
  }

  async function saveUsername() {
    const trimmed = usernameDraft.trim()
    if (!trimmed) {
      setUsernameError('Username cannot be empty.')
      return
    }
    setUsernameSaving(true)
    setUsernameError(null)
    try {
      await setUsername(trimmed)
      setUsernameEditing(false)
    } catch (e: unknown) {
      setUsernameError(e instanceof Error ? e.message : 'Failed to save username.')
    } finally {
      setUsernameSaving(false)
    }
  }

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h2 className="text-ink font-semibold text-xl tracking-tight">Settings</h2>
        <p className="text-ink-muted text-sm mt-1">Manage your account details.</p>
      </div>

      {/* Profile card */}
      <div className="bg-surface border border-divider rounded-xl shadow-card overflow-hidden">
        {/* Avatar + name header */}
        <div className="flex items-center gap-4 px-6 py-5 border-b border-divider">
          {user.picture ? (
            <img
              src={user.picture}
              alt=""
              className="w-14 h-14 rounded-full shrink-0"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-14 h-14 rounded-full bg-surface-2 flex items-center justify-center text-ink-muted text-xl font-bold shrink-0">
              {(user.username ?? user.name).charAt(0).toUpperCase()}
            </div>
          )}
          <div className="min-w-0">
            <p className="text-ink font-semibold text-base truncate">{user.username ?? user.name}</p>
            {user.email && (
              <p className="text-ink-muted text-sm truncate">{user.email}</p>
            )}
          </div>
        </div>

        {/* Fields */}
        <div className="divide-y divide-divider">
          {/* Username row */}
          <div className="px-6 py-4">
            <p className="text-[11px] text-ink-faint uppercase tracking-wider mb-2">Username</p>
            {usernameEditing ? (
              <div className="space-y-2">
                <input
                  type="text"
                  value={usernameDraft}
                  onChange={(e) => setUsernameDraft(e.target.value)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') saveUsername()
                    if (e.key === 'Escape') cancelEditUsername()
                  }}
                  autoFocus
                  maxLength={40}
                  className="w-full bg-surface border border-divider hover:border-divider-strong focus:border-accent focus:ring-2 focus:ring-accent-soft text-ink text-sm rounded-md px-3 py-2 outline-none transition-colors"
                  placeholder="e.g. johndoe"
                />
                {usernameError && (
                  <p className="text-[11px] text-neg">{usernameError}</p>
                )}
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant="primary"
                    size="sm"
                    onClick={saveUsername}
                    disabled={usernameSaving}
                    loading={usernameSaving}
                  >
                    Save
                  </Button>
                  <Button
                    type="button"
                    variant="ghost"
                    size="sm"
                    onClick={cancelEditUsername}
                    disabled={usernameSaving}
                  >
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <p className="text-ink text-sm">
                  {user.username ?? <span className="text-ink-faint italic">Not set</span>}
                </p>
                <button
                  type="button"
                  onClick={startEditUsername}
                  className="text-xs font-medium text-accent hover:opacity-80 transition-opacity shrink-0"
                >
                  {user.username ? 'Change' : 'Set username'}
                </button>
              </div>
            )}
          </div>

          {/* Name row */}
          <div className="px-6 py-4">
            <p className="text-[11px] text-ink-faint uppercase tracking-wider mb-1">Name</p>
            <p className="text-ink text-sm">{user.name}</p>
          </div>

          {/* Email row */}
          <div className="px-6 py-4">
            <p className="text-[11px] text-ink-faint uppercase tracking-wider mb-1">Email</p>
            <p className="text-ink text-sm">
              {user.email ?? <span className="text-ink-faint italic">Not set</span>}
            </p>
          </div>
        </div>
      </div>

      {/* Sign out */}
      <div>
        <button
          type="button"
          onClick={signOut}
          className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-md text-neg border border-neg/30 hover:bg-neg/10 hover:border-neg/50 transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
            <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
            <polyline points="16 17 21 12 16 7" />
            <line x1="21" y1="12" x2="9" y2="12" />
          </svg>
          Sign out
        </button>
      </div>
    </div>
  )
}
