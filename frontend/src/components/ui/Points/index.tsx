import { formatPoints, formatPointsExact, pointsUnitLabel } from '../../../utils/format'

interface Props {
  value: number
  /** Currency unit suffix (e.g., 'BP', 'UR', 'MR'). When provided, rendered after the number. */
  unit?: string
  /** When unit is set, optionally use the helper to look up a localized label. */
  unitFromCurrencyName?: string
  /** When true, render exact integer; otherwise use compact formatting. */
  exact?: boolean
  feature?: boolean
  mono?: boolean
  className?: string
}

export function Points({
  value,
  unit,
  unitFromCurrencyName,
  exact = false,
  feature = false,
  mono = true,
  className = '',
}: Props) {
  const formatted = exact ? formatPointsExact(value) : formatPoints(value)
  const resolvedUnit = unit ?? (unitFromCurrencyName ? pointsUnitLabel(unitFromCurrencyName) : undefined)
  const fontClass = feature ? 'tnum-feature' : mono ? 'tnum-mono' : 'tnum'

  return (
    <span className={`${fontClass} text-ink ${className}`}>
      {formatted}
      {resolvedUnit && <span className="text-ink-faint ml-1 text-[0.85em]">{resolvedUnit}</span>}
    </span>
  )
}
