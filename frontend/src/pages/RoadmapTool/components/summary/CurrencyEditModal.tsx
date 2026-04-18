import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import { ModalBackdrop } from '../../../../components/ModalBackdrop'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'
import { walletCppApi } from '../../../../api/client'
import { queryKeys } from '../../../../lib/queryKeys'
import { WalletPortalSharesEditor } from './WalletPortalSharesEditor'

interface Props {
  walletId: number
  currencyId: number
  onClose: () => void
  onCppChange: () => void
}

export function CurrencyEditModal({ walletId, currencyId, onClose, onCppChange }: Props) {
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

  const setWalletCpp = useMutation({
    mutationFn: ({ centsPerPoint }: { centsPerPoint: number }) =>
      walletCppApi.set(walletId, currencyId, centsPerPoint),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencies(walletId) })
      onCppChange()
    },
  })

  const handleCppBlur = (value: number) => {
    if (!Number.isFinite(value) || value <= 0) return
    if (currency && Math.abs(value - myCpp) < 1e-6) return
    setWalletCpp.mutate({ centsPerPoint: value })
  }

  return (
    <ModalBackdrop
      onClose={onClose}
      label={currency ? `Edit ${currency.name}` : 'Edit Currency'}
      className="w-full max-w-lg bg-slate-900 border border-slate-700 rounded-xl p-5 shadow-xl"
    >
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-base font-semibold text-slate-100">
            {currency ? currency.name : 'Currency'}
          </h3>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-500 hover:text-slate-200"
            aria-label="Close"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>

        {isLoading || !currency ? (
          <div className="text-slate-500 text-sm py-4">Loading…</div>
        ) : (
          <>
            {/* CPP editor — only meaningful for points currencies. */}
            {!isCash && (
              <div>
                <div className="flex items-center gap-1 mb-1">
                  <label className="block text-xs text-slate-400 uppercase tracking-wider">
                    Cents Per Point
                  </label>
                  {hasNoTransferInfo && (
                    <InfoIconButton
                      onClick={() => setShowNoTransferInfo(true)}
                      label="Without a transfer-enabling card"
                      size={12}
                    />
                  )}
                </div>
                <input
                  type="number"
                  min={0.01}
                  step={0.01}
                  key={`cpp-${currency.id}-${currency.user_cents_per_point ?? 'd'}`}
                  defaultValue={myCpp}
                  disabled={setWalletCpp.isPending}
                  onBlur={(e) => handleCppBlur(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-indigo-500"
                />
                <p className="text-[11px] text-slate-500 mt-1">
                  Default: {currency.cents_per_point.toFixed(2)}¢
                </p>
              </div>
            )}

            <WalletPortalSharesEditor
              walletId={walletId}
              filterByCurrencyId={currencyId}
              onChange={onCppChange}
            />
          </>
        )}
      </div>

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
    </ModalBackdrop>
  )
}
