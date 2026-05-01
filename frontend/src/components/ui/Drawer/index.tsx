import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Side = 'left' | 'right'
type Width = 'sm' | 'md' | 'lg'

interface Props {
  open: boolean
  onClose: () => void
  side?: Side
  width?: Width
  dismissible?: boolean
  ariaLabel?: string
  children: ReactNode
  className?: string
}

const WIDTH_CLASS: Record<Width, string> = {
  sm: 'w-72',
  md: 'w-96',
  lg: 'w-[28rem]',
}

export function Drawer({
  open,
  onClose,
  side = 'right',
  width = 'md',
  dismissible = true,
  ariaLabel,
  children,
  className = '',
}: Props) {
  useEffect(() => {
    if (!open || !dismissible) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, dismissible, onClose])

  if (!open) return null

  const sideClass = side === 'right' ? 'right-0 rounded-l-xl' : 'left-0 rounded-r-xl'

  return createPortal(
    <div
      className="fixed inset-0 z-50 bg-black/40"
      onClick={dismissible ? onClose : undefined}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        aria-label={ariaLabel}
        onClick={(e) => e.stopPropagation()}
        className={`absolute top-0 bottom-0 ${sideClass} ${WIDTH_CLASS[width]} bg-surface shadow-modal overflow-y-auto ${className}`}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
