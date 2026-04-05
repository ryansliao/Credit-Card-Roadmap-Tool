import { useState } from 'react'
import type { SpendCategory, WalletSpendItem } from '../../../../api/client'
import { formatMoney } from '../../../../utils/format'
import { useAppSpendCategories } from '../../hooks/useAppSpendCategories'
import { useWalletSpendCategoriesTable } from '../../hooks/useWalletSpendCategoriesTable'

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

function InlineCategoryDropdown({
  existingCategoryIds,
  onSelect,
}: {
  existingCategoryIds: Set<number>
  onSelect: (category: SpendCategory) => void
}) {
  const [search, setSearch] = useState('')
  const [expandedIds, setExpandedIds] = useState<Set<number>>(new Set())
  const { data: categories = [], isLoading } = useAppSpendCategories()

  const visible = categories.filter((c) => !c.is_system)
  const searchLower = search.toLowerCase()
  const filtered = search
    ? visible.filter(
        (c) =>
          c.category.toLowerCase().includes(searchLower) ||
          c.children.some((ch) => ch.category.toLowerCase().includes(searchLower))
      )
    : visible

  return (
    <div className="border-t border-slate-700 mt-2 pt-2">
      <input
        type="search"
        value={search}
        onChange={(e) => setSearch(e.target.value)}
        placeholder="Search categories…"
        autoFocus
        className="w-full bg-slate-800 border border-slate-600 text-white text-xs px-2.5 py-1.5 rounded-lg outline-none focus:border-indigo-500 mb-1"
      />
      <div className="max-h-48 overflow-y-auto">
        {isLoading && <p className="text-slate-500 text-xs px-2 py-1">Loading…</p>}
        {!isLoading && filtered.length === 0 && (
          <p className="text-slate-500 text-xs px-2 py-1">No categories match.</p>
        )}
        {filtered.map((cat) => {
          const alreadyAdded = existingCategoryIds.has(cat.id)
          const hasChildren = cat.children.length > 0
          const isExpanded = expandedIds.has(cat.id)
          return (
            <div key={cat.id}>
              <div className="flex items-center gap-1">
                <button
                  onClick={() => !alreadyAdded && onSelect(cat)}
                  disabled={alreadyAdded}
                  className={`flex-1 text-left px-2 py-1 text-xs rounded transition-colors ${
                    alreadyAdded
                      ? 'text-slate-600 cursor-default'
                      : 'text-slate-200 hover:bg-slate-800'
                  }`}
                >
                  {cat.category}
                </button>
                {hasChildren && (
                  <button
                    onClick={() =>
                      setExpandedIds((prev) => {
                        const next = new Set(prev)
                        if (next.has(cat.id)) next.delete(cat.id)
                        else next.add(cat.id)
                        return next
                      })
                    }
                    className="px-1 py-1 text-slate-500 hover:text-slate-300"
                  >
                    <svg
                      width="10"
                      height="10"
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="currentColor"
                      strokeWidth="2.5"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      className={`transition-transform ${isExpanded ? 'rotate-90' : ''}`}
                    >
                      <polyline points="9 18 15 12 9 6" />
                    </svg>
                  </button>
                )}
              </div>
              {hasChildren && isExpanded && (
                <div className="ml-4 border-l border-slate-700">
                  {cat.children.map((child) => {
                    const childAdded = existingCategoryIds.has(child.id)
                    return (
                      <button
                        key={child.id}
                        onClick={() => !childAdded && onSelect(child)}
                        disabled={childAdded}
                        className={`block w-full text-left px-2 py-1 text-xs rounded transition-colors ${
                          childAdded
                            ? 'text-slate-600 cursor-default'
                            : 'text-slate-300 hover:bg-slate-800'
                        }`}
                      >
                        {child.category}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
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

      {walletId != null && !showPicker && (
        <button
          type="button"
          onClick={openPicker}
          className="shrink-0 mt-2 w-full text-sm text-slate-500 hover:text-indigo-400 hover:bg-slate-800 rounded-lg py-2 transition-colors"
        >
          + Add Spend Category
        </button>
      )}

      {showPicker && (
        <div className="shrink-0">
          <InlineCategoryDropdown
            existingCategoryIds={existingCategoryIds}
            onSelect={(cat) => {
              handlePickCategory(cat)
            }}
          />
          <button
            onClick={closePicker}
            className="mt-1 w-full text-xs text-slate-500 hover:text-slate-300 py-1"
          >
            Cancel
          </button>
        </div>
      )}
    </div>
  )
}
