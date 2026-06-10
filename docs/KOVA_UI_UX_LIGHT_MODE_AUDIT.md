# KOVA UI/UX Light Mode Audit

**Date:** June 11, 2026  
**Scope:** Public/marketing light surfaces, auth, legal, help/blog CTAs; app-shell light mode where applicable  
**Status:** High-impact fixes applied in same sprint (see [Implementation summary](#implementation-summary-jun-2026))

---

## Executive summary

KOVA supports **both light and dark mode** via `class`-based Tailwind dark mode (`localStorage` key `kova-theme`, system `prefers-color-scheme` fallback). Theme toggles exist on:

- Marketing nav (`templates/layouts/marketing.html`) — sun/moon button
- App shell header (`templates/layouts/app.html`) — same pattern
- Admin dashboard (`templates/admin_dashboard/base.html`) — `toggleTheme()`

The **app shell is not dark-only**; sidebar and main content use `bg-white` / `bg-gray-50` in light mode with a standard gray sidebar. This audit prioritized **public light surfaces** where first impressions matter.

**Before:** Decorative motion (ping badges, floating orbs, gradient shifts, pulse rings, scale hovers) competed with copy on white backgrounds.  
**After:** Cleaner static brand presentation; motion gated behind `prefers-reduced-motion: no-preference` where retained; unified `:root` light tokens in `static/css/input.css`.

---

## 1. Light-mode template inventory

### Primary (marketing layout)

| Template | URL / usage | Light bg |
|----------|-------------|----------|
| `templates/pages/landing.html` | `/` | Yes — hero, sections |
| `templates/account/login.html` | `/accounts/login/` | Yes |
| `templates/account/signup.html` | `/accounts/signup/` | Yes |
| `templates/account/password_reset*.html` | Auth flows | Yes |
| `templates/account/email*.html` | Verification | Yes |
| `templates/pages/privacy.html` | `/privacy/` | Yes |
| `templates/pages/terms.html` | `/terms/` | Yes |
| `templates/pages/cookies.html` | `/cookies/` | Yes |
| `templates/pages/acceptable_use.html` | Legal | Yes |
| `templates/pages/dpa.html` | Legal | Yes |
| `templates/pages/compare_*.html` | Comparison pages | Yes |
| `templates/pages/campus_rep.html` | Campus program | Yes |
| `templates/billing/pricing.html` | Pricing | Yes |
| `templates/billing/contact_sales.html` | Sales | Yes |
| `templates/blog/index.html`, `article.html` | Blog | Yes |
| `templates/help/public_index.html`, `public_article.html` | Help center | Yes |
| `templates/partners/landing.html`, apply flows | Partners | Yes |

### Shared brand partials (light surfaces)

| Partial | Used on |
|---------|---------|
| `components/brand/_north_star_tagline.html` | Landing, auth mission, CTAs |
| `components/brand/_mission_panel.html` | Login/signup desktop column |
| `components/brand/_agent_loop_badge.html` | Landing hero, auth mobile |
| `components/brand/_agent_activity_loop.html` | Auth mission panel |
| `components/brand/_atmosphere_orbs.html` | Landing, auth, legal headers |
| `components/brand/_hero_prompt.html` | Landing hero CTA |
| `components/brand/_legal_header.html` | Privacy, terms, cookies |
| `components/brand/_landing_simple_steps.html` | Landing |
| `components/brand/_landing_magic_features.html` | Landing |
| `components/brand/_landing_stories.html` | Landing |
| `components/brand/_public_cta_*.html` | Blog, help CTAs |
| `components/brand/_reveal_script.html` | Scroll reveal (IntersectionObserver) |

### Layout shell

| Template | Role |
|----------|------|
| `templates/base.html` | Theme bootstrap script, fonts, HTMX/Alpine |
| `templates/layouts/marketing.html` | Public nav, footer, theme toggle |

### App shell (light mode exists)

| Template | Light behavior |
|----------|----------------|
| `templates/layouts/app.html` | `bg-gray-50` main, white sidebar, theme toggle in header |
| Settings modals / cards | `.card` → white bg in light mode |

### Out of scope (optional note)

- **Marketing brochures** (`marketing/brochures/html/*.html`) — separate print CSS (`brochure-base.css`); palette aligned but not unified with web tokens in this sprint.

---

## 2. Issues found

### Animations (addressed)

| Issue | Location | Severity |
|-------|----------|----------|
| `animate-ping` on hero badge | `_agent_loop_badge.html` | High — distracting on white |
| `animate-glow-breathe` on K logo | `_mission_panel.html` | High |
| `animate-float` on atmosphere orbs | `_atmosphere_orbs.html` | Medium |
| `animate-pulse-ring` + `animate-pulse` on strategist hub | `landing.html` | High |
| `animate-gradient-shift` on “chases money” | `.text-gradient-hero` in `input.css` | Medium — busy headline |
| Agent SVG dash animation always on | `.agent-connection` | Low — gated now |
| `scale(1.05)` hover on agent nodes | `.agent-node:hover` | Medium — removed |
| Alpine carousel scale + 2.8s interval | `_agent_activity_loop.html` | Medium — softened |
| CTA arrow `group-hover:translate-x` | landing, signup | Low — removed |

### Typography & hierarchy

| Issue | Notes |
|-------|-------|
| North-star tagline uses gradient + animation | Fixed: static kova gradient, Sora display face retained |
| Legal pages rely on `prose` + `glass-panel` | Acceptable; good contrast on white |
| Stats strip `text-xs` labels | WCAG AA for large text only; body labels at 12px gray-500 — monitor |

### Color & contrast

| Element | Light mode | WCAG |
|---------|------------|------|
| `text-kova-600` on white | ~4.6:1 | AA for normal text |
| `text-gray-500` on white | ~4.6:1 | AA borderline for small text |
| Footer (marketing) | Always `bg-gray-900` | Intentional dark footer on light pages — OK |

### Visual noise

| Issue | Mitigation |
|-------|------------|
| Triple radial gradients + floating orbs | Orbs static; gradients kept subtle via `.brand-atmosphere::before` |
| Rainbow agent network gradients | Kept for diagram clarity; connections slowed/gated |
| Multiple reveal delays (0.1–0.6s) | Shortened reveal distance/duration |

### Alpine / HTMX

| Issue | Notes |
|-------|-------|
| `[x-cloak]` flash | Handled globally in `input.css` |
| Pricing currency toggle `x-show` | Brief flash possible before Alpine — acceptable |
| Mobile menu `x-transition` | Functional; not decorative |

---

## 3. Before / after recommendations by page

### Landing (`/`)

| Before | After |
|--------|-------|
| Pulsing strategist hub, ping badge, shifting gradient headline | Static headline gradient; single optional hub ring (`motion-hub-ring`) when motion allowed |
| Floating orbs | Static blurred orbs |
| Heavy scroll reveal (24px / 0.7s) | 12px / 0.45s fade-up |
| Arrow hover slide on CTA | Static arrow |

**Keep:** One-time scroll reveal, pricing toggle, agent network diagram (static lines default).

### Login / Signup

| Before | After |
|--------|-------|
| Breathing logo, ping badge, aggressive activity carousel | Static logo; static dot badge; opacity-only carousel (4.5s), disabled when `prefers-reduced-motion` |
| Duplicate reveal script include | Harmless double-include on login (layout + page) — low priority cleanup |

**Keep:** Mission panel copy hierarchy, glass-panel activity list, `shadow-kova` on auth card.

### Legal (privacy, terms, cookies)

| Before | After |
|--------|-------|
| Floating orbs in legal header | Static orbs |
| Scroll reveal on title | Retained (respects reduced motion) |

**Future:** Consider dropping orbs entirely on legal pages for maximum sobriety.

### Help / Blog / Partners

No template changes this sprint. Recommendations:

- Reuse `.marketing-card` / `.article-content` patterns
- Avoid adding decorative animations to public CTAs

### App shell (light mode)

| Finding | Action |
|---------|--------|
| Theme toggle works | No change |
| Sidebar `nav-link-active` kova-50 bg | Good light-mode affordance |
| In-app decorative pulses (studio, cards) | **Out of scope** — functional loading states |

---

## 4. Animation policy

### Keep (purposeful)

| Animation | Context |
|-----------|---------|
| `animate-spin` | HTMX/form loading, pipeline modals |
| `animate-pulse` (in-app) | Live/recording/composing status indicators |
| Scroll `.reveal` | One-time entrance; disabled when reduced motion |
| Toast / cookie banner transitions | Feedback (< 300ms) |
| `motion-hub-ring` | Optional subtle hub emphasis (landing only, motion-gated) |
| Agent connection dash flow | Optional, slowed to 3s, motion-gated |

### Remove / gate (decorative)

| Removed from public light pages |
|--------------------------------|
| `animate-ping` |
| `animate-glow-breathe` |
| `animate-float` / `animate-float-delayed` |
| `animate-pulse-ring` + double `animate-pulse` hub |
| `animate-gradient-shift` on headline |
| `animate-agent-glow` on orbit nodes |
| Hover scale on marketing cards / agent nodes |
| CTA arrow translate on hover |

### `prefers-reduced-motion`

Implemented in `static/css/input.css`:

- Disables decorative classes and reveals immediately visible
- Alpine activity loop checks `matchMedia` and skips interval
- Agent SVG animations only inside `@media (prefers-reduced-motion: no-preference)`

---

## 5. Professional design tokens (light palette)

Defined in `:root` inside `static/css/input.css` (aligned with Tailwind `kova` scale and brochure navy):

| Token | Value | Usage |
|-------|-------|-------|
| `--kova-light-bg` | `#ffffff` | Page / card surface |
| `--kova-light-bg-muted` | `#f9fafb` | Stats strip, muted sections |
| `--kova-light-bg-subtle` | `#f3f4f6` | Inner panels |
| `--kova-light-text` | `#111827` | Headings (gray-900) |
| `--kova-light-text-muted` | `#4b5563` | Body (gray-600) |
| `--kova-light-text-subtle` | `#6b7280` | Captions (gray-500) |
| `--kova-light-border` | `#e5e7eb` | Cards, dividers |
| `--kova-accent` | `#0d8474` | kova-600 — buttons, links |
| `--kova-accent-hover` | `#0a6d60` | kova-700 |
| `--kova-accent-subtle` | `#edfcf8` | kova-50 highlights |
| `--kova-navy` | `#0c1222` | Footer, brochure alignment |

### Typography scale (existing — keep)

| Level | Classes | Face |
|-------|---------|------|
| H1 hero | `text-4xl sm:text-5xl lg:text-6xl font-extrabold` | Sora (`font-display`) |
| H2 section | `text-3xl sm:text-4xl font-bold` | Sora |
| H3 card | `text-lg–xl font-semibold/bold` | Sora |
| Body | `text-base / text-lg text-gray-600` | Plus Jakarta Sans |
| Caption | `text-xs text-gray-500` | Plus Jakarta Sans |

### Button consistency

Use existing component classes only:

- Primary CTA: `btn-primary`
- Secondary: `btn-secondary`
- Nav CTA: `btn-primary btn-sm`

---

## 6. Implementation summary (Jun 2026)

### Files changed

| File | Change |
|------|--------|
| `static/css/input.css` | Light tokens, motion policy, static gradient hero, reveal tuning |
| `templates/components/brand/_agent_loop_badge.html` | Static status dot |
| `templates/components/brand/_mission_panel.html` | Static logo |
| `templates/components/brand/_atmosphere_orbs.html` | Static orbs |
| `templates/components/brand/_agent_activity_loop.html` | Reduced motion carousel |
| `templates/pages/landing.html` | Hub ring, CTA cleanup |
| `templates/account/signup.html` | Button cleanup |
| `tests/test_public_light_mode.py` | Smoke tests |
| `static/css/output.css` | Rebuilt via Tailwind |

### Animations removed (public/light)

1. `animate-ping` — agent loop badge  
2. `animate-glow-breathe` — mission panel logo  
3. `animate-float` / `animate-float-delayed` — atmosphere orbs  
4. `animate-pulse-ring` + `animate-pulse` — landing strategist hub  
5. `animate-gradient-shift` — north-star headline  
6. `animate-agent-glow` — agent orbit nodes (CSS)  
7. `group-hover:translate-x` — landing/signup CTAs  
8. Scale transforms — agent activity loop, agent node hover  

---

## 7. Testing

### Automated

```bash
pytest tests/test_public_light_mode.py -q
```

Covers: HTTP 200 on landing/login/signup/legal; absence of decorative animation classes on landing; tagline presence.

### Manual checklist (light mode)

1. Open `/` in light mode (toggle or clear `localStorage.kova-theme`, prefer light OS theme).
2. Confirm hero: no pulsing badge, static “chases money” gradient, readable on white.
3. Scroll landing: sections fade in once; no infinite motion except optional hub ring (disable via OS “reduce motion” to verify static).
4. Visit `/accounts/login/` — mission panel static; form card clean white.
5. Visit `/privacy/` — legal header readable; no floating orbs motion.
6. Toggle dark mode on marketing nav — confirm no regressions.
7. Log in → app header theme toggle → light sidebar + gray-50 main content.
8. Enable `prefers-reduced-motion: reduce` in DevTools → reload landing/auth → no carousel cycling, no SVG dash animation.

---

## 8. Future work (not this sprint)

- Dedupe `_reveal_script.html` include on auth pages (included in both layout and page).
- Audit `text-gray-500` at `text-xs` for AAA where easy.
- Optional: shared `components/brand/_light_page_styles.html` if inline docs needed outside Tailwind build.
- Brochure HTML: align `--kova-teal` with web `kova-500/600` if print/web parity matters.
- App-shell studio/card decorative bounces — separate in-app motion audit.

---

## References

- Theme bootstrap: `templates/base.html` (lines 7–15)
- Marketing layout: `templates/layouts/marketing.html`
- Tailwind kova palette: `tailwind.config.js`
- Brochure tokens: `marketing/brochures/assets/brochure-base.css`
