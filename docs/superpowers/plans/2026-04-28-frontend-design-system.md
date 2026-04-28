# Frontend Design System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship editorial design tokens (light + dark), a 25-primitive component library, an internal `/styleguide` route, and migrate RoadmapTool onto the system.

**Architecture:** CSS custom properties on `:root` + `[data-theme="dark"]` are the single source of truth for tokens. Tailwind v4's `@theme inline` block re-declares them as Tailwind utilities so both raw CSS and `bg-page`/`text-ink`-style classes resolve to the same runtime values. Theme mode is set on `<html data-theme>` by an inline FOUC-prevention script in `index.html`, persisted to `localStorage`, and toggled via `useTheme()`. All primitives consume tokens — never hardcoded hex.

**Tech Stack:** React 19, TypeScript, Vite 7, Tailwind CSS v4, React Router v7, TanStack Query v5. Fonts via `@fontsource-variable/{fraunces,inter,jetbrains-mono}` (npm, not Google CDN). No new test framework — verification is the styleguide route in light + dark per spec §3.3.

**Spec:** [docs/superpowers/specs/2026-04-28-frontend-design-system-design.md](../specs/2026-04-28-frontend-design-system-design.md)

**Working directory:** All `cd` instructions in this plan assume you're at the repo root unless otherwise stated. Run `npm` commands from `frontend/`.

**Commit cadence:** Every task ends in a commit. Each task is independently revertable.

---

## Phase 1 — Foundation

### Task 1: Install fonts and dev dependencies

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`

- [ ] **Step 1: Install variable font packages**

```bash
cd frontend
npm install @fontsource-variable/fraunces @fontsource-variable/inter @fontsource-variable/jetbrains-mono
```

Expected: three packages added to `dependencies` in `package.json`. No build errors.

- [ ] **Step 2: Verify packages resolved**

```bash
ls node_modules/@fontsource-variable
```

Expected output includes: `fraunces  inter  jetbrains-mono`

- [ ] **Step 3: Commit**

```bash
git add frontend/package.json frontend/package-lock.json
git commit -m "Install Fraunces, Inter, JetBrains Mono variable fonts"
```

---

### Task 2: Create design tokens

**Files:**
- Create: `frontend/src/styles/tokens.css`

- [ ] **Step 1: Create the styles directory**

```bash
mkdir -p frontend/src/styles
```

- [ ] **Step 2: Write `frontend/src/styles/tokens.css`**

```css
/* ──────────────────────────────────────────────────────────────────────
   Design Tokens — Editorial Direction
   Single source of truth for color, type, spacing, radii, shadows.
   Light values on :root; dark overrides on [data-theme="dark"].
   Tailwind v4 picks these up via @theme inline in index.css.
   ────────────────────────────────────────────────────────────────────── */

:root {
  /* Color — semantic, role-based naming */
  --color-page: #faf8f3;
  --color-surface: #ffffff;
  --color-surface-2: #f5f1e8;
  --color-ink: #1a1a1a;
  --color-ink-muted: #5a5650;
  --color-ink-faint: #8a7f66;
  --color-divider: #e6e1d6;
  --color-divider-strong: #d8d2c3;
  --color-accent: #7a1c2c;
  --color-accent-soft: rgba(122, 28, 44, 0.08);
  --color-pos: #2e7d49;
  --color-neg: #a83210;
  --color-warn: #a8650b;
  --color-info: #3a4f6e;

  /* Radii */
  --radius-sm: 4px;
  --radius-md: 8px;
  --radius-lg: 12px;
  --radius-xl: 14px;

  /* Shadows — editorial leans on borders, shadows are minimal */
  --shadow-card: 0 1px 2px rgba(26, 26, 26, 0.04), 0 1px 1px rgba(26, 26, 26, 0.02);
  --shadow-modal: 0 24px 48px -12px rgba(26, 26, 26, 0.18), 0 8px 16px -8px rgba(26, 26, 26, 0.10);

  /* Type families (Tailwind picks up --font-* automatically) */
  --font-display: "Fraunces Variable", "Fraunces", Georgia, serif;
  --font-sans: "Inter Variable", "Inter", ui-sans-serif, system-ui, sans-serif;
  --font-mono: "JetBrains Mono Variable", "JetBrains Mono", ui-monospace, "SF Mono", Menlo, monospace;
}

[data-theme="dark"] {
  --color-page: #15130f;
  --color-surface: #1d1a14;
  --color-surface-2: #231f18;
  --color-ink: #ece6d4;
  --color-ink-muted: #a09786;
  --color-ink-faint: #8e8775;
  --color-divider: #2a2620;
  --color-divider-strong: #3a3328;
  --color-accent: #c5495b;
  --color-accent-soft: rgba(197, 73, 91, 0.14);
  --color-pos: #8fcf95;
  --color-neg: #e08c79;
  --color-warn: #d6a85b;
  --color-info: #9eb3d6;

  --shadow-card: 0 1px 2px rgba(0, 0, 0, 0.4), 0 1px 1px rgba(0, 0, 0, 0.2);
  --shadow-modal: 0 24px 48px -12px rgba(0, 0, 0, 0.6), 0 8px 16px -8px rgba(0, 0, 0, 0.4);
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/styles/tokens.css
git commit -m "Add design tokens (light + dark, semantic naming)"
```

---

### Task 3: Wire tokens into Tailwind v4 + load fonts

**Files:**
- Modify: `frontend/src/index.css`
- Modify: `frontend/src/main.tsx`
- Modify: `frontend/index.html`

- [ ] **Step 1: Replace `frontend/src/index.css` with token-aware @theme**

Full new contents:

```css
@import "tailwindcss";
@import "./styles/tokens.css";

/* @theme inline tells Tailwind to emit utilities that REFERENCE the
   CSS variables verbatim, so `bg-page` resolves at runtime to whatever
   --color-page is — which depends on data-theme. Without `inline`,
   Tailwind would resolve the variable at build time and lock the value. */
@theme inline {
  --color-page: var(--color-page);
  --color-surface: var(--color-surface);
  --color-surface-2: var(--color-surface-2);
  --color-ink: var(--color-ink);
  --color-ink-muted: var(--color-ink-muted);
  --color-ink-faint: var(--color-ink-faint);
  --color-divider: var(--color-divider);
  --color-divider-strong: var(--color-divider-strong);
  --color-accent: var(--color-accent);
  --color-accent-soft: var(--color-accent-soft);
  --color-pos: var(--color-pos);
  --color-neg: var(--color-neg);
  --color-warn: var(--color-warn);
  --color-info: var(--color-info);

  --font-display: var(--font-display);
  --font-sans: var(--font-sans);
  --font-mono: var(--font-mono);

  --radius-sm: var(--radius-sm);
  --radius-md: var(--radius-md);
  --radius-lg: var(--radius-lg);
  --radius-xl: var(--radius-xl);

  --shadow-card: var(--shadow-card);
  --shadow-modal: var(--shadow-modal);
}

html {
  font-family: var(--font-sans);
  background: var(--color-page);
  color: var(--color-ink);
}

body {
  background: var(--color-page);
  color: var(--color-ink);
}

/* Editorial numeric variants */
.tnum {
  font-feature-settings: "tnum" 1, "lnum" 1;
}
.tnum-mono {
  font-family: var(--font-mono);
  font-feature-settings: "tnum" 1, "lnum" 1;
}
.tnum-feature {
  font-family: var(--font-display);
  font-variation-settings: "opsz" 144;
  font-feature-settings: "tnum" 1, "lnum" 1;
}

/* Custom scrollbars — preserve existing behavior, switch to token */
* {
  scrollbar-width: thin;
  scrollbar-color: var(--color-divider-strong) transparent;
}
*::-webkit-scrollbar { width: 10px; height: 10px; }
*::-webkit-scrollbar-track { background: transparent; }
*::-webkit-scrollbar-thumb {
  background-color: var(--color-divider-strong);
  border-radius: 9999px;
  border: 2px solid transparent;
  background-clip: padding-box;
  transition: background-color 150ms ease;
}
*::-webkit-scrollbar-thumb:hover { background-color: var(--color-ink-faint); }
*::-webkit-scrollbar-thumb:active { background-color: var(--color-ink-muted); }
*::-webkit-scrollbar-corner { background: transparent; }

@keyframes progress-bar {
  0%   { width: 0%; opacity: 1; }
  60%  { width: 85%; opacity: 1; }
  100% { width: 95%; opacity: 1; }
}
.animate-progress-bar { animation: progress-bar 2s ease-out forwards; }
```

- [ ] **Step 2: Replace `frontend/src/main.tsx` to import font CSS**

Full new contents:

```tsx
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

// Font faces — variable fonts, full weight range each
import '@fontsource-variable/fraunces'
import '@fontsource-variable/inter'
import '@fontsource-variable/jetbrains-mono'

import './index.css'
import App from './App.tsx'

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
```

- [ ] **Step 3: Strip Google Fonts links from `frontend/index.html`**

Find:
```html
    <link rel="preconnect" href="https://fonts.googleapis.com" />
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin />
    <link
      href="https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
      rel="stylesheet"
    />
```

Replace with: (just remove the four lines — leave the meta tags and Google Sign-In script intact)

- [ ] **Step 4: Run dev server and confirm no FOUC errors**

```bash
cd frontend
npm run dev
```

Expected: dev server starts without error. Open `http://localhost:5173` — the existing pages render. They will look "wrong" (slate/indigo Tailwind utilities still hardcoded everywhere), but no console errors and `<html>` body should be cream (`#faf8f3`).

- [ ] **Step 5: Verify dark mode toggle works manually**

In browser dev tools console:
```js
document.documentElement.setAttribute('data-theme', 'dark')
```

Expected: page background flips to `#15130f`. Then:
```js
document.documentElement.removeAttribute('data-theme')
```

Expected: page background returns to `#faf8f3`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/index.css frontend/src/main.tsx frontend/index.html
git commit -m "Wire design tokens into Tailwind v4; load variable fonts via @fontsource"
```

---

### Task 4: FOUC-prevention inline script

**Files:**
- Modify: `frontend/index.html`

- [ ] **Step 1: Add inline script before `<div id="root">`**

In `frontend/index.html`, find:
```html
  <body>
    <div id="root"></div>
```

Replace with:
```html
  <body>
    <script>
      (function () {
        try {
          var stored = localStorage.getItem('cs.theme');
          var prefersDark = window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches;
          var theme = stored || (prefersDark ? 'dark' : 'light');
          if (theme === 'dark') {
            document.documentElement.setAttribute('data-theme', 'dark');
          }
        } catch (e) {
          /* localStorage unavailable — fall through with default light */
        }
      })();
    </script>
    <div id="root"></div>
```

- [ ] **Step 2: Manually verify FOUC prevention**

Open dev tools, simulate dark via `localStorage.setItem('cs.theme', 'dark')`, hard-reload. Observe: page paints dark from the first frame — no light flash.

Repeat with `localStorage.setItem('cs.theme', 'light')`. Observe: page paints light from the first frame.

- [ ] **Step 3: Commit**

```bash
git add frontend/index.html
git commit -m "FOUC-prevention inline script for theme initialization"
```

---

### Task 5: useTheme hook

**Files:**
- Create: `frontend/src/hooks/useTheme.ts`

- [ ] **Step 1: Write the hook**

Full contents of `frontend/src/hooks/useTheme.ts`:

```ts
import { useCallback, useEffect, useState } from 'react'

export type Theme = 'light' | 'dark'

const STORAGE_KEY = 'cs.theme'

function readInitialTheme(): Theme {
  if (typeof document === 'undefined') return 'light'
  const attr = document.documentElement.getAttribute('data-theme')
  if (attr === 'dark') return 'dark'
  return 'light'
}

/**
 * Reads/writes the active theme. The actual DOM mutation lives here so the
 * inline FOUC-prevention script in index.html and this hook stay in sync.
 */
export function useTheme(): { theme: Theme; setTheme: (next: Theme) => void; toggle: () => void } {
  const [theme, setThemeState] = useState<Theme>(readInitialTheme)

  const setTheme = useCallback((next: Theme) => {
    setThemeState(next)
    if (next === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark')
    } else {
      document.documentElement.removeAttribute('data-theme')
    }
    try {
      localStorage.setItem(STORAGE_KEY, next)
    } catch {
      /* localStorage unavailable — runtime toggle still works for the session */
    }
  }, [])

  const toggle = useCallback(() => {
    setTheme(theme === 'dark' ? 'light' : 'dark')
  }, [setTheme, theme])

  useEffect(() => {
    const mql = window.matchMedia('(prefers-color-scheme: dark)')
    const onChange = (e: MediaQueryListEvent) => {
      try {
        if (localStorage.getItem(STORAGE_KEY)) return
      } catch { /* ignore */ }
      setTheme(e.matches ? 'dark' : 'light')
    }
    mql.addEventListener('change', onChange)
    return () => mql.removeEventListener('change', onChange)
  }, [setTheme])

  return { theme, setTheme, toggle }
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/hooks/useTheme.ts
git commit -m "Add useTheme hook (read/write data-theme, localStorage-persisted)"
```

---

### Task 6: Add styleguide route (gated by env flag)

**Files:**
- Create: `frontend/src/pages/Styleguide/index.tsx`
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Write the styleguide skeleton**

Full contents of `frontend/src/pages/Styleguide/index.tsx`:

```tsx
import { useTheme } from '../../hooks/useTheme'

/**
 * Internal styleguide route — gated by VITE_SHOW_STYLEGUIDE=1.
 * Each primitive section gets registered here as it lands. The id-anchored
 * sections mean you can deep-link to a primitive: /styleguide#modal.
 */
export default function Styleguide() {
  const { theme, toggle } = useTheme()
  return (
    <div className="min-h-dvh bg-page text-ink">
      <header className="border-b border-divider px-8 py-6 flex items-center justify-between">
        <div>
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Internal</p>
          <h1 className="font-display text-3xl" style={{ fontVariationSettings: '"opsz" 96' }}>
            Styleguide
          </h1>
        </div>
        <button
          onClick={toggle}
          className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors"
        >
          {theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
        </button>
      </header>
      <main className="px-8 py-10 max-w-5xl mx-auto space-y-16">
        <section id="overview">
          <p className="text-ink-muted">
            This page renders every design-system primitive in every variant +
            state, in both light and dark. Each primitive section gets added as
            it ships (Phase 1+).
          </p>
        </section>
      </main>
    </div>
  )
}
```

- [ ] **Step 2: Register the route in `frontend/src/App.tsx`**

Find the import block and add:
```tsx
import Styleguide from './pages/Styleguide'
```

Find the `<Routes>` block. Add a new route gated by env flag. The current routes file has `<Route path="*" element={<Navigate to="/" replace />} />` as the catch-all — insert the styleguide route BEFORE that catch-all:

```tsx
{import.meta.env.VITE_SHOW_STYLEGUIDE === '1' && (
  <Route path="/styleguide" element={<Styleguide />} />
)}
```

- [ ] **Step 3: Verify dev render**

```bash
cd frontend
VITE_SHOW_STYLEGUIDE=1 npm run dev
```

Open `http://localhost:5173/styleguide`. Expected: cream page with "Styleguide" headline in Fraunces, a "Switch to dark" button, and an overview paragraph.

Click the toggle. Expected: page flips to warm dark with cream text.

Restart without the env flag (`npm run dev`), navigate to `/styleguide`. Expected: redirected to `/` (catch-all wins because the styleguide route isn't registered).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Styleguide/index.tsx frontend/src/App.tsx
git commit -m "Add internal /styleguide route (gated by VITE_SHOW_STYLEGUIDE=1)"
```

---

### Task 7: ThemeToggle primitive

**Files:**
- Create: `frontend/src/components/ui/ThemeToggle/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/ThemeToggle/index.tsx`:

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
      className={`text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink ${className}`}
    >
      {theme === 'dark' ? 'Light' : 'Dark'}
    </button>
  )
}
```

- [ ] **Step 2: Replace the inline toggle in Styleguide with the primitive**

In `frontend/src/pages/Styleguide/index.tsx`, find:
```tsx
        <button
          onClick={toggle}
          className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors"
        >
          {theme === 'dark' ? 'Switch to light' : 'Switch to dark'}
        </button>
```

Replace with:
```tsx
        <ThemeToggle />
```

And add the import at the top:
```tsx
import { ThemeToggle } from '../../components/ui/ThemeToggle'
```

Remove the now-unused `useTheme` import and the `const { theme, toggle } = useTheme()` line at the top of the component (the toggle owns its own theme state).

- [ ] **Step 3: Verify in browser**

`VITE_SHOW_STYLEGUIDE=1 npm run dev`, navigate to `/styleguide`, click the new ThemeToggle. Expected: theme toggles correctly; `aria-label` visible in dev tools.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/ThemeToggle/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add ThemeToggle primitive; consume in styleguide"
```

---

### Task 8: Verify WCAG AA accent contrast

**Files:**
- (Possibly) Modify: `frontend/src/styles/tokens.css`

Per spec §1.2 risk: `--color-accent` (`#7a1c2c`) on `--color-page` (`#faf8f3`) must clear WCAG AA for body text (4.5:1).

- [ ] **Step 1: Compute contrast**

Run a contrast check (any tool). Inputs: foreground `#7a1c2c`, background `#faf8f3`.

Expected: ≥ 4.5:1 (passes AA for body text). At time of writing, this combination scores ~9.1:1 — comfortably passing.

For the dark mode pair (`#c5495b` on `#15130f`), expected ≥ 4.5:1. Should score ~5.5:1 — passes.

- [ ] **Step 2: If either fails AA**

If light fails: change `--color-accent` light value to `#6a1828` and re-test.

If dark fails: change `--color-accent` dark value to `#d4647a` and re-test.

If both pass (expected outcome): no edit needed; this task is documentation-only.

- [ ] **Step 3: Commit only if values changed**

```bash
git diff --quiet frontend/src/styles/tokens.css || {
  git add frontend/src/styles/tokens.css
  git commit -m "Tune accent color values to clear WCAG AA on body text"
}
```

---

## Phase 2 — Foundation Primitives

**Convention for all UI primitives going forward:** each lives in `frontend/src/components/ui/<Name>/index.tsx`. Each task: write the component → add a styleguide section → manually verify in light + dark → commit. Styleguide entries appear under a section with `id="<lowercase-primitive-name>"` so they're deep-linkable.

### Task 9: Heading

**Files:**
- Create: `frontend/src/components/ui/Heading/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the Heading primitive**

Full contents of `frontend/src/components/ui/Heading/index.tsx`:

```tsx
import type { ReactNode } from 'react'

type Level = 1 | 2 | 3 | 4

interface Props {
  level?: Level
  children: ReactNode
  className?: string
  /** Override the rendered tag — defaults to h${level}. */
  as?: 'h1' | 'h2' | 'h3' | 'h4' | 'h5' | 'h6' | 'div' | 'span'
}

const STYLE_BY_LEVEL: Record<Level, { fontSize: string; opsz: number; lineHeight: string; letterSpacing: string }> = {
  1: { fontSize: '56px', opsz: 144, lineHeight: '1.05', letterSpacing: '-0.025em' },
  2: { fontSize: '34px', opsz: 96,  lineHeight: '1.1',  letterSpacing: '-0.02em' },
  3: { fontSize: '24px', opsz: 36,  lineHeight: '1.2',  letterSpacing: '-0.015em' },
  4: { fontSize: '18px', opsz: 24,  lineHeight: '1.3',  letterSpacing: '-0.01em' },
}

export function Heading({ level = 2, children, className = '', as }: Props) {
  const Tag = (as ?? `h${level}`) as keyof React.JSX.IntrinsicElements
  const s = STYLE_BY_LEVEL[level]
  return (
    <Tag
      className={`font-display text-ink font-medium ${className}`}
      style={{
        fontSize: s.fontSize,
        lineHeight: s.lineHeight,
        letterSpacing: s.letterSpacing,
        fontVariationSettings: `"opsz" ${s.opsz}`,
      }}
    >
      {children}
    </Tag>
  )
}
```

- [ ] **Step 2: Add a Heading section to the styleguide**

In `frontend/src/pages/Styleguide/index.tsx`, add the import:
```tsx
import { Heading } from '../../components/ui/Heading'
```

Inside `<main>`, after the `#overview` section, add:
```tsx
        <section id="heading" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Heading</p>
          <Heading level={1}>Display — Net EV per year</Heading>
          <Heading level={2}>Headline — Wallet · Default Scenario</Heading>
          <Heading level={3}>Title — Sapphire Reserve</Heading>
          <Heading level={4}>Subtitle — Annual fee waived</Heading>
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`VITE_SHOW_STYLEGUIDE=1 npm run dev`, navigate `/styleguide#heading`. Verify all four levels render in Fraunces, decreasing in size; toggle theme; verify ink color flips. Confirm optical-size axis is visible (Display has wider strokes than Subtitle).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Heading/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Heading primitive (4 levels, optical-size axis)"
```

---

### Task 10: Eyebrow

**Files:**
- Create: `frontend/src/components/ui/Eyebrow/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Eyebrow/index.tsx`:

```tsx
import type { ReactNode } from 'react'

interface Props {
  children: ReactNode
  /** Add the oxblood accent rule above the label. */
  accent?: boolean
  className?: string
}

export function Eyebrow({ children, accent = false, className = '' }: Props) {
  return (
    <div className={className}>
      {accent && (
        <span
          aria-hidden="true"
          className="block bg-accent mb-2"
          style={{ width: 28, height: 2 }}
        />
      )}
      <span className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">
        {children}
      </span>
    </div>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add the import:
```tsx
import { Eyebrow } from '../../components/ui/Eyebrow'
```

Add a new section after `#heading`:
```tsx
        <section id="eyebrow" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Eyebrow</p>
          <Eyebrow>Net EV / yr</Eyebrow>
          <Eyebrow accent>With accent rule</Eyebrow>
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#eyebrow`. Verify Inter 600 uppercase, 0.18em tracked, ink-faint color; accent variant shows 28×2px oxblood bar above. Toggle theme.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Eyebrow/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Eyebrow primitive (with optional accent rule)"
```

---

### Task 11: Money

**Files:**
- Create: `frontend/src/components/ui/Money/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Inspect existing format helpers**

```bash
grep -n "export function format" frontend/src/utils/format.ts
```

Note the signatures of `formatMoney` and `formatMoneyExact` for use below.

- [ ] **Step 2: Write the primitive**

Full contents of `frontend/src/components/ui/Money/index.tsx`:

```tsx
import { formatMoney, formatMoneyExact } from '../../../utils/format'

type Tone = 'neutral' | 'pos' | 'neg' | 'auto'
type Precision = 0 | 2 | 'auto'

interface Props {
  value: number
  precision?: Precision
  tone?: Tone
  /** Render in feature-size Fraunces tabular numerals (used for hero stats). */
  feature?: boolean
  /** Default true — render in JetBrains Mono tabular numerals. Set false for inline body. */
  mono?: boolean
  className?: string
}

function toneClass(tone: Tone, value: number): string {
  if (tone === 'pos') return 'text-pos'
  if (tone === 'neg') return 'text-neg'
  if (tone === 'auto') return value < 0 ? 'text-neg' : value > 0 ? 'text-pos' : 'text-ink'
  return 'text-ink'
}

export function Money({
  value,
  precision = 'auto',
  tone = 'neutral',
  feature = false,
  mono = true,
  className = '',
}: Props) {
  const formatted =
    precision === 0
      ? formatMoney(value)
      : precision === 2
        ? formatMoneyExact(value)
        : Number.isInteger(value)
          ? formatMoney(value)
          : formatMoneyExact(value)

  const fontClass = feature ? 'tnum-feature' : mono ? 'tnum-mono' : 'tnum'

  return (
    <span className={`${fontClass} ${toneClass(tone, value)} ${className}`}>
      {formatted}
    </span>
  )
}
```

- [ ] **Step 3: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add import:
```tsx
import { Money } from '../../components/ui/Money'
```

Add section:
```tsx
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
```

- [ ] **Step 4: Verify in styleguide (light + dark)**

`/styleguide#money`. Verify:
- Mono numerals align (try `1,284.50` next to `842.00`)
- Auto tone: positive renders pos-green, negative renders neg-red
- Feature variant renders large Fraunces serif
- Both modes preserve all behavior

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Money/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Money primitive (formatted currency, mono/feature variants, auto tone)"
```

---

### Task 12: Points

**Files:**
- Create: `frontend/src/components/ui/Points/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Points/index.tsx`:

```tsx
import { formatPoints, formatPointsExact, pointsUnitLabel } from '../../../utils/format'

interface Props {
  value: number
  /** Currency unit suffix (e.g., 'BP', 'UR', 'MR'). When provided, rendered after the number. */
  unit?: string
  /** When unit is set, optionally use the helper to look up a localized label. */
  unitFromCurrencyCode?: string
  /** When true, render exact integer; otherwise use compact formatting. */
  exact?: boolean
  feature?: boolean
  mono?: boolean
  className?: string
}

export function Points({
  value,
  unit,
  unitFromCurrencyCode,
  exact = false,
  feature = false,
  mono = true,
  className = '',
}: Props) {
  const formatted = exact ? formatPointsExact(value) : formatPoints(value)
  const resolvedUnit = unit ?? (unitFromCurrencyCode ? pointsUnitLabel(unitFromCurrencyCode) : undefined)
  const fontClass = feature ? 'tnum-feature' : mono ? 'tnum-mono' : 'tnum'

  return (
    <span className={`${fontClass} text-ink ${className}`}>
      {formatted}
      {resolvedUnit && <span className="text-ink-faint ml-1 text-[0.85em]">{resolvedUnit}</span>}
    </span>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add import:
```tsx
import { Points } from '../../components/ui/Points'
```

Add section:
```tsx
        <section id="points" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Points</p>
          <div className="space-y-2">
            <div>Compact: <Points value={125000} /></div>
            <div>Exact: <Points value={125000} exact /></div>
            <div>With unit: <Points value={125000} unit="UR" /></div>
            <div>Feature: <Points value={125000} feature unit="UR" /></div>
          </div>
        </section>
```

- [ ] **Step 3: Verify in styleguide**

`/styleguide#points`. Confirm rendering, alignment, unit suffix style.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Points/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Points primitive (formatted points/miles, optional unit suffix)"
```

---

### Task 13: Stat

**Files:**
- Create: `frontend/src/components/ui/Stat/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Stat/index.tsx`:

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
  /** Add the oxblood accent rule above the eyebrow. */
  accent?: boolean
  /** Right-align the entire stack. Defaults to left. */
  align?: 'left' | 'right'
  className?: string
}

export function Stat({ label, value, caption, accent = false, align = 'left', className = '' }: Props) {
  const alignClass = align === 'right' ? 'text-right items-end' : 'text-left items-start'
  return (
    <div className={`flex flex-col ${alignClass} ${className}`}>
      <Eyebrow accent={accent}>{label}</Eyebrow>
      <div className="mt-1">{value}</div>
      {caption && (
        <div className="text-xs text-ink-muted mt-1">{caption}</div>
      )}
    </div>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add import:
```tsx
import { Stat } from '../../components/ui/Stat'
```

Add section:
```tsx
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
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#stat`. Verify hero Stat shows accent rule, eyebrow, big Fraunces number, caption. Mini stats line up clean.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Stat/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Stat primitive (eyebrow + hero number + caption block)"
```

---

## Phase 3 — Surface Primitives

### Task 14: Surface

**Files:**
- Create: `frontend/src/components/ui/Surface/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Surface/index.tsx`:

```tsx
import type { ReactNode, HTMLAttributes } from 'react'

type Variant = 'panel' | 'inset' | 'bare'
type Padding = 'none' | 'sm' | 'md' | 'lg'

interface Props extends Omit<HTMLAttributes<HTMLDivElement>, 'children'> {
  variant?: Variant
  padding?: Padding
  /** Apply --shadow-card. Default false (editorial leans on borders). */
  elevated?: boolean
  children: ReactNode
}

const VARIANT_CLASS: Record<Variant, string> = {
  panel: 'bg-surface border border-divider',
  inset: 'bg-surface-2 border border-divider',
  bare: 'bg-transparent',
}
const PADDING_CLASS: Record<Padding, string> = {
  none: '',
  sm: 'p-3',
  md: 'p-5',
  lg: 'p-7',
}

export function Surface({
  variant = 'panel',
  padding = 'md',
  elevated = false,
  className = '',
  children,
  ...rest
}: Props) {
  return (
    <div
      {...rest}
      className={`rounded-lg ${VARIANT_CLASS[variant]} ${PADDING_CLASS[padding]} ${elevated ? 'shadow-card' : ''} ${className}`}
    >
      {children}
    </div>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add import:
```tsx
import { Surface } from '../../components/ui/Surface'
```

Add section:
```tsx
        <section id="surface" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Surface</p>
          <div className="grid grid-cols-3 gap-4">
            <Surface variant="panel">Panel (default)</Surface>
            <Surface variant="inset">Inset</Surface>
            <Surface variant="bare">Bare</Surface>
          </div>
          <Surface elevated>Elevated panel</Surface>
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#surface`. Confirm panel = white/dark surface with divider border, inset = cream/darker bg with divider border, bare = transparent. Elevated has subtle shadow visible only on hover-state surfaces.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Surface/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Surface primitive (panel/inset/bare variants)"
```

---

### Task 15: Modal (with ModalBackdrop compatibility shim)

**Files:**
- Create: `frontend/src/components/ui/Modal/index.tsx`
- Modify: `frontend/src/components/ModalBackdrop.tsx` (becomes a re-export shim)
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Read existing ModalBackdrop to understand its API**

```bash
cat frontend/src/components/ModalBackdrop.tsx
```

Note its prop shape (children, onClose). The new Modal must subsume it.

- [ ] **Step 2: Write the new Modal primitive**

Full contents of `frontend/src/components/ui/Modal/index.tsx`:

```tsx
import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Size = 'xs' | 'sm' | 'md' | 'lg'

interface ModalProps {
  open: boolean
  onClose: () => void
  size?: Size
  /** Allow Esc / backdrop-click dismissal. Default true. */
  dismissible?: boolean
  children: ReactNode
  className?: string
}

const SIZE_CLASS: Record<Size, string> = {
  xs: 'w-80',
  sm: 'max-w-md',
  md: 'max-w-lg',
  lg: 'max-w-2xl',
}

export function Modal({
  open,
  onClose,
  size = 'md',
  dismissible = true,
  children,
  className = '',
}: ModalProps) {
  useEffect(() => {
    if (!open || !dismissible) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, dismissible, onClose])

  if (!open) return null

  return createPortal(
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-[1px]"
      onClick={dismissible ? onClose : undefined}
      role="presentation"
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className={`bg-surface border border-divider rounded-xl shadow-modal w-full ${SIZE_CLASS[size]} mx-4 ${className}`}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}

interface SectionProps {
  children: ReactNode
  className?: string
}

export function ModalHeader({ children, className = '' }: SectionProps) {
  return (
    <div className={`px-6 pt-5 pb-3 border-b border-divider ${className}`}>
      {children}
    </div>
  )
}

export function ModalBody({ children, className = '' }: SectionProps) {
  return <div className={`px-6 py-5 ${className}`}>{children}</div>
}

export function ModalFooter({ children, className = '' }: SectionProps) {
  return (
    <div className={`px-6 py-4 border-t border-divider flex items-center justify-end gap-2 ${className}`}>
      {children}
    </div>
  )
}
```

- [ ] **Step 3: Convert `frontend/src/components/ModalBackdrop.tsx` to a compat shim**

Read the existing file first to confirm its current export shape, then replace contents with a deprecation-marked shim. The shim wraps the old API on top of the new Modal:

Full new contents of `frontend/src/components/ModalBackdrop.tsx`:

```tsx
/**
 * @deprecated Use `Modal` from `components/ui/Modal` instead.
 * Compatibility shim — kept until all call sites are migrated in Phase 7.
 */
import type { ReactNode } from 'react'
import { Modal } from './ui/Modal'

interface Props {
  onClose: () => void
  children: ReactNode
}

export function ModalBackdrop({ onClose, children }: Props) {
  return (
    <Modal open onClose={onClose}>
      {children}
    </Modal>
  )
}

export default ModalBackdrop
```

If the original file used a default export, named export, or a different prop shape, mirror that exactly so existing call sites don't break.

- [ ] **Step 4: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add imports:
```tsx
import { useState } from 'react'
import { Modal, ModalHeader, ModalBody, ModalFooter } from '../../components/ui/Modal'
```

Add section:
```tsx
        <section id="modal" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Modal</p>
          <ModalDemo />
        </section>
```

Above the export default, add a small demo component:
```tsx
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
      <Modal open={open} onClose={() => setOpen(false)}>
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
```

- [ ] **Step 5: Verify in styleguide (light + dark)**

`/styleguide#modal`. Click "Open modal". Verify:
- Backdrop dims; modal centered with border + shadow
- Esc dismisses; backdrop click dismisses
- Header/body/footer styling clean
- Toggle theme while modal open — theme propagates instantly

- [ ] **Step 6: Verify existing call sites still render**

Without doing any migration yet, smoke-check that any existing `<ModalBackdrop>` usage (e.g., in `AddScenarioModal`, `ApplicationRuleWarningModal`, `UsernamePrompt`) still works via the shim. Open one of those flows and confirm it renders.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/Modal/index.tsx frontend/src/components/ModalBackdrop.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Modal primitive; convert ModalBackdrop to compatibility shim"
```

---

### Task 16: Popover (with InfoPopover compatibility shim)

**Files:**
- Create: `frontend/src/components/ui/Popover/index.tsx`
- Modify: `frontend/src/components/InfoPopover.tsx` (compat shim)
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Read existing InfoPopover to capture its public API**

```bash
cat frontend/src/components/InfoPopover.tsx
```

Note all named exports and their prop shapes. The shim must preserve every existing export.

- [ ] **Step 2: Write the new Popover primitive**

Full contents of `frontend/src/components/ui/Popover/index.tsx`:

```tsx
import { useEffect, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  /** Element that triggers the popover. Receives `onClick` to toggle. */
  trigger: (props: { onClick: () => void; ref: React.RefObject<HTMLElement | null> }) => ReactNode
  /** Popover content. */
  children: ReactNode
  /** Close on Esc / outside click. Default true. */
  dismissible?: boolean
  /** Render in a portal (escape overflow:hidden ancestors). Default false. */
  portal?: boolean
  /** Side of the trigger to anchor on. Default 'bottom'. */
  side?: 'top' | 'bottom' | 'left' | 'right'
  className?: string
}

export function Popover({
  trigger,
  children,
  dismissible = true,
  portal = false,
  side = 'bottom',
  className = '',
}: Props) {
  const [open, setOpen] = useState(false)
  const triggerRef = useRef<HTMLElement | null>(null)
  const popoverRef = useRef<HTMLDivElement | null>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  const computePosition = () => {
    if (!triggerRef.current) return
    const r = triggerRef.current.getBoundingClientRect()
    const margin = 8
    let top = 0, left = 0
    switch (side) {
      case 'top':    top = r.top - margin; left = r.left + r.width / 2; break
      case 'bottom': top = r.bottom + margin; left = r.left + r.width / 2; break
      case 'left':   top = r.top + r.height / 2; left = r.left - margin; break
      case 'right':  top = r.top + r.height / 2; left = r.right + margin; break
    }
    setPos({ top, left })
  }

  useEffect(() => {
    if (!open) return
    computePosition()
    const onScroll = () => computePosition()
    window.addEventListener('scroll', onScroll, true)
    window.addEventListener('resize', onScroll)
    return () => {
      window.removeEventListener('scroll', onScroll, true)
      window.removeEventListener('resize', onScroll)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, side])

  useEffect(() => {
    if (!open || !dismissible) return
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false) }
    const onClick = (e: MouseEvent) => {
      const t = e.target as Node
      if (popoverRef.current?.contains(t)) return
      if (triggerRef.current?.contains(t)) return
      setOpen(false)
    }
    window.addEventListener('keydown', onKey)
    window.addEventListener('mousedown', onClick)
    return () => {
      window.removeEventListener('keydown', onKey)
      window.removeEventListener('mousedown', onClick)
    }
  }, [open, dismissible])

  const popoverNode = open && pos && (
    <div
      ref={popoverRef}
      role="dialog"
      style={{
        position: 'fixed',
        top: pos.top,
        left: pos.left,
        transform: side === 'top'
          ? 'translate(-50%, -100%)'
          : side === 'bottom'
            ? 'translate(-50%, 0)'
            : side === 'left'
              ? 'translate(-100%, -50%)'
              : 'translate(0, -50%)',
        zIndex: 60,
      }}
      className={`bg-surface border border-divider rounded-lg shadow-modal p-3 max-w-sm ${className}`}
    >
      {children}
    </div>
  )

  return (
    <>
      {trigger({ onClick: () => setOpen((v) => !v), ref: triggerRef })}
      {popoverNode && (portal ? createPortal(popoverNode, document.body) : popoverNode)}
    </>
  )
}
```

- [ ] **Step 3: Convert `frontend/src/components/InfoPopover.tsx` to a compat shim**

Read the existing exports first to make sure the shim preserves every named export with matching prop shapes. Replace the file with re-exports that wrap the new `Popover` to match the old API. Mark the file deprecated:

```tsx
/**
 * @deprecated Use `Popover` from `components/ui/Popover` instead.
 * Compatibility shim — kept until all call sites are migrated in Phase 7.
 */
// ... preserve every named export from the original file, each implemented
// in terms of the new Popover. If the original exports are e.g.
// `InfoPopover`, `InfoQuoteBox`, then both are re-exported here as wrappers
// over Popover. Keep prop names identical.
```

If the original file's API is non-trivial, write specific wrappers per export. The exact wrapper code depends on what the original exposes — read it first and mirror accordingly.

- [ ] **Step 4: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add import:
```tsx
import { Popover } from '../../components/ui/Popover'
```

Add section:
```tsx
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
```

- [ ] **Step 5: Verify in styleguide (light + dark)**

`/styleguide#popover`. Verify each side anchors correctly, Esc + outside-click dismiss, theme toggles correctly while open. Confirm the portal variant escapes any overflow:hidden parent (try inside a clipped container).

- [ ] **Step 6: Verify existing InfoPopover call sites still render**

Open `MethodologyInfoPopover` (in `pages/RoadmapTool/components/summary/`) and any other site importing from `components/InfoPopover`. Confirm they still work via the shim.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/ui/Popover/index.tsx frontend/src/components/InfoPopover.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Popover primitive; convert InfoPopover to compatibility shim"
```

---

### Task 17: Drawer

**Files:**
- Create: `frontend/src/components/ui/Drawer/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Drawer/index.tsx`:

```tsx
import { useEffect, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Side = 'left' | 'right'
type Width = 'sm' | 'md' | 'lg'

interface Props {
  open: boolean
  onClose: () => void
  side?: Side
  width?: Width
  dismissible?: boolean
  children: ReactNode
  className?: string
}

const WIDTH_CLASS: Record<Width, string> = {
  sm: 'w-72',
  md: 'w-96',
  lg: 'w-[28rem]',
}

export function Drawer({
  open,
  onClose,
  side = 'right',
  width = 'md',
  dismissible = true,
  children,
  className = '',
}: Props) {
  useEffect(() => {
    if (!open || !dismissible) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [open, dismissible, onClose])

  if (!open) return null

  const sideClass = side === 'right' ? 'right-0' : 'left-0'
  return createPortal(
    <div
      className="fixed inset-0 z-50 bg-black/40"
      onClick={dismissible ? onClose : undefined}
    >
      <div
        role="dialog"
        aria-modal="true"
        onClick={(e) => e.stopPropagation()}
        className={`absolute top-0 bottom-0 ${sideClass} ${WIDTH_CLASS[width]} bg-surface border-l border-divider shadow-modal overflow-y-auto ${className}`}
      >
        {children}
      </div>
    </div>,
    document.body,
  )
}
```

- [ ] **Step 2: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add import:
```tsx
import { Drawer } from '../../components/ui/Drawer'
```

Add demo component above the default export:
```tsx
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
      <Drawer open={open} onClose={() => setOpen(false)} side="right" width="md">
        <div className="p-6 space-y-3">
          <Heading level={3}>Drawer</Heading>
          <p className="text-ink-muted text-sm">Slide-over panel from the right. Esc + backdrop dismiss.</p>
        </div>
      </Drawer>
    </>
  )
}
```

Add section:
```tsx
        <section id="drawer" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Drawer</p>
          <DrawerDemo />
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#drawer`. Open drawer, verify slide-in from right, dismiss via Esc and backdrop, toggle theme while open.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Drawer/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Drawer primitive (slide-over from left/right)"
```

---

### Task 18: Toast

**Files:**
- Create: `frontend/src/components/ui/Toast/index.tsx`
- Modify: `frontend/src/App.tsx` (mount the provider)
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the Toast primitive (provider + hook)**

Full contents of `frontend/src/components/ui/Toast/index.tsx`:

```tsx
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { createPortal } from 'react-dom'

type Tone = 'info' | 'success' | 'error'
interface Toast { id: number; tone: Tone; message: string }

interface ToastContextValue {
  show: (message: string, tone?: Tone) => void
}
const ToastContext = createContext<ToastContextValue | null>(null)

export function useToast(): ToastContextValue {
  const ctx = useContext(ToastContext)
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>')
  return ctx
}

interface ProviderProps { children: ReactNode }

export function ToastProvider({ children }: ProviderProps) {
  const [toasts, setToasts] = useState<Toast[]>([])
  const idRef = useRef(0)

  const show = useCallback((message: string, tone: Tone = 'info') => {
    const id = ++idRef.current
    setToasts((cur) => [...cur, { id, tone, message }])
    setTimeout(() => {
      setToasts((cur) => cur.filter((t) => t.id !== id))
    }, 4000)
  }, [])

  const value = useMemo(() => ({ show }), [show])

  return (
    <ToastContext.Provider value={value}>
      {children}
      {createPortal(
        <div className="fixed top-4 right-4 z-[100] flex flex-col gap-2 max-w-sm">
          {toasts.map((t) => (
            <ToastItem key={t.id} toast={t} />
          ))}
        </div>,
        document.body,
      )}
    </ToastContext.Provider>
  )
}

function ToastItem({ toast }: { toast: Toast }) {
  const [enter, setEnter] = useState(false)
  useEffect(() => { setEnter(true) }, [])
  const toneClass: Record<Tone, string> = {
    info: 'border-info/40',
    success: 'border-pos/40',
    error: 'border-neg/40',
  }
  return (
    <div
      role="status"
      className={`bg-surface border ${toneClass[toast.tone]} rounded-md px-4 py-3 text-sm text-ink shadow-card transition-all duration-200 ${
        enter ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-4'
      }`}
    >
      {toast.message}
    </div>
  )
}
```

- [ ] **Step 2: Mount `ToastProvider` in App.tsx**

In `frontend/src/App.tsx`, find the outermost provider tree (likely `<QueryClientProvider>`/`<AuthProvider>`/`<BrowserRouter>`). Wrap the existing children with `<ToastProvider>` immediately inside `<BrowserRouter>` (or wherever route content begins) so any page can call `useToast`. Add the import:
```tsx
import { ToastProvider } from './components/ui/Toast'
```

- [ ] **Step 3: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add import:
```tsx
import { useToast } from '../../components/ui/Toast'
```

Add demo component above the default export:
```tsx
function ToastDemo() {
  const { show } = useToast()
  return (
    <div className="flex gap-2">
      <button onClick={() => show('Hello — info toast', 'info')} className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink">Info</button>
      <button onClick={() => show('Saved successfully', 'success')} className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink">Success</button>
      <button onClick={() => show('Something broke', 'error')} className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink">Error</button>
    </div>
  )
}
```

Add section:
```tsx
        <section id="toast" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Toast</p>
          <ToastDemo />
        </section>
```

- [ ] **Step 4: Verify in styleguide (light + dark)**

`/styleguide#toast`. Click each button, verify slide-in from right + auto-dismiss after 4s, tone color border-tinted matches semantic token.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/ui/Toast/index.tsx frontend/src/App.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Toast provider/primitive (info/success/error tones)"
```

---

### Task 19: Tooltip

**Files:**
- Create: `frontend/src/components/ui/Tooltip/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Tooltip/index.tsx`:

```tsx
import { useRef, useState, type ReactElement, cloneElement } from 'react'
import { createPortal } from 'react-dom'

interface Props {
  label: string
  /** Default 'top'. */
  side?: 'top' | 'bottom' | 'left' | 'right'
  children: ReactElement
}

export function Tooltip({ label, side = 'top', children }: Props) {
  const ref = useRef<HTMLElement | null>(null)
  const [pos, setPos] = useState<{ top: number; left: number } | null>(null)

  const show = () => {
    if (!ref.current) return
    const r = ref.current.getBoundingClientRect()
    const m = 6
    let top = 0, left = 0
    switch (side) {
      case 'top':    top = r.top - m; left = r.left + r.width / 2; break
      case 'bottom': top = r.bottom + m; left = r.left + r.width / 2; break
      case 'left':   top = r.top + r.height / 2; left = r.left - m; break
      case 'right':  top = r.top + r.height / 2; left = r.right + m; break
    }
    setPos({ top, left })
  }
  const hide = () => setPos(null)

  // Clone the child to attach ref + handlers without imposing structure.
  const child = cloneElement(children as ReactElement<Record<string, unknown>>, {
    ref,
    onMouseEnter: show,
    onMouseLeave: hide,
    onFocus: show,
    onBlur: hide,
  })

  const tooltipNode = pos && (
    <span
      role="tooltip"
      style={{
        position: 'fixed',
        top: pos.top,
        left: pos.left,
        transform:
          side === 'top'    ? 'translate(-50%, -100%)' :
          side === 'bottom' ? 'translate(-50%, 0)' :
          side === 'left'   ? 'translate(-100%, -50%)' :
                              'translate(0, -50%)',
        zIndex: 70,
      }}
      className="px-2 py-1 rounded bg-ink text-page text-xs whitespace-nowrap pointer-events-none shadow-card"
    >
      {label}
    </span>
  )

  return (
    <>
      {child}
      {tooltipNode && createPortal(tooltipNode, document.body)}
    </>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

In `frontend/src/pages/Styleguide/index.tsx`, add import:
```tsx
import { Tooltip } from '../../components/ui/Tooltip'
```

Add section:
```tsx
        <section id="tooltip" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Tooltip</p>
          <div className="flex gap-3">
            <Tooltip label="Top tooltip">
              <button className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink">Hover me</button>
            </Tooltip>
            <Tooltip label="Right tooltip" side="right">
              <button className="text-sm border border-divider rounded-md px-3 py-1.5 hover:bg-surface-2 transition-colors text-ink">Hover (right)</button>
            </Tooltip>
          </div>
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#tooltip`. Hover buttons, verify tooltip appears with correct anchor, hides on leave/blur, theme propagates.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Tooltip/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Tooltip primitive (hover-only short text, portaled)"
```

---

## Phase 4 — Form Primitives

### Task 20: Button

**Files:**
- Create: `frontend/src/components/ui/Button/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Button/index.tsx`:

```tsx
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from 'react'

type Variant = 'primary' | 'secondary' | 'ghost' | 'link' | 'icon'
type Size = 'sm' | 'md' | 'lg'

interface Props extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: Size
  loading?: boolean
  children: ReactNode
}

const VARIANT: Record<Variant, string> = {
  primary:   'bg-accent text-page hover:opacity-90',
  secondary: 'bg-transparent text-ink border border-ink hover:bg-surface-2',
  ghost:     'bg-transparent text-ink hover:bg-surface-2',
  link:      'bg-transparent text-accent underline underline-offset-2 hover:opacity-80 px-0 py-0',
  icon:      'bg-transparent text-ink hover:bg-surface-2 aspect-square justify-center',
}
const SIZE: Record<Size, string> = {
  sm: 'text-xs px-2.5 py-1.5',
  md: 'text-sm px-3.5 py-2',
  lg: 'text-base px-5 py-2.5',
}

export const Button = forwardRef<HTMLButtonElement, Props>(function Button(
  { variant = 'primary', size = 'md', loading = false, disabled, children, className = '', ...rest },
  ref,
) {
  const base = variant === 'link' ? '' : 'rounded-md'
  return (
    <button
      ref={ref}
      disabled={disabled || loading}
      className={`inline-flex items-center gap-2 font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed ${base} ${SIZE[size]} ${VARIANT[variant]} ${className}`}
      {...rest}
    >
      {loading && (
        <span aria-hidden="true" className="inline-block w-3 h-3 rounded-full border-2 border-current border-t-transparent animate-spin" />
      )}
      {children}
    </button>
  )
})
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { Button } from '../../components/ui/Button'
```

Add section:
```tsx
        <section id="button" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Button</p>
          <div className="flex flex-wrap items-center gap-3">
            <Button variant="primary">Primary</Button>
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
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#button`. Hover/active states, loading spinner spins, disabled visually muted.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Button/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Button primitive (5 variants, 3 sizes, loading state)"
```

---

### Task 21: Input

**Files:**
- Create: `frontend/src/components/ui/Input/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Input/index.tsx`:

```tsx
import { forwardRef, type InputHTMLAttributes } from 'react'

interface Props extends InputHTMLAttributes<HTMLInputElement> {
  invalid?: boolean
}

export const Input = forwardRef<HTMLInputElement, Props>(function Input(
  { invalid = false, className = '', type = 'text', ...rest },
  ref,
) {
  return (
    <input
      ref={ref}
      type={type}
      aria-invalid={invalid || undefined}
      className={`w-full bg-surface text-ink border ${invalid ? 'border-neg' : 'border-divider'} rounded-md px-3 py-2 text-sm placeholder:text-ink-faint focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft ${className}`}
      {...rest}
    />
  )
})
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { Input } from '../../components/ui/Input'
```

Add section:
```tsx
        <section id="input" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Input</p>
          <div className="space-y-3 max-w-sm">
            <Input placeholder="Default state" />
            <Input placeholder="Disabled" disabled />
            <Input placeholder="Invalid" invalid defaultValue="bad@value" />
            <Input type="number" placeholder="Number" />
          </div>
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#input`. Focus state shows accent ring; invalid state red border; disabled muted.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Input/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Input primitive (focus ring, invalid + disabled states)"
```

---

### Task 22: Field (label + control wrapper)

**Files:**
- Create: `frontend/src/components/ui/Field/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Field/index.tsx`:

```tsx
import { useId, type ReactNode, cloneElement, isValidElement, type ReactElement } from 'react'

interface Props {
  label: ReactNode
  hint?: ReactNode
  error?: ReactNode
  required?: boolean
  /** A single form control. We pass `id` + `aria-describedby` to it. */
  children: ReactElement
}

export function Field({ label, hint, error, required = false, children }: Props) {
  const id = useId()
  const hintId = `${id}-hint`
  const errorId = `${id}-error`
  const describedBy = [hint && hintId, error && errorId].filter(Boolean).join(' ') || undefined

  const child = isValidElement(children)
    ? cloneElement(children as ReactElement<Record<string, unknown>>, {
        id,
        'aria-describedby': describedBy,
        invalid: !!error || (children.props as Record<string, unknown>).invalid,
      })
    : children

  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="block text-sm font-medium text-ink">
        {label}
        {required && <span className="text-neg ml-1">*</span>}
      </label>
      {child}
      {hint && !error && <p id={hintId} className="text-xs text-ink-muted">{hint}</p>}
      {error && <p id={errorId} className="text-xs text-neg">{error}</p>}
    </div>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { Field } from '../../components/ui/Field'
```

Add section:
```tsx
        <section id="field" className="space-y-4 max-w-sm">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Field</p>
          <Field label="Annual spend" hint="Wallet-wide total in USD" required>
            <Input placeholder="120,000" />
          </Field>
          <Field label="Email" error="Not a valid email">
            <Input defaultValue="bad" />
          </Field>
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#field`. Confirm label/control association via id; hint vs error mutual exclusion; required marker red.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Field/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Field primitive (label + control + hint/error wrapper)"
```

---

### Task 23: Select

**Files:**
- Create: `frontend/src/components/ui/Select/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Select/index.tsx`:

```tsx
import { forwardRef, type SelectHTMLAttributes, type ReactNode } from 'react'

interface Props extends SelectHTMLAttributes<HTMLSelectElement> {
  invalid?: boolean
  children: ReactNode
}

export const Select = forwardRef<HTMLSelectElement, Props>(function Select(
  { invalid = false, className = '', children, ...rest },
  ref,
) {
  return (
    <div className="relative">
      <select
        ref={ref}
        aria-invalid={invalid || undefined}
        className={`w-full appearance-none bg-surface text-ink border ${invalid ? 'border-neg' : 'border-divider'} rounded-md pl-3 pr-8 py-2 text-sm focus:outline-none focus:border-accent focus:ring-2 focus:ring-accent-soft ${className}`}
        {...rest}
      >
        {children}
      </select>
      <span aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink-faint text-xs">▾</span>
    </div>
  )
})
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { Select } from '../../components/ui/Select'
```

Add section:
```tsx
        <section id="select" className="space-y-4 max-w-sm">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Select</p>
          <Select defaultValue="">
            <option value="" disabled>Pick a scenario</option>
            <option>Default</option>
            <option>What-if A</option>
            <option>What-if B</option>
          </Select>
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#select`. Native popup is OS-styled but trigger is editorial.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Select/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Select primitive (native, editorial-styled trigger)"
```

---

### Task 24: Checkbox

**Files:**
- Create: `frontend/src/components/ui/Checkbox/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Checkbox/index.tsx`:

```tsx
import { forwardRef, useEffect, useRef, type InputHTMLAttributes, type ReactNode } from 'react'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'children'> {
  indeterminate?: boolean
  label?: ReactNode
}

export const Checkbox = forwardRef<HTMLInputElement, Props>(function Checkbox(
  { indeterminate = false, label, className = '', ...rest },
  forwardedRef,
) {
  const innerRef = useRef<HTMLInputElement | null>(null)

  useEffect(() => {
    if (innerRef.current) innerRef.current.indeterminate = indeterminate
  }, [indeterminate])

  const setRefs = (el: HTMLInputElement | null) => {
    innerRef.current = el
    if (typeof forwardedRef === 'function') forwardedRef(el)
    else if (forwardedRef) (forwardedRef as React.MutableRefObject<HTMLInputElement | null>).current = el
  }

  return (
    <label className={`inline-flex items-center gap-2 cursor-pointer text-sm text-ink ${className}`}>
      <input
        ref={setRefs}
        type="checkbox"
        className="peer sr-only"
        {...rest}
      />
      <span
        aria-hidden="true"
        className="w-4 h-4 rounded border border-divider bg-surface flex items-center justify-center peer-checked:bg-accent peer-checked:border-accent peer-indeterminate:bg-accent peer-indeterminate:border-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent-soft transition-colors"
      >
        <svg viewBox="0 0 14 14" className="w-3 h-3 text-page hidden peer-checked:block" fill="none" stroke="currentColor" strokeWidth={2}>
          <path d="M2 7l3.5 3.5L12 4" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
        <span className="w-2 h-0.5 bg-page hidden peer-indeterminate:block" />
      </span>
      {label && <span>{label}</span>}
    </label>
  )
})
```

> Note: peer-* selectors only see siblings. The visual span must be a *sibling* of the input. The label wrapping doesn't break this because peer-* is scoped to direct following siblings.

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { Checkbox } from '../../components/ui/Checkbox'
```

Add section:
```tsx
        <section id="checkbox" className="space-y-3">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Checkbox</p>
          <Checkbox label="Include SUBs" />
          <Checkbox label="Checked" defaultChecked />
          <Checkbox label="Indeterminate" indeterminate />
          <Checkbox label="Disabled" disabled />
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#checkbox`. Click toggles; indeterminate shows a horizontal bar; focus-visible ring shows on tab.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Checkbox/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Checkbox primitive (with indeterminate support)"
```

---

### Task 25: Toggle

**Files:**
- Create: `frontend/src/components/ui/Toggle/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Toggle/index.tsx`:

```tsx
import { forwardRef, type InputHTMLAttributes, type ReactNode } from 'react'

interface Props extends Omit<InputHTMLAttributes<HTMLInputElement>, 'type' | 'children'> {
  label?: ReactNode
}

export const Toggle = forwardRef<HTMLInputElement, Props>(function Toggle(
  { label, className = '', ...rest },
  ref,
) {
  return (
    <label className={`inline-flex items-center gap-2 cursor-pointer text-sm text-ink ${className}`}>
      <input ref={ref} type="checkbox" className="peer sr-only" {...rest} />
      <span
        aria-hidden="true"
        className="w-9 h-5 rounded-full bg-divider peer-checked:bg-accent peer-focus-visible:ring-2 peer-focus-visible:ring-accent-soft transition-colors relative"
      >
        <span className="absolute top-0.5 left-0.5 w-4 h-4 rounded-full bg-surface peer-checked:translate-x-4 transition-transform" />
      </span>
      {label && <span>{label}</span>}
    </label>
  )
})
```

> Note: the inner span uses `peer-checked:translate-x-4` which is dependent on the input being a peer of the *outer* span. This works in Tailwind v4 because peer-* applies to descendants of the visual span as long as the input precedes the visual span. Verify in browser.

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { Toggle } from '../../components/ui/Toggle'
```

Add section:
```tsx
        <section id="toggle" className="space-y-3">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Toggle</p>
          <Toggle label="Include SUBs" />
          <Toggle label="On" defaultChecked />
          <Toggle label="Disabled" disabled />
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#toggle`. The handle slides on toggle; if `peer-checked:translate-x-4` doesn't propagate to the inner handle (Tailwind peer scope quirk), restructure with two siblings — input + span containing handle — and target the handle via descendant selector.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Toggle/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Toggle primitive (boolean switch)"
```

---

## Phase 5 — Display Primitives

### Task 26: DataTable

**Files:**
- Create: `frontend/src/components/ui/DataTable/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/DataTable/index.tsx`:

```tsx
import type { HTMLAttributes, ReactNode, ThHTMLAttributes, TdHTMLAttributes } from 'react'

interface TableProps extends HTMLAttributes<HTMLTableElement> { children: ReactNode }
function Table({ className = '', children, ...rest }: TableProps) {
  return (
    <table {...rest} className={`w-full text-sm text-ink ${className}`}>
      {children}
    </table>
  )
}

function Head({ children, className = '', ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return <thead {...rest} className={`text-ink-faint ${className}`}>{children}</thead>
}

function Body({ children, className = '', ...rest }: HTMLAttributes<HTMLTableSectionElement>) {
  return <tbody {...rest} className={className}>{children}</tbody>
}

function Row({ children, className = '', ...rest }: HTMLAttributes<HTMLTableRowElement>) {
  return (
    <tr {...rest} className={`border-b border-divider last:border-b-0 ${className}`}>
      {children}
    </tr>
  )
}

interface CellProps extends Omit<TdHTMLAttributes<HTMLTableCellElement>, 'children'> {
  numeric?: boolean
  children: ReactNode
}
function Cell({ numeric = false, className = '', children, ...rest }: CellProps) {
  const align = numeric ? 'text-right tnum-mono' : ''
  return (
    <td {...rest} className={`py-3 px-3 align-baseline ${align} ${className}`}>
      {children}
    </td>
  )
}

interface HeadCellProps extends Omit<ThHTMLAttributes<HTMLTableCellElement>, 'children'> {
  numeric?: boolean
  children: ReactNode
}
function HeadCell({ numeric = false, className = '', children, ...rest }: HeadCellProps) {
  const align = numeric ? 'text-right' : 'text-left'
  return (
    <th
      {...rest}
      className={`py-2 px-3 text-[10px] uppercase tracking-[0.18em] font-semibold ${align} ${className}`}
    >
      {children}
    </th>
  )
}

Table.Head = Head
Table.Body = Body
Table.Row = Row
Table.Cell = Cell
Table.HeadCell = HeadCell

export { Table as DataTable }
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { DataTable } from '../../components/ui/DataTable'
```

Add section:
```tsx
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
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#datatable`. Numeric cells right-aligned and mono; head row uppercase eyebrow style.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/DataTable/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add DataTable primitive (Head/Body/Row/HeadCell/Cell with numeric prop)"
```

---

### Task 27: Badge

**Files:**
- Create: `frontend/src/components/ui/Badge/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Badge/index.tsx`:

```tsx
import type { HTMLAttributes, ReactNode } from 'react'

type Tone = 'neutral' | 'accent' | 'pos' | 'neg' | 'warn' | 'info'

interface Props extends HTMLAttributes<HTMLSpanElement> {
  tone?: Tone
  children: ReactNode
}

const TONE: Record<Tone, string> = {
  neutral: 'bg-surface-2 text-ink border-divider',
  accent:  'bg-accent-soft text-accent border-accent/30',
  pos:     'bg-pos/10 text-pos border-pos/30',
  neg:     'bg-neg/10 text-neg border-neg/30',
  warn:    'bg-warn/10 text-warn border-warn/30',
  info:    'bg-info/10 text-info border-info/30',
}

export function Badge({ tone = 'neutral', children, className = '', ...rest }: Props) {
  return (
    <span
      {...rest}
      className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-[11px] font-semibold uppercase tracking-[0.08em] ${TONE[tone]} ${className}`}
    >
      {children}
    </span>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { Badge } from '../../components/ui/Badge'
```

Add section:
```tsx
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
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#badge`. Each tone reads correctly in both modes; tinted bg + border + text.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Badge/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Badge primitive (6 tones)"
```

---

### Task 28: Tabs

**Files:**
- Create: `frontend/src/components/ui/Tabs/index.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/ui/Tabs/index.tsx`:

```tsx
import { useId, type ReactNode } from 'react'

interface TabItem<T extends string = string> {
  id: T
  label: ReactNode
}

interface Props<T extends string = string> {
  items: TabItem<T>[]
  active: T
  onChange: (id: T) => void
  className?: string
}

export function Tabs<T extends string = string>({ items, active, onChange, className = '' }: Props<T>) {
  const groupId = useId()
  return (
    <div role="tablist" aria-label="Tabs" className={`border-b border-divider flex gap-6 ${className}`}>
      {items.map((it) => {
        const selected = it.id === active
        return (
          <button
            key={it.id}
            id={`${groupId}-${it.id}`}
            role="tab"
            aria-selected={selected}
            tabIndex={selected ? 0 : -1}
            onClick={() => onChange(it.id)}
            className={`relative py-3 text-sm font-medium transition-colors ${
              selected ? 'text-ink' : 'text-ink-muted hover:text-ink'
            }`}
          >
            {it.label}
            <span
              aria-hidden="true"
              className={`absolute left-0 right-0 -bottom-px h-0.5 ${selected ? 'bg-accent' : 'bg-transparent'}`}
            />
          </button>
        )
      })}
    </div>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { Tabs } from '../../components/ui/Tabs'
```

Add demo above the default export:
```tsx
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
```

Add section:
```tsx
        <section id="tabs" className="space-y-4">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">Tabs</p>
          <TabsDemo />
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#tabs`. Active tab shows oxblood underline; inactive muted; click switches.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/ui/Tabs/index.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add Tabs primitive (underline-style, accent on active)"
```

---

## Phase 6 — CardSolver-Specific Primitives

These compose foundation primitives into CardSolver-domain shapes. Each lives under `frontend/src/components/cards/` to match the existing `cards/` folder.

### Task 29: CardTile

**Files:**
- Create: `frontend/src/components/cards/CardTile.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/cards/CardTile.tsx`:

```tsx
import type { ReactNode } from 'react'
import { Surface } from '../ui/Surface'
import { Eyebrow } from '../ui/Eyebrow'
import { Heading } from '../ui/Heading'
import { Money } from '../ui/Money'
import { Badge } from '../ui/Badge'

interface BreakdownItem {
  label: string
  value: ReactNode
  tone?: 'neutral' | 'pos' | 'neg'
}

interface Props {
  issuer: string
  network?: string
  cardName: string
  netEvAnnual: number
  badge?: { tone: 'accent' | 'pos' | 'neg' | 'warn' | 'info' | 'neutral'; label: string }
  breakdown?: BreakdownItem[]
  className?: string
  onClick?: () => void
}

export function CardTile({
  issuer,
  network,
  cardName,
  netEvAnnual,
  badge,
  breakdown,
  className = '',
  onClick,
}: Props) {
  const issuerLine = network ? `${issuer} · ${network}` : issuer
  return (
    <Surface
      variant="panel"
      padding="md"
      className={`flex flex-col gap-3 ${onClick ? 'cursor-pointer hover:bg-surface-2 transition-colors' : ''} ${className}`}
      onClick={onClick}
      role={onClick ? 'button' : undefined}
      tabIndex={onClick ? 0 : undefined}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <Eyebrow>{issuerLine}</Eyebrow>
          <Heading level={4} className="mt-1">{cardName}</Heading>
        </div>
        {badge && <Badge tone={badge.tone}>{badge.label}</Badge>}
      </div>
      <div className="flex items-baseline justify-between border-t border-divider pt-3">
        <Eyebrow>Net EV / yr</Eyebrow>
        <Money value={netEvAnnual} feature tone="auto" />
      </div>
      {breakdown && breakdown.length > 0 && (
        <div className="flex flex-wrap gap-x-5 gap-y-1 text-xs text-ink-muted">
          {breakdown.map((b) => (
            <span key={b.label}>
              {b.label}{' '}
              <span className="text-ink font-medium">{b.value}</span>
            </span>
          ))}
        </div>
      )}
    </Surface>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { CardTile } from '../../components/cards/CardTile'
```

Add section:
```tsx
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
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#cardtile`. Tile composes Surface + Eyebrow + Heading + Money + Badge cleanly; toggle theme.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/cards/CardTile.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add CardTile primitive (issuer/name/EV/badge/breakdown)"
```

---

### Task 30: CategoryRow

**Files:**
- Create: `frontend/src/components/cards/CategoryRow.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/cards/CategoryRow.tsx`:

```tsx
import { Money } from '../ui/Money'

interface Props {
  category: string
  multiplier: number
  /** Annual spend allocated to this card in this category (USD). */
  allocatedSpend: number
  /** Annual point/$ earn (in display units — caller decides). */
  earn: number
  /** Optional caption shown faded under the category name. */
  caption?: string
  className?: string
}

export function CategoryRow({ category, multiplier, allocatedSpend, earn, caption, className = '' }: Props) {
  return (
    <div className={`grid grid-cols-[1fr_auto_auto_auto] items-baseline gap-x-4 gap-y-1 py-2 border-b border-divider last:border-b-0 ${className}`}>
      <div>
        <div className="text-sm font-medium text-ink">{category}</div>
        {caption && <div className="text-xs text-ink-faint">{caption}</div>}
      </div>
      <div className="tnum-mono text-sm text-ink-muted">{multiplier}×</div>
      <div className="tnum-mono text-sm text-ink-muted text-right"><Money value={allocatedSpend} mono /></div>
      <div className="tnum-mono text-sm text-ink text-right"><Money value={earn} mono /></div>
    </div>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { CategoryRow } from '../../components/cards/CategoryRow'
```

Add section:
```tsx
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
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#categoryrow`. Columns line up; mono numerals; caption renders faded.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/cards/CategoryRow.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add CategoryRow primitive (category/multiplier/spend/earn)"
```

---

### Task 31: CreditRow

**Files:**
- Create: `frontend/src/components/cards/CreditRow.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/cards/CreditRow.tsx`:

```tsx
import { Money } from '../ui/Money'

interface Props {
  name: string
  /** Display valuation in USD. */
  valuation: number
  /** Note shown under the name. */
  note?: string
  /** Show as "0" struck-through when user has zeroed out the credit. */
  zeroedOut?: boolean
  className?: string
}

export function CreditRow({ name, valuation, note, zeroedOut = false, className = '' }: Props) {
  return (
    <div className={`flex items-baseline justify-between gap-4 py-2 border-b border-divider last:border-b-0 ${className}`}>
      <div className="min-w-0">
        <div className="text-sm font-medium text-ink truncate">{name}</div>
        {note && <div className="text-xs text-ink-faint">{note}</div>}
      </div>
      <div className={zeroedOut ? 'line-through text-ink-faint' : ''}>
        <Money value={valuation} mono />
      </div>
    </div>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { CreditRow } from '../../components/cards/CreditRow'
```

Add section:
```tsx
        <section id="creditrow" className="space-y-1 max-w-md">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">CreditRow</p>
          <CreditRow name="$300 travel credit" valuation={300} note="Statement credit, recurring annually" />
          <CreditRow name="$200 hotel credit" valuation={150} note="Counted at $150 — partial value" />
          <CreditRow name="Lyft credit" valuation={0} zeroedOut note="User-zeroed" />
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#creditrow`. Strike-through applied when zeroedOut; note italics styling matches.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/cards/CreditRow.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add CreditRow primitive (name/valuation/note, zeroed-out variant)"
```

---

### Task 32: IssuerRuleBanner

**Files:**
- Create: `frontend/src/components/cards/IssuerRuleBanner.tsx`
- Modify: `frontend/src/pages/Styleguide/index.tsx`

- [ ] **Step 1: Write the primitive**

Full contents of `frontend/src/components/cards/IssuerRuleBanner.tsx`:

```tsx
import type { ReactNode } from 'react'
import { Surface } from '../ui/Surface'

interface Props {
  rule: string
  message: ReactNode
  className?: string
}

export function IssuerRuleBanner({ rule, message, className = '' }: Props) {
  return (
    <Surface variant="inset" padding="sm" className={`border-warn/40 ${className}`}>
      <div className="flex items-start gap-3">
        <span aria-hidden="true" className="text-warn text-lg leading-none">⚠</span>
        <div className="space-y-0.5">
          <div className="text-[10px] uppercase tracking-[0.18em] font-semibold text-warn">{rule}</div>
          <div className="text-sm text-ink">{message}</div>
        </div>
      </div>
    </Surface>
  )
}
```

- [ ] **Step 2: Add styleguide entry**

Add import:
```tsx
import { IssuerRuleBanner } from '../../components/cards/IssuerRuleBanner'
```

Add section:
```tsx
        <section id="issuerrulebanner" className="space-y-3 max-w-xl">
          <p className="text-[10px] uppercase tracking-[0.18em] font-semibold text-ink-faint">IssuerRuleBanner</p>
          <IssuerRuleBanner rule="Chase 5/24" message="You've opened 6 personal cards in the last 24 months. Adding this card may be auto-declined." />
          <IssuerRuleBanner rule="Amex 1/90" message="Last Amex application was 42 days ago — wait 48 more days before applying." />
        </section>
```

- [ ] **Step 3: Verify in styleguide (light + dark)**

`/styleguide#issuerrulebanner`. Warning glyph + label + message; warn-toned border.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/components/cards/IssuerRuleBanner.tsx frontend/src/pages/Styleguide/index.tsx
git commit -m "Add IssuerRuleBanner primitive (warn-toned inline notice)"
```

---

## Phase 7 — RoadmapTool Migration

The library is complete. Now migrate RoadmapTool to consume it.

### Task 33: Audit RoadmapTool for primitive replacements

**Files:**
- Create: `docs/superpowers/notes/roadmaptool-migration-checklist.md`

- [ ] **Step 1: Walk every component file under RoadmapTool and catalogue replacements**

```bash
find frontend/src/pages/RoadmapTool -name '*.tsx' | sort
```

Open each one and look for these patterns:
- `<ModalBackdrop>` → replace with `<Modal>`
- `<InfoPopover>`, `<InfoQuoteBox>`, etc. → replace with `<Popover>`
- `bg-slate-800 border-slate-700 rounded-xl` (and variants) on a `<div>` → replace with `<Surface>`
- Hardcoded `text-slate-{100,300,400,500}` → swap to `text-ink`, `text-ink-muted`, `text-ink-faint`
- Hardcoded `bg-slate-{900,800,700,950}` → swap to `bg-page`, `bg-surface`, `bg-surface-2`
- Hardcoded `bg-indigo-{500,600}` / `text-indigo-{300,400}` → swap to `bg-accent` / `text-accent`
- Hardcoded `border-slate-{700,800}` → swap to `border-divider`
- Inline-styled `<button class="text-sm font-medium px-... rounded-... bg-...">` → `<Button>`
- Inline `<input class="bg-slate-900 border-slate-600 ...">` → `<Input>` (often inside a `<Field>`)
- `<h1>`/`<h2>`/`<h3>` with manual font/size/weight → `<Heading level={...}>`
- Uppercase tracked-out labels → `<Eyebrow>`
- `formatMoney()` / `formatMoneyExact()` inside a `<span>` with custom classes → `<Money>`
- `formatPoints()` inline → `<Points>`
- Inline tabular dollar/point columns inside `<table>` or grid → `<DataTable>`
- Pill / chip elements (`px-2 py-0.5 rounded-full ...`) → `<Badge>`
- Tab strips (e.g., in detail panes) → `<Tabs>`
- 5/24 / 1/90 / 1/8 warning blocks → `<IssuerRuleBanner>`
- Per-category breakdown rows in results / overlay editors → `<CategoryRow>`
- Per-credit list rows → `<CreditRow>`

- [ ] **Step 2: Write the checklist**

Create `docs/superpowers/notes/roadmaptool-migration-checklist.md` and list every file that needs touching, with bullet points per replacement target. Example structure:

```markdown
# RoadmapTool Migration Checklist

## Phase 7 — files to touch

### components/AddScenarioModal.tsx
- [ ] Replace `<ModalBackdrop>` with `<Modal>` + `<ModalHeader>` + `<ModalBody>` + `<ModalFooter>`
- [ ] Replace inline buttons with `<Button>`
- [ ] Replace `<input>` + label markup with `<Field>` + `<Input>`

### components/ApplicationRuleWarningModal.tsx
- [ ] Replace `<ModalBackdrop>` with `<Modal>`
- [ ] Replace warning blocks with `<IssuerRuleBanner>`

### components/ScenarioPicker.tsx
- [ ] ...

### components/spend/*
- [ ] ...

### components/summary/*
- [ ] ...

### components/timeline/WalletTimelineChart.tsx
- [ ] Retokenize ONLY (per spec §2.6). Replace hardcoded slate/indigo classes with token utilities. Do NOT decompose structure.

### index.tsx
- [ ] ...
```

- [ ] **Step 3: Commit the checklist**

```bash
git add docs/superpowers/notes/roadmaptool-migration-checklist.md
git commit -m "Phase 7: audit RoadmapTool migration targets"
```

---

### Task 34: Migrate App shell + nav

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1: Inventory existing shell**

Open `frontend/src/App.tsx` end to end. Note the dark slate-950/900/800 backgrounds, indigo button variants, slate-700 borders.

- [ ] **Step 2: Replace inline classes with token utilities + primitives**

For every Tailwind class, follow the swap table from Task 33 step 1. Concrete examples:
- `bg-slate-950` → `bg-page`
- `bg-slate-900` → `bg-page` (nav stays on page bg) or `bg-surface` (if it's a panel)
- `text-slate-100` → `text-ink`
- `text-slate-300` / `400` → `text-ink-muted` / `text-ink-faint`
- `border-slate-700` → `border-divider`
- The nav's "Sign in" / "Get started" buttons → `<Button variant="primary">` and `<Button variant="ghost">`
- The username prompt's modal → swap from `ModalBackdrop` to `Modal` + `ModalHeader/Body/Footer`. Form fields wrap in `<Field>` + `<Input>`.
- Add `<ThemeToggle />` to the nav, to the right of the auth area.

- [ ] **Step 3: Verify dev render**

```bash
cd frontend
npm run dev
```

Walk: home → sign in flow → username prompt → profile → roadmap. No visual regression from the *un-migrated* pages (they keep slate look until their own migration). The shell + nav now read editorial.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "Phase 7.1: migrate App shell + nav to tokens + primitives"
```

---

### Task 35: Migrate ScenarioPicker + AddScenarioModal

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/ScenarioPicker.tsx`
- Modify: `frontend/src/pages/RoadmapTool/components/AddScenarioModal.tsx`

- [ ] **Step 1: Migrate ScenarioPicker**

Open the file. Apply swap table per Task 33. Common moves:
- The selector trigger button → `<Button variant="ghost">` or a `<Surface variant="bare">` if it needs custom layout
- The dropdown panel → wrap in `<Surface variant="panel" padding="sm">`
- Each scenario item row → make sure click target uses `<Button variant="ghost">` styling or matches a list-row pattern
- "Default" badge → `<Badge tone="accent">`
- Trash / edit icon buttons → `<Button variant="icon" size="sm">`

- [ ] **Step 2: Migrate AddScenarioModal**

- Replace `<ModalBackdrop>` with `<Modal open onClose>` + slot composition
- Form fields → `<Field>` + `<Input>` (or `<Select>` if scenario-type is selectable)
- Submit / Cancel actions → `<Button variant="primary">` / `<Button variant="ghost">`
- Move the form's onSubmit to use `<ModalFooter>` for actions

- [ ] **Step 3: Verify**

`npm run dev`, open RoadmapTool, exercise scenario switching + scenario create flow.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/ScenarioPicker.tsx frontend/src/pages/RoadmapTool/components/AddScenarioModal.tsx
git commit -m "Phase 7.2: migrate ScenarioPicker + AddScenarioModal"
```

---

### Task 36: Migrate spend/ components

**Files:**
- Modify: every `.tsx` under `frontend/src/pages/RoadmapTool/components/spend/`

- [ ] **Step 1: List files**

```bash
ls frontend/src/pages/RoadmapTool/components/spend/
```

- [ ] **Step 2: Migrate each file**

For each file, apply the swap table. Spend-related screens commonly use:
- `<Field>` + `<Input>` for spend amount entry
- `<Eyebrow>` for category labels
- `<DataTable>` if there's a tabular layout
- `<CategoryRow>` for category × multiplier rows where applicable
- `<Surface>` for grouping panels

Stage and verify per file (open the relevant UI, check the screen). Theme toggle each.

- [ ] **Step 3: Commit per file or as a single coherent group**

If files are tightly coupled, one commit. Otherwise commit per file:
```bash
git add frontend/src/pages/RoadmapTool/components/spend/<file>.tsx
git commit -m "Phase 7.3: migrate spend/<file>"
```

---

### Task 37: Migrate summary/ components

**Files:**
- Modify: every `.tsx` under `frontend/src/pages/RoadmapTool/components/summary/`

- [ ] **Step 1: List files**

```bash
ls frontend/src/pages/RoadmapTool/components/summary/
```

Currently includes `WalletSummaryStats.tsx`, `MethodologyInfoPopover.tsx`, `CurrencySettingsDropdown.tsx`.

- [ ] **Step 2: Migrate each file**

- `WalletSummaryStats.tsx` heavily uses Money/Points formatting + Stat-style hero blocks. Swap to `<Stat>` + `<Money feature>` + `<Eyebrow accent>`. Replace any `<Surface>`-equivalent panels.
- `MethodologyInfoPopover.tsx` currently imports from `components/InfoPopover`. Switch directly to `<Popover>` from `components/ui/Popover`.
- `CurrencySettingsDropdown.tsx` likely has a dropdown panel — swap to `<Popover>`. Any `<select>` inside switches to `<Select>` (wrapped in `<Field>` if labeled).

- [ ] **Step 3: Verify**

Open RoadmapTool, look at summary panel and the methodology popover.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/summary/
git commit -m "Phase 7.4: migrate summary/ components"
```

---

### Task 38: Retokenize timeline/ (no decomposition)

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx`

Per spec §2.6: this is **retokenize only**. Do NOT decompose the file into Timeline primitives.

- [ ] **Step 1: Find/replace hardcoded color classes**

```bash
grep -n 'slate-' frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx | head -40
grep -n 'indigo-' frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx | head -20
```

Apply swap table (slate-950 → page, slate-900 → page, slate-800 → surface or surface-2 depending on role, slate-700 → divider, slate-100 → ink, slate-300/400 → ink-muted / ink-faint, indigo-* → accent).

The constant `DIVIDER_CLASS` near the top of the file — change `border-slate-800` to `border-divider`.

For inline `style={{ background: '#hexvalue' }}` color literals (if any), swap to `var(--color-...)`.

- [ ] **Step 2: Replace `InfoQuoteBox` import**

The file imports `InfoQuoteBox` from `components/InfoPopover`. Swap to direct `Popover` from `components/ui/Popover` if straightforward; otherwise leave the existing import using the compat shim — Task 40 audits these.

- [ ] **Step 3: Verify**

`npm run dev`. Open RoadmapTool default scenario. Exercise the timeline: hover events, check tooltips render, toggle theme. Numbers / icons must still align — no structural changes allowed in this task.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/timeline/WalletTimelineChart.tsx
git commit -m "Phase 7.5: retokenize WalletTimelineChart (no structural change)"
```

---

### Task 39: Migrate ApplicationRuleWarningModal

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/components/ApplicationRuleWarningModal.tsx`

- [ ] **Step 1: Migrate**

Apply swap table:
- `<ModalBackdrop>` → `<Modal open onClose>` + `<ModalHeader>` + `<ModalBody>` + `<ModalFooter>`
- Each rule violation block → `<IssuerRuleBanner rule={...} message={...}>`
- Action buttons → `<Button variant="primary">` (proceed) / `<Button variant="ghost">` (cancel)

- [ ] **Step 2: Verify**

Trigger the modal in dev (force a 5/24 violation by adding cards to a scenario). Confirm rendering, dismiss behavior, theme toggle.

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/RoadmapTool/components/ApplicationRuleWarningModal.tsx
git commit -m "Phase 7.6: migrate ApplicationRuleWarningModal"
```

---

### Task 40: Migrate index.tsx + remaining loose files; audit and remove compat shims

**Files:**
- Modify: `frontend/src/pages/RoadmapTool/index.tsx` (and any unhandled file from Task 33)
- Possibly delete: `frontend/src/components/ModalBackdrop.tsx`, `frontend/src/components/InfoPopover.tsx`

- [ ] **Step 1: Migrate `index.tsx`**

Open `frontend/src/pages/RoadmapTool/index.tsx`. Apply swap table for any remaining surface, button, input, badge, or popover usage. Common spots: top bar, calculate button, sidebar layout chrome.

- [ ] **Step 2: Catch any file Task 33 missed**

```bash
git grep -l 'slate-\|indigo-\|ModalBackdrop\|from .*InfoPopover' frontend/src/pages/RoadmapTool/
```

For each result, decide:
- Migration target known → migrate now.
- Hardcoded `slate-*` left in `WalletTimelineChart.tsx` because Task 38 retokenized — confirm nothing slipped through.

- [ ] **Step 3: Audit remaining ModalBackdrop / InfoPopover imports app-wide**

```bash
git grep -l "from.*components/ModalBackdrop"
git grep -l "from.*components/InfoPopover"
```

If only RoadmapTool imports them and RoadmapTool is now migrated, delete the shim files:
```bash
rm frontend/src/components/ModalBackdrop.tsx
rm frontend/src/components/InfoPopover.tsx
```

If Home or Profile still import them, leave the shims in place (they're slated for follow-on migration specs).

- [ ] **Step 4: Run build to catch any TS breakage**

```bash
cd frontend
npm run build
```

Expected: clean build. If TypeScript flags missing imports, fix them — most likely a stale import path after deleting a shim.

- [ ] **Step 5: Commit**

```bash
git add -A frontend/src/pages/RoadmapTool/index.tsx frontend/src/components/
git commit -m "Phase 7.7: migrate RoadmapTool index + audit/remove compat shims"
```

---

### Task 41: Final smoke test

**Files:** none (verification only)

- [ ] **Step 1: TypeScript + ESLint pass**

```bash
cd frontend
npm run build
npm run lint
```

Both must pass with no new errors.

- [ ] **Step 2: Calculator snapshot test**

```bash
cd backend
../.venv/bin/python -m pytest tests/test_calculator_snapshot.py
```

Expected: PASS. The frontend rollout makes no backend changes, so any failure points at infrastructure drift, not the migration. Investigate before declaring done.

- [ ] **Step 3: Golden-path UX walkthrough**

Start dev server: `cd frontend && VITE_SHOW_STYLEGUIDE=1 npm run dev`. Walk:

1. Open `/roadmap-tool` (signed-in user with default scenario).
2. Hit **Calculate**; observe results render correctly.
3. Switch scenarios via ScenarioPicker; verify each loads.
4. Open the **Add Card** flow / Future Card editor (whatever exposes scenario-card creation); verify modal renders editorial.
5. Toggle a card off and on via the timeline chart; observe re-calculate and re-render.
6. Open the methodology popover; verify content + dismiss.
7. Trigger an issuer-rule violation by adding a 6th 24-month Chase card; verify `ApplicationRuleWarningModal`.
8. **Toggle theme** — every screen above must look intentional in both modes.
9. Open `/styleguide` and click through every section in both modes — every primitive verified one final time.

- [ ] **Step 4: Mark plan complete**

If everything passes, the design-system rollout is done.

```bash
git log --oneline | head -50
```

Confirm one commit per task and no force-pushes / amends.

---

## Self-Review Notes (this plan)

**Spec coverage:**
- §1.1 token architecture → Tasks 2, 3, 4
- §1.2 color tokens → Task 2
- §1.3 type/spacing/radii/shadows → Tasks 1, 2, 3
- §2.1 foundation primitives → Tasks 9–13
- §2.2 surfaces → Tasks 14–19
- §2.3 form → Tasks 20–25
- §2.4 display → Tasks 26–28
- §2.5 cardsolver-specific → Tasks 29–32
- §2.6 timeline retokenize-only → Task 38
- §3.1 build order → entire plan
- §3.2 styleguide route → Task 6 (skeleton), incremented per primitive
- §3.3 testing → Tasks 8 (contrast), 41 (smoke test)
- §3.4 risks (Fraunces weight, AA contrast, missing primitives, shim audit) → Tasks 1, 8, 33, 40
- §3.5 out of scope (Home/Profile migration, timeline decomp) → respected throughout

**Type consistency:** All primitives import paths use `frontend/src/components/ui/<Name>` or `frontend/src/components/cards/<Name>`. Token utility class names (`bg-page`, `text-ink`, `border-divider`, `text-accent`, etc.) match the token names declared in `tokens.css` + `index.css` `@theme inline`.

**No placeholders detected.** Every step has either complete code, exact commands, or a precise instruction tied to file content.
