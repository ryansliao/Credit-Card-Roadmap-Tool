import { useEffect, useMemo, useRef, useState } from 'react'
import type {
  CardResult,
  RoadmapResponse,
  Wallet,
  WalletCard,
  WalletResult,
} from '../../../../api/client'
import { formatMoney, formatMoneyCompact, formatPoints, formatPointsExact, pointsUnitLabel, today } from '../../../../utils/format'
import {
  cardAnnualPointIncomeActive,
  cardAnnualPointIncomeCurrencyWindow,
  cardEafActive,
  cardEafWindow,
} from '../../../../utils/cardIncome'
import { useCardLibrary } from '../../hooks/useCardLibrary'
import { CurrencySettingsDropdown } from '../summary/CurrencySettingsDropdown'

interface Props {
  wallet: Wallet
  result: WalletResult | null
  roadmap: RoadmapResponse | undefined
  durationYears: number
  durationMonths: number
  isUpdating: boolean
  isStale: boolean
  /** Wallet-level "Include SUBs" toggle. Applied as a pure display switch
   * on top of already-computed results via sub_eaf_contribution on each
   * CardResult — no recalculation required. */
  includeSubs: boolean
  onToggleEnabled: (cardId: number, enabled: boolean) => void
  onEditCard: (wc: WalletCard) => void
  onAddCard: () => void
}

const LEFT_GUTTER = 380 // px
const CURRENCY_ROW_HEIGHT = 45
const CARD_ROW_HEIGHT = 50
const AXIS_HEIGHT = 50
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

/** Format a card's annual income. Cash cards: "$X /Year". Points/miles
 * cards: "X /Year" (unit label omitted to match the currency rows). */
function formatCardIncome(c: CardResult | null, includeSubs: boolean): string | null {
  const pts = cardAnnualPointIncomeActive(c, includeSubs)
  if (pts == null || c == null) return null
  if (c.effective_reward_kind === 'cash') {
    const dollars = (pts * c.cents_per_point) / 100
    return `${formatMoney(dollars)} /Year`
  }
  const rounded = Math.round(pts)
  return `${formatPoints(rounded)} /Year`
}

/** Annual dollar value of a group, regardless of reward kind. Sums only
 * cards that were included in the last calc (have a `cr`). Does NOT gate
 * by live `is_enabled` so group totals/ordering stay stable until the
 * user clicks Calculate again. Uses the currency's own window (earliest
 * card open → latest close among cards earning the currency) for
 * annualization when available. */
function groupAnnualDollars(
  group: GroupData,
  includeSubs: boolean,
  walletWindowYears: number | undefined,
  currencyWindowYears: number | undefined,
): number {
  return group.cards.reduce((s, { cr }) => {
    if (!cr) return s
    const pts =
      cardAnnualPointIncomeCurrencyWindow(
        cr,
        includeSubs,
        walletWindowYears,
        currencyWindowYears,
      ) ?? 0
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

/** Sum of per-card EAF across all cards earning this currency. Uses the
 * window-basis flavor (not the active-year one) so the sum stays on the
 * wallet window. Used as a tiebreaker when ordering zero-balance
 * currencies, so it always honors the "include SUBs" toggle as a display
 * switch — passing `true` mirrors the backend's SUB-inclusive value. */
function groupCombinedEaf(group: GroupData): number {
  return group.cards.reduce(
    (s, { cr }) => s + (cardEafWindow(cr ?? null, true) ?? 0),
    0,
  )
}


function formatGroupIncome(
  group: GroupData,
  includeSubs: boolean,
  walletWindowYears: number | undefined,
  currencyWindowYears: number | undefined,
): string | null {
  const { rewardKind, cards } = group
  if (!rewardKind) return null
  const included = cards.filter(({ cr }) => cr != null)
  if (included.length === 0) return null
  const scaledPts = (c: CardResult | null | undefined): number =>
    cardAnnualPointIncomeCurrencyWindow(
      c ?? null,
      includeSubs,
      walletWindowYears,
      currencyWindowYears,
    ) ?? 0
  if (rewardKind === 'cash') {
    const dollars = included.reduce((s, { cr }) => {
      const pts = scaledPts(cr)
      return s + (pts * (cr?.cents_per_point ?? 1)) / 100
    }, 0)
    return `${formatMoney(dollars)} /Year`
  }
  const pts = included.reduce((s, { cr }) => s + scaledPts(cr), 0)
  const rounded = Math.round(pts)
  return `${formatPoints(rounded)} /Year`
}

/** Format a single secondary-currency annual total, e.g. "$25 Bilt Cash /Year".
 * Group-level aggregates use summed per-card annualised rates (each
 * card's `secondary_currency_net_earn / card_active_years`). */
function formatSecondaryAnnual(secondary: SecondaryAnnual): string {
  if (secondary.rewardKind === 'cash') {
    return `${formatMoneyCompact(secondary.dollars)} ${secondary.name} /Year`
  }
  const rounded = Math.round(secondary.units)
  return `${formatPoints(rounded)} ${secondary.name} /Year`
}

/** Format a currency's end-of-projection balance. Uses the same
 * pts-vs-dollars split as the per-year figure so the two read consistently. */
function formatGroupBalance(group: GroupData): string | null {
  if (group.totalBalance == null) return null
  if (group.rewardKind === 'cash' && group.balanceCpp != null) {
    const dollars = (group.totalBalance * group.balanceCpp) / 100
    return `${formatMoney(dollars)}`
  }
  const rounded = Math.round(group.totalBalance)
  return formatPointsExact(rounded)
}

function formatSecondaryBalance(
  secondary: { name: string; units: number; dollars: number; rewardKind: 'points' | 'cash' },
): string {
  if (secondary.rewardKind === 'cash') {
    return `${formatMoneyCompact(secondary.dollars)} ${secondary.name} /Year`
  }
  const rounded = Math.round(secondary.units)
  return `${formatPoints(rounded)} ${secondary.name} /Year`
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
  isStale,
  includeSubs,
  onToggleEnabled,
  onEditCard,
  onAddCard,
}: Props) {
  const [expandedCurrencyId, setExpandedCurrencyId] = useState<number | null>(null)
  const toggleExpanded = (cid: number) =>
    setExpandedCurrencyId((prev) => (prev === cid ? null : cid))
  // Per-currency-group expansion state for the disabled-cards fold. Folded
  // by default on first mount; survives recalculation (component stays
  // mounted) and resets to folded on a full page refresh (component
  // re-mounts with a fresh Set).
  const [expandedDisabledGroups, setExpandedDisabledGroups] = useState<
    Set<string>
  >(() => new Set())
  const toggleDisabledExpanded = (groupName: string) => {
    setExpandedDisabledGroups((prev) => {
      const next = new Set(prev)
      if (next.has(groupName)) next.delete(groupName)
      else next.add(groupName)
      return next
    })
  }
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
  const currencyWindowYearsById = result?.currency_window_years ?? {}

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
      let photoSlug: string | null
      let rewardKind: 'points' | 'cash' | null
      if (cr) {
        name = cr.effective_currency_name
        currencyId = cr.effective_currency_id ?? null
        photoSlug = cr.effective_currency_photo_slug ?? null
        rewardKind = cr.effective_reward_kind ?? 'points'
      } else {
        const lib = libraryById.get(wc.card_id)
        const cur = lib?.currency_obj
        if (cur) {
          name = cur.name
          currencyId = cur.id
          photoSlug = cur.photo_slug ?? null
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
          photoSlug,
          color: rewardKind === 'cash' ? '#4ade80' : '#818cf8',
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
          totalUnits: cr.secondary_currency_net_earn,
          totalDollars: (cr.secondary_currency_net_earn * secCpp) / 100,
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

      // Aggregate primary-currency balance and secondary totals based on
      // calc results only. Don't gate by live `is_enabled` — the results
      // must stay stable (including currency group order) until the user
      // clicks Calculate again. Cards that weren't enabled at calc time
      // won't have a `cr` anyway.
      let balanceSum = 0
      let balanceCount = 0
      const byId = new Map<number, SecondaryAnnual>()
      for (const entry of g.cards) {
        if (!entry.cr) continue
        balanceSum += entry.cr.total_points
        balanceCount += 1
        const s = entry.secondary
        if (s) {
          const prev = byId.get(s.id) ?? {
            ...s,
            units: 0,
            dollars: 0,
            totalUnits: 0,
            totalDollars: 0,
          }
          prev.units += s.units
          prev.dollars += s.dollars
          prev.totalUnits += s.totalUnits
          prev.totalDollars += s.totalDollars
          byId.set(s.id, prev)
        }
      }
      if (balanceCount > 0) {
        g.totalBalance = balanceSum
        if (g.rewardKind === 'cash') {
          g.balanceCpp = g.cards.find((e) => e.cr != null)?.cr?.cents_per_point ?? null
        }
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
      {visibleCards.length === 0 ? (
        <div ref={scrollRef} className="flex-1 min-h-0 overflow-auto">
          <div className="text-slate-500 text-sm text-center py-10">
            No cards yet. Click + to add one.
          </div>
        </div>
      ) : (
        <>
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
              className={`bg-slate-900 ${DIVIDER_CLASS} px-3 flex items-center gap-2`}
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
            </div>
            <div
              className={`bg-slate-900 ${DIVIDER_CLASS} relative`}
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
              <div
                className="absolute flex items-center text-[11px] text-slate-300 font-semibold whitespace-nowrap pointer-events-none"
                style={{ left: 0, top: 0, bottom: 0, transform: 'translateX(-50%)' }}
              >
                Today
              </div>
              <div
                className="absolute flex items-center text-[11px] text-slate-300 font-semibold whitespace-nowrap pointer-events-none"
                style={{ right: 0, top: 0, bottom: 0, transform: 'translateX(50%)' }}
                title={new Date(range.endMs).toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                  day: 'numeric',
                })}
              >
                {new Date(range.endMs).toLocaleDateString(undefined, {
                  year: 'numeric',
                  month: 'short',
                })}
              </div>
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
                    className="absolute top-0 bottom-0 border-l border-slate-700"
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
                  style={{ left: 0, width: 2, backgroundColor: '#64748b' }}
                />
                <div
                  className="absolute top-0 bottom-0"
                  style={{ right: 0, width: 2, backgroundColor: '#64748b' }}
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
                  g.currencyId ? currencyWindowYearsById[String(g.currencyId)] : undefined
                }
                onToggleEnabled={onToggleEnabled}
                onEditCard={onEditCard}
                walletId={wallet.id}
                walletCards={wallet.wallet_cards ?? []}
                isExpanded={
                  g.currencyId != null && expandedCurrencyId === g.currencyId
                }
                onToggleExpanded={toggleExpanded}
                isDisabledExpanded={expandedDisabledGroups.has(g.name)}
                onToggleDisabledExpanded={() => toggleDisabledExpanded(g.name)}
              />
            ))}
            </div>
          </div>
        </>
      )}
    </div>
  )
}

interface SecondaryAnnual {
  id: number
  name: string
  units: number
  dollars: number
  rewardKind: 'points' | 'cash'
  /** Total projected balance (not annualised). At the per-card entry it
   * holds `cr.secondary_currency_net_earn`; the group header sums those
   * across enabled cards. */
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
  photoSlug: string | null
  color: string
  rewardKind: 'points' | 'cash' | null
  cards: GroupCardEntry[]
  /** Aggregated secondary-currency totals across enabled cards in this
   * group (e.g. Bilt Cash under Bilt Rewards). Shown as extra income
   * figures alongside the primary total. */
  secondaries: SecondaryAnnual[]
  /** End-of-projection balance in this currency: sum of per-card
   * `cr.total_points` across enabled cards (`annual_point_earn_for_balance
   * × card_active_years + SUB`). Null when the calc hasn't run or no
   * enabled card in this group has a result. */
  totalBalance: number | null
  /** CPP to value the balance against when rendering a cash group. */
  balanceCpp: number | null
}

interface GroupSectionProps {
  group: GroupData
  range: Range
  roadmapById: Map<number, RoadmapResponse['cards'][number]>
  isUpdating: boolean
  isStale: boolean
  includeSubs: boolean
  rightColumnPx: number
  walletWindowYears: number
  currencyWindowYears: number | undefined
  walletId: number
  walletCards: WalletCard[]
  isExpanded: boolean
  isDisabledExpanded: boolean
  onToggleEnabled: (cardId: number, enabled: boolean) => void
  onEditCard: (wc: WalletCard) => void
  onToggleExpanded: (currencyId: number) => void
  onToggleDisabledExpanded: () => void
}

function GroupSection({
  group,
  range,
  roadmapById,
  isUpdating,
  isStale,
  includeSubs,
  rightColumnPx,
  walletWindowYears,
  currencyWindowYears,
  walletId,
  walletCards,
  isExpanded,
  isDisabledExpanded,
  onToggleEnabled,
  onEditCard,
  onToggleExpanded,
  onToggleDisabledExpanded,
}: GroupSectionProps) {
  const balanceLabel = formatGroupBalance(group)
  const incomeLabel = formatGroupIncome(group, includeSubs, walletWindowYears, currencyWindowYears)

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
        <CurrencyPhoto slug={group.photoSlug} name={group.name} fallbackColor={group.color} isCash={group.rewardKind === 'cash'} />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-slate-200 truncate">{group.name}</div>
          {(balanceLabel || incomeLabel || group.secondaries.length > 0) && (
            <div
              className={`flex items-center gap-1.5 text-xs text-slate-400 truncate transition-opacity ${isStale ? 'opacity-50' : ''}`}
              title={isStale ? 'Results are out of date — click Calculate to refresh' : undefined}
            >
              {balanceLabel && <span>{balanceLabel}</span>}
              {incomeLabel && (
                <>
                  {balanceLabel && <span className="text-slate-600 text-sm leading-none">·</span>}
                  <span className="text-slate-500">{incomeLabel}</span>
                </>
              )}
              {group.secondaries.map((s) => (
                <span key={`bal-${s.id}`} className="text-slate-500">
                  <span className="mr-1 text-slate-700">·</span>
                  {formatSecondaryBalance(s)}
                </span>
              ))}
            </div>
          )}
        </div>
        {group.currencyId != null && (
          <button
            type="button"
            onClick={() => onToggleExpanded(group.currencyId!)}
            className={`ml-auto p-1.5 rounded transition-colors shrink-0 ${
              isExpanded
                ? 'bg-slate-700 text-indigo-300'
                : 'text-slate-500 hover:text-indigo-400 hover:bg-slate-700'
            }`}
            title={
              isExpanded
                ? `Close ${group.name} settings`
                : `Edit ${group.name} settings`
            }
            aria-label={`Edit ${group.name} settings`}
            aria-expanded={isExpanded}
          >
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="4" y1="6" x2="20" y2="6" />
              <line x1="4" y1="12" x2="20" y2="12" />
              <line x1="4" y1="18" x2="20" y2="18" />
              <circle cx="8" cy="6" r="2" fill="currentColor" stroke="none" />
              <circle cx="16" cy="12" r="2" fill="currentColor" stroke="none" />
              <circle cx="10" cy="18" r="2" fill="currentColor" stroke="none" />
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
      </div>
      {isExpanded && group.currencyId != null && (
        <CurrencySettingsDropdown
          walletId={walletId}
          walletCards={walletCards}
          currencyId={group.currencyId}
          leftGutterPx={LEFT_GUTTER}
          onClose={() => onToggleExpanded(group.currencyId!)}
        />
      )}
      {group.cards
        .filter(({ wc }) => wc.is_enabled)
        .map(({ wc, cr, secondary }) => (
          <CardRow
            key={wc.id}
            wc={wc}
            cr={cr}
            secondary={secondary}
            color={group.color}
            range={range}
            roadmapStatus={roadmapById.get(wc.card_id)}
            isUpdating={isUpdating}
            isStale={isStale}
            includeSubs={includeSubs}
            rightColumnPx={rightColumnPx}
            onToggleEnabled={onToggleEnabled}
            onEditCard={onEditCard}
          />
        ))}
      <DisabledFoldRow
        count={group.cards.filter(({ wc }) => !wc.is_enabled).length}
        expanded={isDisabledExpanded}
        onToggle={onToggleDisabledExpanded}
      />
      {isDisabledExpanded &&
        group.cards
          .filter(({ wc }) => !wc.is_enabled)
          .map(({ wc, cr, secondary }) => (
            <CardRow
              key={wc.id}
              wc={wc}
              cr={cr}
              secondary={secondary}
              color={group.color}
              range={range}
              roadmapStatus={roadmapById.get(wc.card_id)}
              isUpdating={isUpdating}
              isStale={isStale}
              includeSubs={includeSubs}
              rightColumnPx={rightColumnPx}
              onToggleEnabled={onToggleEnabled}
              onEditCard={onEditCard}
            />
          ))}
    </>
  )
}

const DISABLED_FOLD_ROW_HEIGHT = 26

function DisabledFoldRow({
  count,
  expanded,
  onToggle,
}: {
  count: number
  expanded: boolean
  onToggle: () => void
}) {
  if (count === 0) return null
  const label = `${count} Disabled Card${count === 1 ? '' : 's'}`
  return (
    <div className="contents">
      <button
        type="button"
        onClick={onToggle}
        className={`flex items-center gap-1.5 px-3 ${DIVIDER_CLASS} bg-slate-900/40 hover:bg-slate-800/40 text-slate-400 text-xs transition-colors`}
        style={{ height: DISABLED_FOLD_ROW_HEIGHT }}
        aria-expanded={expanded}
        title={expanded ? 'Hide disabled cards' : 'Show disabled cards'}
      >
        <svg
          width="12"
          height="12"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`shrink-0 transition-transform ${expanded ? 'rotate-90' : ''}`}
          aria-hidden
        >
          <polyline points="9 18 15 12 9 6" />
        </svg>
        <span className="truncate">{label}</span>
      </button>
      <button
        type="button"
        onClick={onToggle}
        className={`${DIVIDER_CLASS} bg-slate-900/40 hover:bg-slate-800/40 transition-colors`}
        style={{ height: DISABLED_FOLD_ROW_HEIGHT }}
        aria-label={expanded ? 'Hide disabled cards' : 'Show disabled cards'}
        tabIndex={-1}
      />
    </div>
  )
}

interface CardRowProps {
  wc: WalletCard
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
  onEditCard: (wc: WalletCard) => void
}

function CardRow({
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
  const addedMs = parseDate(wc.added_date).getTime()
  const closedMs = wc.closed_date ? parseDate(wc.closed_date).getTime() : range.endMs

  const barStartPct = pctOf(range, Math.max(addedMs, range.startMs))
  const barEndPct = pctOf(range, Math.min(closedMs, range.endMs))
  const barWidthPct = Math.max(0, barEndPct - barStartPct)

  const enabled = wc.is_enabled

  // sub_earned_date is deprecated and ignored — the projected earn date
  // (auto-computed by the backend from spend rate) is the single source of
  // truth for the SUB tick marker.
  const subProjectedDate =
    wc.sub_projected_earn_date ?? roadmapStatus?.sub_projected_earn_date ?? null
  const subMs = subProjectedDate ? parseDate(subProjectedDate).getTime() : null
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
  const incomeLabel = enabled ? formatCardIncome(cr, includeSubs) : '—'
  const eafValue = enabled ? cardEafActive(cr, includeSubs) : null
  const eafLabelText = enabled
    ? eafValue != null
      ? `${formatMoney(eafValue)} EAF`
      : null
    : '—'

  const tooltip = [
    `Added: ${formatDate(wc.added_date)}`,
    wc.closed_date ? `Closed: ${formatDate(wc.closed_date)}` : null,
    enabled
      ? subProjectedDate
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
              <div
                className={`text-xs text-slate-500 truncate transition-opacity ${isStale ? 'opacity-50' : ''}`}
                title={isStale ? 'Out of date' : undefined}
              >
                {incomeLabel}
                {secondary && (
                  <>
                    <span className="mx-1 text-slate-700">·</span>
                    {formatSecondaryAnnual(secondary)}
                  </>
                )}
                {wc.credit_totals
                  .filter((t) => t.value > 0)
                  .map((t) => (
                    <span key={`${t.kind}-${t.currency_id ?? 'cash'}`}>
                      <span className="mx-1 text-slate-700">·</span>
                      {t.kind === 'cash'
                        ? `${formatMoney(t.value)} Credits`
                        : `${formatPoints(t.value)} ${pointsUnitLabel(t.currency_name)} Credits`}
                    </span>
                  ))}
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
        className={`relative ${DIVIDER_CLASS}`}
        style={{ height: CARD_ROW_HEIGHT }}
        title={tooltip}
      >
        {barWidthPct > 0 && (() => {
          const roundLeft = addedMs > range.startMs
          const roundRight = closedMs < range.endMs
          const roundedClass = `${roundLeft ? 'rounded-l-full' : ''} ${roundRight ? 'rounded-r-full' : ''}`.trim()
          return (
            <div
              className={`absolute ${roundedClass}`}
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
          )
        })()}
        {barWidthPct > 0 && eafLabelText != null && (() => {
          const labelText = eafLabelText
          const baseColor = !enabled
            ? 'text-slate-500'
            : eafValue != null && eafValue < 0
              ? 'text-emerald-400'
              : eafValue != null && eafValue > 0
                ? 'text-red-400'
                : 'text-slate-200'
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
          <SubTick pct={subPct} rowHeight={CARD_ROW_HEIGHT} barHeight={barHeight} />
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
      src={`/photos/cards/${slug}.png`}
      alt={name}
      className="w-14 h-9 object-contain shrink-0"
      onError={(e) => {
        const el = e.currentTarget
        el.style.display = 'none'
      }}
    />
  )
}

function CurrencyPhoto({ slug, name, fallbackColor, isCash }: { slug: string | null; name: string; fallbackColor: string; isCash?: boolean }) {
  const [failed, setFailed] = useState(false)
  if (!slug || failed) {
    if (isCash) {
      return (
        <div className="w-7 h-7 rounded-full shrink-0 bg-emerald-600 flex items-center justify-center">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="1" x2="12" y2="23" />
            <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
          </svg>
        </div>
      )
    }
    return (
      <div className="w-7 h-7 rounded-full shrink-0" style={{ backgroundColor: fallbackColor }} />
    )
  }
  return (
    <img
      src={`/photos/currencies/${slug}`}
      alt={name}
      className="w-7 h-7 rounded-full object-cover shrink-0"
      onError={() => setFailed(true)}
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
  pct,
  rowHeight,
  barHeight,
}: {
  pct: number
  rowHeight: number
  barHeight: number
}) {
  // A thin amber vertical tick marking the projected SUB earn date,
  // extending a few px past the bar top and bottom to stay visible
  // regardless of bar fill color.
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
        width: 0,
        transform: 'translateX(-1px)',
        borderLeft: '2px dashed #f59e0b',
      }}
      title="SUB projected"
    />
  )
}
