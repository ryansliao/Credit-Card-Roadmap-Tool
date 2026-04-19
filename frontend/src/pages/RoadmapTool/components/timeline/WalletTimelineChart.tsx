import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  CardResult,
  RoadmapResponse,
  Wallet,
  WalletCard,
  WalletResult,
} from '../../../../api/client'
import { currencyColor, formatMoney, formatPoints, today } from '../../../../utils/format'
import { useCardLibrary } from '../../hooks/useCardLibrary'

interface Props {
  wallet: Wallet
  result: WalletResult | null
  roadmap: RoadmapResponse | undefined
  durationYears: number
  durationMonths: number
  isUpdating: boolean
  onToggleEnabled: (cardId: number, enabled: boolean) => void
  onEditCard: (wc: WalletCard) => void
  onAddCard: () => void
  onEditCurrency: (currencyId: number) => void
}

const LEFT_GUTTER = 380 // px
const CURRENCY_ROW_HEIGHT = 30
const CARD_ROW_HEIGHT = 56
const AXIS_HEIGHT = 44
const DIVIDER_CLASS = 'border-b border-slate-800'

interface Range {
  startMs: number
  endMs: number
  spanMs: number
}

function parseDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, (m ?? 1) - 1, d ?? 1)
}

function addMonths(d: Date, months: number): Date {
  const r = new Date(d)
  r.setMonth(r.getMonth() + months)
  return r
}

function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x))
}

function pctOf(range: Range, ms: number): number {
  return clamp01((ms - range.startMs) / range.spanMs) * 100
}

function annualIncomePoints(c: CardResult | null, _years: number): number | null {
  if (!c) return null
  // `annual_point_earn` is already per-year on both the simple path and the
  // segmented path (which time-weights across segments). It excludes SUB and
  // first-year bonuses, giving the recurring annual category earn we want for
  // the currency-group header and per-card income label.
  //
  // Computing this via `(total_points - sub_points - sub_spend_earn) / years`
  // was wrong on the segmented path: `sub_spend_earn` is baked into the
  // segment-weighted earn there, so `total_points` never included it — but
  // `cr.sub_spend_earn` still reports the raw card value, so subtracting it
  // pushed the figure negative whenever the SUB bonus spend exceeded the
  // card's recurring annual earn × window.
  return c.annual_point_earn
}

/** Prefix positive values with "+"; negatives and zero keep their natural
 * sign (so we never produce "+-42.9k"). */
function signedPrefix(n: number): string {
  return n > 0 ? '+' : ''
}

/** Format a card's annual income using the same "Pts/Year" / "/Year" suffix
 * as the currency group header so the two read consistently. */
function formatCardIncome(c: CardResult | null, years: number): string | null {
  const pts = annualIncomePoints(c, years)
  if (pts == null || c == null) return null
  if (c.effective_reward_kind === 'cash') {
    const dollars = (pts * c.cents_per_point) / 100
    return `${signedPrefix(dollars)}${formatMoney(dollars)} /Year`
  }
  const rounded = Math.round(pts)
  return `${signedPrefix(rounded)}${formatPoints(rounded)} Pts/Year`
}

/** Annual dollar value of a group, regardless of reward kind. Sums from
 * cards that were included in the last calc (i.e. had a CardResult). We
 * deliberately ignore the live `wc.is_enabled` here so a toggle doesn't
 * reorder currency groups mid-session — the order should only change when
 * the user re-runs the calculation. */
function groupAnnualDollars(group: GroupData, years: number): number {
  return group.cards.reduce((s, { cr }) => {
    if (!cr) return s
    const pts = annualIncomePoints(cr, years)
    if (pts == null) return s
    return s + (pts * cr.cents_per_point) / 100
  }, 0)
}

/** End-of-projection dollar value of a group's balance. Used to order
 * groups by projected balance. Falls back to the first card's CPP when
 * `balanceCpp` isn't set (i.e. points-kind groups). */
function groupBalanceDollars(group: GroupData): number {
  if (group.totalBalance == null) return 0
  const cpp =
    group.balanceCpp ??
    group.cards.find((e) => e.cr != null)?.cr?.cents_per_point ??
    null
  if (cpp == null) return 0
  return (group.totalBalance * cpp) / 100
}

/** Group income total for display in the currency header. Sums across the
 * cards the last calc included (CardResult present), ignoring live enabled
 * state so toggling doesn't silently change the header totals until the
 * next calc. */
function formatGroupIncome(group: GroupData, years: number): string | null {
  const { rewardKind, cards } = group
  if (!rewardKind) return null
  const included = cards.filter(({ cr }) => cr != null)
  if (included.length === 0) return null
  if (rewardKind === 'cash') {
    const dollars = included.reduce((s, { cr }) => {
      const pts = annualIncomePoints(cr, years) ?? 0
      return s + (pts * (cr?.cents_per_point ?? 1)) / 100
    }, 0)
    return `${signedPrefix(dollars)}${formatMoney(dollars)} /Year`
  }
  const pts = included.reduce((s, { cr }) => s + (annualIncomePoints(cr, years) ?? 0), 0)
  const rounded = Math.round(pts)
  return `${signedPrefix(rounded)}${formatPoints(rounded)} Pts/Year`
}

/** Format a single secondary-currency annual total, e.g. "+$25 Bilt Cash". */
function formatSecondaryAnnual(
  secondary: { name: string; units: number; dollars: number; rewardKind: 'points' | 'cash' },
): string {
  if (secondary.rewardKind === 'cash') {
    return `${signedPrefix(secondary.dollars)}${formatMoney(secondary.dollars)} ${secondary.name}`
  }
  const rounded = Math.round(secondary.units)
  return `${signedPrefix(rounded)}${formatPoints(rounded)} ${secondary.name}`
}

/** Format a currency's end-of-projection balance. Uses the same
 * pts-vs-dollars split as the per-year figure so the two read consistently. */
function formatGroupBalance(group: GroupData): string | null {
  if (group.totalBalance == null) return null
  if (group.rewardKind === 'cash' && group.balanceCpp != null) {
    const dollars = (group.totalBalance * group.balanceCpp) / 100
    return `${formatMoney(dollars)} Balance`
  }
  const rounded = Math.round(group.totalBalance)
  return `${formatPoints(rounded)} Pts Balance`
}

function formatSecondaryBalance(
  secondary: { name: string; totalUnits: number; totalDollars: number; rewardKind: 'points' | 'cash' },
): string {
  if (secondary.rewardKind === 'cash') {
    return `${formatMoney(secondary.totalDollars)} ${secondary.name} Balance`
  }
  const rounded = Math.round(secondary.totalUnits)
  return `${formatPoints(rounded)} ${secondary.name} Balance`
}

function formatDate(s: string | null): string {
  if (!s) return '—'
  const d = parseDate(s)
  return d.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' })
}

/** Measure rendered text width via a shared offscreen canvas. The font
 * string matches the bar label (text-xs, semibold, default sans-serif). */
let _measureCtx: CanvasRenderingContext2D | null = null
function measureEafLabelPx(text: string): number {
  if (typeof document === 'undefined') return text.length * 7
  if (!_measureCtx) {
    const canvas = document.createElement('canvas')
    _measureCtx = canvas.getContext('2d')
  }
  if (!_measureCtx) return text.length * 7
  _measureCtx.font = '600 12px ui-sans-serif, system-ui, sans-serif'
  return _measureCtx.measureText(text).width
}

export function WalletTimelineChart({
  wallet,
  result,
  roadmap,
  durationYears,
  durationMonths,
  isUpdating,
  onToggleEnabled,
  onEditCard,
  onAddCard,
  onEditCurrency,
}: Props) {
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

  const visibleCards = useMemo(() => {
    return (wallet.wallet_cards ?? []).filter((wc) => {
      if (wc.closed_date) {
        const closedMs = parseDate(wc.closed_date).getTime()
        if (closedMs < range.startMs) return false
      }
      const addedMs = parseDate(wc.added_date).getTime()
      if (addedMs >= range.endMs) return false
      return true
    })
  }, [wallet.wallet_cards, range])

  const groups = useMemo<GroupData[]>(() => {
    const byCurrency = new Map<string, GroupData>()
    for (const wc of visibleCards) {
      // Pull cr directly from the last calc's result — don't gate by the
      // live `wc.is_enabled`. The backend only emits CardResults for cards
      // that were enabled *at calc time*, so toggling now must not make cr
      // flip in/out of existence (that would reorder currency groups and
      // change their totals between calcs).
      const cr = cardResultById.get(wc.card_id) ?? null
      let name: string
      let currencyId: number | null
      let rewardKind: 'points' | 'cash' | null
      if (cr) {
        name = cr.effective_currency_name
        currencyId = cr.effective_currency_id ?? null
        rewardKind = cr.effective_reward_kind ?? 'points'
      } else {
        const lib = libraryById.get(wc.card_id)
        const cur = lib?.currency_obj
        if (cur) {
          name = cur.name
          currencyId = cur.id
          rewardKind = cur.reward_kind === 'cash' ? 'cash' : 'points'
        } else {
          // Library not loaded yet or card missing — skip so we never show
          // a stray "Unknown" group.
          continue
        }
      }
      if (!byCurrency.has(name)) {
        byCurrency.set(name, {
          name,
          currencyId,
          color: currencyColor(currencyId, name),
          rewardKind,
          cards: [],
          secondaries: [],
          totalBalance: null,
          balanceCpp: null,
        })
      }
      const g = byCurrency.get(name)!
      // Precompute per-card secondary annual earn so both card rows and the
      // group header can render it without extra lookups.
      //
      // Note: the calculator deliberately zeroes ``secondary_currency_value_dollars``
      // when a card is in Bilt 2.0 "Bilt Cash mode" (to avoid double-counting
      // against the lump-sum annual_bonus). For display we want the true
      // dollar value, so we re-derive it from the library secondary
      // currency's cents_per_point × the net-pts figure.
      // Filter by `cr` presence (i.e. "was included in the last calc"),
      // not live `wc.is_enabled`, so toggling a card doesn't change the
      // group's aggregated secondary-currency totals until recalc.
      let secondary: SecondaryAnnual | null = null
      if (
        cr &&
        cr.secondary_currency_id &&
        cr.secondary_currency_net_earn !== 0
      ) {
        const lib = libraryById.get(wc.card_id)
        const secObj = lib?.secondary_currency_obj
        const kind: 'points' | 'cash' = secObj?.reward_kind === 'cash' ? 'cash' : 'points'
        const secCpp = secObj?.cents_per_point ?? 1
        const years = cr.card_active_years || totalYears || 1
        const annualUnits = cr.secondary_currency_net_earn / years
        secondary = {
          id: cr.secondary_currency_id,
          name: cr.secondary_currency_name,
          units: annualUnits,
          dollars: (annualUnits * secCpp) / 100,
          rewardKind: kind,
          totalUnits: 0,
          totalDollars: 0,
        }
      }
      g.cards.push({ wc, cr, secondary })
    }
    for (const g of byCurrency.values()) {
      g.cards.sort((a, b) => {
        const ea = a.cr?.card_effective_annual_fee ?? Number.POSITIVE_INFINITY
        const eb = b.cr?.card_effective_annual_fee ?? Number.POSITIVE_INFINITY
        return ea - eb
      })

      // Aggregate the secondaries to surface the group's total (e.g. Bilt
      // Cash under Bilt Rewards) alongside the primary income.
      const byId = new Map<number, SecondaryAnnual>()
      for (const entry of g.cards) {
        const s = entry.secondary
        if (!s) continue
        const prev = byId.get(s.id) ?? { ...s, units: 0, dollars: 0 }
        prev.units += s.units
        prev.dollars += s.dollars
        byId.set(s.id, prev)
      }
      // Populate end-of-projection balance totals from the last calc.
      // `currency_pts_by_id` / `secondary_currency_pts_by_id` are keyed by
      // currency id (stringified) and hold total pts over the window.
      if (g.currencyId != null) {
        const total = result?.currency_pts_by_id?.[String(g.currencyId)]
        if (total != null) {
          g.totalBalance = total
          if (g.rewardKind === 'cash') {
            const firstCpp = g.cards.find((e) => e.cr != null)?.cr?.cents_per_point ?? null
            g.balanceCpp = firstCpp
          }
        }
      }
      for (const [secId, s] of byId) {
        const total = result?.secondary_currency_pts_by_id?.[String(secId)]
        if (total == null) continue
        s.totalUnits = total
        const perUnitDollars = s.units !== 0 ? s.dollars / s.units : 0
        s.totalDollars = total * perUnitDollars
      }
      g.secondaries = Array.from(byId.values())
    }

    // Sort by end-of-projection balance (in dollars) descending. Fall back
    // to annual dollar value when balances are absent or equal so groups
    // without calc results still order sensibly.
    return Array.from(byCurrency.values()).sort((a, b) => {
      const ba = groupBalanceDollars(a)
      const bb = groupBalanceDollars(b)
      if (ba !== bb) return bb - ba
      const da = groupAnnualDollars(a, totalYears)
      const db = groupAnnualDollars(b, totalYears)
      if (da !== db) return db - da
      return a.name.localeCompare(b.name)
    })
  }, [visibleCards, cardResultById, libraryById, totalYears, result])

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

  const chartHeight = groups.reduce(
    (s, g) => s + CURRENCY_ROW_HEIGHT + g.cards.length * CARD_ROW_HEIGHT,
    0,
  )

  // Observe the scroll container's width so we can decide whether each
  // bar's EAF label fits inside the bar; if not, place it to the right,
  // or to the left when there's no room on either side.
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
    <div className="bg-slate-900 border border-slate-700 rounded-xl pt-2 px-4 pb-4 min-w-0 min-h-0 h-full flex flex-col overflow-hidden">
      <div ref={scrollRef} className="flex-1 min-h-0 overflow-auto">
        {visibleCards.length === 0 ? (
          <div className="text-slate-500 text-sm text-center py-10">
            No cards yet. Click + to add one.
          </div>
        ) : (
          <div
            className="relative"
            style={{ display: 'grid', gridTemplateColumns: `${LEFT_GUTTER}px 1fr` }}
          >
            {/* Axis header (sticky, opaque, stays above scrolling bars and
                the Today line). z-40 keeps it above the Today overlay (z-20)
                and the bars (z-30) so content scrolls behind it cleanly. */}
            <div
              className={`sticky top-0 z-40 bg-slate-900 ${DIVIDER_CLASS} px-3 flex items-center gap-2`}
              style={{ height: AXIS_HEIGHT }}
            >
              <h2 className="text-base font-semibold text-slate-100">Cards</h2>
              <button
                type="button"
                onClick={onAddCard}
                className="p-1 rounded text-slate-500 hover:text-indigo-400 hover:bg-slate-800 transition-colors"
                aria-label="Add card"
                title="Add card"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="12" y1="5" x2="12" y2="19" />
                  <line x1="5" y1="12" x2="19" y2="12" />
                </svg>
              </button>
              {roadmap && (
                <span
                  className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                    roadmap.five_twenty_four_eligible
                      ? 'bg-emerald-900/60 text-emerald-300 border border-emerald-700'
                      : 'bg-red-900/60 text-red-300 border border-red-700'
                  }`}
                  title={`${roadmap.five_twenty_four_count} personal cards opened in last 24 months`}
                >
                  5/24: {roadmap.five_twenty_four_count}/5
                </span>
              )}
              <span
                className="ml-10 flex items-center gap-1.5 text-[11px] text-slate-400"
                title="Amber line marks the SUB earned date (dashed when projected)"
              >
                <span
                  aria-hidden
                  className="inline-block"
                  style={{ width: 2, height: 12, backgroundColor: '#f59e0b' }}
                />
                SUB Earned Date
              </span>
            </div>
            <div
              className={`sticky top-0 z-40 bg-slate-900 ${DIVIDER_CLASS} relative`}
              style={{ height: AXIS_HEIGHT }}
            >
              {yearTicks.map((t) => (
                <div
                  key={t.label}
                  className="absolute top-0 bottom-0 flex items-center text-[11px] text-slate-500"
                  style={{ left: `${t.pct}%`, transform: 'translateX(-50%)' }}
                >
                  {t.label}
                </div>
              ))}
              {/* Today label lives inside the sticky axis so it doesn't
                  scroll away with the chart body. */}
              <div
                className="absolute flex items-center text-[11px] text-slate-300 font-semibold whitespace-nowrap pointer-events-none"
                style={{ left: 0, top: 0, bottom: 0, transform: 'translateX(-50%)' }}
              >
                Today
              </div>
            </div>

            {/* Year gridlines — z-[25] so they cross over the currency
                header rows (z-20) instead of being masked by them. Bars at
                z-30 still overlay them. */}
            <div
              className="pointer-events-none absolute z-[25]"
              style={{ left: LEFT_GUTTER, right: 0, top: 0, height: AXIS_HEIGHT + chartHeight }}
            >
              {yearTicks.map((t) => (
                <div
                  key={t.label}
                  className="absolute top-0 bottom-0 border-l border-slate-700"
                  style={{ left: `${t.pct}%` }}
                />
              ))}
            </div>

            {/* Today vertical line — z-[25] stacks it above currency header
                rows (z-20); bars at z-30 still overlay it. The line spans
                only the chart body so it doesn't bleed into the sticky
                axis (z-40). */}
            <div
              className="pointer-events-none absolute z-[25]"
              style={{ left: LEFT_GUTTER, right: 0, top: AXIS_HEIGHT, height: chartHeight }}
            >
              <div
                className="absolute top-0 bottom-0"
                style={{ left: 0, width: 2, backgroundColor: '#64748b' }}
              />
            </div>

            {/* Groups */}
            {groups.map((g) => (
              <GroupSection
                key={g.name}
                group={g}
                range={range}
                totalYears={totalYears}
                roadmapById={roadmapById}
                isUpdating={isUpdating}
                rightColumnPx={rightColumnPx}
                onToggleEnabled={onToggleEnabled}
                onEditCard={onEditCard}
                onEditCurrency={onEditCurrency}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

interface SecondaryAnnual {
  id: number
  name: string
  units: number
  dollars: number
  rewardKind: 'points' | 'cash'
  /** Total projected balance (not annualised). Populated at the aggregated
   * group level from `result.secondary_currency_pts_by_id`; per-card rows
   * leave it at 0. */
  totalUnits: number
  totalDollars: number
}

interface GroupCardEntry {
  wc: WalletCard
  cr: CardResult | null
  /** Annualized secondary-currency earn for this card (e.g. Bilt Cash on a
   * Bilt Rewards card). Null when the card has no secondary earn. */
  secondary: SecondaryAnnual | null
}

interface GroupData {
  name: string
  currencyId: number | null
  color: string
  rewardKind: 'points' | 'cash' | null
  cards: GroupCardEntry[]
  /** Aggregated secondary-currency totals across enabled cards in this
   * group (e.g. Bilt Cash under Bilt Rewards). Shown as extra income
   * figures alongside the primary total. */
  secondaries: SecondaryAnnual[]
  /** End-of-projection balance in this currency, straight from the last
   * calc's `currency_pts_by_id`. Null when the calc hasn't run or the
   * currency doesn't appear in the result. */
  totalBalance: number | null
  /** CPP to value the balance against when rendering a cash group. */
  balanceCpp: number | null
}

interface GroupSectionProps {
  group: GroupData
  range: Range
  totalYears: number
  roadmapById: Map<number, RoadmapResponse['cards'][number]>
  isUpdating: boolean
  rightColumnPx: number
  onToggleEnabled: (cardId: number, enabled: boolean) => void
  onEditCard: (wc: WalletCard) => void
  onEditCurrency: (currencyId: number) => void
}

function GroupSection({
  group,
  range,
  totalYears,
  roadmapById,
  isUpdating,
  rightColumnPx,
  onToggleEnabled,
  onEditCard,
  onEditCurrency,
}: GroupSectionProps) {
  const incomeLabel = formatGroupIncome(group, totalYears)
  const balanceLabel = formatGroupBalance(group)

  return (
    <>
      {/* Group header: split into two cells so the gear lives inside the
          left (Cards) column, right-aligned. Opaque bg + z-20 so the
          Today line / year gridlines stop at this row rather than crossing
          through the text. */}
      <div
        className={`relative z-20 flex items-center gap-2 px-3 ${DIVIDER_CLASS} bg-slate-800`}
        style={{ height: CURRENCY_ROW_HEIGHT, borderLeft: `3px solid ${group.color}` }}
      >
        <div className="w-2 h-2 rounded-full shrink-0" style={{ backgroundColor: group.color }} />
        <div className="text-sm font-medium text-slate-200 truncate">{group.name}</div>
        {group.currencyId != null && (
          <button
            type="button"
            onClick={() => onEditCurrency(group.currencyId!)}
            className="ml-auto p-1 rounded text-slate-500 hover:text-indigo-400 hover:bg-slate-700 transition-colors shrink-0"
            title={`Edit ${group.name} settings`}
            aria-label={`Edit ${group.name} settings`}
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="3" />
              <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
            </svg>
          </button>
        )}
      </div>
      {/* Right cell — timeline side of the currency header row; carries the
          income total (if any) and keeps the background tint aligned. z-20
          + opaque bg so the Today line and year gridlines don't bleed
          through the text. */}
      <div
        className={`relative z-20 flex items-center gap-2 px-3 ${DIVIDER_CLASS} bg-slate-800`}
        style={{ height: CURRENCY_ROW_HEIGHT }}
      >
        {/* Left cluster — annual income sits just right of the Today line
            (which is at left:0 of this column). */}
        <div className="flex items-center gap-2 pl-2">
          {incomeLabel && <div className="text-xs text-slate-400">{incomeLabel}</div>}
          {group.secondaries.map((s) => (
            <div key={`annual-${s.id}`} className="text-xs text-slate-500">
              <span className="mr-1 text-slate-700">·</span>
              {formatSecondaryAnnual(s)}
            </div>
          ))}
        </div>
        {/* Right cluster — end-of-projection balance, right aligned. */}
        <div className="ml-auto flex items-center gap-2">
          {balanceLabel && (
            <div className="text-xs text-slate-300 font-medium">{balanceLabel}</div>
          )}
          {group.secondaries.map((s) => (
            <div key={`balance-${s.id}`} className="text-xs text-slate-500">
              <span className="mr-1 text-slate-700">·</span>
              {formatSecondaryBalance(s)}
            </div>
          ))}
        </div>
      </div>
      {group.cards.map(({ wc, cr, secondary }) => (
        <CardRow
          key={wc.id}
          wc={wc}
          cr={cr}
          secondary={secondary}
          color={group.color}
          range={range}
          totalYears={totalYears}
          roadmapStatus={roadmapById.get(wc.card_id)}
          isUpdating={isUpdating}
          rightColumnPx={rightColumnPx}
          onToggleEnabled={onToggleEnabled}
          onEditCard={onEditCard}
        />
      ))}
    </>
  )
}

interface CardRowProps {
  wc: WalletCard
  cr: CardResult | null
  secondary: SecondaryAnnual | null
  color: string
  range: Range
  totalYears: number
  roadmapStatus: RoadmapResponse['cards'][number] | undefined
  isUpdating: boolean
  rightColumnPx: number
  onToggleEnabled: (cardId: number, enabled: boolean) => void
  onEditCard: (wc: WalletCard) => void
}

function CardRow({
  wc,
  cr,
  secondary,
  color,
  range,
  totalYears,
  roadmapStatus,
  isUpdating,
  rightColumnPx,
  onToggleEnabled,
  onEditCard,
}: CardRowProps) {
  const addedMs = parseDate(wc.added_date).getTime()
  const closedMs = wc.closed_date ? parseDate(wc.closed_date).getTime() : range.endMs

  const barStartPct = pctOf(range, Math.max(addedMs, range.startMs))
  const barEndPct = pctOf(range, Math.min(closedMs, range.endMs))
  const barWidthPct = Math.max(0, barEndPct - barStartPct)

  const enabled = wc.is_enabled

  const subEarnedDate = wc.sub_earned_date ?? roadmapStatus?.sub_earned_date ?? null
  const subProjectedDate =
    wc.sub_projected_earn_date ?? roadmapStatus?.sub_projected_earn_date ?? null
  const subDateStr = subEarnedDate ?? subProjectedDate
  const subEarned = subEarnedDate != null
  const subMs = subDateStr ? parseDate(subDateStr).getTime() : null
  // Disabled cards don't participate in calculations, so their SUB projection
  // is meaningless — suppress the marker entirely.
  const showSubMarker =
    enabled &&
    subMs != null &&
    subMs >= range.startMs &&
    subMs <= range.endMs &&
    barWidthPct > 0
  const subPct = showSubMarker ? pctOf(range, subMs!) : null
  // Per-card income and EAF are driven by the last calc's `cr`, not the live
  // toggle, so the numbers (and layout) stay stable when the user flips
  // `is_enabled` — only a recalc refreshes what's shown. Cards that weren't
  // in the last calc (cr == null) have nothing to display.
  //
  // For disabled cards we want to suppress real numbers (including "0") and
  // show an em-dash placeholder so the row clearly reads as "not
  // contributing right now" instead of implying $0 EAF / 0 pts.
  const incomeLabel = enabled ? formatCardIncome(cr, totalYears) : '—'
  const eafValue = enabled ? cr?.card_effective_annual_fee ?? null : null
  const eafLabelText = enabled
    ? eafValue != null
      ? `${formatMoney(eafValue)} EAF`
      : null
    : '—'

  const tooltip = [
    `Added: ${formatDate(wc.added_date)}`,
    wc.closed_date ? `Closed: ${formatDate(wc.closed_date)}` : null,
    enabled
      ? subEarned
        ? `SUB earned: ${formatDate(subEarnedDate)}`
        : subProjectedDate
          ? `SUB projected: ${formatDate(subProjectedDate)}`
          : 'No SUB'
      : 'Not Calculated',
    enabled && eafValue != null ? `EAF: ${formatMoney(eafValue)}` : null,
    enabled && incomeLabel ? `Income: ${incomeLabel.replace(/^\+/, '')}` : null,
  ]
    .filter(Boolean)
    .join('\n')

  const barHeight = 24

  // display: contents on the wrapper lets the two children act as direct grid
  // cells while sharing a hover state so the entire row highlights together.
  return (
    <div className="group contents">
      {/* Left gutter */}
      <div
        className={`flex items-center gap-2 px-3 ${DIVIDER_CLASS} transition-colors group-hover:bg-slate-800/60 ${
          enabled ? '' : 'opacity-50'
        }`}
        style={{ height: CARD_ROW_HEIGHT }}
      >
        <button
          type="button"
          onClick={() => onEditCard(wc)}
          className="flex-1 min-w-0 text-left flex items-center gap-3 group-hover:text-indigo-300 transition-colors"
          title="Edit card"
        >
          <CardThumb slug={wc.photo_slug} name={wc.card_name ?? ''} />
          <div className="min-w-0 flex-1">
            <div className="text-sm font-medium text-slate-200 truncate">
              {wc.card_name ?? `Card #${wc.card_id}`}
            </div>
            {incomeLabel && (
              <div className="text-[11px] text-slate-500 truncate">
                {incomeLabel}
                {secondary && (
                  <>
                    <span className="mx-1 text-slate-700">·</span>
                    {formatSecondaryAnnual(secondary)}
                  </>
                )}
              </div>
            )}
          </div>
          <EditAffordance />
        </button>
        <ToggleSwitch
          enabled={enabled}
          disabled={isUpdating}
          onChange={(next) => onToggleEnabled(wc.card_id, next)}
          label={enabled ? 'Disable card' : 'Enable card'}
        />
      </div>

      {/* Right column: timeline bar */}
      <div
        className={`relative ${DIVIDER_CLASS} transition-colors group-hover:bg-slate-800/60`}
        style={{ height: CARD_ROW_HEIGHT }}
        title={tooltip}
      >
        {barWidthPct > 0 && (
          <div
            className="absolute rounded"
            style={{
              left: `${barStartPct}%`,
              width: `${barWidthPct}%`,
              top: (CARD_ROW_HEIGHT - barHeight) / 2,
              height: barHeight,
              backgroundColor: enabled ? `${color}33` : '#33415533',
              border: `1px solid ${enabled ? color : '#475569'}`,
              opacity: enabled ? 1 : 0.55,
              zIndex: 30,
            }}
          />
        )}
        {barWidthPct > 0 && eafLabelText != null && (() => {
          const labelText = eafLabelText
          const labelClass = !enabled
            ? 'text-slate-500'
            : eafValue != null && eafValue < 0
              ? 'text-emerald-400'
              : eafValue != null && eafValue > 0
                ? 'text-red-400'
                : 'text-slate-200'
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
                  top: (CARD_ROW_HEIGHT - barHeight) / 2,
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
          const top = (CARD_ROW_HEIGHT - barHeight) / 2
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
        {showSubMarker && subPct != null && (
          <SubTick earned={subEarned} pct={subPct} rowHeight={CARD_ROW_HEIGHT} barHeight={barHeight} />
        )}
      </div>
    </div>
  )
}

function EditAffordance() {
  return (
    <svg
      className="shrink-0 ml-1 text-slate-600 opacity-0 group-hover:opacity-100 transition-opacity"
      width="14"
      height="14"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden
    >
      <path d="M17 3a2.85 2.85 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z" />
    </svg>
  )
}

function CardThumb({ slug, name }: { slug: string | null; name: string }) {
  if (!slug) {
    return (
      <div className="w-14 h-9 rounded bg-slate-800 border border-slate-700 shrink-0" />
    )
  }
  return (
    <img
      src={`/photos/${slug}.png`}
      alt={name}
      className="w-14 h-9 object-contain shrink-0"
      onError={(e) => {
        const el = e.currentTarget
        el.style.display = 'none'
      }}
    />
  )
}

function ToggleSwitch({
  enabled,
  disabled,
  onChange,
  label,
}: {
  enabled: boolean
  disabled: boolean
  onChange: (next: boolean) => void
  label?: string
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={enabled}
      disabled={disabled}
      onClick={() => onChange(!enabled)}
      className={`relative shrink-0 w-8 h-4 rounded-full transition-colors ${
        enabled ? 'bg-indigo-500' : 'bg-slate-700'
      } ${disabled ? 'opacity-60 cursor-not-allowed' : 'cursor-pointer'}`}
      title={label ?? (enabled ? 'Click to disable' : 'Click to enable')}
      aria-label={label ?? (enabled ? 'Disable' : 'Enable')}
    >
      <span
        className="absolute top-0.5 h-3 w-3 rounded-full bg-white transition-all"
        style={{ left: enabled ? 16 : 2 }}
      />
    </button>
  )
}

function SubTick({
  earned,
  pct,
  rowHeight,
  barHeight,
}: {
  earned: boolean
  pct: number
  rowHeight: number
  barHeight: number
}) {
  // A thin amber vertical tick, extending a few px past the bar top and bottom
  // to keep it visible regardless of bar fill color.
  const extend = 6
  const top = (rowHeight - barHeight) / 2 - extend
  const height = barHeight + extend * 2
  return (
    <div
      className="absolute pointer-events-none"
      style={{
        left: `${pct}%`,
        top,
        height,
        width: 2,
        transform: 'translateX(-1px)',
        backgroundColor: earned ? '#f59e0b' : 'transparent',
        borderLeft: earned ? undefined : '2px dashed #f59e0b',
      }}
      title={earned ? 'SUB earned' : 'SUB projected'}
    />
  )
}
