import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import {
  walletsApi,
  type AddCardToWalletPayload,
  type RoadmapResponse,
  type RoadmapRuleStatus,
  type UpdateWalletCardPayload,
  type WalletCard,
  type WalletResultResponse,
} from '../../api/client'
import { today } from '../../utils/format'
import { WalletCardModal } from './components/cards/WalletCardModal'
import { CreateWalletModal } from './components/wallet/CreateWalletModal'
import { WalletResultsAndCurrenciesPanel } from './components/summary/WalletResultsAndCurrenciesPanel'
import { CardsListPanel } from './components/cards/CardsListPanel'
import { DeleteCardWarningModal } from './components/cards/DeleteCardWarningModal'
import { ApplicationRuleWarningModal } from './components/roadmap/ApplicationRuleWarningModal'
import { DEFAULT_USER_ID } from './constants'
import { useCreditLibrary } from './hooks/useCreditLibrary'
import { queryKeys } from './lib/queryKeys'


type WalletCardModalOpen =
  | { mode: 'add' }
  | { mode: 'edit'; walletCard: WalletCard }

export default function WalletToolPage() {
  const queryClient = useQueryClient()
  const [selectedWalletId, setSelectedWalletId] = useState<number | null>(null)
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [walletCardModal, setWalletCardModal] = useState<WalletCardModalOpen | null>(null)
  const [durationYears, setDurationYears] = useState(2)
  const [durationMonths, setDurationMonths] = useState(0)
  const [result, setResult] = useState<WalletResultResponse | null>(null)
  const [closeCardId, setCloseCardId] = useState<number | null>(null)
  const [closeDateInput, setCloseDateInput] = useState('')
  const [applicationRuleWarnings, setApplicationRuleWarnings] = useState<RoadmapRuleStatus[] | null>(
    null
  )
  const [pendingRemoval, setPendingRemoval] = useState<{ cardId: number; cardName: string } | null>(
    null
  )

  const { data: wallets, isLoading: walletsLoading } = useQuery({
    queryKey: queryKeys.wallets(),
    queryFn: () => walletsApi.list(DEFAULT_USER_ID),
  })

  // Warm the global credit library cache so the credits picker inside
  // WalletCardModal renders instantly when a card is opened.
  useCreditLibrary()

  const createWalletMutation = useMutation({
    mutationFn: (payload: { name: string; description: string }) =>
      walletsApi.create({
        user_id: DEFAULT_USER_ID,
        name: payload.name,
        description: payload.description || null,
      }),
    onSuccess: (wallet) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      setSelectedWalletId(wallet.id)
      setShowCreateModal(false)
    },
  })

  const addCardMutation = useMutation({
    mutationFn: ({ walletId, payload }: { walletId: number; payload: AddCardToWalletPayload }) =>
      walletsApi.addCard(walletId, payload),
    onSuccess: async (_data, { walletId }) => {
      const prev = queryClient.getQueryData<RoadmapResponse>(queryKeys.roadmap(walletId))
      const prevViolatedIds = new Set(
        (prev?.rule_statuses ?? []).filter((r) => r.is_violated).map((r) => r.rule_id)
      )

      queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
      setWalletCardModal(null)

      runCalculation()

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
      queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
      runCalculation()
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
      queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(data.wallet_id) })
    },
  })

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
      queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      queryClient.invalidateQueries({ queryKey: queryKeys.roadmap(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
      queryClient.invalidateQueries({ queryKey: ['wallet-card-credits'] })
      runCalculation()
    },
  })

  const { data: roadmap } = useQuery({
    queryKey: queryKeys.roadmap(selectedWalletId!),
    queryFn: () => walletsApi.roadmap(selectedWalletId!),
    enabled: selectedWalletId != null,
  })

  const selectedWallet = wallets?.find((w) => w.id === selectedWalletId)

  useEffect(() => {
    if (selectedWalletId == null || !selectedWallet) return

    setDurationYears(selectedWallet.calc_duration_years)
    setDurationMonths(selectedWallet.calc_duration_months)

    if (selectedWallet.calc_start_date) {
      // Auto-run the last calculation from today
      resultsMutation.mutate({
        walletId: selectedWalletId,
        params: {
          start_date: today(),
          duration_years: selectedWallet.calc_duration_years,
          duration_months: selectedWallet.calc_duration_months,
        },
      })
    }
  }, [selectedWalletId])

  function runCalculation(years = durationYears, months = durationMonths) {
    if (selectedWalletId == null) return
    if (years * 12 + months === 0) return
    resultsMutation.mutate({
      walletId: selectedWalletId,
      params: { start_date: today(), duration_years: years, duration_months: months },
    })
  }

  if (walletsLoading) {
    return (
      <div className="max-w-screen-xl mx-auto w-full shrink-0">
        <div className="text-center text-slate-400 py-20">Loading wallets…</div>
      </div>
    )
  }

  return (
    <div className="max-w-screen-xl mx-auto w-full flex flex-col flex-1 min-h-0">
      <header className="mb-6 shrink-0 flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between sm:gap-6">
        <div className="min-w-0">
          <h1 className="text-2xl font-bold text-white">Wallet Tool</h1>
          <p className="text-slate-400 text-sm mt-1">
            Manage wallets, add cards with sign-up bonus and min spend. Calculations update automatically.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2 shrink-0">
          <button
            type="button"
            className="text-indigo-400 hover:text-indigo-300 text-sm font-medium px-2 py-2"
            onClick={() => setShowCreateModal(true)}
          >
            + New Wallet
          </button>
          <label htmlFor="wallet-select" className="sr-only">
            Wallet
          </label>
          <select
            id="wallet-select"
            className="bg-slate-800 border border-slate-600 text-white text-sm rounded-lg px-3 py-2 min-w-[10rem] max-w-[16rem]"
            value={selectedWalletId ?? ''}
            onChange={(e) => {
              const v = e.target.value
              setSelectedWalletId(v === '' ? null : Number(v))
              setResult(null)
            }}
          >
            <option value="">
              {wallets?.length === 0 ? 'No wallets — create one' : 'Select wallet…'}
            </option>
            {wallets?.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </div>
      </header>

      <div className="min-w-0 flex-1 min-h-0 flex flex-col">
        {!selectedWallet ? (
          <div className="bg-slate-900 border border-slate-700 rounded-xl p-8 text-center text-slate-500 shrink-0">
            Select a wallet or create one to get started.
          </div>
        ) : (
          <>
            <div
              className="grid flex-1 min-h-0 gap-6 grid-cols-1 grid-rows-[minmax(0,1fr)_minmax(0,1fr)] xl:grid-cols-2 xl:grid-rows-1"
            >
              <WalletResultsAndCurrenciesPanel
                walletId={selectedWalletId}
                result={result?.wallet ?? null}
                resultsError={
                  resultsMutation.isError
                    ? resultsMutation.error instanceof Error
                      ? resultsMutation.error
                      : new Error(String(resultsMutation.error))
                    : null
                }
                isCalculating={resultsMutation.isPending}
                durationYears={durationYears}
                durationMonths={durationMonths}
                onDurationChange={(y, m) => {
                  setDurationYears(y)
                  setDurationMonths(m)
                }}
                onDurationCommit={(y, m) => runCalculation(y, m)}
                onCppChange={() => runCalculation()}
                onSpendChange={() => runCalculation()}
              />

              {/* Mirror the tab column on the Results panel so both inner panels
                  end up the same visual width inside their grid cells. */}
              <div className="flex h-full min-w-0 min-h-0 items-stretch">
                <div className="flex-1 min-w-0 min-h-0">
                  <CardsListPanel
                    wallet={selectedWallet}
                    roadmap={roadmap}
                    closeCardId={closeCardId}
                    closeDateInput={closeDateInput}
                    isUpdating={updateWalletCardMutation.isPending}
                    isRemoving={removeCardMutation.isPending}
                    onSetCloseCard={setCloseCardId}
                    onSetCloseDateInput={setCloseDateInput}
                    onUpdateCard={(cardId, payload) => {
                      updateWalletCardMutation.mutate(
                        { walletId: selectedWallet.id, cardId, payload },
                        {
                          onSuccess: () => {
                            setCloseCardId(null)
                            setCloseDateInput('')
                          },
                        }
                      )
                    }}
                    onRemoveCard={(cardId) => {
                      const wc = selectedWallet.wallet_cards.find((c) => c.card_id === cardId)
                      setPendingRemoval({
                        cardId,
                        cardName: wc?.card_name ?? `Card #${cardId}`,
                      })
                    }}
                    onEditCard={(wc) => setWalletCardModal({ mode: 'edit', walletCard: wc })}
                    onAddCard={() => setWalletCardModal({ mode: 'add' })}
                  />
                </div>
                <div className="shrink-0 w-[35px]" aria-hidden />
              </div>
            </div>

          </>
        )}
      </div>

      {showCreateModal && (
        <CreateWalletModal
          onClose={() => setShowCreateModal(false)}
          onCreate={(name, description) =>
            createWalletMutation.mutate({ name, description })
          }
          isLoading={createWalletMutation.isPending}
        />
      )}

      {applicationRuleWarnings && applicationRuleWarnings.length > 0 && (
        <ApplicationRuleWarningModal
          violations={applicationRuleWarnings}
          onClose={() => setApplicationRuleWarnings(null)}
        />
      )}

      {pendingRemoval && selectedWallet && (
        <DeleteCardWarningModal
          cardName={pendingRemoval.cardName}
          isLoading={removeCardMutation.isPending}
          onClose={() => setPendingRemoval(null)}
          onConfirm={() => {
            removeCardMutation.mutate(
              { walletId: selectedWallet.id, cardId: pendingRemoval.cardId },
              { onSuccess: () => setPendingRemoval(null) },
            )
          }}
        />
      )}

      {walletCardModal && selectedWallet && (
        <WalletCardModal
          key={walletCardModal.mode === 'add' ? 'add' : walletCardModal.walletCard.id}
          mode={walletCardModal.mode}
          walletCard={
            walletCardModal.mode === 'edit' ? walletCardModal.walletCard : undefined
          }
          existingCardIds={selectedWallet.wallet_cards.map((wc) => wc.card_id)}
          onClose={() => setWalletCardModal(null)}
          onAdd={(payload) =>
            addCardMutation.mutate({ walletId: selectedWallet.id, payload })
          }
          onSaveEdit={(payload) => {
            if (walletCardModal.mode !== 'edit') return
            updateWalletCardMutation.mutate(
              {
                walletId: selectedWallet.id,
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
