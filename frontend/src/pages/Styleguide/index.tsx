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
import { Button } from '../../components/ui/Button'
import { Input } from '../../components/ui/Input'
import { Field } from '../../components/ui/Field'
import { Select } from '../../components/ui/Select'
import { Checkbox } from '../../components/ui/Checkbox'
import { Toggle } from '../../components/ui/Toggle'
import { DataTable } from '../../components/ui/DataTable'
import { Badge } from '../../components/ui/Badge'
import { Tabs } from '../../components/ui/Tabs'
import { CardTile } from '../../components/cards/CardTile'
import { CategoryRow } from '../../components/cards/CategoryRow'
import { CreditRow } from '../../components/cards/CreditRow'
import { IssuerRuleBanner } from '../../components/cards/IssuerRuleBanner'

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

function TabsDemo() {
  const [active, setActive] = useState<'wallet' | 'spending' | 'settings'>('wallet')
  return (
    <Tabs
      items={[
        { id: 'wallet', label: 'Wallet' },
        { id: 'spending', label: 'Spending' },
        { id: 'settings', label: 'Settings' },
      ]}
      active={active}
      onChange={setActive}
    />
  )
}

/**
 * Internal styleguide route — gated by VITE_SHOW_STYLEGUIDE=1.
 * Each primitive section gets registered here as it lands. The id-anchored
 * sections mean you can deep-link to a primitive: /styleguide#modal.
 */
export default function Styleguide() {
  return (
    <div className="h-full overflow-y-auto bg-page text-ink">
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
        <section id="button" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Button</p>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary">Primary</Button>
            <Button variant="warn">Warn</Button>
            <Button variant="secondary">Secondary</Button>
            <Button variant="ghost">Ghost</Button>
            <Button variant="link">Link</Button>
            <Button variant="primary" loading>Loading</Button>
            <Button variant="primary" disabled>Disabled</Button>
          </div>
          <div className="flex items-center gap-3">
            <Button size="sm">Small</Button>
            <Button size="md">Medium</Button>
            <Button size="lg">Large</Button>
          </div>
        </section>
        <section id="input" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Input</p>
          <div className="space-y-3 max-w-sm">
            <Input placeholder="Default state" />
            <Input placeholder="Disabled" disabled />
            <Input placeholder="Invalid" invalid defaultValue="bad@value" />
            <Input type="number" placeholder="Number" />
          </div>
        </section>
        <section id="field" className="space-y-4 max-w-sm">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Field</p>
          <Field label="Annual spend" hint="Wallet-wide total in USD" required>
            <Input placeholder="120,000" />
          </Field>
          <Field label="Email" error="Not a valid email">
            <Input defaultValue="bad" />
          </Field>
        </section>
        <section id="select" className="space-y-4 max-w-sm">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Select</p>
          <Select defaultValue="">
            <option value="" disabled>Pick a scenario</option>
            <option>Default</option>
            <option>What-if A</option>
            <option>What-if B</option>
          </Select>
        </section>
        <section id="checkbox" className="space-y-3">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Checkbox</p>
          <Checkbox label="Include SUBs" />
          <Checkbox label="Checked" defaultChecked />
          <Checkbox label="Indeterminate" indeterminate />
          <Checkbox label="Disabled" disabled />
        </section>
        <section id="toggle" className="space-y-3">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Toggle</p>
          <Toggle label="Include SUBs" />
          <Toggle label="On" defaultChecked />
          <Toggle label="Disabled" disabled />
        </section>
        <section id="datatable" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">DataTable</p>
          <DataTable>
            <DataTable.Head>
              <DataTable.Row>
                <DataTable.HeadCell>Card</DataTable.HeadCell>
                <DataTable.HeadCell numeric>Net EV / yr</DataTable.HeadCell>
              </DataTable.Row>
            </DataTable.Head>
            <DataTable.Body>
              <DataTable.Row>
                <DataTable.Cell>Sapphire Reserve</DataTable.Cell>
                <DataTable.Cell numeric>$1,284.50</DataTable.Cell>
              </DataTable.Row>
              <DataTable.Row>
                <DataTable.Cell>Amex Platinum</DataTable.Cell>
                <DataTable.Cell numeric>$842.00</DataTable.Cell>
              </DataTable.Row>
            </DataTable.Body>
          </DataTable>
        </section>
        <section id="badge" className="space-y-3">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Badge</p>
          <div className="flex flex-wrap gap-2">
            <Badge>Visa</Badge>
            <Badge tone="accent">Top pick</Badge>
            <Badge tone="pos">Earned</Badge>
            <Badge tone="neg">Expired</Badge>
            <Badge tone="warn">Pending</Badge>
            <Badge tone="info">No SUB</Badge>
          </div>
        </section>
        <section id="tabs" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Tabs</p>
          <TabsDemo />
        </section>
        <section id="cardtile" className="space-y-4 max-w-md">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">CardTile</p>
          <CardTile
            issuer="Chase"
            network="Visa Infinite"
            cardName="Sapphire Reserve"
            netEvAnnual={1284.5}
            badge={{ tone: 'accent', label: 'Top pick' }}
            breakdown={[
              { label: 'Earn', value: <Money value={2134} mono={false} /> },
              { label: 'Credits', value: <Money value={700} mono={false} /> },
              { label: 'AF', value: <Money value={-795} mono={false} tone="auto" /> },
            ]}
          />
        </section>
        <section id="categoryrow" className="space-y-1 max-w-2xl">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">CategoryRow</p>
          <div className="grid grid-cols-[1fr_auto_auto_auto] gap-x-4 text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint border-b border-divider pb-2">
            <span>Category</span>
            <span className="text-right">Mult</span>
            <span className="text-right">Spend</span>
            <span className="text-right">Earn</span>
          </div>
          <CategoryRow category="Travel" multiplier={3} allocatedSpend={12000} earn={36000} />
          <CategoryRow category="Dining" multiplier={3} allocatedSpend={8000} earn={24000} caption="Restaurants & food delivery" />
          <CategoryRow category="All Other" multiplier={1} allocatedSpend={45000} earn={45000} />
        </section>
        <section id="creditrow" className="space-y-1 max-w-md">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">CreditRow</p>
          <CreditRow name="$300 travel credit" valuation={300} note="Statement credit, recurring annually" />
          <CreditRow name="$200 hotel credit" valuation={150} note="Counted at $150 — partial value" />
          <CreditRow name="Lyft credit" valuation={0} zeroedOut note="User-zeroed" />
        </section>
        <section id="issuerrulebanner" className="space-y-3 max-w-xl">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">IssuerRuleBanner</p>
          <IssuerRuleBanner rule="Chase 5/24" message="You've opened 6 personal cards in the last 24 months. Adding this card may be auto-declined." />
          <IssuerRuleBanner rule="Amex 1/90" message="Last Amex application was 42 days ago — wait 48 more days before applying." />
        </section>
      </main>
    </div>
  )
}
