# WalletCardModal Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the 1,961-line `WalletCardModal` (Lifecycle / Bonuses & Fees / Credits / Categories tabs) to the soft-dashboard direction. Plan 4c — the **final** sub-plan of the app-wide redesign. Spec: `docs/superpowers/specs/2026-05-01-roadmap-tool-redesign-design.md` Section 9.

**Architecture:** Visual restyle only. The modal's data flow (form state, validation, mutations, three-tier overlay/instance/library resolution, credit-search dropdown, category-priority claim-conflict logic) all stay untouched. Chrome and form-field language are replaced with the foundation primitives (Plans 1+3): `Modal`, `ModalHeader`/`Body`/`Footer`, `Heading`, `Field`, `Input`, `Select`, `Button`, `Tabs`, `Toggle`, `Checkbox`, `Badge`. Includes a small follow-up from Plan 4b's review: convert the raw `<button>` Delete in `DeleteCardWarningModal` to use the `Button` primitive.

**Tech Stack:** React + Vite + Tailwind v4. Foundation primitives in `frontend/src/components/ui/`. Build: `cd frontend && npm run build`. Lint: `cd frontend && npm run lint`. Dev: `cd frontend && npm run dev`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `frontend/src/components/cards/WalletCardModal.tsx` | The 1,961-line modal. Modified across 6 logical sections (header, tab bar, Lifecycle, Bonuses, Credits, Priority) but not restructured — same hooks, same prop signatures, same callback contracts. |
| `frontend/src/components/cards/DeleteCardWarningModal.tsx` | (~49 lines, already restyled in Plan 4b) Tiny follow-up: convert the raw `<button>` Delete to use the `Button` primitive with an inline `bg-neg text-on-accent` className override. |

---

## Task 1: Modal header + footer chrome

The current header is a custom band with icon-only buttons (Reset / Delete / Save) that combine the actions into a small toolbar at top-right. Per spec 9.1, switch to a proper modal pattern: header with title + chip row + small Delete icon-button only; footer with Cancel + Save buttons. Reset stays as a small text button next to the Save in the footer for overlay context.

**Files:**
- Modify: `frontend/src/components/cards/WalletCardModal.tsx`

- [ ] **Step 1: Replace the header band**

In `frontend/src/components/cards/WalletCardModal.tsx`, find the header `<div className="flex-shrink-0 px-6 pt-6 pb-4 border-b border-divider">` (around line 1081). Replace the entire `<div>` (from that opening through its closing) with `<ModalHeader>` from the foundation primitive. Inside it, render:

```tsx
<ModalHeader>
  <div className="flex items-start gap-3">
    <div className="min-w-0 flex-1">
      <Heading level={3}>{title}</Heading>
      <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
        {lib?.network_tier && (
          <Badge tone="neutral">{lib.network_tier.name}</Badge>
        )}
        {lib?.issuer && (
          <Badge tone="neutral">{lib.issuer.name}</Badge>
        )}
        {!isAddFlow && (
          isOverlayContext ? (
            <Badge tone="warn">Owned · scenario edit</Badge>
          ) : isFuture ? (
            <Badge tone="accent">Future</Badge>
          ) : (
            <Badge tone="neutral">Owned</Badge>
          )
        )}
      </div>
    </div>
    {onDeleteHandler && (
      <button
        type="button"
        disabled={isLoading}
        onClick={onDeleteHandler}
        className="shrink-0 w-8 h-8 inline-flex items-center justify-center rounded-md text-ink-faint hover:text-neg hover:bg-neg/10 disabled:opacity-50 transition-colors"
        title={isFuture ? 'Delete future card' : 'Delete card'}
        aria-label="Delete card"
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <polyline points="3 6 5 6 21 6" />
          <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
        </svg>
      </button>
    )}
  </div>
</ModalHeader>
```

Drop the icon-only Save button at line 1133–1146 — Save moves to the footer (Step 4 below). Drop the icon-only Reset button at line 1107–1116 — Reset moves to the footer too.

Add the `ModalHeader`, `ModalBody`, `ModalFooter`, `Heading`, `Badge` imports at the top of the file if not already present:

```tsx
import { ModalHeader, ModalBody, ModalFooter } from '../ui/Modal'
import { Heading } from '../ui/Heading'
import { Badge } from '../ui/Badge'
```

(`Modal` is already imported. Verify the relative path `../ui/Modal` matches the existing `Modal` import — same directory.)

- [ ] **Step 2: Update the overlay-context band**

The overlay-context warning band at line 1151–1155 (`Editing in this scenario only — your owned card stays unchanged.`) is now redundant with the new "Owned · scenario edit" badge in the header. Drop the band entirely.

- [ ] **Step 3: Wrap the body in `<ModalBody>`**

Find the body `<div className={\`px-6 pt-3 flex-1 min-h-0 flex flex-col ${activeTab === 'credits' ? 'pb-0' : 'pb-4'}\`}>` (around line 1198). Replace its outer `<div>` with the foundation `<ModalBody>` primitive:

```tsx
<ModalBody className={`flex-1 min-h-0 flex flex-col ${activeTab === 'credits' ? '!pb-0' : ''}`}>
  ... existing children ...
</ModalBody>
```

(Foundation `ModalBody` already supplies `px-5 py-5` paddings from Plan 1. The `!pb-0` override is for the Credits tab which has its own scroll affordance and shouldn't add padding at the bottom.)

- [ ] **Step 4: Add a `<ModalFooter>` with Cancel + Save (+ Reset)**

After the body's closing `</ModalBody>`, but before the closing `</Modal>`, add:

```tsx
<ModalFooter>
  {!isAddFlow && isOverlayContext && onClearOverlay && (
    <Button
      type="button"
      variant="ghost"
      size="sm"
      disabled={isLoading || !resolvedCard?.is_overlay_modified}
      onClick={onClearOverlay}
      className="!text-warn hover:!text-warn"
    >
      Reset overlay
    </Button>
  )}
  <div className="flex-1" />
  <Button
    type="button"
    variant="secondary"
    size="sm"
    disabled={isLoading}
    onClick={onClose}
  >
    Cancel
  </Button>
  <Button
    type="button"
    variant="primary"
    size="sm"
    disabled={saveDisabled}
    loading={isLoading}
    onClick={() => void handlePrimary()}
  >
    {isAddFlow ? 'Add card' : 'Save changes'}
  </Button>
</ModalFooter>
```

If the modal is in `isAddFlow` mode AND the active tab isn't the last in `tabOrder`, the footer can also render the existing "Next →" button (currently rendered as its own footer block at line 1942). Move that "Next" affordance INTO the new `ModalFooter`, replacing the standalone block. The pattern: when add-flow + not on last tab, render Next instead of (or alongside) Save. The simplest approach: have Next push Save off the right edge by reusing the same right-edge slot. Specifically:

```tsx
{isAddFlow && hasNextTab ? (
  <Button
    type="button"
    variant="primary"
    size="sm"
    disabled={isLoading}
    onClick={() => setActiveTab(tabOrder[currentTabIndex + 1])}
  >
    Next →
  </Button>
) : (
  <Button
    type="button"
    variant="primary"
    size="sm"
    disabled={saveDisabled}
    loading={isLoading}
    onClick={() => void handlePrimary()}
  >
    {isAddFlow ? 'Add card' : 'Save changes'}
  </Button>
)}
```

Delete the old standalone "Next" footer block at line 1942–1958.

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 6: Visual QA** — skip; controller will do this.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/cards/WalletCardModal.tsx
git commit -m "WalletCardModal: foundation Modal chrome with proper header + footer"
```

---

## Task 2: Tab bar — switch to foundation Tabs primitive

The current tab bar at line 1157–1195 is a hand-rolled horizontal underline-tab implementation. Switch to the foundation `Tabs` primitive (already used in Plan 4a's RoadmapTool tabs and elsewhere).

**Files:**
- Modify: `frontend/src/components/cards/WalletCardModal.tsx`

- [ ] **Step 1: Replace the tab bar**

Find the `{(isAddFlow || lib) && (` block and the entire `<div className="flex-shrink-0 flex gap-1 px-6 border-b border-divider">` it wraps (around line 1158–1195). Replace with:

```tsx
{(isAddFlow || lib) && (
  <div className="flex-shrink-0 px-5 border-b border-divider">
    <Tabs
      items={[
        { id: 'lifecycle' as const, label: 'Lifecycle' },
        ...(cardSelected
          ? [
              { id: 'bonuses' as const, label: 'Bonuses & Fees' },
              {
                id: 'credits' as const,
                label: (
                  <>
                    Credits
                    {Object.keys(selectedCredits).length > 0 && (
                      <span className="ml-1.5 text-[10.5px] font-medium bg-surface-2 text-ink-faint px-1.5 py-0.5 rounded-full tnum-mono">
                        {Object.keys(selectedCredits).length}
                      </span>
                    )}
                  </>
                ),
              },
            ]
          : []),
        ...(cardSelected && categoryTabEnabled
          ? [
              {
                id: 'priority' as const,
                label: (
                  <>
                    Categories
                    {priorityUserCatCount > 0 && (
                      <span className="ml-1.5 text-[10.5px] font-medium bg-surface-2 text-ink-faint px-1.5 py-0.5 rounded-full tnum-mono">
                        {priorityUserCatCount}
                      </span>
                    )}
                  </>
                ),
              },
            ]
          : []),
      ]}
      active={activeTab}
      onChange={(id) => setActiveTab(id as typeof activeTab)}
    />
  </div>
)}
```

Add the `Tabs` import at the top of the file:

```tsx
import { Tabs } from '../ui/Tabs'
```

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA** — skip; controller will do this.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/cards/WalletCardModal.tsx
git commit -m "WalletCardModal: switch tab bar to foundation Tabs primitive"
```

---

## Task 3: Lifecycle tab — acquisition radio + dates

The Lifecycle tab (around line 1207–1462) has a card picker, an acquisition mode radiogroup, and the date fields. Spec 9.3 wants the Acquisition radio as a stack of selectable cards with title + description; date fields use the Field/Input language.

**Files:**
- Modify: `frontend/src/components/cards/WalletCardModal.tsx`

- [ ] **Step 1: Read the Lifecycle tab block**

Read the full Lifecycle tab from line ~1207 to ~1462. Identify these sub-sections in order:
- Card picker (only visible in `isAddFlow`)
- Acquisition mode radio (Fresh open / Product change)
- Opening date input
- Conditional Product change date (when Acquisition = Product change)
- Conditional "Changing from" instance picker (when Acquisition = Product change)
- Close date (optional)
- A few read-only displays

- [ ] **Step 2: Restyle the Acquisition radiogroup**

Find the Acquisition radiogroup `<div role="radiogroup" className="flex flex-col bg-surface-2/30 border border-divider rounded-lg overflow-hidden">` (around line 1222). Replace with a stack of selectable cards:

```tsx
<div className="space-y-1.5">
  <p className="text-xs font-medium text-ink-muted">Acquisition</p>
  <div role="radiogroup" aria-label="Acquisition" className="space-y-2">
    {[
      {
        value: 'fresh' as const,
        label: 'Fresh open',
        desc: 'New card from this issuer. Counts toward 5/24 and other velocity rules.',
      },
      {
        value: 'product_change' as const,
        label: 'Product change',
        desc: 'Switching from another card. Account number is preserved; doesn\'t count as a new app.',
      },
    ].map((opt) => {
      const selected = acquisitionType === opt.value
      return (
        <button
          key={opt.value}
          type="button"
          role="radio"
          aria-checked={selected}
          onClick={() => setAcquisitionType(opt.value)}
          className={`w-full text-left flex items-start gap-3 px-3 py-3 rounded-lg border transition-colors ${
            selected
              ? 'border-accent bg-accent-soft'
              : 'border-divider hover:border-divider-strong bg-surface'
          }`}
        >
          <span
            aria-hidden
            className={`mt-0.5 shrink-0 w-3.5 h-3.5 rounded-full border transition-colors ${
              selected ? 'border-accent bg-accent' : 'border-divider-strong'
            }`}
          />
          <span className="min-w-0">
            <span className={`block text-sm font-medium ${selected ? 'text-accent' : 'text-ink'}`}>
              {opt.label}
            </span>
            <span className="block text-[11px] text-ink-faint mt-0.5">{opt.desc}</span>
          </span>
        </button>
      )
    })}
  </div>
</div>
```

(Replace whatever variable name the existing code uses for the current acquisition value — `acquisitionType` is a likely name; keep whatever is in scope.)

- [ ] **Step 3: Restyle date inputs**

Find the date input fields (Opening date, Product change date, Close date). Wrap each with the foundation `Field` primitive and use `Input` for the actual input:

```tsx
<Field label="Opening date">
  <Input
    type="date"
    value={openingDate ?? ''}
    onChange={(e) => setOpeningDate(e.target.value)}
  />
</Field>
```

(Use `Field`'s `hint` prop where the existing code has helper text below an input.)

For the two-column layout (Opening date + Close date side-by-side), wrap them in:

```tsx
<div className="grid grid-cols-2 gap-3">
  <Field label="Opening date" ...>...</Field>
  <Field label="Close date" hint="Leave empty if still active.">...</Field>
</div>
```

Add the `Field`, `Input`, `Select` imports at the top of the file if not present:

```tsx
import { Field } from '../ui/Field'
import { Input } from '../ui/Input'
import { Select } from '../ui/Select'
```

- [ ] **Step 4: Restyle the card-picker (add-flow only)**

If `isAddFlow` is true, the Lifecycle tab includes a `<select>` to pick which library card to add. Wrap that with `Field` + `Select`:

```tsx
<Field label="Card" hint="Pick the card you're adding">
  <Select value={selectedCardId ?? ''} onChange={(e) => setSelectedCardId(Number(e.target.value))}>
    <option value="">Choose a card…</option>
    {libraryCards.map((card) => (
      <option key={card.id} value={card.id}>{card.card_name}</option>
    ))}
  </Select>
</Field>
```

(Use whatever variable names match the existing code.)

- [ ] **Step 5: Restyle "Changing from" instance picker**

When Acquisition is Product change, a "Changing from" select appears. Wrap with `Field` + `Select` similarly.

- [ ] **Step 6: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 7: Visual QA** — skip; controller will do this.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/components/cards/WalletCardModal.tsx
git commit -m "WalletCardModal/lifecycle: selectable-card radio + Field/Input dates"
```

---

## Task 4: Bonuses & Fees tab

The Bonuses tab (around line 1463–1555) has SUB inputs (min spend / days / bonus pts), recurring vs first-year-only annual bonus, percentage bonus, multipliers list, top-N group editor.

**Files:**
- Modify: `frontend/src/components/cards/WalletCardModal.tsx`

- [ ] **Step 1: Read the Bonuses tab block**

Read from line ~1463 to ~1555. Note the input fields (text/number `<input>` with custom classes) and the toggle (recurring vs first-year-only).

- [ ] **Step 2: Restyle inputs to use Field + Input**

For each numeric input, wrap with `Field`:

```tsx
<Field label="Min spend" hint="Minimum spend to earn the SUB.">
  <Input type="number" value={subMinSpend ?? ''} onChange={(e) => setSubMinSpend(e.target.value)} />
</Field>
```

For the SUB row (Min spend + Days + Bonus pts), use a 3-column grid:

```tsx
<div className="grid grid-cols-3 gap-3">
  <Field label="Min spend">...</Field>
  <Field label="Days">...</Field>
  <Field label="Bonus pts">...</Field>
</div>
```

- [ ] **Step 3: Restyle the recurring/first-year-only toggle**

Find the recurring vs first-year-only segmented control. Replace with the same idiom used by the SUBs toggle in `WalletSummaryStats` (Plan 4a):

```tsx
<div className="space-y-1.5">
  <p className="text-xs font-medium text-ink-muted">Annual bonus mode</p>
  <div role="radiogroup" className="inline-flex bg-divider rounded-md p-0.5 text-xs font-medium">
    <button
      type="button"
      role="radio"
      aria-checked={!annualBonusFirstYearOnly}
      onClick={() => setAnnualBonusFirstYearOnly(false)}
      className={`px-3 py-1 rounded transition-colors ${
        !annualBonusFirstYearOnly
          ? 'bg-surface text-ink shadow-card'
          : 'text-ink-muted hover:text-ink'
      }`}
    >
      Recurring
    </button>
    <button
      type="button"
      role="radio"
      aria-checked={annualBonusFirstYearOnly}
      onClick={() => setAnnualBonusFirstYearOnly(true)}
      className={`px-3 py-1 rounded transition-colors ${
        annualBonusFirstYearOnly
          ? 'bg-surface text-ink shadow-card'
          : 'text-ink-muted hover:text-ink'
      }`}
    >
      First year only
    </button>
  </div>
</div>
```

- [ ] **Step 4: Restyle multipliers list + top-N groups**

The multipliers list (per-category multiplier rows) and the top-N group editor each have their own chrome. Replace any heavy backgrounds (`bg-surface-2`-with-borders) with `bg-surface-2/40` for the inner section containers, and wrap individual rows in soft hairline-divided chrome (matching Plan 3's CategoryWeightEditor).

Specifically, find any `<div>` with `bg-surface-2 border border-divider rounded-lg` chrome — keep the rounding but switch to `bg-surface-2/40` and drop the border (the parent `ModalBody` already has clear edges).

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 6: Visual QA** — skip; controller will do this.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/cards/WalletCardModal.tsx
git commit -m "WalletCardModal/bonuses: Field/Input inputs, segmented annual-bonus toggle"
```

---

## Task 5: Credits tab

The Credits tab (around line 1556–1860) is the biggest tab — a list of credits with name + value + flags (excludes_first_year, is_one_time), plus a credit-search dropdown to add new credits. Spec 9.5 wants each credit as a small soft-card with hairline-divided flag row.

**Files:**
- Modify: `frontend/src/components/cards/WalletCardModal.tsx`

- [ ] **Step 1: Read the Credits tab block**

Read from line ~1556 to ~1860. Identify:
- The list of credit rows (each with name, source line, value input, flag checkboxes)
- The credit-search dropdown / + Add credit affordance
- Any conditional UI for system vs user-created credits

- [ ] **Step 2: Restyle each credit row**

Per spec 9.5, each credit becomes a small card:

```tsx
<div className="bg-surface-2/40 rounded-lg p-3">
  <div className="flex items-start justify-between gap-3">
    <div className="min-w-0 flex-1">
      <p className="text-sm font-medium text-ink truncate">{creditName}</p>
      <p className="text-[11px] text-ink-faint mt-0.5">
        {sourceLine /* "From <issuer> library default" or "Custom · only on this card" */}
      </p>
    </div>
    <div className="shrink-0 w-24">
      <Input
        type="number"
        value={creditValue}
        onChange={...}
        className="text-right"
      />
    </div>
  </div>
  <div className="mt-3 pt-3 border-t border-divider/60 flex flex-wrap gap-4">
    <Checkbox
      checked={excludesFirstYear}
      onChange={...}
      label="Excludes first year"
    />
    <Checkbox
      checked={isOneTime}
      onChange={...}
      label="One-time only"
    />
  </div>
</div>
```

(Use foundation `Checkbox` from `../ui/Checkbox` instead of any custom `<input type="checkbox">`. Add the import.)

For user-created credits, replace any existing "owner" badge with a foundation `Badge tone="accent"` reading `Custom`.

- [ ] **Step 3: Restyle the "Add credit" affordance**

Find the credit-search dropdown trigger and any "Add credit" button. Replace its className with a dashed-border affordance:

```tsx
<button
  type="button"
  onClick={...}
  className="w-full flex items-center justify-center gap-1.5 py-3 text-sm font-medium text-accent hover:text-accent border-2 border-dashed border-divider hover:border-accent rounded-lg transition-colors"
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
    <line x1="12" y1="5" x2="12" y2="19" />
    <line x1="5" y1="12" x2="19" y2="12" />
  </svg>
  Add credit
</button>
```

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA** — skip; controller will do this.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/cards/WalletCardModal.tsx
git commit -m "WalletCardModal/credits: soft-card credits with foundation Checkbox flags"
```

---

## Task 6: Priority (Categories) tab

The Priority tab (around line 1861–1936) has a list of user spend categories with checkboxes for "pin to this card." Most rows are enabled; some are disabled with a "Claimed By Another Card" label.

**Files:**
- Modify: `frontend/src/components/cards/WalletCardModal.tsx`

- [ ] **Step 1: Read the Priority tab block**

Read from line ~1861 to ~1936.

- [ ] **Step 2: Restyle the category checkbox rows**

Each `<li>` with a checkbox + category name + optional disabled hint becomes a small flex row:

```tsx
<li>
  <label
    className={`flex items-center gap-2 py-2 px-2 rounded transition-colors ${
      disabled ? 'text-ink-faint cursor-not-allowed' : 'text-ink hover:bg-surface-2/40 cursor-pointer'
    }`}
  >
    <Checkbox
      checked={checked}
      disabled={disabled}
      onChange={...}
    />
    <span className="flex-1 min-w-0 truncate text-sm">{userCat.name}</span>
    {disabled && (
      <span className="text-[11px] text-ink-faint shrink-0">Claimed by another card</span>
    )}
  </label>
</li>
```

(Replace any custom checkbox markup with the foundation `Checkbox`.)

- [ ] **Step 3: Restyle the section title and any wrapping ul**

The `<ul>` wrapping the category list and the section title above it should use the eyebrow recipe:

```tsx
<p className="text-[11px] uppercase tracking-wider text-ink-faint font-semibold mb-2">
  Pin categories to this card
</p>
<ul className="divide-y divide-divider/60 -mx-2">
  ...rows...
</ul>
```

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA** — skip; controller will do this.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/cards/WalletCardModal.tsx
git commit -m "WalletCardModal/priority: foundation Checkbox rows, eyebrow section title"
```

---

## Task 7: Form-error pill + DeleteCardWarningModal cleanup

Two small follow-ups in one task.

**Files:**
- Modify: `frontend/src/components/cards/WalletCardModal.tsx`
- Modify: `frontend/src/components/cards/DeleteCardWarningModal.tsx`

- [ ] **Step 1: Tighten the form-error pill**

Find the `<p className="text-xs text-neg bg-neg/10 border border-neg/50 rounded-lg mx-0 mt-3 px-3 py-2">{formError}</p>` in `WalletCardModal.tsx` (around line 1931). Replace with:

```tsx
<div className="mt-3 px-3 py-2 rounded-md bg-neg/10 border border-neg/30 text-[11px] text-neg flex items-start gap-2">
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" className="shrink-0 mt-0.5">
    <circle cx="12" cy="12" r="10" />
    <line x1="12" y1="8" x2="12" y2="12" />
    <line x1="12" y1="16" x2="12.01" y2="16" />
  </svg>
  <span>{formError}</span>
</div>
```

(Adds an inline error icon and tightens the border tone to match the foundation tonal-pill pattern.)

- [ ] **Step 2: DeleteCardWarningModal — convert raw button to Button primitive**

In `frontend/src/components/cards/DeleteCardWarningModal.tsx`, find the raw `<button>` Delete button (around line 42 from Plan 4b). Replace it with the foundation `Button` primitive plus a className override for the neg tone:

```tsx
<Button
  type="button"
  variant="primary"
  onClick={onConfirm}
  loading={isLoading}
  className="!bg-neg !text-on-accent hover:!opacity-90"
>
  Delete
</Button>
```

(The `!`-prefixed Tailwind classes override the primary Button's default `bg-accent` styling. This preserves the Button's loading spinner, focus ring, and disabled states while keeping the neg tone for the destructive action.)

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA** — skip; controller will do this.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/cards/WalletCardModal.tsx frontend/src/components/cards/DeleteCardWarningModal.tsx
git commit -m "WalletCardModal: refine form-error pill; DeleteCardWarning: use Button primitive"
```

---

## Task 8: Final visual QA

End-to-end QA in light + dark before merge. After this lands, the entire app-wide redesign is complete.

**Files:**
- (Verify only.)

- [ ] **Step 1: Run lint**

Run: `cd frontend && npm run lint`
Expected: same 3 pre-existing findings (`Button/index.tsx:27`, `CategoryWeightEditor.tsx:39`, `RoadmapTool/index.tsx:737`). NO new findings.

- [ ] **Step 2: Production build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Walk through the WalletCardModal in `/profile` (Wallet tab)**

Click an existing card to open the modal in `edit-owned` mode. Confirm:
- Header has Heading-level-3 title, network/issuer chips, status badge, small Delete icon-button on the right.
- Tab bar uses foundation Tabs with accent underline + count badges on Credits and Categories.
- Body uses ModalBody padding (20px).
- Footer has Cancel (secondary) + Save (primary) buttons. Reset overlay button only renders for scenario-overlay edits.
- Lifecycle tab: Acquisition radio is a stack of selectable cards with title + description; selected card has accent border + accent-soft tint. Date inputs use Field + Input.
- Bonuses tab: SUB row 3-column grid; recurring vs first-year-only segmented toggle (matches the SUBs toggle idiom in the page hero).
- Credits tab: each credit is a soft-card with name + value input + flag checkboxes below a hairline divider. "+ Add credit" is a dashed-border affordance.
- Priority tab: category list with foundation Checkboxes; disabled rows show "Claimed by another card" inline.

- [ ] **Step 4: Walk through `/roadmap-tool` modal flows**

Click a future card in the timeline to edit; click "Add card" to add a future card; click an owned card row to edit-overlay. Each opens the modal in its respective mode. Confirm the chrome / tabs / form fields match.

- [ ] **Step 5: Walk through dark mode**

Toggle theme. Re-walk the modal in light mode → dark mode for at least one card. Confirm:
- All form inputs readable on dark surface.
- Accent crimson visible on tab underline + acquisition selected state.
- Neg-tinted form-error pill readable.
- Modal shadow visible against the dark page underlay.

- [ ] **Step 6: Trigger DeleteCardWarningModal**

Click the Delete icon-button on the modal header → DeleteCardWarningModal opens. Delete button now uses the Button primitive with neg styling. Cancel uses secondary Button. Click Cancel — closes both modals correctly.

- [ ] **Step 7: Commit a final QA marker**

```bash
git commit --allow-empty -m "WalletCardModal: visual QA pass complete (light + dark, all 4 tabs)"
```

---

## Plan complete

After Task 8, the entire app-wide soft-dashboard redesign is shipped end-to-end:

- ✅ Plan 1: Foundation (tokens + 25 primitives)
- ✅ Plan 2: App shell + Home
- ✅ Plan 3: Profile + retroactive borders
- ✅ Plan 4a: Roadmap Tool page shell
- ✅ Plan 4b: Roadmap Tool content (Timeline, Spend, popovers, modals)
- ✅ Plan 4c: WalletCardModal (this plan)

The entire frontend is in the new soft-dashboard direction.
