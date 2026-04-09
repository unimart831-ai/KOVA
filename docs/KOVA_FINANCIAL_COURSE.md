# Kova Agent — The Complete Financial Course

> **Purpose:** Understand EVERY cost Kova pays to exist and serve customers. Written so a 6-year-old could follow, but accurate enough to run the business.
>
> **Last updated:** April 9, 2026
> **Exchange rate:** 1 USD ≈ 142 KES (Kenyan Shillings)

---

## Table of Contents

1. [The Lemonade Stand — How Any Business Works](#chapter-1--the-lemonade-stand)
2. [Kova's "Ingredients" — Every Cost Explained](#chapter-2--kovas-ingredients)
3. [What Are Tokens? The Currency of AI](#chapter-3--what-are-tokens)
4. [How "Per 1M Tokens" Pricing Works](#chapter-4--how-per-1m-tokens-pricing-works)
5. [How Kova Consumes Tokens — Every Agent, Every Task](#chapter-5--how-kova-consumes-tokens)
6. [Model Routing — Why We Use Different AI Brains](#chapter-6--model-routing)
7. [The Fallback Chain — What Happens When AI Fails](#chapter-7--the-fallback-chain)
8. [Hosting — Keeping Kova Alive 24/7](#chapter-8--hosting)
9. [Third-Party Services — The Helpers](#chapter-9--third-party-services)
10. [Payment Processing — How Money Comes In](#chapter-10--payment-processing)
11. [Image Generation — Making Pictures With AI](#chapter-11--image-generation)
12. [The Full Cost Per Customer](#chapter-12--the-full-cost-per-customer)
13. [Revenue — What Customers Pay Us](#chapter-13--revenue)
14. [Profit Margins — What's Left After Costs](#chapter-14--profit-margins)
15. [Scaling Economics — How Costs Change With Growth](#chapter-15--scaling-economics)
16. [Break-Even — When Does Kova Stop Losing Money?](#chapter-16--break-even)
17. [Risk Scenarios — What Could Go Wrong](#chapter-17--risk-scenarios)
18. [The Cheat Sheet — Numbers You Must Know](#chapter-18--the-cheat-sheet)

---

# Chapter 1 — The Lemonade Stand

Before we talk about AI and servers and tokens, let's talk about a lemonade stand. Because Kova works the same way.

## The Simplest Business in the World

Imagine you sell lemonade on the street corner.

**To sell one cup, you need:**
- Lemons (ingredient cost)
- Sugar (ingredient cost)
- Water (almost free)
- A cup to put it in (packaging cost)
- A table to stand behind (infrastructure cost — like "rent")
- Electricity for your blender (utility cost)

**You sell one cup for KES 50.**

Now, if the lemons + sugar + cup cost you KES 20 per cup... you keep KES 30. That KES 30 is your **gross profit**. The percentage (30/50 = 60%) is your **gross margin**.

But wait — you also pay KES 500/month for the table rental, even if you sell zero cups. That's a **fixed cost** — it doesn't change whether you sell 1 cup or 1,000 cups.

The lemons and sugar? Those are **variable costs** — they go up when you sell more.

## How This Maps to Kova

| Lemonade Stand | Kova Equivalent | Type |
|---------------|-----------------|------|
| Lemons + sugar | AI/LLM tokens (the "brain" that writes content) | Variable — more customers = more AI calls |
| Cups | Image generation (pictures we create for posts) | Variable — more posts = more images |
| Table rental | Railway hosting (servers that keep Kova online 24/7) | Fixed — we pay even with zero customers |
| Blender electricity | Celery workers (background task processing) | Semi-fixed — grows slowly with usage |
| Cash register | M-Pesa / Stripe (payment processing) | Variable — per transaction |
| Water | Platform APIs (Facebook, Instagram, etc) | Free — social media APIs don't charge us |

**The key insight:** Kova's single biggest cost is AI tokens — the "lemons." Everything else is relatively cheap or free. Understanding tokens = understanding 70% of our costs.

---

# Chapter 2 — Kova's "Ingredients"

Every single shilling Kova spends falls into one of these 7 buckets:

### Bucket 1: AI/LLM Tokens (The Brain) — 🟥 BIGGEST COST
This is like the lemons. Every time Kova's AI writes a post, analyzes a trend, replies to a comment, or generates a daily brief — it costs tokens. More on this in Chapters 3-6.

### Bucket 2: Image Generation (The Pictures) — 🟧 SECOND BIGGEST
When Kova creates a social media post, it can also create an image. Free images (FLUX model) are free. Paid images (Gemini) cost ~$0.005 each (~KES 0.71 per image).

### Bucket 3: Hosting/Infrastructure (The Building) — 🟨 FIXED COST
Railway runs our servers. Think of it as the rent for Kova's "office." We pay about $20/month (~KES 2,840) whether we have 1 customer or 100 customers.

### Bucket 4: Payment Processing (The Cash Register) — 🟩 PER TRANSACTION
M-Pesa charges us **0%** per transaction (free!). Stripe (for international cards) charges **2.9% + $0.30** per transaction.

### Bucket 5: Email Delivery (The Mailman) — 🟦 ALMOST FREE
Resend gives us 100 free emails per day. That's 3,000/month. We only pay ($0.001/email) if we exceed that — which won't happen until ~1,000+ users.

### Bucket 6: Platform APIs (The Social Media Connections) — 🟩 FREE
Facebook, Instagram, X/Twitter, LinkedIn, TikTok, YouTube, Pinterest, Threads, Bluesky — all have free APIs. They want people to build on their platforms. We pay nothing to post content or read analytics.

### Bucket 7: Domain + SSL + Monitoring (The Address) — 🟩 NEARLY FREE
Railway includes SSL (the padlock in the browser). Domain costs ~KES 1,000/year. Sentry error monitoring has a free tier.

**The chart of what matters:**
```
AI/LLM Tokens:     ████████████████████████████████  65-80% of costs
Image Generation:   ████████████                      10-20% of costs
Railway Hosting:    ██████                            10-15% of costs
Everything Else:    ██                                < 5% of costs
```

---

# Chapter 3 — What Are Tokens?

This is the most important chapter. If you understand tokens, you understand Kova's economics.

## Tokens Are Pieces of Words

When you type a sentence and send it to an AI (like ChatGPT or Gemini), the AI doesn't read words. It reads **tokens** — small chunks of text.

**Think of it like this:** You have a sentence: "Kova helps African businesses grow."

A human reads 5 words. The AI reads it as tokens:

```
"Kova"    → 1 token
" helps"  → 1 token
" African"→ 1 token
" businesses" → 1 token  (or sometimes 2: " business" + "es")
" grow"   → 1 token
"."       → 1 token
```

**The rough rule:** 1 token ≈ ¾ of a word. Or flip it: **1,000 tokens ≈ 750 words**.

A typical social media post is about 200 words = ~270 tokens.
A typical AI prompt (the instructions we send) is about 500-3,000 tokens.

## Why Tokens Matter

AI companies charge **per token**. Every time Kova asks an AI to do something, we pay based on how many tokens we send IN (the question) and how many tokens come OUT (the answer).

**Analogy:** Imagine a very smart consultant. You pay them per word they read (input) and per word they write back (output). The more detailed your question and the longer their answer, the more you pay.

## Two Types of Tokens

### Input Tokens (What We Send)
This is the "question" — the instructions we give the AI. For Kova, this includes:
- The system prompt ("You are Kova's Create Agent. You write social media posts in the user's brand voice...")
- The user's brand info (tone, language, products, guardrails)
- The content seed ("Write a post about our new product launch")
- Any context (recent posts, performance data, trends)

**Input tokens are CHEAPER** — usually 3-10x cheaper than output tokens.

### Output Tokens (What We Get Back)
This is the "answer" — the content the AI generates. For Kova:
- The actual social media post text
- Hashtags and CTAs
- Platform-specific formatting
- JSON structure wrapping the content

**Output tokens are EXPENSIVE** — this is where most of the cost lives.

## A Real Example

When a Kova user submits a content seed "Announce our new shoe collection," here's what happens:

```
WE SEND (Input — ~2,500 tokens):
├── System prompt: "You are Kova's Create Agent..." (~800 tokens)
├── Brand DNA: tone, voice, language, products (~700 tokens)
├── Seed: "Announce our new shoe collection" (~10 tokens)
├── Platform rules: "For Instagram, max 2200 chars..." (~400 tokens)
├── Recent post examples: last 3 posts for voice matching (~500 tokens)
└── JSON format instructions: "Return a JSON with keys..." (~100 tokens)

WE RECEIVE (Output — ~3,000 tokens):
├── Instagram post: "👟 Step into the NEW COLLECTION..." (~300 tokens)
├── Twitter/X post: "New heat just dropped..." (~100 tokens)
├── Facebook post: "Exciting news!..." (~250 tokens)
├── TikTok caption: "POV: You see..." (~100 tokens)
├── Hashtags per platform: 4 sets (~200 tokens)
├── CTAs per platform: 4 suggestions (~200 tokens)
├── A/B variant: alternate version (~600 tokens)
└── JSON wrapper: braces, keys, formatting (~1,250 tokens)
```

**Total: ~5,500 tokens for one seed → multi-platform posts.**

---

# Chapter 4 — How "Per 1M Tokens" Pricing Works

## The Price Tag

AI companies quote prices like this:

> **Gemini 3 Flash: $0.50 input / $3.00 output per 1M tokens**

This means:
- Every **1,000,000 input tokens** we send costs us **$0.50** (KES 71)
- Every **1,000,000 output tokens** we receive costs us **$3.00** (KES 426)

## Why Per MILLION?

Because individual tokens are incredibly cheap. If they said "per token," the price would be:
- Input: $0.0000005 per token (half a millionth of a dollar)
- Output: $0.000003 per token (three millionths of a dollar)

Those numbers are impossible to think about. So they bundle them into millions — like how you buy rice per kilogram, not per grain.

## Let's Do Real Math

Remember: one seed generates ~2,500 input tokens and ~3,000 output tokens.

With **Gemini 3 Flash** ($0.50 / $3.00 per 1M):

```
Input cost:  2,500 tokens × ($0.50 / 1,000,000) = $0.00125  (KES 0.18)
Output cost: 3,000 tokens × ($3.00 / 1,000,000) = $0.009    (KES 1.28)
─────────────────────────────────────────────────────────────
Total cost for ONE seed → posts:                   $0.01025  (KES 1.46)
```

**One content seed costs us about KES 1.50.** That's less than a sweet in a kiosk.

A Starter user gets 5 seeds/month. So their Create Agent costs us:
```
5 seeds × KES 1.46 = KES 7.30 ($0.05)
```

A Growth user gets 30 seeds × 3 platforms:
```
30 seeds × KES 1.46 = KES 43.80 ($0.31) — just for content creation
```

## Comparing Different AI Models

Here's why model choice matters so much:

| Model | Input $ per 1M | Output $ per 1M | Cost for 1 Seed | Monthly Cost (30 seeds) |
|-------|---------------|-----------------|-----------------|------------------------|
| **DeepSeek V3.2** | $0.26 | $0.38 | **KES 0.25** | **KES 7.50** |
| **Gemini 3 Flash** | $0.50 | $3.00 | **KES 1.46** | **KES 43.80** |
| **GPT-4o-mini** | $0.15 | $0.60 | **KES 0.31** | **KES 9.30** |
| **Claude Sonnet 4.6** | $3.00 | $15.00 | **KES 7.52** | **KES 225.60** |
| **GPT-4 Turbo** | $10.00 | $30.00 | **KES 16.34** | **KES 490.20** |

See the range? The cheapest (DeepSeek) costs KES 0.25 per seed. The most expensive (GPT-4 Turbo) costs KES 16.34. That's a **65x difference** for the same job.

**This is why model selection is the most important financial decision in Kova.** The wrong model at the wrong plan tier can turn a profitable user into a loss.

### Why Output Tokens Are the Killer

Notice how Claude Sonnet charges $3/1M for input but $15/1M for output — that's **5x more** for output. And content creation is output-heavy (we send instructions, AI writes back long posts).

For a Create Agent call: ~55% of tokens are output. With Claude, ~80% of the COST is from output tokens.

**Rule of thumb:** When evaluating AI models for Kova, look at the OUTPUT price first. That's where the money goes.

---

# Chapter 5 — How Kova Consumes Tokens

Kova has 6 AI agents. Each does different tasks. Each task uses different amounts of tokens. Let's walk through every single one.

## Agent 1: Create Agent (The Writer) ✍️

**What it does:** Takes a content seed ("Announce our shoe sale") and writes platform-specific social media posts.

| Task | When it Fires | Input Tokens | Output Tokens | How Often (Starter) | How Often (Agency) |
|------|--------------|-------------|---------------|--------------------|--------------------|
| **Generate** (seed → posts) | User submits a seed | ~2,500 | ~3,000 | 5x/month | 200x/month |
| **Regenerate** (rewrite a post) | User clicks "regenerate" | ~2,000 | ~1,500 | ~2x/month | ~20x/month |
| **Repurpose** (post → other platforms) | User wants more platforms | ~2,500 | ~3,000 | rare | ~50x/month |
| **A/B Variant** (alternate version) | Per generation | ~2,000 | ~3,000 | 5x/month | 200x/month |

**This is the most expensive agent** because it generates the most output tokens (long post content).

**Monthly Create Agent token consumption:**
```
Starter:  ~5 generate × 5,500 tokens  = ~27,500 tokens   → costs ~KES 5 (Gemini Flash)
Growth:   ~30 generate × 5,500 tokens = ~165,000 tokens   → costs ~KES 30
Pro:      ~60 generate × 5,500 tokens = ~330,000 tokens   → costs ~KES 60
Agency:   ~200 generate × 5,500 tokens = ~1,100,000 tokens → costs ~KES 200
```

## Agent 2: Analyst Agent (The Numbers Guy) 📊

**What it does:** Extracts "Content DNA" from posts, predicts engagement, analyzes performance.

| Task | When it Fires | Input Tokens | Output Tokens | How Often |
|------|--------------|-------------|---------------|-----------|
| **Content DNA** (learn what works) | After each post is created | ~800 | ~500 | Per post created |
| **Predict** (will this post do well?) | After each post is created | ~600 | ~300 | Per post created |
| **Performance** (how did posts do?) | Daily brief generation | ~1,500 | ~1,000 | 30x/month (daily) |

**This agent is CHEAP** because:
1. Input and output tokens are small (analyzing data, not writing prose)
2. We use the Fast tier model (cheapest)
3. We batch multiple posts into one call

**Monthly Analyst token consumption:**
```
Starter:  ~15 posts × 2,200 tokens    = ~33,000 tokens   → costs ~KES 0.30 (DeepSeek)
Growth:   ~60 posts × 2,200 tokens    = ~132,000 tokens   → costs ~KES 1.20
Pro:      ~150 posts × 2,200 tokens   = ~330,000 tokens   → costs ~KES 3.00
Agency:   ~500 posts × 2,200 tokens   = ~1,100,000 tokens → costs ~KES 10.00
```

## Agent 3: Research Agent (The Scout) 🔍

**What it does:** Finds trending topics, generates content angles from trends.

| Task | When it Fires | Input Tokens | Output Tokens | How Often |
|------|--------------|-------------|---------------|-----------|
| **Discover trends** | Every 12 hours (automated) | ~1,000 | ~2,000 | 60x/month |
| **Generate angles** | Per trend discovered | ~1,500 | ~2,000 | 60x/month |

**Not available on Starter.** Only Growth and up.

**Monthly Research token consumption:**
```
Growth:   ~60 trends × 6,500 tokens   = ~390,000 tokens   → costs ~KES 2.80 (DeepSeek)
Pro:      ~60 trends × 6,500 tokens   = ~390,000 tokens   → costs ~KES 2.80
Agency:   ~60 trends × 6,500 tokens   = ~390,000 tokens   → costs ~KES 2.80
```

## Agent 4: Adapt Agent (The Scheduler) ⏰

**What it does:** Figures out the best time to post on each platform for each user.

| Task | When it Fires | Input Tokens | Output Tokens | How Often |
|------|--------------|-------------|---------------|-----------|
| **Schedule optimization** | Per post being scheduled | ~500 | ~300 | Per post |

**The cheapest agent.** Small tokens, simple task, runs on the Fast tier.

**Monthly Adapt token consumption:**
```
Growth:   ~60 posts × 800 tokens      = ~48,000 tokens    → costs ~KES 0.44 (DeepSeek)
Pro:      ~150 posts × 800 tokens     = ~120,000 tokens   → costs ~KES 1.10
Agency:   ~500 posts × 800 tokens     = ~400,000 tokens   → costs ~KES 3.64
```

## Agent 5: Engage Agent (The Community Manager) 💬

**What it does:** Monitors comments/DMs, generates smart replies in the user's brand voice.

| Task | When it Fires | Input Tokens | Output Tokens | How Often |
|------|--------------|-------------|---------------|-----------|
| **Analyze interactions** | Every 30 min (batch) | ~800 | ~500 | ~1,440x/month |
| **Generate replies** | Per interaction needing reply | ~1,500 | ~800 | 20-100x/month |

**Not available on Starter or Growth (basic).** Full access on Pro and Agency.

**Why it's expensive:** It runs frequently (every 30 minutes). But we use the Fast tier for analysis and batch multiple interactions into one call.

**Monthly Engage token consumption:**
```
Pro:      ~1,440 analyses + ~50 replies = ~2,020,000 tokens → costs ~KES 18.40 (DeepSeek for analysis, Gemini for replies)
Agency:   ~1,440 analyses + ~100 replies = ~2,220,000 tokens → costs ~KES 20.20
```

## Agent 6: Chief Strategist (The Boss) 🎯

**What it does:** Orchestrates all agents, generates daily briefs, makes autonomous content decisions.

| Task | When it Fires | Input Tokens | Output Tokens | How Often |
|------|--------------|-------------|---------------|-----------|
| **Strategy cycle** | Every 8 hours | ~3,000 | ~2,500 | 90x/month |
| **Daily brief** | Every morning | ~2,500 | ~2,000 | 30x/month |

**Only on Pro and Agency.**

**Monthly Strategist token consumption:**
```
Pro:      90 cycles + 30 briefs = ~660,000 tokens  → costs ~KES 4.80 (DeepSeek)
Agency:   90 cycles + 30 briefs = ~660,000 tokens  → costs ~KES 4.80
```

## Competitor Tracking 🕵️

**What it does:** Analyzes competitors' social media presence weekly.

| Task | When it Fires | Input Tokens | Output Tokens | How Often |
|------|--------------|-------------|---------------|-----------|
| **Full SWOT analysis** | Weekly | ~3,000 | ~4,000 | 4x/month |

**Only on Growth and up.**

```
Growth-Agency: 4 analyses × 7,000 tokens = 28,000 tokens → costs ~KES 0.25 (DeepSeek)
```

## The Grand Total per Plan

| Agent | Starter | Growth | Pro | Agency |
|-------|---------|--------|-----|--------|
| Create (Gemini Flash) | KES 5.00 | KES 30.00 | KES 60.00 | KES 200.00 |
| Analyst (DeepSeek) | KES 0.30 | KES 1.20 | KES 3.00 | KES 10.00 |
| Research (DeepSeek) | — | KES 2.80 | KES 2.80 | KES 2.80 |
| Adapt (DeepSeek) | — | KES 0.44 | KES 1.10 | KES 3.64 |
| Engage (mixed) | — | — | KES 18.40 | KES 20.20 |
| Strategist (DeepSeek) | — | — | KES 4.80 | KES 4.80 |
| Competitor (DeepSeek) | — | KES 0.25 | KES 0.25 | KES 0.25 |
| **TOTAL AI Cost** | **KES 5.30** | **KES 34.69** | **KES 90.35** | **KES 241.69** |
| **In USD** | **$0.04** | **$0.24** | **$0.64** | **$1.70** |

**Wait — that's way less than the $0.20-$4.60 in the Cost Analysis doc!**

That's because the Cost Analysis doc uses worst-case estimates (maximum usage per plan). The numbers above assume typical usage. Real costs will be somewhere in between.

**Realistic range per plan:**
| Plan | Low (light user) | High (power user) | Revenue |
|------|-----------------|-------------------|---------|
| Starter | KES 4 ($0.03) | KES 28 ($0.20) | KES 299 ($2.00) |
| Growth | KES 25 ($0.18) | KES 100 ($0.70) | KES 999 ($7.00) |
| Pro | KES 60 ($0.42) | KES 324 ($2.28) | KES 1,999 ($14.00) |
| Agency | KES 150 ($1.06) | KES 653 ($4.60) | KES 2,999 ($21.00) |

---

# Chapter 6 — Model Routing

## Why Not Use One AI Model for Everything?

Imagine you run a restaurant. Would you hire a Michelin-star chef to wash dishes? No — the chef creates the food, and a dishwasher handles the dishes. Each task needs the right person.

Kova does the same thing with AI models. We have 3 "tiers" of AI:

### Tier 1: Premium (The Chef) 👨‍🍳
**Model:** Gemini 3 Flash Preview
**Cost:** $0.50 input / $3.00 output per 1M tokens
**Used for:** Creating social media posts, writing engagement replies
**Why this model:** It's ranked #3 in Marketing on OpenRouter. It writes creative, platform-native content that follows brand voice instructions. It costs 5x LESS than Claude Sonnet while delivering 80% of the quality.

### Tier 2: Workhorse (The Analyst) 📋
**Model:** DeepSeek V3.2
**Cost:** $0.26 input / $0.38 output per 1M tokens
**Used for:** Research, strategy, competitor analysis, daily briefs
**Why this model:** GPT-5 class reasoning at the cheapest price available. Research and strategy tasks need comprehension and logic, not creative flair. DeepSeek handles this perfectly at nearly zero cost.

### Tier 3: Fast (The Calculator) 🔢
**Model:** DeepSeek V3.2 (same model, different purpose)
**Cost:** $0.26 input / $0.38 output per 1M tokens
**Used for:** Sentiment analysis, engagement scoring, content DNA extraction, scheduling
**Why this model:** These tasks are high-volume, low-stakes. We need quick, cheap, reliable JSON output. DeepSeek is perfect.

## How It Works in Code

In `config/settings/base.py`, we define which model handles which task:

```python
AGENT_MODELS = {
    # Premium tier — the content users actually see and publish
    "create.generate":     GEMINI_FLASH,   # Creates posts from seeds
    "create.regenerate":   GEMINI_FLASH,   # Rewrites posts
    "create.repurpose":    GEMINI_FLASH,   # Adapts to other platforms
    "engage.reply":        GEMINI_FLASH,   # Writes reply to comments/DMs

    # Workhorse tier — smart reasoning, users don't see raw output
    "research.trends":     DEEPSEEK,       # Discovers trending topics
    "research.angles":     DEEPSEEK,       # Turns trends into seed ideas
    "strategist.brief":    DEEPSEEK,       # Morning strategy brief
    "strategist.decide":   DEEPSEEK,       # Autonomous content decisions

    # Fast tier — classification, scoring, extraction (high volume)
    "engage.analyze":      DEEPSEEK,       # Sorts interactions by priority
    "analyst.performance": DEEPSEEK,       # How did posts perform?
    "analyst.content_dna": DEEPSEEK,       # Extract what works from posts
    "analyst.predict":     DEEPSEEK,       # Will this post do well?
    "adapt.schedule":      DEEPSEEK,       # What time should we post?
}
```

When any agent needs AI, it calls `get_model_for_task("create.generate")`, which returns the right model for that specific task. The agent never picks its own model — the routing system decides.

## Plan-Based Routing (Future)

Right now, all plans use the same models. But in the future:

```
Starter/Growth:  Gemini Flash (Premium) + DeepSeek (everything else)
Pro:             Gemini Flash OR Claude Sonnet (Premium) + DeepSeek
Agency:          Claude Sonnet (Premium) + DeepSeek
```

Agency users pay $21/month, so we can afford the more expensive Claude Sonnet ($15/1M output) for their content creation. Starter users at $2/month cannot afford Claude — but Gemini Flash still gives them excellent quality.

## The Cost Impact of Model Choice

Let's say a Growth user creates 30 posts/month. Here's what different Premium models would cost:

| Premium Model | Output Price/1M | 30 Posts Output Cost | Total With Input | % of Revenue |
|--------------|----------------|---------------------|-----------------|-------------|
| **DeepSeek V3.2** | $0.38 | $0.03 | $0.05 | 0.7% |
| **Gemini 3 Flash** | $3.00 | $0.27 | $0.31 | 4.4% |
| **GPT-4o-mini** | $0.60 | $0.05 | $0.07 | 1.0% |
| **Claude Sonnet 4.6** | $15.00 | $1.35 | $1.44 | 20.6% |
| **GPT-4 Turbo** | $30.00 | $2.70 | $2.85 | 40.7% |

DeepSeek uses 0.7% of the Growth user's KES 999 revenue. Claude uses 20.6%. GPT-4 Turbo would eat 40.7% of revenue — and that's JUST the Create Agent, not counting the 5 other agents.

**This is why model routing exists.** Putting Claude on a KES 299 Starter plan would cost MORE in AI than the customer pays.

---

# Chapter 7 — The Fallback Chain

## Why Free Models Fail

Kova currently uses **free AI models** during development (to save money while building). Free models have a problem: they sometimes return empty responses — the AI literally sends back nothing.

This happens because:
1. **Rate limits** — Free models have quotas. When exceeded, you get nothing.
2. **High demand** — When too many people use the free tier, some requests get dropped.
3. **Provider rotation** — Free models on OpenRouter route through different providers. Some providers have issues.

**Free models return empty ~5-10% of the time.** That means 1 in 10-20 AI calls might fail.

## The Safety Net

Kova doesn't just try one model and give up. It has a **fallback chain** — a ordered list of backup models to try:

```
Step 1: Try the primary model (e.g., nvidia/nemotron-3-super:free)
        ↓ empty or error?
Step 2: Try fallback #1 (openai/gpt-oss-120b:free)
        ↓ empty or error?
Step 3: Try fallback #2 (minimax/minimax-m2.5:free)
        ↓ empty or error?
Step 4: 🚨 PAID FALLBACK → deepseek/deepseek-v3.2 ($0.26/$0.38 per 1M)
        This one always works — we're paying for it.
```

**Why not go straight to paid?** Because free models work 90%+ of the time. If we skip free and always use paid, we'd spend money unnecessarily on 90% of calls that the free model would have handled fine.

**Why have a paid fallback at all?** Because a customer whose daily brief fails, or whose posts don't generate, will leave Kova. A few cents on the paid fallback is worth keeping the customer.

## The Cost of Fallbacks

In development (using free models with paid fallback):
```
90% of calls:  Free models succeed     → cost: $0
5% of calls:   Free fallbacks succeed  → cost: $0
5% of calls:   Paid fallback fires     → cost: ~$0.002 per call
```

Average cost per call: ~$0.0001 (effectively free, with paid insurance).

In production (using Gemini Flash + DeepSeek):
```
98% of calls: Primary model succeeds   → cost: as quoted
2% of calls:  Retry or fallback        → cost: same or slightly more
```

Paid models are much more reliable — the fallback chain rarely activates.

---

# Chapter 8 — Hosting

## What "Hosting" Means

When you open kovaagent.com in your browser, your computer sends a message across the internet to **a computer that is running Kova's code 24/7**. That computer is called a **server**.

We don't own a physical server. We rent one from **Railway** — a cloud hosting company. They manage the physical computers, the power, the internet connection, the security. We just upload our code and they run it.

## What Kova Runs On Railway

Kova isn't just one program. It's 5 services working together:

### Service 1: Web Server (Gunicorn) 🌐
**What it does:** Handles every webpage request. When you load the dashboard, submit a seed, check analytics — this is the service responding.
**Analogy:** The waiter in a restaurant. Takes your order (HTTP request), brings it to the kitchen (Django), serves the food (HTML response).
**Cost:** ~$6.56/month (0.2 CPU + 256 MB RAM)

### Service 2: Worker (Celery) ⚙️
**What it does:** Runs background tasks. AI content generation, posting to social media, analyzing engagement, fetching trends. All the heavy work that shouldn't block the web server.
**Analogy:** The kitchen. Does the actual cooking. You don't wait at the counter while they cook — the waiter (web server) takes your order and the kitchen works in the background.
**Cost:** ~$5.00/month (0.15 CPU + 200 MB RAM)

### Service 3: Beat (Celery Beat) ⏰
**What it does:** The scheduler. Tells the Worker "run the Engage Agent analysis now," "send the morning brief now," "check for new trends now." It's the clock that triggers all automated tasks.
**Analogy:** The restaurant manager who tells the kitchen "start prep at 6 AM, dinner service at 7 PM." Without the manager, the kitchen wouldn't know when to start.
**Cost:** ~$1.64/month (0.05 CPU + 64 MB RAM)

### Service 4: PostgreSQL Database 🗄️
**What it does:** Stores ALL of Kova's data. Users, posts, content seeds, analytics, billing records, agent actions, brand settings — everything.
**Analogy:** The filing cabinet. Every order, every recipe, every customer record goes here. Without it, Kova would forget everything every time it restarts.
**Cost:** ~$4.56/month (0.1 CPU + 256 MB RAM)

### Service 5: Redis 🔴
**What it does:** Two jobs:
1. **Message broker** — passes tasks from the Web Server to the Worker ("hey, generate content for this seed")
2. **Cache** — stores frequently accessed data in memory for speed (like plan limits, LLM config)
**Analogy:** The order ticket system. The waiter writes the order on a ticket (Redis), clips it on the line, the kitchen picks it up. Without it, waiter and kitchen can't communicate.
**Cost:** ~$1.64/month (0.05 CPU + 64 MB RAM)

## Railway Pricing Explained

Railway charges for two things: **CPU time** and **RAM time**.

| Resource | Price |
|----------|-------|
| 1 vCPU (1 computer brain) | $20/month |
| 1 GB RAM (1 gigabyte of memory) | $10/month |
| Network (data going out to users) | $0.05 per GB |
| Disk storage | $0.15 per GB/month |

**But we don't use full CPUs.** Kova is lightweight. We use fractions:

```
Web:    0.2 CPU ($4.00) + 0.25 GB RAM ($2.56) = $6.56
Worker: 0.15 CPU ($3.00) + 0.2 GB RAM ($2.00) = $5.00
Beat:   0.05 CPU ($1.00) + 0.06 GB RAM ($0.64) = $1.64
Postgres: 0.1 CPU ($2.00) + 0.25 GB RAM ($2.56) = $4.56
Redis:  0.05 CPU ($1.00) + 0.06 GB RAM ($0.64) = $1.64

TOTAL: ~$19.80/month (KES 2,812)
```

Railway's Hobby plan is $5/month with a $5 usage credit. So our bill would be about **$20/month** total.

## The Magic: Infrastructure Cost Per User SHRINKS

This is key. Railway costs are mostly **fixed**. Whether you have 1 user or 100 users, the servers still need to run. But as you get more users, the cost per user drops:

```
  10 users: $20 hosting ÷ 10  = $2.00/user    (KES 284 per user)
  50 users: $25 hosting ÷ 50  = $0.50/user    (KES 71 per user)
 100 users: $30 hosting ÷ 100 = $0.30/user    (KES 42.60 per user)
 500 users: $50 hosting ÷ 500 = $0.10/user    (KES 14.20 per user)
1000 users: $80 hosting ÷ 1000= $0.08/user    (KES 11.36 per user)
```

At 10 users, hosting is KES 284 per user — almost as much as a Starter pays! At 500 users, it's KES 14 — insignificant.

**This is called "economies of scale."** Fixed costs get spread thinner as volume grows. This also means: the first 10 users are expensive (you're covering the full hosting bill), but every user after that adds almost pure profit.

## Why Railway and Not Others?

| Option | Monthly Cost | Pros | Cons |
|--------|-------------|------|------|
| **Railway** | ~$20 | Easy deploy, auto-scaling, managed Postgres/Redis, free SSL | Small company, less enterprise features |
| **Hetzner VPS** | ~$5-10 | Cheapest, full control | You manage everything (database, SSL, updates, security) |
| **DigitalOcean** | ~$15-30 | Reliable, good docs | More setup than Railway |
| **AWS/GCP** | ~$30-100+ | Enterprise grade, infinite scale | Complex, expensive, overkill for our stage |
| **Heroku** | ~$25+ | Similar to Railway | More expensive, fewer features at our tier |

Railway is the sweet spot: easy enough to deploy in minutes, cheap enough for a startup, and scales with us.

---

# Chapter 9 — Third-Party Services

These are the external tools and APIs Kova depends on.

## OpenRouter (LLM Gateway) — Cost: Per token (see Chapter 4)

**What it is:** A gateway (middleman) that gives us access to 665+ AI models from different companies (OpenAI, Google, Anthropic, DeepSeek, etc.) through ONE API.

**Why not go directly to Google or OpenAI?** Three reasons:
1. **One integration, many models.** Instead of writing separate code for each AI provider, we write to OpenRouter once and can switch models with a config change.
2. **Free model access.** OpenRouter offers free tiers of certain models (subsidized by the model providers for exposure).
3. **Fallback routing.** If one provider is down, OpenRouter routes to another provider hosting the same model.

**Cost model:** Pay per token used. No minimum. No monthly fee. Just pay for what you consume. If we use zero tokens, we pay zero dollars.

## Social Media Platform APIs — Cost: FREE 🎉

The 9 platforms Kova connects to all have **free APIs**:

| Platform | API | Rate Limits | What Kova Does |
|----------|-----|-------------|----------------|
| Facebook | Graph API | 200 calls/hour per user | Post, read analytics, read comments |
| Instagram | Graph API | 200 calls/hour per user | Post, read insights, read comments |
| X (Twitter) | API v2 (Basic) | 100 posts/month, 10K reads | Post, read analytics, read mentions |
| LinkedIn | Marketing API | 100 calls/day | Post, read analytics |
| TikTok | Content Posting API | Varies | Post videos, read analytics |
| YouTube | Data API v3 | 10,000 units/day | Upload, read analytics |
| Pinterest | API v5 | 1,000 calls/day | Pin, read analytics |
| Threads | API | Similar to Instagram | Post, read |
| Bluesky | AT Protocol | Fair use | Post, read |

**Key insight:** These companies WANT developers building on their platforms. It increases their user engagement. So the APIs are free.

**The only cost risk:** X (Twitter) could start charging for their API (they've done it before). If so, we'd need X's Basic plan ($100/month) split across all users. Even at 100 users, that's $1/user/month — manageable.

## Safaricom Daraja (M-Pesa) — Cost: FREE 🎉

**What it is:** The API that lets Kova trigger M-Pesa STK Push payments. When a user clicks "Subscribe," their phone gets a popup asking to enter their M-Pesa PIN.

**Cost:** FREE. Specifically:
- API access: Free (apply at developer.safaricom.co.ke)
- Per-transaction fee: **0% for Paybill** (business receives 100% of payment)
- Settlement: Next business day to your bank account

**Why this is incredible:** Stripe charges 2.9% + $0.30 per transaction. On a KES 299 payment via Stripe, you'd lose KES 72 (24%!). With M-Pesa Paybill, you keep all KES 299.

**This is Kova's payment superpower in Kenya.**

## Resend (Email Service) — Cost: FREE (for now)

**What it is:** Sends transactional emails — welcome emails, password resets, daily briefs, payment confirmations.

**Free tier:** 100 emails/day = 3,000/month. More than enough until ~1,000 users.
**Paid:** $20/month for 50,000 emails when we outgrow free tier.

**Alternative:** AWS SES costs $0.10 per 1,000 emails ($0.0001 per email). At 1,000 users sending 5 emails/month each = 5,000 emails = $0.50/month. Nearly free.

## Sentry (Error Monitoring) — Cost: FREE

**What it is:** Catches bugs. When something breaks in production, Sentry captures the error with full context (which user, what they were doing, the stack trace).

**Free tier:** 5,000 error events/month. If your app is well-built, you won't hit this.
**Paid:** $26/month for Team plan (if we need more).

## R2 Storage (Cloudflare) — Cost: FREE (for now)

**What it is:** Stores uploaded files — user avatars, post media, generated images.
**Free tier:** 10 GB storage + 10 million reads/month. Enough for thousands of users.

## GitHub — Cost: FREE

**What it is:** Where our code lives. Private repository, version control, CI/CD.
**Free tier:** Unlimited private repos. Free for small teams.

---

# Chapter 10 — Payment Processing

## How Money Reaches Kova

There are two paths money can travel to reach us:

### Path 1: M-Pesa (Kenya) 🇰🇪

```
Customer clicks "Subscribe"
    ↓
Kova calls Safaricom Daraja API (STK Push)
    ↓
Customer's phone shows M-Pesa popup: "Pay KES 999 to Kova Agent?"
    ↓
Customer enters their M-Pesa PIN
    ↓
Safaricom sends callback to Kova: "Payment successful!"
    ↓
Kova activates the plan instantly
    ↓
KES 999 lands in Kova's Paybill → settles to bank account next business day
```

**What Kova pays:** NOTHING. Zero fees.
**What customer pays:** Their normal M-Pesa withdrawal fee (KES 0 for Paybill payments in most cases).

### Path 2: Stripe (International) 🌍

```
Customer clicks "Subscribe with Card"
    ↓
Redirected to Stripe Checkout page
    ↓
Customer enters card details
    ↓
Stripe charges the card
    ↓
Stripe sends webhook to Kova: "Payment successful!"
    ↓
Kova activates the plan
    ↓
Money arrives in Kova's Stripe account (minus fees)
    ↓
Stripe pays out to bank account (2-7 days)
```

**What Kova pays:**
| Payment Amount | Stripe Fee (2.9% + $0.30) | Kova Receives | Lost to Fees |
|---------------|--------------------------|---------------|-------------|
| $2 (Starter) | $0.36 | $1.64 | **18%!** |
| $7 (Growth) | $0.50 | $6.50 | 7% |
| $14 (Pro) | $0.71 | $13.29 | 5% |
| $21 (Agency) | $0.91 | $20.09 | 4% |

**Notice:** Stripe's $0.30 flat fee DESTROYS small transactions. On a $2 Starter payment, we lose 18% to Stripe! On a $21 Agency payment, we only lose 4%.

**This is why M-Pesa matters so much.** For Kenyan users (our primary market), we keep 100% of every payment. Stripe is only for international (non-M-Pesa) users.

## Monthly Payment Cost Projection

Assuming 80% M-Pesa (Kenya) and 20% Stripe (international):

| Users | M-Pesa Revenue | Stripe Revenue | Stripe Fees | **Net Payment Cost** | % of Total Revenue |
|-------|---------------|---------------|-------------|---------------------|--------------------|
| 100 | $310 (80%) | $77 (20%) | ~$5.50 | **$5.50** | 1.4% |
| 500 | $1,549 | $387 | ~$27 | **$27** | 1.4% |
| 1,000 | $3,098 | $775 | ~$54 | **$54** | 1.4% |

Payment processing is a small cost — 1-2% of revenue — especially with M-Pesa handling 80% for free.

---

# Chapter 11 — Image Generation

## How AI Makes Pictures

When the Create Agent generates a social media post, it can also create an image to go with it. This requires a different type of AI — an image generation model.

**Text GenAI:** Reads words → writes words (tokens in, tokens out)
**Image GenAI:** Reads words → creates a picture (text description in, image out)

## The Models We Use

### FLUX.1-schnell (HuggingFace) — FREE 🎉

**Used for:** Starter plan (included free)
**How it works:** We send a text description to HuggingFace's free API, they generate an image, we download it.
**Quality:** Good — nice visuals, decent composition. But can't render text in images (words in the image come out garbled).
**Speed:** ~5-10 seconds per image.
**Cost:** $0. HuggingFace provides this free through their Inference API.
**Limit:** Rate-limited. ~100 images/day across all users.

### Gemini 2.5 Flash Image (Google) — ~$0.005/image

**Used for:** Growth and Pro plans
**How it works:** We send a prompt to Google's Gemini API with image generation enabled.
**Quality:** Great — can render text in images, supports editing existing images, good at brand consistency.
**Speed:** ~3-5 seconds per image.
**Cost:** About KES 0.71 per image.

### Gemini 3 Pro Image (Google) — ~$0.04/image

**Used for:** Agency plan (premium quality option)
**Quality:** Excellent — 4K resolution, identity preservation (same character across images), best text rendering.
**Speed:** ~5-8 seconds per image.
**Cost:** About KES 5.68 per image.

## Monthly Image Costs

| Plan | Posts/mo | Image Model | Cost per Image | Monthly Image Cost |
|------|----------|-------------|---------------|-------------------|
| **Starter** | 15 | FLUX (free) | KES 0 | **KES 0** |
| **Growth** | 60 | Gemini 2.5 Flash | KES 0.71 | **KES 42.60** ($0.30) |
| **Pro** | 150 | Gemini 2.5 Flash | KES 0.71 | **KES 106.50** ($0.75) |
| **Agency** | 500 | Gemini 2.5 Flash (default) | KES 0.71 | **KES 355** ($2.50) |

**Note:** Not every post needs an image. Some posts are text-only (quotes, questions, announcements). Realistic image usage is probably 60-70% of posts. This would lower costs by ~30%.

---

# Chapter 12 — The Full Cost Per Customer

Now we put it all together. Every cost bucket, per plan, per month.

## Scenario: 100 Active Users (Budget-Smart Stack)

| Cost Item | Starter ($2.00) | Growth ($7.00) | Pro ($14.00) | Agency ($21.00) |
|-----------|-----------------|----------------|--------------|-----------------|
| **AI/LLM tokens** | $0.05 - $0.20 | $0.24 - $0.70 | $0.64 - $2.28 | $1.70 - $4.60 |
| **Image generation** | $0.00 | $0.21 - $0.30 | $0.53 - $0.75 | $1.75 - $2.50 |
| **Hosting (÷ 100 users)** | $0.30 | $0.30 | $0.30 | $0.30 |
| **Email** | $0.00 | $0.00 | $0.00 | $0.00 |
| **M-Pesa / Stripe** | $0.00 - $0.36 | $0.00 - $0.50 | $0.00 - $0.71 | $0.00 - $0.91 |
| **Platform APIs** | $0.00 | $0.00 | $0.00 | $0.00 |
| **Monitoring** | $0.00 | $0.00 | $0.00 | $0.00 |
| | | | | |
| **Total Cost (typical)** | **$0.35** | **$0.75** | **$1.47** | **$3.75** |
| **Total Cost (max)** | **$0.86** | **$1.80** | **$4.04** | **$8.31** |
| **Revenue** | **$2.00** | **$7.00** | **$14.00** | **$21.00** |
| **Profit (typical)** | **$1.65** | **$6.25** | **$12.53** | **$17.25** |
| **Margin (typical)** | **83%** | **89%** | **89%** | **82%** |
| **Profit (max user)** | **$1.14** | **$5.20** | **$9.96** | **$12.69** |
| **Margin (max user)** | **57%** | **74%** | **71%** | **60%** |

**Key takeaway:** Even a power user maxing out their plan is profitable. The plan limits (15 posts for Starter, 60 for Growth, etc.) naturally cap how much AI they can consume.

## What This Means in KES

For a typical Growth user:

```
They pay:         KES 999
AI costs us:      KES 34 - 100
Images cost us:   KES 30 - 43
Hosting share:    KES 43
Payment:          KES 0 (M-Pesa)
─────────────────────────────
Total cost:       KES 107 - 186
We keep:          KES 813 - 892

That's KES 800+ profit from ONE Growth user.
```

---

# Chapter 13 — Revenue

## What Customers Pay

| Plan | Swahili Name | KES/month | USD/month | What They Get |
|------|-------------|-----------|-----------|---------------|
| **Starter** | Jipange | 299 | ~$2 | 1 account, 15 posts, 5 seeds, 2 agents (Create + Analyst) |
| **Growth** | Kazi | 999 | ~$7 | 3 accounts, 60 posts, 30 seeds, 5 agents + images + competitors |
| **Pro** | Biashara | 1,999 | ~$14 | 10 accounts, 150 posts, 60 seeds, all 6 agents + team |
| **Agency** | Wakala | 2,999 | ~$21 | 25 accounts, unlimited, all agents + 25 team + auto-approve |

## Expected Plan Distribution

Based on typical SaaS in emerging markets:

```
Starter: 45% of users  (cheapest plan, biggest bucket)
Growth:  30% of users  (best value, sweet spot)
Pro:     15% of users  (serious businesses)
Agency:  10% of users  (agencies, brands)
```

## Blended Average Revenue Per User (ARPU)

```
ARPU = (45% × $2) + (30% × $7) + (15% × $14) + (10% × $21)
     = $0.90 + $2.10 + $2.10 + $2.10
     = $7.20/user/month

In KES: KES 1,022/user/month
```

But wait — the distribution might not look like this. If 80% land on Starter:

```
ARPU = (80% × $2) + (10% × $7) + (5% × $14) + (5% × $21)
     = $1.60 + $0.70 + $0.70 + $1.05
     = $4.05/user/month (KES 575)
```

**Strategy implication:** Kova should actively push users from Starter to Growth. The leap from $2 → $7 is a 3.5x revenue increase. Feature gating (no images, no competitors, limited seeds on Starter) creates this natural upgrade pressure.

## Lifetime Value (LTV)

LTV = ARPU × Average Months Before Churn

| Churn Rate | Avg Months | LTV (at $7.20 ARPU) | LTV in KES |
|-----------|-----------|---------------------|-----------|
| 5%/month | 20 months | $144 | KES 20,448 |
| 10%/month | 10 months | $72 | KES 10,224 |
| 15%/month | 6.7 months | $48 | KES 6,816 |
| 20%/month | 5 months | $36 | KES 5,112 |

**Target: Keep monthly churn under 10%.** That gives each user a lifetime value of ~KES 10,000.

---

# Chapter 14 — Profit Margins

## What is Margin?

**Gross margin** tells you: for every KES 100 a customer pays, how much do you keep after covering the direct costs to serve that customer?

```
Gross margin = (Revenue - Cost to Serve) ÷ Revenue × 100%
```

If a Growth user pays KES 999 and costs KES 150 to serve:
```
Margin = (999 - 150) ÷ 999 × 100% = 85%
```

You keep 85 shillings out of every 100 the customer pays. The other 15 goes to AI, hosting, images.

## Kova's Margins by Plan

### With Budget-Smart Stack (Gemini Flash + DeepSeek)

| Plan | Revenue | Typical Cost | Gross Profit | Margin |
|------|---------|-------------|-------------|--------|
| Starter | $2.00 | $0.35 | $1.65 | **83%** |
| Growth | $7.00 | $0.75 | $6.25 | **89%** |
| Pro | $14.00 | $1.47 | $12.53 | **89%** |
| Agency | $21.00 | $3.75 | $17.25 | **82%** |

**These are excellent SaaS margins.** For comparison:
- Hootsuite's gross margin: ~75%
- Buffer's gross margin: ~80%
- Mailchimp's gross margin: ~70-75%
- Kova's gross margin: **82-89%** ← Better than all of them

The secret? M-Pesa (0% fees) + cheap AI models + Railway (cheap hosting).

### If We Used Claude Sonnet for Everyone

| Plan | Revenue | Cost w/ Claude | Gross Profit | Margin |
|------|---------|---------------|-------------|--------|
| Starter | $2.00 | $1.24 | $0.76 | **38%** |
| Growth | $7.00 | $3.72 | $3.28 | **47%** |
| Pro | $14.00 | $11.25 | $2.75 | **20%** |
| Agency | $21.00 | $22.24 | **-$1.24** | **-6% LOSS** |

**See the difference?** Claude's $15/1M output tokens turns Agency from 82% profit into a loss. This is why model routing matters — it's the difference between a thriving business and bankruptcy.

## Contribution vs. True Profit

**Gross profit** only covers variable costs (AI, images, payment fees). You also have fixed costs:

```
Fixed costs (Monthly):
├── Railway hosting:     KES 2,840  ($20)
├── Domain:              KES 83     ($0.58) — annual ÷ 12
├── CEO time:            KES 30,000 ($211) — minimum
└── Total fixed:         KES 32,923 ($232)
```

**True monthly profit** = Total gross profit from all users − Fixed costs

At 100 users (45/30/15/10 distribution):
```
Total gross profit: 45×$1.65 + 30×$6.25 + 15×$12.53 + 10×$17.25
                  = $74 + $188 + $188 + $173
                  = $623/month (KES 88,466)

Minus fixed costs: $623 − $232 = $391/month (KES 55,522)
```

That's KES 55,522 true profit at 100 users. Enough for a modest salary.

---

# Chapter 15 — Scaling Economics

## How Costs Behave as Kova Grows

### Variable Costs (Grow WITH users)
- **AI tokens:** Every new user adds ~$0.35 - $3.75/month in AI cost
- **Images:** Every new user adds ~$0 - $2.50/month in image cost
- **Payment fees:** Each Stripe payment loses 2.9% + $0.30

These scale linearly — 2x users = 2x variable costs.

### Fixed Costs (Stay FLAT regardless of users)
- **Railway hosting:** ~$20/month for the first 100-200 users
- **Domain:** ~$12/year
- **Sentry:** Free until 5,000 errors/month

### Semi-Fixed Costs (Grow SLOWLY, in steps)
- **Railway (at scale):** When we hit ~200 concurrent users, we need to scale up the web server and worker. But it's not linear — doubling users might only add $5-10/month.
- **Email:** Free until ~1,000 users, then $20/month.

## The Economics at Different Scales

| Users | Revenue/mo | Variable Costs | Fixed Costs | Profit | Margin |
|-------|-----------|---------------|-------------|--------|--------|
| **10** | $72 | $15 | $232 | **-$175** (loss) | — |
| **50** | $360 | $75 | $232 | **+$53** | 15% |
| **100** | $720 | $150 | $235 | **+$335** | 47% |
| **500** | $3,600 | $750 | $265 | **+$2,585** | 72% |
| **1,000** | $7,200 | $1,500 | $300 | **+$5,400** | 75% |
| **5,000** | $36,000 | $7,500 | $450 | **+$28,050** | 78% |
| **10,000** | $72,000 | $15,000 | $650 | **+$56,350** | 78% |

**The pattern:** At small scale (10 users), fixed costs dominate and we lose money. As users grow, fixed costs become a smaller percentage and margins expand from 15% → 78%.

## The Beautiful Math of SaaS

At 10,000 users:
- Revenue: $72,000/month = **KES 10.2 million/month**
- Costs: $15,650/month = **KES 2.2 million/month**
- Profit: $56,350/month = **KES 8 million/month**

**KES 8 million per month in profit.** From a product that started with a $20/month server and free AI models.

This is why SaaS businesses are valuable — the margins get better over time, not worse.

---

# Chapter 16 — Break-Even

## What is Break-Even?

Break-even is the point where revenue exactly equals costs. Below this point, you're losing money. Above it, you're making money.

## Break-Even Without Salary (Operations Only)

```
Fixed costs (operations): $21/month (Railway + domain)
Average gross profit per user: $6.25 (at blended ARPU)
Contribution margin per user: $6.25 - $1.32 variable cost = $4.93

Break-even = Fixed costs ÷ Contribution margin
           = $21 ÷ $4.93
           = ~5 users
```

**Kova breaks even on operational costs at just 5 paying users.** This is because Railway is cheap and AI tokens are cheap.

## Break-Even Including Your Salary

This is the real question: when does Kova make enough to pay you?

| Salary Target | KES/month | USD/month | Users Needed |
|--------------|-----------|-----------|-------------|
| Survival (food + rent) | KES 30,000 | $211 | ~48 users |
| Comfortable | KES 60,000 | $423 | ~91 users |
| Good salary | KES 100,000 | $704 | ~148 users |
| Great salary | KES 200,000 | $1,408 | ~331 users |
| Executive level | KES 500,000 | $3,521 | ~720 users |

**At 48 users, Kova pays you a survival salary.** At 150 users, you're earning a good salary. At 330 users, you're very comfortable. Every user after that is building wealth.

## Timeline (Conservative Growth)

| Month | New Users | Total Users | Revenue | Costs | Profit | Cumulative |
|-------|----------|-------------|---------|-------|--------|-----------|
| 1 | 10 | 10 | $72 | $247 | -$175 | -$175 |
| 2 | 15 | 22 | $158 | $261 | -$103 | -$278 |
| 3 | 20 | 37 | $266 | $280 | -$14 | -$292 |
| **4** | 25 | **55** | $396 | $300 | **+$96** | -$196 |
| 5 | 30 | 75 | $540 | $322 | +$218 | +$22 |
| 6 | 35 | 97 | $698 | $347 | +$351 | +$373 |
| 8 | 40 | 145 | $1,044 | $400 | +$644 | +$1,661 |
| 10 | 45 | 195 | $1,404 | $460 | +$944 | +$3,549 |
| 12 | 50 | 250 | $1,800 | $524 | +$1,276 | +$6,101 |

**Month 4:** Kova turns profitable (covers operations).
**Month 5:** Covers operations + starts building salary.
**Month 10:** Generating ~KES 134,000/month profit. Good salary territory.
**Month 12:** KES 181,000/month profit. Cumulative: KES 866,000 in the bank.

(Assumptions: 10% monthly churn, growing user acquisition)

---

# Chapter 17 — Risk Scenarios

## Risk 1: AI Models Get More Expensive

**What could happen:** Google doubles Gemini Flash prices. DeepSeek raises their rates.

**Impact:**
```
Current AI cost per Growth user:  ~$0.50/month
If doubled:                       ~$1.00/month
Impact on Growth margin:          89% → 86%
```

**Not catastrophic.** AI costs are small relative to revenue. Even a 2x increase barely dents margins.

**Mitigation:** There are 665+ models on OpenRouter. If Gemini doubles, we switch to the next best option. Competition keeps prices trending DOWN, not up. Prices have dropped 95% in the last 2 years.

## Risk 2: Most Users Stay on Starter Plan

**What could happen:** 80% of users stay on KES 299 instead of upgrading.

**Impact:**
```
Normal ARPU:     $7.20/user
Worst case ARPU: $4.05/user (80% on Starter)
Users for KES 100K salary: 148 → 264 users
```

**It requires ~2x more users**, but the business still works because Starter is profitable (83% margin).

**Mitigation:** Feature gating. Starter intentionally limits (no images, no competitors, 5 seeds, 1 account) to create upgrade pressure. Once users see the value, they move to Growth.

## Risk 3: Railway Goes Down or Gets Expensive

**What could happen:** Railway doubles prices or has extended downtime.

**Impact of 2x Railway cost:**
```
Current:  $20/month
Doubled:  $40/month
At 100 users: extra $0.20/user. Negligible.
```

**Mitigation:** Kova's code is standard Django. We can deploy anywhere in hours:
- Hetzner VPS: $5-15/month (cheapest)
- DigitalOcean: $15-30/month
- Fly.io: $10-25/month
- We're not locked into Railway.

## Risk 4: A Free AI Model We Depend On Dies

**Already happened!** In April 2026, all 3 of our primary free models went dead (Llama 4 Maverick, Qwen 3.6 Plus, Step 3.5 Flash). All returned 404 errors within the same week.

**What we did:** Switched to 3 new free models within hours (Nemotron, GPT-OSS, Nemotron Nano). The paid fallback (DeepSeek) caught any failed calls during the transition.

**Lesson:** Free models are unreliable. The fallback chain is essential. In production, we'll use paid models (Gemini Flash + DeepSeek) which have 99%+ uptime.

## Risk 5: A Social Media Platform Changes Their API

**What could happen:** Facebook restricts their API, X starts charging.

**Impact:** One platform out of nine becomes unavailable or expensive.

**Mitigation:** Kova supports 9 platforms. No single platform is critical. If Facebook locks down, users still have 8 other options. Our 9-platform strategy is deliberate diversification.

## Risk 6: Currency Devaluation (KES Weakens)

**What could happen:** KES drops from 142/USD to 200/USD ← this has been real.

**Impact:** Our costs are in USD (AI, hosting) but revenue is in KES.

```
At 142 KES/USD: Growth plan KES 999 = $7.03 revenue, $0.75 cost = $6.28 profit
At 200 KES/USD: Growth plan KES 999 = $5.00 revenue, $0.75 cost = $4.25 profit
```

**Profit drops 32%**, but Growth is still profitable at $4.25.

**Mitigation:** 
1. USD pricing for international users (Stripe) provides a hedge
2. If KES drops significantly, raise prices (KES 999 → KES 1,299)
3. Our costs are already so low that we have massive buffer

---

# Chapter 18 — The Cheat Sheet

## The 10 Numbers You Must Know

| # | Metric | Value | Why It Matters |
|---|--------|-------|---------------|
| 1 | **Average cost to serve 1 user/month** | **$0.75 - $1.50** (KES 107-213) | This is your "ingredient cost" |
| 2 | **Average revenue per user/month** | **$7.20** (KES 1,022) — at 45/30/15/10 split | This is what each customer brings in |
| 3 | **Gross margin** | **82-89%** | For every KES 100 earned, KES 82-89 is profit |
| 4 | **Break-even (operations)** | **5 users** | When Kova covers its own server costs |
| 5 | **Break-even (with salary)** | **48-150 users** | When Kova pays you KES 30K-100K |
| 6 | **Biggest cost** | **AI tokens (LLM)** | 65-80% of variable costs |
| 7 | **Key financial lever** | **AI model choice** | Wrong model: -6% margin. Right model: +89% margin |
| 8 | **M-Pesa advantage** | **0% transaction fee** | Stripe would eat 4-18% of every payment |
| 9 | **Hosting cost per user at scale** | **< $0.10** (KES 14) | Infrastructure becomes negligible |
| 10 | **Token output price matters most** | **$0.38 (DeepSeek) vs $15 (Claude)** | 40x difference in just the output cost |

## The 5 Rules of Kova's Financial Health

### Rule 1: Never Put an Expensive Model on a Cheap Plan
Claude Sonnet ($15/1M output) on a KES 299 Starter plan = guaranteed loss. Gemini Flash ($3/1M output) is 80% as good at 20% of the cost.

### Rule 2: Plan Limits Are Financial Guardrails
The 15 posts/5 seeds cap on Starter isn't to punish users — it's to cap our AI costs. Without it, a power user could cost more in AI than they pay.

### Rule 3: M-Pesa Is Your Superpower
Every competitor (Buffer, Hootsuite, Later) loses 3-4% of each payment to credit card processing. We lose 0% on 80%+ of transactions. That's free money.

### Rule 4: Fixed Costs Don't Scale, Revenue Does
Railway costs $20/month whether you have 5 users or 200 users. But 200 users generate 40x more revenue. Time is on your side.

### Rule 5: Output Tokens Are the Bill — Watch Them
When evaluating ANY new AI model, look at the OUTPUT price first. Content creation generates 2-5x more output tokens than input tokens, and output costs 3-40x more per token.

## Quick Reference: Model Costs for Decision Making

| Decision Scenario | Model | Output $/1M | Monthly Cost per Growth User |
|------------------|-------|------------|----------------------------|
| **Cheapest possible** | DeepSeek V3.2 | $0.38 | ~$0.05 (KES 7) |
| **Best value (RECOMMENDED)** | Gemini 3 Flash | $3.00 | ~$0.31 (KES 44) |
| **Premium quality** | Claude Sonnet 4.6 | $15.00 | ~$1.44 (KES 204) |
| **Too expensive** | GPT-4 Turbo | $30.00 | ~$2.85 (KES 405) |

## Glossary

| Term | Meaning | Kova Example |
|------|---------|-------------|
| **Token** | A piece of a word (~¾ of a word) | "Hello world" = ~2 tokens |
| **Input token** | Words we SEND to the AI | The prompt + user's brand info |
| **Output token** | Words the AI SENDS BACK | The generated social media post |
| **Per 1M tokens** | Price per 1 million tokens | Gemini: $3.00 per 1M output tokens |
| **ARPU** | Average Revenue Per User | KES 1,022/month at blended plans |
| **LTV** | Lifetime Value — total $ from one customer | KES 10,224 at 10-month retention |
| **Gross margin** | Revenue minus variable costs, as % | 82-89% for Kova |
| **Variable cost** | Costs that scale with users | AI tokens, images |
| **Fixed cost** | Costs that stay the same regardless of users | Railway hosting, domain |
| **Churn** | % of users who cancel each month | Target: < 10%/month |
| **Break-even** | Point where revenue = costs | ~5 users (ops), ~48 users (salary) |
| **Unit economics** | Profit/loss on serving ONE user | $1.65 - $17.25 per user (by plan) |
| **SaaS** | Software as a Service | Kova's business model — monthly subscription |
| **STK Push** | M-Pesa's payment prompt (phone popup) | "Pay KES 999 to Kova Agent?" |
| **Fallback chain** | Backup AI models tried when primary fails | nvidia → openai → minimax → DeepSeek (paid) |
| **Model routing** | Sending different tasks to different AI models | Creative → Gemini, Analysis → DeepSeek |

---

*Last updated: April 9, 2026. Review and update this document whenever pricing, models, or infrastructure changes.*
