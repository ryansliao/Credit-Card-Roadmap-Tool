import type { ReactNode } from 'react'
import { Eyebrow } from '../Eyebrow'

interface Props {
  /** Eyebrow / label text above the value. */
  label: ReactNode
  /** The hero number content — typically a `<Money feature>` or `<Points feature>`. */
  value: ReactNode
  /** Optional small caption below the value. */
  caption?: ReactNode
  /** Add the oxblood accent rule above the eyebrow. */
  accent?: boolean
  /** Right-align the entire stack. Defaults to left. */
  align?: 'left' | 'right'
  className?: string
}

export function Stat({ label, value, caption, accent = false, align = 'left', className = '' }: Props) {
  const alignClass = align === 'right' ? 'text-right items-end' : 'text-left items-start'
  return (
    <div className={`flex flex-col ${alignClass} ${className}`}>
      <Eyebrow accent={accent}>{label}</Eyebrow>
      <div className="mt-1">{value}</div>
      {caption && (
        <div className="text-xs text-ink-muted mt-1">{caption}</div>
      )}
    </div>
  )
}
