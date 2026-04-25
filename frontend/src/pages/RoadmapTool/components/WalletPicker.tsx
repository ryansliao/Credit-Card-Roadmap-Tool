import { useEffect, useRef, useState } from 'react'
import type { WalletSummary } from '../../../api/client'

interface Props {
  wallets: WalletSummary[]
  currentId: number | null
  onSelect: (walletId: number) => void
  onAddWallet: () => void
}

export function WalletPicker({ wallets, currentId, onSelect, onAddWallet }: Props) {
  const [open, setOpen] = useState(false)
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    const onMouseDown = (e: MouseEvent) => {
      if (!containerRef.current?.contains(e.target as Node)) setOpen(false)
    }
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false)
    }
    document.addEventListener('mousedown', onMouseDown)
    document.addEventListener('keydown', onKey)
    return () => {
      document.removeEventListener('mousedown', onMouseDown)
      document.removeEventListener('keydown', onKey)
    }
  }, [open])

  const current = wallets.find((w) => w.id === currentId) ?? wallets[0] ?? null

  return (
    <div ref={containerRef} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex items-center gap-1.5 px-3 py-1 rounded-md bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 text-sm font-medium transition-colors"
        aria-haspopup="listbox"
        aria-expanded={open}
        title="Switch wallet"
      >
        <span className="truncate max-w-[14rem]">{current?.name ?? 'New Wallet'}</span>
        <svg
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
          className={`shrink-0 transition-transform ${open ? 'rotate-180' : ''}`}
          aria-hidden
        >
          <polyline points="6 9 12 15 18 9" />
        </svg>
      </button>
      {open && (
        <div
          role="listbox"
          className="absolute top-full mt-1 left-0 z-50 min-w-[14rem] max-h-64 overflow-auto rounded-md bg-slate-800 border border-slate-700 shadow-lg py-1"
        >
          {wallets.map((w) => (
            <button
              key={w.id}
              type="button"
              role="option"
              aria-selected={w.id === currentId}
              onClick={() => {
                setOpen(false)
                if (w.id !== currentId) onSelect(w.id)
              }}
              className={`block w-full text-left px-3 py-1.5 text-sm truncate transition-colors hover:bg-slate-700 ${
                w.id === currentId ? 'text-indigo-300 font-semibold' : 'text-slate-200'
              }`}
            >
              {w.name}
            </button>
          ))}
          <div className="border-t border-slate-700/60 my-1" />
          <button
            type="button"
            onClick={() => {
              setOpen(false)
              onAddWallet()
            }}
            className="flex items-center gap-2 w-full text-left px-3 py-1.5 text-sm text-indigo-300 hover:bg-slate-700 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
              <line x1="12" y1="5" x2="12" y2="19" />
              <line x1="5" y1="12" x2="19" y2="12" />
            </svg>
            New wallet
          </button>
        </div>
      )}
    </div>
  )
}
