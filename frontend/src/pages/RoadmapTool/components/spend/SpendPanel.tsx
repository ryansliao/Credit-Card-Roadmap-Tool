import type { CardResult, WalletCard } from '../../../../api/client'
import { SpendTabContent } from './SpendTabContent'

interface Props {
  walletId: number | null
  selectedCards: CardResult[]
  walletCards: WalletCard[]
  totalYears: number
}

export function SpendPanel({ walletId, selectedCards, walletCards, totalYears }: Props) {
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 min-w-0 min-h-0 h-full flex flex-col overflow-hidden">
      <div className="flex-1 min-h-0 overflow-auto">
        <SpendTabContent
          walletId={walletId}
          selectedCards={selectedCards}
          walletCards={walletCards}
          isTotal={false}
          totalYears={totalYears}
        />
      </div>
    </div>
  )
}
