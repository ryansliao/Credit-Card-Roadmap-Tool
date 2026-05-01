# Profile Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Profile settings page (`pages/Profile/`) — its shell, all four tabs (Wallet, Spending, Appearance, User Settings), and the inline `CategoryWeightEditor` — to match the soft-dashboard direction. Plan 3 of 4 for the app-wide redesign. Spec: `docs/superpowers/specs/2026-05-01-roadmap-tool-redesign-design.md` Section 5.

**Architecture:** Visual restyle only — auth, react-query plumbing, mutation flows, the `WalletCardModal` and `DeleteCardWarningModal` (already restyled by Plan 1's primitive update + Plan 2's modal chrome) all stay as-is. The shell switches from a left-rail nav with `bg-surface-2`-style row buttons to a left-rail nav with an accent left-rule for the active tab. Each tab's content lives inside a single white shadow-card (replacing the current bordered-`bg-surface` panel). All ad-hoc Tailwind palette colors (`bg-violet-900`, `text-violet-300`, `text-page` on accent fills) are replaced with tokens.

**Tech Stack:** React + Vite + Tailwind v4. Foundation primitives in `frontend/src/components/ui/` (Plan 1) — consume them rather than re-rolling chrome. App shell + Home (Plan 2) already merged. Build: `cd frontend && npm run build`. Dev: `cd frontend && npm run dev`. Lint: `cd frontend && npm run lint`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `frontend/src/pages/Profile/index.tsx` | Shell (~70 lines): left-rail nav + content card. Modified: nav button styling, content-card surface treatment. |
| `frontend/src/pages/Profile/components/WalletTab.tsx` | Owned-card list (~263 lines). Modified: header, row chrome, empty state, PC badge → `info` tone, ad-hoc violet palette removed. |
| `frontend/src/pages/Profile/components/SpendingTab.tsx` | Annual-spend editor (~495 lines). Modified across multiple sections: header, foreign-spend toolbar card, table chrome, inline edit inputs, total row, `HousingTypeEditor` accordion. |
| `frontend/src/pages/Profile/components/CategoryWeightEditor.tsx` | Inline accordion editor (~197 lines). Modified: container, row inputs, footer buttons. |
| `frontend/src/pages/Profile/components/AppearanceTab.tsx` | Theme preference radio (~52 lines). Modified: 3-option row → 3-up grid of preview cards (Light / Dark / System), each showing a tiny mockup of the theme. |
| `frontend/src/pages/Profile/components/SettingsTab.tsx` | Account settings (~164 lines). Modified: profile-card chrome, username edit row inputs, sign-out button switches to filled-`neg` Button primitive variant idiom. |
| `frontend/src/pages/Profile/components/CardPhoto.tsx` | (~23 lines) Token-driven; not modified. Verified only. |
| `frontend/src/pages/Profile/lib/constants.tsx` | TAB list + icons. Not modified. |
| `frontend/src/pages/Profile/hooks/useMyWallet.ts` | Pure data hook. Not modified. |

**Verification convention:** Each task ends with `cd frontend && npm run build` and a manual visual-QA pass in the dev server. Commits after each task.

---

## Task 1: Profile shell — left-rail nav + content card

The current shell wraps the active tab's content in `bg-surface border border-divider rounded-xl` — that border becomes redundant with Plan 1's softer divider tokens, and the nav uses `bg-surface-2` for the active tab which now blends too softly into the new page. Switch to a clean shadow-card content surface, and an accent left-rule for the active nav item.

**Files:**
- Modify: `frontend/src/pages/Profile/index.tsx`

- [ ] **Step 1: Replace the `Profile` return**

In `frontend/src/pages/Profile/index.tsx`, replace the JSX inside the `return (...)` (lines 33–69) with:

```tsx
return (
  <div className="flex h-full min-h-0 max-w-5xl mx-auto w-full gap-6">
    {/* Sidebar */}
    <nav className="w-48 shrink-0 py-2">
      <ul className="space-y-0.5">
        {TABS.map((tab) => {
          const isActive = activeTab === tab.id
          return (
            <li key={tab.id}>
              <button
                type="button"
                onClick={() => setActiveTab(tab.id)}
                className={`relative w-full flex items-center gap-3 pl-4 pr-3 py-2.5 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? 'text-ink bg-surface-2'
                    : 'text-ink-faint hover:text-ink hover:bg-surface-2/60'
                }`}
              >
                {isActive && (
                  <span aria-hidden="true" className="absolute left-0 top-1.5 bottom-1.5 w-0.5 rounded-full bg-accent" />
                )}
                {tab.icon}
                {tab.label}
              </button>
            </li>
          )
        })}
      </ul>
    </nav>

    {/* Content */}
    <div className="flex-1 min-w-0 min-h-0 bg-surface rounded-xl shadow-card p-6 overflow-auto">
      {activeTab === 'wallet' && (
        <WalletTab
          cardInstances={wallet?.card_instances ?? []}
          isLoading={walletLoading}
        />
      )}
      {activeTab === 'spending' && <SpendingTab />}
      {activeTab === 'appearance' && <AppearanceTab />}
      {activeTab === 'settings' && <SettingsTab />}
    </div>
  </div>
)
```

Key changes vs. current:
- Sidebar list item gap drops from `space-y-1` → `space-y-0.5` (tighter rail).
- Active button gets a positioned `<span>` accent left-rule instead of relying solely on `bg-surface-2` (which now reads too quietly against the new neutral page).
- Active background tone stays `bg-surface-2` (tinted hover state for visibility) but inactive uses `text-ink-faint` and `hover:bg-surface-2/60` — quieter than the current `text-ink-muted hover:bg-surface-2/50`.
- Content panel: `bg-surface border border-divider rounded-xl p-6` → `bg-surface rounded-xl shadow-card p-6` (drop the border, lean on shadow-card).
- The loading and unauthenticated-redirect branches at lines 25–31 stay untouched.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA** — skip; controller will do this.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Profile/index.tsx
git commit -m "Profile/shell: shadow-card content panel, accent left-rule active rail"
```

---

## Task 2: WalletTab — header, list, empty state, PC badge

Restyle the WalletTab so its row containers, empty state, and PC badge align with the new tokens. The PC badge is currently a literal violet palette (`bg-violet-900 text-violet-300 border-violet-700`) — switch to the `info`-toned `Badge` primitive which already has the soft dashboard treatment.

**Files:**
- Modify: `frontend/src/pages/Profile/components/WalletTab.tsx`

- [ ] **Step 1: Replace the header section**

In `frontend/src/pages/Profile/components/WalletTab.tsx`, find the `<div className="flex items-center justify-between mb-5 shrink-0">` block (around line 97) and replace it with:

```tsx
<div className="flex items-center justify-between mb-5 shrink-0">
  <div>
    <h2 className="text-ink font-semibold text-xl tracking-tight">My Cards</h2>
    <p className="text-ink-muted text-sm mt-1">Manage the credit cards in your wallet.</p>
  </div>
  <Button
    type="button"
    variant="primary"
    size="sm"
    onClick={() => setWalletCardModal({ mode: 'add' })}
  >
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
      <line x1="12" y1="5" x2="12" y2="19" />
      <line x1="5" y1="12" x2="19" y2="12" />
    </svg>
    Add Card
  </Button>
</div>
```

(Switches `text-xl font-bold` to `font-semibold text-xl tracking-tight` for consistency with the Home/StepCard heading sizing established in Plan 2.)

- [ ] **Step 2: Replace the empty-state**

Find the `<div className="border-2 border-dashed border-divider/60 rounded-xl py-12 px-6 text-center">` block (around line 118) and replace it with:

```tsx
<div className="border-2 border-dashed border-divider rounded-xl py-12 px-6 text-center">
  <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="mx-auto text-ink-faint mb-3">
    <rect x="1" y="4" width="22" height="16" rx="2" ry="2" />
    <line x1="1" y1="10" x2="23" y2="10" />
  </svg>
  <p className="text-ink font-medium text-sm">No cards yet</p>
  <p className="text-ink-faint text-xs mt-1">Add your first credit card to your wallet.</p>
</div>
```

(Drops the `/60` opacity on the dashed border since the new `--color-divider` is already light enough; bumps the empty-state heading from `text-ink-muted` to `text-ink` for clarity.)

- [ ] **Step 3: Replace the card-row `<li>` chrome**

Find the `<li key={inst.id} className="group ..." ...>` block (around line 132) and replace ONLY the `className` (keep all the rest of the JSX):

```tsx
<li
  key={inst.id}
  className="group bg-surface hover:bg-surface-2 rounded-xl shadow-card transition-colors cursor-pointer overflow-hidden mb-2 last:mb-0"
  onClick={() => setWalletCardModal({ mode: 'edit', instance: inst })}
>
```

(Drops the `bg-surface-2/60 ... border border-divider/40 hover:border-divider` chrome in favor of a soft white shadow-card. Replaces the parent `<ul className="space-y-1.5">` rhythm — but `<ul>` keeps its `space-y-1.5` if you keep it, OR change the `<ul>` to plain `<ul>` with no spacing and use the per-item `mb-2` instead. Use `mb-2 last:mb-0` on each item for consistency.)

After this change, find the `<ul className="space-y-1.5">` (around line 127) and replace with:

```tsx
<ul>
```

(No more parent gap; spacing handled per-item.)

- [ ] **Step 4: Replace the PC badge with the info-toned `Badge` primitive**

In the same `<li>`, find the `<span className="text-[10px] font-medium bg-violet-900/60 text-violet-300 border border-violet-700/50 rounded px-1.5 py-0.5 shrink-0" title={...}>PC</span>` block (around line 145) and replace with:

```tsx
<Badge tone="info" title={`Product change · ${inst.product_change_date}`}>PC</Badge>
```

Add the import at the top of the file (next to the existing `Button` import):

```tsx
import { Badge } from '../../../components/ui/Badge'
```

- [ ] **Step 5: Replace the trash icon button**

Find the `<button type="button" className="p-1.5 rounded-lg text-ink-faint hover:text-neg ..." ...>` (around line 196) and replace with:

```tsx
<button
  type="button"
  className="p-1.5 rounded-md text-ink-faint hover:text-neg hover:bg-neg/10 opacity-0 group-hover:opacity-100 transition-opacity disabled:opacity-50 shrink-0"
  aria-label="Remove card"
  title="Remove"
  onClick={(e) => {
    e.stopPropagation()
    setPendingRemoval({ instanceId: inst.id, cardName })
  }}
  disabled={removeCardMutation.isPending}
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6" />
    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2" />
  </svg>
</button>
```

(Switches `rounded-lg` → `rounded-md` to match the foundation icon-button rhythm.)

- [ ] **Step 6: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 7: Visual QA** — skip; controller will do this.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Profile/components/WalletTab.tsx
git commit -m "Profile/WalletTab: shadow-card rows, info Badge for PC, drop ad-hoc violet palette"
```

---

## Task 3: SpendingTab — header + foreign-spend toolbar card

The header gets the same heading typography as WalletTab. The foreign-spend slider card switches from `bg-surface-2 border border-divider` (heavier panel) to a soft white shadow-card matching the Roadmap Tool's calc-inputs strip style from the spec.

**Files:**
- Modify: `frontend/src/pages/Profile/components/SpendingTab.tsx`

- [ ] **Step 1: Replace the header**

Find the `<div className="mb-5 shrink-0">` block containing "Annual Spending" (around line 111) and replace it with:

```tsx
<div className="mb-5 shrink-0">
  <h2 className="text-ink font-semibold text-xl tracking-tight">Annual Spending</h2>
  <p className="text-ink-muted text-sm mt-1">Track how much you spend in each category per year.</p>
</div>
```

- [ ] **Step 2: Replace the foreign-spend toolbar card**

Find the `<div className="flex gap-3 mb-4 shrink-0">` (around line 116) and replace its CONTENTS — the inner `<div>` with the slider — with the new soft-card treatment. Keep the outer `<div className="flex gap-3 mb-4 shrink-0">` wrapper. Replace its single child (the slider container) with:

```tsx
<div className="bg-surface rounded-xl shadow-card px-4 py-3 flex-1 min-w-0 flex flex-col justify-center">
  <div className="flex items-center justify-between mb-2">
    <div className="flex items-center gap-1">
      <span className="text-[10px] text-ink-muted uppercase tracking-wider">Foreign Spend</span>
      <Popover
        side="bottom"
        portal
        trigger={({ onClick, ref }) => (
          <button
            ref={ref as React.RefObject<HTMLButtonElement>}
            type="button"
            onClick={onClick}
            className="shrink-0 transition-colors text-ink-faint hover:text-accent"
            aria-label="How foreign spend affects calculation"
            title="How foreign spend affects calculation"
          >
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <circle cx="12" cy="12" r="10" />
              <line x1="12" y1="16" x2="12" y2="12" />
              <line x1="12" y1="8" x2="12.01" y2="8" />
            </svg>
          </button>
        )}
      >
        <div className="space-y-3 text-xs text-ink-muted leading-relaxed">
          <h3 className="text-sm font-semibold text-ink">Foreign Spend</h3>
          <p>
            What percentage of your yearly spend happens abroad. Each
            category is split into a domestic part and a foreign part,
            and the calculator assigns them separately.
          </p>
          <div>
            <p className="text-ink font-medium mb-1">Card priority</p>
            <p>
              Foreign spend goes to cards with no foreign-transaction fee.
              If the wallet has a no-fee Visa or Mastercard, that gets
              priority over no-fee cards on other networks (like Amex),
              since Visa/Mastercard are more widely accepted overseas.
            </p>
          </div>
          <div>
            <p className="text-ink font-medium mb-1">Rate on foreign spend</p>
            <p>
              On the foreign portion of a category, a card earns whichever
              is higher: its normal rate for that category, or its dedicated
              "Foreign Transactions" rate. So a card with a foreign-spend
              bonus (e.g. Atmos Summit at 3x) earns that on foreign
              groceries even if its domestic grocery rate is lower.
            </p>
          </div>
          <div>
            <p className="text-ink font-medium mb-1">If every card charges a foreign fee</p>
            <p>
              Cards compete normally and you pay the ~3% fee on the
              winning card's foreign spend.
            </p>
          </div>
        </div>
      </Popover>
    </div>
    <span className="text-xs font-medium text-ink tnum-mono">
      {Math.round(foreignSpendPercent)}%
    </span>
  </div>
  <input
    type="range"
    min={0}
    max={100}
    value={foreignSpendPercent}
    disabled={!walletReady}
    onChange={(e) => setDraftForeignPct(Number(e.target.value))}
    onMouseUp={(e) => {
      const pct = Number((e.target as HTMLInputElement).value)
      if (walletReady) updateWalletMutation.mutate(pct)
    }}
    onTouchEnd={(e) => {
      const pct = Number((e.target as HTMLInputElement).value)
      if (walletReady) updateWalletMutation.mutate(pct)
    }}
    className="w-full h-1.5 accent-accent cursor-pointer block my-0 disabled:cursor-not-allowed disabled:opacity-50"
  />
  <div className="relative h-4 mt-2">
    {(['0%', '25%', '50%', '75%', '100%'] as const).map((label, i) => (
      <span
        key={label}
        className={`absolute text-[10px] text-ink-faint tnum-mono ${i === 0 ? '' : i === 4 ? '-translate-x-full' : '-translate-x-1/2'}`}
        style={{ left: `${i * 25}%` }}
      >
        {label}
      </span>
    ))}
  </div>
</div>
```

(Single change to the outer container className: `bg-surface-2 border border-divider rounded-xl` → `bg-surface rounded-xl shadow-card`. Everything inside is unchanged.)

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA** — skip; controller will do this.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/Profile/components/SpendingTab.tsx
git commit -m "Profile/SpendingTab: shadow-card foreign-spend toolbar, header tightens"
```

---

## Task 4: SpendingTab — table chrome + inline edit inputs

The table is wrapped in a `border border-surface-2` container — switch to a soft shadow-card that matches the Roadmap Tool's Spend matrix idiom. Inline-edit inputs adopt the new field-language hover behavior (transparent border at rest, visible on hover).

**Files:**
- Modify: `frontend/src/pages/Profile/components/SpendingTab.tsx`

- [ ] **Step 1: Replace the table container**

Find the `<div className="rounded-lg border border-surface-2 overflow-hidden">` (around line 232) and replace ONLY its className with:

```tsx
<div className="rounded-xl bg-surface shadow-card overflow-hidden">
```

- [ ] **Step 2: Replace the table head + total row**

Find the `<thead className="bg-page">` (around line 234) and replace the entire `<thead>` block (from `<thead>` through its closing `</thead>`) with:

```tsx
<thead className="bg-surface">
  <tr>
    <th className="text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint px-4 py-3 border-b border-divider">Category</th>
    <th className="text-center text-[11px] font-semibold uppercase tracking-wider text-ink-faint px-4 py-3 border-b border-divider w-40">Annual Spend</th>
    <th className="w-12 border-b border-divider" />
  </tr>
</thead>
```

(Eyebrow-style column headers. The middle column width stays `w-40`.)

- [ ] **Step 3: Replace the total ("Annual Spend") row**

Find the `<tr className="border-b border-surface-2 bg-surface-2/30">` (around line 243) and replace its className with:

```tsx
<tr className="border-b border-divider bg-surface-2/40">
```

Inside that row, the total-amount input has `bg-surface-2 border border-divider focus:border-accent` — replace with:

```tsx
<input
  type="text"
  inputMode="numeric"
  pattern="[0-9]*"
  value={editingAnnualSpend ? annualSpendDraft : totalSpend === 0 ? '' : Math.round(totalSpend)}
  placeholder="0"
  onFocus={startEditAnnualSpend}
  onChange={(e) => setAnnualSpendDraft(e.target.value.replace(/[^0-9]/g, ''))}
  onBlur={commitAnnualSpend}
  onKeyDown={(e) => {
    if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur()
    if (e.key === 'Escape') {
      setEditingAnnualSpend(false)
      ;(e.currentTarget as HTMLInputElement).blur()
    }
  }}
  className="w-full min-w-0 bg-transparent border border-transparent hover:border-divider focus:bg-surface focus:border-accent focus:ring-2 focus:ring-accent-soft text-ink text-sm font-semibold tnum-mono text-right pl-4 pr-1.5 py-1 rounded outline-none placeholder:text-ink-faint transition-colors"
/>
```

- [ ] **Step 4: Replace the body row chrome and per-row input**

Find the body `<tr className="border-b border-surface-2/60 last:border-b-0">` (around line 285) and replace its className with:

```tsx
<tr className="border-b border-divider/60 last:border-b-0 hover:bg-surface-2/40 transition-colors">
```

Then find the per-row editable input (around lines 297–314) and replace it with:

```tsx
<input
  type="text"
  inputMode="numeric"
  pattern="[0-9]*"
  value={isEditing ? amountDraft : item.amount === 0 ? '' : Math.round(item.amount)}
  placeholder="0"
  onFocus={() => startEditAmount(item)}
  onChange={(e) => setAmountDraft(e.target.value.replace(/[^0-9]/g, ''))}
  onBlur={() => commitAmount(item)}
  onKeyDown={(e) => {
    if (e.key === 'Enter') (e.currentTarget as HTMLInputElement).blur()
    if (e.key === 'Escape') {
      setEditingAmountId(null)
      ;(e.currentTarget as HTMLInputElement).blur()
    }
  }}
  className="w-full min-w-0 bg-transparent border border-transparent hover:border-divider focus:bg-surface focus:border-accent focus:ring-2 focus:ring-accent-soft text-ink text-sm tnum-mono text-right pl-4 pr-1.5 py-1 rounded outline-none placeholder:text-ink-faint transition-colors"
/>
```

The "All Other" read-only display (`<div className="w-full text-ink-muted text-sm tnum-mono text-right pl-4 pr-1.5 py-0.5">`) stays as-is.

- [ ] **Step 5: Replace the Category column cell text color**

Find the body row's `<td className="text-left px-3 py-2 text-ink-muted">` (around line 286) and replace with:

```tsx
<td className="text-left px-4 py-2.5 text-ink text-sm">
```

(Tighten padding to `px-4 py-2.5`, bump category text from `text-ink-muted` to `text-ink` for legibility.)

The `<td className="text-center px-2 py-2">` for the spend input cell becomes:

```tsx
<td className="text-center px-3 py-2">
```

The `<td className="px-2 py-2 text-center">` for the chevron / info button cell becomes:

```tsx
<td className="px-2 py-2 text-center">
```

(No change — keeping for clarity.)

- [ ] **Step 6: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 7: Visual QA** — skip; controller will do this.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/Profile/components/SpendingTab.tsx
git commit -m "Profile/SpendingTab: shadow-card table, eyebrow column headers, hover-edit inputs"
```

---

## Task 5: SpendingTab — HousingTypeEditor accordion

The `HousingTypeEditor` uses `bg-page/40` (now neutral gray, fine) and `bg-accent text-page` (broken — `text-page` is now light gray instead of cream-white, so the active segment loses contrast). Switch to `text-on-accent` and use the same segmented-control idiom as the Foundation form fields.

**Files:**
- Modify: `frontend/src/pages/Profile/components/SpendingTab.tsx` (the `HousingTypeEditor` function near the bottom)

- [ ] **Step 1: Replace `HousingTypeEditor` body**

Find the `function HousingTypeEditor(...)` (around line 450) and replace its return statement with:

```tsx
return (
  <div className="px-4 py-3 bg-surface-2/40 border-t border-divider">
    <div className="flex items-center justify-between mb-2">
      <p className="text-[11px] text-ink-faint uppercase tracking-wider font-semibold">
        Housing type
      </p>
      <button
        type="button"
        onClick={onClose}
        className="text-xs text-ink-faint hover:text-ink transition-colors"
      >
        Close
      </button>
    </div>
    <div className="inline-flex gap-0.5 bg-surface rounded-md p-0.5 shadow-card">
      {(['rent', 'mortgage'] as const).map((opt) => {
        const active = housingType === opt
        return (
          <button
            key={opt}
            type="button"
            disabled={!walletReady || isPending}
            onClick={() => {
              if (housingType !== opt) onSelect(opt)
            }}
            className={`text-xs font-medium px-3 py-1 rounded transition-colors capitalize ${
              active
                ? 'bg-accent text-on-accent'
                : 'text-ink-muted hover:bg-surface-2'
            } disabled:opacity-50 disabled:cursor-not-allowed`}
          >
            {opt}
          </button>
        )
      })}
    </div>
  </div>
)
```

Key changes:
- Container: `bg-page/40` → `bg-surface-2/40 border-t border-divider` (clearer separation from the row above).
- Eyebrow: `font-semibold` added.
- Close button: `text-ink-muted` → `text-ink-faint hover:text-ink` (matches new field language).
- Segmented control: `bg-page/60 border border-divider` → `bg-surface shadow-card` (softer container).
- Active segment: `bg-accent text-page` → `bg-accent text-on-accent` (white text — fixes the Plan 1 token-shift broken contrast).

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA** — skip.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Profile/components/SpendingTab.tsx
git commit -m "Profile/SpendingTab: HousingTypeEditor uses on-accent token, soft surface"
```

---

## Task 6: CategoryWeightEditor — inline accordion

Same `bg-page/40` → `bg-surface-2/40` shift. Save button switches to `text-on-accent`. Per-row inputs match the new hover-border field-language.

**Files:**
- Modify: `frontend/src/pages/Profile/components/CategoryWeightEditor.tsx`

- [ ] **Step 1: Replace the editor body**

Find the `return (` block (around line 116). Replace it with:

```tsx
return (
  <div className="px-4 py-3 bg-surface-2/40 border-t border-divider">
    <div className="flex items-center justify-between mb-2">
      <p className="text-[11px] text-ink-faint uppercase tracking-wider font-semibold">
        Mix for {data.user_category_name} spend
      </p>
      <button
        type="button"
        onClick={handleReset}
        disabled={resetMutation.isPending}
        className="text-xs text-ink-faint hover:text-accent disabled:opacity-50 transition-colors"
      >
        Reset to defaults
      </button>
    </div>

    <div className="space-y-1.5">
      {data.mappings.map((row: WalletCategoryWeightRow) => (
        <div key={row.earn_category_id} className="flex items-center gap-3">
          <span className="text-sm text-ink-muted flex-1 min-w-0 truncate">
            {row.earn_category_name}
          </span>
          <div className="relative w-20 shrink-0">
            <input
              type="text"
              inputMode="numeric"
              pattern="[0-9]*"
              value={draft[row.earn_category_id] ?? ''}
              onChange={(e) =>
                setDraft((prev) => ({
                  ...prev,
                  [row.earn_category_id]: e.target.value.replace(/[^0-9]/g, ''),
                }))
              }
              className="w-full bg-transparent border border-transparent hover:border-divider focus:bg-surface focus:border-accent focus:ring-2 focus:ring-accent-soft text-ink text-sm tnum-mono text-right pr-5 pl-1.5 py-1 rounded outline-none placeholder:text-ink-faint transition-colors"
            />
            <span className="absolute right-1.5 top-1/2 -translate-y-1/2 text-xs text-ink-faint pointer-events-none">
              %
            </span>
          </div>
        </div>
      ))}
    </div>

    <div className="flex items-center justify-between mt-3">
      <span
        className={`text-xs ${
          totalIs100 ? 'text-ink-muted' : 'text-warn'
        }`}
      >
        Total: <span className="tnum-mono">{totalPct}%</span>
        {!totalIs100 && (
          <span className="ml-2 text-ink-faint">
            (will be normalized to <span className="tnum-mono">100%</span> on save)
          </span>
        )}
      </span>
      <div className="flex items-center gap-2">
        {submitError && (
          <span className="text-xs text-neg">{submitError}</span>
        )}
        <button
          type="button"
          onClick={onClose}
          disabled={saveMutation.isPending}
          className="text-xs text-ink-faint hover:text-ink px-2 py-1 rounded disabled:opacity-50 transition-colors"
        >
          Cancel
        </button>
        <button
          type="button"
          onClick={handleSave}
          disabled={saveMutation.isPending}
          className="text-xs font-medium bg-accent text-on-accent hover:opacity-90 px-3 py-1 rounded disabled:opacity-50 transition-opacity"
        >
          {saveMutation.isPending ? 'Saving…' : 'Save'}
        </button>
      </div>
    </div>
  </div>
)
```

Also update the loading and error states (around lines 101–112) to match the new container language:

```tsx
if (isLoading) {
  return (
    <div className="px-4 py-3 bg-surface-2/40 border-t border-divider text-xs text-ink-faint">Loading defaults…</div>
  )
}
if (isError || !data) {
  return (
    <div className="px-4 py-3 bg-surface-2/40 border-t border-divider text-xs text-neg">
      Failed to load category weights.
    </div>
  )
}
```

Key changes:
- Container: `bg-page/40` → `bg-surface-2/40 border-t border-divider`.
- Eyebrow: `font-semibold` added.
- Reset button: `text-ink-muted hover:text-accent` → `text-ink-faint hover:text-accent transition-colors`.
- Per-row input: switches to the hover-border field-language (transparent at rest, hover bumps to divider, focus shows accent + ring).
- Save button: `bg-accent text-page hover:opacity-90` → `bg-accent text-on-accent hover:opacity-90 transition-opacity` (white text on accent — fixes the contrast issue).
- Cancel button: `text-ink-muted` → `text-ink-faint`.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA** — skip.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Profile/components/CategoryWeightEditor.tsx
git commit -m "Profile/CategoryWeightEditor: hover-border inputs, on-accent save button"
```

---

## Task 7: AppearanceTab — preview-card grid

Replace the current single-column radio list with a 3-up grid of preview cards (Light · Dark · System). Each card shows a tiny mockup of the theme. Selected card gets the accent ring used elsewhere (matching the Plan 2 Home StepCard "current" treatment).

**Files:**
- Modify: `frontend/src/pages/Profile/components/AppearanceTab.tsx`

- [ ] **Step 1: Replace the entire `AppearanceTab` function**

Replace the contents of `frontend/src/pages/Profile/components/AppearanceTab.tsx` (excluding the import line) with:

```tsx
import { useTheme, type ThemePreference } from '../../../hooks/useTheme'

const OPTIONS: { id: ThemePreference; label: string; preview: 'light' | 'dark' | 'split' }[] = [
  { id: 'light', label: 'Light', preview: 'light' },
  { id: 'dark', label: 'Dark', preview: 'dark' },
  { id: 'system', label: 'System', preview: 'split' },
]

export function AppearanceTab() {
  const { preference, setPreference } = useTheme()

  return (
    <div className="max-w-2xl space-y-6">
      <div>
        <h2 className="text-ink font-semibold text-xl tracking-tight">Appearance</h2>
        <p className="text-ink-muted text-sm mt-1">Choose how the app looks.</p>
      </div>

      <div role="radiogroup" aria-label="Theme" className="grid grid-cols-3 gap-3">
        {OPTIONS.map((opt) => {
          const selected = preference === opt.id
          return (
            <button
              key={opt.id}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => setPreference(opt.id)}
              className={`bg-surface rounded-xl shadow-card overflow-hidden transition-all text-left ${
                selected ? 'ring-2 ring-accent' : 'hover:-translate-y-0.5'
              }`}
            >
              <ThemePreview preview={opt.preview} />
              <div className="px-4 py-3 flex items-center justify-between">
                <span className="text-ink text-sm font-medium">{opt.label}</span>
                <span
                  aria-hidden
                  className={`shrink-0 w-4 h-4 rounded-full border-2 transition-colors ${
                    selected
                      ? 'border-accent bg-accent'
                      : 'border-divider-strong bg-transparent'
                  }`}
                />
              </div>
            </button>
          )
        })}
      </div>
    </div>
  )
}

function ThemePreview({ preview }: { preview: 'light' | 'dark' | 'split' }) {
  if (preview === 'split') {
    return (
      <div className="relative h-24 overflow-hidden">
        <div className="absolute inset-0 grid grid-cols-2">
          <PreviewMockup tone="light" />
          <PreviewMockup tone="dark" />
        </div>
        <div className="absolute inset-y-0 left-1/2 w-px bg-divider-strong" />
      </div>
    )
  }
  return <PreviewMockup tone={preview} />
}

function PreviewMockup({ tone }: { tone: 'light' | 'dark' }) {
  const styles = tone === 'light'
    ? { bg: '#f3f4f6', surface: '#ffffff', ink: '#111827', accent: '#b04256', divider: '#e5e7eb' }
    : { bg: '#0b0d11', surface: '#16181d', ink: '#f5f5f5', accent: '#b04256', divider: '#2a2e36' }
  return (
    <div className="h-24 p-3 flex flex-col gap-2" style={{ background: styles.bg }}>
      <div className="flex items-center gap-1.5">
        <div className="h-1.5 w-8 rounded-full" style={{ background: styles.accent }} />
        <div className="h-1 w-12 rounded-full" style={{ background: styles.divider }} />
      </div>
      <div className="rounded p-2 flex-1 flex flex-col gap-1.5" style={{ background: styles.surface }}>
        <div className="h-1.5 rounded-full" style={{ background: styles.ink, opacity: 0.65, width: '60%' }} />
        <div className="h-1 rounded-full" style={{ background: styles.ink, opacity: 0.25, width: '85%' }} />
        <div className="h-1 rounded-full" style={{ background: styles.ink, opacity: 0.25, width: '70%' }} />
      </div>
    </div>
  )
}
```

The `ThemePreview` and `PreviewMockup` helpers render small theme mockups using inline styles (intentional — these are visual previews of the theme palettes themselves, so they need literal hex values, not tokens). The `split` variant for "System" shows light + dark side-by-side with a vertical divider.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA** — skip; controller will do this.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Profile/components/AppearanceTab.tsx
git commit -m "Profile/AppearanceTab: preview-card grid with theme mockups"
```

---

## Task 8: SettingsTab — profile card + username edit + sign out

The profile card currently uses `bg-surface-2 border border-divider rounded-xl overflow-hidden` — switch to a soft white shadow-card consistent with WalletTab and AppearanceTab. The username edit input adopts the foundation Input chrome. The sign-out button uses the `secondary` Button primitive with neg semantic styling for the destructive action context.

**Files:**
- Modify: `frontend/src/pages/Profile/components/SettingsTab.tsx`

- [ ] **Step 1: Replace the header**

Find the `<div>` containing `<h2 className="text-xl font-bold text-ink">Settings</h2>` (around line 46) and replace with:

```tsx
<div>
  <h2 className="text-ink font-semibold text-xl tracking-tight">Settings</h2>
  <p className="text-ink-muted text-sm mt-1">Manage your account details.</p>
</div>
```

- [ ] **Step 2: Replace the profile-card container**

Find the `<div className="bg-surface-2 border border-divider rounded-xl overflow-hidden">` (around line 52) and replace with:

```tsx
<div className="bg-surface rounded-xl shadow-card overflow-hidden">
```

(Drop the surface-2 background and border; lean on shadow-card. The internal divide-y dividers stay, switched to plain `--color-divider`.)

- [ ] **Step 3: Replace the divide-y class on the fields container**

Find the `<div className="divide-y divide-divider/60">` (around line 76) and replace with:

```tsx
<div className="divide-y divide-divider">
```

- [ ] **Step 4: Replace the username edit input**

Find the username `<input type="text" ...>` block (around lines 82–94) and replace it with:

```tsx
<input
  type="text"
  value={usernameDraft}
  onChange={(e) => setUsernameDraft(e.target.value)}
  onKeyDown={(e) => {
    if (e.key === 'Enter') saveUsername()
    if (e.key === 'Escape') cancelEditUsername()
  }}
  autoFocus
  maxLength={40}
  className="w-full bg-surface border border-divider hover:border-divider-strong focus:border-accent focus:ring-2 focus:ring-accent-soft text-ink text-sm rounded-md px-3 py-2 outline-none transition-colors"
  placeholder="e.g. johndoe"
/>
```

(Matches the foundation Input primitive's chrome: white surface, gray-200 rest, gray-300 hover, accent focus + soft ring.)

- [ ] **Step 5: Replace the username error text and "Set username" link**

Find the `<p className="text-neg text-xs">{usernameError}</p>` (around line 96) and replace with:

```tsx
<p className="text-[11px] text-neg">{usernameError}</p>
```

Find the `<button type="button" onClick={startEditUsername} className="text-xs text-accent hover:opacity-80 transition-opacity shrink-0">` (around line 125) and replace with:

```tsx
<button
  type="button"
  onClick={startEditUsername}
  className="text-xs font-medium text-accent hover:opacity-80 transition-opacity shrink-0"
>
```

(Adds `font-medium` for visual weight matching the field labels.)

- [ ] **Step 6: Replace the sign-out button**

Find the bottom `<button type="button" onClick={signOut} className="text-sm font-medium px-4 py-2 rounded-lg text-neg hover:opacity-80 border border-neg/40 hover:border-neg/60 transition-colors">Sign out</button>` (around line 154) and replace with:

```tsx
<button
  type="button"
  onClick={signOut}
  className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-md text-neg border border-neg/30 hover:bg-neg/10 hover:border-neg/50 transition-colors"
>
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4" />
    <polyline points="16 17 21 12 16 7" />
    <line x1="21" y1="12" x2="9" y2="12" />
  </svg>
  Sign out
</button>
```

(Adds an inline icon for clarity; switches `rounded-lg` → `rounded-md` for consistency; adds a subtle bg tint on hover instead of just border darkening.)

- [ ] **Step 7: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 8: Visual QA** — skip; controller will do this.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/pages/Profile/components/SettingsTab.tsx
git commit -m "Profile/SettingsTab: shadow-card profile panel, foundation Input chrome, neg sign-out"
```

---

## Task 9: Final visual QA pass

End-to-end Profile QA in light + dark before merge.

**Files:**
- (Verify only.)

- [ ] **Step 1: Run lint**

Run: `cd frontend && npm run lint`
Expected: same 3 pre-existing findings (`Button/index.tsx:27`, `CategoryWeightEditor.tsx:39`, `RoadmapTool/index.tsx:737`). NO NEW findings.

If `CategoryWeightEditor.tsx:39` (the `setSubmitError(null)` inside the `useEffect`) is now in a different position because of this plan's changes, that's still pre-existing logic — preserve it. The lint warning was in scope before.

- [ ] **Step 2: Production build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Walk through Profile in light mode**

Sign in. Navigate to `/profile`. Confirm:

- **Sidebar:** 4 tabs in a vertical list, tighter rhythm than before. Active tab has a 2px accent left-rule + light tinted background; inactive in `--color-ink-faint`, hover bumps to `--color-ink`.
- **Content panel:** white card with soft shadow (no visible border). 24px padding.
- **Wallet tab:** "My Cards" header, "Add Card" primary button. Empty state has dashed-border placeholder if no cards. Cards (if any) render as soft white shadow-cards with hover brightening; PC badge (if any product-changed cards exist) uses the info-toned `Badge` primitive.
- **Spending tab:** "Annual Spending" header. Foreign-spend slider in a soft white shadow-card. Table inside a shadow-card: column headers as eyebrow uppercase. Total row with editable annual-spend input. Body rows with hover tint. Inline-edit inputs show transparent at rest, gray border on hover, accent border + soft ring on focus.
- **Spending tab → Housing accordion:** Click chevron on the Housing row. Accordion appears below; segmented Rent/Mortgage with active in accent + white text.
- **Spending tab → Mix accordion:** Click chevron on a non-housing, non-All-Other row. CategoryWeightEditor accordion appears below; per-earn-category inputs in the new field language; "Reset to defaults" link top right; Save button in accent + white text.
- **Appearance tab:** 3-up grid of preview cards (Light, Dark, System). Each shows a small mockup of the theme. Selected card has 2-ring accent + filled radio dot.
- **User Settings tab:** profile-card with avatar + name + email; username row inline-edit; Name and Email rows read-only; sign-out button in neg color with icon.

- [ ] **Step 4: Walk through Profile in dark mode**

Toggle theme. Re-walk all 4 tabs.
- All shadow-cards still readable on the dark page.
- Accent crimson still visible on the active sidebar rule, primary buttons, focus rings.
- Inline-edit inputs read clearly (focus shows the accent ring against the dark surface).
- AppearanceTab's preview cards: the "Light" card shows a literal cream-white preview against the dark page (intentional — it's a visual sample). The "Dark" card shows a literal near-black preview, and "System" shows a split.

- [ ] **Step 5: Toggle "System" theme and confirm OS-driven theme detection still works**

(If the user's OS is set to dark, choosing System should reflect dark in the navbar instantly; switching OS settings should re-render. Just visually check Profile renders correctly in either OS-driven state.)

- [ ] **Step 6: Commit a final QA marker**

If you committed inline fixes during this task, stop here. Otherwise:

```bash
git commit --allow-empty -m "Profile: visual QA pass complete (light + dark, all 4 tabs)"
```

---

## Plan complete

After Task 9, the Profile page is consistent with the soft-dashboard direction across its shell and all four tabs. Plan 4 (Roadmap Tool — page shell, Timeline, Spend, modals, other surfaces) is the last sub-plan.
