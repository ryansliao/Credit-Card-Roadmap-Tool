import { useState } from 'react'
import { ModalBackdrop } from '../../../../components/ModalBackdrop'

interface CreateWalletModalProps {
  onClose: () => void
  onCreate: (name: string, description: string) => void
  isLoading: boolean
}

export function CreateWalletModal({
  onClose,
  onCreate,
  isLoading,
}: CreateWalletModalProps) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')

  return (
    <ModalBackdrop onClose={onClose} zIndex="z-50">
      <div className="bg-slate-800 border border-slate-600 rounded-xl p-6 w-96 shadow-xl">
        <h2 className="text-lg font-semibold text-white mb-4">New Wallet</h2>
        <div className="space-y-3">
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Name *</label>
            <input
              autoFocus
              className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
              placeholder="e.g. Main wallet"
              value={name}
              onChange={(e) => setName(e.target.value)}
            />
          </div>
          <div>
            <label className="text-xs text-slate-400 mb-1 block">Description</label>
            <input
              className="w-full bg-slate-700 border border-slate-600 text-white text-sm px-3 py-2 rounded-lg outline-none focus:border-indigo-500"
              placeholder="Optional"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>
        </div>
        <div className="flex gap-2 mt-5">
          <button
            className="flex-1 bg-slate-700 hover:bg-slate-600 text-white text-sm py-2 rounded-lg"
            onClick={onClose}
          >
            Cancel
          </button>
          <button
            disabled={!name.trim() || isLoading}
            className="flex-1 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white text-sm py-2 rounded-lg"
            onClick={() => onCreate(name.trim(), description.trim())}
          >
            {isLoading ? 'Creating…' : 'Create'}
          </button>
        </div>
      </div>
    </ModalBackdrop>
  )
}
