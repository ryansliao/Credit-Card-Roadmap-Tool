# Spending Tab — Move Housing Type Toggle Onto Housing Row

**Date:** 2026-04-30
**Status:** Draft (approved for implementation)
**Scope:** `frontend/src/pages/Profile/components/SpendingTab.tsx` and a small additive API extension to `frontend/src/components/ui/Popover/index.tsx`.

## Problem

The Spending tab header currently has three cards: `Total Annual Spend`, `Housing Type` (a Rent/Mortgage segmented toggle), and `Foreign Spend`. The Housing category row in the table below shows a read-only ⓘ info popover that explains the current housing fan-out and includes the text "Set by your Housing Type above. Switch to {other} to flip."

Two visual elements describe the same single piece of state. The `Housing Type` card consumes prime real-estate at the top of the page for a setting that conceptually belongs *on* the Housing row. We want one inline control on the Housing row that both displays and changes the housing type.

## Goals

- One control on the Housing row that displays the current housing type and lets the user change it.
- Reclaim header space (`Foreign Spend` widens to fill).
- No backend changes — `wallet.housing_type` and `walletApi.update({ housing_type })` already exist.

## Non-goals

- No new component primitives. Reuse the existing `Popover` component already used elsewhere on the page (with a small backwards-compatible API extension — see "Popover render-prop extension" below).
- No change to how housing weights are computed downstream (the calculator already keys off `wallet.housing_type`).
- No change to the All Other row or any non-housing row.

## UI changes

### Remove from header

Delete the entire `Housing Type` card (the wrapper `<div class="bg-surface-2 …w-56…">` and its contents). The header row goes from three cards to two:

- `Total Annual Spend` — `w-48`, unchanged.
- `Foreign Spend` — `flex-1`, unchanged structure; naturally widens.

### Replace info popover on Housing row

Inside the `editable` branch logic (the IIFE that renders either the chevron-expand button or the housing/all-other info popover), the **Housing** branch swaps the read-only info popover for an inline dropdown chip.

- **All Other** branch is unchanged (still renders nothing — All Other is system-locked and the row hides the trash and chevron buttons).
- **Editable categories** are unchanged (chevron expand button stays).

#### Dropdown chip

A small button next to the "Housing" label, opened via `Popover` (`side="bottom"`, `portal`).

- **Trigger button** — pill style:
  - Classes: `text-xs px-1.5 py-0.5 rounded border border-divider bg-surface-2 text-ink-muted hover:bg-surface-2/80 transition-colors flex items-center gap-1 disabled:opacity-50 disabled:cursor-not-allowed`
  - Content: capitalized current value (`Rent` / `Mortgage`) + a 10-12px chevron-down SVG matching the codebase's existing chevron iconography.
  - Disabled when `!walletReady || housingTypeMutation.isPending`.
  - `aria-haspopup="listbox"`, `aria-label="Housing type"`.

- **Popover content** — vertical menu of two option buttons:
  - `Rent` and `Mortgage`
  - Each option is a button: `w-full text-left text-xs px-2 py-1.5 rounded transition-colors`.
  - Active option (matches current `housingType`): `bg-accent text-page` (mirrors the active state from the removed segmented toggle).
  - Inactive option: `text-ink-muted hover:bg-surface-2/60`.
  - Active option additionally renders a small checkmark on the right (12px SVG) so the active state is conveyed by more than color alone.
  - Clicking an option:
    - Calls `housingTypeMutation.mutate(opt)` only when `housingType !== opt` (matches the existing toggle behavior).
    - Closes the popover by invoking the `close` callback provided through the render-prop children API (see next section).

#### Popover render-prop extension

`Popover` (`frontend/src/components/ui/Popover/index.tsx`) currently auto-closes only on outside-click and Escape. A click *inside* the popover (e.g. on a menu option) does not dismiss. The Housing Type dropdown needs to close the popover after selection.

Tiny additive API change, backwards compatible:

```ts
children: ReactNode | ((props: { close: () => void }) => ReactNode)
```

Render logic detects `typeof children === 'function'` and calls it with `{ close: () => setOpen(false) }`; otherwise renders the `ReactNode` as today. All existing call sites continue to work unchanged because `ReactNode` callers pass plain JSX.

The Housing Type dropdown is the first consumer of the function form.

#### Code that goes away with this change

- The entire `Housing Type` header card (the `bg-surface-2 …w-56` block).
- The Housing-specific branch of the read-only info popover, including:
  - `housingTarget` derivation
  - `displayMappings` rebuild
  - The `{isHousing && (<p>Set by your Housing Type above…</p>)}` line

The All-Other read-only popover branch — though dead in practice (the row hides children for the locked row) — stays in place; this change does not touch it.

## State / data flow

No new React state. `housingType` and `housingTypeMutation` already exist in `SpendingTab.tsx` and are reused as-is; only the JSX consumer moves.

`useMyWallet()` already returns `wallet.housing_type` and the existing `onSuccess` invalidates `queryKeys.myWalletWithScenarios()`, which propagates the new value back through `useMyWallet`. Re-render flow is unchanged.

## Accessibility

- The trigger button has `aria-label="Housing type"` and `aria-haspopup="listbox"`.
- The active option is distinguished by the inline checkmark in addition to color, so the selection is conveyed without relying on color alone.
- Keyboard: the existing `Popover` primitive already handles Escape-to-close and outside-click dismissal.

## Testing

Manual verification only — no automated test currently covers this part of the spending tab, and the calculator snapshot is unaffected.

Manual checklist:
1. Header shows two cards (Total Annual Spend + Foreign Spend); Foreign Spend stretches to fill.
2. Housing row shows a chip with the current housing type and a chevron.
3. Clicking the chip opens a popover with two options; the current value is highlighted with the accent color and a checkmark.
4. Selecting the other option immediately updates the chip text and persists (refresh the page; value is retained).
5. While the mutation is in flight the chip is disabled.
6. All Other row still has no chip, no expand button, no trash.
7. Other categories still show the chevron expand button and no chip.
8. Foreign-spend slider still functions normally.

## Risk

Low. UI-only change in a single component plus a small backwards-compatible API extension on `Popover`. No backend, schema, calculator, or query-key changes. The `Popover` extension is a pure superset (`ReactNode | render-prop`); existing call sites are untouched.
