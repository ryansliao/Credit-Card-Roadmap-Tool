import { useMemo, useState } from 'react'
import type { CardResult, WalletResult } from '../../../../api/client'
import { formatMoney, formatPoints } from '../../../../utils/format'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'

type StatTopic = 'eaf' | 'income' | 'fees' | 'duration' | 'foreign' | null
type SummaryTab = 'summary' | 'settings'

/** Annual point income for a card (excludes SUB points). */
function cardAnnualPointIncome(c: CardResult, totalYears: number): number {
  const y = c.card_active_years || totalYears
  return (c.total_points - c.sub_points - c.sub_spend_earn) / y
}

function formatDuration(years: number, months: number): string {
  const total = years * 12 + months
  const y = Math.floor(total / 12)
  const m = total % 12
  if (y === 0) return `${m} Months`
  if (m === 0) return `${y} Years`
  return `${y} Years, ${m} Months`
}

interface Props {
  result: WalletResult | null
  isCalculating: boolean
  durationYears: number
  durationMonths: number
  foreignSpendPercent: number
  onDurationChange: (years: number, months: number) => void
  onDurationCommit: (years: number, months: number) => void
  onForeignSpendChange: (pct: number) => void
  onForeignSpendCommit: (pct: number) => void
  resultsError?: Error | null
}

export function WalletSummaryStats({
  result,
  isCalculating,
  durationYears,
  durationMonths,
  foreignSpendPercent,
  onDurationChange,
  onDurationCommit,
  onForeignSpendChange,
  onForeignSpendCommit,
  resultsError,
}: Props) {
  const [statTopic, setStatTopic] = useState<StatTopic>(null)
  const [activeTab, setActiveTab] = useState<SummaryTab>('summary')

  const totalYears = Math.max(durationYears + durationMonths / 12, 1 / 12)

  const { totalEffectiveAF, totalAnnualPoints, totalAnnualFees } = useMemo(() => {
    const selected = result?.card_results.filter((c) => c.selected) ?? []
    return {
      totalAnnualFees: selected.reduce((s, c) => s + c.annual_fee, 0),
      totalEffectiveAF: selected.reduce((s, c) => s + c.effective_annual_fee, 0),
      totalAnnualPoints: selected.reduce((s, c) => s + cardAnnualPointIncome(c, totalYears), 0),
    }
  }, [result, totalYears])

  const hasStats = !!result || isCalculating

  return (
    <div className="flex items-stretch min-w-0">
      {/* Binder-style tabs, outside the panel on the left. Vertically
          centered against the panel's height. */}
      <div className="shrink-0 flex flex-col gap-1 justify-center z-10">
        {(
          [
            {
              key: 'summary' as const,
              label: 'Summary',
              icon: (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <rect x="3" y="3" width="7" height="9" rx="1" />
                  <rect x="14" y="3" width="7" height="5" rx="1" />
                  <rect x="14" y="12" width="7" height="9" rx="1" />
                  <rect x="3" y="16" width="7" height="5" rx="1" />
                </svg>
              ),
            },
            {
              key: 'settings' as const,
              label: 'Settings',
              icon: (
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <line x1="4" y1="6" x2="20" y2="6" />
                  <circle cx="8" cy="6" r="2.5" fill="currentColor" stroke="none" />
                  <line x1="4" y1="12" x2="20" y2="12" />
                  <circle cx="16" cy="12" r="2.5" fill="currentColor" stroke="none" />
                  <line x1="4" y1="18" x2="20" y2="18" />
                  <circle cx="10" cy="18" r="2.5" fill="currentColor" stroke="none" />
                </svg>
              ),
            },
          ]
        ).map((tab) => {
          const isActive = activeTab === tab.key
          return (
            <button
              key={tab.key}
              type="button"
              onClick={() => setActiveTab(tab.key)}
              className={`px-2 py-2 rounded-l-md border border-r-0 transition-colors ${
                isActive
                  ? 'bg-slate-900 text-indigo-300 border-slate-700 -mr-px'
                  : 'bg-slate-800/70 text-slate-400 border-slate-800 hover:text-slate-200 hover:bg-slate-800'
              }`}
              aria-pressed={isActive}
              aria-label={tab.label}
              title={tab.label}
            >
              {tab.icon}
            </button>
          )
        })}
      </div>

      {/* min-h keeps the panel the same height regardless of which tab is
          active, so switching tabs doesn't jump the layout below. flex
          column + justify-center vertically centers the tab content. */}
      <div className="flex-1 min-w-0 bg-slate-900 border border-slate-700 rounded-xl p-4 min-h-[108px] flex flex-col justify-center">
        {activeTab === 'summary' ? (
          resultsError ? (
            <div className="text-red-400 text-sm bg-red-950 border border-red-700 rounded-lg p-3">
              {resultsError.message}
            </div>
          ) : !hasStats ? (
            <div className="text-slate-500 text-xs text-center py-2">
              Add cards to see effective annual fee (credits, SUB and fees amortised over your projection).
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-3">
              <div className="bg-indigo-900/40 border border-indigo-700 rounded-xl p-3 text-center">
                <div className="flex items-center justify-center gap-1">
                  <p className="text-[10px] text-indigo-300 uppercase tracking-wider">Effective Annual Fee</p>
                  <InfoIconButton onClick={() => setStatTopic('eaf')} label="How Effective Annual Fee is calculated" />
                </div>
                {result ? (
                  <p className={`text-xl font-bold mt-0.5 ${totalEffectiveAF < 0 ? 'text-emerald-400' : 'text-indigo-100'}`}>{formatMoney(totalEffectiveAF)}</p>
                ) : (
                  <div className="h-7 mt-0.5 flex items-center justify-center">
                    <div className="h-4 w-16 bg-indigo-800/50 rounded animate-pulse" />
                  </div>
                )}
              </div>
              <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center">
                <div className="flex items-center justify-center gap-1">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider">Annual Point Income</p>
                  <InfoIconButton onClick={() => setStatTopic('income')} label="How Annual Point Income is calculated" />
                </div>
                {result ? (
                  <p className="text-xl font-bold text-white mt-0.5">{formatPoints(Math.round(totalAnnualPoints))}</p>
                ) : (
                  <div className="h-7 mt-0.5 flex items-center justify-center">
                    <div className="h-4 w-16 bg-slate-700/50 rounded animate-pulse" />
                  </div>
                )}
              </div>
              <div className="bg-slate-800 border border-slate-700 rounded-xl p-3 text-center">
                <div className="flex items-center justify-center gap-1">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider">Total Annual Fees</p>
                  <InfoIconButton onClick={() => setStatTopic('fees')} label="How Total Annual Fees is calculated" />
                </div>
                {result ? (
                  <p className="text-xl font-bold text-red-400 mt-0.5">{formatMoney(totalAnnualFees)}</p>
                ) : (
                  <div className="h-7 mt-0.5 flex items-center justify-center">
                    <div className="h-4 w-16 bg-slate-700/50 rounded animate-pulse" />
                  </div>
                )}
              </div>
            </div>
          )
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 md:divide-x md:divide-slate-700 gap-y-4">
            {/* Duration slider */}
            <div className="md:pr-4">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1">
                  <span className="text-xs text-slate-400">Duration</span>
                  <InfoIconButton onClick={() => setStatTopic('duration')} label="How duration affects calculation" />
                </div>
                <span className="text-xs font-medium text-slate-200 tabular-nums">
                  {formatDuration(durationYears, durationMonths)}
                </span>
              </div>
              <input
                type="range"
                min={1}
                max={60}
                value={durationYears * 12 + durationMonths}
                onChange={(e) => {
                  const total = Number(e.target.value)
                  onDurationChange(Math.floor(total / 12), total % 12)
                }}
                onMouseUp={(e) => {
                  const total = Number((e.target as HTMLInputElement).value)
                  onDurationCommit(Math.floor(total / 12), total % 12)
                }}
                onTouchEnd={(e) => {
                  const total = Number((e.target as HTMLInputElement).value)
                  onDurationCommit(Math.floor(total / 12), total % 12)
                }}
                className="w-full h-1.5 accent-indigo-500 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-600 mt-1">
                <span>1M</span>
                <span>1Y</span>
                <span>2Y</span>
                <span>3Y</span>
                <span>4Y</span>
                <span>5Y</span>
              </div>
            </div>

            {/* Foreign spend slider */}
            <div className="md:pl-4">
              <div className="flex items-center justify-between mb-1">
                <div className="flex items-center gap-1">
                  <span className="text-xs text-slate-400">Foreign Spend</span>
                  <InfoIconButton onClick={() => setStatTopic('foreign')} label="How foreign spend affects calculation" />
                </div>
                <span className="text-xs font-medium text-slate-200 tabular-nums">
                  {Math.round(foreignSpendPercent)}%
                </span>
              </div>
              <input
                type="range"
                min={0}
                max={100}
                value={foreignSpendPercent}
                onChange={(e) => onForeignSpendChange(Number(e.target.value))}
                onMouseUp={(e) => onForeignSpendCommit(Number((e.target as HTMLInputElement).value))}
                onTouchEnd={(e) => onForeignSpendCommit(Number((e.target as HTMLInputElement).value))}
                className="w-full h-1.5 accent-indigo-500 cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-slate-600 mt-1">
                <span>0%</span>
                <span>25%</span>
                <span>50%</span>
                <span>75%</span>
                <span>100%</span>
              </div>
            </div>
          </div>
        )}

        {statTopic === 'eaf' && (
          <InfoPopover title="Effective Annual Fee" onClose={() => setStatTopic(null)}>
            <p>
              The wallet's net annual cost (or value) after credits, sign-up
              bonuses, and category earn are subtracted from annual fees.
              A negative value means the wallet returns more than it costs.
            </p>
            <div>
              <p className="text-slate-300 font-medium mb-1">Per-card formula</p>
              <p className="px-2 py-1 bg-slate-800 rounded font-mono text-[11px] text-slate-300 leading-snug">
                −(category_earn × cpp + sub/years + credits − fees) / years
              </p>
              <p className="mt-1">
                One-time benefits (SUB, first-year bonus, one-time credits)
                are amortised over the projection duration. Recurring credits
                and category earn count fully each year.
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">Wallet total</p>
              <p>
                Sum of every selected card's individual EAF. Each category's
                spend is allocated to the card with the best
                {' '}<span className="font-mono text-[11px] text-slate-300">multiplier × CPP</span>,
                so the same dollar isn't double-counted across cards.
              </p>
            </div>
          </InfoPopover>
        )}

        {statTopic === 'income' && (
          <InfoPopover title="Annual Point Income" onClose={() => setStatTopic(null)}>
            <p>
              Points and miles earned per year from category spend across all
              selected cards (excludes one-time SUB bonuses).
            </p>
            <div>
              <p className="text-slate-300 font-medium mb-1">How it's allocated</p>
              <p>
                Each spend category goes to the card(s) with the highest
                {' '}<span className="font-mono text-[11px] text-slate-300">multiplier × CPP</span>{' '}
                score. Tied cards split the category dollars evenly. Annual
                bonuses (fixed and percentage-based) are added on top.
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">Currency upgrades</p>
              <p>
                When a card's currency converts to another currency in the
                wallet (e.g. Chase Freedom UR Cash → Chase UR with a Sapphire),
                earn is converted at the upgrade rate and valued at the
                target's CPP.
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">SUB exclusion</p>
              <p>
                Sign-up bonuses are not counted here — they show up in the
                currency balance totals and contribute to EAF as one-time
                amortised benefits.
              </p>
            </div>
          </InfoPopover>
        )}

        {statTopic === 'fees' && (
          <InfoPopover title="Total Annual Fees" onClose={() => setStatTopic(null)}>
            <p>
              Sum of the listed annual fee for every active card in the wallet,
              before any credits, sign-up bonuses, or category earn are netted
              out. This is what you'd pay your issuers each year.
            </p>
            <div>
              <p className="text-slate-300 font-medium mb-1">First-year fee</p>
              <p>
                Cards with a first-year fee waiver still appear at their full
                annual fee here. The waiver is reflected in the EAF
                calculation, where year-1 uses the waived fee and subsequent
                years use the recurring fee.
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">Disabled cards</p>
              <p>
                Cards toggled off in the timeline are excluded from all wallet
                totals. Re-enable them to include their fees and earn in the
                summary.
              </p>
            </div>
          </InfoPopover>
        )}

        {statTopic === 'duration' && (
          <InfoPopover title="Duration" onClose={() => setStatTopic(null)}>
            <p>
              How long to project the wallet's value. The calculator amortizes
              one-time benefits (sign-up bonuses, first-year bonuses, first-year
              fee waivers, one-time credits) across this period to produce an
              average annual EAF.
            </p>
            <div>
              <p className="text-slate-300 font-medium mb-1">Effect on EAF</p>
              <p>
                Longer durations spread one-time benefits thinner, so cards with
                big SUBs look less valuable per year. Recurring benefits (annual
                fees, statement credits, category earn) are unaffected.
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">Effect on roadmap</p>
              <p>
                Cards with future <span className="text-slate-300">added_date</span> only count from when they
                become active, so a longer window lets future cards contribute
                proportionally more to the wallet total.
              </p>
            </div>
          </InfoPopover>
        )}

        {statTopic === 'foreign' && (
          <InfoPopover title="Foreign Spend" onClose={() => setStatTopic(null)}>
            <p>
              Percentage of your total spend that occurs as foreign transactions.
              Each spend category is split: the foreign portion is allocated
              separately from the domestic portion.
            </p>
            <div>
              <p className="text-slate-300 font-medium mb-1">FTF priority</p>
              <p>
                Foreign spend goes to no-FTF cards first. If any no-FTF Visa or
                Mastercard exists in the wallet, it gets priority over no-FTF
                cards on other networks (e.g. American Express).
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">Per-category multiplier</p>
              <p>
                On the foreign portion of a category, the eligible card earns
                {' '}<span className="font-mono text-[11px] text-slate-300">max(category_mult, foreign_transactions_mult)</span>.
                So a card with a "Foreign Transactions" multiplier (e.g. Atmos
                Summit at 3x) earns its full bonus on foreign Groceries even if
                its normal Groceries rate is lower.
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">Fallback</p>
              <p>
                If every card in the wallet charges a foreign transaction fee,
                cards compete normally and the user incurs the ~3% fee on the
                winning card's foreign spend.
              </p>
            </div>
          </InfoPopover>
        )}
      </div>
    </div>
  )
}
