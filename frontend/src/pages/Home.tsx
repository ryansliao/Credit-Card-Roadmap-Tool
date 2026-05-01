import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'
import { walletApi, walletSpendApi } from '../api/client'
import { queryKeys } from '../lib/queryKeys'

type StepStatus = 'pending' | 'current' | 'complete' | 'preview'

export default function Home() {
  const { isAuthenticated } = useAuth()

  const { data: wallet, isFetched: walletFetched } = useQuery({
    queryKey: queryKeys.myWalletWithScenarios(),
    queryFn: () => walletApi.get(),
    enabled: isAuthenticated,
  })

  const { data: spendItems, isFetched: spendFetched } = useQuery({
    queryKey: queryKeys.walletSpendItemsSingular(),
    queryFn: () => walletSpendApi.list(),
    enabled: isAuthenticated && wallet != null,
  })

  const hasCards = (wallet?.card_instances?.length ?? 0) > 0
  const hasSpend = (spendItems?.length ?? 0) > 0
  const stateKnown =
    !isAuthenticated || (walletFetched && (wallet == null || spendFetched))

  const currentStep: 1 | 2 | 3 | null = !isAuthenticated
    ? null
    : !hasCards
    ? 1
    : !hasSpend
    ? 2
    : 3

  const heroCta = buildHeroCta(isAuthenticated, stateKnown, currentStep)

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-6xl mx-auto px-4 py-12 sm:py-20">
        <section className="text-center mb-24">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-2 text-ink-faint text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-accent" />
            Credit card wallet optimizer
          </div>
          <h1
            className="text-ink mb-6 tracking-tight leading-[1.05]"
            style={{ fontSize: 'clamp(40px, 7vw, 56px)', fontWeight: 700, letterSpacing: '-0.02em' }}
          >
            Stop guessing which cards
            <br className="hidden sm:block" />
            <span className="text-accent"> actually pay off.</span>
          </h1>
          <p className="text-ink-muted text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
            Model your real or planned wallet, enter your annual spend, and get a
            segment-aware projection of rewards, credits, and sign-up bonuses —
            with each category allocated optimally across every card.
          </p>
          {heroCta ? (
            <Link
              to={heroCta.to}
              className="inline-flex items-center gap-2 px-6 py-3 bg-accent text-on-accent font-semibold text-sm rounded-lg shadow-card hover:opacity-90 transition-opacity"
            >
              {heroCta.label}
            </Link>
          ) : (
            <p className="text-ink-faint text-sm">Sign in from the navbar to get started.</p>
          )}
          {isAuthenticated && currentStep === 1 && stateKnown && (
            <p className="text-ink-faint text-sm mt-4">Takes about two minutes to set up.</p>
          )}
        </section>

        <section className="mb-20">
          <div className="text-center mb-10">
            <p className="text-[11px] uppercase tracking-[0.18em] text-ink-faint font-semibold mb-3">
              {isAuthenticated ? 'Your setup' : 'How it works'}
            </p>
            <h2
              className="text-ink tracking-tight"
              style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em' }}
            >
              {isAuthenticated && currentStep !== 3
                ? "Let's get your wallet ready."
                : 'Three steps, one number.'}
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
            <StepCard
              num={1}
              title="Add cards"
              body="Build your wallet from the card library. Set open dates, acquisition type, SUB overrides, and future applications you're considering."
              status={stepStatus(currentStep, 1)}
              cta={currentStep === 1 ? { label: 'Add cards →', to: '/profile' } : undefined}
            />
            <StepCard
              num={2}
              title="Enter annual spend"
              body="Break out real spend by category. Set your foreign-spend share and tune per-card credit and multiplier overrides."
              status={stepStatus(currentStep, 2)}
              cta={
                currentStep === 2
                  ? { label: 'Enter spend →', to: '/profile?tab=spending' }
                  : undefined
              }
            />
            <StepCard
              num={3}
              title="Chart your roadmap"
              body="Compare expected value per card, add ones you're considering, drop the ones that don't earn their keep, and track SUB deadlines along the way."
              status={stepStatus(currentStep, 3)}
              cta={
                currentStep === 3
                  ? { label: 'Open Roadmap Tool →', to: '/roadmap-tool' }
                  : undefined
              }
            />
          </div>
        </section>

        <section className="mb-20">
          <div className="text-center mb-10">
            <p className="text-[11px] uppercase tracking-[0.18em] text-ink-faint font-semibold mb-3">
              Under the hood
            </p>
            <h2
              className="text-ink tracking-tight"
              style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em' }}
            >
              More than a multiplier lookup.
            </h2>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
            <FeatureCard
              title="Optimal allocation"
              body="An LP solver places each category's spend on the highest-value card, respecting top-N groups, rotating 5% pools, and currency transfers."
            />
            <FeatureCard
              title="Multi-year projections"
              body="Segment-aware math splits your window at every card open, close, and SUB-earn boundary — so year-1 and steady-state are both honest."
            />
            <FeatureCard
              title="SUB tracking"
              body="Projected earn dates from your actual spend rate, with opportunity cost baked into the total. Mark SUBs earned to stop projecting them."
            />
            <FeatureCard
              title="Issuer rules"
              body="5/24 counter, Amex 1/90, Citi 1/8 and 2/65 — warnings surface on the roadmap before you apply, not after."
            />
            <FeatureCard
              title="Foreign spend & currencies"
              body="FTF-aware allocation on foreign-eligible categories, per-wallet CPP overrides, and currency conversions like UR Cash → Chase UR."
            />
            <FeatureCard
              title="Wallet modeling"
              body="Mix owned cards with future applications. Override fees, credits, SUBs, and multipliers per wallet without touching the card library."
            />
          </div>
        </section>

        {isAuthenticated && currentStep === 3 && (
          <section className="mb-20">
            <div className="bg-surface border border-divider rounded-xl shadow-card p-8 text-center">
              <h2 className="text-ink font-semibold text-xl mb-2 tracking-tight">All set.</h2>
              <p className="text-ink-muted text-sm mb-6 max-w-md mx-auto">
                Open the Roadmap Tool to see your wallet's expected value, fees, and sign-up bonus deadlines.
              </p>
              <Link
                to="/roadmap-tool"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-on-accent font-semibold text-sm rounded-lg shadow-card hover:opacity-90 transition-opacity"
              >
                Open Roadmap Tool →
              </Link>
            </div>
          </section>
        )}
        <footer className="border-t border-divider pt-6 pb-4 text-[11px] text-ink-faint text-center">
          <p>
            Wallet projections are estimates only. Cents-per-point values are configurable defaults — adjust to match your redemption habits in the Roadmap Tool.
          </p>
        </footer>
      </div>
    </div>
  )
}

function buildHeroCta(
  isAuthenticated: boolean,
  stateKnown: boolean,
  step: 1 | 2 | 3 | null,
): { label: string; to: string } | null {
  if (!isAuthenticated) return null
  if (!stateKnown) return { label: 'Continue →', to: '/roadmap-tool' }
  if (step === 1) return { label: 'Add your first card →', to: '/profile' }
  if (step === 2) return { label: 'Enter your annual spend →', to: '/profile?tab=spending' }
  return { label: 'Open Roadmap Tool →', to: '/roadmap-tool' }
}

function stepStatus(current: 1 | 2 | 3 | null, step: 1 | 2 | 3): StepStatus {
  if (current == null) return 'preview'
  if (step < current) return 'complete'
  if (step === current) return 'current'
  return 'pending'
}

function FeatureCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="bg-surface border border-divider rounded-xl p-6 shadow-card">
      <h3 className="text-ink font-semibold text-base mb-2">{title}</h3>
      <p className="text-ink-muted text-sm leading-relaxed">{body}</p>
    </div>
  )
}

function StepCard({
  num,
  title,
  body,
  status,
  cta,
}: {
  num: number
  title: string
  body: string
  status: StepStatus
  cta?: { label: string; to: string }
}) {
  const isComplete = status === 'complete'
  const isCurrent = status === 'current'
  const isPending = status === 'pending'

  const containerClass = isCurrent
    ? 'bg-surface border border-accent ring-2 ring-accent shadow-card'
    : isComplete
    ? 'bg-surface-2 border border-divider shadow-card'
    : 'bg-surface border border-divider shadow-card'

  const titleClass = isPending ? 'text-ink-muted' : 'text-ink'
  const bodyClass = isPending ? 'text-ink-faint' : 'text-ink-muted'

  return (
    <div className={`rounded-xl p-6 transition-colors ${containerClass}`}>
      <div className="flex items-center justify-between mb-4">
        <StepBadge num={num} status={status} />
        {isComplete && (
          <span className="text-[11px] font-medium text-pos uppercase tracking-wider">Done</span>
        )}
        {isCurrent && (
          <span className="text-[11px] font-medium text-accent uppercase tracking-wider">Next up</span>
        )}
      </div>
      <h3 className={`text-base font-semibold mb-2 ${titleClass}`}>{title}</h3>
      <p className={`text-sm leading-relaxed ${bodyClass}`}>{body}</p>
      {cta && (
        <Link
          to={cta.to}
          className="inline-block mt-5 text-sm font-medium text-accent hover:opacity-80 transition-opacity"
        >
          {cta.label}
        </Link>
      )}
    </div>
  )
}

function StepBadge({ num, status }: { num: number; status: StepStatus }) {
  if (status === 'complete') {
    return (
      <div className="w-8 h-8 rounded-full bg-pos/10 text-pos flex items-center justify-center">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
    )
  }
  const toneClass =
    status === 'current'
      ? 'bg-accent text-on-accent'
      : status === 'pending'
      ? 'bg-surface-2 text-ink-faint'
      : 'bg-accent/10 text-accent'
  return (
    <div
      className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${toneClass}`}
    >
      {num}
    </div>
  )
}
