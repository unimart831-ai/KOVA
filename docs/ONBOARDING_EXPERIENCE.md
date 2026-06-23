# Kova Onboarding Experience

**Philosophy:** Hiring and training a new employee — not configuring software.

**North star:** First WOW moment within **3 minutes** of account creation.

**Merged with signup:** After `Create account`, users land directly on the **Hire Kova** screen (`/accounts/onboarding/start/`). No separate setup wizard before value.

---

## 1. Ideal Onboarding Philosophy

| Principle | What it means |
|-----------|---------------|
| **Value before data** | Show generated content before asking for brand strategy |
| **Confirm, don't fill** | Pre-fill from industry packs + optional URL/social — user confirms |
| **Learn automatically** | Brand voice, audience, tone inferred — never asked on day one |
| **Defer friction** | Platform connect, product catalog, menu import — all post-WOW |
| **Hire, don't configure** | Copy speaks like onboarding an employee: "What business do you run?" |

**Avoid:** Multi-page questionnaires, agent settings, dashboard tutorials, marketing jargon, manual brand worksheets.

---

## 2. End-to-End User Journey

```
Sign up (email + phone + password)
    ↓
Hire Kova — business type + goal + name (~60 sec)
    ↓
Confirm brand preview (~30 sec)
    ↓
WOW screen — posts + brief generating (~90 sec)
    ↓
First action — Snap / Studio / Daily Brief
```

**Total active user time:** ~2 minutes. Background intelligence runs while they watch progress.

**OAuth path:** Facebook sign-up may auto-connect platforms → optional magic-fill → confirm → WOW.

---

## 3. Business Discovery Flow

### Screen: "What kind of business do you run?"

**UI:** Visual chips (mobile-first 2×4 grid)

| Chip | Maps to |
|------|---------|
| Salon / Barber | `salon_beauty` + service model |
| Restaurant / Café | `food_restaurant` + product model |
| Boutique / Retail | `fashion_beauty` + product model |
| Electronics store | `wholesale_retail` + product model |
| Agency | `agency` + professional model |
| Consultant | `consulting` + professional model |
| Health / Wellness | `health` + service model |
| Something else | Industry dropdown |

**Collected:** `industry`, `business_model`, `company_name` (one text field)

**Not collected:** Business description, category trees, brand mission statements.

**Implementation:** `apps/accounts/onboarding_discovery.py` + `onboarding_choose_path.html`

---

## 4. Goal Discovery Flow

### Question: "What do you want more of?"

**UI:** Pill chips (single select)

| Goal | Profile goals | Intent |
|------|---------------|--------|
| More sales | drive_sales, generate_leads | sell |
| More bookings | book_appointments, generate_leads | sell |
| More leads | generate_leads | sell |
| More customers | generate_leads, grow_followers | both |
| More awareness | brand_awareness, grow_followers | grow |

**Decision logic:** Goals drive CTA defaults, Daily Brief emphasis, and post-onboarding redirect (commerce vs studio).

---

## 5. Platform Connection Strategy

| Platform | When | Mandatory? |
|----------|------|------------|
| **Instagram** | Optional during hire; encouraged via "Connect Instagram instead" | No |
| **Facebook** | After WOW or from wedge checklist | No |
| **WhatsApp** | Phone collected at signup; Business API later | No (phone yes) |
| **TikTok** | Post-onboarding, commerce users | No |
| **LinkedIn** | Professional/agency users | No |

**Rule:** Nothing blocks finishing onboarding. Publishing is gated; setup is not.

**Magic-fill:** Connecting Instagram/Facebook/LinkedIn auto-fills brand profile from bio, avatar, website.

---

## 6. Business Asset Collection Strategy

Assets are **not** collected during initial onboarding. Collected at first WOW action:

| Business type | First asset moment | Method |
|---------------|-------------------|--------|
| **Product** (retail, fashion, electronics) | Snap-to-Sell after WOW | Photo → AI listing (no catalog form) |
| **Service** (salon, health) | Booking link auto-created | Name + industry only; services added in Snap |
| **Professional** (agency, consultant) | Studio content queue | Portfolio inferred from social/website |
| **Restaurant** | Snap or menu photo import (future) | Photo of menu → OCR (deferred) |

**Rule:** Never ask users to manually build a catalog during onboarding.

---

## 7. Business DNA Architecture

Stored on `UserProfile` + inferred over time:

| Attribute | Required at signup | Source |
|-----------|-------------------|--------|
| Business type / industry | Yes (chip) | User selection |
| Company name | Yes | User input |
| Goals | Yes (chip) | User selection |
| Business model | Auto | Chip mapping |
| Brand voice | No | Industry pack → URL inference → social magic-fill |
| Audience | No | Industry pack + social analysis |
| Tone attributes | No | Industry pack |
| Content pillars | No | Industry pack + analyst agent |
| Visual style | No | Image analysis (post-onboarding) |
| Products / services | No | Snap, imports |
| Competitors | No | Research agent (background) |
| Languages | No | Default `en`; inferred from content |

**Confirm screen:** User sees a preview card — voice, audience, tone, pillars — all pre-filled. One tap to confirm.

---

## 8. Automatic Learning System

```
Industry chip selected
    → industry_packs.apply_pack() (instant defaults)

Optional website URL
    → infer_brand_from_url API (LLM + scrape)

Optional social connect
    → magic_fill.apply_magic_fill() (OAuth profile)

Background (on finish_onboarding)
    → run_onboarding_intelligence chain:
        Research → Seeds → Create drafts → Welcome brief
```

**Business DNA engine (layers):**
1. **Pack layer** — instant, rule-based
2. **URL layer** — website scrape + LLM
3. **Social layer** — platform profile API
4. **Agent layer** — ongoing learning from performance

---

## 9. First WOW Moment Design

### Primary WOW (implemented)
User confirms brand → animated progress → **real draft posts appear** + welcome brief summary.

### WOW variants by path

| Path | WOW moment |
|------|------------|
| Commerce (retail, salon) | "Your AI already wrote these" + Snap CTA |
| Professional | Content queue + LinkedIn-angle drafts |
| Social-connected | Platform-native drafts per connected account |
| No social | Generic drafts ready; connect later to publish |

### Future WOW (roadmap)
- Upload 3 product photos → instant reel + carousel + WhatsApp promo
- Connect Instagram → audience insights card in Daily Brief

---

## 10. WhatsApp-First Onboarding

For users who prefer WhatsApp over web:

```
Kova: Hi 👋 Welcome to Kova. What kind of business do you run?
      1 Salon  2 Restaurant  3 Shop  4 Agency  5 Other

User: 1

Kova: Nice. What should we call your business?

User: Glow Salon

Kova: What do you want more of?
      1 Bookings  2 Leads  3 Sales  4 Customers

User: 1

Kova: Perfect. Send me 2–3 photos of your work (or your Instagram @handle).
      I'll draft posts while you run the shop.

User: [photos]

Kova: Done ✓ I drafted 3 posts. Reply APPROVE to see them or OPEN to review in browser.
```

**Web parity:** Phone collected at signup enables this channel. Template: onboarding WhatsApp flow (admin configurable).

---

## 11. Mobile Experience Design

- **Chip grids:** 2 columns on mobile, 4 on desktop
- **Goal pills:** Horizontal wrap, 44px touch targets
- **Single required text field:** Business name only
- **Progress bar:** 2 steps — Hire → Confirm
- **No atmospheric clutter:** Flat white, growth accent on selection
- **Bottom CTA:** Full-width primary button

---

## 12. Friction Reduction Recommendations

| Step | Verdict | Action |
|------|---------|--------|
| Signup phone | Keep | Required for WhatsApp + M-Pesa |
| Business model 3-column cards | **Removed** | Replaced by business type chips |
| Step 1 long form | **Deferred** | Only for manual/magic-connect fallback |
| Brand voice textarea | **Removed** from onboarding | Industry pack + inference |
| Platform connect gate | **Removed** | Optional throughout |
| Agent configuration | **Never** | Defaults on |
| Dashboard tutorial | **Never** | Daily Brief is the guide |
| Menu/catalog forms | **Deferred** | Snap photo import |
| Competitor list | **Auto** | Research agent |
| Timezone picker | **Auto** | Africa/Nairobi default |

---

## 13. Three-Minute Onboarding Blueprint

| Minute | User does | Kova does |
|--------|-----------|-----------|
| **0:00** | Create account | Creates profile, starts trial |
| **0:30** | Pick business + goal + name | Applies industry pack |
| **1:00** | Confirm brand preview | Starts intelligence chain |
| **1:30** | Watches progress animation | Research + seed ideas |
| **2:30** | Sees draft posts + brief | Create agent finishes drafts |
| **3:00** | Taps Snap or Studio | First value delivered |

---

## 14. Implementation Roadmap

### Shipped (this release)
- [x] Conversational hire screen merged post-signup
- [x] Business type + goal chips
- [x] Fast path → confirm (skip step 1 form)
- [x] 2-step progress indicator
- [x] Middleware routes to hire screen
- [x] Industry pack auto-fill on chip select
- [x] WOW progress screen with post previews

### Next (high impact)
- [ ] Hero signup → pre-fill business hint on hire screen (partial — session hint exists)
- [ ] Photo upload WOW on confirm screen (3 photos → drafts)
- [ ] WhatsApp conversational onboarding bot
- [ ] Menu photo OCR for restaurants
- [ ] Reduce magic-connect to inline OAuth on hire screen

### Later
- [ ] Competitor auto-discovery card in Daily Brief
- [ ] Voice note business description (WhatsApp)
- [ ] Team/agency multi-client onboarding (sales-led)

---

## Code Map

| Piece | Location |
|-------|----------|
| Hire screen | `templates/accounts/onboarding_choose_path.html` |
| Discovery logic | `apps/accounts/onboarding_discovery.py` |
| Confirm preview | `templates/accounts/_onboarding_brand_preview.html` |
| WOW screen | `templates/accounts/onboarding_complete.html` |
| Finish + intelligence | `apps/accounts/onboarding_flow.finish_onboarding` |
| Industry defaults | `apps/accounts/industry_packs.py` |
| Post-onboarding redirect | `apps/accounts/onboarding_redirects.py` |
| First-week checklist | `apps/accounts/setup_mission.py` |

---

*Kova Onboarding Experience — June 2026*
