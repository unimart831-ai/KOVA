# Kova Agent — AI Models Research & Recommendations
> Choosing the right models for content that actually performs

**Last updated:** June 2026
**Current provider:** OpenRouter (gateway to 665+ models)
**Current dev model:** `deepseek/deepseek-v3.2` (all LLM tiers)
**Current image gen:** Together.ai FLUX tier-routed (FLUX.1-krea-dev for Growth, FLUX.1.1-pro for Pro/Agency)

---

## Table of Contents
1. [Current Model Architecture](#1-current-model-architecture)
2. [LLM Models — Tiered Recommendations](#2-llm-models--tiered-recommendations)
3. [Image Generation Models](#3-image-generation-models)
4. [Cost Analysis — Monthly Budget by Plan](#4-cost-analysis--monthly-budget-by-plan)
5. [Free Models for Development](#5-free-models-for-development)
6. [Production Model Strategy](#6-production-model-strategy)
7. [Implementation — Environment Variables](#7-implementation--environment-variables)
8. [Model Comparison Matrix](#8-model-comparison-matrix)
9. [Image Model Comparison](#9-image-model-comparison)
10. [Upgrade Path](#10-upgrade-path)

---

## 1. Current Model Architecture

Kova uses **tiered model routing** — different quality models for different agent tasks. This is configured in `config/settings/base.py`:

```
AGENT_MODELS = {
    # PREMIUM tier — user-facing creative content (must be excellent)
    "create.generate":    LLM_MODEL_PREMIUM,
    "create.regenerate":  LLM_MODEL_PREMIUM,
    "create.repurpose":   LLM_MODEL_PREMIUM,
    "engage.reply":       LLM_MODEL_PREMIUM,

    # WORKHORSE tier — reasoning + synthesis (must be smart)
    "research.trends":    LLM_MODEL_WORKHORSE,
    "research.angles":    LLM_MODEL_WORKHORSE,
    "strategist.brief":   LLM_MODEL_WORKHORSE,

    # FAST tier — classification, scoring, extraction (must be fast + cheap)
    "engage.analyze":     LLM_MODEL_FAST,
    "analyst.performance": LLM_MODEL_FAST,
    "analyst.content_dna": LLM_MODEL_FAST,
    "analyst.predict":    LLM_MODEL_FAST,
    "adapt.schedule":     LLM_MODEL_FAST,
}
```

**The problem:** In dev, ALL tiers use `stepfun/step-3.5-flash:free`. This is fine for testing flow but the content quality isn't production-grade for user-facing output. For production, we need the right model at each tier.

---

## 2. LLM Models — Tiered Recommendations

### Understanding the Tiers

| Tier | Purpose | What matters | Budget priority |
|------|---------|-------------|-----------------|
| **Premium** | Content creation, engagement replies | Creative quality, brand voice adherence, platform-native writing, Swahili/Sheng | Highest — this IS the product |
| **Workhorse** | Research, strategy, competitor analysis | Reasoning depth, structured output, trend comprehension | Medium — quality matters but users don't see raw output |
| **Fast** | Sentiment analysis, scoring, classification | Speed, cost, reliable JSON output | Lowest — high volume, low stakes |

### PREMIUM Tier — Content the User Publishes

This is the most critical choice. The Create Agent's output IS what users pay for.

| Model | Provider | Cost (per 1M tokens: in/out) | Context | Strengths | Weaknesses | Verdict |
|-------|----------|-----|---------|-----------|------------|---------|
| **Claude Sonnet 4.6** | Anthropic | $3 / $15 | 1M | Best creative writing, nuanced brand voice, excellent at following complex system prompts, strong multi-language | Higher cost | **🏆 RECOMMENDED** |
| **Gemini 3 Flash Preview** | Google | $0.50 / $3 | 1M | #3 Marketing rank on OpenRouter, fast, cheap for quality, good multilingual | Newer model still in preview | **Best value pick** |
| **GPT-5 Mini** | OpenAI | ~$1.50 / $6 | 400K | Strong at structured content, good instruction following | Less creative flair than Claude | Good alternative |
| **DeepSeek V3.2** | DeepSeek | $0.26 / $0.38 | 164K | Extremely cheap, #13 Marketing rank, GPT-5 class reasoning | Less proven for creative marketing content | Budget production option |
| **Qwen 3.6 Plus Preview** | Qwen | FREE | 1M | Free, strong reasoning, large context | Data collection, preview status, less tested for marketing | Best free option for staging |
| **Grok 4.20** | xAI | $2 / $6 | 2M | Lowest hallucination, strong instruction following | Higher cost, newer | Worth testing |

**Recommendation:**
- **Production Premium:** `anthropic/claude-sonnet-4.6` — Best creative writing, brand voice adherence, and prompt following. This is what generates the content users publish.
- **Budget Production:** `google/gemini-3-flash-preview` — 80% of Claude's quality at ~15% of the cost. Excellent for the Kazi/Jipange tiers.
- **Staging/Testing:** `qwen/qwen3.6-plus-preview:free` — Free, strong enough to test flows.

### WORKHORSE Tier — Research, Strategy, Competitor Analysis

| Model | Provider | Cost (per 1M: in/out) | Context | Strengths | Verdict |
|-------|----------|-----|---------|-----------|---------|
| **Gemini 3 Flash Preview** | Google | $0.50 / $3 | 1M | #1 Academia, #3 Marketing, #3 Legal — best all-round reasoning at this price | **🏆 RECOMMENDED** |
| **DeepSeek V3.2** | DeepSeek | $0.26 / $0.38 | 164K | GPT-5 class reasoning, absurdly cheap, #4 Academia | **Budget pick** |
| **Claude Sonnet 4.6** | Anthropic | $3 / $15 | 1M | Overkill for this tier but excellent reasoning | Only if budget allows |
| **MiniMax M2.7** | MiniMax | $0.30 / $1.20 | 205K | #17 Marketing, strong multi-agent workflows | Good alternative |
| **StepFun Step 3.5 Flash** | StepFun | FREE | 256K | Currently used in dev, MoE 196B/11B active | Best free option |

**Recommendation:**
- **Production Workhorse:** `google/gemini-3-flash-preview` — Best reasoning-per-dollar. Research and strategy tasks need comprehension, not creativity.
- **Budget Production:** `deepseek/deepseek-v3.2` — At $0.26/$0.38, you could run this tier at nearly zero cost while getting GPT-5 class reasoning.

### FAST Tier — Sentiment, Scoring, Classification

| Model | Provider | Cost (per 1M: in/out) | Context | Strengths | Verdict |
|-------|----------|-----|---------|-----------|---------|
| **Gemma 3n E4B Instruct** | Google (via Together) | $0.02 / $0.04 | — | Absurdly cheap, fast, good for classification | **🏆 RECOMMENDED for cost** |
| **Llama 3 8B Instruct Lite** | Meta (via Together) | $0.10 / $0.10 | — | Proven, reliable JSON output, very fast | **Reliable pick** |
| **Mistral Small 3** | Mistral (via Together) | $0.10 / $0.30 | — | European model, good structured output | Good alternative |
| **Qwen 2.5 7B Instruct Turbo** | Qwen (via Together) | $0.30 / $0.30 | — | Strong for size, good multilingual | Slightly more expensive |
| **DeepSeek V3.2** | DeepSeek | $0.26 / $0.38 | 164K | Could unify workhorse + fast on same model | Simplicity advantage |
| **StepFun Step 3.5 Flash** | StepFun | FREE | 256K | Current dev model, works for classification | Best free option |

**Recommendation:**
- **Production Fast:** `deepseek/deepseek-v3.2` via OpenRouter — Unify workhorse + fast on the same model. At $0.26/$0.38 per 1M tokens, it costs almost nothing for classification tasks (which use ~200-500 tokens each). Simplifies config.
- **Ultra-budget:** `google/gemma-3n-e4b-instruct` via Together.ai — $0.02/$0.04 if you need absolute minimum cost.

---

## 3. Image Generation Models

### Current Setup (Implemented — Tier-Routed)
- **Architecture**: Per-plan model routing via LLMConfig singleton (admin-configurable)
- **Starter**: Images disabled (0 limit) — fallback model: FLUX.1-schnell ($0.003/img)
- **Growth**: Together.ai FLUX.1-krea-dev ($0.025/img, 50/month)
- **Pro**: Together.ai FLUX.1.1-pro ($0.04/img, 100/month)
- **Agency**: Together.ai FLUX.1.1-pro ($0.04/img, 500/month — capped)
- **Fallback chain**: Together.ai → HuggingFace FLUX.1-schnell (free) → Pollinations (free)
- **Visual Strategy**: AI selects optimal visual type (ai_photo, quote_card, tip_graphic, etc.) — Pillow graphics are FREE
- **Kill switch**: Admin dashboard toggle + `AI_IMAGE_GENERATION_ENABLED` env var

> **Note:** The research table below shows models evaluated during planning. The implemented system uses Together.ai FLUX models exclusively for AI photo generation, with Pillow for branded graphics.

### Available Image Models (via OpenRouter + Direct APIs)

| Model | Provider | Cost per image | Quality | Speed | Text in images | Editing | Verdict |
|-------|----------|---------------|---------|-------|---------------|---------|---------|
| **FLUX.1-schnell** | HuggingFace (free) | FREE | Good — fast generation, decent quality | ~3-5s | Poor | No | **Current: Good for free tier** |
| **FLUX.1-dev** | HuggingFace / Together | ~$0.01 | Better — more detailed, coherent | ~8-12s | Fair | No | **Free tier upgrade** |
| **Gemini 2.5 Flash Image (Nano Banana)** | Google via OpenRouter | ~$0.003-0.01 | Excellent — contextual understanding, high quality | ~5-8s | Good | Yes (multi-turn) | **🏆 BEST VALUE** |
| **Gemini 3.1 Flash Image (Nano Banana 2)** | Google via OpenRouter | ~$0.005-0.015 | Excellent+ — Pro-level quality at Flash speed | ~5-8s | Very good | Yes (multi-turn) | **Premium pick** |
| **Gemini 3 Pro Image (Nano Banana Pro)** | Google via OpenRouter | ~$0.03-0.05 | Industry-leading — 4K output, identity preservation, text rendering | ~10-15s | Excellent | Yes (localized edits) | **Best quality available** |
| **GPT-5 Image Mini** | OpenAI via OpenRouter | ~$0.02-0.04 | Excellent — superior instruction following, text rendering | ~8-12s | Excellent | Yes | **Strong alternative** |
| **GPT-5 Image** | OpenAI via OpenRouter | ~$0.08-0.15 | Top tier — best instruction following | ~10-15s | Excellent | Yes | **Premium-only option** |
| **Seedream 4.5** | ByteDance via OpenRouter | $0.04 per image | Excellent — portrait refinement, text rendering | ~5-8s | Very good | Yes | **Good all-rounder** |
| **Riverflow V2 Fast** | Sourceful via OpenRouter | ~$0.02 per image | Excellent — reasoning-integrated generation | ~3-5s | Good (custom fonts) | Yes | **Speed + quality** |
| **Riverflow V2 Pro** | Sourceful via OpenRouter | ~$0.15 per image | Best — SOTA image gen + editing | ~8-12s | Excellent (custom fonts) | Yes | **Top quality pick** |
| **DALL-E 3** | OpenAI direct | ~$0.04-0.08 | Good — reliable, safe | ~10-15s | Good | No | Legacy but reliable |
| **Stable Diffusion 3.5** | Stability AI | ~$0.01-0.03 | Good — open source, customizable | ~5-10s | Fair | No | Self-host option |

### Image Model Recommendation for Kova

**The key insight:** Social media images need to be *good enough quickly*, not *perfect slowly*. A 3-second FLUX image that goes out on time beats a 15-second masterpiece that delays the pipeline.

**Recommended Strategy (3-tier image generation):**

| Tier | Model | When to use | Cost | Why |
|------|-------|-------------|------|-----|
| **Free / Dev** | HuggingFace FLUX.1-schnell | Development, Jipange plan users | FREE | Already works, decent quality |
| **Standard** | Gemini 2.5 Flash Image (Nano Banana) | Kazi + Biashara plan users | ~$0.003-0.01/image | Best value: contextual understanding means it handles brand-specific prompts better. Text rendering for promotional images. Multi-turn editing. |
| **Premium** | Gemini 3 Pro Image (Nano Banana Pro) | Wakala plan users, hero content | ~$0.03-0.05/image | Industry-leading quality. 4K output. Identity preservation (consistent brand characters). Localized edits. |

**Why Gemini image models over GPT-5 Image:**
1. **Cheaper** — Nano Banana is ~3-5x cheaper than GPT-5 Image Mini
2. **Contextual understanding** — The Gemini image models understand context from conversation, so it can reference previous brand imagery
3. **Multi-turn editing** — "Make the logo bigger" / "Change background to blue" in follow-up calls
4. **Text rendering** — Critical for social media promotional images (sale prices, CTAs, brand names)
5. **Works via OpenRouter** — Same API gateway Kova already uses for LLMs

### Image Generation via OpenRouter (New Capability)

OpenRouter now supports image generation models. This means Kova can route BOTH text AND image generation through a single API gateway:

```python
# Current: Separate API for images (HuggingFace direct)
# New: Can use OpenRouter for images too

# Example: Gemini Image via OpenRouter
response = client.chat.completions.create(
    model="google/gemini-2.5-flash-image",
    messages=[{"role": "user", "content": prompt}],
    # Returns image in response
)
```

**Advantage:** Single API key, unified billing, consistent fallback handling.

---

## 4. Cost Analysis — Monthly Budget by Plan

### Assumptions
- Average post generates ~1,500 tokens (prompt + response) for Create Agent
- Each post triggers ~500 tokens for scoring/DNA (Fast tier)
- Daily Brief: ~3,000 tokens/day (Workhorse)
- Research: ~2,000 tokens per run, 2x/day (Workhorse)
- Strategist: ~3,000 tokens per run, 3x/day (Workhorse)
- Engage cycle: ~500 tokens per interaction (Fast + Premium for replies)
- Competitor analysis: ~5,000 tokens per analysis, weekly (Workhorse)
- Image: 1 per post

### Recommended Production Config Cost Estimates

| Plan | Posts/mo | AI Cost Est. | Image Cost Est. | Total AI Cost | Plan Revenue | Margin |
|------|----------|-------------|----------------|---------------|-------------|--------|
| **Jipange** (KES 299) | 15 | ~$0.05 | FREE (FLUX) | ~$0.05 | ~$2.00 | 98% |
| **Kazi** (KES 999) | 60 | ~$0.25 | ~$0.18 (Nano Banana) | ~$0.43 | ~$7.00 | 94% |
| **Biashara** (KES 1,999) | 200 | ~$0.85 | ~$0.60 (Nano Banana) | ~$1.45 | ~$14.00 | 90% |
| **Wakala** (KES 2,999) | 500 | ~$2.50 | ~$2.50 (Nano Banana Pro) | ~$5.00 | ~$21.00 | 76% |

**Key insight:** Even with premium models (Claude Sonnet for content, Gemini Flash for reasoning, Gemini images), AI costs are **under $5/month** for the highest plan. Margins are excellent at every tier.

### Alternative: All-DeepSeek Budget Config

| Plan | Posts/mo | AI + Image Cost | Plan Revenue | Margin |
|------|----------|----------------|-------------|--------|
| **Jipange** | 15 | ~$0.02 | ~$2.00 | 99% |
| **Kazi** | 60 | ~$0.10 | ~$7.00 | 99% |
| **Biashara** | 200 | ~$0.35 | ~$14.00 | 98% |
| **Wakala** | 500 | ~$1.00 | ~$21.00 | 95% |

DeepSeek V3.2 across all tiers + FLUX free images = almost zero cost. Quality trade-off: content writing won't be as polished as Claude, but still GPT-5 class.

---

## 5. Free Models for Development

### Best Free LLM Models (via OpenRouter)

| Model | ID | Context | Quality | Rate Limits | Notes |
|-------|-----|---------|---------|-------------|-------|
| **Qwen 3.6 Plus Preview** | `qwen/qwen3.6-plus-preview:free` | 1M | Near frontier | Generous | ⭐ Best free model RIGHT NOW. Strong reasoning, good creative output. |
| **StepFun Step 3.5 Flash** | `stepfun/step-3.5-flash:free` | 256K | Good | Generous | Current dev model. MoE 196B. Good for most tasks. |
| **DeepSeek R1 (free)** | `deepseek/deepseek-r1:free` | 164K | Excellent reasoning | Rate limited | Best free reasoning model, but slow (thinking tokens). |
| **Llama 4 Maverick (free)** | `meta-llama/llama-4-maverick:free` | 1M | Good | Rate limited | Meta's latest open model. |
| **Gemini 2.5 Flash (free)** | `google/gemini-2.5-flash-preview:free` | 1M | Good | Rate limited | Good for testing Gemini quality before upgrading. |

**Recommended dev config (April 2026):**
```env
# Switch from stepfun to qwen for better dev quality
LLM_MODEL_PREMIUM=qwen/qwen3.6-plus-preview:free
LLM_MODEL_WORKHORSE=qwen/qwen3.6-plus-preview:free
LLM_MODEL_FAST=stepfun/step-3.5-flash:free
```

### Free Image Generation
- **HuggingFace FLUX.1-schnell** — Already configured, working, free
- No free alternatives match its ease of use

---

## 6. Production Model Strategy

### The Recommended Production Stack

```
┌─────────────────────────────────────────────────────────────┐
│                    PREMIUM TIER                              │
│  Claude Sonnet 4.6 (anthropic/claude-sonnet-4.6)           │
│  $3/$15 per 1M tokens                                       │
│  → Create Agent content, Engage Agent replies                │
│  → WHY: Best creative writing, brand voice, multilingual     │
├─────────────────────────────────────────────────────────────┤
│                   WORKHORSE TIER                             │
│  Gemini 3 Flash Preview (google/gemini-3-flash-preview)     │
│  $0.50/$3 per 1M tokens                                     │
│  → Research, Strategy, Daily Brief, Competitor Intel         │
│  → WHY: #1 Academia, #3 Marketing, best value for reasoning  │
├─────────────────────────────────────────────────────────────┤
│                      FAST TIER                               │
│  DeepSeek V3.2 (deepseek/deepseek-v3.2)                    │
│  $0.26/$0.38 per 1M tokens                                  │
│  → Sentiment, scoring, DNA extraction, scheduling            │
│  → WHY: GPT-5 class at fraction of cost, reliable JSON      │
├─────────────────────────────────────────────────────────────┤
│                   IMAGE GENERATION                           │
│  Free: HuggingFace FLUX.1-schnell (Jipange plan)           │
│  Standard: Gemini 2.5 Flash Image — Nano Banana (Kazi+)    │
│  Premium: Gemini 3 Pro Image — Nano Banana Pro (Wakala)     │
│  → WHY: Text rendering, contextual understanding, editing    │
└─────────────────────────────────────────────────────────────┘
```

### Alternative: Budget-First Stack (Maximize Margin)

```
PREMIUM:    google/gemini-3-flash-preview   ($0.50/$3)
WORKHORSE:  deepseek/deepseek-v3.2          ($0.26/$0.38)
FAST:       deepseek/deepseek-v3.2          ($0.26/$0.38)
IMAGE:      HuggingFace FLUX.1-schnell      (FREE)
```

Total cost: under $1/month for the highest plan. Sacrifice ~20% content quality vs. the recommended stack.

### Alternative: Quality-Maximized Stack

```
PREMIUM:    anthropic/claude-opus-4.6       ($5/$25)
WORKHORSE:  anthropic/claude-sonnet-4.6     ($3/$15)
FAST:       google/gemini-3-flash-preview   ($0.50/$3)
IMAGE:      Gemini 3 Pro Image              (~$0.05/image)
```

Best possible quality. Cost: ~$10-15/month for Wakala plan. Still highly profitable.

---

## 7. Implementation — Environment Variables

### Development (.env)
```env
# ─── LLM (OpenRouter — free models for dev) ─────────────────
DEFAULT_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx

# Upgrade from stepfun to qwen for better dev quality
LLM_MODEL_PREMIUM=qwen/qwen3.6-plus-preview:free
LLM_MODEL_WORKHORSE=qwen/qwen3.6-plus-preview:free
LLM_MODEL_FAST=stepfun/step-3.5-flash:free

# ─── IMAGE (HuggingFace — free) ─────────────────────────────
AI_IMAGE_GENERATION_ENABLED=True
HF_TOKEN=hf_xxxxxxxxxxxxx
```

### Production (Railway env vars)
```env
# ─── LLM (OpenRouter — paid models) ─────────────────────────
DEFAULT_LLM_PROVIDER=openrouter
OPENROUTER_API_KEY=sk-or-v1-xxxxxxxxxxxxx

LLM_MODEL_PREMIUM=anthropic/claude-sonnet-4.6
LLM_MODEL_WORKHORSE=google/gemini-3-flash-preview
LLM_MODEL_FAST=deepseek/deepseek-v3.2

# ─── IMAGE (multi-tier) ─────────────────────────────────────
AI_IMAGE_GENERATION_ENABLED=True
HF_TOKEN=hf_xxxxxxxxxxxxx
# Future: Add OpenRouter image gen for premium tiers
```

### Per-Agent Override Examples
```env
# If you want a specific model for a specific task:
LLM_MODEL_CREATE_GENERATE=anthropic/claude-sonnet-4.6
LLM_MODEL_ENGAGE_REPLY=anthropic/claude-sonnet-4.6
LLM_MODEL_RESEARCH_TRENDS=google/gemini-3-flash-preview
LLM_MODEL_ANALYST_DNA=deepseek/deepseek-v3.2
LLM_MODEL_STRATEGIST_BRIEF=google/gemini-3-flash-preview
```

---

## 8. Model Comparison Matrix — LLM

### Quality Rankings (OpenRouter community data, April 2026)

| Model | Marketing | Creative | Reasoning | Multilingual | JSON Output | Cost/1M out |
|-------|-----------|----------|-----------|-------------|-------------|-------------|
| Claude Opus 4.6 | #26 | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | $25 |
| Claude Sonnet 4.6 | **#6** | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $15 |
| Gemini 3 Flash | **#3** | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $3 |
| DeepSeek V3.2 | **#13** | ⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | $0.38 |
| Grok 4.20 | — | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | $6 |
| Qwen 3.6 Plus (free) | #28 | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | FREE |
| StepFun 3.5 Flash (free) | #45 | ⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐ | FREE |
| MiniMax M2.7 | **#17** | ⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐⭐⭐ | $1.20 |

### What "Marketing" rank means for Kova
OpenRouter ranks models by category based on community usage and ratings. #3 Marketing means Gemini 3 Flash is the 3rd most used/rated model for marketing tasks across all OpenRouter users. This is directly relevant — our agents generate marketing content.

---

## 9. Image Model Comparison

### Visual Quality Ranking for Social Media Content

| Model | Photo realism | Graphic design | Text in images | Brand consistency | Speed | Cost |
|-------|--------------|----------------|---------------|-------------------|-------|------|
| Gemini 3 Pro Image | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | 10-15s | $0.03-0.05 |
| GPT-5 Image | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 10-15s | $0.08-0.15 |
| Gemini 2.5 Flash Image | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 5-8s | $0.003-0.01 |
| Seedream 4.5 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ⭐⭐⭐ | 5-8s | $0.04 |
| Riverflow V2 Pro | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ | 8-12s | $0.15 |
| FLUX.1-schnell (current) | ⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | 3-5s | FREE |
| FLUX.1-dev | ⭐⭐⭐⭐ | ⭐⭐⭐ | ⭐⭐ | ⭐⭐ | 8-12s | ~$0.01 |

### Why Text-in-Image Matters for Social Media
- Promotional posts need price callouts ("KES 150 ONLY!")
- CTAs in images ("Shop Now", "Swipe Up")
- Brand name/logo placement
- Quote graphics (Twitter, LinkedIn)
- Sale/offer announcements

FLUX models are weak at text in images. Gemini and GPT-5 Image models excel. This is a significant quality differentiator.

### Carousel / Multi-Image Generation

For carousel posts (Instagram, LinkedIn), the image model needs to:
1. Generate multiple related images in a consistent style
2. Maintain brand color/style across images
3. Handle sequential storytelling (slide 1: problem, slide 2: solution, etc.)

**Best for carousels:**
- **Gemini 3 Pro Image** — Identity preservation across multiple images, style consistency
- **GPT-5 Image** — Strong instruction following for "generate image 3 of 5 in this series"
- **Riverflow V2 Pro** — Editing + enhancement per-slide

**Not suitable for carousels:**
- FLUX.1 models — No multi-image consistency, no editing

---

## 10. Upgrade Path

### Phase 1: Immediate (Development Quality)
**Goal:** Better dev experience, test production prompts properly.

```env
# Switch dev model from stepfun to qwen
LLM_MODEL_PREMIUM=qwen/qwen3.6-plus-preview:free
LLM_MODEL_WORKHORSE=qwen/qwen3.6-plus-preview:free
LLM_MODEL_FAST=stepfun/step-3.5-flash:free
```
**Cost:** $0
**Impact:** Noticeably better content quality in dev testing.

### Phase 2: Production Launch
**Goal:** Production-grade content quality with sustainable margins.

```env
LLM_MODEL_PREMIUM=anthropic/claude-sonnet-4.6
LLM_MODEL_WORKHORSE=google/gemini-3-flash-preview
LLM_MODEL_FAST=deepseek/deepseek-v3.2
```
**Cost:** ~$1-5/month per active user
**Impact:** User-facing content is genuinely good. Worth paying for.

### Phase 3: Image Quality Upgrade
**Goal:** Social media images with text rendering, brand consistency, editing.

- Add Gemini 2.5 Flash Image as standard tier (via OpenRouter)
- Add Gemini 3 Pro Image as premium tier
- Keep FLUX.1-schnell as free fallback
- Implement plan-based image tier routing

**Cost:** ~$0.01-0.05/image
**Impact:** Images go from "AI generated" to "professionally designed."

### Phase 4: Plan-Based Model Routing
**Goal:** Differentiate plan tiers through AI quality.

| Plan | LLM Premium | Image Model | Quality Level |
|------|-------------|-------------|---------------|
| Jipange (KES 299) | Gemini 3 Flash | FLUX.1-schnell (free) | Good |
| Kazi (KES 999) | Gemini 3 Flash | Gemini 2.5 Flash Image | Great |
| Biashara (KES 1,999) | Claude Sonnet 4.6 | Gemini 2.5 Flash Image | Excellent |
| Wakala (KES 2,999) | Claude Sonnet 4.6 | Gemini 3 Pro Image | Premium |

This creates genuine value differentiation between tiers — higher plans get measurably better content and images.

### Phase 5: OpenRouter Image Unification
**Goal:** Route ALL generation (text + image) through OpenRouter.

Update `media.py` to add OpenRouter as a provider alongside HuggingFace/Together/Pollinations. Single API key, unified billing, consistent fallback.

---

## Summary — The 5 Key Decisions

| Decision | Recommendation | Why |
|----------|---------------|-----|
| **Premium LLM** | Claude Sonnet 4.6 | Best creative writing, brand voice, multilingual — this IS the product |
| **Workhorse LLM** | Gemini 3 Flash Preview | #3 Marketing rank, best reasoning/dollar, 5x cheaper than Claude |
| **Fast LLM** | DeepSeek V3.2 | GPT-5 class at $0.38/1M — nearly free for classification tasks |
| **Standard Images** | Gemini 2.5 Flash Image (Nano Banana) | Text rendering + contextual understanding at $0.003-0.01/image |
| **Premium Images** | Gemini 3 Pro Image (Nano Banana Pro) | 4K output, identity preservation, localized edits at $0.03-0.05/image |

**Total production AI cost:** ~$1-5/month per active user. Margins stay above 80% at every plan tier.

---

*This research should be refreshed quarterly as model capabilities and pricing change rapidly. OpenRouter's model page (openrouter.ai/models) is the best live reference.*
