import type { ReactNode } from 'react'
import { Surface } from '../ui/Surface'
import { Eyebrow } from '../ui/Eyebrow'
import { Heading } from '../ui/Heading'
import { Money } from '../ui/Money'
import { Badge } from '../ui/Badge'

interface BreakdownItem {
  label: string
  value: ReactNode
  tone?: 'neutral' | 'pos' | 'neg'
}

interface Props {
  issuer: string
  network?: string
  cardName: string
  netEvAnnual: number
  badge?: { tone: 'accent' | 'pos' | 'neg' | 'warn' | 'info' | 'neutral'; label: string }
  breakdown?: BreakdownItem[]
  className?: string
  onClick?: () => void
}

export function CardTile({
  issuer,
  network,
  cardName,
  netEvAnnual,
  badge,
  breakdown,
  className = '',
  onClick,
}: Props) {
  const issuerLine = network ? `${issuer} · ${network}` : issuer
  return (
    <Surface
      variant="panel"
      padding="md"
      className={`flex flex-col gap-3 ${onClick ? 'cursor-pointer hover:bg-surface-2 transition-colors' : ''} ${className}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <Eyebrow>{issuerLine}</Eyebrow>
          <Heading level={4} className="mt-1">{cardName}</Heading>
        </div>
        {badge && <Badge tone={badge.tone}>{badge.label}</Badge>}
      </div>
      <div className="flex items-baseline justify-between border-t border-divider pt-3">
        <Eyebrow>Net EV / yr</Eyebrow>
        <Money value={netEvAnnual} feature tone="auto" />
      </div>
      {breakdown && breakdown.length > 0 && (
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
          {breakdown.map((b) => (
            <span key={b.label}>
              {b.label}{' '}
              <span className="text-ink font-medium">{b.value}</span>
            </span>
          ))}
        </div>
      )}
    </Surface>
  )
}
