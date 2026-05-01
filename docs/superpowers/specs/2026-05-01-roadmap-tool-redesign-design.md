# App-Wide Soft-Dashboard Redesign

**Date:** 2026-05-01
**Status:** Design proposal, awaiting user review
**Scope:** App-wide visual + structural redesign. Covers tokens, the UI primitive library, the app shell (navbar / sign-in / username gates / error boundary), the Home landing page, the Profile settings page (4 tabs), and the Roadmap Tool routes including all modals invoked from them. The Styleguide page is updated only insofar as it must reflect the new primitive states.

## Goal

Replace the warm-editorial visual language across the entire frontend with a calmer, more contemporary "soft dashboard" direction (Notion / Stripe-feeling: white cards on neutral page, gentle shadows, big confident numbers, generous whitespace). Make the app less overwhelming for first-time users without removing any information or functionality that advanced users rely on. The Roadmap Tool's timeline concept is preserved.

## Constraints (from the user)

- Every metric currently shown must remain reachable somewhere — fine to nest behind expansion or hover, not fine to remove.
- The timeline concept (per-card lifetime bars on a horizontal time axis, grouped by reward currency, with SUB earning segments) is preserved.
- Otherwise, restructure freely.
- The whole app should follow the new design philosophy — not just the Roadmap Tool. UI primitives, the navbar, sign-in surfaces, Home, and Profile all get the same treatment.

## Decisions made during brainstorming

| Axis | Choice | Notes |
| --- | --- | --- |
| Visual direction | **Soft dashboard** (Notion / Stripe-feeling) | Picked from Editorial Refined / Modern Minimal / Soft Dashboard. White cards on a neutral page, gentle shadows, big confident numbers, generous whitespace. |
| Roadmap layout | **Section-stacked + horizontal tabs** | "C with B's tabs": stats hero is always visible at top; horizontal tabs (Timeline / Spend) switch the main content area. The current vertical-binder-tab spine is removed. |
| Information policy | **No reduction; some popovers become inline accordions** | Category-mapping breakdown moves from popover to row-expand. Stat info icons stay (per-stat info button rather than one global help button). |
| Timeline visual metaphor | **Preserved** | Per-card lifetime bar with striped SUB segment, rounded edges only when the bar end is inside the visible window, EAF label placed inside / right-of / left-of the bar based on space — semantics carry over. |
| Scope | **App-wide** | Confirmed mid-brainstorm. The token and primitive changes flow into Home, Profile, and the app shell, not just the Roadmap Tool. |

## Section 1 — Foundation revisions

This work supersedes the visual portion of `2026-04-28-frontend-design-system-design.md`. Token names stay; some token values shift to support the new direction.

### 1.1 Color tokens

| Token | Current (light) | Proposed (light) | Rationale |
| --- | --- | --- | --- |
| `--color-page` | `#faf8f3` (cream) | `#f3f4f6` (neutral gray-100) | Matches the soft-dashboard reference picked during brainstorming. Cooler, less editorial. |
| `--color-surface` | `#ffffff` | `#ffffff` | Unchanged. |
| `--color-surface-2` | `#ebe5d6` (warm tan) | `#fafbfc` (very light gray) | Used for hover, sub-panel, mapping accordion. |
| `--color-divider` | `#c2b89e` (warm tan) | `#e5e7eb` (gray-200) | Hairline rules instead of warm tan; replaces "panel border" feel with "soft card on page" feel. |
| `--color-divider-strong` | `#a09173` | `#d1d5db` (gray-300) | Same shift, one step darker. |
| `--color-ink` | `#1a1a1a` | `#111827` (gray-900) | Slightly cooler ink to match the cooler page. |
| `--color-ink-muted` | `#3f3a30` | `#4b5563` (gray-600) | Same. |
| `--color-ink-faint` | `#6e6452` | `#9ca3af` (gray-400) | Same. |
| `--color-accent` | `#b04256` (crimson) | **Keep `#b04256`** | Brand identity. The mockups used indigo placeholder; final spec routes accent UI through the existing oxblood. |
| `--chart-points` | `#4f46e5` (indigo) | **Keep** | Timeline point-currency bars and SUB stripe. |
| `--chart-cash` | `#16a34a` (green) | **Keep** | Cash-back currency bars. |
| `--shadow-card` | `0 1px 2px rgba(26,26,26,0.04), 0 1px 1px rgba(26,26,26,0.02)` | `0 1px 2px rgba(17,24,39,0.04), 0 1px 3px rgba(17,24,39,0.04)` | Soft cards now lean on shadow (not borders) for depth. |

Dark-mode equivalents follow the same shift (cool-gray scale instead of warm-brown scale; accent stays).

### 1.2 Typography

- **Inter** is the default for everything app-wide — UI chrome, body, hero numbers, modal headings.
- **JetBrains Mono** retained for tabular numerals via `.tnum-mono`.
- **Fraunces** is dropped from the dependency tree entirely. Inter weights cover everything previously rendered in Fraunces (display headlines, hero stat values, modal titles).
- Hero stat values: 26px Inter weight 700, letter-spacing −0.02em, `font-variant-numeric: tabular-nums`.
- Wordmarks (e.g. "Roadmap"): Inter Bold tight (not serif).

### 1.3 Spacing rhythm

- Page padding container: existing `max-w-screen-xl mx-auto` for app surfaces, `max-w-6xl` for marketing pages — unchanged.
- Card padding: 16–20px standard.
- Section gap (between cards): 12px standard, 16px between major regions.
- Modal sections: 18px between sections, 12px between fields.
- Form fields: 6px between label and input, 11px help text below.

## Section 2 — UI primitive library

The primitives in `frontend/src/components/ui/<Primitive>/index.tsx` are restyled in lockstep with the token shift. **No primitive APIs change** — surface-level CSS only — so consumers don't have to migrate. The Styleguide page (`pages/Styleguide`) is the visual regression target for this section.

| Primitive | Change |
| --- | --- |
| `Button` | Primary uses `--color-accent` filled, white text, soft shadow; secondary is white with a 1px gray-200 border; `icon` and `tone` variants follow. Hover states lighten by 4% (instead of darkening); focus rings use accent at 10%. |
| `Input` | White background, 1px gray-200 border, 8px radius, 13px Inter. Hover bumps to gray-300; focus shows accent border + 3px accent-soft ring. Error state uses `--color-neg`. |
| `Field` | 12px label, 6px gap, optional 11px help text. |
| `Select` | Same chrome as Input; chevron in `--color-ink-faint`. |
| `Checkbox` | 14px square, 3px radius, accent fill on check. |
| `Toggle` | 28×16 pill, accent on / gray-300 off, 12px white knob. (Already close — colors only.) |
| `Modal` | 14px radius shell, 18–20px head/body padding, soft drop shadow (`--shadow-modal`), header has hairline divider. |
| `Drawer` | Same surface treatment; 14px radius left edge, hairline divider with main content. |
| `Popover` | 12px radius, white surface, soft shadow, 12px padding for prose content. Pure visual update. |
| `Tooltip` | Dark-on-light variant: very dark gray-900 background, white text, 6px radius, 11px Inter. |
| `Tabs` | Underline-style tabs (already close); active uses `--color-accent` for the underline; inactive labels are `--color-ink-faint`. |
| `Toast` | White surface, 12px radius, soft shadow, semantic icon left, dismiss right. |
| `Surface` | Pure white, 12px radius, `--shadow-card`. The default container building block. |
| `Heading` | Inter weights only (drop Fraunces dependency). Levels 1–4 map to 28 / 22 / 17 / 14 px with `letter-spacing: -0.01em` on the larger sizes. |
| `Eyebrow` | 11px uppercase, letter-spacing 0.06em, `--color-ink-faint`. (Mostly unchanged.) |
| `Badge` | Subtle by default (gray-100 bg, gray-700 text); semantic variants (`pos` / `neg` / `warn` / `accent`) tint background and text. |
| `Stat` | New canonical hero-stat card layout: label (with optional `i` info button) · value (26px tnum) · 11px delta line. |
| `Money` / `Points` | Numeric formatting unchanged; pick up the new mono font. |
| `DataTable` | Hairline rows, sticky header on `--color-surface`, hover row tint `--color-surface-2`. Used by Profile spending and other table surfaces. |
| `ThemeToggle` | Visual restyle to match the new icon-button language; sun/moon glyphs preserved. |

The `Styleguide` page must render every primitive in light + dark and serve as the QA target for this section.

## Section 3 — App shell

The shell lives in `frontend/src/App.tsx` (~430 lines). Restyle all of these in place; no extraction is required.

### 3.1 Navbar

The current navbar is a thin wordmark + nav links + sign-in dropdown / user pill. New treatment:

- Background: `--color-surface` with a 1px `--color-divider` bottom border (replaces the subtle gradient feel).
- Wordmark: 17px Inter 700 in `--color-ink`. Click goes home.
- Nav links: 13px Inter 500, `--color-ink-faint` rest, `--color-ink` hover, `--color-accent` for the active route (with a 2px accent underline 6px below the label).
- Right side: theme toggle · sign-in dropdown / user pill.

### 3.2 SignInDropdown (App.tsx · `SignInDropdown` function)

- Trigger button: pill, white surface, soft shadow, 13px Inter 500, label "Sign in".
- Dropdown panel: 280–320px wide, 12px radius, `--shadow-modal`, opens below-right.
- Tab row at the top: "Sign in" / "Create account" — same underline-tab language as elsewhere.
- Form: stacked fields in the new field language. Primary `Continue` button uses accent.
- Google sign-in button: white with Google's logo, 1px gray-200 border, 13px Inter 500. Sits below the email/password form with a 1px hairline `or` divider.
- Errors: red text in `--color-neg`, 11px below the form, no shouting backgrounds.

### 3.3 UsernamePrompt (App.tsx · `UsernamePrompt` function)

The post-OAuth username gate. New treatment:

- Renders as a `Modal` (already does); inherits the new modal chrome.
- Body has a soft welcoming heading + 1-line subtitle, then a single `Field` for username, then a primary `Continue` button.
- Validation errors render inline beneath the field.

### 3.4 AuthGate (App.tsx · `AuthGate` function)

Pure logic; no visual surface. Preserved.

### 3.5 UsernameGate (App.tsx · `UsernameGate` function)

Same — pure logic, only renders `UsernamePrompt`. Preserved.

### 3.6 ErrorBoundary (App.tsx top class component)

- Page-level error UI restyled: centered card with neg-tinted icon, `Heading` level 2 "Something went wrong", monospace error message in a `--color-surface-2` tinted card with 8px radius, primary "Reload" button.

## Section 4 — Home page

Currently `pages/Home.tsx` (~260 lines): hero with eyebrow pill + headline + description + CTA, then "How it works" / "Your setup" steps, plus auth-aware variants. New treatment:

### 4.1 Hero

- Container: `max-w-6xl` (current) — unchanged.
- Eyebrow pill: gray-100 surface with a 1.5px dot, 11px Inter 500, `--color-ink-faint` text, `--color-accent` dot. (Replaces the current accent-tinted pill, which reads loud against the new neutral page.)
- Headline: 48–56px Inter 700, `letter-spacing: -0.02em`, `--color-ink`. The accent phrase ("actually pay off.") gets `--color-accent` color, no underline.
- Description: 18px Inter 400, `--color-ink-muted`, `max-w-2xl`.
- Primary CTA: large pill (`--color-accent` filled, white text, 12px radius, soft shadow, 14px Inter 600). Hover lightens 4%.
- Auth-known footnote (e.g. "Takes about two minutes to set up") in 13px Inter 400, `--color-ink-faint`.

### 4.2 Steps section

- Eyebrow: "How it works" / "Your setup" — 11px uppercase, `--color-ink-faint`.
- Section heading: 28–32px Inter 700 with the dynamic copy from current logic.
- Step cards: 3-up grid on lg, stacked on smaller widths. Each card is a `Surface` with a small rounded number marker (1, 2, 3), title, 1–2 line description, and a state pill (`pending` / `current` / `complete` / `preview`). Step numbers and active-step styling follow the existing logic.
- "Current" step gets accent border + accent-soft tint.
- "Complete" step uses `pos` semantic color for the marker.
- "Preview" step is dimmed.

### 4.3 Closing section / footer

- A quiet final card with a single CTA, "Open the Roadmap Tool" once setup is complete; otherwise omitted.
- Footer is reduced to a single hairline-bordered band with copy and a help link in `--color-ink-faint`.

## Section 5 — Profile page

`pages/Profile/index.tsx` (~70 lines) is the shell; tabs live under `pages/Profile/components/`. The shell uses a left-rail vertical nav (4 tabs) + content card. Restyling:

### 5.1 Profile shell

- Container: keep `max-w-5xl mx-auto`.
- Sidebar nav (left rail, 192px): each tab is a `flex` row with icon + label, 8px radius, 8–12px padding. Rest: `--color-ink-faint`. Hover: `--color-ink` + `--color-surface-2` background. Active: `--color-ink` + `--color-surface-2` background + 2px accent left rule.
- Content card: `Surface` (white, 12px radius, soft shadow). Padding 24px.

### 5.2 WalletTab

The owned-cards view. Existing pattern is a list of `CardTile`s; new treatment:

- Section title bar inside the content card: "Your cards" + "Add card" button right.
- Each card row: thumbnail + name + issuer/network chips + key dates (opening, last calc, status badge "Owned"). Click opens `WalletCardModal` in `edit-overlay`-style mode.
- Add affordance: dashed-bordered button at the bottom of the list.

### 5.3 SpendingTab

The annual-spend editor + per-category weight overrides. New treatment:

- Top bar: housing type segmented (Rent / Mortgage), foreign spend % numeric input — same pattern as Roadmap's Spend toolbar.
- Below it: per-category accordion list using the same `display: grid` row pattern as Roadmap's Spend matrix (Category · Amount input · expand chevron). Expanded state shows the `CategoryWeightEditor` inline (existing component, restyled per the new field language).
- Total at the top of the list (sticky inside the card).

### 5.4 AppearanceTab

Currently theme + density settings. New treatment:

- Theme toggle as a 2-up card grid (Light · Dark): each card shows a tiny illustrated preview of the theme.
- Reduced motion / contrast toggles in the new toggle language.

### 5.5 SettingsTab

Account settings (display name, email, sign-out, delete account). New treatment:

- Form fields in the new language.
- Destructive actions ("Delete account") in a clearly-separated section at the bottom with `--color-neg` semantic and a confirmation modal.
- Sign out as a secondary button.

## Section 6 — Roadmap Tool · page layout

Top of the Roadmap Tool route, in this vertical order:

1. **Header bar.** Wordmark "Roadmap" · scenario picker pill · "?" help button on the left. The "?" button opens the existing "How the Roadmap Is Calculated" Popover content (currently anchored next to the Calculate button in `index.tsx`) — its position moves; its content is preserved verbatim. Calculate button anchored on the right.
2. **Hero stat trio.** Three soft white cards: **Effective Annual Fee**, **Annual Fees**, **Annual Point Income**. Each shows label · big value · 11px delta line. Each label has an inline `i` info button that opens the existing per-stat Popover content unchanged.
3. **Calc-inputs strip.** Single soft card, horizontal row: Time horizon slider + value · vertical hairline divider · Sign-up bonuses segmented toggle (Include / Exclude). Lower visual weight than the hero stats.
4. **Tabs.** Horizontal underline tabs: `Timeline` (with selected-card count badge — `<n>`) · `Spend`. Active tab uses `--color-accent` for the underline; inactive labels are `--color-ink-faint`.
5. **Active tab content.**

The header bar through tabs become a sticky region; the active tab's content scrolls beneath. Sticky behavior is implementation-time choice (default off; revisit if scroll-then-Calculate ergonomics suffer).

## Section 7 — Roadmap Tool · Timeline tab

### 7.1 Timeline toolbar

Single row directly below the tabs:

- `+ Add card` — dashed-bordered button on the left. Hover: dashed border switches to `--color-accent`.
- Issuer-rule warning chip(s) — inline (`warn`-tinted), only rendered when violations exist.
- **Legend** pushed right — three swatches (Active card window · SUB earning · Add to calc toggle) at 11px ink-faint. The current right-side legend panel from `WalletSummaryStats` is removed; this is its new home.

### 7.2 Currency group card

Each reward currency is a collapsible white card. Header row (always visible): group name + subtitle (`<n> cards · <cpp>¢/pt · balance <pts>`), group EAF on the right (colored: `--color-pos` for negative), expand/collapse chevron.

When expanded: `TimelineAxis` row immediately under the header; card rows beneath, separated by hairline dividers. Per-currency CPP / portal-share / balance editors keep their popover triggers, repositioned inside the group header.

### 7.3 Card row

Two-column grid: 220px left gutter + `1fr` right (the bar track), 50px row height.

**Left gutter:** `CardThumb` 40×26px (existing primitive, kept) → card name (13px Inter 500) + per-year income summary (11px ink-faint, tnum-mono): `+$<n>/yr · <secondary> · <credits> · <housing fee>` → lock badge (owned) or toggle (future).

**Right column:** the lifetime bar — same metaphor: rounded rectangle from open→close, dimmed when disabled, SUB earning segment renders as a striped slice anchored at the SUB start (`SubEarningSegment` logic preserved), EAF label placed inside / right-of / left-of the bar based on space (`measureEafLabelPx` placement logic preserved). Disabled bar shows a muted "disabled" label inline.

Hover state highlights the entire row.

### 7.4 Time axis

`TimelineAxis` primitive reused with restyled tick labels (10–11px `--color-ink-faint`). The "today" and "duration end" vertical lines stay (`--color-ink-muted`).

### 7.5 Empty / loading / stale states

| State | Treatment |
| --- | --- |
| Wallet has no cards | Soft empty card with copy "Add cards in Profile to start a roadmap" + secondary CTA back to Profile. Driven by the existing `wallet`/`activeScenarioId` null check in `index.tsx`. |
| No calc yet (`hasNeverCalculated === true`) | Hero stat values render dashed placeholders (`—`); `Calculate` button is the primary action. Card rows show `—/yr`. |
| Stale results (after edit) | Hero stat cards and timeline bars dim to 60% opacity (matches current). Calculate button text becomes `Recalculate` and tone shifts to `warn`. |
| Calculating | Existing 0.5px progress bar at the top of viewport stays. |

## Section 8 — Roadmap Tool · Spend tab

### 8.1 Spend toolbar

Soft white card, single row: housing type segmented · vertical hairline divider · foreign spend % numeric input + suffix label.

### 8.2 Spend matrix

A single white card. Every row uses the **same** `display: grid; grid-template-columns: minmax(0, 1fr) 130px 130px 220px` so columns line up exactly across header / total / body / mapping rows.

Columns:

1. **Category** — left, `1fr`. Chevron · name · `i` info icon. Click anywhere in the row toggles the mapping accordion.
2. **Annual spend** — right, 130px. Inline-edit input.
3. **Annual income** — right, 130px. Read-only result. Format: `+$<n> · <ce>¢/$`.
4. **Top earning card** — left, 220px. Compact prev/next cycler.

A sticky **Total** row sits between the column header and the body rows. Click a category row to expand a mapping accordion underneath: pills showing each underlying earn category and its weight % (replaces the popover-based mapping breakdown). Category color chips dropped.

### 8.3 Spend tab states

| State | Treatment |
| --- | --- |
| No spend yet | Empty state inside the matrix card with copy "Add your monthly spend in Profile, then come back" + CTA. |
| No calc yet | Top-card column shows "—" instead of card names; income column shows dashes. |

## Section 9 — Roadmap Tool · WalletCardModal

Structurally unchanged — same 4 internal tabs (Lifecycle · Bonuses · Credits · Priority), same multi-mode behavior. Chrome and form fields are restyled.

### 9.1 Modal chrome

- **Header band:** card thumbnail (56×36) · title (17px Inter 600) · chip row with `<network>`, `<issuer>`, status (`Owned` warn-tinted / `Future` accent-tinted) · right-side icon-buttons for History and Remove.
- **Tabs band:** 4 horizontal underline tabs, 22px gap. Credits has a `<n>` badge when overrides exist.
- **Body:** 18–20px padding, scroll-y, `flex: 1`.
- **Footer band:** Last-calc note on the left in `--color-ink-faint`; Cancel (secondary) + Save changes (primary, accent) on the right.

When no library card is selected yet (add-future mode pre-selection), only the Lifecycle tab is reachable. Existing logic preserved.

### 9.2 Form-field language

- Field group: 12px label · input · 11px help text.
- Section title: 11px uppercase, `letter-spacing: 0.06em`, `--color-ink-faint`, 8px below.
- Two-column rows: `display: grid; grid-template-columns: 1fr 1fr; gap: 12px`.
- Input rest: `1px solid #e5e7eb`, white background, 8px radius, 13px Inter.
- Input focus: border `--color-accent`, ring `0 0 0 3px <accent at 10%>`.

### 9.3 Lifecycle tab

- **Acquisition:** stack of selectable cards (full-width clickable). Each card has a 14px circular radio · label · 1-line description. Selected: accent border + accent-soft tint.
- **Dates:** two-column row — Opening date · Close date. Conditional sub-fields appear when Acquisition = Product change.

### 9.4 Bonuses tab

Existing controls re-skinned to the form-field language: multipliers list (per-row card), top-N group editor (collapsible block), recurring vs first-year-only annual bonus toggle (segmented pill), SUB block (three-column row).

### 9.5 Credits tab

Each credit is a small card with: top row (name + source line on the left, value-input on the right) · hairline divider · flag row (two checkboxes: `Excludes first year`, `One-time only`). User-created credits show "Custom" in `--color-accent`. `+ Add credit` is a dashed-border affordance at the bottom.

### 9.6 Priority tab

Per-category pin list inherits the row-card style. Existing semantics.

## Section 10 — Other Roadmap Tool modals

- **AddScenarioModal:** small modal (~420px wide). Adopts the same form-field language and footer.
- **ApplicationRuleWarningModal:** `warn` semantic for the icon and a soft warn-tinted header band; primary action "Continue" in accent.
- **DeleteCardWarningModal:** `neg` semantic icon header; primary `Delete` button is filled `--color-neg`.

All modals continue to wrap in `<ModalBackdrop>` per existing convention.

## Section 11 — Other Roadmap Tool surfaces

- **ScenarioPicker:** restyled as a dashboard pill — white surface, soft shadow, chevron — placed inline next to the wordmark in the page header.
- **CurrencySettingsDropdown / WalletPortalSharesEditor:** inherit the soft popover treatment. Field language matches the modal form fields.
- **TimelineGlyphs (`CardThumb`, `EditAffordance`):** unchanged.
- **TimelineAxis:** restyled tick labels only.

## Section 12 — Out of scope

- Tablet / mobile responsive layouts (the existing app is desktop-only; this redesign assumes desktop).
- New animation work beyond the existing hover transitions and progress bar.
- New functionality. Pure visual + structural redesign.
- Backend / API / data-model changes.
- Internationalization, localization, accessibility audits beyond AA contrast spot-checks during QA.

## Section 13 — Implementation sketch

This is a sketch; the canonical step-by-step plan is produced by the writing-plans skill next.

1. **Tokens.** Update `frontend/src/styles/tokens.css` for `--color-page`, `--color-surface-2`, divider tokens, ink tokens, shadow values. Light + dark in lockstep. Snapshot the Styleguide page before/after.
2. **Primitives.** Re-skin every primitive in `components/ui/` per Section 2. Verify in the Styleguide page, light + dark.
3. **App shell.** Update `App.tsx`: navbar, `SignInDropdown`, `UsernamePrompt`, `ErrorBoundary` to the new chrome.
4. **Home.** Restyle `pages/Home.tsx` per Section 4 — hero pill, headline weight, step cards.
5. **Profile shell + tabs.** Restyle `pages/Profile/index.tsx` left-rail + content card, then each tab (`WalletTab`, `SpendingTab`, `AppearanceTab`, `SettingsTab`).
6. **Roadmap page shell.** Refactor `RoadmapTool/index.tsx` to the new top-down layout: header bar, hero, calc-inputs strip, horizontal tabs, content area. Drop the vertical binder-tabs gutter.
7. **Roadmap hero stats.** Replace `WalletSummaryStats`'s 4-panel layout with the 3-stat hero + standalone calc-inputs strip.
8. **Roadmap Timeline tab.** Restyle `WalletTimelineChart`'s group section, toolbar, and `CardRow` left gutter.
9. **Roadmap Spend tab.** Rebuild `SpendTabContent` with the shared 4-column grid and inline mapping accordion.
10. **WalletCardModal chrome + form fields.** Update header band, tabs, footer, and re-skin all four tab bodies.
11. **Other modals + dropdowns.** Apply the form-field language to `AddScenarioModal`, `ApplicationRuleWarningModal`, `DeleteCardWarningModal`, `ScenarioPicker`, `CurrencySettingsDropdown`, `WalletPortalSharesEditor`.
12. **Visual QA pass.** Snapshot every page and tab in light and dark mode. Tweak token values for AA contrast as needed (especially the accent on the new gray-100 background).

## Section 14 — Open decisions (defaults noted)

- **Page background exact value** — default `#f3f4f6`. Could push lighter (`#fafafa`) for a more "white page" feel.
- **Whether the calc-inputs strip is sticky** — default not sticky.
- **Whether to dim or hide stale results** — default dim.
- **Per-stat info icons vs one global help button** — default keep per-stat.
- **Whether to keep `--color-accent` at the current `#b04256` crimson or shift to the deeper oxblood `#7a1c2c` proposed in the 2026-04-28 design system spec** — default keep current.
- **Profile tab ordering and icons** — preserved from current `TABS` constant; revisit only if a tab disappears or merges.
