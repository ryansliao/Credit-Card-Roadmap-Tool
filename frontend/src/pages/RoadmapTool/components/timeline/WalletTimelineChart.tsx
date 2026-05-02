import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  CardResult,
  RoadmapResponse,
  WalletResult,
} from '../../../../api/client'
import type { ResolvedCard } from '../../lib/resolveScenarioCards'
import { today } from '../../../../utils/format'
import { useCardLibrary } from '../../hooks/useCardLibrary'
import { Popover } from '../../../../components/ui/Popover'
import { Button } from '../../../../components/ui/Button'
import { TimelineAxis } from '../../../../components/cards/TimelineAxis'
import { GroupSection } from './GroupSection'
import type { GroupData } from './GroupSection'
import { parseDate, addMonths, pctOf } from './lib/timelineUtils'
import type { Range } from './lib/timelineUtils'
import {
  groupAnnualDollars,
  groupBalanceDollars,
  groupCombinedEaf,
  formatDate,
} from './lib/timelineFormatters'
import {
  buildGroupsFromVisibleCards,
  enrichRuleStatuses,
} from './lib/timelineGroups'

interface Props {
  /** Active scenario id — drives the per-currency CPP / portal-share editors. */
  scenarioId: number
  /** Resolved cards (owned + scenario-future, with overlays layered in). */
  walletCards: ResolvedCard[]
  result: WalletResult | null
  roadmap: RoadmapResponse | undefined
  durationYears: number
  durationMonths: number
  isUpdating: boolean
  isStale: boolean
  /** Scenario-level "Include SUBs" toggle. Applied as a pure display switch
   * on top of already-computed results via sub_eaf_contribution on each
   * CardResult — no recalculation required. */
  includeSubs: boolean
  onToggleEnabled: (cardId: number, enabled: boolean) => void
  onEditCard: (wc: ResolvedCard) => void
  onAddCard: () => void
}

const LEFT_GUTTER = 420 // px
const AXIS_HEIGHT = 32
const DIVIDER_CLASS = 'border-b border-divider'

export function WalletTimelineChart({
  scenarioId,
  walletCards,
  result,
  roadmap,
  durationYears,
  durationMonths,
  isUpdating,
  isStale,
  includeSubs,
  onToggleEnabled,
  onEditCard,
  onAddCard,
}: Props) {
  const [expandedCurrencyId, setExpandedCurrencyId] = useState<number | null>(null)
  const toggleExpanded = (cid: number) =>
    setExpandedCurrencyId((prev) => (prev === cid ? null : cid))

  const { rules: applicableRules, maxSeverity } = useMemo(
    () => enrichRuleStatuses(roadmap),
    [roadmap],
  )

  const range = useMemo<Range>(() => {
    const start = parseDate(today())
    const end = addMonths(start, durationYears * 12 + durationMonths)
    return {
      startMs: start.getTime(),
      endMs: end.getTime(),
      spanMs: Math.max(end.getTime() - start.getTime(), 1),
    }
  }, [durationYears, durationMonths])

  const totalYears = Math.max(durationYears + durationMonths / 12, 1 / 12)

  // Wallet window (fractional years) from the backend; falls back to the
  // duration slider when not provided (e.g. pre-calc render).
  const walletWindowYears = result?.wallet_window_years || totalYears
  const currencyWindowYearsById = useMemo(
    () => result?.currency_window_years ?? {},
    [result],
  )

  const cardResultById = useMemo(() => {
    const m = new Map<number, CardResult>()
    for (const cr of result?.card_results ?? []) m.set(cr.card_id, cr)
    return m
  }, [result])

  const { data: libraryCards } = useCardLibrary()
  const libraryById = useMemo(() => {
    const m = new Map<number, NonNullable<typeof libraryCards>[number]>()
    for (const c of libraryCards ?? []) m.set(c.id, c)
    return m
  }, [libraryCards])

  const roadmapById = useMemo(() => {
    const m = new Map<number, RoadmapResponse['cards'][number]>()
    for (const rc of roadmap?.cards ?? []) m.set(rc.card_id, rc)
    return m
  }, [roadmap])

  const visibleCards = useMemo(() => walletCards ?? [], [walletCards])

  const groups = useMemo<GroupData[]>(() => {
    const rawGroups = buildGroupsFromVisibleCards(
      visibleCards,
      cardResultById,
      libraryById,
      totalYears,
    )
    // Sort by end-of-projection balance (in dollars) descending. Fall back
    // to annual dollar value when balances are absent or equal so groups
    // without calc results still order sensibly.
    return rawGroups.sort((a, b) => {
      const ba = groupBalanceDollars(a)
      const bb = groupBalanceDollars(b)
      if (ba !== bb) return bb - ba
      if (ba === 0 && bb === 0) {
        const ea = groupCombinedEaf(a)
        const eb = groupCombinedEaf(b)
        if (ea !== eb) return ea - eb
      }
      // Order groups by recurring income only (SUB-excluded) so the group
      // sequence stays stable when the user flips the "Include SUBs" toggle.
      const cyA = a.currencyId ? currencyWindowYearsById[String(a.currencyId)] : undefined
      const cyB = b.currencyId ? currencyWindowYearsById[String(b.currencyId)] : undefined
      const da = groupAnnualDollars(a, false, walletWindowYears, cyA)
      const db = groupAnnualDollars(b, false, walletWindowYears, cyB)
      if (da !== db) return db - da
      return a.name.localeCompare(b.name)
    })
  }, [visibleCards, cardResultById, libraryById, totalYears, walletWindowYears, currencyWindowYearsById])

  const yearTicks = useMemo(() => {
    const out: Array<{ pct: number; label: string }> = []
    const startYear = new Date(range.startMs).getFullYear()
    const endYear = new Date(range.endMs).getFullYear()
    for (let y = startYear; y <= endYear; y++) {
      const ms = new Date(y, 0, 1).getTime()
      if (ms < range.startMs || ms > range.endMs) continue
      out.push({ pct: pctOf(range, ms), label: String(y) })
    }
    return out
  }, [range])

  // Observe the scroll container's width so we can decide whether each
  // bar's EAF dollar label fits inside the bar; if not, place it to the
  // right, or to the left when there's no room on either side.
  const scrollRef = useRef<HTMLDivElement>(null)
  const [scrollWidthPx, setScrollWidthPx] = useState(0)
  useEffect(() => {
    const el = scrollRef.current
    if (!el) return
    setScrollWidthPx(el.clientWidth)
    const obs = new ResizeObserver(() => setScrollWidthPx(el.clientWidth))
    obs.observe(el)
    return () => obs.disconnect()
  }, [])
  const rightColumnPx = Math.max(0, scrollWidthPx - LEFT_GUTTER)

  return (
    <div className="bg-surface border border-divider rounded-xl shadow-card min-w-0 min-h-0 h-full flex flex-col overflow-hidden">
      {visibleCards.length === 0 ? (
        <div ref={scrollRef} className="flex-1 min-h-0 overflow-auto">
          <div className="flex flex-col items-center gap-3 py-16">
            <p className="text-ink-muted text-sm font-medium">No cards yet</p>
            <p className="text-ink-faint text-xs -mt-2">Add a card to start your roadmap.</p>
            <Button type="button" variant="primary" onClick={onAddCard}>
              <svg
                width="14"
                height="14"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2.5"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <line x1="12" y1="5" x2="12" y2="19" />
                <line x1="5" y1="12" x2="19" y2="12" />
              </svg>
              Add Card
            </Button>
          </div>
        </div>
      ) : (
        <>
          {visibleCards.length > 0 && (
            <div className="flex items-center gap-2 px-4 pt-3 pb-2 shrink-0">
              <Button
                type="button"
                variant="secondary"
                size="sm"
                onClick={onAddCard}
              >
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
                Add card
              </Button>
              {applicableRules.length > 0 && (
                <Popover
                  side="bottom"
                  portal
                  trigger={({ onClick, ref }) => (
                    <button
                      ref={ref as React.RefObject<HTMLButtonElement>}
                      type="button"
                      onClick={onClick}
                      className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider transition-colors ${
                        maxSeverity === 'violated'
                          ? 'bg-neg/10 text-neg hover:bg-neg/15'
                          : maxSeverity === 'in_effect'
                            ? 'bg-warn/10 text-warn hover:bg-warn/15'
                            : 'bg-accent-soft text-accent hover:bg-accent/15'
                      }`}
                      aria-label="Application rule status"
                      title="Application rule status"
                    >
                      <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
                        <line x1="12" y1="9" x2="12" y2="13" />
                        <line x1="12" y1="17" x2="12.01" y2="17" />
                      </svg>
                      {applicableRules.length === 1 ? 'Rule alert' : `${applicableRules.length} rule alerts`}
                    </button>
                  )}
                >
                  <div className="min-w-[280px] max-w-sm">
                    <p className="text-sm font-semibold text-ink mb-2">Application Rules</p>
                    <p className="text-xs text-ink-muted mb-3">Issuer velocity rules tracked across your cards.</p>
                    <ul className="space-y-2">
                      {applicableRules.map((r) => {
                        const containerClass =
                          r.severity === 'violated'
                            ? 'bg-neg/10 border-neg/30'
                            : r.severity === 'in_effect'
                              ? 'bg-warn/10 border-warn/30'
                              : 'bg-surface-2 border-divider'
                        const titleClass =
                          r.severity === 'violated'
                            ? 'text-neg'
                            : r.severity === 'in_effect'
                              ? 'text-warn'
                              : 'text-ink'
                        const intervalClass =
                          r.severity === 'violated'
                            ? 'text-neg'
                            : r.severity === 'in_effect'
                              ? 'text-warn'
                              : 'text-ink-muted'
                        return (
                          <li key={r.rule_id} className={`rounded-md border px-2.5 py-2 ${containerClass}`}>
                            <div className="flex items-baseline gap-1.5 min-w-0">
                              <span className={`font-medium truncate ${titleClass}`}>{r.rule_name}</span>
                              {r.issuer_name && (
                                <span className="text-[10px] text-ink-faint shrink-0">{r.issuer_name}</span>
                              )}
                            </div>
                            {r.description && (
                              <p className="text-[11px] text-ink-muted mt-0.5">{r.description}</p>
                            )}
                            {r.at_risk_intervals.length > 0 && (
                              <ul className="mt-1 space-y-0.5">
                                {r.at_risk_intervals.map((iv, idx) => (
                                  <li key={idx} className={`text-[11px] ${intervalClass}`}>
                                    At limit <span className="tnum-mono">{formatDate(iv.start)} → {formatDate(iv.end)}</span>
                                  </li>
                                ))}
                              </ul>
                            )}
                          </li>
                        )
                      })}
                    </ul>
                  </div>
                </Popover>
              )}
              <div className="flex-1" />
              <div className="hidden sm:flex items-center gap-3 text-[11px] text-ink-faint">
                <span className="inline-flex items-center gap-1.5">
                  <span aria-hidden className="w-7 h-2.5 rounded-full" style={{ background: 'color-mix(in oklab, var(--chart-points) 18%, transparent)', border: '1px solid var(--chart-points)' }} />
                  Active card
                </span>
                <span className="inline-flex items-center gap-1.5">
                  <span
                    aria-hidden
                    className="w-7 h-2.5 rounded-full border"
                    style={{
                      backgroundImage: `repeating-linear-gradient(45deg, color-mix(in oklab, var(--chart-points) 38%, transparent) 0, color-mix(in oklab, var(--chart-points) 38%, transparent) 4px, color-mix(in oklab, var(--chart-points) 10%, transparent) 4px, color-mix(in oklab, var(--chart-points) 10%, transparent) 8px)`,
                      borderColor: 'var(--chart-points)',
                    }}
                  />
                  SUB earning
                </span>
              </div>
            </div>
          )}
          {/* Axis header — outside the scroll container so the vertical
              scrollbar starts at the first currency row, not above. The
              same scrollbar-gutter is applied here so the right edge
              tracks the body's content area regardless of scrollbar
              presence. */}
          <div
            className="grid shrink-0 overflow-hidden"
            style={{
              gridTemplateColumns: `${LEFT_GUTTER}px 1fr`,
              scrollbarGutter: 'stable',
            }}
          >
            <div
              className={`bg-surface ${DIVIDER_CLASS} px-3 flex items-center gap-2`}
              style={{ height: AXIS_HEIGHT }}
            >
              <span className="text-[11px] uppercase tracking-wider text-ink-faint font-semibold">Cards</span>
            </div>
            <div
              className={`bg-surface ${DIVIDER_CLASS} relative`}
              style={{ height: AXIS_HEIGHT }}
            >
              <TimelineAxis yearTicks={yearTicks} endMs={range.endMs} />
            </div>
          </div>

          <div
            ref={scrollRef}
            className="flex-1 min-h-0 overflow-auto"
            style={{ scrollbarGutter: 'stable' }}
          >
            <div
              className="relative"
              style={{ display: 'grid', gridTemplateColumns: `${LEFT_GUTTER}px 1fr` }}
            >
              {/* Year gridlines — z-[25] so they cross over the currency
                  header rows (z-20) instead of being masked by them. Bars
                  at z-30 still overlay them. */}
              <div
                className="pointer-events-none absolute z-[25]"
                style={{ left: LEFT_GUTTER, right: 0, top: 0, bottom: 0 }}
              >
                {yearTicks.map((t) => (
                  <div
                    key={t.label}
                    className="absolute top-0 bottom-0 border-l border-divider"
                    style={{ left: `${t.pct}%` }}
                  />
                ))}
              </div>

              {/* Today (start) + duration end vertical lines. Bars at z-30
                  still overlay them. */}
              <div
                className="pointer-events-none absolute z-[25]"
                style={{ left: LEFT_GUTTER, right: 0, top: 0, bottom: 0 }}
              >
                <div
                  className="absolute top-0 bottom-0"
                  style={{ left: 0, width: 2, backgroundColor: 'var(--color-ink-muted)' }}
                />
                <div
                  className="absolute top-0 bottom-0"
                  style={{ right: 0, width: 2, backgroundColor: 'var(--color-ink-muted)' }}
                />
              </div>

              {/* Groups */}
              {groups.map((g) => (
                <GroupSection
                  key={g.name}
                  group={g}
                  range={range}
                  roadmapById={roadmapById}
                  isUpdating={isUpdating}
                  isStale={isStale}
                  includeSubs={includeSubs}
                  rightColumnPx={rightColumnPx}
                  walletWindowYears={walletWindowYears}
                  currencyWindowYears={
                    g.currencyId
                      ? currencyWindowYearsById[String(g.currencyId)]
                      : undefined
                  }
                  onToggleEnabled={onToggleEnabled}
                  onEditCard={onEditCard}
                  scenarioId={scenarioId}
                  walletCards={walletCards ?? []}
                  isExpanded={
                    g.currencyId != null && expandedCurrencyId === g.currencyId
                  }
                  onToggleExpanded={toggleExpanded}
                />
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
