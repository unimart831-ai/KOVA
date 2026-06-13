# Kova Cost Ledger — Every Penny, One Place

**Last updated:** June 2026  
**Dashboard:** Admin → **Cost Economics** (`/dashboard/costs/`)  
**Code source of truth:** `apps/billing/cost_registry.py`  
**Deep dive:** `KOVA_FINANCIAL_AUDIT.md`, `COST_ANALYSIS.md`

---

## Quick totals (30-day window)

The admin **Spend Ledger** tab aggregates:

| Bucket | Formula | Tracking |
|--------|---------|----------|
| **LLM tokens** | Σ tokens × model $/1M | `AgentAction`, `UserTokenBucket` |
| **Snap vision** | snap.* action types | `AgentAction` |
| **FLUX images** | posts × plan tier ($0.025 / $0.04) | `Post.media_status=generated` |
| **Photoroom Plus** | credits × ($500 / 5000 pool) | `commerce.studio_polish` |
| **Photoroom Basic** | calls × ~20% of Plus unit | provider=`photoroom_basic` |
| **Whisper** | minutes × $0.006 | `VoiceBrief.duration_seconds` |
| **WhatsApp** | convos × $0.049 marketing / $0.020 utility | `WhatsAppMessage` templates |
| **Email** | sends × $0.0004 (est. above free tier) | `EmailLog` |

**Variable COGS** = sum of metered lines above (excludes fixed Railway/R2).

---

## Section-by-section cost map

### 1. Social agents (LLM)

| Product | Tasks | Typical trigger | Cost driver |
|---------|-------|-----------------|-------------|
| **Create** | Generate post, regenerate | Per seed × platform | Premium tier tokens |
| **Analyst** | DNA, engagement prediction, performance | Per post / daily brief | Fast tier tokens |
| **Research** | Trends, angles | Every 12h cron | Workhorse tokens |
| **Engage** | Analyze inbox, draft replies | Every 30min + per reply | Fast + premium |
| **Strategist** | Strategy cycle, daily brief | Every 8h + daily | Workhorse + premium |
| **Adapt** | Schedule suggestions | Per post | Fast tokens |

**Math:** `(input_tokens/1e6 × $in) + (output_tokens/1e6 × $out)`  
**Registry:** `settings.MODEL_TOKEN_COSTS`, `apps/agents/pricing.py`  
**Caps:** `daily_llm_tokens` per plan in `PLAN_LIMITS`

**Production default:** DeepSeek V3.2 ~$0.26 / $0.38 per 1M in/out → **~$0.04–$0.88/user/mo** at medium use.

---

### 2. Snap to Sell

| Step | Service | Unit cost | Notes |
|------|---------|-----------|-------|
| Vision analysis | GPT-4o mini | ~$0.0003/call | Not budget-gated when `user=None` |
| Product copy | LLM | ~$0.001/call | `commerce.*` actions |
| Studio polish | Photoroom Plus | ~$0.10/credit | 1 API call = 1 credit |
| Basic cutout | Photoroom Basic | ~$0.02/call | 5 Basic ≈ 1 Plus credit |
| Reel compose | FFmpeg | $0 | Worker CPU only |

**Per Snap (heavy):** 1 vision + 3–8 Photoroom credits + LLM ≈ **$0.30–$1.00** at full Plus pack.

---

### 3. AI image generation (posts)

| Plan | Model | Limit/mo | $/image |
|------|-------|----------|---------|
| Starter | — | 0 | — |
| Growth | FLUX.1-krea-dev | 50 | $0.025 |
| Pro | FLUX.1.1-pro | 100 | $0.04 |
| Agency | FLUX.1.1-pro | 500 | $0.04 |

Fallback: HuggingFace / Pollinations = **$0**.

---

### 4. Voice Campaign

| Step | Service | Unit cost |
|------|---------|-----------|
| Transcription | Whisper | $0.006/min |
| Intent + campaign LLM | OpenRouter | Included in agent LLM |

**Typical memo:** 20s → **~$0.002** Whisper + **~$0.01** LLM.

---

### 5. WhatsApp

| Type | Est. cost (Kenya) | Metered in app |
|------|-------------------|----------------|
| Marketing template | ~$0.049/conversation | Yes (distinct convos/mo) |
| Utility template | ~$0.020/conversation | Yes |
| Service (user-initiated) | Free tier 1K/mo | No |

**Risk:** Heavy Pro broadcast users can exceed subscription revenue — see `KOVA_FINANCIAL_AUDIT.md`.

---

### 6. Email (Resend)

| Tier | Cost |
|------|------|
| Free | 100 emails/day |
| Paid estimate | ~$0.0004/email in ledger |

Sources: auth, billing, daily brief, email campaigns, autopilot review emails.

---

### 7. Research (Tavily)

| Tier | Cost |
|------|------|
| Free | 1,000 searches/mo |
| Over limit | ~$8/1K searches |

**Not logged in DB** — monitor Tavily dashboard manually.

---

### 8. Infrastructure (fixed / semi-fixed)

| Service | Est. monthly |
|---------|--------------|
| Railway (web, worker, beat, Postgres, Redis) | $20–80 by scale |
| Cloudflare R2 | ~$0.015/GB after 10 GB free |
| Sentry | $0 (free tier) or ~$26 Team |

Allocated per user in **Unit Economics** tab as shared infra.

---

### 9. Payments (fees, not COGS)

| Provider | Fee |
|----------|-----|
| M-Pesa STK (subscription) | **0%** merchant |
| Stripe (international) | 2.9% + $0.30 |

---

## Per-plan variable COGS ceiling (configured limits)

From `PLAN_LIMITS` + cost registry (worst case if user maxes every cap):

| Plan | Price USD | LLM (med est.) | Images max | Photoroom max | Notes |
|------|-----------|----------------|------------|---------------|-------|
| Starter | $4 | ~$0.04 | $0 | 30 × $0.10 = $3 | Polish can dominate |
| Growth | $7 | ~$0.10 | 50 × $0.025 = $1.25 | 100 × $0.10 = $10 | Pool throttle at 80% |
| Pro | $14 | ~$0.25 | $4 | 200 × $0.10 = $20 | WhatsApp adds variable |
| Agency | $21 | ~$0.88 | $20 | 500 × $0.10 = $50 | Unlimited posts = token risk |

Use **Scenario Calculator** (Unit Economics tab) for what-if modeling.

---

## Settings you can tune

| Env var | Default | Purpose |
|---------|---------|---------|
| `PHOTOROOM_MONTHLY_COST_USD` | 500 | Pool cost attribution |
| `PHOTOROOM_MONTHLY_POOL` | 5000 | Credits in subscription |
| `WHISPER_COST_PER_MINUTE` | 0.006 | Voice STT ledger |
| `WHATSAPP_MARKETING_COST_USD` | 0.049 | WA marketing ledger |
| `WHATSAPP_UTILITY_COST_USD` | 0.020 | WA utility ledger |
| `RESEND_COST_PER_EMAIL_USD` | 0.0004 | Email ledger |
| `TAVILY_COST_PER_SEARCH_USD` | 0.008 | Planning only |
| `PHOTOROOM_BASIC_COST_RATIO` | 0.2 | Basic vs Plus unit cost |

---

## Maintenance

When adding a new paid API:

1. Add a `CostLineItem` to `get_cost_catalog()` in `cost_registry.py`
2. Implement usage in `aggregate_platform_spend()` if metered
3. Add enforcement cap in `PLAN_LIMITS` or feature module if user-facing
4. Update this doc and the Spend Ledger tab will pick it up automatically

---

*Numbers are estimates unless marked “actual” in the dashboard. Exchange rate for KES display: ~142 KES/USD.*
