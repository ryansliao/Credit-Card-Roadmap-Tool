import type { CardResult, RoadmapResponse } from '../../../../api/client'
import type { ResolvedCard } from '../../lib/resolveScenarioCards'
import { Toggle } from '../../../../components/ui/Toggle'
import { Tooltip } from '../../../../components/ui/Tooltip'
import { CardThumb, EditAffordance } from './TimelineGlyphs'
import type { SecondaryAnnual } from './GroupSection'
import type { Range } from './lib/timelineUtils'
import { parseDate, pctOf } from './lib/timelineUtils'
import {
  formatCardIncome,
  formatDate,
  formatSecondaryAnnual,
} from './lib/timelineFormatters'
import {
  cardEafActive,
} from '../../../../utils/cardIncome'
import {
  formatMoney,
  formatPoints,
  pointsUnitLabel,
} from '../../../../utils/format'
import { measureEafLabelPx } from './lib/timelineUtils'

const CARD_ROW_HEIGHT = 50
const DIVIDER_CLASS = 'border-b border-divider'

export interface CardRowProps {
  wc: ResolvedCard
  cr: CardResult | null
  secondary: SecondaryAnnual | null
  color: string
  range: Range
  roadmapStatus: RoadmapResponse['cards'][number] | undefined
  isUpdating: boolean
  isStale: boolean
  includeSubs: boolean
  rightColumnPx: number
  onToggleEnabled: (cardId: number, enabled: boolean) => void
  onEditCard: (wc: ResolvedCard) => void
}

function SubEarningSegment({
  range,
  segmentStartMs,
  segmentEndMs,
  lifetimeStartMs,
  lifetimeEndMs,
  rowHeight,
  barHeight,
  title,
}: {
  range: Range
  /** When the SUB starts being earned (sub_start_date or opening_date). */
  segmentStartMs: number
  /** When the SUB is projected to be earned. */
  segmentEndMs: number
  /** Lifetime bar bounds — used to round corners only when the segment
   * touches a rounded edge of the lifetime bar. */
  lifetimeStartMs: number
  lifetimeEndMs: number
  rowHeight: number
  barHeight: number
  /** Native tooltip text shown on hover. The segment owns its own
   * pointer-events handling so this fires reliably regardless of any
   * parent `title` attributes. */
  title: string | null
}) {
  // Yellow segment of the lifetime bar covering [sub_start_date or opening,
  // sub_projected_earn_date]. Same y-position and height as the lifetime
  // bar, opaque fill so the segment reads as part of the bar — not a
  // separate overlay. Caller suppresses the segment when the SUB cannot be
  // earned (no projected_earn_date).
  const visStart = Math.max(segmentStartMs, range.startMs)
  const visEnd = Math.min(segmentEndMs, range.endMs)
  if (visEnd <= visStart) return null

  const startPct = pctOf(range, visStart)
  const widthPct = pctOf(range, visEnd) - startPct
  if (widthPct <= 0) return null

  const top = (rowHeight - barHeight) / 2

  // Match the lifetime bar's rounded corners only when the SUB segment
  // actually touches a rounded edge of the lifetime bar (which is itself
  // only rounded when it sits inside the visible range).
  const lifetimeRoundsLeft = lifetimeStartMs > range.startMs
  const lifetimeRoundsRight = lifetimeEndMs < range.endMs
  const segmentTouchesLifetimeLeft = segmentStartMs <= lifetimeStartMs
  const segmentTouchesLifetimeRight = segmentEndMs >= lifetimeEndMs
  const roundLeft = lifetimeRoundsLeft && segmentTouchesLifetimeLeft
  const roundRight = lifetimeRoundsRight && segmentTouchesLifetimeRight
  const roundedClass = `${roundLeft ? 'rounded-l-full' : ''} ${roundRight ? 'rounded-r-full' : ''}`.trim()

  // Match the lifetime bar's visual style: semi-transparent fill + 1px
  // colored border. Uses the same `${color}33` alpha pattern the rest of
  // the bar uses (33/255 ≈ 20% alpha).
  const yellow = 'var(--chart-sub)'
  // Skip the right border when the indigo lifetime bar abuts this segment —
  // otherwise both bars render a 1px border at the seam and it reads as 2px.
  const abutsLifetimeRight = !segmentTouchesLifetimeRight
  return (
    <div
      className={`absolute ${roundedClass}`}
      style={{
        left: `${startPct}%`,
        width: `${widthPct}%`,
        top,
        height: barHeight,
        backgroundColor: `color-mix(in oklab, ${yellow} 20%, transparent)`,
        borderTop: `1px solid ${yellow}`,
        borderBottom: `1px solid ${yellow}`,
        borderLeft: `1px solid ${yellow}`,
        borderRight: abutsLifetimeRight ? 'none' : `1px solid ${yellow}`,
        zIndex: 31,
      }}
      title={title ?? undefined}
    />
  )
}

export function CardRow({
  wc,
  cr,
  secondary,
  color,
  range,
  roadmapStatus,
  isUpdating,
  isStale,
  includeSubs,
  rightColumnPx,
  onToggleEnabled,
  onEditCard,
}: CardRowProps) {
  // For PC cards, the bar shows when THIS PRODUCT was active — starting at
  // product_changed_date, not at the original account opening_date (which
  // is preserved through the PC for 5/24 purposes but isn't when this card
  // existed). Fresh opens fall through to added_date (= opening_date).
  const productStartStr = wc.product_changed_date ?? wc.added_date
  const addedMs = parseDate(productStartStr).getTime()
  const closedMs = wc.closed_date ? parseDate(wc.closed_date).getTime() : range.endMs

  const barStartPct = pctOf(range, Math.max(addedMs, range.startMs))
  const barEndPct = pctOf(range, Math.min(closedMs, range.endMs))
  const barWidthPct = Math.max(0, barEndPct - barStartPct)

  const enabled = wc.is_enabled

  // The projected SUB earn date (auto-computed by the backend from spend
  // rate, with the SUB-window cap applied) is the single source of truth
  // for the SUB earn marker.
  const subProjectedDate = roadmapStatus?.sub_projected_earn_date ?? null
  const subProjectedMs = subProjectedDate ? parseDate(subProjectedDate).getTime() : null

  // SUB earning segment: anchored at opening_date and ending at the
  // projected SUB-earn date. Rendered whenever a projected date exists,
  // even when the card is disabled or the scenario is stale — those cases
  // gray the segment via ``dimmed`` instead of removing it (mirrors the
  // lifetime bar's disabled styling). The segment is suppressed only when
  // the SUB has no projection at all (no SUB, expired, or no calc has
  // been run yet).
  const subSegment = (() => {
    if (!subProjectedMs) return null
    const startMs = parseDate(wc.added_date).getTime()
    if (subProjectedMs <= startMs) return null
    if (subProjectedMs <= range.startMs || startMs >= range.endMs) return null
    return { startMs, endMs: subProjectedMs }
  })()

  // Detect "card has a SUB but cannot earn it" — drives the lifetime-bar
  // warning tooltip. roadmap status carries the authoritative classification:
  // "expired" (window closed) or "pending" with no projected date (rate too
  // low to reach the minimum within the window).
  const subStatus = roadmapStatus?.sub_status
  const subUnearnable =
    enabled &&
    !!wc.sub_points &&
    !!wc.sub_min_spend &&
    (subStatus === 'expired' ||
      (subStatus === 'pending' && roadmapStatus?.sub_projected_earn_date == null))

  // Tooltip text shown on hover over the yellow SUB segment. The segment
  // itself owns the listener (pointer-events: auto) so the tooltip fires
  // reliably whenever the cursor is over the yellow region.
  const subSegmentTitle = subProjectedDate
    ? subStatus === 'earned'
      ? `SUB earned ${formatDate(subProjectedDate)}`
      : `SUB projected to earn ${formatDate(subProjectedDate)}`
    : null
  // Per-card income and EAF are driven by the last calc's `cr`, not the live
  // toggle, so the numbers (and layout) stay stable when the user flips
  // `is_enabled` — only a recalc refreshes what's shown.
  //
  // Show dashed placeholders ("---/yr", "--- EAF") whenever the row has
  // no real data to display: the card is currently disabled, OR it was added
  // since the last calc and isn't in `cr`. This is preferred over a bare
  // em-dash because it keeps the unit labels in place so the columns read
  // consistently and the user can tell what figure will appear once they
  // recalc / re-enable.
  const showPlaceholders = !enabled || !cr
  const incomeLabel = showPlaceholders ? '—/yr' : formatCardIncome(cr, includeSubs)
  const eafValue = showPlaceholders ? null : cardEafActive(cr, includeSubs)
  const eafLabelText = showPlaceholders
    ? '— EAF'
    : eafValue != null
      ? `${formatMoney(eafValue)} EAF`
      : null

  const subTooltipLine = enabled
    ? subUnearnable
      ? subStatus === 'expired'
        ? 'SUB window expired — cannot be earned'
        : 'SUB cannot be earned at the current spend rate'
      : subProjectedDate
        ? subStatus === 'earned'
          ? `SUB earned: ${formatDate(subProjectedDate)}`
          : `SUB projected: ${formatDate(subProjectedDate)}`
        : 'No SUB'
    : 'Disabled — not contributing'

  const tooltip = [
    wc.product_changed_date
      ? `Product change: ${formatDate(wc.product_changed_date)} (account opened ${formatDate(wc.added_date)})`
      : `Added: ${formatDate(wc.added_date)}`,
    wc.closed_date ? `Closed: ${formatDate(wc.closed_date)}` : null,
    subTooltipLine,
    enabled && showPlaceholders ? 'Click Calculate to see EAF and income' : null,
    !showPlaceholders && eafValue != null ? `EAF: ${formatMoney(eafValue)}` : null,
    !showPlaceholders && incomeLabel ? `Income: ${incomeLabel.replace(/^\+/, '')}` : null,
  ]
    .filter(Boolean)
    .join('\n')

  const barHeight = 24
  const rowHeight = CARD_ROW_HEIGHT

  // display: contents on the wrapper lets the two children act as direct grid
  // cells while sharing a hover state so the entire row highlights together.
  return (
    <div className="group contents">
      {/* Left gutter */}
      <div
        className={`flex items-center gap-2 px-3 ${DIVIDER_CLASS} transition-colors group-hover:bg-surface-2/60`}
        style={{ height: rowHeight }}
      >
        <button
          type="button"
          onClick={() => onEditCard(wc)}
          className={`flex-1 min-w-0 text-left flex items-center gap-3 group-hover:text-accent transition-colors ${
            enabled ? '' : 'opacity-50'
          }`}
          title="Edit card"
        >
          <CardThumb slug={wc.photo_slug} name={wc.card_name ?? ''} />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-ink truncate">
              {wc.card_name ?? `Card #${wc.card_id}`}
            </div>
            {incomeLabel && (
              <div
                className={`text-xs text-ink-faint truncate transition-opacity ${isStale ? 'opacity-50' : ''}`}
                title={isStale ? 'Out of date' : undefined}
              >
                {incomeLabel}
                {secondary && (
                  <>
                    <span className="mx-1 text-ink-faint">·</span>
                    {formatSecondaryAnnual(secondary)}
                  </>
                )}
                {wc.credit_totals
                  .filter((t) => t.value > 0)
                  .map((t) => (
                    <span key={`${t.kind}-${t.currency_id ?? 'cash'}`}>
                      <span className="mx-1 text-ink-faint">·</span>
                      {t.kind === 'cash'
                        ? `${formatMoney(t.value)} Credits`
                        : `${formatPoints(t.value)} ${pointsUnitLabel(t.currency_name)} Credits`}
                    </span>
                  ))}
                {cr && (cr.housing_fee_dollars ?? 0) > 0 && (
                  <span title="3% rent/mortgage payment processing fee, deducted from EAF">
                    <span className="mx-1 text-ink-faint">·</span>
                    <span className="text-neg">
                      −{formatMoney(cr.housing_fee_dollars ?? 0)} Housing Fee
                    </span>
                  </span>
                )}
              </div>
            )}
          </div>
          <EditAffordance />
        </button>
        {/* Owned cards are always part of the wallet — they get a padlock
            badge in place of the toggle. To remove an owned card from a
            scenario use the close-date or product-change overlay in the
            modal. Future cards keep the toggle since they're hypothetical. */}
        {wc.is_future ? (
          <Toggle
            checked={enabled}
            disabled={isUpdating}
            onChange={(e) => onToggleEnabled(wc.instance_id, e.target.checked)}
            aria-label={enabled ? 'Disable card' : 'Enable card'}
            title={enabled ? 'Disable card' : 'Enable card'}
          />
        ) : (
          <Tooltip label="Owned card — locked from this view">
            <span className="shrink-0 text-warn inline-flex items-center justify-center w-9 h-5">
              <svg
                width="18"
                height="18"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2" />
                <path d="M7 11V7a5 5 0 0 1 10 0v4" />
              </svg>
            </span>
          </Tooltip>
        )}
      </div>

      {/* Right column: timeline bar */}
      <div
        className={`relative ${DIVIDER_CLASS}`}
        style={{ height: rowHeight }}
        title={tooltip}
      >
        {barWidthPct > 0 &&
          (() => {
            // When a SUB segment exists, render the lifetime indigo bar
            // STARTING AT the SUB's end so amber and indigo sit side-by-side
            // (no transparency stack, no border overlap).
            const cutStartMs = subSegment ? subSegment.endMs : addedMs
            const cutStartPct = pctOf(range, Math.max(cutStartMs, range.startMs))
            const cutWidthPct = Math.max(0, barEndPct - cutStartPct)
            if (cutWidthPct <= 0) return null
            const roundLeft = !subSegment && addedMs > range.startMs
            const roundRight = closedMs < range.endMs
            const roundedClass =
              `${roundLeft ? 'rounded-l-full' : ''} ${roundRight ? 'rounded-r-full' : ''}`.trim()
            return (
              <div
                className={`absolute ${roundedClass}`}
                style={{
                  left: `${cutStartPct}%`,
                  width: `${cutWidthPct}%`,
                  top: (rowHeight - barHeight) / 2,
                  height: barHeight,
                  backgroundColor: enabled
                    ? `color-mix(in oklab, ${color} 20%, transparent)`
                    : `color-mix(in oklab, var(--color-divider-strong) 25%, transparent)`,
                  border: `1px solid ${enabled ? color : 'var(--color-divider-strong)'}`,
                  opacity: enabled ? 1 : 0.55,
                  zIndex: 30,
                }}
              />
            )
          })()}
        {barWidthPct > 0 &&
          eafLabelText != null &&
          (() => {
            const labelText = eafLabelText
            const baseColor = showPlaceholders
              ? 'text-ink-faint'
              : eafValue != null && eafValue < 0
                ? 'text-pos'
                : eafValue != null && eafValue > 0
                  ? 'text-neg'
                  : 'text-ink'
            const labelClass = `${baseColor} ${isStale ? 'opacity-50' : ''}`
            const PADDING = 8
            const GAP = 4
            // When the container isn't measured yet, fall back to drawing the
            // label inside the bar (matching prior behaviour); truncation will
            // handle visual overflow until the observer fires.
            if (rightColumnPx === 0) {
              return (
                <div
                  className="absolute flex items-center justify-end text-xs font-semibold pointer-events-none"
                  style={{
                    left: `${barStartPct}%`,
                    width: `${barWidthPct}%`,
                    top: (rowHeight - barHeight) / 2,
                    height: barHeight,
                    zIndex: 30,
                  }}
                >
                  <span className={`truncate px-2 ${labelClass}`}>{labelText}</span>
                </div>
              )
            }
            const labelPx = measureEafLabelPx(labelText)
            const barPx = (barWidthPct / 100) * rightColumnPx
            const barStartPx = (barStartPct / 100) * rightColumnPx
            const rightRoomPx = rightColumnPx - (barStartPx + barPx)
            const leftRoomPx = barStartPx
            let placement: 'inside' | 'right' | 'left' = 'inside'
            if (barPx < labelPx + PADDING * 2) {
              if (rightRoomPx >= labelPx + GAP) placement = 'right'
              else if (leftRoomPx >= labelPx + GAP) placement = 'left'
              else placement = 'inside'
            }
            const top = (rowHeight - barHeight) / 2
            if (placement === 'inside') {
              return (
                <div
                  className="absolute flex items-center justify-end text-xs font-semibold pointer-events-none"
                  style={{
                    left: `${barStartPct}%`,
                    width: `${barWidthPct}%`,
                    top,
                    height: barHeight,
                    zIndex: 30,
                  }}
                >
                  <span className={`truncate px-2 ${labelClass}`}>{labelText}</span>
                </div>
              )
            }
            if (placement === 'right') {
              return (
                <div
                  className="absolute flex items-center text-xs font-semibold whitespace-nowrap pointer-events-none"
                  style={{
                    left: `${barStartPct + barWidthPct}%`,
                    top,
                    height: barHeight,
                    paddingLeft: GAP,
                    zIndex: 30,
                  }}
                >
                  <span className={labelClass}>{labelText}</span>
                </div>
              )
            }
            // left
            return (
              <div
                className="absolute flex items-center justify-end text-xs font-semibold whitespace-nowrap pointer-events-none"
                style={{
                  right: `${100 - barStartPct}%`,
                  top,
                  height: barHeight,
                  paddingRight: GAP,
                  zIndex: 30,
                }}
              >
                <span className={labelClass}>{labelText}</span>
              </div>
            )
          })()}
        {subSegment && (
          <SubEarningSegment
            range={range}
            segmentStartMs={subSegment.startMs}
            segmentEndMs={subSegment.endMs}
            lifetimeStartMs={addedMs}
            lifetimeEndMs={closedMs}
            rowHeight={rowHeight}
            barHeight={barHeight}
            title={subSegmentTitle}
          />
        )}
      </div>
    </div>
  )
}
