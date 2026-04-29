import type { ReactNode } from 'react'

type Level = 1 | 2 | 3 | 4

interface Props {
  level?: Level
  children: ReactNode
  className?: string
  /** Override the rendered tag — defaults to h${level}. */
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'div' | 'span'
}

const STYLE_BY_LEVEL: Record<Level, { fontSize: string; opsz: number; lineHeight: string; letterSpacing: string }> = {
  1: { fontSize: '56px', opsz: 144, lineHeight: '1.05', letterSpacing: '-0.025em' },
  2: { fontSize: '34px', opsz: 96,  lineHeight: '1.1',  letterSpacing: '-0.02em' },
  3: { fontSize: '24px', opsz: 36,  lineHeight: '1.2',  letterSpacing: '-0.015em' },
  4: { fontSize: '18px', opsz: 24,  lineHeight: '1.3',  letterSpacing: '-0.01em' },
}

export function Heading({ level = 2, children, className = '', as }: Props) {
  const Tag = (as ?? `h${level}`) as keyof React.JSX.IntrinsicElements
  const s = STYLE_BY_LEVEL[level]
  return (
    <Tag
      className={`font-display text-ink font-medium ${className}`}
      style={{
        fontSize: s.fontSize,
        lineHeight: s.lineHeight,
        letterSpacing: s.letterSpacing,
        fontVariationSettings: `"opsz" ${s.opsz}, "SOFT" var(--font-display-soft)`,
      }}
    >
      {children}
    </Tag>
  )
}
