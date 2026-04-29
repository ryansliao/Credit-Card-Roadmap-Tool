import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Add the oxblood accent rule above the label. */
  accent?: boolean
  className?: string
}

export function Eyebrow({ children, accent = false, className = '' }: Props) {
  return (
    <div className={className}>
      {accent && (
        <span
          aria-hidden="true"
          className="block bg-accent mb-2"
          style={{ width: 28, height: 2 }}
        />
      )}
      <span className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">
        {children}
      </span>
    </div>
  )
}
