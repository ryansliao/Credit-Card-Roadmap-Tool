import { Modal, ModalBody, ModalFooter, ModalHeader } from '../ui/Modal'
import { Button } from '../ui/Button'
import { Heading } from '../ui/Heading'

interface Props {
  cardName: string
  onConfirm: () => void
  onClose: () => void
  isLoading: boolean
}

export function DeleteCardWarningModal({ cardName, onConfirm, onClose, isLoading }: Props) {
  return (
    <Modal open={true} onClose={onClose} size="sm" ariaLabel="Remove card from wallet">
      <ModalHeader>
        <div className="flex items-center gap-3 px-5 pt-5">
          <div className="w-10 h-10 rounded-full bg-neg/10 text-neg flex items-center justify-center shrink-0">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <polyline points="3 6 5 6 21 6" />
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
            </svg>
          </div>
          <Heading level={3}>Remove card from wallet?</Heading>
        </div>
      </ModalHeader>
      <ModalBody>
        <p className="text-sm text-ink-muted mb-3">
          Are you sure you want to remove{' '}
          <span className="font-semibold text-ink">{cardName}</span> from this wallet?
        </p>
        <div className="bg-neg/10 border border-neg/40 rounded-lg px-3 py-2 text-xs text-ink-muted">
          This will also delete any per-wallet customizations attached to this card —
          statement credit selections, multiplier overrides, and top-N category picks.
          This action cannot be undone.
        </div>
      </ModalBody>
      <ModalFooter>
        <Button
          type="button"
          variant="secondary"
          onClick={onClose}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <button
          type="button"
          onClick={onConfirm}
          className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-md bg-neg text-white hover:opacity-90 transition-opacity disabled:opacity-50"
          disabled={isLoading}
        >
          {isLoading ? 'Removing…' : 'Remove card'}
        </button>
      </ModalFooter>
    </Modal>
  )
}
