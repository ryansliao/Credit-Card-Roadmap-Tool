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
        <div className="flex items-center gap-3 px-5 pt-5">
          <div className="w-10 h-10 rounded-full bg-warn/10 text-warn flex items-center justify-center shrink-0">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
          </div>
          <Heading level={3}>Application rule warning</Heading>
        </div>
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
        <Button variant="primary" className="w-full" onClick={onClose}>
          OK
        </Button>
      </ModalFooter>
    </Modal>
  )
}
