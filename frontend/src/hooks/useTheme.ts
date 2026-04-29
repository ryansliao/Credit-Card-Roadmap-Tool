import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'
export type ThemePreference = 'light' | 'dark' | 'system'

const STORAGE_KEY = 'cs.theme'

function readSystemTheme(): Theme {
  if (typeof window === 'undefined' || !window.matchMedia) return 'light'
  return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

function readInitialTheme(): Theme {
  if (typeof document === 'undefined') return 'light'
  const attr = document.documentElement.getAttribute('data-theme')
  if (attr === 'dark') return 'dark'
  return 'light'
}

function readInitialPreference(): ThemePreference {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch { /* localStorage unavailable */ }
  return 'system'
}

function applyTheme(t: Theme) {
  if (t === 'dark') {
    document.documentElement.setAttribute('data-theme', 'dark')
  } else {
    document.documentElement.removeAttribute('data-theme')
  }
}

/**
 * Reads/writes the active theme. The actual DOM mutation lives here so the
 * inline FOUC-prevention script in index.html and this hook stay in sync.
 */
export function useTheme(): {
  theme: Theme
  preference: ThemePreference
  setPreference: (next: ThemePreference) => void
  setTheme: (next: Theme) => void
  toggle: () => void
} {
  const [theme, setThemeState] = useState<Theme>(readInitialTheme)
  const [preference, setPreferenceState] = useState<ThemePreference>(readInitialPreference)

  const setPreference = useCallback((next: ThemePreference) => {
    setPreferenceState(next)
    if (next === 'system') {
      try { localStorage.removeItem(STORAGE_KEY) } catch { /* ignore */ }
      const resolved = readSystemTheme()
      setThemeState(resolved)
      applyTheme(resolved)
    } else {
      try { localStorage.setItem(STORAGE_KEY, next) } catch { /* ignore */ }
      setThemeState(next)
      applyTheme(next)
    }
  }, [])

  const setTheme = useCallback((next: Theme) => {
    setPreference(next)
  }, [setPreference])

  const toggle = useCallback(() => {
    setPreference(theme === 'dark' ? 'light' : 'dark')
  }, [setPreference, theme])

  useEffect(() => {
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => {
      if (preference !== 'system') return
      const next: Theme = e.matches ? 'dark' : 'light'
      setThemeState(next)
      applyTheme(next)
    }
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [preference])

  return { theme, preference, setPreference, setTheme, toggle }
}
