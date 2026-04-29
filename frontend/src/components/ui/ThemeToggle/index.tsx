import { useTheme } from '../../../hooks/useTheme'

interface Props {
  className?: string
}

export function ThemeToggle({ className = '' }: Props) {
  const { theme, toggle } = useTheme()
  const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className={`text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink ${className}`}
    >
      {theme === 'dark' ? 'Light' : 'Dark'}
    </button>
  )
}
