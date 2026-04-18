import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  walletSpendItemsApi,
  walletsApi,
  type UserSpendCategory,
  type WalletSpendItem,
} from '../../../api/client'
import { useUserSpendCategories } from '../../../hooks/useUserSpendCategories'
import { useMyWallet } from '../hooks/useMyWallet'
import { queryKeys } from '../../../lib/queryKeys'
import { ModalBackdrop } from '../../../components/ModalBackdrop'
import { InfoIconButton, InfoPopover } from '../../../components/InfoPopover'

interface SpendingTabProps {
  walletId: number | null
}

export function SpendingTab({ walletId }: SpendingTabProps) {
  const queryClient = useQueryClient()
  const [editingAmountId, setEditingAmountId] = useState<number | null>(null)
  const [amountDraft, setAmountDraft] = useState('')
  const [showPicker, setShowPicker] = useState(false)
  // In-flight slider drag; null means "show committed value from wallet".
  const [draftForeignPct, setDraftForeignPct] = useState<number | null>(null)
  const [showForeignInfo, setShowForeignInfo] = useState(false)

  const { data: spendItems = [], isLoading } = useQuery({
    queryKey: queryKeys.walletSpendItems(walletId),
    queryFn: () => walletSpendItemsApi.list(walletId!),
    enabled: walletId != null,
  })

  const { data: categories = [] } = useUserSpendCategories()
  const { data: wallet } = useMyWallet()

  const foreignSpendPercent = draftForeignPct ?? wallet?.foreign_spend_percent ?? 0

  const updateWalletMutation = useMutation({
    mutationFn: (pct: number) =>
      walletsApi.update(walletId!, { foreign_spend_percent: pct }),
    onSuccess: () => {
      setDraftForeignPct(null)
      queryClient.invalidateQueries({ queryKey: queryKeys.myWallet() })
    },
  })

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.walletSpendItems(walletId) })

  const createMutation = useMutation({
    mutationFn: (payload: { user_spend_category_id: number; amount?: number }) =>
      walletSpendItemsApi.create(walletId!, payload),
    onSuccess: invalidate,
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, amount }: { id: number; amount: number }) =>
      walletSpendItemsApi.update(walletId!, id, { amount }),
    onSuccess: invalidate,
  })

  const deleteMutation = useMutation({
    mutationFn: (id: number) => walletSpendItemsApi.delete(walletId!, id),
    onSuccess: invalidate,
  })

  function startEditAmount(item: WalletSpendItem) {
    setEditingAmountId(item.id)
    setAmountDraft(item.amount === 0 ? '' : String(Math.round(item.amount)))
  }

  function commitAmount(item: WalletSpendItem) {
    const val = amountDraft === '' ? 0 : parseFloat(amountDraft)
    if (!isNaN(val) && val >= 0 && val !== item.amount) {
      updateMutation.mutate({ id: item.id, amount: val })
    }
    setEditingAmountId(null)
  }

  function handlePickCategory(category: UserSpendCategory) {
    setShowPicker(false)
    createMutation.mutate({ user_spend_category_id: category.id })
  }

  function requestDeleteItem(item: WalletSpendItem) {
    const catName = item.user_spend_category?.name ?? 'Unknown'
    if (window.confirm(`Remove "${catName}" from spend?`)) {
      deleteMutation.mutate(item.id)
    }
  }

  const existingCategoryIds = new Set(spendItems.map((i) => i.user_spend_category_id).filter((id): id is number => id != null))
  const totalSpend = spendItems.reduce((sum, item) => sum + (item.amount || 0), 0)

  if (isLoading) {
    return <div className="text-slate-500 text-sm">Loading spending...</div>
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      <div className="flex items-center justify-between mb-5 shrink-0">
        <div>
          <h2 className="text-xl font-bold text-white">Annual Spending</h2>
          <p className="text-slate-400 text-sm mt-1">Track how much you spend in each category per year.</p>
        </div>
        <button
          type="button"
          onClick={() => setShowPicker(true)}
          className="flex items-center justify-center gap-1.5 px-4 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
            <line x1="12" y1="5" x2="12" y2="19" />
            <line x1="5" y1="12" x2="19" y2="12" />
          </svg>
          Add Category
        </button>
      </div>

      <div className="flex gap-3 mb-4 shrink-0">
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center w-48 shrink-0 flex flex-col justify-center">
          <p className="text-[10px] text-slate-400 uppercase tracking-wider">Total Annual Spend</p>
          <p className="text-xl font-bold text-white mt-0.5 tabular-nums">${totalSpend.toLocaleString()}</p>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 flex-1 min-w-0 flex flex-col justify-center">
          <div className="flex items-center justify-between mb-1">
            <div className="flex items-center gap-1">
              <span className="text-xs text-slate-400">Foreign Spend</span>
              <InfoIconButton onClick={() => setShowForeignInfo(true)} label="How foreign spend affects calculation" />
            </div>
            <span className="text-xs font-medium text-slate-200 tabular-nums">
              {Math.round(foreignSpendPercent)}%
            </span>
          </div>
          <input
            type="range"
            min={0}
            max={100}
            value={foreignSpendPercent}
            disabled={walletId == null}
            onChange={(e) => setDraftForeignPct(Number(e.target.value))}
            onMouseUp={(e) => {
              const pct = Number((e.target as HTMLInputElement).value)
              if (walletId != null) updateWalletMutation.mutate(pct)
            }}
            onTouchEnd={(e) => {
              const pct = Number((e.target as HTMLInputElement).value)
              if (walletId != null) updateWalletMutation.mutate(pct)
            }}
            className="w-full h-1.5 accent-indigo-500 cursor-pointer disabled:cursor-not-allowed disabled:opacity-50"
          />
          <div className="flex justify-between text-[10px] text-slate-600 mt-1">
            <span>0%</span>
            <span>25%</span>
            <span>50%</span>
            <span>75%</span>
            <span>100%</span>
          </div>
        </div>
      </div>

      {showForeignInfo && (
        <InfoPopover title="Foreign Spend" onClose={() => setShowForeignInfo(false)}>
          <p>
            Percentage of your total spend that occurs as foreign transactions.
            Each spend category is split: the foreign portion is allocated
            separately from the domestic portion.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">FTF priority</p>
            <p>
              Foreign spend goes to no-FTF cards first. If any no-FTF Visa or
              Mastercard exists in the wallet, it gets priority over no-FTF
              cards on other networks (e.g. American Express).
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Per-category multiplier</p>
            <p>
              On the foreign portion of a category, the eligible card earns
              {' '}<span className="font-mono text-[11px] text-slate-300">max(category_mult, foreign_transactions_mult)</span>.
              So a card with a "Foreign Transactions" multiplier (e.g. Atmos
              Summit at 3x) earns its full bonus on foreign Groceries even if
              its normal Groceries rate is lower.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Fallback</p>
            <p>
              If every card in the wallet charges a foreign transaction fee,
              cards compete normally and the user incurs the ~3% fee on the
              winning card's foreign spend.
            </p>
          </div>
        </InfoPopover>
      )}

      <div className="min-h-0 overflow-y-auto flex-1">
        {spendItems.length === 0 ? (
          <div className="border-2 border-dashed border-slate-700/60 rounded-xl py-12 px-6 text-center">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mx-auto text-slate-600 mb-3">
              <line x1="12" y1="1" x2="12" y2="23" />
              <path d="M17 5H9.5a3.5 3.5 0 0 0 0 7h5a3.5 3.5 0 0 1 0 7H6" />
            </svg>
            <p className="text-slate-400 text-sm font-medium">No spend categories</p>
            <p className="text-slate-500 text-xs mt-1">Add categories to track your annual spending.</p>
          </div>
        ) : (
          <div className="rounded-lg border border-slate-800 overflow-hidden">
            <table className="w-full text-sm">
              <thead className="bg-slate-900">
                <tr>
                  <th className="text-left text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-slate-800">Category</th>
                  <th className="text-center text-sm font-semibold text-slate-300 px-3 py-2.5 border-b border-slate-800 w-40">Annual Spend</th>
                  <th className="w-12 border-b border-slate-800" />
                </tr>
              </thead>
              <tbody>
                {spendItems.map((item) => {
                  const isEditing = editingAmountId === item.id
                  const catName = item.user_spend_category?.name ?? 'Unknown'
                  const isLocked = item.user_spend_category?.is_system && catName === 'All Other'
                  return (
                    <tr key={item.id} className="border-b border-slate-800/60 last:border-b-0">
                      <td className="text-left px-3 py-2 text-slate-200">{catName}</td>
                      <td className="text-center px-2 py-2 tabular-nums">
                        <div className="relative w-full">
                          <span className="absolute left-1.5 top-1/2 -translate-y-1/2 text-xs text-slate-500 pointer-events-none">$</span>
                          <input
                            type="text"
                            inputMode="numeric"
                            pattern="[0-9]*"
                            value={isEditing ? amountDraft : item.amount === 0 ? '' : Math.round(item.amount)}
                            placeholder="0"
                            onFocus={() => startEditAmount(item)}
                            onChange={(e) => setAmountDraft(e.target.value.replace(/[^0-9]/g, ''))}
                            onBlur={() => commitAmount(item)}
                            onKeyDown={(e) => {
                              if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur()
                              if (e.key === 'Escape') {
                                setEditingAmountId(null)
                                ;(e.currentTarget as HTMLInputElement).blur()
                              }
                            }}
                            className="w-full min-w-0 bg-slate-700 border border-slate-600 text-white text-sm tabular-nums text-right pl-4 pr-1.5 py-0.5 rounded outline-none focus:border-indigo-500 placeholder:text-slate-500"
                          />
                        </div>
                      </td>
                      <td className="px-2 py-2 text-center">
                        {!isLocked && (
                          <button
                            type="button"
                            onClick={() => requestDeleteItem(item)}
                            disabled={deleteMutation.isPending}
                            className="p-1 rounded text-slate-600 hover:text-red-400 hover:bg-red-950/40 transition-colors disabled:opacity-50"
                            title="Remove"
                          >
                            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                              <polyline points="3 6 5 6 21 6" />
                              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
                            </svg>
                          </button>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {showPicker && (
        <ModalBackdrop onClose={() => setShowPicker(false)}>
          <div className="bg-slate-900 border border-slate-700 rounded-xl shadow-xl max-w-xl w-full m-4 max-h-[90vh] flex flex-col">
            <div className="p-5 border-b border-slate-700 shrink-0">
              <h3 className="text-lg font-bold text-white">Add spend category</h3>
              <p className="text-xs text-slate-400 mt-1">Pick a category to track your annual spend.</p>
            </div>
            <div className="overflow-y-auto flex-1 divide-y divide-slate-800">
              {categories.map((cat) => {
                const alreadyAdded = existingCategoryIds.has(cat.id)
                return (
                  <button
                    key={cat.id}
                    onClick={() => !alreadyAdded && handlePickCategory(cat)}
                    disabled={alreadyAdded}
                    className={`w-full text-left px-4 py-2 text-sm transition-colors ${
                      alreadyAdded ? 'text-slate-600 cursor-default' : 'text-slate-200 hover:bg-slate-800'
                    }`}
                  >
                    <span>{cat.name}</span>
                    {alreadyAdded && <span className="ml-2 text-xs text-slate-600">added</span>}
                  </button>
                )
              })}
            </div>
            <div className="p-3 border-t border-slate-700 shrink-0">
              <button
                onClick={() => setShowPicker(false)}
                className="w-full text-sm text-slate-400 hover:text-slate-200 py-1.5 rounded-lg hover:bg-slate-800 transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </ModalBackdrop>
      )}
    </div>
  )
}
