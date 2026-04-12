import type { RoadmapRuleStatus } from '../../../../api/client'

interface Props {
  violations: RoadmapRuleStatus[]
  onClose: () => void
}

export function ApplicationRuleWarningModal({ violations, onClose }: Props) {
  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div
        className="bg-slate-900 border border-amber-700/50 rounded-xl p-5 max-w-lg w-full shadow-xl"
        role="alertdialog"
        aria-labelledby="application-rule-warning-title"
        aria-describedby="application-rule-warning-desc"
      >
        <h2
          id="application-rule-warning-title"
          className="text-base font-semibold text-amber-300 mb-1"
        >
          Application rule warning
        </h2>
        <p id="application-rule-warning-desc" className="text-xs text-slate-400 mb-4">
          Adding this card pushed your wallet past at least one issuer application rule.
        </p>
        <div className="space-y-2 max-h-[min(50vh,320px)] overflow-y-auto">
          {violations.map((r) => (
            <div
              key={r.rule_id}
              className="flex items-start gap-3 bg-amber-900/20 border border-amber-700/40 rounded-lg px-3 py-2"
            >
              <span className="text-amber-400 font-bold text-sm shrink-0">{r.rule_name}</span>
              <div className="text-xs text-slate-300 flex-1">
                <span className="text-amber-300 font-medium">{r.issuer_name}: </span>
                {r.description}
                <span className="ml-2 text-amber-400">
                  ({r.current_count}/{r.max_count} in {r.period_days}d)
                </span>
              </div>
            </div>
          ))}
        </div>
        <button
          type="button"
          className="mt-5 w-full bg-slate-700 hover:bg-slate-600 text-white text-sm py-2 rounded-lg"
          onClick={onClose}
        >
          OK
        </button>
      </div>
    </div>
  )
}
