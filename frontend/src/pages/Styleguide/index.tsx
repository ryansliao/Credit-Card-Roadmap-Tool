import { useState } from 'react'
import { ThemeToggle } from '../../components/ui/ThemeToggle'
import { Heading } from '../../components/ui/Heading'
import { Eyebrow } from '../../components/ui/Eyebrow'
import { Money } from '../../components/ui/Money'
import { Points } from '../../components/ui/Points'
import { Stat } from '../../components/ui/Stat'
import { Surface } from '../../components/ui/Surface'
import { Modal, ModalHeader, ModalBody, ModalFooter } from '../../components/ui/Modal'
import { Popover } from '../../components/ui/Popover'
import { Drawer } from '../../components/ui/Drawer'
import { useToast } from '../../components/ui/Toast'
import { Tooltip } from '../../components/ui/Tooltip'

function ModalDemo() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink"
      >
        Open modal
      </button>
      <Modal open={open} onClose={() => setOpen(false)} ariaLabel="Modal demo">
        <ModalHeader>
          <Heading level={3}>Modal title</Heading>
        </ModalHeader>
        <ModalBody>
          <p className="text-ink-muted text-sm">
            The modal supports header / body / footer slots and sizes xs/sm/md/lg.
            Press Esc or click the backdrop to dismiss.
          </p>
        </ModalBody>
        <ModalFooter>
          <button
            onClick={() => setOpen(false)}
            className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink"
          >
            Close
          </button>
        </ModalFooter>
      </Modal>
    </>
  )
}

function DrawerDemo() {
  const [open, setOpen] = useState(false)
  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink"
      >
        Open drawer
      </button>
      <Drawer open={open} onClose={() => setOpen(false)} side="right" width="md" ariaLabel="Drawer demo">
        <div className="p-6 space-y-3">
          <Heading level={3}>Drawer</Heading>
          <p className="text-ink-muted text-sm">Slide-over panel from the right. Esc + backdrop dismiss.</p>
        </div>
      </Drawer>
    </>
  )
}

function ToastDemo() {
  const { show } = useToast()
  return (
    <div className="flex gap-2">
      <button
        onClick={() => show('Hello — info toast', 'info')}
        className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink"
      >
        Info
      </button>
      <button
        onClick={() => show('Saved successfully', 'success')}
        className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink"
      >
        Success
      </button>
      <button
        onClick={() => show('Something broke', 'error')}
        className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink"
      >
        Error
      </button>
    </div>
  )
}

/**
 * Internal styleguide route — gated by VITE_SHOW_STYLEGUIDE=1.
 * Each primitive section gets registered here as it lands. The id-anchored
 * sections mean you can deep-link to a primitive: /styleguide#modal.
 */
export default function Styleguide() {
  return (
    <div className="min-h-dvh bg-page text-ink">
      <header className="border-b border-divider px-8 py-6 flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Internal</p>
          <h1 className="font-display text-3xl">
            Styleguide
          </h1>
        </div>
        <ThemeToggle />
      </header>
      <main className="px-8 py-10 max-w-5xl mx-auto space-y-16">
        <section id="overview">
          <p className="text-ink-muted">
            This page renders every design-system primitive in every variant +
            state, in both light and dark. Each primitive section gets added as
            it ships (Phase 1+).
          </p>
        </section>
        <section id="heading" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Heading</p>
          <Heading level={1}>Display — Net EV per year</Heading>
          <Heading level={2}>Headline — Wallet · Default Scenario</Heading>
          <Heading level={3}>Title — Sapphire Reserve</Heading>
          <Heading level={4}>Subtitle — Annual fee waived</Heading>
        </section>
        <section id="eyebrow" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Eyebrow</p>
          <Eyebrow>Net EV / yr</Eyebrow>
          <Eyebrow accent>With accent rule</Eyebrow>
        </section>
        <section id="money" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Money</p>
          <div className="space-y-2">
            <div>Inline mono: <Money value={1284.50} /></div>
            <div>Inline non-mono: <Money value={1284} mono={false} /></div>
            <div>Tone auto positive: <Money value={842} tone="auto" /></div>
            <div>Tone auto negative: <Money value={-795} tone="auto" /></div>
            <div>Precision 0: <Money value={1284.5} precision={0} /></div>
            <div>Precision 2: <Money value={1284} precision={2} /></div>
          </div>
          <div>Feature size:</div>
          <Money value={3418} feature />
        </section>
        <section id="points" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Points</p>
          <div className="space-y-2">
            <div>Compact: <Points value={125000} /></div>
            <div>Exact: <Points value={125000} exact /></div>
            <div>With unit: <Points value={125000} unit="UR" /></div>
            <div>Feature: <Points value={125000} feature unit="UR" /></div>
          </div>
        </section>
        <section id="stat" className="space-y-6">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Stat</p>
          <Stat
            label="Net EV / yr"
            value={<Money value={3418} feature />}
            caption="over 7 years, default scenario"
            accent
          />
          <div className="flex justify-between border-t border-divider pt-4">
            <Stat label="Earn" value={<Money value={2134} />} />
            <Stat label="Credits" value={<Money value={700} />} />
            <Stat label="Annual fee" value={<Money value={-795} tone="auto" />} align="right" />
          </div>
        </section>
        <section id="surface" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Surface</p>
          <div className="grid grid-cols-3 gap-4">
            <Surface variant="panel">Panel (default)</Surface>
            <Surface variant="inset">Inset</Surface>
            <Surface variant="bare">Bare</Surface>
          </div>
          <Surface elevated>Elevated panel</Surface>
        </section>
        <section id="modal" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Modal</p>
          <ModalDemo />
        </section>
        <section id="popover" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Popover</p>
          <div className="flex gap-3">
            <Popover
              side="bottom"
              trigger={({ onClick, ref }) => (
                <button
                  ref={ref as React.RefObject<HTMLButtonElement>}
                  onClick={onClick}
                  className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink"
                >
                  Bottom popover
                </button>
              )}
            >
              <p className="text-sm text-ink">
                Popover anchored bottom. Click outside or press Esc to dismiss.
              </p>
            </Popover>
            <Popover
              side="right"
              portal
              trigger={({ onClick, ref }) => (
                <button
                  ref={ref as React.RefObject<HTMLButtonElement>}
                  onClick={onClick}
                  className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink"
                >
                  Right (portal)
                </button>
              )}
            >
              <p className="text-sm text-ink">Portaled — escapes overflow:hidden parents.</p>
            </Popover>
          </div>
        </section>
        <section id="drawer" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Drawer</p>
          <DrawerDemo />
        </section>
        <section id="toast" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Toast</p>
          <ToastDemo />
        </section>
        <section id="tooltip" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Tooltip</p>
          <div className="flex gap-3">
            <Tooltip label="Top tooltip">
              <button className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink">
                Hover me
              </button>
            </Tooltip>
            <Tooltip label="Right tooltip" side="right">
              <button className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink">
                Hover (right)
              </button>
            </Tooltip>
          </div>
        </section>
      </main>
    </div>
  )
}
