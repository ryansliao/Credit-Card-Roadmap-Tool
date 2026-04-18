import { Link } from 'react-router-dom'
import { useAuth } from '../auth/useAuth'

export default function Home() {
  const { isAuthenticated } = useAuth()

  return (
    <div className="flex-1 flex flex-col items-center justify-center text-center px-6">
      <h1 className="text-4xl sm:text-5xl font-bold text-white mb-4 tracking-tight">
        CardSolver
      </h1>
      <p className="text-slate-400 text-lg sm:text-xl max-w-2xl mb-10 leading-relaxed">
        Build your ideal credit card wallet. Compare sign-up bonuses, project
        multi-year value, and track your roadmap to maximizing rewards.
      </p>

      {isAuthenticated && (
        <Link
          to="/roadmap-tool"
          className="px-6 py-3 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold rounded-lg transition-colors"
        >
          Go to Roadmap Tool
        </Link>
      )}
      {!isAuthenticated && (
        <p className="text-slate-500 text-sm">Sign in from the navbar to get started.</p>
      )}

      <div className="mt-16 grid grid-cols-1 sm:grid-cols-3 gap-8 max-w-3xl w-full">
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
          <h3 className="text-white font-semibold mb-2">Wallet Builder</h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            Add cards with open dates, fees, and SUB details to model your real or planned wallet.
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
          <h3 className="text-white font-semibold mb-2">EV Projections</h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            See expected annual value across points, credits, and bonuses over a 1-5 year horizon.
          </p>
        </div>
        <div className="bg-slate-900 border border-slate-700 rounded-xl p-6">
          <h3 className="text-white font-semibold mb-2">Roadmap Tracking</h3>
          <p className="text-slate-400 text-sm leading-relaxed">
            Track 5/24 status, SUB progress, and issuer application rule alerts at a glance.
          </p>
        </div>
      </div>
    </div>
  )
}
