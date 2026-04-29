import type { CardResult } from '../../../../../api/client'
import {
  cardAnnualPointIncomeActive,
  cardAnnualPointIncomeCurrencyWindow,
  cardEafWindow,
} from '../../../../../utils/cardIncome'
import {
  formatMoney,
  formatMoneyCompact,
  formatPoints,
  formatPointsExact,
} from '../../../../../utils/format'
import { parseDate } from './timelineUtils'

/** These types are re-used across formatters and are defined here to avoid
 * circular imports. The full GroupData / SecondaryAnnual interfaces live in
 * their respective component files; we use structural sub-types here so this
 * module stays pure (no React, no JSX). */
interface GroupIncomeArgs {
  rewardKind: 'points' | 'cash' | null
  cards: Array<{ cr: CardResult | null }>
}

interface GroupBalanceArgs {
  totalBalance: number | null
  rewardKind: 'points' | 'cash' | null
  balanceCpp: number | null
  cards: Array<{ cr: CardResult | null }>
}

/** Format a card's annual income. Cash cards: "$X/yr". Points/miles
 * cards: "X/yr" (unit label omitted to match the currency rows). */
export function formatCardIncome(
  c: CardResult | null,
  includeSubs: boolean,
): string | null {
  const pts = cardAnnualPointIncomeActive(c, includeSubs)
  if (pts == null || c == null) return null
  if (c.effective_reward_kind === 'cash') {
    const dollars = (pts * c.cents_per_point) / 100
    return `${formatMoney(dollars)}/yr`
  }
  const rounded = Math.round(pts)
  return `${formatPoints(rounded)}/yr`
}

/** Annual dollar value of a group, regardless of reward kind. Sums only
 * cards that were included in the last calc (have a `cr`). Does NOT gate
 * by live `is_enabled` so group totals/ordering stay stable until the
 * user clicks Calculate again. Uses the currency's own window (earliest
 * card open → latest close among cards earning the currency) for
 * annualization when available. */
export function groupAnnualDollars(
  group: GroupBalanceArgs,
  includeSubs: boolean,
  walletWindowYears: number | undefined,
  currencyWindowYears: number | undefined,
): number {
  return group.cards.reduce((s, { cr }) => {
    if (!cr) return s
    const pts =
      cardAnnualPointIncomeCurrencyWindow(
        cr,
        includeSubs,
        walletWindowYears,
        currencyWindowYears,
      ) ?? 0
    return s + (pts * cr.cents_per_point) / 100
  }, 0)
}

/** End-of-projection dollar value of a group's balance. Used to order
 * groups by projected balance. Falls back to the first card's CPP when
 * `balanceCpp` isn't set (i.e. points-kind groups). */
export function groupBalanceDollars(group: GroupBalanceArgs): number {
  if (group.totalBalance == null) return 0
  const cpp =
    group.balanceCpp ??
    group.cards.find((e) => e.cr != null)?.cr?.cents_per_point ??
    null
  if (cpp == null) return 0
  return (group.totalBalance * cpp) / 100
}

/** Sum of per-card EAF across all cards earning this currency. Uses the
 * window-basis flavor (not the active-year one) so the sum stays on the
 * wallet window. Used as a tiebreaker when ordering zero-balance
 * currencies, so it always honors the "include SUBs" toggle as a display
 * switch — passing `true` mirrors the backend's SUB-inclusive value. */
export function groupCombinedEaf(group: GroupIncomeArgs): number {
  return group.cards.reduce(
    (s, { cr }) => s + (cardEafWindow(cr ?? null, true) ?? 0),
    0,
  )
}

export function formatGroupIncome(
  group: GroupIncomeArgs,
  includeSubs: boolean,
  walletWindowYears: number | undefined,
  currencyWindowYears: number | undefined,
): string | null {
  const { rewardKind, cards } = group
  if (!rewardKind) return null
  const included = cards.filter(({ cr }) => cr != null)
  if (included.length === 0) return null
  const scaledPts = (c: CardResult | null | undefined): number =>
    cardAnnualPointIncomeCurrencyWindow(
      c ?? null,
      includeSubs,
      walletWindowYears,
      currencyWindowYears,
    ) ?? 0
  if (rewardKind === 'cash') {
    const dollars = included.reduce((s, { cr }) => {
      const pts = scaledPts(cr)
      return s + (pts * (cr?.cents_per_point ?? 1)) / 100
    }, 0)
    return `${formatMoney(dollars)}/yr`
  }
  const pts = included.reduce((s, { cr }) => s + scaledPts(cr), 0)
  const rounded = Math.round(pts)
  return `${formatPoints(rounded)}/yr`
}

/** Format a single secondary-currency annual total, e.g. "$25 Bilt Cash/yr".
 * Group-level aggregates use summed per-card annualised rates (each
 * card's `secondary_currency_net_earn / card_active_years`). */
export function formatSecondaryAnnual(secondary: {
  rewardKind: 'points' | 'cash'
  dollars: number
  units: number
  name: string
}): string {
  if (secondary.rewardKind === 'cash') {
    return `${formatMoneyCompact(secondary.dollars)} ${secondary.name}/yr`
  }
  const rounded = Math.round(secondary.units)
  return `${formatPoints(rounded)} ${secondary.name}/yr`
}

/** Format a currency's end-of-projection balance. Uses the same
 * pts-vs-dollars split as the per-year figure so the two read consistently. */
export function formatGroupBalance(group: GroupBalanceArgs): string | null {
  if (group.totalBalance == null) return null
  if (group.rewardKind === 'cash' && group.balanceCpp != null) {
    const dollars = (group.totalBalance * group.balanceCpp) / 100
    return `${formatMoney(dollars)}`
  }
  const rounded = Math.round(group.totalBalance)
  return formatPointsExact(rounded)
}

export function formatSecondaryBalance(secondary: {
  name: string
  units: number
  dollars: number
  rewardKind: 'points' | 'cash'
}): string {
  if (secondary.rewardKind === 'cash') {
    return `${formatMoneyCompact(secondary.dollars)} ${secondary.name}/yr`
  }
  const rounded = Math.round(secondary.units)
  return `${formatPoints(rounded)} ${secondary.name}/yr`
}

export function formatDate(s: string | null): string {
  if (!s) return '—'
  const d = parseDate(s)
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
  })
}
