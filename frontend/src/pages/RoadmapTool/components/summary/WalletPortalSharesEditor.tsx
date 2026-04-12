import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  type WalletPortalShare,
  travelPortalApi,
  walletPortalShareApi,
  walletsApi,
} from '../../../../api/client'
import { useCardLibrary } from '../../hooks/useCardLibrary'
import { queryKeys } from '../../lib/queryKeys'

/**
 * Per-wallet, per-travel-portal share editor.
 *
 * Shows a row for every TravelPortal that has at least one in-wallet card
 * with a portal-only multiplier (e.g., Chase Freedom Flex's 5x on Chase
 * Travel). The user picks what fraction of their travel-coverable spend
 * they book through that portal; the calculator credits the portal premium
 * only to that fraction.
 *
 * When `filterByCurrencyId` is supplied, only portals whose member cards
 * include at least one card earning that currency directly are shown — used
 * by the per-currency settings modals so each modal lists just the portals
 * relevant to that currency's ecosystem.
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
  const { data: travelPortals = [] } = useQuery({
    queryKey: queryKeys.travelPortals,
    queryFn: () => travelPortalApi.list(),
  })
  const walletCards = wallet?.wallet_cards ?? []

  // Travel portals that have at least one in-wallet card that (a) belongs to
  // the portal, (b) carries at least one portal-flagged multiplier, and (c)
  // matches the optional currency filter.
  const visiblePortals = useMemo(() => {
    if (!cards || walletCards.length === 0 || travelPortals.length === 0) return []
    const inWalletCardIds = new Set(
      walletCards
        .filter((wc) => wc.panel === 'in_wallet' || wc.panel === 'future_cards')
        .map((wc) => wc.card_id),
    )
    const cardsById = new Map(cards.map((c) => [c.id, c]))
    return travelPortals
      .map((portal) => {
        const matchingCardNames: string[] = []
        for (const cid of portal.card_ids) {
          if (!inWalletCardIds.has(cid)) continue
          const c = cardsById.get(cid)
          if (!c) continue
          if (filterByCurrencyId != null && c.currency_id !== filterByCurrencyId) continue
          const portalMults = (c.multipliers ?? []).filter(
            (m) => m.is_portal,
          )
          if (portalMults.length === 0) continue
          matchingCardNames.push(c.name)
        }
        return { id: portal.id, name: portal.name, cardNames: matchingCardNames }
      })
      .filter((p) => p.cardNames.length > 0)
      .sort((a, b) => a.name.localeCompare(b.name))
  }, [cards, walletCards, travelPortals, filterByCurrencyId])

  const { data: shares = [] } = useQuery({
    queryKey: queryKeys.walletPortalShares(walletId),
    queryFn: () => walletPortalShareApi.list(walletId!),
    enabled: walletId != null,
  })

  const sharesByPortal = useMemo(() => {
    const out = new Map<number, WalletPortalShare>()
    for (const s of shares) out.set(s.travel_portal_id, s)
    return out
  }, [shares])

  const upsertMutation = useMutation({
    mutationFn: (payload: { travel_portal_id: number; share: number }) =>
      walletPortalShareApi.upsert(walletId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.walletPortalShares(walletId) })
      onChange?.()
    },
  })

  // Local edit buffer so the slider doesn't fire requests on every drag.
  const [pendingByPortal, setPendingByPortal] = useState<Record<number, number>>({})

  if (walletId == null || visiblePortals.length === 0) return null

  return (
    <div className="rounded-lg border border-slate-700 bg-slate-900/40 p-3 mt-3">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
        Travel Portal Shares
      </p>
      <p className="text-[11px] text-slate-400 mb-3">
        What fraction of your travel-coverable spend do you book through each
        travel portal? Cards earn elevated rates only on the portal portion.
      </p>
      <ul className="space-y-3">
        {visiblePortals.map((portal) => {
          const existing = sharesByPortal.get(portal.id)
          const value = pendingByPortal[portal.id] ?? existing?.share ?? 0
          const pct = Math.round(value * 100)
          return (
            <li key={portal.id}>
              <div className="flex items-center justify-between text-xs text-slate-300 mb-1">
                <span>
                  {portal.name}
                  <span className="text-slate-500 ml-1">
                    ({portal.cardNames.length} card
                    {portal.cardNames.length === 1 ? '' : 's'})
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
                  setPendingByPortal((prev) => ({
                    ...prev,
                    [portal.id]: Number(e.target.value) / 100,
                  }))
                }
                onMouseUp={(e) => {
                  const next = Number((e.target as HTMLInputElement).value) / 100
                  if (next !== (existing?.share ?? 0)) {
                    upsertMutation.mutate({
                      travel_portal_id: portal.id,
                      share: next,
                    })
                  }
                }}
                onTouchEnd={(e) => {
                  const next = Number((e.target as HTMLInputElement).value) / 100
                  if (next !== (existing?.share ?? 0)) {
                    upsertMutation.mutate({
                      travel_portal_id: portal.id,
                      share: next,
                    })
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
