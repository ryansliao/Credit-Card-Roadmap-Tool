import { useEffect, useRef, useState } from 'react'
import { ModalBackdrop } from '../../../components/ModalBackdrop'

interface Props {
  isSubmitting: boolean
  errorMessage: string | null
  onSubmit: (name: string) => void
  onClose: () => void
}

export function AddWalletModal({ isSubmitting, errorMessage, onSubmit, onClose }: Props) {
  const [name, setName] = useState('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const trimmed = name.trim()
  const canSubmit = trimmed.length > 0 && !isSubmitting

  return (
    <ModalBackdrop
      onClose={isSubmitting ? () => undefined : onClose}
      label="Add wallet"
      className="bg-slate-900 border border-slate-700 rounded-xl shadow-xl w-full max-w-md p-5"
    >
      <form
        onSubmit={(e) => {
          e.preventDefault()
          if (canSubmit) onSubmit(trimmed)
        }}
      >
        <h2 className="text-lg font-semibold text-slate-100 mb-3">New Wallet</h2>
        <label className="block text-xs font-medium text-slate-400 uppercase tracking-wider mb-1">
          Name
        </label>
        <input
          ref={inputRef}
          type="text"
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={120}
          placeholder="e.g. Travel-focused wallet"
          className="w-full px-3 py-2 rounded-md bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 focus:border-indigo-500"
          disabled={isSubmitting}
        />
        {errorMessage && (
          <p className="mt-2 text-sm text-red-400">{errorMessage}</p>
        )}
        <div className="mt-5 flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            disabled={isSubmitting}
            className="px-3 py-1.5 rounded-md text-sm text-slate-300 hover:bg-slate-800 transition-colors disabled:opacity-50"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!canSubmit}
            className={`px-4 py-1.5 rounded-md text-sm font-semibold transition-colors ${
              canSubmit
                ? 'bg-indigo-500 hover:bg-indigo-400 text-white'
                : 'bg-slate-700 text-slate-500 cursor-not-allowed'
            }`}
          >
            {isSubmitting ? 'Creating…' : 'Create'}
          </button>
        </div>
      </form>
    </ModalBackdrop>
  )
}
