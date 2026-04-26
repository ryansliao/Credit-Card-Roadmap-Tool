import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { Card, CardResult, UserSpendCategory } from '../../../../api/client'
import { walletSpendApi } from '../../../../api/client'
import type { ResolvedCard } from '../../lib/resolveScenarioCards'
import { InfoQuoteBox } from '../../../../components/InfoPopover'
import { formatMoneyExact, formatPointsExact } from '../../../../utils/format'
import { queryKeys } from '../../../../lib/queryKeys'
import { useCardLibrary } from '../../hooks/useCardLibrary'

interface Props {
  selectedCards: CardResult[]
  walletCards: ResolvedCard[]
  isTotal: boolean
  totalYears: number
  isStale: boolean
}

function CardPhoto({ slug, name }: { slug: string | null; name: string }) {
  const [failed, setFailed] = useState(false)
  if (!slug || failed) {
    return (
      <div className="w-full h-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center">
        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-slate-500">
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
          <line x1="1" y1="10" x2="23" y2="10" />
        </svg>
      </div>
    )
  }
  return (
    <img
      src={`/photos/cards/${slug}.png`}
      alt={name}
      title={name}
      className="w-full h-full object-contain"
      onError={() => setFailed(true)}
    />
  )
}

export function SpendTabContent({
  selectedCards,
  walletCards,
  isTotal,
  totalYears,
  isStale,
}: Props) {
  const { data: spendItems = [], isLoading } = useQuery({
    queryKey: queryKeys.walletSpendItemsSingular(),
    queryFn: () => walletSpendApi.list(),
  })

  const { data: cardLibrary = [] } = useCardLibrary()

  const [infoCategory, setInfoCategory] = useState<
    { cat: UserSpendCategory; anchor: HTMLElement } | null
  >(null)

  const cardLibById = useMemo(() => {
    const m = new Map<number, Card>()
    for (const c of cardLibrary) m.set(c.id, c)
    return m
  }, [cardLibrary])

  // CardResult.card_id is the synthetic CardInstance.id under the new
  // model, not the library card_id. Translate via walletCards so library
  // lookups (rotating groups, portal premiums, standalone multipliers)
  // resolve correctly. Without this every per-card library lookup
  // returned undefined → no rotating badge, no portal multiplier
  // adjustment, baseline ROS gets inflated for portal cards.
  const libraryCardIdByInstanceId = useMemo(() => {
    const m = new Map<number, number>()
    for (const wc of walletCards) m.set(wc.instance_id, wc.card_id)
    return m
  }, [walletCards])

  function libCardForInstanceId(instanceId: number): Card | undefined {
    const libId = libraryCardIdByInstanceId.get(instanceId)
    return libId != null ? cardLibById.get(libId) : undefined
  }

  // Set of earn-category names (lowercase) covered by any rotating group
  // on the card's library definition. Categories in this set must not be
  // credited with their rotating rate in the baseline ROS calculation —
  // fall back to the card's non-rotating rate (standalone or All Other).
  function getRotatingCategoriesForInstanceId(instanceId: number): Set<string> {
    const lib = libCardForInstanceId(instanceId)
    const out = new Set<string>()
    if (!lib) return out
    for (const g of lib.multiplier_groups ?? []) {
      if (!g.is_rotating) continue
      for (const c of g.categories ?? []) out.add(c.name.trim().toLowerCase())
    }
    return out
  }

  // Standalone non-portal, non-group multipliers keyed by lowercase category
  // name. Used as the fallback rate for categories that only earn a bonus
  // via a rotating group.
  function getStandaloneMultsForInstanceId(instanceId: number): Map<string, number> {
    const lib = libCardForInstanceId(instanceId)
    const out = new Map<string, number>()
    if (!lib) return out
    for (const m of lib.multipliers ?? []) {
      if (m.is_portal) continue
      out.set(m.category.trim().toLowerCase(), m.multiplier)
    }
    return out
  }

  // Portal-elevated multipliers for the card. The backend pre-expands portal
  // rows through the spend-category hierarchy (a portal row on "Travel"
  // produces entries for Hotels, Airlines, Flights, …), so this is just a
  // direct keying of `card.portal_premiums` by lowercase category name.
  function getPortalMultsForInstanceId(instanceId: number): Map<string, { mult: number; isAdditive: boolean }> {
    const out = new Map<string, { mult: number; isAdditive: boolean }>()
    const lib = libCardForInstanceId(instanceId)
    if (!lib) return out
    for (const p of lib.portal_premiums ?? []) {
      out.set(p.category.trim().toLowerCase(), {
        mult: p.multiplier,
        isAdditive: !!p.is_additive,
      })
    }
    return out
  }

  // Closed / product-changed-away-from cards are excluded from earn allocation.
  // CardResult.card_id under the new model is the synthetic instance.id (=
  // ResolvedCard.id), so we exclude by instance id throughout. PC source
  // instances are excluded when a future card carries pc_from_instance_id.
  const excludedInstanceIds = useMemo(() => {
    const ids = new Set<number>()
    for (const wc of walletCards) {
      if (wc.panel !== 'in_wallet' && wc.panel !== 'future_cards') continue
      if (wc.closed_date) ids.add(wc.instance_id)
    }
    for (const pcCard of walletCards) {
      if (!pcCard.is_future) continue
      if (pcCard.acquisition_type !== 'product_change') continue
      if (pcCard.pc_from_instance_id != null) {
        ids.add(pcCard.pc_from_instance_id)
      }
    }
    return ids
  }, [walletCards])

  const topRosCards = useMemo(
    () => selectedCards.filter((c) => !excludedInstanceIds.has(c.card_id)),
    [selectedCards, excludedInstanceIds]
  )

  // Cycling through cards in the third column. Index is clamped to the
  // current card list so removing a card doesn't leave a stale index.
  const [cardCursor, setCardCursor] = useState(0)
  const cardCount = selectedCards.length
  const safeCardIndex = cardCount > 0 ? cardCursor % cardCount : 0
  const currentCard = cardCount > 0 ? selectedCards[safeCardIndex] : null

  function cycleCard(delta: number) {
    if (cardCount === 0) return
    setCardCursor((c) => (c + delta + cardCount) % cardCount)
  }

  // Baseline multiplier for a card's earn category, excluding both rotating
  // group boosts and travel-portal elevated rates. Rotating-only categories
  // fall back to the card's standalone rate, or to All Other when none.
  function getBaselineMultForEarnCategory(card: CardResult, earnCatName: string): number {
    const lower = earnCatName.trim().toLowerCase()
    const mults = card.category_multipliers ?? {}
    let allOther = 1.0
    let directMatch: number | null = null
    for (const [k, v] of Object.entries(mults)) {
      const kl = k.trim().toLowerCase()
      if (kl === lower) directMatch = v
      if (kl === 'all other') allOther = v
    }
    const rotating = getRotatingCategoriesForInstanceId(card.card_id)
    if (rotating.has(lower)) {
      const standalone = getStandaloneMultsForInstanceId(card.card_id).get(lower)
      if (standalone !== undefined) return standalone
      return allOther
    }
    if (directMatch !== null) return directMatch
    return allOther
  }

  // Portal-adjusted multiplier assuming all eligible spend on this card
  // flows through its travel portal. Returns null when the card has no
  // portal premium covering this earn category.
  function getPortalMultForEarnCategory(card: CardResult, earnCatName: string): number | null {
    const portal = getPortalMultsForInstanceId(card.card_id).get(earnCatName.trim().toLowerCase())
    if (!portal) return null
    const base = getBaselineMultForEarnCategory(card, earnCatName)
    return portal.isAdditive ? base + portal.mult : portal.mult
  }

  function userCategoryHasPortalCoverage(card: CardResult, userCategory: UserSpendCategory): boolean {
    const portals = getPortalMultsForInstanceId(card.card_id)
    if (portals.size === 0) return false
    for (const m of userCategory.mappings) {
      if (portals.has(m.earn_category.category.trim().toLowerCase())) return true
    }
    return false
  }

  // Full rotating rate for a card's earn category. For categories covered by
  // a rotating group, the backend's `category_multipliers` already reports the
  // active-quarter rate (base + additive premium, or the replacement rate for
  // non-additive groups). Categories outside any rotating group return null so
  // the caller falls back to baseline.
  function getRotatingMultForEarnCategory(card: CardResult, earnCatName: string): number | null {
    const lower = earnCatName.trim().toLowerCase()
    if (!getRotatingCategoriesForInstanceId(card.card_id).has(lower)) return null
    const mults = card.category_multipliers ?? {}
    for (const [k, v] of Object.entries(mults)) {
      if (k.trim().toLowerCase() === lower) return v
    }
    return null
  }

  function userCategoryHasRotatingCoverage(card: CardResult, userCategory: UserSpendCategory): boolean {
    const rotating = getRotatingCategoriesForInstanceId(card.card_id)
    if (rotating.size === 0) return false
    for (const m of userCategory.mappings) {
      if (rotating.has(m.earn_category.category.trim().toLowerCase())) return true
    }
    return false
  }

  type RosMode = 'baseline' | 'rotating' | 'portal'

  function getWeightedRosForCard(
    card: CardResult,
    userCategory: UserSpendCategory | null,
    mode: RosMode,
  ): number {
    if (!userCategory || userCategory.mappings.length === 0) {
      return 0
    }
    // Recurring percentage bonus factor (e.g., CSP 10% → 1.1)
    const earnBonusFactor =
      card.annual_bonus_percent && !card.annual_bonus_first_year_only
        ? 1 + card.annual_bonus_percent / 100
        : 1

    // Rotating mode: the card earns its rotating rate on whatever category
    // rotates that quarter, so take the max rotating rate across the user
    // category's mappings that fall in the rotating group — don't blend with
    // baseline for non-rotating mappings. This makes uniform-rate rotating
    // cards (e.g. original Chase Freedom at 5x on every rotating category)
    // produce the same rotating ROS across all user categories that have
    // any rotating coverage.
    if (mode === 'rotating') {
      let maxRotRate = 0
      for (const mapping of userCategory.mappings) {
        const rotMult = getRotatingMultForEarnCategory(card, mapping.earn_category.category)
        if (rotMult !== null && rotMult > maxRotRate) maxRotRate = rotMult
      }
      return maxRotRate * card.cents_per_point * earnBonusFactor
    }

    let weightedRos = 0
    for (const mapping of userCategory.mappings) {
      const baseline = getBaselineMultForEarnCategory(card, mapping.earn_category.category)
      let mult = baseline
      if (mode === 'portal') {
        const portalMult = getPortalMultForEarnCategory(card, mapping.earn_category.category)
        if (portalMult !== null && portalMult > mult) mult = portalMult
      }
      weightedRos += mapping.default_weight * mult * card.cents_per_point * earnBonusFactor
    }
    return weightedRos
  }

  interface TopCardEntry {
    card: CardResult
    ros: number
    tag: 'baseline' | 'rotating' | 'portal'
  }

  function topCardsForCategory(userCategory: UserSpendCategory | null): TopCardEntry[] {
    if (topRosCards.length === 0 || !userCategory) return []
    // Baseline top (excludes rotating bonuses and portal elevation).
    let baselineBest = -Infinity
    let baselineCards: CardResult[] = []
    for (const card of topRosCards) {
      const r = getWeightedRosForCard(card, userCategory, 'baseline')
      if (r > baselineBest + 1e-9) {
        baselineBest = r
        baselineCards = [card]
      } else if (Math.abs(r - baselineBest) <= 1e-9) {
        baselineCards.push(card)
      }
    }
    if (!(baselineBest > 0)) return []

    const entries: TopCardEntry[] = baselineCards.map((card) => ({
      card,
      ros: baselineBest,
      tag: 'baseline',
    }))

    // Rotating / portal candidates: any card whose boosted ROS strictly
    // exceeds both its own baseline (so the boost actually helps the card)
    // and the baseline top. Both tags can appear for the same card when
    // the user category draws from overlapping earn categories (e.g. Chase
    // Freedom Flex has rotating Dining and a Travel portal row).
    const rotatingEntries: TopCardEntry[] = []
    const portalEntries: TopCardEntry[] = []
    for (const card of topRosCards) {
      const ownBaseline = getWeightedRosForCard(card, userCategory, 'baseline')

      if (userCategoryHasRotatingCoverage(card, userCategory)) {
        const rotRos = getWeightedRosForCard(card, userCategory, 'rotating')
        if (rotRos > ownBaseline + 1e-9 && rotRos > baselineBest + 1e-9) {
          rotatingEntries.push({ card, ros: rotRos, tag: 'rotating' })
        }
      }

      if (userCategoryHasPortalCoverage(card, userCategory)) {
        const portalRos = getWeightedRosForCard(card, userCategory, 'portal')
        if (portalRos > ownBaseline + 1e-9 && portalRos > baselineBest + 1e-9) {
          portalEntries.push({ card, ros: portalRos, tag: 'portal' })
        }
      }
    }
    rotatingEntries.sort((a, b) => b.ros - a.ros)
    portalEntries.sort((a, b) => b.ros - a.ros)
    // Cap portal to a single entry per category — showing every card whose
    // portal beats baseline top gets noisy on Travel-heavy buckets where
    // several cards qualify, and only the highest one is actionable.
    const topPortal = portalEntries.length > 0 ? [portalEntries[0]] : []
    return [...entries, ...rotatingEntries, ...topPortal]
  }

  function formatRos(ros: number): string {
    if (Number.isInteger(ros)) return `${ros}%`
    return `${ros.toFixed(2).replace(/\.?0+$/, '')}%`
  }

  // Build an earn-category × card lookup of annual points. The backend keys
  // `category_earn` by the granular earn-category name ("Wholesale Clubs"),
  // not the user-facing spend category ("Groceries"), so we need to
  // aggregate across a user category's mappings when reading per row.
  const earnByCategoryByCard = useMemo(() => {
    const map = new Map<string, Map<number, number>>()
    for (const card of selectedCards) {
      for (const item of card.category_earn) {
        if (!map.has(item.category)) map.set(item.category, new Map())
        map.get(item.category)!.set(card.card_id, item.points)
      }
    }
    return map
  }, [selectedCards])

  function earnForUserCategory(
    card: CardResult,
    userCategory: UserSpendCategory | null,
  ): number {
    if (!userCategory) return 0
    let total = 0
    for (const m of userCategory.mappings) {
      total += earnByCategoryByCard.get(m.earn_category.category)?.get(card.card_id) ?? 0
    }
    return total
  }

  function formatCardEarn(card: CardResult, points: number): string {
    // `points` is already the time-weighted annual earn (same basis as
    // `card.annual_point_earn` shown on the main tab). For the "Total"
    // view multiply by the window length; for the annual view display
    // the time-weighted annual rate directly so it matches the main tab.
    const adjusted = isTotal ? points * totalYears : points
    if ((card.effective_reward_kind ?? 'points') === 'cash') {
      return formatMoneyExact((adjusted * card.cents_per_point) / 100)
    }
    return formatPointsExact(adjusted)
  }

  // First-time empty state: wallet has cards but no calc has run, so the
  // backend hasn't produced any selected card results to populate the Top
  // ROS column or per-card income figures. Show an inline prompt above the
  // table so the empty cells read as "needs calc" rather than "no data".
  const showCalculatePrompt =
    !isLoading && selectedCards.length === 0 && walletCards.length > 0

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      {isLoading ? (
        <div className="text-slate-500 text-sm">Loading…</div>
      ) : (
        <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-slate-800">
          {showCalculatePrompt && (
            <div className="px-3 py-2 text-xs text-indigo-200 bg-indigo-900/20 border-b border-indigo-700/40">
              Click <span className="font-semibold text-indigo-300">Calculate</span> to see your top earning card per category.
            </div>
          )}
          <table className="w-full text-sm border-collapse table-fixed">
            <colgroup>
              <col />
              <col className="w-28" />
              <col className="w-72" />
              <col className="w-80" />
            </colgroup>
            <thead className="sticky top-0 bg-slate-900 z-10">
              <tr>
                <th className="text-left text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-r border-slate-800">
                  Category
                </th>
                <th className="text-center text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-r border-slate-800 whitespace-nowrap">
                  Annual Spend
                </th>
                <th className="text-center text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-r border-slate-800 whitespace-nowrap">
                  Annual Point Income
                </th>
                <th
                  rowSpan={2}
                  className="text-center text-sm font-semibold text-slate-300 px-3 py-2.5 border-b-2 border-slate-700 bg-slate-900 whitespace-nowrap"
                >
                  Top ROS Card
                </th>
              </tr>
              {/* Total row — kept inside thead so it sticks together with
                  the header row when the table body scrolls. */}
              <tr className="border-b-2 border-slate-700 bg-slate-800/50">
                <th
                  scope="row"
                  className="text-left px-3 py-2 text-slate-100 font-semibold border-r border-slate-800/60"
                >
                  Total
                </th>
                <td className="text-center px-2 py-2 tabular-nums border-r border-slate-800/60">
                  <div className="text-slate-100 font-semibold">
                    ${spendItems.reduce((sum, item) => sum + (item.amount || 0), 0).toLocaleString()}
                  </div>
                </td>
                <td className="px-2 py-2 text-slate-300 border-r border-slate-800/60">
                  <div className="flex items-center justify-between gap-2 w-full">
                    <button
                      type="button"
                      onClick={() => cycleCard(-1)}
                      disabled={cardCount < 2}
                      className="shrink-0 p-0.5 rounded text-slate-500 hover:text-slate-200 hover:bg-slate-800 disabled:opacity-30 disabled:hover:text-slate-500 disabled:hover:bg-transparent"
                      aria-label="Previous card"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="15 18 9 12 15 6" />
                      </svg>
                    </button>
                    <span className="flex-1 min-w-0 truncate text-center" title={currentCard?.card_name ?? ''}>
                      {currentCard?.card_name ?? '—'}
                    </span>
                    <button
                      type="button"
                      onClick={() => cycleCard(1)}
                      disabled={cardCount < 2}
                      className="shrink-0 p-0.5 rounded text-slate-500 hover:text-slate-200 hover:bg-slate-800 disabled:opacity-30 disabled:hover:text-slate-500 disabled:hover:bg-transparent"
                      aria-label="Next card"
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="9 18 15 12 9 6" />
                      </svg>
                    </button>
                  </div>
                </td>
              </tr>
            </thead>
            <tbody>
              {spendItems.map((item) => {
                const catName = item.user_spend_category?.name ?? 'Unknown'
                const topEntries = topCardsForCategory(item.user_spend_category)
                const noTop = topEntries.length === 0
                return (
                  <tr key={item.id} className="border-b border-slate-800/60">
                    <td className="text-left px-3 py-2 text-slate-200 border-r border-slate-800/60">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate" title={catName}>
                          {catName}
                        </span>
                        {item.user_spend_category && item.user_spend_category.mappings.length > 0 && (() => {
                          const cat = item.user_spend_category
                          const isOpen = infoCategory?.cat.id === cat.id
                          return (
                            <button
                              type="button"
                              onClick={(e) => {
                                const anchor = e.currentTarget
                                setInfoCategory(isOpen ? null : { cat, anchor })
                              }}
                              aria-expanded={isOpen}
                              className={`shrink-0 p-0.5 rounded transition-colors ${
                                isOpen
                                  ? 'text-indigo-300 bg-indigo-500/10'
                                  : 'text-slate-500 hover:text-slate-300 hover:bg-slate-700/50'
                              }`}
                              title="View category details"
                            >
                              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                                <circle cx="12" cy="12" r="10" />
                                <path d="M12 16v-4" />
                                <path d="M12 8h.01" />
                              </svg>
                            </button>
                          )
                        })()}
                      </div>
                    </td>
                    <td className="text-center px-2 py-2 tabular-nums border-r border-slate-800/60">
                      <span className="text-slate-200">
                        ${item.amount === 0 ? '0' : Math.round(item.amount).toLocaleString()}
                      </span>
                    </td>
                    <td
                      className={`text-center tabular-nums px-3 py-2 text-slate-200 border-r border-slate-800/60 transition-opacity ${isStale ? 'opacity-50' : ''}`}
                      title={isStale ? 'Out of date' : undefined}
                    >
                      {currentCard ? (
                        (() => {
                          const pts = earnForUserCategory(currentCard, item.user_spend_category)
                          return pts > 0 ? (
                            formatCardEarn(currentCard, pts)
                          ) : (
                            <span className="text-slate-700">—</span>
                          )
                        })()
                      ) : (
                        <span className="text-slate-700">—</span>
                      )}
                    </td>
                    <td
                      className={`px-3 py-2 text-slate-200 transition-opacity ${isStale ? 'opacity-50' : ''}`}
                      title={isStale ? 'Out of date' : undefined}
                    >
                      {noTop ? (
                        <div className="text-center text-slate-700">—</div>
                      ) : (
                        <div className="flex flex-col gap-1.5">
                          {topEntries.map((entry) => (
                            <div
                              key={`${entry.card.card_id}-${entry.tag}`}
                              className="flex items-center gap-2 min-w-0"
                            >
                              <div className="w-[60px] h-9 shrink-0 rounded overflow-hidden bg-slate-700/50">
                                <CardPhoto slug={entry.card.photo_slug} name={entry.card.card_name} />
                              </div>
                              <div className="min-w-0 flex-1 text-left">
                                <div className="text-xs text-slate-200 truncate mb-0.5" title={entry.card.card_name}>
                                  {entry.card.card_name}
                                </div>
                                <div className="flex items-center gap-1.5">
                                  <div className="text-xs font-semibold text-indigo-300 tabular-nums">
                                    {formatRos(entry.ros)}
                                  </div>
                                  {entry.tag === 'portal' && (
                                    <span
                                      className="text-[10px] uppercase tracking-wide text-amber-300/90 bg-amber-500/10 border border-amber-500/30 rounded px-1 py-[1px]"
                                      title="Requires booking through this card's travel portal"
                                    >
                                      Portal
                                    </span>
                                  )}
                                  {entry.tag === 'rotating' && (
                                    <span
                                      className="text-[10px] uppercase tracking-wide text-violet-300/90 bg-violet-500/10 border border-violet-500/30 rounded px-1 py-[1px]"
                                      title="Only applies when this category is in the card's active rotating bonus"
                                    >
                                      Rotating
                                    </span>
                                  )}
                                </div>
                              </div>
                            </div>
                          ))}
                        </div>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {infoCategory && (
        <InfoQuoteBox
          anchorEl={infoCategory.anchor}
          title={infoCategory.cat.name}
          onClose={() => setInfoCategory(null)}
        >
          {infoCategory.cat.description && <p>{infoCategory.cat.description}</p>}
          <div>
            <p className="text-slate-300 font-medium mb-1.5">Includes spend on:</p>
            <ul className="space-y-1">
              {infoCategory.cat.mappings
                .sort((a, b) => b.default_weight - a.default_weight)
                .map((mapping) => (
                  <li key={mapping.id} className="flex items-center justify-between">
                    <span className="text-slate-300">{mapping.earn_category.category}</span>
                    <span className="text-slate-500 tabular-nums">
                      {Math.round(mapping.default_weight * 100)}%
                    </span>
                  </li>
                ))}
            </ul>
          </div>
        </InfoQuoteBox>
      )}
    </div>
  )
}
