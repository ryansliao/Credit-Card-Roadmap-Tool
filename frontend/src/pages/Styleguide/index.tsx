import { ThemeToggle } from '../../components/ui/ThemeToggle'

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
      </main>
    </div>
  )
}
