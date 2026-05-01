import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'link' | 'icon' | 'warn'
type Size = 'sm' | 'md' | 'lg'
export type IconTone = 'info' | 'danger' | 'neutral'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  /** Hover treatment for `variant="icon"`. Ignored for other variants. */
  tone?: IconTone
  loading?: boolean
  children: ReactNode
}

const VARIANT: Record<Exclude<Variant, 'icon'>, string> = {
  primary:   'bg-accent text-on-accent hover:opacity-90',
  warn:      'bg-warn text-page hover:opacity-90',
  secondary: 'bg-transparent text-ink border border-ink hover:bg-surface-2',
  ghost:     'bg-transparent text-ink hover:bg-surface-2',
  link:      'bg-transparent text-accent underline underline-offset-2 hover:opacity-80 px-0 py-0',
}

// Canonical hover treatments for icon-only buttons. Inline icon buttons that
// can't use <Button variant="icon"> (e.g. need custom padding/layout) should
// pull from ICON_TONE_CLASS to stay in sync with this homogenized vocabulary.
export const ICON_TONE_CLASS: Record<IconTone, string> = {
  info:    'hover:text-accent',
  danger:  'hover:text-neg hover:bg-neg/10',
  neutral: 'hover:text-ink hover:bg-surface-2',
}

const ICON_BASE = 'bg-transparent text-ink-faint aspect-square justify-center'

const SIZE: Record<Size, string> = {
  sm: 'text-xs px-2.5 py-1.5',
  md: 'text-sm px-3.5 py-2',
  lg: 'text-base px-5 py-2.5',
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = 'primary', size = 'md', tone = 'neutral', loading = false, disabled, children, className = '', ...rest },
  ref,
) {
  const base = variant === 'link' ? '' : 'rounded-md'
  const variantClass = variant === 'icon'
    ? `${ICON_BASE} ${ICON_TONE_CLASS[tone]}`
    : VARIANT[variant]
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex items-center gap-2 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${base} ${SIZE[size]} ${variantClass} ${className}`}
      {...rest}
    >
      {loading && (
        <span aria-hidden="true" className="inline-block w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
      )}
      {children}
    </button>
  )
})
