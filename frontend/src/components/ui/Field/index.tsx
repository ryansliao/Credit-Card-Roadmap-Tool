import { useId, type ReactNode, cloneElement, isValidElement, type ReactElement } from 'react'

interface Props {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  required?: boolean
  /** A single form control. We pass `id` + `aria-describedby` to it. */
  children: ReactElement
}

export function Field({ label, hint, error, required = false, children }: Props) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined

  const child = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id,
        'aria-describedby': describedBy,
        invalid: !!error || (children.props as Record<string, unknown>).invalid,
      })
    : children

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-neg ml-1">*</span>}
      </label>
      {child}
      {hint && !error && <p id={hintId} className="text-xs text-ink-muted">{hint}</p>}
      {error && <p id={errorId} className="text-xs text-neg">{error}</p>}
    </div>
  )
}
