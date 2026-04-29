import { Money } from '../ui/Money'

interface Props {
  name: string
  /** Display valuation in USD. */
  valuation: number
  /** Note shown under the name. */
  note?: string
  /** Show as "0" struck-through when user has zeroed out the credit. */
  zeroedOut?: boolean
  className?: string
}

export function CreditRow({ name, valuation, note, zeroedOut = false, className = '' }: Props) {
  return (
    <div className={`flex items-baseline justify-between gap-4 py-2 border-b border-divider last:border-b-0 ${className}`}>
      <div className="min-w-0">
        <div className="text-sm font-medium text-ink truncate">{name}</div>
        {note && <div className="text-xs text-ink-faint">{note}</div>}
      </div>
      <div className={zeroedOut ? 'line-through text-ink-faint' : ''}>
        <Money value={valuation} mono />
      </div>
    </div>
  )
}
