import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { Popover } from '../../../../components/ui/Popover'
import { Eyebrow } from '../../../../components/ui/Eyebrow'
import { scenarioCppApi, type WalletCard } from '../../../../api/client'
import { queryKeys } from '../../../../lib/queryKeys'
import { WalletPortalSharesEditor } from './WalletPortalSharesEditor'

interface Props {
  scenarioId: number
  walletCards: WalletCard[]
  currencyId: number
  /** Pixel width of the left gutter column. The dropdown occupies a full
   * grid row (to keep `display: contents` card rows auto-placed correctly)
   * but its visible panel is clipped to the left gutter so it doesn't
   * bleed over the Today divider into the timeline area. */
  leftGutterPx: number
  onClose: () => void
}

export function CurrencySettingsDropdown({ scenarioId, walletCards, currencyId, leftGutterPx, onClose }: Props) {
  const queryClient = useQueryClient()
  const { data: currencies = [], isLoading } = useQuery({
    queryKey: queryKeys.scenarioCurrencies(scenarioId),
    queryFn: () => scenarioCppApi.listCurrencies(scenarioId),
  })

  const currency = currencies.find((c) => c.id === currencyId) ?? null
  const isCash = (currency?.reward_kind ?? 'points') === 'cash'
  const myCpp = currency?.user_cents_per_point != null
    ? currency.user_cents_per_point
    : currency?.cents_per_point ?? 1
  const hasNoTransferInfo =
    currency != null && (currency.no_transfer_rate != null || currency.no_transfer_cpp != null)

  // Local drag buffer so the CPP slider updates the label continuously while
  // dragging, but only commits on release (mirrors the portal-share slider).
  const [pendingCpp, setPendingCpp] = useState<number | null>(null)
  const displayCpp = pendingCpp ?? myCpp
  const clampedCpp = Math.min(3, Math.max(0.5, displayCpp))

  const setScenarioCpp = useMutation({
    mutationFn: ({ centsPerPoint }: { centsPerPoint: number }) =>
      scenarioCppApi.set(scenarioId, currencyId, centsPerPoint),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.scenarioCurrencies(scenarioId) })
      setPendingCpp(null)
    },
  })

  const commitCpp = (value: number) => {
    const next = Math.round(value * 20) / 20
    if (!Number.isFinite(next) || next <= 0) return
    if (Math.abs(next - myCpp) < 1e-6) {
      setPendingCpp(null)
      return
    }
    setScenarioCpp.mutate({ centsPerPoint: next })
  }

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', handler)
    return () => window.removeEventListener('keydown', handler)
  }, [onClose])

  return (
    <div
      className="relative z-20 bg-surface/70 border-b border-divider px-5 pt-2 pb-4"
      style={{ gridColumn: '1 / -1', width: leftGutterPx }}
    >
      {isLoading || !currency ? (
        <div className="text-ink-faint text-sm">Loading…</div>
      ) : (
        <div className="space-y-3">
          {!isCash && (
            <div>
              <div className="flex items-center justify-between text-[11px] text-ink-muted mb-1.5">
                <div className="flex items-center gap-1">
                  <Eyebrow>Cents Per Point</Eyebrow>
                  {hasNoTransferInfo && (
                    <Popover
                      side="bottom"
                      portal
                      trigger={({ onClick, ref }) => (
                        <button
                          ref={ref as React.RefObject<HTMLButtonElement>}
                          onClick={onClick}
                          type="button"
                          aria-label="Without a premium card"
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
                          These points reach their full value when you can transfer them
                          to airline and hotel partners, which requires a specific
                          premium card in your wallet (e.g. a Sapphire for Chase UR).
                        </p>
                        <p>
                          {currency.no_transfer_rate != null ? (
                            <>
                              Without one, points can only be redeemed as cash back, so
                              they're worth{' '}
                              <span className="text-warn font-medium">
                                {Math.round(currency.no_transfer_rate * 100)}%
                              </span>{' '}
                              of their full value (
                              <span className="text-warn font-medium">
                                {(myCpp * currency.no_transfer_rate).toFixed(2)}¢
                              </span>{' '}
                              per point).
                            </>
                          ) : (
                            <>
                              Without one, points can only be redeemed as cash back, so
                              they're worth{' '}
                              <span className="text-warn font-medium">
                                {currency.no_transfer_cpp}¢
                              </span>{' '}
                              per point.
                            </>
                          )}
                        </p>
                        <p>Add the premium card to the wallet to unlock full value.</p>
                      </div>
                    </Popover>
                  )}
                </div>
                <span className="text-accent tabular-nums">
                  {clampedCpp.toFixed(2)}¢
                </span>
              </div>
              <input
                type="range"
                min={0.5}
                max={3}
                step={0.05}
                value={clampedCpp}
                disabled={setScenarioCpp.isPending}
                onChange={(e) => setPendingCpp(Number(e.target.value))}
                onMouseUp={(e) =>
                  commitCpp(Number((e.target as HTMLInputElement).value))
                }
                onTouchEnd={(e) =>
                  commitCpp(Number((e.target as HTMLInputElement).value))
                }
                onKeyUp={(e) =>
                  commitCpp(Number((e.target as HTMLInputElement).value))
                }
                className="w-full h-1.5 accent-accent cursor-pointer block my-0"
              />
            </div>
          )}

          <WalletPortalSharesEditor
            scenarioId={scenarioId}
            walletCards={walletCards}
            filterByCurrencyId={currencyId}
          />
        </div>
      )}
    </div>
  )
}
