import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  walletsApi,
  walletCardCategoryPriorityApi,
  type AddCardToWalletPayload,
  type UpdateWalletCardPayload,
  type WalletCard,
} from '../../../api/client'
import { WalletCardModal } from '../../../components/cards/WalletCardModal'
import { DeleteCardWarningModal } from '../../../components/cards/DeleteCardWarningModal'
import { useCreditLibrary } from '../../../hooks/useCreditLibrary'
import { queryKeys } from '../../../lib/queryKeys'
import { formatMoney } from '../../../utils/format'
import { CardPhoto } from './CardPhoto'

type WalletCardModalOpen = { mode: 'add' } | { mode: 'edit'; walletCard: WalletCard }

interface WalletTabProps {
  walletId: number | null
  walletCards: WalletCard[]
  isLoading: boolean
}

export function WalletTab({ walletId, walletCards, isLoading }: WalletTabProps) {
  const queryClient = useQueryClient()
  const [walletCardModal, setWalletCardModal] = useState<WalletCardModalOpen | null>(null)
  const [pendingRemoval, setPendingRemoval] = useState<{ cardId: number; cardName: string } | null>(null)

  useCreditLibrary()

  const addCardMutation = useMutation({
    mutationFn: ({ walletId, payload }: { walletId: number; payload: AddCardToWalletPayload }) =>
      walletsApi.addCard(walletId, payload),
    onSuccess: async (_data, { walletId, payload }) => {
      if (payload.priority_category_ids && payload.priority_category_ids.length > 0) {
        await walletCardCategoryPriorityApi.set(walletId, payload.card_id, payload.priority_category_ids)
        queryClient.invalidateQueries({ queryKey: queryKeys.walletCategoryPriorities(walletId) })
      }
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      setWalletCardModal(null)
    },
  })

  const removeCardMutation = useMutation({
    mutationFn: ({ walletId, cardId }: { walletId: number; cardId: number }) =>
      walletsApi.removeCard(walletId, cardId),
    onSuccess: (_data, { walletId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
    },
  })

  const updateWalletCardMutation = useMutation({
    mutationFn: ({ walletId, cardId, payload }: { walletId: number; cardId: number; payload: UpdateWalletCardPayload }) =>
      walletsApi.updateCard(walletId, cardId, payload),
    onSuccess: (_data, { walletId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCardCredits(walletId, null) })
    },
  })

  const inWalletCards = walletCards
    .filter((wc) => wc.panel === 'in_wallet')
    .sort((a, b) => {
      const da = a.added_date?.trim() ?? ''
      const db = b.added_date?.trim() ?? ''
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
            {inWalletCards.map((wc) => (
              <li
                key={wc.id}
                className="group bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 hover:border-slate-600 rounded-xl transition-colors cursor-pointer overflow-hidden"
                onClick={() => setWalletCardModal({ mode: 'edit', walletCard: wc })}
              >
                <div className="flex items-center gap-3 px-3 py-2">
                  <div className="w-[72px] h-11 shrink-0 rounded overflow-hidden bg-slate-700/50">
                    <CardPhoto slug={wc.photo_slug} name={wc.card_name ?? `Card #${wc.card_id}`} />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-medium text-white truncate">{wc.card_name ?? `Card #${wc.card_id}`}</p>
                      {wc.acquisition_type === 'product_change' && (
                        <span className="text-[10px] font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50 rounded px-1.5 py-0.5 shrink-0">PC</span>
                      )}
                    </div>
                    <div className="flex items-center gap-1.5 mt-0.5">
                      {wc.issuer_name && <span className="text-xs text-slate-400">{wc.issuer_name}</span>}
                      {wc.issuer_name && wc.added_date && <span className="text-slate-600 text-xs">·</span>}
                      {wc.added_date && (
                        <span className="text-xs text-slate-500">
                          {wc.acquisition_type === 'product_change' ? 'PC' : 'Opened'} {wc.added_date}
                        </span>
                      )}
                    </div>
                  </div>
                  <div className="text-right shrink-0 mr-1">
                    <p className="text-xs tabular-nums text-white">
                      Annual Fee: {(wc.annual_fee ?? 0) > 0 ? <span className="text-red-400">{formatMoney(wc.annual_fee ?? 0)}</span> : <span className="text-emerald-400">$0</span>}
                    </p>
                    {wc.credit_total > 0 && (
                      <p className="text-xs tabular-nums text-white mt-0.5">
                        Credit Value: <span className="text-emerald-400">{formatMoney(wc.credit_total)}</span>
                      </p>
                    )}
                  </div>
                  <button
                    type="button"
                    className="p-1.5 rounded-lg text-slate-700 hover:text-red-400 hover:bg-red-950/40 opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 shrink-0"
                    aria-label="Remove card"
                    title="Remove"
                    onClick={(e) => { e.stopPropagation(); setPendingRemoval({ cardId: wc.card_id, cardName: wc.card_name ?? `Card #${wc.card_id}` }) }}
                    disabled={removeCardMutation.isPending}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <polyline points="3 6 5 6 21 6" />
                      <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                    </svg>
                  </button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {pendingRemoval && walletId && (
        <DeleteCardWarningModal
          cardName={pendingRemoval.cardName}
          isLoading={removeCardMutation.isPending}
          onClose={() => setPendingRemoval(null)}
          onConfirm={() => {
            removeCardMutation.mutate(
              { walletId, cardId: pendingRemoval.cardId },
              { onSuccess: () => setPendingRemoval(null) }
            )
          }}
        />
      )}

      {walletCardModal && walletId && (
        <WalletCardModal
          key={walletCardModal.mode === 'add' ? 'add' : walletCardModal.walletCard.id}
          mode={walletCardModal.mode}
          walletId={walletId}
          walletCard={walletCardModal.mode === 'edit' ? walletCardModal.walletCard : undefined}
          existingCardIds={walletCards.map((wc) => wc.card_id)}
          walletCardIds={walletCards.map((wc) => wc.card_id)}
          onClose={() => setWalletCardModal(null)}
          onAdd={(payload) => addCardMutation.mutate({ walletId, payload: { ...payload, panel: 'in_wallet' } })}
          onSaveEdit={(payload) => {
            if (walletCardModal.mode !== 'edit') return
            updateWalletCardMutation.mutate(
              { walletId, cardId: walletCardModal.walletCard.card_id, payload },
              { onSuccess: () => setWalletCardModal(null) }
            )
          }}
          isLoading={addCardMutation.isPending || updateWalletCardMutation.isPending}
        />
      )}
    </div>
  )
}
