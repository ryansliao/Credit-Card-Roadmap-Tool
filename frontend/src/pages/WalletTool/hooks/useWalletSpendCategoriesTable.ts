import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  walletSpendItemsApi,
  type SpendCategory,
  type WalletSpendItem,
} from '../../../api/client'
import { queryKeys } from '../lib/queryKeys'

export function useWalletSpendCategoriesTable(
  walletId: number | null,
  onSpendChange?: () => void
) {
  const queryClient = useQueryClient()
  const [editingAmountId, setEditingAmountId] = useState<number | null>(null)
  const [amountDraft, setAmountDraft] = useState('')
  const [showPicker, setShowPicker] = useState(false)
  const [mutationError, setMutationError] = useState<string | undefined>()

  const { data: spendItems = [], isLoading } = useQuery({
    queryKey: queryKeys.walletSpendItems(walletId),
    queryFn: () => walletSpendItemsApi.list(walletId!),
    enabled: walletId != null,
  })

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.walletSpendItems(walletId) })

  const createMutation = useMutation({
    mutationFn: (payload: { spend_category_id: number; amount: number }) =>
      walletSpendItemsApi.create(walletId!, payload),
    onSuccess: () => {
      invalidate()
      setMutationError(undefined)
      onSpendChange?.()
    },
    onError: (e: Error) => setMutationError(e.message),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: number }) =>
      walletSpendItemsApi.update(walletId!, id, { amount }),
    onSuccess: () => {
      invalidate()
      setMutationError(undefined)
      onSpendChange?.()
    },
    onError: (e: Error) => setMutationError(e.message),
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => walletSpendItemsApi.delete(walletId!, id),
    onSuccess: () => {
      invalidate()
      onSpendChange?.()
    },
  })

  function startEditAmount(item: WalletSpendItem) {
    setEditingAmountId(item.id)
    setAmountDraft(String(Math.round(item.amount)))
  }

  function commitAmount(item: WalletSpendItem) {
    const val = parseFloat(amountDraft)
    if (!isNaN(val) && val >= 0 && val !== item.amount) {
      updateMutation.mutate({ id: item.id, amount: val })
    }
    setEditingAmountId(null)
  }

  function openPicker() {
    setMutationError(undefined)
    setShowPicker(true)
  }

  function handlePickCategory(category: SpendCategory) {
    setShowPicker(false)
    setMutationError(undefined)
    createMutation.mutate({ spend_category_id: category.id, amount: 0 })
  }

  function requestDeleteItem(item: WalletSpendItem) {
    if (window.confirm(`Remove "${item.spend_category.category}" from spend?`)) {
      deleteMutation.mutate(item.id)
    }
  }

  return {
    spendItems,
    isLoading,
    editingAmountId,
    amountDraft,
    setAmountDraft,
    startEditAmount,
    commitAmount,
    cancelEditAmount: () => setEditingAmountId(null),
    showPicker,
    closePicker: () => setShowPicker(false),
    openPicker,
    handlePickCategory,
    mutationError,
    deleteMutationIsPending: deleteMutation.isPending,
    requestDeleteItem,
  }
}
