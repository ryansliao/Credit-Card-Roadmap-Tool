import { ThemeToggle } from '../../components/ui/ThemeToggle'
import { Heading } from '../../components/ui/Heading'
import { Eyebrow } from '../../components/ui/Eyebrow'
import { Money } from '../../components/ui/Money'
import { Points } from '../../components/ui/Points'
import { Stat } from '../../components/ui/Stat'

/**
 * Internal styleguide route — gated by VITE_SHOW_STYLEGUIDE=1.
 * Each primitive section gets registered here as it lands. The id-anchored
 * sections mean you can deep-link to a primitive: /styleguide#modal.
 */
export default function Styleguide() {
  return (
    <div className="min-h-dvh bg-page text-ink">
      <header className="border-b border-divider px-8 py-6 flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Internal</p>
          <h1 className="font-display text-3xl" style={{ fontVariationSettings: '"opsz" 96' }}>
            Styleguide
          </h1>
        </div>
        <ThemeToggle />
      </header>
      <main className="px-8 py-10 max-w-5xl mx-auto space-y-16">
        <section id="overview">
          <p className="text-ink-muted">
            This page renders every design-system primitive in every variant +
            state, in both light and dark. Each primitive section gets added as
            it ships (Phase 1+).
          </p>
        </section>
        <section id="heading" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Heading</p>
          <Heading level={1}>Display — Net EV per year</Heading>
          <Heading level={2}>Headline — Wallet · Default Scenario</Heading>
          <Heading level={3}>Title — Sapphire Reserve</Heading>
          <Heading level={4}>Subtitle — Annual fee waived</Heading>
        </section>
        <section id="eyebrow" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Eyebrow</p>
          <Eyebrow>Net EV / yr</Eyebrow>
          <Eyebrow accent>With accent rule</Eyebrow>
        </section>
        <section id="money" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Money</p>
          <div className="space-y-2">
            <div>Inline mono: <Money value={1284.50} /></div>
            <div>Inline non-mono: <Money value={1284} mono={false} /></div>
            <div>Tone auto positive: <Money value={842} tone="auto" /></div>
            <div>Tone auto negative: <Money value={-795} tone="auto" /></div>
            <div>Precision 0: <Money value={1284.5} precision={0} /></div>
            <div>Precision 2: <Money value={1284} precision={2} /></div>
          </div>
          <div>Feature size:</div>
          <Money value={3418} feature />
        </section>
        <section id="points" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Points</p>
          <div className="space-y-2">
            <div>Compact: <Points value={125000} /></div>
            <div>Exact: <Points value={125000} exact /></div>
            <div>With unit: <Points value={125000} unit="UR" /></div>
            <div>Feature: <Points value={125000} feature unit="UR" /></div>
          </div>
        </section>
        <section id="stat" className="space-y-6">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Stat</p>
          <Stat
            label="Net EV / yr"
            value={<Money value={3418} feature />}
            caption="over 7 years, default scenario"
            accent
          />
          <div className="flex justify-between border-t border-divider pt-4">
            <Stat label="Earn" value={<Money value={2134} />} />
            <Stat label="Credits" value={<Money value={700} />} />
            <Stat label="Annual fee" value={<Money value={-795} tone="auto" />} align="right" />
          </div>
        </section>
      </main>
    </div>
  )
}
