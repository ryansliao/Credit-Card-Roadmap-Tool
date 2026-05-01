# Roadmap Tool Redesign — Soft Dashboard

**Date:** 2026-05-01
**Status:** Design proposal, awaiting user review
**Scope:** Visual + structural redesign of the Roadmap Tool routes and the modals invoked from them. Profile, Home, navbar, and sign-in flow are out of scope.

## Goal

Make the Roadmap Tool calmer and more contemporary for first-time users, without removing any information or functionality that advanced users rely on. The timeline concept stays intact.

## Constraints (from the user)

- Every metric currently shown must remain reachable somewhere — fine to nest behind expansion or hover, not fine to remove.
- The timeline concept (per-card lifetime bars on a horizontal time axis, grouped by reward currency, with SUB earning segments) is preserved.
- Otherwise, restructure freely.

## Decisions made during brainstorming

| Axis | Choice | Notes |
| --- | --- | --- |
| Visual direction | **Soft dashboard** (Notion / Stripe-feeling) | Picked from Editorial Refined / Modern Minimal / Soft Dashboard. White cards on a neutral page, gentle shadows, big confident numbers, generous whitespace. |
| Layout structure | **Section-stacked + horizontal tabs** | "C with B's tabs": stats hero is always visible at top; horizontal tabs (Timeline / Spend) switch the main content area. The current vertical-binder-tab spine is removed. |
| Information policy | **No reduction; some popovers become inline accordions** | Category-mapping breakdown moves from popover to row-expand. Stat info icons stay (per-stat info button rather than one global help button). |
| Timeline visual metaphor | **Preserved** | Per-card lifetime bar with striped SUB segment, rounded edges only when the bar end is inside the visible window, EAF label placed inside / right-of / left-of the bar based on space — semantics carry over. |

## Section 1 — Foundation revisions

This work supersedes the visual portion of `2026-04-28-frontend-design-system-design.md` for the Roadmap Tool only. Token names stay; some token values shift to support the new direction. Other pages still use the current values.

### 1.1 Color tokens

| Token | Current (light) | Proposed (light) | Rationale |
| --- | --- | --- | --- |
| `--color-page` | `#faf8f3` (cream) | `#f3f4f6` (neutral gray-100) | Matches the soft-dashboard reference picked during brainstorming. Cooler, less editorial. |
| `--color-surface` | `#ffffff` | `#ffffff` | Unchanged. |
| `--color-surface-2` | `#ebe5d6` (warm tan) | `#fafbfc` (very light gray) | Used for hover, sub-panel, mapping accordion. |
| `--color-divider` | `#c2b89e` (warm tan) | `#e5e7eb` (gray-200) | Hairline rules instead of warm warm tan; replaces "panel border" feel with "soft card on page" feel. |
| `--color-divider-strong` | `#a09173` | `#d1d5db` (gray-300) | Same shift, one step darker. |
| `--color-ink` | `#1a1a1a` | `#111827` (gray-900) | Slightly cooler ink to match the cooler page. |
| `--color-ink-muted` | `#3f3a30` | `#4b5563` (gray-600) | Same. |
| `--color-ink-faint` | `#6e6452` | `#9ca3af` (gray-400) | Same. |
| `--color-accent` | `#b04256` (crimson) | **Keep `#b04256`** | Brand identity. The mockups used indigo placeholder; final spec routes accent UI through the existing oxblood. |
| `--chart-points` | `#4f46e5` (indigo) | **Keep** | Timeline point-currency bars and SUB stripe. |
| `--chart-cash` | `#16a34a` (green) | **Keep** | Cash-back currency bars. |
| `--shadow-card` | `0 1px 2px rgba(26,26,26,0.04), 0 1px 1px rgba(26,26,26,0.02)` | `0 1px 2px rgba(17,24,39,0.04), 0 1px 3px rgba(17,24,39,0.04)` | Soft cards now lean on shadow (not borders) for depth — second layer adds a touch more depth without becoming a "popped" card. |

Dark-mode equivalents follow the same shift (cool-gray scale instead of warm-brown scale; accent stays).

### 1.2 Typography

- **Inter** is the default for everything in the Roadmap Tool — UI chrome, body, hero numbers, modal headings.
- **JetBrains Mono** retained for tabular numerals via `.tnum-mono`.
- **Fraunces** is no longer used by the Roadmap Tool; it stays loaded for other pages that opt into it.
- Hero stat values: 26px Inter weight 700, letter-spacing −0.02em, `font-variant-numeric: tabular-nums`.
- The page wordmark "Roadmap" is Inter Bold tight (not serif).

### 1.3 Spacing rhythm

- Page padding: existing `max-w-screen-xl mx-auto` unchanged.
- Hero stat card: 16–20px padding, 12px gap between cards.
- Calc-inputs strip: 10px vertical / 14px horizontal.
- Group cards in the timeline: 12px gap between cards.
- Card rows: 50px row height retained (preserves bar visual semantics).
- Modal sections: 18px between sections, 12px between fields.

## Section 2 — Page layout

Top of page (in this vertical order):

1. **Header bar.** Wordmark "Roadmap" · scenario picker pill · "?" help button on the left. The "?" button opens the existing "How the Roadmap Is Calculated" Popover content (currently anchored next to the Calculate button in `index.tsx`) — its position moves; its content is preserved verbatim. Calculate button anchored on the right.
2. **Hero stat trio.** Three soft white cards: **Effective Annual Fee**, **Annual Fees**, **Annual Point Income**. Each shows label · big value · 11px delta line ("net wallet value · 1.5y projection", "across 5 selected cards", "redeemed value"). Each label has an inline `i` info button that opens the existing per-stat Popover content unchanged.
3. **Calc-inputs strip.** Single soft card, horizontal row: Time horizon slider + value · vertical hairline divider · Sign-up bonuses segmented toggle (Include / Exclude). Lower visual weight than the hero stats.
4. **Tabs.** Horizontal underline tabs: `Timeline` (with selected-card count badge — `<n>`) · `Spend`. Active tab uses `--color-accent` for the underline; inactive labels are `--color-ink-faint`.
5. **Active tab content.**

The header bar through tabs become a sticky region; the active tab's content scrolls beneath. Sticky behavior is implementation-time choice (default off; revisit if scroll-then-Calculate ergonomics suffer).

## Section 3 — Timeline tab

### 3.1 Timeline toolbar

Single row directly below the tabs:

- `+ Add card` — dashed-bordered button on the left. Hover: dashed border switches to `--color-accent`, label color follows.
- Issuer-rule warning chip(s) — inline (`warn`-tinted), only rendered when violations exist. Click opens the existing rule-detail Popover.
- **Legend** pushed right — three swatches (Active card window · SUB earning · Add to calc toggle) at 11px ink-faint. The current right-side legend panel from `WalletSummaryStats` is removed; this is its new home.

### 3.2 Currency group card

Each reward currency is a collapsible white card. Header row (always visible):

- Group name (e.g. "Chase Ultimate Rewards") + subtitle (`<n> cards · <cpp>¢/pt · balance <pts>`).
- Group EAF on the right, colored: `--color-pos` for negative (good), default ink for positive.
- Expand/collapse chevron.

When expanded, the group renders:

- A `TimelineAxis` row (existing primitive) immediately under the header, spanning the right gutter.
- The card rows inside the group, separated by hairline dividers.

The current per-currency CPP / portal-share / balance editors keep their popover triggers, repositioned inside the group header (replacing the "expand/collapse cap" affordance from the current `GroupSection`).

### 3.3 Card row

Two-column grid: `220px` left gutter + `1fr` right (the bar track), 50px row height.

**Left gutter** (left → right):

- `CardThumb` 40×26px (existing primitive) — kept.
- Card name (13px Inter 500) + per-year income summary (11px ink-faint, tnum-mono): `+$<n>/yr · <secondary> · <credits> · <housing fee>`. Same content as today, restyled.
- Either a **lock badge** (owned cards — replaces the current padlock SVG, same warn color) OR a **toggle** (future cards — existing `Toggle` primitive).

**Right column:** the lifetime bar.

- Same metaphor: rounded rectangle from open→close, dimmed when disabled.
- SUB earning segment renders as a striped slice anchored at the SUB start — existing `SubEarningSegment` logic preserved.
- EAF label placed inside / right-of / left-of the bar based on space (existing `measureEafLabelPx` placement logic preserved). Color: `--color-pos` for negative, `--color-neg` for positive.
- Disabled bar shows a muted "disabled" label inline.

Hover state highlights the entire row (left gutter + bar track), as today.

### 3.4 Time axis

`TimelineAxis` primitive reused with restyled tick labels (10–11px `--color-ink-faint`). The "today" and "duration end" vertical lines stay (`--color-ink-muted`).

### 3.5 Empty / loading / stale states

| State | Treatment |
| --- | --- |
| Wallet has no cards | Soft empty card with copy "Add cards in Profile to start a roadmap" + secondary CTA back to Profile. Driven by the existing `wallet`/`activeScenarioId` null check in `index.tsx`. |
| No calc yet (`hasNeverCalculated === true`) | Hero stat values render dashed placeholders (`—`); `Calculate` button is the primary action. Card rows show `—/yr`. |
| Stale results (after edit) | Hero stat cards and timeline bars dim to 60% opacity (matches current). Calculate button text becomes `Recalculate` and tone shifts to `warn`. |
| Calculating | Existing 0.5px progress bar at the top of viewport stays (`animate-progress-bar`). |

## Section 4 — Spend tab

### 4.1 Spend toolbar

Soft white card, single row:

- Housing type segmented (Rent / Mortgage)
- Vertical hairline divider
- Foreign spend % numeric input + suffix label "% of eligible categories"

### 4.2 Spend matrix

A single white card. Every row in the card uses the **same** `display: grid; grid-template-columns: minmax(0, 1fr) 130px 130px 220px` so columns line up exactly across header / total / body / mapping rows.

Columns:

1. **Category** — left, `1fr`. Chevron · name · `i` info icon. Click anywhere in the row toggles the mapping accordion.
2. **Annual spend** — right, 130px. Inline-edit input (transparent border at rest, visible on hover, `--color-accent` on focus).
3. **Annual income** — right, 130px. Read-only result. Format: `+$<n> · <ce>¢/$`.
4. **Top earning card** — left, 220px. Compact prev/next cycler (existing logic from current `SpendTabContent`).

A sticky **Total** row sits between the column header and the body rows: total spend (sum), total annual income, and the wallet-wide top-card cycler.

Click a category row to expand a mapping accordion underneath:

- Indented 32px from the left, light tinted background.
- "Maps to earn categories:" label, then pills showing each underlying earn category and its weight % (e.g. "U.S. Supermarkets 85%").

This replaces the current category-info popover for mappings — same data, inline rather than in a popover. The popover-based per-category info icon is preserved for cases where users want it without expanding (e.g. tooltip-only hover).

Category color chips dropped (no longer carry signal at 15 categories).

### 4.3 Spend tab states

| State | Treatment |
| --- | --- |
| No spend yet | Empty state inside the matrix card: "Add your monthly spend in Profile, then come back" + secondary CTA to Profile. |
| No calc yet | Top-card column shows "—" instead of card names; income column shows dashes; toolbar still active so spend can be edited before recalculating. |

## Section 5 — WalletCardModal

Structurally unchanged — same 4 internal tabs (Lifecycle · Bonuses · Credits · Priority), same multi-mode behavior (add-future / edit-overlay / edit-future). Chrome and form fields are restyled.

### 5.1 Modal chrome

- **Header band** (18–20px padding):
  - Card thumbnail (56×36, rounded 5px).
  - Title (17px Inter 600).
  - Chip row beneath the title: `<network>`, `<issuer>`, status (`Owned` warn-tinted / `Future` accent-tinted).
  - Right side: small icon-buttons for History (where the mode supports it) and Remove (opens DeleteCardWarningModal).
- **Tabs band:** 4 horizontal underline tabs, 22px gap. `Lifecycle · Bonuses · Credits · Priority`. Credits has a `<n>` badge when overrides exist.
- **Body:** 18–20px padding, scroll-y, `flex: 1`.
- **Footer band:** Last-calc note ("Last calc · 2 days ago") on the left in `--color-ink-faint`; **Cancel** (secondary) + **Save changes** (primary, accent) on the right.

When no library card is selected yet (add-future mode pre-selection), only the Lifecycle tab is reachable; selecting a card unlocks the rest. Existing logic preserved.

### 5.2 Form-field language

- Field group: 12px label · input · 11px help text.
- Section title: 11px uppercase, `letter-spacing: 0.06em`, `--color-ink-faint`, 8px below.
- Two-column rows: `display: grid; grid-template-columns: 1fr 1fr; gap: 12px`.
- Input rest: `1px solid #e5e7eb`, white background, 8px radius, 13px Inter.
- Input hover: border `#d1d5db`.
- Input focus: border `--color-accent`, ring `0 0 0 3px <accent at 10%>`.

### 5.3 Lifecycle tab

- **Acquisition** section: stack of selectable cards (full-width clickable) instead of the current radiogroup-pills. Each card has a 14px circular radio · label · 1-line description. Selected: accent border + accent-soft tint.
  - "Fresh open" — "New card from this issuer. Counts toward 5/24 and other velocity rules."
  - "Product change" — "Switching from another card. Account number is preserved; doesn't count as a new app."
- **Dates** section: two-column row — Opening date · Close date. Conditional sub-fields (Product change date, Changing from) appear when Acquisition = Product change, in the same field language.

### 5.4 Bonuses tab

Same chrome; existing controls re-skinned to the form-field language:

- Multipliers list: per-row card with category select + multiplier input + remove icon-button.
- Top-N group editor: collapsible block per group; existing semantics.
- Recurring vs first-year-only annual bonus: segmented pill toggle.
- SUB block: min spend · days · bonus pts inputs in a three-column row.

### 5.5 Credits tab

Each credit renders as a small card with:

- **Top row:** name + source line ("From `<issuer>` library default" or "Custom · only on this card") on the left; value-input (right-aligned 90px) on the right.
- **Hairline divider.**
- **Flag row:** two checkboxes — `Excludes first year` and `One-time only` — using a custom 14px filled-square check.

`+ Add credit` is a dashed-border affordance at the bottom of the list, opening the existing credit-search dropdown unchanged.

User-created credits show "Custom" in `--color-accent` text (replacing the current owner badge).

### 5.6 Priority tab

Same chrome; per-category pin list inherits the row-card style. Existing semantics.

## Section 6 — Other modals

- **AddScenarioModal:** small modal (~420px wide). Name input + optional description, primary Save (accent). Adopts the same form-field language and footer.
- **ApplicationRuleWarningModal:** `warn` semantic for the icon and a soft warn-tinted header band; primary action "Continue" in accent. Body uses the existing rule-explanation copy.
- **DeleteCardWarningModal:** `neg` semantic icon header; primary `Delete` button is filled `--color-neg` (replaces the current text-only neg styling). Cancel is secondary.

All modals continue to wrap in `<ModalBackdrop>` per existing convention.

## Section 7 — Other Roadmap Tool surfaces

- **ScenarioPicker:** restyled as a dashboard pill — white surface, soft shadow, chevron — placed inline next to the wordmark in the page header. Open state shows the existing list of scenarios with the same actions (set default, delete, add). Visual restyling only.
- **CurrencySettingsDropdown / WalletPortalSharesEditor:** inherit the soft popover treatment — white card, 12px radius, `--shadow-modal`. Field language matches the modal form fields. No semantic changes.
- **TimelineGlyphs (`CardThumb`, `EditAffordance`):** unchanged.
- **TimelineAxis:** restyled tick labels only (10–11px ink-faint).

## Section 8 — Out of scope

- Profile (`/profile`) page restyle.
- Home page restyle.
- Navbar / sign-in flow.
- Tablet / mobile responsive layouts.
- New animation work beyond the existing hover transitions and progress bar.
- New functionality. Pure visual + structural redesign.

## Section 9 — Implementation sketch

This is a sketch; the canonical step-by-step plan is produced by the writing-plans skill next.

1. **Tokens.** Update `frontend/src/styles/tokens.css` for `--color-page`, `--color-surface-2`, divider tokens, ink tokens, shadow values. Remove warm-tan dependence. Light + dark in lockstep.
2. **Page shell.** Refactor `RoadmapTool/index.tsx` to the new top-down layout: header bar, hero, calc-inputs strip, horizontal tabs, content area. Drop the vertical binder-tabs gutter. Keep the existing data plumbing (queries, mutations, hash signature, snapshot logic) untouched.
3. **Hero stats card.** Replace `WalletSummaryStats`'s 4-panel layout with the 3-stat hero + standalone calc-inputs strip. Same data shape; restyle only. Inline `i` info buttons reuse the existing popover content.
4. **Timeline tab toolbar + currency group card.** Restyle `WalletTimelineChart`'s group section as a soft card with collapsible header. Move legend out of the stats strip into the toolbar. Keep all calc-related rendering (axis, today/end lines, group bar logic) intact.
5. **Card row gutter.** Restyle `CardRow`'s left gutter for the new visual rhythm. Bar visuals (lifetime bar, SUB segment, EAF label placement) unchanged in semantics.
6. **Spend tab.** Rebuild `SpendTabContent` with the shared 4-column grid. Drop the colored category icon. Add the row-expand mapping accordion.
7. **Modal chrome + form-field language.** Update `WalletCardModal` chrome (header band, tabs, footer) and re-skin form fields. Acquisition section converts to selectable-card radio.
8. **Other modals + dropdowns.** Apply the form-field language to `AddScenarioModal`, `ApplicationRuleWarningModal`, `DeleteCardWarningModal`, `ScenarioPicker`, `CurrencySettingsDropdown`, `WalletPortalSharesEditor`.
9. **Visual QA pass.** Snapshot each tab in light and dark mode. Tweak token values for AA contrast as needed (especially the accent on the new gray-100 background).

## Section 10 — Open decisions (defaults noted)

- **Page background exact value** — default `#f3f4f6`. Could push lighter (`#fafafa`) for a more "white page" feel.
- **Whether the calc-inputs strip is sticky** — default not sticky. Sticky keeps the slider always visible but adds chrome.
- **Whether to dim or hide stale results** — default dim (preserves visibility). Could overlay a "Recalculate to refresh" banner instead.
- **Per-stat info icons vs one global help button** — default keep per-stat (matches today; lets each popover own its content).
- **Whether to keep `--color-accent` at the current `#b04256` crimson or shift to the deeper oxblood `#7a1c2c` proposed in the 2026-04-28 design system spec** — default keep current. Shift only if the 04-28 spec is being executed elsewhere first.
