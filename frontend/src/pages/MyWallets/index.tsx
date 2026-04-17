import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { useParams, useNavigate } from 'react-router-dom'
import {
  walletsApi,
  walletCardCategoryPriorityApi,
  type AddCardToWalletPayload,
  type UpdateWalletCardPayload,
  type WalletCard,
} from '../../api/client'
import { WalletCardModal } from '../RoadmapTool/components/cards/WalletCardModal'
import { CreateWalletModal } from '../RoadmapTool/components/wallet/CreateWalletModal'
import { DeleteCardWarningModal } from '../RoadmapTool/components/cards/DeleteCardWarningModal'
import { useCreditLibrary } from '../RoadmapTool/hooks/useCreditLibrary'
import { queryKeys } from '../RoadmapTool/lib/queryKeys'
import { WalletCardList } from './components/WalletCardList'

type WalletCardModalOpen =
  | { mode: 'add' }
  | { mode: 'edit'; walletCard: WalletCard }

export default function MyWalletsPage() {
  const queryClient = useQueryClient()
  const navigate = useNavigate()
  const { walletId: walletIdParam } = useParams<{ walletId: string }>()
  const selectedWalletId = walletIdParam ? Number(walletIdParam) : null
  const setSelectedWalletId = (id: number | null) => {
    if (id == null) navigate('/wallets')
    else navigate(`/wallets/${id}`)
  }
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [walletCardModal, setWalletCardModal] = useState<WalletCardModalOpen | null>(null)
  const [pendingRemoval, setPendingRemoval] = useState<{ cardId: number; cardName: string } | null>(
    null
  )

  const { data: wallets, isLoading: walletsLoading } = useQuery({
    queryKey: queryKeys.wallets(),
    queryFn: () => walletsApi.list(),
  })

  useEffect(() => {
    if (selectedWalletId == null && wallets && wallets.length > 0) {
      const latest = wallets[wallets.length - 1]
      navigate(`/wallets/${latest.id}`, { replace: true })
    }
  }, [wallets, selectedWalletId, navigate])

  useCreditLibrary()

  const createWalletMutation = useMutation({
    mutationFn: (payload: { name: string; description: string }) =>
      walletsApi.create({
        name: payload.name,
        description: payload.description || null,
      }),
    onSuccess: (wallet) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      navigate(`/wallets/${wallet.id}`)
      setShowCreateModal(false)
    },
  })

  const addCardMutation = useMutation({
    mutationFn: ({ walletId, payload }: { walletId: number; payload: AddCardToWalletPayload }) =>
      walletsApi.addCard(walletId, payload),
    onSuccess: async (_data, { walletId, payload }) => {
      if (payload.priority_category_ids && payload.priority_category_ids.length > 0) {
        await walletCardCategoryPriorityApi.set(walletId, payload.card_id, payload.priority_category_ids)
        queryClient.invalidateQueries({ queryKey: queryKeys.walletCategoryPriorities(walletId) })
      }

      queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
      setWalletCardModal(null)
    },
  })

  const removeCardMutation = useMutation({
    mutationFn: ({ walletId, cardId }: { walletId: number; cardId: number }) =>
      walletsApi.removeCard(walletId, cardId),
    onSuccess: (_data, { walletId }) => {
      queryClient.invalidateQueries({ queryKey: queryKeys.wallets() })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
    },
  })

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
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletSettingsCurrencyIds(walletId) })
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCardCredits(walletId, null) })
    },
  })

  const selectedWallet = wallets?.find((w) => w.id === selectedWalletId)
  const inWalletCards = (selectedWallet?.wallet_cards ?? [])
    .filter((wc) => wc.panel === 'in_wallet')
    .sort((a, b) => {
      const da = a.added_date?.trim() ?? ''
      const db = b.added_date?.trim() ?? ''
      if (!da && !db) return 0
      if (!da) return 1
      if (!db) return -1
      return db.localeCompare(da)
    })

  if (walletsLoading) {
    return (
      <div className="max-w-screen-xl mx-auto w-full shrink-0">
        <div className="text-center text-slate-400 py-20">Loading wallets…</div>
      </div>
    )
  }

  return (
    <div className="max-w-3xl mx-auto w-full flex flex-col flex-1 min-h-0">
      {/* Content */}
      <div className="min-w-0 flex-1 min-h-0 flex flex-col">
        {!selectedWallet ? (
          <div className="flex-1 flex items-center justify-center">
            <div className="text-center">
              <svg
                width="48"
                height="48"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
                strokeLinecap="round"
                strokeLinejoin="round"
                className="mx-auto text-slate-600 mb-4"
              >
                <rect x="2" y="5" width="20" height="14" rx="2" />
                <path d="M2 10h20" />
              </svg>
              <p className="text-slate-400 text-sm mb-3">No wallet selected</p>
              <button
                type="button"
                onClick={() => setShowCreateModal(true)}
                className="text-sm font-medium px-4 py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
              >
                Create your first wallet
              </button>
            </div>
          </div>
        ) : (
          <div className="flex-1 min-h-0">
            <WalletCardList
              cards={inWalletCards}
              isRemoving={removeCardMutation.isPending}
              onRemoveCard={(cardId) => {
                const wc = selectedWallet.wallet_cards.find((c) => c.card_id === cardId)
                setPendingRemoval({
                  cardId,
                  cardName: wc?.card_name ?? `Card #${cardId}`,
                })
              }}
              onEditCard={(wc) => setWalletCardModal({ mode: 'edit', walletCard: wc })}
              onAddCard={() => setWalletCardModal({ mode: 'add' })}
              wallets={wallets ?? []}
              selectedWalletId={selectedWalletId}
              onSelectWallet={setSelectedWalletId}
              onCreateWallet={() => setShowCreateModal(true)}
            />
          </div>
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
          walletId={selectedWallet.id}
          walletCard={
            walletCardModal.mode === 'edit' ? walletCardModal.walletCard : undefined
          }
          existingCardIds={selectedWallet.wallet_cards.map((wc) => wc.card_id)}
          walletCardIds={selectedWallet.wallet_cards.map((wc) => wc.card_id)}
          onClose={() => setWalletCardModal(null)}
          onAdd={(payload) =>
            addCardMutation.mutate({ walletId: selectedWallet.id, payload: { ...payload, panel: 'in_wallet' } })
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
