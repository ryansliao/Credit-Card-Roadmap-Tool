import type { WalletSpendItem } from '../../../../api/client'
import { formatMoney } from '../../../../utils/format'
import { useWalletSpendCategoriesTable } from '../../hooks/useWalletSpendCategoriesTable'
import AddSpendCategoryPicker from './AddSpendCategoryPicker'

type SpendItemRowProps = {
  item: WalletSpendItem
  isEditingAmount: boolean
  amountDraft: string
  onAmountDraftChange: (value: string) => void
  onStartEditAmount: () => void
  onCommitAmount: () => void
  onCancelEditAmount: () => void
  onRequestDelete: () => void
  deletePending: boolean
}

function SpendItemRow({
  item,
  isEditingAmount,
  amountDraft,
  onAmountDraftChange,
  onStartEditAmount,
  onCommitAmount,
  onCancelEditAmount,
  onRequestDelete,
  deletePending,
}: SpendItemRowProps) {
  const cat = item.spend_category
  const isSystem = cat.is_system

  return (
    <div className="border-b border-slate-800 py-2">
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm text-slate-200 font-medium flex-1 truncate flex items-center gap-2 min-w-0">
          <span className="truncate">{cat.category}</span>
        </span>
        <div className="flex items-center gap-1 shrink-0">
          {isEditingAmount ? (
            <input
              autoFocus
              className="w-24 bg-slate-700 text-white text-sm text-right px-2 py-0.5 rounded border border-indigo-500 outline-none"
              value={amountDraft}
              onChange={(e) => onAmountDraftChange(e.target.value)}
              onBlur={onCommitAmount}
              onKeyDown={(e) => {
                if (e.key === 'Enter') onCommitAmount()
                if (e.key === 'Escape') onCancelEditAmount()
              }}
            />
          ) : (
            <button
              className="text-sm text-indigo-300 hover:text-indigo-100 w-24 text-right"
              onClick={onStartEditAmount}
            >
              {formatMoney(item.amount)}
            </button>
          )}
          {!isSystem && (
            <button
              onClick={onRequestDelete}
              disabled={deletePending}
              className="p-1 rounded text-slate-600 hover:text-red-400 hover:bg-red-950/40 disabled:opacity-50"
              aria-label="Delete spend category"
              title="Delete"
            >
              <svg
                width="13"
                height="13"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <polyline points="3 6 5 6 21 6" />
                <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
              </svg>
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

export function AnnualSpendPanel({
  walletId,
  onSpendChange,
}: {
  walletId: number | null
  onSpendChange?: () => void
}) {
  const {
    spendItems,
    isLoading,
    editingAmountId,
    amountDraft,
    setAmountDraft,
    startEditAmount,
    commitAmount,
    cancelEditAmount,
    showPicker,
    closePicker,
    openPicker,
    handlePickCategory,
    mutationError,
    deleteMutationIsPending,
    requestDeleteItem,
  } = useWalletSpendCategoriesTable(walletId, onSpendChange)

  const existingCategoryIds = new Set(spendItems.map((i) => i.spend_category_id))

  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 min-w-0 min-h-0 h-full flex flex-col overflow-hidden">
      <div className="flex items-center justify-between gap-2 mb-3 shrink-0">
        <h2 className="text-sm font-semibold text-slate-200">Annual Spend</h2>
        {walletId != null && (
          <button
            type="button"
            onClick={openPicker}
            className="p-1 rounded text-slate-500 hover:text-indigo-400 hover:bg-slate-800 transition-colors shrink-0"
            aria-label="Add spend category"
            title="Add spend category"
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
          </button>
        )}
      </div>
      <div className="min-h-0 overflow-y-auto flex-1">
        {isLoading ? (
          <div className="text-slate-500 text-sm">Loading…</div>
        ) : (
          <div className="space-y-1">
            {spendItems.length === 0 && (
              <p className="text-slate-500 text-xs pb-2">
                No spend categories yet. Add one to configure your annual spend.
              </p>
            )}
            {spendItems.map((item) => (
              <SpendItemRow
                key={item.id}
                item={item}
                isEditingAmount={editingAmountId === item.id}
                amountDraft={amountDraft}
                onAmountDraftChange={setAmountDraft}
                onStartEditAmount={() => startEditAmount(item)}
                onCommitAmount={() => commitAmount(item)}
                onCancelEditAmount={cancelEditAmount}
                onRequestDelete={() => requestDeleteItem(item)}
                deletePending={deleteMutationIsPending}
              />
            ))}

            {mutationError && (
              <p className="text-red-400 text-xs mt-2" role="alert">
                {mutationError}
              </p>
            )}
          </div>
        )}
      </div>

      {showPicker && (
        <AddSpendCategoryPicker
          existingCategoryIds={existingCategoryIds}
          onSelect={handlePickCategory}
          onClose={closePicker}
        />
      )}
    </div>
  )
}
