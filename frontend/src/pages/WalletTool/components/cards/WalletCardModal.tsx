import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
// Note: useRef is used here to track which data has been hydrated into the form,
// preventing re-runs when the card library re-fetches without the user changing selection.
import {
  type AddCardToWalletPayload,
  type CardCredit,
  type CardMultiplierGroup,
  type UpdateWalletCardPayload,
  type WalletCard,
  type WalletCardAcquisitionType,
  type WalletCardRotationOverride,
  creditsApi,
  walletCardCreditApi,
  walletCardGroupSelectionApi,
  walletCardRotationOverrideApi,
} from '../../../../api/client'
import { ModalBackdrop } from '../../../../components/ModalBackdrop'
import { formatMoney, today } from '../../../../utils/format'
import { useCardLibrary } from '../../hooks/useCardLibrary'
import { useCreditLibrary } from '../../hooks/useCreditLibrary'
import { buildWalletCardFields, walletFormToUpdatePayload } from '../../lib/walletCardForm'
import { queryKeys } from '../../lib/queryKeys'

// ---------------------------------------------------------------------------
// Main modal
// ---------------------------------------------------------------------------

export function WalletCardModal({
  mode,
  walletCard,
  existingCardIds,
  onClose,
  onAdd,
  onSaveEdit,
  isLoading,
}: {
  mode: 'add' | 'edit'
  walletCard?: WalletCard
  existingCardIds: number[]
  onClose: () => void
  onAdd: (payload: AddCardToWalletPayload) => void
  onSaveEdit: (payload: UpdateWalletCardPayload) => void
  isLoading: boolean
}) {
  const { data: cards } = useCardLibrary()
  const queryClient = useQueryClient()

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
  const [subPoints, setSubPoints] = useState('')
  const [subMinSpend, setSubMinSpend] = useState('')
  const [subMonths, setSubMonths] = useState('')
  const [annualBonus, setAnnualBonus] = useState('')
  const [annualFee, setAnnualFee] = useState('')
  const [firstYearFee, setFirstYearFee] = useState('')
  // Selected statement credits for this wallet card: library_credit_id -> value.
  // The presence of a key means the credit is attached to this wallet card.
  const [selectedCredits, setSelectedCredits] = useState<Record<number, number>>({})
  const [creditsExpanded, setCreditsExpanded] = useState(false)
  const [creditPickerOpen, setCreditPickerOpen] = useState(false)
  const [creditSearch, setCreditSearch] = useState('')
  const [groupSelectionsExpanded, setGroupSelectionsExpanded] = useState(false)
  // group_id -> array of selected spend_category_ids (length == top_n)
  const [groupSelections, setGroupSelections] = useState<Record<number, number[]>>({})
  const [formError, setFormError] = useState<string | null>(null)

  // Tracks the last key we hydrated form state from, preventing re-runs when the
  // card library re-fetches without the user changing their selection.
  // Format: "add:<cardId>" | "edit:<walletCardId>"
  const hydratedKey = useRef<string>('')

  const effectiveCardId =
    mode === 'add' ? (typeof cardId === 'number' ? cardId : null) : (walletCard?.card_id ?? null)

  // Global standardized credit library (Priority Pass, Global Entry, etc.).
  // Cached indefinitely; prefetched at the WalletTool root so opening the
  // modal does not block on a network round-trip.
  const { data: creditLibrary, isLoading: creditLibraryLoading } = useCreditLibrary()
  const creditLibraryById = useMemo(() => {
    const m = new Map<number, CardCredit>()
    for (const c of creditLibrary ?? []) m.set(c.id, c)
    return m
  }, [creditLibrary])

  const createCreditMutation = useMutation({
    mutationFn: (credit_name: string) => creditsApi.create({ credit_name, credit_value: 0 }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credits() })
      setSelectedCredits((prev) => ({ ...prev, [created.id]: created.credit_value }))
      setCreditPickerOpen(false)
      setCreditSearch('')
    },
    onError: (e: Error) => setFormError(e.message),
  })

  // Existing wallet-card credit selections (edit mode only)
  const { data: existingCreditOverrides } = useQuery({
    queryKey: queryKeys.walletCardCredits(walletCard?.wallet_id ?? null, walletCard?.card_id ?? null),
    queryFn: () => walletCardCreditApi.list(walletCard!.wallet_id, walletCard!.card_id),
    enabled: mode === 'edit' && walletCard != null,
  })

  // Fetch existing group category selections (edit mode only)
  const { data: existingGroupSelections } = useQuery({
    queryKey: queryKeys.walletCardGroupSelections(walletCard?.wallet_id ?? null, walletCard?.card_id ?? null),
    queryFn: () => walletCardGroupSelectionApi.list(walletCard!.wallet_id, walletCard!.card_id),
    enabled: mode === 'edit' && walletCard != null,
  })

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

  // Groups with top-N behavior on the selected card
  const topNGroups = useMemo<CardMultiplierGroup[]>(() => {
    if (!lib) return []
    return lib.multiplier_groups.filter((g) => g.top_n_categories != null && g.top_n_categories > 0)
  }, [lib])

  // Rotating-bonus groups on the selected card (Discover IT / Chase Freedom Flex / Freedom)
  const rotatingGroups = useMemo<CardMultiplierGroup[]>(() => {
    if (!lib) return []
    return lib.multiplier_groups.filter((g) => g.is_rotating)
  }, [lib])
  const hasRotating = rotatingGroups.length > 0

  // Rotation overrides — only fetched in edit mode (need an existing wallet card row).
  const { data: existingOverrides } = useQuery({
    queryKey: queryKeys.walletCardRotationOverrides(
      walletCard?.wallet_id ?? null,
      walletCard?.card_id ?? null,
    ),
    queryFn: () =>
      walletCardRotationOverrideApi.list(walletCard!.wallet_id, walletCard!.card_id),
    enabled: mode === 'edit' && walletCard != null && hasRotating,
  })

  const [rotationExpanded, setRotationExpanded] = useState(false)
  const [pinYear, setPinYear] = useState<number>(new Date().getFullYear())
  const [pinQuarter, setPinQuarter] = useState<number>(
    Math.floor(new Date().getMonth() / 3) + 1,
  )
  const [pinCategoryId, setPinCategoryId] = useState<number | ''>('')

  const addOverrideMutation = useMutation({
    mutationFn: (payload: {
      year: number
      quarter: number
      spend_category_id: number
    }) =>
      walletCardRotationOverrideApi.add(
        walletCard!.wallet_id,
        walletCard!.card_id,
        payload,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.walletCardRotationOverrides(
          walletCard!.wallet_id,
          walletCard!.card_id,
        ),
      })
      setPinCategoryId('')
    },
  })

  const deleteOverrideMutation = useMutation({
    mutationFn: (overrideId: number) =>
      walletCardRotationOverrideApi.delete(
        walletCard!.wallet_id,
        walletCard!.card_id,
        overrideId,
      ),
    onSuccess: () => {
      queryClient.invalidateQueries({
        queryKey: queryKeys.walletCardRotationOverrides(
          walletCard!.wallet_id,
          walletCard!.card_id,
        ),
      })
    },
  })

  // Combined unique category list across all rotating groups for the picker
  const rotatingCategoryUniverse = useMemo(() => {
    const seen = new Map<number, string>()
    for (const g of rotatingGroups) {
      for (const c of g.categories) {
        if (!seen.has(c.spend_category_id)) seen.set(c.spend_category_id, c.name)
      }
    }
    return Array.from(seen.entries())
      .map(([id, name]) => ({ id, name }))
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [rotatingGroups])

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
      setSubPoints(lib.sub != null ? String(lib.sub) : '')
      setSubMinSpend(lib.sub_min_spend != null ? String(lib.sub_min_spend) : '')
      setSubMonths(lib.sub_months != null ? String(lib.sub_months) : '')
      setAnnualBonus(lib.annual_bonus != null ? String(lib.annual_bonus) : '')
      setAnnualFee(String(lib.annual_fee))
      setFirstYearFee(lib.first_year_fee != null ? String(lib.first_year_fee) : '')
      // Auto-attach the default statement credits this card natively offers,
      // based on the global card_credits link table.
      const defaults: Record<number, number> = {}
      for (const c of creditLibrary) {
        if (c.card_ids.includes(cardId)) {
          defaults[c.id] = c.credit_value
        }
      }
      setSelectedCredits(defaults)
      setCreditsExpanded(Object.keys(defaults).length > 0)
      setGroupSelections({})
      setFormError(null)
    } else {
      if (!walletCard || !lib) return
      const key = `edit:${walletCard.id}`
      if (hydratedKey.current === key) return
      hydratedKey.current = key
      setAddedDate(walletCard.added_date)
      setAcquisitionType(walletCard.acquisition_type)
      const effSub = walletCard.sub ?? lib.sub
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
      setSelectedCredits({})
      setGroupSelections({})
      setFormError(null)
    }
  }, [mode, cardId, lib, walletCard, creditLibrary])

  // Populate selected credits from the wallet-specific API data (edit mode).
  useEffect(() => {
    if (mode !== 'edit' || existingCreditOverrides === undefined) return
    const m: Record<number, number> = {}
    for (const o of existingCreditOverrides) {
      m[o.library_credit_id] = o.value
    }
    setSelectedCredits(m)
  }, [mode, existingCreditOverrides])

  // Populate group selection state from the wallet-specific API data (edit mode).
  useEffect(() => {
    if (mode !== 'edit' || !lib || existingGroupSelections === undefined) return
    const m: Record<number, number[]> = {}
    for (const g of topNGroups) {
      const picks = existingGroupSelections
        .filter((s) => s.multiplier_group_id === g.id)
        .map((s) => s.spend_category_id)
      if (picks.length > 0) {
        m[g.id] = picks
      }
    }
    setGroupSelections(m)
  }, [mode, lib, existingGroupSelections, topNGroups])

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

    if (mode === 'add') {
      if (typeof cardId !== 'number') return
      onAdd({
        card_id: cardId,
        added_date: addedDate,
        acquisition_type: acquisitionType,
        sub: built.sub,
        sub_min_spend: built.sub_min_spend,
        sub_months: built.sub_months,
        annual_bonus: built.annual_bonus,
        annual_fee: built.annual_fee,
        first_year_fee: built.first_year_fee,
        credits: Object.entries(selectedCredits).map(([id, value]) => ({
          library_credit_id: Number(id),
          value,
        })),
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
    // Save group selections via the dedicated API.
    const groupOps: Promise<unknown>[] = []
    for (const g of topNGroups) {
      const rawPicks = groupSelections[g.id] ?? []
      const realPicks = rawPicks.filter((id) => id !== 0)
      const hadExisting = existingGroupSelections?.some((s) => s.multiplier_group_id === g.id)
      if (realPicks.length === (g.top_n_categories ?? 1)) {
        groupOps.push(walletCardGroupSelectionApi.set(walletCard.wallet_id, walletCard.card_id, g.id, realPicks))
      } else if (hadExisting && realPicks.length === 0) {
        // All slots reverted to auto — delete selections
        groupOps.push(walletCardGroupSelectionApi.delete(walletCard.wallet_id, walletCard.card_id, g.id))
      }
      // If partially filled (some auto, some real), skip saving — user needs to fill all slots
    }

    try {
      await Promise.all([...creditOps, ...groupOps])
    } catch {
      setFormError('Failed to save overrides.')
      return
    }

    queryClient.invalidateQueries({
      queryKey: queryKeys.walletCardCredits(walletCard.wallet_id, walletCard.card_id),
    })
    onSaveEdit(walletFormToUpdatePayload(built, lib, addedDate, acquisitionType))
  }

  const formDisabled = !lib
  const title =
    mode === 'add'
      ? 'Add Card to Wallet'
      : `${walletCard?.card_name ?? `Card #${walletCard?.card_id ?? ''}`}`

  const primaryLabel =
    mode === 'add' ? (isLoading ? 'Adding…' : 'Add Card') : isLoading ? 'Saving…' : 'Save Changes'

  const primaryDisabled =
    mode === 'add'
      ? (acquisitionType === 'product_change' ? (!pcFromCardId || !cardId || isLoading) : (!cardId || isLoading))
      : isLoading || !walletCard

  return (
    <>
      <ModalBackdrop
        onClose={onClose}
        className="bg-slate-800 border border-slate-600 rounded-xl w-full max-w-lg shadow-xl flex flex-col max-h-[90vh]"
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
          </div>
        </div>

        {/* ── Body ── */}
        <div className="px-6 py-4 overflow-y-auto flex-1 min-h-0">
          {mode === 'edit' && !lib ? (
            <p className="text-sm text-slate-400 py-8 text-center">Loading card…</p>
          ) : (
            <div className="space-y-3">
              {/* Acquisition type (left) | Opening date (right) */}
              <div className="grid grid-cols-2 gap-3 items-start">
                <div>
                  <label className="text-xs text-slate-400 mb-1 block">Acquisition Type</label>
                  <div className="flex flex-col gap-1.5 pt-1">
                    {(['opened', 'product_change'] as const).map((v) => (
                      <label key={v} className="flex items-center gap-1.5 text-xs text-white cursor-pointer">
                        <input
                          type="radio"
                          name="acquisitionType"
                          value={v}
                          checked={acquisitionType === v}
                          onChange={() => setAcquisitionType(v)}
                          className="accent-indigo-500"
                        />
                        {v === 'opened' ? 'Account Opening' : 'Product Change'}
                      </label>
                    ))}
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

              {/* Statement Credits inline collapsible */}
              {lib && (
                <div className="border border-slate-600 rounded-lg overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setCreditsExpanded((prev) => !prev)}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-slate-300 hover:bg-slate-700/40"
                  >
                    <span>
                      Statement Credits
                      {Object.keys(selectedCredits).length > 0 && (
                        <span className="text-indigo-300 ml-1">
                          ({Object.keys(selectedCredits).length})
                        </span>
                      )}
                    </span>
                    <svg
                      className={`w-4 h-4 text-slate-400 transition-transform ${creditsExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {creditsExpanded && (
                    <div className="border-t border-slate-700">
                      {creditLibraryLoading ? (
                        <div className="flex items-center gap-2 px-3 py-3 text-xs text-slate-400">
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
                        <p className="text-xs text-slate-500 px-3 py-3">
                          No credits selected. Add credits this card grants from the picker below.
                        </p>
                      ) : (
                        <ul className="divide-y divide-slate-700/40 max-h-48 overflow-y-auto">
                          {Object.entries(selectedCredits).map(([idStr, value]) => {
                            const libId = Number(idStr)
                            const lc = creditLibraryById.get(libId)
                            return (
                              <li
                                key={libId}
                                className="flex items-center justify-between gap-2 px-3 py-2 text-sm"
                              >
                                <span className="text-slate-200 truncate min-w-0 flex-1">
                                  {lc?.credit_name ?? `Credit #${libId}`}
                                </span>
                                <div className="flex items-center gap-2 shrink-0">
                                  <div className="relative">
                                    <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-slate-500 pointer-events-none">
                                      $
                                    </span>
                                    <input
                                      type="number"
                                      min={0}
                                      step="0.01"
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
                                      className="w-24 bg-slate-700 border border-slate-600 text-white text-xs tabular-nums pl-5 pr-2 py-1 rounded outline-none focus:border-indigo-500 placeholder:text-slate-500"
                                    />
                                  </div>
                                  <button
                                    type="button"
                                    onClick={() =>
                                      setSelectedCredits((prev) => {
                                        const next = { ...prev }
                                        delete next[libId]
                                        return next
                                      })
                                    }
                                    className="text-slate-500 hover:text-red-400 text-xs px-2 py-1 rounded-md hover:bg-slate-700/80"
                                  >
                                    Remove
                                  </button>
                                </div>
                              </li>
                            )
                          })}
                        </ul>
                      )}
                      <div className="px-3 py-2 border-t border-slate-700/60">
                        {!creditPickerOpen ? (
                          <button
                            type="button"
                            onClick={() => {
                              setCreditPickerOpen(true)
                              setCreditSearch('')
                            }}
                            className="text-xs text-indigo-400 hover:text-indigo-300 font-medium"
                          >
                            + Add credit
                          </button>
                        ) : (
                          <div className="space-y-1.5">
                            <div className="flex items-center gap-2">
                              <input
                                type="search"
                                autoFocus
                                value={creditSearch}
                                onChange={(e) => setCreditSearch(e.target.value)}
                                placeholder="Search credits…"
                                className="flex-1 bg-slate-700 border border-slate-600 text-white text-xs px-2 py-1.5 rounded outline-none focus:border-indigo-500"
                              />
                              <button
                                type="button"
                                onClick={() => {
                                  setCreditPickerOpen(false)
                                  setCreditSearch('')
                                }}
                                className="text-xs text-slate-400 hover:text-white px-2 py-1.5"
                              >
                                Cancel
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
                                          setSelectedCredits((prev) => ({
                                            ...prev,
                                            [c.id]: c.credit_value,
                                          }))
                                          setCreditPickerOpen(false)
                                          setCreditSearch('')
                                        }}
                                        className="w-full flex items-center justify-between gap-2 px-2 py-1.5 text-xs text-slate-200 hover:bg-slate-700/60"
                                      >
                                        <span className="truncate min-w-0">{c.credit_name}</span>
                                        <span className="text-slate-500 tabular-nums shrink-0">
                                          {formatMoney(c.credit_value)}
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
                  )}
                </div>
              )}

              {/* Rotation override pinning (rotating-bonus cards in edit mode) */}
              {hasRotating && mode === 'edit' && walletCard != null && (
                <div className="border border-slate-600 rounded-lg overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setRotationExpanded((prev) => !prev)}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-slate-300 hover:bg-slate-700/40"
                  >
                    <span>
                      Rotation Quarter Pins{' '}
                      {existingOverrides && existingOverrides.length > 0 && (
                        <span className="text-indigo-300 ml-1">
                          ({existingOverrides.length})
                        </span>
                      )}
                    </span>
                    <svg
                      className={`w-4 h-4 text-slate-400 transition-transform ${rotationExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {rotationExpanded && (
                    <div className="border-t border-slate-700 px-3 py-3 space-y-3">
                      <p className="text-[11px] text-slate-400">
                        Pin a category as the active rotating bonus for a specific
                        quarter. Pinned quarters override the inferred historical
                        activation probabilities — pinned categories get the full{' '}
                        {rotatingGroups[0].multiplier}× rate up to the cap. Quarters
                        without a pin keep using the inferred weights.
                      </p>
                      {existingOverrides && existingOverrides.length > 0 && (
                        <ul className="space-y-1">
                          {existingOverrides.map((ov: WalletCardRotationOverride) => (
                            <li
                              key={ov.id}
                              className="flex items-center justify-between text-xs text-slate-200 bg-slate-900/50 rounded px-2 py-1.5"
                            >
                              <span>
                                <span className="text-slate-400 tabular-nums mr-2">
                                  {ov.year}Q{ov.quarter}
                                </span>
                                {ov.category_name}
                              </span>
                              <button
                                type="button"
                                onClick={() => deleteOverrideMutation.mutate(ov.id)}
                                className="text-slate-500 hover:text-red-400 text-[11px]"
                              >
                                Remove
                              </button>
                            </li>
                          ))}
                        </ul>
                      )}
                      <div className="flex gap-2 items-end">
                        <div className="w-20">
                          <label className="text-[10px] text-slate-500 block mb-0.5">
                            Year
                          </label>
                          <input
                            type="number"
                            value={pinYear}
                            onChange={(e) => setPinYear(Number(e.target.value))}
                            className="w-full bg-slate-700 border border-slate-600 text-white text-xs px-2 py-1.5 rounded outline-none focus:border-indigo-500"
                          />
                        </div>
                        <div className="w-16">
                          <label className="text-[10px] text-slate-500 block mb-0.5">
                            Quarter
                          </label>
                          <select
                            value={pinQuarter}
                            onChange={(e) => setPinQuarter(Number(e.target.value))}
                            className="w-full bg-slate-700 border border-slate-600 text-white text-xs px-2 py-1.5 rounded outline-none focus:border-indigo-500"
                          >
                            <option value={1}>Q1</option>
                            <option value={2}>Q2</option>
                            <option value={3}>Q3</option>
                            <option value={4}>Q4</option>
                          </select>
                        </div>
                        <div className="flex-1">
                          <label className="text-[10px] text-slate-500 block mb-0.5">
                            Category
                          </label>
                          <select
                            value={pinCategoryId}
                            onChange={(e) =>
                              setPinCategoryId(
                                e.target.value === '' ? '' : Number(e.target.value),
                              )
                            }
                            className="w-full bg-slate-700 border border-slate-600 text-white text-xs px-2 py-1.5 rounded outline-none focus:border-indigo-500"
                          >
                            <option value="">Pick a category…</option>
                            {rotatingCategoryUniverse.map((c) => (
                              <option key={c.id} value={c.id}>
                                {c.name}
                              </option>
                            ))}
                          </select>
                        </div>
                        <button
                          type="button"
                          disabled={pinCategoryId === '' || addOverrideMutation.isPending}
                          onClick={() =>
                            addOverrideMutation.mutate({
                              year: pinYear,
                              quarter: pinQuarter,
                              spend_category_id: Number(pinCategoryId),
                            })
                          }
                          className="bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white text-xs px-3 py-1.5 rounded"
                        >
                          Pin
                        </button>
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Bonus Category Selections inline collapsible */}
              {topNGroups.length > 0 && (
                <div className="border border-slate-600 rounded-lg overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setGroupSelectionsExpanded((prev) => !prev)}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-slate-300 hover:bg-slate-700/40"
                  >
                    <span>Bonus Category Selections</span>
                    <svg
                      className={`w-4 h-4 text-slate-400 transition-transform ${groupSelectionsExpanded ? 'rotate-180' : ''}`}
                      fill="none"
                      viewBox="0 0 24 24"
                      stroke="currentColor"
                      strokeWidth={2}
                    >
                      <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                    </svg>
                  </button>
                  {groupSelectionsExpanded && (
                    <div className="border-t border-slate-700 px-3 py-3 space-y-4">
                      {topNGroups.map((g) => {
                        const topN = g.top_n_categories ?? 1
                        const picks = groupSelections[g.id] ?? []
                        return (
                          <div key={g.id}>
                            <p className="text-xs text-slate-400 mb-2">
                              {g.multiplier}x — pick {topN} of {g.categories.length} categories
                            </p>
                            {Array.from({ length: topN }, (_, slotIdx) => {
                              const currentPick = picks[slotIdx] ?? 0
                              // Categories already picked in other slots for this group
                              const otherPicks = picks.filter((_, i) => i !== slotIdx)
                              return (
                                <select
                                  key={slotIdx}
                                  className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 mb-2"
                                  value={currentPick}
                                  onChange={(e) => {
                                    const val = Number(e.target.value)
                                    setGroupSelections((prev) => {
                                      const arr = [...(prev[g.id] ?? Array(topN).fill(0))]
                                      arr[slotIdx] = val
                                      return { ...prev, [g.id]: arr }
                                    })
                                  }}
                                >
                                  <option value={0}>Auto (by spend)</option>
                                  {g.categories.map((cat) => (
                                    <option
                                      key={cat.spend_category_id}
                                      value={cat.spend_category_id}
                                      disabled={otherPicks.includes(cat.spend_category_id)}
                                    >
                                      {cat.name}
                                    </option>
                                  ))}
                                </select>
                              )
                            })}
                          </div>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {formError && (
                <p className="text-xs text-red-400 bg-red-950/40 border border-red-900/50 rounded-lg px-3 py-2">
                  {formError}
                </p>
              )}
            </div>
          )}
        </div>

        {/* ── Fixed footer ── */}
        <div className="flex-shrink-0 flex gap-2 px-6 py-4 border-t border-slate-700">
          <button
            type="button"
            className="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-sm py-2 rounded-lg"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            type="button"
            disabled={primaryDisabled}
            className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm py-2 rounded-lg"
            onClick={handlePrimary}
          >
            {primaryLabel}
          </button>
        </div>
      </ModalBackdrop>

    </>
  )
}
