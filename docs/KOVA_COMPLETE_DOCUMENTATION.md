# KOVA AI — Complete Platform Documentation

> **Version:** 1.0 | **Last Updated:** July 2025
> **The AI Social Media Manager That Runs Your Entire Online Presence**

---

## Table of Contents

1. [Platform Overview](#1-platform-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture & Infrastructure](#3-architecture--infrastructure)
4. [Plans & Pricing](#4-plans--pricing)
5. [User Accounts & Onboarding](#5-user-accounts--onboarding)
6. [Social Platform Connections](#6-social-platform-connections)
7. [Content Creation & Publishing](#7-content-creation--publishing)
8. [AI Agent System](#8-ai-agent-system)
9. [Daily Briefings](#9-daily-briefings)
10. [WhatsApp Business Suite](#10-whatsapp-business-suite)
11. [Meme Intelligence Engine](#11-meme-intelligence-engine)
12. [Engagement & Community Management](#12-engagement--community-management)
13. [Analytics & Intelligence](#13-analytics--intelligence)
14. [Revenue Attribution & Kova Pixel](#14-revenue-attribution--kova-pixel)
15. [Competitor Intelligence](#15-competitor-intelligence)
16. [Media Queue](#16-media-queue)
17. [Campaigns](#17-campaigns)
18. [Email Marketing](#18-email-marketing)
19. [Product Catalog](#19-product-catalog)
20. [Lead Capture & CRM](#20-lead-capture--crm)
21. [Kova Pages (Link-in-Bio)](#21-kova-pages-link-in-bio)
22. [Teams & Collaboration](#22-teams--collaboration)
23. [Billing & Payments](#23-billing--payments)
24. [Notifications](#24-notifications)
25. [Help Center](#25-help-center)
26. [Growth Partners Program](#26-growth-partners-program)
27. [Admin Dashboard](#27-admin-dashboard)
28. [REST API](#28-rest-api)
29. [Celery Task Schedule](#29-celery-task-schedule)
30. [Security & Middleware](#30-security--middleware)
31. [Feature Matrix by Plan](#31-feature-matrix-by-plan)

---

## 1. Platform Overview

Kova AI is a comprehensive AI-powered social media management platform designed for African businesses, creators, and agencies. It replaces the need for multiple tools by combining content creation, scheduling, publishing, engagement, analytics, email marketing, lead capture, WhatsApp automation, and revenue attribution into one platform — all powered by 6 specialized AI agents that learn your brand voice and work autonomously.

### What Makes Kova Unique

- **6 AI Agents** that work together as a team — Research finds trends, Create writes posts, Adapt optimizes timing, Engage handles replies, Analyst tracks performance, Strategist orchestrates everything
- **WhatsApp Business Suite** — Full conversational AI, broadcast campaigns, drip sequences, Status Studio, and WhatsApp Channels management
- **Meme Intelligence Engine** — Discovers trending memes (with Kenyan cultural calendar awareness), adapts them to your brand, and queues for publishing
- **Multi-Touch Revenue Attribution** — Track every click to conversion with the Kova Pixel, Shopify integration, and M-Pesa commerce tracking
- **Content DNA Analysis** — AI learns what makes your content perform by analyzing format, hook type, tone, CTA, and emotion patterns
- **10 Social Platforms** — Twitter, LinkedIn, Instagram, Facebook, TikTok, YouTube, Pinterest, Threads, Bluesky, WhatsApp
- **Built for Africa** — M-Pesa payments, KES pricing, Kenyan cultural calendar, Sheng language support, WhatsApp-first approach

### The Kova Workflow

```
[User Onboarding] → [Connect Platforms] → [Set Brand Voice]
        ↓
[Content Seeds] → [AI Create Agent] → [AI-Generated Posts]
        ↓
[Review & Edit] → [Schedule/Queue] → [Auto-Publish]
        ↓
[Engage Agent Monitors] → [AI Replies] → [Superfan Tracking]
        ↓
[Analyst Tracks Performance] → [Content DNA Extraction]
        ↓
[Strategist Agent] → [Next Day's Strategy] → [Daily Brief]
        ↓                                        ↓
[Revenue Attribution] ← [Kova Pixel] ← [Conversions]
```

---

## 2. Technology Stack

| Layer | Technology |
|-------|-----------|
| **Framework** | Django 5.1 (Python 3.12) |
| **ASGI Server** | Daphne (WebSocket) + Gunicorn (production HTTP) |
| **Database** | PostgreSQL 16 + pgvector (vector embeddings) |
| **Cache / Broker** | Redis 7 |
| **Task Queue** | Celery 5.4 + django-celery-beat (DB-based scheduler) |
| **WebSockets** | Django Channels + channels-redis |
| **AI / LLM** | LangChain + LangGraph + OpenAI + Anthropic + OpenRouter |
| **Primary LLM** | DeepSeek V3.2 via OpenRouter |
| **Image Generation** | FLUX.1-schnell via Together.ai / HuggingFace / Pollinations |
| **Web Search** | Tavily (real-time web search for agents) |
| **Frontend** | Django Templates + HTMX + Alpine.js + Tailwind CSS |
| **Authentication** | django-allauth (email-based, mandatory verification) |
| **REST API** | Django REST Framework (token + session auth) |
| **Payments** | Stripe (international) + M-Pesa STK Push (Kenya) |
| **Email Service** | Resend |
| **File Storage** | Cloudflare R2 (S3-compatible) via django-storages + boto3 |
| **Token Encryption** | Fernet symmetric encryption |
| **PWA** | Service worker + web manifest |

---

## 3. Architecture & Infrastructure

### Production Deployment (Railway)

Kova runs on Railway with 3 services:

| Service | Command | Purpose |
|---------|---------|---------|
| **web** | `bash start.sh` → Gunicorn (3 workers) | HTTP server, Django app |
| **worker** | Celery worker, concurrency=3 | Background tasks (AI, publishing, analytics) |
| **beat** | Celery Beat with DatabaseScheduler | Periodic task scheduling |

The `start.sh` script handles: Tailwind CSS compilation → `collectstatic` → `migrate` → superuser creation → storage backend check → Gunicorn launch.

### Development (Docker Compose)

5 services: `web` (Django dev server), `db` (PostgreSQL 16), `redis` (Redis 7), `celery_worker`, `celery_beat`, `tailwind` (CSS watcher).

### Celery Queue Architecture

3 priority queues ensure user-facing operations are never blocked by background AI work:

| Queue | Purpose | Example Tasks |
|-------|---------|---------------|
| **critical** | User-facing, time-sensitive | Publish posts, refresh tokens, process media queue, WhatsApp incoming messages |
| **default** | AI generation & agents | Generate from seed, daily research, engage cycle, strategy cycle, daily briefs |
| **low** | Analytics & background intel | Fetch metrics, evaluate A/B tests, competitor analysis, trial expiry emails |

### Application Architecture

21 Django apps organized by domain:

```
apps/
├── accounts/          # User model, profiles, onboarding
├── admin_dashboard/   # Internal admin analytics (70+ routes)
├── agents/            # 6 AI agents + LLM abstraction
├── analytics/         # Performance, competitors, revenue, pixel
├── api/               # REST API (DRF)
├── billing/           # Stripe + M-Pesa, plan enforcement
├── briefs/            # Daily AI briefings
├── campaigns/         # Cross-channel marketing campaigns
├── content/           # Posts, seeds, A/B tests, scheduling
├── emails/            # Transactional + marketing email
├── engage/            # Community engagement inbox
├── help/              # Help center (20 articles)
├── leads/             # Lead capture & CRM
├── links/             # Kova Pages (link-in-bio)
├── media_queue/       # Scheduled photo queue
├── memes/             # Meme Intelligence Engine
├── notifications/     # In-app notifications
├── partners/          # Growth Partners referral program
├── platforms/         # Social account OAuth & publishing
├── products/          # Product catalog & stock
├── teams/             # Team management & brands
├── utils/             # Shared utilities (resilient HTTP)
└── whatsapp/          # WhatsApp Business automation
```

---

## 4. Plans & Pricing

Kova offers 4 subscription tiers with a **14-day free trial** on all plans:

| | **Starter** | **Growth** | **Pro** | **Agency** |
|---|:---:|:---:|:---:|:---:|
| **Monthly Price** | KES 299 / $2 | KES 999 / $7 | KES 1,999 / $14 | KES 2,999 / $21 |
| Social Accounts | 1 | 3 | 10 | 25 |
| Posts / Month | 15 | 60 | 150 | Unlimited |
| Content Seeds / Month | 5 | 30 | 60 | Unlimited |
| AI Agents | Create, Analyst | + Research, Adapt | + Engage, Strategist | All 6 |
| AI Image Generation | ❌ | 50 / month | 100 / month | 500 / month |
| A/B Testing | ❌ | ✅ | ✅ | ✅ |
| Team Members | 0 | 0 | 5 | 25 |
| Kova Pages | 1 | 3 | 10 | 50 |
| Leads | 10 | 100 | Unlimited | Unlimited |
| Email Subscribers | 50 | 2,500 | 25,000 | Unlimited |
| Products | 5 | 30 | 100 | Unlimited |
| WhatsApp Suite | ❌ | ❌ | ✅ | ✅ |
| Meme Intelligence | ❌ | ❌ | ✅ | ✅ |
| Campaigns | ❌ | 3 / month | 10 / month | Unlimited |
| REST API Access | ❌ | ❌ | ✅ | ✅ |

**Payment Methods:**
- **Stripe** — Credit/debit cards (international)
- **M-Pesa** — STK Push (Kenya) with polling confirmation

---

## 5. User Accounts & Onboarding

### User Model

Kova uses a custom user model with UUID primary keys and email-based authentication (no usernames).

| Field | Description |
|-------|-------------|
| Email | Primary login identifier (unique, required) |
| Full Name | Display name |
| Plan | Current subscription tier (starter/growth/pro/agency) |
| Trial End Date | 14 days from registration |
| Timezone | User's timezone for scheduling |
| Stripe Customer ID | Links to Stripe for billing |

### User Profile

Every user has a profile that stores brand intelligence and AI preferences:

| Setting | Description |
|---------|-------------|
| **Company Name** | Business name used in AI content |
| **Industry** | Industry vertical for Research Agent context |
| **Brand Voice** | Detailed description of brand personality and communication style |
| **Brand Tone** | Tone keywords (e.g., professional, witty, casual) |
| **Content Pillars** | Core themes the brand posts about |
| **Target Audience** | Audience description for content targeting |
| **Visual Style** | Visual aesthetic preferences for AI image generation |
| **Default CTA** | Default call-to-action for posts |
| **CTA URL** | Default link for CTAs |
| **Agent Autonomy** | How much independence AI agents have (low/medium/high) |
| **Pixel Token** | Unique token for Kova Pixel website tracking |

### 4-Step Onboarding Wizard

New users are guided through a streamlined onboarding flow:

1. **Brand Basics** — Company name, industry, target audience
2. **Brand Voice** — Tone, voice description, content pillars
3. **Connect Platforms** — OAuth connect to social accounts
4. **First Content** — Create first content seed or explore the platform

The `OnboardingMiddleware` automatically redirects new users to this flow until completed.

### AI Brand Builder

An AI-powered alternative to manual onboarding. Users provide their website URL or a brief description, and the AI:
- Analyzes the brand's online presence
- Suggests brand voice, tone, and content pillars
- Generates a complete brand profile ready for content creation

---

## 6. Social Platform Connections

### Supported Platforms (10)

| Platform | Auth Method | Features |
|----------|------------|----------|
| **Twitter/X** | OAuth 2.0 | Text posts, media, threads |
| **LinkedIn** | OAuth 2.0 | Text posts, articles, media |
| **Instagram** | Facebook OAuth → Instagram Graph API | Photo/video posts, carousels, stories |
| **Facebook** | OAuth 2.0 (Page token) | Page posts, media, scheduling |
| **TikTok** | OAuth 2.0 | Video posts |
| **YouTube** | OAuth 2.0 | Video uploads |
| **Pinterest** | OAuth 2.0 | Pin creation, boards |
| **Threads** | Meta OAuth | Text posts |
| **Bluesky** | App Password | Text posts, media |
| **WhatsApp** | Permanent Access Token | Messaging, broadcasts, status, channels |

### Social Account Model

Each connected platform account tracks:

| Field | Description |
|-------|-------------|
| Platform | Which social network |
| Platform User ID | Unique identifier on the platform |
| Account Name / Username | Display name and handle |
| Access Token / Refresh Token | Encrypted with Fernet |
| Token Expiry | Auto-refresh before expiration |
| Failure Count | Tracks API failures (0-3) |
| Is Active | Auto-deactivated after 3 consecutive failures |
| Metadata | Platform-specific data (page IDs, audience size, etc.) |

### Provider Architecture

Each platform has a dedicated provider class inheriting from `BaseProvider`:

```
BaseProvider (Interface)
├── TwitterProvider
├── LinkedInProvider
├── InstagramProvider
├── FacebookProvider
├── TikTokProvider
├── YouTubeProvider
├── PinterestProvider
├── ThreadsProvider
├── BlueskyProvider
└── WhatsAppProvider
```

Providers handle: OAuth flow, token refresh, post publishing, comment fetching, mention retrieval, and audience metrics.

### Auto-Deactivation (3-Strike System)

If a platform API call fails 3 consecutive times, the account is automatically deactivated to prevent wasted API calls. Users are notified and can reconnect.

### Token Refresh

A Celery task runs every 30 minutes to refresh tokens expiring within 24 hours. Tokens are encrypted at rest using Fernet symmetric encryption.

---

## 7. Content Creation & Publishing

### Content Seeds → AI → Posts

The content pipeline starts with a **Content Seed** — a simple idea that AI expands into full posts:

```
Content Seed (idea + target platforms)
    ↓
AI Create Agent (generates platform-specific posts)
    ↓
Draft Posts (ready for review)
    ↓
User Review & Edit
    ↓
Schedule or Publish
    ↓
Auto-Publish at Scheduled Time
```

### Content Seed

A seed is the starting point for AI content generation:

| Field | Description |
|-------|-------------|
| Topic | The core idea or subject |
| Notes | Additional context, key points, URLs |
| Seed Type | text, link, image, product_promo, event, thread, carousel, meme |
| Target Platforms | Which platforms to generate for |
| Tone Override | Override brand voice for this specific content |
| CTA Override | Custom call-to-action |
| Status | draft → generating → completed → failed |
| Schedule Intent | How to schedule the generated posts |

### Post Model

Each generated post is a full, platform-optimized content piece:

| Field | Description |
|-------|-------------|
| Content | The actual post text |
| Platform | Target social platform |
| Social Account | Specific account to publish on |
| Status | draft → pending_approval → approved → scheduled → publishing → published / failed / rejected |
| Scheduled Time | When to auto-publish |
| Published At | Actual publish timestamp |
| Platform Post ID | ID returned by platform after publishing |
| Media Attachments | Images, videos, documents |
| CTA Text / URL | Call-to-action |
| UTM Parameters | Auto-generated for tracking (source, medium, campaign, content) |
| Hashtags | Platform-appropriate hashtags |
| Content DNA | AI-extracted: format, hook type, tone, CTA presence, emotion, length |
| Predicted Engagement | AI prediction score (0-100) before publishing |
| Is A/B Test | Whether this post is part of an A/B test |

### Post Statuses (8)

| Status | Description |
|--------|-------------|
| `draft` | Just created, needs review |
| `pending_approval` | Submitted for team approval |
| `approved` | Approved, ready to schedule |
| `scheduled` | Has a scheduled time, waiting for publish |
| `publishing` | Currently being sent to platform API |
| `published` | Successfully published |
| `failed` | Publish attempt failed |
| `rejected` | Rejected during review |

### 5 Scheduling Intents

| Intent | Behavior |
|--------|----------|
| `post_now` | Publish immediately |
| `next_best` | AI picks the next optimal time based on audience activity |
| `smart_queue` | AI distributes posts across optimal times over coming days |
| `quick` | Quick-pick: 30 minutes, 1 hour, 3 hours, or tomorrow |
| `exact` | User specifies exact date and time |

### Platform Peak Hours

Kova has built-in knowledge of optimal posting times per platform:

| Platform | Peak Hours (UTC) |
|----------|-----------------|
| Twitter | 9:00, 12:00, 17:00 |
| LinkedIn | 7:30, 12:00, 17:30 |
| Instagram | 11:00, 13:00, 19:00 |
| Facebook | 9:00, 13:00, 16:00 |
| TikTok | 7:00, 12:00, 19:00 |
| YouTube | 12:00, 15:00, 18:00 |
| Pinterest | 8:00, 14:00, 20:00 |
| Threads | 10:00, 13:00, 18:00 |
| Bluesky | 9:00, 12:00, 17:00 |

### A/B Testing

Growth, Pro, and Agency plans can create A/B tests:

1. Select a post to test
2. AI generates variant(s) with different hooks, CTAs, or formats
3. Both versions are published at similar times
4. After sufficient data collection, the Analyst Agent evaluates the winner
5. Winning patterns are fed back into future content creation

**ABTest Model:**
- Links a control post to a variant post
- Tracks: status (running/completed), winner (control/variant/draw), confidence level, evaluation notes
- Auto-evaluated by Celery task every hour

### Content Studio Views (38+)

| View | Purpose |
|------|---------|
| Content Studio | Main content hub — all posts with filters |
| Seed Create | Create new content seed |
| Seed Detail | View seed with generated posts |
| Post Detail | Individual post view |
| Post Edit | Edit post content, CTA, hashtags |
| Post Schedule | Set scheduling for a post |
| Queue View | All scheduled posts in chronological order |
| Calendar View | Visual calendar of scheduled content |
| A/B Test Create | Create A/B test from existing post |
| A/B Test Dashboard | View all running and completed tests |
| Media Upload | Upload images/videos with EXIF stripping |
| Bulk Actions | Approve, schedule, or delete multiple posts |

### Media Handling

- Media files are uploaded to Cloudflare R2 (production) or local filesystem (development)
- **EXIF data is stripped** from all uploaded images for privacy
- Supported: images (JPG, PNG, GIF, WebP), videos (MP4, MOV), documents
- Media can be attached during seed creation or added to posts directly

---

## 8. AI Agent System

Kova's AI is organized into 6 specialized agents that work together:

```
                    ┌─────────────────┐
                    │   STRATEGIST    │
                    │  🧠 Orchestrator │
                    └────────┬────────┘
                             │ coordinates
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
    ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
    │   RESEARCH   │ │    CREATE    │ │    ADAPT     │
    │ 🔍 Discovers  │ │ ✍️ Generates  │ │ 🔄 Optimizes  │
    └──────────────┘ └──────────────┘ └──────────────┘
            │                │                │
            └────────────────┼────────────────┘
                             ▼
                    ┌──────────────┐
                    │   ANALYST    │
                    │ 📊 Evaluates  │
                    └──────────────┘
                             │
                             ▼
                    ┌──────────────┐
                    │    ENGAGE    │
                    │ 💬 Responds   │
                    └──────────────┘
```

### Agent Availability by Plan

| Agent | Starter | Growth | Pro | Agency |
|-------|:-------:|:------:|:---:|:------:|
| Create ✍️ | ✅ | ✅ | ✅ | ✅ |
| Analyst 📊 | ✅ | ✅ | ✅ | ✅ |
| Research 🔍 | ❌ | ✅ | ✅ | ✅ |
| Adapt 🔄 | ❌ | ✅ | ✅ | ✅ |
| Engage 💬 | ❌ | ❌ | ✅ | ✅ |
| Strategist 🧠 | ❌ | ❌ | ✅ | ✅ |

### Research Agent 🔍

**Purpose:** Discovers trending topics, competitor movements, and content angles relevant to the user's industry.

**What it does:**
- Searches the web for trending topics in the user's industry
- Analyzes competitors' content strategies
- Generates specific content angles from discovered trends
- Feeds insights to the Strategist for daily planning

**Runs:** Every 12 hours (Celery periodic task), staggered per user

**Key Functions:**
| Function | Description |
|----------|-------------|
| `discover_trends()` | Main entry — finds trending topics for user's industry |
| `generate_content_angles()` | Creates specific content angles from a topic |

### Create Agent ✍️

**Purpose:** Generates platform-optimized posts from content seeds, using the user's brand voice.

**What it does:**
- Takes a content seed and generates posts for each target platform
- Adapts tone, length, hashtags, and CTAs per platform
- Generates A/B test variants
- Can regenerate or repurpose existing posts to new platforms
- Injects past performance data into prompts (what worked before)

**Key Functions:**
| Function | Description |
|----------|-------------|
| `run_create_agent()` | Main entry — generates posts from a ContentSeed |
| `regenerate_single_post()` | Regenerate one post with fresh copy |
| `repurpose_post()` | Adapt a post to different platforms |
| `generate_ab_variants()` | Create A/B test variants |

### Adapt Agent 🔄

**Purpose:** Optimizes posting schedules based on audience activity patterns.

**What it does:**
- Analyzes historical time-based performance data
- Suggests optimal posting times per platform
- Auto-schedules posts to the best available time slots
- Considers platform peak hours and audience timezone

**Key Functions:**
| Function | Description |
|----------|-------------|
| `suggest_optimal_times()` | AI-powered optimal time suggestions |
| `auto_schedule_post()` | Automatically schedule a post to optimal time |

### Engage Agent 💬

**Purpose:** Monitors social interactions and generates/sends AI-powered replies.

**What it does:**
- Fetches comments and mentions from all connected platforms
- Analyzes sentiment and priority of each interaction
- Generates brand-voice replies
- Auto-sends high-confidence replies (configurable threshold)
- Tracks superfans (recurring engagers)
- Learns from user edits to improve future replies

**Confidence Routing:**
| Confidence Score | Action |
|-----------------|--------|
| > 0.8 | Auto-send reply |
| 0.5 - 0.8 | Save as draft for user review |
| < 0.5 | Escalate / flag for human response |

**Runs:** Every 30 minutes (Celery periodic task)

**Key Functions:**
| Function | Description |
|----------|-------------|
| `run_engage_cycle()` | Full cycle: fetch → analyze → reply → auto-send |
| `fetch_interactions()` | Fetches comments/mentions from all platforms |
| `analyze_interactions()` | AI sentiment and priority analysis |
| `generate_replies()` | AI reply generation in brand voice |
| `auto_respond()` | Send approved replies via platform APIs |

### Analyst Agent 📊

**Purpose:** Tracks performance, extracts content DNA, predicts engagement, and evaluates A/B tests.

**What it does:**
- Analyzes post performance across all platforms
- Extracts **Content DNA** — the genetic makeup of what makes content perform:
  - Format (carousel, video, text, etc.)
  - Hook type (question, statistic, story, etc.)
  - Tone (professional, casual, provocative, etc.)
  - CTA presence and type
  - Emotional tone
  - Content length
- Predicts engagement scores before publishing
- Evaluates A/B test results with statistical confidence
- Compares predicted vs actual engagement to improve over time

**Key Functions:**
| Function | Description |
|----------|-------------|
| `analyze_performance()` | AI performance analysis across posts |
| `extract_content_dna()` | Extracts content DNA from a post |
| `predict_engagement()` | Predicts engagement score (0-100) |
| `evaluate_ab_test()` | Determines A/B test winner |
| `get_content_dna_summary()` | Aggregated DNA patterns over time |

### Strategist Agent 🧠

**Purpose:** Orchestrates all agents, runs daily strategy cycles, and drives long-term growth decisions.

**What it does:**
- Gathers intelligence from all other agents (trends, performance, engagement, DNA patterns)
- Analyzes content-to-growth correlation (what content types drive follower growth)
- Identifies revenue signals (which posts drive conversions)
- Makes strategic decisions and creates content seeds automatically
- Generates the Daily Brief

**Runs:** Every 8 hours (Celery periodic task)

**Key Functions:**
| Function | Description |
|----------|-------------|
| `run_strategy_cycle()` | Main entry — daily strategy orchestration |
| `_get_content_growth_correlation()` | Correlates content types with follower growth |
| `_get_revenue_signals()` | Revenue intelligence for strategy |
| `_get_sentiment_breakdown()` | Audience sentiment analysis |

### Agent Configuration

Each user can configure their agents:

| Setting | Description |
|---------|-------------|
| Is Active | Toggle agent on/off |
| Custom Instructions | Persona instructions that modify the agent's behavior |
| Config | Agent-specific configuration blob |

### Agent Action Audit Log

Every AI action is logged with full traceability:

| Tracked Data | Description |
|--------------|-------------|
| Agent Type | Which agent performed the action |
| Action Type | What was done (e.g., `strategy_cycle`, `generate`) |
| Status | started / completed / failed / needs_approval |
| Input/Output Data | Full request and response data |
| Tokens Used | Input + output token counts |
| Model Used | Which LLM model was used |
| Duration | Time taken in milliseconds |
| Outcome Score | Retroactive quality score (0-100) |

### Memory & Learning System

Kova's agents learn and improve through feedback loops:

| Memory Type | How It Works |
|-------------|-------------|
| **Edit Tracking** | When users edit AI-generated content, the system records what changed. Future prompts include these patterns so the AI adapts to user preferences. |
| **Prediction Validation** | After a post is published and metrics come in, the system compares predicted vs actual engagement. This accuracy data improves future predictions. |
| **Outcome Scoring** | Agent actions are retroactively scored based on real-world outcomes (posts created, engagement received, user edits required). |
| **Strategy History** | Past strategy decisions and their outcomes are fed back into future strategy cycles. |

### LLM Architecture

**3-Tier Model Routing:**

| Tier | Use Case | Task Keys |
|------|----------|-----------|
| **Premium** | Creative writing, user-facing text | `create.generate`, `create.regenerate`, `create.repurpose`, `engage.reply` |
| **Workhorse** | Reasoning, research, strategy | `research.trends`, `research.angles`, `strategist.brief`, `strategist.decide` |
| **Fast** | Classification, scoring, structured data | `engage.analyze`, `analyst.performance`, `analyst.content_dna`, `analyst.predict`, `adapt.schedule` |

**Model Resolution Order:**
1. Per-task override (from LLMConfig in admin)
2. Plan-specific tier model (different plans can get different quality models)
3. Global tier defaults
4. Settings fallback
5. Default model

**Retry & Fallback Chain:**
1. Try primary model
2. If free model fails → rotate through free fallback models
3. If all free models fail → escalate to paid fallback model
4. Backoff: exponential (2^attempt seconds, capped at 2s)
5. If all fail → return empty response (caller handles gracefully)

**JSON Parsing (5-Stage Repair):**

LLM outputs are often imperfect JSON. Kova's parser has 5 repair stages:
1. Direct parse (strip fences, smart quotes, trailing commas, `<think>` blocks)
2. Fix unescaped newlines in string values
3. Fix single quotes as JSON delimiters
4. Repair truncated JSON (close open brackets/braces)
5. Salvage complete objects from truncated arrays

### AI Image Generation

| Provider | Model | Role |
|----------|-------|------|
| Together.ai | FLUX.1-schnell | Primary |
| HuggingFace | FLUX.1-schnell | Fallback 1 |
| Pollinations.ai | FLUX.1-schnell | Fallback 2 |

Image generation is plan-gated: Growth (50/mo), Pro (100/mo), Agency (500/mo).

### LLMConfig (Admin-Managed)

The LLM configuration is a singleton model managed through the admin dashboard. Platform administrators can change:
- Default provider and model
- Tier-specific models (premium, workhorse, fast)
- Per-task model overrides
- Per-plan model routing
- Rate limits per plan
- Free fallback model chain
- Image generation provider, model, and fallback chain
- Global kill-switch for image generation

---

## 9. Daily Briefings

Every day, Kova generates a personalized Daily Brief for each user — their AI-powered morning dashboard.

### What's in the Brief

| Section | Content |
|---------|---------|
| **Summary** | Plain-language day plan ("Today focus on..." ) |
| **Trending Topics** | From Research Agent — what's hot in your industry |
| **Suggested Posts** | AI post suggestions with reasoning |
| **Performance Summary** | Yesterday's metrics across all platforms |
| **Agent Activity** | What your AI agents did and will do today |
| **Posts Pending** | How many posts are queued/scheduled |

### Brief Dashboard

The Brief is the main landing page after login. It also shows:

- **Quick Stats** — Published today, failed count, scheduled count
- **Top 5 Superfans** — Your most engaged community members
- **Platform Nudge** — Reminder to connect platforms if none connected
- **Setup Checklist** (first 14 days) — Connect platform, set brand voice, publish first post, read brief
- **Value Summary** — "What Kova did this week": posts published, posts created, replies drafted, leads captured

### Generation Schedule

Briefs are generated every 15 minutes via Celery task, ensuring fresh data throughout the day. One brief per user per day.

---

## 10. WhatsApp Business Suite

Kova's WhatsApp integration is a complete business communication platform.

### WhatsApp Inbox

A conversational inbox for all WhatsApp Business conversations:

| Feature | Description |
|---------|-------------|
| **Conversation Threading** | Organized by contact with full message history |
| **AI Auto-Reply** | Automatic AI-powered responses based on conversation context |
| **Language Detection** | Detects English, Swahili, and Sheng — responds in the contact's language |
| **24-Hour Window** | Tracks Meta's 24-hour messaging window for each conversation |
| **Sentiment Tracking** | AI scores conversation sentiment |
| **Manual Override** | Toggle AI off for any conversation and respond manually |
| **Escalation** | Low-confidence conversations are flagged for human review |

**AI Confidence Routing:**
| Score | Action |
|-------|--------|
| > 0.8 | Auto-send AI reply |
| 0.5 - 0.8 | Save as draft for review |
| < 0.5 | Escalate to human |

### Status Studio

Create and schedule WhatsApp Status updates:

| Feature | Description |
|---------|-------------|
| **AI Content Generation** | Generate Status content from a prompt |
| **Post Repurposing** | Adapt existing social posts to Status format |
| **Category System** | new_product, offer, testimonial, behind-the-scenes, poll, meme, quote, tip, announcement, repurposed |
| **Share URLs** | Generate shareable links for each Status |
| **7-Day Calendar** | Visual planner with content mix optimization |
| **Status Templates** | Reusable templates for common content types |

**Status Lifecycle:** draft → ready → shared → expired/skipped

### WhatsApp Broadcasts

Send targeted messages to segmented contact lists:

| Feature | Description |
|---------|-------------|
| **Segment-Based Targeting** | Filter recipients by tags, language, activity |
| **Meta Template Integration** | Uses approved WhatsApp templates |
| **Delivery Tracking** | Sent, delivered, read, replied, failed counts |
| **Scheduling** | Schedule broadcasts for optimal timing |
| **Launch Workflow** | Resolve recipients → preview → launch |

### Drip Sequences

Multi-step automated message sequences:

| Feature | Description |
|---------|-------------|
| **Sequence Types** | Onboarding, re-engagement, cart abandonment, post-purchase, custom |
| **Step Configuration** | Each step has a template, delay (hours), and custom variables |
| **Enrollment Tracking** | Tracks each contact's progress through the sequence |
| **Auto-Processing** | Celery task runs every 30 minutes to send due steps |

### WhatsApp Channels

Manage WhatsApp Channels (broadcast newsletters):

| Feature | Description |
|---------|-------------|
| **Channel Management** | Create and manage WhatsApp Channels |
| **Auto-Curation** | Automatically curate content from other social platforms |
| **AI Adaptation** | Content is AI-adapted for the channel format |
| **Publishing** | Post directly to channel with reach/reaction tracking |

### WhatsApp Analytics

| Metric | Description |
|--------|-------------|
| **Message Volume** | Conversations, messages in/out, daily trends |
| **AI Performance** | AI replies sent, auto-sent rate, draft rate, confidence distribution |
| **Response Time** | Average response time in seconds |
| **Sentiment** | Positive/neutral/negative breakdown |
| **Delivery** | Sent/delivered/read/failed rates |
| **Revenue** | Conversions and revenue attributed to WhatsApp |
| **Status** | Statuses shared count |
| **Weekly Digest** | AI-generated weekly performance summary with recommendations |

---

## 11. Meme Intelligence Engine

Kova automatically discovers trending memes and adapts them to your brand.

### How It Works

```
Web Search (Kenyan + Global memes)
    ↓
Cultural Calendar Check (upcoming holidays/events)
    ↓
Dedup Against Existing Memes
    ↓
LLM Analysis (virality, safety, cultural scores)
    ↓
Brand Adaptation (personalized per user)
    ↓
User Queue (approve → post)
```

### Trending Meme Discovery

Every 3 hours, Kova:
1. Searches for trending memes via Tavily (3 queries: KOT/Kenya Twitter, TikTok Kenya, global memes)
2. Checks the Kenyan cultural calendar for upcoming events that could be meme-worthy
3. Deduplicates against previously discovered memes
4. Runs LLM analysis to score each meme on:
   - **Virality Score** (0-100) — how likely to spread
   - **Safety Score** (0-100) — brand safety
   - **Cultural Score** (0-100) — cultural relevance
5. Saves 5-8 scored memes per discovery run

### Meme Lifecycle

```
emerging (0-6h) → trending (6-48h) → peaked (48-96h) → fading (96-168h) → dead
```

Each meme has a calculated shelf life. The lifecycle task runs daily to age memes through stages.

### Brand Adaptation

Every 4 hours, Kova:
1. Takes the top 10 usable memes (trending + high scores)
2. For each active user with meme preferences enabled:
   - Checks risk tolerance (conservative/moderate/bold)
   - Respects weekly quota
   - Creates 2 personalized adaptations per run
3. Adaptations are scored for brand_relevance and humor_preserved

### Kenyan Cultural Calendar

Pre-populated database of Kenyan events (holidays, sports, political events) with:
- Meme potential score
- Sensitivity rating
- Suggested meme angles

### User Preferences

| Setting | Options |
|---------|---------|
| Risk Tolerance | Conservative, Moderate, Bold |
| Category Preferences | Which meme categories to include |
| Humor Types | Preferred humor styles |
| Weekly Quota | Max meme adaptations per week |
| Auto-Queue | Automatically add approved memes to content queue |

---

## 12. Engagement & Community Management

### Engagement Inbox

A unified inbox for all social interactions across platforms:

| Feature | Description |
|---------|-------------|
| **Interaction Types** | Comments, replies, mentions, DMs |
| **Status Tracking** | new → ai_replied / user_replied / ignored / flagged |
| **Sentiment Analysis** | AI-powered sentiment scoring per interaction |
| **AI Reply Suggestions** | One-click AI reply generation |
| **Platform Filters** | Filter by platform, status, sentiment |
| **Manual Trigger** | Manually trigger the Engage Agent cycle |

### Interaction Model

Each tracked interaction records:
- Author name and username
- Content of the interaction
- Platform and linked post
- AI-suggested reply
- Whether the reply was AI-generated, edited by user, or manually written
- Sentiment score

### Superfan Tracking

Kova automatically identifies and tracks repeat engagers:

| Tier | Criteria | Description |
|------|----------|-------------|
| **Rising** | 3-5 interactions | New active community member |
| **Loyal** | 6-15 interactions | Consistently engaged |
| **Superfan** | 16+ interactions | Your biggest advocates |

Superfan data includes: username, platforms they engage on, interaction count, last sentiment, and custom notes.

---

## 13. Analytics & Intelligence

### Performance Dashboard

The main analytics view shows:

| Metric | Description |
|--------|-------------|
| **Post Metrics** | Impressions, reach, likes, comments, shares, saves, clicks, engagement rate |
| **Prediction Accuracy** | Predicted vs actual engagement scores, prediction error tracking |
| **Content DNA Patterns** | Aggregated view of what content characteristics drive performance |
| **Platform Comparison** | Side-by-side performance across all connected platforms |

### Post Metrics

For every published post, Kova tracks:

| Metric | Description |
|--------|-------------|
| Impressions | Number of times content was displayed |
| Reach | Unique accounts that saw the content |
| Likes | Like/favorite count |
| Comments | Comment/reply count |
| Shares | Share/retweet/repost count |
| Saves | Bookmark/save count |
| Clicks | Link clicks |
| Engagement Rate | Calculated engagement percentage |
| Predicted Score | AI prediction before publish (0-100) |
| Actual Score | Normalized actual engagement (0-100) |
| Prediction Error | Difference (positive = AI underestimated) |

Metrics are fetched every 6 hours via Celery task.

### Content DNA

Every post's "genetic makeup" is extracted by the Analyst Agent:

| DNA Component | What It Captures |
|---------------|-----------------|
| **Format** | Carousel, single image, video, text-only, thread, poll |
| **Hook Type** | Question, statistic, story, bold claim, how-to, list |
| **Tone** | Professional, casual, provocative, educational, humorous |
| **CTA Presence** | Whether a call-to-action is included and its type |
| **Emotional Tone** | Inspirational, urgent, curious, empathetic |
| **Length** | Short, medium, long |
| **Stats Usage** | Whether statistics/data points are included |

DNA patterns are aggregated over time to reveal what content characteristics drive the most engagement.

### Audience Growth Tracking

Daily snapshots capture:
- Follower count per platform
- Following count
- Total posts on platform
- Daily change (delta)
- Growth velocity (daily and weekly)
- Trend direction (accelerating / decelerating / steady)
- Best and worst performing days

---

## 14. Revenue Attribution & Kova Pixel

### Multi-Touch Attribution

Kova tracks the complete customer journey from social media impression to conversion:

```
Social Post → Click (UTM tracked) → Website Visit → Lead → Sale
```

**Attribution Model:**
| Touches | Credit Distribution |
|---------|-------------------|
| 1 touch | 100% to that touchpoint |
| 2 touches | 40% first, 60% last |
| 3+ touches | 40% first, 20% middle (split), 40% last |

### Conversion Journey

Each customer journey tracks:
- **Visitor ID** — Cookie-based or email identification
- **Touchpoints** — Every interaction (post clicks, page views, form submissions, ad clicks)
- **First/Last Touch** — Attribution anchors
- **Revenue** — Total revenue from this journey
- **Conversion Status** — Whether the journey resulted in a conversion

### Touchpoint Types

| Type | Description |
|------|-------------|
| `post_click` | Click from a social media post |
| `page_view` | Website page view |
| `link_click` | Click on a Kova Link |
| `form_submit` | Lead form submission |
| `ad_click` | Paid ad click |
| `direct` | Direct visit |

### Kova Pixel

A JavaScript tracking snippet that users add to their website:

```html
<script src="https://yourdomain.com/analytics/pixel/kova-pixel.js"></script>
<script>
  KovaPixel.init('YOUR_PIXEL_TOKEN');
</script>
```

**What it tracks:**
- Page views
- Form submissions
- Button clicks
- Purchases (with revenue)
- Add to cart events
- Sign-ups
- Custom events

**Technical details:**
- Authenticated by pixel_token (not session cookies)
- Rate limited: 120 requests/minute per token
- CORS-enabled for cross-origin tracking
- No PII collected — uses anonymous visitor IDs

### Conversion Sources

| Source | Integration |
|--------|------------|
| **Kova Pixel** | JavaScript snippet on user's website |
| **Shopify** | Order webhook (HMAC-verified) → automatic conversion creation |
| **M-Pesa** | Commerce callback → automatic conversion creation |
| **Manual** | API endpoint for custom conversion tracking |

### Revenue Dashboard

Aggregated revenue analytics:
- Total revenue, conversions, sales, leads, clicks
- Revenue by platform
- Revenue by content type (which content formats drive sales)
- Revenue by CTA type
- Revenue by product (links to Product catalog)
- Top posts by revenue
- Daily revenue trend
- ROI calculation
- Sales funnel visualization

---

## 15. Competitor Intelligence

### Competitor Tracking

Users can add competitors and track their social media strategies:

| Data Tracked | Description |
|-------------|-------------|
| Platform Handles | Twitter, Instagram, Facebook, LinkedIn, TikTok, YouTube, Threads |
| Strengths | AI-identified competitive strengths |
| Weaknesses | AI-identified competitive weaknesses |
| Content Patterns | Formats, themes, posting frequency, tone |
| Threat Level | Low, Medium, High |

### AI Competitor Analysis

Periodic AI-powered analysis generates:

| Output | Description |
|--------|-------------|
| **Summary** | Executive summary of competitor's strategy |
| **Content Strategy** | Themes, formats, frequency, tone, best-performing content |
| **SWOT Analysis** | Strengths, weaknesses, opportunities, threats |
| **Head-to-Head** | Direct comparison against user's performance |
| **Actionable Insights** | Specific content ideas from competitor gaps |

### Competitor Insights

Insights are categorized by type and priority:

| Type | Description |
|------|-------------|
| `content_gap` | Topic the competitor isn't covering |
| `trend_ahead` | Competitor is ahead on a trend |
| `weakness` | Competitor weakness to exploit |
| `strategy_shift` | Competitor changed their strategy |
| `viral_content` | Competitor had viral content — learn from it |
| `opportunity` | Market opportunity identified |

| Priority | Action |
|----------|--------|
| **High** | Act Now — immediate action recommended |
| **Medium** | This Week — address soon |
| **Low** | Good to Know — background awareness |

### Competitor Landscape

Visual competitive landscape view showing all tracked competitors with threat levels, analysis recency, and comparative positioning.

### Schedule

- Individual competitor analysis: On-demand (triggered from UI)
- All competitors: Weekly automatic analysis (Celery task)
- Frequency: Competitors not analyzed in 6+ days are queued

---

## 16. Media Queue

A scheduled photo queue system for visual-first content strategies.

### How It Works

| Feature | Description |
|---------|-------------|
| **Per-Account Queues** | Each social account has its own media queue |
| **Rhythm Scheduling** | Daily or weekly posting rhythm |
| **Drag-Drop Ordering** | Reorder queue items visually |
| **Bulk Upload** | Upload multiple images at once |
| **Auto-Crop** | Automatic image optimization |
| **Auto-Schedule** | Queue automatically calculates next post times |
| **Recalculate** | Adjusting rhythm or adding items auto-recalculates the schedule |

### Queue Item

Each item in the queue:
- Image/media file
- Caption (optional)
- Scheduled post time (auto-calculated from rhythm)
- Order position (drag-drop reorderable)
- Status (pending/published/failed)

### Processing

A Celery task runs every 5 minutes to check for due queue items and publish them.

---

## 17. Campaigns

Cross-channel marketing campaigns that orchestrate content and email together.

### Campaign Model

| Field | Description |
|-------|-------------|
| Name | Campaign title |
| Description | Campaign brief |
| Objective | awareness / engagement / traffic / leads / sales / launch |
| Status | draft → pending_approval → approved → active → paused → completed → cancelled |
| Date Range | Start and end dates |
| Target Platforms | Which social platforms |
| Target Audience | Audience description |
| UTM Tag | Auto-applied to all campaign content |

### Campaign Orchestration

A campaign links together:
- **Content Seeds** — With roles (primary, supporting, follow-up) and sequence ordering
- **Email Campaigns** — With roles (announcement, follow-up, reminder) and ordering
- **Activity Notes** — Comments, status changes, approvals, content additions

### Campaign Performance

The campaign detail view shows aggregated metrics:
- Total posts created and published
- Conversions attributed to the campaign UTM tag
- Revenue generated
- Leads captured
- Email open/click rates
- Activity timeline

---

## 18. Email Marketing

A complete email marketing system built into Kova.

### Email Subscribers

| Field | Description |
|-------|-------------|
| Email | Subscriber email address |
| Name | Display name |
| Source | Where they came from: kova_form, manual, import, social_bio, api, lead_sync |
| Status | active / unsubscribed / bounced / complained |
| Tags | JSON array of tags for segmentation |
| Engagement Score | 0-100 score based on open/click behavior |
| Lead Link | Optional link to a Lead record |

### Email Lists

Named subscriber lists with two modes:
- **Static Lists** — Manually managed subscriber groups
- **Smart Lists** — Auto-populated based on filter rules (tags, engagement score, source, etc.)

### Email Campaigns

| Field | Description |
|-------|-------------|
| Subject | Email subject line |
| Preview Text | Inbox preview snippet |
| HTML / Text Content | Email body (dual format) |
| From Name | Sender display name |
| Reply To | Reply-to address |
| Target List | Which email list to send to |
| Status | draft → scheduled → sending → sent → cancelled |
| A/B Testing | Variant support with `variant_of` self-link |
| AI Generated | Whether content was AI-created |
| Source Post | Optionally repurposed from a social post |

**Campaign Metrics:**
- Total sent, opened, clicked, bounced, unsubscribed

### Email Sequences (Drip Campaigns)

Automated email series triggered by events:

| Trigger | Description |
|---------|-------------|
| `form_submission` | When someone submits a Kova Form |
| `tag_added` | When a tag is added to a subscriber |
| `subscriber_added` | When a new subscriber joins |
| `lead_status_change` | When a lead's status changes |
| `manual` | Manually enrolled |

Each sequence has ordered steps with configurable delays (days/hours) and individual email content.

### Email Delivery

- **Provider:** Resend
- **Webhook Integration:** Delivery status tracking (delivered, opened, clicked, bounced, complained) via HMAC-verified webhooks
- **Unsubscribe:** One-click unsubscribe (CAN-SPAM/GDPR compliant, no login required)
- **Email Types (30+):** Welcome, payment confirmations, plan changes, team invitations, weekly reports, partner notifications, usage warnings, trial expiry sequences, and more

### Trial Expiry Email Sequence

Automated emails at Day 7, Day 3, Day 1, and Day 0 of the trial period.

### Email Log

Every email sent is tracked in the EmailLog with:
- Recipient, type, subject, status
- Timestamps for each status transition (queued → sent → delivered → opened → clicked)
- Provider message ID for tracking
- 30+ email types categorized

---

## 19. Product Catalog

A product management system for businesses that sell products, services, or digital offerings.

### Product Types

| Type | Description |
|------|-------------|
| `product` | Physical product |
| `service` | Service offering |
| `digital` | Digital product/download |

### Product Model

| Field | Description |
|-------|-------------|
| Name | Product name |
| Description | Full description |
| Category | Organized by ProductCategory |
| Offering Type | product / service / digital |
| Price | Fixed price (with currency, default KES) |
| Price Range | Min/max for variable pricing |
| Image | Product image |
| Stock Status | in_stock / low_stock / out_of_stock / made_to_order / unlimited |
| Quantity | Current stock count |
| Low Stock Threshold | When to trigger alerts |
| Is Featured | Featured products get priority in promotions |
| Tags | JSON array for categorization |

### Stock Management

- **Real-time tracking** — Every stock change is logged with reason (manual, sale, restock, adjustment)
- **Auto-alerts** — AI-generated stock intelligence alerts:
  - Low stock warning
  - Out of stock alert
  - Restocked notification
  - Featured product with no content (suggests creating posts)
  - Overstock with no promotion (suggests running a sale)
- **Audit Trail** — Full StockUpdate history per product

### Features

| Feature | Description |
|---------|-------------|
| Catalog View | Filter by status, category, featured, search |
| Quick Stock Update | HTMX-powered inline stock adjustment |
| CSV Import | Bulk import products from CSV or pasted text |
| Category Management | Organize products into categories |
| Revenue Integration | Products link to Conversions for revenue attribution |

---

## 20. Lead Capture & CRM

A lightweight CRM system for capturing and managing leads.

### Lead Model

| Field | Description |
|-------|-------------|
| Name | Lead's name |
| Email | Primary identifier (unique per user) |
| Phone | Phone number |
| Source Type | form_submission / social_dm / social_comment / manual / import / api |
| Source Platform | Which platform the lead came from |
| Source Post | Which post generated the lead |
| Source Form | Which Kova Form captured the lead |
| Status | new → contacted → qualified → converted → lost |
| Priority | high / medium / low |
| Tags | JSON array for segmentation |
| Notes | Free-text notes |
| Metadata | UTM parameters, custom fields |
| Converted At | When the lead converted to a customer |

### Lead Activity Timeline

Every touchpoint is tracked:

| Activity Type | Description |
|--------------|-------------|
| `form_submitted` | Submitted a Kova Form |
| `email_sent` | Sent an email to this lead |
| `opened` | Opened an email |
| `clicked` | Clicked a link in email |
| `social_interaction` | Engaged on social media |
| `note_added` | Team member added a note |
| `status_changed` | Status was updated |
| `phone_called` | Phone call logged |
| `whatsapp_sent` | WhatsApp message sent |
| `tag_added` | Tag was applied |

### Lead Analytics

- Funnel visualization (new → contacted → qualified → converted → lost)
- Leads by source (which channels drive the most leads)
- Leads by priority
- Conversion rate
- Time-to-conversion

---

## 21. Kova Pages (Link-in-Bio)

Custom landing pages that replace Linktree-style tools.

### KovaPage

Public URL: `yourdomain.com/k/your-slug/`

| Field | Description |
|-------|-------------|
| Title | Page title |
| Slug | URL slug (unique) |
| Bio | Short bio/description |
| Avatar | Profile image URL |
| Theme | minimal / bold / gradient / dark / neon / warm |
| Custom Colors | Override theme with custom colors |
| SEO Title/Description | Search engine optimization |
| OG Image | Social sharing image |
| Is Published | Public visibility toggle |

### Kova Links

Each page contains ordered links:

| Link Type | Description |
|-----------|-------------|
| `url` | Standard URL link |
| `social` | Social media profile link |
| `email` | Email link (mailto:) |
| `phone` | Phone link (tel:) |
| `header` | Section header (visual separator) |

Links track: title, URL, icon, featured status, active status, order position, and total clicks.

### Lead Capture Forms

Embeddable forms on Kova Pages (Growth+ plans):

| Form Type | Description |
|-----------|-------------|
| `contact` | General contact form |
| `newsletter` | Newsletter signup |
| `waitlist` | Waitlist/pre-launch signup |
| `booking` | Booking/appointment request |
| `custom` | Custom fields form |

Forms support:
- Toggle fields: name, phone, message
- Custom fields (JSON-defined)
- Custom button text and success message
- Email notification on submission
- UTM tracking on submissions
- Auto-creation of Leads from form submissions

### Analytics

| Metric | Description |
|--------|-------------|
| Link Clicks | Per-link click tracking with referrer, country, device, UTM |
| Page Views | Daily aggregated views and unique visitors |
| Form Submissions | Total submissions per form |

### Plan Limits

| Plan | Pages | Links per Page |
|------|:-----:|:--------------:|
| Starter | 1 | 5 |
| Growth | 3 | 20 |
| Pro | 10 | 100 |
| Agency | 50 | Unlimited |

---

## 22. Teams & Collaboration

### Team Model

| Field | Description |
|-------|-------------|
| Name | Team name |
| Owner | User who created the team |
| Created At | Team creation date |

### Brands

Teams can manage multiple brands:

| Field | Description |
|-------|-------------|
| Name | Brand name |
| Team | Which team owns this brand |
| Description | Brand description |
| Logo | Brand logo |
| Brand Voice | Brand voice description |
| Industry | Industry vertical |

### Team Roles (4)

| Role | Permissions |
|------|------------|
| **Owner** | Full control — manage team, members, brands, billing |
| **Admin** | Manage members, brands, content. Cannot delete team or manage billing |
| **Editor** | Create and edit content, publish posts. Cannot manage members |
| **Viewer** | Read-only access to all content and analytics |

### Team Invitations

- Token-based invitation system
- Invite by email with specified role
- Invitation expiry tracking
- Accept/decline flow

### Team Activity Audit Log

Every team action is logged:
- Member added/removed/role changed
- Brand created/edited/deleted
- Content created/published
- Settings changed

---

## 23. Billing & Payments

### Stripe Integration

| Feature | Description |
|---------|-------------|
| **Checkout** | Stripe-hosted checkout for new subscriptions |
| **Customer Portal** | Self-service plan management, payment methods, invoices |
| **Webhooks** | Real-time subscription status updates |
| **Plan Changes** | Upgrade/downgrade with proration |

### M-Pesa Integration (Kenya)

| Feature | Description |
|---------|-------------|
| **STK Push** | Prompt appears on user's phone to complete payment |
| **Polling** | Automatic status checking after STK push |
| **Webhook Callbacks** | M-Pesa sends payment confirmation |
| **Subscription Tracking** | MpesaPayment model tracks all M-Pesa transactions |

### Billing Models

| Model | Description |
|-------|-------------|
| **BillingEvent** | Audit log of all billing events |
| **MpesaPayment** | M-Pesa transaction records |
| **SubscriptionOverride** | Admin-granted plan overrides (e.g., give a user Pro features for free) |
| **PlanPrice** | Pricing configuration per plan and currency |
| **DiscountCode** | Promotional discount codes |
| **DiscountRedemption** | Tracks which codes have been used |

### Plan Enforcement

The `PlanEnforcementMiddleware` runs on every request and:
1. Checks if the requested URL requires a specific plan
2. If the user's plan doesn't include that feature → redirects to upgrade page
3. Checks trial status — expired trials lose access
4. Admin/staff users bypass all checks

### 14-Day Trial

- All plans start with a 14-day free trial
- Full feature access during trial
- Automated email sequence: Day 7, Day 3, Day 1, Day 0
- After expiry: Plan enforcement blocks premium features

---

## 24. Notifications

### In-App Notifications

| Type | Description |
|------|-------------|
| `post_published` | A post was successfully published |
| `publish_failed` | A post failed to publish |
| `posts_generated` | AI finished generating posts from a seed |
| `agent_action` | An AI agent completed a significant action |
| `system` | System-level notification |

### Notification Preferences

Users can toggle each notification type on/off.

### UI Components

- **Bell Badge** — Unread count in the navigation bar (HTMX auto-refresh)
- **Dropdown** — Recent notifications in a dropdown menu
- **Full Page** — Complete notification history (auto-marks as read)

---

## 25. Help Center

### Structure

20 articles organized across 5 categories:

| Category | Articles |
|----------|---------|
| **Getting Started** | Welcome to Kova, Connecting Platforms, Setting Up Brand Voice |
| **Content & Publishing** | Content Studio, Content Queue, Content Calendar, Media Queue |
| **AI Agents** | Understanding Agents, Configuring Agents, Daily Brief |
| **Analytics & Insights** | Analytics Insights, Competitor Tracking, Engagement Inbox, Kova Pixel, Leads, Kova Links |
| **Account & Billing** | Plans & Pricing, Managing Your Account, Teams & Brands, FAQ |

### Access

- **Authenticated** — Full help center for logged-in users at `/help/`
- **Public** — Public-facing help center at `/learn/` (no login required)
- **Article Analytics** — Tracks which articles are viewed and by whom

---

## 26. Growth Partners Program

A referral and commission program for growing Kova's user base.

### Partner Tiers

| Tier | Clients Required | Commission Rate |
|------|:----------------:|:--------------:|
| **Starter** | 1-25 | 15% |
| **Connector** | 26-75 | 20% |
| **Catalyst** | 76-150 | 25% |
| **Powerhouse** | 150+ | 30% |

### Commission Structure

- Partners earn a percentage of each referred client's subscription revenue
- Commissions are tracked monthly with status: pending → approved → paid
- Commission expires after 24 months per referral
- Profit sharing tiers at 100/200/500+ clients

### Milestone Awards

| Clients | Bonus |
|:-------:|-------|
| 10 | Milestone bonus + extras |
| 25 | Milestone bonus + extras |
| 50 | Milestone bonus + extras |
| 100 | Milestone bonus + extras |
| 250 | Milestone bonus + extras |

### How It Works

1. **Apply** — Public application form at `/partners/apply/`
2. **Review** — Admin reviews and approves/rejects application
3. **Get Referral Code** — Unique code (e.g., `KOVA-JAMES-A3X7`)
4. **Share** — Partner shares code with potential customers
5. **Track** — `ReferralMiddleware` captures referral codes from URL parameters
6. **Earn** — Monthly commissions on referred customer payments

### Anti-Fraud

- Signup IP tracking per referral
- Flagging system for suspicious referrals
- Consecutive paid months tracking (ensures real customers)

### Partner Dashboard

Shows: total earned, pending payouts, active referrals, commission history, milestone progress, tier status.

---

## 27. Admin Dashboard

A comprehensive internal dashboard for platform administrators with 70+ routes.

### Dashboard Sections

| Section | Purpose |
|---------|---------|
| **Overview** | Platform-wide metrics, activity feed, agent health |
| **Users** | User management, export, plan changes, staff toggles, health scoring |
| **Content** | All posts, seeds, failed publishes |
| **Agents** | Agent overview, activity logs, token economics |
| **LLM Config** | Model configuration, task routing, plan models, rate limits, image config |
| **Platforms** | Connected accounts overview |
| **Billing** | Payments, events, subscriptions, pricing config, discounts, bulk grants, overrides |
| **Cost Economics** | Cost analysis dashboard, calculator |
| **Engagement** | Interactions, superfans overview |
| **System** | System health, error log |
| **Logs** | Activity log with CSV export |
| **Analytics** | Content DNA analysis, competitor tracking |
| **Revenue** | Conversions, Shopify stores, conversion journeys |
| **Pixel** | Kova Pixel tracking, events, per-user stats |
| **Teams** | Team management |
| **A/B Tests** | Test management and results |
| **Emails** | Email log, test sending, broadcast |
| **Partners** | Application review, partner management |
| **Help** | Article analytics, view logs |
| **Media Queue** | Queue management, manual processing |
| **Products** | Product listing, stock alerts, update history |
| **Campaigns** | Campaign overview |
| **Memes** | Meme discovery, adaptations |
| **WhatsApp** | Conversations, templates, broadcasts |

### HTMX Auto-Refresh

Dashboard components use HTMX for real-time updates:
- Stat cards refresh automatically
- Activity feed streams new events
- Agent health indicators update live

---

## 28. REST API

Kova provides a REST API for Pro and Agency plan users.

### Authentication

- **Token Auth** — API token in `Authorization: Token <token>` header
- **Session Auth** — Cookie-based (for browser clients)

### Rate Limits

| User Type | Limit |
|-----------|-------|
| Anonymous | 20 requests/minute |
| Authenticated | 120 requests/minute |
| Plan-based | Additional throttling per plan |

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/v1/platforms/` | List connected social accounts |
| GET, POST | `/api/v1/seeds/` | List or create content seeds |
| GET | `/api/v1/seeds/<id>/` | Get a specific seed |
| GET | `/api/v1/posts/` | List posts (filter by status, platform) |
| GET, PUT/PATCH | `/api/v1/posts/<id>/` | Get or update a post |
| GET | `/api/v1/analytics/summary/` | Aggregate analytics |
| GET | `/api/v1/analytics/metrics/<id>/` | Post-specific metrics |
| GET | `/api/v1/agents/` | List agent configurations |
| GET | `/api/v1/agents/actions/` | List recent agent actions |
| GET, POST | `/api/v1/conversions/` | List or create conversion events |

### Serializers

Fully serialized models: SocialAccount, ContentSeed, Post, PostMetric, AgentConfig, AgentAction, Conversion.

---

## 29. Celery Task Schedule

All automated background tasks:

| Task | Frequency | Purpose |
|------|-----------|---------|
| `check_and_publish_due_posts` | Every 5 min | Publish posts that are due |
| `process_queues` (media) | Every 5 min | Process media queue items |
| `refresh_expiring_tokens` | Every 30 min | Refresh platform tokens before expiry |
| `generate_all_daily_briefs` | Every 15 min | Generate/refresh daily briefs |
| `run_engage_cycle` | Every 30 min | Fetch interactions → analyze → generate replies |
| `process_sequence_steps` (WA) | Every 30 min | Send due WhatsApp drip sequence steps |
| `evaluate_ab_tests` | Every hour | Evaluate running A/B tests |
| `discover_trending_memes` | Every 3 hours | Discover trending memes via web search |
| `adapt_memes_for_users` | Every 4 hours | Create brand-adapted meme versions |
| `curate_channel_content` (WA) | Every 6 hours | Auto-curate WhatsApp Channel content |
| `fetch_all_recent_metrics` | Every 6 hours | Pull engagement metrics from all platforms |
| `run_strategy_cycle` | Every 8 hours | Strategist Agent — full strategy cycle |
| `run_daily_research` | Every 12 hours | Research Agent — discover trends |
| `measure_agent_outcomes` | Every 12 hours | Score agent actions from last 7 days |
| `track_audience_growth` | Daily | Snapshot follower counts across all platforms |
| `check_mpesa_subscriptions` | Daily | Verify M-Pesa subscription status |
| `check_trial_expiry_emails` | Daily | Send trial expiry email sequence |
| `generate_status_queue` (WA) | Daily | Generate daily WhatsApp Status content |
| `update_meme_lifecycle` | Daily | Age memes through lifecycle stages |
| `check_stock_alerts` | Daily | Generate stock intelligence alerts |
| `aggregate_daily_wa_analytics` | Daily | Aggregate WhatsApp daily analytics |
| `analyze_all_competitors` | Weekly | Run AI analysis on all active competitors |
| `generate_weekly_wa_digest` | Weekly | Generate WhatsApp weekly performance digest |
| `send_weekly_reports_all` | Weekly | Send performance reports to all users |

---

## 30. Security & Middleware

### Middleware Stack (12 layers)

| # | Middleware | Purpose |
|---|-----------|---------|
| 1 | `SecurityMiddleware` | HTTPS enforcement, HSTS headers |
| 2 | `SessionMiddleware` | 30-day session management |
| 3 | `CommonMiddleware` | URL normalization, content length |
| 4 | `CsrfViewMiddleware` | CSRF protection on all forms |
| 5 | `AuthenticationMiddleware` | User authentication |
| 6 | `MessageMiddleware` | Django messages framework |
| 7 | `XFrameOptionsMiddleware` | Clickjacking protection |
| 8 | `AccountMiddleware` | django-allauth account handling |
| 9 | `HtmxMiddleware` | HTMX request detection |
| 10 | `OnboardingMiddleware` | Forces new users through onboarding |
| 11 | `PlanEnforcementMiddleware` | Gates features by subscription plan |
| 12 | `ReferralMiddleware` | Captures partner referral codes |

### Security Features

| Feature | Implementation |
|---------|---------------|
| **Token Encryption** | Platform OAuth tokens encrypted with Fernet at rest |
| **EXIF Stripping** | All uploaded images have metadata removed |
| **Webhook Verification** | Shopify (HMAC), Stripe (signature), M-Pesa, Resend — all webhooks verified |
| **Rate Limiting** | allauth: 5 login/min, 30/hour. API: 120/min per user. Pixel: 120/min per token |
| **CSRF Protection** | All forms protected. Pixel endpoint exempt (uses token auth) |
| **Email Verification** | Mandatory email verification on registration |
| **Unsubscribe Compliance** | CAN-SPAM/GDPR compliant one-click unsubscribe |
| **Anti-Fraud (Partners)** | IP tracking, flag system, consecutive payment tracking |
| **CORS** | Configured for Kova Pixel cross-origin requests |
| **UUID Primary Keys** | Non-sequential, non-guessable IDs across all models |

### Resilient HTTP Client

All external API calls (platform providers, M-Pesa, email, media uploads) use a shared resilient HTTP client with:
- Automatic retry on transient failures (429, 500-504)
- Exponential backoff with jitter
- Configurable: max retries (3), base delay (1s), max delay (30s), timeout (30s)
- Distinct error types: `TransientAPIError` (retryable) vs `PermanentAPIError` (immediate fail)

---

## 31. Feature Matrix by Plan

A complete reference of every feature and its plan availability:

| Feature | Starter | Growth | Pro | Agency |
|---------|:-------:|:------:|:---:|:------:|
| **Pricing** | KES 299/$2 | KES 999/$7 | KES 1,999/$14 | KES 2,999/$21 |
| **14-Day Trial** | ✅ | ✅ | ✅ | ✅ |
| **Social Accounts** | 1 | 3 | 10 | 25 |
| **Posts/Month** | 15 | 60 | 150 | ∞ |
| **Content Seeds/Month** | 5 | 30 | 60 | ∞ |
| **Create Agent** | ✅ | ✅ | ✅ | ✅ |
| **Analyst Agent** | ✅ | ✅ | ✅ | ✅ |
| **Research Agent** | ❌ | ✅ | ✅ | ✅ |
| **Adapt Agent** | ❌ | ✅ | ✅ | ✅ |
| **Engage Agent** | ❌ | ❌ | ✅ | ✅ |
| **Strategist Agent** | ❌ | ❌ | ✅ | ✅ |
| **AI Image Generation** | ❌ | 50/mo | 100/mo | 500/mo |
| **A/B Testing** | ❌ | ✅ | ✅ | ✅ |
| **Content Calendar** | ✅ | ✅ | ✅ | ✅ |
| **Content Queue** | ✅ | ✅ | ✅ | ✅ |
| **Media Queue** | ✅ | ✅ | ✅ | ✅ |
| **Daily Briefs** | ✅ | ✅ | ✅ | ✅ |
| **Analytics Dashboard** | Basic | Full | Full | Full |
| **Content DNA** | ❌ | ✅ | ✅ | ✅ |
| **Competitor Tracking** | ❌ | 3 competitors | 10 competitors | ∞ |
| **Revenue Dashboard** | ❌ | ✅ | ✅ | ✅ |
| **Kova Pixel** | ❌ | ✅ | ✅ | ✅ |
| **Team Members** | 0 | 0 | 5 | 25 |
| **Brands** | 1 | 1 | 5 | ∞ |
| **Kova Pages** | 1 | 3 | 10 | 50 |
| **Links per Page** | 5 | 20 | 100 | ∞ |
| **Lead Capture Forms** | ❌ | ✅ | ✅ | ✅ |
| **Leads** | 10 | 100 | ∞ | ∞ |
| **Products** | 5 | 30 | 100 | ∞ |
| **Email Subscribers** | 50 | 2,500 | 25,000 | ∞ |
| **Email Campaigns** | ❌ | 5/mo | 20/mo | ∞ |
| **Email Sequences** | ❌ | 2 | 10 | ∞ |
| **Campaigns** | ❌ | 3/mo | 10/mo | ∞ |
| **WhatsApp Suite** | ❌ | ❌ | ✅ | ✅ |
| **Meme Intelligence** | ❌ | ❌ | ✅ | ✅ |
| **REST API** | ❌ | ❌ | ✅ | ✅ |
| **Notifications** | ✅ | ✅ | ✅ | ✅ |
| **Help Center** | ✅ | ✅ | ✅ | ✅ |
| **Stripe Payments** | ✅ | ✅ | ✅ | ✅ |
| **M-Pesa Payments** | ✅ | ✅ | ✅ | ✅ |

---

## Glossary

| Term | Definition |
|------|-----------|
| **Content Seed** | An idea or topic that AI expands into full social media posts |
| **Content DNA** | AI-extracted characteristics of a post (format, hook, tone, CTA, emotion) |
| **Superfan** | A community member who has interacted with your content 16+ times |
| **Kova Page** | A customizable link-in-bio landing page |
| **Kova Pixel** | JavaScript tracking snippet for website conversion attribution |
| **STK Push** | M-Pesa's "Sim Toolkit Push" — a payment prompt sent to the user's phone |
| **Content Pillar** | A core theme or topic area that a brand consistently creates content around |
| **Brand Voice** | The consistent personality and style used in all brand communications |
| **UTM Parameters** | Tracking tags added to URLs (source, medium, campaign, content) for attribution |
| **HTMX** | A JavaScript library that enables dynamic UI updates without full page reloads |
| **Fernet** | A symmetric encryption method used to encrypt stored tokens |
| **OpenRouter** | An AI model routing service that provides access to multiple LLM providers |
| **Drip Sequence** | An automated series of messages sent over time based on triggers |
| **Smart Queue** | AI-distributed scheduling that spaces posts across optimal time slots |

---

*Kova AI — Built in Africa, for the World.*
