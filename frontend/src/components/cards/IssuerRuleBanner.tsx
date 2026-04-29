import type { ReactNode } from 'react'
import { Surface } from '../ui/Surface'

interface Props {
  rule: string
  message: ReactNode
  className?: string
}

export function IssuerRuleBanner({ rule, message, className = '' }: Props) {
  return (
    <Surface variant="inset" padding="sm" className={`border-warn/40 ${className}`}>
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="text-warn text-lg leading-none">⚠</span>
        <div className="space-y-0.5">
          <div className="text-[10px] uppercase tracking-[0.18em] font-semibold text-warn">{rule}</div>
          <div className="text-sm text-ink">{message}</div>
        </div>
      </div>
    </Surface>
  )
}
