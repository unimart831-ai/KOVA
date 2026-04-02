# Kova Agent — Funding Requirements & Fund Usage Plan

### Detailed Financial Blueprint for Investors, Grants, and Partners

**Confidential | April 2026**

---

> This document provides a transparent, line-by-line breakdown of how Kova Agent will use every shilling raised — from seed capital through Series A readiness. It covers current operating costs, funding requirements by stage, detailed allocation tables, milestone-linked disbursements, and financial controls.

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

### Product (100% Functional)

| Component | Status | Value Created |
|-----------|--------|--------------|
| Django web application (8 app modules) | ✅ Live | Months of engineering effort |
| 6 AI agents (Create, Analyst, Research, Adapt, Engage, Strategist) | ✅ Running | Core product IP |
| 9 Celery Beat scheduled tasks (24/7 automation) | ✅ Running | Autonomous operation |
| Facebook + Instagram publishing (real posts verified) | ✅ Live | Platform integration |
| Content DNA learning system | ✅ Live | Competitive moat |
| M-Pesa billing (STK Push, full flow) | ✅ Integrated | Revenue infrastructure |
| Stripe billing (international) | ✅ Integrated | Global payments |
| 4-tier plan system with middleware enforcement | ✅ Live | Monetization ready |
| Daily Brief generation | ✅ Live | User retention feature |
| Competitor intelligence system | ✅ Live | Premium feature |
| PWA (installable on mobile) | ✅ Live | Mobile distribution |
| Railway deployment (Web + Worker + Beat + Redis + PostgreSQL) | ✅ Live | Production infrastructure |
| OAuth social login (Meta) | ✅ Live | User onboarding |
| Provider abstraction for 9 platforms | ✅ Built | Scalable architecture |

### Estimated Development Value

If this product were built by an agency or outsourced team:

| Item | Estimated Cost |
|------|---------------|
| Backend development (Django, Celery, 8 apps) | $25,000–$40,000 |
| 6 AI agent system (prompts, orchestration, learning loop) | $15,000–$25,000 |
| Platform integrations (OAuth, Graph API, publishing) | $8,000–$12,000 |
| Billing system (M-Pesa + Stripe) | $5,000–$8,000 |
| Frontend (templates, HTMX, Tailwind, PWA) | $8,000–$12,000 |
| DevOps & deployment | $3,000–$5,000 |
| **Total estimated build value** | **$64,000–$102,000** |

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
| Domain & DNS | ~$1 | 125 | Annual, amortized |
| OpenRouter API (LLM) | $2–$10 | 250–1,250 | Usage-based, currently low |
| M-Pesa API (sandbox) | $0 | 0 | Free in sandbox mode |
| GitHub (free tier) | $0 | 0 | Source control |
| **Total current monthly** | **$28–$36** | **KES 3,500–4,500** | |

**Annual current operating cost: ~$400–$430**

This is the power of modern infrastructure — a full production system with 4 services and a database running for less than KES 5,000/month.

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
| LLM API credits (OpenRouter) | 75,000 | 600 | 15% | AI costs for first 50 users |
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
| Trial → Paid conversion | >10% | Paid users / total signups |
| Daily Brief open rate | >50% | Users who read their brief daily |
| User feedback score | >7/10 | Post-trial survey |

---

## Seed Round: $150,000–$300,000 — Kenya Launch

**Source:** Angel investors, Africa-focused VCs, grants
**Timeline:** Q3 2026 – Q2 2027 (12-18 months)
**Goal:** 1,000 paying users, revenue-generating, ready for regional expansion

### Why This Amount

| Consideration | Reasoning |
|--------------|-----------|
| **$150K minimum** | Covers 12 months of team (2 hires) + infrastructure + marketing. Lean but viable. |
| **$300K ideal** | 18-month runway. Allows 3 hires + aggressive marketing + Nigeria/SA groundwork. |
| **Why not more?** | We don't need $1M to prove Kenya PMF. African SaaS rounds are capital-efficient. Over-raising at pre-revenue creates valuation pressure. |
| **Why not less?** | Below $100K, we can't hire — limiting growth to founder-only capacity. Marketing budget becomes too thin for meaningful traction. |

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
│  │   MARKETING & GTM   │  Campaigns, partnerships, events│
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
| → Growth/Marketing Lead (1) | $30,000 | $2,500 | 12 months. Full-time. GTM execution. |
| **Subtotal Team** | **$66,000** | **$5,500** | **44%** |
| | | | |
| **Marketing & User Acquisition** | | | |
| → Digital ads (Facebook, Google, Instagram) | $12,000 | $1,000 | Targeted: Kenyan SME owners |
| → WhatsApp campaigns (data + tools) | $3,600 | $300 | Direct outreach to MSME groups |
| → Content marketing (blog, video, social) | $4,800 | $400 | SEO, thought leadership, case studies |
| → Events & workshops (SME meetups) | $3,600 | $300 | Monthly in Nairobi, quarterly in Mombasa/Kisumu |
| → Referral program rewards | $3,000 | $250 | "Invite a business, get 1 month free" |
| → Agency partnership onboarding | $2,400 | $200 | Co-branded materials, partner support |
| → PR & media outreach | $2,400 | $200 | Tech publications, podcast features |
| **Subtotal Marketing** | **$31,800** | **$2,650** | **21%** |
| | | | |
| **LLM & AI Costs** | | | |
| → OpenRouter API credits | $18,000 | $1,500 | ~$0.40/user × 1,000 users at peak + buffer |
| → Image generation API | $3,000 | $250 | Hugging Face / Together.ai |
| → Model experimentation | $1,500 | $125 | Testing new models for quality/cost |
| **Subtotal AI** | **$22,500** | **$1,875** | **15%** |
| | | | |
| **Infrastructure** | | | |
| → Railway / Cloud hosting | $9,600 | $800 | Scale up as users grow |
| → Domain, SSL, CDN | $1,200 | $100 | Production domain + Cloudflare |
| → Monitoring (Sentry, uptime) | $1,800 | $150 | Error tracking, alerting |
| → Email service (Resend) | $1,200 | $100 | Transactional + daily brief emails |
| **Subtotal Infrastructure** | **$13,800** | **$1,150** | **9%** |
| | | | |
| **Operations** | | | |
| → Legal (company registration, terms, privacy) | $3,000 | — | One-time + annual |
| → Accounting & compliance | $2,400 | $200 | Monthly bookkeeping, tax filings |
| → Coworking / office | $3,600 | $300 | Shared workspace in Nairobi |
| → Software tools (GitHub, Figma, analytics) | $2,400 | $200 | Team productivity |
| → Data protection registration (ODPC Kenya) | $500 | — | One-time |
| → M-Pesa production fees | $1,200 | $100 | Transaction fees, API costs |
| → Travel (partnership meetings) | $1,800 | $150 | Nairobi, Mombasa, Kisumu |
| **Subtotal Operations** | **$14,900** | **$950** | **10%** |
| | | | |
| **Contingency** | **$1,000** | — | **1%** |
| | | | |
| **TOTAL** | **$150,000** | **~$12,125** | **100%** |

**Runway at $150K: ~12 months** (at $12,125/month burn + growing revenue offset)

---

### Scenario B: $200,000 (Target Raise)

Everything in Scenario A, plus:

| Additional Allocation | Amount | Purpose |
|----------------------|--------|---------|
| 3rd hire: Designer/Frontend | $18,000 | 12 months, part-time → full-time. Mobile UX, marketing assets. |
| Expanded marketing budget | $15,000 | Double digital ad spend. More events. |
| Nigeria/SA market research | $5,000 | Payment integration research, user interviews. |
| Extended contingency | $12,000 | 3-month safety net |
| **Additional total** | **$50,000** | |

**Runway at $200K: ~15 months**

---

### Scenario C: $300,000 (Maximum Raise)

Everything in Scenario B, plus:

| Additional Allocation | Amount | Purpose |
|----------------------|--------|---------|
| 4th hire: Full-time AI Engineer | $36,000 | Dedicated to agent optimization, model fine-tuning |
| Nigeria launch GTM | $20,000 | Paystack integration, Lagos marketing, local partnerships |
| South Africa launch GTM | $15,000 | Ozow/SnapScan integration, Jo'burg marketing |
| Platform expansion (Twitter, LinkedIn APIs) | $8,000 | API review fees, compliance, testing |
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
| Initial marketing campaigns | 25% |

**Milestone to unlock Tranche 2:**
- 100 active users
- 30+ paying subscribers
- Trial → Paid conversion >8%
- Target timeline: 3 months

### Tranche 2: 35% on user milestone ($52K–$105K)

**Released when 100 active users reached**

| Use | Allocation |
|-----|-----------|
| Marketing scale-up | 40% |
| LLM API credits (growing usage) | 25% |
| 3rd hire | 20% |
| Operations | 15% |

**Milestone to unlock Tranche 3:**
- 500 active users
- $2,000+ MRR
- 3+ agency partnerships
- Target timeline: 3 months after Tranche 2

### Tranche 3: 25% on revenue milestone ($37K–$75K)

**Released when $2,000 MRR reached**

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
| 1 | **Backend/AI Engineer** | Month 1 | 375,000 | $3,000 | Agent optimization, new platform integrations, API development |
| 2 | **Growth Lead** | Month 1 | 312,500 | $2,500 | GTM execution, partnerships, community building, content marketing |
| 3 | **Designer (part → full time)** | Month 3 | 187,500 | $1,500 | Mobile UX improvement, marketing assets, brand identity |
| 4 | **AI Engineer** (if $300K) | Month 4 | 375,000 | $3,000 | Prompt engineering, model fine-tuning, Content DNA evolution |

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
| Platform Engineer | Month 14 | $3,000 | Twitter, LinkedIn, TikTok integrations |
| Nigeria Country Lead | Month 15 | $2,500 | Local GTM, partnerships, market development |
| South Africa Country Lead | Month 16 | $2,500 | Local GTM, partnerships |
| Content Creator (in-house) | Month 15 | $1,500 | Kova's own social media, case studies, blog |

---

## Infrastructure Scaling Plan

### Cost Progression as Users Grow

| Users | Infrastructure | LLM/AI | Total Monthly | Revenue Offset |
|-------|---------------|--------|--------------|---------------|
| 0–50 | $30 | $20 | $50 | $50–$200 |
| 50–200 | $50 | $80 | $130 | $400–$1,000 |
| 200–500 | $100 | $200 | $300 | $1,000–$3,000 |
| 500–1,000 | $200 | $400 | $600 | $3,000–$7,500 |
| 1,000–5,000 | $500 | $2,000 | $2,500 | $7,500–$40,000 |
| 5,000–10,000 | $1,200 | $4,000 | $5,200 | $40,000–$85,000 |

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
| **Content marketing (SEO/blog)** | $4,800 | $400 | 100 | $48 (but compounds) |
| **Events & workshops** | $3,600 | $300 | 80 | $45 |
| **Referral program** | $3,000 | $250 | 120 | $25 |
| **Agency partnerships** | $2,400 | $200 | 100 (via agencies) | $24 |
| **PR/Media** | $2,400 | $200 | 50 | $48 (brand building) |
| **Total** | **$31,800** | **$2,650** | **~1,200 signups** | **Blended: ~$26** |

At 30% trial → engagement and 15% trial → paid conversion: **~180 paying users from marketing alone**, supplemented by organic/word-of-mouth for remaining 820.

### Marketing Mix Evolution

| Phase | Primary Channel | Budget Share |
|-------|----------------|-------------|
| Months 1-3 | WhatsApp groups + direct outreach | 40% |
| Months 4-6 | Facebook/Instagram ads + content | 35% |
| Months 7-9 | Referrals + agency partnerships | 30% |
| Months 10-12 | SEO/content + PR + events | 35% |

The mix shifts from high-touch (WhatsApp outreach) to scalable (content, referrals, partnerships) as we learn which channels convert best.

---

## LLM & AI Cost Projections

### Cost Per User Breakdown

Each active Kova user generates these AI calls daily:

| Agent Task | Calls/Day | Avg Tokens/Call | Daily Cost/User |
|-----------|----------|----------------|----------------|
| Create Agent (content generation) | 0.5 | 2,000 | $0.003 |
| Analyst (DNA extraction) | 0.5 | 1,000 | $0.001 |
| Analyst (engagement prediction) | 0.5 | 800 | $0.001 |
| Engage Agent (analysis + replies) | 2.0 | 1,500 | $0.004 |
| Research Agent | 0.08 (every 12h) | 3,000 | $0.001 |
| Strategist | 0.12 (every 8h) | 4,000 | $0.002 |
| Daily Brief compilation | 0.07 (once/day) | 3,000 | $0.001 |
| **Total daily** | | | **~$0.013** |
| **Total monthly** | | | **~$0.40** |

### Model Cost Trends

| Period | Cost per 1M tokens (input) | Cost per 1M tokens (output) | Trend |
|--------|--------------------------|---------------------------|-------|
| 2024 | $15.00 (GPT-4) | $45.00 | — |
| 2025 | $2.50 (GPT-4o) | $10.00 | -83% |
| 2026 (now) | $0.10 (Gemini Flash) | $0.40 | -96% from 2024 |
| 2027 (projected) | $0.05 | $0.20 | -50% from now |

**Key insight:** Our per-user AI cost is shrinking every quarter. By 2027, the same workload may cost $0.20/user instead of $0.40. This is a **structural tailwind** — our margins expand automatically.

### Annual LLM Cost by User Scale

| Users | Monthly AI Cost | Annual AI Cost | % of Revenue |
|-------|----------------|---------------|-------------|
| 50 | $20 | $240 | ~5% |
| 200 | $80 | $960 | ~6% |
| 500 | $200 | $2,400 | ~6% |
| 1,000 | $400 | $4,800 | ~5% |
| 5,000 | $2,000 | $24,000 | ~5% |
| 10,000 | $4,000 | $48,000 | ~5% |

AI costs remain a consistent ~5-6% of revenue across all scales. This is sustainable.

---

## Revenue Projections vs. Burn Rate

### Month-by-Month Year 1 (Kenya Launch)

| Month | Users | MRR | Monthly Burn | Net Burn | Cumulative Spend |
|-------|-------|-----|-------------|----------|-----------------|
| 1 | 10 | $50 | $8,000 | -$7,950 | $7,950 |
| 2 | 25 | $150 | $9,000 | -$8,850 | $16,800 |
| 3 | 50 | $350 | $10,000 | -$9,650 | $26,450 |
| 4 | 80 | $560 | $11,500 | -$10,940 | $37,390 |
| 5 | 120 | $900 | $12,000 | -$11,100 | $48,490 |
| 6 | 180 | $1,350 | $12,500 | -$11,150 | $59,640 |
| 7 | 250 | $1,900 | $12,500 | -$10,600 | $70,240 |
| 8 | 350 | $2,800 | $13,000 | -$10,200 | $80,440 |
| 9 | 450 | $3,600 | $13,000 | -$9,400 | $89,840 |
| 10 | 600 | $4,800 | $13,500 | -$8,700 | $98,540 |
| 11 | 800 | $6,400 | $13,500 | -$7,100 | $105,640 |
| 12 | 1,000 | $7,500 | $14,000 | -$6,500 | $112,140 |

**Year 1 total spend: ~$112,000**
**Year 1 total revenue: ~$30,400**
**Net cash required: ~$82,000** (covered by $150K raise with ~$38K buffer remaining)

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
| Conservative (team of 3) | 1,800 | $14,000 | Month 15-18 |
| Base case (team of 4) | 2,200 | $17,000 | Month 18-21 |
| Aggressive (team of 5) | 2,800 | $22,000 | Month 21-24 |

### Break-Even Assumptions

| Component | Monthly Cost at Break-Even |
|-----------|--------------------------|
| Team (4 people) | $10,000 |
| Infrastructure | $500 |
| LLM/AI costs | $900 |
| Marketing | $3,000 |
| Operations | $1,500 |
| **Total monthly burn** | **$15,900** |
| **Required MRR** | **~$16,000** |
| **Users needed** (at $8 ARPU) | **~2,000** |

After break-even, every new user contributes directly to profit. With 94%+ gross margins, the business becomes highly cash-generative quickly.

---

## Grant Funding Opportunities

Grants accelerate growth without dilution. Here's how grant funding would be deployed:

### Digital Inclusion Pilot — $20,000–$50,000

| Line Item | Amount | Deliverable |
|-----------|--------|------------|
| Platform costs for 500 MSMEs (6 months) | $12,000 | 500 businesses × $4/month average |
| Onboarding workshops (10 sessions) | $5,000 | In-person training in Nairobi, Mombasa, Kisumu |
| Impact measurement tools | $3,000 | Survey platforms, analytics dashboards |
| Program coordinator (6 months) | $9,000 | Dedicated person managing the pilot |
| Final impact report | $2,000 | Professional report for grant donor |
| **Total** | **$31,000** | |

**Measurable outcomes:** Social media posting frequency, engagement metrics, business revenue change, time saved, digital confidence score.

### Women Entrepreneurs Program — $30,000–$50,000

| Line Item | Amount | Deliverable |
|-----------|--------|------------|
| Platform costs for 300 women-owned SMEs (12 months) | $14,400 | Full-year access |
| 12 monthly workshops | $12,000 | "AI-Powered Marketing for Women in Business" |
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
**Trigger:** 1,000+ paying users, $5,000+ MRR, proven unit economics

### Allocation

| Category | Amount | % | Purpose |
|----------|--------|---|---------|
| **Nigeria launch** | $100,000 | 20% | Paystack integration, Lagos GTM, local partnerships, 3-month campaign |
| **South Africa launch** | $80,000 | 16% | Ozow/SnapScan integration, Jo'burg GTM |
| **Team expansion** (5 new hires) | $180,000 | 36% | Country leads, platform engineer, customer success, content creator |
| **Product development** | $60,000 | 12% | Twitter/LinkedIn integrations, team collaboration features, video content |
| **Marketing at scale** | $50,000 | 10% | Multi-country campaigns, influencer partnerships |
| **Operations & contingency** | $30,000 | 6% | Legal per country, compliance, buffer |
| **Total** | **$500,000** | **100%** | |

### Bridge Round Success Metrics

| Metric | Target |
|--------|--------|
| Total users (3 countries) | 10,000 |
| MRR | $85,000 |
| Revenue run rate | $1M ARR |
| Countries live | 3 (Kenya, Nigeria, South Africa) |
| Agency partners | 50+ |
| Team size | 10-12 |

---

## Series A Readiness: $2M–$5M

**Timeline:** Q3–Q4 2027
**Trigger:** $1M ARR, proven retention, multi-country traction

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
| Runway drops below 6 months | Freeze non-essential hiring. Reduce marketing to organic only. |
| Runway drops below 4 months | Salary reduction (founder first). Initiate bridge fundraising. |
| Revenue exceeds projections by 50%+ | Accelerate hiring plan. Increase marketing budget. |
| Revenue misses projections by 30%+ | Root cause analysis within 2 weeks. Pivot GTM strategy. Reduce burn. |

---

## Risk-Adjusted Scenarios

### Optimistic Scenario (everything goes right)

| Month | Users | MRR | Cumulative Revenue |
|-------|-------|-----|--------------------|
| 6 | 300 | $2,400 | $8,000 |
| 12 | 2,000 | $16,000 | $60,000 |
| 18 | 5,000 | $40,000 | $200,000 |

**Outcome:** Break-even by Month 12. Bridge round purely for acceleration. Strong Series A at $5M+.

### Base Case (realistic)

| Month | Users | MRR | Cumulative Revenue |
|-------|-------|-----|--------------------|
| 6 | 180 | $1,350 | $4,500 |
| 12 | 1,000 | $7,500 | $30,000 |
| 18 | 3,000 | $24,000 | $100,000 |

**Outcome:** Break-even by Month 18. Bridge round needed for regional expansion. Series A at $2M–$3M.

### Pessimistic Scenario (slow adoption)

| Month | Users | MRR | Cumulative Revenue |
|-------|-------|-----|--------------------|
| 6 | 80 | $500 | $1,500 |
| 12 | 400 | $3,000 | $12,000 |
| 18 | 800 | $6,000 | $30,000 |

**Outcome:** Runway extends to Month 18 on $150K (low burn, some revenue). Need to raise bridge or pivot GTM. Product stays viable — user unit economics still work.

### Worst Case (pivot needed)

| Signal | Response |
|--------|----------|
| <50 users after 6 months | Likely GTM problem, not product. Shift: agency-first strategy (sell through agencies). |
| <5% trial → paid conversion | Pricing or value demonstration problem. Test: lower entry price, improve onboarding. |
| High churn (>15%/month) | Product-market fit issue. Deep user interviews. Feature/positioning pivot. |
| LLM costs spike unexpectedly | Switch to open-source models (Llama, Mistral). Self-host if needed. |

**Even in the worst case, the core code, agents, and architecture retain value.** The question is GTM strategy, not product viability.

---

## Return on Investment Projections

### For Angel Investors ($50K–$100K at Seed)

| Scenario | Equity (est.) | Year 3 Valuation | Return Multiple |
|----------|--------------|-------------------|----------------|
| Optimistic | 5-8% | $30M (5x ARR of $6M) | 15x–24x |
| Base case | 5-8% | $12M (2x ARR of $6M) | 6x–10x |
| Conservative | 5-8% | $6M (1x ARR of $6M) | 3x–5x |

### For VC Funds ($150K–$300K at Seed)

| Exit Scenario | Timeline | Estimated Valuation | Fund Return (at 15% equity) |
|---------------|----------|--------------------|-----------------------------|
| Series A exit (secondary) | Year 2 | $5M–$10M | $750K–$1.5M (2.5x–5x) |
| Series B exit | Year 3-4 | $20M–$50M | $3M–$7.5M (10x–25x) |
| Acquisition (by Hootsuite, Buffer, African tech co.) | Year 3-5 | $10M–$30M | $1.5M–$4.5M (5x–15x) |
| IPO pathway (long term) | Year 5-7 | $100M+ | $15M+ (50x+) |

### Comparable Exits (African SaaS)

| Company | Country | Category | Exit/Valuation | Stage at Raise |
|---------|---------|----------|---------------|---------------|
| Paystack | Nigeria | Payments | $200M (Stripe acquisition) | Started with $8M seed |
| Flutterwave | Nigeria | Payments | $3B valuation | Started with seed |
| mPharma | Ghana | Health tech | $100M+ valuation | Started with $500K seed |
| Andela | Nigeria | Talent | $1.5B valuation | Started with seed |

**Kova sits in the SaaS + AI + Africa intersection — the fastest-growing segment in African tech.**

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
│  │   15%  ███████░░░░░░░░░░░░░░░░░░░░░░░░  LLM & AI costs    │ │
│  │    9%  ████░░░░░░░░░░░░░░░░░░░░░░░░░░░  Infrastructure     │ │
│  │   10%  █████░░░░░░░░░░░░░░░░░░░░░░░░░░  Operations         │ │
│  │    1%  ░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░░  Contingency        │ │
│  └────────────────────────────────────────────────────────────┘ │
│                                                                 │
│  WHAT INVESTORS GET:                                            │
│  ✓ Live product (not a prototype)                               │
│  ✓ 94%+ gross margins                                           │
│  ✓ $4.6B TAM with zero direct competitors                      │
│  ✓ CLV:CAC >10:1                                                │
│  ✓ Path to $1M ARR in 24 months                                │
│  ✓ Structural AI cost tailwind (margins improve over time)      │
│                                                                 │
│  BREAK-EVEN: ~2,000 users (~Month 15-18)                       │
│  YEAR 3 TARGET: 50,000 users / $6M ARR                         │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### The Core Principle

**Every shilling raised either acquires users or serves users.** There are no vanity expenditures. No expensive office. No unnecessary hires ahead of demand. We scale costs with revenue, not ambition.

The product is built. The market is waiting. The capital is the fuel.

---

> *"We don't need money to build. We need money to grow."*
>
> **Kova Agent — Every shilling accounted for.**

---

*Confidential — April 2026*
*For investor, grant, and partner review only.*
