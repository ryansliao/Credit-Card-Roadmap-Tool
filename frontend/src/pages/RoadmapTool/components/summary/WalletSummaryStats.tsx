import { useMemo, type ReactNode } from 'react'
import type { WalletResult } from '../../../../api/client'
import { cardAnnualPointIncomeWindow, cardEafWindow } from '../../../../utils/cardIncome'
import { Popover } from '../../../../components/ui/Popover'
import { Stat } from '../../../../components/ui/Stat'
import { Money } from '../../../../components/ui/Money'

interface DurationParts {
  years: number | null
  months: number | null
}

function durationParts(years: number, months: number): DurationParts {
  const total = years * 12 + months
  const y = Math.floor(total / 12)
  const m = total % 12
  if (y === 0) return { years: null, months: m }
  if (m === 0) return { years: y, months: null }
  return { years: y, months: m }
}

interface Props {
  result: WalletResult | null
  isCalculating: boolean
  isStale: boolean
  /** True when the wallet has cards/spending set up but no calc has ever
   * been persisted. */
  hasNeverCalculated?: boolean
  durationYears: number
  durationMonths: number
  onDurationChange: (years: number, months: number) => void
  includeSubs: boolean
  onIncludeSubsChange: (value: boolean) => void
  resultsError?: Error | null
}

function InfoButton({ label, children }: { label: string; children: ReactNode }) {
  return (
    <Popover
      side="bottom"
      portal
      trigger={({ onClick, ref }) => (
        <button
          ref={ref as React.RefObject<HTMLButtonElement>}
          onClick={onClick}
          type="button"
          aria-label={label}
          title={label}
          className="shrink-0 text-ink-faint hover:text-accent transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        </button>
      )}
    >
      <div className="space-y-3 text-xs text-ink-muted leading-relaxed">{children}</div>
    </Popover>
  )
}

export function WalletSummaryStats({
  result,
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

  const durationLabel = (() => {
    const p = durationParts(durationYears, durationMonths)
    const parts: string[] = []
    if (p.years != null) parts.push(`${p.years}y`)
    if (p.months != null) parts.push(`${p.months}mo`)
    return parts.join(' ')
  })()

  if (resultsError) {
    return (
      <div className="bg-surface border border-neg/40 rounded-xl shadow-card p-5 text-sm text-neg">
        {resultsError.message}
      </div>
    )
  }

  return (
    <div className={`flex flex-col gap-3 transition-opacity ${showStaleHint ? 'opacity-60' : ''}`}>
      {/* Hero stats trio */}
      <div className="grid grid-cols-3 gap-3">
        <div className="bg-surface border border-divider rounded-xl shadow-card p-4">
          <Stat
            label="Effective annual fee"
            info={
              <InfoButton label="How Effective Annual Fee is calculated">
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
              </InfoButton>
            }
            value={
              hasStats && result ? (
                <Money value={totalEffectiveAF} precision={0} feature tone="auto" />
              ) : (
                <span className="text-2xl font-bold text-ink-faint tnum-mono">—</span>
              )
            }
            caption={
              !hasStats && hasNeverCalculated
                ? 'Click Calculate to see your value'
                : undefined
            }
          />
        </div>

        <div className="bg-surface border border-divider rounded-xl shadow-card p-4">
          <Stat
            label="Annual fees"
            info={
              <InfoButton label="How Annual Fees is calculated">
                <p>
                  The total annual fee billed by the cards in your wallet — what
                  you'd pay every year if every selected card stayed open.
                  First-year-fee waivers don't reduce this number; they're
                  netted into the Effective Annual Fee instead.
                </p>
              </InfoButton>
            }
            value={
              hasStats && result ? (
                <Money value={totalAnnualFees} precision={0} feature tone="neutral" />
              ) : (
                <span className="text-2xl font-bold text-ink-faint tnum-mono">—</span>
              )
            }
          />
        </div>

        <div className="bg-surface border border-divider rounded-xl shadow-card p-4">
          <Stat
            label="Annual point income"
            info={
              <InfoButton label="How Annual Point Income is calculated">
                <p>
                  The dollar value of all points and credits the wallet earns
                  per year, valued at each currency's cents-per-point. Sign-up
                  bonuses and first-year perks are spread across the projection
                  years.
                </p>
              </InfoButton>
            }
            value={
              hasStats && result ? (
                <Money value={totalAnnualPoints} precision={0} feature tone="pos" />
              ) : (
                <span className="text-2xl font-bold text-ink-faint tnum-mono">—</span>
              )
            }
          />
        </div>
      </div>

      {/* Calc-inputs strip */}
      <div className="bg-surface border border-divider rounded-xl shadow-card px-4 py-3 flex items-center gap-5 flex-wrap">
        <div className="flex items-center gap-3 flex-1 min-w-[280px]">
          <div className="flex items-center gap-1.5 shrink-0">
            <span className="text-[11px] uppercase tracking-wider text-ink-faint font-semibold">Time horizon</span>
            <InfoButton label="How time horizon affects calculation">
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
            </InfoButton>
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
            className="flex-1 min-w-0 h-1.5 accent-accent cursor-pointer"
          />
          <span className="text-xs font-medium text-ink tnum-mono shrink-0 min-w-[56px] text-right">{durationLabel}</span>
        </div>

        <div className="w-px h-7 bg-divider shrink-0 hidden md:block" />

        <div className="flex items-center gap-3 shrink-0">
          <div className="flex items-center gap-1.5">
            <span className="text-[11px] uppercase tracking-wider text-ink-faint font-semibold whitespace-nowrap">Sign-up bonuses</span>
            <InfoButton label="How the Sign Up Bonus toggle affects calculation">
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
            </InfoButton>
          </div>
          <div
            role="radiogroup"
            aria-label="Include Sign Up Bonuses in calculation"
            className="inline-flex bg-surface-2 border border-divider-strong rounded-md p-0.5 text-xs font-medium"
          >
            <button
              type="button"
              role="radio"
              aria-checked={includeSubs}
              onClick={() => onIncludeSubsChange(true)}
              className={`px-3 py-1 rounded transition-colors ${
                includeSubs
                  ? 'bg-surface text-ink shadow-card'
                  : 'text-ink-faint hover:text-ink'
              }`}
            >
              Include
            </button>
            <button
              type="button"
              role="radio"
              aria-checked={!includeSubs}
              onClick={() => onIncludeSubsChange(false)}
              className={`px-3 py-1 rounded transition-colors ${
                !includeSubs
                  ? 'bg-surface text-ink shadow-card'
                  : 'text-ink-faint hover:text-ink'
              }`}
            >
              Exclude
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}
