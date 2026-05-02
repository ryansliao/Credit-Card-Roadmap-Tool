import { useEffect, useRef, useState } from 'react'
import type { ScenarioSummary } from '../../../api/client'
import { Modal, ModalHeader, ModalBody, ModalFooter } from '../../../components/ui/Modal'
import { Heading } from '../../../components/ui/Heading'
import { Field } from '../../../components/ui/Field'
import { Input } from '../../../components/ui/Input'
import { Select } from '../../../components/ui/Select'
import { Button } from '../../../components/ui/Button'

interface Props {
  isSubmitting: boolean
  errorMessage: string | null
  scenarios: ScenarioSummary[]
  onSubmit: (payload: { name: string; description: string | null; copy_from_scenario_id: number | null }) => void
  onClose: () => void
}

/** Replaces AddWalletModal: collects scenario name + optional description and
 * an optional "copy from" source scenario. Posts to scenariosApi.create. */
export function AddScenarioModal({
  isSubmitting,
  errorMessage,
  scenarios,
  onSubmit,
  onClose,
}: Props) {
  const [name, setName] = useState('')
  const [description, setDescription] = useState('')
  const [copyFromId, setCopyFromId] = useState<number | ''>('')
  const inputRef = useRef<HTMLInputElement>(null)

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const trimmed = name.trim()
  const canSubmit = trimmed.length > 0 && !isSubmitting

  return (
    <Modal open={true} onClose={isSubmitting ? () => undefined : onClose} size="sm" ariaLabel="Add scenario">
      <ModalHeader>
        <Heading level={3}>New Scenario</Heading>
      </ModalHeader>
      <ModalBody>
        <form
          id="add-scenario-form"
          onSubmit={(e) => {
            e.preventDefault()
            if (canSubmit) {
              onSubmit({
                name: trimmed,
                description: description.trim() || null,
                copy_from_scenario_id: copyFromId === '' ? null : copyFromId,
              })
            }
          }}
          className="space-y-4"
        >
          <Field label="Name">
            <Input
              ref={inputRef}
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={120}
              placeholder="e.g. Add Sapphire Reserve"
              disabled={isSubmitting}
            />
          </Field>
          <Field label="Description">
            <Input
              type="text"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              maxLength={240}
              placeholder="Optional"
              disabled={isSubmitting}
            />
          </Field>
          {scenarios.length > 0 && (
            <Field label="Copy from (optional)">
              <Select
                value={copyFromId}
                onChange={(e) =>
                  setCopyFromId(e.target.value === '' ? '' : Number(e.target.value))
                }
                disabled={isSubmitting}
              >
                <option value="">Start fresh</option>
                {scenarios.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                    {s.is_default ? ' (default)' : ''}
                  </option>
                ))}
              </Select>
            </Field>
          )}
          {errorMessage && <p className="mt-2 text-sm text-neg">{errorMessage}</p>}
        </form>
      </ModalBody>
      <ModalFooter>
        <Button variant="secondary" size="sm" type="button" onClick={onClose} disabled={isSubmitting}>
          Cancel
        </Button>
        <Button
          variant="primary"
          size="sm"
          type="submit"
          form="add-scenario-form"
          disabled={!canSubmit || isSubmitting}
          loading={isSubmitting}
        >
          Create
        </Button>
      </ModalFooter>
    </Modal>
  )
}
