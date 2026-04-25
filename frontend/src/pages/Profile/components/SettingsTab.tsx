import { useState } from 'react'
import { useAuth } from '../../../auth/useAuth'

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
        <h2 className="text-xl font-bold text-white">Settings</h2>
        <p className="text-slate-400 text-sm mt-1">Manage your account details.</p>
      </div>

      {/* Profile card */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
        {/* Avatar + name header */}
        <div className="flex items-center gap-4 px-6 py-5 border-b border-slate-700">
          {user.picture ? (
            <img
              src={user.picture}
              alt=""
              className="w-14 h-14 rounded-full shrink-0"
              referrerPolicy="no-referrer"
            />
          ) : (
            <div className="w-14 h-14 rounded-full bg-slate-700 flex items-center justify-center text-slate-300 text-xl font-bold shrink-0">
              {(user.username ?? user.name).charAt(0).toUpperCase()}
            </div>
          )}
          <div className="min-w-0">
            <p className="text-white font-semibold text-base truncate">{user.username ?? user.name}</p>
            {user.email && (
              <p className="text-slate-400 text-sm truncate">{user.email}</p>
            )}
          </div>
        </div>

        {/* Fields */}
        <div className="divide-y divide-slate-700/60">
          {/* Username row */}
          <div className="px-6 py-4">
            <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-2">Username</p>
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
                  className="w-full bg-slate-700 border border-slate-600 focus:border-indigo-500 text-white text-sm rounded-lg px-3 py-2 outline-none"
                  placeholder="e.g. johndoe"
                />
                {usernameError && (
                  <p className="text-red-400 text-xs">{usernameError}</p>
                )}
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={saveUsername}
                    disabled={usernameSaving}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors disabled:opacity-50"
                  >
                    {usernameSaving ? 'Saving…' : 'Save'}
                  </button>
                  <button
                    type="button"
                    onClick={cancelEditUsername}
                    disabled={usernameSaving}
                    className="px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-white hover:bg-slate-700 transition-colors"
                  >
                    Cancel
                  </button>
                </div>
              </div>
            ) : (
              <div className="flex items-center justify-between gap-3">
                <p className="text-white text-sm">
                  {user.username ?? <span className="text-slate-500 italic">Not set</span>}
                </p>
                <button
                  type="button"
                  onClick={startEditUsername}
                  className="text-xs text-indigo-400 hover:text-indigo-300 transition-colors shrink-0"
                >
                  {user.username ? 'Change' : 'Set username'}
                </button>
              </div>
            )}
          </div>

          {/* Name row */}
          <div className="px-6 py-4">
            <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1">Name</p>
            <p className="text-white text-sm">{user.name}</p>
          </div>

          {/* Email row */}
          <div className="px-6 py-4">
            <p className="text-[11px] text-slate-500 uppercase tracking-wider mb-1">Email</p>
            <p className="text-white text-sm">
              {user.email ?? <span className="text-slate-500 italic">Not set</span>}
            </p>
          </div>
        </div>
      </div>

      {/* Sign out */}
      <div>
        <button
          type="button"
          onClick={signOut}
          className="text-sm font-medium px-4 py-2 rounded-lg text-red-400 hover:text-red-300 hover:bg-red-950/40 border border-red-900/40 hover:border-red-800/60 transition-colors"
        >
          Sign out
        </button>
      </div>
    </div>
  )
}
