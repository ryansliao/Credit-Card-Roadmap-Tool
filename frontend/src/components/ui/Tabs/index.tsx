import { useId, type ReactNode } from 'react'

interface TabItem<T extends string = string> {
  id: T
  label: ReactNode
}

interface Props<T extends string = string> {
  items: TabItem<T>[]
  active: T
  onChange: (id: T) => void
  className?: string
}

export function Tabs<T extends string = string>({ items, active, onChange, className = '' }: Props<T>) {
  const groupId = useId()
  return (
    <div role="tablist" aria-label="Tabs" className={`border-b border-divider flex gap-6 ${className}`}>
      {items.map((it) => {
        const selected = it.id === active
        return (
          <button
            key={it.id}
            id={`${groupId}-${it.id}`}
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(it.id)}
            className={`relative py-3 text-sm font-medium transition-colors ${
              selected ? 'text-ink' : 'text-ink-muted hover:text-ink'
            }`}
          >
            {it.label}
            <span
              aria-hidden="true"
              className={`absolute left-0 right-0 -bottom-px h-0.5 ${selected ? 'bg-accent' : 'bg-transparent'}`}
            />
          </button>
        )
      })}
    </div>
  )
}
