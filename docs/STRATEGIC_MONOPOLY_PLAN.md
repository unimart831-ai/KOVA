# Kova — Strategic Monopoly Plan: The 3-Pillar Closed Loop

> **Mission:** Make Kova the undisputed Business Intelligent Operating System for African SMEs —
> where Social Media, Commerce, and Leads form an unbreakable flywheel that no competitor can replicate.

---

## The Closed Loop Vision

```
┌─────────────────────────────────────────────────────────────────┐
│                     THE KOVA FLYWHEEL                            │
│                                                                 │
│   ┌──────────┐      Content drives       ┌──────────────┐      │
│   │  SOCIAL  │ ─────────────────────────► │   COMMERCE   │      │
│   │  MEDIA   │                            │              │      │
│   │          │ ◄───────────────────────── │              │      │
│   └──────────┘      Products fuel posts   └──────────────┘      │
│        │                                         │              │
│        │ Engagement                    Purchases │              │
│        │ captures                      convert   │              │
│        ▼                                         ▼              │
│   ┌──────────────────────────────────────────────────┐          │
│   │                    LEADS                          │          │
│   │  (Every interaction becomes a relationship)      │          │
│   └──────────────────────────────────────────────────┘          │
│        │                                                        │
│        │ Nurture sequences → Repeat purchases → More content    │
│        └────────────────────────────────────────────────────────┘
│                                                                 │
│   Each revolution makes the next one faster + smarter.          │
│   AI learns from every cycle. No manual work required.          │
└─────────────────────────────────────────────────────────────────┘
```

**Why this is monopoly-grade:** Competitors offer pieces (Buffer = scheduling, Shopify = commerce, HubSpot = CRM). Kova is the ONLY platform where:
1. A product photo becomes a social post AND a commerce page AND captures a lead — in ONE action
2. AI learns from sales data to improve content, from engagement to qualify leads, from leads to recommend products
3. The entire loop runs on autopilot without the user touching anything after initial setup

---

## Current State Assessment

### Pillar 1: Social Media Management — Score: 8.5/10

**What's world-class:**
- Full AI pipeline: seed → multi-platform posts → scheduling → publish → metrics → learning
- 10 platforms connected with robust OAuth + token lifecycle
- Create/Adapt/Engage/Strategist/Analyst/Research agents — a full AI agency
- Autopilot with weekly planning, voice-to-campaign, A/B testing
- Content DNA extraction + performance prediction validation

**Critical gaps:**
- Video content is FFmpeg-composed from statics — no native product video generation
- TikTok/Pinterest engagement is zero (can't fetch comments)
- No unified DM inbox across platforms
- Media Queue is images-only, no video drip
- WhatsApp not in main content publish flow

### Pillar 2: Commerce — Score: 7/10

**What's world-class:**
- Snap2sell: phone photo → professional listing + social content in < 60 seconds
- Photoroom Plus with 30+ AI scene variants, category-aware selection
- Batch Snap (Market Day) with voice brief + stall intelligence
- Public shop with mobile-optimized M-Pesa checkout
- Commerce Autopilot: snap → approve → post → sell — zero touch

**Critical gaps:**
- No product variants/SKUs (size/color picker on shop)
- Single-item checkout only — no cart
- No Order/fulfillment model (payment = only record of sale)
- Services and digital products can't use M-Pesa checkout
- No seller payout/settlement system
- No dynamic pricing or discount/coupon system

### Pillar 3: Leads — Score: 5.5/10

**What's world-class:**
- Form → Lead signal with auto-scoring, temperature, priority
- WhatsApp auto-lead on first contact + commerce bot
- Lead nurture sequences (email + tag + status) on Celery beat
- Email marketing stack (subscribers, campaigns, AI-generated drips)
- Attribution dashboard: social → clicks → leads → sales

**Critical gaps:**
- Commerce purchases DON'T create leads (massive hole in the loop!)
- Bookings DON'T create leads
- QR scans/walk-ins DON'T create leads
- Three parallel nurture systems that don't talk to each other
- No lead import or public API
- Email engagement not reflected on lead timeline
- WhatsApp leads use synthetic emails — can't receive email marketing

---

## MONOPOLY-GRADE FEATURES

### Feature 1: "Every Buyer Becomes a Lead" (Loop Closer)

**The gap:** Currently, a buyer pays via M-Pesa → gets a receipt → disappears. The seller has no CRM record.

**The fix:**
```
Commerce Payment → Lead (auto-created)
Booking Confirmed → Lead (auto-created)
QR Scan → Lead (auto-created)
Walk-In → Lead (auto-created)
Engage DM → Lead (auto-created)
```

**Why monopoly-grade:** No social media tool captures buyers as CRM leads. No commerce tool creates social content from sales patterns. Kova does BOTH — every purchase teaches the AI what to post next, and every lead gets nurtured back to buy again.

**Implementation:**
- Signal on `CommercePayment.status = completed` → `create_or_update_lead()`
- Signal on `Booking.status = confirmed` → `create_or_update_lead()`
- Bridge `QRScan` and `WalkInEvent` to Lead model
- Engage Agent: when DM/comment shows purchase intent → create Lead with `source=social_dm`
- Unified Lead timeline shows commerce events, booking events, social interactions

---

### Feature 2: "AI Product Video" (Photoroom Video API)

**The gap:** Reels/TikTok are the #1 growth channel. Kova currently composes basic motion from static images via FFmpeg. Competitors require users to edit video manually.

**The fix:** Integrate Photoroom's Video API (`/v1/animate`) to generate professional product videos from the SAME photos used in Snap2sell.

**Flow:**
```
User snaps product photo(s)
  → Photoroom generates studio stills (existing)
  → Photoroom generates 3-5 second product video (NEW)
  → Create Agent writes reel caption + hooks
  → Auto-publish to IG Reels, TikTok, YouTube Shorts, FB Reels
```

**Why monopoly-grade:** No other social tool auto-generates video from a product photo. The user takes ONE photo and gets: carousel + reel + commerce page + WhatsApp catalog image. This is 10x faster than any competitor.

**Implementation:**
- New `photoroom_video.py` module calling `/v1/animate`
- Integrate into `expand_product_photos()` pipeline (after stills)
- Store video URL on Product `promo_video` field or as MediaAttachment
- Reel composer uses Photoroom video instead of FFmpeg slideshow
- Plan-gate: Growth+ only (video credits are expensive)

---

### Feature 3: "Virtual Model Studio" (Fashion Dominance)

**The gap:** Fashion/apparel is the #1 SME category in Africa. Sellers photograph flat clothes on floors/tables. Professional model photography costs $500+ per shoot.

**The fix:** One flat-lay photo → multiple AI model shots with diverse African models wearing the product.

**Flow:**
```
User uploads garment photo
  → Photoroom Virtual Model API generates:
    • Model A (female, dark skin, confident pose, urban scene)
    • Model B (male, casual pose, studio background)
    • Model C (lifestyle scene — market/street/event)
  → Carousel: Model shots + flat lay + price
  → Commerce page: Model hero image
  → Instagram: Multiple post angles from one product
```

**Why monopoly-grade:** No competitor offers AI model generation FOR African sellers with African models in African contexts. This eliminates the entire photography industry for fashion SMEs. One photo = entire product campaign.

**Implementation:**
- New variant in `photoroom_plus.py`: `virtual_model` category
- Model presets tuned for African diversity (skin tones, body types, scenes)
- Category detection: if `apparel/fashion` → auto-include virtual model variants
- Carousel composer uses model shots as hero slides
- Public shop: model image as primary, flat lay as gallery

---

### Feature 4: "Promo Engine" (Photoroom Templating)

**The gap:** Sellers want to run sales, announce new arrivals, and create promotional graphics. Currently they need Canva. Kova generates text posts but not visual promo creatives with prices/CTAs baked into the image.

**The fix:** Use Photoroom's Templating Mode to auto-generate branded promotional images with:
- Product photo (background-removed)
- Price overlay
- CTA text ("Order Now", "Limited Stock", "New Arrival")
- Brand colors + logo
- Platform-optimized sizing

**Flow:**
```
Trigger: New product / Low stock / Restock / Sale price / Holiday
  → Kova selects appropriate promo template
  → Photoroom renders: product + price + CTA + brand colors
  → Auto-scheduled as social post + WhatsApp status + commerce banner
  → COST: $0.10 (one API call does everything)
```

**Why monopoly-grade:** This is "Canva on autopilot" — the user NEVER opens a design tool. Promotional content is generated automatically based on business events (new stock, low stock, holiday, sale). No competitor auto-generates branded promotional creatives from business triggers.

**Implementation:**
- Create Photoroom template library (10-15 promo templates per category)
- New `promo_engine.py` module with trigger → template → render pipeline
- Triggers: product_created, low_stock, restocked, price_changed, holiday_detected
- Template injection: product image, name, price, CTA, brand palette
- Output: 1080x1080 (feed), 1080x1920 (story), 1200x628 (ad)

---

### Feature 5: "Commerce WhatsApp Bot" (Conversational Commerce)

**The gap:** WhatsApp is the #1 communication channel in Africa. Kova has AI replies but no structured product browsing/ordering via WhatsApp. Buyers want to browse and buy without leaving WhatsApp.

**The fix:** Full conversational commerce flow within WhatsApp:

```
Buyer: "Hi, do you have shoes?"
Kova Bot: [Product carousel] "Here are our available shoes:"
  • Nike Air Max - KES 4,500 [View] [Buy]
  • Adidas Ultra - KES 3,800 [View] [Buy]
Buyer: [clicks Buy on Nike]
Kova Bot: "Great choice! Send M-Pesa to shortcode XXX"
Kova Bot: [Payment confirmed] "Receipt #12345. Delivery in 2-3 days."
  → Lead created + tagged "buyer"
  → Stock decremented
  → Seller notified
  → Follow-up sequence enrolled
```

**Why monopoly-grade:** This combines WhatsApp (Africa's #1 app) + AI + Commerce + Leads in a single conversation. No competitor offers AI-powered conversational commerce that automatically captures leads and triggers nurture. This is Africa's equivalent of Shopify Inbox + HubSpot + ChatGPT in one.

**Implementation:**
- Extend `apps/whatsapp/commerce.py` state machine with:
  - Product search/browse (interactive message templates)
  - Cart builder (WhatsApp list messages)
  - M-Pesa payment initiation from chat
  - Order confirmation + tracking
- Every WhatsApp sale → Lead with `source=whatsapp`, enriched with purchase history
- Post-purchase: auto-enroll in review request + cross-sell sequence

---

### Feature 6: "Smart Lead Scoring + AI Nurture Unification"

**The gap:** Three disconnected nurture systems (Lead sequences, Email sequences, WhatsApp broadcasts). No intelligent scoring that uses commerce + social + engagement data together.

**The fix:** Unified Lead Intelligence Engine:

```
Lead Score = f(
  social_engagement,      ← from Engage Agent
  commerce_purchases,     ← from CommercePayment
  email_opens_clicks,     ← from EmailLog
  whatsapp_conversations, ← from WhatsApp
  booking_history,        ← from Bookings
  page_visits,            ← from Pixel
  time_since_last_action
)
```

**Unified Nurture Router:**
- Score triggers the BEST channel (not all channels):
  - High WhatsApp engagement → nurture via WhatsApp
  - High email engagement → nurture via email
  - Neither → retarget via social content (post specifically for them)
- AI picks the message content based on lead's purchase history + browsing + social interactions

**Why monopoly-grade:** HubSpot scores leads. Mailchimp sends emails. Neither uses social media engagement + commerce data + WhatsApp behavior to score leads and pick the optimal channel. Kova's AI knows more about each lead than any single-pillar tool.

---

### Feature 7: "AI Edit with Instructions" (Seasonal/Contextual Variants)

**The gap:** Products look the same year-round. During holidays, events, and seasons, sellers need to update product imagery (add festive elements, change backgrounds, seasonal staging).

**The fix:** Use Photoroom's "Edit With AI" to auto-generate seasonal product variants:

```
December → "Add Christmas decorations around product"
Valentine's → "Place product with roses and hearts"  
Eid → "Add crescent moon and lanterns"
Mashujaa Day → "Kenyan flag colors in background"
```

**Flow:**
- Calendar Intel detects upcoming holiday/event
- For sellers with active products in relevant categories
- Auto-generate seasonal variants of top products
- Schedule seasonal posts with updated imagery
- Revert to standard after event passes

**Why monopoly-grade:** Zero-effort seasonal marketing. The seller does NOTHING. Kova's AI knows what holidays are coming, generates themed product content, and reverts after. No competitor offers automatic seasonal product photography.

---

## PHOTOROOM INTEGRATION MAP

### Current Usage (Already Implemented)

| Feature | Photoroom API | Where in Kova |
|---------|--------------|---------------|
| Background removal | `v2/edit` outputSize + bg.color | `photoroom.py` → Snap pipeline |
| AI Scene Generation | `v2/edit` background.prompt | `photoroom_plus.py` → 30+ variants |
| Shadow types | `v2/edit` shadow.mode | Brand template per industry |
| Padding/scaling | `v2/edit` padding + scaling | Preflight + brand template |
| Batch processing | Sequential API calls | Batch Snap pipeline |
| Channel exports | Resize + format | Story (9:16), banner (16:9) |

### New Integrations (To Implement)

| Feature | Photoroom API | Kova Use Case | Priority |
|---------|--------------|---------------|----------|
| **Product Video** | `/v1/animate` | Reels/TikTok from product photos | P0 |
| **Virtual Models** | `v2/edit` virtualModel params | Fashion seller model shots | P0 |
| **Promo Templates** | Template Mode + text layers | Auto promotional creatives | P1 |
| **Edit With AI** | `v2/edit` editPrompt | Seasonal variants, color changes | P1 |
| **Text-to-Image** | `/v1/create` (no input image) | Background assets, brand graphics | P2 |
| **Ghost Mannequin** | `v2/edit` with mannequin detection | Fashion catalog consistency | P2 |
| **Flat Lay** | `v2/edit` flatLay mode | Apparel lifestyle alternatives | P2 |
| **Deterministic Shadows** | Shadow 2026-04-15 model params | Catalog visual consistency | P3 |

### Cost Optimization Strategy

| Principle | Implementation |
|-----------|---------------|
| One call = one credit | Chain ALL edits (bg + shadow + resize + lighting) in single request |
| Preflight validation | Don't burn credits on blurry/dark/tiny images |
| Plan-tiered variants | Starter: 2 variants, Growth: 5, Pro: 10, Agency: 20 |
| Smart variant selection | Category-aware — don't generate fashion variants for food |
| Credit pooling | Platform-wide pool with per-user caps prevents one seller draining budget |
| Video credits separate | Enterprise pricing for `/v1/animate` — gate to Growth+ |

---

## IMPLEMENTATION ROADMAP

### Phase 1: Close the Loop (2 weeks)
> Every commerce/booking/QR action creates a Lead

- [ ] Commerce Payment → Lead bridge (signal + task)
- [ ] Booking → Lead bridge
- [ ] QR/Walk-in → Lead bridge  
- [ ] Engage DM purchase intent → Lead
- [ ] Unified Lead timeline (commerce events, bookings, social)
- [ ] Lead analytics updated with commerce conversion data

### Phase 2: Visual Monopoly (3 weeks)
> Photoroom Video + Virtual Models + Promo Engine

- [ ] Product Video generation via `/v1/animate`
- [ ] Reel pipeline upgraded: Photoroom video → social publish
- [ ] Virtual Model integration for fashion/apparel category
- [ ] Model diversity presets (African market)
- [ ] Promo Engine: template library + trigger system
- [ ] Seasonal variant generation (Calendar Intel → Edit With AI)

### Phase 3: Conversational Commerce (2 weeks)
> WhatsApp becomes a full shopping channel

- [ ] Product browsing via WhatsApp interactive messages
- [ ] In-chat M-Pesa payment flow
- [ ] Order confirmation + tracking messages
- [ ] WhatsApp sale → Lead + nurture enrollment
- [ ] Review request via WhatsApp after purchase

### Phase 4: Intelligent Nurture (2 weeks)
> Unified scoring + channel-aware nurture

- [ ] Composite lead score (social + commerce + email + WhatsApp + pixel)
- [ ] Channel preference detection per lead
- [ ] Unified nurture router (best channel selection)
- [ ] Cross-channel sequence builder (email step → WhatsApp step → social retarget)
- [ ] Nurture performance dashboard

### Phase 5: Platform Engagement Expansion (1 week)
> Close TikTok/Pinterest/Bluesky engagement gaps

- [ ] TikTok comment fetching + Engage coverage
- [ ] Pinterest engagement basics
- [ ] Bluesky reply/comment support
- [ ] Unified DM inbox (consolidate FB/IG/Twitter DMs with WhatsApp)

---

## COMPETITOR COMPARISON AFTER IMPLEMENTATION

| Capability | Buffer | Hootsuite | Shopify | HubSpot | Kova |
|-----------|--------|-----------|---------|---------|------|
| Multi-platform scheduling | ✅ | ✅ | ❌ | ❌ | ✅ |
| AI content generation | ❌ | Basic | ❌ | Basic | ✅ Full agency |
| Product → post pipeline | ❌ | ❌ | Plugin | ❌ | ✅ Zero-touch |
| AI product photography | ❌ | ❌ | ❌ | ❌ | ✅ 30+ variants |
| AI product video | ❌ | ❌ | ❌ | ❌ | ✅ Auto-reels |
| Virtual models | ❌ | ❌ | ❌ | ❌ | ✅ |
| Mobile commerce | ❌ | ❌ | ✅ | ❌ | ✅ M-Pesa native |
| WhatsApp commerce | ❌ | ❌ | ❌ | ❌ | ✅ |
| Lead scoring | ❌ | ❌ | ❌ | ✅ | ✅ Multi-signal |
| Social → Lead capture | ❌ | ❌ | ❌ | Partial | ✅ Auto |
| Auto-nurture | ❌ | ❌ | ❌ | ✅ | ✅ Channel-aware |
| Seasonal auto-content | ❌ | ❌ | ❌ | ❌ | ✅ |
| Receipt-to-restock | ❌ | ❌ | ❌ | ❌ | ✅ |
| Promo auto-generation | ❌ | ❌ | ❌ | ❌ | ✅ |

**The monopoly columns:** AI product video, virtual models, WhatsApp commerce, seasonal auto-content, receipt-to-restock, and promo auto-generation are features NO competitor offers. Combined in one platform with the closed loop, Kova becomes irreplaceable.

---

## THE MOAT

1. **Data Flywheel:** Every cycle (post → sell → lead → nurture → repeat) generates data that makes the AI smarter. Competitors starting today would need years of African SME behavior data.

2. **Photoroom Infrastructure:** Deep API integration with 30+ variant catalog, brand templates, preflight, and cost management. Replicating this takes 6+ months of engineering.

3. **WhatsApp-First:** Built for Africa's #1 platform from day one. Western competitors retrofit WhatsApp as an afterthought.

4. **M-Pesa Native:** Payment infrastructure built for the dominant African payment method. Stripe/PayPal competitors don't work here.

5. **Segment Intelligence:** Business mode detection (merchant/service/digital/expert) means the AI adapts its ENTIRE behavior — not just templates, but which agents run, what content types are generated, what commerce features are enabled.

6. **Zero-Touch Operations:** The complete autopilot (Snap → studio → schedule → publish → engage → analyze → adapt) means the user can run their entire digital presence from their phone while selling at a market stall.

---

*This document defines where Kova must go. Each phase builds on the previous. Phase 1 closes the most critical gap (loop completion). Phase 2 creates visual moat. Phase 3 captures Africa's commerce channel. Phase 4 makes every lead intelligent. Phase 5 fills platform gaps.*

*After all 5 phases: No competitor can match Kova without building ALL of this simultaneously — which would take 18-24 months and $5M+ in engineering investment.*

---

*Last updated: May 29, 2026*
