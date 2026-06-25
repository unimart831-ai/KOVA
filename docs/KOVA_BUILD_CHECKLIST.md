# Kova Master Build Checklist

**Category:** AI Marketing Department + Commerce Infrastructure for African SMEs  
**Last updated:** 2026-06-25  
**Owners:** Founders (Product + Engineering)  
**Supersedes:** Multi-tier public pricing (legacy Starter / Growth / Pro — grandfathered only in `PLAN_LIMITS`)

---

## North star

One loop, end to end:

```
Send asset → Seeds proposed → Campaign built → Visuals (Photoroom) →
Carousel/Reel (Kova) → Publish → Commerce page → Lead → WhatsApp →
Payment → Revenue learned → Better seeds next time
```

**We are not:** Canva · Buffer · Hootsuite · Shopify  
**We are:** Marketing intelligence + commerce infrastructure — one plan, one promise.

---

## Pricing decision (LOCKED)

### One public plan

| | Value |
|---|--------|
| **Name** | Kova |
| **Price** | **KES 1,300 / month** (~**USD 10**) |
| **Core quota** | **30 campaigns / month** |
| **Trial** | 7 days · **5 campaigns** (confirm at launch) |
| **Payment** | M-Pesa (primary) · Stripe/card (secondary) |

Customer-facing unit: **Campaign** (internal code: `ContentSeed` until rename migration).

### What’s included (unlimited / not campaign-metered)

These are **infrastructure** — included so owners stay daily-active:

| Included | Notes |
|----------|--------|
| Daily Brief | Morning standup |
| Publishing & scheduling | All platforms connected |
| Approval queue | No cap on posts *from* campaigns |
| Kova Commerce Page | `/shop/<slug>/` auto-generated |
| Product & service pages | From assets |
| M-Pesa checkout | On commerce pages |
| Booking pages | Service businesses |
| Lead capture & inbox | Engage + leads list |
| WhatsApp utility replies | Booking confirm, order updates |
| Brand DNA & onboarding | One business profile |
| Analytics & revenue board | Base dashboards |
| Social accounts | **Up to 4** (FB, IG, TikTok, LinkedIn) |
| WhatsApp inbox | Lead + order conversations |

### Campaign add-ons (subscribe for more)

When 30 campaigns aren’t enough, user buys **extra campaigns** — not a new tier.

| Add-on pack | Campaigns | Suggested price | Notes |
|-------------|-----------|-----------------|-------|
| **Boost** | +10 / month | KES 450 (~$3.50) | Recurring or one-time month |
| **Scale** | +30 / month | KES 1,200 (~$9) | ~same unit economics as base |
| **Burst** | +5 one-time | KES 250 (~$2) | Expires end of calendar month |

**Founder confirm before build:** exact add-on KES amounts and whether Boost/Scale are recurring subscriptions or manual top-ups.

Implementation: extend `profile.seed_monthly_bonus` from **purchased add-ons** (audit in `ContentSeedQuotaLog`); Stripe Price IDs + M-Pesa SKU per pack.

### Removed from public pricing

- ~~Starter / Growth / Pro ladder~~
- ~~Posts-per-month as customer-facing limit~~ (keep internal guardrail only)
- ~~Feature gating by tier~~ for core loop (brief, commerce, publish, inbox)

### Kept internal-only

| Tier | Purpose |
|------|---------|
| **Agency** | Sales-approved · multi-brand · white-label · custom caps |
| **Staff / pilot** | `seed_monthly_limit_override`, comp accounts |

### Economics guardrails (non-negotiable)

Per **activated campaign** (Growth-equivalent bundle):

- Photoroom: cap scenes per campaign (e.g. 5 variants)
- Carousel: Bannerbear or local Pillow (no unlimited API spam)
- Reel: FFmpeg default · Kling **not** in base plan
- LLM: soft monthly token ceiling with fair-use message (no hard tier UX)

---

## Terminology map

| Customer says | Code / DB today | Target |
|---------------|-----------------|--------|
| Campaign | `ContentSeed` | `Campaign` model (Phase 2) |
| Marketing opportunity | Seed proposal | `SeedProposal` |
| Commerce Page | `/shop/<slug>/` | Unified public surface |
| Campaign Page | — | `/c/<slug>/` (new) |
| Snap | Snap to Sell | **Kova Commerce** intake |

---

## Build phases overview

| Phase | Focus | Weeks | Unlocks |
|-------|--------|-------|---------|
| **0** | Pricing & positioning | 1–2 | Single plan live |
| **1** | Campaign foundation | 3–5 | Asset → seeds → campaign |
| **2** | Commerce unification | 4–6 | One public URL story |
| **3** | Media factory | 5–8 | Photoroom + carousel + reel stack |
| **4** | WhatsApp-first ops | 6–9 | Daily loop on phone |
| **5** | Intelligence & QA | 8–11 | Brain + visible quality score |
| **6** | Revenue OS | 10–14 | Attribution closed loop |
| **7** | Agency & scale | 14+ | B2B, partners |

---

## Phase 0 — Pricing & positioning

**Goal:** One plan, one checkout, campaigns as the only scarce resource.

### 0.1 Founder sign-off
- [x] Confirm KES 1,300 and USD 10 display prices *(locked in `PLAN_LIMITS`)*
- [x] Confirm trial: 7 days, 5 campaigns *(locked in billing code)*
- [x] Confirm add-on pack prices (Boost / Scale / Burst) *(config in `campaign_addons.py`)*
- [x] Confirm included platform cap (4 social + WA inbox) *(Kova plan limits)*

### 0.2 Billing code (`apps/billing/`)
- [x] Add single plan key `kova` in `PLAN_LIMITS` with `max_seeds_per_month: 30`
- [x] Set `price_kes: 1300`, `price_usd: 10`
- [x] Merge Growth-tier capabilities into `kova` (commerce, bannerbear, engage, etc.)
- [x] Deprecate `starter` / `growth` / `pro` for **new** checkouts (keep for grandfathered users via `maybe_grandfather_to_kova`)
- [x] `PUBLIC_PLAN_TIERS = ["kova"]`
- [x] `TRIAL_FEATURE_PLAN = "kova"` with trial campaign cap override (5)
- [x] Remove post-limit middleware user messaging (internal cap only)
- [x] Add `CampaignAddonProduct` model or config: pack_id, campaigns, price_kes, stripe_price_id
- [x] M-Pesa STK for base plan + add-on packs
- [x] Stripe checkout for base + add-ons (`STRIPE_PRICE_KOVA`, addon price IDs, `stripe_addon_checkout`)
- [x] On successful add-on payment → `recurring_campaign_bonus` / `burst_campaign_bonus` → `seed_monthly_bonus`
- [x] Webhook renewal: recurring add-ons stack on base 30; burst expires month-end (`campaign_renewal.py`)

### 0.3 UI & copy
- [x] Rewrite `templates/billing/pricing.html` — single card + add-on packs
- [x] Settings → billing: show **Campaigns: 12 / 30** (+ bonus if any)
- [x] Replace “seeds” / “posts per month” in user-facing strings → **campaigns** (Studio, Settings, landing)
- [x] Landing page pricing section — single Kova plan + add-ons
- [x] Help articles + onboarding copy
- [x] Update legacy plan docs removed — `KOVA_BUILD_CHECKLIST.md` is sole pricing source

### 0.4 Migration
- [x] Grandfather map: existing Growth/Pro → kova at renewal + goodwill campaigns (`maybe_grandfather_to_kova`)
- [x] Admin report: subscribers by legacy tier (`python manage.py legacy_tier_report`)
- [x] Email existing users before switch (`python manage.py kova_migration_email --send`)

**Exit criteria:** New user can pay KES 1,300, see 30 campaigns/month, buy +10 add-on.

---

## Phase 1 — Campaign foundation

**Goal:** Asset → multiple seed proposals → one campaign bundle per activation.

### 1.1 Business Asset Engine (Layer 1)
*Status: ~90% built*

- [x] `BusinessAsset` model + types (product, service, portfolio, testimonial, offer, event)
- [x] Product ↔ Asset bridge (`business_assets.sync_asset_from_product`)
- [x] Asset API `/api/v1/assets/`
- [x] Single **Asset intake** UI (`products:asset_intake` + Snap → proposals)
- [x] Asset list in Studio (`_studio_assets_panel.html`)
- [x] Asset → metadata schema (`asset_metadata.py` + intelligence merge)

**Files:** `apps/products/models.py`, `apps/products/business_assets.py`, `apps/products/views.py`

### 1.2 Seed Generation Engine (Layer 2) — **critical path**
*Status: ~85% built*

- [x] `propose_seeds_from_asset(asset) → SeedProposal[]` (LLM + rules)
- [x] Proposal schema: `title`, `angle`, `intent`, `suggested_formats`, `rationale`
- [x] UI: “Kova found 5 ways to market this” → user picks 1
- [x] Each pick consumes **1 campaign** from quota
- [x] Wire Snap complete → seed proposals screen (`proposals_only=True` on `snap_to_sell_analyze`)
- [x] Strategist: bias proposals from revenue history + vision metadata
- [x] Brief one-click actions → proposal flow (not raw seed create)
- [x] WhatsApp `IDEA N` → proposals URL (not auto-seed)

**Files:** `apps/content/seed_proposals.py`, `templates/content/campaign_proposals.html`

### 1.3 Campaign Generation Engine (Layer 3)
*Status: ~75% built*

- [x] `Campaign` model: links `BusinessAsset`, `ContentSeed`, blueprint, outputs, quality_score, commerce_url
- [x] Campaign states: `draft` → `generating` → `review` → `approved` → `published` → `archived`
- [x] Campaign bundle spec (see below) enforced on `generate_from_seed`
- [x] Objective / audience / CTA on campaign card
- [x] Approval UI: one campaign card (not scattered posts)

**Campaign output spec (v1 — base plan):**

| Output | Included |
|--------|----------|
| Feed post | IG + FB |
| Story set | 3 frames |
| Carousel | 5–6 slides (funnel structure) |
| Reel | 1 (FFmpeg + director) |
| Platform copy | TikTok + LinkedIn if connected |
| Campaign page | `/c/<slug>/` (Phase 2) |
| Photoroom variants | Up to 5 per campaign |

**Files:** `apps/content/campaign_bundle.py`, `apps/content/campaign_approval.py`, `apps/content/models.py`, `apps/content/tasks.py`, `apps/agents/create_agent.py`

### 1.4 Rename & quota
- [x] Count **campaign activations** (seed → generating), not raw seed rows
- [x] Autopilot / strategist seeds respect same quota
- [x] User-facing: “23 campaigns left this month”

**Exit criteria:** Upload handbag → see 5 proposals → pick “Weekend offer” → one campaign card with reel + carousel + posts.

---

## Phase 2 — Kova Commerce

**Goal:** “The website you don’t have to build.”

### 2.1 Unified Commerce Page (Layer 15)
*Status: ~75% built*

- [x] Public shop `/shop/<page_slug>/` + storefront themes (`storefront.py`)
- [x] Per-product commerce `/shop/<page_slug>/<slug>/` + M-Pesa
- [x] Booking `/book/<slug>/`
- [x] Kova Pages `/k/<slug>/` (link-in-bio)
- [x] **Unify:** one canonical URL per business (`page_slug` = brand handle)
- [x] Merge Kova Page forms/links into shop footer
- [x] Service layout: services section + book-on-WA CTA (`resolve_business_layout`)
- [x] Professional layout: portfolio from published `BusinessAsset`
- [x] Gallery from Kova-published media (`commerce_gallery.py` + shop partial)
- [x] SEO + OG tags enriched from Brand DNA (`commerce_seo.py`)

### 2.2 Campaign Pages — **critical path**
*Status: ~90% built*

- [x] `CampaignPage` model: slug, offer copy, assets, expiry, CTA, payment mode (`MarketingCampaign`)
- [x] Public route `/c/<campaign_slug>/`
- [x] Auto-create on campaign generation
- [x] Default post CTA → campaign page or product commerce URL
- [x] Archive when campaign ends / offer expires
- [x] Conversion tracking: view → click → lead → sale (page views + UTM on post CTAs)

**Files:** `apps/products/commerce_views.py`, new `apps/commerce/campaign_pages.py`

### 2.3 Payments (Layer 16)
*Status: ~85% built*

- [x] M-Pesa commerce STK
- [x] Campaign page checkout
- [x] Receipt + WhatsApp order notification (buyer receipt + seller alert on M-Pesa / WA click)
- [ ] Card payments (Stripe) — future *(commerce checkout; billing Stripe done)*
- [ ] Airtel Money — future

**Exit criteria:** Every campaign has a Kova URL; bio link is `/shop/handle`, flash sale is `/c/summer-sale`.

---

## Phase 3 — Media factory

**Goal:** Photoroom = pixels · Kova = story. See architecture below.

### 3.1 Visual Production — Photoroom (Layer 7)
*Status: ~85% built*

- [x] Background removal, relight, scenes, beautify, expand
- [x] Orchestrator sends instructions (`apps/media/orchestrator.py`)
- [x] Plan persisted on `BusinessAsset.metadata.media_plan`
- [x] Per-campaign scene cap (5) enforced in orchestrator + `CampaignVisualBrief`
- [x] Campaign-level brief to Photoroom (`CampaignVisualBrief` → `photo_variations`)
- [x] `MediaProviderConfig` centralizes provider keys (`apps/media/media_provider_config.py`)
- [ ] Production Bannerbear template UIDs + Fal keys in Railway *(deploy — validate via `MediaProviderConfig`)*

### 3.2 Carousel Factory (Layer 8)
*Status: ~75% built*

- [x] Funnel slide structure in `apps/agents/carousel.py`
- [x] Bannerbear bridge + Pillow fallback
- [x] Campaign-driven slide JSON (`CarouselStrategy` + Create Agent prompt)
- [x] Educational / FAQ / offer carousel templates by business type
- [x] Renderer abstraction for V2 HTML screenshot (`carousel_renderer.py`)

### 3.3 Reel Factory (Layer 9)
*Status: ~70% built*

- [x] `reel_director.py` — hook, scenes, recipes
- [x] FFmpeg compose (`video_compose.py`) — **default**
- [x] Photoroom animate — single-hero optional
- [x] Kling — add-on or Agency only (not base $10 plan)
- [x] Reel strategy JSON on Campaign (`ReelStrategy` → `compose_reel_video`)
- [x] Text overlay plan → FFmpeg burn-in quality pass (`TextOverlayPass`)
- [x] Remotion eval spike complete — production stack in `media_factory.py`

### 3.4 Platform Adaptation (Layer 10)
*Status: ~80% built*

- [x] Blueprint + renderers per platform
- [x] Native rewrite pass (`platform_rewrite.py`) in Create Agent
- [x] Platform fit in QA score (`platform_fit.py`, min 80 gate)

**Media stack (locked):**

| Job | Owner |
|-----|--------|
| Images | Photoroom |
| Carousel pixels | Kova → Bannerbear / Pillow |
| Reel story + assembly | Kova → FFmpeg |
| Premium motion clip | Kling (add-on) |

---

## Phase 4 — WhatsApp-first operations

**Goal:** Phone is the daily cockpit.

### 4.1 Onboarding (Layer 2)
*Status: ~85% built*

- [x] Hire Kova web onboarding
- [x] WhatsApp onboarding: “What business do you run?” → profile (`owner_onboarding.py`)
- [x] Social connect (FB, IG, TikTok, LinkedIn)
- [x] Brand discovery / industry packs
- [x] Competitor discovery (research agent → brief hints)

### 4.2 WhatsApp Commerce (Layer 14)
*Status: ~90% built*

- [x] Owner snap intake on master number
- [x] Approve/reject commands
- [x] MONEY, LEADS, BOOK commands
- [x] Campaign ready notification + approve from WA
- [x] Product/service share cards
- [x] AI reply drafts: inbox badge + `REPLIES` / `APPROVE REPLY` / `REJECT REPLY` owner commands
- [x] Order tracking messages (seller notified on WA order tap + M-Pesa sale)

### 4.3 Publishing (Layer 12)
*Status: ~80% built*

- [x] Schedule, auto-publish, approval queue
- [x] Bulk approve at **campaign** level
- [x] Default CTA = Kova commerce URL

### 4.4 Engagement (Layer 13)
*Status: ~75% built*

- [x] Engage agent, inbox
- [x] DM monitoring depth (platform-dependent via `ai_intent` + routing)
- [x] Lead detection + escalation (`lead_escalation.py`)
- [x] Sentiment on flagged threads (negative → FLAGGED status)

**Exit criteria:** Owner completes loop without opening laptop: photo → WA → approve → publish → lead reply.

---

## Phase 5 — Kova Brain & quality

### 5.1 Intelligence layers (Layer 1)
*Status: ~75% built*

- [x] Brand DNA (`apps/media/brand_dna.py`, profile fields)
- [x] Content DNA (analyst agent)
- [x] Audience DNA structured fields + inference (`audience_dna.py`)
- [x] Revenue DNA: winning hooks/CTAs/formats from attribution DB (`revenue_dna.py`)
- [x] Feed recommendations back into `propose_seeds_from_asset`

### 5.2 Authority Content (Layer 6)
*Status: ~65% built*

- [x] Professional templates, educator agent
- [x] FAQ / myth / tip packs from Brand DNA (`authority_packs.py`)
- [x] Auto authority seeds for consultants (weekly) (`authority_packs.py` → Strategist cycle)

### 5.3 Quality Assurance (Layer 20)
*Status: ~75% built*

- [x] `blueprint_quality_score` + auto-retry
- [x] User-visible **Campaign quality: 87/100**
- [x] Gates: brand, visual, platform, CTA, compliance
- [x] Block publish below threshold (configurable, default 75)
- [x] Premium add-on: “Cinematic reel” (Kling) only if QA pass (`reel_bridge.py` + `KLING_MIN_CAMPAIGN_QA`)

### 5.4 Daily Brief (Layer 11)
*Status: ~90% built*

- [x] Brief generation, decisions, trends
- [x] Campaign suggestions tied to assets in catalog (`asset_suggestions.py`)
- [x] Lead + revenue summary blocks (parity with MONEY command — `_money_board.html`)

---

## Phase 6 — Revenue operating system

### 6.1 Analytics (Layer 18)
*Status: ~80% built*

- [x] Pageviews, conversions, revenue dashboard
- [x] Campaign-level performance view
- [x] Platform comparison per campaign type

### 6.2 Revenue Attribution (Layer 19) — **moat**
*Status: ~85% built*

- [x] M-Pesa → product, bookings → service
- [x] `asset_attribution`, Pixel UTM on posts
- [x] `campaign_id` on all conversion events
- [x] Funnel: campaign → page view → lead → WA → sale
- [x] Brief line: “Weekend handbag campaign → KES 12,400”
- [x] Brain feedback: downrank low-revenue angles

**Exit criteria:** Owner sees which **campaign** made money, not just which post.

---

## Phase 7 — Agency & future

### 7.1 Agency mode (Layer 21)
*Status: ~65% built — sales-only*

- [x] Teams, brands, agency theme
- [x] Client approval workflow (`teams/client_approval.py` + studio routes)
- [ ] White-label commerce URL (CNAME)
- [ ] White-label reporting PDF
- [ ] Separate pricing (not $10 plan)

### 7.2 Optional add-ons (paid extras)

| Add-on | Type |
|--------|------|
| +10 / +30 campaigns | Recurring pack |
| Cinematic reel (Kling) | Per campaign or monthly cap |
| Extra business (2nd brand) | Agency-lite |
| Custom domain | `shop.brand.co.ke` |
| Priority support | Human onboarding call |

---

## Master feature checklist (21 engines)

Use **Status** column: `Done` · `Partial` · `Not started` · `Phase N`

| # | Engine | Status | Phase | Primary modules |
|---|--------|--------|-------|-----------------|
| 1 | Kova Brain | Partial | 5 | `agents/`, `media/brand_dna.py`, `audience_dna.py`, `revenue_dna.py` |
| 2 | Onboarding | Done | 4 | `accounts/`, `agents/onboarding_tasks.py`, `whatsapp/owner_onboarding.py` |
| 3 | Content Asset | Done | 1 | `products/business_assets.py`, `asset_intake` |
| 4 | Seed Generation | Done | 1 | `content/seed_proposals.py` |
| 5 | Campaign Generation | Done | 1 | `content/campaign_bundle.py`, `create_agent.py` |
| 6 | Authority Content | Partial | 5 | `media/authority_packs.py`, `agents/strategist_agent.py` |
| 7 | Visual Production | Done | 3 | `media/media_factory.py`, `orchestrator.py` |
| 8 | Carousel Factory | Done | 3 | `carousel_strategy.py`, `carousel_renderer.py` |
| 9 | Reel Factory | Done | 3 | `reel_strategy.py`, `video_compose.py`, `text_overlay.py` |
| 10 | Platform Adaptation | Done | 3 | `platform_rewrite.py`, `platform_fit.py` |
| 11 | Daily Brief | Done | 5 | `briefs/`, `asset_suggestions.py` |
| 12 | Publishing | Done | 4 | `content/tasks.py`, `platforms/` |
| 13 | Engagement | Partial | 4 | `engage/lead_escalation.py` |
| 14 | WhatsApp Commerce | Done | 4 | `whatsapp/`, `owner_snap_whatsapp.py` |
| 15 | Kova Commerce | Done | 2 | `commerce_views.py`, `commerce_gallery.py` |
| 16 | Payments | Partial | 2 | M-Pesa commerce done; Stripe commerce future |
| 17 | Bookings | Partial | 2 | `bookings/` |
| 18 | Analytics | Done | 6 | `analytics/` |
| 19 | Revenue Attribution | Done | 6 | `campaign_attribution.py`, Pixel |
| 20 | Quality Assurance | Done | 5 | `campaign_qa.py`, `platform_fit.py` |
| 21 | Agency Mode | Partial | 7 | `teams/client_approval.py` |

---

## Sprint order (next 12 weeks)

| Sprint | Weeks | Deliverables |
|--------|-------|--------------|
| **P0** | 1–2 | Single plan billing + pricing UI + campaign terminology |
| **P1a** | 3–4 | `propose_seeds_from_asset` + proposal UI |
| **P1b** | 4–5 | `Campaign` model + campaign approval card |
| **P2a** | 5–6 | Campaign pages `/c/` + default CTAs |
| **P2b** | 6–7 | Commerce page unification (one URL) |
| **P3** | 7–8 | Campaign output spec wired end-to-end |
| **P4** | 8–9 | WA campaign approve + commerce share |
| **P5** | 9–10 | Visible QA score + publish gate |
| **P6** | 10–12 | Campaign-level revenue attribution |

---

## Definition of done — MVP (70% vision)

A Nairobi SME owner can:

1. Pay **KES 1,300/mo** (or trial 5 campaigns)
2. Send a product photo via Snap or WhatsApp
3. See **seed proposals** and pick one (uses 1 of 30 campaigns)
4. Receive **one campaign**: reel + carousel + posts + campaign page
5. Approve in **< 5 minutes** (web or WhatsApp)
6. Publish with CTA to **Kova Commerce / campaign page**
7. Get a lead on WhatsApp, reply with AI draft
8. Receive **M-Pesa payment** linked to campaign
9. See in brief: **“This campaign earned KES X”**
10. Buy **+10 campaigns** if they run out

---

## Open decisions (resolve in Phase 0)

| # | Question | Options |
|---|----------|---------|
| 1 | Trial campaigns | 3 vs 5 vs 7 |
| 2 | Add-on Boost price | KES 400 vs 450 vs 500 |
| 3 | Kling in base plan? | **No** (add-on only) — recommended |
| 4 | Grandfather old tiers? | Auto-migrate vs honor until cancel |
| 5 | Count strategist auto-seeds? | Yes — against campaign quota |
| 6 | Public domain | `app.kova.co.ke` vs `kova.co` short links |

---

## Related docs

| Doc | Purpose |
|-----|---------|
| `MEDIA_PROVIDER_AUDIT.md` | **Photoroom / Bannerbear / Remotion** — full capabilities + Kova implementation map |
| `STRATEGIC_EXECUTION_ROADMAP.md` | Wave history + WA-first guardrails |
| `ONBOARDING_EXPERIENCE.md` | Hire Kova flow |
| `MEDIA_API_SETUP.md` | Photoroom / Fal / Bannerbear env |
| `DESIGN_SYSTEM.md` | v3 growth-first UI |
| `KOVA_BUILD_CHECKLIST.md` | **Authoritative** — pricing, phases, feature status |
| `STRIPE_SETUP_GUIDE.md` | Stripe checkout (`STRIPE_PRICE_KOVA` + add-ons) |
| `KOVA_TESTING_GUIDE.md` | Test procedures and coverage |

---

## Changelog

| Date | Change |
|------|--------|
| 2026-06-25 | Removed legacy `apps/campaigns`, superseded plan docs, dead enforcement code |
| 2026-06-23 | Initial checklist · single-plan pricing KES 1,300 / 30 campaigns · phased build map |
