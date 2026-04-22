import { useMemo, useState } from 'react'
import type { CardResult, RoadmapResponse, WalletResult } from '../../../../api/client'
import { formatMoney, formatPointsExact } from '../../../../utils/format'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'

type StatTopic = 'eaf' | 'income' | 'fees' | 'duration' | 'subs' | null

/** Annual recurring point income for a card.
 *
 * `annual_point_earn` is already per-year on both the simple and segmented
 * calculator paths and excludes one-time SUB bonuses / first-year matches,
 * so it's the recurring category earn rate. */
function cardAnnualPointIncome(c: CardResult): number {
  return c.annual_point_earn
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
  roadmap?: RoadmapResponse | null
  isCalculating: boolean
  isStale: boolean
  durationYears: number
  durationMonths: number
  onDurationChange: (years: number, months: number) => void
  includeSubs: boolean
  onIncludeSubsChange: (value: boolean) => void
  resultsError?: Error | null
}

export function WalletSummaryStats({
  result,
  roadmap,
  isCalculating,
  isStale,
  durationYears,
  durationMonths,
  onDurationChange,
  includeSubs,
  onIncludeSubsChange,
  resultsError,
}: Props) {
  const [statTopic, setStatTopic] = useState<StatTopic>(null)

  const { totalEffectiveAF, totalAnnualPoints, totalAnnualFees } = useMemo(() => {
    const selected = result?.card_results.filter((c) => c.selected) ?? []
    return {
      totalAnnualFees: selected.reduce((s, c) => s + c.annual_fee, 0),
      totalEffectiveAF: selected.reduce((s, c) => s + c.effective_annual_fee, 0),
      totalAnnualPoints: selected.reduce((s, c) => s + cardAnnualPointIncome(c), 0),
    }
  }, [result])

  const hasStats = !!result || isCalculating

  const showStaleHint = isStale && hasStats && !resultsError

  const durationTicks = [
    { months: 1, label: '1M' },
    { months: 12, label: '1Y' },
    { months: 24, label: '2Y' },
    { months: 36, label: '3Y' },
    { months: 48, label: '4Y' },
    { months: 60, label: '5Y' },
  ]

  const panelBorder = showStaleHint ? 'border-amber-700/60' : 'border-slate-700'

  return (
    <div className="min-w-0 flex gap-4 items-stretch">
      {/* Left: summary stats panel */}
      <div
        className={`flex-1 min-w-0 bg-slate-900 border rounded-xl px-5 py-3 flex flex-col justify-center transition-colors ${panelBorder}`}
      >
        {resultsError ? (
          <div className="text-red-400 text-sm bg-red-950 border border-red-700 rounded-lg p-3">
            {resultsError.message}
          </div>
        ) : !hasStats ? (
          <div className="text-slate-500 text-xs text-center py-2">
            Add cards to see effective annual fee (credits, SUB and fees amortised over your projection).
          </div>
        ) : (
          <div
            className={`grid grid-cols-[1fr_1px_1fr_1px_1fr] gap-3 items-stretch w-full transition-opacity ${
              showStaleHint ? 'opacity-60' : ''
            }`}
          >
            <div className="px-1 py-0.5 text-center min-w-0 flex flex-col justify-center gap-1">
              <div className="flex items-center justify-center gap-1 h-5">
                <p className="text-[10px] text-indigo-300 uppercase tracking-wider whitespace-nowrap">Effective Annual Fee</p>
                <InfoIconButton onClick={() => setStatTopic('eaf')} label="How Effective Annual Fee is calculated" />
              </div>
              {result ? (
                <p className={`text-xl font-bold tabular-nums truncate ${totalEffectiveAF < 0 ? 'text-emerald-400' : 'text-indigo-100'}`}>{formatMoney(totalEffectiveAF)}</p>
              ) : (
                <div className="h-7 flex items-center justify-center">
                  <div className="h-4 w-20 bg-indigo-800/50 rounded animate-pulse" />
                </div>
              )}
            </div>
            <div className="bg-slate-700/60 self-stretch my-1" />
            <div className="px-1 py-0.5 text-center min-w-0 flex flex-col justify-center gap-1">
              <div className="flex items-center justify-center gap-1 h-5">
                <p className="text-[10px] text-slate-400 uppercase tracking-wider whitespace-nowrap">Annual Fees</p>
                <InfoIconButton onClick={() => setStatTopic('fees')} label="How Annual Fees is calculated" />
              </div>
              {result ? (
                <p className="text-xl font-bold text-white tabular-nums truncate">{formatMoney(totalAnnualFees)}</p>
              ) : (
                <div className="h-7 flex items-center justify-center">
                  <div className="h-4 w-20 bg-slate-700/50 rounded animate-pulse" />
                </div>
              )}
            </div>
            <div className="bg-slate-700/60 self-stretch my-1" />
            <div className="px-1 py-0.5 text-center min-w-0 flex flex-col justify-center gap-1">
              <div className="flex items-center justify-center gap-1 h-5">
                <p className="text-[10px] text-slate-400 uppercase tracking-wider whitespace-nowrap">Recurring Income</p>
                <InfoIconButton onClick={() => setStatTopic('income')} label="How Recurring Point Income is calculated" />
              </div>
              {result ? (
                <p className="text-xl font-bold text-white tabular-nums truncate">
                  {formatPointsExact(Math.round(totalAnnualPoints))}
                  <span className="ml-1 text-sm font-medium text-slate-400">Pts/Year</span>
                </p>
              ) : (
                <div className="h-7 flex items-center justify-center">
                  <div className="h-4 w-20 bg-slate-700/50 rounded animate-pulse" />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Middle: duration slider */}
      <div
        className={`shrink-0 w-64 lg:w-72 bg-slate-900 border rounded-xl px-4 py-3 flex flex-col justify-center transition-colors ${panelBorder}`}
      >
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-1">
            <span className="text-[10px] text-slate-400 uppercase tracking-wider">Time Horizon</span>
            <InfoIconButton onClick={() => setStatTopic('duration')} label="How time horizon affects calculation" />
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
          className="w-full h-1.5 accent-indigo-500 cursor-pointer block my-0"
        />
        <div className="relative h-4 mt-2">
          {durationTicks.map((t) => {
            const pct = ((t.months - 1) / 59) * 100
            return (
              <span
                key={t.label}
                className="absolute text-[10px] text-slate-500 -translate-x-1/2 tabular-nums"
                style={{ left: `${pct}%` }}
              >
                {t.label}
              </span>
            )
          })}
        </div>
      </div>

      {/* Include SUBs toggle — segmented control, distinct from the per-card
          enable/disable pill toggle in the timeline. */}
      <div
        className={`shrink-0 w-44 bg-slate-900 border rounded-xl px-3 py-2 flex flex-col justify-center transition-colors ${panelBorder}`}
      >
        <div className="flex items-center gap-1 mb-2.5">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider whitespace-nowrap">Sign Up Bonuses</span>
          <InfoIconButton onClick={() => setStatTopic('subs')} label="How the Sign Up Bonus toggle affects calculation" />
        </div>
        <div
          role="radiogroup"
          aria-label="Include Sign Up Bonuses in calculation"
          className="flex rounded-md border border-slate-700 overflow-hidden text-xs font-medium"
        >
          <button
            type="button"
            role="radio"
            aria-checked={includeSubs}
            onClick={() => onIncludeSubsChange(true)}
            className={`flex-1 px-2 py-1 transition-colors ${
              includeSubs
                ? 'bg-indigo-500/90 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Include
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={!includeSubs}
            onClick={() => onIncludeSubsChange(false)}
            className={`flex-1 px-2 py-1 transition-colors border-l border-slate-700 ${
              !includeSubs
                ? 'bg-indigo-500/90 text-white'
                : 'bg-slate-800 text-slate-400 hover:text-slate-200'
            }`}
          >
            Exclude
          </button>
        </div>
      </div>

      {/* Right: 5/24 status + legend */}
      {roadmap && (
        <div
          className={`shrink-0 w-52 bg-slate-900 border rounded-xl px-3 py-2 flex flex-col justify-center transition-colors ${panelBorder}`}
        >
          <div
            className="flex items-center justify-between gap-2"
            title={`${roadmap.five_twenty_four_count} personal cards opened in last 24 months`}
          >
            <div className="flex items-center gap-1.5">
              <span
                aria-hidden
                className={`inline-block w-1.5 h-1.5 rounded-full ${
                  roadmap.five_twenty_four_eligible ? 'bg-emerald-400' : 'bg-red-400'
                }`}
              />
              <p className="text-[10px] text-slate-400 uppercase tracking-wider whitespace-nowrap">5/24 Status</p>
            </div>
            <p
              className={`text-sm font-semibold tabular-nums ${
                roadmap.five_twenty_four_eligible ? 'text-emerald-400' : 'text-red-400'
              }`}
            >
              {roadmap.five_twenty_four_count}/5
            </p>
          </div>
          <div className="mt-1.5 pt-1.5 border-t border-slate-700/40 grid grid-cols-[14px_1fr] gap-x-2 gap-y-0.5 items-center text-[10px] text-slate-500">
            <span
              aria-hidden
              className="justify-self-center inline-block"
              style={{ width: 2, height: 9, backgroundColor: '#f59e0b' }}
              title="Amber line in the timeline marks the SUB earned date (dashed when projected)"
            />
            <span className="whitespace-nowrap">SUB Earned Date</span>
            <span
              aria-hidden
              className="justify-self-center relative inline-block w-4 h-2 rounded-full bg-indigo-500"
              title="Per-card toggle in the timeline includes the card in calculation"
            >
              <span
                className="absolute top-0.5 w-1 h-1 rounded-full bg-white"
                style={{ left: 9 }}
              />
            </span>
            <span className="whitespace-nowrap">Add Card to Calculation</span>
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
          <InfoPopover title="Recurring Point Income" onClose={() => setStatTopic(null)}>
            <p>
              Recurring points and miles earned per year from category spend
              across all selected cards. Excludes one-time sign-up bonuses
              and first-year matches — those roll into the EAF calculation
              and currency balance totals separately.
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
          </InfoPopover>
        )}

        {statTopic === 'fees' && (
          <InfoPopover title="Annual Fees" onClose={() => setStatTopic(null)}>
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

        {statTopic === 'subs' && (
          <InfoPopover title="Sign Up Bonuses" onClose={() => setStatTopic(null)}>
            <p>
              Controls whether Sign Up Bonuses count toward the wallet's
              effective annual fee and recurring income across the roadmap.
              Toggle off to see the wallet's steady-state value — how it earns
              once all SUBs have been claimed and the welcome period is over.
            </p>
            <div>
              <p className="text-slate-300 font-medium mb-1">When included</p>
              <p>
                SUB bonuses (points and cash) are amortised into EAF, the SUB
                spend requirement pulls allocation priority during its window
                (inflating recurring income for the card with an active SUB),
                and SUB opportunity cost is deducted from the best alternative
                card.
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">When excluded</p>
              <p>
                Every card is evaluated as if it had no welcome offer: no SUB
                amortisation in EAF, no SUB-window allocation boost, and no
                opportunity cost. Useful for comparing cards on their long-term
                merits.
              </p>
            </div>
            <div>
              <p className="text-slate-300 font-medium mb-1">What stays the same</p>
              <p>
                Currency balances you track manually are unaffected. The
                roadmap's SUB earned-date markers and 5/24 status also ignore
                this toggle.
              </p>
            </div>
          </InfoPopover>
        )}

        {statTopic === 'duration' && (
          <InfoPopover title="Time Horizon" onClose={() => setStatTopic(null)}>
            <p>
              How long to project the wallet's value. The calculator amortizes
              one-time benefits (sign-up bonuses, first-year bonuses, first-year
              fee waivers, one-time credits) across this period to produce an
              average annual EAF.
            </p>
            <div>
              <p className="text-slate-300 font-medium mb-1">Effect on EAF</p>
              <p>
                Longer horizons spread one-time benefits thinner, so cards with
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

    </div>
  )
}
