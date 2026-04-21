/** Format a dollar amount as currency with no cents (e.g. $1,234). */
export function formatMoney(n: number): string {
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
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

/** Format a dollar amount with k/M suffix (e.g. $1.5k, $2.3M). Returns '$0' for zero/non-finite. */
export function formatMoneyCompact(n: number): string {
  if (!Number.isFinite(n) || n === 0) return '$0'
  const a = Math.abs(n)
  if (a >= 1_000_000) return `$${(n / 1_000_000).toFixed(2)}M`
  if (a >= 1_000) return `$${(n / 1_000).toFixed(1)}k`
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })
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
