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
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-300 text-xs font-medium mb-6">
            <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
            Credit card wallet optimizer
          </div>
          <h1 className="text-5xl sm:text-6xl font-bold text-white mb-6 tracking-tight leading-[1.05]">
            Stop guessing which cards
            <br className="hidden sm:block" />
            <span className="text-indigo-400"> actually pay off.</span>
          </h1>
          <p className="text-slate-400 text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
            Model your real or planned wallet, enter your annual spend, and get a
            segment-aware projection of rewards, credits, and sign-up bonuses —
            with each category allocated optimally across every card.
          </p>
          {heroCta ? (
            <Link
              to={heroCta.to}
              className="inline-block px-7 py-3.5 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-colors"
            >
              {heroCta.label}
            </Link>
          ) : (
            <p className="text-slate-500 text-sm">Sign in from the navbar to get started.</p>
          )}
          {isAuthenticated && currentStep === 1 && stateKnown && (
            <p className="text-slate-500 text-sm mt-4">Takes about two minutes to set up.</p>
          )}
        </section>

        <section className="mb-24">
          <div className="text-center mb-12">
            <h2 className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">
              {isAuthenticated ? 'Your setup' : 'How it works'}
            </h2>
            <h3 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              {isAuthenticated && currentStep !== 3
                ? "Let's get your wallet ready."
                : 'Three steps, one number.'}
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
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

        <section className="mb-4">
          <div className="text-center mb-12">
            <h2 className="text-xs uppercase tracking-widest text-slate-500 font-semibold mb-3">
              Under the hood
            </h2>
            <h3 className="text-3xl sm:text-4xl font-bold text-white tracking-tight">
              More than a multiplier lookup.
            </h3>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
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
    <div className="bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl p-6 transition-colors">
      <h4 className="text-white font-semibold mb-2">{title}</h4>
      <p className="text-slate-400 text-sm leading-relaxed">{body}</p>
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
    ? 'bg-slate-900 border border-indigo-500/50 ring-1 ring-indigo-500/20'
    : isComplete
    ? 'bg-slate-900/60 border border-slate-800'
    : 'bg-slate-900 border border-slate-800'

  const titleClass = isPending ? 'text-slate-400' : 'text-white'
  const bodyClass = isPending ? 'text-slate-500' : 'text-slate-400'

  return (
    <div className={`rounded-xl p-6 transition-colors ${containerClass}`}>
      <div className="flex items-center justify-between mb-4">
        <StepBadge num={num} status={status} />
        {isComplete && (
          <span className="text-xs font-medium text-emerald-400">Done</span>
        )}
        {isCurrent && (
          <span className="text-xs font-medium text-indigo-300">Next up</span>
        )}
      </div>
      <h4 className={`font-semibold mb-2 ${titleClass}`}>{title}</h4>
      <p className={`text-sm leading-relaxed ${bodyClass}`}>{body}</p>
      {cta && (
        <Link
          to={cta.to}
          className="inline-block mt-5 text-sm font-medium text-indigo-300 hover:text-indigo-200 transition-colors"
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
      <div className="w-8 h-8 rounded-full bg-emerald-500/10 border border-emerald-500/30 text-emerald-300 flex items-center justify-center">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="20 6 9 17 4 12" />
        </svg>
      </div>
    )
  }
  const toneClass =
    status === 'current'
      ? 'bg-indigo-500/15 border-indigo-500/40 text-indigo-200'
      : status === 'pending'
      ? 'bg-slate-800/60 border-slate-700 text-slate-500'
      : 'bg-indigo-500/10 border-indigo-500/30 text-indigo-300'
  return (
    <div
      className={`w-8 h-8 rounded-full border flex items-center justify-center text-sm font-bold ${toneClass}`}
    >
      {num}
    </div>
  )
}
