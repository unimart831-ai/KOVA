# Kova Design System v3

**Positioning:** Kova is the AI marketing employee for African businesses — helping retail stores, salons, restaurants, agencies, and service businesses get more customers with less effort.

**Visual goal:** A world-class growth platform that makes users feel *"more customers, more revenue, less work"* — not corporate banking software, not a generic AI tool.

**Emotional hierarchy:** Growth first. Trust second. Action third.

---

## 1. Color Distribution

The interface should *feel* approximately:

| Weight | Color | Role |
|--------|-------|------|
| **50%** | Growth Emerald `#10B981` | Revenue, customers, momentum, primary CTAs |
| **30%** | Trust Blue `#1E3A8A` | Navigation, links, stability, content metrics |
| **20%** | Action Gold `#F59E0B` | Approvals, pending, attention highlights |

**Avoid:** 80% blue / 15% white / 5% everything else.

---

## 2. Official Tokens

### Growth Emerald — emotional hero
```
growth-500: #10B981  ← primary CTAs, revenue, customers
growth-600: #059669  ← hover
growth-400: #34D399  ← leads chart, secondary growth
growth-50:  #ECFDF5  ← subtle backgrounds
```
**Use for:** Primary buttons, money metrics, lead counts, hero emphasis ("chases money"), checkmarks, published/success states, revenue charts.

### Trust Blue — stability layer
```
kova-800: #1E3A8A  ← trust anchor (nav active text, secondary CTAs)
kova-700: #1D4ED8
kova-50:  #EFF6FF  ← subtle nav backgrounds
```
**Use for:** Sidebar navigation, links, secondary/outline buttons, content/engagement metrics, supporting brand elements. Blue **supports** — it does not dominate.

### Action Gold — attention layer
```
gold-500: #F59E0B
gold-50:  #FFFBEB
```
**Use sparingly for:** Pending approvals, notifications, "Approve in 5 minutes" highlights, warnings requiring action.

### Text
```
Primary:   #0F172A  (gray-900 / charcoal)
Secondary: #475569  (gray-600)
Muted:     #64748B  (gray-500)
```

### Backgrounds
```
Primary:   #FFFFFF  (marketing — pure white, no atmospheric tint)
Secondary: #F8FAFC  (gray-50 — alternating sections)
Surface:   #F1F5F9  (gray-100)
Dark page: #0F172A  (gray-900 — flat, no glows)
```

### CSS variables (`input.css :root`)
```css
--growth-emerald: #10B981;
--growth-emerald-hover: #059669;
--trust-blue: #1E3A8A;
--action-gold: #F59E0B;
--chart-revenue: #10B981;
--chart-leads: #34D399;
--chart-content: #1E3A8A;
--chart-pending: #F59E0B;
--chart-error: #DC2626;
```

---

## 3. Button System

| Variant | Style |
|---------|-------|
| **Primary CTA** | `bg-growth-500` → hover `growth-600`, white text |
| **Secondary CTA** | Border + text `kova-800`, hover `kova-50` surface |
| **Tertiary** | Text-only links |
| **Danger** | `red-*` only |

Classes: `.btn-primary`, `.btn-secondary`, `.btn-outline`, `.btn-ghost`

---

## 4. Hero Typography Hierarchy

Example north-star tagline:

| Phrase | Color |
|--------|-------|
| "The system that" | Dark text |
| "chases money" | **Growth Emerald** |
| "for my business" | Dark text |
| "while I run the shop." | **Trust Blue** |

Creates visual movement: growth → trust.

---

## 5. Role-Based Usage

| UI element | Token |
|------------|-------|
| Primary CTA / signup | `btn-primary` → `growth-500` |
| Sidebar active link | `nav-link-active` → `kova-50` / `kova-800` |
| Revenue stat / money board | `growth-*` |
| Lead metrics | `growth-*` |
| Customer growth | `growth-*` |
| Navigation chrome | `kova-800` |
| Pending approvals | `gold-*` |
| Content / engagement | `kova-*` |
| Errors / failures | `red-*` only |
| Platform accents (IG, WA) | Third-party colors — unchanged |

### Semantic badges
```html
<span class="badge-revenue">KSh 12,400</span>
<span class="badge-pending">3 awaiting approval</span>
<span class="badge-success">Paid</span>
<span class="badge-danger">Failed</span>
```

---

## 6. Dashboard Rebalancing

### Daily Brief
- Money board → `growth-*`
- "Your move today" → `growth-500` icon
- Pending tasks → `gold-*`
- Nav / links → `kova-800`

### Results / Revenue
- Headline revenue → `growth-600`
- Period pills active → `growth-500`
- Revenue tab underline → `growth-500`
- Attribution confidence → growth (high), gold (medium), gray (low)

### Content Studio
- Approve primary action → `btn-primary` (green)
- Pending posts → `gold-*`
- Published → `growth-*`

---

## 7. Landing Page

- Logo mark → `bg-growth-500`
- Hero emphasis → growth gradient text (`.text-gradient-hero`)
- Agent network SVG → `#10B981` + `#1E3A8A` gradients
- "Approve in 5 minutes" → `gold-*` (action)
- Pricing "Most Popular" → `growth-500` border/badge
- Currency toggle active → `growth-500`
- Feature pillars → growth for revenue outcomes, kova for trust/platform
- Bottom CTA → `btn-primary` + `shadow-growth`
- Footer logo → green

Marketing backgrounds: solid `#FFFFFF` — no atmospheric gradients on hero.

---

## 8. Chart Standards

| Series | Hex | Tailwind |
|--------|-----|----------|
| Revenue | `#10B981` | `growth-500` |
| Leads | `#34D399` | `growth-400` |
| Content / engagement | `#1E3A8A` | `kova-800` |
| Approvals / pending | `#F59E0B` | `gold-500` |
| Errors | `#DC2626` | `red-600` |
| Neutral | `#94A3B8` | `gray-400` |

Fill opacity for content area charts: `rgba(30, 58, 138, 0.1)`.

---

## 9. Component System

Defined in `static/css/input.css`:

| Component | Class |
|-----------|-------|
| Primary button | `.btn-primary` (growth) |
| Secondary button | `.btn-secondary` (trust blue outline) |
| Card | `.card` |
| Revenue badge | `.badge-revenue` |
| Pending badge | `.badge-pending` |
| Nav active | `.nav-link-active` |
| Hero gradient text | `.text-gradient-hero` |
| Growth shadow | `.shadow-growth` |
| Stat card accent | `.stat-card` → growth border |

**Tailwind scales:** `growth`, `kova`, `gold`, `gray` (slate-aligned)

---

## 10. Brand Feel

**Reference:** Stripe, Shopify, Wise, Linear — clean, confident, outcome-focused.

**Avoid:** Banking portals, government portals, crypto aesthetics, neon startups, generic AI purple gradients.

---

## 11. Accessibility

| Pair | Notes |
|------|-------|
| `growth-600` on white | ✓ body text |
| `growth-500` on white | ✓ large text / buttons |
| `kova-800` on white | ✓ links, nav |
| `gold-700` on white | ✓ pending labels |
| White on `growth-500` | ✓ primary buttons |

Focus rings: `ring-growth-500` on primary actions, `ring-kova-500` on inputs. Touch targets: 44px minimum on mobile.

---

## 12. Dark Mode

| Light | Dark |
|-------|------|
| `bg-white` | `bg-gray-900` |
| `growth-500` accents | `growth-400` |
| `kova-800` nav | `kova-300` text |
| `gold-500` pending | `gold-400` |

No radial glow overlays. Flat dark surfaces.

---

## Migration from v2

| v2 (blue-primary) | v3 (growth-primary) |
|-------------------|---------------------|
| `kova-600` `#0F4C81` as primary | `growth-500` `#10B981` as primary CTA |
| `growth-500` `#00A86B` | `growth-500` `#10B981` (Emerald) |
| Blue dominates UI | Green dominates emotional weight |
| Hero CTAs blue | Hero CTAs green |
| Nav blue-600 | Nav `kova-800` trust blue |

---

## Rebuild CSS

```bash
cd kova_agent
npx tailwindcss -i ./static/css/input.css -o ./static/css/output.css --minify
python manage.py check
```

---

*Kova Design System v3 — Growth-first visual identity — June 2026*
