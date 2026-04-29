import { useTheme, type ThemePreference } from '../../../hooks/useTheme'

const OPTIONS: { id: ThemePreference; label: string }[] = [
  { id: 'light', label: 'Light' },
  { id: 'dark', label: 'Dark' },
  { id: 'system', label: 'System' },
]

export function AppearanceTab() {
  const { preference, setPreference } = useTheme()

  return (
    <div className="max-w-lg space-y-6">
      <div>
        <h2 className="text-xl font-bold text-ink">Appearance</h2>
      </div>

      <div className="bg-surface-2 border border-divider rounded-xl overflow-hidden">
        <div className="px-6 py-4 border-b border-divider">
          <p className="text-[11px] text-ink-faint uppercase tracking-wider">Theme</p>
        </div>
        <div role="radiogroup" aria-label="Theme" className="divide-y divide-divider/60">
          {OPTIONS.map((opt) => {
            const selected = preference === opt.id
            return (
              <button
                key={opt.id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => setPreference(opt.id)}
                className={`w-full flex items-center justify-between gap-4 px-6 py-4 text-left transition-colors ${
                  selected ? 'bg-surface' : 'hover:bg-surface/60'
                }`}
              >
                <p className="text-ink text-sm font-medium">{opt.label}</p>
                <span
                  aria-hidden
                  className={`shrink-0 w-4 h-4 rounded-full border-2 transition-colors ${
                    selected
                      ? 'border-accent bg-accent'
                      : 'border-divider-strong bg-transparent'
                  }`}
                />
              </button>
            )
          })}
        </div>
      </div>
    </div>
  )
}
