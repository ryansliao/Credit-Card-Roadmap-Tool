import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import {
  walletsApi,
  walletCardCategoryPriorityApi,
  type AddCardToWalletPayload,
  type RoadmapResponse,
  type RoadmapRuleStatus,
  type UpdateWalletCardPayload,
  type WalletCard,
  type WalletResultResponse,
} from '../../api/client'
import { today } from '../../utils/format'
import { WalletCardModal } from '../../components/cards/WalletCardModal'
import { DeleteCardWarningModal } from '../../components/cards/DeleteCardWarningModal'
import { CloseCardModal } from './components/cards/CloseCardModal'
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

export default function RoadmapToolPage() {
  const queryClient = useQueryClient()
  const [walletCardModal, setWalletCardModal] = useState<WalletCardModalOpen | null>(null)
  const [durationYears, setDurationYears] = useState(2)
  const [durationMonths, setDurationMonths] = useState(0)
  const [showMethodology, setShowMethodology] = useState(false)
  const [editingCurrencyId, setEditingCurrencyId] = useState<number | null>(null)
  const [result, setResult] = useState<WalletResultResponse | null>(null)
  const [isStale, setIsStale] = useState(false)
  const [mainView, setMainView] = useState<MainView>('timeline')
  const [applicationRuleWarnings, setApplicationRuleWarnings] = useState<RoadmapRuleStatus[] | null>(
    null
  )
  const [pendingRemoval, setPendingRemoval] = useState<{ cardId: number; cardName: string } | null>(
    null
  )
  const [pendingClose, setPendingClose] = useState<
    { cardId: number; cardName: string; addedDate: string } | null
  >(null)

  const { data: wallet, isLoading: walletLoading } = useQuery({
    queryKey: queryKeys.myWallet(),
    queryFn: () => walletsApi.getMyWallet(),
  })

  const walletId = wallet?.id ?? null

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
      }

      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
      setWalletCardModal(null)

      setIsStale(true)

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
    onSuccess: (_data, { walletId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
      setIsStale(true)
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
    onSuccess: (data) => {
      setResult(data)
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(data.wallet_id) })
    },
  })

  // Wraps runCalculation to clear staleness up-front so any edits the user
  // makes while the calc is in-flight correctly re-mark the result as stale.
  function calculateNow() {
    setIsStale(false)
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
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCardCredits(walletId, null) })
      setIsStale(true)
    },
  })

  const { data: roadmap } = useQuery({
    queryKey: queryKeys.roadmap(walletId!),
    queryFn: () => walletsApi.roadmap(walletId!),
    enabled: walletId != null,
  })

  useEffect(() => {
    if (walletId == null || !wallet) return

    // One-shot init: wallet id flips from null to a number once per session.
    setDurationYears(wallet.calc_duration_years)
    setDurationMonths(wallet.calc_duration_months)

    if (wallet.calc_start_date) {
      resultsMutation.mutate({
        walletId: walletId,
        params: {
          start_date: today(),
          duration_years: wallet.calc_duration_years,
          duration_months: wallet.calc_duration_months,
        },
      })
    }
    // resultsMutation is a stable react-query handle; wallet is intentionally
    // gated by wallet?.id so we run this only on the initial load, not on
    // every wallet field update.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [walletId, wallet?.id])

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
      <header className="mb-4 shrink-0 flex items-start justify-between gap-4">
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
            disabled={resultsMutation.isPending}
            aria-live="polite"
            className={`shrink-0 px-4 py-2 rounded-lg text-sm font-semibold transition-colors ${
              resultsMutation.isPending
                ? 'bg-slate-700 text-slate-400 cursor-wait'
                : isStale
                ? 'bg-amber-500 hover:bg-amber-400 text-slate-900 shadow-sm shadow-amber-900/40'
                : 'bg-slate-700 hover:bg-slate-600 text-slate-200'
            }`}
            title={isStale ? 'Results are out of date — click to recalculate' : 'Recalculate with current settings'}
          >
            {resultsMutation.isPending
              ? 'Calculating…'
              : isStale
              ? 'Calculate (out of date)'
              : 'Calculate'}
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
                isCalculating={resultsMutation.isPending}
                isStale={isStale}
                durationYears={durationYears}
                durationMonths={durationMonths}
                onDurationChange={(y, m) => {
                  setDurationYears(y)
                  setDurationMonths(m)
                  setIsStale(true)
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

      {pendingClose && wallet && (
        <CloseCardModal
          cardName={pendingClose.cardName}
          minDate={pendingClose.addedDate}
          isLoading={updateWalletCardMutation.isPending}
          onClose={() => setPendingClose(null)}
          onConfirm={(closedDate) => {
            updateWalletCardMutation.mutate(
              {
                walletId: wallet.id,
                cardId: pendingClose.cardId,
                payload: { closed_date: closedDate },
              },
              { onSuccess: () => setPendingClose(null) },
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
          onCppChange={() => setIsStale(true)}
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
          onCloseCard={(wc) => {
            setWalletCardModal(null)
            setPendingClose({
              cardId: wc.card_id,
              cardName: wc.card_name ?? `Card #${wc.card_id}`,
              addedDate: wc.added_date,
            })
          }}
          onReopenCard={(wc) => {
            updateWalletCardMutation.mutate({
              walletId: wallet.id,
              cardId: wc.card_id,
              payload: { closed_date: null },
            })
            setWalletCardModal(null)
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
