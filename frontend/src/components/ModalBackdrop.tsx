import { useEffect, useId, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  onClose: () => void
  children: ReactNode
  /** Accessible label for the dialog (shown to screen readers). */
  label?: string
  className?: string
  zIndex?: string
}

/**
 * @deprecated Use `Modal` from `components/ui/Modal` instead.
 * This component is preserved unchanged during the design-system migration;
 * Phase 7 replaces call sites with `Modal` + slot helpers and deletes this file.
 *
 * Shared modal backdrop with consistent styling, backdrop-click dismiss,
 * and Escape key handling. Wrap dialog content as children.
 *
 * Rendered via a portal to `document.body` so the backdrop/dialog escape
 * any ancestor stacking context or overflow clipping (e.g. when the
 * trigger lives inside a z-indexed panel or a scrollable container).
 */
export function ModalBackdrop({ onClose, children, label, className, zIndex = 'z-50' }: Props) {
  const titleId = useId()

  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onClose])

  if (typeof document === 'undefined') return null

  return createPortal(
    <div
      className={`fixed inset-0 ${zIndex} flex items-center justify-center bg-black/60 p-4`}
      role="dialog"
      aria-modal="true"
      aria-labelledby={label ? titleId : undefined}
      onClick={onClose}
    >
      <div
        className={className}
        onClick={(e) => e.stopPropagation()}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
