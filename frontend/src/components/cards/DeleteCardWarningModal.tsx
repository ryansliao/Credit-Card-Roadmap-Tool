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
        <Heading level={4} className="text-neg">Remove card from wallet?</Heading>
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
          variant="ghost"
          onClick={onClose}
          disabled={isLoading}
        >
          Cancel
        </Button>
        <Button
          type="button"
          variant="warn"
          onClick={onConfirm}
          disabled={isLoading}
        >
          {isLoading ? 'Removing…' : 'Remove card'}
        </Button>
      </ModalFooter>
    </Modal>
  )
}
