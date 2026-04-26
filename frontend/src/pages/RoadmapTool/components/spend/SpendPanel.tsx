import type { CardResult, ScenarioCardCategoryPriority } from '../../../../api/client'
import type { ResolvedCard } from '../../lib/resolveScenarioCards'
import { SpendTabContent } from './SpendTabContent'

interface Props {
  selectedCards: CardResult[]
  walletCards: ResolvedCard[]
  categoryPriorities: ScenarioCardCategoryPriority[]
  totalYears: number
  isStale: boolean
}

export function SpendPanel({
  selectedCards,
  walletCards,
  categoryPriorities,
  totalYears,
  isStale,
}: Props) {
  return (
    <div className="bg-slate-900 border border-slate-700 rounded-xl p-4 min-w-0 min-h-0 h-full flex flex-col overflow-hidden">
      <div className="flex-1 min-h-0 overflow-auto">
        <SpendTabContent
          selectedCards={selectedCards}
          walletCards={walletCards}
          categoryPriorities={categoryPriorities}
          isTotal={false}
          totalYears={totalYears}
          isStale={isStale}
        />
      </div>
    </div>
  )
}
