import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  type AddCardToWalletPayload,
  type CardCredit,
  type UpdateWalletCardPayload,
  type WalletCard,
  type WalletCardAcquisitionType,
  creditsApi,
  currenciesApi,
  walletCardCategoryPriorityApi,
  walletCardCreditApi,
  walletSpendItemsApi,
} from '../../api/client'
import { ModalBackdrop } from '../ModalBackdrop'
import { formatMoney, today } from '../../utils/format'
import { useCardLibrary } from '../../pages/RoadmapTool/hooks/useCardLibrary'
import { useCreditLibrary } from '../../hooks/useCreditLibrary'
import { buildWalletCardFields, walletFormToUpdatePayload } from '../../pages/RoadmapTool/lib/walletCardForm'
import { queryKeys } from '../../lib/queryKeys'

// ---------------------------------------------------------------------------
// Main modal
// ---------------------------------------------------------------------------

export function WalletCardModal({
  mode,
  walletId,
  walletCard,
  existingCardIds,
  walletCardIds,
  onClose,
  onAdd,
  onSaveEdit,
  onRemove,
  isLoading,
}: {
  mode: 'add' | 'edit'
  walletId: number
  walletCard?: WalletCard
  existingCardIds: number[]
  /** Card IDs currently in the wallet (used to derive wallet currency set). */
  walletCardIds: number[]
  onClose: () => void
  onAdd: (payload: AddCardToWalletPayload) => void
  onSaveEdit: (payload: UpdateWalletCardPayload) => void
  /** Edit mode only: triggers the wallet card removal flow. */
  onRemove?: (walletCard: WalletCard) => void
  isLoading: boolean
}) {
  const { data: cards } = useCardLibrary()
  const queryClient = useQueryClient()

  // Currency IDs present in the wallet (from existing wallet cards + the card being added/edited)
  const walletCurrencyIds = useMemo(() => {
    if (!cards) return new Set<number>()
    const ids = new Set<number>()
    for (const wcId of walletCardIds) {
      const c = cards.find((card) => card.id === wcId)
      if (c) ids.add(c.currency_id)
    }
    return ids
  }, [cards, walletCardIds])

  const [cardId, setCardId] = useState<number | ''>('')
  const [cardSearch, setCardSearch] = useState('')
  const [cardDropdownOpen, setCardDropdownOpen] = useState(false)
  const cardSearchRef = useRef<HTMLDivElement>(null)
  const [pcFromCardId, setPcFromCardId] = useState<number | ''>('')

  const [addedDate, setAddedDate] = useState(
    () => (mode === 'edit' && walletCard ? walletCard.added_date : today())
  )
  const [acquisitionType, setAcquisitionType] = useState<WalletCardAcquisitionType>(
    mode === 'edit' && walletCard ? walletCard.acquisition_type : 'opened'
  )
  // Empty string = card is active. A YYYY-MM-DD string = card is closed on that date.
  const [closedDate, setClosedDate] = useState<string>(
    () => (mode === 'edit' && walletCard ? walletCard.closed_date ?? '' : '')
  )
  const [subPoints, setSubPoints] = useState('')
  const [subMinSpend, setSubMinSpend] = useState('')
  const [subMonths, setSubMonths] = useState('')
  const [annualBonus, setAnnualBonus] = useState('')
  const [annualFee, setAnnualFee] = useState('')
  const [firstYearFee, setFirstYearFee] = useState('')
  const [secondaryCurrencyRate, setSecondaryCurrencyRate] = useState('')
  // Selected statement credits for this wallet card: library_credit_id -> value.
  // The presence of a key means the credit is attached to this wallet card.
  const [selectedCredits, setSelectedCredits] = useState<Record<number, number>>({})
  const [creditSearch, setCreditSearch] = useState('')
  const [creditOptionsOpen, setCreditOptionsOpen] = useState<number | null>(null)
  const [showCreditPicker, setShowCreditPicker] = useState(false)
  // Set of spend_category_ids this wallet card claims as priority-pinned.
  const [priorityCategoryIds, setPriorityCategoryIds] = useState<Set<number>>(new Set())
  const [formError, setFormError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<
    'lifecycle' | 'bonuses' | 'credits' | 'priority'
  >('lifecycle')

  // Tracks the last key we hydrated form state from, preventing re-runs when the
  // card library re-fetches without the user changing their selection.
  // Format: "add:<cardId>" | "edit:<walletCardId>"
  const hydratedKey = useRef<string>('')

  const effectiveCardId =
    mode === 'add' ? (typeof cardId === 'number' ? cardId : null) : (walletCard?.card_id ?? null)

  // Global standardized credit library (Priority Pass, Global Entry, etc.).
  // Cached indefinitely; prefetched at the RoadmapTool root so opening the
  // modal does not block on a network round-trip.
  const { data: creditLibrary, isLoading: creditLibraryLoading } = useCreditLibrary()
  const creditLibraryById = useMemo(() => {
    const m = new Map<number, CardCredit>()
    for (const c of creditLibrary ?? []) m.set(c.id, c)
    return m
  }, [creditLibrary])
  const { data: currencies } = useQuery({
    queryKey: queryKeys.currencies(),
    queryFn: () => currenciesApi.list(),
    staleTime: Infinity,
  })

  const createCreditMutation = useMutation({
    mutationFn: (credit_name: string) => creditsApi.create({ credit_name, value: 0 }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credits() })
      setSelectedCredits((prev) => ({ ...prev, [created.id]: created.value ?? 0 }))
      setCreditSearch('')
    },
    onError: (e: Error) => setFormError(e.message),
  })

  // Existing wallet-card credit selections (edit mode only)
  const { data: existingCreditOverrides, isLoading: creditOverridesLoading } = useQuery({
    queryKey: queryKeys.walletCardCredits(walletCard?.wallet_id ?? null, walletCard?.card_id ?? null),
    queryFn: () => walletCardCreditApi.list(walletCard!.wallet_id, walletCard!.card_id),
    enabled: mode === 'edit' && walletCard != null,
  })

  // All spend items in the wallet — the category list shown in the priority picker.
  const { data: walletSpendItems } = useQuery({
    queryKey: queryKeys.walletSpendItems(walletId),
    queryFn: () => walletSpendItemsApi.list(walletId),
  })

  // Wallet-wide category priority pins (used to gray out categories claimed by OTHER cards).
  const { data: walletCategoryPriorities } = useQuery({
    queryKey: queryKeys.walletCategoryPriorities(walletId),
    queryFn: () => walletCardCategoryPriorityApi.list(walletId),
  })

  // Map spend_category_id -> the wallet_card_id that currently claims it.
  // Used to render grayed-out "Claimed by another card" state for picks other
  // wallet cards already own.
  const priorityClaimsByOther = useMemo(() => {
    const m = new Map<number, number>()
    if (!walletCategoryPriorities) return m
    const currentWalletCardId = walletCard?.id ?? -1
    for (const p of walletCategoryPriorities) {
      if (p.wallet_card_id !== currentWalletCardId) {
        m.set(p.spend_category_id, p.wallet_card_id)
      }
    }
    return m
  }, [walletCategoryPriorities, walletCard?.id])

  // Count of user-facing spend categories fully pinned to this card (for Priority tab badge).
  const priorityUserCatCount = useMemo(() => {
    if (!walletSpendItems || priorityCategoryIds.size === 0) return 0
    return walletSpendItems.filter((item) => {
      const userCat = item.user_spend_category
      if (!userCat) return false
      const earnCatIds = userCat.mappings.map((m) => m.earn_category_id)
      return earnCatIds.length > 0 && earnCatIds.every((id) => priorityCategoryIds.has(id))
    }).length
  }, [walletSpendItems, priorityCategoryIds])

  // Cards already in the wallet — shown in the "changing from" picker
  const walletCards = useMemo(() => {
    if (!cards) return []
    return [...cards]
      .filter((c) => existingCardIds.includes(c.id))
      .sort((a, b) => a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }))
  }, [cards, existingCardIds])

  // "Changing to" candidates: same issuer as the selected from-card, not already in wallet
  const issuerFilteredCards = useMemo(() => {
    if (!cards) return []
    if (acquisitionType !== 'product_change') return cards
    if (!pcFromCardId) return []
    const fromCard = cards.find((c) => c.id === pcFromCardId)
    if (!fromCard) return []
    return cards.filter((c) => c.issuer_id === fromCard.issuer_id && !existingCardIds.includes(c.id))
  }, [cards, acquisitionType, pcFromCardId, existingCardIds])

  const searchedCards = useMemo(() => {
    const q = cardSearch.trim().toLowerCase()
    const filtered = !q
      ? issuerFilteredCards
      : issuerFilteredCards.filter((c) => c.name.toLowerCase().includes(q))
    return [...filtered].sort((a, b) =>
      a.name.localeCompare(b.name, undefined, { sensitivity: 'base' }),
    )
  }, [issuerFilteredCards, cardSearch])

  const lib = useMemo(
    () =>
      effectiveCardId != null && cards ? cards.find((c) => c.id === effectiveCardId) : undefined,
    [effectiveCardId, cards]
  )




  // Close card dropdown when clicking outside
  useEffect(() => {
    function onPointerDown(e: PointerEvent) {
      if (cardSearchRef.current && !cardSearchRef.current.contains(e.target as Node)) {
        setCardDropdownOpen(false)
      }
    }
    document.addEventListener('pointerdown', onPointerDown)
    return () => document.removeEventListener('pointerdown', onPointerDown)
  }, [])

  useEffect(() => {
    if (mode === 'add') {
      if (!cardId) {
        hydratedKey.current = ''
        return
      }
      if (!lib) return
      // Wait for the credit library before hydrating so we can pre-populate
      // the card's default statement credits in the same pass.
      if (!creditLibrary) return
      const key = `add:${cardId}`
      if (hydratedKey.current === key) return
      hydratedKey.current = key
      // One-shot hydration gated by hydratedKey.current — not a render loop.
      // eslint-disable-next-line react-hooks/set-state-in-effect
      setSubPoints(lib.sub_points != null ? String(lib.sub_points) : '')
      setSubMinSpend(lib.sub_min_spend != null ? String(lib.sub_min_spend) : '')
      setSubMonths(lib.sub_months != null ? String(lib.sub_months) : '')
      setAnnualBonus(lib.annual_bonus != null ? String(lib.annual_bonus) : '')
      setAnnualFee(String(lib.annual_fee))
      setFirstYearFee(lib.first_year_fee != null ? String(lib.first_year_fee) : '')
      setSecondaryCurrencyRate(lib.secondary_currency_rate != null ? String(lib.secondary_currency_rate) : '')
      // Auto-attach the default statement credits this card natively offers,
      // based on the global card_credits link table.
      const defaults: Record<number, number> = {}
      for (const c of creditLibrary) {
        if (c.card_ids.includes(cardId)) {
          defaults[c.id] = c.card_values[cardId] ?? c.value ?? 0
        }
      }
      setSelectedCredits(defaults)
      setFormError(null)
    } else {
      if (!walletCard || !lib) return
      // Wait for credit overrides before hydrating so we populate credits in
      // the same pass and never flash "0 credits".
      if (existingCreditOverrides === undefined) return
      const key = `edit:${walletCard.id}`
      if (hydratedKey.current === key) return
      hydratedKey.current = key
      setAddedDate(walletCard.added_date)
      setAcquisitionType(walletCard.acquisition_type)
      setClosedDate(walletCard.closed_date ?? '')
      const effSub = walletCard.sub_points ?? lib.sub_points
      setSubPoints(effSub != null ? String(effSub) : '')
      const effMin = walletCard.sub_min_spend ?? lib.sub_min_spend
      setSubMinSpend(effMin != null ? String(effMin) : '')
      const effMo = walletCard.sub_months ?? lib.sub_months
      setSubMonths(effMo != null ? String(effMo) : '')
      const effBonus = walletCard.annual_bonus ?? lib.annual_bonus
      setAnnualBonus(effBonus != null ? String(effBonus) : '')
      const effAf = walletCard.annual_fee ?? lib.annual_fee
      setAnnualFee(String(effAf))
      const effFy = walletCard.first_year_fee ?? lib.first_year_fee
      setFirstYearFee(effFy != null ? String(effFy) : '')
      const effSecRate = walletCard.secondary_currency_rate ?? lib.secondary_currency_rate
      setSecondaryCurrencyRate(effSecRate != null ? String(effSecRate) : '')
      const m: Record<number, number> = {}
      for (const o of existingCreditOverrides) {
        m[o.library_credit_id] = o.value
      }
      setSelectedCredits(m)
      setFormError(null)
    }
  }, [mode, cardId, lib, walletCard, creditLibrary, existingCreditOverrides])

  // Hydrate this card's own priority pins from the wallet-wide list.
  useEffect(() => {
    if (walletCategoryPriorities === undefined) return
    const currentWalletCardId = walletCard?.id ?? -1
    const mine = new Set<number>()
    for (const p of walletCategoryPriorities) {
      if (p.wallet_card_id === currentWalletCardId) {
        mine.add(p.spend_category_id)
      }
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPriorityCategoryIds(mine)
  }, [walletCategoryPriorities, walletCard?.id])

  function selectPcFromCard(id: number) {
    setPcFromCardId(id)
    // Reset "to" selection whenever "from" changes
    setCardId('')
    setCardSearch('')
  }

  function selectCard(id: number, name: string) {
    setCardId(id)
    setCardSearch(name)
    setCardDropdownOpen(false)
  }

  function handleCardSearchChange(value: string) {
    setCardSearch(value)
    setCardId('')
    setCardDropdownOpen(true)
  }

  async function handlePrimary() {
    setFormError(null)
    const built = buildWalletCardFields(
      subPoints,
      subMinSpend,
      subMonths,
      annualBonus,
      annualFee,
      firstYearFee
    )
    if (!built.ok) {
      setFormError(built.message)
      return
    }
    if (closedDate && closedDate < addedDate) {
      setFormError('Closed date must be on or after the opening date.')
      return
    }

    if (mode === 'add') {
      if (typeof cardId !== 'number') return
      onAdd({
        card_id: cardId,
        added_date: addedDate,
        acquisition_type: acquisitionType,
        sub_points: built.sub_points,
        sub_min_spend: built.sub_min_spend,
        sub_months: built.sub_months,
        annual_bonus: built.annual_bonus,
        annual_fee: built.annual_fee,
        first_year_fee: built.first_year_fee,
        secondary_currency_rate: secondaryCurrencyRate.trim() ? Number(secondaryCurrencyRate) : null,
        credits: Object.entries(selectedCredits).map(([id, value]) => ({
          library_credit_id: Number(id),
          value,
        })),
        pc_from_card_id: acquisitionType === 'product_change' && typeof pcFromCardId === 'number' ? pcFromCardId : undefined,
      })
      return
    }

    if (!walletCard || !lib) {
      setFormError('Card library data is still loading.')
      return
    }

    // Reconcile selected credits against the existing wallet rows: upsert any
    // newly-added or value-changed credits, delete any that were removed.
    const creditOps: Promise<unknown>[] = []
    const existingByLibId = new Map(
      (existingCreditOverrides ?? []).map((o) => [o.library_credit_id, o]),
    )
    for (const [idStr, value] of Object.entries(selectedCredits)) {
      const libId = Number(idStr)
      const existing = existingByLibId.get(libId)
      if (!existing || Math.abs(existing.value - value) > 1e-6) {
        creditOps.push(
          walletCardCreditApi.upsert(walletCard.wallet_id, walletCard.card_id, libId, { value }),
        )
      }
    }
    for (const [libId] of existingByLibId) {
      if (!(libId in selectedCredits)) {
        creditOps.push(
          walletCardCreditApi.delete(walletCard.wallet_id, walletCard.card_id, libId),
        )
      }
    }

    // Save category-priority pins via the dedicated API.
    const priorityOp = walletCardCategoryPriorityApi
      .set(walletCard.wallet_id, walletCard.card_id, Array.from(priorityCategoryIds))
      .catch((e: Error) => {
        throw new Error(e.message || 'Failed to save category priorities.')
      })

    try {
      await Promise.all([...creditOps, priorityOp])
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to save overrides.'
      setFormError(msg)
      return
    }

    queryClient.invalidateQueries({
      queryKey: queryKeys.walletCardCredits(walletCard.wallet_id, walletCard.card_id),
    })
    queryClient.invalidateQueries({
      queryKey: queryKeys.walletCategoryPriorities(walletCard.wallet_id),
    })
    const secRate = secondaryCurrencyRate.trim() ? Number(secondaryCurrencyRate) : null
    onSaveEdit(
      walletFormToUpdatePayload(built, lib, addedDate, acquisitionType, secRate, closedDate || null),
    )
  }

  const formDisabled = !lib
  const title =
    mode === 'add'
      ? 'Add Card to Wallet'
      : `${walletCard?.card_name ?? `Card #${walletCard?.card_id ?? ''}`}`

  // Linear tab order: Next advances through these; the header Save icon submits.
  const tabOrder: readonly typeof activeTab[] =
    mode === 'add'
      ? ['lifecycle', 'bonuses', 'credits']
      : ['lifecycle', 'bonuses', 'credits', 'priority']
  const currentTabIndex = tabOrder.indexOf(activeTab)
  const hasNextTab = currentTabIndex !== -1 && currentTabIndex < tabOrder.length - 1

  const saveDisabled =
    mode === 'add'
      ? (acquisitionType === 'product_change' ? (!pcFromCardId || !cardId || isLoading) : (!cardId || isLoading))
      : isLoading || !walletCard

  return (
    <>
      <ModalBackdrop
        onClose={onClose}
        className="bg-slate-800 border border-slate-600 rounded-xl w-full max-w-lg shadow-xl flex flex-col h-[640px] max-h-[90vh]"
      >
        {/* ── Fixed header ── */}
        <div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-slate-700">
          <div className="flex items-center gap-2 flex-wrap">
            <h2 className="text-lg font-semibold text-white">{title}</h2>
            {lib?.network_tier && (
              <span className="text-[10px] font-medium bg-slate-700 text-slate-400 border border-slate-600 rounded px-1.5 py-0.5">
                {lib.network_tier.name}
              </span>
            )}
            <div className="ml-auto flex items-center gap-2">
              {mode === 'edit' && walletCard && onRemove && (
                <button
                  type="button"
                  disabled={isLoading}
                  onClick={() => onRemove(walletCard)}
                  className="p-2 rounded-lg text-slate-500 hover:text-red-400 hover:bg-red-950/40 disabled:opacity-50 transition-colors"
                  title="Delete card"
                  aria-label="Delete card"
                >
                  <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <polyline points="3 6 5 6 21 6" />
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                  </svg>
                </button>
              )}
              <button
                type="button"
                disabled={saveDisabled}
                onClick={() => void handlePrimary()}
                className="p-2 rounded-lg text-slate-400 hover:text-indigo-300 hover:bg-indigo-950/40 disabled:opacity-40 disabled:hover:text-slate-400 disabled:hover:bg-transparent transition-colors"
                title={mode === 'add' ? 'Add card' : 'Save changes'}
                aria-label={mode === 'add' ? 'Add card' : 'Save changes'}
              >
                <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z" />
                  <polyline points="17 21 17 13 7 13 7 21" />
                  <polyline points="7 3 7 8 15 8" />
                </svg>
              </button>
            </div>
          </div>
        </div>

        {/* ── Tab bar ── */}
        {(mode === 'add' || lib) && (
          <div className="flex-shrink-0 flex gap-1 px-6 border-b border-slate-700">
            {([
              { id: 'lifecycle' as const, label: 'Lifecycle', badge: 0 },
              { id: 'bonuses' as const, label: 'Bonuses & Fees', badge: 0 },
              {
                id: 'credits' as const,
                label: 'Credits',
                badge: Object.keys(selectedCredits).length,
              },
              ...(mode === 'edit'
                ? [{ id: 'priority' as const, label: 'Categories', badge: priorityUserCatCount }]
                : []),
            ]).map((t) => (
              <button
                key={t.id}
                type="button"
                onClick={() => setActiveTab(t.id)}
                className={`px-4 py-3 text-sm font-medium border-b-2 -mb-px transition-colors whitespace-nowrap ${
                  activeTab === t.id
                    ? 'border-indigo-500 text-indigo-300'
                    : 'border-transparent text-slate-400 hover:text-slate-200'
                }`}
              >
                {t.label}
                {(t.id === 'credits' || t.id === 'priority') && t.badge > 0 && (
                  <span className={`ml-1.5 ${activeTab === t.id ? 'text-indigo-400' : 'text-slate-500'}`}>
                    ({t.badge})
                  </span>
                )}
              </button>
            ))}
          </div>
        )}

        {/* ── Body ── */}
        <div
          className={`px-6 pt-3 flex-1 min-h-0 flex flex-col ${
            activeTab === 'credits' ? 'pb-0' : 'pb-4'
          }`}
        >
          {mode === 'edit' && !lib ? (
            <p className="text-sm text-slate-400 py-8 text-center">Loading card…</p>
          ) : (
            <div className="flex-1 min-h-0 flex flex-col">
              {activeTab === 'lifecycle' && (
              <div className="space-y-3">
              <p className="text-[11px] text-slate-500 -mx-6 px-6 pb-2 border-b border-slate-700/60">
                When and how this card entered the wallet, and whether it's still active.
              </p>
              {/* Acquisition type (left) | Opening date (right) */}
              <div className="grid grid-cols-2 gap-3 items-start">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Acquisition Type</label>
                  <div role="radiogroup" className="flex flex-col bg-slate-700/30 border border-slate-600 rounded-lg overflow-hidden">
                    {(['opened', 'product_change'] as const).map((v, i) => {
                      const selected = acquisitionType === v
                      return (
                        <button
                          key={v}
                          type="button"
                          role="radio"
                          aria-checked={selected}
                          onClick={() => setAcquisitionType(v)}
                          className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs transition-colors ${
                            i > 0 ? 'border-t border-slate-600/60' : ''
                          } ${
                            selected
                              ? 'bg-slate-700 text-white'
                              : 'text-slate-300 hover:bg-slate-700/60'
                          }`}
                        >
                          <span className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                            selected ? 'border-indigo-500' : 'border-slate-500'
                          }`}>
                            {selected && <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full" />}
                          </span>
                          {v === 'opened' ? 'Account Opening' : 'Product Change'}
                        </button>
                      )
                    })}
                  </div>
                </div>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">
                    {acquisitionType === 'product_change' ? 'Product Change Date *' : 'Opening Date *'}
                  </label>
                  <input
                    type="date"
                    className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
                    value={addedDate}
                    onChange={(e) => setAddedDate(e.target.value)}
                  />
                </div>
              </div>

              {/* Card pickers (add mode only) */}
              {mode === 'add' && (
                <>
                  {/* PC: "Changing from" — wallet cards only */}
                  {acquisitionType === 'product_change' && (
                    <div>
                      <label className="text-xs text-slate-400 mb-1 block">Changing From *</label>
                      <select
                        className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
                        value={pcFromCardId}
                        onChange={(e) => e.target.value ? selectPcFromCard(Number(e.target.value)) : setPcFromCardId('')}
                      >
                        <option value="">Select a wallet card…</option>
                        {walletCards.map((c) => (
                          <option key={c.id} value={c.id}>{c.name}</option>
                        ))}
                      </select>
                    </div>
                  )}

                  {/* "Changing to" / regular card search */}
                  <div ref={cardSearchRef} className="relative">
                    <label className="text-xs text-slate-400 mb-1 block">
                      {acquisitionType === 'product_change' ? 'Changing To *' : 'Card *'}
                    </label>
                    <input
                      type="text"
                      placeholder="Search cards…"
                      disabled={acquisitionType === 'product_change' && !pcFromCardId}
                      className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                      value={cardSearch}
                      onChange={(e) => handleCardSearchChange(e.target.value)}
                      onFocus={() => setCardDropdownOpen(true)}
                    />
                    {cardDropdownOpen && (
                      <ul className="absolute z-10 mt-1 w-full bg-slate-800 border border-slate-600 rounded-lg shadow-xl max-h-48 overflow-y-auto">
                        {searchedCards.length === 0 ? (
                          <li className="px-3 py-2 text-sm text-slate-500">No cards found</li>
                        ) : (
                          searchedCards.map((c) => (
                            <li
                              key={c.id}
                              onPointerDown={(e) => { e.preventDefault(); selectCard(c.id, c.name) }}
                              className={`px-3 py-2 text-sm cursor-pointer flex items-center gap-2 ${
                                cardId === c.id
                                  ? 'bg-indigo-600 text-white'
                                  : 'text-slate-200 hover:bg-slate-700'
                              }`}
                            >
                              <span className="flex-1 min-w-0 truncate">{c.name}</span>
                              {c.network_tier && (
                                <span className={`text-[10px] font-medium shrink-0 rounded px-1.5 py-0.5 border ${
                                  cardId === c.id
                                    ? 'bg-indigo-500/60 text-indigo-100 border-indigo-400/50'
                                    : 'bg-slate-700 text-slate-400 border-slate-600'
                                }`}>
                                  {c.network_tier.name}
                                </span>
                              )}
                            </li>
                          ))
                        )}
                      </ul>
                    )}
                    {acquisitionType === 'product_change' && pcFromCardId && (
                      <p className="text-[11px] text-slate-500 mt-1">Showing same-issuer cards</p>
                    )}
                  </div>
                </>
              )}

              {/* Card Status toggle + Closed Date (edit mode only).
                  Closed date empty = card is still active. */}
              {mode === 'edit' && (
                <div className="grid grid-cols-2 gap-3 items-start">
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Card Status</label>
                    <div role="radiogroup" className="flex flex-col bg-slate-700/30 border border-slate-600 rounded-lg overflow-hidden">
                      {([
                        { v: 'active' as const, label: 'Active' },
                        { v: 'closed' as const, label: 'Closed' },
                      ]).map(({ v, label }, i) => {
                        const isClosed = closedDate !== ''
                        const selected = v === 'active' ? !isClosed : isClosed
                        return (
                          <button
                            key={v}
                            type="button"
                            role="radio"
                            aria-checked={selected}
                            onClick={() => {
                              if (v === 'active') setClosedDate('')
                              else if (!closedDate) setClosedDate(today())
                            }}
                            className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs transition-colors ${
                              i > 0 ? 'border-t border-slate-600/60' : ''
                            } ${
                              selected
                                ? 'bg-slate-700 text-white'
                                : 'text-slate-300 hover:bg-slate-700/60'
                            }`}
                          >
                            <span className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                              selected ? 'border-indigo-500' : 'border-slate-500'
                            }`}>
                              {selected && <span className="w-1.5 h-1.5 bg-indigo-500 rounded-full" />}
                            </span>
                            {label}
                          </button>
                        )
                      })}
                    </div>
                  </div>
                  <div>
                    <label className="text-xs text-slate-400 mb-1 block">Closed Date</label>
                    <input
                      type="date"
                      min={addedDate}
                      disabled={!closedDate}
                      className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                      value={closedDate}
                      onChange={(e) => setClosedDate(e.target.value)}
                    />
                  </div>
                </div>
              )}
              </div>
              )}

              {activeTab === 'bonuses' && (
              <div className="space-y-3">
              <p className="text-[11px] text-slate-500 -mx-6 px-6 pb-2 border-b border-slate-700/60">
                Sign-up / product-change bonus, annual bonus, and fees.
              </p>
              {/* SUB Points | Annual Bonus */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">
                    {acquisitionType === 'product_change' ? 'PC Bonus (Pts)' : 'Sign-Up Bonus (Pts)'}
                  </label>
                  <input
                    type="number"
                    min={0}
                    disabled={formDisabled}
                    className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                    value={subPoints}
                    onChange={(e) => setSubPoints(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Annual Bonus (Pts)</label>
                  <input
                    type="number"
                    min={0}
                    disabled={formDisabled}
                    placeholder="Optional"
                    className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                    value={annualBonus}
                    onChange={(e) => setAnnualBonus(e.target.value)}
                  />
                </div>
              </div>

              {/* SUB Min Spend | SUB Months */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">
                    {acquisitionType === 'product_change' ? 'PC Min Spend ($)' : 'SUB Min Spend ($)'}
                  </label>
                  <input
                    type="number"
                    min={0}
                    disabled={formDisabled}
                    className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                    value={subMinSpend}
                    onChange={(e) => setSubMinSpend(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">
                    {acquisitionType === 'product_change' ? 'PC Spend Months' : 'SUB Spend Months'}
                  </label>
                  <input
                    type="number"
                    min={0}
                    disabled={formDisabled}
                    className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                    value={subMonths}
                    onChange={(e) => setSubMonths(e.target.value)}
                  />
                </div>
              </div>

              {/* Annual Fee | First-Year Fee */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Annual Fee ($)</label>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    disabled={formDisabled}
                    className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                    value={annualFee}
                    onChange={(e) => setAnnualFee(e.target.value)}
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">First-Year Fee ($)</label>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    disabled={formDisabled}
                    className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                    placeholder="Optional"
                    value={firstYearFee}
                    onChange={(e) => setFirstYearFee(e.target.value)}
                  />
                </div>
              </div>

              {/* Secondary currency rate override (only shown when the card has one) */}
              {lib && lib.secondary_currency_id != null && (
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">
                    {lib.secondary_currency_obj?.name ?? 'Secondary Currency'} Rate (%)
                  </label>
                  <input
                    type="number"
                    min={0}
                    max={100}
                    step="0.01"
                    disabled={formDisabled}
                    className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 disabled:opacity-50"
                    placeholder="e.g. 4 for 4%"
                    value={secondaryCurrencyRate ? String(Number(secondaryCurrencyRate) * 100) : ''}
                    onChange={(e) => {
                      const v = e.target.value.trim()
                      if (v === '') setSecondaryCurrencyRate('')
                      else setSecondaryCurrencyRate(String(Number(v) / 100))
                    }}
                  />
                </div>
              )}

              </div>
              )}

              {/* Statement Credits tab */}
              {activeTab === 'credits' && lib && (
                <div className="-mx-6 flex-1 min-h-0 flex flex-col">
                  <div className="flex-1 min-h-0 flex flex-col">
                    <p className="text-[11px] text-slate-500 px-6 pb-2 border-b border-slate-700/60">
                      Input your valuation of each credit.
                    </p>
                      {creditLibraryLoading || creditOverridesLoading ? (
                        <div className="flex items-center gap-2 px-6 py-3 text-xs text-slate-400">
                          <svg
                            className="w-3.5 h-3.5 animate-spin text-indigo-400"
                            fill="none"
                            viewBox="0 0 24 24"
                          >
                            <circle
                              className="opacity-25"
                              cx="12"
                              cy="12"
                              r="10"
                              stroke="currentColor"
                              strokeWidth="4"
                            />
                            <path
                              className="opacity-75"
                              fill="currentColor"
                              d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"
                            />
                          </svg>
                          Loading credits…
                        </div>
                      ) : Object.keys(selectedCredits).length === 0 ? (
                        <p className="text-xs text-slate-500 px-6 py-3">
                          No credits selected. Add credits this card grants from the picker below.
                        </p>
                      ) : (
                        <ul className="divide-y divide-slate-700/40 flex-1 min-h-0 overflow-y-auto">
                          {Object.entries(selectedCredits).map(([idStr, value]) => {
                            const libId = Number(idStr)
                            const lc = creditLibraryById.get(libId)
                            const isExpanded = creditOptionsOpen === libId
                            return (
                              <li key={libId}>
                                <div className="flex items-center justify-between gap-2 px-6 py-2 text-sm">
                                  {/* Expand arrow */}
                                  <button
                                    type="button"
                                    onClick={() => setCreditOptionsOpen(isExpanded ? null : libId)}
                                    className="text-slate-500 hover:text-slate-300 shrink-0"
                                  >
                                    <svg
                                      className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                                      fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
                                    >
                                      <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                    </svg>
                                  </button>
                                  <span className="text-slate-200 truncate min-w-0 flex-1">
                                    {lc?.credit_name ?? `Credit #${libId}`}
                                  </span>
                                  <div className="flex items-center gap-1.5 shrink-0">
                                    <div className="relative">
                                      {(() => {
                                        const cur = lc?.credit_currency_id != null ? currencies?.find(c => c.id === lc.credit_currency_id) : null
                                        const isCash = !cur || cur.reward_kind === 'cash'
                                        return isCash ? (
                                          <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-slate-500 pointer-events-none">$</span>
                                        ) : null
                                      })()}
                                      <input
                                        type="number"
                                        min={0}
                                        step={(() => {
                                          const cur = lc?.credit_currency_id != null ? currencies?.find(c => c.id === lc.credit_currency_id) : null
                                          return (!cur || cur.reward_kind === 'cash') ? '0.01' : '1'
                                        })()}
                                        value={value === 0 ? '' : value}
                                        placeholder="0"
                                        onChange={(e) => {
                                          const raw = e.target.value
                                          const parsed = raw === '' ? 0 : Number.parseFloat(raw)
                                          if (Number.isNaN(parsed) || parsed < 0) return
                                          setSelectedCredits((prev) => ({
                                            ...prev,
                                            [libId]: parsed,
                                          }))
                                        }}
                                        className={`w-24 bg-slate-700 border border-slate-600 text-white text-xs tabular-nums pr-2 py-1 rounded outline-none focus:border-indigo-500 placeholder:text-slate-500 ${
                                          (() => {
                                            const cur = lc?.credit_currency_id != null ? currencies?.find(c => c.id === lc.credit_currency_id) : null
                                            return (!cur || cur.reward_kind === 'cash') ? 'pl-5' : 'pl-2'
                                          })()
                                        }`}
                                      />
                                    </div>
                                    {/* Remove (X icon) */}
                                    <button
                                      type="button"
                                      onClick={() => {
                                        setSelectedCredits((prev) => {
                                          const next = { ...prev }
                                          delete next[libId]
                                          return next
                                        })
                                        if (isExpanded) setCreditOptionsOpen(null)
                                      }}
                                      className="text-slate-500 hover:text-red-400 p-0.5 rounded hover:bg-slate-700/80"
                                      title="Remove credit"
                                    >
                                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                        <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                      </svg>
                                    </button>
                                  </div>
                                </div>
                                {isExpanded && (
                                  <div className="flex items-center gap-3 px-6 pb-2.5 pt-0.5 text-xs text-slate-400">
                                    <label className="flex items-center gap-1.5 cursor-pointer select-none">
                                      <input
                                        type="checkbox"
                                        checked={lc?.excludes_first_year ?? false}
                                        onChange={() => {
                                          if (!lc) return
                                          creditsApi.update(lc.id, { excludes_first_year: !lc.excludes_first_year })
                                            .then(() => queryClient.invalidateQueries({ queryKey: queryKeys.credits() }))
                                        }}
                                        className="accent-amber-500 w-3 h-3"
                                      />
                                      <span>After Year 1</span>
                                    </label>
                                    <label className="flex items-center gap-1.5 cursor-pointer select-none">
                                      <input
                                        type="checkbox"
                                        checked={lc?.is_one_time ?? false}
                                        onChange={() => {
                                          if (!lc) return
                                          creditsApi.update(lc.id, { is_one_time: !lc.is_one_time })
                                            .then(() => queryClient.invalidateQueries({ queryKey: queryKeys.credits() }))
                                        }}
                                        className="accent-indigo-500 w-3 h-3"
                                      />
                                      <span>One-Time</span>
                                    </label>
                                    <div className="flex-1" />
                                    <select
                                      value={lc?.credit_currency_id ?? 'null'}
                                      onChange={(e) => {
                                        if (!lc) return
                                        const cid = e.target.value === 'null' ? null : Number(e.target.value)
                                        creditsApi.update(lc.id, { credit_currency_id: cid })
                                          .then(() => queryClient.invalidateQueries({ queryKey: queryKeys.credits() }))
                                      }}
                                      className="bg-slate-700 border border-slate-600 text-white text-xs px-2 py-1 rounded outline-none focus:border-indigo-500"
                                    >
                                      {(currencies ?? []).filter((cur) => {
                                        if (cur.reward_kind === 'cash') return true
                                        if (walletCurrencyIds.has(cur.id)) return true
                                        const selectedCard = cardId ? cards?.find((c) => c.id === cardId) : null
                                        if (selectedCard && cur.id === selectedCard.currency_id) return true
                                        return false
                                      }).map((cur) => (
                                        <option key={cur.id} value={cur.id}>{cur.name}</option>
                                      ))}
                                    </select>
                                  </div>
                                )}
                              </li>
                            )
                          })}
                        </ul>
                      )}
                      <div className="px-6 py-2 border-t border-slate-700/60">
                        {!showCreditPicker ? (
                          <button
                            type="button"
                            onClick={() => setShowCreditPicker(true)}
                            className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs text-indigo-400 hover:text-indigo-300 hover:bg-slate-700/40 rounded transition-colors"
                          >
                            <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M12 4v16m8-8H4" />
                            </svg>
                            Add Credit
                          </button>
                        ) : (
                          <div className="space-y-1.5">
                            <div className="flex items-center gap-2">
                              <input
                                type="search"
                                value={creditSearch}
                                onChange={(e) => {
                                  setCreditSearch(e.target.value)
                                }}
                                placeholder="Search credits…"
                                className="flex-1 bg-slate-700 border border-slate-600 text-white text-xs px-2 py-1.5 rounded outline-none focus:border-indigo-500"
                                autoFocus
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  setShowCreditPicker(false)
                                  setCreditSearch('')
                                }}
                                className="p-1 text-slate-500 hover:text-slate-300 rounded hover:bg-slate-700/80"
                                title="Cancel"
                              >
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                            {(() => {
                              const trimmed = creditSearch.trim()
                              const q = trimmed.toLowerCase()
                              const matches = (creditLibrary ?? [])
                                .filter((c) => !(c.id in selectedCredits))
                                .filter((c) => !q || c.credit_name.toLowerCase().includes(q))
                              const exactExists = (creditLibrary ?? []).some(
                                (c) => c.credit_name.toLowerCase() === q,
                              )
                              const canCreate = trimmed.length > 0 && !exactExists
                              if (matches.length === 0 && !canCreate) {
                                return (
                                  <p className="text-[11px] text-slate-500 px-1 py-1">
                                    No matching credits.
                                  </p>
                                )
                              }
                              return (
                                <ul className="max-h-40 overflow-y-auto rounded border border-slate-700 divide-y divide-slate-700/60">
                                  {matches.map((c) => (
                                    <li key={c.id}>
                                      <button
                                        type="button"
                                        onClick={() => {
                                          const cardVal = cardId ? (c.card_values[cardId] ?? c.value ?? 0) : (c.value ?? 0)
                                          setSelectedCredits((prev) => ({
                                            ...prev,
                                            [c.id]: cardVal,
                                          }))
                                          setCreditSearch('')
                                          setShowCreditPicker(false)
                                        }}
                                        className="w-full flex items-center justify-between gap-2 px-2 py-1.5 text-xs text-slate-200 hover:bg-slate-700/60"
                                      >
                                        <span className="truncate min-w-0">{c.credit_name}</span>
                                        <span className="text-slate-500 tabular-nums shrink-0">
                                          {formatMoney(cardId ? (c.card_values[cardId] ?? c.value ?? 0) : (c.value ?? 0))}
                                        </span>
                                      </button>
                                    </li>
                                  ))}
                                  {canCreate && (
                                    <li>
                                      <button
                                        type="button"
                                        disabled={createCreditMutation.isPending}
                                        onClick={() => createCreditMutation.mutate(trimmed)}
                                        className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-indigo-300 hover:bg-slate-700/60 disabled:opacity-50"
                                      >
                                        <span className="shrink-0">+</span>
                                        <span className="truncate min-w-0">
                                          {createCreditMutation.isPending
                                            ? `Creating "${trimmed}"…`
                                            : `Create "${trimmed}"`}
                                        </span>
                                      </button>
                                    </li>
                                  )}
                                </ul>
                              )
                            })()}
                          </div>
                        )}
                      </div>
                    </div>
                </div>
              )}

              {/* Spend Category Priority tab.
                  Pins one or more wallet spend categories to this card so
                  the calculator always routes that spend here. A category
                  already claimed by another wallet card is disabled. */}
              {activeTab === 'priority' && lib && mode === 'edit' && (
                <div className="flex-1 min-h-0 flex flex-col">
                  <p className="text-[11px] text-slate-500 -mx-6 px-6 pb-2 border-b border-slate-700/60 mb-3">
                    Force category spend onto this card only. Does not affect SUB spend allocation.
                  </p>
                  {!walletSpendItems || walletSpendItems.length === 0 ? (
                    <p className="text-xs text-slate-500 py-1">
                      No wallet spend categories yet.
                    </p>
                  ) : (
                    <ul className="grid grid-cols-2 gap-x-2 gap-y-1 auto-rows-min flex-1 min-h-0 overflow-y-auto border border-slate-600 rounded-lg p-2">
                      {[...walletSpendItems]
                        .filter((item) => item.user_spend_category != null)
                        .sort((a, b) =>
                          (a.user_spend_category?.name ?? '').localeCompare(
                            b.user_spend_category?.name ?? '',
                            undefined,
                            { sensitivity: 'base' },
                          ),
                        )
                        .map((item) => {
                          const userCat = item.user_spend_category!
                          const earnCatIds = userCat.mappings.map((m) => m.earn_category_id)
                          const claimedByOther = earnCatIds.some((id) => priorityClaimsByOther.has(id))
                          const checked = earnCatIds.length > 0 && earnCatIds.every((id) => priorityCategoryIds.has(id))
                          const disabled = claimedByOther && !checked
                          return (
                            <li key={item.id}>
                              <label
                                className={`flex items-center gap-2 text-xs px-1 py-1 rounded ${
                                  disabled
                                    ? 'text-slate-500 cursor-not-allowed'
                                    : 'text-slate-200 cursor-pointer hover:bg-slate-700/40'
                                }`}
                              >
                                <input
                                  type="checkbox"
                                  className="accent-indigo-500"
                                  checked={checked}
                                  disabled={disabled}
                                  onChange={() => {
                                    setPriorityCategoryIds((prev) => {
                                      const next = new Set(prev)
                                      if (checked) {
                                        earnCatIds.forEach((id) => next.delete(id))
                                      } else {
                                        earnCatIds.forEach((id) => next.add(id))
                                      }
                                      return next
                                    })
                                  }}
                                />
                                <span className="flex-1 min-w-0 truncate">
                                  {userCat.name}
                                </span>
                                {disabled && (
                                  <span className="text-[10px] text-slate-600 shrink-0">
                                    Claimed By Another Card
                                  </span>
                                )}
                              </label>
                            </li>
                          )
                        })}
                    </ul>
                  )}
                </div>
              )}

              {formError && (
                <p className="text-xs text-red-400 bg-red-950/40 border border-red-900/50 rounded-lg mx-0 mt-3 px-3 py-2">
                  {formError}
                </p>
              )}
            </div>
          )}
        </div>

        {/* ── Fixed footer ── */}
        {hasNextTab && (
          <div className="flex-shrink-0 flex items-center gap-2 px-6 py-4 border-t border-slate-700">
            <button
              type="button"
              disabled={isLoading}
              className="flex-1 flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm py-2 rounded-lg"
              onClick={() => setActiveTab(tabOrder[currentTabIndex + 1])}
            >
              Next
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M5 12h14" />
                <path d="M13 6l6 6-6 6" />
              </svg>
            </button>
          </div>
        )}
      </ModalBackdrop>

    </>
  )
}
