import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import {
  walletCategoryWeightsApi,
  type WalletCategoryWeightRow,
} from '../../../api/client'
import { queryKeys } from '../../../lib/queryKeys'

interface Props {
  userCategoryId: number
  onClose: () => void
}

/**
 * Inline accordion editor for a single UserSpendCategory's per-wallet
 * weight overrides. Lazy-fetches on mount; manages a local draft;
 * Save → normalize+persist+invalidate+collapse, Cancel → discard,
 * Reset → DELETE override rows + show defaults.
 */
export function CategoryWeightEditor({ userCategoryId, onClose }: Props) {
  const queryClient = useQueryClient()

  const { data, isLoading, isError } = useQuery({
    queryKey: queryKeys.walletCategoryWeights(userCategoryId),
    queryFn: () => walletCategoryWeightsApi.get(userCategoryId),
  })

  // Draft state: earn_category_id -> typed string (percentage as integer-ish).
  const [draft, setDraft] = useState<Record<number, string>>({})
  const [submitError, setSubmitError] = useState<string | null>(null)

  // Initialize draft when data first arrives (effective_weight * 100, rounded).
  useEffect(() => {
    if (!data) return
    const init: Record<number, string> = {}
    for (const row of data.mappings) {
      init[row.earn_category_id] = String(Math.round(row.effective_weight * 100))
    }
    setDraft(init)
    setSubmitError(null)
  }, [data])

  const totalPct = useMemo(
    () =>
      Object.values(draft).reduce((sum, s) => {
        const n = parseInt(s, 10)
        return sum + (Number.isFinite(n) ? n : 0)
      }, 0),
    [draft],
  )

  const invalidateDownstream = () => {
    queryClient.invalidateQueries({
      queryKey: queryKeys.walletCategoryWeights(userCategoryId),
    })
    queryClient.invalidateQueries({ queryKey: queryKeys.walletSpendItemsSingular() })
    queryClient.invalidateQueries({ queryKey: queryKeys.myWalletWithScenarios() })
  }

  const saveMutation = useMutation({
    mutationFn: () => {
      const payload = {
        weights: Object.entries(draft).map(([id, val]) => ({
          earn_category_id: Number(id),
          weight: Math.max(0, parseInt(val, 10) || 0),
        })),
      }
      return walletCategoryWeightsApi.save(userCategoryId, payload)
    },
    onSuccess: () => {
      invalidateDownstream()
      onClose()
    },
    onError: (err: Error) => setSubmitError(err.message),
  })

  const resetMutation = useMutation({
    mutationFn: () => walletCategoryWeightsApi.reset(userCategoryId),
    onSuccess: () => {
      invalidateDownstream()
      // Stay open so the user sees the defaults snap back.
    },
    onError: (err: Error) => setSubmitError(err.message),
  })

  const handleSave = () => {
    setSubmitError(null)
    if (totalPct <= 0) {
      setSubmitError('Total cannot be 0%.')
      return
    }
    saveMutation.mutate()
  }

  const handleReset = () => {
    if (!window.confirm(`Reset ${data?.user_category_name ?? 'category'} weights to defaults?`)) return
    setSubmitError(null)
    resetMutation.mutate()
  }

  if (isLoading) {
    return (
      <div className="px-3 py-3 text-xs text-ink-faint">Loading defaults…</div>
    )
  }
  if (isError || !data) {
    return (
      <div className="px-3 py-3 text-xs text-neg">
        Failed to load category weights.
      </div>
    )
  }

  const totalIs100 = totalPct === 100

  return (
    <div className="px-3 py-3 bg-page/40">
      <div className="flex items-center justify-between mb-2">
        <p className="text-[11px] text-ink-faint uppercase tracking-wider">
          Mix for {data.user_category_name} spend
        </p>
        <button
          type="button"
          onClick={handleReset}
          disabled={resetMutation.isPending}
          className="text-xs text-ink-muted hover:text-accent disabled:opacity-50"
        >
          Reset to defaults
        </button>
      </div>

      <div className="space-y-1.5">
        {data.mappings.map((row: WalletCategoryWeightRow) => (
          <div key={row.earn_category_id} className="flex items-center gap-3">
            <span className="text-sm text-ink-muted flex-1 min-w-0 truncate">
              {row.earn_category_name}
            </span>
            <div className="relative w-20 shrink-0">
              <input
                type="text"
                inputMode="numeric"
                pattern="[0-9]*"
                value={draft[row.earn_category_id] ?? ''}
                onChange={(e) =>
                  setDraft((prev) => ({
                    ...prev,
                    [row.earn_category_id]: e.target.value.replace(/[^0-9]/g, ''),
                  }))
                }
                className="w-full bg-surface-2 border border-divider text-ink text-sm tabular-nums text-right pr-5 pl-1.5 py-0.5 rounded outline-none focus:border-accent placeholder:text-ink-faint"
              />
              <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-xs text-ink-faint pointer-events-none">
                %
              </span>
            </div>
          </div>
        ))}
      </div>

      <div className="flex items-center justify-between mt-3">
        <span
          className={`text-xs tabular-nums ${
            totalIs100 ? 'text-ink-muted' : 'text-warn'
          }`}
        >
          Total: {totalPct}%
          {!totalIs100 && (
            <span className="ml-2 text-ink-faint">
              (will be normalized to 100% on save)
            </span>
          )}
        </span>
        <div className="flex items-center gap-2">
          {submitError && (
            <span className="text-xs text-neg">{submitError}</span>
          )}
          <button
            type="button"
            onClick={onClose}
            disabled={saveMutation.isPending}
            className="text-xs text-ink-muted hover:text-ink px-2 py-1 rounded disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={saveMutation.isPending}
            className="text-xs font-medium bg-accent text-page hover:opacity-90 px-3 py-1 rounded disabled:opacity-50"
          >
            {saveMutation.isPending ? 'Saving…' : 'Save'}
          </button>
        </div>
      </div>
    </div>
  )
}
