import { Money } from '../ui/Money'

interface Props {
  category: string
  multiplier: number
  /** Annual spend allocated to this card in this category (USD). */
  allocatedSpend: number
  /** Annual point/$ earn (in display units — caller decides). */
  earn: number
  /** Optional caption shown faded under the category name. */
  caption?: string
  className?: string
}

export function CategoryRow({ category, multiplier, allocatedSpend, earn, caption, className = '' }: Props) {
  return (
    <div className={`grid grid-cols-[1fr_auto_auto_auto] items-baseline gap-x-4 gap-y-1 py-2 border-b border-divider last:border-b-0 ${className}`}>
      <div>
        <div className="text-sm font-medium text-ink">{category}</div>
        {caption && <div className="text-xs text-ink-faint">{caption}</div>}
      </div>
      <div className="tnum-mono text-sm text-ink-muted">{multiplier}×</div>
      <div className="tnum-mono text-sm text-ink-muted text-right"><Money value={allocatedSpend} mono /></div>
      <div className="tnum-mono text-sm text-ink text-right"><Money value={earn} mono /></div>
    </div>
  )
}
