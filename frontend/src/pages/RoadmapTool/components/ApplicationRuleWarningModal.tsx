import type { RoadmapRuleStatus } from '../../../api/client'
import { Modal, ModalHeader, ModalBody, ModalFooter } from '../../../components/ui/Modal'
import { Heading } from '../../../components/ui/Heading'
import { Button } from '../../../components/ui/Button'
import { IssuerRuleBanner } from '../../../components/cards/IssuerRuleBanner'

interface Props {
  violations: RoadmapRuleStatus[]
  onClose: () => void
}

export function ApplicationRuleWarningModal({ violations, onClose }: Props) {
  return (
    <Modal open={true} onClose={onClose} size="md" ariaLabel="Application rule warning">
      <ModalHeader>
        <Heading level={3} className="text-warn">Application rule warning</Heading>
      </ModalHeader>
      <ModalBody>
        <p className="text-xs text-ink-muted mb-4">
          Adding this card pushed your wallet past at least one issuer application rule.
        </p>
        <div className="space-y-2 max-h-[min(50vh,320px)] overflow-y-auto">
          {violations.map((r) => (
            <IssuerRuleBanner
              key={r.rule_id}
              rule={`${r.issuer_name} ${r.rule_name}`}
              message={
                <>
                  {r.description}{' '}
                  <span className="text-ink-faint">
                    ({r.current_count}/{r.max_count} in {r.period_days}d)
                  </span>
                </>
              }
            />
          ))}
        </div>
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" className="w-full" onClick={onClose}>
          OK
        </Button>
      </ModalFooter>
    </Modal>
  )
}
