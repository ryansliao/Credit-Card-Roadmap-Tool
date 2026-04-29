import { useMemo } from 'react'
import type { RoadmapResponse, WalletResult } from '../../../../api/client'
import { formatMoney, formatPointsExact } from '../../../../utils/format'
import { cardAnnualPointIncomeWindow, cardEafWindow } from '../../../../utils/cardIncome'
import { Popover } from '../../../../components/ui/Popover'
import { Eyebrow } from '../../../../components/ui/Eyebrow'

function formatDuration(years: number, months: number): string {
  const total = years * 12 + months
  const y = Math.floor(total / 12)
  const m = total % 12
  if (y === 0) return `${m} Mo.`
  if (m === 0) return `${y} Years`
  return `${y} Years, ${m} Mo.`
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

/** Inline info icon SVG used inside each Popover trigger. */
function InfoIcon({ size = 15 }: { size?: number }) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  )
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
    { months: 6, label: '0.5Y' },
    { months: 12, label: '1Y' },
    { months: 18, label: '1.5Y' },
    { months: 24, label: '2Y' },
    { months: 30, label: '2.5Y' },
    { months: 36, label: '3Y' },
  ]

  const panelBorder = showStaleHint ? 'border-amber-700/60' : 'border-divider'

  return (
    <div className="min-w-0 flex gap-4 items-stretch">
      {/* Left: summary stats panel */}
      <div
        className={`flex-1 min-w-0 bg-surface border rounded-xl px-5 py-3 flex flex-col justify-center transition-colors ${panelBorder}`}
      >
        {resultsError ? (
          <div className="text-neg text-sm bg-red-950 border border-red-700 rounded-lg p-3">
            {resultsError.message}
          </div>
        ) : !hasStats ? (
          hasNeverCalculated ? (
            <div className="text-ink-muted text-xs text-center py-2">
              Click <span className="font-semibold text-accent">Calculate</span> to see your effective annual fee, fees, and point income.
            </div>
          ) : (
            <div className="text-ink-faint text-xs text-center py-2">
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
                <Eyebrow className="whitespace-nowrap">Effective Annual Fee</Eyebrow>
                <Popover
                  side="bottom"
                  portal
                  trigger={({ onClick, ref }) => (
                    <button
                      ref={ref as React.RefObject<HTMLButtonElement>}
                      onClick={onClick}
                      type="button"
                      aria-label="How Effective Annual Fee is calculated"
                      className="shrink-0 translate-y-px text-ink-faint hover:text-accent transition-colors"
                    >
                      <InfoIcon size={15} />
                    </button>
                  )}
                >
                  <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
                    <p>
                      The wallet's true yearly cost (or value) once you net out
                      rewards, credits, and sign-up bonuses against the annual fees
                      you pay. A negative number means the wallet pays you more than
                      it costs.
                    </p>
                    <div>
                      <p className="text-ink-muted font-medium mb-1">How it's averaged</p>
                      <p>
                        One-time perks — sign-up bonuses, first-year bonuses, one-time
                        credits — are spread evenly across the projection years.
                        Annual fees, recurring credits, and everyday rewards count
                        fully each year.
                      </p>
                    </div>
                    <div>
                      <p className="text-ink-muted font-medium mb-1">Wallet total</p>
                      <p>
                        Each dollar of spend is assigned to the card that earns the
                        most on it, so no dollar is double-counted. The wallet total
                        is the sum of every selected card's individual value.
                      </p>
                    </div>
                  </div>
                </Popover>
              </div>
              {result ? (
                <p className={`text-xl font-bold tabular-nums truncate ${totalEffectiveAF < 0 ? 'text-pos' : 'text-ink'}`}>{formatMoney(totalEffectiveAF)}</p>
              ) : (
                <div className="h-7 flex items-center justify-center">
                  <div className="h-4 w-20 bg-accent/20 rounded animate-pulse" />
                </div>
              )}
            </div>
            <div className="bg-divider/60 self-stretch my-1" />
            <div className="px-1 py-0.5 text-center min-w-0 flex flex-col justify-center gap-1">
              <div className="flex items-center justify-center gap-1 h-5">
                <Eyebrow className="whitespace-nowrap">Annual Fees</Eyebrow>
                <Popover
                  side="bottom"
                  portal
                  trigger={({ onClick, ref }) => (
                    <button
                      ref={ref as React.RefObject<HTMLButtonElement>}
                      onClick={onClick}
                      type="button"
                      aria-label="How Annual Fees is calculated"
                      className="shrink-0 translate-y-px text-ink-faint hover:text-accent transition-colors"
                    >
                      <InfoIcon size={15} />
                    </button>
                  )}
                >
                  <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
                    <p>
                      Sum of the listed annual fee for every active card — what
                      you'd pay your card issuers each year, before credits,
                      sign-up bonuses, or rewards are netted out.
                    </p>
                    <div>
                      <p className="text-ink-muted font-medium mb-1">First-year waivers</p>
                      <p>
                        Cards with a waived first-year fee still show at their full
                        fee here. The waiver only affects the Effective Annual Fee,
                        where year 1 uses the waived amount and later years use the
                        recurring fee.
                      </p>
                    </div>
                    <div>
                      <p className="text-ink-muted font-medium mb-1">Disabled cards</p>
                      <p>
                        Cards toggled off in the timeline don't count toward any
                        wallet totals. Turn them back on to include their fees and
                        rewards.
                      </p>
                    </div>
                  </div>
                </Popover>
              </div>
              {result ? (
                <p className="text-xl font-bold text-ink tabular-nums truncate">{formatMoney(totalAnnualFees)}</p>
              ) : (
                <div className="h-7 flex items-center justify-center">
                  <div className="h-4 w-20 bg-divider/50 rounded animate-pulse" />
                </div>
              )}
            </div>
            <div className="bg-divider/60 self-stretch my-1" />
            <div className="px-1 py-0.5 text-center min-w-0 flex flex-col justify-center gap-1">
              <div className="flex items-center justify-center gap-1 h-5">
                <Eyebrow className="whitespace-nowrap">Point Income</Eyebrow>
                <Popover
                  side="bottom"
                  portal
                  trigger={({ onClick, ref }) => (
                    <button
                      ref={ref as React.RefObject<HTMLButtonElement>}
                      onClick={onClick}
                      type="button"
                      aria-label="How Income is calculated"
                      className="shrink-0 translate-y-px text-ink-faint hover:text-accent transition-colors"
                    >
                      <InfoIcon size={15} />
                    </button>
                  )}
                >
                  <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
                    <p>
                      Rewards earned per year from your spending, across every card
                      in the wallet. With the Sign Up Bonus toggle on, sign-up
                      bonuses and first-year matches are spread across the projection
                      and counted here too; with it off, only your everyday rewards
                      show up.
                    </p>
                    <div>
                      <p className="text-ink-muted font-medium mb-1">How spend is assigned</p>
                      <p>
                        Each category goes to whichever card earns the most on it.
                        If two cards tie, the dollars are split evenly. Flat annual
                        point bonuses are added on top.
                      </p>
                    </div>
                    <div>
                      <p className="text-ink-muted font-medium mb-1">Point upgrades</p>
                      <p>
                        Some cards earn points that become more valuable when paired
                        with a premium card (e.g. Chase Freedom's UR Cash is worth
                        more when you also hold a Sapphire). When that pairing
                        exists, the earn is upgraded and valued at the higher rate.
                      </p>
                    </div>
                  </div>
                </Popover>
              </div>
              {result ? (
                <p className="text-xl font-bold text-ink tabular-nums truncate">
                  {formatPointsExact(Math.round(totalAnnualPoints))}
                  <span className="ml-1 text-sm font-medium text-ink-muted">Pts/Year</span>
                </p>
              ) : (
                <div className="h-7 flex items-center justify-center">
                  <div className="h-4 w-20 bg-divider/50 rounded animate-pulse" />
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* Middle: duration slider */}
      <div
        className={`shrink-0 w-56 lg:w-64 bg-surface border rounded-xl px-4 py-3 flex flex-col justify-center transition-colors ${panelBorder}`}
      >
        <div className="flex items-baseline justify-between mb-2">
          <div className="flex items-center gap-1">
            <Eyebrow className="whitespace-nowrap">Time Horizon</Eyebrow>
            <Popover
              side="bottom"
              portal
              trigger={({ onClick, ref }) => (
                <button
                  ref={ref as React.RefObject<HTMLButtonElement>}
                  onClick={onClick}
                  type="button"
                  aria-label="How time horizon affects calculation"
                  className="shrink-0 translate-y-px text-ink-faint hover:text-accent transition-colors"
                >
                  <InfoIcon size={15} />
                </button>
              )}
            >
              <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
                <p>
                  How many years to project the wallet's value. One-time perks
                  — sign-up bonuses, first-year rewards, first-year fee waivers,
                  one-time credits — are spread across this period to produce
                  an average annual value.
                </p>
                <div>
                  <p className="text-ink-muted font-medium mb-1">Why it matters</p>
                  <p>
                    Longer projections spread one-time perks thinner, so cards
                    with big sign-up bonuses look less valuable per year.
                    Recurring stuff — annual fees, statement credits, everyday
                    rewards — isn't affected.
                  </p>
                </div>
                <div>
                  <p className="text-ink-muted font-medium mb-1">Future cards</p>
                  <p>
                    A card with a future start date only contributes from when
                    it becomes active, so a longer window gives those cards more
                    time to pay off.
                  </p>
                </div>
              </div>
            </Popover>
          </div>
          <span className="text-xs font-medium text-ink tabular-nums">
            {formatDuration(durationYears, durationMonths)}
          </span>
        </div>
        <input
          type="range"
          min={6}
          max={36}
          value={durationYears * 12 + durationMonths}
          onChange={(e) => {
            const total = Number(e.target.value)
            onDurationChange(Math.floor(total / 12), total % 12)
          }}
          className="w-full h-1.5 accent-accent cursor-pointer block my-0"
        />
        <div className="relative h-4 mt-2 mx-2">
          {durationTicks.map((t) => {
            const pct = ((t.months - 6) / 30) * 100
            // All labels center-aligned on their position so the visual
            // spacing between labels is even. End labels overflow slightly
            // into the panel's px-4 padding — acceptable.
            return (
              <span
                key={t.label}
                className="absolute text-[10px] text-ink-faint tabular-nums -translate-x-1/2"
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
        className={`shrink-0 w-44 bg-surface border rounded-xl px-3 py-2 flex flex-col justify-center transition-colors ${panelBorder}`}
      >
        <div className="flex items-center justify-center gap-1 mb-2.5">
          <Eyebrow className="whitespace-nowrap">Sign-Up Bonuses</Eyebrow>
          <Popover
            side="bottom"
            portal
            trigger={({ onClick, ref }) => (
              <button
                ref={ref as React.RefObject<HTMLButtonElement>}
                onClick={onClick}
                type="button"
                aria-label="How the Sign Up Bonus toggle affects calculation"
                className="shrink-0 translate-y-px text-ink-faint hover:text-accent transition-colors"
              >
                <InfoIcon size={15} />
              </button>
            )}
          >
            <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
              <p>
                Controls whether sign-up bonuses affect the wallet's Effective
                Annual Fee and income. Turn off to see what the wallet looks
                like once every welcome offer has been claimed — its long-term,
                steady-state value.
              </p>
              <div>
                <p className="text-ink-muted font-medium mb-1">When on</p>
                <p>
                  Sign-up bonuses are spread across the projection and counted
                  toward income. Cards with an active sign-up offer get
                  priority for spend during their window (which boosts their
                  income those months). The lost value from diverting spend
                  away from your best-earning card is deducted.
                </p>
              </div>
              <div>
                <p className="text-ink-muted font-medium mb-1">When off</p>
                <p>
                  Every card is treated as if it had no welcome offer. Useful
                  for comparing cards purely on long-term value.
                </p>
              </div>
              <div>
                <p className="text-ink-muted font-medium mb-1">What doesn't change</p>
                <p>
                  Point balances you track manually. The timeline's SUB
                  earned-date markers and 5/24 status also aren't affected.
                </p>
              </div>
            </div>
          </Popover>
        </div>
        <div
          role="radiogroup"
          aria-label="Include Sign Up Bonuses in calculation"
          className="flex rounded-md border border-divider overflow-hidden text-xs font-medium"
        >
          <button
            type="button"
            role="radio"
            aria-checked={includeSubs}
            onClick={() => onIncludeSubsChange(true)}
            className={`flex-1 px-2 py-1 transition-colors ${
              includeSubs
                ? 'bg-accent/90 text-page'
                : 'bg-surface text-ink-muted hover:text-ink'
            }`}
          >
            Include
          </button>
          <button
            type="button"
            role="radio"
            aria-checked={!includeSubs}
            onClick={() => onIncludeSubsChange(false)}
            className={`flex-1 px-2 py-1 transition-colors border-l border-divider ${
              !includeSubs
                ? 'bg-accent/90 text-page'
                : 'bg-surface text-ink-muted hover:text-ink'
            }`}
          >
            Exclude
          </button>
        </div>
      </div>

      {/* Right: timeline legend */}
      {roadmap && (
        <div
          className={`shrink-0 w-52 bg-surface border rounded-xl px-3 py-2 flex flex-col justify-center transition-colors ${panelBorder}`}
        >
          <div className="grid grid-cols-[36px_1fr] gap-x-2 gap-y-2 items-center text-xs text-ink-faint">
            <span
              aria-hidden
              className="justify-self-center inline-block rounded-full"
              style={{
                width: 32,
                height: 12,
                backgroundColor: 'color-mix(in oklab, var(--chart-sub) 20%, transparent)',
                border: '1px solid var(--chart-sub)',
              }}
              title="Yellow segment of the bar covers the SUB earning period (anchor → projected earn date)"
            />
            <span className="whitespace-nowrap">SUB Earning Period</span>

            <span
              aria-hidden
              className="justify-self-center inline-block rounded-full"
              style={{
                width: 32,
                height: 12,
                backgroundColor: 'color-mix(in oklab, var(--chart-points) 20%, transparent)',
                border: '1px solid var(--chart-points)',
              }}
              title="Coloured bar shows when the card is active (open and not closed)"
            />
            <span className="whitespace-nowrap">Active Card Window</span>

            <span
              aria-hidden
              className="justify-self-center relative inline-block w-7 h-3.5 rounded-full bg-accent"
              title="Per-card toggle in the timeline includes the card in calculation"
            >
              <span
                className="absolute w-2.5 h-2.5 rounded-full bg-surface"
                style={{ left: 14, top: 2 }}
              />
            </span>
            <span className="whitespace-nowrap">Add Card to Calculation</span>
          </div>
        </div>
      )}
    </div>
  )
}
