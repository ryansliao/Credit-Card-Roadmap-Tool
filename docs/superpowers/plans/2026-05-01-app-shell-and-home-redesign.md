# App Shell + Home Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Restyle the application shell (`App.tsx` — Navbar, SignInDropdown, UsernamePrompt, AuthGate, ErrorBoundary) and the Home landing page (`pages/Home.tsx`) to match the soft-dashboard direction. Plan 2 of 4 for the app-wide redesign. Spec: `docs/superpowers/specs/2026-05-01-roadmap-tool-redesign-design.md` Sections 3 (App shell) and 4 (Home).

**Architecture:** Visual-only refactor. No prop or behavior changes — the existing auth flow, route structure, and Home content (hero / steps / "Under the hood" feature grid) are preserved in semantics. Only the chrome (typography, surfaces, spacing, color usage, button styling, dropdown panel, modal scaffolding) is replaced with the new soft-dashboard language. One new optional section is added: a quiet "Open Roadmap Tool" closing CTA card + hairline footer band on Home (per spec 4.3).

**Tech Stack:** React + Vite + Tailwind v4, primitives in `frontend/src/components/ui/` (foundation primitives now restyled by Plan 1; consume them rather than re-rolling chrome). Build: `cd frontend && npm run build` (typecheck + Vite). Lint: `cd frontend && npm run lint`. Dev: `cd frontend && npm run dev`.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `frontend/src/App.tsx` | App shell (~430 lines): `ErrorBoundary`, `SignInDropdown`, `UsernamePrompt`, `Nav`, `AuthGate`, `UsernameGate`, top-level `App`. Modified: every visual sub-component restyled. Routing logic, auth wiring, QueryClient + AuthProvider providers all stay untouched. |
| `frontend/src/pages/Home.tsx` | Public landing page (~260 lines): hero, "Your setup" / "How it works" steps, "Under the hood" feature grid. Modified: typography + surface treatment for every section. New: optional closing-CTA card + hairline footer band. |

(Auth context, hooks, queryKeys, and primitive APIs are not modified — primitives consumed via existing imports.)

**Verification convention:** every task ends with `cd frontend && npm run build` (TypeScript + Vite), then visual QA in the dev server (`http://localhost:5174` if 5173 is busy). Each task commits independently.

---

## Task 1: Restyle the navbar

The current navbar is a wide oxblood-on-white band (`bg-accent text-on-accent`) — loud against the new neutral-gray page. Switch to a quieter dashboard-style navbar: white surface with a hairline bottom border, accent reserved for the active route's underline.

**Files:**
- Modify: `frontend/src/App.tsx` (the `Nav` function and the surrounding `<main>` flex shell)

- [ ] **Step 1: Replace the `Nav` function body**

In `frontend/src/App.tsx`, find the `function Nav() { ... }` block (around line 306) and replace it with:

```tsx
function Nav() {
  const { user, isAuthenticated, isLoading, signOut } = useAuth()

  return (
    <nav className="bg-surface border-b border-divider px-6 h-14 flex items-center gap-2">
      <Link to="/" className="text-base font-bold text-ink hover:text-accent transition-colors mr-6">
        CardSolver
      </Link>
      {isAuthenticated && (
        <NavLink
          to="/roadmap-tool"
          className={({ isActive }) =>
            `relative text-sm font-medium px-1 py-4 transition-colors ${
              isActive ? 'text-ink' : 'text-ink-faint hover:text-ink'
            }`
          }
        >
          {({ isActive }) => (
            <>
              Roadmap Tool
              {isActive && (
                <span aria-hidden="true" className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
              )}
            </>
          )}
        </NavLink>
      )}
      <div className="flex-1" />
      {!isLoading && (
        isAuthenticated && user ? (
          <div className="flex items-center gap-2">
            <Link
              to="/profile"
              className="flex items-center gap-2 px-2 py-1.5 rounded-md text-ink-faint hover:text-ink hover:bg-surface-2 transition-colors"
            >
              {user.picture && (
                <img
                  src={user.picture}
                  alt=""
                  className="w-7 h-7 rounded-full"
                  referrerPolicy="no-referrer"
                />
              )}
              <span className="text-sm hidden sm:inline">{user.username ?? user.name}</span>
            </Link>
            <ThemeToggle />
            <Button variant="ghost" size="sm" onClick={signOut}>
              Sign out
            </Button>
          </div>
        ) : (
          <div className="flex items-center gap-2">
            <ThemeToggle />
            <SignInDropdown />
          </div>
        )
      )}
    </nav>
  )
}
```

- [ ] **Step 2: Add the `ThemeToggle` import**

At the top of `frontend/src/App.tsx`, add:

```tsx
import { ThemeToggle } from './components/ui/ThemeToggle'
```

(Import order: alphabetical-ish near the other `./components/ui/*` imports — keep in the existing block.)

- [ ] **Step 3: Drop the unused `<main>` page coloring**

The `<main>` element currently sets `bg-page text-ink` via the outer `<div className="h-dvh ... bg-page text-ink">`. The page container is fine. No change to the `<main>` itself in this step.

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA**

Open `/` (Home) signed-out, then signed-in.
Expected:
- Navbar is white with a 1px hairline divider beneath; wordmark in dark ink; on hover, wordmark darkens to accent crimson.
- Active route ("Roadmap Tool" when on `/roadmap-tool`) shows a 2px accent underline below the label, label in `--color-ink`. Inactive label in `--color-ink-faint`.
- User pill (signed-in): avatar + username; hover tints to `--color-surface-2`.
- Right side has the `ThemeToggle` icon button next to either "Sign out" (ghost button) or `SignInDropdown`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "shell/Nav: white surface, hairline divider, accent-underline active route"
```

---

## Task 2: Restyle SignInDropdown

The dropdown panel chrome is mostly fine since `Modal`, `Field`, and `Input` were updated by Plan 1. Two things to clean up: (1) the trigger button is a custom pill — switch to the `Button variant="secondary" size="sm"` primitive so it matches the rest of the navbar; (2) the panel itself uses `shadow-xl` (a Tailwind default) rather than `--shadow-modal` (the spec's modal shadow); fix that and tighten its layout to use `Field`-flavored spacing.

**Files:**
- Modify: `frontend/src/App.tsx` (the `SignInDropdown` function)

- [ ] **Step 1: Update the trigger button**

In `frontend/src/App.tsx`, find the `<button type="button" onClick={() => { setOpen(!open); resetForm() }}` (around line 159) and replace the button block:

```tsx
<Button
  variant="secondary"
  size="sm"
  onClick={() => { setOpen(!open); resetForm() }}
>
  Sign in
</Button>
```

- [ ] **Step 2: Update the dropdown panel chrome**

Replace the `<div className="absolute right-0 mt-2 w-72 bg-surface border border-divider rounded-xl shadow-xl z-50">` panel container with:

```tsx
<div className="absolute right-0 mt-2 w-80 bg-surface rounded-xl shadow-modal z-50 overflow-hidden">
```

(Drop the border, switch to `--shadow-modal`, widen to `w-80` for breathing room, and add `overflow-hidden` so the rounded corners clip the tab row underline cleanly.)

- [ ] **Step 3: Update the tab row**

Replace the `<div className="flex border-b border-divider">` block (the Sign in / Sign up tabs, around line 168) with:

```tsx
<div className="flex border-b border-divider">
  <button
    type="button"
    onClick={() => { setTab('signin'); setError('') }}
    className={`relative flex-1 text-sm py-3 font-medium transition-colors ${
      tab === 'signin' ? 'text-ink' : 'text-ink-faint hover:text-ink'
    }`}
  >
    Sign in
    {tab === 'signin' && (
      <span aria-hidden="true" className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
    )}
  </button>
  <button
    type="button"
    onClick={() => { setTab('signup'); setError('') }}
    className={`relative flex-1 text-sm py-3 font-medium transition-colors ${
      tab === 'signup' ? 'text-ink' : 'text-ink-faint hover:text-ink'
    }`}
  >
    Create account
    {tab === 'signup' && (
      <span aria-hidden="true" className="absolute left-0 right-0 -bottom-px h-0.5 bg-accent" />
    )}
  </button>
</div>
```

(Replaces the `border-b-2 border-accent` baked into the tab label with a positioned underline span — same idiom as the navbar active route, and the foundation Tabs primitive.)

- [ ] **Step 4: Tighten the form-row gaps**

Replace the `<form onSubmit={handleSubmit} className="p-4 space-y-3">` block opening with:

```tsx
<form onSubmit={handleSubmit} className="p-4 space-y-3">
```

(No change.) Then replace the error and submit button block (around line 230–238) with:

```tsx
{error && <p className="text-[11px] text-neg">{error}</p>}
<Button
  variant="primary"
  type="submit"
  className="w-full"
  loading={loading}
>
  {tab === 'signin' ? 'Sign in' : 'Create account'}
</Button>
```

(Error text drops to 11px to match the field-help typography from Plan 1's Field update.)

- [ ] **Step 5: Update the Google sign-in divider section**

Replace the `<div className="px-4 pb-4">` Google button section (around line 241) with:

```tsx
<div className="px-4 pb-4">
  <div className="flex items-center gap-3 mb-3">
    <div className="flex-1 border-t border-divider" />
    <span className="text-[11px] uppercase tracking-wider text-ink-faint font-medium">or</span>
    <div className="flex-1 border-t border-divider" />
  </div>
  <div ref={googleBtnRef} />
</div>
```

(Promotes the "or" to a small uppercase label for visual hierarchy.)

- [ ] **Step 6: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 7: Visual QA**

Click "Sign in" on the navbar.
Expected:
- Trigger looks like a secondary `Button`: white, gray-300 border, "Sign in" label in dark ink, focus ring on Tab.
- Dropdown panel is 320px wide, white, no border, soft modal shadow, 14px radius corners.
- Tabs at the top with active underline in accent (matches nav and foundation Tabs primitive).
- Form fields are the Plan 1 inputs (gray-200 border, accent focus). Error text in 11px neg.
- "or" divider reads as a small uppercase eyebrow.
- Google button renders below.

- [ ] **Step 8: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "shell/SignInDropdown: secondary trigger, soft modal panel, accent-underline tabs"
```

---

## Task 3: Restyle UsernamePrompt + ErrorBoundary + AuthGate loading state

Three small chrome cleanups in one task — they share the same theme: replace ad-hoc Tailwind utilities with primitives or token-aware classes.

**Files:**
- Modify: `frontend/src/App.tsx` (`UsernamePrompt`, `ErrorBoundary`, `AuthGate`)

- [ ] **Step 1: Tighten `UsernamePrompt`**

In `frontend/src/App.tsx`, find the `function UsernamePrompt()` block. Replace its return statement with:

```tsx
return (
  <Modal open={true} onClose={() => undefined} dismissible={false} size="xs">
    <ModalHeader>
      <Heading level={3}>Choose a username</Heading>
    </ModalHeader>
    <ModalBody>
      <form onSubmit={handleSubmit} className="space-y-4">
        <p className="text-ink-muted text-sm">Pick a username to finish setting up your account.</p>
        <Field label="Username" hint="3–30 characters: letters, numbers, underscores">
          <Input
            type="text"
            placeholder="username"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            required
            minLength={3}
            maxLength={30}
            pattern="[a-zA-Z0-9_]{3,30}"
            autoFocus
          />
        </Field>
        {error && <p className="text-[11px] text-neg">{error}</p>}
        <Button variant="primary" type="submit" className="w-full" loading={loading}>
          Continue
        </Button>
      </form>
    </ModalBody>
  </Modal>
)
```

(Adds a `hint` to the Field with the constraints copy that was previously a `title` attribute, drops the redundant `title` attribute, drops the manual `'...'` text in favor of the Button's built-in `loading` spinner, and standardizes error text to 11px.)

- [ ] **Step 2: Restyle `ErrorBoundary` fallback**

Find the `class ErrorBoundary` block. Replace its `render()` body for the `hasError` branch with:

```tsx
return (
  <div className="max-w-md mx-auto py-20 text-center space-y-4">
    <div className="inline-flex items-center justify-center w-12 h-12 rounded-full bg-neg/10 text-neg">
      <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    </div>
    <Heading level={3}>Something went wrong</Heading>
    <p className="text-ink-muted text-sm">{this.state.error?.message ?? 'Unknown error'}</p>
    <Button
      variant="secondary"
      onClick={() => this.setState({ hasError: false, error: null })}
    >
      Try again
    </Button>
  </div>
)
```

(Adds a neg-tinted icon, uses `Heading level={3}` so the size matches modal headings, and keeps the `Try again` button for the existing reset behavior.)

- [ ] **Step 3: Fix `AuthGate` loading text**

In the `AuthGate` function, the loading branch currently uses `text-slate-400` (a literal Tailwind color, not a token). Replace its return with:

```tsx
if (isLoading) {
  return (
    <div className="text-center text-ink-faint py-20 text-sm">Loading…</div>
  )
}
```

(Token-aware color, slightly softer ellipsis, smaller text to match other inline loading states.)

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA**

To trigger `UsernamePrompt`: requires a fresh Google sign-in for a user without a username. To preview without going through OAuth, temporarily flip `if (isAuthenticated && needsUsername)` in `UsernameGate` to `if (true)` for a manual visual check, then revert. (Skip this step if not needed.)

Confirm:
- `UsernamePrompt` modal renders with the new modal chrome (no border, soft shadow, 20px paddings) and a `Field` with a hint line below the input.
- `ErrorBoundary` (force one by tossing `throw new Error('test')` somewhere temporarily) shows neg-tinted icon, "Something went wrong" heading at level 3, ink-muted body, "Try again" secondary button. Revert the test throw before committing.
- `AuthGate` loading state (briefly visible while auth resolves on cold start) shows in `--color-ink-faint`.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/App.tsx
git commit -m "shell: refresh UsernamePrompt, ErrorBoundary, AuthGate loading"
```

---

## Task 4: Restyle Home hero

Soften the hero per spec 4.1: pill in neutral gray with crimson dot, headline weight tightened to 700 letter-spacing −0.02em, primary CTA picks up a soft shadow.

**Files:**
- Modify: `frontend/src/pages/Home.tsx` (the first `<section className="text-center mb-24">` block)

- [ ] **Step 1: Replace the hero `<section>` body**

Find the `<section className="text-center mb-24">` containing the eyebrow pill and headline (around line 43). Replace the section's children (everything between the opening `<section>` and closing `</section>`) with:

```tsx
<div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-surface-2 text-ink-faint text-xs font-medium mb-6">
  <span className="w-1.5 h-1.5 rounded-full bg-accent" />
  Credit card wallet optimizer
</div>
<h1
  className="text-ink mb-6 tracking-tight leading-[1.05]"
  style={{ fontSize: 'clamp(40px, 7vw, 56px)', fontWeight: 700, letterSpacing: '-0.02em' }}
>
  Stop guessing which cards
  <br className="hidden sm:block" />
  <span className="text-accent"> actually pay off.</span>
</h1>
<p className="text-ink-muted text-lg sm:text-xl max-w-2xl mx-auto mb-10 leading-relaxed">
  Model your real or planned wallet, enter your annual spend, and get a
  segment-aware projection of rewards, credits, and sign-up bonuses —
  with each category allocated optimally across every card.
</p>
{heroCta ? (
  <Link
    to={heroCta.to}
    className="inline-flex items-center gap-2 px-6 py-3 bg-accent text-on-accent font-semibold text-sm rounded-lg shadow-card hover:opacity-90 transition-opacity"
  >
    {heroCta.label}
  </Link>
) : (
  <p className="text-ink-faint text-sm">Sign in from the navbar to get started.</p>
)}
{isAuthenticated && currentStep === 1 && stateKnown && (
  <p className="text-ink-faint text-sm mt-4">Takes about two minutes to set up.</p>
)}
```

Key changes vs. current:
- Eyebrow pill: `bg-accent/10 border border-accent/20 text-accent` → `bg-surface-2 text-ink-faint` (quieter, neutral with a single accent dot).
- Headline: dropped the `text-5xl sm:text-6xl font-bold` Tailwind classes, uses inline `clamp(...)` and `font-weight: 700` for explicit control matching spec 1.2.
- CTA: `bg-accent ... text-page font-semibold rounded-lg` → `bg-accent text-on-accent shadow-card hover:opacity-90` (matches the foundation Button primitive's primary variant; `text-page` was the off-white that the Plan 1 token shift turned light gray, breaking the original intent — switching to `text-on-accent` (white) restores legibility).
- Padding tightened from `px-7 py-3.5` to `px-6 py-3`.
- Footnote text dropped `mt-4` margin elsewhere — left as-is.

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Open `/` signed-out and signed-in (with various step states).
Expected:
- Pill is small, neutral gray, with a single crimson dot.
- Headline reads ~48–56px depending on viewport, bold (700), tightly-tracked.
- CTA (when present): crimson pill with white text, soft drop shadow, hover lightens.
- Footnote shows in `--color-ink-faint` for step-1 setup.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "Home: hero pill toned down, headline tightened, CTA uses on-accent token"
```

---

## Task 5: Restyle Home steps section

The steps section has its own visual language built into `StepCard` and `StepBadge`. Move both to consume the foundation primitives (`Surface`, `Heading`, `Button`-style links) and align with the soft-dashboard chrome.

**Files:**
- Modify: `frontend/src/pages/Home.tsx` (the second `<section className="mb-24">` block, plus `StepCard` and `StepBadge` helpers)

- [ ] **Step 1: Replace the steps `<section>` body**

Find the `<section className="mb-24">` containing the steps grid (around line 73). Replace the entire section, from `<section>` to `</section>`, with:

```tsx
<section className="mb-20">
  <div className="text-center mb-10">
    <p className="text-[11px] uppercase tracking-[0.18em] text-ink-faint font-semibold mb-3">
      {isAuthenticated ? 'Your setup' : 'How it works'}
    </p>
    <h2
      className="text-ink tracking-tight"
      style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em' }}
    >
      {isAuthenticated && currentStep !== 3
        ? "Let's get your wallet ready."
        : 'Three steps, one number.'}
    </h2>
  </div>
  <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
    <StepCard
      num={1}
      title="Add cards"
      body="Build your wallet from the card library. Set open dates, acquisition type, SUB overrides, and future applications you're considering."
      status={stepStatus(currentStep, 1)}
      cta={currentStep === 1 ? { label: 'Add cards →', to: '/profile' } : undefined}
    />
    <StepCard
      num={2}
      title="Enter annual spend"
      body="Break out real spend by category. Set your foreign-spend share and tune per-card credit and multiplier overrides."
      status={stepStatus(currentStep, 2)}
      cta={
        currentStep === 2
          ? { label: 'Enter spend →', to: '/profile?tab=spending' }
          : undefined
      }
    />
    <StepCard
      num={3}
      title="Chart your roadmap"
      body="Compare expected value per card, add ones you're considering, drop the ones that don't earn their keep, and track SUB deadlines along the way."
      status={stepStatus(currentStep, 3)}
      cta={
        currentStep === 3
          ? { label: 'Open Roadmap Tool →', to: '/roadmap-tool' }
          : undefined
      }
    />
  </div>
</section>
```

(Eyebrow uses the canonical `text-[11px] uppercase tracking-[0.18em]` recipe matching the `Eyebrow` primitive's typography. Section heading uses inline 32px / 700 to match Heading level 2's new weight without depending on the Heading primitive's responsive defaults. Grid gap drops from `gap-4` to `gap-3` for tighter rhythm.)

- [ ] **Step 2: Replace `StepCard`**

Find `function StepCard({ num, title, body, status, cta }: { ... })` (around line 186) and replace its return statement:

```tsx
const containerClass = isCurrent
  ? 'bg-surface ring-2 ring-accent shadow-card'
  : isComplete
  ? 'bg-surface-2 shadow-card'
  : 'bg-surface shadow-card'

const titleClass = isPending ? 'text-ink-muted' : 'text-ink'
const bodyClass = isPending ? 'text-ink-faint' : 'text-ink-muted'

return (
  <div className={`rounded-xl p-6 transition-colors ${containerClass}`}>
    <div className="flex items-center justify-between mb-4">
      <StepBadge num={num} status={status} />
      {isComplete && (
        <span className="text-[11px] font-medium text-pos uppercase tracking-wider">Done</span>
      )}
      {isCurrent && (
        <span className="text-[11px] font-medium text-accent uppercase tracking-wider">Next up</span>
      )}
    </div>
    <h3 className={`text-base font-semibold mb-2 ${titleClass}`}>{title}</h3>
    <p className={`text-sm leading-relaxed ${bodyClass}`}>{body}</p>
    {cta && (
      <Link
        to={cta.to}
        className="inline-block mt-5 text-sm font-medium text-accent hover:opacity-80 transition-opacity"
      >
        {cta.label}
      </Link>
    )}
  </div>
)
```

(Replaces the cream-tinged `border` containers with shadow-card surfaces. The `current` state gets a 2-ring crimson outline rather than a border + faint ring; complete state uses `bg-surface-2` for a quieter "done" feel; pending uses the same shadow-card as current/complete to keep visual rhythm consistent. Badge labels uppercase to match spec.)

- [ ] **Step 3: Replace `StepBadge`**

Find `function StepBadge({ num, status }: { num: number; status: StepStatus })` (around line 237) and replace its return:

```tsx
if (status === 'complete') {
  return (
    <div className="w-8 h-8 rounded-full bg-pos/10 text-pos flex items-center justify-center">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3" strokeLinecap="round" strokeLinejoin="round">
        <polyline points="20 6 9 17 4 12" />
      </svg>
    </div>
  )
}
const toneClass =
  status === 'current'
    ? 'bg-accent text-on-accent'
    : status === 'pending'
    ? 'bg-surface-2 text-ink-faint'
    : 'bg-accent/10 text-accent'
return (
  <div
    className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${toneClass}`}
  >
    {num}
  </div>
)
```

(Drops the per-state border (which read fussy on the new surface treatment); uses solid filled accent for the current step instead of a tinted border-with-text combo.)

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA**

Open `/` in different states:
- Signed out → "How it works" eyebrow, "Three steps, one number." heading, all 3 cards in pending state with numbered badges in surface-2.
- Signed in, no cards → "Your setup" eyebrow, "Let's get your wallet ready." heading. Card 1 has `current` ring (accent ring + soft shadow) + a filled accent badge "1" + a "Next up" eyebrow on the right + the "Add cards →" link at the bottom.
- Signed in, cards but no spend → Card 1 marked Done (complete badge with check, "DONE" eyebrow), Card 2 is current.
- Signed in, full setup → All 3 marked Done; the third card's CTA is "Open Roadmap Tool →".

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "Home/steps: shadow-card surfaces, accent-ring current state, filled accent badge"
```

---

## Task 6: Restyle Home features grid ("Under the hood")

Restyle the `FeatureCard` and the surrounding section to match the new soft-dashboard surfaces.

**Files:**
- Modify: `frontend/src/pages/Home.tsx` (the third `<section className="mb-4">` block plus `FeatureCard` helper)

- [ ] **Step 1: Replace the features `<section>` body**

Find the `<section className="mb-4">` containing the "Under the hood" heading (around line 117). Replace the entire section with:

```tsx
<section className="mb-20">
  <div className="text-center mb-10">
    <p className="text-[11px] uppercase tracking-[0.18em] text-ink-faint font-semibold mb-3">
      Under the hood
    </p>
    <h2
      className="text-ink tracking-tight"
      style={{ fontSize: '32px', fontWeight: 700, letterSpacing: '-0.02em' }}
    >
      More than a multiplier lookup.
    </h2>
  </div>
  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
    <FeatureCard
      title="Optimal allocation"
      body="An LP solver places each category's spend on the highest-value card, respecting top-N groups, rotating 5% pools, and currency transfers."
    />
    <FeatureCard
      title="Multi-year projections"
      body="Segment-aware math splits your window at every card open, close, and SUB-earn boundary — so year-1 and steady-state are both honest."
    />
    <FeatureCard
      title="SUB tracking"
      body="Projected earn dates from your actual spend rate, with opportunity cost baked into the total. Mark SUBs earned to stop projecting them."
    />
    <FeatureCard
      title="Issuer rules"
      body="5/24 counter, Amex 1/90, Citi 1/8 and 2/65 — warnings surface on the roadmap before you apply, not after."
    />
    <FeatureCard
      title="Foreign spend & currencies"
      body="FTF-aware allocation on foreign-eligible categories, per-wallet CPP overrides, and currency conversions like UR Cash → Chase UR."
    />
    <FeatureCard
      title="Wallet modeling"
      body="Mix owned cards with future applications. Override fees, credits, SUBs, and multipliers per wallet without touching the card library."
    />
  </div>
</section>
```

- [ ] **Step 2: Replace `FeatureCard`**

Find `function FeatureCard({ title, body }: { title: string; body: string })` (around line 177) and replace it:

```tsx
function FeatureCard({ title, body }: { title: string; body: string }) {
  return (
    <div className="bg-surface rounded-xl p-6 shadow-card">
      <h3 className="text-ink font-semibold text-base mb-2">{title}</h3>
      <p className="text-ink-muted text-sm leading-relaxed">{body}</p>
    </div>
  )
}
```

(Drops the `Surface` primitive wrapper since the inline class is short and explicit. Removes the `hover:border-divider` (which became a no-op when borders were removed from `Surface panel` in Plan 1). Uses `text-base` on the title to align with the StepCard title sizing.)

- [ ] **Step 3: Drop the unused `Surface` import**

`FeatureCard` was the only consumer of `Surface` in `Home.tsx`. With Step 2's change, the import becomes unused and `tsc` strict mode will fail the build. Remove the line:

```tsx
import { Surface } from '../components/ui/Surface'
```

- [ ] **Step 4: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 5: Visual QA**

On `/`, scroll past the steps. The "Under the hood" section heading should match the steps section in style; below it, 6 feature cards in a 1/2/3-column responsive grid, each as a soft white card with subtle shadow, no borders.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "Home/features: shadow-card surfaces, drop hover border, align headings"
```

---

## Task 7: Add closing CTA + footer band (spec 4.3)

Per spec 4.3, when setup is complete (`currentStep === 3`), Home gets a quiet closing CTA card pointing at the Roadmap Tool. Below that, a single hairline-bordered footer band sits below all sections regardless of state.

**Files:**
- Modify: `frontend/src/pages/Home.tsx` (insert two new sections at the bottom of the main scroll content)

- [ ] **Step 1: Add the closing CTA + footer to Home**

In `frontend/src/pages/Home.tsx`, find the closing `</section>` of the features grid (the last section before `</div></div>` at the end of the main JSX), and insert immediately AFTER that closing `</section>` (before the final `</div></div>`):

```tsx
{isAuthenticated && currentStep === 3 && (
  <section className="mb-20">
    <div className="bg-surface rounded-xl shadow-card p-8 text-center">
      <h2 className="text-ink font-semibold text-xl mb-2 tracking-tight">All set.</h2>
      <p className="text-ink-muted text-sm mb-6 max-w-md mx-auto">
        Open the Roadmap Tool to see your wallet's expected value, fees, and sign-up bonus deadlines.
      </p>
      <Link
        to="/roadmap-tool"
        className="inline-flex items-center gap-2 px-5 py-2.5 bg-accent text-on-accent font-semibold text-sm rounded-lg shadow-card hover:opacity-90 transition-opacity"
      >
        Open Roadmap Tool →
      </Link>
    </div>
  </section>
)}
<footer className="border-t border-divider pt-6 pb-4 text-[11px] text-ink-faint text-center">
  <p>
    Wallet projections are estimates only. Cents-per-point values are configurable defaults — adjust to match your redemption habits in the Roadmap Tool.
  </p>
</footer>
```

(The closing CTA only renders for users with full setup. The footer always renders, in 11px ink-faint, separated by a hairline divider.)

- [ ] **Step 2: Build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Visual QA**

Sign in with full setup (cards + spend). Scroll to the bottom of `/`. Expected:
- A new white card with "All set." heading + body + CTA pill.
- Below it, a hairline-divided footer band with the disclaimer text in 11px ink-faint, centered.

Sign in without full setup (or sign out). Expected:
- The CTA card is hidden; only the footer renders.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/Home.tsx
git commit -m "Home: add conditional closing CTA + hairline footer band"
```

---

## Task 8: Final visual QA pass + lint

End-to-end check before merge.

**Files:**
- (Verify only.)

- [ ] **Step 1: Run lint and confirm no NEW issues**

Run: `cd frontend && npm run lint`
Expected: same 3 pre-existing findings inherited from main (`Button/index.tsx:27` ICON_TONE_CLASS export, `CategoryWeightEditor.tsx:39` setState-in-effect, `RoadmapTool/index.tsx:737` exhaustive-deps). NO new findings introduced by this branch.

- [ ] **Step 2: Production build**

Run: `cd frontend && npm run build`
Expected: success.

- [ ] **Step 3: Walk through the navbar in light mode**

Open `/` signed out. Confirm:
- Navbar is white with hairline bottom border.
- Wordmark `CardSolver` in `--color-ink`, hover crimson.
- Right side shows ThemeToggle (icon-only) + "Sign in" secondary Button.
- Click "Sign in" — dropdown panel appears, all primitives (Input, Button, Field) match Plan 1 styling.

- [ ] **Step 4: Walk through the navbar in dark mode**

Toggle theme via the navbar icon. Confirm:
- Navbar background switches to dark surface (cool gray-900-ish), wordmark in light ink, hairline divider visible.
- Active route underline still crimson.
- Sign-in dropdown still readable; tab underline still crimson; form inputs use dark surface tokens.

- [ ] **Step 5: Walk through Home unauthenticated**

Confirm:
- Hero pill in surface-2 with crimson dot.
- Headline 48–56px, bold, tightly-tracked, accent crimson on the second line.
- CTA missing (sign-in required); footnote replaces it.
- Steps section: 3 pending step cards, surface-2 badges with numbers.
- Features grid: 6 shadow-card panels.
- Footer: hairline-bordered, 11px ink-faint disclaimer.

- [ ] **Step 6: Walk through Home authenticated at each step**

Sign in. Cycle through:
- Step 1 (no cards): "Let's get your wallet ready." heading; card 1 has accent ring + filled accent badge + "Next up" eyebrow + "Add cards →" link.
- Step 2 (cards added): card 1 shows complete badge ✓ in pos/10 + "Done" eyebrow; card 2 is current.
- Step 3 (full setup): all 3 complete; new closing-CTA card appears below features grid with "All set." heading + "Open Roadmap Tool →" CTA.

- [ ] **Step 7: Toggle dark mode on Home**

Confirm Home reads cleanly in dark mode — no warm-tan tint leaking through, all surfaces use the dark page/surface tokens.

- [ ] **Step 8: Commit a checkpoint marker**

```bash
git commit --allow-empty -m "shell+home: visual QA pass complete (light + dark, all states)"
```

---

## Plan complete

After Task 8, every entry point to the app feels consistent with the new soft-dashboard direction. Plan 3 (Profile) and Plan 4 (Roadmap Tool) consume the same primitive set and the same rhythm decisions established here.
