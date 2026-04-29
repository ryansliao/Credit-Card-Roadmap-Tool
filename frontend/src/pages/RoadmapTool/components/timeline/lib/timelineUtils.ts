export interface Range {
  startMs: number
  endMs: number
  spanMs: number
}

export function parseDate(s: string): Date {
  const [y, m, d] = s.split('-').map(Number)
  return new Date(y, (m ?? 1) - 1, d ?? 1)
}

export function addMonths(d: Date, months: number): Date {
  const r = new Date(d)
  r.setMonth(r.getMonth() + months)
  return r
}

export function clamp01(x: number): number {
  return Math.min(1, Math.max(0, x))
}

export function pctOf(range: Range, ms: number): number {
  return clamp01((ms - range.startMs) / range.spanMs) * 100
}

/** Measure rendered text width via a shared offscreen canvas. The font
 * string matches the bar label (text-xs, semibold, default sans-serif). */
let _measureCtx: CanvasRenderingContext2D | null = null
export function measureEafLabelPx(text: string): number {
  if (typeof document === 'undefined') return text.length * 7
  if (!_measureCtx) {
    const canvas = document.createElement('canvas')
    _measureCtx = canvas.getContext('2d')
  }
  if (!_measureCtx) return text.length * 7
  _measureCtx.font = '600 12px ui-sans-serif, system-ui, sans-serif'
  return _measureCtx.measureText(text).width
}
