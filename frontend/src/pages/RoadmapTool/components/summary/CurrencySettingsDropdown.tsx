import { useMutation, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'
import {
  walletCppApi,
  walletsApi,
  type CurrencyRead,
  type WalletCurrencyBalance,
} from '../../../../api/client'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'
import { queryKeys } from '../../lib/queryKeys'
import { WalletPortalSharesEditor } from './WalletPortalSharesEditor'

interface CurrencySettingsDropdownProps {
  walletId: number | null
  currency: CurrencyRead
  balance: WalletCurrencyBalance | null
  /** Called when user CPP overrides change (clears stale calculate on parent). */
  onCppChange: () => void
}

export function CurrencySettingsDropdown({
  walletId,
  currency,
  balance,
  onCppChange,
}: CurrencySettingsDropdownProps) {
  const queryClient = useQueryClient()

  const setWalletCpp = useMutation({
    mutationFn: ({ currencyId, centsPerPoint }: { currencyId: number; centsPerPoint: number }) =>
      walletCppApi.set(walletId!, currencyId, centsPerPoint),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencies(walletId) })
      onCppChange()
    },
  })

  const setInitialMutation = useMutation({
    mutationFn: ({ currencyId, initial }: { currencyId: number; initial: number }) =>
      walletsApi.setCurrencyInitialBalance(walletId!, currencyId, initial),
    onSuccess: () => {
      if (walletId == null) return
      queryClient.invalidateQueries({ queryKey: queryKeys.walletCurrencyBalances(walletId) })
    },
  })

  const busy = setWalletCpp.isPending || setInitialMutation.isPending

  const isCash = (currency.reward_kind ?? 'points') === 'cash'

  const myCpp = currency.user_cents_per_point != null
    ? currency.user_cents_per_point
    : currency.cents_per_point

  const handleCppBlur = (value: number) => {
    if (!Number.isFinite(value) || value <= 0) return
    setWalletCpp.mutate({ currencyId: currency.id, centsPerPoint: value })
  }

  const tracked = balance != null && walletId != null

  const [showNoTransferInfo, setShowNoTransferInfo] = useState(false)
  const [showInitialBalanceInfo, setShowInitialBalanceInfo] = useState(false)
  const hasNoTransferInfo =
    currency.no_transfer_rate != null || currency.no_transfer_cpp != null

  return (
    <div className="border-t border-slate-700/60 bg-slate-900/60 px-3 py-3">
      <div className="space-y-3">
        {/* CPP + Initial balance side by side. CPP hidden for cash currencies. */}
        {(!isCash || tracked) && (
          <div className="flex gap-3">
            {!isCash ? (
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1 mb-1">
                  <label className="block text-[11px] text-slate-400">¢ Per Point</label>
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
                  key={`cpp-${currency.id}-${currency.user_cents_per_point ?? 'd'}-${currency.cents_per_point}`}
                  defaultValue={myCpp}
                  disabled={busy}
                  onBlur={(e) => handleCppBlur(Number(e.target.value))}
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-indigo-500"
                />
              </div>
            ) : null}
            {tracked && (
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1 mb-1">
                  <label className="block text-[11px] text-slate-400">
                    {isCash ? 'Initial Balance (USD)' : 'Initial Balance (Pts)'}
                  </label>
                  <InfoIconButton
                    onClick={() => setShowInitialBalanceInfo(true)}
                    label="What to enter for initial balance"
                    size={12}
                  />
                </div>
                <input
                  type="number"
                  min={0}
                  step={isCash ? 0.01 : 1000}
                  key={`init-${balance.id}-${balance.initial_balance}-${isCash ? 'c' : 'p'}`}
                  defaultValue={isCash ? balance.initial_balance / 100 : balance.initial_balance}
                  disabled={busy}
                  onBlur={(e) => {
                    const v = Number(e.target.value)
                    if (!Number.isFinite(v) || v < 0) return
                    const stored = isCash ? Math.round(v * 100) : v
                    if (stored === balance.initial_balance) return
                    setInitialMutation.mutate({ currencyId: currency.id, initial: stored })
                  }}
                  className="w-full bg-slate-800 border border-slate-600 text-white text-sm px-3 py-1.5 rounded-lg focus:outline-none focus:border-indigo-500"
                />
              </div>
            )}
          </div>
        )}

        <WalletPortalSharesEditor
          walletId={walletId}
          filterByCurrencyId={currency.id}
          onChange={onCppChange}
        />
      </div>

      {showInitialBalanceInfo && (
        <InfoPopover
          title="Initial Balance"
          onClose={() => setShowInitialBalanceInfo(false)}
        >
          <p>
            Enter the {isCash ? 'cash back' : 'points'} you currently hold in
            this currency, including any sign-up bonuses you've already earned.
          </p>
          <p>
            The wallet projection adds future earn (category spend, recurring
            bonuses) and future SUBs on top of this starting balance, so any
            SUB that has already hit your account should be baked into this
            number rather than tracked separately.
          </p>
        </InfoPopover>
      )}

      {showNoTransferInfo && (
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
          <p>
            Full CPP requires a transfer-enabling card in the wallet.
          </p>
        </InfoPopover>
      )}
    </div>
  )
}
