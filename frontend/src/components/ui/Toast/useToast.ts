import { createContext, useContext } from 'react'

export type Tone = 'info' | 'success' | 'error'

export interface ToastContextValue {
  show: (message: string, tone?: Tone) => void
}

export const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}
