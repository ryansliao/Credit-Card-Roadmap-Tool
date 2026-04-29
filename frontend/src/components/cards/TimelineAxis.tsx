/** TimelineAxis — the year-tick ruler rendered at the top of a timeline chart.
 * Renders year tick labels plus "Today" (start) and a formatted end-date label.
 * This is a pure presentational primitive; all data-prep is done by the caller.
 */
export interface YearTick {
  pct: number
  label: string
}

export interface TimelineAxisProps {
  /** Array of year ticks to render (label + left percentage). */
  yearTicks: YearTick[]
  /** Timestamp for the end of the range, used to format the "End" label. */
  endMs: number
}

export function TimelineAxis({ yearTicks, endMs }: TimelineAxisProps) {
  return (
    <div className="relative w-full h-full">
      {yearTicks.map((t) => (
        <div
          key={t.label}
          className="absolute top-0 bottom-0 flex items-center text-[11px] text-ink-faint"
          style={{ left: `${t.pct}%`, transform: 'translateX(-50%)' }}
        >
          {t.label}
        </div>
      ))}
      <div
        className="absolute flex items-center text-[11px] text-ink-muted font-semibold whitespace-nowrap pointer-events-none"
        style={{ left: 0, top: 0, bottom: 0, transform: 'translateX(-50%)' }}
      >
        Today
      </div>
      <div
        className="absolute flex items-center text-[11px] text-ink-muted font-semibold whitespace-nowrap pointer-events-none"
        style={{ right: 0, top: 0, bottom: 0, transform: 'translateX(50%)' }}
        title={new Date(endMs).toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
          day: 'numeric',
        })}
      >
        {new Date(endMs).toLocaleDateString(undefined, {
          year: 'numeric',
          month: 'short',
        })}
      </div>
    </div>
  )
}
