import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  type WalletPortalShare,
  travelPortalApi,
  walletPortalShareApi,
  walletsApi,
} from '../../../../api/client'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'
import { useCardLibrary } from '../../hooks/useCardLibrary'
import { queryKeys } from '../../../../lib/queryKeys'

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
  const walletCards = useMemo(() => wallet?.wallet_cards ?? [], [wallet])

  // Travel portals that have at least one in-wallet card that (a) belongs to
  // the portal, (b) carries at least one portal-flagged multiplier, and (c)
  // matches the optional currency filter.
  const visiblePortals = useMemo(() => {
    if (!cards || walletCards.length === 0 || travelPortals.length === 0) return []
    const inWalletCardIds = new Set(
      walletCards.filter((wc) => wc.is_enabled).map((wc) => wc.card_id),
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
  const [showInfo, setShowInfo] = useState(false)

  if (walletId == null || visiblePortals.length === 0) return null

  return (
    <div>
      <ul className="space-y-2">
        {visiblePortals.map((portal) => {
          const existing = sharesByPortal.get(portal.id)
          const value = pendingByPortal[portal.id] ?? existing?.share ?? 0
          const pct = Math.round(value * 100)
          return (
            <li key={portal.id}>
              <div className="flex items-center justify-between text-[11px] text-slate-300 mb-1.5">
                <div className="flex items-center gap-1">
                  <span className="text-slate-400 uppercase tracking-wider">
                    Travel Portal Spend
                  </span>
                  <InfoIconButton
                    onClick={() => setShowInfo(true)}
                    label="About travel portal shares"
                    size={11}
                  />
                </div>
                <span>
                  {portal.name}:{' '}
                  <span className="text-indigo-300 tabular-nums">{pct}%</span>
                </span>
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
                className="w-full h-1.5 accent-indigo-500 cursor-pointer block my-0"
              />
            </li>
          )
        })}
      </ul>

      {showInfo && (
        <InfoPopover
          title="Travel Portal Spend"
          onClose={() => setShowInfo(false)}
        >
          <p>
            What fraction of your travel-coverable spend in this currency do
            you book through each travel portal? Cards earn elevated rates
            only on the portal portion.
          </p>
        </InfoPopover>
      )}
    </div>
  )
}
