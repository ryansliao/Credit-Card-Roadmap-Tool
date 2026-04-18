import { useState } from 'react'
import { ModalBackdrop } from '../../../../components/ModalBackdrop'
import { today } from '../../../../utils/format'

interface Props {
  cardName: string
  minDate?: string
  isLoading: boolean
  onClose: () => void
  onConfirm: (closedDate: string) => void
}

export function CloseCardModal({ cardName, minDate, isLoading, onClose, onConfirm }: Props) {
  const [value, setValue] = useState(today())
  const invalid = !value

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (invalid) return
    onConfirm(value)
  }

  return (
    <ModalBackdrop
      onClose={onClose}
      label="Close card"
      className="w-full max-w-sm bg-slate-900 border border-slate-700 rounded-xl p-5 shadow-xl"
    >
      <form onSubmit={handleSubmit} className="space-y-4">
        <div>
          <h3 className="text-base font-semibold text-slate-100">Close card</h3>
          <p className="text-sm text-slate-400 mt-1">
            When was <span className="text-slate-200">{cardName}</span> closed?
          </p>
        </div>
        <label className="block">
          <span className="text-xs text-slate-400 uppercase tracking-wider">Closed date</span>
          <input
            type="date"
            value={value}
            min={minDate}
            onChange={(e) => setValue(e.target.value)}
            className="mt-1 block w-full bg-slate-800 border border-slate-700 text-slate-100 text-sm rounded px-2 py-1.5 focus:outline-none focus:border-indigo-500"
            autoFocus
          />
        </label>
        <div className="flex items-center justify-end gap-2">
          <button
            type="button"
            onClick={onClose}
            className="text-sm text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded"
            disabled={isLoading}
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={isLoading || invalid}
            className="text-sm bg-amber-600 hover:bg-amber-500 text-white px-3 py-1.5 rounded disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {isLoading ? 'Closing…' : 'Close card'}
          </button>
        </div>
      </form>
    </ModalBackdrop>
  )
}
