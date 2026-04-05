import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useId, useMemo, useRef, useState } from 'react'
// Note: useRef is used here to track which data has been hydrated into the form,
// preventing re-runs when the card library re-fetches without the user changing selection.
import {
  type AddCardToWalletPayload,
  type CardCredit,
  type UpdateWalletCardPayload,
  type WalletCard,
  type WalletCardAcquisitionType,
  cardsApi,
  walletCardCreditApi,
} from '../../../../api/client'
import { ModalBackdrop } from '../../../../components/ModalBackdrop'
import { formatMoney, today } from '../../../../utils/format'
import { useCardLibrary } from '../../hooks/useCardLibrary'
import { buildWalletCardFields, walletFormToUpdatePayload } from '../../lib/walletCardForm'
import { queryKeys } from '../../lib/queryKeys'

// ---------------------------------------------------------------------------
// Inline credit value editor dialog
// ---------------------------------------------------------------------------

function MiniDialog({
  title,
  children,
  onClose,
}: {
  title: string
  children: React.ReactNode
  onClose: () => void
}) {
  const titleId = useId()
  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-[70] p-4"
      role="dialog"
      aria-modal="true"
      aria-labelledby={titleId}
      onClick={onClose}
    >
      <div
        className="bg-slate-800 border border-slate-600 rounded-xl p-5 w-full max-w-sm shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id={titleId} className="text-base font-semibold text-white mb-4">
          {title}
        </h3>
        {children}
      </div>
    </div>
  )
}

function CreditValueEditorDialog({
  open,
  creditName,
  initialValue,
  onClose,
  onSave,
}: {
  open: boolean
  creditName: string
  initialValue: number
  onClose: () => void
  onSave: (value: number) => void
}) {
  const [valueText, setValueText] = useState(String(initialValue))

  useEffect(() => {
    if (open) setValueText(String(initialValue))
  }, [open, initialValue])

  if (!open) return null

  function submit() {
    const v = Number.parseFloat(valueText.trim())
    if (Number.isNaN(v) || v < 0) return
    onSave(v)
    onClose()
  }

  return (
    <MiniDialog title="Statement credit (this wallet)" onClose={onClose}>
      <p className="text-sm text-slate-300 mb-3">{creditName}</p>
      <label className="text-xs text-slate-400 mb-1 block">Value ($)</label>
      <input
        type="number"
        min={0}
        step="0.01"
        className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500 mb-4"
        value={valueText}
        onChange={(e) => setValueText(e.target.value)}
        onKeyDown={(e) => e.key === 'Enter' && submit()}
      />
      <div className="flex gap-2">
        <button
          type="button"
          className="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-sm py-2 rounded-lg"
          onClick={onClose}
        >
          Cancel
        </button>
        <button
          type="button"
          className="flex-1 bg-indigo-600 hover:bg-indigo-500 text-white text-sm py-2 rounded-lg"
          onClick={submit}
        >
          Save
        </button>
      </div>
    </MiniDialog>
  )
}

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
  const [creditOverrides, setCreditOverrides] = useState<Record<number, number>>({})
  const [creditsExpanded, setCreditsExpanded] = useState(false)
  const [editingCredit, setEditingCredit] = useState<CardCredit | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  // Tracks the last key we hydrated form state from, preventing re-runs when the
  // card library re-fetches without the user changing their selection.
  // Format: "add:<cardId>" | "edit:<walletCardId>"
  const hydratedKey = useRef<string>('')

  const effectiveCardId =
    mode === 'add' ? (typeof cardId === 'number' ? cardId : null) : (walletCard?.card_id ?? null)

  // Fetch existing per-wallet credit overrides (edit mode only)
  const { data: existingCreditOverrides } = useQuery({
    queryKey: queryKeys.walletCardCredits(walletCard?.wallet_id ?? null, walletCard?.card_id ?? null),
    queryFn: () => walletCardCreditApi.list(walletCard!.wallet_id, walletCard!.card_id),
    enabled: mode === 'edit' && walletCard != null,
  })

  // Cards already in the wallet — shown in the "changing from" picker
  const walletCards = useMemo(() => {
    if (!cards) return []
    return cards.filter((c) => existingCardIds.includes(c.id))
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
    if (!q) return issuerFilteredCards
    return issuerFilteredCards.filter((c) => c.name.toLowerCase().includes(q))
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

  const patchCreditMutation = useMutation({
    mutationFn: ({
      creditId,
      payload,
    }: {
      creditId: number
      payload: { is_one_time: boolean }
    }) => cardsApi.updateCredit(effectiveCardId!, creditId, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.cards() })
    },
  })

  useEffect(() => {
    if (mode === 'add') {
      if (!cardId) {
        hydratedKey.current = ''
        return
      }
      if (!lib) return
      const key = `add:${cardId}`
      if (hydratedKey.current === key) return
      hydratedKey.current = key
      setSubPoints(lib.sub != null ? String(lib.sub) : '')
      setSubMinSpend(lib.sub_min_spend != null ? String(lib.sub_min_spend) : '')
      setSubMonths(lib.sub_months != null ? String(lib.sub_months) : '')
      setAnnualBonus(lib.annual_bonus != null ? String(lib.annual_bonus) : '')
      setAnnualFee(String(lib.annual_fee))
      setFirstYearFee(lib.first_year_fee != null ? String(lib.first_year_fee) : '')
      setCreditOverrides({})
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
      setCreditOverrides({})
      setFormError(null)
    }
  }, [mode, cardId, lib, walletCard])

  // Populate credit override state from the wallet-specific API data (edit mode).
  useEffect(() => {
    if (mode !== 'edit' || !lib || existingCreditOverrides === undefined) return
    const m: Record<number, number> = {}
    for (const cr of lib.credits) {
      const existing = existingCreditOverrides.find((o) => o.library_credit_id === cr.id)
      m[cr.id] = existing !== undefined ? existing.value : cr.credit_value
    }
    setCreditOverrides(m)
  }, [mode, lib, existingCreditOverrides])

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
      })
      return
    }

    if (!walletCard || !lib) {
      setFormError('Card library data is still loading.')
      return
    }

    // Save credit overrides via the dedicated API before patching the card row.
    const creditOps: Promise<unknown>[] = []
    for (const cr of lib.credits) {
      const v = creditOverrides[cr.id] ?? cr.credit_value
      const hasExisting = existingCreditOverrides?.some((o) => o.library_credit_id === cr.id)
      if (Math.abs(v - cr.credit_value) > 1e-6) {
        creditOps.push(walletCardCreditApi.upsert(walletCard.wallet_id, walletCard.card_id, cr.id, { value: v }))
      } else if (hasExisting) {
        // Override was reset to library default — remove the stored row.
        creditOps.push(walletCardCreditApi.delete(walletCard.wallet_id, walletCard.card_id, cr.id))
      }
    }
    try {
      await Promise.all(creditOps)
    } catch {
      setFormError('Failed to save credit valuations.')
      return
    }

    onSaveEdit(walletFormToUpdatePayload(built, lib, creditOverrides, addedDate, acquisitionType))
  }

  function displayCreditValue(cr: CardCredit) {
    return creditOverrides[cr.id] ?? cr.credit_value
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
        className="bg-slate-800 border border-slate-600 rounded-xl w-full max-w-lg shadow-xl flex flex-col"
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
        <div className="px-6 py-4">
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

              {/* Credit Valuations inline collapsible */}
              {lib && lib.credits.length > 0 && (
                <div className="border border-slate-600 rounded-lg overflow-hidden">
                  <button
                    type="button"
                    onClick={() => setCreditsExpanded((prev) => !prev)}
                    className="w-full flex items-center justify-between px-3 py-2.5 text-sm text-slate-300 hover:bg-slate-700/40"
                  >
                    <span>Credit Valuations</span>
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
                      <ul className="divide-y divide-slate-700/40 max-h-48 overflow-y-auto">
                        {lib.credits.map((cr) => (
                          <li
                            key={cr.id}
                            className="flex flex-col gap-1.5 sm:flex-row sm:items-center sm:justify-between px-3 py-2 text-sm"
                          >
                            <div className="min-w-0">
                              <span className="text-slate-200 block truncate">{cr.credit_name}</span>
                              <label className="mt-0.5 flex items-center gap-2 text-xs text-slate-500 cursor-pointer select-none">
                                <input
                                  type="checkbox"
                                  className="rounded border-slate-500 bg-slate-800 text-indigo-500 focus:ring-indigo-500"
                                  checked={Boolean(cr.is_one_time)}
                                  disabled={patchCreditMutation.isPending || effectiveCardId == null}
                                  onChange={(e) =>
                                    patchCreditMutation.mutate({
                                      creditId: cr.id,
                                      payload: { is_one_time: e.target.checked },
                                    })
                                  }
                                />
                                One-Time Credit
                              </label>
                            </div>
                            <div className="flex items-center gap-2 shrink-0 self-end sm:self-center">
                              <span className="text-slate-400 tabular-nums">
                                {formatMoney(displayCreditValue(cr))}
                              </span>
                              <button
                                type="button"
                                onClick={() => setEditingCredit(cr)}
                                className="text-indigo-400 hover:text-indigo-300 text-xs font-medium px-2 py-1 rounded-md hover:bg-slate-700/80"
                              >
                                Edit
                              </button>
                            </div>
                          </li>
                        ))}
                      </ul>
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

      <CreditValueEditorDialog
        open={editingCredit != null}
        creditName={editingCredit?.credit_name ?? ''}
        initialValue={editingCredit != null ? displayCreditValue(editingCredit) : 0}
        onClose={() => setEditingCredit(null)}
        onSave={(value) => {
          if (editingCredit) setCreditOverrides((prev) => ({ ...prev, [editingCredit.id]: value }))
        }}
      />
    </>
  )
}
