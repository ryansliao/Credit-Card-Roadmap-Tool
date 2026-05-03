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

const CURRENCY_ROW_HEIGHT = 44
const CARD_COL = 380
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

  const cardCount = group.cards.length
  const isCash = group.rewardKind === 'cash'
  const settingsAvailable = group.currencyId != null && !isCash
  // Rail merges across the header row + dropdown (when expanded) + every
  // card row in the group. The dropdown spans cols 2/-1 only so the rail
  // in col 1 stays unbroken under it, visually anchoring the dropdown to
  // its currency.
  const railRowSpan = 1 + (isExpanded ? 1 : 0) + Math.max(1, cardCount)

  return (
    <>
      {/* Currency rail — column 1, merged across the entire group block.
          Holds the currency icon and a thin accent connector that visually
          anchors the cards beneath this currency. */}
      <div
        className="relative bg-surface-2 border-b border-r border-divider flex flex-col items-center pt-2 pb-2"
        style={{ gridColumn: 1, gridRow: `span ${railRowSpan}` }}
      >
        <CurrencyPhoto
          slug={group.photoSlug}
          name={group.name}
          fallbackColor={group.color}
          isCash={isCash}
        />
        <div
          aria-hidden
          className="mt-2 w-0.5 flex-1 rounded-full"
          style={{
            backgroundColor: 'color-mix(in oklab, var(--color-accent) 35%, transparent)',
          }}
        />
      </div>

      {/* Currency header — split into two cells along the Cards / Timeline
          column boundary so the Today + End vertical gridlines pass through
          uninterrupted. Cards-column cell holds the name + Cash pill +
          gear (gear pushed to the right edge of its cell via ml-auto, so
          it sits just before the Today line). Timeline-column cell holds
          the stats inside an opaque bg-surface chip (z-[30]) so year
          gridlines don't slice through the text; ml-1 anchors it just to
          the right of the Today line. */}
      <div
        className={`relative flex items-center gap-2 px-3 ${DIVIDER_CLASS} hover:bg-surface-2/40 transition-colors`}
        style={{ gridColumn: 2, height: CURRENCY_ROW_HEIGHT }}
      >
        <span className="text-sm font-semibold text-ink truncate">{group.name}</span>
        {isCash && (
          <span className="shrink-0 text-[9px] font-bold uppercase tracking-wider text-ink-faint bg-surface-2 px-1.5 py-0.5 rounded-full">
            Cash
          </span>
        )}
        {settingsAvailable && (
          <button
            type="button"
            onClick={() => onToggleExpanded(group.currencyId!)}
            className={`shrink-0 ml-auto p-1.5 rounded transition-colors ${
              isExpanded
                ? 'bg-accent-soft text-accent'
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
              width="20"
              height="20"
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
      <div
        className={`relative flex items-center ${DIVIDER_CLASS} hover:bg-surface-2/40 transition-colors`}
        style={{ gridColumn: 3, height: CURRENCY_ROW_HEIGHT }}
      >
        <div
          className={`ml-1 px-1 relative z-[30] bg-surface flex items-center gap-1.5 text-xs text-ink-muted truncate transition-opacity ${isStale ? 'opacity-60' : ''}`}
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
          <span className="text-ink-faint text-sm leading-none">·</span>
          {incomeLabel && (
            <span className="text-ink-faint">
              <span className="tnum-mono">{incomeLabel.number}</span>
              {incomeLabel.suffix}
            </span>
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
      </div>

      {/* Currency settings — opens directly beneath the currency header row
          (between the header and the first card) so the dropdown stays
          visually attached to its currency. Spans cols 2/-1 only; the rail
          in col 1 continues unbroken behind it. */}
      {isExpanded && group.currencyId != null && (
        <CurrencySettingsDropdown
          scenarioId={scenarioId}
          walletCards={walletCards}
          currencyId={group.currencyId}
          leftGutterPx={CARD_COL}
          onClose={() => onToggleExpanded(group.currencyId!)}
        />
      )}

      {/* Card rows — each renders 2 cells (display:contents) which auto-flow
          into columns 2 + 3 of the rows the rail occupies. */}
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
