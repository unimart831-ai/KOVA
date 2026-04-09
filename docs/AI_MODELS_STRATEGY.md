# KOVA AI MODELS STRATEGY — Founders Decision Document

> **Last Updated**: April 2026
> **Status**: ACTIVE — Strategic decisions for Kova's AI brain
> **Decision Makers**: Founders

---

## EXECUTIVE SUMMARY

Kova has 6 AI agents performing 13 distinct LLM tasks. This document is the founder-level decision on which AI models power each task, why, and the financial impact on our business.

**The bottom line**: We can deliver production-quality AI to ALL plan tiers while keeping AI costs at **$0.05 - $2.25 per user per month** — maintaining **>90% margins on AI spend** at every plan level.

---

## 1. THE CURRENT STATE (What We Have)

### Model Configuration Today
| Tier | Model | Cost | Role |
|------|-------|------|------|
| **Premium** | `qwen/qwen3.6-plus:free` | $0/1M tokens | Creative content, user-facing |
| **Workhorse** | `qwen/qwen3.6-plus:free` | $0/1M tokens | Reasoning, strategy |
| **Fast** | `stepfun/step-3.5-flash:free` | $0/1M tokens | Classification, extraction |
| **Paid Fallback** | `gpt-4o-mini` | $0.15/$0.60 per 1M | Last resort (5-10% of calls) |

### Fallback Chain (when primary model returns empty)
```
qwen/qwen3.6-plus:free → nvidia/nemotron → minimax/minimax-m2.5:free → stepfun/step-3.5-flash:free → gpt-4o-mini (paid)
```

### Problems With Current Setup
1. **Single provider dependency** — Qwen (Alibaba) provides 2 of our 4 fallback models
2. **Data privacy risk** — Qwen free tier explicitly collects all prompt/completion data for model training
3. **Reliability** — Free models return empty responses ~5-10% of the time, triggering fallback chain
4. **Step 3.5 Flash underperforming** — Demoted to last in fallback chain due to frequent empty responses in free tier
5. **gpt-4o-mini expensive as fallback** — At $0.60/1M output, it's the most expensive option when it fires

---

## 2. THE MODEL LANDSCAPE (What's Available)

### Comprehensive Model Comparison (April 2026)

| Model | Input $/1M | Output $/1M | Context | Throughput | Uptime | Struct. Error | Intelligence | Hallucination |
|-------|-----------|-------------|---------|------------|--------|--------------|-------------|---------------|
| **Qwen 3.6 Plus (free)** | $0 | $0 | 1M | 45 tok/s | 99.9% | 0.95% | #1 ranked | N/A |
| **DeepSeek V3.2** | $0.26 | $0.38 | 164K | 76 tok/s | Multi | 0.78% | 41.7 (89th) | 18.3% |
| **Gemini 3 Flash** | $0.50 | $3.00 | 1M | 76 tok/s | 99.4% | 1.22% | 46.4 (94th) | **7.8%** |
| **Gemini 3.1 Flash Lite** | $0.25 | $1.50 | 1M | 83 tok/s | 99.7% | **0.68%** | 33.5 (76th) | 18.4% |
| **Step 3.5 Flash** | $0.10 | $0.30 | 262K | **117 tok/s** | 99.9% | 2.78% | 37.8 (82nd) | 14.8% |
| **MiniMax M2.7** | $0.30 | $1.20 | 205K | 46 tok/s | **89.3%** | N/A | 49.6 (97th) | **65.6%** |
| **gpt-4o-mini** | $0.15 | $0.60 | 128K | varies | 99.9% | low | good | low |

### Key Discoveries

**DeepSeek V3.2 is the clear winner for Kova's workload:**
- 89th percentile intelligence — strong enough for content creation
- **$0.26/$0.38 per 1M tokens** — cheapest quality model available
- 0.78% structured output error rate — excellent for our JSON-heavy agents
- Multi-provider on OpenRouter (13 providers) — high redundancy
- Open weights — no vendor lock-in, no data collection
- "GPT-5 class" reasoning claimed, strong agentic tool-use

**Gemini 3 Flash is the quality king but output-expensive:**
- 94th percentile intelligence, lowest hallucination rate (7.8%)
- But **$3.00/1M output tokens** — 8x more expensive than DeepSeek output
- For content generation (4K-8K output tokens per call), this adds up fast
- Best reserved for high-value customers who generate more revenue

**MiniMax M2.7 — DISQUALIFIED despite #5 ranking:**
- 65.6% hallucination rate is unacceptable for any Kova agent
- 89.3% uptime is lowest among viable candidates
- Only 2 providers — no redundancy

**Step 3.5 Flash paid — Speed champion for bulk tasks:**
- 117 tok/s throughput — fastest available
- $0.10/$0.30 per 1M — cheapest paid model
- Best for high-volume, low-creativity tasks (classification, prediction)
- Higher structured output errors (2.78%) limits it to simple JSON responses

---

## 3. THE AGENT-TASK MATRIX (What Each Agent Needs)

### Task Requirements Analysis

| Agent | Task | Creativity | Reasoning | Speed | JSON | Output Size | Frequency |
|-------|------|-----------|-----------|-------|------|-------------|-----------|
| **Create** | generate | ★★★★★ | ★★★ | ★★ | ✅ | 8K tokens | Per request |
| **Create** | regenerate | ★★★★★ | ★★ | ★★★ | ✅ | 2K tokens | Per request |
| **Create** | repurpose | ★★★★ | ★★★ | ★★ | ✅ | 8K tokens | Per request |
| **Create** | A/B variant | ★★★★★ | ★★ | ★★ | ✅ | 8K tokens | Per generate |
| **Engage** | analyze | ★ | ★★ | ★★★★ | ✅ | 1.5K tokens | Hourly batch |
| **Engage** | reply | ★★★★ | ★★★ | ★★★ | ⚠️ | 250/reply | Per batch |
| **Analyst** | performance | ★ | ★★★ | ★★★★ | ✅ | 4K tokens | Per request |
| **Analyst** | content_dna | ★ | ★★ | ★★★★★ | ✅ | 500 tokens | Batch |
| **Analyst** | predict | ★ | ★★★ | ★★★★★ | ✅ | 200 tokens | Batch |
| **Research** | trends | ★★★ | ★★★★ | ★★ | ✅ | 2K tokens | Daily |
| **Research** | angles | ★★★ | ★★★ | ★★★ | ✅ | 1.5K tokens | Daily |
| **Adapt** | schedule | ★ | ★★★ | ★★★★ | ✅ | 1.2K tokens | Daily |
| **Strategist** | decide | ★★ | ★★★★★ | ★★ | ✅ | 2.5K tokens | Weekly |

### Critical Insight: TWO Distinct Workload Types

**User-Blocking (needs quality + speed):** `create.generate`, `create.regenerate`, `create.repurpose`, `engage.reply`
- User is WAITING for this response
- Quality directly affects whether user stays or leaves
- These are the tasks where model quality earns revenue

**Background (needs cost efficiency):** All analyst tasks, `adapt.schedule`, `research.*`, `strategist.decide`, `engage.analyze`
- User never sees raw output
- Runs in Celery tasks, user isn't waiting
- Lower quality is acceptable — data is synthesized with other signals
- High volume = big cost multiplier

---

## 4. THE STRATEGIC RECOMMENDATION

### Phase 1: Immediate Action (This Week)
> **Goal**: Reduce fallback costs 50%, improve fallback quality

**Change paid fallback from gpt-4o-mini to DeepSeek V3.2:**

| | gpt-4o-mini (current) | DeepSeek V3.2 (recommended) |
|---|---|---|
| Input cost | $0.15/1M | $0.26/1M |
| Output cost | $0.60/1M | $0.38/1M |
| Intelligence | Good | 89th percentile |
| Reasoning | Limited | "GPT-5 class" |
| JSON compliance | Good | 0.78% error rate |
| Providers | 1 (OpenAI) | 13 (OpenRouter) |

**Why**: DeepSeek output tokens are 37% cheaper ($0.38 vs $0.60). Since Kova's tasks are output-heavy (content generation), this saves real money on the 5-10% of calls hitting the paid fallback. And the quality is significantly better.

**Implementation**: Change `LLM_PAID_FALLBACK` env var to `deepseek/deepseek-v3.2` and set `LLM_PAID_FALLBACK_PROVIDER` to `openrouter`.

### Phase 2: Launch & Early Growth (Months 1-3)
> **Goal**: Maximum reliability at near-zero cost for first 50 users

**Keep free models as primary. Add model diversity to fallback chain.**

```
PRIMARY:      qwen/qwen3.6-plus:free
FALLBACK 1:   nvidia/nemotron:free
FALLBACK 2:   minimax/minimax-m2.5:free
FALLBACK 3:   stepfun/step-3.5-flash:free
FALLBACK 4:   deepseek/deepseek-v3.2 (paid — $0.26/$0.38)
```

**Cost per user (worst case all-paid):**
| Plan | Starter | Growth | Pro | Agency |
|------|---------|--------|-----|--------|
| Monthly AI cost | $0.05 | $0.23 | $0.90 | $2.25 |
| Revenue | $2.00 | $7.00 | $14.00 | $21.00 |
| **AI Margin** | **92.9%** | **93.5%** | **91.5%** | **90.9%** |

**Reality**: 90%+ of calls use free models. Actual AI cost is ~$0.005-$0.23/user.

**Why this works**: First 50 users need to validate product-market fit. Paying for models before we've proven users will pay is premature spend. Free models are #1 ranked on OpenRouter — they're genuinely good.

### Phase 3: Paid Model Upgrade (Month 3-6, after 50+ paying users)
> **Goal**: Upgrade user-facing quality for paying customers

**Introduce plan-based model routing:**

| Task Type | Starter | Growth | Pro | Agency |
|-----------|---------|--------|-----|--------|
| **Premium** (content creation) | DeepSeek V3.2 | DeepSeek V3.2 | Gemini 3 Flash | Gemini 3 Flash |
| **Workhorse** (reasoning) | DeepSeek V3.2 | DeepSeek V3.2 | DeepSeek V3.2 | DeepSeek V3.2 |
| **Fast** (classification) | DeepSeek V3.2 | DeepSeek V3.2 | DeepSeek V3.2 | DeepSeek V3.2 |

**Why DeepSeek everywhere for Starter/Growth:**
- At $0.26/$0.38 per 1M tokens, it's near-free — cheaper than current gpt-4o-mini fallback
- 89th percentile intelligence means quality content at Starter/Growth value expectations
- 0.78% structured output error — excellent JSON compliance for all agent tasks

**Why Gemini 3 Flash for Pro/Agency Premium:**
- Pro ($14.00/mo) and Agency ($21.00/mo) customers pay enough to absorb higher costs
- 94th percentile intelligence + 7.8% hallucination = best content quality available
- Creates a real quality differentiation between plans that justifies the price gap
- Multimodal support enables future image/video analysis features

**Phase 3 Cost Per User:**
| Plan | Starter | Growth | Pro | Agency |
|------|---------|--------|-----|--------|
| Premium model cost | $0.02 | $0.12 | $2.20 | $5.50 |
| Fast+WH model cost | $0.03 | $0.12 | $0.46 | $1.16 |
| **Total AI cost** | **$0.05** | **$0.24** | **$2.66** | **$6.66** |
| Revenue | $2.00 | $7.00 | $14.00 | $21.00 |
| **AI Margin** | **92.9%** | **93.2%** | **74.8%** | **73.0%** |

### Phase 4: Scale Optimization (Month 6+)
> **Goal**: Model-specific routing for maximum value per token

**Per-task model assignment:**

| Task | Model | Why |
|------|-------|-----|
| `create.generate` | Gemini 3 Flash (Pro+Agency) / DeepSeek V3.2 (Starter+Growth) | User sees this. Quality = retention |
| `create.regenerate` | Same as generate | Same reasoning |
| `create.repurpose` | Same as generate | Same reasoning |
| `engage.reply` | Same as generate | User-facing responses |
| `engage.analyze` | Step 3.5 Flash ($0.10/$0.30) | Bulk classification, speed matters |
| `analyst.content_dna` | Step 3.5 Flash | Simple classification (500 tokens), 117 tok/s |
| `analyst.predict` | Step 3.5 Flash | Tiny output (200 tokens), pure speed |
| `analyst.performance` | DeepSeek V3.2 | Needs reasoning for performance analysis |
| `research.trends` | DeepSeek V3.2 | Reasoning-heavy, background task |
| `research.angles` | DeepSeek V3.2 | Semi-creative, background |
| `adapt.schedule` | Step 3.5 Flash | Data analysis, daily batch |
| `strategist.decide` | DeepSeek V3.2 | Strongest reasoning needed, weekly |

**Phase 4 Cost Per User (optimized):**
| Plan | Starter | Growth | Pro | Agency |
|------|---------|--------|-----|--------|
| **Total AI cost** | **$0.03** | **$0.15** | **$1.80** | **$4.50** |
| Revenue | $2.00 | $7.00 | $14.00 | $21.00 |
| **AI Margin** | **95.7%** | **95.7%** | **83.0%** | **81.7%** |

---

## 5. FINANCIAL CROSS-REFERENCE (vs COST_ANALYSIS.md)

### Comparison With Original Cost Doc Projections

| Stack | Starter | Growth | Pro | Agency | Source |
|-------|---------|--------|-----|--------|--------|
| **Best Models (Claude)** | $0.94 | $4.72 | $9.44 | $21.94 | COST_ANALYSIS.md |
| **Budget Smart (Gemini+DS)** | $0.20 | $1.00 | $2.00 | $4.60 | COST_ANALYSIS.md |
| **Our Phase 2** | $0.05 | $0.23 | $0.90 | $2.25 | This document |
| **Our Phase 3** | $0.05 | $0.24 | $2.66 | $6.66 | This document |
| **Our Phase 4** | $0.03 | $0.15 | $1.80 | $4.50 | This document |

### Key Financial Insights

1. **Phase 2 (near-zero cost) beats even Budget Smart** — Because we're still primarily on free models with DeepSeek as the safety net

2. **Phase 3 costs are inline with Budget Smart** — Pro/Agency add Gemini Flash, but DeepSeek for everything else keeps it affordable

3. **Phase 4 optimized routing saves ~30% over Phase 3** — Task-specific model selection (Step Flash for bulk, DeepSeek for reasoning) reduces waste

4. **Claude Sonnet remains economically unviable** for Starter/Growth — At $3/$15 per 1M tokens, even Starter would cost $0.94 just for AI (134% of revenue)

5. **All phases maintain >70% AI margins** — The worst case (Phase 3 Agency) is 73.0%, which still covers infra + growth

### Total Unit Economics (Including Infrastructure)

*Using Phase 3 (most conservative) + $20/mo Railway split across users:*

| | Starter | Growth | Pro | Agency |
|---|---------|--------|-----|--------|
| Revenue | $2.00 | $7.00 | $14.00 | $21.00 |
| AI Cost | $0.05 | $0.24 | $2.66 | $6.66 |
| Infra (at 50 users) | $0.40 | $0.40 | $0.40 | $0.40 |
| **Net Margin** | **$1.55 (77.5%)** | **$6.36 (90.9%)** | **$10.94 (78.1%)** | **$13.94 (66.4%)** |

At 100 users, infra per user drops to $0.20 and margins improve 5-15% across all tiers.

---

## 6. RISK ANALYSIS

### Risk 1: Free Model Discontinuation
**Probability**: Medium (6-12 months)
**Impact**: High — forces immediate paid migration
**Mitigation**: Phase 2 already has DeepSeek V3.2 as paid fallback. Migration is a config change, not a code change.

### Risk 2: DeepSeek Service Disruption
**Probability**: Low (13 providers on OpenRouter)
**Impact**: Medium — affects paid fallback reliability
**Mitigation**: Multi-provider routing via OpenRouter. Can add Gemini 3 Flash as secondary paid fallback.

### Risk 3: Qwen Data Collection Exposure
**Probability**: Certain (it's stated in their terms)
**Impact**: Medium — Agency clients' brand data used for model training
**Mitigation**: Phase 3 migrates paying users to DeepSeek (open weights, no data collection) and Gemini (Google enterprise privacy). Only free/trial users stay on Qwen.

### Risk 4: Output Quality Gap Between Free and Paid
**Probability**: Low-Medium
**Impact**: Low — Qwen 3.6 Plus is #1 ranked, comparable to paid models
**Mitigation**: A/B test content quality between Qwen free and DeepSeek paid before Phase 3 migration.

### Risk 5: Token Cost Inflation
**Probability**: Low (costs have been decreasing industry-wide)
**Impact**: Low — at 90%+ margins, 2x price increase still maintains profitability
**Mitigation**: Phase 4's per-task routing minimizes total tokens consumed.

---

## 7. MODELS WE EXPLICITLY REJECTED

| Model | Reason |
|-------|--------|
| **Claude Sonnet 4.6** | $3/$15 per 1M tokens — would consume 134% of Starter revenue |
| **MiniMax M2.7** | 65.6% hallucination rate, 89.3% uptime — both disqualifying |
| **Gemini 3.1 Flash Lite** | 76th percentile intelligence — too low for content creation. Output price ($1.50/1M) higher than DeepSeek ($0.38) with worse quality |
| **GPT-4o** | $2.50/$10.00 per 1M — massively expensive, and OpenAI's competitive moat makes lock-in risky |
| **MiMo-V2-Pro** | New model (#2 ranked) but no production track record, limited provider availability |

---

## 8. VOICE, IMAGE & MULTIMODAL STRATEGY

### Voice (Not Yet Implemented)
- **Current**: No voice features
- **Future**: Gemini 3 Flash supports audio input ($1/1M audio tokens) — could enable voice-to-content
- **Recommendation**: Phase 4+ feature. No model decision needed now.

### Image Generation
- **Current**: HuggingFace FLUX.1-schnell (free), Gemini image gen for paid tiers
- **Status**: Working well at current cost
- **Recommendation**: No change. Image generation is a separate pipeline from LLM routing.

### Multimodal Analysis
- **Opportunity**: Gemini 3 Flash and Qwen 3.6 Plus both support image+text input
- **Use Case**: Analyzing competitor posts (screenshots), understanding visual brand identity
- **Recommendation**: Phase 4+ feature. Build on Gemini infrastructure once Pro/Agency customers use it.

---

## 9. IMPLEMENTATION CHECKLIST

### Immediate (Phase 1 — This Week)
- [ ] Change `LLM_PAID_FALLBACK` env var from `gpt-4o-mini` to `deepseek/deepseek-v3.2`
- [ ] Change `LLM_PAID_FALLBACK_PROVIDER` env var to `openrouter`
- [ ] Add DeepSeek V3.2 to `MODEL_TOKEN_COSTS` in settings
- [ ] Update LLMConfig in admin dashboard

### Month 3 (Phase 3 — After 50 paying users)
- [ ] Set up `plan_tier_models` in LLMConfig for Pro/Agency → Gemini 3 Flash
- [ ] A/B test content quality: Qwen free vs DeepSeek vs Gemini Flash
- [ ] Add Gemini 3 Flash to `MODEL_TOKEN_COSTS`
- [ ] Update cost tracking dashboards

### Month 6 (Phase 4 — Optimization)
- [ ] Implement per-task model routing in `plan_tier_models`
- [ ] Add Step 3.5 Flash (paid) for bulk classification tasks
- [ ] Build model performance monitoring (quality scores per model per task)
- [ ] Review and update this document with 6 months of production data

---

## 10. THE 5 NUMBERS THAT MATTER

| Metric | Value |
|--------|-------|
| **Worst-case AI cost per user** | $6.66/mo (Phase 3 Agency) |
| **Best-case AI margin** | 95.7% (Phase 4 Starter) |
| **Models needed for full stack** | 3 (DeepSeek V3.2 + Gemini 3 Flash + Step 3.5 Flash) |
| **Free model dependency** | Eliminated by Phase 3 |
| **Break-even with salary** | ~179 users (unchanged — AI costs don't significantly impact this) |

---

*This is a living document. Revisit every 3 months as the model landscape evolves rapidly.*

---

## 11. COST ECONOMICS DASHBOARD — HOW IT WORKS

> **Location**: Admin Dashboard → Finance → Cost Economics
> **Code**: `apps/admin_dashboard/views/costs.py`
> **Template**: `templates/admin_dashboard/costs/overview.html`

The Cost Economics dashboard is Kova's real-time financial intelligence center. It answers one question: **"Are we making money, and where?"**

### 11.1 Dashboard Sections

The dashboard has 6 sections, each serving a specific purpose:

#### Section 1: Real-Time AI Cost Summary (Top Cards)
Shows actual AI spend over 3 time windows:

| Card | What It Shows | Why It Matters |
|------|--------------|----------------|
| **Cost (24h)** | Total USD spent on AI in the last 24 hours | Spot spikes immediately (e.g., a runaway prompt loop) |
| **Cost (7d)** | Weekly spend | Trend indicator — is spend growing faster than users? |
| **Cost (30d)** | Monthly spend | The real number — compare against revenue |
| **Paid vs Free Calls** | How many LLM calls hit paid models vs free | If paid % is climbing, free models may be degrading |

**How it calculates**: Every AI call logs an `AgentAction` record with `model_used`, `input_tokens`, and `output_tokens`. The dashboard multiplies these against the `MODEL_PRICING` table (defined in `costs.py`):

```
cost = (input_tokens / 1,000,000 × input_price) + (output_tokens / 1,000,000 × output_price)
```

If the model contains `:free` in its name or has $0 pricing, it's counted as a free call.

#### Section 2: Daily Cost Trend Chart
A 30-day line chart showing paid vs free AI cost per day. Helps you see:
- Did a deployment change cause a cost spike?
- Are costs growing linearly or exponentially with users?
- What days have the highest usage? (scheduling optimization)

#### Section 3: Per-Plan Unit Economics Table
**The most important section.** For each plan (Starter, Growth, Pro, Agency), shows:

| Column | Meaning |
|--------|---------|
| **Active Users** | Real count of paying users on that plan |
| **Avg Calls/User** | How many AI calls each user makes per month |
| **Avg Tokens/User** | Input + output tokens consumed per user |
| **LLM Cost** | Actual AI cost per user (from real AgentAction data) |
| **Image Cost** | Estimated image generation cost per user |
| **Voice Cost** | Estimated Whisper transcription cost per user |
| **Infra Cost** | Railway hosting cost ÷ total active users |
| **Total Cost** | LLM + Image + Voice + Infra per user |
| **Profit/User** | Plan price (USD) − Total cost per user |
| **Margin %** | (Profit ÷ Price) × 100 |

**Critical rule**: If any plan shows negative profit, that plan is losing money on every user. Action required immediately (reduce model quality for that tier or increase price).

**Image cost logic**: Starter gets $0 image cost (free providers only). Growth/Pro/Agency estimated at $0.005/image using Pollinations.ai as paid fallback.

**Voice cost logic**: OpenAI Whisper at $0.006/minute, with average memo length of 20 seconds:
```
voice_cost = voice_memos × (20 / 60) × $0.006
```

**Infrastructure cost scaling** (built into `_calculate_infra_cost_per_user()`):

| Users | Railway Estimate | Per User |
|-------|-----------------|----------|
| 1-50 | $25/mo | $0.50 |
| 51-100 | $30/mo | $0.30 |
| 101-500 | $50/mo | $0.10 |
| 501-1000 | $80/mo | $0.08 |
| 1001-5000 | $200/mo | $0.04 |
| 5000+ | $400/mo | $0.08 |

#### Section 4: Top Consuming Users
Lists the 15 users consuming the most tokens in the last 30 days. Shows:
- Their email, company, and plan tier
- Total AI cost attributed to them
- Their plan revenue vs their cost
- Whether they're **profitable or underwater**

**Why this exists**: A single Agency user running bulk content could consume more AI than 50 Starter users. If one user costs more than they pay, you need to either upgrade their plan, add rate limits, or accept it as a growth investment.

#### Section 5: Cost by Agent Type
Breaks down AI costs by which agent is spending: Create, Engage, Analyst, Research, Adapt, Strategist. Shows calls, tokens, and cost per agent.

**Common pattern**: Create agent dominates costs (40-60%) because it generates the most output tokens (full blog posts, social captions). If Engage or Analyst costs spike, something may be misfiring in batch jobs.

#### Section 6: Scenario Cost Calculator
An interactive "what-if" projector. You enter:

**Left side — User Counts**:
- How many users on each plan tier

**Right side — Model Pricing** (USD per 1M tokens):
- Premium Tier: input / output prices
- Workhorse Tier: input / output prices
- Fast Tier: input / output prices
- Image, Voice, and Hosting costs

Hit **Calculate** and it returns per-plan projections: revenue, cost breakdown, profit per user, and margins.

### 11.2 The 3 Model Tiers Explained

Kova doesn't use one AI model for everything. Tasks are grouped into 3 tiers based on what they need, and each tier can run a different model. This is configured in the `LLMConfig` singleton (`apps/agents/models.py`).

#### Premium Tier — "The Copywriter"
- **Purpose**: Creative, user-facing text that the customer will see and judge
- **Tasks**: `create.generate`, `create.regenerate`, `create.repurpose`, `engage.reply`
- **Quality requirement**: HIGH — this is the product output. Bad text = churn
- **Token profile**: Heavy output (4K-8K tokens per call)
- **Cost sensitivity**: Low — quality earns/retains revenue
- **Recommended model**: Gemini 3 Flash ($0.50/$3.00) for Pro/Agency, DeepSeek V3.2 ($0.26/$0.38) for Starter/Growth

#### Workhorse Tier — "The Strategist"
- **Purpose**: Deep reasoning, research, and strategic analysis
- **Tasks**: `research.trends`, `research.angles`, `strategist.brief`, `strategist.decide`
- **Quality requirement**: MEDIUM-HIGH — needs strong reasoning but output is internal
- **Token profile**: Moderate (1.5K-2.5K tokens output)
- **Cost sensitivity**: Medium — user doesn't see raw output, it's synthesized
- **Recommended model**: DeepSeek V3.2 ($0.26/$0.38) — 89th percentile reasoning at lowest cost

#### Fast Tier — "The Analyst"
- **Purpose**: Quick classification, scoring, data extraction
- **Tasks**: `engage.analyze`, `analyst.content_dna`, `analyst.predict`, `analyst.performance`, `adapt.schedule`
- **Quality requirement**: LOW-MEDIUM — simple structured JSON output
- **Token profile**: Light (200-1.5K tokens output)
- **Cost sensitivity**: HIGH — these run in bulk batches (hourly/daily), volume multiplies cost fast
- **Recommended model**: Step 3.5 Flash ($0.10/$0.30) — fastest throughput (117 tok/s) at lowest price

#### Token Distribution Across Tiers
The calculator splits estimated tokens per plan as:
- **40% Premium** — content generation is the bulk of output
- **35% Workhorse** — research and strategy tasks
- **25% Fast** — classification and analytics

This split is based on observed production patterns. If your Create agent fires more than Research, the real split may be 50/25/25. The Top Consuming Users section shows actual data to validate these estimates.

### 11.3 Scenario Presets

The calculator has 5 preset buttons that load different model pricing scenarios:

#### Phase 2 (Now) — Free Models
```
Premium:   $0 / $0          (Qwen 3.6 Plus free)
Workhorse: $0 / $0          (Qwen 3.6 Plus free)
Fast:      $0 / $0          (StepFun free)
Images:    $0               (HuggingFace/Together.ai free)
```
**When to use**: Current state. 90%+ calls hit free models, paid fallback rare. Shows your floor cost (just infra + voice).

#### Phase 3 — All DeepSeek
```
Premium:   $0.26 / $0.38    (DeepSeek V3.2)
Workhorse: $0.26 / $0.38    (DeepSeek V3.2)
Fast:      $0.26 / $0.38    (DeepSeek V3.2)
Images:    $0.005           (Pollinations.ai)
```
**When to use**: After free model dependency is eliminated. All tiers on cheapest quality paid model. This is the "safe paid floor."

#### Phase 4 — Optimized Routing
```
Premium:   $0.50 / $3.00    (Gemini 3 Flash)
Workhorse: $0.26 / $0.38    (DeepSeek V3.2)
Fast:      $0.10 / $0.30    (Step 3.5 Flash)
Images:    $0.005
```
**When to use**: Mature state. Premium gets the best model, fast gets the cheapest model, workhorse in the middle. Maximizes quality-per-dollar.

#### Free Only
Same as Phase 2. All zeros. Shows infrastructure-only cost.

#### Premium — Ceiling Test
```
Premium:   $3.00 / $15.00   (Claude Sonnet level)
Workhorse: $0.50 / $3.00    (Gemini Flash level)
Fast:      $0.26 / $0.38    (DeepSeek level)
Images:    $0.04            (Expensive image gen)
```
**When to use**: Stress test. "What if we used the most expensive models?" Shows your worst-case cost ceiling. If margins are still positive here, your pricing is robust.

### 11.4 Estimated Token Usage Per Plan

These are the assumed monthly token volumes per user, per plan (defined in `PLAN_TOKEN_ESTIMATES`):

| Plan | Input Tokens | Output Tokens | Images | Voice Memos |
|------|-------------|--------------|--------|-------------|
| **Starter** | 40,000 | 35,000 | 0 | 5 |
| **Growth** | 260,000 | 220,000 | 50 | 20 |
| **Pro** | 1,100,000 | 900,000 | 200 | 50 |
| **Agency** | 2,200,000 | 1,800,000 | 500 | 100 |

**Where these numbers come from**: Based on plan feature limits (max posts, max agents, max platforms) and estimated usage patterns from the COST_ANALYSIS.md doc. The Per-Plan Unit Economics section shows **actual** usage — check it regularly to see if estimates match reality. If actual Pro usage is 500K tokens but we estimated 1.1M, margins are better than projected.

### 11.5 The Non-LLM Cost Components

Not all AI costs are LLM tokens:

| Service | Provider | Cost | Used For |
|---------|----------|------|----------|
| **Whisper** | OpenAI | $0.006/min | Voice memo transcription |
| **FLUX.1-schnell** | Together.ai | Free | Image generation (primary) |
| **FLUX.1-schnell** | HuggingFace | Free | Image generation (fallback 1) |
| **Pollinations.ai** | Pollinations | $0.005/img | Image generation (fallback 2) |
| **Pillow Graphics** | On-device | Free | Branded quote cards, stat graphics, CTA banners |
| **Railway** | Railway.app | $20+/mo | Server hosting, DB, Redis |

**Image generation priority chain**: Together.ai (free) → HuggingFace (free) → Pollinations ($0.005/img). The calculator uses $0.005 as worst-case, but in practice most images are generated for free.

### 11.6 Reading the Numbers — Decision Framework

Use this framework when reviewing Cost Economics:

| Signal | Meaning | Action |
|--------|---------|--------|
| **Margin < 50% on any plan** | Plan is barely profitable | Raise price or downgrade model tier for that plan |
| **Margin < 0% on any plan** | Losing money per user | Immediate: downgrade model or raise price |
| **Paid calls > 20%** | Free models degrading | Check free model uptime, consider Phase 3 migration |
| **One user > 3× avg cost** | Power user or abuse | Check if plan matches usage, consider rate limits |
| **Agent cost spike** | Possible batch loop or prompt issue | Check Celery logs, look for repeated failures |
| **Cost growing faster than revenue** | Unsustainable trajectory | Review token estimates, optimize prompts, adjust routing |
| **Actual tokens << estimated tokens** | Users less active than projected | Good for margins, but may signal engagement problem |

### 11.7 How Dynamic Pricing Connects

The Cost Economics dashboard now uses `get_all_plan_limits()` instead of hardcoded `PLAN_LIMITS`. This means:

1. When you change a plan price on the **Plan Pricing** page (Admin → Billing → Plan Pricing), the cost calculator automatically picks up the new price for margin calculations
2. Revenue projections in the scenario calculator use live DB prices
3. Per-plan unit economics reflect the actual prices you're charging, not the code defaults

**The feedback loop**: Change prices on Plan Pricing → refresh Cost Economics → verify margins are still healthy → adjust if needed. No code changes, no redeployment.
