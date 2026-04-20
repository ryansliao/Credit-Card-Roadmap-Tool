import { useMemo, useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { CardResult, UserSpendCategory, WalletCard } from '../../../../api/client'
import { walletSpendItemsApi } from '../../../../api/client'
import { ModalBackdrop } from '../../../../components/ModalBackdrop'
import { formatMoneyExact, formatPointsExact } from '../../../../utils/format'
import { queryKeys } from '../../../../lib/queryKeys'

interface Props {
  walletId: number | null
  selectedCards: CardResult[]
  walletCards: WalletCard[]
  isTotal: boolean
  totalYears: number
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
  walletId,
  selectedCards,
  walletCards,
  isTotal,
  totalYears,
}: Props) {
  const { data: spendItems = [], isLoading } = useQuery({
    queryKey: queryKeys.walletSpendItems(walletId),
    queryFn: () => walletSpendItemsApi.list(walletId!),
    enabled: walletId != null,
  })

  const [infoCategory, setInfoCategory] = useState<UserSpendCategory | null>(null)

  // Closed / product-changed-away-from cards; matches CardsListPanel dimming.
  const excludedCardIds = useMemo(() => {
    const ids = new Set<number>()
    for (const wc of walletCards) {
      if (wc.panel !== 'in_wallet' && wc.panel !== 'future_cards') continue
      if (wc.closed_date) ids.add(wc.card_id)
    }
    for (const pcCard of walletCards) {
      if (pcCard.acquisition_type !== 'product_change' || pcCard.panel !== 'future_cards') continue
      if (pcCard.pc_from_card_id != null) {
        ids.add(pcCard.pc_from_card_id)
      } else {
        for (const c of walletCards) {
          if (c.product_changed_date && c.product_changed_date === pcCard.added_date) {
            ids.add(c.card_id)
          }
        }
      }
    }
    return ids
  }, [walletCards])

  const topRosCards = useMemo(
    () => selectedCards.filter((c) => !excludedCardIds.has(c.card_id)),
    [selectedCards, excludedCardIds]
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

  function getMultForCard(card: CardResult, catName: string): number {
    const mults = card.category_multipliers ?? {}
    const lower = catName.trim().toLowerCase()
    let allOther = 1.0
    for (const [k, v] of Object.entries(mults)) {
      const kl = k.trim().toLowerCase()
      if (kl === lower) return v
      if (kl === 'all other') allOther = v
    }
    return allOther
  }

  function getRosForCard(card: CardResult, catName: string): number {
    // Return on spend, expressed as a percentage: multiplier × effective CPP.
    // e.g. 3x at 2¢/pt → 6 (i.e. 6% back).
    return getMultForCard(card, catName) * card.cents_per_point
  }

  function topCardsForCategory(catName: string): { cards: CardResult[]; ros: number } {
    if (topRosCards.length === 0) return { cards: [], ros: 0 }
    let best = -Infinity
    let bestCards: CardResult[] = []
    for (const card of topRosCards) {
      const r = getRosForCard(card, catName)
      if (r > best + 1e-9) {
        best = r
        bestCards = [card]
      } else if (Math.abs(r - best) <= 1e-9) {
        bestCards.push(card)
      }
    }
    return { cards: bestCards, ros: best }
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

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0">
      {isLoading ? (
        <div className="text-slate-500 text-sm">Loading…</div>
      ) : (
        <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-slate-800">
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
                <th className="text-center text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-r border-slate-800">
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
                    <span className="flex-1 min-w-0 truncate">Annual Point Income</span>
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
                <td className="text-center px-3 py-2 text-slate-300 border-r border-slate-800/60 truncate" title={currentCard?.card_name ?? ''}>
                  {currentCard?.card_name ?? '—'}
                </td>
              </tr>
            </thead>
            <tbody>
              {spendItems.map((item) => {
                const catName = item.user_spend_category?.name ?? 'Unknown'
                const top = topCardsForCategory(catName)
                const noTop = top.cards.length === 0 || top.ros <= 0
                return (
                  <tr key={item.id} className="border-b border-slate-800/60">
                    <td className="text-left px-3 py-2 text-slate-200 border-r border-slate-800/60">
                      <div className="flex items-center gap-1.5">
                        <span className="truncate" title={catName}>
                          {catName}
                        </span>
                        {item.user_spend_category && item.user_spend_category.mappings.length > 0 && (
                          <button
                            type="button"
                            onClick={() => setInfoCategory(item.user_spend_category)}
                            className="shrink-0 p-0.5 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-700/50"
                            title="View category details"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <circle cx="12" cy="12" r="10" />
                              <path d="M12 16v-4" />
                              <path d="M12 8h.01" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="text-center px-2 py-2 tabular-nums border-r border-slate-800/60">
                      <span className="text-slate-200">
                        ${item.amount === 0 ? '0' : Math.round(item.amount).toLocaleString()}
                      </span>
                    </td>
                    <td className="text-center tabular-nums px-3 py-2 text-slate-200 border-r border-slate-800/60">
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
                    <td className="px-3 py-2 text-slate-200">
                      {noTop ? (
                        <div className="text-center text-slate-700">—</div>
                      ) : (
                        <div className="flex flex-col gap-1.5">
                          {top.cards.map((c) => (
                            <div key={c.card_id} className="flex items-center gap-2 min-w-0">
                              <div className="w-[60px] h-9 shrink-0 rounded overflow-hidden bg-slate-700/50">
                                <CardPhoto slug={c.photo_slug} name={c.card_name} />
                              </div>
                              <div className="min-w-0 flex-1 text-left">
                                <div className="text-xs text-slate-200 truncate mb-0.5" title={c.card_name}>
                                  {c.card_name}
                                </div>
                                <div className="text-xs font-semibold text-indigo-300 tabular-nums">
                                  {formatRos(top.ros)}
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

      {/* Category Info Modal */}
      {infoCategory && (
        <ModalBackdrop onClose={() => setInfoCategory(null)}>
          <div className="bg-slate-900 border border-slate-700 rounded-lg shadow-xl w-full max-w-md p-5">
            <div className="flex items-start justify-between gap-3 mb-4">
              <div>
                <h3 className="text-lg font-semibold text-white">{infoCategory.name}</h3>
                {infoCategory.description && (
                  <p className="text-sm text-slate-400 mt-1">{infoCategory.description}</p>
                )}
              </div>
              <button
                type="button"
                onClick={() => setInfoCategory(null)}
                className="shrink-0 p-1 rounded text-slate-500 hover:text-slate-300 hover:bg-slate-800"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="18" y1="6" x2="6" y2="18" />
                  <line x1="6" y1="6" x2="18" y2="18" />
                </svg>
              </button>
            </div>

            <div className="border-t border-slate-700 pt-4">
              <h4 className="text-sm font-medium text-slate-300 mb-3">Includes spend on:</h4>
              <ul className="space-y-2">
                {infoCategory.mappings
                  .sort((a, b) => b.default_weight - a.default_weight)
                  .map((mapping) => (
                    <li key={mapping.id} className="flex items-center justify-between text-sm">
                      <span className="text-slate-200">{mapping.earn_category.category}</span>
                      <span className="text-slate-500 tabular-nums">
                        {Math.round(mapping.default_weight * 100)}%
                      </span>
                    </li>
                  ))}
              </ul>
            </div>
          </div>
        </ModalBackdrop>
      )}
    </div>
  )
}
