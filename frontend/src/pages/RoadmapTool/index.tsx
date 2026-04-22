import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  walletsApi,
  walletCardCategoryPriorityApi,
  walletSpendItemsApi,
  type AddCardToWalletPayload,
  type RoadmapResponse,
  type RoadmapRuleStatus,
  type UpdateWalletCardPayload,
  type Wallet,
  type WalletCard,
  type WalletResultResponse,
  type WalletSpendItem,
} from '../../api/client'
import { today } from '../../utils/format'
import { WalletCardModal } from '../../components/cards/WalletCardModal'
import { DeleteCardWarningModal } from '../../components/cards/DeleteCardWarningModal'
import { WalletSummaryStats } from './components/summary/WalletSummaryStats'
import { MethodologyInfoPopover } from './components/summary/MethodologyInfoPopover'
import { CurrencyEditModal } from './components/summary/CurrencyEditModal'
import { WalletTimelineChart } from './components/timeline/WalletTimelineChart'
import { SpendPanel } from './components/spend/SpendPanel'
import { ApplicationRuleWarningModal } from './components/ApplicationRuleWarningModal'
import { InfoIconButton } from '../../components/InfoPopover'
import { useCreditLibrary } from '../../hooks/useCreditLibrary'
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
): string {
  if (!wallet) return ''
  const cards = [...(wallet.wallet_cards ?? [])]
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
  return JSON.stringify({
    durationYears,
    durationMonths,
    foreign_spend_percent: wallet.foreign_spend_percent,
    include_subs: wallet.include_subs,
    cards,
    spend,
  })
}

export default function RoadmapToolPage() {
  const queryClient = useQueryClient()
  const [walletCardModal, setWalletCardModal] = useState<WalletCardModalOpen | null>(null)
  const [durationYears, setDurationYears] = useState(2)
  const [durationMonths, setDurationMonths] = useState(0)
  const [showMethodology, setShowMethodology] = useState(false)
  const [editingCurrencyId, setEditingCurrencyId] = useState<number | null>(null)
  const [result, setResult] = useState<WalletResultResponse | null>(null)
  // Signature of wallet + duration at the last successful calc.
  const [snapshotSignature, setSnapshotSignature] = useState<string | null>(null)
  // Edits to fields that are in the signature (toggle, duration, added/closed
  // date, SUB overrides, annual fee overrides, …). Set eagerly for instant
  // feedback; auto-clears when the signature returns to the snapshot, so a
  // toggle-off/toggle-on round-trip clears the "out of date" warning.
  const [inSigDirty, setInSigDirty] = useState(false)
  // Edits to fields that aren't in the signature (wallet CPP overrides, per-card
  // credits/multipliers/group selections/priorities saved through the modal).
  // Only the next successful calc clears these.
  const [outOfSigDirty, setOutOfSigDirty] = useState(false)
  const [mainView, setMainView] = useState<MainView>('timeline')
  const [applicationRuleWarnings, setApplicationRuleWarnings] = useState<RoadmapRuleStatus[] | null>(
    null
  )
  const [pendingRemoval, setPendingRemoval] = useState<{ cardId: number; cardName: string } | null>(
    null
  )

  const { data: wallet, isLoading: walletLoading } = useQuery({
    queryKey: queryKeys.myWallet(),
    queryFn: () => walletsApi.getMyWallet(),
  })

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

  const currentSignature = useMemo(
    () => walletCalcSignature(wallet ?? null, durationYears, durationMonths, spendItems),
    [wallet, durationYears, durationMonths, spendItems],
  )
  const signatureMatchesSnapshot =
    snapshotSignature !== null && currentSignature === snapshotSignature

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
    outOfSigDirty ||
    inSigDirty ||
    (snapshotSignature !== null && currentSignature !== snapshotSignature)

  // Warm the global credit library cache so the credits picker inside
  // WalletCardModal renders instantly when a card is opened.
  useCreditLibrary()

  const addCardMutation = useMutation({
    mutationFn: ({ walletId, payload }: { walletId: number; payload: AddCardToWalletPayload }) =>
      walletsApi.addCard(walletId, payload),
    onSuccess: async (_data, { walletId, payload }) => {
      const prev = queryClient.getQueryData<RoadmapResponse>(queryKeys.roadmap(walletId))
      const prevViolatedIds = new Set(
        (prev?.rule_statuses ?? []).filter((r) => r.is_violated).map((r) => r.rule_id)
      )

      if (payload.priority_category_ids && payload.priority_category_ids.length > 0) {
        await walletCardCategoryPriorityApi.set(walletId, payload.card_id, payload.priority_category_ids)
        queryClient.invalidateQueries({ queryKey: queryKeys.walletCategoryPriorities(walletId) })
        // priorities are tied to this card — not in the wallet signature, so
        // flag out-of-band until the next calc.
        setOutOfSigDirty(true)
      }

      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      setWalletCardModal(null)
      setInSigDirty(true)

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
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      setInSigDirty(true)
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
      setOutOfSigDirty(false)
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
    onSuccess: (_data, { walletId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      queryClient.invalidateQueries({ queryKey: queryKeys.roadmap(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCardCredits(walletId, null) })
      setInSigDirty(true)
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
          ),
      )
    }
    setHasHydrated(true)
  }, [hasHydrated, latestResultFetched, latestResult, spendItemsFetched, spendItems, wallet])

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
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white">Roadmap Tool</h1>
            <InfoIconButton
              onClick={() => setShowMethodology(true)}
              label="Calculation methodology"
              size={18}
            />
          </div>
        </div>
        {wallet && (
          <button
            type="button"
            onClick={calculateNow}
            disabled={resultsMutation.isPending || !isStale}
            aria-live="polite"
            className={`shrink-0 px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
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
        )}
      </header>

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
                  setInSigDirty(true)
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
                    onToggleEnabled={(cardId, enabled) =>
                      updateWalletCardMutation.mutate({
                        walletId: wallet.id,
                        cardId,
                        payload: { is_enabled: enabled },
                      })
                    }
                    onEditCard={(wc) => setWalletCardModal({ mode: 'edit', walletCard: wc })}
                    onAddCard={() => setWalletCardModal({ mode: 'add' })}
                    onEditCurrency={(cid) => setEditingCurrencyId(cid)}
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

      {showMethodology && (
        <MethodologyInfoPopover onClose={() => setShowMethodology(false)} />
      )}

      {editingCurrencyId != null && wallet && (
        <CurrencyEditModal
          walletId={wallet.id}
          currencyId={editingCurrencyId}
          onClose={() => setEditingCurrencyId(null)}
          onCppChange={() => setOutOfSigDirty(true)}
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
            // Modal save can also mutate per-card credits/multipliers/group
            // selections/priorities before reaching this handler. Those aren't
            // in the wallet signature, so mark out-of-sig dirty to keep the
            // calc flagged as stale until the next run.
            setOutOfSigDirty(true)
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
