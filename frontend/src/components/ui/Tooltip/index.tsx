import { useCallback, useState, type ReactElement, cloneElement } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  label: string
  /** Default 'top'. */
  side?: 'top' | 'bottom' | 'left' | 'right'
  children: ReactElement
}

export function Tooltip({ label, side = 'top', children }: Props) {
  const [target, setTarget] = useState<HTMLElement | null>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  const setTargetRef = useCallback((el: HTMLElement | null) => {
    setTarget(el)
  }, [])

  const show = () => {
    if (!target) return
    const r = target.getBoundingClientRect()
    const m = 6
    let top = 0
    let left = 0
    switch (side) {
      case 'top':
        top = r.top - m
        left = r.left + r.width / 2
        break
      case 'bottom':
        top = r.bottom + m
        left = r.left + r.width / 2
        break
      case 'left':
        top = r.top + r.height / 2
        left = r.left - m
        break
      case 'right':
        top = r.top + r.height / 2
        left = r.right + m
        break
    }
    setPos({ top, left })
  }
  const hide = () => setPos(null)

  // Clone the child to attach ref + handlers without imposing structure.
  const child = cloneElement(children as ReactElement<Record<string, unknown>>, {
    ref: setTargetRef,
    onMouseEnter: show,
    onMouseLeave: hide,
    onFocus: show,
    onBlur: hide,
  })

  const transform =
    side === 'top'
      ? 'translate(-50%, -100%)'
      : side === 'bottom'
        ? 'translate(-50%, 0)'
        : side === 'left'
          ? 'translate(-100%, -50%)'
          : 'translate(0, -50%)'

  const tooltipNode = pos ? (
    <span
      role="tooltip"
      style={{
        position: 'fixed',
        top: pos.top,
        left: pos.left,
        transform,
        zIndex: 70,
      }}
      className="px-2 py-1 rounded bg-[#0b0d11] text-white text-[11px] font-medium whitespace-nowrap pointer-events-none shadow-card"
    >
      {label}
    </span>
  ) : null

  return (
    <>
      {child}
      {tooltipNode && typeof document !== 'undefined' && createPortal(tooltipNode, document.body)}
    </>
  )
}
