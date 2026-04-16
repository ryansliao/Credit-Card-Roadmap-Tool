import { useMemo, useState } from 'react'
import type { CardResult, SpendCategory, WalletCard } from '../../../../api/client'
import { formatMoneyExact, formatPointsExact } from '../../../../utils/format'
import { useAppSpendCategories } from '../../hooks/useAppSpendCategories'
import { useWalletSpendCategoriesTable } from '../../hooks/useWalletSpendCategoriesTable'

interface Props {
  walletId: number | null
  selectedCards: CardResult[]
  walletCards: WalletCard[]
  isTotal: boolean
  totalYears: number
  onSpendChange: () => void
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
      src={`/photos/${slug}.png`}
      alt={name}
      title={name}
      className="w-full h-full object-contain"
      onError={() => setFailed(true)}
    />
  )
}

function InlineCategoryDropdown({
  existingCategoryIds,
  onSelect,
}: {
  existingCategoryIds: Set<number>
  onSelect: (category: SpendCategory) => void
}) {
  const [search, setSearch] = useState('')
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const { data: categories = [], isLoading } = useAppSpendCategories()

  const visible = categories.filter((c) => !c.is_system)
  const searchLower = search.toLowerCase()
  const filtered = search
    ? visible.filter(
        (c) =>
          c.category.toLowerCase().includes(searchLower) ||
          c.children.some((ch) => ch.category.toLowerCase().includes(searchLower))
      )
    : visible

  return (
    <div className="border-t border-slate-700 mt-2 pt-2">
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search categories…"
        autoFocus
        className="w-full bg-slate-800 border border-slate-600 text-white text-xs px-2.5 py-1.5 rounded-lg outline-none focus:border-indigo-500 mb-1"
      />
      <div className="max-h-48 overflow-y-auto">
        {isLoading && <p className="text-slate-500 text-xs px-2 py-1">Loading…</p>}
        {!isLoading && filtered.length === 0 && (
          <p className="text-slate-500 text-xs px-2 py-1">No categories match.</p>
        )}
        {filtered.map((cat) => {
          const alreadyAdded = existingCategoryIds.has(cat.id)
          const hasChildren = cat.children.length > 0
          const isExpanded = expandedIds.has(cat.id)
          return (
            <div key={cat.id}>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => !alreadyAdded && onSelect(cat)}
                  disabled={alreadyAdded}
                  className={`flex-1 text-left px-2 py-1 text-xs rounded transition-colors ${
                    alreadyAdded
                      ? 'text-slate-600 cursor-default'
                      : 'text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  {cat.category}
                </button>
                {hasChildren && (
                  <button
                    onClick={() =>
                      setExpandedIds((prev) => {
                        const next = new Set(prev)
                        if (next.has(cat.id)) next.delete(cat.id)
                        else next.add(cat.id)
                        return next
                      })
                    }
                    className="px-1 py-1 text-slate-500 hover:text-slate-300"
                  >
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className={`transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                    >
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </button>
                )}
              </div>
              {hasChildren && isExpanded && (
                <div className="ml-4 border-l border-slate-700">
                  {cat.children.map((child) => {
                    const childAdded = existingCategoryIds.has(child.id)
                    return (
                      <button
                        key={child.id}
                        onClick={() => !childAdded && onSelect(child)}
                        disabled={childAdded}
                        className={`block w-full text-left px-2 py-1 text-xs rounded transition-colors ${
                          childAdded
                            ? 'text-slate-600 cursor-default'
                            : 'text-slate-300 hover:bg-slate-800'
                        }`}
                      >
                        {child.category}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}

export function SpendTabContent({
  walletId,
  selectedCards,
  walletCards,
  isTotal,
  totalYears,
  onSpendChange,
}: Props) {
  const {
    spendItems,
    isLoading,
    editingAmountId,
    amountDraft,
    setAmountDraft,
    startEditAmount,
    commitAmount,
    cancelEditAmount,
    showPicker,
    closePicker,
    openPicker,
    handlePickCategory,
    mutationError,
    deleteMutationIsPending,
    requestDeleteItem,
  } = useWalletSpendCategoriesTable(walletId, onSpendChange)

  const existingCategoryIds = new Set(spendItems.map((i) => i.spend_category_id))

  // View mode toggle: per-card (cycle through cards, show earn) vs
  // top-ros (highest return-on-spend card in each category).
  const [viewMode, setViewMode] = useState<'per-card' | 'top-ros'>('top-ros')
  const [includeClosed, setIncludeClosed] = useState(false)

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
    () =>
      includeClosed
        ? selectedCards
        : selectedCards.filter((c) => !excludedCardIds.has(c.card_id)),
    [includeClosed, selectedCards, excludedCardIds]
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

  // Build a category × card lookup of points (in raw effective-currency units, per-year).
  // The backend returns category_earn keyed by spend-category name; we match by name.
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

  function formatCardEarn(card: CardResult, points: number): string {
    const cardYears = card.card_active_years || totalYears
    const adjusted = isTotal ? points * totalYears : points * totalYears / cardYears
    if ((card.effective_reward_kind ?? 'points') === 'cash') {
      return formatMoneyExact((adjusted * card.cents_per_point) / 100)
    }
    return formatPointsExact(adjusted)
  }

  return (
    <div className="flex flex-col flex-1 min-h-0 min-w-0 pt-3">
      <div className="shrink-0 flex items-center justify-between gap-3 mb-2">
        <div className="inline-flex rounded-lg border border-slate-700 overflow-hidden text-xs">
          <button
            type="button"
            onClick={() => setViewMode('top-ros')}
            className={`px-2.5 py-1 transition-colors ${
              viewMode === 'top-ros'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            Top ROS
          </button>
          <button
            type="button"
            onClick={() => setViewMode('per-card')}
            className={`px-2.5 py-1 border-l border-slate-700 transition-colors ${
              viewMode === 'per-card'
                ? 'bg-indigo-600 text-white'
                : 'bg-slate-900 text-slate-400 hover:text-slate-200 hover:bg-slate-800'
            }`}
          >
            Per-Card Earn
          </button>
        </div>
        {viewMode === 'top-ros' && (
          <label className="inline-flex items-center gap-2 text-xs text-slate-400 cursor-pointer select-none">
            <span>Include Closed Cards</span>
            <button
              type="button"
              role="switch"
              aria-checked={includeClosed}
              onClick={() => setIncludeClosed((v) => !v)}
              className={`relative inline-flex h-4 w-7 shrink-0 items-center rounded-full transition-colors ${
                includeClosed ? 'bg-indigo-600' : 'bg-slate-700'
              }`}
            >
              <span
                className={`inline-block h-3 w-3 transform rounded-full bg-white transition-transform ${
                  includeClosed ? 'translate-x-3.5' : 'translate-x-0.5'
                }`}
              />
            </button>
          </label>
        )}
      </div>
      {isLoading ? (
        <div className="text-slate-500 text-sm">Loading…</div>
      ) : (
        <div className="flex-1 min-h-0 overflow-auto rounded-lg border border-slate-800">
          <table className="w-full text-sm border-collapse table-fixed">
            <colgroup>
              <col />
              <col className="w-30" />
              <col className={viewMode === 'top-ros' ? 'w-36' : 'w-56'} />
              {viewMode === 'top-ros' && <col className="w-20" />}
            </colgroup>
            <thead className="sticky top-0 bg-slate-900 z-10">
              <tr>
                <th className="text-left text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-r border-slate-800">
                  Category
                </th>
                <th className="text-center text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-r border-slate-800 whitespace-nowrap">
                  Annual Spend
                </th>
                <th className="text-center text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-slate-800">
                  {viewMode === 'per-card' ? (
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
                      <div className="flex-1 min-w-0 flex items-center justify-center">
                        <div className="w-[72px] h-11 shrink-0 rounded overflow-hidden bg-slate-700/50">
                          <CardPhoto
                            slug={currentCard?.photo_slug ?? null}
                            name={currentCard?.card_name ?? 'Card'}
                          />
                        </div>
                      </div>
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
                  ) : (
                    <span>Top ROS Card</span>
                  )}
                </th>
                {viewMode === 'top-ros' && (
                  <th className="text-center text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-l border-slate-800 whitespace-nowrap">
                    ROS
                  </th>
                )}
              </tr>
            </thead>
            <tbody>
              {spendItems.map((item) => {
                const isEditing = editingAmountId === item.id
                const catName = item.spend_category.category
                const isSystem = item.spend_category.is_system
                const earnRow = earnByCategoryByCard.get(catName)
                return (
                  <tr key={item.id} className="border-b border-slate-800/60">
                    <td className="text-left px-3 py-2 text-slate-200 border-r border-slate-800/60">
                      <div className="flex items-center gap-2 min-w-0">
                        <span className="flex-1 min-w-0 truncate" title={catName}>
                          {catName}
                        </span>
                        {!isSystem && (
                          <button
                            onClick={() => requestDeleteItem(item)}
                            disabled={deleteMutationIsPending}
                            className="p-1 rounded text-slate-700 hover:text-red-400 hover:bg-red-950/40 disabled:opacity-50 shrink-0"
                            aria-label="Delete spend category"
                            title="Delete"
                          >
                            <svg
                              width="13"
                              height="13"
                              viewBox="0 0 24 24"
                              fill="none"
                              stroke="currentColor"
                              strokeWidth="2"
                              strokeLinecap="round"
                              strokeLinejoin="round"
                            >
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        )}
                      </div>
                    </td>
                    <td className="text-center px-2 py-2 tabular-nums border-r border-slate-800/60">
                      <div className="relative w-full">
                        <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-xs text-slate-500 pointer-events-none">
                          $
                        </span>
                        <input
                          type="number"
                          min={0}
                          step="1"
                          value={
                            isEditing
                              ? amountDraft
                              : item.amount === 0
                                ? ''
                                : Math.round(item.amount)
                          }
                          placeholder="0"
                          onFocus={() => startEditAmount(item)}
                          onChange={(e) => setAmountDraft(e.target.value)}
                          onBlur={() => commitAmount(item)}
                          onKeyDown={(e) => {
                            if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur()
                            if (e.key === 'Escape') {
                              cancelEditAmount()
                              ;(e.currentTarget as HTMLInputElement).blur()
                            }
                          }}
                          className="w-full min-w-0 bg-slate-700 border border-slate-600 text-white text-sm tabular-nums text-right pl-4 pr-1.5 py-0.5 rounded outline-none focus:border-indigo-500 placeholder:text-slate-500"
                        />
                      </div>
                    </td>
                    {viewMode === 'per-card' ? (
                      <td className="text-center tabular-nums px-3 py-2 text-slate-200">
                        {currentCard ? (
                          (() => {
                            const pts = earnRow?.get(currentCard.card_id) ?? 0
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
                    ) : (
                      (() => {
                        const top = topCardsForCategory(catName)
                        const noTop = top.cards.length === 0 || top.ros <= 0
                        return (
                          <>
                            <td className="text-center px-3 py-2 text-slate-200">
                              {noTop ? (
                                <span className="text-slate-700">—</span>
                              ) : (
                                <div className="flex flex-wrap items-center justify-center gap-1.5">
                                  {top.cards.map((c) => (
                                    <div
                                      key={c.card_id}
                                      className="w-[72px] h-11 shrink-0 rounded overflow-hidden bg-slate-700/50"
                                    >
                                      <CardPhoto slug={c.photo_slug} name={c.card_name} />
                                    </div>
                                  ))}
                                </div>
                              )}
                            </td>
                            <td className="text-center tabular-nums px-3 py-2 border-l border-slate-800/60">
                              {noTop ? (
                                <span className="text-slate-700">—</span>
                              ) : (
                                <span className="font-semibold text-indigo-300">
                                  {formatRos(top.ros)}
                                </span>
                              )}
                            </td>
                          </>
                        )
                      })()
                    )}
                  </tr>
                )
              })}
              {spendItems.length === 0 && (
                <tr>
                  <td
                    colSpan={viewMode === 'top-ros' ? 4 : 3}
                    className="text-center text-slate-500 text-sm py-5"
                  >
                    No spend categories yet. Add one to configure your annual spend.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      )}

      {mutationError && (
        <p className="text-red-400 text-xs mt-2 shrink-0" role="alert">
          {mutationError}
        </p>
      )}

      {walletId != null && !showPicker && (
        <button
          type="button"
          onClick={openPicker}
          className="shrink-0 mt-2 w-full text-sm text-slate-500 hover:text-indigo-400 hover:bg-slate-800 rounded-lg py-2 transition-colors"
        >
          + Add Spend Category
        </button>
      )}

      {showPicker && (
        <div className="shrink-0">
          <InlineCategoryDropdown
            existingCategoryIds={existingCategoryIds}
            onSelect={(cat) => handlePickCategory(cat)}
          />
          <button
            onClick={closePicker}
            className="mt-1 w-full text-xs text-slate-500 hover:text-slate-300 py-1"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}
