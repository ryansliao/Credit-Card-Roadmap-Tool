import { useTheme, type ThemePreference } from '../../../hooks/useTheme'

const OPTIONS: { id: ThemePreference; label: string; preview: 'light' | 'dark' | 'split' }[] = [
  { id: 'light', label: 'Light', preview: 'light' },
  { id: 'dark', label: 'Dark', preview: 'dark' },
  { id: 'system', label: 'System', preview: 'split' },
]

export function AppearanceTab() {
  const { preference, setPreference } = useTheme()

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-ink font-semibold text-xl tracking-tight">Appearance</h2>
        <p className="text-ink-muted text-sm mt-1">Choose how the app looks.</p>
      </div>

      <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-3">
        {OPTIONS.map((opt) => {
          const selected = preference === opt.id
          return (
            <button
              key={opt.id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => setPreference(opt.id)}
              className={`bg-surface border rounded-xl shadow-card overflow-hidden transition-all text-left ${
                selected
                  ? 'border-accent ring-2 ring-accent'
                  : 'border-divider hover:border-divider-strong hover:-translate-y-0.5'
              }`}
            >
              <ThemePreview preview={opt.preview} />
              <div className="px-4 py-3 flex items-center justify-between">
                <span className="text-ink text-sm font-medium">{opt.label}</span>
                <span
                  aria-hidden
                  className={`shrink-0 w-4 h-4 rounded-full border-2 transition-colors ${
                    selected
                      ? 'border-accent bg-accent'
                      : 'border-divider-strong bg-transparent'
                  }`}
                />
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function ThemePreview({ preview }: { preview: 'light' | 'dark' | 'split' }) {
  if (preview === 'split') {
    return (
      <div className="relative h-24 overflow-hidden">
        <div className="absolute inset-0 grid grid-cols-2">
          <PreviewMockup tone="light" />
          <PreviewMockup tone="dark" />
        </div>
        <div className="absolute inset-y-0 left-1/2 w-px bg-divider-strong" />
      </div>
    )
  }
  return <PreviewMockup tone={preview} />
}

function PreviewMockup({ tone }: { tone: 'light' | 'dark' }) {
  const styles = tone === 'light'
    ? { bg: '#f3f4f6', surface: '#ffffff', ink: '#111827', accent: '#b04256', divider: '#e5e7eb' }
    : { bg: '#0b0d11', surface: '#16181d', ink: '#f5f5f5', accent: '#b04256', divider: '#2a2e36' }
  return (
    <div className="h-24 p-3 flex flex-col gap-2" style={{ background: styles.bg }}>
      <div className="flex items-center gap-1.5">
        <div className="h-1.5 w-8 rounded-full" style={{ background: styles.accent }} />
        <div className="h-1 w-12 rounded-full" style={{ background: styles.divider }} />
      </div>
      <div className="rounded p-2 flex-1 flex flex-col gap-1.5" style={{ background: styles.surface }}>
        <div className="h-1.5 rounded-full" style={{ background: styles.ink, opacity: 0.65, width: '60%' }} />
        <div className="h-1 rounded-full" style={{ background: styles.ink, opacity: 0.25, width: '85%' }} />
        <div className="h-1 rounded-full" style={{ background: styles.ink, opacity: 0.25, width: '70%' }} />
      </div>
    </div>
  )
}
