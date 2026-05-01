# Roadmap Tool Page Shell Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Roadmap Tool's top-level page chrome — header bar (wordmark + scenario picker + help button + Calculate button), the 3-up hero stats trio, and the calc-inputs strip (time horizon slider + SUBs toggle). Replace the vertical binder-tab spine with horizontal tabs (Timeline / Spend) using the foundation `Tabs` primitive. Plan 4a of 4c for the Roadmap Tool's redesign (final sub-plans 4b and 4c follow). Spec: `docs/superpowers/specs/2026-05-01-roadmap-tool-redesign-design.md` Section 6.

**Architecture:** Visual + structural refactor of the page-level layout only. The data plumbing (scenarios, results queries, mutations, hash signature, snapshot logic) and the inner Timeline / Spend views (covered by Plans 4b–4c) stay untouched. The `WalletSummaryStats` 4-panel strip is replaced with two stacked surfaces: a 3-stat hero trio + a quieter calc-inputs strip. The legend (currently rendered in `WalletSummaryStats`) is **temporarily removed** here — Plan 4b adds it back inside the Timeline tab's local toolbar where the spec says it belongs.

**Tech Stack:** React + Vite + Tailwind v4. Foundation primitives in `frontend/src/components/ui/` (Plans 1+3) — `Stat` (with new `info` slot), `Tabs` (horizontal underline), `Button`, `Popover`, plus the existing `ScenarioPicker`. Build: `cd frontend && npm run build`. Lint: `cd frontend && npm run lint`. Dev: `cd frontend && npm run dev`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `frontend/src/pages/RoadmapTool/index.tsx` | Page shell (~1,227 lines). Modified: header section (wordmark + scenario picker + help + Calculate), the binder-tab spine → horizontal `Tabs` primitive, the surrounding layout. Data hooks, `compute`/`hash` functions, and modals untouched. |
| `frontend/src/pages/RoadmapTool/components/summary/WalletSummaryStats.tsx` | Top-of-content summary panel (~548 lines). **Rewritten**: 4-panel strip → 3-stat hero + calc-inputs strip. Drops the legend section. Drops the surrounding stale-fallback panel chrome (the parent in `index.tsx` handles stale styling now). |

The Timeline view (`WalletTimelineChart`, `CardRow`, `GroupSection`, `TimelineGlyphs`, `TimelineAxis`), Spend view (`SpendPanel`, `SpendTabContent`), `ScenarioPicker`, currency / portal popovers, and modals are all out of scope for this plan — touched by Plans 4b and 4c.

---

## Task 1: Page header restyle

The current header (around lines 815–952 of `index.tsx`) uses `<Heading level={3}>` for the page title and inlines a 50-line "How the Roadmap Is Calculated" Popover next to the Calculate button. Restyle to a flat row matching the navbar idiom (wordmark → scenario picker → help button on left, Calculate button on right). The help Popover content stays verbatim — only its trigger position moves.

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/index.tsx`

- [ ] **Step 1: Replace the `<header>` block**

In `frontend/src/pages/RoadmapTool/index.tsx`, find the `<header className="mb-3 shrink-0 flex items-start justify-between gap-4">` block (around line 815) and replace the entire `<header>` element — from `<header>` to its closing `</header>` — with:

```tsx
<header className="mb-4 shrink-0 flex items-center gap-3">
  <h1 className="text-base font-bold text-ink tracking-tight shrink-0">Roadmap</h1>
  {scenarios.length > 0 && (
    <ScenarioPicker
      scenarios={scenarios}
      currentId={activeScenarioId}
      onSelect={(id) => navigate(`/roadmap-tool/scenarios/${id}`)}
      onAddScenario={() => {
        setAddScenarioError(null)
        setShowAddScenario(true)
      }}
      onMakeDefault={(id) => makeDefaultMutation.mutate(id)}
      onDelete={(id) => deleteScenarioMutation.mutate(id)}
    />
  )}
  {activeScenarioId != null && (
    <Popover
      side="bottom"
      portal
      trigger={({ onClick, ref }) => (
        <button
          ref={ref as React.RefObject<HTMLButtonElement>}
          type="button"
          onClick={onClick}
          aria-label="How the roadmap is calculated"
          title="How the roadmap is calculated"
          className="w-7 h-7 inline-flex items-center justify-center rounded-md text-ink-faint hover:text-ink hover:bg-surface-2 transition-colors"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        </button>
      )}
    >
      <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
        <p className="text-sm font-semibold text-ink">How the Roadmap Is Calculated</p>
        <p>
          The roadmap turns your cards, spending, and time horizon into the
          rewards, credits, fees, and Effective Annual Fee shown in the
          summary and timeline.
        </p>
        <div>
          <p className="text-ink-muted font-medium mb-1">How spend is assigned</p>
          <p>
            Each dollar of spend goes to the card that earns the most on
            it — no double-counting across cards. If two cards tie, the
            dollars are split evenly.
          </p>
        </div>
        <div>
          <p className="text-ink-muted font-medium mb-1">Time periods</p>
          <p>
            Cards only count during the periods they're active. When cards
            have start or close dates, the projection is split into chunks
            at every card open, close, sign-up-bonus earn, and cap reset,
            and each chunk uses only the cards active then.
          </p>
        </div>
        <div>
          <p className="text-ink-muted font-medium mb-1">Sign-up bonuses</p>
          <p>
            Sign-up bonus minimums are tracked against their deadlines,
            and priority spend is steered to cards with an active offer.
            The lost value from diverting that spend away from your
            best-earning card is deducted.
          </p>
        </div>
        <div>
          <p className="text-ink-muted font-medium mb-1">Fees, credits, and perks</p>
          <p>
            Annual fees, statement credits, first-year fee waivers, and
            one-time perks all get netted in. One-time perks are spread
            evenly across the projection years.
          </p>
        </div>
        <div>
          <p className="text-ink-muted font-medium mb-1">Foreign spend and point upgrades</p>
          <p>
            Foreign-transaction rules split eligible categories into
            domestic and foreign portions, favoring no-fee Visa/Mastercard
            cards abroad. Point-upgrade pairings (e.g. Freedom + Sapphire)
            boost the value of cards whose points become worth more when
            paired with a premium card in the wallet.
          </p>
        </div>
        <p className="text-ink-faint">
          For more detail on any of the numbers, click the ⓘ next to the
          stat you're curious about.
        </p>
      </div>
    </Popover>
  )}
  <div className="flex-1" />
  {activeScenarioId != null && (
    <Button
      variant={
        resultsMutation.isPending
          ? 'primary'
          : isStale
          ? 'warn'
          : 'primary'
      }
      size="sm"
      loading={resultsMutation.isPending}
      disabled={resultsMutation.isPending || !needsCalculate}
      onClick={calculateNow}
      aria-live="polite"
      title={
        isStale
          ? 'Results are out of date — click to recalculate'
          : needsInitialCalc
          ? 'Click to calculate your scenario'
          : 'Results are up to date'
      }
    >
      {resultsMutation.isPending
        ? 'Calculating…'
        : needsCalculate
        ? isStale
          ? 'Recalculate'
          : 'Calculate'
        : 'Up to Date'}
    </Button>
  )}
</header>
```

Key changes vs. current:
- Page title `<Heading level={3}>Roadmap Tool</Heading>` → `<h1 className="text-base font-bold text-ink tracking-tight">Roadmap</h1>` (smaller, tighter, Inter weight matching the navbar).
- Help button moves from right-of-Calculate to left-of-Calculate spacer (left side of the header).
- Help button visual: drops the `Button variant="icon" tone="info"` for a smaller 28×28 icon-button consistent with the navbar's ThemeToggle / icon-button rhythm.
- Help button SVG sizes from 18 → 15.
- Layout: `items-start` → `items-center`, removes the inner `<div className="min-w-0 flex items-center gap-3">` and `<div className="shrink-0 flex items-center gap-2">` — flatter row.
- Calculate button content stays exactly the same (variant logic, loading, disabled, aria-live, title, label resolution).
- Drop the `<Heading>` import below if it becomes unused (verify after Step 2).

- [ ] **Step 2: Drop the `Heading` import if unused**

The previous header was the only `Heading` usage in `index.tsx`. After Step 1, search the file for any remaining `<Heading` JSX. If none, remove the import:

```tsx
import { Heading } from '../../components/ui/Heading'
```

If `Heading` is still used elsewhere in the file (search before deleting), leave the import.

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA** — skip; controller will do this.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RoadmapTool/index.tsx
git commit -m "RoadmapTool: flat page header with wordmark + scenario picker + help button"
```

---

## Task 2: Replace `WalletSummaryStats` with hero stats + calc-inputs strip

Rewrite the file from a 4-panel strip into two stacked surfaces:
1. **Hero stats** (top): three soft white cards using the foundation `Stat` primitive with `info` slot for inline Popover triggers — Effective Annual Fee, Annual Fees, Annual Point Income.
2. **Calc-inputs strip** (below hero): a quieter single white card with horizontal layout — Time horizon slider + value · vertical hairline divider · Sign-up bonuses segmented toggle.

The legend that previously sat at the right of the stats strip is **dropped here** — Plan 4b adds it back inside the Timeline view's local toolbar.

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/summary/WalletSummaryStats.tsx`

- [ ] **Step 1: Replace the file's contents**

Replace the entire contents of `frontend/src/pages/RoadmapTool/components/summary/WalletSummaryStats.tsx` with:

```tsx
import { useMemo, type ReactNode } from 'react'
import type { WalletResult } from '../../../../api/client'
import { formatMoney, formatPointsExact } from '../../../../utils/format'
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
  const selectedCount = result?.card_results.filter((c) => c.selected).length ?? 0

  const durationTicks: Array<{ months: number; num: string; unit: string }> = [
    { months: 6, num: '0.5', unit: 'Y' },
    { months: 12, num: '1', unit: 'Y' },
    { months: 18, num: '1.5', unit: 'Y' },
    { months: 24, num: '2', unit: 'Y' },
    { months: 30, num: '2.5', unit: 'Y' },
    { months: 36, num: '3', unit: 'Y' },
  ]

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
                <Money value={totalEffectiveAF} feature tone="auto" />
              ) : (
                <span className="text-2xl font-bold text-ink-faint tnum-mono">—</span>
              )
            }
            caption={
              !hasStats && hasNeverCalculated
                ? 'Click Calculate to see your value'
                : `across ${selectedCount || 0} selected card${selectedCount === 1 ? '' : 's'}`
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
                <Money value={totalAnnualFees} feature tone="neutral" />
              ) : (
                <span className="text-2xl font-bold text-ink-faint tnum-mono">—</span>
              )
            }
            caption="recurring annual cost"
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
                <Money value={totalAnnualPoints} feature tone="pos" />
              ) : (
                <span className="text-2xl font-bold text-ink-faint tnum-mono">—</span>
              )
            }
            caption="redeemed value"
          />
        </div>
      </div>

      {/* Calc-inputs strip */}
      <div className="bg-surface border border-divider rounded-xl shadow-card px-4 py-3 flex items-center gap-5 flex-wrap">
        {/* Time horizon slider */}
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

        {/* Vertical divider */}
        <div className="w-px h-7 bg-divider shrink-0 hidden md:block" />

        {/* SUBs segmented toggle */}
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
            className="inline-flex bg-surface-2 rounded-md p-0.5 text-xs font-medium"
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

        {/* Tick row beneath the slider — visible only on the slider's column */}
        <div className="basis-full hidden md:flex items-center gap-3">
          <div style={{ width: 'calc(180px + 0.375rem)' }} className="shrink-0" />
          <div className="flex-1 relative h-3">
            {durationTicks.map((t) => {
              const pct = ((t.months - 6) / 30) * 100
              return (
                <span
                  key={`${t.num}${t.unit}`}
                  className="absolute text-[10px] text-ink-faint -translate-x-1/2"
                  style={{ left: `${pct}%` }}
                >
                  <span className="tnum-mono">{t.num}</span>
                  {t.unit}
                </span>
              )
            })}
          </div>
        </div>
      </div>
    </div>
  )
}

// formatPointsExact is intentionally re-exported in case downstream Plan 4b/4c
// surfaces want to share the same utility while this file is in flux.
export { formatPointsExact, formatMoney }
```

Key changes vs. current:
- File rewritten from ~548 lines to ~280 lines (removes the 4-panel layout, the legend block, and `Eyebrow`-based labels in favor of `Stat info=...` from Plan 1).
- Drops the `roadmap` prop (was used only for the legend; legend moves to Plan 4b).
- Drops the `formatPointsExact` import-and-not-use leftover.
- Hero stats use the foundation `Stat` primitive with the new `info` slot for inline Popover triggers.
- Calc-inputs strip: slider gets a typographic label-with-info-button on the left + value-readout on the right; SUBs toggle uses a soft-dashboard segmented control (gray track, white pill for active).
- Stale styling: the parent `<div>` gets `opacity-60` when results are stale (matches the previous behavior, simpler implementation).

- [ ] **Step 2: Update the consumer in `index.tsx`**

In `frontend/src/pages/RoadmapTool/index.tsx`, find where `WalletSummaryStats` is rendered (around lines 967–999). The component still accepts the same props **except** `roadmap` is no longer needed. Remove the `roadmap` prop from the JSX:

Find:
```tsx
<WalletSummaryStats
  result={result?.wallet ?? null}
  roadmap={roadmap ?? null}
  isCalculating={resultsMutation.isPending}
  ...
/>
```

Replace with:
```tsx
<WalletSummaryStats
  result={result?.wallet ?? null}
  isCalculating={resultsMutation.isPending}
  isStale={isStale}
  hasNeverCalculated={hasNeverCalculated}
  durationYears={durationYears}
  durationMonths={durationMonths}
  onDurationChange={(y, m) => {
    setDurationYears(y)
    setDurationMonths(m)
    setInSigDirty(true)
  }}
  includeSubs={includeSubs}
  onIncludeSubsChange={(v) => {
    setIncludeSubs(v)
    if (activeScenarioId != null) {
      updateScenarioMutation.mutate({
        scenarioId: activeScenarioId,
        include_subs: v,
      })
    }
  }}
  resultsError={
    resultsMutation.isError
      ? resultsMutation.error instanceof Error
        ? resultsMutation.error
        : new Error(String(resultsMutation.error))
      : null
  }
/>
```

(Drops only the `roadmap={roadmap ?? null}` line.)

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA** — skip; controller will do this.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/summary/WalletSummaryStats.tsx frontend/src/pages/RoadmapTool/index.tsx
git commit -m "RoadmapTool/summary: hero stats trio + calc-inputs strip, drop legend"
```

---

## Task 3: Replace vertical binder-tabs with horizontal `Tabs`

The current binder-tabs spine (lines 1000–1045 of `index.tsx`) is a vertical column of icon-only buttons on the left of the content panel. Replace it with the foundation `Tabs` primitive (horizontal underline) above the content, with a `<n>` count badge on the Timeline tab.

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/index.tsx`

- [ ] **Step 1: Add the `Tabs` import**

At the top of `index.tsx`, near the existing `import { Button } from '../../components/ui/Button'`, add:

```tsx
import { Tabs } from '../../components/ui/Tabs'
```

- [ ] **Step 2: Replace the binder-tabs + content layout**

Find the block starting with `<div className="flex flex-1 min-h-0 min-w-0 items-stretch">` (around line 1000) — this contains the binder-tabs column and the content panel. Replace the entire block (from that opening `<div>` through its closing `</div>` two lines after `</div>` for the inner content panel) with:

```tsx
<div className="flex flex-col flex-1 min-h-0 min-w-0">
  <Tabs
    items={[
      {
        id: 'timeline' as const,
        label: (
          <>
            Timeline
            {result?.wallet && (
              <span className="ml-1.5 text-[10.5px] font-medium bg-surface-2 text-ink-faint px-1.5 py-0.5 rounded-full tnum-mono">
                {result.wallet.card_results.filter((c) => c.selected).length}
              </span>
            )}
          </>
        ),
      },
      { id: 'spend' as const, label: 'Spend' },
    ]}
    active={mainView}
    onChange={(id) => setMainView(id as 'timeline' | 'spend')}
    className="mb-3 shrink-0"
  />

  <div className="flex-1 min-w-0 min-h-0">
    {mainView === 'timeline' ? (
      <WalletTimelineChart
        scenarioId={activeScenarioId}
        walletCards={resolvedCards}
        result={result?.wallet ?? null}
        roadmap={roadmap}
        durationYears={durationYears}
        durationMonths={durationMonths}
        isUpdating={
          updateFutureCardMutation.isPending ||
          upsertOverlayMutation.isPending
        }
        isStale={isStale}
        includeSubs={includeSubs}
        onToggleEnabled={(instanceId, enabled) => {
          toggleCardEnabled(instanceId, enabled)
        }}
        onEditCard={(wc) => {
          if (wc.is_future) {
            setWalletCardModal({ mode: 'edit-future', resolved: wc })
          } else {
            setWalletCardModal({ mode: 'edit-overlay', resolved: wc })
          }
        }}
        onAddCard={() => setWalletCardModal({ mode: 'add-future' })}
      />
    ) : (
      <SpendPanel
        selectedCards={result?.wallet.card_results.filter((c) => c.selected) ?? []}
        walletCards={resolvedCards}
        categoryPriorities={categoryPriorities ?? []}
        totalYears={Math.max(durationYears + durationMonths / 12, 1 / 12)}
        isStale={isStale}
      />
    )}
  </div>
</div>
```

Key changes:
- Outer `<div>` switches from `flex` (row) to `flex flex-col` (column) so tabs sit above the content.
- Vertical binder-tabs column (lines 1002–1045 of current) deleted — replaced by the `Tabs` primitive above the content.
- `Tabs` `items` includes a count badge for Timeline rendered as JSX inside the `label` ReactNode.
- `WalletTimelineChart` and `SpendPanel` props are unchanged — same data plumbing.

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA** — skip; controller will do this.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RoadmapTool/index.tsx
git commit -m "RoadmapTool: horizontal Tabs primitive replaces binder-tab spine"
```

---

## Task 4: Final visual QA pass

End-to-end Roadmap Tool page-shell QA in light + dark before merge. The Timeline view chrome itself is still the **old** design (Plan 4b restyles the rest); confirm the new shell wraps it cleanly.

**Files:**
- (Verify only.)

- [ ] **Step 1: Run lint**

Run: `cd frontend && npm run lint`
Expected: same 3 pre-existing findings (`Button/index.tsx:27`, `CategoryWeightEditor.tsx:39`, `RoadmapTool/index.tsx:737`). NO new findings.

If `RoadmapTool/index.tsx:737`'s warning has shifted to a different line because of this plan's edits, that's fine — it's pre-existing logic and out of scope.

- [ ] **Step 2: Production build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Walk through the page in light mode**

Sign in. Navigate to `/roadmap-tool` (auto-resolves to default scenario). Confirm:

- **Page header:** flat row — `Roadmap` wordmark in dark ink (Inter Bold), Scenario picker pill, small 28×28 help button on the left. Right side: Calculate button (or `Up to Date` / `Recalculate`).
- **Hero stats trio:** three soft white shadow-cards (with the new `border border-divider` from Plan 3's retroactive update), each with the foundation `Stat` primitive: eyebrow label + inline `i` info button + value (large) + 11px caption. Click each `i` — the same Popover content as before opens. EAF tone is auto (negative = pos green, positive = neg red); Annual Fees is neutral; Annual Point Income is pos green.
- **Calc-inputs strip:** quieter single-row card below hero. Time horizon slider with eyebrow label + info button + slider + value readout (`1.5y`, `2y 6mo`, etc.); vertical hairline divider; SUBs Include/Exclude segmented control.
- **Tabs:** horizontal `Timeline N · Spend` underline tabs above the content area. Timeline shows a count badge (the number of selected cards). Active tab uses accent underline.
- **Stale state:** edit any input that affects the calc (e.g. drag the slider). The hero + calc-inputs surfaces dim to 60% opacity. Calculate button switches to "Recalculate" warn tone. Run Calculate — opacity returns to full, button returns to "Up to Date".
- **Empty states:** if a fresh wallet has no cards, the "Add cards in Profile" empty state renders (handled in `index.tsx`, untouched). If a calc has never run, hero values show dashed `—` placeholders + "Click Calculate to see your value" caption.

- [ ] **Step 4: Walk through dark mode**

Toggle theme. Re-walk the same checklist. The hero stat surfaces should still be readable; accent crimson visible; slider thumb readable; SUBs toggle background (surface-2) contrasts against the dark page.

- [ ] **Step 5: Commit a final QA marker**

```bash
git commit --allow-empty -m "RoadmapTool/page-shell: visual QA pass complete (light + dark, all states)"
```

---

## Plan complete

After Task 4, the Roadmap Tool's top-level page shell is shipped. The Timeline tab content (currency groups, CardRow, axis), Spend tab table, ScenarioPicker, currency / portal popovers, and 3 small modals are still in their pre-redesign state — Plan 4b handles them. The WalletCardModal (4-tab editor) is Plan 4c.
