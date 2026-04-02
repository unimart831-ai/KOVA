# Kova Agent — Complete System Lifecycle

> The full operating manual for how Kova's 6 AI agents, 9 scheduled tasks, and automated pipelines work together to manage social media for Kenyan MSMEs.

---

## Table of Contents

1. [System Overview](#system-overview)
2. [The 6 AI Agents](#the-6-ai-agents)
3. [Content Creation Flow](#content-creation-flow)
4. [Publishing Pipeline](#publishing-pipeline)
5. [Metrics Collection](#metrics-collection)
6. [Engagement Cycle](#engagement-cycle)
7. [Research & Trends](#research--trends)
8. [Strategy Cycle](#strategy-cycle)
9. [Performance Analysis](#performance-analysis)
10. [Scheduling Optimization](#scheduling-optimization)
11. [Daily Brief](#daily-brief)
12. [Competitor Intelligence](#competitor-intelligence)
13. [Token Maintenance](#token-maintenance)
14. [Billing & Plan Enforcement](#billing--plan-enforcement)
15. [Notification System](#notification-system)
16. [Content DNA System](#content-dna-system)
17. [Complete Task Schedule](#complete-task-schedule)
18. [Status Lifecycles](#status-lifecycles)
19. [Architecture Diagram](#architecture-diagram)

---

## System Overview

Kova Agent is a fully autonomous social media management system. Once a user connects their social accounts and sets their brand profile, Kova runs **24/7** with minimal human intervention.

### Infrastructure

| Component | Technology | Purpose |
|-----------|-----------|---------|
| Web Server | Django 5.1 + Gunicorn | HTTP requests, dashboard UI |
| Task Queue | Celery 5.6 | Async background processing |
| Scheduler | Celery Beat | Periodic task scheduling |
| Message Broker | Redis 7.4 | Task queue + caching |
| Database | PostgreSQL | Persistent data storage |
| LLM Provider | OpenRouter (Gemini 2.0 Flash) | AI reasoning for all agents |
| Hosting | Railway | 4 services: Web, Worker, Beat, Redis |
| Static Files | WhiteNoise | Compressed static serving |
| Social APIs | Meta Graph API v25.0 | Facebook + Instagram integration |

### How It All Connects

```
User Action (seed/approve) ──→ Celery Task Queue ──→ Worker executes task
                                                        │
Celery Beat (scheduler) ────→ Periodic tasks ──────────→ Worker executes task
                                                        │
                                                        ├──→ LLM (OpenRouter)
                                                        ├──→ Platform APIs (Meta, etc.)
                                                        ├──→ Database (read/write)
                                                        └──→ Notifications (to user)
```

---

## The 6 AI Agents

Each agent is a specialized AI module with a distinct role. They share the same LLM (Gemini 2.0 Flash via OpenRouter) but have different system prompts, data inputs, and outputs.

| # | Agent | File | Role | Runs |
|---|-------|------|------|------|
| 1 | **Create Agent** | `apps/agents/create_agent.py` | Generate platform-optimized content from seeds | On-demand (user submits seed) |
| 2 | **Analyst Agent** | `apps/agents/analyst_agent.py` | Analyze performance, extract Content DNA, predict engagement | After each post is created + on-demand |
| 3 | **Research Agent** | `apps/agents/research_agent.py` | Discover trending topics and content opportunities | Every 12 hours |
| 4 | **Adapt Agent** | `apps/agents/adapt_agent.py` | Optimize posting times based on historical performance | When scheduling posts |
| 5 | **Engage Agent** | `apps/agents/engage_agent.py` | Fetch comments/mentions, analyze sentiment, generate/send replies | Every 30 minutes |
| 6 | **Chief Strategist** | `apps/agents/strategist_agent.py` | Orchestrate all agents, create proactive content seeds | Every 8 hours |

### Agent Dependencies

```
Research Agent ──→ discovers trends ──→ feeds into ──→ Strategist
Analyst Agent ──→ performance data ──→ feeds into ──→ Strategist + Create Agent
Engage Agent ──→ sentiment data ──→ feeds into ──→ Strategist
Adapt Agent ──→ optimal times ──→ feeds into ──→ Auto-scheduling
                                                        │
Strategist ──→ creates proactive seeds ──→ Create Agent ──→ generates posts
                                                              │
                                    Analyst extracts DNA ←────┘
```

---

## Content Creation Flow

### Step 1: User Submits a Seed

The user enters an idea in the Content Studio. This creates a `ContentSeed`:

```
ContentSeed {
    idea: "Share tips about saving money for school fees"
    notes: "Focus on M-Pesa savings"
    target_platforms: ["facebook", "instagram"]
    status: "new"
}
```

### Step 2: Create Agent Takes Over

The Celery task `generate_from_seed` fires immediately:

1. **Load context** — User's brand voice, goals, industry, target audience, content pillars
2. **Get performance intelligence** — What Content DNA attributes have worked best in last 30 days (e.g., "question format gets 2.4x more comments")
3. **Get recent angles** — What angles were used recently (to avoid repetition)
4. **For each target platform:**
   - Load platform-specific strategy guide (psychology, winning patterns, CTA style)
   - Build a system prompt with all context
   - Call LLM to generate content
   - Generate image if enabled and budget allows
5. **Create Post objects** with:
   - `status: "draft"`
   - `generated_by_agent: "create"`
   - `ai_angle` — the strategic angle chosen (e.g., "vulnerability hook")
   - `ai_framework` — the content framework used (e.g., "Hook → Value → CTA")

### Step 3: Post-Generation Processing

Immediately after creation, for each generated post:

1. **Extract Content DNA** — Analyst Agent tags the post with structured attributes (format, tone, hook type, etc.)
2. **Predict Engagement** — Analyst Agent scores the post 0-100 based on historical data
3. **Auto-schedule** (if user has `auto_approve` enabled) — Adapt Agent picks the optimal time

### Step 4: User Reviews

Posts appear in the Content Studio as drafts. The user can:
- **Edit** the content
- **Approve** → status changes to `approved`
- **Schedule** → user sets date/time, status changes to `scheduled`
- **Reject** → status changes to `rejected`
- **Post Now** → `scheduled_at` set to now, picked up in 60 seconds

---

## Publishing Pipeline

### The Publisher (Every 60 Seconds)

The `check-and-publish-due-posts` task runs every 60 seconds:

```
1. Find posts where:
   - scheduled_at ≤ now
   - status IN ("approved", "scheduled")

2. For each post: fire publish_post(post_id)
```

### Publish Post Task

This is the core publishing pipeline with built-in resilience:

```
Guard Checks
  └── Status must be "approved" or "scheduled"
  
Set status → "publishing"
  │
  ├── Check token freshness
  │     └── If expiring: refresh via provider
  │     └── If refresh fails: mark FAILED, notify user
  │
  ├── Add UTM tracking to URLs
  │     └── utm_source={platform}&utm_medium=social&utm_campaign=kova_{post_id}
  │
  ├── Extract platform-specific credentials
  │     └── Facebook/Instagram: use page_access_token from metadata
  │
  └── Call provider.publish_post()
        │
        ├── SUCCESS:
        │     ├── status → "published"
        │     ├── Store platform_post_id + platform_post_url
        │     ├── Create notification: "Published to {platform}"
        │     └── Schedule metrics fetch in 1 hour
        │
        └── FAILURE:
              ├── Retry with exponential backoff (60s → 120s → 240s)
              ├── Max 3 retries
              └── After max retries: status → "failed", notify user
```

### Retry Strategy

| Attempt | Wait Time | Total Elapsed |
|---------|-----------|---------------|
| 1st retry | 60 seconds | ~1 min |
| 2nd retry | 120 seconds | ~3 min |
| 3rd retry | 240 seconds | ~7 min |
| Give up | Mark failed | ~7 min |

---

## Metrics Collection

### Immediate Metrics (1 Hour After Publishing)

When a post is published successfully, a `fetch_post_metrics` task is scheduled for 1 hour later:

```
fetch_post_metrics(post_id):
  1. Get published post + its platform_post_id
  2. Get appropriate token (page token for Facebook/Instagram)
  3. Call provider.get_post_metrics()
  4. Store/update PostMetric:
     - impressions, reach, likes, comments, shares, saves, clicks
     - engagement_rate = (likes + comments + shares + saves) / impressions × 100
```

### Bulk Metrics (Every 6 Hours)

The `fetch-all-recent-metrics` task runs every 6 hours:

```
1. Find ALL published posts from the last 7 days with a platform_post_id
2. Queue fetch_post_metrics for each one
```

This means every published post gets its metrics updated **at least 4 times per day** for a full week after publishing.

### Metrics Timeline for a Single Post

| Time | Event |
|------|-------|
| T+0 | Post published |
| T+1h | First metrics fetch (scheduled by publisher) |
| T+6h | Bulk metrics update |
| T+12h | Bulk metrics update |
| T+18h | Bulk metrics update |
| T+24h | Bulk metrics update |
| ... | Every 6h for 7 days |
| T+7d | Falls out of "recent" window, no more auto-updates |

---

## Engagement Cycle

### The Engage Agent (Every 30 Minutes)

The most frequent agent cycle. Runs 48 times per day.

```
run_engage_cycle(user):
  │
  ├── Step 1: FETCH — Get new interactions from platforms
  │     ├── Fetch comments on published posts (last 7 days)
  │     ├── Fetch mentions
  │     └── Create Interaction objects (status: "new")
  │
  ├── Step 2: ANALYZE — Classify every interaction
  │     ├── Detect superfans (repeat engagers: 3+ interactions in 30 days)
  │     ├── LLM batch analysis:
  │     │     ├── Sentiment: positive / neutral / negative
  │     │     ├── Priority: high / medium / low
  │     │     └── Is spam: true / false
  │     └── Update statuses:
  │           ├── Spam → "ignored"
  │           ├── High priority → "flagged"
  │           └── Others → remain "new"
  │
  ├── Step 3: GENERATE — Create AI reply suggestions
  │     ├── Pick interactions needing replies (flagged first, then newest)
  │     ├── For each: generate contextual reply via LLM
  │     │     Context includes: brand voice, original post, sentiment, platform
  │     └── Store in interaction.ai_suggested_reply
  │
  └── Step 4: AUTO-RESPOND — Send replies automatically
        ├── Only if user has auto_engage enabled
        ├── Only for: positive sentiment + comment/reply type
        ├── Send via platform API (using page token for Facebook)
        └── Mark as "ai_replied"
```

### Priority Classification

| Priority | Triggers | Action |
|----------|----------|--------|
| **High** | Complaints, purchase intent, influencer, negative sentiment | Flagged for immediate attention |
| **Medium** | Genuine questions, detailed feedback, conversation starters | Reply generated, queued |
| **Low** | Generic compliments, emoji-only | Reply generated if capacity |
| **Spam** | Spam patterns detected | Automatically ignored |

### Superfan Detection

The Engage Agent tracks repeat engagers over 30 days:

| Interactions | Tier |
|-------------|------|
| 3-5 | Rising |
| 6-15 | Loyal |
| 16+ | Superfan |

Superfans are highlighted in the Daily Brief and Strategy Cycle.

---

## Research & Trends

### Research Agent (Every 12 Hours)

Discovers trending topics and content opportunities relevant to the user's niche.

```
discover_trends(user):
  │
  ├── Gather context:
  │     ├── Company name, industry, brand voice, target audience
  │     ├── Content pillars and goals
  │     └── Recent posts (last 10) — to avoid repetition
  │
  └── LLM generates:
        ├── trending_topics (5-8):
        │     ├── topic — specific topic (not just a hashtag)
        │     ├── relevance — why it matters to this brand
        │     ├── urgency — high / medium / low
        │     ├── suggested_angle — specific content angle
        │     └── platforms — best platforms for this topic
        │
        └── opportunity_briefs (3-4):
              ├── title — catchy brief title
              ├── description — 2-3 sentence brief
              ├── content_type — post / thread / story / reel / carousel
              ├── platform — best platform
              ├── timing — today / this_week / upcoming
              └── why_now — reason this opportunity exists now
```

### Exploring a Trend

When a user clicks "Explore" on a trending topic from their Daily Brief:

```
generate_content_angles(user, topic):
  └── LLM generates 4-6 platform-specific angles:
        ├── angle — specific hook/angle
        ├── platform — twitter / linkedin / instagram / tiktok
        ├── format — tweet / carousel / reel / story / article / thread
        ├── opening_line — draft opening line
        └── why_it_works — brief explanation
```

---

## Strategy Cycle

### Chief Strategist Agent (Every 8 Hours)

The orchestrator. It reads data from ALL other agents and makes coordinated decisions.

```
run_strategy_cycle(user):
  │
  ├── Step 1: GATHER INPUTS from all sources
  │     ├── Research Agent → latest trends (24h)
  │     ├── Analyst Agent → performance data (7d)
  │     ├── Engage Agent → engagement stats:
  │     │     ├── new_interactions_24h
  │     │     ├── unanswered conversations
  │     │     ├── flagged items
  │     │     ├── sentiment breakdown (positive / neutral / negative)
  │     │     └── top_engagers (superfans)
  │     ├── Content Pipeline → current state:
  │     │     ├── pending_approval count
  │     │     ├── scheduled_upcoming count
  │     │     ├── published_this_week count
  │     │     ├── failed_recent count
  │     │     └── seeds_today count
  │     ├── Competitor Intelligence → recent insights
  │     └── User Context → company, industry, brand_voice, goals
  │
  ├── Step 2: MAKE STRATEGIC DECISIONS via LLM
  │     ├── Which trends to act on (aligned with brand)
  │     ├── Content mix recommendations (avoid 3 promos in a row)
  │     ├── Engagement sentiment response (if negative, address it)
  │     ├── Performance patterns (lean into what works)
  │     ├── Competitor gaps (find opportunities they miss)
  │     └── Risk flags and alerts
  │
  │     Output:
  │     ├── content_plan — list of content seed ideas with reasoning
  │     ├── recommendations — 2-4 actionable items with urgency
  │     ├── engagement_insights — summary of engagement patterns
  │     └── alerts — warnings that need attention
  │
  ├── Step 3: EXECUTE — Create proactive content seeds
  │     ├── For each high-priority idea in content_plan:
  │     │     └── ContentSeed.create() → generate_from_seed.delay()
  │     └── This means the Strategist can autonomously create content
  │
  └── Step 4: REPORT — Build strategy report for Daily Brief
        └── Seeds created, recommendations, insights, alerts, superfans
```

### The Autonomy Loop

This is where Kova becomes truly autonomous:

```
Strategist observes data from all agents
  → Decides "we need a post about X trending topic"
  → Creates a ContentSeed automatically
  → Create Agent generates the content
  → Analyst Agent tags it with Content DNA + predicts engagement
  → Adapt Agent schedules it at the optimal time
  → Publisher publishes it
  → Metrics collected automatically
  → Engage Agent handles responses
  → Analyst feeds performance back to next Strategist cycle
  → Strategist learns what worked → makes better decisions
```

---

## Performance Analysis

### Analyst Agent

#### Content DNA Extraction

Immediately after a post is created, the Analyst extracts structured attributes:

```json
{
    "format": "question | statement | story | list | thread | how_to | hot_take | announcement | behind_scenes",
    "tone": "inspirational | educational | humorous | provocative | professional | casual | urgent | empathetic",
    "topic": "brief topic label",
    "has_cta": true/false,
    "has_stats": true/false,
    "has_question": true/false,
    "has_emoji": true/false,
    "has_hashtags": true/false,
    "length": "short | medium | long",
    "hook_type": "statistic | question | bold_claim | story_opener | curiosity_gap | none"
}
```

#### Engagement Prediction

Before a post is published, the Analyst predicts its engagement score (0-100):

1. Pull historical metrics for the same platform (needs at least 3 published posts)
2. Get top 10 posts by engagement and their Content DNA patterns
3. LLM compares the new post against historical winners
4. Returns a score + reasoning

#### Performance Analysis (On-Demand)

```
analyze_performance(user, days=7):
  ├── Aggregate: platform_stats, top_posts, total_engagement, avg_engagement_rate
  └── LLM generates:
        ├── summary — 2-3 sentence overview
        ├── top_insight — single most important finding
        ├── content_dna_insights — "Question posts get 2.4x more comments"
        ├── recommendations — 2-3 specific action items
        └── platform_breakdown — analysis per platform
```

---

## Scheduling Optimization

### Adapt Agent

Analyzes 30 days of posting history to find optimal times:

```
suggest_optimal_times(user):
  │
  ├── Analyze time performance (30 days):
  │     ├── For each platform:
  │     │     ├── hourly_engagement: {0: 3.2%, 1: 2.1%, ..., 23: 5.8%}
  │     │     └── daily_engagement: {"Monday": 4.5%, "Tuesday": 3.2%, ...}
  │
  └── LLM recommends per platform:
        ├── best_hours — [9, 12, 18]
        ├── best_days — ["Tuesday", "Thursday"]
        ├── avoid_hours — [2, 3, 4]
        ├── reasoning — "Your audience peaks at lunch and evening"
        └── confidence — high / medium / low (based on data volume)
```

### Auto-Scheduling

When auto_approve is enabled, the Adapt Agent automatically schedules posts:

1. Get optimal times for the post's target platform
2. Pick the next available optimal hour based on current day/time
3. Set `post.scheduled_at`
4. Change `post.status` to `"scheduled"`

---

## Daily Brief

### Generation (Every 15 Minutes Check)

The `generate-daily-briefs` task checks every 15 minutes:

```
For each user where:
  - onboarding_completed = True
  - daily_brief_time ≤ current time  (user's preferred time has passed)
  - No brief exists for today

Generate their daily brief.
```

### What Goes Into a Brief

The Daily Brief is a compilation of intelligence from ALL agents:

```
_gather_brief_data(user):
  │
  ├── Yesterday's Performance
  │     ├── Published posts count
  │     └── Each post: platform, content preview, engagement metrics
  │
  ├── Current Pipeline State
  │     ├── Posts pending approval
  │     ├── Scheduled for today
  │     └── Failed posts needing attention
  │
  ├── This Week Summary (7 days)
  │     ├── Total posts created
  │     ├── Published count
  │     └── Failed count
  │
  ├── Agent Activity (last 24h)
  │     └── What each agent did
  │
  ├── Analyst Agent Data
  │     ├── Performance analysis
  │     └── Winning Content DNA attributes
  │
  ├── Research Agent Data
  │     ├── Trending topics
  │     └── Opportunity briefs
  │
  ├── Strategist Data
  │     ├── Engagement report (sentiment breakdown)
  │     └── Top engagers / superfans
  │
  └── Competitor Intel
        └── Latest competitor insights
```

### LLM Compiles the Brief

```
Output:
  ├── summary — 3-5 sentences: what happened, what needs attention, what's coming
  ├── trending_topics — relevant trends to act on
  ├── suggested_posts — content ideas with reasoning
  ├── performance_highlight — one standout metric
  ├── engagement_summary — 2-3 sentences about engagement health
  ├── agent_summary — what the AI agents have been doing
  └── competitor_update — competitor moves and opportunities
```

### Delivery

1. Brief saved to database
2. Email sent (if plan includes `email_brief`)
3. Notification: "Your daily brief is ready. Good morning!"
4. Visible on the Briefs dashboard page

---

## Competitor Intelligence

### Adding a Competitor

Users add competitors with: name, website, industry, notes, social handles.

### Analysis Process

```
analyze_competitor(user, competitor):
  │
  ├── Build OUR context:
  │     ├── company, industry, brand_voice, audience, goals
  │     ├── Recent posts + their Content DNA
  │     └── Post count (30 days)
  │
  ├── Build THEIR context:
  │     ├── name, website, industry, handles, platforms
  │     └── Previous analysis (if exists)
  │
  └── LLM competitive analysis:
        ├── summary — executive summary
        ├── content_strategy:
        │     ├── primary_themes
        │     ├── content_formats
        │     ├── posting_frequency
        │     ├── tone / brand voice
        │     ├── best_platforms
        │     └── target_audience
        ├── strengths — 3-5 things they do well
        ├── weaknesses — gaps in their strategy
        ├── opportunities — what we can capitalize on
        ├── competitive_positioning:
        │     ├── our_advantages
        │     └── our_disadvantages
        ├── content_gaps — content they're NOT doing that we could own
        └── actionable_insights — specific moves to make
```

### Schedule

| Trigger | Timing |
|---------|--------|
| Manual | User adds/re-analyzes a competitor |
| Automatic | Weekly task for all active competitors (every 7 days) |

---

## Token Maintenance

### OAuth Token Refresh (Every 30 Minutes)

```
refresh_expiring_tokens():
  │
  ├── Find accounts where:
  │     ├── is_active = True
  │     ├── token_expires_at ≤ now + 30 minutes
  │     └── refresh_token exists
  │
  └── For each account:
        ├── Call provider.refresh_access_token(refresh_token)
        ├── Update: access_token, refresh_token, token_expires_at
        └── Clear last_error
```

### Token Lifecycle (Facebook)

| Token Type | Lifespan | Source |
|-----------|----------|--------|
| Short-lived user token | ~1 hour | OAuth login |
| Long-lived user token | ~60 days | Exchanged during OAuth callback |
| Page access token | Non-expiring* | Extracted from user token during OAuth |

*Page tokens derived from long-lived user tokens don't expire, but the user token they depend on does. When the user token expires after 60 days, the user needs to re-authenticate.

### Publishing Token Logic

For Facebook and Instagram publishing, Kova uses the **page access token** (not the user token):

```
token = account.metadata["pages"][0]["access_token"]  # Page token
page_id = account.metadata["pages"][0]["id"]           # Page ID
```

---

## Billing & Plan Enforcement

### Plan Tiers

| Feature | Jipange (KES 99) | Kazi (KES 500) | Biashara (KES 1,500) | Wakala (KES 5,000) |
|---------|:-:|:-:|:-:|:-:|
| Social accounts | 1 | 3 | 10 | 25 |
| Posts/month | 10 | 50 | Unlimited | Unlimited |
| Seeds/month | 5 | 30 | Unlimited | Unlimited |
| Create Agent | ✅ | ✅ | ✅ | ✅ |
| Analyst Agent | ✅ | ✅ | ✅ | ✅ |
| Research Agent | ❌ | ✅ | ✅ | ✅ |
| Adapt Agent | ❌ | ✅ | ✅ | ✅ |
| Engage Agent | ❌ | ✅ | ✅ | ✅ |
| Strategist | ❌ | ❌ | ✅ | ✅ |
| Daily Brief | ✅ | ✅ | ✅ | ✅ |
| Email Brief | ❌ | ✅ | ✅ | ✅ |
| Competitor Tracking | ❌ | ✅ | ✅ | ✅ |
| AI Image Generation | ❌ | ✅ | ✅ | ✅ |
| Auto-Approve | ❌ | ❌ | ✅ | ✅ |
| Trial | 14 days | 14 days | 14 days | — |

### Plan Enforcement Middleware

The `PlanEnforcementMiddleware` attaches `plan_limits` to every authenticated request and blocks actions that exceed the plan:

- **Platform limit** — Can't connect more social accounts than plan allows
- **Post limit** — Can't create more posts per month than plan allows
- **Seed limit** — Can't create more seeds per month than plan allows
- **Feature gates** — Competitor tracking, engagement inbox blocked on lower plans

### Subscription Lifecycle

```
trialing
  └── [14 days pass]
        ├── [Payment received] → active
        └── [No payment] → past_due
              └── [3-day grace period]
                    ├── [Payment received] → active
                    └── [Grace expires] → expired → downgrade to starter
```

The `check-mpesa-subscriptions` daily task handles trial expiry, subscription expiry, grace periods, and automatic renewals via M-Pesa.

---

## Notification System

### Notification Types

| Type | Trigger | Example Message |
|------|---------|----------------|
| `post_published` | Post published successfully | "Published to Facebook: Tips for saving..." |
| `publish_failed` | Publishing error after retries | "Failed to publish: Token refresh failed" |
| `posts_generated` | Create Agent finished | "3 posts generated from your seed" |
| `agent_action` | An agent took a significant action | "Strategist created 2 new content seeds" |
| `system` | System event | "Your daily brief is ready. Good morning!" |

### Where Notifications Appear

- **Bell icon** in the top navigation bar (unread count badge)
- **Notification dropdown** with message previews
- **Notification page** with full history

---

## Content DNA System

Content DNA is Kova's learning system. It's how the AI agents learn what works for YOUR specific audience.

### The Learning Loop

```
1. CREATE — Create Agent generates content
       ↓
2. TAG — Analyst Agent extracts Content DNA attributes
       ↓
3. PUBLISH — Post goes live on platform
       ↓
4. MEASURE — Metrics collected over 7 days
       ↓
5. CORRELATE — Analyst aggregates: "Which DNA attributes get highest engagement?"
       ↓
6. LEARN — Winning attributes fed back to Create Agent
       ↓
7. IMPROVE — Create Agent biases toward winning patterns
       ↓
   Back to step 1 → continuous improvement
```

### DNA Attributes

| Attribute | Values | Example Insight |
|-----------|--------|----------------|
| format | question, statement, story, list, thread, how_to, hot_take, announcement, behind_scenes | "Question format gets 2.4x more comments" |
| tone | inspirational, educational, humorous, provocative, professional, casual, urgent, empathetic | "Educational tone drives highest shares" |
| hook_type | statistic, question, bold_claim, story_opener, curiosity_gap, none | "Bold claims get 3x more engagement" |
| has_cta | true / false | "Posts with CTAs get 40% more clicks" |
| has_question | true / false | "Asking questions doubles comments" |
| length | short / medium / long | "Short posts outperform long ones by 2x" |

---

## Complete Task Schedule

| Frequency | Task | What It Does |
|-----------|------|-------------|
| **Every 60s** | `check-and-publish-due-posts` | Find posts due for publishing and dispatch them |
| **Every 15m** | `generate-daily-briefs` | Check if users' brief time has passed, generate if needed |
| **Every 30m** | `run-engage-cycle` | Fetch comments/mentions → analyze → generate replies → auto-send |
| **Every 30m** | `refresh-expiring-tokens` | Refresh OAuth tokens expiring within 30 minutes |
| **Every 6h** | `fetch-all-recent-metrics` | Update metrics for all posts published in the last 7 days |
| **Every 8h** | `run-strategy-cycle` | Strategist reads all agents, makes decisions, creates proactive seeds |
| **Every 12h** | `run-daily-research` | Research Agent discovers trends and opportunities |
| **Daily** | `check-mpesa-subscriptions` | Handle trial expiry, renewals, grace periods, downgrades |
| **Weekly** | `analyze-all-competitors` | Run competitive analysis for all active competitors |

### Daily Activity Timeline (Example)

```
00:00  ├── Engage cycle, Token refresh
00:30  ├── Engage cycle, Token refresh
01:00  ├── Engage cycle, Token refresh
       ...
06:00  ├── Strategy cycle + Research cycle + Metrics fetch
06:15  ├── Daily brief check
06:30  ├── Engage cycle, Token refresh
07:00  ├── Daily brief generated (if user's time is 7am)
       ├── Notification: "Your daily brief is ready!"
       ...
12:00  ├── Metrics fetch
14:00  ├── Strategy cycle
       ...
18:00  ├── Research cycle + Metrics fetch
22:00  ├── Strategy cycle
       ...
24:00  ├── Subscription check, Competitor analysis (if weekly)

Throughout the day:
  └── Every 60s: Publisher checks for due posts
  └── Every 30m: Engage cycle (48 times/day)
  └── Every 30m: Token refresh
```

---

## Status Lifecycles

### Post Status

```
              ┌─────── [User rejects] ──────→ rejected
              │
draft ──→ [User approves] ──→ approved ──→ [User sets time] ──→ scheduled
                                  │                                  │
                                  └─── [Post Now] ──────────────────→│
                                                                     │
                                               [Scheduled time arrives]
                                                        │
                                                  publishing
                                                   │      │
                                            [Success]    [Failure]
                                                │           │
                                           published    [Retry ×3]
                                                            │
                                                         failed
```

### ContentSeed Status

```
new → processing → completed
                 → failed
```

### Interaction Status

```
new → [LLM analysis]
       ├── [Spam detected] → ignored
       ├── [High priority] → flagged
       ├── [Reply generated] → ai_suggested_reply populated
       │     ├── [Auto-send success] → ai_replied
       │     └── [User sends manually] → user_replied
       └── [Low priority, no reply needed] → remains "new" or "ignored"
```

### Subscription Status

```
trialing → [Payment] → active → [Expires] → past_due → [Grace 3d] → expired → starter
                          ↑         │
                          └─────────┘  (renewal)
```

---

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                        USER DASHBOARD                       │
│                                                             │
│  Content Studio │ Briefs │ Engage │ Analytics │ Competitors │
└────────────┬────────────────────────────────────────────────┘
             │ HTTP
             ▼
┌─────────────────────────┐     ┌──────────────────────────┐
│     DJANGO WEB SERVER   │     │      CELERY BEAT         │
│     (Gunicorn)          │     │      (Scheduler)         │
│                         │     │                          │
│  Views → Templates      │     │  9 periodic tasks        │
│  Plan Middleware         │     │  Fires tasks on schedule │
│  Auth (allauth)         │     └────────────┬─────────────┘
│  WhiteNoise (static)    │                  │
└────────────┬────────────┘                  │
             │                               │
             ▼                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      REDIS (Broker)                         │
│                   Task Queue + Results                      │
└────────────────────────────┬────────────────────────────────┘
                             │
                             ▼
┌─────────────────────────────────────────────────────────────┐
│                    CELERY WORKER                            │
│                                                             │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐      │
│  │ Create   │ │ Analyst  │ │ Research │ │ Adapt    │      │
│  │ Agent    │ │ Agent    │ │ Agent    │ │ Agent    │      │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘      │
│       │             │            │             │            │
│  ┌────┴─────┐ ┌────┴──────────┐                            │
│  │ Engage   │ │ Strategist    │                            │
│  │ Agent    │ │ (Orchestrator)│                            │
│  └────┬─────┘ └────┬──────────┘                            │
│       │             │                                       │
│       ▼             ▼                                       │
│  ┌──────────────────────────────┐                          │
│  │  OpenRouter API              │                          │
│  │  (Gemini 2.0 Flash LLM)     │                          │
│  └──────────────────────────────┘                          │
│       │                                                     │
│       ▼                                                     │
│  ┌──────────────────────────────┐                          │
│  │  Platform Providers          │                          │
│  │  Facebook │ Instagram │ ...  │                          │
│  └──────────────────────────────┘                          │
└─────────────────────────────────────────────────────────────┘
             │
             ▼
┌─────────────────────────────────────────────────────────────┐
│                    POSTGRESQL DATABASE                       │
│                                                             │
│  Users │ Posts │ Metrics │ Interactions │ Briefs │ Seeds    │
│  SocialAccounts │ Competitors │ Subscriptions │ Notifications│
└─────────────────────────────────────────────────────────────┘
```

---

## Key Numbers

| Metric | Value |
|--------|-------|
| Background tasks per day | ~200+ (48 engage cycles + metrics + publishing + briefs + strategy + research) |
| Post check frequency | Every 60 seconds |
| Engagement response time | ≤ 30 minutes (fetch + analyze + reply) |
| Metrics tracking window | 7 days per post |
| Token refresh window | 30 minutes before expiry |
| Content DNA learning cycle | Continuous (every post improves the model) |
| Strategy replanning | 3 times per day (every 8 hours) |
| Competitor analysis | Weekly per competitor |

---

*Last updated: July 2025*
*Kova Agent v1.0 — Built for Kenyan MSMEs*
