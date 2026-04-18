/** Format a dollar amount as currency with no cents (e.g. $1,234). */
export function formatMoney(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
}

/**
 * Format internal cash-reward units as USD (units are cents when cpp is 1).
 * Same convention as backend: dollars = units * cpp / 100; pass cpp when not 1.
 */
export function formatCashRewardUnits(units: number, centsPerPoint = 1): string {
  if (!Number.isFinite(units)) return formatMoney(0)
  const dollars = (units * centsPerPoint) / 100
  return formatMoney(dollars)
}

/** Format a dollar amount as currency with cents (e.g. $1,234.56). */
export function formatMoneyExact(n: number): string {
  return n.toLocaleString('en-US', {
    style: 'currency',
    currency: 'USD',
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })
}

/** Format a point count with no abbreviation (e.g. 12,345). Returns '0' for zero/non-finite. */
export function formatPointsExact(n: number): string {
  if (!Number.isFinite(n) || n === 0) return '0'
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
}

/** Format a point balance with k/M suffix. Returns '0' for zero and non-finite values. */
export function formatPoints(n: number): string {
  if (!Number.isFinite(n) || n === 0) return '0'
  const a = Math.abs(n)
  if (a >= 1_000_000) return `${(n / 1_000_000).toFixed(2)}M`
  if (a >= 1_000) return `${(n / 1_000).toFixed(1)}k`
  return n.toLocaleString('en-US', { maximumFractionDigits: 0 })
}

/** Return today's date as a YYYY-MM-DD string (local time). */
export function today(): string {
  const d = new Date()
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

// Brand-aware color map for reward currencies. Each color is chosen to
// evoke the issuer/partner's brand identity while staying mutually
// distinguishable on a single chart. Unknown currencies fall back to a
// deterministic palette hash so they still get a stable color.
const CURRENCY_COLOR_BY_NAME: Record<string, string> = {
  'American AAdvantage Miles': '#b91c1c',          // AA brick red
  'American Express Membership Rewards': '#0b2d6f', // Amex deep blue
  'Atmos Rewards': '#f97316',                       // neutral orange (no strong brand cue)
  'Bank of America Points': '#ef4444',              // BoA red (brighter than AA)
  'Bilt Cash': '#f472b6',                           // Bilt pink (lighter variant for cash)
  'Bilt Rewards': '#ec4899',                        // Bilt hot pink
  'Capital One Venture Miles': '#9f1239',           // Cap One crimson
  'Cash': '#22c55e',                                // generic money green
  'Chase Ultimate Rewards': '#2563eb',              // Chase blue
  'Citi ThankYou Points': '#06b6d4',                // Citi cyan
  'Delta SkyMiles': '#7f1d1d',                      // Delta maroon
  'Hilton Honors': '#4c1d95',                       // Hilton indigo/purple
  'IHG One Rewards': '#2dd4bf',                     // IHG bright teal
  'Marriott Bonvoy': '#92400e',                     // Marriott brown
  'United MileagePlus': '#1e3a8a',                  // United royal navy
  'Wells Fargo Rewards': '#eab308',                 // Wells Fargo amber/gold
  'World of Hyatt': '#0f766e',                      // Hyatt dark teal
}

// Distinct, deterministic palette hashed by currency_id for currencies that
// aren't in the brand table (new additions, etc.).
const CURRENCY_PALETTE = [
  '#6366f1', // indigo
  '#10b981', // emerald
  '#f59e0b', // amber
  '#ec4899', // pink
  '#06b6d4', // cyan
  '#a855f7', // purple
  '#ef4444', // red
  '#14b8a6', // teal
  '#f97316', // orange
  '#84cc16', // lime
  '#8b5cf6', // violet
  '#0ea5e9', // sky
]

export function currencyColor(
  currencyId: number | null | undefined,
  currencyName?: string | null,
): string {
  if (currencyName && CURRENCY_COLOR_BY_NAME[currencyName]) {
    return CURRENCY_COLOR_BY_NAME[currencyName]
  }
  if (currencyId == null) return '#64748b' // slate fallback for unknown currency
  return CURRENCY_PALETTE[currencyId % CURRENCY_PALETTE.length]
}
