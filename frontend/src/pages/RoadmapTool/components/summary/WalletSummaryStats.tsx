import { useMemo, useState } from 'react'
import type { RoadmapResponse, WalletResult } from '../../../../api/client'
import { formatMoney, formatPointsExact } from '../../../../utils/format'
import { cardAnnualPointIncomeWindow, cardEafWindow } from '../../../../utils/cardIncome'
import { InfoIconButton, InfoQuoteBox } from '../../../../components/InfoPopover'

type StatTopicName = 'eaf' | 'income' | 'fees' | 'duration' | 'subs'
type StatTopic = { name: StatTopicName; anchor: HTMLElement } | null

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
  /** True when the wallet has cards/spending set up but no calc has ever
   * been persisted. Drives the empty-state copy so first-time users see a
   * "Click Calculate" prompt instead of the "Add cards" message. */
  hasNeverCalculated?: boolean
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
  hasNeverCalculated,
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
    // Wallet-level totals: sum window-basis per-card values so the result
    // stays on the wallet's own window. Per-card display values are
    // active-year basis; summing those would inflate both EAF and income.
    return {
      totalAnnualFees: selected.reduce((s, c) => s + c.annual_fee, 0),
      totalEffectiveAF: selected.reduce(
        (s, c) => s + (cardEafWindow(c, includeSubs) ?? 0),
        0,
      ),
      totalAnnualPoints: selected.reduce(
        (s, c) => s + (cardAnnualPointIncomeWindow(c, includeSubs) ?? 0),
        0,
      ),
    }
  }, [result, includeSubs])

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
          hasNeverCalculated ? (
            <div className="text-slate-300 text-xs text-center py-2">
              Click <span className="font-semibold text-indigo-300">Calculate</span> to see your effective annual fee, fees, and point income.
            </div>
          ) : (
            <div className="text-slate-500 text-xs text-center py-2">
              Add cards to see effective annual fee (credits, SUB and fees amortised over your projection).
            </div>
          )
        ) : (
          <div
            className={`grid grid-cols-[1fr_1px_1fr_1px_1fr] gap-3 items-stretch w-full transition-opacity ${
              showStaleHint ? 'opacity-60' : ''
            }`}
          >
            <div className="px-1 py-0.5 text-center min-w-0 flex flex-col justify-center gap-1">
              <div className="flex items-center justify-center gap-1 h-5">
                <p className="text-[10px] text-indigo-300 uppercase tracking-wider whitespace-nowrap">Effective Annual Fee</p>
                <InfoIconButton
                  onClick={(e) => {
                    const anchor = e.currentTarget
                    setStatTopic((t) =>
                      t?.name === 'eaf' ? null : { name: 'eaf', anchor },
                    )
                  }}
                  label="How Effective Annual Fee is calculated"
                  active={statTopic?.name === 'eaf'}
                />
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
                <InfoIconButton
                  onClick={(e) => {
                    const anchor = e.currentTarget
                    setStatTopic((t) =>
                      t?.name === 'fees' ? null : { name: 'fees', anchor },
                    )
                  }}
                  label="How Annual Fees is calculated"
                  active={statTopic?.name === 'fees'}
                />
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
                <p className="text-[10px] text-slate-400 uppercase tracking-wider whitespace-nowrap">Point Income</p>
                <InfoIconButton
                  onClick={(e) => {
                    const anchor = e.currentTarget
                    setStatTopic((t) =>
                      t?.name === 'income' ? null : { name: 'income', anchor },
                    )
                  }}
                  label="How Income is calculated"
                  active={statTopic?.name === 'income'}
                />
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
            <InfoIconButton
              onClick={(e) => {
                const anchor = e.currentTarget
                setStatTopic((t) =>
                  t?.name === 'duration' ? null : { name: 'duration', anchor },
                )
              }}
              label="How time horizon affects calculation"
              active={statTopic?.name === 'duration'}
            />
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
        <div className="flex items-center justify-center gap-1 mb-2.5">
          <span className="text-[10px] text-slate-400 uppercase tracking-wider whitespace-nowrap">Sign-Up Bonuses</span>
          <InfoIconButton
            onClick={(e) => {
              const anchor = e.currentTarget
              setStatTopic((t) =>
                t?.name === 'subs' ? null : { name: 'subs', anchor },
              )
            }}
            label="How the Sign Up Bonus toggle affects calculation"
            active={statTopic?.name === 'subs'}
          />
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

      {/* Right: timeline legend */}
      {roadmap && (
        <div
          className={`shrink-0 w-52 bg-slate-900 border rounded-xl px-3 py-2 flex flex-col justify-center transition-colors ${panelBorder}`}
        >
          <div className="grid grid-cols-[20px_1fr] gap-x-2 gap-y-1 items-center text-[10px] text-slate-500">
            <span
              aria-hidden
              className="justify-self-center inline-block"
              style={{ width: 2, height: 11, backgroundColor: '#64748b' }}
              title="Solid slate lines mark Today and the end of the projection window"
            />
            <span className="whitespace-nowrap">Time Horizon Bounds</span>

            <span
              aria-hidden
              className="justify-self-center inline-block"
              style={{
                width: 0,
                height: 11,
                borderLeft: '2px dashed #f59e0b',
              }}
              title="Dashed amber line marks the projected SUB earn date"
            />
            <span className="whitespace-nowrap">SUB Earn Date</span>

            <span
              aria-hidden
              className="justify-self-center inline-block rounded-full"
              style={{
                width: 18,
                height: 7,
                backgroundColor: '#818cf833',
                border: '1px solid #818cf8',
              }}
              title="Coloured bar shows when the card is active (open and not closed)"
            />
            <span className="whitespace-nowrap">Active Card Window</span>

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

      {statTopic?.name === 'eaf' && (
        <InfoQuoteBox anchorEl={statTopic.anchor} title="Effective Annual Fee" onClose={() => setStatTopic(null)}>
          <p>
            The wallet's true yearly cost (or value) once you net out
            rewards, credits, and sign-up bonuses against the annual fees
            you pay. A negative number means the wallet pays you more than
            it costs.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">How it's averaged</p>
            <p>
              One-time perks — sign-up bonuses, first-year bonuses, one-time
              credits — are spread evenly across the projection years.
              Annual fees, recurring credits, and everyday rewards count
              fully each year.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Wallet total</p>
            <p>
              Each dollar of spend is assigned to the card that earns the
              most on it, so no dollar is double-counted. The wallet total
              is the sum of every selected card's individual value.
            </p>
          </div>
        </InfoQuoteBox>
      )}

      {statTopic?.name === 'income' && (
        <InfoQuoteBox anchorEl={statTopic.anchor} title="Income" onClose={() => setStatTopic(null)}>
          <p>
            Rewards earned per year from your spending, across every card
            in the wallet. With the Sign Up Bonus toggle on, sign-up
            bonuses and first-year matches are spread across the projection
            and counted here too; with it off, only your everyday rewards
            show up.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">How spend is assigned</p>
            <p>
              Each category goes to whichever card earns the most on it.
              If two cards tie, the dollars are split evenly. Flat annual
              point bonuses are added on top.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Point upgrades</p>
            <p>
              Some cards earn points that become more valuable when paired
              with a premium card (e.g. Chase Freedom's UR Cash is worth
              more when you also hold a Sapphire). When that pairing
              exists, the earn is upgraded and valued at the higher rate.
            </p>
          </div>
        </InfoQuoteBox>
      )}

      {statTopic?.name === 'fees' && (
        <InfoQuoteBox anchorEl={statTopic.anchor} title="Annual Fees" onClose={() => setStatTopic(null)}>
          <p>
            Sum of the listed annual fee for every active card — what
            you'd pay your card issuers each year, before credits,
            sign-up bonuses, or rewards are netted out.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">First-year waivers</p>
            <p>
              Cards with a waived first-year fee still show at their full
              fee here. The waiver only affects the Effective Annual Fee,
              where year 1 uses the waived amount and later years use the
              recurring fee.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Disabled cards</p>
            <p>
              Cards toggled off in the timeline don't count toward any
              wallet totals. Turn them back on to include their fees and
              rewards.
            </p>
          </div>
        </InfoQuoteBox>
      )}

      {statTopic?.name === 'subs' && (
        <InfoQuoteBox anchorEl={statTopic.anchor} title="Sign Up Bonuses" onClose={() => setStatTopic(null)}>
          <p>
            Controls whether sign-up bonuses affect the wallet's Effective
            Annual Fee and income. Turn off to see what the wallet looks
            like once every welcome offer has been claimed — its long-term,
            steady-state value.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">When on</p>
            <p>
              Sign-up bonuses are spread across the projection and counted
              toward income. Cards with an active sign-up offer get
              priority for spend during their window (which boosts their
              income those months). The lost value from diverting spend
              away from your best-earning card is deducted.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">When off</p>
            <p>
              Every card is treated as if it had no welcome offer. Useful
              for comparing cards purely on long-term value.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">What doesn't change</p>
            <p>
              Point balances you track manually. The timeline's SUB
              earned-date markers and 5/24 status also aren't affected.
            </p>
          </div>
        </InfoQuoteBox>
      )}

      {statTopic?.name === 'duration' && (
        <InfoQuoteBox anchorEl={statTopic.anchor} title="Time Horizon" onClose={() => setStatTopic(null)}>
          <p>
            How many years to project the wallet's value. One-time perks
            — sign-up bonuses, first-year rewards, first-year fee waivers,
            one-time credits — are spread across this period to produce
            an average annual value.
          </p>
          <div>
            <p className="text-slate-300 font-medium mb-1">Why it matters</p>
            <p>
              Longer projections spread one-time perks thinner, so cards
              with big sign-up bonuses look less valuable per year.
              Recurring stuff — annual fees, statement credits, everyday
              rewards — isn't affected.
            </p>
          </div>
          <div>
            <p className="text-slate-300 font-medium mb-1">Future cards</p>
            <p>
              A card with a future start date only contributes from when
              it becomes active, so a longer window gives those cards more
              time to pay off.
            </p>
          </div>
        </InfoQuoteBox>
      )}
    </div>
  )
}
