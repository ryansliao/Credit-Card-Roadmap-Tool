import type { WalletResult } from '../api/client'

function money(n: number) {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

function pts(n: number) {
  if (n === 0) return null
  return n >= 1000 ? `${(n / 1000).toFixed(1)}k` : n.toFixed(0)
}

interface Props {
  result: WalletResult
}

export default function WalletSummary({ result }: Props) {
  const currencies = Object.entries(result.currency_pts).filter(([, v]) => v > 0)

  const selected = result.card_results.filter((c) => c.selected)

  return (
    <div className="space-y-4">
      {/* Top-level totals */}
      <div className="grid grid-cols-2 gap-3">
        <div className="bg-indigo-900/40 border border-indigo-700 rounded-xl p-4 text-center">
          <p className="text-xs text-indigo-300 uppercase tracking-wider">Annual EV</p>
          <p className="text-2xl font-bold text-indigo-100 mt-1">{money(result.total_annual_ev)}</p>
        </div>
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 text-center">
          <p className="text-xs text-slate-400 uppercase tracking-wider">Total Points/yr</p>
          <p className="text-2xl font-bold text-white mt-1">
            {(result.total_annual_pts / 1000).toFixed(1)}k
          </p>
        </div>
      </div>

      {/* Currency breakdown */}
      {currencies.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Points by Currency</p>
          <div className="grid grid-cols-2 gap-2">
            {currencies.map(([name, amount]) => (
              <div key={name} className="bg-slate-800 rounded-lg px-3 py-2 flex justify-between">
                <span className="text-xs text-slate-400">{name}</span>
                <span className="text-xs font-medium text-white">
                  {pts(amount)}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Per-card breakdown */}
      {selected.length > 0 && (
        <div>
          <p className="text-xs text-slate-400 uppercase tracking-wider mb-2">Per Card</p>
          <div className="space-y-1">
            {selected
              .sort((a, b) => b.annual_ev - a.annual_ev)
              .map((cr) => (
                <div
                  key={cr.card_id}
                  className="flex items-center justify-between bg-slate-800 rounded-lg px-3 py-2"
                >
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-medium truncate">{cr.card_name}</p>
                    <p className="text-xs text-slate-400">
                      {(cr.annual_point_earn / 1000).toFixed(1)}k pts · {money(cr.credit_valuation)}{' '}
                      credits
                      {cr.sub_opp_cost_dollars > 0 && (
                        <span className="text-amber-400/90 ml-1">
                          · SUB opp cost {money(cr.sub_opp_cost_dollars)}
                        </span>
                      )}
                    </p>
                  </div>
                  <div className="text-right ml-3">
                    <p
                      className={`text-sm font-bold ${cr.annual_ev >= 0 ? 'text-emerald-400' : 'text-red-400'}`}
                    >
                      {money(cr.annual_ev)}
                    </p>
                    <p className="text-xs text-slate-500">-{money(cr.annual_fee)} fee</p>
                  </div>
                </div>
              ))}
          </div>
        </div>
      )}
    </div>
  )
}
