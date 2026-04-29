import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo, useState } from 'react'
import {
  type WalletCard,
  type ScenarioPortalShareRead,
  scenarioPortalShareApi,
} from '../../../../api/client'
import { Popover } from '../../../../components/ui/Popover'
import { Eyebrow } from '../../../../components/ui/Eyebrow'
import { useCardLibrary } from '../../hooks/useCardLibrary'
import { useTravelPortals } from '../../../../hooks/useTravelPortals'
import { queryKeys } from '../../../../lib/queryKeys'

/**
 * Per-scenario, per-travel-portal share editor.
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
  scenarioId,
  walletCards,
  filterByCurrencyId,
  onChange,
}: {
  scenarioId: number | null
  walletCards: WalletCard[]
  filterByCurrencyId?: number
  /** Called after a successful slider commit so the parent can re-run the
   * scenario calculation (portal-share changes affect EAF). */
  onChange?: () => void
}) {
  const queryClient = useQueryClient()
  const { data: cards } = useCardLibrary()
  const { data: travelPortals = [] } = useTravelPortals()

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
    queryKey: queryKeys.scenarioPortalShares(scenarioId),
    queryFn: () => scenarioPortalShareApi.list(scenarioId!),
    enabled: scenarioId != null,
  })

  const sharesByPortal = useMemo(() => {
    const out = new Map<number, ScenarioPortalShareRead>()
    for (const s of shares) out.set(s.travel_portal_id, s)
    return out
  }, [shares])

  const upsertMutation = useMutation({
    mutationFn: (payload: { travel_portal_id: number; share: number }) =>
      scenarioPortalShareApi.upsert(scenarioId!, payload),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.scenarioPortalShares(scenarioId) })
      onChange?.()
    },
  })

  // Local edit buffer so the slider doesn't fire requests on every drag.
  const [pendingByPortal, setPendingByPortal] = useState<Record<number, number>>({})

  if (scenarioId == null || visiblePortals.length === 0) return null

  return (
    <div>
      <ul className="space-y-2">
        {visiblePortals.map((portal) => {
          const existing = sharesByPortal.get(portal.id)
          const value = pendingByPortal[portal.id] ?? existing?.share ?? 0
          const pct = Math.round(value * 100)
          return (
            <li key={portal.id}>
              <div className="flex items-center justify-between text-[11px] text-ink-muted mb-1.5">
                <div className="flex items-center gap-1">
                  <Eyebrow>Travel Portal Spend</Eyebrow>
                  <Popover
                    side="bottom"
                    portal
                    trigger={({ onClick, ref }) => (
                      <button
                        ref={ref as React.RefObject<HTMLButtonElement>}
                        onClick={onClick}
                        type="button"
                        aria-label="About travel portal shares"
                        className="shrink-0 text-ink-faint hover:text-accent transition-colors"
                      >
                        <svg
                          width={11}
                          height={11}
                          viewBox="0 0 24 24"
                          fill="none"
                          stroke="currentColor"
                          strokeWidth="2"
                          strokeLinecap="round"
                          strokeLinejoin="round"
                        >
                          <circle cx="12" cy="12" r="10" />
                          <line x1="12" y1="16" x2="12" y2="12" />
                          <line x1="12" y1="8" x2="12.01" y2="8" />
                        </svg>
                      </button>
                    )}
                  >
                    <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
                      <p>
                        What share of your travel spend do you book through each
                        travel portal (like Chase Travel or Amex Travel)? Cards only
                        earn their boosted portal rate on the portion you actually
                        book through the portal — the rest earns the normal travel
                        rate.
                      </p>
                    </div>
                  </Popover>
                </div>
                <span>
                  {portal.name}:{' '}
                  <span className="text-accent tabular-nums">{pct}%</span>
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
                className="w-full h-1.5 accent-accent cursor-pointer block my-0"
              />
            </li>
          )
        })}
      </ul>
    </div>
  )
}
