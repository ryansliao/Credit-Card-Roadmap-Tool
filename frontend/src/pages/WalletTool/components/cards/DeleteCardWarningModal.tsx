import { ModalBackdrop } from '../../../../components/ModalBackdrop'

interface Props {
  cardName: string
  onConfirm: () => void
  onClose: () => void
  isLoading: boolean
}

/**
 * Confirmation dialog shown before removing a card from a wallet. Removing a
 * wallet card is destructive — it cascades and deletes per-wallet credit
 * overrides, multiplier overrides, group selections, and rotation overrides
 * for that card — so we ask the user to confirm.
 */
export function DeleteCardWarningModal({ cardName, onConfirm, onClose, isLoading }: Props) {
  return (
    <ModalBackdrop
      onClose={onClose}
      label="Remove card from wallet"
      className="bg-slate-900 border border-red-700/50 rounded-xl p-5 max-w-md w-full shadow-xl"
    >
      <h2 className="text-base font-semibold text-red-300 mb-1">Remove card from wallet?</h2>
      <p className="text-sm text-slate-300 mb-3">
        Are you sure you want to remove{' '}
        <span className="font-semibold text-white">{cardName}</span> from this wallet?
      </p>
      <div className="bg-red-900/20 border border-red-700/40 rounded-lg px-3 py-2 text-xs text-slate-300 mb-5">
        This will also delete any per-wallet customizations attached to this card —
        statement credit selections, multiplier overrides, top-N category picks, and
        rotation overrides. This action cannot be undone.
      </div>
      <div className="flex items-center justify-end gap-2">
        <button
          type="button"
          onClick={onClose}
          disabled={isLoading}
          className="px-4 py-2 text-sm text-slate-300 hover:text-white rounded-lg hover:bg-slate-700/60 disabled:opacity-50"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={onConfirm}
          disabled={isLoading}
          className="px-4 py-2 text-sm bg-red-600 hover:bg-red-500 text-white rounded-lg disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {isLoading ? 'Removing…' : 'Remove card'}
        </button>
      </div>
    </ModalBackdrop>
  )
}
