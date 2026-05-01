# Roadmap Tool Content Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the Roadmap Tool's two main tab contents (Timeline + Spend) and every "in-roadmap" surface beneath the page shell — ScenarioPicker dropdown body, `CurrencySettingsDropdown`, `WalletPortalSharesEditor`, `AddScenarioModal`, `ApplicationRuleWarningModal`, `DeleteCardWarningModal`, plus the legend that Plan 4a temporarily dropped. Plan 4b of 4c. Spec: `docs/superpowers/specs/2026-05-01-roadmap-tool-redesign-design.md` Sections 7, 8, 10, and 11.

**Architecture:** Visual restyle only. The timeline calc semantics (per-card lifetime bars, SUB stripes, EAF label placement, currency group sort, capped-pool markers, today/end vertical lines) are preserved exactly — `WalletTimelineChart`, `CardRow`, `GroupSection`, `TimelineAxis`, and `TimelineGlyphs` keep their math and rendering logic; only their chrome (containers, headers, toolbars, paddings, color usage) changes. The Spend matrix's column order is preserved; row chrome and inline-edit inputs adopt the field-language established in Plan 3 (Profile/SpendingTab).

**Tech Stack:** React + Vite + Tailwind v4. Foundation primitives in `frontend/src/components/ui/` (Plans 1+3). Build: `cd frontend && npm run build`. Lint: `cd frontend && npm run lint`. Dev: `cd frontend && npm run dev`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx` | Timeline shell (~426 lines): outer container, axis header (Cards label + Add Card + rule warning), scroll body with currency groups. Modified: outer surface treatment, axis-header → soft toolbar, rule-warning popover styling. |
| `frontend/src/pages/RoadmapTool/components/timeline/GroupSection.tsx` | Currency group block (~230 lines): collapsible header with currency name + CPP + balance + EAF, secondary annual rows, expansion contents. Modified: header chrome (card-on-card with the divider border), expand/collapse rhythm, secondary-row tinting. |
| `frontend/src/pages/RoadmapTool/components/timeline/CardRow.tsx` | Per-card row (~502 lines): left gutter + lifetime bar + EAF label + SUB stripe segment. Modified: gutter chrome (CardThumb size, name/income typography, lock/toggle layout). Bar visuals + EAF label placement preserved. |
| `frontend/src/pages/RoadmapTool/components/spend/SpendTabContent.tsx` | Spend matrix (~725 lines): header, columns (Category · Spend · Income · Top Card), inline edits, mapping/category-priority popovers. Modified: outer card surface, table chrome (eyebrow column heads, hairline rows, hover tint), edit-input field-language. |
| `frontend/src/pages/RoadmapTool/components/spend/SpendPanel.tsx` | Tiny container (~20 lines) — passes props through to SpendTabContent. Modified: outer container surface treatment. |
| `frontend/src/pages/RoadmapTool/components/ScenarioPicker.tsx` | Scenario picker trigger + dropdown panel. Modified: dropdown panel chrome + per-row chrome (Plan 4a already updated the trigger border). |
| `frontend/src/pages/RoadmapTool/components/summary/CurrencySettingsDropdown.tsx` | Per-currency CPP + balance editor popover (~183 lines). Modified: popover chrome and form field language. |
| `frontend/src/pages/RoadmapTool/components/summary/WalletPortalSharesEditor.tsx` | Per-currency travel-portal share editor popover (~196 lines). Modified: popover chrome and form field language. |
| `frontend/src/pages/RoadmapTool/components/AddScenarioModal.tsx` | Small modal (~119 lines). Modified: `Field`-based form, `Button` primary, soft modal chrome. |
| `frontend/src/pages/RoadmapTool/components/ApplicationRuleWarningModal.tsx` | Small modal (~46 lines). Modified: warn-tinted icon header band, primary continue button. |
| `frontend/src/components/cards/DeleteCardWarningModal.tsx` | Small modal (~49 lines). Modified: neg-tinted icon header, filled `--color-neg` Delete button. |
| `frontend/src/pages/RoadmapTool/components/timeline/TimelineGlyphs.tsx` | (~60 lines) Token-driven; not modified. Verified only. |
| `frontend/src/components/cards/TimelineAxis.tsx` | (~51 lines) Modified: tick label typography (10–11px ink-faint). |

---

## Task 1: Timeline outer chrome + toolbar

The current `WalletTimelineChart` wraps the chart in `bg-surface border border-divider rounded-xl pt-2 px-4 pb-4` with the `Add Card` button and rule warning baked into the axis-header alongside `<h2>Cards</h2>`. Per spec 7.1, those move out of the axis-header and into a dedicated toolbar above the chart, plus a legend on the right (the legend Plan 4a temporarily dropped).

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx`

- [ ] **Step 1: Replace the outer container className**

In `frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx`, find the outer `<div className="bg-surface border border-divider rounded-xl pt-2 px-4 pb-4 min-w-0 min-h-0 h-full flex flex-col overflow-hidden">` (around line 174). Replace its className with:

```tsx
className="bg-surface border border-divider rounded-xl shadow-card min-w-0 min-h-0 h-full flex flex-col overflow-hidden"
```

(Adds `shadow-card`, drops the inner padding — the toolbar and chart body manage their own padding now.)

- [ ] **Step 2: Add a timeline toolbar above the axis-header**

Immediately inside the outer container, before the axis-header grid (around line 204), insert a new toolbar `<div>`:

```tsx
{visibleCards.length > 0 && (
  <div className="flex items-center gap-2 px-4 pt-3 pb-2 shrink-0">
    <Button
      type="button"
      variant="secondary"
      size="sm"
      onClick={onAddCard}
    >
      <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
        <line x1="12" y1="5" x2="12" y2="19" />
        <line x1="5" y1="12" x2="19" y2="12" />
      </svg>
      Add card
    </Button>
    {applicableRules.length > 0 && (
      <Popover
        side="bottom"
        portal
        trigger={({ onClick, ref }) => (
          <button
            ref={ref as React.RefObject<HTMLButtonElement>}
            type="button"
            onClick={onClick}
            className={`inline-flex items-center gap-1.5 rounded-md px-2.5 py-1 text-[11px] font-medium uppercase tracking-wider transition-colors ${
              maxSeverity === 'violated'
                ? 'bg-neg/10 text-neg hover:bg-neg/15'
                : maxSeverity === 'in_effect'
                  ? 'bg-warn/10 text-warn hover:bg-warn/15'
                  : 'bg-accent-soft text-accent hover:bg-accent/15'
            }`}
            aria-label="Application rule status"
            title="Application rule status"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
              <line x1="12" y1="9" x2="12" y2="13" />
              <line x1="12" y1="17" x2="12.01" y2="17" />
            </svg>
            {applicableRules.length === 1 ? 'Rule alert' : `${applicableRules.length} rule alerts`}
          </button>
        )}
      >
        <div className="min-w-[280px] max-w-sm">
          <p className="text-sm font-semibold text-ink mb-2">Application Rules</p>
          <p className="text-xs text-ink-muted mb-3">Issuer velocity rules tracked across your cards.</p>
          <ul className="space-y-2">
            {applicableRules.map((r) => {
              const containerClass =
                r.severity === 'violated'
                  ? 'bg-neg/10 border-neg/30'
                  : r.severity === 'in_effect'
                    ? 'bg-warn/10 border-warn/30'
                    : 'bg-surface-2 border-divider'
              const titleClass =
                r.severity === 'violated'
                  ? 'text-neg'
                  : r.severity === 'in_effect'
                    ? 'text-warn'
                    : 'text-ink'
              const intervalClass =
                r.severity === 'violated'
                  ? 'text-neg'
                  : r.severity === 'in_effect'
                    ? 'text-warn'
                    : 'text-ink-muted'
              return (
                <li key={r.rule_id} className={`rounded-md border px-2.5 py-2 ${containerClass}`}>
                  <div className="flex items-baseline gap-1.5 min-w-0">
                    <span className={`font-medium truncate ${titleClass}`}>{r.rule_name}</span>
                    {r.issuer_name && (
                      <span className="text-[10px] text-ink-faint shrink-0">{r.issuer_name}</span>
                    )}
                  </div>
                  {r.description && (
                    <p className="text-[11px] text-ink-muted mt-0.5">{r.description}</p>
                  )}
                  {r.at_risk_intervals.length > 0 && (
                    <ul className="mt-1 space-y-0.5">
                      {r.at_risk_intervals.map((iv, idx) => (
                        <li key={idx} className={`text-[11px] ${intervalClass}`}>
                          At limit <span className="tnum-mono">{formatDate(iv.start)} → {formatDate(iv.end)}</span>
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              )
            })}
          </ul>
        </div>
      </Popover>
    )}
    <div className="flex-1" />
    <div className="hidden sm:flex items-center gap-3 text-[11px] text-ink-faint">
      <span className="inline-flex items-center gap-1.5">
        <span aria-hidden className="w-7 h-2.5 rounded-full" style={{ background: 'color-mix(in oklab, var(--chart-points) 18%, transparent)', border: '1px solid var(--chart-points)' }} />
        Active card
      </span>
      <span className="inline-flex items-center gap-1.5">
        <span
          aria-hidden
          className="w-7 h-2.5 rounded-full border"
          style={{
            backgroundImage: `repeating-linear-gradient(45deg, color-mix(in oklab, var(--chart-points) 38%, transparent) 0, color-mix(in oklab, var(--chart-points) 38%, transparent) 4px, color-mix(in oklab, var(--chart-points) 10%, transparent) 4px, color-mix(in oklab, var(--chart-points) 10%, transparent) 8px)`,
            borderColor: 'var(--chart-points)',
          }}
        />
        SUB earning
      </span>
    </div>
  </div>
)}
```

This new toolbar takes responsibility from the axis-header for the Add Card button and the rule warning. The legend on the right (Active card · SUB earning) is what Plan 4a dropped from `WalletSummaryStats`.

- [ ] **Step 3: Strip the axis-header content**

The axis-header currently mixes the title (`<h2>Cards</h2>`), the Add Card button, and the rule warning. Now that the toolbar owns those, simplify the axis-header to just the "Cards" label.

Find the axis-header `<div className={`bg-surface ${DIVIDER_CLASS} px-3 flex items-center gap-2`}` (around line 211). Replace the entire axis-header child content (everything inside that div) with just:

```tsx
<span className="text-[11px] uppercase tracking-wider text-ink-faint font-semibold">Cards</span>
```

(Drops the `<h2>`, the inline `<Button>`, and the rule-warning `Popover` from the axis-header.)

- [ ] **Step 4: Tighten the empty-state padding**

The empty-state branch (`visibleCards.length === 0`) currently pads with `py-10` inside `<div ref={scrollRef} className="flex-1 min-h-0 overflow-auto">`. Bump to `py-16` for more breathing room and switch the helper text to `text-ink-muted`:

Find the existing block:

```tsx
<div className="flex flex-col items-center gap-3 py-10">
  <p className="text-ink-faint text-sm">No cards yet.</p>
  <Button type="button" variant="primary" onClick={onAddCard}>
```

And replace `py-10` with `py-16` and `text-ink-faint` with `text-ink-muted text-sm font-medium`. Add a small subtitle line below the headline:

```tsx
<div className="flex flex-col items-center gap-3 py-16">
  <p className="text-ink-muted text-sm font-medium">No cards yet</p>
  <p className="text-ink-faint text-xs -mt-2">Add a card to start your roadmap.</p>
  <Button type="button" variant="primary" onClick={onAddCard}>
```

- [ ] **Step 5: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 6: Visual QA** — skip; controller will do this.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx
git commit -m "RoadmapTool/timeline: shadow-card outer, soft toolbar with legend"
```

---

## Task 2: Currency group card chrome

The currency group header (collapsible) shows the currency name + CPP + balance + EAF in a row. Per spec 7.2, give it the soft-card treatment with a clear divider beneath the header when expanded.

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/timeline/GroupSection.tsx`

- [ ] **Step 1: Restyle the group header row**

Read `frontend/src/pages/RoadmapTool/components/timeline/GroupSection.tsx` and locate the header `<button>` or `<div>` that's clickable to expand/collapse the group. It should currently include the currency name, CPP / balance / EAF readouts, and a chevron.

Replace its outer wrapper className so the header sits inside a `bg-surface-2/40 hover:bg-surface-2 transition-colors` row (instead of whatever loud background it currently has). Drop any heavy borders inside the header — let the existing per-currency vertical separator (between currency-name and the secondary readouts) be a `bg-divider` 1px-wide span.

Specifically: find the header row's outer container className (the one containing `cursor-pointer` or `onClick={onToggleExpanded}`). Replace it with a className that uses `hover:bg-surface-2/40 transition-colors` for hover, drops any `bg-surface-2` rest-state highlights (so the header sits flat against the chart's white surface).

The internal structure (currency icon glyph, name, CPP popover trigger, balance popover trigger, EAF, chevron) stays the same. Only the wrapping classes change.

- [ ] **Step 2: Adjust the secondary annual rows**

Some currency groups have secondary annual rows (e.g., a card's secondary rate). Find those `<div>` rows (search for `secondary` in the file). Wherever they have a heavy background, switch to `bg-surface-2/40` for consistency with the new card chrome.

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA** — skip; controller will do this.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/timeline/GroupSection.tsx
git commit -m "RoadmapTool/GroupSection: soft surface chrome, transparent rest state"
```

---

## Task 3: Card row gutter

The left gutter (220px) shows: `CardThumb` (40×26) → card name + income summary line → lock-badge or future-card toggle. Per spec 7.3, restyle for the new visual rhythm — keep the bar visuals (lifetime bar, SUB stripe, EAF label placement) untouched.

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/timeline/CardRow.tsx`

- [ ] **Step 1: Restyle the gutter container**

Read `frontend/src/pages/RoadmapTool/components/timeline/CardRow.tsx`. Locate the row's outer wrapper or the gutter `<div>` (the left 220px region). Adjust its hover state so the gutter highlights to `hover:bg-surface-2/40` on row hover (matching the SpendTab body row in Plan 3).

The CardThumb size, the SVG glyph rendering, the lifetime bar `<div>` (with `style={{ background: ... }}`), the SUB stripe overlay, and the EAF label placement logic (`measureEafLabelPx` etc.) stay exactly as-is — these are calc semantics in CSS clothing.

- [ ] **Step 2: Tighten gutter typography**

Card name should be 13px Inter 500 in `--color-ink`. Income-summary line should be 11px in `--color-ink-faint` with `tnum-mono` for the dollar amounts. Find the `<div>` or `<span>` rendering the card name and the per-year summary — adjust their classNames to:

- Card name: `text-sm font-medium text-ink truncate`
- Income summary: `text-[11px] text-ink-faint tnum-mono truncate`

Per-year summary content (e.g. `+$<n>/yr · <secondary> · <credits> · <housing fee>`) stays the same — only the typography classes change.

- [ ] **Step 3: Lock badge / toggle layout**

Owned cards render a lock SVG; future cards render a `Toggle` primitive. Both should sit at the right edge of the gutter, vertically centered. If the current code uses inconsistent margins, normalize to `ml-auto shrink-0` on the lock/toggle wrapper.

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA** — skip; controller will do this.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/timeline/CardRow.tsx
git commit -m "RoadmapTool/CardRow: gutter typography, hover tint, lock/toggle alignment"
```

---

## Task 4: Spend tab — header, toolbar, table chrome

Per spec 8, restyle `SpendTabContent` and the surrounding `SpendPanel` to match the soft-dashboard direction.

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/spend/SpendTabContent.tsx`
- Modify: `frontend/src/pages/RoadmapTool/components/spend/SpendPanel.tsx`

- [ ] **Step 1: Wrap SpendTab content in a shadow-card**

Read `frontend/src/pages/RoadmapTool/components/spend/SpendPanel.tsx` (small file). Update its outer `<div>` className to match the Roadmap Timeline outer container:

```tsx
<div className="bg-surface border border-divider rounded-xl shadow-card min-w-0 min-h-0 h-full flex flex-col overflow-hidden p-4">
  <SpendTabContent ... />
</div>
```

(Or whatever wrapping currently exists — replace it with a single shadow-card-bordered container that the SpendTabContent renders inside.)

- [ ] **Step 2: Restyle SpendTabContent header**

In `SpendTabContent.tsx`, find any header/heading at the top of the file's JSX. Restyle to match the Roadmap header pattern — `<h2 className="text-ink font-semibold text-base tracking-tight">Spend</h2>` plus a subtitle in `text-ink-muted text-sm`.

If SpendTabContent currently has a `Calculate` prompt banner (around the `showCalculatePrompt` branch), update its className to match the soft-dashboard chrome: `bg-accent-soft text-accent border border-accent/30 rounded-md` (or similar light tint). Drop any heavy backgrounds.

- [ ] **Step 3: Restyle the table head**

Find the `<thead>` in `SpendTabContent.tsx`. Update column header classNames so each `<th>` reads as a quiet eyebrow:

```tsx
<th className="text-left text-[11px] font-semibold uppercase tracking-wider text-ink-faint px-3 py-3 border-b border-divider">
  ...
</th>
```

Apply this to all column heads — Category, Annual Spend, Annual Point Income, Top ROS Card. Adjust per-column alignment (`text-center` on numeric columns) as already in the file.

- [ ] **Step 4: Restyle table body rows + inline edits**

Find each `<tr>` in the body. Replace its className with `border-b border-divider/60 last:border-b-0 hover:bg-surface-2/40 transition-colors`.

For the inline-edit inputs in the spend amount cells, replace their `bg-surface-2 border border-divider focus:border-accent` chrome with the hover-border field-language used in Plan 3:

```tsx
className="w-full min-w-0 bg-transparent border border-transparent hover:border-divider focus:bg-surface focus:border-accent focus:ring-2 focus:ring-accent-soft text-ink text-sm tnum-mono text-right pl-4 pr-1.5 py-1 rounded outline-none placeholder:text-ink-faint transition-colors"
```

(Same idiom as the SpendingTab editable spend amounts in Plan 3.)

- [ ] **Step 5: Restyle the Total row**

Find the `<tr>` rendering the "Total" sticky row (search for `Total`). Replace its className with `bg-surface-2/40 border-b border-divider`. Inside, the `<td>` cells use `text-ink font-semibold` for the total label and `tnum-mono font-bold` for the values — preserve current alignment but match the Plan 3 SpendingTab total-row treatment.

- [ ] **Step 6: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 7: Visual QA** — skip; controller will do this.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/spend/SpendTabContent.tsx frontend/src/pages/RoadmapTool/components/spend/SpendPanel.tsx
git commit -m "RoadmapTool/Spend: shadow-card outer, eyebrow column heads, hover-edit inputs"
```

---

## Task 5: ScenarioPicker dropdown panel

Plan 4a touched only the trigger button. Now update the dropdown panel itself to match the new soft-dashboard popovers (used in Profile and Plan 4a's hero stats).

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/ScenarioPicker.tsx`

- [ ] **Step 1: Restyle the dropdown panel**

Read `ScenarioPicker.tsx`. Find the dropdown panel (likely a `<div>` with `absolute` positioning, after the trigger `<button>`). Replace its className to use the new soft popover treatment:

```tsx
className="absolute right-0 mt-2 w-72 bg-surface rounded-xl shadow-modal z-50 overflow-hidden"
```

(Drop any `border border-divider` if present — `shadow-modal` does the work.)

- [ ] **Step 2: Restyle per-scenario rows**

Find the rendering of each scenario row (likely a `<button>` or `<li>`). Update its className so the active scenario gets `bg-accent-soft` and inactive gets `hover:bg-surface-2`. Replace any heavy backgrounds:

```tsx
className={`w-full flex items-center gap-2 px-3 py-2 text-left transition-colors ${
  s.id === currentId
    ? 'bg-accent-soft text-accent'
    : 'text-ink hover:bg-surface-2'
}`}
```

- [ ] **Step 3: Restyle "Add Scenario" + per-row action buttons**

The dropdown has an "Add Scenario" affordance at the bottom and per-row action buttons (set as default, delete). Update their classNames:

- Bottom CTA: `flex items-center gap-2 px-3 py-2 text-sm font-medium text-accent hover:bg-accent-soft border-t border-divider transition-colors`
- Per-row action buttons (icon-only): `p-1 rounded text-ink-faint hover:text-ink hover:bg-surface-2 transition-colors`. The delete should hover to `text-neg` instead.

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA** — skip; controller will do this.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/ScenarioPicker.tsx
git commit -m "RoadmapTool/ScenarioPicker: soft modal panel, accent-soft active row"
```

---

## Task 6: CurrencySettingsDropdown + WalletPortalSharesEditor popovers

Both are popovers triggered from the timeline group headers. They share form-field language with the rest of the app.

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/summary/CurrencySettingsDropdown.tsx`
- Modify: `frontend/src/pages/RoadmapTool/components/summary/WalletPortalSharesEditor.tsx`

- [ ] **Step 1: Restyle CurrencySettingsDropdown**

Read the file. It's a popover with form fields for CPP override and per-scenario balance. Replace the inputs' chrome to match the foundation `Input` field-language (1px gray-200 border, hover gray-300, focus accent + soft ring). Replace any custom save/cancel buttons with foundation `Button` primary/secondary variants.

Specifically:
- Section title spans: `text-[11px] uppercase tracking-wider text-ink-faint font-semibold mb-2`
- Field label: `text-xs font-medium text-ink-muted mb-1.5`
- Input: `w-full bg-surface border border-divider hover:border-divider-strong focus:border-accent focus:ring-2 focus:ring-accent-soft text-ink text-sm rounded-md px-3 py-2 outline-none transition-colors`

- [ ] **Step 2: Restyle WalletPortalSharesEditor**

Same treatment — read the file, identify form fields and surrounding chrome, apply the same field language. Buttons become foundation `Button` primary/secondary.

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA** — skip; controller will do this.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/summary/CurrencySettingsDropdown.tsx frontend/src/pages/RoadmapTool/components/summary/WalletPortalSharesEditor.tsx
git commit -m "RoadmapTool/currency-settings: foundation field language + Button primitives"
```

---

## Task 7: Three small modals

`AddScenarioModal`, `ApplicationRuleWarningModal`, `DeleteCardWarningModal` all need the new modal chrome from Plan 1 (already in `Modal` primitive) plus updated form fields / button styling.

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/AddScenarioModal.tsx`
- Modify: `frontend/src/pages/RoadmapTool/components/ApplicationRuleWarningModal.tsx`
- Modify: `frontend/src/components/cards/DeleteCardWarningModal.tsx`

- [ ] **Step 1: AddScenarioModal**

Read the file. Convert the form to use the foundation `Field` + `Input` primitives. The Save button should be `Button variant="primary"`, Cancel `variant="secondary"`. Drop any custom button chrome.

- [ ] **Step 2: ApplicationRuleWarningModal**

Read the file. Add a warn-tinted icon header band at the top of the modal:

```tsx
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
```

Replace any custom modal scaffolding with the foundation `Modal` + `ModalBody` + `ModalFooter` primitives. Primary continue button uses `Button variant="primary"`.

- [ ] **Step 3: DeleteCardWarningModal**

Read the file. Add a neg-tinted icon header band (same pattern as ApplicationRuleWarningModal but `bg-neg/10 text-neg` and a trash-can icon). Convert the Delete button to a filled-`neg` style:

```tsx
<button
  type="button"
  onClick={onConfirm}
  className="inline-flex items-center gap-2 text-sm font-medium px-4 py-2 rounded-md bg-neg text-white hover:opacity-90 transition-opacity disabled:opacity-50"
  disabled={isLoading}
>
  Delete
</button>
```

Cancel button uses foundation `Button variant="secondary"`.

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA** — skip; controller will do this.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/AddScenarioModal.tsx frontend/src/pages/RoadmapTool/components/ApplicationRuleWarningModal.tsx frontend/src/components/cards/DeleteCardWarningModal.tsx
git commit -m "RoadmapTool/modals: warn/neg-tinted header bands, foundation field+button primitives"
```

---

## Task 8: TimelineAxis tick labels

Tiny styling refresh — tick labels move to 10–11px ink-faint per spec 7.4.

**Files:**
- Modify: `frontend/src/components/cards/TimelineAxis.tsx`

- [ ] **Step 1: Update tick label classNames**

Read the file. Find the year-tick label `<span>` (rendering the year string). Replace its className with `text-[10px] tnum-mono text-ink-faint`. If month or sub-year tick labels exist, give them the same treatment.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/cards/TimelineAxis.tsx
git commit -m "components/cards/TimelineAxis: 10px ink-faint tick labels"
```

---

## Task 9: Final visual QA

End-to-end Roadmap Tool QA in light + dark before merge. Combined with Plan 4a, every Roadmap Tool surface except the WalletCardModal (Plan 4c) is now restyled.

**Files:**
- (Verify only.)

- [ ] **Step 1: Run lint**

Run: `cd frontend && npm run lint`
Expected: same 3 pre-existing findings. NO new findings.

- [ ] **Step 2: Production build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Walk through `/roadmap-tool` light mode**

Sign in. Navigate to `/roadmap-tool`. Confirm:

- **Page header + hero stats + calc-inputs strip + tabs** still match Plan 4a — unchanged.
- **Timeline tab toolbar:** `+ Add card` secondary button on the left, rule alert chip(s) inline next to it (when violations exist) in tonal pill form, legend (Active card · SUB earning) on the right.
- **Currency group cards:** soft surface, hover tint on the header row, expand chevron rotates on click. The CPP / balance / EAF readouts stay as before.
- **Card row gutter:** card thumb · name (13px Inter 500) · income summary (11px ink-faint mono) · lock badge or toggle on the right. Hover tints the gutter.
- **Lifetime bars:** unchanged — same colors, same SUB stripes, same EAF label placement.
- **Spend tab:** soft outer card. Eyebrow column heads. Inline-edit inputs are transparent at rest; hover bumps to gray-200; focus shows accent border + ring.
- **ScenarioPicker dropdown:** click the picker — soft white panel, soft modal shadow, hover-tinted rows, accent-soft active scenario.
- **CurrencySettingsDropdown / WalletPortalSharesEditor:** click the popover triggers in a currency group — clean form-field language.
- **Modals:** trigger AddScenario, ApplicationRuleWarning, DeleteCard — each shows the new modal chrome (no border, soft shadow, 14px radius). Warn / neg tinted icon header bands where appropriate.
- **TimelineAxis:** tick labels are 10px ink-faint.

- [ ] **Step 4: Walk through `/roadmap-tool` dark mode**

Toggle theme. Re-walk the same checklist. Confirm:
- All shadow-card surfaces still readable on the dark page.
- Accent crimson, warn yellow, neg red, pos green all visible.
- Rule alert chips read clearly against the dark surface.
- Inline-edit inputs show focus ring against dark surface.

- [ ] **Step 5: Commit a final QA marker**

```bash
git commit --allow-empty -m "RoadmapTool/content: visual QA pass complete (light + dark, Timeline + Spend + popovers + modals)"
```

---

## Plan complete

After Task 9, every Roadmap Tool surface except `WalletCardModal` is in the new soft-dashboard direction. Plan 4c handles the 2,000-line modal with its 4 internal tabs.
