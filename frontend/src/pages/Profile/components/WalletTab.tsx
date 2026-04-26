import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  ownedCardInstancesApi,
  type CardInstance,
  type OwnedCardCreatePayload,
  type OwnedCardUpdatePayload,
} from '../../../api/client'
import { WalletCardModal } from '../../../components/cards/WalletCardModal'
import { DeleteCardWarningModal } from '../../../components/cards/DeleteCardWarningModal'
import { useCreditLibrary } from '../../../hooks/useCreditLibrary'
import { queryKeys } from '../../../lib/queryKeys'
import { formatMoney, formatPoints, pointsUnitLabel } from '../../../utils/format'
import { CardPhoto } from './CardPhoto'

type WalletCardModalOpen =
  | { mode: 'add' }
  | { mode: 'edit'; instance: CardInstance }

interface WalletTabProps {
  cardInstances: CardInstance[]
  isLoading: boolean
}

export function WalletTab({ cardInstances, isLoading }: WalletTabProps) {
  const queryClient = useQueryClient()
  const [walletCardModal, setWalletCardModal] = useState<WalletCardModalOpen | null>(null)
  const [pendingRemoval, setPendingRemoval] = useState<{
    instanceId: number
    cardName: string
  } | null>(null)

  useCreditLibrary()

  const invalidateWallet = () => {
    queryClient.invalidateQueries({ queryKey: queryKeys.myWalletWithScenarios() })
    queryClient.invalidateQueries({ queryKey: queryKeys.ownedCardInstances() })
  }

  const addCardMutation = useMutation({
    mutationFn: (payload: OwnedCardCreatePayload) => ownedCardInstancesApi.create(payload),
    onSuccess: () => {
      invalidateWallet()
      setWalletCardModal(null)
    },
  })

  const removeCardMutation = useMutation({
    mutationFn: (instanceId: number) => ownedCardInstancesApi.delete(instanceId),
    onSuccess: () => invalidateWallet(),
  })

  const updateCardMutation = useMutation({
    mutationFn: ({
      instanceId,
      payload,
    }: {
      instanceId: number
      payload: OwnedCardUpdatePayload
    }) => ownedCardInstancesApi.update(instanceId, payload),
    onSuccess: () => invalidateWallet(),
  })

  const inWalletCards = cardInstances
    .filter((inst) => inst.scenario_id === null && inst.panel === 'in_wallet')
    .sort((a, b) => {
      const da = a.opening_date?.trim() ?? ''
      const db = b.opening_date?.trim() ?? ''
      if (!da && !db) return 0
      if (!da) return 1
      if (!db) return -1
      return db.localeCompare(da)
    })

  if (isLoading) {
    return <div className="text-slate-500 text-sm">Loading wallet...</div>
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center justify-between mb-5 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-white">My Cards</h2>
          <p className="text-slate-400 text-sm mt-1">Manage the credit cards in your wallet.</p>
        </div>
        <button
          type="button"
          onClick={() => setWalletCardModal({ mode: 'add' })}
          className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Card
        </button>
      </div>

      <div className="min-h-0 overflow-y-auto flex-1">
        {inWalletCards.length === 0 ? (
          <div className="border-2 border-dashed border-slate-700/60 rounded-xl py-12 px-6 text-center">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mx-auto text-slate-600 mb-3">
              <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
              <line x1="1" y1="10" x2="23" y2="10" />
            </svg>
            <p className="text-slate-400 text-sm font-medium">No cards yet</p>
            <p className="text-slate-500 text-xs mt-1">Add your first credit card to your wallet.</p>
          </div>
        ) : (
          <ul className="space-y-1.5">
            {inWalletCards.map((inst) => {
              const cardName = inst.card_name ?? `Card #${inst.card_id}`
              const isPc = inst.product_change_date != null
              return (
                <li
                  key={inst.id}
                  className="group bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 hover:border-slate-600 rounded-xl transition-colors cursor-pointer overflow-hidden"
                  onClick={() => setWalletCardModal({ mode: 'edit', instance: inst })}
                >
                  <div className="flex items-center gap-3 px-3 py-2">
                    <div className="w-[72px] h-11 shrink-0 rounded overflow-hidden bg-slate-700/50">
                      <CardPhoto slug={inst.photo_slug} name={cardName} />
                    </div>
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 flex-wrap">
                        <p className="text-sm font-medium text-white truncate">{cardName}</p>
                        {isPc && (
                          <span
                            className="text-[10px] font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50 rounded px-1.5 py-0.5 shrink-0"
                            title={`Product change · ${inst.product_change_date}`}
                          >
                            PC
                          </span>
                        )}
                      </div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        {inst.issuer_name && (
                          <span className="text-xs text-slate-400">{inst.issuer_name}</span>
                        )}
                        {inst.issuer_name && inst.opening_date && (
                          <span className="text-slate-600 text-xs">·</span>
                        )}
                        {inst.opening_date && (
                          <span className="text-xs text-slate-500">
                            Opened {inst.opening_date}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right shrink-0 mr-1">
                      <p className="text-xs tabular-nums text-white">
                        {inst.credit_totals
                          .filter((t) => t.value > 0)
                          .map((t) => (
                            <span key={`${t.kind}-${t.currency_id ?? 'cash'}`}>
                              Credits:{' '}
                              <span className="text-emerald-400">
                                {t.kind === 'cash'
                                  ? formatMoney(t.value)
                                  : `${formatPoints(t.value)} ${pointsUnitLabel(t.currency_name)}`}
                              </span>
                              <span className="text-slate-600 mx-1.5">·</span>
                            </span>
                          ))}
                        Annual Fee:{' '}
                        {(inst.annual_fee ?? 0) > 0 ? (
                          <span className="text-red-400">{formatMoney(inst.annual_fee ?? 0)}</span>
                        ) : (
                          <span className="text-emerald-400">$0</span>
                        )}
                      </p>
                    </div>
                    <button
                      type="button"
                      className="p-1.5 rounded-lg text-slate-700 hover:text-red-400 hover:bg-red-950/40 opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 shrink-0"
                      aria-label="Remove card"
                      title="Remove"
                      onClick={(e) => {
                        e.stopPropagation()
                        setPendingRemoval({ instanceId: inst.id, cardName })
                      }}
                      disabled={removeCardMutation.isPending}
                    >
                      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polyline points="3 6 5 6 21 6" />
                        <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                      </svg>
                    </button>
                  </div>
                </li>
              )
            })}
          </ul>
        )}
      </div>

      {pendingRemoval && (
        <DeleteCardWarningModal
          cardName={pendingRemoval.cardName}
          isLoading={removeCardMutation.isPending}
          onClose={() => setPendingRemoval(null)}
          onConfirm={() => {
            removeCardMutation.mutate(pendingRemoval.instanceId, {
              onSuccess: () => setPendingRemoval(null),
            })
          }}
        />
      )}

      {walletCardModal && (
        <WalletCardModal
          key={walletCardModal.mode === 'add' ? 'add' : walletCardModal.instance.id}
          mode="owned-base"
          isAddFlow={walletCardModal.mode === 'add'}
          ownedInstance={
            walletCardModal.mode === 'edit' ? walletCardModal.instance : undefined
          }
          existingCardIds={cardInstances.map((c) => c.card_id)}
          onClose={() => setWalletCardModal(null)}
          onAddOwned={(payload) => addCardMutation.mutate(payload)}
          onSaveOwned={(payload) => {
            if (walletCardModal.mode !== 'edit') return
            updateCardMutation.mutate(
              { instanceId: walletCardModal.instance.id, payload },
              { onSuccess: () => setWalletCardModal(null) },
            )
          }}
          onDeleteOwned={(instance) =>
            setPendingRemoval({
              instanceId: instance.id,
              cardName: instance.card_name ?? `Card #${instance.card_id}`,
            })
          }
          isLoading={addCardMutation.isPending || updateCardMutation.isPending}
          showCategoryPriorityTab={false}
        />
      )}
    </div>
  )
}
