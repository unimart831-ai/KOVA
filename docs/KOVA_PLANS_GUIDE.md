# Kova Subscription Plans — Complete Guide

**Last updated:** May 2026  
**Authoritative limits:** `apps/billing/models.py` → `PLAN_LIMITS`  
**Pricing spec:** `docs/PLAN_V2_SPEC.md`

This guide explains what each Kova plan includes, what it costs, and what you can and cannot do on each tier. It is written for founders, sales, and customers. All numeric limits match the current Plan v2 configuration.

---

## 1. Introduction

**Kova Agent** is an AI-powered social media and commerce workspace for Kenyan and global small businesses. Instead of staring at a blank screen, you describe your business once; Kova’s AI agents research trends, draft posts, adapt content per platform, monitor engagement, and deliver a daily brief — you approve in minutes.

### How plans work

Kova offers **four subscription tiers**:

| Internal name | Customer name (Kenya) | Customer name (international) |
|---------------|----------------------|------------------------------|
| `starter` | **Jipange** | **Starter** |
| `growth` | **Kazi** | **Growth** |
| `pro` | **Biashara** | **Pro** |
| `agency` | **Wakala** | **Agency** |

Three tiers (**Starter**, **Growth**, **Pro**) are available via **self-serve checkout**. **Agency** is **sales-only** and requires explicit approval before checkout.

Each plan defines:

- How many social accounts, posts, and content seeds you can use per month
- Which AI agents and product modules are unlocked
- Caps on AI tokens, studio polish credits, AI images, and WhatsApp marketing conversations
- Limits on leads, products, email, team seats, and Kova Link pages

When you hit **100% of any cap**, the action is **blocked** with an upgrade message. There are no automatic overage charges — limits are hard stops.

### Billing

| Method | Who it’s for | How it works |
|--------|--------------|--------------|
| **M-Pesa** | Kenya | STK Push to your Safaricom number; instant activation after PIN confirmation |
| **Stripe** | International | Card checkout via Stripe; includes the 7-day trial on first signup |

Prices below are the **default monthly** amounts. Admins may override `price_kes` / `price_usd` via the `PlanPrice` database table; limits always come from `PLAN_LIMITS`.

Discount codes can reduce checkout price on eligible plans.

### Free trial

Every **new account** gets a **7-day free trial**:

- **No payment required** to start (no credit card for M-Pesa; Stripe trial included where available)
- Trial users receive **Starter-tier limits**, not full Growth limits
- Label in the app: **“Starter trial”**
- After the trial, choose a paid plan or access is restricted until you subscribe

---

## 2. Plan comparison at a glance

| | **Starter / Jipange** | **Growth / Kazi** | **Pro / Biashara** | **Agency / Wakala** |
|---|:---:|:---:|:---:|:---:|
| **Price (KES/mo)** | 499 | 1,499 | 2,999 | 7,999 |
| **Price (USD/mo)** | 4 | 11 | 22 | 59 |
| **Public checkout** | Yes | Yes | Yes | No — contact sales |
| **Who it’s for** | Solopreneurs getting started | Growing brands | Serious marketers & small teams | Agencies managing multiple clients |
| **Social accounts** | 2 | 4 (no WhatsApp) | 5 (all platforms + WhatsApp) | 25 |
| **Posts / month** | 18 | 60 | 150 | 300 |
| **Content seeds / month** | 8 | 30 | 60 | 120 |
| **AI agents** | 2 | 4 | 6 | 6 |
| **Daily LLM tokens** | 50K | 200K | 500K | 2M |
| **Monthly LLM tokens** | 1M | 4M | 10M | 40M |
| **Studio polish / month** | 8 | 30 | 100 | 150 |
| **AI images / month** | 0 | 50 | 100 | 200 |
| **WhatsApp Business** | No | No | Yes | Yes |
| **WhatsApp marketing convos / month** | 0 | 50 | 300 | 1,000 |
| **Team members** | 0 | 0 | 5 | 25 |
| **Max campaigns** | 2 | 5 | 15 | 25 |

**Platforms (channel ladder):** Facebook, Instagram, TikTok, LinkedIn, and WhatsApp. Starter connects **2** accounts; Growth connects **4** (WhatsApp excluded); Pro and Agency connect **5** including WhatsApp as a channel.

---

## 3. Per-plan deep dives

---

### Starter / Jipange — KSh 499 / $4 per month

**Positioning:** For solopreneurs getting organized. The lowest-cost way to let Kova draft content and deliver a daily brief while you stay in control of publishing.

#### Channels & publishing

| Capability | Limit / access |
|------------|----------------|
| Social accounts | **2** (e.g. Instagram + Facebook) |
| AI posts per month | **18** |
| Content seeds per month | **8** (ideas you submit for the AI to expand) |
| Queue & calendar | Yes — review, edit, and schedule before publish |
| Content Autopilot | Available within post/seed caps; weekly plans land in Studio for approval unless you enable auto-publish settings on higher tiers |
| Auto-approve publishing | **No** — you approve every post |

#### Create & Studio

| Capability | Access |
|------------|--------|
| AI agents | **2:** Content Creator + Analytics Agent |
| AI image generation | **No** — upload your own images |
| Studio polish (Photoroom Plus) | **8 credits/month**; up to **3** scene variants per product |
| Premium studio polish | No |
| Carousels & motion reels | Unlimited format creation within post cap |
| Memes & trend intelligence | **No** |
| Adapt v2 (advanced platform adaptation) | **No** |
| Competitor tracking | **No** |
| A/B testing | **No** |
| Voice-to-seed | Yes, within seed cap |

#### Engage

| Capability | Access |
|------------|--------|
| Engagement inbox (comments, mentions, DMs) | **No** |
| Engagement Agent | **Not enabled** |

#### WhatsApp

| Capability | Access |
|------------|--------|
| WhatsApp Business (inbox, templates, Status Studio, broadcasts, sequences) | **No** |
| WhatsApp morning brief | **No** |
| WhatsApp marketing conversations | **0** |

#### REACH (leads, links, nurture)

| Capability | Limit |
|------------|-------|
| Leads in pipeline | **10** max |
| Edit lead details | **No** (view-only) |
| Kova Link pages | **1** page, **5** links per page |
| Lead capture forms on links | **No** |
| Walk-in QR attribution | Available (not separately capped in plan) |
| Email subscribers | **50** |
| Email lists | **1** |
| Email campaigns per month | **2** |
| Email nurture sequences | **0** |
| Bookings links | Available |

#### Commerce (Snap2sell)

| Capability | Limit |
|------------|-------|
| Products in catalog | **5** |
| M-Pesa commerce checkout | **No** |
| Shopify integration | **No** |
| Product CSV import | **No** |
| Quantity / stock tracking | **No** |
| Revenue dashboard | **Yes** |
| Multi-touch attribution (Kova Pixel) | **No** |

#### Command & intelligence

| Capability | Access |
|------------|--------|
| Daily brief (in-app) | **Yes** |
| Email brief reports | **No** |
| Workspace: Standup, Moments, Listen | **Yes** (brief/moments use daily brief flag; not separately tier-gated) |
| Holiday / calendar moments in brief | Included via daily brief |

#### Teams & agency

| Capability | Access |
|------------|--------|
| Team seats | **0** |
| White-label / multi-brand | **No** |

#### Limits & fair use

| Meter | Cap |
|-------|-----|
| Daily LLM tokens | **50,000** |
| Monthly LLM tokens | **1,000,000** |
| Studio polish credits | **8** / month (1 debit per Photoroom API call) |
| AI images | **0** |
| Social campaigns (voice campaigns) | **2** active |

#### What you cannot do on Starter

- Connect more than **2** social accounts
- Generate AI images (must upload your own)
- Use the engagement inbox or AI comment/DM replies
- Connect WhatsApp Business or send WhatsApp marketing
- Track competitors or run A/B tests
- Use M-Pesa checkout, Shopify sync, or memes
- Invite team members or use lead capture forms
- Run email nurture sequences
- Auto-approve posts without manual review (plan-level auto-approve is off)
- Exceed **18 posts**, **8 seeds**, or token/polish caps in a billing month

#### Typical user story

*Grace runs a home bakery in Nairobi on Instagram and Facebook. She connects both accounts, uploads photos of today’s tray, and lets Kova’s Create and Analyst agents draft captions and suggest posting times. Each morning she reads the daily brief, approves two or three posts from her queue, and stays within her 18-post monthly budget while building consistency without hiring a social manager.*

---

### Growth / Kazi — KSh 1,499 / $11 per month

**Positioning:** **Most popular.** For growing brands that need more volume, AI images, commerce tools, and hands-on engagement — without full WhatsApp Business yet.

#### Channels & publishing

| Capability | Limit / access |
|------------|----------------|
| Social accounts | **4** platforms (Facebook, Instagram, TikTok, LinkedIn — **no WhatsApp channel**) |
| AI posts per month | **60** |
| Content seeds per month | **30** |
| Queue & calendar | Yes |
| Content Autopilot | Yes, within caps |
| Auto-approve publishing | **No** at plan level (manual approval default) |

#### Create & Studio

| Capability | Access |
|------------|--------|
| AI agents | **4:** Content Creator, Analytics Agent, Research Agent, Platform Adapter |
| AI image generation | **Yes** — **50 images/month** (Instagram, TikTok, Pinterest-style outputs) |
| Studio polish | **30 credits/month**; up to **5** scene variants per product |
| Premium studio polish | No |
| Adapt v2 | **Yes** |
| Competitor tracking | **Yes** |
| Memes & trend intelligence | **No** |
| A/B testing | **Yes** |

#### Engage

| Capability | Access |
|------------|--------|
| Engagement inbox | **Yes** — comments, mentions, social DMs |
| Engagement Agent | **Enabled** — AI drafts replies; you review or configure autonomy in agent settings |
| Sub-areas | Comments & Mentions, Messages, AI auto-sent log |

#### WhatsApp

| Capability | Access |
|------------|--------|
| WhatsApp Business module (inbox, AI replies, templates, Status Studio, broadcasts, sequences, channels, analytics) | **No** — requires Pro (`whatsapp_enabled`) |
| WhatsApp morning brief | **No** |
| WhatsApp marketing conversation cap | **50/month** — defined in plan limits and shown on pricing; counts distinct conversations contacted via **marketing** templates only. **Utility** (e.g. booking confirmations) and **authentication** templates do **not** count. Full WhatsApp workspace access requires **Pro**. |

#### REACH

| Capability | Limit |
|------------|-------|
| Leads | **100** max; **editable** |
| Kova Link pages | **3** pages, **20** links each |
| Lead capture forms | **Yes** |
| Email subscribers | **2,500** |
| Email lists | **5** |
| Email campaigns / month | **10** |
| Email nurture sequences | **3** |
| Walk-in QR & bookings | Yes |

#### Commerce

| Capability | Limit |
|------------|-------|
| Products | **30** |
| M-Pesa commerce checkout | **Yes** |
| Shopify integration | **Yes** |
| Product CSV import | **Yes** |
| Stock tracking | **Yes** |
| Revenue dashboard | **Yes** |
| Multi-touch attribution (Kova Pixel) | **No** |
| Catalog showcase (multi-product carousel/reel) | Yes when Commerce Autopilot is on — not separately plan-gated |

#### Command & intelligence

| Capability | Access |
|------------|--------|
| Daily brief | **Yes** |
| Email brief reports | **Yes** |
| WhatsApp morning brief | **No** |
| Moments / Listen / Standup | Yes |

#### Teams & agency

| Capability | Access |
|------------|--------|
| Team seats | **0** |
| White-label | **No** |

#### Limits & fair use

| Meter | Cap | Notes |
|-------|-----|-------|
| Daily LLM tokens | **200,000** | |
| Monthly LLM tokens | **4,000,000** | |
| Studio polish | **30** / month | Growth may be **temporarily throttled** when platform-wide Photoroom pool exceeds **80%** used |
| AI images | **50** / month | |
| Social campaigns | **5** | |

#### What you cannot do on Growth

- Connect WhatsApp as a **5th platform** or open the WhatsApp Business workspace (Pro required)
- Use Meme Intelligence or WhatsApp morning brief
- Use plan-level auto-approve or multi-touch pixel attribution
- Invite team members (Pro: 5 seats; Agency: 25)
- Exceed **60 posts**, **30 seeds**, **50 AI images**, or marketing/token/polish caps

#### Typical user story

*James owns a fashion boutique with Instagram, TikTok, Facebook, and LinkedIn. On Growth he imports 25 products from Shopify, enables M-Pesa checkout links, and uses the Research and Adapter agents to turn one product photo into platform-native posts. The Engagement Agent drafts replies to comments overnight; James clears the inbox over coffee. He tracks two competitors and runs A/B tests on hooks — all within 60 posts and 50 AI images per month.*

---

### Pro / Biashara — KSh 2,999 / $22 per month

**Positioning:** For serious marketers and small teams who need WhatsApp, memes, auto-publish, attribution, and collaboration.

#### Channels & publishing

| Capability | Limit / access |
|------------|----------------|
| Social accounts | **5** — **all platforms including WhatsApp** |
| AI posts per month | **150** |
| Content seeds per month | **60** |
| Auto-approve publishing | **Yes** at plan level — combined with user preference `auto_approve_posts` for hands-off publishing |
| Content Autopilot | Full use within caps; commerce autopilot can auto-schedule when enabled |

#### Create & Studio

| Capability | Access |
|------------|--------|
| AI agents | **All 6:** Content Creator, Analytics Agent, Research Agent, Platform Adapter, Engagement Agent, Chief Strategist |
| AI images | **100/month** |
| Studio polish | **100 credits/month**; up to **7** variants per product |
| Premium studio polish | **Yes** |
| Memes & trend intelligence | **Yes** — discover, adapt, queue, trend alerts |
| Adapt v2, competitors, A/B testing | **Yes** |

#### Engage

| Capability | Access |
|------------|--------|
| Engagement inbox | **Yes** (full Growth capabilities) |
| Engagement Agent + Strategist | **Yes** — higher autonomy options with auto-approve |

#### WhatsApp

| Capability | Access |
|------------|--------|
| WhatsApp Business | **Yes** — full module unlocked |
| Inbox & AI replies | Yes — toggle AI per conversation |
| Templates | Create and manage approved templates |
| Status Studio | Create, share, repurpose, calendar view |
| Broadcasts | Launch, pause, detail views |
| Sequences | Multi-step drip sequences with marketing cap enforcement |
| Channels | Dashboard, posts, curation |
| Analytics & digests | WhatsApp performance analytics |
| WhatsApp morning brief | **Yes** (requires Pro + user opt-in) |
| Marketing conversation cap | **300 distinct conversations/month** via marketing templates; utility/auth excluded |

#### REACH

| Capability | Limit |
|------------|-------|
| Leads | **5,000** |
| Kova Link pages | **10** pages, **100** links each |
| Forms on links | **Yes** |
| Email subscribers | **25,000** |
| Email lists | **15** |
| Email campaigns / month | **30** |
| Nurture sequences | **10** |

#### Commerce

| Capability | Limit |
|------------|-------|
| Products | **100** |
| M-Pesa + Shopify + CSV + stock | **Yes** |
| Multi-touch attribution (Kova Pixel) | **Yes** — Pro+ only |
| Revenue dashboard | **Yes** |

#### Command & intelligence

| Capability | Access |
|------------|--------|
| Daily brief + email + WhatsApp brief | **All yes** |
| Moments, Listen, Standup | Yes |

#### Teams & agency

| Capability | Access |
|------------|--------|
| Team members | **Up to 5** seats on the owner’s plan |
| Roles | Owner, admin, editor, viewer invitations |
| White-label multi-client | **No** — Agency tier + sales approval |

#### Limits & fair use

| Meter | Cap |
|-------|-----|
| Daily LLM tokens | **500,000** |
| Monthly LLM tokens | **10,000,000** |
| Studio polish | **100** / month |
| AI images | **100** / month |
| WhatsApp marketing convos | **300** / month |
| Social campaigns | **15** |

#### What you cannot do on Pro

- Connect more than **5** social accounts or exceed **150 posts** / **60 seeds** per month
- Exceed **300** WhatsApp marketing conversations (broadcasts/sequences block with upgrade message)
- Use more than **5** team seats
- Access Agency white-label, **25** accounts, or **25** seats without Agency plan
- Exceed lead, product, email subscriber, or token/polish/image caps

#### Typical user story

*Amina runs a wellness studio with a team of three. Pro lets her connect WhatsApp alongside Instagram and Facebook, send booking confirmations (utility — not counted against marketing cap), and run monthly promotional broadcasts to 200 clients within the 300-conversation limit. Meme Intelligence adapts trending formats to her brand; auto-approve publishes approved Autopilot plans while she teaches classes. Her strategist agent summarizes performance in the WhatsApp morning brief.*

---

### Agency / Wakala — KSh 7,999 / $59 per month

**Positioning:** For agencies and multi-client operators managing many brands from one workspace. **Not on public checkout** — requires `is_agency_approved` on your profile after sales onboarding.

#### Channels & publishing

| Capability | Limit / access |
|------------|----------------|
| Social accounts | **25** across client brands |
| AI posts per month | **300** |
| Content seeds per month | **120** |
| Auto-approve | **Yes** |
| All Pro publishing features | Yes, at Agency scale |

#### Create & Studio

Same feature flags as **Pro**, with higher caps:

| Capability | Agency cap |
|------------|------------|
| AI agents | All **6** |
| AI images | **200/month** |
| Studio polish | **150/month**; **10** variants per product |
| Premium polish, memes, adapt v2, A/B, competitors | **Yes** |

#### Engage & WhatsApp

| Capability | Agency cap |
|------------|------------|
| Full engagement inbox | Yes |
| Full WhatsApp Business suite | Yes |
| WhatsApp marketing convos | **1,000/month** |
| WhatsApp morning brief | Yes |

#### REACH & Commerce

| Capability | Agency cap |
|------------|------------|
| Leads | **10,000** |
| Kova Link pages | **50** pages, **200** links each |
| Email subscribers | **100,000** |
| Email lists | **50** |
| Email campaigns / month | **50** |
| Nurture sequences | **20** |
| Products | **500** |
| M-Pesa, Shopify, pixel attribution | **Yes** |

#### Teams & agency-specific

| Capability | Access |
|------------|--------|
| Team members | **Up to 25** seats |
| Multi-brand / client sub-accounts | **Yes** — Brands under Teams; client role sees scoped dashboard |
| White-label (v1) | Custom domain display on commerce URLs, agency logo & theme on reports, sidebar accent theming |
| Sales onboarding | Required — email **hello@kova.ai** |

#### Limits & fair use

| Meter | Cap |
|-------|-----|
| Daily LLM tokens | **2,000,000** |
| Monthly LLM tokens | **40,000,000** |
| Social campaigns | **25** |

All Pro-level feature flags apply; Agency replaces former “unlimited” placeholders with **finite** caps above.

#### What you cannot do on Agency

- Self-serve checkout without **`is_agency_approved`**
- Exceed any numeric cap (300 posts, 1,000 WA marketing convos, 25 accounts, etc.) without sales discussion for custom arrangements
- Automatic DNS verification for custom domains (v1 is manual CNAME + verified flag)

#### Typical user story

*Digital First Agency manages twelve restaurant clients in Kenya. After sales approval, they onboard Wakala: each client is a Brand under their Team, with up to 25 connected accounts and white-label reports for monthly client meetings. They pool 300 posts and 1,000 WhatsApp marketing conversations across clients, using Status Studio and broadcast sequences per brand while staying within Agency caps.*

---

## 4. Free trial (detailed)

| Aspect | Detail |
|--------|--------|
| Duration | **7 days** |
| Payment | **Not required** to start |
| Limits applied | **Starter-tier** (`TRIAL_FEATURE_PLAN = "starter"`) — not Growth |
| UI label | **“Starter trial”** |
| What you get | Same caps as paid Starter: 2 accounts, 18 posts, 8 seeds, 2 agents, 8 polish credits, etc. |
| What you don’t get | Growth/Pro features (engagement inbox, AI images, WhatsApp, memes, commerce, etc.) during trial |
| After trial | Subscribe to Starter, Growth, or Pro via M-Pesa or Stripe, or lose full app access |
| Stripe | International card checkout includes the 7-day trial |
| M-Pesa | Trial signup collects phone for reminder before trial ends; no charge until you convert |

---

## 5. Agency plan — sales-only onboarding

| Rule | Detail |
|------|--------|
| Public pricing page | Shows Agency pricing for transparency; **no self-serve checkout button** |
| Checkout gate | `can_subscribe_to_agency(user)` requires `UserProfile.is_agency_approved == True` |
| How to get approved | Contact **hello@kova.ai** (subject: Agency plan inquiry) |
| Included | Highest caps, 25 accounts, 25 team seats, white-label v1, full Pro feature set |
| Grandfathered users | Some legacy Agency users may exist; all use finite Plan v2 caps |

---

## 6. Overages & upgrade path

Kova Plan v2 uses **hard caps**, not metered overages:

| When you hit a cap | What happens |
|--------------------|--------------|
| Posts, seeds, accounts, leads, products, etc. | Action blocked; message prompts **upgrade** or wait until next month (for monthly counters) |
| LLM tokens (daily or monthly) | AI generation stops until reset or upgrade |
| Studio polish | “Use as-is” or upgrade; Growth may see temporary throttle at platform pool >80% |
| WhatsApp marketing | Broadcast/sequence launch blocked |
| Expired trial / lapsed subscription | POST actions blocked; redirect to pricing |

**Upgrade path:** Billing → choose higher tier → M-Pesa or Stripe. Changes typically apply at the **end of the current billing cycle** for downgrades; upgrades unlock immediately after payment.

There is **no** documented pay-as-you-go overage billing in Plan v2.

---

## 7. FAQ

**1. What’s the difference between a “post” and a “content seed”?**  
A **seed** is an idea you submit (text or voice) for the AI to expand into full content. A **post** is a finished piece scheduled or published to a platform. Both have separate monthly caps.

**2. What counts as a WhatsApp “marketing” conversation vs utility?**  
Only outbound sends using **marketing** category templates count toward the monthly cap. **Utility** templates (e.g. booking confirmations, order updates) and **authentication** templates do **not** count.

**3. Growth shows 50 WhatsApp marketing convos but no WhatsApp Business — why?**  
Plan limits define a **50-conversation marketing allowance** on Growth (shown on the pricing page). The full **WhatsApp Business workspace** (inbox, Status Studio, broadcasts UI, sequences) requires **Pro** (`whatsapp_enabled`). Upgrade to Biashara/Pro to connect and operate WhatsApp.

**4. What are studio polish credits?**  
Each **Photoroom Plus** enhancement (product scene expansion / “studio polish”) uses **one credit** when the API call completes. Starter includes 8/month; higher tiers include more. **Plus pack** scenes per product: 3 (Starter), 5 (Growth), 7 (Pro), 10 (Agency).

**5. Why did my polish fail on Growth when I still had credits?**  
When the **platform-wide** Photoroom pool exceeds **80%** utilization, **Growth** accounts may be temporarily throttled until capacity frees up. Pro and Agency are not throttled this way.

**6. Do AI tokens and images share the same pool?**  
No. **LLM tokens** (daily + monthly) power text generation and analysis. **AI images** are a separate monthly counter (`ai_images_per_month`). Starter has 0 AI images; Growth+ include them.

**7. Can I try Growth features during the free trial?**  
No. The trial uses **Starter limits only** for seven days. Upgrade to Growth or Pro after trial for engagement, AI images, commerce, etc.

**8. How do team seats work on Pro vs Agency?**  
**Pro:** up to **5** team members on the account owner’s plan. **Agency:** up to **25** members plus **Brands** for client scoping and white-label. Teams nav is prominently shown for Agency; Pro owners with `max_team_members > 0` can still use Teams URLs.

**9. Is Content Autopilot included on all plans?**  
Yes — Autopilot planning is available on all tiers, but output volume is bounded by your **posts/month** and **seeds/month** caps. Auto-publish without review requires **Pro+** plan auto-approve or Commerce Autopilot settings where applicable.

**10. How do I pay — M-Pesa or card?**  
Kenya customers typically use **M-Pesa STK Push** (KES). International customers use **Stripe** (USD). Toggle currency on the pricing page. Both support subscribing after trial.

---

## Appendix A — Feature flags → plan matrix

For implementers mapping UI gates to `PLAN_LIMITS`:

| Flag | Starter | Growth | Pro | Agency |
|------|:-------:|:------:|:---:|:------:|
| `engagement_agent` | | ✓ | ✓ | ✓ |
| `competitor_tracking` | | ✓ | ✓ | ✓ |
| `ai_image_generation` | | ✓ | ✓ | ✓ |
| `whatsapp_enabled` | | | ✓ | ✓ |
| `whatsapp_brief` | | | ✓ | ✓ |
| `memes_enabled` | | | ✓ | ✓ |
| `adapt_v2_enabled` | | ✓ | ✓ | ✓ |
| `auto_approve` | | | ✓ | ✓ |
| `ab_testing` | | ✓ | ✓ | ✓ |
| `visual_enhance_premium` | | | ✓ | ✓ |
| `mpesa_commerce` | | ✓ | ✓ | ✓ |
| `shopify_integration` | | ✓ | ✓ | ✓ |
| `multi_touch_attribution` | | | ✓ | ✓ |
| `kova_forms` | | ✓ | ✓ | ✓ |
| `leads_can_edit` | | ✓ | ✓ | ✓ |
| `product_csv_import` | | ✓ | ✓ | ✓ |
| `requires_agency_approval` | | | | ✓ |

**Middleware-gated URL groups** (`apps/billing/middleware.py`):

- `competitor_tracking` → analytics competitor URLs  
- `engagement_agent` → engage inbox URLs  
- `whatsapp_enabled` → all WhatsApp module URLs  
- `memes_enabled` → memes URLs  

**Enforcement modules:** `apps/billing/enforcement.py` (seeds, leads, A/B, auto-approve), `apps/agents/budget.py` (LLM tokens), `apps/billing/visual_credits.py` (studio polish), `apps/billing/whatsapp_marketing.py` (marketing convos).

---

## Appendix B — AI agents by tier

| Agent (UI name) | Code | Starter | Growth | Pro | Agency |
|-----------------|------|:-------:|:------:|:---:|:------:|
| Content Creator | `create` | ✓ | ✓ | ✓ | ✓ |
| Analytics Agent | `analyst` | ✓ | ✓ | ✓ | ✓ |
| Research Agent | `research` | | ✓ | ✓ | ✓ |
| Platform Adapter | `adapt` | | ✓ | ✓ | ✓ |
| Engagement Agent | `engage` | | | ✓ | ✓ |
| Chief Strategist | `strategist` | | | ✓ | ✓ |

---

*Document generated from Plan v2 sources. For pricing changes, update `PLAN_LIMITS` and `PlanPrice` in admin; this guide should be refreshed when limits change.*
