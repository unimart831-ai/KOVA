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
| Revenue | $0.70 | $3.52 | $10.56 | $24.65 |
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
- Pro ($10.56/mo) and Agency ($24.65/mo) customers pay enough to absorb higher costs
- 94th percentile intelligence + 7.8% hallucination = best content quality available
- Creates a real quality differentiation between plans that justifies the price gap
- Multimodal support enables future image/video analysis features

**Phase 3 Cost Per User:**
| Plan | Starter | Growth | Pro | Agency |
|------|---------|--------|-----|--------|
| Premium model cost | $0.02 | $0.12 | $2.20 | $5.50 |
| Fast+WH model cost | $0.03 | $0.12 | $0.46 | $1.16 |
| **Total AI cost** | **$0.05** | **$0.24** | **$2.66** | **$6.66** |
| Revenue | $0.70 | $3.52 | $10.56 | $24.65 |
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
| Revenue | $0.70 | $3.52 | $10.56 | $24.65 |
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
| Revenue | $0.70 | $3.52 | $10.56 | $24.65 |
| AI Cost | $0.05 | $0.24 | $2.66 | $6.66 |
| Infra (at 50 users) | $0.40 | $0.40 | $0.40 | $0.40 |
| **Net Margin** | **$0.25 (35.7%)** | **$2.88 (81.8%)** | **$7.50 (71.0%)** | **$17.59 (71.4%)** |

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
