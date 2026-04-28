# Frontend Design System — Editorial Direction

**Date:** 2026-04-28
**Status:** Approved for implementation planning
**Scope:** Establish a coherent visual language for the CardSolver frontend, ship a comprehensive primitive library, and migrate RoadmapTool onto it. Home and Profile migrate later as follow-on specs.

## Goal

Replace the current generic dark-dashboard look (slate + indigo, inline Tailwind utilities throughout) with an opinionated editorial design system: cream-paper light mode, warm dark mode, oxblood accent, Fraunces + Inter + JetBrains Mono typography, and a primitive component layer that enforces the system going forward.

## Decisions Made During Brainstorming

| Axis | Choice | Reasoning |
| --- | --- | --- |
| Aesthetic direction | Editorial / magazine | Picked over Quiet Financial Precision, Premium Card-Collector, and Crisp Consumer Fintech. Reads as contemporary, elegant, minimalist; optimized for thinking, not scanning. |
| Theme modes | Light + dark, both first-class | Maximum flexibility; accepts the ~30% upfront and ongoing cost of testing every component in both modes. Light is the default. |
| Accent palette | Oxblood (`#7a1c2c` light / `#c5495b` dark) | Most personality of the three options. Keeps "gain green" cleanly distinct from accent. |
| Typography | Fraunces + Inter + JetBrains Mono | Display serif for editorial moments (Fraunces variable, with optical-size axis), Inter for UI chrome, JetBrains Mono for tabular numerals in dense data. |
| Primitive scope | Comprehensive (option C) | 25 primitives: tokens-only would erode without enforcement; small set leaves too many decisions ad-hoc. |
| Rollout | Vertical slice — RoadmapTool first | Tokens + primitives + RoadmapTool migration in one push; Home and Profile follow as separate specs. Validates the system on the hardest screen. |
| Timeline component | Retokenize only in this rollout | The 1566-line `WalletTimelineChart.tsx` decomposes into Timeline primitives in a follow-on spec, not here. |

## Section 1 — Foundation Architecture

### 1.1 Token architecture

- Tokens live in `frontend/src/styles/tokens.css` as CSS custom properties on `:root` (light defaults) and `[data-theme="dark"]` (dark overrides).
- Tailwind v4's `@theme` block in `frontend/src/index.css` consumes the same variable names so utilities and raw CSS resolve identically.
- Mode toggle sets `data-theme` on `<html>`, persisted to `localStorage` under `cs.theme`.
- Initial mode resolution: an inline script in `index.html` runs before first paint, reads `localStorage` (falling back to `prefers-color-scheme`), and sets `data-theme` on `<html>` to prevent FOUC.
- A `useTheme()` hook in `frontend/src/hooks/useTheme.ts` exposes the current mode and a setter; the navbar hosts a `ThemeToggle` primitive.

### 1.2 Color tokens (semantic, not nominal)

| Token | Light | Dark | Use |
| --- | --- | --- | --- |
| `--bg-page` | `#faf8f3` | `#15130f` | App background |
| `--bg-surface` | `#ffffff` | `#1d1a14` | Cards, panels |
| `--bg-surface-2` | `#f5f1e8` | `#231f18` | Sub-panels, hover |
| `--ink` | `#1a1a1a` | `#ece6d4` | Primary text |
| `--ink-muted` | `#5a5650` | `#a09786` | Body / secondary |
| `--ink-faint` | `#8a7f66` | `#8e8775` | Eyebrows, metadata |
| `--border` | `#e6e1d6` | `#2a2620` | Standard divider |
| `--border-strong` | `#d8d2c3` | `#3a3328` | Section divider |
| `--accent` | `#7a1c2c` | `#c5495b` | Accent rule, link, focus |
| `--accent-soft` | `rgba(122,28,44,0.08)` | `rgba(197,73,91,0.14)` | Accent tint backgrounds |
| `--pos` | `#2e7d49` | `#8fcf95` | Gain / earn semantic |
| `--neg` | `#a83210` | `#e08c79` | Loss / fee semantic |
| `--warn` | `#a8650b` | `#d6a85b` | Issuer rule, expiring |
| `--info` | `#3a4f6e` | `#9eb3d6` | Informational |

Light-mode accent contrast against `--bg-page` will be verified for WCAG AA on body link text during step 1; if it fails AA on small text we darken accent to `#6a1828` or restrict accent to accent rules and focus rings only and use `--ink` for body links.

### 1.3 Type, spacing, radii, shadows

- **Type families:**
  - **Fraunces** (variable, display + numerals). Loaded via `@fontsource-variable/fraunces` (npm).
  - **Inter** (body, UI chrome). Loaded via `@fontsource-variable/inter`.
  - **JetBrains Mono** (tabular numerals in dense data). Loaded via `@fontsource-variable/jetbrains-mono`.
  - All loaded as variable fonts via `@fontsource` packages (npm, version-pinned, offline-friendly — no Google CDN).
- **Type scale (seven steps):** Display 56 / Headline 34 / Title 24 / Subtitle 18 / Body 14 / Small 12 / Micro 10. Fraunces optical-size axis set per step (144 for Display, 96 for Headline, 36 for Title, 14 for inline serif).
- **Numeric variants:**
  - `.tnum` — Inter with `font-feature-settings: "tnum" 1, "lnum" 1`.
  - `.tnum-mono` — JetBrains Mono.
  - `.tnum-feature` — Fraunces tabular at opsz 144 for hero stats.
- **Spacing:** keep Tailwind's default 4px scale unchanged.
- **Radii:** `--radius-sm 4px` / `--radius-md 8px` / `--radius-lg 12px` / `--radius-xl 14px`. Nothing larger than 14 — editorial favors restrained corners.
- **Shadows:** `--shadow-card` (1px subtle, for hover-elevation only), `--shadow-modal` (deeper, modal/popover only). Editorial leans on borders, not drop shadows.

## Section 2 — Primitive Inventory

All primitives live under `frontend/src/components/ui/<Primitive>/index.tsx` with colocated styles. CardSolver-specific primitives live under `frontend/src/components/cards/`.

Total: **25 primitives** (5 foundation + 6 surface + 6 form + 3 display + 4 cardsolver + ThemeToggle).

### 2.1 Foundation (typography + numeric formatting)

| Primitive | Purpose / variants |
| --- | --- |
| `Heading` | Editorial headings, `level` 1–4 maps to Display / Headline / Title / Subtitle. Renders Fraunces with the right optical-size axis baked in. |
| `Eyebrow` | Uppercase metadata label (Inter 600, 10px, 0.18em tracked). Optional `accent` prop adds the oxblood accent rule above. |
| `Money` | Formatted currency. Props: `value`, `precision` (0/2/auto), `tone` (neutral/pos/neg/auto-from-sign), `feature` (renders Fraunces feature numerals for hero stats), `mono` (default true → JetBrains Mono). Wraps existing `formatMoney` / `formatMoneyExact`. |
| `Points` | Same shape as `Money` but for points/miles, with currency unit suffix support (BP, UR, MR). Wraps `formatPoints`. |
| `Stat` | Feature-number block: eyebrow + caption + big number. Used for "Net EV / yr"-style hero values across RoadmapTool. |

### 2.2 Surfaces

| Primitive | Purpose / variants | Replaces |
| --- | --- | --- |
| `Surface` | Base panel — bg, border, padding. Variants: `panel` (bordered, default), `inset` (bg-surface-2 sub-panel), `bare` (no border). | Most inline `bg-slate-800 border-slate-700 rounded-xl` blocks |
| `Modal` | Backdrop + dialog + header/body/footer slots. `size` xs/sm/md/lg, `dismissible` (Esc, backdrop click). | `ModalBackdrop` plus every modal's bespoke shell |
| `Popover` | Anchored floating layer — info bubble, menu, dropdown. Click-outside + Esc handled. Includes `portal` prop for use inside overflow-hidden containers. | `InfoPopover` |
| `Drawer` | Slide-over panel from left/right, used for the wallet/scenario detail panes if/when adopted. | New |
| `Toast` | Transient notification (success/info/error). App-level provider. | New |
| `Tooltip` | Hover-only short text. Distinct from Popover (no interactivity inside). | New |

### 2.3 Form

| Primitive | Purpose / variants |
| --- | --- |
| `Button` | Variants: `primary` (filled accent), `secondary` (bordered ink), `ghost` (text-only on hover bg), `link` (underline), `icon`. Sizes sm/md/lg. `loading` state. |
| `Input` | Single-line text/number/email. Editorial styling: hairline border, accent focus ring, error state surfaces `--neg`. |
| `Select` | Native-styled-as-custom dropdown. Single-select only — multi-select uses Popover + Checkbox. |
| `Checkbox` | Custom check, accent-tinted. Indeterminate supported. |
| `Toggle` | Boolean switch (more visual weight than Checkbox). Used for include-subs, theme switch, etc. |
| `Field` | Label + control + error/hint wrapper. Standardizes vertical rhythm; every form control gets composed inside this. |

### 2.4 Display

| Primitive | Purpose / variants |
| --- | --- |
| `DataTable` | Editorial bordered table. Sub-components: `Table.Head`, `Table.Row`, `Table.Cell`. `Table.Cell` accepts a `numeric` prop that right-aligns the cell and applies JetBrains Mono tabular numerals. |
| `Badge` | Small pill — `tone` neutral/accent/pos/neg/warn/info. For issuer / network / status (Pending / Earned / Expired). |
| `Tabs` | Underline-style tabs, accent on active. Used in Profile (wallet/spending/settings) and inside RoadmapTool detail pages. |

### 2.5 CardSolver-specific (`components/cards/`)

| Primitive | Purpose |
| --- | --- |
| `CardTile` | The wallet card-result tile — header (issuer / name) + Stat + breakdown rows. Used everywhere a single card's result is shown. |
| `CategoryRow` | Category × multiplier × dollar earn line. The unit-of-display for every per-category breakdown across allocation, results, and overlay editors. |
| `CreditRow` | Credit name × valuation × note. Used in the WalletTab credit modal and in the per-card credit list. |
| `IssuerRuleBanner` | Inline warning surface — "Chase 5/24 violation", "Amex 1/90 cooldown". Wraps `Surface(inset)` with `--warn` accent. |

### 2.6 Timeline (carved out of this rollout)

The wallet timeline (`frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx`, 1566 lines) is **retokenized only** in this rollout — its hardcoded slate/indigo colors become token references and its type families update via the `@theme` cascade, but its structure is unchanged. The `IconHoverLabel` portal helper stays inline.

Full decomposition into `TimelineAxis`, `TimelineRow`, `TimelineGutter`, `TimelineBar`, `TimelineMarker`, `TimelineLegend` is a follow-on spec.

## Section 3 — Rollout, Styleguide, Testing

### 3.1 Build order within the vertical slice

The push lands in this sequence on a single feature branch — each step is a self-contained commit so review is incremental and revert is trivial:

1. **Tokens + theme toggle.** `tokens.css`, `@theme` block in `index.css`, `useTheme` hook, `ThemeToggle` primitive, FOUC-prevention inline script in `index.html`. Tokens land with their final editorial values (per §1.2) from day one. Pages not yet migrated to primitives keep their hardcoded slate/indigo Tailwind classes — those don't reference tokens, so visually nothing changes for un-migrated pages. Pages adopt editorial as their components are migrated to primitives that consume tokens.
2. **Foundation primitives** (Heading, Eyebrow, Money, Points, Stat). Pure presentational, no app dependencies.
3. **Surface primitives** (Surface, Modal, Popover, Drawer, Toast, Tooltip). Modal and Popover ship with compatibility wrappers so existing call sites that import `ModalBackdrop` / `InfoPopover` keep working — wrappers get audited and removed in step 7.
4. **Form primitives** (Button, Input, Select, Checkbox, Toggle, Field).
5. **Display primitives** (DataTable, Badge, Tabs).
6. **CardSolver-specific** (CardTile, CategoryRow, CreditRow, IssuerRuleBanner).
7. **RoadmapTool migration.** Replace inline Tailwind soup with primitives, file by file. The 1566-line `WalletTimelineChart.tsx` gets retokenized only, not decomposed (per §2.6). Audit and delete `ModalBackdrop.tsx` / `InfoPopover.tsx` (or keep as re-export shims — decided during implementation based on import-call-site count).

Home and Profile migrations are out of scope for this spec. They keep working unchanged in the meantime because the token cascade is non-breaking; their visual treatment stays as-is until their own follow-on migration spec.

### 3.2 Styleguide route (`/styleguide`)

A new internal route renders every primitive in every variant + state, side by side in light + dark. Gated behind an env flag (`VITE_SHOW_STYLEGUIDE=1`) so it ships in dev but isn't reachable in production. Built incrementally as each primitive lands so we never have a primitive without a styleguide entry. Replaces "open RoadmapTool, navigate seven clicks deep, hope you can see the Modal in dark mode" with "open `/styleguide#modal`."

### 3.3 Testing approach

- **Manual visual:** `/styleguide` is the source of truth. Every primitive verified in light + dark before its commit lands.
- **Golden path walkthrough:** before final merge, walk RoadmapTool's golden path end-to-end — load default scenario → Calculate → switch scenarios → edit a card → toggle theme — and verify no visual regressions vs. current dark theme.
- **Automated:** existing TypeScript + ESLint pipeline catches API breakage on the wrapper deletions in step 7. No new visual regression infra (Chromatic / Percy) — overkill for a solo project; styleguide + manual is sufficient.
- **Calculator snapshot test:** no backend changes are made, but `pytest tests/test_calculator_snapshot.py` runs after merge as a smoke check per `CLAUDE.md`.

### 3.4 Risks / known unknowns

| Risk | Mitigation |
| --- | --- |
| Fraunces variable font at multiple opsz sizes is heavier than current single-Inter setup. | `@fontsource-variable/fraunces` ships only the variable file; total font payload should land under 200KB gzipped. Measure during step 1; cap if overshoot. |
| Light-mode accent (`#7a1c2c`) on `--bg-page` (`#faf8f3`) needs WCAG AA verification for body link text. | Verify in step 1; if it fails AA on small text, darken accent to `#6a1828` or restrict accent to accent rules / focus rings and use `--ink` for body links. |
| The 25 primitives list assumes RoadmapTool's actual UI matches what was inferred from file structure. | Step 7 may surface a missing primitive (e.g., a slider or chip-input). Add as encountered; this spec is amendable. |
| `ModalBackdrop` / `InfoPopover` are imported in places not yet audited. | Compatibility wrappers in step 3 keep them working until step 7's audit. |
| Both-modes mandate increases ongoing surface area. | Styleguide route forces light + dark verification at primitive-creation time, not at use-site time. |

### 3.5 Out of scope (explicit)

- Home page migration (follow-on spec).
- Profile page migration (follow-on spec).
- `WalletTimelineChart` decomposition into Timeline primitives (follow-on spec).
- Backend changes of any kind.
- Visual regression test infra.
- Storybook (the `/styleguide` route covers the same need with much less infra).
