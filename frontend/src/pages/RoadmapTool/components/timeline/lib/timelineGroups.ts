import type { Card, CardResult, RoadmapResponse } from '../../../../../api/client'
import type { ResolvedCard } from '../../../lib/resolveScenarioCards'
import type { GroupData, SecondaryAnnual } from '../GroupSection'
import { parseDate } from './timelineUtils'

/** Build currency groups from visible cards, enriching each group with
 * aggregated balance + secondary totals. Pure: no React, no hooks. */
export function buildGroupsFromVisibleCards(
  visibleCards: ResolvedCard[],
  cardResultById: Map<number, CardResult>,
  libraryById: Map<number, Card>,
  totalYears: number,
): GroupData[] {
  const byCurrency = new Map<string, GroupData>()
  for (const wc of visibleCards) {
    // Pull cr directly from the last calc's result — don't gate by the
    // live `wc.is_enabled`. The backend only emits CardResults for cards
    // that were enabled *at calc time*, so toggling now must not make cr
    // flip in/out of existence (that would reorder currency groups and
    // change their totals between calcs).
    // CardResult.card_id is the synthetic instance id (= ResolvedCard.id),
    // not the library card_id — see ScenarioResolver.build_compute_inputs.
    const cr = cardResultById.get(wc.id) ?? null
    let name: string
    let currencyId: number | null
    let photoSlug: string | null
    let rewardKind: 'points' | 'cash' | null
    if (cr) {
      name = cr.effective_currency_name
      currencyId = cr.effective_currency_id ?? null
      photoSlug = cr.effective_currency_photo_slug ?? null
      rewardKind = cr.effective_reward_kind ?? 'points'
    } else {
      const lib = libraryById.get(wc.card_id)
      const cur = lib?.currency_obj
      if (cur) {
        name = cur.name
        currencyId = cur.id
        photoSlug = cur.photo_slug ?? null
        rewardKind = cur.reward_kind === 'cash' ? 'cash' : 'points'
      } else {
        // Library not loaded yet or card missing — skip so we never show
        // a stray "Unknown" group.
        continue
      }
    }
    if (!byCurrency.has(name)) {
      byCurrency.set(name, {
        name,
        currencyId,
        photoSlug,
        color: rewardKind === 'cash' ? 'var(--color-pos)' : 'var(--color-info)',
        rewardKind,
        cards: [],
        secondaries: [],
        totalBalance: null,
        balanceCpp: null,
      })
    }
    const g = byCurrency.get(name)!
    // Precompute per-card secondary annual earn so both card rows and the
    // group header can render it without extra lookups.
    //
    // Note: the calculator deliberately zeroes ``secondary_currency_value_dollars``
    // when a card is in Bilt 2.0 "Bilt Cash mode" (to avoid double-counting
    // against the lump-sum annual_bonus). For display we want the true
    // dollar value, so we re-derive it from the library secondary
    // currency's cents_per_point × the net-pts figure.
    // Filter by `cr` presence (i.e. "was included in the last calc"),
    // not live `wc.is_enabled`, so toggling a card doesn't change the
    // group's aggregated secondary-currency totals until recalc.
    let secondary: SecondaryAnnual | null = null
    if (cr && cr.secondary_currency_id && cr.secondary_currency_net_earn !== 0) {
      const lib = libraryById.get(wc.card_id)
      const secObj = lib?.secondary_currency_obj
      const kind: 'points' | 'cash' = secObj?.reward_kind === 'cash' ? 'cash' : 'points'
      const secCpp = secObj?.cents_per_point ?? 1
      const years = cr.card_active_years || totalYears || 1
      const annualUnits = cr.secondary_currency_net_earn / years
      secondary = {
        id: cr.secondary_currency_id,
        name: cr.secondary_currency_name,
        units: annualUnits,
        dollars: (annualUnits * secCpp) / 100,
        rewardKind: kind,
        totalUnits: cr.secondary_currency_net_earn,
        totalDollars: (cr.secondary_currency_net_earn * secCpp) / 100,
      }
    }
    g.cards.push({ wc, cr, secondary })
  }

  for (const g of byCurrency.values()) {
    g.cards.sort((a, b) => {
      const ea = a.cr?.card_effective_annual_fee ?? Number.POSITIVE_INFINITY
      const eb = b.cr?.card_effective_annual_fee ?? Number.POSITIVE_INFINITY
      return ea - eb
    })

    // Aggregate primary-currency balance and secondary totals based on
    // calc results only. Don't gate by live `is_enabled` — the results
    // must stay stable (including currency group order) until the user
    // clicks Calculate again. Cards that weren't enabled at calc time
    // won't have a `cr` anyway.
    let balanceSum = 0
    let balanceCount = 0
    const byId = new Map<number, SecondaryAnnual>()
    for (const entry of g.cards) {
      if (!entry.cr) continue
      balanceSum += entry.cr.total_points
      balanceCount += 1
      const s = entry.secondary
      if (s) {
        const prev = byId.get(s.id) ?? {
          ...s,
          units: 0,
          dollars: 0,
          totalUnits: 0,
          totalDollars: 0,
        }
        prev.units += s.units
        prev.dollars += s.dollars
        prev.totalUnits += s.totalUnits
        prev.totalDollars += s.totalDollars
        byId.set(s.id, prev)
      }
    }
    if (balanceCount > 0) {
      g.totalBalance = balanceSum
      if (g.rewardKind === 'cash') {
        g.balanceCpp = g.cards.find((e) => e.cr != null)?.cr?.cents_per_point ?? null
      }
    }
    g.secondaries = Array.from(byId.values())
  }

  return Array.from(byCurrency.values())
}

export type Severity = 'inactive' | 'in_effect' | 'violated'
export type EnrichedRule = RoadmapResponse['rule_statuses'][number] & { severity: Severity }

/** Enrich roadmap rule statuses with a severity field and sort highest-risk
 * first. Returns the sorted rules and the max severity across them. */
export function enrichRuleStatuses(
  roadmap: RoadmapResponse | undefined,
): { rules: EnrichedRule[]; maxSeverity: Severity } {
  const empty: { rules: EnrichedRule[]; maxSeverity: Severity } = {
    rules: [],
    maxSeverity: 'inactive',
  }
  if (!roadmap) return empty

  const walletIssuers = new Set<string>()
  for (const c of roadmap.cards ?? []) {
    if (c.issuer_name) walletIssuers.add(c.issuer_name)
  }
  const applicable = roadmap.rule_statuses.filter(
    (r) => r.issuer_name != null && walletIssuers.has(r.issuer_name),
  )
  const enriched: EnrichedRule[] = applicable.map((r) => {
    let severity: Severity = 'inactive'
    if (r.current_count >= r.max_count) {
      // Limit reached. A rule is *violated* only when a card from the
      // rule's issuer was approved while the count — within that card's
      // own trailing period window — was already at or over max. We
      // have to do the per-card date check on every rule, not just
      // scope_all_issuers ones: short cooldowns like Citi 1/8 anchor
      // `counted_cards` to today with no upper bound, so two issuer
      // cards more than `period_days` apart can both land in
      // `counted_cards` without actually violating each other.
      const counted = new Set(r.counted_cards)
      const periodMs = r.period_days * 86400000
      const cards = roadmap.cards ?? []
      const candidateCards = cards.filter((c) => {
        if (!counted.has(c.card_name)) return false
        // For scope_all_issuers rules (e.g. Chase 5/24) only the rule's
        // own issuer can violate it; non-issuer cards in the count just
        // contribute to the trigger threshold.
        if (r.issuer_name && c.issuer_name !== r.issuer_name) return false
        return true
      })
      const violated = candidateCards.some((c) => {
        const cMs = parseDate(c.added_date).getTime()
        const windowStartMs = cMs - periodMs
        let priorCount = 0
        for (const other of cards) {
          if (other === c) continue
          if (!counted.has(other.card_name)) continue
          const oMs = parseDate(other.added_date).getTime()
          // <= cMs because we don't have intraday ordering — treat
          // same-day adds as already in the count when c is approved.
          if (oMs >= windowStartMs && oMs <= cMs) priorCount++
        }
        return priorCount >= r.max_count
      })
      severity = violated ? 'violated' : 'in_effect'
    }
    return { ...r, severity }
  })

  const rank: Record<Severity, number> = { inactive: 0, in_effect: 1, violated: 2 }
  const maxSeverity = enriched.reduce<Severity>(
    (m, r) => (rank[r.severity] > rank[m] ? r.severity : m),
    'inactive',
  )
  // Sort highest-risk first: violated → in effect → inactive, then by
  // how close to the limit (count/max), then alphabetically for stability.
  const sorted = [...enriched].sort((a, b) => {
    const ds = rank[b.severity] - rank[a.severity]
    if (ds !== 0) return ds
    const dr = b.current_count / b.max_count - a.current_count / a.max_count
    if (Math.abs(dr) > 1e-9) return dr
    return a.rule_name.localeCompare(b.rule_name)
  })
  return { rules: sorted, maxSeverity }
}
