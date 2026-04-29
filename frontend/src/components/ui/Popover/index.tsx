import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  /** Element that triggers the popover. Receives `onClick` and `ref` to attach. */
  trigger: (props: { onClick: () => void; ref: React.RefObject<HTMLElement | null> }) => ReactNode
  /** Popover content. */
  children: ReactNode
  /** Close on Esc / outside click. Default true. */
  dismissible?: boolean
  /** Render in a portal (escape overflow:hidden ancestors). Default false. */
  portal?: boolean
  /** Side of the trigger to anchor on. Default 'bottom'. */
  side?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}

export function Popover({
  trigger,
  children,
  dismissible = true,
  portal = false,
  side = 'bottom',
  className = '',
}: Props) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLElement | null>(null)
  const popoverRef = useRef<HTMLDivElement | null>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  useEffect(() => {
    if (!open) return
    const computePosition = () => {
      if (!triggerRef.current) return
      const r = triggerRef.current.getBoundingClientRect()
      const margin = 8
      let top = 0
      let left = 0
      switch (side) {
        case 'top':
          top = r.top - margin
          left = r.left + r.width / 2
          break
        case 'bottom':
          top = r.bottom + margin
          left = r.left + r.width / 2
          break
        case 'left':
          top = r.top + r.height / 2
          left = r.left - margin
          break
        case 'right':
          top = r.top + r.height / 2
          left = r.right + margin
          break
      }
      setPos({ top, left })
    }
    computePosition()
    const onScroll = () => computePosition()
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
  }, [open, side])

  useEffect(() => {
    if (!open || !dismissible) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node
      if (popoverRef.current?.contains(t)) return
      if (triggerRef.current?.contains(t)) return
      setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onClick)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onClick)
    }
  }, [open, dismissible])

  const transform =
    side === 'top'
      ? 'translate(-50%, -100%)'
      : side === 'bottom'
        ? 'translate(-50%, 0)'
        : side === 'left'
          ? 'translate(-100%, -50%)'
          : 'translate(0, -50%)'

  const popoverNode =
    open && pos ? (
      <div
        ref={popoverRef}
        role="dialog"
        style={{
          position: 'fixed',
          top: pos.top,
          left: pos.left,
          transform,
          zIndex: 60,
        }}
        className={`bg-surface border border-divider rounded-lg shadow-modal p-3 max-w-sm ${className}`}
      >
        {children}
      </div>
    ) : null

  return (
    <>
      {trigger({ onClick: () => setOpen((v) => !v), ref: triggerRef })}
      {popoverNode && (portal ? createPortal(popoverNode, document.body) : popoverNode)}
    </>
  )
}
