import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  type WalletPortalShare,
  walletPortalShareApi,
  walletsApi,
} from '../../../../api/client'
import { useCardLibrary } from '../../hooks/useCardLibrary'
import { queryKeys } from '../../lib/queryKeys'

/**
 * Per-wallet, per-issuer travel-portal share editor.
 *
 * Shows a row for every issuer that has at least one in-wallet card with a
 * portal-only multiplier (e.g., Chase Freedom Flex's 5x on Chase Travel).
 * The user picks what fraction of their travel-coverable spend they book
 * through that issuer's portal; the calculator credits the portal premium
 * only to that fraction.
 *
 * When `filterByCurrencyId` is supplied, only cards that earn that currency
 * directly are considered — used by the per-currency settings modals so each
 * modal shows just the portal sliders relevant to that currency's ecosystem.
 *
 * Hidden entirely when no eligible in-wallet card exposes a portal multiplier.
 */
export function WalletPortalSharesEditor({
  walletId,
  filterByCurrencyId,
  onChange,
}: {
  walletId: number | null
  filterByCurrencyId?: number
  /** Called after a successful slider commit so the parent can re-run the
   * wallet calculation (portal-share changes affect EAF). */
  onChange?: () => void
}) {
  const queryClient = useQueryClient()
  const { data: cards } = useCardLibrary()
  const { data: wallet } = useQuery({
    queryKey: queryKeys.wallet(walletId ?? 0),
    queryFn: () => walletsApi.get(walletId!),
    enabled: walletId != null,
  })
  const walletCards = wallet?.wallet_cards ?? []

  // Issuers that have at least one in-wallet card with at least one portal
  // multiplier row. We treat a row as portal-flagged if any of its standalone
  // multipliers carries a portal-shaped name (the API doesn't currently expose
  // is_portal directly on the read schema, so we look at the card's full
  // multiplier list and infer from is_portal when present, falling back to
  // category name heuristics for resilience).
  const portalIssuers = useMemo(() => {
    if (!cards || walletCards.length === 0) return []
    // Only "in_wallet" cards contribute to EAF, so on-deck cards must be
    // excluded — otherwise the slider shows but moving it has no effect.
    const inWalletCardIds = new Set(
      walletCards.filter((wc) => wc.panel === 'in_wallet').map((wc) => wc.card_id),
    )
    const issuerMap = new Map<number, { id: number; name: string; cardNames: string[] }>()
    for (const c of cards) {
      if (!inWalletCardIds.has(c.id)) continue
      // Currency-scoped editor (used inside per-currency modals): only count
      // cards whose direct currency matches the modal's currency.
      if (filterByCurrencyId != null && c.currency_id !== filterByCurrencyId) continue
      const portalMults = (c.multipliers ?? []).filter((m) => (m as { is_portal?: boolean }).is_portal)
      if (portalMults.length === 0) continue
      const entry = issuerMap.get(c.issuer_id)
      if (entry) {
        entry.cardNames.push(c.name)
      } else {
        issuerMap.set(c.issuer_id, {
          id: c.issuer_id,
          name: c.issuer.name,
          cardNames: [c.name],
        })
      }
    }
    return Array.from(issuerMap.values()).sort((a, b) => a.name.localeCompare(b.name))
  }, [cards, walletCards, filterByCurrencyId])

  const { data: shares = [] } = useQuery({
    queryKey: queryKeys.walletPortalShares(walletId),
    queryFn: () => walletPortalShareApi.list(walletId!),
    enabled: walletId != null,
  })

  const sharesByIssuer = useMemo(() => {
    const out = new Map<number, WalletPortalShare>()
    for (const s of shares) out.set(s.issuer_id, s)
    return out
  }, [shares])

  const upsertMutation = useMutation({
    mutationFn: (payload: { issuer_id: number; share: number }) =>
      walletPortalShareApi.upsert(walletId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.walletPortalShares(walletId) })
      onChange?.()
    },
  })

  // Local edit buffer so the slider doesn't fire requests on every drag.
  const [pendingByIssuer, setPendingByIssuer] = useState<Record<number, number>>({})

  if (walletId == null || portalIssuers.length === 0) return null

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/40 p-3 mt-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
        Travel Portal Shares
      </p>
      <p className="text-[11px] text-slate-400 mb-3">
        What fraction of your travel-coverable spend do you book through each
        issuer's portal? Cards earn elevated rates only on the portal portion.
      </p>
      <ul className="space-y-3">
        {portalIssuers.map((iss) => {
          const existing = sharesByIssuer.get(iss.id)
          const value = pendingByIssuer[iss.id] ?? existing?.share ?? 0
          const pct = Math.round(value * 100)
          return (
            <li key={iss.id}>
              <div className="flex items-center justify-between text-xs text-slate-300 mb-1">
                <span>
                  {iss.name} Travel
                  <span className="text-slate-500 ml-1">
                    ({iss.cardNames.length} card{iss.cardNames.length === 1 ? '' : 's'})
                  </span>
                </span>
                <span className="text-indigo-300 tabular-nums">{pct}%</span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                step={5}
                value={pct}
                onChange={(e) =>
                  setPendingByIssuer((prev) => ({
                    ...prev,
                    [iss.id]: Number(e.target.value) / 100,
                  }))
                }
                onMouseUp={(e) => {
                  // Read directly from the input — pendingByIssuer may still
                  // be stale here because onChange's setState hasn't flushed
                  // a re-render before onMouseUp fires.
                  const next = Number((e.target as HTMLInputElement).value) / 100
                  if (next !== (existing?.share ?? 0)) {
                    upsertMutation.mutate({ issuer_id: iss.id, share: next })
                  }
                }}
                onTouchEnd={(e) => {
                  const next = Number((e.target as HTMLInputElement).value) / 100
                  if (next !== (existing?.share ?? 0)) {
                    upsertMutation.mutate({ issuer_id: iss.id, share: next })
                  }
                }}
                className="w-full"
              />
            </li>
          )
        })}
      </ul>
    </div>
  )
}
