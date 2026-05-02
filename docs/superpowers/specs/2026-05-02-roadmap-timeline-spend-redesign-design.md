# Roadmap Tool — Timeline + Spend Redesign

Date: 2026-05-02

## Goal

Refresh the visual design of the **Timeline** and **Spend** tabs inside the Roadmap Tool. Two specific desires drive this:

1. Visually group cards by currency on the timeline (currency becomes a column on the left).
2. Replace the multi-hue (indigo + green) chart palette with a single accent treatment, while preserving existing semantic colors (pos / neg / warn / info) for stats and status.
3. Make the Spend table denser without losing information.

This is purely a presentation change. No calculator semantics, data model, or routing change. The existing data flow, queries, hooks, and computed values are untouched — only the rendering of timeline rows and spend rows is updated.

## Non-goals

- No changes to the calculator, scenario data model, ScenarioResolver, or backend schemas.
- No new fields on `CardResult`, `WalletResult`, `ResolvedCard`, or `RoadmapResponse`.
- No reorganization of the calculate / scenario lifecycle.
- The `--chart-points` and `--chart-cash` design tokens stay defined in `tokens.css` (other surfaces may still use them); only the Roadmap timeline stops referencing them.
- The `housing_fee_dollars` per-card display, `WalletCardCredit`, three-tier credit chain, and tooltip semantics are unchanged.
- Existing keyboard shortcuts, modals, popovers (rule-alert, category info), `CurrencySettingsDropdown`, and the `Add card` flow are unchanged.

## Color rules

A single rule the redesign follows everywhere:

> **Accent (`var(--color-accent)`) is reserved for chart marks and interactive affordances. Stat numbers keep their existing semantic colors.**

Concretely:

- **Use accent for**: lifetime bars (fill + border), SUB earning stripe pattern (border + stripes), button / icon hover states, the toolbar `+ Add card` hover, the rule-alert button when severity is `inactive`.
- **Do NOT use accent for**: balance numbers, annual income numbers, per-card earn strip text, EAF labels (those keep `text-pos` / `text-neg` / `text-ink`), the cycler card thumbnail, sparkline segments (use `text-ink-muted` / `text-ink-faint`).
- **Rule alert button** continues to follow today's severity rule: `violated` → `bg-neg/10 text-neg`; `in_effect` → `bg-warn/10 text-warn`; `inactive` → `bg-accent-soft text-accent`.

`--chart-points` and `--chart-cash` are no longer referenced from the timeline subtree (the cash-icon fallback in `TimelineGlyphs.CurrencyPhoto` switches to `--color-accent`). The tokens themselves remain in `tokens.css` for other consumers.

## Timeline tab — design

### Grid layout

The timeline body changes from a 2-column grid to a **3-column grid**:

| Column | Width | Content |
|---|---|---|
| 1 — Rail | 40px | Merged across each currency group. Carries the currency icon (centered horizontally near the top) and a thin accent vertical line down the rest of the merged span. |
| 2 — Cards | 380px | Currency header row sits in this column (spans 2 → 3). Card rows show thumb + name + per-card metric strip + lock/toggle. |
| 3 — Timeline | 1fr | Currency header row also extends here so stats can float right. Card rows show the lifetime bar + SUB stripe + EAF label, plus year gridlines + Today / end-of-window vertical lines. |

The `LEFT_GUTTER` constant becomes `40 + 380 = 420` px (same total as today, just split). Existing absolute-positioned year gridlines and Today / end vertical lines keep using `LEFT_GUTTER`.

### Currency header row

The existing dedicated currency header row stays (this was direction C in brainstorming). Layout inside the row:

- **Left of Today line** (sits in the Cards column area, packed left):
  - Currency name (text-ink, font-semibold, 13px).
  - Optional `Cash` pill (small uppercase tag, ink-faint background) for cash currencies.
  - **Settings gear button** — moved from the right edge to here, immediately after the name / pill. Uses `text-ink-faint` → `bg-accent-soft text-accent` when the dropdown is open. Only renders for non-cash currencies (matching today's logic).
- **Right of Today line** (`margin-left: auto` pushes these to the far right of the row):
  - Balance: `text-ink`, `font-semibold`, `tabular-nums`.
  - Annual income: `text-ink-faint`, `tabular-nums`, dot-separated.
  - Secondary balances (e.g. Bilt Cash): `text-ink-faint`, smaller, dot-separated.

The header row no longer carries a left-border in the currency color (today it has `borderLeft: 3px solid group.color`); the currency rail in column 1 now serves that role.

### Currency rail (column 1)

A merged cell (`gridColumn: 1; gridRow: span N` where N = group cards count + 1 for the header row). Background `bg-surface-2` (`#fafbfc`). Right border `border-divider`.

Content:
- Currency icon (`CurrencyPhoto`, 30px round). Aligned to top, padding 8px.
- Below the icon: a thin accent vertical bar (2px wide, `color-mix(in oklab, var(--color-accent) 35%, transparent)`, rounded). Runs from below the icon to the bottom of the rail with a small inset, providing the visual "this group is one currency" anchor.

For cash currencies the icon background switches from `--chart-cash` (today) to `--color-accent` so the rail is consistent across kinds.

### Card row

Mostly unchanged from today:

- Left cell (column 2): card thumb, card name, per-card metric strip, lock or toggle.
- Right cell (column 3): lifetime bar + SUB stripe + EAF label.

Two changes:

1. **Bar / stripe color**: source comes from `groupData.color`, which is now always `var(--color-accent)`. The lifetime bar fill, border, and the SUB stripe pattern (38% / 10% mix of accent) all use the same hue.
2. **Per-card strip**: stays a single line. **No accent highlight on the income number** — keep today's `text-ink-faint` for the whole strip, including the `+45,200/yr` figure. The strip retains the existing dot separators, secondary-currency line, credit lines, and housing-fee line; only the source color of the bars changes.

The EAF label inside the bar keeps existing rules:
- Negative EAF (= card returns more than it costs) → `text-pos` (green).
- Positive EAF (= net cost) → `text-neg` (red).
- Zero / missing → `text-ink` / `text-ink-faint`.

### Toolbar

The toolbar above the chart keeps `+ Add card`, the rule-alert button (existing severity colors), and the legend chips. Legend chip colors switch from `--chart-points` to `--color-accent` so the swatches match the bars.

## Spend tab — design

### Toolbar above the table

A new `bg-surface-2` strip above the table carries:

- **Card cycler**: small pill with `< [thumb] Card Name 3/6 >`. Thumb 32×20 (credit-card aspect). Replaces today's prev/next arrows that live in the table thead.
- **Total spend** and **Selected card earn** stats (right-aligned). Today's "Total" row in the thead goes away — its information lives here.

### Table

Columns:

| Column | Width | Content |
|---|---|---|
| Category | auto | Name + info-popover icon (existing) + new **fan-out sparkline** (60×6 px stacked horizontal bar) showing the user-category → earn-category weight distribution. Sparkline tooltip lists each mapping with its weight. |
| Annual Spend | 120px | Existing dollar amount, mono. |
| Selected Card | 140px | The currently-cycled card's earn for this user category. Mono. Replaces "Annual Point Income" (rename for clarity). |
| Top ROS Cards | auto | New **tile-style chip layout** (Variant A from brainstorming). |

The total row in the existing thead is removed (totals now live in the toolbar).

### Top ROS tiles

Each tile is a 64px-wide vertical chip:
- 64×40 px card photo on top (preserves credit card aspect ratio so card art is recognizable).
- ROS percentage below the photo (`text-[11px] font-semibold tnum-mono`).
- Optional **tag dot** in the top-right corner of the photo (`absolute`, 8px round, white border): warn-yellow for Portal, info-blue for Rotating, pos-green for Override. Tooltip carries the meaning.
- Card name moves to the tile's `title` attribute (hover tooltip), removing the redundant text label that today wraps below each card photo.

Tiles wrap horizontally inside the Top ROS cell. Hover lifts the tile photo border to accent.

The existing `topCardsForCategory` logic, baseline / rotating / portal / override ranking, the housing-fee penalty math, and the rotating cap of "one entry per category" are all unchanged — only the rendered chip shape changes.

### Sparkline (category fan-out)

Pure presentational addition. Reads `effectiveMappings(userCategory)` (already in scope), sorts by `default_weight` descending, and renders one segment per non-zero mapping with width proportional to the weight. Two color stops only:

- First (largest) segment: `bg-ink-muted` (`#4b5563`).
- Subsequent segments: `bg-ink-faint` (`#9ca3af`).

When a user category maps to a single earn category, a single full-width segment is still rendered (matches the agreed mockup, where Dining / Gas / Streaming / Mortgage all show a single flat bar).

## Files touched

Frontend only. All changes scoped to the Roadmap Tool subtree.

```
frontend/src/pages/RoadmapTool/components/timeline/
  WalletTimelineChart.tsx        # 2-col → 3-col grid, axis header, legend colors
  GroupSection.tsx               # add merged rail cell with row-span; header row keeps stats but moves gear
  CardRow.tsx                    # SUB stripe color → accent (sourced via group.color, indirectly)
  TimelineGlyphs.tsx             # cash-icon fallback bg → accent
  lib/timelineGroups.ts          # group.color always accent (drop chart-points / chart-cash branch)

frontend/src/pages/RoadmapTool/components/spend/
  SpendTabContent.tsx            # toolbar above table; 4-col layout; tile-style ROS chips; sparkline; remove thead total row + cycler
```

No new files, no new exports outside these. Existing prop shapes on `GroupSection`, `CardRow`, `WalletTimelineChart`, `SpendTabContent`, and `SpendPanel` stay the same.

## Layout constants

```ts
// WalletTimelineChart.tsx
const RAIL_COL = 40
const CARD_COL = 380
const LEFT_GUTTER = RAIL_COL + CARD_COL  // = 420 (unchanged)
const AXIS_HEIGHT = 32                   // unchanged

// GroupSection.tsx
const CARD_ROW_HEIGHT = 50               // unchanged
const HEADER_ROW_HEIGHT = 44             // currency header row
```

The currency rail's `gridRow` span is `headerRow + cards.length` so it merges across the entire group block.

## Validation

- `npx tsc --noEmit` from `frontend/` must stay green.
- Calculator snapshot test (`backend && ../.venv/bin/python -m pytest tests/test_calculator_snapshot.py`) must stay green; this is a presentational change only, so no fixture update is expected.
- Manual browser walkthrough on the local dev server: 5+ card wallet covering Chase UR (multi-card group), Bilt (group with secondary currency), and a cash currency (single-card group with long name) — verify every state described above.

## Out-of-scope follow-ups

- Animating the rail accent line on hover.
- Replacing `topCardsForCategory` with a server-computed result.
- Theming the sparkline by tag / category color.
- Drag-to-reorder the cycler in the spend toolbar.
