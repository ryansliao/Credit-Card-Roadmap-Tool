import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'link' | 'icon'
type Size = 'sm' | 'md' | 'lg'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: ReactNode
}

const VARIANT: Record<Variant, string> = {
  primary:   'bg-accent text-page hover:opacity-90',
  secondary: 'bg-transparent text-ink border border-ink hover:bg-surface-2',
  ghost:     'bg-transparent text-ink hover:bg-surface-2',
  link:      'bg-transparent text-accent underline underline-offset-2 hover:opacity-80 px-0 py-0',
  icon:      'bg-transparent text-ink hover:bg-surface-2 aspect-square justify-center',
}
const SIZE: Record<Size, string> = {
  sm: 'text-xs px-2.5 py-1.5',
  md: 'text-sm px-3.5 py-2',
  lg: 'text-base px-5 py-2.5',
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = 'primary', size = 'md', loading = false, disabled, children, className = '', ...rest },
  ref,
) {
  const base = variant === 'link' ? '' : 'rounded-md'
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex items-center gap-2 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${base} ${SIZE[size]} ${VARIANT[variant]} ${className}`}
      {...rest}
    >
      {loading && (
        <span aria-hidden="true" className="inline-block w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
      )}
      {children}
    </button>
  )
})
