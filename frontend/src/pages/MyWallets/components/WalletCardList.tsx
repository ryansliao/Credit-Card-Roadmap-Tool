import { useState } from 'react'
import type { WalletCard } from '../../../api/client'
import { formatMoney } from '../../../utils/format'

interface WalletOption {
  id: number
  name: string
}

interface Props {
  cards: WalletCard[]
  isRemoving: boolean
  onRemoveCard: (cardId: number) => void
  onEditCard: (wc: WalletCard) => void
  onAddCard: () => void
  wallets: WalletOption[]
  selectedWalletId: number | null
  onSelectWallet: (id: number | null) => void
  onCreateWallet: () => void
}

function CardPhoto({ slug, name }: { slug: string | null; name: string }) {
  const [failed, setFailed] = useState(false)

  if (!slug || failed) {
    return (
      <div className="w-full h-full bg-gradient-to-br from-slate-700 to-slate-800 flex items-center justify-center">
        <svg
          width="24"
          height="24"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="1.5"
          strokeLinecap="round"
          strokeLinejoin="round"
          className="text-slate-500"
        >
          <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
          <line x1="1" y1="10" x2="23" y2="10" />
        </svg>
      </div>
    )
  }

  return (
    <img
      src={`/photos/${slug}.png`}
      alt={name}
      className="w-full h-full object-contain"
      onError={() => setFailed(true)}
    />
  )
}

function WalletCardItem({
  wc,
  isRemoving,
  onRemoveCard,
  onEditCard,
}: {
  wc: WalletCard
  isRemoving: boolean
  onRemoveCard: (cardId: number) => void
  onEditCard: (wc: WalletCard) => void
}) {
  const cardName = wc.card_name ?? `Card #${wc.card_id}`
  const annualFee = wc.annual_fee ?? 0

  return (
    <li
      className="group bg-slate-800/60 hover:bg-slate-800 border border-slate-700/40 hover:border-slate-600 rounded-xl transition-colors cursor-pointer overflow-hidden"
      onClick={() => onEditCard(wc)}
    >
      <div className="flex items-center gap-3 px-3 py-2">
        {/* Card image */}
        <div className="w-[72px] h-11 shrink-0 rounded overflow-hidden bg-slate-700/50">
          <CardPhoto slug={wc.photo_slug} name={cardName} />
        </div>

        {/* Card info */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2 flex-wrap">
            <p className="text-sm font-medium text-white truncate">{cardName}</p>
            {wc.acquisition_type === 'product_change' && (
              <span className="text-[10px] font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50 rounded px-1.5 py-0.5 shrink-0">
                PC
              </span>
            )}
          </div>
          <div className="flex items-center gap-1.5 mt-0.5">
            {wc.issuer_name && (
              <span className="text-xs text-slate-400">{wc.issuer_name}</span>
            )}
            {wc.issuer_name && wc.network_tier_name && (
              <span className="text-slate-600 text-xs">·</span>
            )}
            {wc.network_tier_name && (
              <span className="text-xs text-slate-500">{wc.network_tier_name}</span>
            )}
            {wc.added_date && (
              <>
                {(wc.issuer_name || wc.network_tier_name) && (
                  <span className="text-slate-600 text-xs">·</span>
                )}
                <span className="text-xs text-slate-500">
                  {wc.acquisition_type === 'product_change' ? 'PC' : 'Opened'} {wc.added_date}
                </span>
              </>
            )}
          </div>
        </div>

        {/* Value info */}
        <div className="text-right shrink-0 mr-1">
          <p className="text-xs tabular-nums text-white">
            Annual Fee: {annualFee > 0 ? <span className="text-red-400">{formatMoney(annualFee)}</span> : <span className="text-emerald-400">$0</span>}
          </p>
          {wc.credit_total > 0 && (
            <p className="text-xs tabular-nums text-white mt-0.5">
              Credit Value: <span className="text-emerald-400">{formatMoney(wc.credit_total)}</span>
            </p>
          )}
        </div>

        {/* Remove button */}
        <button
          type="button"
          className="p-1.5 rounded-lg text-slate-700 hover:text-red-400 hover:bg-red-950/40 opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 shrink-0"
          aria-label="Remove card"
          title="Remove"
          onClick={(e) => { e.stopPropagation(); onRemoveCard(wc.card_id) }}
          disabled={isRemoving}
        >
          <svg
            width="14"
            height="14"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <polyline points="3 6 5 6 21 6" />
            <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
          </svg>
        </button>
      </div>
    </li>
  )
}

export function WalletCardList({
  cards,
  isRemoving,
  onRemoveCard,
  onEditCard,
  onAddCard,
  wallets,
  selectedWalletId,
  onSelectWallet,
  onCreateWallet,
}: Props) {
  const totalFees = cards.reduce((sum, wc) => sum + (wc.annual_fee ?? 0), 0)
  const totalCredits = cards.reduce((sum, wc) => sum + wc.credit_total, 0)

  return (
    <div className="h-full flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between mb-5 shrink-0">
        <div>
          <div className="flex items-baseline gap-3">
            <h2 className="text-2xl font-bold text-white">My Wallet</h2>
            {cards.length > 0 && (
              <span className="text-sm text-slate-500">{cards.length}</span>
            )}
          </div>
          <p className="text-slate-400 text-sm mt-1">Manage the cards in your wallet.</p>
        </div>
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={onAddCard}
            className="flex items-center justify-center gap-1.5 w-28 py-2 rounded-lg text-sm font-medium bg-indigo-600 hover:bg-indigo-500 text-white border border-transparent transition-colors"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            Add Card
          </button>
          <button
            type="button"
            onClick={onCreateWallet}
            className="flex items-center justify-center gap-1.5 w-28 py-2 rounded-lg text-sm font-medium bg-slate-700 hover:bg-slate-600 text-slate-200 border border-slate-600 transition-colors"
          >
            <svg
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect x="2" y="5" width="20" height="14" rx="2" />
              <path d="M2 10h20" />
              <line x1="12" y1="14" x2="12" y2="18" />
              <line x1="10" y1="16" x2="14" y2="16" />
            </svg>
            Add Wallet
          </button>
          <select
            id="wallet-select"
            className="bg-slate-800 border border-slate-600 text-white text-sm rounded-lg px-3 py-2 min-w-[10rem] max-w-[16rem]"
            value={selectedWalletId ?? ''}
            onChange={(e) => {
              const v = e.target.value
              onSelectWallet(v === '' ? null : Number(v))
            }}
          >
            <option value="">
              {wallets.length === 0 ? 'No wallets' : 'Select wallet…'}
            </option>
            {wallets.map((w) => (
              <option key={w.id} value={w.id}>
                {w.name}
              </option>
            ))}
          </select>
        </div>
      </div>

      {/* Summary stats */}
      {cards.length > 0 && (
        <div className={`grid gap-3 mb-4 shrink-0 ${totalCredits > 0 ? 'grid-cols-3' : 'grid-cols-1'}`}>
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center">
            <p className="text-[10px] text-slate-400 uppercase tracking-wider">Annual Fee</p>
            <p className="text-xl font-bold text-red-400 mt-0.5 tabular-nums">{formatMoney(totalFees)}</p>
          </div>
          {totalCredits > 0 && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center">
              <p className="text-[10px] text-slate-400 uppercase tracking-wider">Credit Value</p>
              <p className="text-xl font-bold text-emerald-400 mt-0.5 tabular-nums">{formatMoney(totalCredits)}</p>
            </div>
          )}
          {totalCredits > 0 && (
            <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center">
              <p className="text-[10px] text-slate-400 uppercase tracking-wider">Net Cost</p>
              <p className={`text-xl font-bold mt-0.5 tabular-nums ${totalFees - totalCredits <= 0 ? 'text-emerald-400' : 'text-slate-200'}`}>
                {formatMoney(Math.abs(totalFees - totalCredits))}
              </p>
            </div>
          )}
        </div>
      )}

      {/* Card list */}
      <div className="min-h-0 overflow-y-auto flex-1">
        {cards.length === 0 ? (
          <div className="border-2 border-dashed border-slate-700/60 rounded-xl py-12 px-6 text-center">
            <svg
              width="36"
              height="36"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
              className="mx-auto text-slate-600 mb-3"
            >
              <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
              <line x1="1" y1="10" x2="23" y2="10" />
            </svg>
            <p className="text-slate-400 text-sm font-medium">No cards yet</p>
            <p className="text-slate-500 text-xs mt-1">Add your first credit card to this wallet.</p>
          </div>
        ) : (
          <ul className="space-y-1.5">
            {cards.map((wc) => (
              <WalletCardItem
                key={wc.id}
                wc={wc}
                isRemoving={isRemoving}
                onRemoveCard={onRemoveCard}
                onEditCard={onEditCard}
              />
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
