import type { CardResult, RoadmapResponse } from '../../../../api/client'
import type { ResolvedCard } from '../../lib/resolveScenarioCards'
import { CurrencySettingsDropdown } from '../summary/CurrencySettingsDropdown'
import { CardRow } from './CardRow'
import { CurrencyPhoto } from './TimelineGlyphs'
import type { Range } from './lib/timelineUtils'
import {
  formatGroupBalance,
  formatGroupIncome,
  formatSecondaryBalance,
} from './lib/timelineFormatters'

const CURRENCY_ROW_HEIGHT = 45
const LEFT_GUTTER = 420
const DIVIDER_CLASS = 'border-b border-divider'

export interface SecondaryAnnual {
  id: number
  name: string
  units: number
  dollars: number
  rewardKind: 'points' | 'cash'
  /** Total projected balance (not annualised). At the per-card entry it
   * holds `cr.secondary_currency_net_earn`; the group header sums those
   * across enabled cards. */
  totalUnits: number
  totalDollars: number
}

export interface GroupCardEntry {
  wc: ResolvedCard
  cr: CardResult | null
  /** Annualized secondary-currency earn for this card (e.g. Bilt Cash on a
   * Bilt Rewards card). Null when the card has no secondary earn. */
  secondary: SecondaryAnnual | null
}

export interface GroupData {
  name: string
  currencyId: number | null
  photoSlug: string | null
  color: string
  rewardKind: 'points' | 'cash' | null
  cards: GroupCardEntry[]
  /** Aggregated secondary-currency totals across enabled cards in this
   * group (e.g. Bilt Cash under Bilt Rewards). Shown as extra income
   * figures alongside the primary total. */
  secondaries: SecondaryAnnual[]
  /** End-of-projection balance in this currency: sum of per-card
   * `cr.total_points` across enabled cards (`annual_point_earn_for_balance
   * × card_active_years + SUB`). Null when the calc hasn't run or no
   * enabled card in this group has a result. */
  totalBalance: number | null
  /** CPP to value the balance against when rendering a cash group. */
  balanceCpp: number | null
}

export interface GroupSectionProps {
  group: GroupData
  range: Range
  roadmapById: Map<number, RoadmapResponse['cards'][number]>
  isUpdating: boolean
  isStale: boolean
  includeSubs: boolean
  rightColumnPx: number
  walletWindowYears: number
  currencyWindowYears: number | undefined
  scenarioId: number
  walletCards: ResolvedCard[]
  isExpanded: boolean
  onToggleEnabled: (cardId: number, enabled: boolean) => void
  onEditCard: (wc: ResolvedCard) => void
  onToggleExpanded: (currencyId: number) => void
}

export function GroupSection({
  group,
  range,
  roadmapById,
  isUpdating,
  isStale,
  includeSubs,
  rightColumnPx,
  walletWindowYears,
  currencyWindowYears,
  scenarioId,
  walletCards,
  isExpanded,
  onToggleEnabled,
  onEditCard,
  onToggleExpanded,
}: GroupSectionProps) {
  // When the group has no contributing CardResults yet — fresh wallet, every
  // card just added, or every card disabled — fall back to dashed placeholders
  // so the balance/income labels still anchor the row instead of disappearing.
  const balanceLabel = formatGroupBalance(group)
  const incomeLabel =
    formatGroupIncome(group, includeSubs, walletWindowYears, currencyWindowYears) ?? {
      number: '—',
      suffix: '/yr',
    }

  return (
    <>
      {/* Group header: split into two cells so the gear lives inside the
          left (Cards) column, right-aligned. Opaque bg + z-20 so the
          Today line / year gridlines stop at this row rather than crossing
          through the text. */}
      <div
        className={`relative z-20 flex items-center gap-2 px-3 ${DIVIDER_CLASS} bg-surface-2`}
        style={{ height: CURRENCY_ROW_HEIGHT, borderLeft: `3px solid ${group.color}` }}
      >
        <CurrencyPhoto
          slug={group.photoSlug}
          name={group.name}
          fallbackColor={group.color}
          isCash={group.rewardKind === 'cash'}
        />
        <div className="min-w-0 flex-1">
          <div className="text-sm font-medium text-ink truncate">{group.name}</div>
          {(balanceLabel || incomeLabel || group.secondaries.length > 0) && (
            <div
              className={`flex items-center gap-1.5 text-xs text-ink-muted truncate transition-opacity ${isStale ? 'opacity-60' : ''}`}
              title={
                isStale
                  ? 'Results are out of date — click Calculate to refresh'
                  : undefined
              }
            >
              {balanceLabel != null ? (
                <span className="tnum-mono">{balanceLabel}</span>
              ) : (
                <span>—</span>
              )}
              {incomeLabel && (
                <>
                  <span className="text-ink-faint text-sm leading-none">·</span>
                  <span className="text-ink-faint">
                    <span className="tnum-mono">{incomeLabel.number}</span>
                    {incomeLabel.suffix}
                  </span>
                </>
              )}
              {group.secondaries.map((s) => {
                const parts = formatSecondaryBalance(s)
                return (
                  <span key={`bal-${s.id}`} className="text-ink-faint">
                    <span className="mr-1 text-ink-faint">·</span>
                    <span className="tnum-mono">{parts.number}</span>
                    {parts.suffix}
                  </span>
                )
              })}
            </div>
          )}
        </div>
        {group.currencyId != null && group.rewardKind !== 'cash' && (
          <button
            type="button"
            onClick={() => onToggleExpanded(group.currencyId!)}
            className={`ml-auto p-1.5 rounded transition-colors shrink-0 ${
              isExpanded
                ? 'bg-surface text-accent'
                : 'text-ink-faint hover:text-accent hover:bg-surface-2'
            }`}
            title={
              isExpanded
                ? `Close ${group.name} settings`
                : `Edit ${group.name} settings`
            }
            aria-label={`Edit ${group.name} settings`}
            aria-expanded={isExpanded}
          >
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <line x1="4" y1="6" x2="20" y2="6" />
              <line x1="4" y1="12" x2="20" y2="12" />
              <line x1="4" y1="18" x2="20" y2="18" />
              <circle cx="8" cy="6" r="2" fill="currentColor" stroke="none" />
              <circle cx="16" cy="12" r="2" fill="currentColor" stroke="none" />
              <circle cx="10" cy="18" r="2" fill="currentColor" stroke="none" />
            </svg>
          </button>
        )}
      </div>
      {/* Right cell — timeline side of the currency header row; carries the
          income total (if any) and keeps the background tint aligned. z-20
          + opaque bg so the Today line and year gridlines don't bleed
          through the text. */}
      <div
        className={`relative z-20 flex items-center gap-2 px-3 ${DIVIDER_CLASS} bg-surface-2`}
        style={{ height: CURRENCY_ROW_HEIGHT }}
      />
      {isExpanded && group.currencyId != null && (
        <CurrencySettingsDropdown
          scenarioId={scenarioId}
          walletCards={walletCards}
          currencyId={group.currencyId}
          leftGutterPx={LEFT_GUTTER}
          onClose={() => onToggleExpanded(group.currencyId!)}
        />
      )}
      {group.cards.map(({ wc, cr, secondary }) => (
        <CardRow
          key={wc.id}
          wc={wc}
          cr={cr}
          secondary={secondary}
          color={group.color}
          range={range}
          roadmapStatus={roadmapById.get(wc.card_id)}
          isUpdating={isUpdating}
          isStale={isStale}
          includeSubs={includeSubs}
          rightColumnPx={rightColumnPx}
          onToggleEnabled={onToggleEnabled}
          onEditCard={onEditCard}
        />
      ))}
    </>
  )
}
