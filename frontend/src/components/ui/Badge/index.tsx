import type { HTMLAttributes, ReactNode } from 'react'

type Tone = 'neutral' | 'accent' | 'pos' | 'neg' | 'warn' | 'info'

interface Props extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
  children: ReactNode
}

const TONE: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-ink border-divider',
  accent:  'bg-accent-soft text-accent border-accent/30',
  pos:     'bg-pos/10 text-pos border-pos/30',
  neg:     'bg-neg/10 text-neg border-neg/30',
  warn:    'bg-warn/10 text-warn border-warn/30',
  info:    'bg-info/10 text-info border-info/30',
}

export function Badge({ tone = 'neutral', children, className = '', ...rest }: Props) {
  return (
    <span
      {...rest}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-semibold uppercase tracking-[0.08em] ${TONE[tone]} ${className}`}
    >
      {children}
    </span>
  )
}
