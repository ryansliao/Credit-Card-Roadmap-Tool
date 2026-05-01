import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Size = 'xs' | 'sm' | 'md' | 'lg'

interface ModalProps {
  open: boolean
  onClose: () => void
  size?: Size
  /** Allow Esc / backdrop-click dismissal. Default true. */
  dismissible?: boolean
  /** Accessible label for the dialog (passed to aria-label on the inner element). */
  ariaLabel?: string
  children: ReactNode
  className?: string
}

const SIZE_CLASS: Record<Size, string> = {
  xs: 'w-80',
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
}

export function Modal({
  open,
  onClose,
  size = 'md',
  dismissible = true,
  ariaLabel,
  children,
  className = '',
}: ModalProps) {
  useEffect(() => {
    if (!open || !dismissible) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, dismissible, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-[1px] p-4"
      onClick={dismissible ? onClose : undefined}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        onClick={(e) => e.stopPropagation()}
        className={`bg-surface rounded-xl shadow-modal w-full ${SIZE_CLASS[size]} ${className}`}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}

interface SectionProps {
  children: ReactNode
  className?: string
}

export function ModalHeader({ children, className = '' }: SectionProps) {
  return (
    <div className={`px-5 pt-5 pb-4 border-b border-divider ${className}`}>
      {children}
    </div>
  )
}

export function ModalBody({ children, className = '' }: SectionProps) {
  return <div className={`px-5 py-5 ${className}`}>{children}</div>
}

export function ModalFooter({ children, className = '' }: SectionProps) {
  return (
    <div className={`px-5 py-4 border-t border-divider flex items-center justify-end gap-2 ${className}`}>
      {children}
    </div>
  )
}
