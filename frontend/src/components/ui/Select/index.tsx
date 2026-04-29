import { forwardRef, type SelectHTMLAttributes, type ReactNode } from 'react'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean
  children: ReactNode
}

export const Select = forwardRef<HTMLSelectElement, Props>(function Select(
  { invalid = false, className = '', children, ...rest },
  ref,
) {
  return (
    <div className="relative">
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={`w-full appearance-none bg-surface text-ink border ${invalid ? 'border-neg' : 'border-divider'} rounded-md pl-3 pr-8 py-2 text-sm focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft ${className}`}
        {...rest}
      >
        {children}
      </select>
      <span aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint text-xs">▾</span>
    </div>
  )
})
