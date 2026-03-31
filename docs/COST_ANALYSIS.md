# Kova Agent — Cost & Unit Economics Analysis
> Can we charge KES 99-3500 and not burn?

**Last updated:** April 1, 2026
**Currency:** All costs in USD unless marked KES. Exchange rate: 1 USD ≈ 142 KES
**Goal:** Prove that Kova's pricing is sustainable at every plan tier, even with the best AI models

---

## Table of Contents
1. [Revenue Per User](#1-revenue-per-user)
2. [Cost Category Breakdown](#2-cost-category-breakdown)
3. [AI Model Costs — Task-Level Analysis](#3-ai-model-costs--task-level-analysis)
4. [Image Generation Costs](#4-image-generation-costs)
5. [Infrastructure Costs (Railway)](#5-infrastructure-costs-railway)
6. [Third-Party Service Costs](#6-third-party-service-costs)
7. [WhatsApp Conversation Costs](#7-whatsapp-conversation-costs)
8. [Full Unit Economics Model](#8-full-unit-economics-model)
9. [Scenario Modeling — 10 to 10,000 Users](#9-scenario-modeling--10-to-10000-users)
10. [Break-Even Analysis](#10-break-even-analysis)
11. [Cost Control Strategies](#11-cost-control-strategies)
12. [Risk Scenarios — What Could Go Wrong](#12-risk-scenarios--what-could-go-wrong)
13. [Decision Matrix — Which Models to Use](#13-decision-matrix--which-models-to-use)

---

## 1. Revenue Per User

### Current Plan Tiers

| Plan | Swahili Name | KES/mo | USD/mo | Platforms | Posts/mo | Seeds/mo | Agents |
|------|-------------|--------|--------|-----------|----------|----------|--------|
| **Starter** | Jipange | 99 | ~$0.70 | 1 | 15 | 10 | Create, Analyst |
| **Growth** | Kazi | 500 | ~$3.52 | 3 | 50 | 30 | + Research, Adapt |
| **Pro** | Biashara | 1,500 | ~$10.56 | 10 | Unlimited | Unlimited | + Engage, Strategist |
| **Agency** | Wakala | 3,500 | ~$24.65 | 25 | Unlimited | Unlimited | All 6 agents |

### Annual Revenue Per User (if retained 12 months)

| Plan | Monthly | Annual | LTV (assume 8-month avg retention) |
|------|---------|--------|-----|
| Starter | $0.70 | $8.40 | $5.60 |
| Growth | $3.52 | $42.24 | $28.16 |
| Pro | $10.56 | $126.72 | $84.48 |
| Agency | $24.65 | $295.80 | $197.20 |

---

## 2. Cost Category Breakdown

Every dollar Kova spends falls into one of these buckets:

| Category | What's Inside | Variable/Fixed | Controls |
|----------|--------------|----------------|----------|
| **AI Models (LLM)** | OpenRouter API calls for 6 agents | Variable (per-token) | Model choice, prompt length, frequency |
| **AI Models (Image)** | HuggingFace / Gemini image gen | Variable (per-image) | Model tier, images per post |
| **Infrastructure** | Railway (web, worker, beat, DB, Redis) | Semi-fixed (usage-based) | Service sizing, scaling |
| **Third-party APIs** | Platform APIs (mostly free), email (Resend/SES) | Mostly free | Volume limits |
| **Payment processing** | M-Pesa (0% for STK Push) / Stripe (2.9% + $0.30) | Variable (per-txn) | Provider choice |
| **WhatsApp** | Meta conversation fees (future) | Variable (per-convo) | Message volume, template vs service |
| **Domain & SSL** | Custom domain, SSL cert | Fixed | Railway includes SSL |
| **Monitoring** | Sentry, uptime monitoring | Fixed (free tiers exist) | Plan selection |

---

## 3. AI Model Costs — Task-Level Analysis

### Token Usage Per Agent Task

Measured from actual Kova prompts (system prompt + user content + response):

| Agent | Task | Trigger | Input Tokens | Output Tokens | Frequency/User/Mo |
|-------|------|---------|-------------|---------------|-------------------|
| **Create** | Generate from seed | Per seed | ~2,500 | ~3,000 | 10-30 (per seed × platforms) |
| **Create** | Regenerate post | Manual | ~2,000 | ~1,500 | ~5 |
| **Analyst** | Extract Content DNA | Per post created | ~800 | ~500 | 15-60 |
| **Analyst** | Predict engagement | Per post created | ~600 | ~300 | 15-60 |
| **Analyst** | Performance analysis | Per brief | ~1,500 | ~1,000 | 30 (daily) |
| **Research** | Discover trends | Every 12h | ~1,000 | ~2,000 | 60 |
| **Research** | Generate angles | Per trend | ~1,500 | ~2,000 | 60 |
| **Adapt** | Suggest times | Per post | ~500 | ~300 | 15-60 |
| **Engage** | Analyze interactions | Every 30min | ~800 | ~500 | ~1,440 |
| **Engage** | Generate replies | Per interaction | ~1,500 | ~800 | 20-100 |
| **Strategist** | Strategy cycle | Every 8h | ~3,000 | ~2,500 | 90 |
| **Strategist** | Daily brief | Daily | ~2,500 | ~2,000 | 30 |
| **Competitor** | Full analysis | Weekly | ~3,000 | ~4,000 | 4 |

### Monthly Token Totals Per Plan (Estimated Active User)

| Plan | Premium Tokens (in/out) | Workhorse Tokens (in/out) | Fast Tokens (in/out) | Total Tokens |
|------|------------------------|--------------------------|---------------------|-------------|
| **Starter** (15 posts, 10 seeds, 2 agents) | 55K / 50K | 0 | 25K / 15K | ~145K |
| **Growth** (50 posts, 30 seeds, 4 agents) | 180K / 160K | 150K / 120K | 80K / 50K | ~740K |
| **Pro** (200 posts, 100 seeds, 6 agents) | 600K / 500K | 500K / 400K | 400K / 250K | ~2.65M |
| **Agency** (500 posts, 200 seeds, 6 agents) | 1.2M / 1M | 1M / 800K | 900K / 550K | ~5.45M |

### Cost Per Plan — Best Models (Recommended Stack)

**Premium tier:** Claude Sonnet 4.6 ($3/$15 per 1M tokens)
**Workhorse tier:** Gemini 3 Flash Preview ($0.50/$3 per 1M tokens)
**Fast tier:** DeepSeek V3.2 ($0.26/$0.38 per 1M tokens)

| Plan | Premium Cost | Workhorse Cost | Fast Cost | **Total LLM Cost** |
|------|-------------|---------------|-----------|-------------------|
| **Starter** | $0.17 + $0.75 = **$0.92** | $0.00 | $0.01 + $0.01 = **$0.02** | **$0.94** |
| **Growth** | $0.54 + $2.40 = **$2.94** | $0.08 + $0.36 = **$0.44** | $0.02 + $0.02 = **$0.04** | **$3.42** |
| **Pro** | $1.80 + $7.50 = **$9.30** | $0.25 + $1.20 = **$1.45** | $0.10 + $0.10 = **$0.20** | **$10.95** |
| **Agency** | $3.60 + $15.00 = **$18.60** | $0.50 + $2.40 = **$2.90** | $0.23 + $0.21 = **$0.44** | **$21.94** |

### 🚨 PROBLEM: Starter and Growth Are Underwater with Best Models

| Plan | Revenue | LLM Cost (Best) | Remaining for Everything Else |
|------|---------|-----------------|-------------------------------|
| **Starter** ($0.70) | $0.70 | $0.94 | **-$0.24 (LOSS)** |
| **Growth** ($3.52) | $3.52 | $3.42 | **$0.10 (3% margin)** |
| **Pro** ($10.56) | $10.56 | $10.95 | **-$0.39 (LOSS)** |
| **Agency** ($24.65) | $24.65 | $21.94 | **$2.71 (11% margin)** |

**Claude Sonnet 4.6 as the premium model burns through all revenue.** The $15/1M output tokens is the killer — content generation is output-heavy.

### Cost Per Plan — Budget-Smart Stack (Recommended for Launch)

**Premium tier:** Gemini 3 Flash Preview ($0.50/$3 per 1M tokens)
**Workhorse tier:** DeepSeek V3.2 ($0.26/$0.38 per 1M tokens)
**Fast tier:** DeepSeek V3.2 ($0.26/$0.38 per 1M tokens)

| Plan | Premium Cost | Workhorse Cost | Fast Cost | **Total LLM Cost** |
|------|-------------|---------------|-----------|-------------------|
| **Starter** | $0.03 + $0.15 = **$0.18** | $0.00 | $0.01 + $0.01 = **$0.02** | **$0.20** |
| **Growth** | $0.09 + $0.48 = **$0.57** | $0.04 + $0.05 = **$0.09** | $0.02 + $0.02 = **$0.04** | **$0.70** |
| **Pro** | $0.30 + $1.50 = **$1.80** | $0.13 + $0.15 = **$0.28** | $0.10 + $0.10 = **$0.20** | **$2.28** |
| **Agency** | $0.60 + $3.00 = **$3.60** | $0.26 + $0.30 = **$0.56** | $0.23 + $0.21 = **$0.44** | **$4.60** |

### Cost Per Plan — Hybrid Stack (Best Quality vs Cost Balance)

**Premium tier:** Gemini 3 Flash Preview for Starter/Growth, Claude Sonnet for Pro/Agency
**Workhorse tier:** DeepSeek V3.2 (all plans)
**Fast tier:** DeepSeek V3.2 (all plans)

| Plan | Premium Model | Total LLM Cost | Revenue | **Margin** |
|------|--------------|----------------|---------|-----------|
| **Starter** | Gemini 3 Flash | **$0.20** | $0.70 | **71%** ✅ |
| **Growth** | Gemini 3 Flash | **$0.70** | $3.52 | **80%** ✅ |
| **Pro** | Claude Sonnet 4.6 | **$10.43** | $10.56 | **1%** ❌ |
| **Agency** | Claude Sonnet 4.6 | **$21.38** | $24.65 | **13%** ❌ |

Still doesn't work for Pro/Agency with Claude. The problem is clear: **Claude Sonnet's output pricing ($15/1M) is too expensive for high-volume plans.**

### ✅ FINAL RECOMMENDED STACK — Launch Configuration

| Tier | Model | Cost (in/out per 1M) | Why |
|------|-------|---------------------|-----|
| **Premium** | `google/gemini-3-flash-preview` | $0.50 / $3.00 | #3 Marketing rank, excellent creative quality, 5x cheaper output than Claude |
| **Workhorse** | `deepseek/deepseek-v3.2` | $0.26 / $0.38 | GPT-5 class reasoning, absurdly cheap |
| **Fast** | `deepseek/deepseek-v3.2` | $0.26 / $0.38 | Same model simplifies config, near-free for classification |
| **Image (Free)** | HuggingFace FLUX.1-schnell | FREE | Starter plan |
| **Image (Paid)** | Gemini 2.5 Flash Image | ~$0.005/img | Growth+ plans |

**Why not Claude?** Claude Sonnet 4.6 is the best creative writer, but at $15/1M output tokens, it's 5x more expensive than Gemini Flash ($3/1M). Gemini 3 Flash is ranked #3 in Marketing on OpenRouter — it's 80% of Claude's quality at 20% of the cost. For a KES 99-3500 product, this is the right trade-off.

**When to upgrade to Claude:** When average revenue per user exceeds $15/month (i.e., most users are on Pro/Agency), introduce Claude as a premium content tier for Pro+ users only.

---

## 4. Image Generation Costs

### Per-Image Costs by Model

| Model | Cost/Image | Quality | Best For |
|-------|-----------|---------|---------|
| HuggingFace FLUX.1-schnell | **FREE** | Good (no text rendering) | Starter plan, dev |
| Gemini 2.5 Flash Image | **~$0.005** | Great (text rendering, editing) | Growth/Pro plans |
| Gemini 3 Pro Image | **~$0.04** | Excellent (4K, identity preservation) | Agency plan |
| GPT-5 Image Mini | **~$0.03** | Excellent (instruction following) | Alternative premium |

### Monthly Image Cost Per Plan

Assumption: 1 AI image per post (some posts won't need images)

| Plan | Posts/mo | Image Model | Cost/Image | **Total Image Cost** |
|------|----------|-------------|-----------|---------------------|
| **Starter** | 15 | FLUX.1-schnell | FREE | **$0.00** |
| **Growth** | 50 | Gemini 2.5 Flash | $0.005 | **$0.25** |
| **Pro** | 200 | Gemini 2.5 Flash | $0.005 | **$1.00** |
| **Agency** | 500 | Gemini 3 Pro | $0.04 | **$20.00** |

### 🚨 Agency Image Cost Alert

At $0.04/image × 500 posts = $20/month — that's 81% of Agency revenue just on images.

**Fix:** Use Gemini 2.5 Flash ($0.005) as default even for Agency. Offer Gemini 3 Pro as "Premium quality" toggle (10 premium images/month included).

**Revised Agency image cost:** 490 × $0.005 + 10 × $0.04 = $2.45 + $0.40 = **$2.85**

---

## 5. Infrastructure Costs (Railway)

### Current Railway Setup (Procfile)

Kova runs 3 services on Railway:
```
web:    gunicorn (Django app)
worker: celery -A config worker --concurrency=2
beat:   celery -A config beat
```

Plus Railway-managed services:
- **PostgreSQL** database
- **Redis** (Celery broker)

### Railway Pricing (April 2026)

| Resource | Cost |
|----------|------|
| RAM | $10 / GB / month |
| CPU | $20 / vCPU / month |
| Network Egress | $0.05 / GB |
| Volume Storage | $0.15 / GB / month |
| **Hobby plan** | $5/mo (includes $5 usage credit) |
| **Pro plan** | $20/mo (includes $20 usage credit) |

### Estimated Service Resource Usage

| Service | CPU (avg) | RAM (avg) | Monthly Cost |
|---------|-----------|-----------|-------------|
| **Web** (gunicorn, 2 workers) | 0.2 vCPU | 256 MB | $4.00 + $2.56 = **$6.56** |
| **Worker** (celery, concurrency=2) | 0.15 vCPU | 200 MB | $3.00 + $2.00 = **$5.00** |
| **Beat** (celery beat) | 0.05 vCPU | 64 MB | $1.00 + $0.64 = **$1.64** |
| **PostgreSQL** | 0.1 vCPU | 256 MB | $2.00 + $2.56 = **$4.56** |
| **Redis** | 0.05 vCPU | 64 MB | $1.00 + $0.64 = **$1.64** |
| **Volume storage** (1 GB) | — | — | **$0.15** |
| **Network egress** (~5 GB) | — | — | **$0.25** |
| | | **TOTAL** | **$19.80** |

### Railway Plan Selection

- **Hobby ($5/mo):** Includes $5 usage. Our ~$20 usage means we'd pay **~$20/mo total**
- **Pro ($20/mo):** Includes $20 usage. Our ~$20 usage means we'd pay **~$20/mo total**

**Recommendation:** Start on **Hobby ($5/mo)** — the $5 credit covers about 25% of usage. Total bill ~$20/mo. When we need team features or scale > 48 vCPU, upgrade to Pro.

### Infrastructure Cost Per User (at different scales)

| Users | Railway Cost | Cost/User/Mo |
|-------|-------------|-------------|
| 10 | ~$20 | **$2.00** |
| 50 | ~$25 | **$0.50** |
| 100 | ~$30 | **$0.30** |
| 500 | ~$50 | **$0.10** |
| 1,000 | ~$80 | **$0.08** |
| 5,000 | ~$200 | **$0.04** |
| 10,000 | ~$400 | **$0.04** |

Infrastructure scales sub-linearly. At 100+ users it becomes negligible per user.

---

## 6. Third-Party Service Costs

| Service | What It's For | Free Tier | Paid Cost | Kova Usage |
|---------|--------------|-----------|-----------|-----------|
| **OpenRouter** | LLM API gateway | Pay-per-use (no minimum) | Per-token (see Section 3) | All AI agents |
| **HuggingFace** | Image generation | Free Inference API | — | Starter images |
| **Safaricom Daraja** | M-Pesa STK Push | Free API access | **0% transaction fee** (Paybill) | Payment processing |
| **Stripe** | Card payments (future) | — | 2.9% + $0.30/txn | International payments |
| **Resend / AWS SES** | Transactional email | 100 emails/day free (Resend) | $0.001/email (SES) | Email verification, briefs |
| **Platform APIs** | Social media posting | Free (rate-limited) | — | Content publishing |
| **Sentry** | Error monitoring | 5K events/mo free | $26/mo (Team) | Error tracking |
| **GitHub** | Code hosting | Free (public/private) | — | Source control |
| **Railway DNS** | Custom domain | Free (included) | — | SSL + domain |

### Monthly Third-Party Costs (Non-AI)

| Service | Cost at 100 users | Cost at 1,000 users |
|---------|------------------|---------------------|
| M-Pesa Daraja | **$0** (free STK Push) | **$0** |
| Email (Resend free tier) | **$0** (< 3,000 emails/mo) | **$20** (upgrade needed) |
| Sentry (free tier) | **$0** (< 5K events/mo) | **$0** (probably still under) |
| Platform APIs | **$0** (all have free tiers) | **$0** |
| Domain | **$0** (Railway included) | **$0** |
| **Total** | **$0** | **~$20** |

### M-Pesa Cost Advantage

This is critical for Kenya. M-Pesa STK Push via Paybill has **zero transaction fees** for the merchant. Compare:

| Provider | Transaction Fee | On KES 500 payment | On KES 3,500 payment |
|----------|----------------|--------------------|--------------------|
| **M-Pesa (Paybill)** | **0%** | **KES 0** | **KES 0** |
| Stripe | 2.9% + $0.30 | ~KES 56 (11%) | ~KES 144 (4%) |
| PayPal | 3.49% + KES 50 | ~KES 68 (14%) | ~KES 172 (5%) |
| Flutterwave | 3.5% | ~KES 18 (4%) | ~KES 123 (4%) |

**M-Pesa = 100% of payment collected.** This is a significant margin advantage in Kenya.

---

## 7. WhatsApp Conversation Costs (Future — Phase 5)

### Meta's Per-Conversation Pricing (Kenya)

| Type | Who Initiates | Cost USD | Notes |
|------|--------------|----------|-------|
| **Service** | Customer → Business | **FREE** (first 1,000/mo) | Customer-initiated |
| **Marketing** | Business → Customer (template) | ~$0.049 | Outbound campaigns |
| **Utility** | Business → Customer (template) | ~$0.020 | Order updates, confirmations |
| **Authentication** | Business → Customer (template) | ~$0.015 | OTPs, verification |

### Estimated WhatsApp Costs Per Plan

| Plan | Service Convos | Marketing Convos | Utility Convos | **Total WhatsApp Cost** |
|------|---------------|-----------------|---------------|------------------------|
| Starter | N/A (no WhatsApp) | — | — | **$0** |
| Growth | ~50 (free) | ~20 | ~10 | ~$0.98 + $0.20 = **$1.18** |
| Pro | ~200 (free) | ~100 | ~50 | ~$4.90 + $1.00 = **$5.90** |
| Agency | ~500 (free) | ~300 | ~100 | ~$14.70 + $2.00 = **$16.70** |

**🚨 WhatsApp marketing messages are expensive.** At $0.049 per conversation, 300 outbound campaigns = $14.70. This needs careful plan allocation or pass-through pricing.

### WhatsApp Cost Mitigation

1. **Service conversations are free** — Kova's Engage Agent auto-reply runs at zero WhatsApp cost
2. **Cap marketing templates per plan** — Growth: 20/mo, Pro: 100/mo, Agency: 300/mo
3. **Pass-through option** — Charge KES 3 per WhatsApp marketing message (covers $0.049 × 142 KES = KES 6.96, charge half)
4. **Prioritize service conversations** — AI auto-replies use the free 1,000 service convos

---

## 8. Full Unit Economics Model

### Per-User Monthly Cost — Launch Configuration (Budget-Smart Stack)

| Cost Item | Starter | Growth | Pro | Agency |
|-----------|---------|--------|-----|--------|
| **LLM (Gemini Flash + DeepSeek)** | $0.20 | $0.70 | $2.28 | $4.60 |
| **Image generation** | $0.00 | $0.25 | $1.00 | $2.85 |
| **Infrastructure (at 100 users)** | $0.30 | $0.30 | $0.30 | $0.30 |
| **Email** | $0.00 | $0.00 | $0.00 | $0.00 |
| **M-Pesa fees** | $0.00 | $0.00 | $0.00 | $0.00 |
| **WhatsApp (future)** | $0.00 | $1.18 | $5.90 | $16.70 |
| | | | | |
| **Total Cost (no WhatsApp)** | **$0.50** | **$1.25** | **$3.58** | **$7.75** |
| **Revenue** | **$0.70** | **$3.52** | **$10.56** | **$24.65** |
| **Gross Margin** | **29%** | **64%** | **66%** | **69%** |
| **Gross Profit/User** | **$0.20** | **$2.27** | **$6.98** | **$16.90** |
| | | | | |
| **Total Cost (with WhatsApp)** | **$0.50** | **$2.43** | **$9.48** | **$24.45** |
| **Gross Margin (with WA)** | **29%** | **31%** | **10%** | **1%** |

### 🚨 KEY INSIGHT: WhatsApp Marketing Messages Destroy Margins

Without WhatsApp: 29-69% margins. Healthy.
With WhatsApp marketing: Pro drops to 10%, Agency to 1%. **Unsustainable.**

**Solution options:**
1. **WhatsApp as premium add-on** — Separate pricing for WhatsApp marketing campaigns
2. **Include limited allocation** — 20 marketing messages for Growth, 50 for Pro, 100 for Agency
3. **Pass-through pricing** — Charge per WhatsApp marketing message (KES 3-5 each)
4. **Focus on service conversations** — Free 1,000/mo covers customer support AI auto-replies

---

## 9. Scenario Modeling — 10 to 10,000 Users

### Assumption: Plan Distribution
Based on typical SaaS distribution in emerging markets:
- Starter: 45% of users
- Growth: 30% of users
- Pro: 15% of users
- Agency: 10% of users

### Revenue & Cost at Scale (No WhatsApp, Budget-Smart Stack)

| Users | Starter (45%) | Growth (30%) | Pro (15%) | Agency (10%) | **Monthly Revenue** | **Monthly Cost** | **Gross Profit** | **Margin** |
|-------|--------------|-------------|----------|-------------|--------------------|-----------------|-----------------| -------|
| **10** | 5 | 3 | 1 | 1 | $39 | $28 | $11 | 28% |
| **50** | 23 | 15 | 7 | 5 | $194 | $98 | $96 | 49% |
| **100** | 45 | 30 | 15 | 10 | $387 | $175 | $212 | 55% |
| **500** | 225 | 150 | 75 | 50 | $1,936 | $802 | $1,134 | 59% |
| **1,000** | 450 | 300 | 150 | 100 | $3,873 | $1,555 | $2,318 | 60% |
| **5,000** | 2,250 | 1,500 | 750 | 500 | $19,363 | $7,475 | $11,888 | 61% |
| **10,000** | 4,500 | 3,000 | 1,500 | 1,000 | $38,725 | $14,650 | $24,075 | 62% |

### Monthly Costs Breakdown at Scale

| Users | LLM Cost | Image Cost | Railway | Email | Other | **Total** |
|-------|----------|-----------|---------|-------|-------|-----------|
| 10 | $8 | $3 | $20 | $0 | $0 | $28* |
| 50 | $39 | $16 | $23 | $0 | $0 | $78 |
| 100 | $79 | $32 | $30 | $0 | $0 | $141 |
| 500 | $394 | $158 | $50 | $0 | $0 | $602 |
| 1,000 | $788 | $317 | $80 | $20 | $0 | $1,205 |
| 5,000 | $3,938 | $1,583 | $200 | $50 | $26 | $5,797 |
| 10,000 | $7,875 | $3,167 | $400 | $100 | $26 | $11,568 |

*At 10 users, Railway's $20 base cost dominates. This is the cold-start problem — infrastructure is a fixed cost that needs to be amortized.*

### Break-Even: When Does Kova Stop Losing Money?

Including **your time** (founder salary equivalent) and **fixed costs**:

| Fixed Cost | Monthly Amount | Notes |
|------------|---------------|-------|
| Railway hosting | ~$20 | Base infrastructure |
| Domain/DNS | ~$1 | Included in Railway |
| OpenRouter minimum | $0 | Pay-per-use, no minimum |
| Email (Resend free) | $0 | Up to 100/day |
| **Total fixed** | **~$21** |

---

## 10. Break-Even Analysis

### Break-Even with Fixed Costs Only (No Salary)

At the assumed plan distribution (45/30/15/10):

**Average revenue per user:** $3.87/mo
**Average variable cost per user:** $1.55/mo
**Average contribution margin per user:** $2.32/mo

```
Break-even users = Fixed costs / Contribution margin per user
Break-even users = $21 / $2.32 = ~10 users
```

**Kova breaks even on operational costs at just 10 paying users.**

### Break-Even Including Founder Salary

If you want to pay yourself a modest salary:

| Salary Target (KES/mo) | USD/mo | Users Needed |
|------------------------|--------|-------------|
| KES 30,000 (~entry dev salary) | $211 | ~100 users |
| KES 60,000 (~mid dev salary) | $423 | ~191 users |
| KES 100,000 (~senior salary) | $704 | ~312 users |
| KES 200,000 (~management) | $1,408 | ~616 users |

### Break-Even Timeline Projection

| Month | New Users/Mo | Total Users | MRR | Costs | Net |
|-------|-------------|-------------|-----|-------|-----|
| 1 | 10 | 10 | $39 | $28 | +$11 |
| 2 | 15 | 22 | $85 | $55 | +$30 |
| 3 | 20 | 37 | $143 | $78 | +$65 |
| 4 | 25 | 55 | $213 | $107 | +$106 |
| 5 | 30 | 75 | $290 | $137 | **+$153** (~KES 30K salary) |
| 6 | 35 | 97 | $376 | $172 | **+$204** |
| 8 | 45 | 145 | $561 | $246 | **+$315** |
| 10 | 55 | 200 | $774 | $330 | **+$444** (~KES 60K salary) |
| 12 | 65 | 260 | $1,006 | $424 | **+$582** (~KES 80K salary) |

**Assumptions:** 10% monthly churn, linear user acquisition growth. Conservative.

---

## 11. Cost Control Strategies

### Strategy 1: Model Routing by Plan Tier

| Plan | Premium Model | Image Model | Why |
|------|--------------|-------------|-----|
| **Starter** | Gemini 3 Flash | FLUX.1-schnell (FREE) | Minimize cost, still good quality |
| **Growth** | Gemini 3 Flash | Gemini 2.5 Flash ($0.005) | Better images, same LLM |
| **Pro** | Gemini 3 Flash | Gemini 2.5 Flash ($0.005) | Same quality, scale-efficient |
| **Agency** | Claude Sonnet 4.6 | Gemini 2.5 Flash ($0.005) | Premium content for premium price |

**Only Agency gets Claude.** At $24.65 revenue, we can absorb the ~$19 Claude cost and still make $5+ margin. For all other plans, Gemini Flash delivers 80% of the quality at 20% of the cost.

### Strategy 2: Prompt Engineering to Reduce Tokens

Every 20% reduction in prompt length = 20% reduction in LLM cost.

- **Compress system prompts:** Remove redundant instructions, use shorthand
- **Cache common analysis:** Don't re-analyze the same post twice
- **Batch operations:** Analyze 5 interactions in one LLM call vs 5 separate calls
- **Smart triggers:** Don't run Engage Agent if no new interactions (check before calling LLM)

### Strategy 3: Caching & Deduplication

- **Cache Content DNA:** Once extracted, store in JSONField (already done)
- **Cache trend research:** Trends valid for 12h, don't re-research
- **Cache competitor analysis:** Valid for 7 days
- **Deduplicate engagement:** Don't analyze the same comment twice

### Strategy 4: Rate Limiting by Plan

Already implemented in `PLAN_LIMITS`:
- **Starter:** 15 posts, 10 seeds → natural cap on LLM usage
- **Growth:** 50 posts, 30 seeds → moderate cap
- **Pro/Agency:** Unlimited posts → need soft caps (e.g., 500 posts triggers warning)

### Strategy 5: Gradual Model Upgrade Path

```
Launch:      Gemini Flash (all plans) → $0.20-4.60/user
Month 3:     Claude for Agency only → Agency cost +$15, revenue covers it
Month 6:     Claude for Pro + Agency → Requires Pro price increase to KES 2,000
Month 12:    Claude for all plans → Requires Growth price increase to KES 800
```

---

## 12. Risk Scenarios — What Could Go Wrong

### Scenario A: "Power User" on Starter Plan

A user on KES 99 plan maxes out at 15 posts/month with complex prompts.

| Metric | Value |
|--------|-------|
| Revenue | $0.70 |
| LLM cost (max) | $0.30 |
| Image cost | $0.00 |
| Infra (shared) | $0.30 |
| **Net** | **+$0.10** |

**Verdict:** Still profitable. Plan limits (15 posts, 10 seeds) naturally cap costs.

### Scenario B: AI Model Price Increase

OpenRouter models increase by 2x.

| Stack | Current Cost | 2x Cost | Impact |
|-------|-------------|---------|--------|
| Budget-Smart | $0.20-4.60/user | $0.40-9.20/user | Growth still profitable, Agency tight |
| Best Models | $0.94-21.94/user | $1.88-43.88/user | All plans underwater |

**Mitigation:** Multiple model options. If Gemini doubles, switch to DeepSeek ($0.26/$0.38 is already nearly free). If all models double, raise prices by KES 200-500 across plans.

### Scenario C: Railway Price Increase

Railway doubles pricing.

| Users | Current | 2x | Impact |
|-------|---------|-----|--------|
| 100 | $30/mo | $60/mo | +$0.30/user. Manageable. |
| 1,000 | $80/mo | $160/mo | +$0.08/user. Negligible. |

**Mitigation:** Railway is already cheap. Could migrate to Hetzner/DigitalOcean VPS ($5-20/mo) if needed.

### Scenario D: 80% of Users on Starter Plan

If plan distribution shifts to 80/10/5/5 (most on cheapest plan):

| Metric | Current (45/30/15/10) | Worst case (80/10/5/5) |
|--------|----------------------|------------------------|
| Avg revenue/user | $3.87 | $1.96 |
| Avg cost/user | $1.55 | $0.63 |
| Avg margin/user | $2.32 | $1.33 |
| Break-even (no salary) | 10 users | 16 users |
| 200 users net profit | $444/mo | $246/mo |

**Verdict:** Still profitable, just slower to scale. Push upsells via feature differentiation (Engage Agent, Strategist only on Growth+).

### Scenario E: WhatsApp Marketing at Scale

500 Agency users each sending 300 marketing messages:

| Metric | Value |
|--------|-------|
| Monthly marketing conversations | 150,000 |
| Cost at $0.049/convo | **$7,350/mo** |
| Revenue from 500 Agency users | $12,325/mo |
| Remaining margin | $4,975/mo |

**Verdict:** WhatsApp marketing must be a separate line item or add-on. Never include unlimited marketing messages in base plan.

---

## 13. Decision Matrix — Which Models to Use

### Launch Day Configuration (Day 1)

```env
# PRODUCTION — Launch Configuration
LLM_MODEL_PREMIUM=google/gemini-3-flash-preview
LLM_MODEL_WORKHORSE=deepseek/deepseek-v3.2
LLM_MODEL_FAST=deepseek/deepseek-v3.2

# Image: FLUX.1-schnell for all (free)
AI_IMAGE_GENERATION_ENABLED=True
HF_TOKEN=hf_xxxxxxxxxxxxx
```

**Total AI cost:** $0.20-4.60/user/month
**Margins:** 29-69% (healthy at all tiers)

### Growth Configuration (100+ Users, 3 Months In)

```env
# PRODUCTION — Growth Configuration
# Agency users get Claude
LLM_MODEL_PREMIUM=google/gemini-3-flash-preview
LLM_MODEL_PREMIUM_AGENCY=anthropic/claude-sonnet-4.6

# Paid images for Growth+
AI_IMAGE_MODEL_GROWTH=google/gemini-2.5-flash-image
AI_IMAGE_MODEL_AGENCY=google/gemini-2.5-flash-image
```

**Requires:** Plan-based model routing in `llm.py` (check user plan → select model)

### Scale Configuration (1,000+ Users, 6 Months In)

```env
# PRODUCTION — Scale Configuration
# Pro + Agency get Claude for content
LLM_MODEL_PREMIUM_DEFAULT=google/gemini-3-flash-preview
LLM_MODEL_PREMIUM_PRO=anthropic/claude-sonnet-4.6
LLM_MODEL_PREMIUM_AGENCY=anthropic/claude-sonnet-4.6

# Consider price increase:
# Pro: KES 1,500 → KES 2,000 ($14.08)
# Agency: KES 3,500 → KES 4,500 ($31.69)
```

---

## Summary — The 5 Numbers That Matter

| Metric | Value |
|--------|-------|
| **Average cost to serve 1 user/month** | **$1.55** (Budget-Smart stack, no WhatsApp) |
| **Average revenue per user/month** | **$3.87** (blended across plans) |
| **Gross margin** | **60%** (at 100+ users) |
| **Break-even** | **10 users** (operational costs only) |
| **Break-even with KES 60K salary** | **~200 users** |

### The Bottom Line

Kova's pricing works. Even at KES 99 ($0.70), the Starter plan is profitable because:
1. **Gemini 3 Flash is ridiculously good for the price** — #3 Marketing rank at $3/1M output tokens
2. **DeepSeek V3.2 is nearly free** — $0.38/1M output tokens for GPT-5 class reasoning
3. **M-Pesa has zero transaction fees** — 100% of every KES goes to Kova
4. **Railway is usage-based** — no $50/mo minimums, grows with you
5. **Plan limits naturally cap costs** — 15 posts on Starter means max ~$0.30 in LLM costs

**The only threat to margins is WhatsApp marketing messages** ($0.049/conversation). Solution: separate pricing or capped allocation per plan. Never include unlimited outbound marketing in base plan.

---

*This analysis should be refreshed monthly for the first 6 months as real usage data replaces estimates.*
