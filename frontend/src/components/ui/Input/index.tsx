import { forwardRef, type InputHTMLAttributes } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { invalid = false, className = '', type = 'text', ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      type={type}
      aria-invalid={invalid || undefined}
      className={`w-full bg-surface text-ink border ${invalid ? 'border-neg' : 'border-divider'} rounded-md px-3 py-2 text-sm placeholder:text-ink-faint hover:border-divider-strong focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft transition-colors ${className}`}
      {...rest}
    />
  )
})
