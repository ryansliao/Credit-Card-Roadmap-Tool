import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Tone = 'info' | 'success' | 'error'

interface Toast {
  id: number
  tone: Tone
  message: string
}

interface ToastContextValue {
  show: (message: string, tone?: Tone) => void
}

const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
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
  const [enter, setEnter] = useState(false)
  useEffect(() => {
    setEnter(true)
  }, [])
  const toneClass: Record<Tone, string> = {
    info: 'border-info/40',
    success: 'border-pos/40',
    error: 'border-neg/40',
  }
  return (
    <div
      role="status"
      className={`bg-surface border ${toneClass[toast.tone]} rounded-md px-4 py-3 text-sm text-ink shadow-card transition-all duration-200 ${
        enter ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-4'
      }`}
    >
      {toast.message}
    </div>
  )
}
