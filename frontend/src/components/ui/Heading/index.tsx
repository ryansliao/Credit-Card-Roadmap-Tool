import type { ReactNode } from 'react'

type Level = 1 | 2 | 3 | 4

interface Props {
  level?: Level
  children: ReactNode
  className?: string
  /** Override the rendered tag — defaults to h${level}. */
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'div' | 'span'
}

const STYLE_BY_LEVEL: Record<Level, { fontSize: string; lineHeight: string; letterSpacing: string; weight: number }> = {
  1: { fontSize: '48px', lineHeight: '1.05', letterSpacing: '-0.02em',  weight: 700 },
  2: { fontSize: '28px', lineHeight: '1.15', letterSpacing: '-0.02em',  weight: 700 },
  3: { fontSize: '22px', lineHeight: '1.2',  letterSpacing: '-0.015em', weight: 600 },
  4: { fontSize: '17px', lineHeight: '1.3',  letterSpacing: '-0.01em',  weight: 600 },
}

export function Heading({ level = 2, children, className = '', as }: Props) {
  const Tag = (as ?? `h${level}`) as keyof React.JSX.IntrinsicElements
  const s = STYLE_BY_LEVEL[level]
  return (
    <Tag
      className={`text-ink ${className}`}
      style={{
        fontSize: s.fontSize,
        lineHeight: s.lineHeight,
        letterSpacing: s.letterSpacing,
        fontWeight: s.weight,
      }}
    >
      {children}
    </Tag>
  )
}
