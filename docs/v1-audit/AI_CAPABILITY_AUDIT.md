# AI Capability Audit

**Date:** July 2026

---

## AI Architecture Overview

Kova's AI layer consists of:
- **6 specialized agents** coordinated by a Chief Strategist
- **Multi-provider LLM abstraction** (OpenAI, Anthropic, OpenRouter)
- **Per-user token budget system** with daily cost tracking
- **Agent memory** with outcome measurement and feedback loops
- **Content safety gates** with fail-closed publishing

---

## Agent Inventory

### 1. Chief Strategist Agent

| Attribute | Value |
|-----------|-------|
| File | `agents/strategist_agent.py` |
| Status | **Implemented** |
| Purpose | Orchestrates all agents into a cohesive growth strategy |
| Inputs | Research trends, Analyst data, Engage patterns, Growth snapshots |
| Outputs | ContentSeeds, strategic recommendations, Daily Brief intelligence |
| Autonomy | Manual (suggest + approve) or Autonomous (create + publish) |

**Capabilities:**
- Reviews Research Agent trends → picks best to act on
- Auto-creates ContentSeeds from trends
- Reviews Engage data → identifies patterns
- Tracks audience growth → correlates content types with follower growth
- Monitors revenue signals → click attribution
- Compiles strategic recommendations → feeds Daily Brief
- Adjusts content mix based on what GROWS audience

**Assessment:** Fully implemented. This is the brain of the system. Production-ready.

---

### 2. Create Agent

| Attribute | Value |
|-----------|-------|
| File | `agents/create_agent.py` |
| Status | **Implemented** |
| Purpose | Strategic content generation from seeds to platform-native posts |
| Inputs | ContentSeeds, Business Brain DNA, platform requirements |
| Outputs | Platform-native post drafts with captions, hashtags, CTAs |
| Visual | Maps to AI photos, branded graphics, or carousels via visual_strategy.py |

**Capabilities:**
- Generates multi-platform content from a single seed
- Adapts tone/format per platform (Instagram vs LinkedIn vs TikTok)
- Respects brand voice and business DNA
- Produces visual strategy recommendations
- Generates carousel content structure
- Handles content safety pre-checks

**Assessment:** Fully implemented. Core value-delivery agent. Production-ready.

---

### 3. Research Agent

| Attribute | Value |
|-----------|-------|
| File | `agents/research_agent.py` |
| Status | **Implemented** |
| Purpose | Trend discovery via web search for content inspiration |
| Integration | Tavily web search API |
| Outputs | Trend briefs with relevance scoring |

**Capabilities:**
- Searches web for industry-relevant trends
- Evaluates trend relevance to the specific business
- Produces structured trend briefs
- Feeds into Strategist for seed creation

**Assessment:** Implemented. Depends on Tavily API availability. Production-ready.

---

### 4. Analyst Agent

| Attribute | Value |
|-----------|-------|
| File | `agents/analyst_agent.py` |
| Status | **Implemented** |
| Purpose | Performance analysis and Content DNA extraction |
| Inputs | Post metrics, engagement data, growth snapshots |
| Outputs | Performance analysis, engagement scoring, DNA insights |

**Capabilities:**
- Analyzes which content performs best
- Extracts Content DNA patterns (what works for this business)
- Scores engagement quality
- Feeds into Adapt Agent for learning

**Assessment:** Implemented. Dependent on sufficient post history for meaningful analysis. Production-ready once businesses have 2+ weeks of data.

---

### 5. Adapt Agent

| Attribute | Value |
|-----------|-------|
| File | `agents/adapt_agent.py` |
| Status | **Implemented** |
| Purpose | Learning loop that evolves content strategy over time |
| Inputs | Analyst output, engagement patterns, growth data |
| Outputs | Mutated pillar weights, DNA preferences, optimal schedule |

**Capabilities:**
- Adjusts content pillar weights based on performance
- Refines DNA preferences (tone, format, topics)
- Optimizes posting schedule based on engagement timing
- Implements prediction validation (did predictions come true?)

**Assessment:** Implemented. This is the self-improving loop. Production-ready but value increases over time.

---

### 6. Engage Agent

| Attribute | Value |
|-----------|-------|
| File | `agents/engage_agent.py` |
| Status | **Implemented** |
| Purpose | Social comment/DM analysis and AI reply generation |
| Routing | `agents/engage_routing.py` — graduated autonomy |
| Safety | Auto-send vs draft vs escalate based on confidence |

**Capabilities:**
- Fetches comments/DMs from connected platforms
- Analyzes intent (question, complaint, booking, praise)
- Generates contextual replies in brand voice
- Routes by confidence: auto-send (high), draft (medium), escalate (low)
- Detects booking intent → routes to booking flow
- Identifies superfans (repeat engagers)

**Assessment:** Implemented with graduated autonomy safety rails. Production-ready.

---

### 7. Educator Agent

| Attribute | Value |
|-----------|-------|
| File | `agents/educator_agent.py` |
| Status | **Implemented** |
| Purpose | Platform-level blog articles and weekly digest for Kova itself |
| Outputs | Help articles, blog posts, weekly digest |

**Assessment:** Implemented but serves Kova's own content marketing, not the user's business. Low priority for V1.

---

## Supporting AI Infrastructure

### LLM Layer

| Component | File | Status | Purpose |
|-----------|------|--------|---------|
| LLM Abstraction | `agents/llm.py` | **Implemented** | Multi-provider routing (OpenAI/Anthropic/OpenRouter) |
| Model Config | `agents/models.py` (LLMConfig) | **Implemented** | Singleton model routing config |
| Structured Output | `agents/llm.py` (parse_llm_json) | **Implemented** | JSON parsing with retry |
| Streaming | `agents/llm.py` | **Implemented** | Token streaming support |
| Token Tracking | `agents/models.py` (UserTokenBucket) | **Implemented** | Per-user daily usage tracking |
| Budget Enforcement | `agents/budget.py` | **Implemented** | Daily cost caps per user |
| Cost Registry | `agents/pricing.py` | **Implemented** | Token cost per model |
| Output Schemas | `agents/schemas.py` | **Implemented** | Pydantic schemas for agent outputs |

### Memory & Learning

| Component | File | Status | Purpose |
|-----------|------|--------|---------|
| Agent Memory | `agents/memory.py` | **Implemented** | History injection, outcome measurement, edit feedback |
| Customer Memory | `whatsapp/memory.py` | **Implemented** | Per-customer conversation memory for AI Salesperson |
| Business Brain | `accounts/business_brain.py` | **Implemented** | 6-layer business DNA for AI grounding |
| Content DNA | `agents/adapt_agent.py` | **Implemented** | Evolving content preferences/patterns |

### Visual Intelligence

| Component | File | Status | Purpose |
|-----------|------|--------|---------|
| Visual Strategy | `agents/visual_strategy.py` | **Implemented** | Maps content to visual type (photo/graphic/carousel/none) |
| AI Image Gen | `agents/media.py` | **Implemented** | Together/Pollinations/HuggingFace FLUX chain |
| Branded Graphics | `agents/graphics.py` | **Implemented** | Quote cards, tips, stats, CTAs via Pillow |
| Carousel Gen | `agents/carousel.py` | **Implemented** | Multi-slide structured content |
| Batch Snap Intel | `products/batch_snap_intelligence.py` | **Implemented** | Vision LLM for product photos |
| Media Asset Intel | `media/asset_intelligence.py` | **Implemented** | AI media plan recommendations |

### Content Safety

| Component | File | Status | Purpose |
|-----------|------|--------|---------|
| Safety Gates | `content/safety.py` | **Implemented** | Vision/text moderation before publish |
| Safety Config | `content/models.py` (SystemSafetyConfig) | **Implemented** | Platform-wide kill switches |
| Safety Incidents | `content/models.py` (ContentSafetyIncident) | **Implemented** | Audit trail for flagged content |

### Additional AI Features

| Component | File | Status | Purpose |
|-----------|------|--------|---------|
| Voice Transcription | `content/voice.py` | **Implemented** | Whisper via Groq/OpenAI for voice memos |
| Platform Rewrite | `content/platform_rewrite.py` | **Implemented** | Per-platform native copy adaptation |
| AI Salesperson | `kova_page/salesperson.py` | **Implemented** | Grounded Q&A on public business pages |
| Competitor Intel | `analytics/competitor_intel.py` | **Partial** | AI analysis of competitors |
| Sentiment Analysis | `reviews/sentiment.py` | **Implemented** | Keyword/emoji classifier (no LLM) |
| Booking Intent | `agents/booking_intent.py` | **Implemented** | Heuristic intent detection |
| Lead Escalation | `engage/lead_escalation.py` | **Implemented** | Intent detection for lead flagging |

---

## Capability Status Summary

| Capability | Status | V1 Ready? |
|------------|--------|-----------|
| Brand Brain / Business DNA | Implemented | Yes |
| Content generation (text) | Implemented | Yes |
| Content generation (images) | Implemented | Yes |
| Platform adaptation | Implemented | Yes |
| AI image enhancement (Photoroom) | Implemented | Yes |
| Voice memo transcription | Implemented | Yes |
| AI auto-reply (social) | Implemented | Yes |
| AI auto-reply (WhatsApp) | Implemented | Yes |
| Daily brief intelligence | Implemented | Yes |
| Strategic recommendations | Implemented | Yes |
| Content scheduling intelligence | Implemented | Yes |
| Conversation assistance | Implemented | Yes |
| Lead intelligence | Implemented | Yes |
| Performance analysis | Implemented | Yes |
| Self-improving loop (Adapt) | Implemented | Yes |
| Competitor intelligence | Partial | V1.1 |
| A/B testing intelligence | Partial | V2 |
| Revenue attribution AI | Partial | V1.1 |
| Carousel generation | Implemented | Yes |
| Video/Reel AI | Partial | V1.1 |

---

## AI Cost Management

The system has robust cost controls:

1. **Per-user daily token bucket** — prevents any single business from exceeding budget
2. **Model routing by task** — expensive models for complex tasks, cheaper for simple ones
3. **LLMConfig singleton** — centralized model selection across all agents
4. **AgentAction logging** — every AI action tracked with token usage and outcome score
5. **Budget enforcement** — requests rejected when daily cap reached

---

## Recommendations

1. **All core agents are V1-ready.** The 6-agent system with Strategist orchestration is the product's differentiator. Ship as-is.

2. **Simplify the media pipeline for V1.** The 18 Photoroom files + Fal + Bannerbear + Remotion creates maintenance surface. For V1: Photoroom (product images) + Together/FLUX (AI generation) + Pillow graphics. Defer Fal video, Bannerbear carousels, Remotion to V1.1.

3. **Validate the Adapt Agent feedback loop.** It needs 2+ weeks of data per business. Consider a cold-start acceleration using industry playbooks (`agents/playbooks.py`).

4. **Content safety gates are critical.** The fail-closed approach is correct for V1. Ensure kill switches work.

5. **Monitor LLM costs closely at scale.** The token budget system exists but per-plan limits need validation with real usage patterns.
