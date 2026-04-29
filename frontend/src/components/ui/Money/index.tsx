import { formatMoney, formatMoneyExact } from '../../../utils/format'

type Tone = 'neutral' | 'pos' | 'neg' | 'auto'
type Precision = 0 | 2 | 'auto'

interface Props {
  value: number
  precision?: Precision
  tone?: Tone
  /** Render in feature-size Fraunces tabular numerals (used for hero stats). */
  feature?: boolean
  /** Default true — render in JetBrains Mono tabular numerals. Set false for inline body. */
  mono?: boolean
  className?: string
}

function toneClass(tone: Tone, value: number): string {
  if (tone === 'pos') return 'text-pos'
  if (tone === 'neg') return 'text-neg'
  if (tone === 'auto') return value < 0 ? 'text-neg' : value > 0 ? 'text-pos' : 'text-ink'
  return 'text-ink'
}

export function Money({
  value,
  precision = 'auto',
  tone = 'neutral',
  feature = false,
  mono = true,
  className = '',
}: Props) {
  const formatted =
    precision === 0
      ? formatMoney(value)
      : precision === 2
        ? formatMoneyExact(value)
        : Number.isInteger(value)
          ? formatMoney(value)
          : formatMoneyExact(value)

  const fontClass = feature ? 'tnum-feature' : mono ? 'tnum-mono' : 'tnum'

  return (
    <span className={`${fontClass} ${toneClass(tone, value)} ${className}`}>
      {formatted}
    </span>
  )
}
