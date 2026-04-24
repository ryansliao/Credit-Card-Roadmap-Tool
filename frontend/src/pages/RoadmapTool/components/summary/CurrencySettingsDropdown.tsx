import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'
import { walletCppApi } from '../../../../api/client'
import { queryKeys } from '../../../../lib/queryKeys'
import { WalletPortalSharesEditor } from './WalletPortalSharesEditor'

interface Props {
  walletId: number
  currencyId: number
  /** Pixel width of the left gutter column. The dropdown occupies a full
   * grid row (to keep `display: contents` card rows auto-placed correctly)
   * but its visible panel is clipped to the left gutter so it doesn't
   * bleed over the Today divider into the timeline area. */
  leftGutterPx: number
  onClose: () => void
}

export function CurrencySettingsDropdown({ walletId, currencyId, leftGutterPx, onClose }: Props) {
  const queryClient = useQueryClient()
  const { data: currencies = [], isLoading } = useQuery({
    queryKey: queryKeys.walletCurrencies(walletId),
    queryFn: () => walletCppApi.listCurrencies(walletId),
  })

  const currency = currencies.find((c) => c.id === currencyId) ?? null
  const isCash = (currency?.reward_kind ?? 'points') === 'cash'
  const myCpp = currency?.user_cents_per_point != null
    ? currency.user_cents_per_point
    : currency?.cents_per_point ?? 1
  const hasNoTransferInfo =
    currency != null && (currency.no_transfer_rate != null || currency.no_transfer_cpp != null)

  const [showNoTransferInfo, setShowNoTransferInfo] = useState(false)
  // Local drag buffer so the CPP slider updates the label continuously while
  // dragging, but only commits on release (mirrors the portal-share slider).
  const [pendingCpp, setPendingCpp] = useState<number | null>(null)
  const displayCpp = pendingCpp ?? myCpp
  const clampedCpp = Math.min(3, Math.max(0.5, displayCpp))

  const setWalletCpp = useMutation({
    mutationFn: ({ centsPerPoint }: { centsPerPoint: number }) =>
      walletCppApi.set(walletId, currencyId, centsPerPoint),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencies(walletId) })
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
    setWalletCpp.mutate({ centsPerPoint: next })
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
      className="relative z-20 bg-slate-800/70 border-b border-slate-700 px-5 py-4"
      style={{ gridColumn: '1 / -1', width: leftGutterPx }}
    >
      {isLoading || !currency ? (
        <div className="text-slate-500 text-sm">Loading…</div>
      ) : (
        <div className="space-y-3">
          {!isCash && (
            <div>
              <div className="flex items-center justify-between text-[11px] text-slate-300 mb-1.5">
                <div className="flex items-center gap-1">
                  <span className="text-slate-400 uppercase tracking-wider">
                    Cents Per Point
                  </span>
                  {hasNoTransferInfo && (
                    <InfoIconButton
                      onClick={() => setShowNoTransferInfo(true)}
                      label="Without a transfer-enabling card"
                      size={11}
                    />
                  )}
                </div>
                <span className="text-indigo-300 tabular-nums">
                  {clampedCpp.toFixed(2)}¢
                </span>
              </div>
              <input
                type="range"
                min={0.5}
                max={3}
                step={0.05}
                value={clampedCpp}
                disabled={setWalletCpp.isPending}
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
                className="w-full h-1.5 accent-indigo-500 cursor-pointer block my-0"
              />
            </div>
          )}

          <WalletPortalSharesEditor
            walletId={walletId}
            filterByCurrencyId={currencyId}
          />
        </div>
      )}

      {showNoTransferInfo && currency && (
        <InfoPopover
          title="Without a Transfer Enabler"
          onClose={() => setShowNoTransferInfo(false)}
        >
          <p>
            {currency.no_transfer_rate != null ? (
              <>
                Without a transfer-enabling card in the wallet, this currency is
                valued at{' '}
                <span className="text-amber-300 font-medium">
                  {Math.round(currency.no_transfer_rate * 100)}%
                </span>{' '}
                of its CPP (
                <span className="text-amber-300 font-medium">
                  {(myCpp * currency.no_transfer_rate).toFixed(2)}¢
                </span>{' '}
                per point).
              </>
            ) : (
              <>
                Without a transfer-enabling card in the wallet, this currency is
                valued at{' '}
                <span className="text-amber-300 font-medium">
                  {currency.no_transfer_cpp}¢
                </span>{' '}
                per point.
              </>
            )}
          </p>
          <p>Full CPP requires a transfer-enabling card in the wallet.</p>
        </InfoPopover>
      )}
    </div>
  )
}
