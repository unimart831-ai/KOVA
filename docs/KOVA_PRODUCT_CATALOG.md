# Kova Product Catalog — What We Sell

**Last updated:** June 2026  
**Audience:** Founders, sales, onboarding, support, investors  
**Authoritative limits:** `apps/billing/models.py` → `PLAN_LIMITS`  
**Plan deep-dive:** `docs/KOVA_PLANS_GUIDE.md`  
**Identity & pitch:** `docs/KOVA_WHAT_WE_ARE.md`  
**Platform GTM order:** `docs/KOVA_PRODUCT_STRUCTURE_AND_PLATFORM_PRIORITY.md`

---

## 1. Purpose of this document

This is the **single product catalog** for Kova Agent: what customers pay for, what each module does, how plans gate access, and what is **live in product vs blocked operationally**.

Use this when:

- Writing landing copy, sales decks, or pilot onboarding scripts
- Deciding what to promise in Wave 1 vs later
- Onboarding a new team member who needs the full product map in one place

**Not duplicated here:** line-by-line limit tables for every plan field — see `KOVA_PLANS_GUIDE.md` and `PLAN_V2_SPEC.md`.

---

## 2. What Kova is (in one page)

### North Star

> **The system that chases money for my business while I run the shop.**

### Category

**Business intelligence operating system for social-led growth** — not a scheduler, not a caption writer.

### Core promise

| Layer | Promise |
|-------|---------|
| **Input** | Describe your business once; connect platforms |
| **Overnight** | Six AI agents research, draft, adapt, and monitor |
| **Morning** | Open the **Daily Brief** — trends, ready posts, engagement queue |
| **Daily habit** | Approve in **Studio** in ~5 minutes |
| **Outcome** | Published content, captured leads, attributed revenue |

### Supporting tagline (marketing)

**Your AI team · Snap to Sell · WhatsApp · M-Pesa — approve in 5 minutes.**

### Default safety model

**Approve-first publishing.** Nothing goes live until the user approves, unless they explicitly enable **auto-approve** (Pro+ only).

---

## 3. Product pillars (what we sell)

Kova is sold as **one connected loop**, not a bundle of unrelated tools:

```
Research → Create → Adapt → Publish → Engage → Measure → Improve
                              ↑                           |
                              └──────── Content DNA ──────┘
```

| Pillar | Customer-facing name | Primary screens |
|--------|---------------------|-----------------|
| **Intelligence** | Daily Brief + Kova Score | Today / Home |
| **Content** | AI Studio + Queue + Calendar | Studio, Queue |
| **Distribution** | Multi-platform publishing | Platforms, Queue |
| **Engagement** | Social + WhatsApp inbox | Engage, WhatsApp |
| **Commerce** | Snap to Sell + public shop | Products, Shop |
| **Growth** | Leads, links, attribution | Leads, Links, QR |
| **Measurement** | Analytics + money proof | Insights, Revenue, Attribution |

---

## 4. Feature catalog (detailed)

Each section describes **what it is**, **how it works**, **user value**, **plan access**, and **code location**.

---

### 4.1 AI Content Studio

**What it is:** The core creation surface. Users submit a content **seed** (idea, prompt, or voice note); Kova generates **one platform-native post per connected account**.

**How it works:**

1. User enters an idea in Studio (or voice campaign flow).
2. **Create Agent** drafts copy in brand voice using profile/onboarding context.
3. **Adapt Agent** (Growth+) reshapes each draft for the target platform (tone, length, format).
4. Posts land in **Pending approval** or **Draft** status.
5. User reviews, edits, approves, and schedules from Studio or post detail.

**Formats supported:**

| Format | Description |
|--------|-------------|
| Text post | Standard feed post |
| Image post | User upload or AI-generated image (Growth+) |
| Carousel | Multi-slide posts with async media build |
| Reel / motion | Video composition pipeline |
| Story | Where platform API supports it |

**User value:** Replaces staring at a blank screen. One idea → multiple ready-to-publish drafts.

**Plan limits (posts / seeds per month):**

| Plan | AI posts/mo | Content seeds/mo |
|------|-------------|------------------|
| Starter | 18 | 8 |
| Growth | 60 | 30 |
| Pro | 150 | 60 |
| Agency | 300 | 120 |

**Code:** `apps/content/`, `apps/agents/create_agent.py`, `apps/agents/adapt_agent.py`

---

### 4.2 Content Queue & Calendar

**What it is:** Pipeline view of all posts by status (draft, pending, scheduled, published, failed) plus a calendar grid for scheduled content.

**How it works:**

- Approved posts enter the queue with a scheduled datetime (AI-suggested “next best time” or manual pick).
- Celery tasks publish via platform providers when due.
- Failures surface with reconnect/rate-limit messaging.

**User value:** One place to see “what’s going out this week” without logging into each network.

**Plan access:** All paid tiers (within post caps).

**Code:** `apps/content/views.py`, `apps/content/tasks.py` (`publish_post`)

---

### 4.3 Daily Brief (retention hook)

**What it is:** The morning dashboard — Kova’s primary **daily habit** surface.

**What it shows:**

- **Kova Score** (0–100 composite health metric; “Day 1 · building baseline” for new users)
- Posts ready for approval
- Performance deltas vs prior period
- Engagement items needing attention
- **Money proof** board (revenue attributed to posts; empty state guides QR/link setup)
- Setup / wedge checklist for new users

**Delivery channels:**

| Channel | Starter | Growth | Pro | Agency |
|---------|---------|--------|-----|--------|
| In-app brief | ✓ | ✓ | ✓ | ✓ |
| Email brief | — | ✓ | ✓ | ✓ |
| WhatsApp brief | — | — | ✓ | ✓ |

**User value:** “Open Kova once a day and know exactly what to do.”

**Code:** `apps/briefs/`, `apps/agents/onboarding_tasks.py` (welcome brief)

---

### 4.4 Six AI Agents

Kova sells **specialized agents**, not one generic chatbot. Each agent has a defined job; outputs feed the next step in the loop.

| Agent | Role | Unlocked |
|-------|------|----------|
| **Create** | Writes original content in brand voice | All plans |
| **Analyst** | Tracks performance; feeds **Content DNA** learning loop | All plans |
| **Research** | Finds trends, competitors, content opportunities | Growth+ |
| **Adapt** | Platform-native adaptation (not copy-paste) | Growth+ |
| **Engage** | Monitors comments/DMs; drafts replies | Growth+ (full); Starter trial only |
| **Strategist (Chief)** | Orchestrates agents; produces Daily Brief | Pro+ |

**Content DNA (compounding intelligence):** The Analyst tracks which attributes (tone, format, hooks, CTAs) correlate with engagement. Create/Adapt consume this over time — **post #50 should outperform post #1**.

**Code:** `apps/agents/` (37+ Python modules)

---

### 4.5 Multi-Platform Publishing

**What it is:** OAuth connect → token management → schedule → publish → read metrics/engagement.

**Platforms — user-facing connect UI (`ACTIVE_PLATFORMS`):**

| Platform | Status in app | Typical use |
|----------|---------------|-------------|
| Facebook | **Active** | Pages, posts, comments, DMs |
| Instagram | **Active** | Reels, carousels, stories, DMs |
| TikTok | **Active** | Short-form video |
| LinkedIn | **Active** | B2B, company pages |
| WhatsApp | **Active** | Business inbox, templates, Status |
| Pinterest | **Active** | Visual discovery pins |
| Bluesky | **Active** | Decentralized social |
| YouTube | Coming soon | Provider built; OAuth pending |
| X (Twitter) | Coming soon | Provider built; OAuth pending |
| Threads | Coming soon | Provider built; OAuth pending |

**Plan account ladder:**

| Plan | Max connected accounts | WhatsApp as channel |
|------|------------------------|---------------------|
| Starter | 2 | No (plan cap) |
| Growth | 4 | Inbox wedge; not full Business tier |
| Pro | 5 | Full WhatsApp Business |
| Agency | 25 | Full |

**GTM wedge order:** WhatsApp → Instagram → Facebook (see platform priority doc).

**Operational note:** Facebook/Instagram **publish + engage** require **Meta App Review** and business verification. Code path exists; production access is paperwork-dependent. See `docs/META_APP_REVIEW_PACKET.md`.

**Code:** `apps/platforms/providers/`, `apps/content/tasks.py`

---

### 4.6 Engagement Inbox (social)

**What it is:** Unified surface for comments, mentions, and DMs across connected Meta platforms (and related providers).

**How it works:**

- Inbox pulls engagement items from platform APIs.
- **Engage Agent** drafts suggested replies (suggest-mode by default).
- User approves, edits, or sends manually.
- Separate tabs: Comments & Mentions, Messages (DMs), Auto-sent log.

**Plan access:**

| Capability | Starter | Growth+ |
|------------|---------|---------|
| Full Engagement Agent | Trial: 5 auto-replies/week | ✓ |
| Engagement inbox UI | Limited trial | ✓ |
| Competitor tracking | — | ✓ |

**User value:** Reply to customers without living in five different apps.

**Code:** `apps/engage/`

---

### 4.7 WhatsApp Business

**What it is:** WhatsApp Cloud API integration — inbox, AI handling, templates, marketing conversations, morning brief delivery.

**Features:**

| Feature | Description |
|---------|-------------|
| **Inbox** | Conversation list + thread view |
| **AI toggle** | Per-conversation AI on/off |
| **Save as lead** | One-click lead creation from chat |
| **Templates** | AI-assisted template authoring |
| **Marketing** | Outbound marketing conversations (capped/month) |
| **Morning brief** | Pro+: brief delivered via WhatsApp |

**Plan access:**

| Capability | Starter | Growth | Pro | Agency |
|------------|---------|--------|-----|--------|
| WhatsApp inbox | — | ✓ | ✓ | ✓ |
| Full WhatsApp Business (`whatsapp_enabled`) | — | — | ✓ | ✓ |
| Marketing convos/mo | 0 | 50 | 300 | 1,000 |

**Operational note:** Requires **WhatsApp Business Platform** setup (WABA, phone number, Meta business verification).

**Code:** `apps/whatsapp/`, `apps/platforms/providers/whatsapp.py`

---

### 4.8 Snap to Sell (Commerce)

**What it is:** Photograph or upload a product → AI generates listing copy, optional polish visuals, public shop page, and social posts to promote it.

**Flow:**

1. **Snap** — camera/upload product photo(s).
2. **AI polish** — studio credits enhance product imagery (Photoroom Plus pipeline).
3. **Catalog** — product saved with title, description, price, category.
4. **Shop** — public storefront (`shop_index.html`) with hero, grid, M-Pesa/WhatsApp CTAs.
5. **Promote** — one-click push to Studio as a post.

**Commerce capabilities:**

| Capability | Starter | Growth | Pro | Agency |
|------------|---------|--------|-----|--------|
| Max products | 5 | 30 | 100 | 500 |
| M-Pesa checkout | — | ✓ | ✓ | ✓ |
| Shopify sync | — | ✓ | ✓ | ✓ |
| CSV import | — | ✓ | ✓ | ✓ |
| Stock tracking | — | ✓ | ✓ | ✓ |
| Studio polish credits/mo | 8 | 30 | 100 | 150 |
| AI images/mo | 0 | 50 | 100 | 200 |

**User value:** “I run a shop on WhatsApp and Instagram — Kova is my back office.”

**Code:** `apps/products/`, `templates/products/public/`

---

### 4.9 Kova Pages & Links (link-in-bio + lead capture)

**What it is:** Branded public pages (link-in-bio style) with tracked links and optional contact/enquiry forms.

**Features:**

- Custom slug pages with brand colors
- Link list with click tracking
- Enquiry forms → **Leads** inbox
- QR codes for offline → online attribution

**Plan limits:**

| Plan | Pages | Links/page | Forms |
|------|-------|------------|-------|
| Starter | 1 | 5 | — |
| Growth | 3 | 20 | ✓ |
| Pro | 10 | 100 | ✓ |
| Agency | 50 | 200 | ✓ |

**Code:** `apps/links/`, `apps/kova_page/`, `apps/qr_attribution/`

---

### 4.10 Leads & Nurture

**What it is:** Pipeline for people who showed interest — from forms, WhatsApp, QR scans, tracked links.

**Lead sources:**

- Kova Page form submissions
- WhatsApp “Save as lead”
- QR / tracked link events
- Walk-in attribution

**Nurture:**

- Multi-step nurture sequences (configure steps, delays, channel)
- Activity timeline per lead
- Lead analytics dashboard

**Plan limits:**

| Plan | Max leads | Edit leads | Email subs | Campaigns/mo | Sequences |
|------|-----------|------------|------------|--------------|-----------|
| Starter | 10 | View only | 50 | 2 | 0 |
| Growth | 100 | ✓ | 2,500 | 10 | 3 |
| Pro | 5,000 | ✓ | 25,000 | 30 | 10 |
| Agency | 10,000 | ✓ | 100,000 | 50 | 20 |

**Code:** `apps/leads/`

---

### 4.11 Analytics & Revenue Attribution

**What it is:** Performance dashboards plus Kova’s **money proof** differentiator — tying social activity to revenue.

**Modules:**

| Module | What it shows |
|--------|---------------|
| **Insights** | Per-platform performance, top posts, filters |
| **Revenue dashboard** | Conversion funnel: clicks → leads → sales |
| **Attribution** | Multi-touch path (Pro+); PDF export |
| **Money board (Today)** | Which posts drove paying customers |
| **Kova Pixel** | Website tracking script (Pro+ for full unlock) |

**Attribution mechanics:**

- QR codes at counter / packaging
- Tracked short links on posts
- Walk-in events linked to campaigns

**Plan access:**

| Capability | Starter | Growth | Pro |
|------------|---------|--------|-----|
| Revenue dashboard | ✓ | ✓ | ✓ |
| Multi-touch attribution | — | — | ✓ |

**Code:** `apps/analytics/`, `apps/qr_attribution/`

---

### 4.12 Memes & Trend Intelligence

**What it is:** Kenyan/regional trend scanning + meme adaptation for brand-safe viral content.

**Flow:**

1. **Discover** — ranked trending memes filtered by industry fit.
2. **Adapt** — one-click brand remix.
3. **Queue** — review adapted memes; approve → send to Studio.
4. **Trend alerts** — proactive alerts when trends match business profile.
5. **Settings** — risk tolerance, excluded categories, auto-queue threshold.

**Plan access:** **Pro+ only** (`memes_enabled: true`).

**Code:** `apps/memes/`

---

### 4.13 Calendar Intelligence

**What it is:** Proactive content calendar support — holidays, industry moments, custom events.

**Features:**

- Kenyan holidays & industry moments surfaced in Studio
- **Custom moments** (anniversaries, launches)
- **Moment packs** — pre-drafted content bundles for upcoming events
- Holiday refine settings per event type

**Plan access:** All plans (generation still consumes post/seed caps).

**Code:** `apps/calendar_intel/`

---

### 4.14 Campaigns

**What it is:** Coordinate content seeds and email campaigns under one named campaign with lifecycle (draft → active → complete).

**Use case:** Product launch, seasonal promo, event — link multiple posts and one email blast.

**Plan limits:** Starter 2 · Growth 5 · Pro 15 · Agency 25 campaigns.

**Code:** `apps/campaigns/`

---

### 4.15 Profile Audit

**What it is:** AI scans connected social profiles and suggests improvements (bio, links, completeness).

**Flow:** Run audit → suggestion rows → one-click **Apply to [platform]** or dismiss.

**Plan access:** All plans.

**Code:** `apps/profile_audit/`

---

### 4.16 Teams & Collaboration

**What it is:** Multi-seat workspace with roles and approval workflows for agencies and small teams.

**Plan access:**

| Plan | Team seats | Auto-approve publishing |
|------|------------|-------------------------|
| Starter | 0 | — |
| Growth | 0 | — |
| Pro | 5 | ✓ |
| Agency | 25 | ✓ |

**Code:** `apps/teams/`

---

### 4.17 Additional modules (built, secondary GTM)

These exist in product but are not primary Wave 1 selling points:

| Module | Purpose | Notes |
|--------|---------|-------|
| **Email marketing** | Lists, campaigns, sequences | Caps per plan; Resend backend |
| **Bookings** | Appointment links + calendar | Available; not plan-gated heavily |
| **Reviews** | Review request workflow | Secondary |
| **Media queue** | Bulk media processing pipeline | Power-user / ops |
| **Command center** | Standup, moments, listen views | Internal/strategist UX |
| **Partners / Campus Rep** | Referral & campus program | Separate GTM track |
| **Help / Learn** | In-app help articles | Support surface |

---

## 5. Pricing & plans (summary)

**Billing methods:** M-Pesa STK Push (Kenya primary) · Stripe (international)  
**Trial:** 7-day Starter trial on signup — no payment required  
**Enforcement:** Hard caps at 100% of any limit; no silent overages

| Plan | Kenya name | Intl name | KES/mo | USD/mo | Checkout |
|------|------------|-----------|--------|--------|----------|
| `starter` | Jipange | Starter | 499 | 4 | Self-serve |
| `growth` | Kazi | Growth | 1,499 | 11 | Self-serve |
| `pro` | Biashara | Pro | 2,999 | 22 | Self-serve |
| `agency` | Wakala | Agency | 7,999 | 59 | **Sales only** |

### Who each plan is for

| Plan | Ideal customer | Core unlock |
|------|----------------|-------------|
| **Starter** | Solopreneur testing social consistency | Brief + Studio + 2 platforms + basic analytics |
| **Growth** | Growing brand ready to sell online | M-Pesa commerce, engagement, AI images, 4 platforms |
| **Pro** | Serious marketer / small team | All 6 agents, WhatsApp Business, teams, memes, attribution |
| **Agency** | Multi-client operator | 25 accounts, 300 posts, 25 seats, sales onboarding |

Full limit tables: **`docs/KOVA_PLANS_GUIDE.md`**

---

## 6. Feature × plan matrix (quick reference)

| Feature | Starter | Growth | Pro | Agency |
|---------|:-------:|:------:|:---:|:------:|
| Daily Brief (in-app) | ✓ | ✓ | ✓ | ✓ |
| AI Studio + Queue | ✓ | ✓ | ✓ | ✓ |
| Create + Analyst agents | ✓ | ✓ | ✓ | ✓ |
| Research + Adapt agents | — | ✓ | ✓ | ✓ |
| Engage agent (full) | Trial | ✓ | ✓ | ✓ |
| Strategist agent | — | — | ✓ | ✓ |
| AI image generation | — | ✓ | ✓ | ✓ |
| M-Pesa commerce | — | ✓ | ✓ | ✓ |
| WhatsApp inbox | — | ✓ | ✓ | ✓ |
| WhatsApp Business (full) | — | — | ✓ | ✓ |
| Memes & trends | — | — | ✓ | ✓ |
| Multi-touch attribution | — | — | ✓ | ✓ |
| Team seats | — | — | 5 | 25 |
| Auto-approve publish | — | — | ✓ | ✓ |
| A/B testing | — | ✓ | ✓ | ✓ |
| Competitor tracking | — | ✓ | ✓ | ✓ |

---

## 7. The daily user loop (what we train customers to do)

This is the **habit Kova is designed around**:

```
Morning  → Open Daily Brief (Today)
           Review Kova Score, money proof, posts pending

5 min    → Studio: approve / edit / reject generated posts
           Optional: Engage inbox for flagged replies

Done     → Queue publishes on schedule
           Analyst updates Content DNA overnight
```

**Onboarding wow moment:** After setup, user sees **real generated post previews** on completion screen and a welcome brief with accurate `posts_pending` count.

---

## 8. Differentiation (what we say vs competitors)

| vs | They give you | Kova gives you |
|----|---------------|----------------|
| **Buffer / Hootsuite** | Blank scheduler | AI team + daily brief + approve-first loop |
| **ChatGPT / Jasper** | Generic text | Platform-native posts + learning loop + publish path |
| **Linktree** | Static link page | Tracked links + forms + attribution + shop |
| **WhatsApp-only tools** | Chat | Chat + content + commerce + analytics in one OS |
| **US-priced tools ($49–99/mo)** | Same features, USD pricing | Same AI power from **KSh 499/mo** + M-Pesa |

**Moats we sell (when true in production):**

1. **Compounding intelligence** — Content DNA improves over time  
2. **Africa-native stack** — M-Pesa, WhatsApp-first, KES pricing  
3. **Offline → online loop** — QR at counter → attributed sale → post that drove it  
4. **Approve in 5 minutes** — automation with human control  

---

## 9. Launch readiness & honest caveats

**Infrastructure:** Production-deployed (Railway, PostgreSQL, Redis, Celery, R2 media, Sentry).

**Product code:** Feature modules above are implemented and plan-gated in middleware.

**Operational blockers before full customer promise:**

| Blocker | Impact | Doc |
|---------|--------|-----|
| Meta App Review | FB/IG publish, engage, insights for real customer pages | `META_APP_REVIEW_PACKET.md` |
| WhatsApp Business setup | WABA, templates, marketing sends | Meta Business + WABA docs |
| Company registration | Required for Meta business verification | Operational |
| Pilot users | Playbook test accounts; not yet broad paid cohort | `PILOT_WAVE1_PLAYBOOK.md` |

**Do not over-promise in sales until:**

- Customer has connected platforms that are **approved for their use case**
- Meta/WhatsApp paperwork is complete for **their** business (or Kova’s app is live in production mode)

**Readiness check:** `python manage.py pilot_smoke` (+ `--live` when credentials exist)

---

## 10. Sales demo order (recommended)

When showing the product live, follow this sequence (matches `KOVA_WHAT_WE_ARE.md`):

1. **Daily Brief (Today)** — morning habit, Kova Score, money proof  
2. **Studio** — real drafts, batch approve, platform badges  
3. **Queue / Calendar** — scheduled pipeline  
4. **By pain:** Engage · Products (Snap) · Leads · Analytics · WhatsApp  

Close with: **7-day trial → connect wedge platform (IG or WhatsApp) → onboarding posts ready before setup finishes.**

---

## 11. Cost economics — math at your fingertips

**Live dashboard:** Admin → **Cost Economics** → tabs **Overview · Spend Ledger · Price Catalog · Unit Economics**

**Code registry:** `apps/billing/cost_registry.py` · **Full reference:** `docs/KOVA_COST_LEDGER.md`

| Feature area | What costs money | Typical unit | Where capped |
|--------------|------------------|--------------|--------------|
| Social agents | LLM tokens (OpenRouter) | $0–$0.88/user/mo | `daily_llm_tokens` |
| Snap to Sell | Vision + LLM + **Photoroom** | ~$0.30–1.00/snap | `visual_enhancements_per_month` |
| Post images | Together FLUX | $0.025–0.04/image | `ai_images_per_month` |
| Voice Campaign | Whisper + LLM | ~$0.002/min + tokens | Plan voice usage |
| WhatsApp marketing | Meta per conversation | ~$0.049/convo | `whatsapp_marketing_conversations_per_month` |
| Email | Resend | Free 100/day; then ~$0.0004/email | Subscriber limits |
| Research | Tavily search | 1000/mo free | Growth+ only |
| Hosting | Railway + R2 | $20–80/mo platform | — |

**Dominant variable costs at scale:** Photoroom studio polish, FLUX images, WhatsApp marketing — not LLM tokens (when on free/DeepSeek stack).

---

## 12. Related documents

| Document | Use when |
|----------|----------|
| `KOVA_WHAT_WE_ARE.md` | Voice, pitch, objection handles |
| `KOVA_PLANS_GUIDE.md` | Every numeric limit per plan |
| `PLAN_V2_SPEC.md` | Pricing philosophy & tier design |
| `KOVA_PRODUCT_STRUCTURE_AND_PLATFORM_PRIORITY.md` | What to ship first; platform wedge |
| `META_APP_REVIEW_PACKET.md` | Meta submission |
| `KOVA_FINANCIAL_AUDIT.md` | Unit economics & metering |
| `KOVA_COST_LEDGER.md` | **Every cost line — formulas & admin Spend Ledger** |
| `COST_ANALYSIS.md` | Scenario modeling & break-even |
| `STRATEGIC_MONOPOLY_PLAN.md` | Long-term moat roadmap |
| `PILOT_WAVE1_PLAYBOOK.md` | 30-day pilot execution |

---

## 13. Maintenance

When product or pricing changes:

1. Update `PLAN_LIMITS` in `apps/billing/models.py`
2. Sync **`apps/billing/cost_registry.py`** if a new paid API is added
3. Sync this catalog’s **summary tables** if positioning shifts
3. Update `KOVA_PLANS_GUIDE.md` for full limit detail
4. Update landing/pricing templates if customer-facing copy changes

**Source of truth for numbers:** always `PLAN_LIMITS`, not this markdown file.

---

*Kova Agent — Your AI team handles social media. You approve in 5 minutes.*
