import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'children'> {
  label?: ReactNode
}

export const Toggle = forwardRef<HTMLInputElement, Props>(function Toggle(
  { label, className = '', ...rest },
  ref,
) {
  return (
    <label className={`inline-flex items-center gap-2 cursor-pointer text-sm text-ink ${className}`}>
      <input ref={ref} type="checkbox" className="peer sr-only" {...rest} />
      <span
        aria-hidden="true"
        className="w-9 h-5 rounded-full bg-divider relative transition-colors peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent-soft peer-checked:[&>span]:translate-x-4"
      >
        <span className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-surface transition-transform" />
      </span>
      {label && <span>{label}</span>}
    </label>
  )
})
