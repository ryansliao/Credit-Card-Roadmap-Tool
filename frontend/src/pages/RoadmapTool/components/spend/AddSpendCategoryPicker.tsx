import { useState } from 'react'
import type { SpendCategory } from '../../../../api/client'
import { useAppSpendCategories } from '../../hooks/useAppSpendCategories'

interface Props {
  existingCategoryIds: Set<number>
  onSelect: (category: SpendCategory) => void
  onClose: () => void
}

function ChevronIcon({ open }: { open: boolean }) {
  return (
    <svg
      width="12"
      height="12"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.5"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`transition-transform shrink-0 ${open ? 'rotate-90' : ''}`}
    >
      <polyline points="9 18 15 12 9 6" />
    </svg>
  )
}

function CategoryRow({
  category,
  existingIds,
  onSelect,
}: {
  category: SpendCategory
  existingIds: Set<number>
  onSelect: (cat: SpendCategory) => void
}) {
  const [expanded, setExpanded] = useState(false)
  const hasChildren = category.children.length > 0
  const alreadyAdded = existingIds.has(category.id)

  return (
    <div>
      <div className="flex items-center gap-1">
        <button
          onClick={() => !alreadyAdded && onSelect(category)}
          disabled={alreadyAdded}
          className={`flex-1 text-left px-4 py-2 text-sm transition-colors ${
            alreadyAdded
              ? 'text-slate-600 cursor-default'
              : 'text-slate-200 hover:bg-slate-800'
          }`}
        >
          <span>{category.category}</span>
          {alreadyAdded && (
            <span className="ml-2 text-xs text-slate-600">added</span>
          )}
        </button>
        {hasChildren && (
          <button
            onClick={() => setExpanded((v) => !v)}
            className="px-2 py-2 text-slate-500 hover:text-slate-300"
            aria-label={expanded ? 'Collapse' : 'Expand'}
          >
            <ChevronIcon open={expanded} />
          </button>
        )}
      </div>

      {hasChildren && expanded && (
        <div className="border-l border-slate-700 ml-6">
          {category.children.map((child) => (
            <div key={child.id} className="flex items-center">
              <button
                onClick={() => !existingIds.has(child.id) && onSelect(child)}
                disabled={existingIds.has(child.id)}
                className={`flex-1 text-left px-4 py-1.5 text-sm transition-colors ${
                  existingIds.has(child.id)
                    ? 'text-slate-600 cursor-default'
                    : 'text-slate-300 hover:bg-slate-800'
                }`}
              >
                <span>{child.category}</span>
                {existingIds.has(child.id) && (
                  <span className="ml-2 text-xs text-slate-600">added</span>
                )}
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default function AddSpendCategoryPicker({ existingCategoryIds, onSelect, onClose }: Props) {
  const [search, setSearch] = useState('')
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
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/60"
      onClick={onClose}
    >
      <div
        className="bg-slate-900 border border-slate-700 rounded-xl shadow-xl max-w-xl w-full m-4 max-h-[90vh] flex flex-col"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="p-5 border-b border-slate-700 shrink-0">
          <h3 className="text-lg font-bold text-white">Add spend category</h3>
          <p className="text-xs text-slate-400 mt-1">
            Pick a category. Sub-categories (shown when expanded) give more accurate multiplier matching.
          </p>
        </div>

        <div className="p-3 border-b border-slate-700 shrink-0">
          <input
            type="search"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search categories…"
            autoFocus
            className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
          />
        </div>

        <div className="overflow-y-auto flex-1 divide-y divide-slate-800">
          {isLoading && (
            <p className="text-slate-500 text-xs px-4 py-3">Loading…</p>
          )}
          {!isLoading && filtered.length === 0 && (
            <p className="text-slate-500 text-xs px-4 py-3">No categories match.</p>
          )}
          {filtered.map((cat) => (
            <CategoryRow
              key={cat.id}
              category={cat}
              existingIds={existingCategoryIds}
              onSelect={onSelect}
            />
          ))}
        </div>

        <div className="p-3 border-t border-slate-700 shrink-0">
          <button
            onClick={onClose}
            className="w-full text-sm text-slate-400 hover:text-slate-200 py-1.5 rounded-lg hover:bg-slate-800 transition-colors"
          >
            Cancel
          </button>
        </div>
      </div>
    </div>
  )
}
