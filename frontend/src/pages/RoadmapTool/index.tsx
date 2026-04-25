import { useMutation, useQueries, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import {
  walletsApi,
  walletCardCategoryPriorityApi,
  walletCardCreditApi,
  walletCppApi,
  walletPortalShareApi,
  walletSpendItemsApi,
  type AddCardToWalletPayload,
  type CurrencyRead,
  type RoadmapResponse,
  type RoadmapRuleStatus,
  type UpdateWalletCardPayload,
  type Wallet,
  type WalletCard,
  type WalletCardCategoryPriority,
  type WalletCardCreditOverride,
  type WalletPortalShare,
  type WalletResultResponse,
  type WalletSpendItem,
} from '../../api/client'
import { today } from '../../utils/format'
import { WalletCardModal } from '../../components/cards/WalletCardModal'
import { DeleteCardWarningModal } from '../../components/cards/DeleteCardWarningModal'
import { WalletSummaryStats } from './components/summary/WalletSummaryStats'
import { MethodologyInfoPopover } from './components/summary/MethodologyInfoPopover'
import { WalletTimelineChart } from './components/timeline/WalletTimelineChart'
import { SpendPanel } from './components/spend/SpendPanel'
import { ApplicationRuleWarningModal } from './components/ApplicationRuleWarningModal'
import { AddWalletModal } from './components/AddWalletModal'
import { WalletPicker } from './components/WalletPicker'
import { InfoIconButton } from '../../components/InfoPopover'
import { useCreditLibrary } from '../../hooks/useCreditLibrary'
import { useTravelPortals } from '../../hooks/useTravelPortals'
import { queryKeys } from '../../lib/queryKeys'

type MainView = 'timeline' | 'spend'


type WalletCardModalOpen =
  | { mode: 'add' }
  | { mode: 'edit'; walletCard: WalletCard }

const SNAPSHOT_SIG_STORAGE_PREFIX = 'roadmap:snapshot-sig:'
function snapshotSigKey(walletId: number) {
  return `${SNAPSHOT_SIG_STORAGE_PREFIX}${walletId}`
}
function readStoredSnapshotSig(walletId: number): string | null {
  try {
    return localStorage.getItem(snapshotSigKey(walletId))
  } catch {
    return null
  }
}
function writeStoredSnapshotSig(walletId: number, sig: string) {
  try {
    localStorage.setItem(snapshotSigKey(walletId), sig)
  } catch {
    /* storage full or unavailable — stale flag falls back to in-session only */
  }
}

/** Serialize the wallet + projection inputs that drive the calculation.
 * Two calls return the same string iff no calc-relevant input changed, so
 * comparing against the snapshot from the last successful calc lets us
 * distinguish "truly out of date" from "edited and then reverted". */
function walletCalcSignature(
  wallet: Wallet | null | undefined,
  durationYears: number,
  durationMonths: number,
  spendItems: WalletSpendItem[] | undefined,
  walletCurrencies: CurrencyRead[] | undefined,
  portalShares: WalletPortalShare[] | undefined,
  categoryPriorities: WalletCardCategoryPriority[] | undefined,
  creditOverridesByCardId: Map<number, WalletCardCreditOverride[]>,
): string {
  if (!wallet) return ''
  // Only serialize cards that would participate in the calc. Disabled cards
  // are filtered by the backend's `active_wallet_cards` predicate, so edits
  // to them can't change results — leave them out of the signature so those
  // edits don't falsely trip the "out of date" warning.
  const cards = [...(wallet.wallet_cards ?? [])]
    .filter((wc) => wc.is_enabled)
    .map((wc) => ({
      card_id: wc.card_id,
      is_enabled: wc.is_enabled,
      added_date: wc.added_date,
      closed_date: wc.closed_date,
      sub_points: wc.sub_points,
      sub_min_spend: wc.sub_min_spend,
      sub_months: wc.sub_months,
      sub_spend_earn: wc.sub_spend_earn,
      annual_bonus: wc.annual_bonus,
      annual_fee: wc.annual_fee,
      first_year_fee: wc.first_year_fee,
      secondary_currency_rate: wc.secondary_currency_rate,
      sub_earned_date: wc.sub_earned_date,
      product_changed_date: wc.product_changed_date,
      transfer_enabler: wc.transfer_enabler,
      acquisition_type: wc.acquisition_type,
      pc_from_card_id: wc.pc_from_card_id,
      panel: wc.panel,
    }))
    .sort((a, b) => a.card_id - b.card_id)
  const spend = [...(spendItems ?? [])]
    .map((it) => ({
      user_spend_category_id: it.user_spend_category_id,
      amount: it.amount,
    }))
    .sort((a, b) => (a.user_spend_category_id ?? 0) - (b.user_spend_category_id ?? 0))
  // Wallet-scoped overrides that used to trip a sticky `outOfSigDirty` flag.
  // Folding them into the signature lets reverting a change back to its last-
  // calculated value clear the "out of date" warning automatically.
  const activeCardIds = new Set(cards.map((c) => c.card_id))
  const cppOverrides = [...(walletCurrencies ?? [])]
    .map((c) => ({
      currency_id: c.id,
      cpp: c.user_cents_per_point ?? c.cents_per_point,
    }))
    .sort((a, b) => a.currency_id - b.currency_id)
  const portals = [...(portalShares ?? [])]
    .map((p) => ({ travel_portal_id: p.travel_portal_id, share: p.share }))
    .sort((a, b) => a.travel_portal_id - b.travel_portal_id)
  // Key category priorities by library card_id (not wallet_card_id) so they
  // stay stable across add/remove cycles, and skip priorities on disabled
  // cards (those don't affect the calc).
  const prioritiesByCardId = new Map<number, number[]>()
  const walletCardIdToCardId = new Map<number, number>()
  for (const wc of wallet.wallet_cards ?? []) {
    walletCardIdToCardId.set(wc.id, wc.card_id)
  }
  for (const pr of categoryPriorities ?? []) {
    const cardId = walletCardIdToCardId.get(pr.wallet_card_id)
    if (cardId == null || !activeCardIds.has(cardId)) continue
    const list = prioritiesByCardId.get(cardId) ?? []
    list.push(pr.spend_category_id)
    prioritiesByCardId.set(cardId, list)
  }
  const priorities = [...prioritiesByCardId.entries()]
    .map(([cardId, ids]) => ({ card_id: cardId, ids: [...ids].sort((a, b) => a - b) }))
    .sort((a, b) => a.card_id - b.card_id)
  // Per-card credit overrides — same treatment as priorities: drop disabled
  // cards, sort by library credit id for stability. Values include the dollar
  // amount so editing a credit's value (not just toggling it) invalidates
  // the result.
  const credits: { card_id: number; overrides: { library_credit_id: number; value: number }[] }[] = []
  for (const [cardId, rows] of creditOverridesByCardId) {
    if (!activeCardIds.has(cardId)) continue
    credits.push({
      card_id: cardId,
      overrides: [...rows]
        .map((o) => ({ library_credit_id: o.library_credit_id, value: o.value }))
        .sort((a, b) => a.library_credit_id - b.library_credit_id),
    })
  }
  credits.sort((a, b) => a.card_id - b.card_id)
  return JSON.stringify({
    durationYears,
    durationMonths,
    foreign_spend_percent: wallet.foreign_spend_percent,
    // include_subs is deliberately absent: the backend now always computes
    // with SUBs included and returns sub_eaf_contribution so the frontend
    // can apply the wallet-level "Include SUBs" toggle as a pure display
    // switch. Adding it here would falsely mark results stale on toggle.
    cards,
    spend,
    cppOverrides,
    portals,
    priorities,
    credits,
  })
}

export default function RoadmapToolPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { walletId: walletIdParam } = useParams<{ walletId?: string }>()
  const requestedWalletId = walletIdParam ? Number(walletIdParam) : null
  const [walletCardModal, setWalletCardModal] = useState<WalletCardModalOpen | null>(null)
  const [durationYears, setDurationYears] = useState(2)
  const [durationMonths, setDurationMonths] = useState(0)
  const [methodologyAnchor, setMethodologyAnchor] = useState<HTMLElement | null>(null)
  const [result, setResult] = useState<WalletResultResponse | null>(null)
  // Signature of wallet + duration at the last successful calc.
  const [snapshotSignature, setSnapshotSignature] = useState<string | null>(null)
  // Eager drift flag: set right after a mutation succeeds so the amber
  // "Calculate" button appears before the wallet query refetches. Auto-clears
  // when the signature returns to the snapshot, so a toggle-off/toggle-on
  // round-trip (or any other revert to the calculated value) clears the
  // warning automatically.
  const [inSigDirty, setInSigDirty] = useState(false)
  const [mainView, setMainView] = useState<MainView>('timeline')
  const [applicationRuleWarnings, setApplicationRuleWarnings] = useState<RoadmapRuleStatus[] | null>(
    null
  )
  const [pendingRemoval, setPendingRemoval] = useState<{ cardId: number; cardName: string } | null>(
    null
  )
  const [showAddWallet, setShowAddWallet] = useState(false)
  const [addWalletError, setAddWalletError] = useState<string | null>(null)

  const { data: walletList } = useQuery({
    queryKey: queryKeys.wallets(),
    queryFn: () => walletsApi.list(),
  })

  // Single wallet query that resolves to either the URL-requested wallet or
  // the user's default. Falls back gracefully when the requested wallet is
  // missing/forbidden so a stale link doesn't dead-end the page. The fallback
  // signal travels with the data so the banner stays in sync with refetches.
  const { data: walletData, isLoading: walletLoading } = useQuery({
    queryKey: [...queryKeys.myWallet(), requestedWalletId] as const,
    queryFn: async (): Promise<{
      wallet: Wallet
      isFallback: boolean
      requestedId: number | null
    }> => {
      if (requestedWalletId != null) {
        try {
          const w = await walletsApi.get(requestedWalletId)
          return { wallet: w, isFallback: false, requestedId: requestedWalletId }
        } catch {
          const w = await walletsApi.getMyWallet()
          return { wallet: w, isFallback: true, requestedId: requestedWalletId }
        }
      }
      const w = await walletsApi.getMyWallet()
      return { wallet: w, isFallback: false, requestedId: null }
    },
  })
  const wallet = walletData?.wallet ?? null
  const fallbackMessage = walletData?.isFallback
    ? `Wallet #${walletData.requestedId} is unavailable — showing your default wallet.`
    : null

  const walletId = wallet?.id ?? null

  // Last persisted calculation. Hydrated once per wallet mount so returning
  // to the Roadmap Tool shows the prior numbers without forcing another
  // Calculate click.
  const { data: latestResult, isFetched: latestResultFetched } = useQuery({
    queryKey: queryKeys.walletLatestResults(walletId),
    queryFn: () => walletsApi.latestResults(walletId!),
    enabled: walletId != null,
    staleTime: Infinity,
  })

  const { data: spendItems, isFetched: spendItemsFetched } = useQuery({
    queryKey: queryKeys.walletSpendItems(walletId),
    queryFn: () => walletSpendItemsApi.list(walletId!),
    enabled: walletId != null,
  })

  // Pull in the wallet-scoped override collections so the signature can tell
  // when the user has reverted a CPP/portal/priority edit back to its last-
  // calculated value — at which point the "out of date" warning disappears.
  const { data: walletCurrencies } = useQuery({
    queryKey: queryKeys.walletCurrencies(walletId),
    queryFn: () => walletCppApi.listCurrencies(walletId!),
    enabled: walletId != null,
  })
  const { data: portalShares } = useQuery({
    queryKey: queryKeys.walletPortalShares(walletId),
    queryFn: () => walletPortalShareApi.list(walletId!),
    enabled: walletId != null,
  })
  const { data: categoryPriorities } = useQuery({
    queryKey: queryKeys.walletCategoryPriorities(walletId),
    queryFn: () => walletCardCategoryPriorityApi.list(walletId!),
    enabled: walletId != null,
  })

  // Credits live on their own per-card endpoint. Fan out a query per enabled
  // wallet card so the main signature can see every credit value; ReactQuery
  // caches them so opening the WalletCardModal is still instant.
  const enabledWalletCardIds = useMemo(
    () =>
      (wallet?.wallet_cards ?? [])
        .filter((wc) => wc.is_enabled)
        .map((wc) => wc.card_id)
        .sort((a, b) => a - b),
    [wallet],
  )
  const creditQueries = useQueries({
    queries: enabledWalletCardIds.map((cardId) => ({
      queryKey: queryKeys.walletCardCredits(walletId, cardId),
      queryFn: () => walletCardCreditApi.list(walletId!, cardId),
      enabled: walletId != null,
    })),
  })
  const creditOverridesByCardId = useMemo(() => {
    const m = new Map<number, WalletCardCreditOverride[]>()
    enabledWalletCardIds.forEach((cardId, idx) => {
      const rows = creditQueries[idx]?.data
      if (rows) m.set(cardId, rows)
    })
    return m
  }, [creditQueries, enabledWalletCardIds])

  const currentSignature = useMemo(
    () =>
      walletCalcSignature(
        wallet ?? null,
        durationYears,
        durationMonths,
        spendItems,
        walletCurrencies,
        portalShares,
        categoryPriorities,
        creditOverridesByCardId,
      ),
    [
      wallet,
      durationYears,
      durationMonths,
      spendItems,
      walletCurrencies,
      portalShares,
      categoryPriorities,
      creditOverridesByCardId,
    ],
  )
  const signatureMatchesSnapshot =
    snapshotSignature !== null && currentSignature === snapshotSignature

  // Whether a given wallet card is calc-relevant: either it was calculated in
  // the last result, or it would be calculated by the next calc (is_enabled).
  // Edits to cards outside this set can't change the displayed or next result,
  // so we don't mark them as triggering staleness.
  const isCardRelevant = useMemo(() => {
    const lastCalcIds = new Set<number>(
      (result?.wallet.card_results ?? [])
        .filter((cr) => cr.selected)
        .map((cr) => cr.card_id),
    )
    const activeIds = new Set<number>(
      (wallet?.wallet_cards ?? [])
        .filter((wc) => wc.is_enabled)
        .map((wc) => wc.card_id),
    )
    return (cardId: number) => lastCalcIds.has(cardId) || activeIds.has(cardId)
  }, [result, wallet])

  // When the wallet/duration state returns to the snapshot (e.g. the user
  // toggled a card off and then back on), drop the in-signature dirty flag.
  // The out-of-signature dirty flag is *not* cleared here — the signature
  // can't tell us whether a CPP/modal-deep edit has been reverted.
  useEffect(() => {
    if (inSigDirty && signatureMatchesSnapshot) {
      setInSigDirty(false)
    }
  }, [inSigDirty, signatureMatchesSnapshot])

  // A result exists but something calc-affecting has drifted since it ran.
  // Falls back to false (no stale warning) when no calc has ever run.
  const isStale =
    inSigDirty ||
    (snapshotSignature !== null && currentSignature !== snapshotSignature)

  // Warm the global credit library cache so the credits picker inside
  // WalletCardModal renders instantly when a card is opened.
  useCreditLibrary()
  // Same trick for travel portals so the per-currency portal-share meter
  // renders instantly the first time the currency settings dropdown opens.
  useTravelPortals()

  const createWalletMutation = useMutation({
    mutationFn: ({ name }: { name: string }) => walletsApi.create({ name }),
    onSuccess: async (newWallet) => {
      await queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      setShowAddWallet(false)
      setAddWalletError(null)
      navigate(`/roadmap-tool/wallets/${newWallet.id}`)
    },
    onError: (err) => {
      setAddWalletError(err instanceof Error ? err.message : String(err))
    },
  })

  const addCardMutation = useMutation({
    mutationFn: ({ walletId, payload }: { walletId: number; payload: AddCardToWalletPayload }) =>
      walletsApi.addCard(walletId, payload),
    onSuccess: async (data, { walletId, payload }) => {
      const prev = queryClient.getQueryData<RoadmapResponse>(queryKeys.roadmap(walletId))
      const prevViolatedIds = new Set(
        (prev?.rule_statuses ?? []).filter((r) => r.is_violated).map((r) => r.rule_id)
      )

      // New cards default to is_enabled=true backend-side; inspect the server
      // response to catch any explicit override and skip staleness when the
      // card was added disabled (won't be in any calc).
      const addedActive = data.is_enabled !== false

      if (payload.priority_category_ids && payload.priority_category_ids.length > 0) {
        await walletCardCategoryPriorityApi.set(walletId, payload.card_id, payload.priority_category_ids)
        queryClient.invalidateQueries({ queryKey: queryKeys.walletCategoryPriorities(walletId) })
      }

      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      setWalletCardModal(null)
      if (addedActive) setInSigDirty(true)

      try {
        await queryClient.invalidateQueries({ queryKey: queryKeys.roadmap(walletId) })
        const fresh = await queryClient.fetchQuery({
          queryKey: queryKeys.roadmap(walletId),
          queryFn: () => walletsApi.roadmap(walletId),
        })
        const newlyViolated = fresh.rule_statuses.filter(
          (r) => r.is_violated && !prevViolatedIds.has(r.rule_id)
        )
        if (newlyViolated.length > 0) {
          setApplicationRuleWarnings(newlyViolated)
        }
      } catch {
        /* roadmap optional for add flow */
      }
    },
  })

  const removeCardMutation = useMutation({
    mutationFn: ({ walletId, cardId }: { walletId: number; cardId: number }) =>
      walletsApi.removeCard(walletId, cardId),
    onSuccess: (_data, { cardId }) => {
      const wasRelevant = isCardRelevant(cardId)
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      if (wasRelevant) setInSigDirty(true)
    },
  })

  const updateWalletSettingMutation = useMutation({
    mutationFn: ({ walletId, include_subs }: { walletId: number; include_subs: boolean }) =>
      walletsApi.update(walletId, { include_subs }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
    },
  })

  const resultsMutation = useMutation({
    mutationFn: ({
      walletId,
      params,
    }: {
      walletId: number
      params: {
        start_date: string
        end_date?: string
        duration_years?: number
        duration_months?: number
      }
    }) => walletsApi.results(walletId, params),
    // Snapshot at request time (not success time) so edits made while the
    // calc is in-flight still register as drift after it returns.
    onMutate: () => ({ signature: currentSignature }),
    onSuccess: (data, _vars, ctx) => {
      setResult(data)
      const sig = ctx?.signature ?? null
      setSnapshotSignature(sig)
      if (sig != null) writeStoredSnapshotSig(data.wallet_id, sig)
      setInSigDirty(false)
      queryClient.setQueryData(queryKeys.walletLatestResults(data.wallet_id), data)
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
    },
  })

  function calculateNow() {
    runCalculation()
  }

  // Single mutation for all wallet card updates (quick actions + edit modal).
  // Call sites handle their own UI side effects (clearing state / closing modals).
  const updateWalletCardMutation = useMutation({
    mutationFn: ({
      walletId,
      cardId,
      payload,
    }: {
      walletId: number
      cardId: number
      payload: UpdateWalletCardPayload
    }) => walletsApi.updateCard(walletId, cardId, payload),
    onSuccess: (data, { walletId, cardId }) => {
      // Edit affects calc iff the card is calc-relevant before the edit (so
      // the current result depends on it) or after (so the next result will).
      // `isCardRelevant` covers the "before" case; `data.is_enabled` covers
      // the "after" case, including the re-enable flip.
      const wasRelevant = isCardRelevant(cardId)
      const isNowActive = data.is_enabled
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      queryClient.invalidateQueries({ queryKey: queryKeys.roadmap(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCardCredits(walletId, null) })
      if (wasRelevant || isNowActive) setInSigDirty(true)
    },
  })

  const { data: roadmap } = useQuery({
    queryKey: queryKeys.roadmap(walletId!),
    queryFn: () => walletsApi.roadmap(walletId!),
    enabled: walletId != null,
  })

  useEffect(() => {
    if (walletId == null || !wallet) return

    // One-shot init: sync duration from the wallet's persisted calc config.
    // We deliberately do NOT auto-fire a calculation — the Calculate button is
    // the only thing that should trigger `walletsApi.results`.
    setDurationYears(wallet.calc_duration_years)
    setDurationMonths(wallet.calc_duration_months)
  }, [walletId, wallet?.id])

  // Hydrate result state from the persisted snapshot exactly once per mount.
  // The snapshot signature is read from localStorage (written at calc time) so
  // edits made on *other* pages between calc and this mount still flag the
  // calc as stale. If nothing was stored (first visit after upgrade, or a
  // different browser), fall back to the current wallet signature — equivalent
  // to the pre-persistence behaviour.
  const [hasHydrated, setHasHydrated] = useState(false)
  useEffect(() => {
    if (hasHydrated) return
    if (!latestResultFetched) return
    if (!spendItemsFetched) return
    if (!wallet) return
    if (latestResult) {
      setResult(latestResult)
      const stored = readStoredSnapshotSig(wallet.id)
      setSnapshotSignature(
        stored ??
          walletCalcSignature(
            wallet,
            latestResult.duration_years,
            latestResult.duration_months,
            spendItems,
            walletCurrencies,
            portalShares,
            categoryPriorities,
            creditOverridesByCardId,
          ),
      )
    }
    setHasHydrated(true)
  }, [
    hasHydrated,
    latestResultFetched,
    latestResult,
    spendItemsFetched,
    spendItems,
    wallet,
    walletCurrencies,
    portalShares,
    categoryPriorities,
    creditOverridesByCardId,
  ])

  function runCalculation(years = durationYears, months = durationMonths) {
    if (walletId == null) return
    if (years * 12 + months === 0) return
    resultsMutation.mutate({
      walletId: walletId,
      params: { start_date: today(), duration_years: years, duration_months: months },
    })
  }

  const isBusy = updateWalletCardMutation.isPending || removeCardMutation.isPending || resultsMutation.isPending

  if (walletLoading) {
    return (
      <div className="max-w-screen-xl mx-auto w-full shrink-0">
        <div className="text-center text-slate-400 py-20">Loading wallet…</div>
      </div>
    )
  }

  return (
    <div className="max-w-screen-xl mx-auto w-full flex flex-col flex-1 min-h-0">
      {isBusy && (
        <div className="fixed top-0 left-0 right-0 z-50 h-0.5">
          <div className="h-full bg-indigo-500 animate-progress-bar" />
        </div>
      )}
      <header className="mb-3 shrink-0 flex items-start justify-between gap-4">
        <div className="min-w-0 flex items-center gap-3">
          <h1 className="text-2xl font-bold text-white shrink-0">Roadmap Tool</h1>
          {walletList && (
            <WalletPicker
              wallets={walletList}
              currentId={walletId}
              onSelect={(id) => navigate(`/roadmap-tool/wallets/${id}`)}
              onAddWallet={() => {
                setAddWalletError(null)
                setShowAddWallet(true)
              }}
            />
          )}
        </div>
        {wallet && (
          <div className="shrink-0 flex items-center gap-2">
            <InfoIconButton
              onClick={(e) => {
                const anchor = e.currentTarget
                setMethodologyAnchor((cur) => (cur ? null : anchor))
              }}
              label="How the roadmap is calculated"
              size={18}
              active={!!methodologyAnchor}
            />
            <button
              type="button"
              onClick={calculateNow}
              disabled={resultsMutation.isPending || !isStale}
              aria-live="polite"
              className={`px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
                resultsMutation.isPending
                  ? 'bg-slate-700 text-slate-400 cursor-wait'
                  : isStale
                  ? 'bg-amber-500 hover:bg-amber-400 text-slate-900 shadow-sm shadow-amber-900/40'
                  : 'bg-slate-700 text-slate-500 cursor-not-allowed'
              }`}
              title={isStale ? 'Results are out of date — click to recalculate' : 'Results are up to date'}
            >
              {resultsMutation.isPending
                ? 'Calculating…'
                : isStale
                ? 'Calculate'
                : 'Up to Date'}
            </button>
          </div>
        )}
      </header>

      {methodologyAnchor && (
        <MethodologyInfoPopover
          anchorEl={methodologyAnchor}
          onClose={() => setMethodologyAnchor(null)}
        />
      )}

      {fallbackMessage && (
        <div className="mb-3 shrink-0 px-3 py-2 rounded-md border border-amber-700/60 bg-amber-900/30 text-amber-200 text-sm">
          {fallbackMessage}
        </div>
      )}

      <div className="min-w-0 flex-1 min-h-0 flex flex-col">
        {!wallet ? (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 text-center text-slate-500 shrink-0">
            Add cards and spending in your <Link to="/profile" className="text-indigo-400 hover:text-indigo-300">profile</Link> to get started.
          </div>
        ) : (
          <>
            <div className="mb-4 shrink-0">
              <WalletSummaryStats
                result={result?.wallet ?? null}
                roadmap={roadmap ?? null}
                isCalculating={resultsMutation.isPending}
                isStale={isStale}
                durationYears={durationYears}
                durationMonths={durationMonths}
                onDurationChange={(y, m) => {
                  setDurationYears(y)
                  setDurationMonths(m)
                  setInSigDirty(true)
                }}
                includeSubs={wallet.include_subs ?? true}
                onIncludeSubsChange={(v) => {
                  updateWalletSettingMutation.mutate({ walletId: wallet.id, include_subs: v })
                }}
                resultsError={
                  resultsMutation.isError
                    ? resultsMutation.error instanceof Error
                      ? resultsMutation.error
                      : new Error(String(resultsMutation.error))
                    : null
                }
              />
            </div>
            <div className="flex flex-1 min-h-0 min-w-0 items-stretch">
              {/* Binder-style tabs sit outside the panel on the left. */}
              <div className="shrink-0 flex flex-col gap-1 pt-6 z-10">
                {([
                  {
                    key: 'timeline' as const,
                    label: 'Timeline',
                    icon: (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="3" y1="6" x2="21" y2="6" />
                        <line x1="3" y1="12" x2="14" y2="12" />
                        <line x1="3" y1="18" x2="18" y2="18" />
                      </svg>
                    ),
                  },
                  {
                    key: 'spend' as const,
                    label: 'Spend',
                    icon: (
                      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <line x1="12" y1="1" x2="12" y2="23" />
                        <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
                      </svg>
                    ),
                  },
                ]).map((tab) => {
                  const isActive = mainView === tab.key
                  return (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => setMainView(tab.key)}
                      className={`px-2 py-3 rounded-l-md border border-r-0 transition-colors ${
                        isActive
                          ? 'bg-slate-900 text-indigo-300 border-slate-700 -mr-px'
                          : 'bg-slate-800/70 text-slate-400 border-slate-800 hover:text-slate-200 hover:bg-slate-800'
                      }`}
                      aria-pressed={isActive}
                      aria-label={tab.label}
                      title={tab.label}
                    >
                      {tab.icon}
                    </button>
                  )
                })}
              </div>

              <div className="flex-1 min-w-0 min-h-0">
                {mainView === 'timeline' ? (
                  <WalletTimelineChart
                    wallet={wallet}
                    result={result?.wallet ?? null}
                    roadmap={roadmap}
                    durationYears={durationYears}
                    durationMonths={durationMonths}
                    isUpdating={updateWalletCardMutation.isPending}
                    isStale={isStale}
                    includeSubs={wallet.include_subs ?? true}
                    onToggleEnabled={(cardId, enabled) =>
                      updateWalletCardMutation.mutate({
                        walletId: wallet.id,
                        cardId,
                        payload: { is_enabled: enabled },
                      })
                    }
                    onEditCard={(wc) => setWalletCardModal({ mode: 'edit', walletCard: wc })}
                    onAddCard={() => setWalletCardModal({ mode: 'add' })}
                  />
                ) : (
                  <SpendPanel
                    walletId={walletId}
                    selectedCards={result?.wallet.card_results.filter((c) => c.selected) ?? []}
                    walletCards={wallet.wallet_cards ?? []}
                    totalYears={Math.max(durationYears + durationMonths / 12, 1 / 12)}
                    isStale={isStale}
                  />
                )}
              </div>
            </div>

          </>
        )}
      </div>

      {applicationRuleWarnings && applicationRuleWarnings.length > 0 && (
        <ApplicationRuleWarningModal
          violations={applicationRuleWarnings}
          onClose={() => setApplicationRuleWarnings(null)}
        />
      )}

      {showAddWallet && (
        <AddWalletModal
          isSubmitting={createWalletMutation.isPending}
          errorMessage={addWalletError}
          onClose={() => {
            setShowAddWallet(false)
            setAddWalletError(null)
          }}
          onSubmit={(name) => {
            setAddWalletError(null)
            createWalletMutation.mutate({ name })
          }}
        />
      )}

      {pendingRemoval && wallet && (
        <DeleteCardWarningModal
          cardName={pendingRemoval.cardName}
          isLoading={removeCardMutation.isPending}
          onClose={() => setPendingRemoval(null)}
          onConfirm={() => {
            removeCardMutation.mutate(
              { walletId: wallet.id, cardId: pendingRemoval.cardId },
              { onSuccess: () => setPendingRemoval(null) },
            )
          }}
        />
      )}

      {walletCardModal && wallet && (
        <WalletCardModal
          onRemove={(wc) => {
            setWalletCardModal(null)
            setPendingRemoval({
              cardId: wc.card_id,
              cardName: wc.card_name ?? `Card #${wc.card_id}`,
            })
          }}
          key={walletCardModal.mode === 'add' ? 'add' : walletCardModal.walletCard.id}
          mode={walletCardModal.mode}
          walletId={wallet.id}
          walletCard={
            walletCardModal.mode === 'edit' ? walletCardModal.walletCard : undefined
          }
          existingCardIds={wallet.wallet_cards.map((wc) => wc.card_id)}
          walletCardIds={wallet.wallet_cards.map((wc) => wc.card_id)}
          onClose={() => setWalletCardModal(null)}
          onAdd={(payload) =>
            addCardMutation.mutate({ walletId: wallet.id, payload })
          }
          onSaveEdit={(payload) => {
            if (walletCardModal.mode !== 'edit') return
            // Every field the modal can mutate — wallet card props, credits,
            // and category priorities — is now part of the wallet signature,
            // so the amber Calculate button turns on via sig mismatch and
            // clears the moment the user reverts back to the calculated
            // value. No separate sticky flag needed.
            updateWalletCardMutation.mutate(
              {
                walletId: wallet.id,
                cardId: walletCardModal.walletCard.card_id,
                payload,
              },
              {
                onSuccess: () => {
                  setWalletCardModal(null)
                },
              }
            )
          }}
          isLoading={addCardMutation.isPending || updateWalletCardMutation.isPending}
        />
      )}
    </div>
  )
}
