import { forwardRef, useEffect, useRef, type InputHTMLAttributes, type ReactNode } from 'react'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'children'> {
  indeterminate?: boolean
  label?: ReactNode
}

export const Checkbox = forwardRef<HTMLInputElement, Props>(function Checkbox(
  { indeterminate = false, label, className = '', ...rest },
  forwardedRef,
) {
  const innerRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (innerRef.current) innerRef.current.indeterminate = indeterminate
  }, [indeterminate])

  const setRefs = (el: HTMLInputElement | null) => {
    innerRef.current = el
    if (typeof forwardedRef === 'function') forwardedRef(el)
    else if (forwardedRef) (forwardedRef as React.MutableRefObject<HTMLInputElement | null>).current = el
  }

  return (
    <label className={`inline-flex items-center gap-2 cursor-pointer text-sm text-ink ${className}`}>
      <input ref={setRefs} type="checkbox" className="peer sr-only" {...rest} />
      <span
        aria-hidden="true"
        className="w-4 h-4 rounded border border-divider bg-surface flex items-center justify-center transition-colors peer-checked:bg-accent peer-checked:border-accent peer-indeterminate:bg-accent peer-indeterminate:border-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent-soft peer-checked:[&_svg]:block peer-indeterminate:[&_.cb-bar]:block"
      >
        <svg viewBox="0 0 14 14" className="w-3 h-3 text-page hidden" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M2 7l3.5 3.5L12 4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="cb-bar w-2 h-0.5 bg-page hidden" />
      </span>
      {label && <span>{label}</span>}
    </label>
  )
})
