# Kova — Funding Requirements & Fund Usage Plan

### Detailed Financial Blueprint for Investors, Grants, and Partners

**Confidential | April 2026**

---

> This document provides a transparent, line-by-line breakdown of how Kova will use every shilling raised — from seed capital through Series A readiness. It covers current operating costs, funding requirements by stage, detailed allocation tables, milestone-linked disbursements, and financial controls.

---

## Table of Contents

1. [Current State — What's Already Built](#current-state--whats-already-built)
2. [Current Operating Costs](#current-operating-costs)
3. [Funding Overview](#funding-overview)
4. [Pre-Seed: KES 500,000 ($4,000) — Bootstrap Phase](#pre-seed-kes-500000-4000--bootstrap-phase)
5. [Seed Round: $150,000–$300,000 — Kenya Launch](#seed-round-150000300000--kenya-launch)
6. [Detailed Seed Round Allocation](#detailed-seed-round-allocation)
7. [Milestone-Linked Disbursement](#milestone-linked-disbursement)
8. [Hiring Plan](#hiring-plan)
9. [Infrastructure Scaling Plan](#infrastructure-scaling-plan)
10. [Marketing & User Acquisition Budget](#marketing--user-acquisition-budget)
11. [LLM & AI Cost Projections](#llm--ai-cost-projections)
12. [Revenue Projections vs. Burn Rate](#revenue-projections-vs-burn-rate)
13. [Path to Break-Even](#path-to-break-even)
14. [Grant Funding Opportunities](#grant-funding-opportunities)
15. [Bridge Round: $500,000 — Regional Expansion](#bridge-round-500000--regional-expansion)
16. [Series A Readiness: $2M–$5M](#series-a-readiness-2m5m)
17. [Financial Controls & Governance](#financial-controls--governance)
18. [Risk-Adjusted Scenarios](#risk-adjusted-scenarios)
19. [Return on Investment Projections](#return-on-investment-projections)
20. [Summary — How Every Dollar is Spent](#summary--how-every-dollar-is-spent)

---

## Current State — What's Already Built

Before asking for a single shilling, here's what exists today — built with sweat equity and minimal capital:

### Product (100% Functional — Business Intelligence Operating System)

| Component | Status | Value Created |
|-----------|--------|--------------|
| Django web application (16 app modules) | ✅ Live | Full BIOS platform |
| 6 AI agents (Create, Analyst, Research, Adapt, Engage, Strategist) | ✅ Running | Core product IP — autonomous intelligence loop |
| 12+ Celery Beat scheduled tasks (24/7 automation) | ✅ Running | Continuous autonomous operation |
| 9 social platform integrations (Twitter/X, LinkedIn, Instagram, Facebook, TikTok, YouTube, Pinterest, Threads, Bluesky) | ✅ Built | Complete platform coverage |
| Facebook + Instagram publishing (real posts verified) | ✅ Live | Production-verified publishing |
| Content DNA learning system | ✅ Live | Competitive moat — compounding intelligence |
| A/B testing with auto-winner declaration | ✅ Live | Data-driven content optimization |
| Smart CTAs (6 types + UTM auto-tracking) | ✅ Live | Measurable conversion from every post |
| Kova Links — link-in-bio landing pages (5 themes, click tracking, SEO) | ✅ Live | Conversion touchpoint from social profiles |
| Lead Capture Forms (5 types: contact, newsletter, waitlist, booking, custom) | ✅ Live | Turns followers into identifiable contacts |
| Lead Management pipeline (CRM-light with scoring, tagging, activity timeline) | ✅ Live | Full lead-to-customer tracking |
| Email Marketing system (subscribers, lists, campaigns, sequences) | ✅ Live | Lead nurturing without third-party tools |
| Comprehensive email system — 20+ email types via Resend | ✅ Live | Authentication, billing, onboarding, reports, marketing |
| M-Pesa billing (STK Push, auto-renewal, grace periods) | ✅ Integrated | Revenue infrastructure — Kenya |
| Stripe billing (international, webhooks) | ✅ Integrated | Revenue infrastructure — global |
| 4-tier plan system with middleware enforcement | ✅ Live | Monetization with feature gating |
| Daily Brief generation with trend exploration | ✅ Live | User retention feature |
| Engagement cycle (fetch → analyze → sentiment → reply → auto-send) | ✅ Live | Automated community management |
| Superfan detection (Rising → Loyal → Superfan tiers) | ✅ Live | Relationship intelligence |
| Competitor intelligence system | ✅ Live | Premium strategic feature |
| Media Queue — rhythm-based photo publishing (daily/weekly) | ✅ Live | Photo content pipeline |
| Growth Partner Program (commissions, milestones, profit share) | ✅ Live | Built-in distribution channel |
| Teams & Multi-Brand (roles, permissions, brand voice per brand) | ✅ Live | Agency and enterprise feature |
| Admin Dashboard (Celery status, LLM config, payments, user stats) | ✅ Live | System monitoring |
| Legal pages (Privacy Policy, Terms, Cookies, Acceptable Use, DPA) | ✅ Live | Regulatory compliance |
| 3-strike account resilience + auto token refresh + FB auto-extension | ✅ Live | Platform reliability |
| R2 cloud storage (Cloudflare) for media | ✅ Live | Scalable media infrastructure |
| Railway deployment (Web + Worker + Beat + Redis + PostgreSQL) | ✅ Live | Production infrastructure |
| PWA (installable on mobile) | ✅ Live | Mobile distribution |
| OAuth social login (Meta) | ✅ Live | User onboarding |
| Provider abstraction for 9 platforms | ✅ Built | Scalable architecture |

### Estimated Development Value

If this product were built by an agency or outsourced team:

| Item | Estimated Cost |
|------|---------------|
| Backend development (Django, Celery, 16 app modules) | $40,000–$60,000 |
| 6 AI agent system (prompts, orchestration, learning loop, outcome scoring) | $20,000–$30,000 |
| 9 platform integrations (OAuth, APIs, publishing, token management) | $15,000–$25,000 |
| Conversion engine (Kova Links, Lead Capture, CRM, Email Marketing) | $25,000–$40,000 |
| Billing system (M-Pesa + Stripe + plan enforcement + auto-renewal) | $8,000–$12,000 |
| Partner Program (applications, commissions, milestones, profit share) | $8,000–$12,000 |
| Teams & Multi-Brand (roles, permissions, brand management) | $8,000–$12,000 |
| Email system (20+ types, Resend, webhooks, subscriber management) | $8,000–$12,000 |
| Frontend (templates, HTMX, Tailwind, PWA, legal pages) | $12,000–$18,000 |
| Media system (queues, R2 storage, image generation) | $5,000–$8,000 |
| Admin Dashboard + monitoring | $5,000–$8,000 |
| DevOps & deployment (Railway, 4 services, CI/CD) | $5,000–$8,000 |
| **Total estimated build value** | **$159,000–$245,000** |

**This is already built. The investment ask is for growth, not building.**

---

## Current Operating Costs

### Monthly Costs (Current — Minimal Users)

| Expense | Monthly Cost (USD) | Monthly Cost (KES) | Notes |
|---------|-------------------|-------------------|-------|
| Railway Web Service | $5 | 625 | Starter plan |
| Railway Worker Service | $5 | 625 | Celery worker |
| Railway Beat Service | $5 | 625 | Celery scheduler |
| Railway Redis | $5 | 625 | Message broker |
| Railway PostgreSQL | $5 | 625 | Database |
| Cloudflare R2 | $0 | 0 | Free tier sufficient for now |
| Domain & DNS | ~$1 | 125 | Annual, amortized |
| OpenRouter API (LLM) | $2–$10 | 250–1,250 | Free tier models + paid fallback |
| Resend (Email) | $0 | 0 | Free tier for <3,000 emails/month |
| M-Pesa API (sandbox) | $0 | 0 | Free in sandbox mode |
| GitHub (free tier) | $0 | 0 | Source control |
| **Total current monthly** | **$28–$36** | **KES 3,500–4,500** | |

**Annual current operating cost: ~$400–$430**

This is the power of modern infrastructure + free-tier AI models — a full BIOS with 16 modules, 6 agents, and 12+ tasks running for less than KES 5,000/month.

---

## Funding Overview

### The Three Stages

```
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  PRE-SEED              SEED                    BRIDGE                   │
│  KES 500K ($4K)        $150K–$300K             $500K                    │
│  ───────────           ────────────            ──────────               │
│  Self/friends          Angels/VCs/Grants       VCs/Growth investors     │
│                                                                         │
│  ► First 50 users      ► 1,000 users           ► 10,000 users          │
│  ► Validate PMF        ► Kenya market           ► Nigeria + SA          │
│  ► Organic growth      ► Hire core team         ► Hire growth team      │
│                        ► Marketing launch       ► Product expansion     │
│                        ► Activate partners      ► Continental GTM       │
│                                                                         │
│  Timeline: Now         Timeline: Q2-Q3 2026     Timeline: Q1-Q2 2027   │
│  Runway: 3 months      Runway: 12-18 months     Runway: 12 months      │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Pre-Seed: KES 500,000 ($4,000) — Bootstrap Phase

**Source:** Founder savings, friends & family, personal network
**Timeline:** Now – June 2026 (3 months)
**Goal:** First 50 paying users, validate product-market fit

### Allocation

| Item | Amount (KES) | Amount (USD) | % | Purpose |
|------|-------------|-------------|---|---------|
| Infrastructure (Railway) | 90,000 | 720 | 18% | 3 months of production hosting |
| LLM API credits (OpenRouter) | 75,000 | 600 | 15% | AI costs for first 50 users (mostly free tier) |
| M-Pesa production setup | 25,000 | 200 | 5% | Go-live fees, production API access |
| Facebook App Review + Meta Business verification | 15,000 | 120 | 3% | Required for public OAuth access |
| Marketing (data bundles, social ads) | 100,000 | 800 | 20% | WhatsApp campaigns, Facebook ads targeting SMEs |
| Beta user incentives | 50,000 | 400 | 10% | Extended trials, onboarding support |
| Domain (kova.ai or similar) | 15,000 | 120 | 3% | Premium domain purchase |
| Miscellaneous & contingency | 130,000 | 1,040 | 26% | Transport, meetings, data, unforeseen |
| **Total** | **500,000** | **$4,000** | **100%** | |

### Pre-Seed Success Metrics

| Metric | Target | How We Measure |
|--------|--------|---------------|
| Active users | 50 | Completed onboarding + 1 week active |
| Paying users | 15+ | Converted from trial to paid plan |
| Posts published | 500+ | Total across all users |
| Leads captured via Kova Forms | 100+ | Validates conversion engine |
| Trial → Paid conversion | >10% | Paid users / total signups |
| Daily Brief open rate | >50% | Users who read their brief daily |
| Growth Partners activated | 10+ | Partner applications approved |
| User feedback score | >7/10 | Post-trial survey |

---

## Seed Round: $150,000–$300,000 — Kenya Launch

**Source:** Angel investors, Africa-focused VCs, grants
**Timeline:** Q3 2026 – Q2 2027 (12-18 months)
**Goal:** 1,000 paying users, revenue-generating, ready for regional expansion

### Why This Amount

| Consideration | Reasoning |
|--------------|-----------|
| **$150K minimum** | Covers 12 months of team (2 hires) + infrastructure + marketing + partner program activation. Lean but viable. |
| **$300K ideal** | 18-month runway. 3 hires + aggressive marketing + Nigeria/SA groundwork + partner scale. |
| **Why not more?** | We don't need $1M to prove Kenya PMF. The product is fully built — $159-245K of sweat equity already invested. African SaaS rounds are capital-efficient. Over-raising at pre-revenue creates valuation pressure. |
| **Why not less?** | Below $100K, we can't hire — limiting growth to founder-only capacity. Marketing budget becomes too thin for meaningful traction. Partner program needs activation capital. |

### High-Level Allocation ($200K Baseline)

```
┌──────────────────────────────────────────────────────────┐
│                SEED ROUND: $200,000                       │
│                                                          │
│  ┌─────────────────────┐  40%  = $80,000                 │
│  │   TEAM & TALENT     │  2-3 hires over 12 months       │
│  └─────────────────────┘                                 │
│                                                          │
│  ┌─────────────────────┐  25%  = $50,000                 │
│  │   MARKETING & GTM   │  Campaigns, partnerships,       │
│  │                     │  partner program, events         │
│  └─────────────────────┘                                 │
│                                                          │
│  ┌─────────────────────┐  15%  = $30,000                 │
│  │   LLM & API COSTS   │  AI inference for 1,000 users   │
│  └─────────────────────┘                                 │
│                                                          │
│  ┌─────────────────────┐  10%  = $20,000                 │
│  │   INFRASTRUCTURE    │  Scaling Railway → AWS/GCP       │
│  └─────────────────────┘                                 │
│                                                          │
│  ┌─────────────────────┐  10%  = $20,000                 │
│  │   OPERATIONS        │  Legal, compliance, tools, misc  │
│  └─────────────────────┘                                 │
└──────────────────────────────────────────────────────────┘
```

---

## Detailed Seed Round Allocation

### Scenario A: $150,000 (Minimum Viable Raise)

| Category | Budget | Monthly | Details |
|----------|--------|---------|---------|
| **Team** | | | |
| → Backend/AI Engineer (1) | $36,000 | $3,000 | 12 months. Full-time. Django + LLM expertise. |
| → Growth/Marketing Lead (1) | $30,000 | $2,500 | 12 months. Full-time. GTM + partner program execution. |
| **Subtotal Team** | **$66,000** | **$5,500** | **44%** |
| | | | |
| **Marketing & User Acquisition** | | | |
| → Digital ads (Facebook, Google, Instagram) | $12,000 | $1,000 | Targeted: Kenyan SME owners |
| → WhatsApp campaigns (data + tools) | $3,600 | $300 | Direct outreach to MSME groups |
| → Content marketing (blog, video, social) | $4,800 | $400 | SEO, thought leadership, case studies |
| → Events & workshops (SME meetups) | $3,600 | $300 | Monthly in Nairobi, quarterly in Mombasa/Kisumu |
| → Growth Partner Program activation | $3,000 | $250 | Partner onboarding, commission payouts, materials |
| → Referral program rewards | $2,400 | $200 | "Invite a business, get 1 month free" |
| → Agency partnership onboarding | $2,400 | $200 | Co-branded materials, partner support |
| **Subtotal Marketing** | **$31,800** | **$2,650** | **21%** |
| | | | |
| **LLM & AI Costs** | | | |
| → OpenRouter API credits (free tier + fallback) | $15,000 | $1,250 | 3-tier model strategy, ~$0.25/user at scale |
| → Image generation API | $3,000 | $250 | AI image generation for Pro/Agency users |
| → Model experimentation | $1,500 | $125 | Testing new free models, optimizing prompts |
| **Subtotal AI** | **$19,500** | **$1,625** | **13%** |
| | | | |
| **Infrastructure** | | | |
| → Railway / Cloud hosting | $9,600 | $800 | Scale up as users grow |
| → Domain, SSL, CDN | $1,200 | $100 | Production domain + Cloudflare |
| → Monitoring (Sentry, uptime) | $1,800 | $150 | Error tracking, alerting |
| → Email service (Resend) | $1,200 | $100 | Transactional + marketing emails at scale |
| → Cloudflare R2 storage | $600 | $50 | Media storage scaling |
| **Subtotal Infrastructure** | **$14,400** | **$1,200** | **10%** |
| | | | |
| **Operations** | | | |
| → Legal (company registration, ODPC Kenya) | $3,500 | — | One-time + annual |
| → Accounting & compliance | $2,400 | $200 | Monthly bookkeeping, tax filings |
| → Coworking / office | $3,600 | $300 | Shared workspace in Nairobi |
| → Software tools (GitHub, Figma, analytics) | $2,400 | $200 | Team productivity |
| → M-Pesa production fees | $1,200 | $100 | Transaction fees, API costs |
| → Travel (partnership meetings) | $1,800 | $150 | Nairobi, Mombasa, Kisumu |
| **Subtotal Operations** | **$14,900** | **$950** | **10%** |
| | | | |
| **Contingency** | **$3,400** | — | **2%** |
| | | | |
| **TOTAL** | **$150,000** | **~$11,925** | **100%** |

**Runway at $150K: ~12 months** (at $11,925/month burn + growing revenue offset)

---

### Scenario B: $200,000 (Target Raise)

Everything in Scenario A, plus:

| Additional Allocation | Amount | Purpose |
|----------------------|--------|---------|
| 3rd hire: Designer/Frontend | $18,000 | 12 months, part-time → full-time. Mobile UX, marketing assets. |
| Expanded marketing budget | $12,000 | Double digital ad spend. More events. Partner activation. |
| Nigeria/SA market research | $5,000 | Payment integration research, user interviews. |
| Partner program scale-up | $5,000 | Support 100+ active partners |
| Extended contingency | $10,000 | 3-month safety net |
| **Additional total** | **$50,000** | |

**Runway at $200K: ~15 months**

---

### Scenario C: $300,000 (Maximum Raise)

Everything in Scenario B, plus:

| Additional Allocation | Amount | Purpose |
|----------------------|--------|---------|
| 4th hire: Full-time AI Engineer | $36,000 | Agent optimization, model fine-tuning, Content DNA evolution |
| Nigeria launch GTM | $20,000 | Paystack integration, Lagos marketing, local partnerships |
| South Africa launch GTM | $15,000 | Ozow/SnapScan integration, Jo'burg marketing |
| Platform API review fees | $8,000 | Twitter, LinkedIn, TikTok API compliance |
| Extended runway buffer | $21,000 | Additional safety |
| **Additional total** | **$100,000** | |

**Runway at $300K: ~18 months** (with revenue contribution reducing burn)

---

## Milestone-Linked Disbursement

For investors who prefer milestone-based capital release:

### Tranche 1: 40% on close ($60K–$120K)

**Released immediately upon investment close**

| Use | Allocation |
|-----|-----------|
| First 2 hires (start immediately) | 60% |
| Infrastructure scaling | 15% |
| Initial marketing + partner activation | 25% |

**Milestone to unlock Tranche 2:**
- 100 active users
- 30+ paying subscribers
- 10+ Growth Partners activated
- Trial → Paid conversion >8%
- Target timeline: 3 months

### Tranche 2: 35% on user milestone ($52K–$105K)

**Released when 100 active users reached**

| Use | Allocation |
|-----|-----------|
| Marketing scale-up | 35% |
| LLM API credits (growing usage) | 20% |
| 3rd hire | 20% |
| Partner program expansion | 10% |
| Operations | 15% |

**Milestone to unlock Tranche 3:**
- 500 active users
- $3,000+ MRR
- 3+ agency partnerships
- 25+ active Growth Partners
- Target timeline: 3 months after Tranche 2

### Tranche 3: 25% on revenue milestone ($37K–$75K)

**Released when $3,000 MRR reached**

| Use | Allocation |
|-----|-----------|
| Regional expansion prep (Nigeria/SA) | 40% |
| Team growth (4th hire) | 30% |
| Extended marketing | 20% |
| Contingency | 10% |

---

## Hiring Plan

### Year 1 Hires (Seed Round)

| # | Role | Start | Monthly Salary (KES) | Monthly (USD) | Why |
|---|------|-------|---------------------|--------------|-----|
| 1 | **Backend/AI Engineer** | Month 1 | 375,000 | $3,000 | Agent optimization, new platform integrations, conversion engine enhancements |
| 2 | **Growth Lead** | Month 1 | 312,500 | $2,500 | GTM execution, partner program management, community building |
| 3 | **Designer (part → full time)** | Month 3 | 187,500 | $1,500 | Mobile UX, Kova Links themes, marketing assets, brand identity |
| 4 | **AI Engineer** (if $300K) | Month 4 | 375,000 | $3,000 | Prompt engineering, model fine-tuning, email sequence optimization |

### Salary Rationale

| Benchmark | Range (KES/month) | Our Offer |
|-----------|-------------------|-----------|
| Mid-level Django developer (Nairobi) | 200,000–500,000 | 375,000 |
| Digital marketing manager (Nairobi) | 150,000–400,000 | 312,500 |
| UI/UX designer (Nairobi) | 120,000–350,000 | 187,500 |

Salaries are competitive for Nairobi's tech market — high enough to attract talent, lean enough to extend runway. Equity (vesting) offered to all early hires.

### Year 2 Hires (Bridge Round)

| Role | When | Monthly (USD) | Purpose |
|------|------|--------------|---------|
| Customer Success Lead | Month 13 | $2,000 | User onboarding, retention, support |
| Platform Engineer | Month 14 | $3,000 | Advanced platform integrations, API development |
| Nigeria Country Lead | Month 15 | $2,500 | Local GTM, partnerships, market development |
| South Africa Country Lead | Month 16 | $2,500 | Local GTM, partnerships |
| Content Creator (in-house) | Month 15 | $1,500 | Kova's own social media, case studies, blog |

---

## Infrastructure Scaling Plan

### Cost Progression as Users Grow

| Users | Infrastructure | LLM/AI | Email | Total Monthly | Revenue Offset |
|-------|---------------|--------|-------|--------------|---------------|
| 0–50 | $30 | $10 | $0 | $40 | $50–$250 |
| 50–200 | $50 | $50 | $5 | $105 | $400–$1,400 |
| 200–500 | $100 | $125 | $15 | $240 | $1,400–$3,500 |
| 500–1,000 | $200 | $250 | $30 | $480 | $3,500–$9,000 |
| 1,000–5,000 | $500 | $1,250 | $100 | $1,850 | $9,000–$45,000 |
| 5,000–10,000 | $1,200 | $2,500 | $250 | $3,950 | $45,000–$90,000 |

*LLM costs reduced vs. original projections due to 3-tier free model strategy with paid fallback only when free models fail.*

### Migration Plan

| Stage | Platform | When | Why |
|-------|----------|------|-----|
| Current | Railway (4 services) | Now | Simple, affordable, fast deployment |
| 500 users | Railway Pro + larger instances | ~Q4 2026 | More CPU/RAM for worker tasks |
| 2,000 users | AWS / GCP migration | ~Q2 2027 | Auto-scaling, better SLAs, regional data centers |
| 10,000 users | AWS with CDN + multi-region | ~Q4 2027 | Africa-wide low latency, compliance |

### Database Scaling

| Stage | Solution | Monthly Cost |
|-------|----------|-------------|
| Current | Railway PostgreSQL (1GB) | $5 |
| 500 users | Railway PostgreSQL (5GB) | $20 |
| 2,000 users | AWS RDS (20GB, read replicas) | $100 |
| 10,000 users | AWS RDS (100GB, multi-AZ) | $400 |

---

## Marketing & User Acquisition Budget

### Channel-by-Channel Breakdown (12 months, $150K scenario)

| Channel | Annual Budget | Monthly | Expected Signups | CAC |
|---------|-------------|---------|-----------------|-----|
| **Facebook/Instagram Ads** | $7,200 | $600 | 400 | $18 |
| **Google Ads (search)** | $4,800 | $400 | 200 | $24 |
| **WhatsApp campaigns** | $3,600 | $300 | 150 | $24 |
| **Growth Partner referrals** | $3,000 | $250 | 200 | $15 |
| **Content marketing (SEO/blog)** | $4,800 | $400 | 100 | $48 (but compounds) |
| **Events & workshops** | $3,600 | $300 | 80 | $45 |
| **Referral program** | $2,400 | $200 | 120 | $20 |
| **Agency partnerships** | $2,400 | $200 | 100 (via agencies) | $24 |
| **Total** | **$31,800** | **$2,650** | **~1,350 signups** | **Blended: ~$24** |

At 30% trial → engagement and 15% trial → paid conversion: **~200 paying users from marketing alone**, supplemented by organic/word-of-mouth and partner referrals for remaining 800.

### Marketing Mix Evolution

| Phase | Primary Channel | Budget Share |
|-------|----------------|-------------|
| Months 1-3 | WhatsApp groups + partner activation + direct outreach | 40% |
| Months 4-6 | Facebook/Instagram ads + content + partner scaling | 35% |
| Months 7-9 | Referrals + agency partnerships + partner network | 30% |
| Months 10-12 | SEO/content + PR + events + established partner base | 35% |

The mix shifts from high-touch (WhatsApp outreach) to scalable (content, partners, referrals) as we learn which channels convert best. The Growth Partner Program becomes increasingly important as partners earn commissions and recruit more businesses.

---

## LLM & AI Cost Projections

### Cost Per User Breakdown

We run a 3-tier free LLM strategy: Nvidia Nemotron 120B (premium), GPT-OSS 120B (workhorse), Nemotron Nano 30B (fast), with DeepSeek V3.2 as paid fallback only when free models fail.

Each active Kova user generates these AI calls daily:

| Agent Task | Calls/Day | Avg Tokens/Call | Daily Cost/User |
|-----------|----------|----------------|----------------|
| Create Agent (content generation) | 0.5 | 2,000 | $0.001* |
| Analyst (DNA extraction) | 0.5 | 1,000 | $0.000* |
| Analyst (engagement prediction) | 0.5 | 800 | $0.000* |
| Engage Agent (analysis + replies) | 2.0 | 1,500 | $0.002* |
| Research Agent | 0.08 (every 12h) | 3,000 | $0.000* |
| Strategist | 0.12 (every 8h) | 4,000 | $0.001* |
| Daily Brief compilation | 0.07 (once/day) | 3,000 | $0.000* |
| **Total daily (free tier)** | | | **~$0.004** |
| **Total monthly (free tier)** | | | **~$0.12** |
| **With 20% paid fallback** | | | **~$0.25** |

*\* Free tier models have zero per-token cost. Cost only incurred when falling back to paid model (DeepSeek V3.2 at $0.14/$0.28 per 1M tokens).*

### Model Cost Trends

| Period | Cost per 1M tokens (input) | Cost per 1M tokens (output) | Trend |
|--------|--------------------------|---------------------------|-------|
| 2024 | $15.00 (GPT-4) | $45.00 | — |
| 2025 | $2.50 (GPT-4o) | $10.00 | -83% |
| 2026 (now) | $0.00 (free tier) / $0.14 (fallback) | $0.00 / $0.28 | -99% from 2024 |
| 2027 (projected) | More free models, lower fallback | Even cheaper | Improving |

**Key insight:** Our 3-tier free model strategy means baseline AI cost is near-zero. Paid fallback only triggers when free models fail. As free models improve, fallback frequency decreases. This is a **structural tailwind** — our margins expand automatically.

### Annual LLM Cost by User Scale

| Users | Monthly AI Cost | Annual AI Cost | % of Revenue |
|-------|----------------|---------------|-------------|
| 50 | $13 | $150 | ~2% |
| 200 | $50 | $600 | ~3% |
| 500 | $125 | $1,500 | ~3% |
| 1,000 | $250 | $3,000 | ~3% |
| 5,000 | $1,250 | $15,000 | ~3% |
| 10,000 | $2,500 | $30,000 | ~3% |

AI costs remain ~3% of revenue across all scales (down from ~5-6% in our original projections, thanks to the free model strategy). This is highly sustainable.

---

## Revenue Projections vs. Burn Rate

### Month-by-Month Year 1 (Kenya Launch)

| Month | Users | MRR | Monthly Burn | Net Burn | Cumulative Spend |
|-------|-------|-----|-------------|----------|-----------------|
| 1 | 10 | $70 | $8,000 | -$7,930 | $7,930 |
| 2 | 25 | $175 | $9,000 | -$8,825 | $16,755 |
| 3 | 50 | $400 | $10,000 | -$9,600 | $26,355 |
| 4 | 80 | $640 | $11,500 | -$10,860 | $37,215 |
| 5 | 120 | $1,000 | $12,000 | -$11,000 | $48,215 |
| 6 | 180 | $1,500 | $12,500 | -$11,000 | $59,215 |
| 7 | 250 | $2,100 | $12,500 | -$10,400 | $69,615 |
| 8 | 350 | $3,000 | $13,000 | -$10,000 | $79,615 |
| 9 | 450 | $4,000 | $13,000 | -$9,000 | $88,615 |
| 10 | 600 | $5,200 | $13,500 | -$8,300 | $96,915 |
| 11 | 800 | $7,000 | $13,500 | -$6,500 | $103,415 |
| 12 | 1,000 | $8,500 | $14,000 | -$5,500 | $108,915 |

**Year 1 total spend: ~$109,000**
**Year 1 total revenue: ~$33,600**
**Net cash required: ~$75,000** (covered by $150K raise with ~$41K buffer remaining)

### The Revenue Crossover

```
$15K ┤
     │                                              ╱ Revenue
$12K ┤                                           ╱
     │                                        ╱
$10K ┤                                     ╱
     │                                  ╱
 $8K ┤                               ╱  ← Revenue crosses burn here
     │            ─────────────────────── Burn Rate
 $6K ┤                         ╱
     │                      ╱
 $4K ┤                   ╱
     │                ╱
 $2K ┤             ╱
     │          ╱
   0 ┤───────╱────────────────────────────────────
     M1    M3    M6    M9    M12   M15   M18   M21
```

---

## Path to Break-Even

### When Does Revenue Cover Costs?

| Scenario | Break-Even Users | Break-Even MRR | Expected Timeline |
|----------|-----------------|----------------|-------------------|
| Conservative (team of 3) | 1,600 | $14,000 | Month 15-18 |
| Base case (team of 4) | 2,000 | $17,000 | Month 18-21 |
| Aggressive (team of 5) | 2,500 | $22,000 | Month 21-24 |

### Break-Even Assumptions

| Component | Monthly Cost at Break-Even |
|-----------|--------------------------|
| Team (4 people) | $10,000 |
| Infrastructure | $500 |
| LLM/AI costs (free tier + fallback) | $500 |
| Email (Resend) | $100 |
| Marketing | $3,000 |
| Operations | $1,500 |
| **Total monthly burn** | **$15,600** |
| **Required MRR** | **~$16,000** |
| **Users needed** (at $9 ARPU) | **~1,800** |

After break-even, every new user contributes directly to profit. With 96%+ gross margins, the business becomes highly cash-generative quickly.

---

## Grant Funding Opportunities

Grants accelerate growth without dilution. Here's how grant funding would be deployed:

### Digital Inclusion Pilot — $20,000–$50,000

| Line Item | Amount | Deliverable |
|-----------|--------|------------|
| Platform costs for 500 MSMEs (6 months) | $12,000 | Full BIOS access — content, leads, email, analytics |
| Onboarding workshops (10 sessions) | $5,000 | In-person training in Nairobi, Mombasa, Kisumu |
| Impact measurement tools | $3,000 | Survey platforms, analytics dashboards |
| Program coordinator (6 months) | $9,000 | Dedicated person managing the pilot |
| Final impact report | $2,000 | Professional report for grant donor |
| **Total** | **$31,000** | |

**Measurable outcomes:** Posting frequency, engagement metrics, leads captured, email subscribers grown, business revenue change, time saved, digital confidence score.

### Women Entrepreneurs Program — $30,000–$50,000

| Line Item | Amount | Deliverable |
|-----------|--------|------------|
| Platform costs for 300 women-owned SMEs (12 months) | $14,400 | Full-year BIOS access including conversion engine |
| 12 monthly workshops | $12,000 | "AI-Powered Business Intelligence for Women in Business" |
| Childcare support at workshops | $2,400 | Remove participation barriers |
| Story collection & documentation | $3,000 | Video testimonials, written case studies |
| Program management | $12,000 | Coordinator + travel |
| Reporting | $2,000 | Impact measurement and donor report |
| **Total** | **$45,800** | |

### Multi-Language Expansion — $30,000

| Line Item | Amount | Deliverable |
|-----------|--------|------------|
| Swahili prompt engineering | $8,000 | All 6 agents generating content in Swahili |
| Sheng content adaptation | $4,000 | Informal Swahili for youth-targeted brands |
| French content support | $8,000 | For DRC, Rwanda, Cameroon expansion |
| Yoruba content support | $6,000 | For Nigerian market |
| Testing & quality assurance | $4,000 | Native speaker review of AI-generated content |
| **Total** | **$30,000** | |

---

## Bridge Round: $500,000 — Regional Expansion

**Timeline:** Q1–Q2 2027 (after proving Kenya PMF)
**Trigger:** 1,000+ paying users, $5,000+ MRR, proven unit economics, active partner network

### Allocation

| Category | Amount | % | Purpose |
|----------|--------|---|---------|
| **Nigeria launch** | $100,000 | 20% | Paystack integration, Lagos GTM, local partnerships, partner program activation |
| **South Africa launch** | $80,000 | 16% | Ozow/SnapScan integration, Jo'burg GTM |
| **Team expansion** (5 new hires) | $180,000 | 36% | Country leads, platform engineer, customer success, content creator |
| **Product development** | $60,000 | 12% | WhatsApp integration, video content, agency white-label, advanced email sequences |
| **Marketing at scale** | $50,000 | 10% | Multi-country campaigns, influencer partnerships, regional partner programs |
| **Operations & contingency** | $30,000 | 6% | Legal per country, compliance, buffer |
| **Total** | **$500,000** | **100%** | |

### Bridge Round Success Metrics

| Metric | Target |
|--------|--------|
| Total users (3 countries) | 10,000 |
| MRR | $90,000 |
| Revenue run rate | $1.1M ARR |
| Countries live | 3 (Kenya, Nigeria, South Africa) |
| Agency partners | 50+ |
| Growth Partners | 200+ |
| Team size | 10-12 |

---

## Series A Readiness: $2M–$5M

**Timeline:** Q3–Q4 2027
**Trigger:** $1M ARR, proven retention, multi-country traction, active partner network

We don't need Series A to survive — we'll be nearing break-even. Series A is for **acceleration**:

| Category | Allocation | Purpose |
|----------|-----------|---------|
| Pan-African expansion (5+ new countries) | 30% | Ghana, Tanzania, Uganda, Rwanda, Egypt |
| Team scaling (20-30 people) | 35% | Engineering, sales, support across regions |
| Product (marketplace, video, enterprise) | 20% | Revenue-expanding features |
| Brand & marketing at continental scale | 15% | Become the category name in Africa |

---

## Financial Controls & Governance

### How We Protect Investor Capital

| Control | Implementation |
|---------|---------------|
| **Monthly financial reports** | Revenue, expenses, runway, KPIs shared with investors by 5th of each month |
| **Quarterly board meetings** | Formal review of strategy, metrics, and budget vs. actual |
| **Bank account controls** | Dual signatory for withdrawals above KES 500,000 |
| **Expense policy** | All expenses >$500 require founder + board approval |
| **Accounting** | Professional bookkeeper from Month 1. Annual audit from Year 2. |
| **Budget vs. Actual tracking** | Monthly comparison with variance explanation for anything >10% off |
| **Runway dashboard** | Real-time dashboard showing months of runway remaining |

### Burn Rate Guardrails

| Trigger | Action |
|---------|--------|
| Runway drops below 6 months | Freeze non-essential hiring. Reduce marketing to organic + partner referrals only. |
| Runway drops below 4 months | Salary reduction (founder first). Initiate bridge fundraising. |
| Revenue exceeds projections by 50%+ | Accelerate hiring plan. Increase marketing + partner activation budget. |
| Revenue misses projections by 30%+ | Root cause analysis within 2 weeks. Pivot GTM strategy. Reduce burn. |

---

## Risk-Adjusted Scenarios

### Optimistic Scenario (everything goes right)

| Month | Users | MRR | Cumulative Revenue |
|-------|-------|-----|--------------------|
| 6 | 300 | $2,700 | $10,000 |
| 12 | 2,000 | $18,000 | $70,000 |
| 18 | 5,000 | $45,000 | $230,000 |

**Outcome:** Break-even by Month 12. Bridge round purely for acceleration. Strong Series A at $5M+.

### Base Case (realistic)

| Month | Users | MRR | Cumulative Revenue |
|-------|-------|-----|--------------------|
| 6 | 180 | $1,500 | $5,000 |
| 12 | 1,000 | $8,500 | $34,000 |
| 18 | 3,000 | $27,000 | $115,000 |

**Outcome:** Break-even by Month 18. Bridge round needed for regional expansion. Series A at $2M–$3M.

### Pessimistic Scenario (slow adoption)

| Month | Users | MRR | Cumulative Revenue |
|-------|-------|-----|--------------------|
| 6 | 80 | $560 | $1,700 |
| 12 | 400 | $3,200 | $13,000 |
| 18 | 800 | $6,400 | $32,000 |

**Outcome:** Runway extends to Month 18 on $150K (low burn, some revenue). Need to raise bridge or pivot GTM. Product stays viable — user unit economics still work.

### Worst Case (pivot needed)

| Signal | Response |
|--------|----------|
| <50 users after 6 months | GTM problem, not product. Shift: agency-first strategy (sell through agencies via Wakala plan). Lean into Growth Partner Program. |
| <5% trial → paid conversion | Value demonstration problem. Test: improve onboarding, show conversion engine value (leads captured, emails sent) within first 3 days. |
| High churn (>15%/month) | Product-market fit issue. Deep user interviews. Feature/positioning pivot. |
| LLM free models all fail | Switch to self-hosted open-source models (Llama, Mistral). Increase paid fallback budget. |

**Even in the worst case, the core code, 16 modules, agents, and conversion engine retain value.** The question is GTM strategy, not product viability.

---

## Return on Investment Projections

### For Angel Investors ($50K–$100K at Seed)

| Scenario | Equity (est.) | Year 3 Valuation | Return Multiple |
|----------|--------------|-------------------|----------------|
| Optimistic | 5-8% | $36M (5x ARR of $7.2M) | 18x–29x |
| Base case | 5-8% | $14M (2x ARR of $7.2M) | 7x–11x |
| Conservative | 5-8% | $7M (1x ARR of $7.2M) | 3.5x–5.6x |

### For VC Funds ($150K–$300K at Seed)

| Exit Scenario | Timeline | Estimated Valuation | Fund Return (at 15% equity) |
|---------------|----------|--------------------|-----------------------------|
| Series A exit (secondary) | Year 2 | $5M–$10M | $750K–$1.5M (2.5x–5x) |
| Series B exit | Year 3-4 | $20M–$50M | $3M–$7.5M (10x–25x) |
| Acquisition (by Hootsuite, HubSpot, African tech co.) | Year 3-5 | $10M–$30M | $1.5M–$4.5M (5x–15x) |
| IPO pathway (long term) | Year 5-7 | $100M+ | $15M+ (50x+) |

### Comparable Exits (African SaaS)

| Company | Country | Category | Exit/Valuation | Stage at Raise |
|---------|---------|----------|---------------|---------------|
| Paystack | Nigeria | Payments | $200M (Stripe acquisition) | Started with $8M seed |
| Flutterwave | Nigeria | Payments | $3B valuation | Started with seed |
| mPharma | Ghana | Health tech | $100M+ valuation | Started with $500K seed |
| Andela | Nigeria | Talent | $1.5B valuation | Started with seed |

**Kova sits in the SaaS + AI + Africa intersection — the fastest-growing segment in African tech. And unlike most African SaaS plays, Kova has a built-in distribution channel (Growth Partner Program) that reduces CAC as the network grows.**

---

## Summary — How Every Dollar is Spent

### The One-Page Version

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  FUNDING ASK: $150,000 – $300,000 (Seed)                       │
│  RUNWAY: 12–18 months                                           │
│  GOAL: 1,000 paying users in Kenya                              │
│                                                                 │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │                   WHERE THE MONEY GOES                     │ │
│  │                                                            │ │
│  │   44%  ████████████████████░░░░░░░░░░░  Team (2-4 hires)  │ │
│  │   21%  ██████████░░░░░░░░░░░░░░░░░░░░░  Marketing & GTM   │ │
│  │   13%  ██████░░░░░░░░░░░░░░░░░░░░░░░░░  LLM & AI costs    │ │
│  │   10%  █████░░░░░░░░░░░░░░░░░░░░░░░░░░  Infrastructure     │ │
│  │   10%  █████░░░░░░░░░░░░░░░░░░░░░░░░░░  Operations         │ │
│  │    2%  █░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Contingency        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  WHAT'S ALREADY BUILT:                                          │
│  ✓ 16 app modules (full Business Intelligence OS)               │
│  ✓ 6 AI agents + 12+ automated tasks                           │
│  ✓ Conversion engine (Kova Links + Leads + Email)               │
│  ✓ Growth Partner Program (built-in distribution)               │
│  ✓ Teams, M-Pesa, Stripe, 9 platforms, R2 storage              │
│  ✓ Estimated build value: $159K–$245K                           │
│                                                                 │
│  WHAT INVESTORS GET:                                            │
│  ✓ Live product (not a prototype) — 16 integrated modules       │
│  ✓ 96%+ gross margins (3-tier free LLM strategy)                │
│  ✓ $4.6B TAM with zero direct competitors                      │
│  ✓ CLV:CAC >12:1                                                │
│  ✓ Built-in growth via Partner Program                          │
│  ✓ Path to $1.1M ARR in 24 months                              │
│  ✓ Structural AI cost tailwind (margins improve over time)      │
│                                                                 │
│  BREAK-EVEN: ~1,800 users (~Month 15-18)                       │
│  YEAR 3 TARGET: 50,000 users / $7.2M ARR                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### The Core Principle

**Every shilling raised either acquires users or serves users.** There are no vanity expenditures. No expensive office. No unnecessary hires ahead of demand. We scale costs with revenue, not ambition.

The product is built — $159K-$245K worth of engineering. The market is waiting. The capital is the fuel.

---

> *"We don't need money to build. We need money to grow."*
>
> **Kova — Every shilling accounted for.**

---

*Confidential — April 2026*
*For investor, grant, and partner review only.*
