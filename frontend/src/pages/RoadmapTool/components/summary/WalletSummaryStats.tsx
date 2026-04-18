import { useMemo, useState } from 'react'
import type { CardResult, WalletResult } from '../../../../api/client'
import { formatMoney, formatPointsExact } from '../../../../utils/format'
import { InfoIconButton, InfoPopover } from '../../../../components/InfoPopover'

type StatTopic = 'eaf' | 'income' | 'fees' | 'duration' | null

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
  isStale: boolean
  durationYears: number
  durationMonths: number
  onDurationChange: (years: number, months: number) => void
  resultsError?: Error | null
}

export function WalletSummaryStats({
  result,
  isCalculating,
  isStale,
  durationYears,
  durationMonths,
  onDurationChange,
  resultsError,
}: Props) {
  const [statTopic, setStatTopic] = useState<StatTopic>(null)

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

  const showStaleHint = isStale && hasStats && !resultsError

  return (
    <div className="min-w-0">
      <div
        className={`bg-slate-900 border rounded-xl px-4 py-3 flex gap-4 items-stretch transition-colors ${
          showStaleHint ? 'border-amber-700/60' : 'border-slate-700'
        }`}
      >
        {/* Left: 3 squished summary stats */}
        <div className="flex-1 min-w-0 flex flex-col justify-center">
          {resultsError ? (
            <div className="text-red-400 text-sm bg-red-950 border border-red-700 rounded-lg p-3">
              {resultsError.message}
            </div>
          ) : !hasStats ? (
            <div className="text-slate-500 text-xs text-center py-2">
              Add cards to see effective annual fee (credits, SUB and fees amortised over your projection).
            </div>
          ) : (
            <div className={`grid grid-cols-3 gap-2 transition-opacity ${showStaleHint ? 'opacity-60' : ''}`}>
              <div className="bg-indigo-900/40 border border-indigo-700 rounded-xl px-2 py-2 text-center min-w-0">
                <div className="flex items-center justify-center gap-1">
                  <p className="text-[10px] text-indigo-300 uppercase tracking-wider truncate">Effective Annual Fee</p>
                  <InfoIconButton onClick={() => setStatTopic('eaf')} label="How Effective Annual Fee is calculated" />
                </div>
                {result ? (
                  <p className={`text-lg font-bold mt-0.5 truncate ${totalEffectiveAF < 0 ? 'text-emerald-400' : 'text-indigo-100'}`}>{formatMoney(totalEffectiveAF)}</p>
                ) : (
                  <div className="h-6 mt-0.5 flex items-center justify-center">
                    <div className="h-4 w-16 bg-indigo-800/50 rounded animate-pulse" />
                  </div>
                )}
              </div>
              <div className="bg-slate-800 border border-slate-700 rounded-xl px-2 py-2 text-center min-w-0">
                <div className="flex items-center justify-center gap-1">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider truncate">Annual Point Income</p>
                  <InfoIconButton onClick={() => setStatTopic('income')} label="How Annual Point Income is calculated" />
                </div>
                {result ? (
                  <p className="text-lg font-bold text-white mt-0.5 truncate">{formatPointsExact(Math.round(totalAnnualPoints))}</p>
                ) : (
                  <div className="h-6 mt-0.5 flex items-center justify-center">
                    <div className="h-4 w-16 bg-slate-700/50 rounded animate-pulse" />
                  </div>
                )}
              </div>
              <div className="bg-slate-800 border border-slate-700 rounded-xl px-2 py-2 text-center min-w-0">
                <div className="flex items-center justify-center gap-1">
                  <p className="text-[10px] text-slate-400 uppercase tracking-wider truncate">Total Annual Fees</p>
                  <InfoIconButton onClick={() => setStatTopic('fees')} label="How Total Annual Fees is calculated" />
                </div>
                {result ? (
                  <p className="text-lg font-bold text-red-400 mt-0.5 truncate">{formatMoney(totalAnnualFees)}</p>
                ) : (
                  <div className="h-6 mt-0.5 flex items-center justify-center">
                    <div className="h-4 w-16 bg-slate-700/50 rounded animate-pulse" />
                  </div>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Vertical divider */}
        <div className="w-px bg-slate-700 shrink-0" />

        {/* Right: duration slider */}
        <div className="w-64 lg:w-72 shrink-0 flex flex-col justify-center gap-3">
          <div>
            <div className="flex items-center justify-between mb-0.5">
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
              className="w-full h-1.5 accent-indigo-500 cursor-pointer"
            />
            <div className="flex justify-between text-[10px] text-slate-600 mt-0.5">
              <span>1M</span>
              <span>1Y</span>
              <span>2Y</span>
              <span>3Y</span>
              <span>4Y</span>
              <span>5Y</span>
            </div>
          </div>
        </div>
      </div>

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

    </div>
  )
}
