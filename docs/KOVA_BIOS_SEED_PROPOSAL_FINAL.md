# KOVA BIOS Seed Funding Proposal

---

## Business Canvas

| **Problem** | **Impact** | **Market Size** |
|---|---|---|
| 7.4M Kenyan SMEs run with no marketing function — no strategist, no content creator, no analyst, no email marketer. A social media manager alone averages KES 37,000/month (Glassdoor 2025); a full marketing team is 4–6× that. | Most SMEs go without marketing infrastructure entirely. The result: invisible online presence, untracked leads, no email follow-up, no repeat business. Compounded, it is the single biggest reason small African businesses stay small. | **TAM** $3.7B — 44M MSMEs in Sub-Saharan Africa × $7/mo × 12 (IFC). **SAM** $320M — 7.4M Kenyan MSMEs × 50% addressable × $7/mo × 12 (KNBS). **SOM** $3.2M ARR by Year 3 — 1% of Kenya SAM (~37K paying users). |

| **Users** | **User Job** | **User Journey** |
|---|---|---|
| Small and medium business owners in Kenya: salon & beauty owners, restaurants, retailers, e-commerce sellers, consultants, and service providers. | Attract new customers and grow their business using social media — without spending hours every day creating content, engaging followers, and tracking results. | **Before Kova:** Post occasionally → go silent for weeks → try again → give up → hire a manager they can't afford → back to zero. **With Kova:** Drop an idea (3 mins) → AI creates content for every platform → posts at optimal time → engages followers automatically → captures leads → owner reviews results at breakfast. |

| **Value Proposition** | **Product** | **Production** |
|---|---|---|
| An autonomous AI marketing team for KES 299/month. No skills needed. No credit card. No daily time investment. 6 AI agents run your social media, capture leads, and send marketing emails — 24 hours a day, 7 days a week. | **Kova BIOS** — a Business Intelligence Operating System with 6 AI agents (Create, Engage, Analyse, Research, Adapt, Strategist), 9 social media platform integrations, lead capture forms, email marketing, and a daily performance brief. | Cloud SaaS hosted on Railway (web, worker, scheduler, database). AI content via OpenRouter (50+ models). Media stored on Cloudflare R2. Payments via M-Pesa (Daraja API) + Stripe. Accessible via browser or installable PWA — no app store required. |

| **Ecosystem** | **Unique Selling Proposition** | *(Production continued above)* |
|---|---|---|
| Safaricom M-Pesa (payments), Meta/Google/TikTok (social APIs), OpenRouter (AI models), MSME associations & university incubators, Growth Partners (earn 15–30% commission on referrals), digital marketing agencies (Wakala plan). | The only Business Intelligence Operating System built for African SMEs — AI-native, M-Pesa payments, KES pricing, and the only tool covering the complete loop: content → publishing → engagement → leads → email → analytics. All in one platform. Starting at KES 299/month. | |

| **Team & Assets** | **Revenue Streams** | **Cost Structure** |
|---|---|---|
| **Team:** Iranzi Innocent — Founder & CTO. Ezekiel [Last Name] — Marketing Lead. **Assets:** Fully built platform (24 app modules, 6 AI agents, 9 social integrations), M-Pesa + Stripe billing live, tested and functional. | **Primary:** Subscriptions — Jipange KES 299/mo · Kazi KES 999/mo · Biashara KES 1,999/mo · Wakala KES 2,999/mo. Blended ARPU assumption: KES 999 (~$7) anchored on the Kazi tier. **Secondary:** Growth Partner referral commissions (15–30%). **Future:** Agency white-label, template marketplace. | **Variable (per user/month):** AI $1.30 · M-Pesa fee $0.18 · Stripe fee $0.05 · Email $0.05 · SMS $0.05 · Marginal hosting $0.02 = **~$1.65/user** (**76% gross margin**). **Fixed (per month):** Railway $75 · OpenRouter base $30 · R2 storage $10 · Resend $20 · Domain/SSL/Sentry $5 · Ops marketing $30 = **$170/month**. |

---

## Problem

Kenya has **7.4 million MSMEs** (KNBS), employing 14.9 million people and generating
30% of GDP. Almost none of them have a marketing department. The typical small
business owner is also the strategist, the content creator, the community manager,
the email marketer, and the analyst — between serving customers, ordering supplies,
and closing the till. So most of the marketing work simply doesn't get done.

Hiring even part of that function out of pocket is out of reach. A social media
manager in Nairobi averages **KES 37,000/month** (Glassdoor 2025). A graphic designer
runs **KES 50,000–100,000/month** (Ikigai College). Adding a community manager, an
email/CRM specialist, and an analyst pushes the cost of a real marketing team well
past **KES 150,000/month** — more than most SMEs earn in revenue.

Western SaaS isn't a workable substitute either. Buffer charges **$5/channel/month**
(over $45/mo for the 9 platforms a serious SME needs), Hootsuite Professional is
**$99/month**, Mailchimp ranges $20–$100+/month, and a full HubSpot stack runs
**$3,000–$7,000/month**. Even at the low end, the SaaS bill alone is **$300+/month**
— before anyone is hired to operate it.

The result is predictable: SMEs post sporadically, lose leads they never captured,
don't follow up with customers, and have no idea which channel made the last sale.
Meanwhile, **78% of small-business owners in Sub-Saharan Africa already use WhatsApp
for business**, and those who do report **2.4× higher monthly revenue growth**
(Infobip 2026) — yet no Western tool serves this channel for SMEs.

Social media tools are not the answer. SMEs don't need another scheduler. **They need
the marketing department itself** — at a price they can pay, in a currency they use,
on the channels they already work in.

---

## Solution

Kova BIOS is a **Business Intelligence Operating System** — the AI-powered marketing,
sales, and customer operations layer for African SMEs. It replaces the work of an
eight-person growth team and runs it autonomously, 24/7, for **KES 299/month**.

**Six AI agents take on the roles of an entire marketing department:**

- **Strategist** — plans monthly campaigns around local context: paydays, holidays,
  M-Pesa cycles, regional events.
- **Research** — monitors competitors, tracks trending topics in the user's industry,
  surfaces what's working in the market this week.
- **Create** — generates posts, carousels, memes, captions, and images (via FLUX.1)
  tuned to the business's voice and audience.
- **Engage** — replies to comments and DMs across platforms and runs **WhatsApp
  Business conversations** — used by 78% of SSA small-business owners and linked
  to 2.4× higher revenue growth (Infobip 2026).
- **Analyse** — turns raw platform data into a daily one-page brief: what worked,
  what didn't, what to do today.
- **Adapt** — learns from every result and shifts the strategy automatically. The
  approach that performs gets more weight; the one that doesn't gets retired.

**Around the agents, Kova runs the rest of the growth stack natively:**

- **Publishing** to 9 platforms (Instagram, Facebook, TikTok, X, LinkedIn, YouTube,
  Pinterest, Threads, Bluesky) at optimal times.
- **Lead capture** through built-in forms, link-in-bio pages, and trackable short
  links.
- **Email marketing** — newsletters, drip sequences, and post-sale follow-ups
  triggered by leads the agents capture.
- **Calendar intelligence** that knows Kenyan holidays, school terms, paydays, and
  regional events.
- **Profile audits** — point Kova at any social profile (yours or a competitor's)
  and get a teardown in 60 seconds.
- **Campaigns** that tie a goal (sales, signups, foot traffic) to a multi-week,
  multi-platform plan with auto-tracking.
- **Daily brief** — the owner's one-page morning report: leads captured, conversations
  needing a human, top-performing post, recommended next move.

The owner's job shrinks from running marketing to **reviewing it**. Three minutes at
breakfast. Three minutes at dinner. That's it.

**Pricing** starts at **KES 299/month via M-Pesa** — under 1% of the monthly cost of
hiring even a single marketing role, and roughly **15× cheaper than the equivalent
Western SaaS stack** (Buffer + Mailchimp + Hootsuite at minimum tiers). No credit
card. No skills required. No app store.

Kova is not a scheduling tool with AI bolted on. **It is the operating system that
runs the customer-facing half of a small business** — content, conversations, leads,
email, analytics, strategy — as one unified system, in one app, on one subscription,
in one local currency.

---

## Scalability / Innovation

Existing tools (Buffer, Hootsuite, Mailchimp, HubSpot) are scheduling and email
products built for Western agencies and priced in dollars. None of them replace the
marketing function itself, and none are built around the channels and payment rails
that African SMEs actually use — M-Pesa, KES pricing, WhatsApp Business, local
context.

Kova is the **first Business Intelligence Operating System** designed for those
constraints. The same product that serves a Nairobi salon serves a Lagos retailer,
a Kampala consultancy, and a Kigali restaurant — because the underlying problem
(no marketing department, no budget for one, no time to operate one) is identical
across the continent. Sub-Saharan Africa alone holds **44 million MSMEs** (IFC),
of which 90% of all African businesses and over half of all jobs depend.

The AI-agent architecture means each new feature compounds: when Strategist learns
a new campaign pattern from a salon in Mombasa, the same pattern adapts for salons
in Accra. Marginal cost per user stays at **$0.40/month** regardless of scale —
unit economics that legacy SaaS players, built on per-seat human labor, cannot match.

---

## Business Model

We sell **tiered monthly subscriptions** — Jipange KES 299, Kazi KES 999, Biashara
KES 1,999, and Wakala KES 2,999 — with a **blended ARPU of KES 999 (~$7)** anchored
on the Kazi tier (the plan most validated SME prospects selected during interviews).

Each subscription costs us approximately **$1.65** to serve, the cost breakdown being:

- AI (LLM usage across 6 agents + image generation via FLUX) — $1.30
- M-Pesa Daraja transaction fee (~KES 25 per recurring charge) — $0.18
- Stripe fee (weighted; only triggers on international card payments) — $0.05
- Email delivery (~50 transactional emails via Resend) — $0.05
- SMS notifications (M-Pesa STK Push, lead alerts) — $0.05
- Marginal cloud hosting — $0.02

This yields a **76% gross margin** per user, and with a customer acquisition cost
of **$9** (see Budget), **CAC payback is under 2 months**.

Our monthly fixed operations cost is **$170**, from:

- Railway hosting (web, worker, scheduler, Postgres, Redis) — $75 (KES 10,000)
- OpenRouter base credits (agent system overhead, batch jobs) — $30
- Cloudflare R2 storage and bandwidth — $10
- Resend email service base — $20
- Domain, SSL, Sentry monitoring — $5
- Ongoing operational marketing (organic, content) — $30

Operational breakeven sits at roughly **32 paying users** ($170 fixed ÷ $5.35
gross profit per user) — well within our 6-month onboarding target of 100.

To get started, we'll also have capital expenditure of **$1,080** on:

- Legal company registration (BRS Kenya) — $200
- Product launch event (Nairobi MSME meetup) — $400
- Marketing collateral (flyers, banners, demo materials) — $230
- Professional branding & design assets — $150
- Business banking setup — $100

---

## Social & Environmental Impact

Wider benefits of our solution's use will be stronger economic growth for Kenyan small
businesses and more equal access to professional marketing tools. We'll measure these
with:

- No. of users publishing 3+ posts/week across at least 2 platforms
- Hours saved per business owner per week through AI automation (target: 10+ hrs/week
  reclaimed vs. the typical 3 hrs/day required for self-managed social)
- No. of customer leads captured per user per month through Kova's built-in forms
- No. of WhatsApp conversations handled by Kova on behalf of business owners
  (channel used by 78% of SSA SMEs — Infobip 2026)
- No. of women-owned businesses actively using Kova

---

## Market Validation / Risk Mitigation

The biggest assumptions behind our venture model have been validated with the
following 4 prototyping tests:

1. AI can create authentic, high-quality content for Kenyan businesses.
   a. We tested Kova on 3 business accounts (a salon, a restaurant, and a retail
      shop) for 14 days. AI-generated posts achieved 4.2% average engagement vs.
      the owners' previous 1.1% — a 3.8× improvement. All 3 owners confirmed the
      content sounds like their own business.

2. Small business owners will pay KES 999/month for AI marketing automation.
   a. We spoke to 12 SME owners across Nairobi. 9 of 12 confirmed they would pay
      KES 999/month, citing time saved and the cost vs. hiring a social media
      manager (KES 37,000/mo average per Glassdoor 2025). 3 have already requested
      access at launch.

3. M-Pesa works reliably as a recurring monthly subscription payment method.
   a. We built and tested the full M-Pesa STK Push integration (Safaricom Daraja
      API). All 5 test payments completed successfully and auto-renewal triggered
      correctly — confirming the billing model works without a credit card.

4. The platform is stable and handles real social media operations reliably.
   a. We ran the full Kova system for 30 days (Apr 12 – May 11, 2026) in a testing
      environment, processing 200+ AI content requests, successfully publishing
      posts to 5 connected social media accounts, and triggering automated engagement
      responses — with no unrecovered failures across the test window.

---

## Team

- **Iranzi Innocent**, iranzi297@gmail.com, [Phone]
  Founder & CTO — Full-stack software engineer. Built the entire Kova platform
  (24 app modules, 6 AI agents, 9 social media platform integrations, M-Pesa +
  Stripe billing) as a solo developer. Mastercard Foundation Scholar, USIU-Africa.

- **Ezekiel [Last Name]**, [Email], [Phone]
  Marketing Lead — [Qualification]. [Relevant experience with Nairobi SMEs].
  Responsible for customer outreach, MSME partnerships, and Growth Partner activation.

---

## Budget for Funding

We'll use the $3,000 to cover the $1,200 initial capital expenditure, onboard
100 paying users, and cover 6 months of operations costs. The breakdown of the
budget is:

| Item Description | Cost | No. Units | Amount |
|---|---|---|---|
| Unit Costs / CAC (Digital ads $4 + Demo events $3 + Onboarding $2) | $9 | 100 users | $900 |
| Operations Costs (Railway $75 + OpenRouter $30 + R2 $10 + Resend $20 + Domain/SSL $5 + Ops marketing $30) | $170 | 6 months | $1,020 |
| Capital Expenditure | $1,080 | 1 | $1,080 |
| **TOTAL** | | | **$3,000** |

---

## Goals

With $3,000, we'll track performance against the following milestones/targets:

- **Registration —** We'll register the company and open a business bank account
  by June 2026.

- **Product Design —** We'll complete platform testing, refine user onboarding,
  and add Swahili-language content generation by July 2026.

- **Production & Partnerships —** We'll activate 5 Growth Partners (earning 15–30%
  recurring commission per referral) and partner with 3 MSME business associations
  by August 2026.

- **Sales —** We'll onboard 100 paying users over 6 months on a linear ramp —
  **15 by Aug · 35 by Sept · 55 by Oct · 75 by Nov · 100 by Dec 2026** — generating
  **$2,100 in total subscription revenue** (≈3 months avg tenure × $7 ARPU × 100
  users) and exiting Month 6 at **$700 MRR**.

---

## Sources

Market and salary figures cited above are drawn from the following:

- **Kenya MSME population (7.4M; 1.56M formal + 5.84M informal; 14.9M employed; 30% of GDP)** — Kenya National Bureau of Statistics, *2016 Micro, Small and Medium Enterprises Survey Basic Report*; FSD Kenya MSME Outlook 2024; KIPPRA.
- **Sub-Saharan Africa MSMEs (44M; 97% micro; Nigeria 37M; 90% of African businesses, 50%+ of jobs)** — International Finance Corporation (IFC) MSME Finance research; MasterCard Foundation analysis.
- **Social Media Manager salary, Nairobi (KES 37,000/mo average; KES 25K–97K range)** — Glassdoor, 2025.
- **Graphic Designer salary, Nairobi (KES 50K–100K entry; up to 250K senior)** — Glassdoor; Ikigai College of Interior Design.
- **Competitor SaaS pricing (Buffer $5/channel; Hootsuite $99/mo; Mailchimp $20–$100+; HubSpot $3,000–$7,000/mo for full stack)** — Buffer, Hootsuite, Mailchimp, and HubSpot 2026 published pricing.
- **WhatsApp adoption (78% of SSA small-business owners; 97% Kenya; 2.4× revenue growth for users)** — Infobip *WhatsApp Statistics 2026*; SQ Magazine.
- **Kenya social media users (13.05M Jan 2024; 4 hr 13 min daily — highest globally)** — DataReportal *Digital 2026: Kenya*.
