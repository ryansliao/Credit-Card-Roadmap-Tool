import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ToastContext, type Tone } from './useToast'

interface Toast {
  id: number
  tone: Tone
  message: string
}

interface ProviderProps {
  children: ReactNode
}

export function ToastProvider({ children }: ProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const idRef = useRef(0)

  const show = useCallback((message: string, tone: Tone = 'info') => {
    const id = ++idRef.current
    setToasts((cur) => [...cur, { id, tone, message }])
    setTimeout(() => {
      setToasts((cur) => cur.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  const value = useMemo(() => ({ show }), [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
            {toasts.map((t) => (
              <ToastItem key={t.id} toast={t} />
            ))}
          </div>,
          document.body,
        )}
    </ToastContext.Provider>
  )
}

function ToastItem({ toast }: { toast: Toast }) {
  const toneClass: Record<Tone, string> = {
    info: 'border-info/40',
    success: 'border-pos/40',
    error: 'border-neg/40',
  }
  return (
    <div
      role="status"
      className={`bg-surface border ${toneClass[toast.tone]} rounded-md px-4 py-3 text-sm text-ink shadow-card animate-toast-in`}
    >
      {toast.message}
    </div>
  )
}
