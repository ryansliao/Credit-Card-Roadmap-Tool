# Foundation Redesign — Tokens + Primitives Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Shift the design tokens from warm-editorial (cream + warm tan + crimson) to a soft-dashboard palette (neutral gray-100 page + gray hairlines + crimson accent retained), and re-skin every UI primitive in `frontend/src/components/ui/` so consumers downstream (app shell, Home, Profile, Roadmap Tool) automatically pick up the new look. Spec: `docs/superpowers/specs/2026-05-01-roadmap-tool-redesign-design.md` Sections 1–2.

**Architecture:** Token-driven. Most primitives already consume CSS variables (`--color-page`, `--color-divider`, etc.) so swapping the values in `tokens.css` cascades automatically. A small number of primitives need code changes (focus rings, hover states, default elevation, weight bumps, an info-icon slot on `Stat`). The Styleguide page (`frontend/src/pages/Styleguide`) is the visual QA target — it imports and renders every primitive in light + dark mode.

**Tech Stack:** React + Vite + Tailwind v4 (`@theme inline` block in `frontend/src/index.css`) + CSS custom properties in `frontend/src/styles/tokens.css`. TypeScript strict. Inter Variable + JetBrains Mono Variable as `@fontsource-variable` packages. Dev server: `cd frontend && npm run dev`. Build/typecheck: `cd frontend && npm run build`. Lint: `cd frontend && npm run lint`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `frontend/src/styles/tokens.css` | The single source of truth for color, type, radii, shadows, light + dark. Modified extensively. |
| `frontend/src/index.css` | Tailwind `@theme inline` mappings — exposes tokens as utility variables. Touched only if a new token name is introduced (none in this plan). |
| `frontend/src/components/ui/Button/index.tsx` | Filled/secondary/ghost/link/icon button. Modified: secondary border tone, focus rings. |
| `frontend/src/components/ui/Input/index.tsx` | Text input. Modified: hover state. |
| `frontend/src/components/ui/Select/index.tsx` | Native select with chevron. Modified: hover state. |
| `frontend/src/components/ui/Field/index.tsx` | Label / help text wrapper. Modified: typography sizing. |
| `frontend/src/components/ui/Surface/index.tsx` | Generic card surface. Modified: `panel` variant drops the border and adds `--shadow-card` by default. |
| `frontend/src/components/ui/Modal/index.tsx` | Modal shell + Header / Body / Footer slots. Modified: header/footer paddings to 18–20px. |
| `frontend/src/components/ui/Heading/index.tsx` | Editorial heading levels 1–4. Modified: weight bump (700/700/600/600). |
| `frontend/src/components/ui/Stat/index.tsx` | Hero stat card (label · value · caption). Modified: optional `info` slot rendered inline next to the label. |
| `frontend/src/components/ui/DataTable/index.tsx` | Compound table primitive. Modified: row hover tint. |
| `frontend/src/components/ui/ThemeToggle/index.tsx` | Light/dark toggle. Modified: icon-button visual language. |
| `frontend/src/pages/Styleguide/index.tsx` | The visual QA target. Modified: a new "Stat with info" demo so the Stat info-icon slot has a render target. |
| `frontend/src/components/ui/Checkbox/index.tsx` | Token-driven; not modified. Verified only. |
| `frontend/src/components/ui/Toggle/index.tsx` | Token-driven; not modified. Verified only. |
| `frontend/src/components/ui/Drawer/index.tsx` | Modified: round the page-facing edge to `--radius-xl`. |
| `frontend/src/components/ui/Popover/index.tsx` | Token-driven; not modified. Verified only. |
| `frontend/src/components/ui/Tooltip/index.tsx` | Modified: pin a near-black background so it works in both themes. |
| `frontend/src/components/ui/Tabs/index.tsx` | Token-driven; not modified. Verified only. |
| `frontend/src/components/ui/Toast/index.tsx` | Modified: add semantic icon on the left and a dismiss button on the right. |
| `frontend/src/components/ui/Eyebrow/index.tsx` | Token-driven; not modified. Verified only. |
| `frontend/src/components/ui/Badge/index.tsx` | Token-driven; not modified. Verified only. |
| `frontend/src/components/ui/Money/index.tsx` | Token-driven; not modified. Verified only. |
| `frontend/src/components/ui/Points/index.tsx` | Token-driven; not modified. Verified only. |

**Verification convention used in every task:** because these are visual changes, "the test" is "run the dev server and look at the Styleguide page in both light and dark mode." Each task ends with a `npm run build` step (typecheck + Vite build, no runtime tests) and a manual visual-QA step. Commits after each task.

---

## Task 1: Update color and shadow tokens

**Files:**
- Modify: `frontend/src/styles/tokens.css`

- [ ] **Step 1: Replace the `:root` block in `tokens.css` with the soft-dashboard values**

```css
:root {
  /* Color — semantic, role-based naming */
  --color-page: #f3f4f6;
  --color-surface: #ffffff;
  --color-surface-2: #fafbfc;
  --color-ink: #111827;
  --color-ink-muted: #4b5563;
  --color-ink-faint: #9ca3af;
  --color-divider: #e5e7eb;
  --color-divider-strong: #d1d5db;
  --color-accent: #b04256;
  --color-accent-soft: rgba(176, 66, 86, 0.10);
  --color-on-accent: #ffffff;
  --color-pos: #15803d;
  --color-neg: #a83210;
  --color-warn: #9e5d09;
  --color-info: #3a4f6e;

  /* Chart palette — distinct from semantic tokens */
  --chart-cash: #16a34a;
  --chart-points: #4f46e5;

  /* Radii */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 14px;

  /* Shadows — soft-dashboard leans on shadows for depth */
  --shadow-card: 0 1px 2px rgba(17, 24, 39, 0.04), 0 1px 3px rgba(17, 24, 39, 0.04);
  --shadow-modal: 0 24px 48px -12px rgba(17, 24, 39, 0.18), 0 8px 16px -8px rgba(17, 24, 39, 0.10);

  /* Type families (Tailwind picks up --font-* automatically) */
  --font-display: "Inter Variable", "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-sans: "Inter Variable", "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono Variable", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
}
```

- [ ] **Step 2: Replace the `[data-theme="dark"]` block in `tokens.css` with cool-gray dark-mode values**

```css
[data-theme="dark"] {
  --color-page: #0b0d11;
  --color-surface: #16181d;
  --color-surface-2: #1d2026;
  --color-ink: #f5f5f5;
  --color-ink-muted: #a3a3a3;
  --color-ink-faint: #6b7280;
  --color-divider: #2a2e36;
  --color-divider-strong: #3b424d;
  --color-accent: #b04256;
  --color-accent-soft: rgba(176, 66, 86, 0.22);
  --color-on-accent: #ffffff;
  --color-pos: #22c55e;
  --color-neg: #e08c79;
  --color-warn: #d6a85b;
  --color-info: #9eb3d6;

  --chart-points: #818cf8;

  --shadow-card: 0 1px 2px rgba(0, 0, 0, 0.4), 0 1px 3px rgba(0, 0, 0, 0.25);
  --shadow-modal: 0 24px 48px -12px rgba(0, 0, 0, 0.6), 0 8px 16px -8px rgba(0, 0, 0, 0.4);
}
```

- [ ] **Step 3: Run typecheck + build to confirm CSS still compiles**

Run: `cd frontend && npm run build`
Expected: build succeeds with no errors.

- [ ] **Step 4: Visual QA — start the dev server and open the Styleguide page**

Run: `cd frontend && npm run dev`
Open: `http://localhost:5173/styleguide` (or whichever port Vite reports).
Expected: page renders on a neutral light-gray background instead of cream. Dividers are gray hairlines. Accent (oxblood crimson) still appears on accent rules and primary buttons.
Toggle dark mode using the navbar `ThemeToggle`. Expected: page switches to a near-black background with cool-gray surfaces; accent crimson still visible.

- [ ] **Step 5: Commit**

```bash
cd frontend && cd ..
git add frontend/src/styles/tokens.css
git commit -m "tokens: shift to soft-dashboard palette (neutral gray + crimson accent)"
```

---

## Task 2: Re-skin `Surface` primitive — drop default border, add shadow

The `panel` variant currently has `border border-divider` and no shadow. Soft dashboard relies on shadow for depth, not borders. Switch it.

**Files:**
- Modify: `frontend/src/components/ui/Surface/index.tsx`

- [ ] **Step 1: Update `VARIANT_CLASS` to drop the border on `panel` and rely on shadow**

Replace the `VARIANT_CLASS` and `Surface` body in `frontend/src/components/ui/Surface/index.tsx` with:

```tsx
const VARIANT_CLASS: Record<Variant, string> = {
  panel: 'bg-surface shadow-card',
  inset: 'bg-surface-2',
  bare: 'bg-transparent',
}
```

- [ ] **Step 2: Drop the `elevated` prop usage from the `Surface` JSX since `panel` is now elevated by default**

Replace the return statement in `Surface` with:

```tsx
return (
  <div
    {...rest}
    className={`rounded-lg ${VARIANT_CLASS[variant]} ${PADDING_CLASS[padding]} ${elevated ? 'shadow-card' : ''} ${className}`}
  >
    {children}
  </div>
)
```

(The `elevated` prop stays for backwards compatibility — passing `elevated` on a non-panel variant still adds shadow. Panel ignores it because panel already has the shadow class; duplicate `shadow-card` is harmless.)

- [ ] **Step 3: Build to confirm**

Run: `cd frontend && npm run build`
Expected: build succeeds.

- [ ] **Step 4: Visual QA**

Open: `http://localhost:5173/styleguide`. Find the Surface section.
Expected: panel surface now reads as a white card with a subtle drop shadow instead of a bordered box. `inset` variant remains a soft-tinted area without border. Dark mode: same change applied.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Surface/index.tsx
git commit -m "ui/Surface: drop panel border, lean on shadow-card"
```

---

## Task 3: Re-skin `Button` primitive — secondary border, focus rings

Two changes: secondary variant uses `--color-divider-strong` (gray-300) instead of `--color-ink` (near-black border looks heavy in soft dashboard), and add a focus-visible ring with `--color-accent-soft`.

**Files:**
- Modify: `frontend/src/components/ui/Button/index.tsx`

- [ ] **Step 1: Update `VARIANT` to use the divider tone for secondary border**

In `frontend/src/components/ui/Button/index.tsx`, replace the `VARIANT` constant:

```tsx
const VARIANT: Record<Exclude<Variant, 'icon'>, string> = {
  primary:   'bg-accent text-on-accent shadow-card hover:opacity-90',
  warn:      'bg-warn text-on-accent hover:opacity-90',
  secondary: 'bg-surface text-ink border border-divider-strong hover:bg-surface-2',
  ghost:     'bg-transparent text-ink hover:bg-surface-2',
  link:      'bg-transparent text-accent underline underline-offset-2 hover:opacity-80 px-0 py-0',
}
```

- [ ] **Step 2: Add a focus-visible ring to the base classes**

In the same file, replace the `<button>` className expression in the `Button` component:

```tsx
className={`inline-flex items-center gap-2 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent-soft ${base} ${SIZE[size]} ${variantClass} ${className}`}
```

- [ ] **Step 3: Build to confirm**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA**

Open Styleguide. Find the Button section.
Expected:
- Primary button: filled crimson, white text, subtle shadow.
- Secondary button: white surface with a gray-300 1px border, dark text. (No longer a near-black border.)
- Tab through the buttons (Tab key) — each focused button should show a soft crimson ring around it.
- Toggle to dark mode and re-verify.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Button/index.tsx
git commit -m "ui/Button: lighten secondary border, add focus-visible ring"
```

---

## Task 4: Re-skin `Input` and `Select` — add hover state

Spec section 2: "Hover bumps to gray-300". Both Input and Select need this.

**Files:**
- Modify: `frontend/src/components/ui/Input/index.tsx`
- Modify: `frontend/src/components/ui/Select/index.tsx`

- [ ] **Step 1: Add hover border to Input**

Replace the `<input>` className in `frontend/src/components/ui/Input/index.tsx`:

```tsx
className={`w-full bg-surface text-ink border ${invalid ? 'border-neg' : 'border-divider'} rounded-md px-3 py-2 text-sm placeholder:text-ink-faint hover:border-divider-strong focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft transition-colors ${className}`}
```

- [ ] **Step 2: Add hover border to Select**

Replace the `<select>` className in `frontend/src/components/ui/Select/index.tsx`:

```tsx
className={`w-full appearance-none bg-surface text-ink border ${invalid ? 'border-neg' : 'border-divider'} rounded-md pl-3 pr-8 py-2 text-sm hover:border-divider-strong focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft transition-colors ${className}`}
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA**

Open Styleguide. Find the form / Input / Select sections.
Expected: hovering over an input or select bumps the border one shade darker (gray-200 → gray-300). Focus shows a crimson border + soft ring. Dark mode: same.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Input/index.tsx frontend/src/components/ui/Select/index.tsx
git commit -m "ui/Input,Select: add hover border state"
```

---

## Task 5: Re-skin `Field` primitive — adjust label / help typography

Spec section 9.2: "Field group: 12px label · input · 11px help text." Currently Field uses `text-sm` (14px) for the label and `text-xs` (12px) for the help text. Switch to 12px / 11px.

**Files:**
- Modify: `frontend/src/components/ui/Field/index.tsx`

- [ ] **Step 1: Update label and help-text classes**

Replace the `return` in `frontend/src/components/ui/Field/index.tsx`:

```tsx
return (
  <div className="space-y-1.5">
    <label htmlFor={id} className="block text-xs font-medium text-ink-muted">
      {label}
      {required && <span className="text-neg ml-1">*</span>}
    </label>
    {child}
    {hint && !error && <p id={hintId} className="text-[11px] text-ink-faint">{hint}</p>}
    {error && <p id={errorId} className="text-[11px] text-neg">{error}</p>}
  </div>
)
```

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Open Styleguide. Find the Field section.
Expected: labels are smaller (12px) and use ink-muted color; help text is 11px ink-faint. Error text is 11px neg.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Field/index.tsx
git commit -m "ui/Field: tighten label/help typography to 12/11px"
```

---

## Task 6: Re-skin `Modal` primitive — paddings + shadow

Spec section 9.1: "Header band 18–20px padding". Current header uses `px-6 pt-5 pb-3` (24/20/12). Tighten to 20px on all sides for a cleaner soft-dashboard feel. Also pin the radius to `--radius-xl` (14px) explicitly via the existing `rounded-xl`.

**Files:**
- Modify: `frontend/src/components/ui/Modal/index.tsx`

- [ ] **Step 1: Tighten header / body / footer paddings**

Replace `ModalHeader`, `ModalBody`, and `ModalFooter` in `frontend/src/components/ui/Modal/index.tsx`:

```tsx
export function ModalHeader({ children, className = '' }: SectionProps) {
  return (
    <div className={`px-5 pt-5 pb-4 border-b border-divider ${className}`}>
      {children}
    </div>
  )
}

export function ModalBody({ children, className = '' }: SectionProps) {
  return <div className={`px-5 py-5 ${className}`}>{children}</div>
}

export function ModalFooter({ children, className = '' }: SectionProps) {
  return (
    <div className={`px-5 py-4 border-t border-divider flex items-center justify-end gap-2 ${className}`}>
      {children}
    </div>
  )
}
```

- [ ] **Step 2: Drop the modal shell border (rely on shadow for depth)**

Replace the inner `<div role="dialog">` className in `Modal`:

```tsx
className={`bg-surface rounded-xl shadow-modal w-full ${SIZE_CLASS[size]} ${className}`}
```

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA**

Open Styleguide. Click "Open modal".
Expected: modal appears with no visible border, soft drop shadow, 20px padding around header/body/footer. Header still has a hairline divider beneath it. Dark mode: same modal shell with darker page underlay.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Modal/index.tsx
git commit -m "ui/Modal: tighten paddings, drop shell border, lean on shadow-modal"
```

---

## Task 7: Re-skin `Heading` primitive — bump weights by level

Spec section 1.2: hero stat values are Inter weight 700; modal headings use Inter 600. Map `Heading` levels accordingly: 1 and 2 → 700, 3 and 4 → 600. Also tighten letter-spacing on smaller levels per spec.

**Files:**
- Modify: `frontend/src/components/ui/Heading/index.tsx`

- [ ] **Step 1: Update weight resolution per level**

Replace the `Heading` body in `frontend/src/components/ui/Heading/index.tsx`:

```tsx
const STYLE_BY_LEVEL: Record<Level, { fontSize: string; lineHeight: string; letterSpacing: string; weight: number }> = {
  1: { fontSize: '48px', lineHeight: '1.05', letterSpacing: '-0.02em',  weight: 700 },
  2: { fontSize: '28px', lineHeight: '1.15', letterSpacing: '-0.02em',  weight: 700 },
  3: { fontSize: '22px', lineHeight: '1.2',  letterSpacing: '-0.015em', weight: 600 },
  4: { fontSize: '17px', lineHeight: '1.3',  letterSpacing: '-0.01em',  weight: 600 },
}

export function Heading({ level = 2, children, className = '', as }: Props) {
  const Tag = (as ?? `h${level}`) as keyof React.JSX.IntrinsicElements
  const s = STYLE_BY_LEVEL[level]
  return (
    <Tag
      className={`text-ink ${className}`}
      style={{
        fontSize: s.fontSize,
        lineHeight: s.lineHeight,
        letterSpacing: s.letterSpacing,
        fontWeight: s.weight,
      }}
    >
      {children}
    </Tag>
  )
}
```

(Removed the `font-display` and `font-medium` Tailwind classes — both are now covered by inline weight + the global `font-sans`.)

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Open Styleguide. Find the Heading levels demo.
Expected: levels 1–2 are bold (700); levels 3–4 are semibold (600). Sizes are slightly smaller across the board than before (was 56/34/24/18 → now 48/28/22/17). Letter-spacing tightens at larger sizes.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Heading/index.tsx
git commit -m "ui/Heading: bump weights (1-2: 700, 3-4: 600), refine size scale"
```

---

## Task 8: Re-skin `Stat` primitive — add optional `info` slot

Spec section 6 (Roadmap page layout): "Each label has an inline `i` info button that opens the existing per-stat Popover content unchanged." Add an optional `info` prop to `Stat` so consumers can render a popover trigger inline beside the label.

**Files:**
- Modify: `frontend/src/components/ui/Stat/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx` (add a demo for the new slot)

- [ ] **Step 1: Add `info` prop to `Stat`**

Replace `frontend/src/components/ui/Stat/index.tsx` entirely with:

```tsx
import type { ReactNode } from 'react'
import { Eyebrow } from '../Eyebrow'

interface Props {
  /** Eyebrow / label text above the value. */
  label: ReactNode
  /** The hero number content — typically a `<Money feature>` or `<Points feature>`. */
  value: ReactNode
  /** Optional small caption below the value. */
  caption?: ReactNode
  /** Optional content rendered inline next to the label (typically an info Popover trigger). */
  info?: ReactNode
  /** Add the oxblood accent rule above the eyebrow. */
  accent?: boolean
  /** Right-align the entire stack. Defaults to left. */
  align?: 'left' | 'right'
  className?: string
}

export function Stat({ label, value, caption, info, accent = false, align = 'left', className = '' }: Props) {
  const alignClass = align === 'right' ? 'text-right items-end' : 'text-left items-start'
  return (
    <div className={`flex flex-col ${alignClass} ${className}`}>
      <div className={`flex items-center gap-1.5 ${align === 'right' ? 'flex-row-reverse' : ''}`}>
        <Eyebrow accent={accent}>{label}</Eyebrow>
        {info}
      </div>
      <div className="mt-1">{value}</div>
      {caption && (
        <div className="text-xs text-ink-muted mt-1">{caption}</div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add a Styleguide demo for the new info slot**

Find the existing Stat demo in `frontend/src/pages/Styleguide/index.tsx`. Identify the section that renders `<Stat ... />` examples. Add one new example beneath the existing ones (search for `<Stat ` to locate them). The pattern is:

```tsx
<Stat
  label="Effective annual fee"
  info={
    <Popover
      side="bottom"
      portal
      trigger={({ onClick, ref }) => (
        <button
          ref={ref as React.RefObject<HTMLButtonElement>}
          type="button"
          onClick={onClick}
          aria-label="What is effective annual fee?"
          className="text-ink-faint hover:text-accent transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10" />
            <line x1="12" y1="16" x2="12" y2="12" />
            <line x1="12" y1="8" x2="12.01" y2="8" />
          </svg>
        </button>
      )}
    >
      <p className="text-xs text-ink-muted">The wallet's true yearly cost (or value) once rewards, credits, and SUBs are netted out against fees.</p>
    </Popover>
  }
  value={<Money value={-1247} feature tone="auto" />}
  caption="net wallet value · 1.5y projection"
/>
```

If `Popover` isn't already imported in the Styleguide file (search for `import { Popover }`), add the import. If `Money` isn't imported with the right props, also confirm `feature` and `tone` are supported (they are — see `frontend/src/components/ui/Money/index.tsx`).

- [ ] **Step 3: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 4: Visual QA**

Open Styleguide. Find the Stat section.
Expected: the new demo Stat shows an `i` icon next to the label. Clicking the icon opens a small popover with the help copy. Existing Stat demos still render correctly.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Stat/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "ui/Stat: add optional info slot for inline popover trigger"
```

---

## Task 9: Re-skin `DataTable` primitive — row hover

Spec section 2: "Hairline rows, sticky header on `--color-surface`, hover row tint `--color-surface-2`". `Row` currently has no hover state. Add it.

**Files:**
- Modify: `frontend/src/components/ui/DataTable/index.tsx`

- [ ] **Step 1: Add hover-tint to `Row`**

In `frontend/src/components/ui/DataTable/index.tsx`, replace the `Row` function:

```tsx
function Row({ children, className = '', ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr {...rest} className={`border-b border-divider last:border-b-0 hover:bg-surface-2 transition-colors ${className}`}>
      {children}
    </tr>
  )
}
```

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Open Styleguide. Find the DataTable demo. Hover over body rows.
Expected: the row tints to `--color-surface-2` (very-light-gray light, slightly-lighter-than-page dark).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/DataTable/index.tsx
git commit -m "ui/DataTable: tint row on hover"
```

---

## Task 10: Re-skin `ThemeToggle` primitive — icon-button language

Currently `ThemeToggle` is a text button reading "Light" / "Dark". Spec section 2 says it's an icon-button. Switch to a sun/moon icon, square 32×32, hairline border, ghost hover.

**Files:**
- Modify: `frontend/src/components/ui/ThemeToggle/index.tsx`

- [ ] **Step 1: Replace `ThemeToggle` with the icon-button form**

Replace the contents of `frontend/src/components/ui/ThemeToggle/index.tsx` with:

```tsx
import { useTheme } from '../../../hooks/useTheme'

interface Props {
  className?: string
}

export function ThemeToggle({ className = '' }: Props) {
  const { theme, toggle } = useTheme()
  const label = theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'
  return (
    <button
      type="button"
      onClick={toggle}
      aria-label={label}
      title={label}
      className={`w-8 h-8 inline-flex items-center justify-center rounded-md text-ink-faint hover:text-ink hover:bg-surface-2 transition-colors ${className}`}
    >
      {theme === 'dark' ? (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <circle cx="12" cy="12" r="4" />
          <path d="M12 2v2M12 20v2M4.93 4.93l1.41 1.41M17.66 17.66l1.41 1.41M2 12h2M20 12h2M4.93 19.07l1.41-1.41M17.66 6.34l1.41-1.41" />
        </svg>
      ) : (
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
        </svg>
      )}
    </button>
  )
}
```

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Look at the navbar (any page).
Expected: previously-text "Light"/"Dark" button is now a 32×32 icon-only button showing a sun (when in dark mode) or moon (when in light mode). Hover bumps to the muted-surface tint.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/ThemeToggle/index.tsx
git commit -m "ui/ThemeToggle: convert to 32px icon-button with sun/moon glyph"
```

---

## Task 11: Re-skin `Drawer` primitive — round page-facing edge

Spec section 2: "Drawer — Same surface treatment; 14px radius left edge". Currently the drawer is a plain rectangle anchored to the page edge. Round the edge that faces the main content.

**Files:**
- Modify: `frontend/src/components/ui/Drawer/index.tsx`

- [ ] **Step 1: Round the page-facing edge based on `side`**

In `frontend/src/components/ui/Drawer/index.tsx`, replace the `sideClass` line and the inner `<div role="dialog">` className:

```tsx
const sideClass = side === 'right' ? 'right-0 rounded-l-xl' : 'left-0 rounded-r-xl'
```

```tsx
className={`absolute top-0 bottom-0 ${sideClass} ${WIDTH_CLASS[width]} bg-surface shadow-modal overflow-y-auto ${className}`}
```

(Drops the `border-l` / `border-r` — shadow is enough.)

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Open Styleguide, click "Open drawer". Expected: drawer slides in from the right with the left edge rounded (`--radius-xl` = 14px). No visible border on the page-facing edge — soft drop shadow handles separation.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Drawer/index.tsx
git commit -m "ui/Drawer: round page-facing edge, drop side border"
```

---

## Task 12: Re-skin `Tooltip` primitive — pin dark background

Currently `Tooltip` uses `bg-ink text-page`, which flips colors in dark mode (light tooltip on dark page becomes nearly invisible). Spec section 2 wants a "Dark-on-light variant: very dark gray-900 background, white text" — i.e., the same dark background in both themes.

**Files:**
- Modify: `frontend/src/components/ui/Tooltip/index.tsx`

- [ ] **Step 1: Pin tooltip background and text**

In `frontend/src/components/ui/Tooltip/index.tsx`, replace the tooltip `<span>` className:

```tsx
className="px-2 py-1 rounded bg-[#0b0d11] text-white text-[11px] font-medium whitespace-nowrap pointer-events-none shadow-card"
```

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Open Styleguide. Hover over the tooltip demo trigger.
Expected: tooltip shows as a near-black pill with white text. Toggle to dark mode and hover again — tooltip looks identical (dark background does not flip to light).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Tooltip/index.tsx
git commit -m "ui/Tooltip: pin dark background for cross-theme contrast"
```

---

## Task 13: Re-skin `Toast` primitive — semantic icon + dismiss button

Spec section 2: "Toast — White surface, 12px radius, soft shadow, semantic icon left, dismiss right." Current Toast is a bordered card with text only. Add an inline semantic icon on the left and a close-button on the right.

**Files:**
- Modify: `frontend/src/components/ui/Toast/index.tsx`

- [ ] **Step 1: Replace `ToastItem` with the new layout, and surface a `dismiss` callback**

In `frontend/src/components/ui/Toast/index.tsx`, find the `ToastItem` component and the surrounding state. Replace the relevant section so the toast renders an icon, the message, and a close button. Update the body of the `ToastProvider` only where the JSX renders the toasts (no new state needed — `dismiss` becomes a function that filters by id and clears the auto-dismiss timer entry). Replace from the start of `ToastProvider` to the end of the file with:

```tsx
import { useCallback, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'
import { ToastContext, type Tone } from './useToast'

interface Toast {
  id: number
  tone: Tone
  message: string
}

interface ProviderProps {
  children: ReactNode
}

export function ToastProvider({ children }: ProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const idRef = useRef(0)

  const dismiss = useCallback((id: number) => {
    setToasts((cur) => cur.filter((t) => t.id !== id))
  }, [])

  const show = useCallback((message: string, tone: Tone = 'info') => {
    const id = ++idRef.current
    setToasts((cur) => [...cur, { id, tone, message }])
    setTimeout(() => dismiss(id), 4000)
  }, [dismiss])

  const value = useMemo(() => ({ show }), [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {typeof document !== 'undefined' &&
        createPortal(
          <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
            {toasts.map((t) => (
              <ToastItem key={t.id} toast={t} onDismiss={() => dismiss(t.id)} />
            ))}
          </div>,
          document.body,
        )}
    </ToastContext.Provider>
  )
}

const ICON_BY_TONE: Record<Tone, ReactNode> = {
  info: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="16" x2="12" y2="12" />
      <line x1="12" y1="8" x2="12.01" y2="8" />
    </svg>
  ),
  success: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  ),
  error: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
      <circle cx="12" cy="12" r="10" />
      <line x1="12" y1="8" x2="12" y2="12" />
      <line x1="12" y1="16" x2="12.01" y2="16" />
    </svg>
  ),
}

function ToastItem({ toast, onDismiss }: { toast: Toast; onDismiss: () => void }) {
  const toneClass: Record<Tone, string> = {
    info: 'text-info',
    success: 'text-pos',
    error: 'text-neg',
  }
  return (
    <div
      role="status"
      className="bg-surface rounded-xl px-3 py-2.5 text-sm text-ink shadow-card animate-toast-in flex items-start gap-2.5"
    >
      <span className={`shrink-0 mt-0.5 ${toneClass[toast.tone]}`}>{ICON_BY_TONE[toast.tone]}</span>
      <span className="flex-1 min-w-0 pt-0.5">{toast.message}</span>
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="shrink-0 -mr-1 -mt-0.5 w-6 h-6 inline-flex items-center justify-center rounded text-ink-faint hover:text-ink hover:bg-surface-2 transition-colors"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  )
}
```

This replaces the entire body below the existing imports and `Toast` interface.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Open Styleguide. Trigger the toast demo (click the demo button that calls `show()`).
Expected: toast appears top-right as a white pill with a 12px radius (`--radius-xl`), soft shadow, semantic icon (info / check / alert) on the left in the appropriate tone color, message text in the middle, an `×` button on the right. Clicking `×` dismisses the toast immediately. Toast still auto-dismisses after 4s.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Toast/index.tsx
git commit -m "ui/Toast: add semantic icon, dismiss button, and surface treatment"
```

---

## Task 14: Verify the remaining token-driven primitives in the Styleguide

The remaining primitives (`Checkbox`, `Toggle`, `Popover`, `Tabs`, `Eyebrow`, `Badge`, `Money`, `Points`) pick up the new look from token changes alone. Structured verification — no code changes unless something looks broken.

**Files:**
- (Verify only — no edits unless an issue surfaces.)

- [ ] **Step 1: Start the dev server if not already running**

Run: `cd frontend && npm run dev`
Open: `http://localhost:5173/styleguide`.

- [ ] **Step 2: Verify each token-driven primitive in light mode**

Walk through the Styleguide top-to-bottom:

- **Checkbox** — 16px square, gray-200 border at rest, crimson fill when checked. Indeterminate shows a crimson bar.
- **Toggle** — 36×20 pill, gray-200 off / crimson on, smooth knob slide.
- **Popover** — white surface, soft shadow, 8px radius (`rounded-lg`), 12px padding.
- **Tabs** — underline-style active tab in crimson, inactive labels in `--color-ink-muted`. Hairline bottom rule.
- **Eyebrow** — small uppercase label, optional crimson accent rule.
- **Badge** — neutral default reads as soft gray pill; semantic variants (`pos`/`neg`/`warn`/`info`/`accent`) use tinted backgrounds.
- **Money / Points** — render in JetBrains Mono tabular numerals.

If any primitive shows residual warm-tan or other look-and-feel breakage, identify the offending class string and fix it inline (commit separately with a message describing the fix).

- [ ] **Step 3: Toggle to dark mode and repeat the walk-through**

Click the navbar `ThemeToggle`. Re-verify the same list. Specifically:

- Contrast on `Eyebrow` and `Badge` text remains readable against the dark page.
- Accent crimson stays visible.
- No primitive flips into an inverted state in dark mode.

- [ ] **Step 4: Note any deferred follow-ups**

If a primitive looks acceptable but not perfect (e.g., a Badge tone reads too saturated against the new background), don't fix it now — append a note to `docs/superpowers/specs/2026-05-01-roadmap-tool-redesign-design.md` Section 14 ("Open decisions") for a later pass. Keep this plan's scope tight.

- [ ] **Step 5: If you committed any inline fixes, the task is done. Otherwise, no commit.**

---

## Task 15: Final visual QA pass — Styleguide, light + dark, every primitive

End-to-end verification before merging. Treats the Styleguide as the contract for the foundation layer.

**Files:**
- (Verify only.)

- [ ] **Step 1: Run a full production build**

Run: `cd frontend && npm run build`
Expected: build succeeds, no TypeScript errors.

- [ ] **Step 2: Run lint**

Run: `cd frontend && npm run lint`
Expected: passes. Fix any new warnings you introduced (most likely unused imports from the Styleguide demo edit).

- [ ] **Step 3: Open the Styleguide in the dev server**

Run: `cd frontend && npm run dev`
Open: `http://localhost:5173/styleguide`.

- [ ] **Step 4: Light-mode walk-through**

Confirm each section visually matches the spec:

- Page background: neutral gray-100, not cream.
- Surface (`panel`): white card with soft drop shadow, no visible border.
- Heading levels: 48 / 28 / 22 / 17 px; bold for 1–2, semibold for 3–4.
- Stat: hero-stat layout with an info `i` icon next to the label (new demo).
- Button: primary filled crimson with shadow + opacity hover; secondary white with gray-300 border; focus rings visible on Tab.
- Input / Select: gray-200 rest border, gray-300 hover, crimson focus + soft ring.
- Field: 12px label / 11px help text.
- Modal: 14px radius, no border, soft shadow, 20px paddings.
- Drawer / Popover / Tooltip / Toast: render correctly, soft shadows.
- Tabs: crimson underline on active.
- DataTable: rows tint on hover.
- Theme toggle (navbar): icon-only square button.

- [ ] **Step 5: Dark-mode walk-through**

Click the theme toggle and repeat the same checklist in dark mode. Specific dark-mode checks:

- Page background: near-black (#0b0d11), not warm brown.
- Surfaces: cool dark-gray, not warm-brown.
- Crimson accent still visible against the dark page.
- Contrast on muted/faint text remains readable.

- [ ] **Step 6: Check the navbar and Home page in passing**

Navigate to `/` (Home) and observe the navbar.
Expected: navbar background is white (light) or cool-dark (dark); the wordmark and links read correctly. The Home page itself will look transitional — that's fine; this plan doesn't restyle it. Plan 2 covers it.

- [ ] **Step 7: Commit a final QA note**

If you made any inline fixes during this task that haven't been committed, commit them now. Otherwise:

```bash
git commit --allow-empty -m "foundation: visual QA pass complete (light + dark, all primitives)"
```

This empty commit serves as a checkpoint marker so reviewers can find the QA boundary in the log.

---

## Plan complete

After Task 15, the foundation layer is shipped. The app will look "transitional" — primitives are crisp and modern, but pages that consume them haven't been restructured yet. That's expected. Plan 2 (App shell + Home), Plan 3 (Profile), and Plan 4 (Roadmap Tool) handle the consumers.
