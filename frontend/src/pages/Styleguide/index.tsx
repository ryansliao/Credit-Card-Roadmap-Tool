import { ThemeToggle } from '../../components/ui/ThemeToggle'
import { Heading } from '../../components/ui/Heading'
import { Eyebrow } from '../../components/ui/Eyebrow'

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
      </main>
    </div>
  )
}
