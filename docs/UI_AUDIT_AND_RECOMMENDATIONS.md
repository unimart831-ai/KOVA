# Kova Agent — UI & Design Audit + Professional Recommendations

**Date:** May 2026  
**Scope:** Full-stack UI audit — colors, typography, components, dark mode, and brand consistency  
**Objective:** Build a world-class product UI that users trust, love, and recommend

---

## Current State Summary

| Dimension | Score | Verdict |
|-----------|-------|---------|
| Brand clarity | 7/10 | Strong teal identity, muddled documentation |
| Component system | 7/10 | Good primitives, weak enforcement |
| Dark mode | 8/10 | Excellent in app; gaps in modals/public pages |
| Typography | 6/10 | Good font choice, missing weight/scale discipline |
| Color consistency | 5/10 | 3+ greens competing, sub-products drift |
| Accessibility | 8/10 | Focus rings, touch targets, skip links present |
| Mobile UX | 8/10 | Bottom nav, safe areas, tap manipulation |
| Overall polish | 7/10 | Professional for early-stage; needs system maturity |

---

## Immediate Fixes Applied (This Session)

| Fix | File | Impact |
|-----|------|--------|
| PWA manifest `theme_color` → `#0d8474` | `static/manifest.json` | Mobile app chrome matches brand |
| Load Inter 400–800 weights | `templates/base.html` | No more synthesized bold |
| Modal dark mode support | `templates/components/modal.html` | Modals no longer blind users in dark mode |

---

## Professional Recommendations

### Priority 1: Establish One Source of Truth for Color

**Problem:** Three "greens" compete — `kova-*` (teal), `green-*` (Tailwind green), `emerald-*` (Tailwind emerald). Developers pick whichever is closest, creating visual noise.

**Recommendation:**

| Role | Token to Use | When |
|------|--------------|------|
| Primary brand / CTAs | `kova-*` (teal) | Buttons, nav active, links, brand surfaces |
| Success feedback | `emerald-*` | Toasts, badges, checkmarks, "connected" states |
| Money / revenue | `emerald-*` | Revenue metrics, payment success |
| Error / destructive | `red-*` | Form errors, delete actions, failed states |
| Warning / attention | `amber-*` | Limits, approaching quotas, degraded |
| Info / neutral | `blue-*` | Tips, informational badges |
| Sub-product accent | `orange-*` | Snap2sell only (intentional differentiation) |

**Action:** Remove `green-*` usage entirely. Replace with `emerald-*` for success and `kova-*` for brand. This gives every shade a clear semantic meaning.

---

### Priority 2: Lock Down the Type Scale

**Problem:** Ad-hoc font sizes (`text-[10px]`, `text-[11px]`, arbitrary `text-xl` vs `text-lg`) make the hierarchy feel improvised.

**Recommendation — Define 7 named sizes:**

| Token | Tailwind | Use case |
|-------|----------|----------|
| Display | `text-4xl sm:text-5xl font-bold` | Landing hero only |
| Heading 1 | `text-2xl font-bold` | Page titles |
| Heading 2 | `text-xl font-semibold` | Section headings |
| Heading 3 | `text-lg font-semibold` | Card titles, modal headings |
| Body | `text-sm` (14px) | Default body text |
| Caption | `text-xs` (12px) | Timestamps, helper text, badges |
| Micro | `text-[11px]` | Nav section labels, pill counts |

**Why `text-sm` as body default:** Kova is a dense dashboard. 14px is the sweet spot — readable on mobile, efficient on desktop. Most SaaS tools (Linear, Notion, Vercel) use 14px body.

**Action:** Create utility classes if needed, but mainly enforce by convention. Document in a `STYLE_GUIDE.md`.

---

### Priority 3: Strengthen the Component Contract

**Problem:** ~30% of buttons are hand-rolled (`px-4 py-2 bg-kova-600...`) instead of using `btn-primary`. Same for cards.

**Recommendation:**

1. **Never hand-roll a button.** Available classes:
   - `btn-primary` — main CTA (one per view ideally)
   - `btn-secondary` — secondary actions
   - `btn-danger` — destructive actions
   - `btn-ghost` — tertiary / low-emphasis
   - Add size modifiers: `btn-sm`, `btn-lg`

2. **Never hand-roll a card.** Use `.card` + `.card-body`.

3. **Remove dead tokens:** Delete `surface.DEFAULT`, `surface.card`, `surface.raised` from Tailwind config — they're unused and misleading.

4. **Badge standardization:** Use `.badge-success`, `.badge-warning`, `.badge-danger`, `.badge-info` instead of inline `px-2 py-0.5 rounded-full bg-emerald-100...`.

---

### Priority 4: Dark Mode Completion

**Currently broken/missing:**

| Area | Fix needed |
|------|-----------|
| ~~Modal component~~ | ~~Fixed this session~~ |
| Public commerce pages | Add `dark:` variants or use CSS custom properties |
| Email templates | Low priority (email clients barely support dark mode) |
| Chart.js hardcoded hex | Read theme class and swap palettes |
| Marketing footer | Currently always dark — acceptable but document as intentional |

**Principle:** Every surface that a logged-in user sees must support dark mode. Public/marketing can default to light or always-dark (both are valid).

---

### Priority 5: Spacing & Radius Consistency

**Current state:** Mostly consistent, but drifts in sub-products.

**Recommendation — codify the system:**

| Element | Border radius | Spacing |
|---------|---------------|---------|
| Buttons | `rounded-lg` (8px) | `px-4 py-2` (standard), `px-3 py-1.5` (sm) |
| Cards | `rounded-xl` (12px) | `p-4 sm:p-6` body |
| Modals | `rounded-xl` (12px) | `px-6 py-4` header/body/footer |
| Inputs | `rounded-lg` (8px) | `px-3 py-2` |
| Badges/Pills | `rounded-full` | `px-2 py-0.5` |
| Page sections | No rounding | `space-y-6` between sections |

**Rule:** Never use `rounded-2xl` or `rounded-3xl` — they look cheap and bloated.

---

### Priority 6: Brand Documentation Alignment

**Problem:** The brand playbook says primary is blue (`#2563EB`), but the live product uses teal (`#0d8474`). This confuses new developers and creates drift.

**Recommendation:**
- Update `docs/KOVA_BRAND_PLAYBOOK.md` Section 7 to reflect the actual implementation
- Or make a decision: is the brand teal or blue? Pick one, update everything
- The teal is distinctive and works well — recommend keeping it

**New brand color spec to document:**

```
Primary:    kova-600 (#0d8474) — teal, distinctive, calming, professional
Accent:     indigo-600 (#4f46e5) — secondary accent in marketing gradients
Success:    emerald-500 (#10b981) — connected, published, revenue
Warning:    amber-500 (#f59e0b) — limits, attention needed
Danger:     red-500 (#ef4444) — errors, destructive actions
Neutral:    gray-* — all structural elements
```

---

### Priority 7: Sub-Product Accents (Intentional Differentiation)

Some color "inconsistencies" are actually good — they help users orient within different product areas. Formalize them:

| Product Area | Accent | Rationale |
|-------------|--------|-----------|
| Core (Studio, Queue, Brief) | `kova-*` teal | Brand primary |
| Snap2sell / Commerce | `orange-*` | Energy, action, "snap = instant" |
| Partners / Referrals | `emerald-*` | Money, growth, partnership |
| Engage / DMs | Platform colors | Match the platform the user is on |
| Agent identities | Per-agent color | Humanize the AI team |

**Document this** so future developers know orange in Snap isn't a bug.

---

### Priority 8: Performance & Production Polish

| Item | Recommendation |
|------|---------------|
| Font loading | Add `font-display: swap` (already in Google Fonts URL) |
| Compiled CSS size | 199KB is large — run `purgecss` in production build |
| Image icons | Consider inline SVG sprite for common icons (faster than HTTP requests) |
| Loading states | The `.shimmer` class is good — ensure all HTMX endpoints use `_loading_skeleton.html` |
| Transitions | Consistent 150ms ease-in-out for interactive elements (already in `.btn`) |

---

### Priority 9: Mobile-First Excellence

**Current:** Already good — bottom nav, safe areas, 44px touch targets.

**Enhancements for the future:**

| Enhancement | Why |
|-------------|-----|
| Haptic feedback on mobile actions | Makes approve/reject feel physical |
| Pull-to-refresh on Studio feed | Expected mobile behavior |
| Swipe actions on post cards | Quick approve/reject without opening |
| App-like page transitions | HTMX + View Transitions API |
| Reduce motion for `prefers-reduced-motion` | Already partially implemented, extend |

---

### Priority 10: Future-Proofing for Scale

As Kova grows, the current system will hit walls. Plan for:

1. **Design tokens as CSS custom properties** — Enables runtime theming (white-label for agency clients), easier dark mode, and doesn't require Tailwind rebuild
2. **Component library documentation** — A Storybook-like page showing all components (can be a simple internal page)
3. **Automated visual regression** — Screenshot tests on key pages to catch UI drift
4. **Accessibility audit tool** — Run `axe-core` in CI to catch contrast/ARIA issues

---

## Summary — What to Do Now vs. Later

### Do Now (this sprint)
- [x] Fix manifest theme color
- [x] Load proper font weights
- [x] Fix modal dark mode
- [ ] Remove dead `surface` tokens from Tailwind config
- [ ] Update brand playbook colors to match reality
- [ ] Grep for `green-` usage and convert to `emerald-` or `kova-`

### Do Next (next 2-4 weeks)
- [ ] Enforce `btn-primary` / `.card` usage via code review convention
- [ ] Add dark mode to remaining public commerce templates
- [ ] Document the sub-product accent system
- [ ] Create a living style guide page (even just `/admin/styleguide/`)

### Do Eventually (quarterly)
- [ ] Migrate to CSS custom properties for runtime theming
- [ ] Visual regression testing
- [ ] Full accessibility audit (WCAG 2.1 AA)
- [ ] Consider component library (if team grows beyond 3 devs)

---

## Color Reference Card

For quick developer reference — copy-paste into team docs:

```
┌─────────────────────────────────────────────────────────┐
│  KOVA DESIGN TOKENS                                     │
├─────────────────────────────────────────────────────────┤
│  Brand Primary    │  kova-600    │  #0d8474  │  teal   │
│  Brand Light      │  kova-50     │  #edfcf8  │         │
│  Brand Dark       │  kova-800    │  #08564a  │         │
│                                                         │
│  Success          │  emerald-500 │  #10b981  │  green  │
│  Warning          │  amber-500   │  #f59e0b  │  yellow │
│  Error            │  red-500     │  #ef4444  │  red    │
│  Info             │  blue-500    │  #3b82f6  │  blue   │
│                                                         │
│  Snap2sell        │  orange-500  │  #f97316  │  orange │
│  Partners         │  emerald-600 │  #059669  │  green  │
│                                                         │
│  Surface (light)  │  white       │  #ffffff  │         │
│  Surface (dark)   │  gray-900    │  #111827  │         │
│  Page bg (light)  │  gray-50     │  #f9fafb  │         │
│  Page bg (dark)   │  gray-950    │  #030712  │         │
└─────────────────────────────────────────────────────────┘
```
