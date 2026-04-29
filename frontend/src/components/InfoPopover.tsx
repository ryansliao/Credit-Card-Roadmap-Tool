import {
  forwardRef,
  useEffect,
  useLayoutEffect,
  useRef,
  useState,
  type MouseEvent,
  type ReactNode,
} from 'react'
import { createPortal } from 'react-dom'

/**
 * @deprecated Use `Popover` from `components/ui/Popover` instead.
 * This file is preserved unchanged during the design-system migration;
 * Phase 7 replaces call sites with `Popover` and deletes this file.
 *
 * Exports `InfoIconButton` (styled "?" icon button) and `InfoQuoteBox`
 * (positioned popover panel with arrow). Caller manages open state
 * and anchor ref; the panel auto-flips to top/bottom based on viewport space.
 */

export const InfoIconButton = forwardRef<
  HTMLButtonElement,
  {
    onClick: (e: MouseEvent<HTMLButtonElement>) => void
    label: string
    size?: number
    active?: boolean
  }
>(function InfoIconButton({ onClick, label, size = 15, active = false }, ref) {
  return (
    <button
      ref={ref}
      type="button"
      onClick={onClick}
      className={`shrink-0 transition-colors ${
        active ? 'text-indigo-300' : 'text-slate-500 hover:text-indigo-300'
      }`}
      aria-label={label}
      aria-expanded={active}
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
})

const POPOVER_WIDTH = 360
const VIEWPORT_MARGIN = 12
const ANCHOR_GAP = 10

interface Position {
  top: number
  left: number
  arrowLeft: number
  placement: 'top' | 'bottom'
}

function usePopoverPosition(anchorEl: HTMLElement | null): Position | null {
  const [pos, setPos] = useState<Position | null>(null)

  useLayoutEffect(() => {
    if (!anchorEl || typeof window === 'undefined') {
      setPos(null)
      return
    }
    const update = () => {
      const rect = anchorEl.getBoundingClientRect()
      const vw = window.innerWidth
      const vh = window.innerHeight
      const btnCenter = rect.left + rect.width / 2

      const spaceBelow = vh - rect.bottom
      const spaceAbove = rect.top
      const placement: 'top' | 'bottom' =
        spaceBelow >= 220 || spaceBelow >= spaceAbove ? 'bottom' : 'top'

      const maxLeft = vw - POPOVER_WIDTH - VIEWPORT_MARGIN
      const minLeft = VIEWPORT_MARGIN
      const desiredLeft = btnCenter - POPOVER_WIDTH / 2
      const left = Math.max(minLeft, Math.min(maxLeft, desiredLeft))
      const arrowLeft = Math.max(16, Math.min(POPOVER_WIDTH - 16, btnCenter - left))
      const top = placement === 'bottom' ? rect.bottom + ANCHOR_GAP : rect.top - ANCHOR_GAP

      setPos({ top, left, arrowLeft, placement })
    }
    update()
    window.addEventListener('resize', update)
    window.addEventListener('scroll', update, true)
    return () => {
      window.removeEventListener('resize', update)
      window.removeEventListener('scroll', update, true)
    }
  }, [anchorEl])

  return pos
}

export function InfoQuoteBox({
  anchorEl,
  title,
  onClose,
  children,
}: {
  anchorEl: HTMLElement | null
  title?: string
  onClose: () => void
  children: ReactNode
}) {
  const pos = usePopoverPosition(anchorEl)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    const onMouseDown = (e: globalThis.MouseEvent) => {
      const target = e.target as Node | null
      if (!target) return
      if (containerRef.current?.contains(target)) return
      if (anchorEl?.contains(target)) return
      onClose()
    }
    document.addEventListener('keydown', onKeyDown)
    document.addEventListener('mousedown', onMouseDown)
    return () => {
      document.removeEventListener('keydown', onKeyDown)
      document.removeEventListener('mousedown', onMouseDown)
    }
  }, [anchorEl, onClose])

  if (!pos || !anchorEl || typeof document === 'undefined') return null

  const wrapperStyle: React.CSSProperties =
    pos.placement === 'bottom'
      ? { top: pos.top, left: pos.left, width: POPOVER_WIDTH, maxWidth: 'calc(100vw - 24px)' }
      : {
          top: pos.top,
          left: pos.left,
          width: POPOVER_WIDTH,
          maxWidth: 'calc(100vw - 24px)',
          transform: 'translateY(-100%)',
        }

  return createPortal(
    <div
      ref={containerRef}
      role="dialog"
      aria-label={title}
      className="fixed z-[60]"
      style={wrapperStyle}
    >
      {pos.placement === 'bottom' && (
        <div
          aria-hidden
          className="absolute z-10 w-3 h-3 bg-slate-900 border-l border-t border-slate-700 rotate-45"
          style={{ left: pos.arrowLeft - 6, top: -5 }}
        />
      )}
      <div className="relative bg-slate-900 border border-slate-700 rounded-lg shadow-xl shadow-black/40 px-4 py-3">
        {title && (
          <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
        )}
        <div className={`${title ? 'mt-2 ' : ''}space-y-3 text-xs text-slate-400 leading-relaxed`}>{children}</div>
      </div>
      {pos.placement === 'top' && (
        <div
          aria-hidden
          className="absolute z-10 w-3 h-3 bg-slate-900 border-r border-b border-slate-700 rotate-45"
          style={{ left: pos.arrowLeft - 6, bottom: -5 }}
        />
      )}
    </div>,
    document.body,
  )
}
