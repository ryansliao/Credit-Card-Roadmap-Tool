import { type ReactNode } from 'react'
import { ModalBackdrop } from './ModalBackdrop'

export function InfoIconButton({
  onClick,
  label,
  size = 15,
}: {
  onClick: () => void
  label: string
  size?: number
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="shrink-0 text-slate-500 hover:text-indigo-300 transition-colors"
      aria-label={label}
      title={label}
    >
      <svg
        width={size}
        height={size}
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
      >
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="16" x2="12" y2="12" />
        <line x1="12" y1="8" x2="12.01" y2="8" />
      </svg>
    </button>
  )
}

export function InfoPopover({
  title,
  onClose,
  children,
  zIndex = 'z-[60]',
}: {
  title: string
  onClose: () => void
  children: ReactNode
  zIndex?: string
}) {
  return (
    <ModalBackdrop onClose={onClose} label={title} zIndex={zIndex}>
      <div className="bg-slate-900 border border-slate-700 rounded-xl p-5 w-full max-w-md space-y-4">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
          <button
            type="button"
            onClick={onClose}
            className="text-slate-500 hover:text-slate-200 transition-colors"
            aria-label="Close"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <line x1="18" y1="6" x2="6" y2="18" />
              <line x1="6" y1="6" x2="18" y2="18" />
            </svg>
          </button>
        </div>
        <div className="space-y-3 text-xs text-slate-400 leading-relaxed">{children}</div>
      </div>
    </ModalBackdrop>
  )
}
