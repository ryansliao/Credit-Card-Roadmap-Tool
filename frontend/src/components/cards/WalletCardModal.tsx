import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useRef, useState } from 'react'
import {
  type CardCredit,
  type CardInstance,
  type FutureCardCreatePayload,
  type FutureCardUpdatePayload,
  type OwnedCardCreatePayload,
  type OwnedCardUpdatePayload,
  type UpsertOverlayPayload,
  type WalletCardCreditValue,
  creditsApi,
  currenciesApi,
  scenarioCardCreditApi,
  scenarioCategoryPriorityApi,
  walletSpendApi,
} from '../../api/client'
import type { ResolvedCard } from '../../pages/RoadmapTool/lib/resolveScenarioCards'
import { Modal, ModalHeader, ModalBody, ModalFooter } from '../ui/Modal'
import { Button } from '../ui/Button'
import { Heading } from '../ui/Heading'
import { Badge } from '../ui/Badge'
import { Tabs } from '../ui/Tabs'
import { Field } from '../ui/Field'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
import { formatMoney, today } from '../../utils/format'
import { useCardLibrary } from '../../pages/RoadmapTool/hooks/useCardLibrary'
import { useCreditLibrary } from '../../hooks/useCreditLibrary'
import {
  buildWalletCardFields,
  walletFormToFutureUpdatePayload,
  walletFormToOverlayUpsertPayload,
  walletFormToOwnedUpdatePayload,
} from '../../pages/RoadmapTool/lib/walletCardForm'
import { queryKeys } from '../../lib/queryKeys'

// ---------------------------------------------------------------------------
// Modes
// ---------------------------------------------------------------------------
//
// `owned-base`     — Profile/WalletTab adding/editing the user's actual cards.
//                    Add flow asks ONLY card_id + opening_date. Edit flow
//                    surfaces every override field plus opening_date,
//                    closed_date, product_change_date.
//
// `overlay`        — Roadmap clicking an OWNED card. Library card identity
//                    and opening_date are read-only. Only overlay-able fields
//                    are editable. Save writes a sparse overlay; "Reset to
//                    base values" clears the overlay row.
//
// `scenario-future`— Roadmap clicking a FUTURE card or hitting "Add card".
//                    Full edit access. Acquisition is set by the
//                    product_change_date / pc_from_instance_id pair.

/** Library default credit values for a card, keyed by library_credit_id.
 *  Walks the credit library for entries that natively offer this card and
 *  picks the card-specific value (``card_values[cardId]``) or the credit's
 *  global default (``c.value``) — same logic the future-add hydration uses. */
function ownedCardCreditDefaults(
  creditLibrary: CardCredit[] | undefined,
  cardId: number,
): Record<number, number> {
  const defaults: Record<number, number> = {}
  if (!creditLibrary) return defaults
  for (const c of creditLibrary) {
    if (c.card_ids.includes(cardId)) {
      defaults[c.id] = c.card_values[cardId] ?? c.value ?? 0
    }
  }
  return defaults
}

/** Diff selected credits against library defaults to produce the wallet
 *  override set. Only entries whose value differs from the library default
 *  are included; library credits the user removed (not in selected) are
 *  emitted as ``value=0`` overrides so the calculator treats them as
 *  zeroed-out (not inherited). Custom credits not in the library are
 *  always included. */
/** Per-credit flag override the modal buffers in ``creditFlagEdits``. */
type CreditFlagEdit = {
  excludes_first_year?: boolean
  is_one_time?: boolean
}

/** Library defaults for the two flags, keyed by library_credit_id. Used so
 *  the diff knows when a buffered flag edit matches library (→ no override
 *  needed) vs. genuinely diverges (→ persist as a column override). */
type LibraryFlagDefaults = Record<
  number,
  { excludes_first_year: boolean; is_one_time: boolean }
>

function diffWalletCreditOverrides(
  selected: Record<number, number>,
  libraryDefaults: Record<number, number>,
  flagEdits: Record<number, CreditFlagEdit> = {},
  libraryFlagDefaults: LibraryFlagDefaults = {},
): WalletCardCreditValue[] {
  const out: WalletCardCreditValue[] = []
  for (const [idStr, value] of Object.entries(selected)) {
    const libId = Number(idStr)
    const libDefault = libraryDefaults[libId]
    const valueDiffers =
      libDefault === undefined || Math.abs(value - libDefault) > 1e-6
    const edit = flagEdits[libId]
    const libFlags = libraryFlagDefaults[libId]
    const excludesOverride =
      edit?.excludes_first_year !== undefined &&
      libFlags !== undefined &&
      edit.excludes_first_year !== libFlags.excludes_first_year
        ? edit.excludes_first_year
        : null
    const oneTimeOverride =
      edit?.is_one_time !== undefined &&
      libFlags !== undefined &&
      edit.is_one_time !== libFlags.is_one_time
        ? edit.is_one_time
        : null
    const flagDiffers = excludesOverride !== null || oneTimeOverride !== null
    if (valueDiffers || flagDiffers) {
      out.push({
        library_credit_id: libId,
        value,
        excludes_first_year: excludesOverride,
        is_one_time: oneTimeOverride,
      })
    }
  }
  for (const libIdStr of Object.keys(libraryDefaults)) {
    const libId = Number(libIdStr)
    if (!(libId in selected)) {
      out.push({ library_credit_id: libId, value: 0 })
    }
  }
  return out
}

export type WalletCardModalMode = 'owned-base' | 'overlay' | 'scenario-future'

export interface WalletCardModalProps {
  mode: WalletCardModalMode
  isAddFlow: boolean
  /** Required for `overlay` and `scenario-future`. Ignored for `owned-base`. */
  scenarioId?: number
  /** When editing, the resolved card view. When adding, undefined. */
  resolvedCard?: ResolvedCard
  /** Owned card instance — passed by Profile/WalletTab in owned-base mode. */
  ownedInstance?: CardInstance
  /** Library card_ids already in the wallet (excluded from add picker). */
  existingCardIds: number[]
  /** Instance lookup for the PC picker + "Changed From" / "Changed To" display.
   * `pc_from_instance_id` references CardInstance.id (not library card_id),
   * so the picker stores instance ids and the read display resolves the
   * source via this list. `opening_date` is used so a PC add inherits the
   * source instance's account-open date (PCs preserve `opening_date`).
   * `pc_from_instance_id` + `is_enabled` + `acquisition_type` let the
   * overlay mode locate the future PC card pointing at the current source
   * (so we can show "Changed To" and lock the Card Status toggle).
   * Required for scenario-future + overlay modes. */
  instanceLookup?: {
    instance_id: number
    card_id: number
    card_name: string
    opening_date?: string
    pc_from_instance_id?: number | null
    is_enabled?: boolean
    acquisition_type?: 'opened' | 'product_change'
  }[]
  onClose: () => void

  // Owned-base callbacks
  onAddOwned?: (payload: OwnedCardCreatePayload) => void
  onSaveOwned?: (payload: OwnedCardUpdatePayload) => void
  onDeleteOwned?: (instance: CardInstance) => void

  // Scenario-future callbacks
  onAddFuture?: (payload: FutureCardCreatePayload) => void
  onSaveFuture?: (payload: FutureCardUpdatePayload) => void
  onRemoveFuture?: (resolved: ResolvedCard) => void

  // Overlay callbacks
  onSaveOverlay?: (payload: UpsertOverlayPayload) => void
  onClearOverlay?: () => void

  isLoading: boolean
  /** When false, hides the Categories (priority) tab. Defaults to true for
   * scenario modes; Profile passes false. */
  showCategoryPriorityTab?: boolean
}

export function WalletCardModal(props: WalletCardModalProps) {
  const {
    mode,
    isAddFlow,
    scenarioId,
    resolvedCard,
    ownedInstance,
    existingCardIds,
    instanceLookup,
    onClose,
    onAddOwned,
    onSaveOwned,
    onDeleteOwned,
    onAddFuture,
    onSaveFuture,
    onRemoveFuture,
    onSaveOverlay,
    onClearOverlay,
    isLoading,
    showCategoryPriorityTab,
  } = props

  const isOwnedBase = mode === 'owned-base'
  const isOverlay = mode === 'overlay'
  const isFuture = mode === 'scenario-future'

  // Categories tab availability: Profile (owned-base) drops it; Roadmap modes
  // include it by default.
  const categoryTabEnabled = showCategoryPriorityTab ?? !isOwnedBase

  const { data: cards } = useCardLibrary()
  const queryClient = useQueryClient()

  // ── Form state ──────────────────────────────────────────────────────────
  // For add flows, cardId starts unselected.
  // For edit flows, the resolved card / owned instance pins cardId.
  const editingCardId =
    resolvedCard?.card_id ?? ownedInstance?.card_id ?? null
  const [cardId, setCardId] = useState<number | ''>(editingCardId ?? '')

  // Currency IDs in the issuer ecosystem of the card being edited — used to
  // restrict the credit-currency dropdown so a Chase card can't denominate a
  // credit in Amex MR, etc. Cash currencies are always allowed (the dropdown
  // adds them on top of this set).
  const issuerCurrencyIds = useMemo(() => {
    if (!cards) return new Set<number>()
    const focusCardId = (typeof cardId === 'number' ? cardId : null) ?? editingCardId
    if (focusCardId == null) return new Set<number>()
    const focus = cards.find((c) => c.id === focusCardId)
    if (!focus) return new Set<number>()
    const ids = new Set<number>()
    for (const c of cards) {
      if (c.issuer_id === focus.issuer_id) ids.add(c.currency_id)
    }
    return ids
  }, [cards, cardId, editingCardId])

  const [cardSearch, setCardSearch] = useState('')
  const [cardDropdownOpen, setCardDropdownOpen] = useState(false)
  const cardSearchRef = useRef<HTMLDivElement>(null)
  // PC parent picker (scenario-future mode only). For owned-base / overlay
  // we don't expose the PC chain in the modal.
  const [pcFromInstanceId, setPcFromInstanceId] = useState<number | ''>(
    resolvedCard?.pc_from_instance_id ?? '',
  )
  const [acquisitionMode, setAcquisitionMode] = useState<'open' | 'pc'>(
    (resolvedCard?.product_changed_date ?? ownedInstance?.product_change_date) != null
      ? 'pc'
      : 'open',
  )

  const initialOpeningDate =
    resolvedCard?.added_date ?? ownedInstance?.opening_date ?? today()
  const [openingDate, setOpeningDate] = useState(initialOpeningDate)
  const [productChangeDate, setProductChangeDate] = useState<string>(
    resolvedCard?.product_changed_date ??
      ownedInstance?.product_change_date ??
      '',
  )
  const [closedDate, setClosedDate] = useState<string>(
    resolvedCard?.closed_date ?? ownedInstance?.closed_date ?? '',
  )

  const [subPoints, setSubPoints] = useState('')
  const [subMinSpend, setSubMinSpend] = useState('')
  const [subMonths, setSubMonths] = useState('')
  const [annualBonus, setAnnualBonus] = useState('')
  const [annualFee, setAnnualFee] = useState('')
  const [firstYearFee, setFirstYearFee] = useState('')
  const [secondaryCurrencyRate, setSecondaryCurrencyRate] = useState('')

  // Selected statement credits: library_credit_id -> value
  const [selectedCredits, setSelectedCredits] = useState<Record<number, number>>({})
  // Buffered library-level edits to user-owned credits — { libId: { … } }.
  // Applied on Save; reset on hydrate so closing without saving discards them.
  const [creditFlagEdits, setCreditFlagEdits] = useState<
    Record<
      number,
      {
        excludes_first_year?: boolean
        is_one_time?: boolean
        credit_currency_id?: number | null
      }
    >
  >({})
  const [creditSearch, setCreditSearch] = useState('')
  const [creditOptionsOpen, setCreditOptionsOpen] = useState<number | null>(null)
  const [showCreditPicker, setShowCreditPicker] = useState(false)
  const [priorityCategoryIds, setPriorityCategoryIds] = useState<Set<number>>(new Set())
  const [formError, setFormError] = useState<string | null>(null)
  const [activeTab, setActiveTab] = useState<
    'lifecycle' | 'bonuses' | 'credits' | 'priority'
  >('lifecycle')

  const hydratedKey = useRef<string>('')

  const effectiveCardId = isAddFlow
    ? typeof cardId === 'number' ? cardId : null
    : editingCardId

  // Library lookups
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
    // Auto-link the new credit to the card the user is currently editing so
    // it shows up in this card's default suggestions next time. The credit
    // is user-scoped (owner stamped server-side), but card_ids is the global
    // suggestion link — so it still appears in the search dropdown when
    // editing other cards.
    mutationFn: (credit_name: string) =>
      creditsApi.create({
        credit_name,
        value: 0,
        card_ids: effectiveCardId != null ? [effectiveCardId] : [],
      }),
    onSuccess: (created) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.credits() })
      setSelectedCredits((prev) => ({ ...prev, [created.id]: created.value ?? 0 }))
      setCreditSearch('')
      setShowCreditPicker(false)
    },
    onError: (e: Error) => setFormError(e.message),
  })

  // Existing scenario credit overrides (only for scenario modes — owned-base
  // doesn't carry a scenario context).
  const instanceForCredits =
    isFuture || isOverlay ? resolvedCard?.instance_id ?? null : null
  const { data: existingCreditOverrides, isLoading: creditOverridesLoading } = useQuery({
    queryKey: queryKeys.scenarioCardCredits(scenarioId ?? null, instanceForCredits),
    queryFn: () =>
      scenarioCardCreditApi.list(scenarioId!, instanceForCredits!),
    enabled:
      !isAddFlow &&
      scenarioId != null &&
      instanceForCredits != null &&
      (isFuture || isOverlay),
  })

  // Wallet spend items + scenario priorities (only when category tab is shown).
  const { data: walletSpendItems } = useQuery({
    queryKey: queryKeys.walletSpendItemsSingular(),
    queryFn: () => walletSpendApi.list(),
    enabled: categoryTabEnabled,
  })

  const { data: scenarioCategoryPriorities } = useQuery({
    queryKey: queryKeys.scenarioCategoryPriorities(scenarioId ?? null),
    queryFn: () => scenarioCategoryPriorityApi.list(scenarioId!),
    enabled: categoryTabEnabled && scenarioId != null,
  })

  const priorityClaimsByOther = useMemo(() => {
    const m = new Map<number, number>()
    if (!scenarioCategoryPriorities) return m
    const currentInstanceId = resolvedCard?.instance_id ?? -1
    for (const p of scenarioCategoryPriorities) {
      if (p.card_instance_id !== currentInstanceId) {
        m.set(p.spend_category_id, p.card_instance_id)
      }
    }
    return m
  }, [scenarioCategoryPriorities, resolvedCard?.instance_id])

  const priorityUserCatCount = useMemo(() => {
    if (!walletSpendItems || priorityCategoryIds.size === 0) return 0
    return walletSpendItems.filter((item) => {
      const userCat = item.user_spend_category
      if (!userCat) return false
      const earnCatIds = userCat.mappings.map((m) => m.earn_category_id)
      return earnCatIds.length > 0 && earnCatIds.every((id) => priorityCategoryIds.has(id))
    }).length
  }, [walletSpendItems, priorityCategoryIds])

  // PC destination of the current card: when the modal is on an owned source
  // (overlay mode) that has an enabled future PC card pointing at it, this
  // resolves to that destination's lookup row. Used to lock the Card Status
  // toggle (PC closure can't be edited via overlay; disable the future PC
  // card to "open" the source) and to render a "Changed To" display.
  const pcDestination = useMemo(() => {
    const sourceInstanceId = resolvedCard?.instance_id ?? ownedInstance?.id ?? null
    if (sourceInstanceId == null || !instanceLookup) return null
    return (
      instanceLookup.find(
        (i) =>
          i.pc_from_instance_id === sourceInstanceId &&
          i.is_enabled !== false &&
          i.acquisition_type === 'product_change',
      ) ?? null
    )
  }, [resolvedCard?.instance_id, ownedInstance?.id, instanceLookup])

  // Card Status is locked to "Closed" (at the PC date) while an enabled PC
  // future card targets this card. Applies to any edit mode that surfaces
  // the source side of a PC chain (overlay on owned, or scenario-future on
  // a card that's been chained off of).
  const cardStatusLocked = !isAddFlow && pcDestination != null

  // "Changing to" candidates: same issuer as the selected from-card, not already in wallet.
  // Only relevant when adding a future card with PC acquisition.
  const issuerFilteredCards = useMemo(() => {
    if (!cards) return []
    if (!(isFuture && isAddFlow && acquisitionMode === 'pc')) return cards
    if (!pcFromInstanceId) return []
    // pcFromInstanceId is a CardInstance.id — translate to library card_id
    // via instanceLookup, then look the library card up to get its issuer.
    const fromInst = instanceLookup?.find((i) => i.instance_id === pcFromInstanceId)
    const fromCard = fromInst ? cards.find((c) => c.id === fromInst.card_id) : undefined
    if (!fromCard) return cards
    return cards.filter(
      (c) => c.issuer_id === fromCard.issuer_id && !existingCardIds.includes(c.id),
    )
  }, [cards, isFuture, isAddFlow, acquisitionMode, pcFromInstanceId, existingCardIds, instanceLookup])

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
    [effectiveCardId, cards],
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

  // Hydrate form state on add (after card pick) or edit (after data loads).
  useEffect(() => {
    if (isAddFlow) {
      if (!cardId) {
        hydratedKey.current = ''
        return
      }
      if (!lib) return
      if (!creditLibrary) return
      const key = `add:${cardId}:${acquisitionMode}`
      if (hydratedKey.current === key) return
      hydratedKey.current = key
      // Owned-base add seeds the same defaults as the future-add flow —
      // SUB/fee fields plus library credits in the picker.
      if (isOwnedBase) {
        // eslint-disable-next-line react-hooks/set-state-in-effect -- one-shot hydration from library lookup when card_id changes; refactoring to render-time would require lifting form state into the parent
        setOpeningDate(today())
        setSubPoints(lib.sub_points != null ? String(lib.sub_points) : '')
        setSubMinSpend(lib.sub_min_spend != null ? String(lib.sub_min_spend) : '')
        setSubMonths(lib.sub_months != null ? String(lib.sub_months) : '')
        setAnnualBonus(lib.annual_bonus != null ? String(lib.annual_bonus) : '')
        setAnnualFee(String(lib.annual_fee))
        setFirstYearFee(lib.first_year_fee != null ? String(lib.first_year_fee) : '')
        setSecondaryCurrencyRate(lib.secondary_currency_rate != null ? String(lib.secondary_currency_rate) : '')
        const ownedDefaults: Record<number, number> = {}
        for (const c of creditLibrary) {
          if (c.card_ids.includes(cardId)) {
            ownedDefaults[c.id] = c.card_values[cardId] ?? c.value ?? 0
          }
        }
        setSelectedCredits(ownedDefaults)
        setCreditFlagEdits({})
        setFormError(null)
        return
      }
      // Future add flow: PC zeroes SUB defaults; otherwise inherit library.
      const isPc = acquisitionMode === 'pc'
      setSubPoints(isPc ? '0' : (lib.sub_points != null ? String(lib.sub_points) : ''))
      setSubMinSpend(isPc ? '0' : (lib.sub_min_spend != null ? String(lib.sub_min_spend) : ''))
      setSubMonths(isPc ? '0' : (lib.sub_months != null ? String(lib.sub_months) : ''))
      setAnnualBonus(lib.annual_bonus != null ? String(lib.annual_bonus) : '')
      setAnnualFee(String(lib.annual_fee))
      setFirstYearFee(lib.first_year_fee != null ? String(lib.first_year_fee) : '')
      setSecondaryCurrencyRate(lib.secondary_currency_rate != null ? String(lib.secondary_currency_rate) : '')
      const defaults: Record<number, number> = {}
      for (const c of creditLibrary) {
        if (c.card_ids.includes(cardId)) {
          defaults[c.id] = c.card_values[cardId] ?? c.value ?? 0
        }
      }
      setSelectedCredits(defaults)
      setCreditFlagEdits({})
      setFormError(null)
    } else {
      // Edit flow.
      if (!lib) return
      // Wait for the credit library so the owned-base credits tab can
      // seed library defaults; for scenario modes also wait for the
      // existing scenario credit overrides.
      if (!creditLibrary) return
      if ((isFuture || isOverlay) && existingCreditOverrides === undefined) return
      const editKey = `edit:${mode}:${
        resolvedCard?.instance_id ?? ownedInstance?.id ?? '?'
      }`
      if (hydratedKey.current === editKey) return
      hydratedKey.current = editKey

      if (isOwnedBase && ownedInstance) {
        setOpeningDate(ownedInstance.opening_date)
        setProductChangeDate(ownedInstance.product_change_date ?? '')
        setClosedDate(ownedInstance.closed_date ?? '')
        const effSub = ownedInstance.sub_points ?? lib.sub_points
        setSubPoints(effSub != null ? String(effSub) : '')
        const effMin = ownedInstance.sub_min_spend ?? lib.sub_min_spend
        setSubMinSpend(effMin != null ? String(effMin) : '')
        const effMo = ownedInstance.sub_months ?? lib.sub_months
        setSubMonths(effMo != null ? String(effMo) : '')
        const effBonus = ownedInstance.annual_bonus ?? lib.annual_bonus
        setAnnualBonus(effBonus != null ? String(effBonus) : '')
        const effAf = ownedInstance.annual_fee ?? lib.annual_fee
        setAnnualFee(String(effAf))
        const effFy = ownedInstance.first_year_fee ?? lib.first_year_fee
        setFirstYearFee(effFy != null ? String(effFy) : '')
        const effSecRate = ownedInstance.secondary_currency_rate ?? lib.secondary_currency_rate
        setSecondaryCurrencyRate(effSecRate != null ? String(effSecRate) : '')
        // Seed library defaults, then overlay wallet-level overrides so
        // the credits tab reflects the user's actual valuation. Library
        // credits not overridden flow through with their issuer-stated
        // value; wallet overrides (including value=0 to "remove") win.
        const ownedDefaults: Record<number, number> = {}
        for (const c of creditLibrary ?? []) {
          if (c.card_ids.includes(ownedInstance.card_id)) {
            ownedDefaults[c.id] = c.card_values[ownedInstance.card_id] ?? c.value ?? 0
          }
        }
        const merged: Record<number, number> = { ...ownedDefaults }
        for (const o of ownedInstance.credit_overrides ?? []) {
          merged[o.library_credit_id] = o.value
        }
        setSelectedCredits(merged)
        // Hydrate buffered flag edits from any existing per-instance flag
        // overrides so the credit-options panel checkboxes mirror what's
        // saved. Subsequent toggles keep editing the same buffer.
        const flagBuffer: Record<number, CreditFlagEdit> = {}
        for (const o of ownedInstance.credit_overrides ?? []) {
          const e: CreditFlagEdit = {}
          if (o.excludes_first_year != null) e.excludes_first_year = o.excludes_first_year
          if (o.is_one_time != null) e.is_one_time = o.is_one_time
          if (Object.keys(e).length > 0) flagBuffer[o.library_credit_id] = e
        }
        setCreditFlagEdits(flagBuffer)
        setFormError(null)
        return
      }

      if (resolvedCard) {
        setOpeningDate(resolvedCard.added_date)
        setProductChangeDate(resolvedCard.product_changed_date ?? '')
        setClosedDate(resolvedCard.closed_date ?? '')
        setSubPoints(resolvedCard.sub_points != null ? String(resolvedCard.sub_points) : '')
        setSubMinSpend(resolvedCard.sub_min_spend != null ? String(resolvedCard.sub_min_spend) : '')
        setSubMonths(resolvedCard.sub_months != null ? String(resolvedCard.sub_months) : '')
        setAnnualBonus(resolvedCard.annual_bonus != null ? String(resolvedCard.annual_bonus) : '')
        setAnnualFee(resolvedCard.annual_fee != null ? String(resolvedCard.annual_fee) : String(lib.annual_fee))
        setFirstYearFee(resolvedCard.first_year_fee != null ? String(resolvedCard.first_year_fee) : '')
        setSecondaryCurrencyRate(
          resolvedCard.secondary_currency_rate != null ? String(resolvedCard.secondary_currency_rate) : '',
        )
        // Credits tab inheritance chain (display):
        //   library defaults → wallet overrides → scenario overrides
        // Each later layer wins by library_credit_id. Wallet rows only
        // exist for owned cards (overlay mode); future cards skip that
        // tier. Save-time diffing against (library+wallet) makes scenario
        // overrides sparse — see ``reconcileScenarioOverrides``.
        const baseline = ownedCardCreditDefaults(creditLibrary, resolvedCard.card_id)
        for (const o of resolvedCard.wallet_credit_overrides) {
          baseline[o.library_credit_id] = o.value
        }
        const merged: Record<number, number> = { ...baseline }
        for (const o of existingCreditOverrides ?? []) {
          merged[o.library_credit_id] = o.value
        }
        setSelectedCredits(merged)
        // Hydrate flag edits from existing scenario per-instance overrides
        // and any underlying wallet overrides on the resolved owned card
        // (overlay mode). Scenario flag overrides win when both are set.
        const flagBuffer: Record<number, CreditFlagEdit> = {}
        if (!resolvedCard.is_future) {
          for (const o of resolvedCard.wallet_credit_overrides ?? []) {
            const e: CreditFlagEdit = {}
            const ex = (o as { excludes_first_year?: boolean | null }).excludes_first_year
            const ot = (o as { is_one_time?: boolean | null }).is_one_time
            if (ex != null) e.excludes_first_year = ex
            if (ot != null) e.is_one_time = ot
            if (Object.keys(e).length > 0) flagBuffer[o.library_credit_id] = e
          }
        }
        for (const o of existingCreditOverrides ?? []) {
          const e: CreditFlagEdit = flagBuffer[o.library_credit_id] ?? {}
          if (o.excludes_first_year != null) e.excludes_first_year = o.excludes_first_year
          if (o.is_one_time != null) e.is_one_time = o.is_one_time
          if (Object.keys(e).length > 0) flagBuffer[o.library_credit_id] = e
        }
        setCreditFlagEdits(flagBuffer)
        setFormError(null)
      }
    }
  }, [
    isAddFlow,
    isOwnedBase,
    isFuture,
    isOverlay,
    mode,
    cardId,
    lib,
    resolvedCard,
    ownedInstance,
    creditLibrary,
    existingCreditOverrides,
    acquisitionMode,
  ])

  // Hydrate this card's own priority pins from the scenario-wide list.
  useEffect(() => {
    if (!categoryTabEnabled) return
    if (scenarioCategoryPriorities === undefined) return
    const currentInstanceId = resolvedCard?.instance_id ?? -1
    const mine = new Set<number>()
    for (const p of scenarioCategoryPriorities) {
      if (p.card_instance_id === currentInstanceId) {
        mine.add(p.spend_category_id)
      }
    }
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setPriorityCategoryIds(mine)
  }, [scenarioCategoryPriorities, resolvedCard?.instance_id, categoryTabEnabled])

  function selectPcFromInstance(id: number) {
    setPcFromInstanceId(id)
    setCardId('')
    setCardSearch('')
  }

  function handleAcquisitionModeChange(v: 'open' | 'pc') {
    if (v === acquisitionMode) return
    setAcquisitionMode(v)
    // In edit flows, preserve the user's existing field values across toggles
    // so they can flip without losing data. Only the add flow seeds defaults.
    if (!isAddFlow) return
    if (v === 'pc') {
      setSubPoints('0')
      setSubMinSpend('0')
      setSubMonths('0')
      if (!productChangeDate) setProductChangeDate(openingDate || today())
    } else if (lib) {
      setSubPoints(lib.sub_points != null ? String(lib.sub_points) : '')
      setSubMinSpend(lib.sub_min_spend != null ? String(lib.sub_min_spend) : '')
      setSubMonths(lib.sub_months != null ? String(lib.sub_months) : '')
    }
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

  /** Push buffered LIBRARY-row edits to the backend. After the per-instance
   *  flag override migration, only ``credit_currency_id`` ever lands here —
   *  ``excludes_first_year`` / ``is_one_time`` are persisted as per-instance
   *  overrides via the wallet/scenario credit payloads. The currency edit
   *  affordance is gated to user-owned credits in the UI, so this call is
   *  always permitted by the backend's owner check. */
  async function flushCreditFlagEdits() {
    const entries = Object.entries(creditFlagEdits)
      .map(([idStr, patch]) => {
        const onlyCurrency: { credit_currency_id?: number | null } = {}
        if ('credit_currency_id' in patch) {
          onlyCurrency.credit_currency_id = patch.credit_currency_id
        }
        return [idStr, onlyCurrency] as const
      })
      .filter(([, p]) => Object.keys(p).length > 0)
    if (entries.length === 0) return
    try {
      await Promise.all(
        entries.map(([idStr, patch]) =>
          creditsApi.update(Number(idStr), patch),
        ),
      )
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to save credit settings.'
      setFormError(msg)
      throw e
    }
    queryClient.invalidateQueries({ queryKey: queryKeys.credits() })
  }

  /** Library flag defaults keyed by ``library_credit_id`` for the diff
   *  helper. Built from ``creditLibrary`` so the modal can decide when a
   *  buffered flag matches library (and therefore needs no override row)
   *  vs. genuinely diverges. */
  const libraryFlagDefaults: LibraryFlagDefaults = useMemo(() => {
    const out: LibraryFlagDefaults = {}
    for (const c of creditLibrary ?? []) {
      out[c.id] = {
        excludes_first_year: !!c.excludes_first_year,
        is_one_time: !!c.is_one_time,
      }
    }
    return out
  }, [creditLibrary])

  async function handlePrimary() {
    setFormError(null)

    // All paths build the same form fields. Credits & priority tabs are
    // hidden for owned-base; only lifecycle + bonuses inputs feed the
    // owned-base payload.
    const built = buildWalletCardFields(
      subPoints,
      subMinSpend,
      subMonths,
      annualBonus,
      annualFee,
      firstYearFee,
    )
    if (!built.ok) {
      setFormError(built.message)
      return
    }
    if (closedDate && closedDate < openingDate) {
      setFormError('Closed date must be on or after the opening date.')
      return
    }

    // Owned-base ADD: card_id + opening_date plus the same SUB/bonus/fee
    // override fields the future-add flow sends, plus wallet-level credit
    // overrides (only entries whose value differs from the library
    // default — library updates flow through unchanged credits). Priority
    // pins are scenario-only and stay scenario-only.
    if (isOwnedBase && isAddFlow) {
      if (typeof cardId !== 'number') return
      const secRate = secondaryCurrencyRate.trim() ? Number(secondaryCurrencyRate) : null
      try {
        await flushCreditFlagEdits()
      } catch {
        return
      }
      const overrides = diffWalletCreditOverrides(
        selectedCredits,
        ownedCardCreditDefaults(creditLibrary, cardId),
        creditFlagEdits,
        libraryFlagDefaults,
      )
      onAddOwned?.({
        card_id: cardId,
        opening_date: openingDate,
        sub_points: built.sub_points,
        sub_min_spend: built.sub_min_spend,
        sub_months: built.sub_months,
        annual_bonus: built.annual_bonus,
        annual_fee: built.annual_fee,
        first_year_fee: built.first_year_fee,
        secondary_currency_rate: secRate,
        credit_overrides: overrides,
      })
      return
    }

    // Owned-base EDIT
    if (isOwnedBase && !isAddFlow && ownedInstance && lib) {
      const secRate = secondaryCurrencyRate.trim() ? Number(secondaryCurrencyRate) : null
      const isPc = acquisitionMode === 'pc'
      try {
        await flushCreditFlagEdits()
      } catch {
        return
      }
      const overrides = diffWalletCreditOverrides(
        selectedCredits,
        ownedCardCreditDefaults(creditLibrary, ownedInstance.card_id),
        creditFlagEdits,
        libraryFlagDefaults,
      )
      onSaveOwned?.({
        ...walletFormToOwnedUpdatePayload(
          built,
          lib,
          openingDate,
          closedDate || null,
          isPc ? (productChangeDate || null) : null,
          secRate,
        ),
        credit_overrides: overrides,
      })
      return
    }

    // Scenario-future ADD
    if (isFuture && isAddFlow) {
      if (typeof cardId !== 'number') return
      const secRate = secondaryCurrencyRate.trim() ? Number(secondaryCurrencyRate) : null
      const isPc = acquisitionMode === 'pc'
      // For a PC add, opening_date is inherited from the source instance
      // (PCs preserve the original account-open date). Fall back to the
      // user-entered openingDate if the lookup is missing the field.
      const sourceInst = isPc
        ? instanceLookup?.find((i) => i.instance_id === pcFromInstanceId)
        : undefined
      const effectiveOpeningDate =
        isPc ? (sourceInst?.opening_date ?? openingDate) : openingDate
      const effectivePcDate = isPc ? (productChangeDate || openingDate) : null
      const payload: FutureCardCreatePayload = {
        card_id: cardId,
        opening_date: effectiveOpeningDate,
        product_change_date: effectivePcDate,
        pc_from_instance_id: isPc && typeof pcFromInstanceId === 'number' ? pcFromInstanceId : null,
        sub_points: built.sub_points,
        sub_min_spend: built.sub_min_spend,
        sub_months: built.sub_months,
        annual_bonus: built.annual_bonus,
        annual_fee: built.annual_fee,
        first_year_fee: built.first_year_fee,
        secondary_currency_rate: secRate,
        priority_category_ids: Array.from(priorityCategoryIds),
      }
      try {
        await flushCreditFlagEdits()
      } catch {
        return
      }
      onAddFuture?.(payload)
      return
    }

    // Scenario-future EDIT
    if (isFuture && !isAddFlow && resolvedCard && lib) {
      const secRate = secondaryCurrencyRate.trim() ? Number(secondaryCurrencyRate) : null
      const isPc = acquisitionMode === 'pc'
      const payload = walletFormToFutureUpdatePayload(
        built,
        lib,
        openingDate,
        closedDate || null,
        isPc ? (productChangeDate || openingDate) : null,
        isPc && typeof pcFromInstanceId === 'number' ? pcFromInstanceId : null,
        secRate,
      )

      // Reconcile credits + priorities for scenario modes.
      try {
        await flushCreditFlagEdits()
      } catch {
        return
      }
      await reconcileScenarioOverrides(
        scenarioId!,
        resolvedCard.instance_id,
        existingCreditOverrides ?? [],
        selectedCredits,
        scenarioCreditBaseline(resolvedCard),
        Array.from(priorityCategoryIds),
      )
      onSaveFuture?.(payload)
      return
    }

    // Overlay EDIT (owned card, scenario context)
    if (isOverlay && resolvedCard && lib) {
      const secRate = secondaryCurrencyRate.trim() ? Number(secondaryCurrencyRate) : null
      const baseline = {
        // Resolved card already represents (instance ?? library), so when
        // computing diffs treat the resolved values as the baseline. Overlay
        // upsert sends only the values the user changed.
        sub_points: resolvedCard.sub_points,
        sub_min_spend: resolvedCard.sub_min_spend,
        sub_months: resolvedCard.sub_months,
        annual_bonus: resolvedCard.annual_bonus,
        annual_fee: resolvedCard.annual_fee,
        first_year_fee: resolvedCard.first_year_fee,
        secondary_currency_rate: resolvedCard.secondary_currency_rate,
        closed_date: resolvedCard.closed_date,
      }
      const payload = walletFormToOverlayUpsertPayload(
        built,
        baseline,
        closedDate || null,
        secRate,
        // Don't toggle is_enabled from this modal — keep null.
        null,
      )
      try {
        await flushCreditFlagEdits()
      } catch {
        return
      }
      await reconcileScenarioOverrides(
        scenarioId!,
        resolvedCard.instance_id,
        existingCreditOverrides ?? [],
        selectedCredits,
        scenarioCreditBaseline(resolvedCard),
        Array.from(priorityCategoryIds),
      )
      onSaveOverlay?.(payload)
      return
    }
  }

  /** Diff selected credits + category priorities against existing scenario
   * rows and apply via the per-instance scenario APIs.
   *
   * ``baseline`` is the inherited credit set the scenario would see
   * without any ScenarioCardCredit rows: library defaults for future
   * cards, library + wallet overrides for owned cards in overlay mode.
   * Selected values matching the baseline don't generate scenario rows
   * (and any existing override matching the baseline is deleted), so
   * library/wallet updates flow through unchanged credits. */
  async function reconcileScenarioOverrides(
    sid: number,
    instanceId: number,
    existing: {
      library_credit_id: number
      value: number
      excludes_first_year?: boolean | null
      is_one_time?: boolean | null
    }[],
    selected: Record<number, number>,
    baseline: Record<number, number>,
    priorityIds: number[],
  ) {
    const desired = diffWalletCreditOverrides(
      selected,
      baseline,
      creditFlagEdits,
      libraryFlagDefaults,
    )
    const desiredByLibId = new Map(desired.map((d) => [d.library_credit_id, d]))
    const existingByLibId = new Map(existing.map((o) => [o.library_credit_id, o]))
    const creditOps: Promise<unknown>[] = []
    const flagsEqual = (
      a: boolean | null | undefined,
      b: boolean | null | undefined,
    ) => (a ?? null) === (b ?? null)
    for (const [libId, d] of desiredByLibId) {
      const ex = existingByLibId.get(libId)
      const valueChanged = !ex || Math.abs(ex.value - d.value) > 1e-6
      const excludesChanged =
        !ex || !flagsEqual(ex.excludes_first_year, d.excludes_first_year)
      const oneTimeChanged =
        !ex || !flagsEqual(ex.is_one_time, d.is_one_time)
      if (valueChanged || excludesChanged || oneTimeChanged) {
        creditOps.push(
          scenarioCardCreditApi.upsert(sid, instanceId, libId, {
            value: d.value,
            excludes_first_year: d.excludes_first_year ?? null,
            is_one_time: d.is_one_time ?? null,
          }),
        )
      }
    }
    for (const [libId] of existingByLibId) {
      if (!desiredByLibId.has(libId)) {
        creditOps.push(scenarioCardCreditApi.delete(sid, instanceId, libId))
      }
    }
    const priorityOp = scenarioCategoryPriorityApi
      .set(sid, instanceId, priorityIds)
      .catch((e: Error) => {
        throw new Error(e.message || 'Failed to save category priorities.')
      })
    try {
      await Promise.all([...creditOps, priorityOp])
    } catch (e) {
      const msg = e instanceof Error ? e.message : 'Failed to save overrides.'
      setFormError(msg)
      throw e
    }
    queryClient.invalidateQueries({
      queryKey: queryKeys.scenarioCardCredits(sid, instanceId),
    })
    queryClient.invalidateQueries({
      queryKey: queryKeys.scenarioCategoryPriorities(sid),
    })
  }

  /** Build the credit baseline a scenario would see without explicit
   *  ScenarioCardCredit rows — library defaults plus wallet overrides
   *  for owned cards. Future cards skip the wallet tier. */
  function scenarioCreditBaseline(rc: ResolvedCard): Record<number, number> {
    const baseline = ownedCardCreditDefaults(creditLibrary, rc.card_id)
    if (!rc.is_future) {
      for (const o of rc.wallet_credit_overrides) {
        baseline[o.library_credit_id] = o.value
      }
    }
    return baseline
  }

  const formDisabled = !lib

  // Title
  const cardName = resolvedCard?.card_name ?? ownedInstance?.card_name
  const cardIdForTitle = resolvedCard?.card_id ?? ownedInstance?.card_id
  const title =
    isAddFlow
      ? isOwnedBase
        ? 'Add Card to Wallet'
        : 'Add Future Card'
      : cardName ?? `Card #${cardIdForTitle ?? ''}`

  // Tabs visible
  const cardSelected = !isAddFlow || cardId !== ''

  // If the user deselects a card while on a card-dependent tab, snap back to Lifecycle.
  useEffect(() => {
    if (!cardSelected && activeTab !== 'lifecycle') {
      // eslint-disable-next-line react-hooks/set-state-in-effect -- sync active tab to valid state when card selection changes; render-time derivation would lose user intent on re-select
      setActiveTab('lifecycle')
    }
  }, [cardSelected, activeTab])

  // Priority tab is gated by ``categoryTabEnabled`` (false for owned-base
  // since priority pins are scenario-scoped).
  const tabOrder: readonly typeof activeTab[] = (
      [
        'lifecycle',
        ...(cardSelected ? (['bonuses', 'credits'] as const) : []),
        ...(cardSelected && categoryTabEnabled ? (['priority'] as const) : []),
      ] as const)
  const currentTabIndex = tabOrder.indexOf(activeTab)
  const hasNextTab = currentTabIndex !== -1 && currentTabIndex < tabOrder.length - 1

  const saveDisabled =
    isAddFlow
      ? (isFuture && acquisitionMode === 'pc')
        ? !pcFromInstanceId || !cardId || isLoading
        : !cardId || isLoading
      : isLoading || !(resolvedCard || ownedInstance)

  const isOverlayContext = isOverlay
  const onDeleteHandler =
    !isAddFlow && isOwnedBase && ownedInstance && onDeleteOwned
      ? () => onDeleteOwned(ownedInstance)
      : !isAddFlow && isFuture && resolvedCard && onRemoveFuture
        ? () => onRemoveFuture(resolvedCard)
        : null

  return (
    <Modal
      open={true}
      onClose={onClose}
      size="md"
      ariaLabel={title}
      className="flex flex-col h-[640px] max-h-[90vh]"
    >
      {/* ── Fixed header ── */}
      <ModalHeader>
        <div className="flex items-start gap-3">
          <div className="min-w-0 flex-1">
            <Heading level={3}>{title}</Heading>
            <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
              {lib?.network_tier && (
                <Badge tone="neutral">{lib.network_tier.name}</Badge>
              )}
              {lib?.issuer && (
                <Badge tone="neutral">{lib.issuer.name}</Badge>
              )}
              {!isAddFlow && (
                isOverlayContext ? (
                  <Badge tone="warn">Owned · scenario edit</Badge>
                ) : isFuture ? (
                  <Badge tone="accent">Future</Badge>
                ) : (
                  <Badge tone="neutral">Owned</Badge>
                )
              )}
            </div>
          </div>
          {onDeleteHandler && (
            <button
              type="button"
              disabled={isLoading}
              onClick={onDeleteHandler}
              className="shrink-0 w-8 h-8 inline-flex items-center justify-center rounded-md text-ink-faint hover:text-neg hover:bg-neg/10 disabled:opacity-50 transition-colors"
              title={isFuture ? 'Delete future card' : 'Delete card'}
              aria-label="Delete card"
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>
          )}
        </div>
      </ModalHeader>

      {/* ── Tab bar ── */}
      {(isAddFlow || lib) && (
        <div className="flex-shrink-0 px-5">
          <Tabs
            items={[
              { id: 'lifecycle' as const, label: 'Lifecycle' },
              ...(cardSelected
                ? [
                    { id: 'bonuses' as const, label: 'Bonuses & Fees' },
                    {
                      id: 'credits' as const,
                      label: (
                        <>
                          Credits
                          {Object.keys(selectedCredits).length > 0 && (
                            <span className="ml-1.5 text-[10.5px] font-medium bg-surface-2 text-ink-faint px-1.5 py-0.5 rounded-full tnum-mono">
                              {Object.keys(selectedCredits).length}
                            </span>
                          )}
                        </>
                      ),
                    },
                  ]
                : []),
              ...(cardSelected && categoryTabEnabled
                ? [
                    {
                      id: 'priority' as const,
                      label: (
                        <>
                          Categories
                          {priorityUserCatCount > 0 && (
                            <span className="ml-1.5 text-[10.5px] font-medium bg-surface-2 text-ink-faint px-1.5 py-0.5 rounded-full tnum-mono">
                              {priorityUserCatCount}
                            </span>
                          )}
                        </>
                      ),
                    },
                  ]
                : []),
            ]}
            active={activeTab}
            onChange={(id) => setActiveTab(id as typeof activeTab)}
          />
        </div>
      )}

      {/* ── Body ── */}
      <ModalBody className={`flex-1 min-h-0 flex flex-col ${activeTab === 'credits' ? '!pb-0' : ''}`}>
        {!isAddFlow && !lib ? (
          <p className="text-sm text-ink-muted py-8 text-center">Loading card…</p>
        ) : (
          <div className="flex-1 min-h-0 flex flex-col">
            {activeTab === 'lifecycle' && (
              <div className="space-y-3">
                <p className="text-[11px] text-ink-faint -mx-6 px-6 pb-2 border-b border-divider/60">
                  When and how this card entered the wallet, and whether it's still active.
                </p>

                {/* Acquisition toggle + matching date input. The toggle is hidden
                    for owned-base ADD (implicit "open new") and overlay
                    (read-only); those modes show just the Opening Date. */}
                {(isFuture || (isOwnedBase && !isAddFlow)) ? (
                  <div className="space-y-3">
                    <div className="space-y-1.5">
                      <p className="text-xs font-medium text-ink-muted">Acquisition</p>
                      <div role="radiogroup" aria-label="Acquisition" className="space-y-2">
                        {([
                          {
                            v: 'open' as const,
                            label: 'Account Opening',
                            desc: 'New card from this issuer. Counts toward 5/24 and other velocity rules.',
                          },
                          {
                            v: 'pc' as const,
                            label: 'Product Change',
                            desc: "Switching from another card. Account number is preserved; doesn't count as a new app.",
                          },
                        ]).map(({ v, label, desc }) => {
                          const selected = acquisitionMode === v
                          return (
                            <button
                              key={v}
                              type="button"
                              role="radio"
                              aria-checked={selected}
                              onClick={() => handleAcquisitionModeChange(v)}
                              className={`w-full text-left flex items-start gap-3 px-3 py-3 rounded-lg border transition-colors ${
                                selected
                                  ? 'border-accent bg-accent-soft'
                                  : 'border-divider hover:border-divider-strong bg-surface'
                              }`}
                            >
                              <span
                                aria-hidden
                                className={`mt-0.5 shrink-0 w-3.5 h-3.5 rounded-full border transition-colors ${
                                  selected ? 'border-accent bg-accent' : 'border-divider-strong'
                                }`}
                              />
                              <span className="min-w-0">
                                <span className={`block text-sm font-medium ${selected ? 'text-accent' : 'text-ink'}`}>
                                  {label}
                                </span>
                                <span className="block text-[11px] text-ink-faint mt-0.5">{desc}</span>
                              </span>
                            </button>
                          )
                        })}
                      </div>
                    </div>
                    <Field label={acquisitionMode === 'pc' ? 'Product Change Date' : 'Opening Date'} required>
                      <Input
                        type="date"
                        value={acquisitionMode === 'pc' ? productChangeDate : openingDate}
                        onChange={(e) =>
                          acquisitionMode === 'pc'
                            ? setProductChangeDate(e.target.value)
                            : setOpeningDate(e.target.value)
                        }
                      />
                    </Field>
                  </div>
                ) : (
                  <Field label="Opening Date" required>
                    <Input
                      type="date"
                      disabled={isOverlay}
                      value={openingDate}
                      onChange={(e) => setOpeningDate(e.target.value)}
                    />
                  </Field>
                )}

                {/* Changing From: editable picker in scenario-future ADD (PC),
                    read-only "Changed From" display in scenario-future EDIT
                    when the source is already pinned. */}
                {isFuture && acquisitionMode === 'pc' && isAddFlow && (
                  <Field label="Changing From" required>
                    <Select
                      value={pcFromInstanceId}
                      onChange={(e) => e.target.value ? selectPcFromInstance(Number(e.target.value)) : setPcFromInstanceId('')}
                    >
                      <option value="">Select a wallet card…</option>
                      {(instanceLookup ?? []).map((inst) => (
                        <option key={inst.instance_id} value={inst.instance_id}>
                          {inst.card_name}
                        </option>
                      ))}
                    </Select>
                  </Field>
                )}

                {!isAddFlow && isFuture && acquisitionMode === 'pc' && pcFromInstanceId !== '' && (() => {
                  const fromInst = instanceLookup?.find(
                    (i) => i.instance_id === pcFromInstanceId,
                  )
                  return (
                    <div>
                      <label className="text-xs text-ink-muted mb-1 block">
                        Changed From
                      </label>
                      <div className="w-full bg-surface/60 border border-divider text-ink text-sm px-3 py-2 rounded-lg">
                        {fromInst?.card_name ?? `Instance #${pcFromInstanceId}`}
                      </div>
                    </div>
                  )
                })()}

                {/* "Changed To" display on the source side: shown when an
                    enabled future PC card in the scenario points at this
                    owned card. Pairs with the disabled Card Status toggle
                    below. */}
                {pcDestination != null && (
                  <div>
                    <label className="text-xs text-ink-muted mb-1 block">
                      Changed To
                    </label>
                    <div className="w-full bg-surface/60 border border-divider text-ink text-sm px-3 py-2 rounded-lg">
                      {pcDestination.card_name}
                    </div>
                  </div>
                )}

                {/* Card library search (add flow only). */}
                {isAddFlow && (
                  <div ref={cardSearchRef} className="relative">
                    <label className="text-xs text-ink-muted mb-1 block">
                      {isFuture && acquisitionMode === 'pc' ? 'Changing To *' : 'Card *'}
                    </label>
                    <input
                      type="text"
                      placeholder="Search cards…"
                      disabled={isFuture && acquisitionMode === 'pc' && !pcFromInstanceId}
                      className="w-full bg-surface-2 border border-divider text-ink text-sm px-3 py-2 rounded-lg outline-none focus:border-accent disabled:opacity-50"
                      value={cardSearch}
                      onChange={(e) => handleCardSearchChange(e.target.value)}
                      onFocus={() => setCardDropdownOpen(true)}
                    />
                    {cardDropdownOpen && (
                      <ul className="absolute z-10 mt-1 w-full bg-surface border border-divider rounded-lg shadow-xl max-h-48 overflow-y-auto">
                        {searchedCards.length === 0 ? (
                          <li className="px-3 py-2 text-sm text-ink-faint">No cards found</li>
                        ) : (
                          searchedCards.map((c) => (
                            <li
                              key={c.id}
                              onPointerDown={(e) => { e.preventDefault(); selectCard(c.id, c.name) }}
                              className={`px-3 py-2 text-sm cursor-pointer flex items-center gap-2 ${
                                cardId === c.id
                                  ? 'bg-accent text-page'
                                  : 'text-ink hover:bg-surface-2'
                              }`}
                            >
                              <span className="flex-1 min-w-0 truncate">{c.name}</span>
                              {c.network_tier && (
                                <span className={`text-[10px] font-medium shrink-0 rounded px-1.5 py-0.5 border ${
                                  cardId === c.id
                                    ? 'bg-accent/60 text-page border-accent/50'
                                    : 'bg-surface-2 text-ink-muted border-divider'
                                }`}>
                                  {c.network_tier.name}
                                </span>
                              )}
                            </li>
                          ))
                        )}
                      </ul>
                    )}
                    {isFuture && acquisitionMode === 'pc' && pcFromInstanceId && (
                      <p className="text-[11px] text-ink-faint mt-1">Showing same-issuer cards</p>
                    )}
                  </div>
                )}

                {/* Card status / Closed date (edit only) */}
                {!isAddFlow && (
                  <div className="grid grid-cols-2 gap-3 items-start">
                    <div>
                      <label className="text-xs text-ink-muted mb-1 block">Card Status</label>
                      <div
                        role="radiogroup"
                        className={`flex flex-col bg-surface-2/30 border border-divider rounded-lg overflow-hidden ${
                          cardStatusLocked ? 'opacity-60' : ''
                        }`}
                        title={
                          cardStatusLocked
                            ? `Closed by product change to ${pcDestination?.card_name}`
                            : undefined
                        }
                      >
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
                              disabled={cardStatusLocked}
                              onClick={() => {
                                if (cardStatusLocked) return
                                if (v === 'active') setClosedDate('')
                                else if (!closedDate) setClosedDate(today())
                              }}
                              className={`w-full flex items-center gap-2.5 px-3 py-2 text-xs transition-colors ${
                                i > 0 ? 'border-t border-divider/60' : ''
                              } ${
                                selected
                                  ? 'bg-surface-2 text-ink'
                                  : 'text-ink-muted hover:bg-surface-2/60'
                              } ${cardStatusLocked ? 'cursor-not-allowed' : ''}`}
                            >
                              <span className={`w-3.5 h-3.5 rounded-full border-2 flex items-center justify-center shrink-0 transition-colors ${
                                selected ? 'border-accent' : 'border-divider'
                              }`}>
                                {selected && <span className="w-1.5 h-1.5 bg-accent rounded-full" />}
                              </span>
                              {label}
                            </button>
                          )
                        })}
                      </div>
                      {cardStatusLocked && (
                        <p className="text-[11px] text-ink-faint mt-1">
                          Closed by product change. Disable the new card to keep this one open.
                        </p>
                      )}
                    </div>
                    {closedDate && (
                      <Field label="Closed Date">
                        <Input
                          type="date"
                          min={openingDate}
                          disabled={cardStatusLocked}
                          value={closedDate}
                          onChange={(e) => setClosedDate(e.target.value)}
                        />
                      </Field>
                    )}
                  </div>
                )}
              </div>
            )}

            {activeTab === 'bonuses' && (
              <div className="space-y-3">
                <p className="text-[11px] text-ink-faint -mx-6 px-6 pb-2 border-b border-divider/60">
                  Sign-up / product-change bonus, annual bonus, and fees.
                </p>

                <div className="grid grid-cols-3 gap-3">
                  <Field label={acquisitionMode === 'pc' ? 'PC Bonus (Pts)' : 'SUB Bonus (Pts)'}>
                    <Input
                      type="number"
                      min={0}
                      disabled={formDisabled}
                      value={subPoints}
                      onChange={(e) => setSubPoints(e.target.value)}
                    />
                  </Field>
                  <Field label={acquisitionMode === 'pc' ? 'PC Min Spend ($)' : 'SUB Min Spend ($)'}>
                    <Input
                      type="number"
                      min={0}
                      disabled={formDisabled}
                      value={subMinSpend}
                      onChange={(e) => setSubMinSpend(e.target.value)}
                    />
                  </Field>
                  <Field label={acquisitionMode === 'pc' ? 'PC Spend Months' : 'SUB Spend Months'}>
                    <Input
                      type="number"
                      min={0}
                      disabled={formDisabled}
                      value={subMonths}
                      onChange={(e) => setSubMonths(e.target.value)}
                    />
                  </Field>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <Field label="Annual Bonus (Pts)">
                    <Input
                      type="number"
                      min={0}
                      disabled={formDisabled}
                      placeholder="Optional"
                      value={annualBonus}
                      onChange={(e) => setAnnualBonus(e.target.value)}
                    />
                  </Field>
                  <Field label="Annual Fee ($)">
                    <Input
                      type="number"
                      min={0}
                      step="0.01"
                      disabled={formDisabled}
                      value={annualFee}
                      onChange={(e) => setAnnualFee(e.target.value)}
                    />
                  </Field>
                </div>

                <div className="grid grid-cols-2 gap-3">
                  <Field label="First-Year Fee ($)">
                    <Input
                      type="number"
                      min={0}
                      step="0.01"
                      disabled={formDisabled}
                      placeholder="Optional"
                      value={firstYearFee}
                      onChange={(e) => setFirstYearFee(e.target.value)}
                    />
                  </Field>
                </div>

              </div>
            )}

            {activeTab === 'credits' && lib && (
              <div className="-mx-6 flex-1 min-h-0 flex flex-col">
                <div className="flex-1 min-h-0 flex flex-col">
                  <p className="text-[11px] text-ink-faint px-6 pb-2 border-b border-divider/60">
                    Input your valuation of each credit.
                  </p>
                  {creditLibraryLoading || creditOverridesLoading ? (
                    <div className="flex items-center gap-2 px-6 py-3 text-xs text-ink-muted">
                      <svg className="w-3.5 h-3.5 animate-spin text-accent" fill="none" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z" />
                      </svg>
                      Loading credits…
                    </div>
                  ) : Object.keys(selectedCredits).length === 0 ? (
                    <p className="text-xs text-ink-faint px-6 py-3">
                      No credits selected. Add credits this card grants from the picker below.
                    </p>
                  ) : (
                    <ul className="divide-y divide-divider/40 flex-1 min-h-0 overflow-y-auto">
                      {Object.entries(selectedCredits).map(([idStr, value]) => {
                        const libId = Number(idStr)
                        const lc = creditLibraryById.get(libId)
                        const isExpanded = creditOptionsOpen === libId
                        // Pending currency edit (buffered until Save) drives the $/pts
                        // affordances so the input UI matches the user's pick instantly.
                        const pendingEdits = creditFlagEdits[libId]
                        const effCurrencyIdForRow =
                          'credit_currency_id' in (pendingEdits ?? {})
                            ? pendingEdits!.credit_currency_id
                            : lc?.credit_currency_id ?? null
                        return (
                          <li key={libId}>
                            <div className="flex items-center justify-between gap-2 px-6 py-2 text-sm">
                              <button
                                type="button"
                                onClick={() => setCreditOptionsOpen(isExpanded ? null : libId)}
                                className="text-ink-faint hover:text-ink hover:bg-surface-2 rounded p-0.5 shrink-0 transition-colors"
                              >
                                <svg
                                  className={`w-3 h-3 transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                                  fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2.5}
                                >
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M9 5l7 7-7 7" />
                                </svg>
                              </button>
                              <span className="text-ink truncate min-w-0 flex-1">
                                {lc?.credit_name ?? `Credit #${libId}`}
                              </span>
                              <div className="flex items-center gap-1.5 shrink-0">
                                <div className="relative">
                                  {(() => {
                                    const cur = effCurrencyIdForRow != null ? currencies?.find(c => c.id === effCurrencyIdForRow) : null
                                    const isCash = !cur || cur.reward_kind === 'cash'
                                    return isCash ? (
                                      <span className="absolute left-2 top-1/2 -translate-y-1/2 text-xs text-ink-faint pointer-events-none">$</span>
                                    ) : null
                                  })()}
                                  <input
                                    type="number"
                                    min={0}
                                    step={(() => {
                                      const cur = effCurrencyIdForRow != null ? currencies?.find(c => c.id === effCurrencyIdForRow) : null
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
                                    className={`w-24 bg-surface-2 border border-divider text-ink text-xs tabular-nums pr-2 py-1 rounded outline-none focus:border-accent placeholder:text-ink-faint ${
                                      (() => {
                                        const cur = effCurrencyIdForRow != null ? currencies?.find(c => c.id === effCurrencyIdForRow) : null
                                        return (!cur || cur.reward_kind === 'cash') ? 'pl-5' : 'pl-2'
                                      })()
                                    }`}
                                  />
                                </div>
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
                                  className="text-ink-faint hover:text-neg hover:bg-neg/10 p-0.5 rounded transition-colors"
                                  title="Remove credit"
                                >
                                  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                                  </svg>
                                </button>
                              </div>
                            </div>
                            {isExpanded && (() => {
                              // ``After Year 1`` / ``One-Time`` are per-instance overrides —
                              // any user can flip them on any credit and the change persists
                              // as a column override on WalletCardCredit / ScenarioCardCredit
                              // (NULL on the row inherits the library default). Currency is
                              // intentionally library-only and stays gated to user-owned
                              // credits. Edits buffer in ``creditFlagEdits`` and only persist
                              // on Save.
                              const isUserOwned = lc?.owner_user_id != null
                              const edits = creditFlagEdits[libId]
                              const effExcludesFirstYear =
                                edits?.excludes_first_year ?? lc?.excludes_first_year ?? false
                              const effIsOneTime =
                                edits?.is_one_time ?? lc?.is_one_time ?? false
                              const effCurrencyId =
                                'credit_currency_id' in (edits ?? {})
                                  ? edits!.credit_currency_id
                                  : lc?.credit_currency_id ?? null
                              return (
                              <div className="flex items-center gap-3 px-6 pb-2.5 pt-0.5 text-xs text-ink-muted">
                                <label className="flex items-center gap-1.5 select-none cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={effExcludesFirstYear}
                                    onChange={() => {
                                      if (!lc) return
                                      setCreditFlagEdits((prev) => ({
                                        ...prev,
                                        [libId]: {
                                          ...prev[libId],
                                          excludes_first_year: !effExcludesFirstYear,
                                        },
                                      }))
                                    }}
                                    className="accent-warn w-3 h-3"
                                  />
                                  <span>After Year 1</span>
                                </label>
                                <label className="flex items-center gap-1.5 select-none cursor-pointer">
                                  <input
                                    type="checkbox"
                                    checked={effIsOneTime}
                                    onChange={() => {
                                      if (!lc) return
                                      setCreditFlagEdits((prev) => ({
                                        ...prev,
                                        [libId]: {
                                          ...prev[libId],
                                          is_one_time: !effIsOneTime,
                                        },
                                      }))
                                    }}
                                    className="accent-accent w-3 h-3"
                                  />
                                  <span>One-Time</span>
                                </label>
                                <div className="flex-1" />
                                <select
                                  disabled={!isUserOwned}
                                  value={effCurrencyId ?? 'null'}
                                  onChange={(e) => {
                                    if (!lc || !isUserOwned) return
                                    const cid = e.target.value === 'null' ? null : Number(e.target.value)
                                    setCreditFlagEdits((prev) => ({
                                      ...prev,
                                      [libId]: {
                                        ...prev[libId],
                                        credit_currency_id: cid,
                                      },
                                    }))
                                  }}
                                  className="w-60 bg-surface-2 border border-divider text-ink text-xs px-2 py-1 rounded outline-none focus:border-accent disabled:opacity-60 disabled:cursor-not-allowed truncate"
                                >
                                  {(currencies ?? []).filter((cur) => {
                                    // Cash + every currency in the card issuer's ecosystem.
                                    if (cur.reward_kind === 'cash') return true
                                    return issuerCurrencyIds.has(cur.id)
                                  }).map((cur) => (
                                    <option key={cur.id} value={cur.id}>{cur.name}</option>
                                  ))}
                                </select>
                              </div>
                              )
                            })()}
                          </li>
                        )
                      })}
                    </ul>
                  )}
                  <div className="px-6 py-2 border-t border-divider/60">
                    {!showCreditPicker ? (
                      <button
                        type="button"
                        onClick={() => setShowCreditPicker(true)}
                        className="w-full flex items-center justify-center gap-1.5 py-1.5 text-xs text-accent hover:text-accent hover:bg-surface-2/40 rounded transition-colors"
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
                            onChange={(e) => setCreditSearch(e.target.value)}
                            placeholder="Search credits…"
                            className="flex-1 bg-surface-2 border border-divider text-ink text-xs px-2 py-1.5 rounded outline-none focus:border-accent"
                            autoFocus
                          />
                          <button
                            type="button"
                            onClick={() => {
                              setShowCreditPicker(false)
                              setCreditSearch('')
                            }}
                            className="p-1 text-ink-faint hover:text-ink hover:bg-surface-2 rounded transition-colors"
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
                          // Create row is always the first row in the dropdown so
                          // users know the option exists. It's disabled until the
                          // user has typed a name not already in the library.
                          const canCreate = trimmed.length > 0 && !exactExists
                          return (
                            <ul className="max-h-40 overflow-y-auto rounded border border-divider divide-y divide-divider/60">
                              <li>
                                <button
                                  type="button"
                                  disabled={!canCreate || createCreditMutation.isPending}
                                  onClick={() => canCreate && createCreditMutation.mutate(trimmed)}
                                  className="w-full flex items-center gap-2 px-2 py-1.5 text-xs text-accent hover:bg-surface-2/60 disabled:text-ink-faint disabled:hover:bg-transparent disabled:cursor-not-allowed"
                                >
                                  <span className="shrink-0">+</span>
                                  <span className="truncate min-w-0">
                                    {createCreditMutation.isPending
                                      ? `Creating "${trimmed}"…`
                                      : trimmed.length === 0
                                        ? 'Create New Credit (Type in search)'
                                        : exactExists
                                          ? `"${trimmed}" already exists`
                                          : `Create "${trimmed}"`}
                                  </span>
                                </button>
                              </li>
                              {matches.length === 0 ? (
                                <li>
                                  <p className="text-[11px] text-ink-faint px-2 py-1.5">
                                    {trimmed.length === 0
                                      ? 'No more credits to add.'
                                      : 'No matching credits.'}
                                  </p>
                                </li>
                              ) : (
                                matches.map((c) => (
                                  <li key={c.id}>
                                    <button
                                      type="button"
                                      onClick={() => {
                                        const cardVal = effectiveCardId ? (c.card_values[effectiveCardId] ?? c.value ?? 0) : (c.value ?? 0)
                                        setSelectedCredits((prev) => ({
                                          ...prev,
                                          [c.id]: cardVal,
                                        }))
                                        setCreditSearch('')
                                        setShowCreditPicker(false)
                                      }}
                                      className="w-full flex items-center justify-between gap-2 px-2 py-1.5 text-xs text-ink hover:bg-surface-2/60"
                                    >
                                      <span className="truncate min-w-0">{c.credit_name}</span>
                                      <span className="text-ink-faint tabular-nums shrink-0">
                                        {formatMoney(effectiveCardId ? (c.card_values[effectiveCardId] ?? c.value ?? 0) : (c.value ?? 0))}
                                      </span>
                                    </button>
                                  </li>
                                ))
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

            {activeTab === 'priority' && lib && categoryTabEnabled && (
              <div className="flex-1 min-h-0 flex flex-col">
                <p className="text-[11px] text-ink-faint -mx-6 px-6 pb-2 border-b border-divider/60 mb-3">
                  Force category spend onto this card only. Does not affect SUB spend allocation.
                </p>
                {!walletSpendItems || walletSpendItems.length === 0 ? (
                  <p className="text-xs text-ink-faint py-1">
                    No wallet spend categories yet.
                  </p>
                ) : (
                  <ul className="grid grid-cols-2 gap-x-2 gap-y-1 auto-rows-min flex-1 min-h-0 overflow-y-auto border border-divider rounded-lg p-2">
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
                                  ? 'text-ink-faint cursor-not-allowed'
                                  : 'text-ink cursor-pointer hover:bg-surface-2/40'
                              }`}
                            >
                              <input
                                type="checkbox"
                                className="accent-accent"
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
                                <span className="text-[10px] text-ink-faint shrink-0">
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
              <p className="text-xs text-neg bg-neg/10 border border-neg/50 rounded-lg mx-0 mt-3 px-3 py-2">
                {formError}
              </p>
            )}
          </div>
        )}
      </ModalBody>

      {/* ── Footer ── */}
      <ModalFooter>
        {!isAddFlow && isOverlayContext && onClearOverlay && (
          <Button
            type="button"
            variant="ghost"
            size="sm"
            disabled={isLoading || !resolvedCard?.is_overlay_modified}
            onClick={onClearOverlay}
            className="!text-warn hover:!text-warn"
          >
            Reset overlay
          </Button>
        )}
        <div className="flex-1" />
        <Button
          type="button"
          variant="secondary"
          size="sm"
          disabled={isLoading}
          onClick={onClose}
        >
          Cancel
        </Button>
        {isAddFlow && hasNextTab ? (
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={isLoading}
            onClick={() => setActiveTab(tabOrder[currentTabIndex + 1])}
          >
            Next →
          </Button>
        ) : (
          <Button
            type="button"
            variant="primary"
            size="sm"
            disabled={saveDisabled}
            loading={isLoading}
            onClick={() => void handlePrimary()}
          >
            {isAddFlow ? 'Add card' : 'Save changes'}
          </Button>
        )}
      </ModalFooter>
    </Modal>
  )
}
