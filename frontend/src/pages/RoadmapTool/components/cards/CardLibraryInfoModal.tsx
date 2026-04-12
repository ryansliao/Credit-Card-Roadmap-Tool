import { useEffect, useId, useState } from 'react'
import { adminApi, type Card, type CardMultiplierGroup, type CardRotatingHistoryRow } from '../../../../api/client'
import { ModalBackdrop } from '../../../../components/ModalBackdrop'
import { useCardLibrary } from '../../hooks/useCardLibrary'

function earnSummary(c: Card) {
  return (
    [
      c.multipliers.length > 0 && `${c.multipliers.length} listed rates`,
      c.multiplier_groups.length > 0 &&
        `${c.multiplier_groups.length} rate group${c.multiplier_groups.length === 1 ? '' : 's'}`,
    ]
      .filter(Boolean)
      .join(' · ') || '—'
  )
}

function capPeriodLabel(months: number | null | undefined): string {
  if (!months) return ''
  if (months === 1) return 'monthly'
  if (months === 3) return 'quarterly'
  if (months === 6) return 'semi-annually'
  if (months === 12) return 'annually'
  return `every ${months} months`
}

function RotatingGroupBlock({
  group,
  history,
}: {
  group: CardMultiplierGroup
  history: CardRotatingHistoryRow[]
}) {
  const [showHistory, setShowHistory] = useState(false)
  const weights = (group.rotation_weights ?? []).slice().sort((a, b) => b.weight - a.weight)
  const cap = group.cap_per_billing_cycle
  const period = capPeriodLabel(group.cap_period_months)
  const distinctQuarters = new Set(history.map((h) => `${h.year}Q${h.quarter}`)).size

  // Group history rows by (year, quarter) for the collapsible list.
  const grouped: Record<string, { year: number; quarter: number; categories: string[] }> = {}
  for (const row of history) {
    const key = `${row.year}Q${row.quarter}`
    if (!grouped[key]) {
      grouped[key] = { year: row.year, quarter: row.quarter, categories: [] }
    }
    grouped[key].categories.push(row.category_name)
  }
  const orderedQuarters = Object.values(grouped).sort((a, b) => {
    if (a.year !== b.year) return b.year - a.year
    return b.quarter - a.quarter
  })

  return (
    <div className="rounded-lg border border-indigo-700/60 bg-indigo-950/30 p-3">
      <div className="flex items-center justify-between gap-2 mb-2">
        <p className="text-[11px] font-semibold uppercase tracking-wide text-indigo-300">
          Rotating bonus group
        </p>
        <span className="text-[10px] font-semibold rounded-full bg-indigo-700/40 text-indigo-200 px-2 py-0.5">
          {group.multiplier}× · ${cap?.toLocaleString() ?? '—'} {period}
        </span>
      </div>
      {weights.length === 0 ? (
        <p className="text-xs text-slate-400 italic">
          No history loaded — using uniform weights for every category in the group.
        </p>
      ) : (
        <>
          <p className="text-[11px] text-slate-400 mb-2">
            Activation probabilities inferred from {distinctQuarters} historical{' '}
            {distinctQuarters === 1 ? 'quarter' : 'quarters'}. Each category's expected bonus cap is{' '}
            <span className="text-indigo-300 font-semibold">cap × p</span>.
          </p>
          <table className="w-full text-xs">
            <thead>
              <tr className="text-slate-500 text-[10px] uppercase tracking-wide">
                <th className="text-left font-medium pb-1">Category</th>
                <th className="text-right font-medium pb-1">p</th>
                <th className="text-right font-medium pb-1">Expected cap</th>
              </tr>
            </thead>
            <tbody>
              {weights.map((w) => (
                <tr key={w.spend_category_id} className="border-t border-slate-700/40">
                  <td className="text-slate-200 py-1">{w.name}</td>
                  <td className="text-right text-slate-300 tabular-nums py-1">
                    {(w.weight * 100).toFixed(0)}%
                  </td>
                  <td className="text-right text-slate-300 tabular-nums py-1">
                    {cap != null
                      ? `$${Math.round(cap * w.weight).toLocaleString()}`
                      : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
      {orderedQuarters.length > 0 && (
        <div className="mt-3">
          <button
            type="button"
            onClick={() => setShowHistory((s) => !s)}
            className="text-[11px] font-medium text-indigo-300 hover:text-indigo-200"
          >
            {showHistory ? 'Hide' : 'Show'} history ({orderedQuarters.length} quarters)
          </button>
          {showHistory && (
            <ul className="mt-2 space-y-0.5 text-[11px] text-slate-300 max-h-48 overflow-y-auto">
              {orderedQuarters.map((q) => (
                <li key={`${q.year}Q${q.quarter}`} className="flex gap-2">
                  <span className="text-slate-500 tabular-nums w-12">
                    {q.year}Q{q.quarter}
                  </span>
                  <span>{q.categories.join(', ')}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </div>
  )
}

export function CardLibraryInfoModal({
  cardId,
  onClose,
}: {
  cardId: number
  onClose: () => void
}) {
  const titleId = useId()
  const { data: cards, isLoading } = useCardLibrary()
  const card = cards?.find((c) => c.id === cardId)
  const rotatingGroups = (card?.multiplier_groups ?? []).filter((g) => g.is_rotating)
  const [history, setHistory] = useState<CardRotatingHistoryRow[]>([])

  useEffect(() => {
    if (!card || rotatingGroups.length === 0) {
      setHistory([])
      return
    }
    let cancelled = false
    adminApi
      .listCardRotatingHistory(card.id)
      .then((rows) => {
        if (!cancelled) setHistory(rows)
      })
      .catch(() => {
        if (!cancelled) setHistory([])
      })
    return () => {
      cancelled = true
    }
  }, [card, rotatingGroups.length])

  return (
    <ModalBackdrop onClose={onClose} zIndex="z-[55]" className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-full max-w-md shadow-xl max-h-[90vh] overflow-y-auto">
        <div className="flex items-start justify-between gap-3 mb-4">
          <h2 id={titleId} className="text-lg font-semibold text-white pr-2">
            {isLoading ? 'Card details' : card?.name ?? 'Card'}
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="shrink-0 text-slate-400 hover:text-white text-sm px-2 py-1 rounded-lg hover:bg-slate-700"
          >
            Close
          </button>
        </div>

        {isLoading && (
          <p className="text-sm text-slate-400 py-8 text-center">Loading card…</p>
        )}

        {!isLoading && !card && (
          <p className="text-sm text-amber-400 py-4">Card not found.</p>
        )}

        {card && (
          <div className="space-y-3">
            <div className="rounded-lg border border-slate-600/80 bg-slate-900/50 p-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-slate-500 mb-2">
                Reference
              </p>
              <dl className="space-y-1.5 text-xs">
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Issuer</dt>
                  <dd className="text-slate-200 text-right">{card.issuer.name}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Co-brand</dt>
                  <dd className="text-slate-200 text-right">{card.co_brand?.name ?? '—'}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Currency</dt>
                  <dd className="text-slate-200 text-right">{card.currency_obj.name}</dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Network</dt>
                  <dd className="text-slate-200 text-right">
                    {card.network_tier?.name || '—'}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Product</dt>
                  <dd className="text-slate-200 text-right">
                    {card.business ? 'Business' : 'Personal'}
                  </dd>
                </div>
                <div className="flex justify-between gap-3">
                  <dt className="text-slate-500">Earning structure</dt>
                  <dd className="text-slate-200 text-right">{earnSummary(card)}</dd>
                </div>
              </dl>
            </div>
            {rotatingGroups.map((g) => (
              <RotatingGroupBlock key={g.id} group={g} history={history} />
            ))}
          </div>
        )}
    </ModalBackdrop>
  )
}
