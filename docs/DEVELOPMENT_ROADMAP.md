# ============================================================================
# KOVA AGENT — DEVELOPMENT ROADMAP
# ============================================================================
# Autonomous Social Intelligence Platform
# "Your social media runs itself. You stay in control."
#
# This document is the SINGLE SOURCE OF TRUTH for building Kova Agent.
# Every decision, every sprint, every feature traces back to here.
# Last Updated: April 6, 2026
# ============================================================================


# TABLE OF CONTENTS
# ─────────────────
# 1. PRODUCT VISION & IDENTITY
# 2. TARGET USERS & PAIN POINTS
# 3. TECHNOLOGY STACK
# 4. SYSTEM ARCHITECTURE
# 5. DATA MODELS (Core Entities)
# 6. AGENT SYSTEM DESIGN
# 7. PLATFORM INTEGRATIONS
# 8. FEATURE MAP (Complete)
# 9. BUILD PHASES (Detailed Sprint Plans)
# 10. UI/UX PRINCIPLES & KEY SCREENS
# 11. AUTHENTICATION & SECURITY
# 12. PRICING & BILLING
# 13. TESTING STRATEGY
# 14. DEPLOYMENT & INFRASTRUCTURE
# 15. METRICS & SUCCESS CRITERIA
# 16. RISKS & MITIGATIONS
# 17. FUTURE VISION (Post-Launch)


# ============================================================================
# 1. PRODUCT VISION & IDENTITY
# ============================================================================

## 1.1 Name
Kova Agent

## 1.2 Tagline
"Your social media runs itself. You stay in control."

## 1.3 Category
Autonomous Social Intelligence — a new category.
NOT a social media scheduler. NOT a dashboard. NOT a content generator.
Kova is a CREW of AI agents that operates your entire social media presence.

## 1.4 Core Philosophy
- The user is the STRATEGIST, not the operator
- AI agents do the work. Humans approve, override, and set direction
- 5 minutes a day is the target interaction time
- Every insight leads to an ACTION, not a chart
- The system gets smarter the longer you use it (compounding intelligence)

## 1.5 What Makes Kova Different From Everything Else
| Existing Tools                  | Kova Agent                                     |
|---------------------------------|------------------------------------------------|
| AI writes when you click        | AI agents work 24/7 proactively                |
| You decide what/when/where      | Agents decide — you approve or override         |
| Calendar + Timer                | Autonomous pipeline (research → create → post → engage → learn) |
| Analytics dashboard             | Decisions delivered to you, not data            |
| Same content cross-posted       | Platform-native content from single seed idea   |
| Post and ghost                  | Engage Agent maintains conversations for you    |
| Generic "best times"            | YOUR audience's specific behavioral patterns    |

## 1.6 The Uniqueness Test
Nobody should be able to say "Kova is like [X]."
- Not like Buffer (Buffer is a timer — Kova is autonomous)
- Not like Hootsuite (Hootsuite is a dashboard — Kova has no dashboard, it has a Daily Brief)
- Not like Postiz (Postiz schedules — Kova's agents operate your entire presence)
- Not like Jasper (Jasper generates on demand — Kova generates proactively and posts)
- Not like a VA (VAs do what you say — Kova decides what needs doing)


# ============================================================================
# 2. TARGET USERS & PAIN POINTS
# ============================================================================

## 2.1 Primary Personas

### Persona 1: Solo Creator ("Alex")
- Full-time content creator, 10K-100K followers
- Active on 3-5 platforms
- Spends 2-3 hours/day on social media management
- Pain: "I spend more time managing posts than creating value"
- Kova Value: Reduces daily management to 5 minutes. Agents handle everything else.
- Plan: Growth ($79/mo)

### Persona 2: Small Business Owner ("Maria")
- Runs a bakery/consultancy/e-commerce store
- Knows social media matters but has no time
- Currently posts inconsistently or pays a freelancer $500+/mo
- Pain: "I can't afford a social media team but I need consistent presence"
- Kova Value: An AI team for $79/mo that does what a $500/mo freelancer does, 24/7.
- Plan: Growth ($79/mo)

### Persona 3: Marketing Team Lead ("James")
- Manages social for a mid-size brand
- Team of 2-3 people
- Uses Hootsuite/Sprout Social at $200-400/mo/seat
- Pain: "We have tools but we still spend 15+ hours/week on execution"
- Kova Value: Agents automate 80% of execution. Team focuses on strategy.
- Plan: Pro ($149/mo)

### Persona 4: Agency Owner ("Priya")
- Manages 10-30 client accounts
- Needs white-label, multi-brand management
- Pain: "Scaling means hiring more people. Margins shrink."
- Kova Value: Each client gets their own AI crew. Scale without headcount.
- Plan: Agency ($299/mo)

## 2.2 Universal Pain Points (All Personas)
1. Too much time spent on repetitive execution (not strategy)
2. Content doesn't perform — no predictive insight before posting
3. Engagement drops because nobody responds to comments/DMs consistently
4. Analytics exist but are never acted upon
5. Cross-posting produces generic, algorithm-punished content
6. Trend detection is always too late
7. Can't justify the cost of larger tools (Hootsuite $199/seat)


# ============================================================================
# 3. TECHNOLOGY STACK
# ============================================================================

## 3.1 Backend
- Python 3.12+ ✅ (Python 3.12.8)
- Django 5.x ✅ (Django 5.1.15)
- ~~Django REST Framework~~ — Not needed yet. HTMX returns HTML partials, agents call services directly
- Celery ✅ (configured, Redis broker on Railway)
- Redis ✅ (Railway Redis plugin — cache, Celery broker, Channels backend)
- PostgreSQL 16+ ✅ (Railway PostgreSQL plugin)
- ~~Django Channels~~ — Not needed yet. HTMX polling covers real-time needs for now
- django-allauth ✅ (authentication — registration, login, email verification, social OAuth)
- WhiteNoise ✅ (static file serving in production)
- gunicorn ✅ (WSGI server via Railway Procfile)

## 3.2 Frontend
- Django Templates (server-rendered HTML — fast, SEO-friendly)
- HTMX (dynamic interactions without JavaScript frameworks)
- Alpine.js (lightweight client-side interactivity: modals, dropdowns, toggles)
- Tailwind CSS (utility-first styling — responsive, fast to build)
- No build step needed for HTMX/Alpine.js (CDN or static files)

## 3.3 AI & Agent Layer
- ~~LangGraph / CrewAI~~ — **Decision: Custom agent layer** (simpler, no heavy dependencies)
  - Each agent is a Python module in `apps/agents/` (e.g., `analyst_agent.py`, `research_agent.py`, `adapt_agent.py`)
  - Agents use `apps/agents/llm.py` — a shared LLM wrapper calling OpenRouter
  - Agent actions logged to `AgentAction` model for full audit trail
  - Agent configs stored in `AgentConfig` model (custom instructions, autonomy level)
- **OpenRouter API** ✅ — primary LLM gateway (supports multiple models via single API)
  - Current model: `google/gemini-2.0-flash-001` (fast, cost-effective)
  - Can switch to any OpenRouter-supported model (GPT-4o, Claude, Llama, etc.)
- User can choose their LLM provider (future: open-source models)

## 3.4 Data & Memory
- PostgreSQL ✅ (structured data: users, posts, schedules, analytics)
- ~~pgvector~~ — Not needed yet. Content DNA stored as JSONField on Post model
- ~~Redis~~ — Using Django LocMemCache. Redis planned for production scaling

## 3.5 External Services
- Social platform OAuth + APIs (see Section 7)
- Resend ✅ (transactional email via SMTP relay: 19 email types, delivery/open/click tracking via webhooks)
- Stripe ✅ (subscription billing: Checkout, Portal, Webhooks)
- M-Pesa ✅ (STK Push for KES payments)
- S3-compatible storage (media files: images, videos for posts)
  Options: AWS S3, Cloudflare R2 (cheaper), MinIO (self-hosted)
- Sentry ✅ (error monitoring: Django + Celery integrations, release tracking)

## 3.6 Development Tools
- Git + GitHub ✅ (version control — github.com/kakumagreens-ai/KOVA_AGENT)
- ~~Docker + Docker Compose~~ — Using Railway Nixpacks instead (auto-detects Python, zero config)
- Django test framework (testing — planned)
- ~~Ruff / pre-commit~~ — Not configured yet. Manual code review for now

## 3.7 Deployment
- **Railway** ✅ (fully deployed — https://kovaagent-production.up.railway.app/)
  - Nixpacks build (auto-detect Python → install deps → collectstatic)
  - Procfile → start.sh → gunicorn
  - PostgreSQL plugin (DATABASE_PUBLIC_URL)
  - Environment variables managed in Railway dashboard
- ~~Docker containers~~ — Not needed. Railway Nixpacks handles build/deploy
- ~~CI/CD: GitHub Actions~~ — Manual `git push` + Railway auto-deploy from main branch
- Monitoring: Django error pages + Railway logs (Sentry planned)


# ============================================================================
# 4. SYSTEM ARCHITECTURE
# ============================================================================

## 4.1 High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER BROWSER                             │
│       Django Templates + HTMX + Alpine.js + Tailwind CSS         │
└──────────────────────────────┬──────────────────────────────────┘
                               │ HTTP / WebSocket
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│                        DJANGO APPLICATION                        │
│                                                                  │
│  ┌──────────┐ ┌──────────┐ ┌───────────┐ ┌───────────────────┐  │
│  │  Views   │ │   API    │ │  Channels │ │   Admin Panel     │  │
│  │ (HTMX)  │ │  (DRF)   │ │(WebSocket)│ │  (Django Admin)   │  │
│  └────┬─────┘ └────┬─────┘ └─────┬─────┘ └───────────────────┘  │
│       │             │             │                               │
│  ┌────▼─────────────▼─────────────▼──────────────────────────┐   │
│  │                    SERVICE LAYER                            │   │
│  │  AccountService | PostService | AgentService | Analytics   │   │
│  └────────────────────────┬──────────────────────────────────┘   │
│                           │                                      │
│  ┌────────────────────────▼──────────────────────────────────┐   │
│  │                     ORM / MODELS                           │   │
│  └────────────────────────┬──────────────────────────────────┘   │
└───────────────────────────┼──────────────────────────────────────┘
                            │
              ┌─────────────┼─────────────┐
              ▼             ▼             ▼
       ┌────────────┐ ┌─────────┐ ┌──────────────┐
       │ PostgreSQL │ │  Redis  │ │  S3 Storage  │
       │ + pgvector │ │         │ │  (media)     │
       └────────────┘ └────┬────┘ └──────────────┘
                           │
                    ┌──────▼──────┐
                    │   CELERY    │
                    │  WORKERS    │
                    └──────┬──────┘
                           │
              ┌────────────┼────────────────┐
              ▼            ▼                ▼
     ┌──────────────┐ ┌────────┐  ┌──────────────────┐
     │ AGENT SYSTEM │ │SOCIAL  │  │  SCHEDULED TASKS  │
     │ (LangGraph/  │ │MEDIA   │  │  (Periodic beats) │
     │  CrewAI)     │ │APIs    │  │                    │
     └──────────────┘ └────────┘  └──────────────────┘
```

## 4.2 Request Flow Examples

### User approves a post from Daily Brief:
1. User clicks "Approve" button (HTMX sends POST to Django)
2. Django view calls PostService.approve(post_id)
3. PostService creates Celery task: publish_post.delay(post_id)
4. Celery worker picks up task, calls platform API, publishes post
5. Worker updates post status in DB
6. Django Channels sends WebSocket message: "Post published ✅"
7. HTMX updates the post card in-place (no page reload)

### Agent generates Daily Brief (automated, 6 AM):
1. Celery Beat triggers daily_brief_generation task
2. Task calls AgentService.generate_daily_brief(user_id)
3. Research Agent checks trends → passes to Create Agent
4. Create Agent generates content queue for the day
5. Analyst Agent scores each piece (predicted engagement)
6. Chief Strategist compiles brief
7. Brief saved to DB + email notification sent to user
8. User opens Kova → sees Daily Brief ready

### Agent handles incoming comment:
1. Webhook/polling detects new comment on user's post
2. Celery task created: process_incoming_engagement
3. Engage Agent evaluates: Can I handle this? (confidence threshold)
4. HIGH confidence (>85%): Draft reply, auto-send (logged for user review)
5. MEDIUM confidence (50-85%): Draft reply, flag for approval
6. LOW confidence (<50%): Flag for user's personal reply
7. User sees flagged items in Daily Brief

## 4.3 Django App Structure

```
kova_agent/
├── manage.py
├── config/                    # Project settings
│   ├── settings/
│   │   ├── base.py           # Shared settings
│   │   ├── development.py    # Dev overrides
│   │   └── production.py     # Prod overrides
│   ├── urls.py               # Root URL config
│   ├── celery.py             # Celery app config
│   ├── asgi.py               # ASGI for Channels
│   └── wsgi.py               # WSGI fallback
│
├── apps/
│   ├── accounts/              # User management
│   │   ├── models.py         # User, UserProfile, Subscription
│   │   ├── views.py          # Registration, login, onboarding
│   │   ├── forms.py
│   │   ├── urls.py
│   │   └── templates/accounts/
│   │
│   ├── platforms/             # Social platform connections
│   │   ├── models.py         # SocialAccount, PlatformToken
│   │   ├── views.py          # OAuth callback handlers
│   │   ├── services.py       # Platform API wrappers
│   │   ├── providers/        # Per-platform logic
│   │   │   ├── base.py       # Abstract provider
│   │   │   ├── instagram.py
│   │   │   ├── x_twitter.py
│   │   │   ├── linkedin.py
│   │   │   ├── tiktok.py
│   │   │   └── facebook.py
│   │   └── urls.py
│   │
│   ├── content/               # Posts, content pipeline
│   │   ├── models.py         # Post, ContentSeed, ContentDNA, MediaAsset
│   │   ├── views.py          # Content queue, calendar, approval
│   │   ├── services.py       # Content CRUD, publishing logic
│   │   ├── tasks.py          # Celery tasks: publish, schedule
│   │   └── templates/content/
│   │
│   ├── agents/                # AI Agent system
│   │   ├── models.py         # AgentRun, AgentMemory, AgentConfig
│   │   ├── services.py       # AgentService (interface to agent layer)
│   │   ├── tasks.py          # Celery tasks for agent operations
│   │   ├── crew/             # Agent definitions
│   │   │   ├── chief.py      # Chief Strategist (orchestrator)
│   │   │   ├── research.py   # Research Agent
│   │   │   ├── create.py     # Create Agent
│   │   │   ├── adapt.py      # Adapt Agent
│   │   │   ├── engage.py     # Engage Agent
│   │   │   └── analyst.py    # Analyst Agent
│   │   ├── tools/            # Tools agents can use
│   │   │   ├── search.py     # Web/trend search
│   │   │   ├── publish.py    # Post to platforms
│   │   │   ├── analytics.py  # Read analytics data
│   │   │   └── memory.py     # Read/write agent memory
│   │   └── prompts/          # System prompts for each agent
│   │       ├── research.md
│   │       ├── create.md
│   │       ├── adapt.md
│   │       ├── engage.md
│   │       └── analyst.md
│   │
│   ├── analytics/             # Performance tracking
│   │   ├── models.py         # PostMetric, AudienceInsight, ContentDNAScore
│   │   ├── views.py          # Insights views (not dashboards — decision briefs)
│   │   ├── services.py       # Metric collection, prediction model
│   │   └── tasks.py          # Periodic metric fetching
│   │
│   ├── briefs/                # Daily Brief system
│   │   ├── models.py         # DailyBrief, BriefItem
│   │   ├── views.py          # Brief display + interaction
│   │   ├── services.py       # Brief generation logic
│   │   ├── tasks.py          # Scheduled brief generation
│   │   └── templates/briefs/
│   │
│   ├── engage/                # Community & relationship management
│   │   ├── models.py         # Conversation, AudienceMember, RelationshipScore
│   │   ├── views.py          # Inbox, flagged replies
│   │   ├── services.py       # Engagement processing
│   │   └── tasks.py          # Monitor mentions, process comments
│   │
│   └── billing/               # Subscription & payments
│       ├── models.py         # Plan, Subscription, Invoice
│       ├── views.py          # Pricing page, checkout, portal
│       ├── services.py       # Stripe integration
│       └── webhooks.py       # Stripe webhook handler
│
├── templates/                 # Global templates
│   ├── base.html             # Master layout (nav, sidebar, notifications)
│   ├── components/           # Reusable HTMX/Alpine components
│   │   ├── post_card.html
│   │   ├── agent_status.html
│   │   ├── approval_button.html
│   │   ├── notification.html
│   │   └── modal.html
│   ├── layouts/
│   │   ├── app.html          # Logged-in app layout
│   │   └── marketing.html    # Public pages layout
│   └── pages/
│       ├── landing.html       # Marketing homepage
│       ├── pricing.html
│       └── about.html
│
├── static/
│   ├── css/
│   │   └── input.css         # Tailwind source
│   ├── js/
│   │   ├── htmx.min.js
│   │   └── alpine.min.js
│   └── images/
│
├── docs/                      # This folder
│   └── DEVELOPMENT_ROADMAP.md # This file
│
├── docker-compose.yml
├── Dockerfile
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── .env.example
├── .gitignore
└── README.md
```


# ============================================================================
# 5. DATA MODELS (Core Entities)
# ============================================================================

## 5.1 accounts app

### User (extends Django AbstractUser)
- email (unique, primary login)
- full_name
- timezone
- onboarding_completed (bool)
- daily_brief_time (time — when to generate brief, default 6:00 AM)
- created_at, updated_at

### UserProfile
- user (OneToOne → User)
- brand_voice_description (text — "professional but warm, uses humor...")
- brand_voice_samples (JSON — array of past post examples for voice training)
- industry (choice field)
- goals (JSON — array: "grow_followers", "drive_traffic", "build_community", etc.)
- target_audience_description (text)
- avatar (image)
- tone_attributes (JSON — array of selected tones from 12-option grid: confident, witty, bold, inspirational, etc.)
- content_language (choice field — 11 options: English, Swahili, Sheng, Pidgin, French, etc.)
- key_offerings (JSON — array of products/services the business sells)
- brand_restrictions (text — guardrails: topics, words, and approaches the AI must avoid)
- platform_priority (JSON — ordered platform preferences)

### Subscription
- user (OneToOne → User)
- plan (FK → Plan)
- stripe_subscription_id
- status (active, trialing, past_due, canceled)
- current_period_start, current_period_end
- trial_end

## 5.2 platforms app

### SocialAccount
- user (FK → User)
- platform (choice: instagram, x_twitter, linkedin, tiktok, facebook, youtube, pinterest, threads, bluesky, reddit)
- platform_user_id (platform's user ID)
- platform_username
- display_name
- avatar_url
- access_token (encrypted)
- refresh_token (encrypted)
- token_expires_at (datetime)
- is_active (bool)
- connected_at
- metadata (JSON — platform-specific data)

### PlatformMetric (daily snapshot)
- social_account (FK → SocialAccount)
- date
- followers_count
- following_count
- posts_count
- engagement_rate
- impressions
- reach
- metadata (JSON)

## 5.3 content app

### ContentSeed
- user (FK → User)
- raw_input (text — user's rough idea, voice memo transcript, etc.)
- input_type (choice: text, voice_memo, url, image)
- status (draft, processing, expanded, archived)
- created_at

### Post
- user (FK → User)
- content_seed (FK → ContentSeed, nullable — can be agent-generated)
- social_account (FK → SocialAccount)
- content_text (text)
- media_assets (M2M → MediaAsset)
- post_type (choice: text, image, video, carousel, story, reel, thread)
- status (choice: draft, ai_generated, pending_approval, approved, scheduled, publishing, published, failed)
- scheduled_at (datetime)
- published_at (datetime)
- platform_post_id (returned after publishing)
- platform_post_url
- predicted_engagement_score (float, 0-100 — from Analyst Agent)
- content_dna (JSON — hook_type, visual_style, topic_category, cta_type, emotion, length_class)
- agent_run (FK → AgentRun, nullable — which agent run created this)
- is_auto_generated (bool)
- created_at, updated_at

### MediaAsset
- user (FK → User)
- file (file field — S3)
- media_type (image, video, gif)
- alt_text
- ai_generated (bool)
- created_at

## 5.4 agents app

### AgentConfig
- user (FK → User)
- agent_type (choice: research, create, adapt, engage, analyst, chief)
- is_enabled (bool)
- auto_approve (bool — if True, agent can act without user approval)
- confidence_threshold (float — 0.0 to 1.0, for auto-actions)
- custom_instructions (text — user overrides for this agent)
- llm_provider (choice: openai, anthropic)
- llm_model (char — e.g., "gpt-4o", "claude-sonnet")
- metadata (JSON)

### AgentRun
- user (FK → User)
- agent_type (choice field)
- status (choice: pending, running, completed, failed)
- input_data (JSON)
- output_data (JSON)
- tokens_used (int)
- cost_usd (decimal)
- duration_seconds (float)
- error_message (text, nullable)
- started_at, completed_at

### AgentMemory
- user (FK → User)
- agent_type (choice field)
- memory_type (choice: short_term, long_term, episodic)
- content (text)
- embedding (vector field — pgvector)
- relevance_score (float)
- created_at
- expires_at (nullable — short-term memories expire)

## 5.5 analytics app

### PostMetric
- post (FK → Post)
- fetched_at (datetime)
- likes (int)
- comments (int)
- shares (int)
- saves (int)
- impressions (int)
- reach (int)
- engagement_rate (float)
- clicks (int)
- metadata (JSON — platform-specific metrics)

### ContentDNAScore
- user (FK → User)
- dna_attribute (char — e.g., "hook_type:question")
- avg_engagement_rate (float)
- sample_size (int)
- last_calculated (datetime)
- NOTE: This tracks which content "genes" perform best for this user

## 5.6 briefs app

### DailyBrief
- user (FK → User)
- date
- status (generating, ready, viewed, expired)
- summary_text (text — AI-generated brief summary)
- generated_at
- viewed_at (nullable)

### BriefItem
- brief (FK → DailyBrief)
- item_type (choice: performance_summary, trend_alert, content_queue, engagement_flag, strategy_insight, competitor_alert)
- title (char)
- body (text)
- priority (choice: high, medium, low)
- action_required (bool)
- action_type (choice: approve_post, reply_comment, review_strategy, none)
- related_post (FK → Post, nullable)
- metadata (JSON)
- order (int)

## 5.7 engage app

### AudienceMember
- user (FK → User)
- platform (choice)
- platform_user_id
- username
- display_name
- relationship_score (float — 0-100, calculated from interaction frequency/sentiment)
- is_superfan (bool)
- total_interactions (int)
- last_interaction_at
- notes (text — agent observations: "frequently asks about baking tips")
- metadata (JSON)

### Conversation
- user (FK → User)
- audience_member (FK → AudienceMember)
- social_account (FK → SocialAccount)
- conversation_type (choice: comment, dm, mention, reply)
- platform_conversation_id
- status (choice: new, agent_handling, flagged_for_user, resolved)
- agent_confidence (float)
- agent_draft_reply (text, nullable)
- user_reply (text, nullable)
- resolved_at


# ============================================================================
# 6. AGENT SYSTEM DESIGN
# ============================================================================

## 6.1 Agent Architecture Principles
1. Each agent has a SINGLE clear responsibility
2. Agents communicate through SHARED STATE (database), not direct calls
3. All agent actions are LOGGED (AgentRun) for transparency and billing
4. Human-in-the-loop is a FIRST-CLASS feature, not an afterthought
5. Every agent has configurable AUTONOMY LEVEL per user
6. Agents use TOOLS (functions) to interact with the outside world
7. Agent memory persists across runs (long-term learning)

## 6.2 Agent Definitions

### CHIEF STRATEGIST (Orchestrator)
- Role: Coordinates all other agents, resolves conflicts, prioritizes work
- Trigger: Daily (generates daily plan) + on-demand (when events need coordination)
- Inputs: All agent outputs, user goals, current performance data
- Outputs: Task assignments for other agents, daily brief compilation
- Tools: read_agent_outputs, assign_tasks, compile_brief
- Autonomy: Always runs. User doesn't interact directly.

### RESEARCH AGENT (The Scout)
- Role: Find what's happening in user's niche, spot trends, track competitors
- Trigger: Every 6 hours + on-demand
- Inputs: User's industry, keywords, competitor accounts, past trending topics
- Outputs: Opportunity briefs, trending topic alerts, competitor move reports
- Tools: web_search, social_search, trend_detection, competitor_analysis
- Autonomy: Full auto. Research doesn't publish anything.
- Memory: Remembers past trends to avoid repeating alerts

### CREATE AGENT (The Writer/Designer)
- Role: Transform seed ideas into platform-native content
- Trigger: On content_seed creation + daily queue generation
- Inputs: Content seed, user's brand voice, target platform, content DNA insights
- Outputs: Ready-to-publish posts with text + media suggestions
- Tools: generate_text, suggest_media, format_for_platform, predict_engagement
- Autonomy: Creates drafts. Publishing requires approval (configurable).
- Memory: Learns user's voice from corrections and which content performs best

### ADAPT AGENT (The Optimizer)
- Role: Determine optimal timing, adjust schedule based on real-time signals
- Trigger: Every 2 hours + on new content in queue
- Inputs: User's audience activity patterns, current queue, trending signals, platform data
- Outputs: Scheduled times for posts, queue reordering
- Tools: analyze_audience_activity, get_trending_now, reorder_queue, set_schedule
- Autonomy: Can adjust timing freely. Moving a post to a different day = needs approval.
- Memory: Remembers timing patterns that worked/failed

### ENGAGE AGENT (The Relationship Manager)
- Role: Monitor and manage community interactions
- Trigger: Polling/webhooks for new comments, DMs, mentions
- Inputs: Incoming engagement, audience member history, brand voice, conversation context
- Outputs: Reply drafts, auto-replies, flagged items for user
- Tools: read_comments, draft_reply, send_reply, update_relationship_score, flag_for_user
- Autonomy: Configurable. Default: auto-reply to simple comments (>85% confidence), flag complex ones.
- Memory: Remembers each audience member's history, preferences, past conversations

### ANALYST AGENT (The Strategist)
- Role: Turn data into decisions, predict content performance, optimize strategy
- Trigger: After each post gets 4+ hours of data + weekly deep analysis
- Inputs: Post metrics, content DNA, audience data, historical performance
- Outputs: Engagement predictions, strategy adjustments, content DNA insights
- Tools: fetch_metrics, calculate_content_dna, predict_engagement, generate_strategy_update
- Autonomy: Full auto for analysis. Strategy changes presented as recommendations.
- Memory: Builds progressively deeper model of what works for this user

## 6.3 Agent Communication Flow

```
User drops a seed idea: "AI is changing marketing"
         │
         ▼
CHIEF STRATEGIST receives seed
  ├── Assigns to RESEARCH AGENT: "Find current angles on this topic"
  │         │
  │         ▼ Returns: "Top 3 angles: [privacy concerns], [small biz adoption], [ROI data]"
  │
  ├── Assigns to CREATE AGENT: "Generate posts for all connected platforms using angle #2"
  │         │
  │         ▼ Returns: LinkedIn article draft, Twitter thread, Instagram carousel outline
  │
  ├── Assigns to ANALYST AGENT: "Score these drafts"
  │         │
  │         ▼ Returns: LinkedIn 87/100, Twitter 72/100, Instagram 91/100
  │
  ├── Assigns to ADAPT AGENT: "Schedule these optimally"
  │         │
  │         ▼ Returns: LinkedIn Tue 9:15AM, Twitter Tue 12:30PM, Instagram Wed 6PM
  │
  └── Compiles into Daily Brief → Presented to user for approval
```

## 6.4 Human-in-the-Loop Levels

Users set autonomy per agent:

| Level | Name          | Behavior                                              |
|-------|---------------|-------------------------------------------------------|
| 1     | Manual        | Agent suggests. User must approve everything.         |
| 2     | Guided        | Agent acts on high-confidence tasks. Flags the rest.  |
| 3     | Autonomous    | Agent handles everything. User reviews daily log.     |

Default for new users: Level 2 (Guided) — builds trust gradually.


# ============================================================================
# 7. PLATFORM INTEGRATIONS
# ============================================================================

## 7.1 Phase 1 Platforms (MVP — 5 platforms)
| Platform  | Auth         | Capabilities                              | API Notes                    |
|-----------|-------------|-------------------------------------------|------------------------------|
| X/Twitter | OAuth 2.0   | Post text/images/video, read metrics, read mentions, threads, like/retweet | Free tier: 1500 posts/mo. Chunked media upload (v1.1) |
| LinkedIn  | OAuth 2.0   | Post text/images/video/articles, Company Pages, read metrics, comments | Personal: w_member_social. Org: w_organization_social |
| Instagram | OAuth via FB | Post images/carousels/reels, read comments | Requires Business/Creator account |
| Facebook  | OAuth 2.0   | Post to Pages only, read metrics, read comments | Personal profiles NOT supported (Meta restriction since 2018) |
| TikTok    | OAuth 2.0   | Post videos via Content Posting API        | Unaudited apps: SELF_ONLY privacy |

## 7.2 Phase 2 Platforms (add 4 more)
- YouTube (OAuth 2.0 — upload videos, read metrics)
- Pinterest (OAuth 2.0 — create pins, read metrics)
- Threads (via Instagram API — post text/images)
- Bluesky (AT Protocol — open, no review needed)

## 7.3 Phase 3+ Platforms
- Reddit, Mastodon, Telegram, Discord, Medium, Dev.to, WordPress

## 7.5 Phase 5 Platform — WhatsApp (Cloud API)
| Capability | API Support | Notes |
|---|---|---|
| Send/receive messages (text, image, video, docs) | ✅ Full | Meta Cloud API (Graph API v21.0) |
| Template messages (pre-approved by Meta) | ✅ Full | Required for outbound to non-conversations |
| Interactive messages (buttons, lists, CTAs) | ✅ Full | Product cards, quick replies |
| Webhooks (incoming messages, delivery receipts) | ✅ Full | Real-time event streaming |
| Business profile management | ✅ Full | Name, about, photo, address |
| Catalog/product messages | ✅ Full | WhatsApp Commerce |
| Flows (interactive forms) | ✅ Full | Multi-step data collection |
| Status posting | ❌ Not in API | Workaround: one-tap deep link share |
| Group management | ❌ Not in API | — |
| Channels | ⚠️ Limited | Expanding — future-ready design |

## 7.4 Integration Architecture
- Each platform = a Provider class inheriting from BaseProvider
- BaseProvider defines interface: connect(), publish(), get_metrics(), get_engagement()
- Each provider implements platform-specific logic
- Token refresh handled automatically by background task
- All API calls go through rate-limit-aware wrapper
- Failed publishes retry with exponential backoff (max 3 retries)

### Account Type Tracking
- SocialAccount.account_type: personal | business | creator | page | organization
- Auto-detected during OAuth callback (Facebook→page, Instagram→business, LinkedIn→personal)
- LinkedIn Company Pages: separate connect flow with organization scopes
- Platform limitations:
  - Facebook: Meta removed personal profile publishing in 2018 (Graph API v3.0+). Pages only.
  - Instagram: Requires Business or Creator account (not personal). Guide provided in UI.
  - Twitter/X, YouTube, Pinterest, Threads, Bluesky: All account types supported.
  - TikTok: Unaudited apps restricted to SELF_ONLY privacy level.


# ============================================================================
# 8. FEATURE MAP (Complete)
# ============================================================================

## 8.1 MUST HAVE (MVP — Phase 1)
- [x] User registration + login (email + password) — django-allauth
- [x] User onboarding flow (brand voice, goals, industry, connect platforms)
- [x] Connect social accounts via OAuth (5 platforms) — X, LinkedIn, Instagram, Facebook, TikTok
- [x] Content seed input (text box — drop a rough idea)
- [x] Create Agent: Seed → platform-native content generation — OpenRouter + Gemini 2.0 Flash
- [x] Post approval workflow (approve / edit / reject)
- [x] Manual scheduling (pick date/time)
- [x] Content queue view (list of upcoming posts)
- [x] Basic calendar view (month/week) — `content/calendar/` timeline view
- [x] Auto-publish at scheduled time — Celery Beat task (60s check)
- [x] Post status tracking (draft → approved → scheduled → published → failed)
- [x] Basic post metrics display (likes, comments, shares after publishing)
- [x] Settings: manage connected accounts
- [x] Settings: update brand voice / profile
- [x] Responsive UI (works on mobile browsers) — Tailwind CSS responsive
- [x] Landing page (marketing homepage) — with KSH/USD toggle pricing
- [x] Pricing page — 4 tiers: Jipange, Kazi, Biashara, Wakala

## 8.2 SHOULD HAVE (Phase 2)
- [x] Daily Brief (morning summary + action items) — Celery Beat every 15 min
- [x] Analyst Agent v1: Engagement prediction (score before publishing)
- [x] Research Agent v1: Trending topic detection in user's niche — LLM-powered with urgency/relevance scoring
- [x] Adapt Agent: Smart scheduling (optimal times based on user's audience)
- [x] Content DNA system: Track which content attributes drive engagement — JSONField on Post model
- [x] Email Daily Brief (receive brief in inbox) — routed through EmailService for logging
- [x] Twitter/X media upload — chunked upload via v1.1 API (images + video)
- [x] LinkedIn Company Page publishing — w_organization_social scope, page selection UI
- [ ] Multi-image / carousel support
- [ ] Post preview (see how it will look on each platform)
- [ ] Basic competitor tracking (manually add competitor accounts)
- [x] Agent activity log (see what agents did and why) — /agents/activity/
- [x] Agent configuration (enable/disable agents, set autonomy level) — /agents/<slug>/ + custom instructions
- [ ] Stripe billing integration
- [ ] Free trial (7 days)

## 8.3 NICE TO HAVE (Phase 3)
- [x] Engage Agent: Comment/DM monitoring + auto-reply drafts — Celery Beat every 30 min
- [x] Relationship Memory: Track audience members, superfans — Superfan model with tier system
- [x] Unified inbox (all comments/DMs across platforms) — engage/inbox with status/sentiment/platform filters
- [x] Full agent orchestration (Chief Strategist coordinates all agents) — Strategist Agent with proactive seeds
- [ ] Content A/B testing (auto-generate variations)
- [x] Team features: invite members, roles, approval workflows — Team model, invitations, roles (admin/editor/viewer)
- [ ] Hashtag research + suggestions
- [ ] Re-queue evergreen content
- [x] Voice memo input (speech-to-text → content seed) — OpenAI Whisper, browser MediaRecorder, Alpine.js voice recorder in studio
- [x] AI image generation for posts — Multi-provider: HuggingFace → Together.ai → Pollinations.ai

## 8.4 FUTURE (Phase 4+)
- [ ] Agency/multi-brand management
- [ ] White-label client reports
- [ ] Revenue attribution (connect social activity to business outcomes)
- [ ] Custom agent skills marketplace
- [ ] Open API for third-party integrations
- [ ] Open-source self-hosted option
- [ ] Mobile app (PWA or native)
- [ ] Content import (import from existing posts/RSS)
- [ ] Bulk content upload (CSV)

## 8.5 WHATSAPP INTELLIGENCE (Phase 5)
- [ ] WhatsApp Cloud API provider (messaging, templates, interactive messages, webhooks)
- [ ] Meme Intelligence Engine (trend detection → meme ranking → brand adaptation)
- [ ] Status Content Studio (templates, AI generation, scheduling queue, one-tap share)
- [ ] Conversational AI auto-reply (Swahili/Sheng/English, brand-voice trained)
- [ ] Catalog assistant (product card responses, order status queries)
- [ ] Broadcast campaign builder (smart segmentation, timing optimization, drip sequences)
- [ ] WhatsApp analytics dashboard (response rates, sentiment trends, revenue attribution)
- [ ] WhatsApp Channels integration (content curation, cross-post from Kova)


# ============================================================================
# 9. BUILD PHASES (Detailed Sprint Plans)
# ============================================================================

## PROGRESS SUMMARY
| Phase | Sprint | Status | Key Deliverables |
|-------|--------|--------|-----------------|
| Phase 1 | Sprint 1 | ✅ Complete | Foundation, Auth, Onboarding, Landing Page |
| Phase 1 | Sprint 2 | ✅ Complete | Platform OAuth (5 platforms), Token Refresh |
| Phase 1 | Sprint 3 | ✅ Complete | Content Pipeline, Create Agent, Post Approval |
| Phase 1 | Sprint 4 | ✅ Complete | Auto-Publish, Metrics, Railway Deployment |
| Phase 2 | Sprint 5 | ✅ Complete | Daily Brief, Analyst Agent, Content DNA |
| Phase 2 | Sprint 6 | ✅ Complete | Research Agent, Adapt Agent, Agent Config UI |
| Phase 2 | Sprint 7 | ✅ Complete | Billing + Growth Features |
| Phase 2 | Sprint 8 | ✅ Complete | More Platforms, Competitor Intel, Multi-image, Previews |
| Phase 3 | Sprint 9 | ✅ Complete | Engage Agent, Unified Inbox, Superfan Detection |
| Phase 3 | Sprint 10 | ✅ Complete | Strategist Orchestration, Full Pipeline |
| Phase 3 | Sprint 11 | ✅ Complete | Team Features, Help Center, Admin Dashboard, API, Email System |
| Phase 3 | Sprint 12 | ✅ Complete | Production Hardening (security, perf optimization, caching, token encryption) |
| Phase 4 | Sprint 13 | ✅ Complete | Agency Multi-Brand, Revenue Attribution, Mobile PWA, API Docs |
| Phase 4 | Voice Memo | ✅ Complete | Voice Memo input (Whisper transcription → content seed) |
| Phase 6 | Post-Phase 5 | ⏳ Deferred | White-label UI, Agent Marketplace, Open-source, Video AI |
| Phase 5 | Post-Launch  | ⏳ Not Started | WhatsApp Intelligence, Meme Engine, Status Studio |

## CELERY BEAT SCHEDULE (Current — 9 tasks)
| Task | Schedule | Source |
|------|----------|--------|
| `check-and-publish` | Every 60 seconds | `apps/content/tasks.py` |
| `fetch-post-metrics` | Every 6 hours | `apps/analytics/tasks.py` |
| `refresh-expiring-tokens` | Every 30 minutes | `apps/platforms/tasks.py` |
| `generate-daily-briefs` | Every 15 minutes | `apps/briefs/tasks.py` |
| `run-daily-research` | Every 12 hours | `apps/agents/tasks.py` |
| `run-engage-cycle` | Every 30 minutes | `apps/agents/tasks.py` |
| `run-strategy-cycle` | Every 8 hours | `apps/agents/tasks.py` |
| `check-mpesa-subscriptions` | Every 24 hours | `apps/billing/tasks.py` |
| `analyze-all-competitors` | Weekly | `apps/analytics/tasks.py` |
| `send-weekly-reports-all` | Weekly (Monday 8AM) | `apps/emails/tasks.py` |

## ─── PHASE 1: MVP — "AI-Assisted Scheduling" (Weeks 1-8) ✅ COMPLETE ───

### Sprint 1 (Week 1-2): Foundation ✅ COMPLETE
- [x] Create Django project with proper structure
- [x] Configure settings (base, dev, prod) — config/settings/{base,development,production}.py
- ~~Set up Docker + Docker Compose~~ → Using Railway Nixpacks instead
- [x] Set up Celery with Redis broker — Celery configured (ALWAYS_EAGER mode, no Redis needed yet)
- [x] Install and configure: HTMX, Alpine.js, Tailwind CSS — CDN-based, no build step
- [x] Create base.html template with Tailwind + HTMX + Alpine
- [x] Create app layout template (sidebar + main area)
- [x] accounts app: User model, registration, login, logout — django-allauth
- [x] accounts app: User profile + onboarding form — 3-step onboarding (basics + language + offerings, voice + tone grid + guardrails + pillar suggestions, goals + auto-engage)
- [x] Basic landing page (marketing) — with KSH/USD pricing toggle
- ~~Evaluate LangGraph vs CrewAI~~ → Built custom agent layer instead (simpler, no heavy deps)
- DELIVERABLE: ✅ User can register, login, complete onboarding. App looks good.
- **IMPLEMENTATION NOTES:**
  - Auth: django-allauth (email verification = "none" in production for easy testing)
  - 9 Django apps: accounts, platforms, content, agents, analytics, briefs, engage, billing, notifications
  - Frontend: HTMX 2.0.4, Alpine.js 3.14.8, Tailwind CSS 3.4 (all via CDN)
  - Static files: WhiteNoise CompressedStaticFilesStorage

### Sprint 2 (Week 3-4): Platform Connections ✅ COMPLETE
- [x] platforms app: SocialAccount model — stores OAuth tokens + platform metadata
- [x] BaseProvider abstract class — apps/platforms/providers/base.py
- [x] X/Twitter OAuth flow + provider
- [x] LinkedIn OAuth flow + provider
- [x] Instagram/Facebook OAuth flow + provider
- [x] TikTok OAuth flow + provider
- [x] Token refresh background task — Celery Beat every 30 min
- [x] "Connect Account" UI in settings
- [x] Connected accounts dashboard
- DELIVERABLE: ✅ User can connect their social media accounts.
- **IMPLEMENTATION NOTES:**
  - OAuth via django-allauth social providers (not custom OAuth flows)
  - Platform providers: X, LinkedIn, Instagram, Facebook, TikTok
  - Token refresh: `refresh_expiring_tokens` Celery task every 30 min
  - Settings page with connect/disconnect UI per platform

### Sprint 3 (Week 5-6): Content Pipeline + Create Agent ✅ COMPLETE
- [x] content app: ContentSeed, Post, MediaAsset models
- [x] Content seed input form ("Drop your idea here")
- [x] Create Agent v1: text seed → multi-platform posts — OpenRouter + Gemini 2.0 Flash
- [x] Brand voice training: Use user's sample posts to fine-tune agent output — onboarding brand voice feeds into prompts
- [x] Post editor (edit AI-generated content before approving)
- [x] Post approval flow (approve / edit / reject)
- [x] Content queue view (upcoming posts list)
- [ ] Calendar view (basic month view with scheduled posts) — deferred
- [ ] Media upload support (images) — deferred
- DELIVERABLE: ✅ User drops an idea → AI generates platform-native posts → user approves.
- **IMPLEMENTATION NOTES:**
  - Create Agent: `apps/agents/create_agent.py` — generates platform-native content from seed ideas
  - LLM: OpenRouter API via `apps/agents/llm.py` (model: google/gemini-2.0-flash-001)
  - Content pipeline: seed → generate → approve → schedule → publish
  - Post model has status field: draft/approved/scheduled/published/failed

### Sprint 4 (Week 7-8): Publishing + Polish ✅ COMPLETE
- [x] Scheduling system: pick date/time for each post
- [x] Auto-publish Celery task (fires at scheduled_at, calls platform API)
- [x] Publish status tracking + error handling + retry
- [x] Post metrics: fetch basic metrics after publishing (periodic task) — Celery Beat every 6 hrs
- [x] Post detail view (see metrics after publishing)
- [x] Notification system (in-app: post published, post failed)
- [x] Error states + empty states throughout the app
- [x] Mobile responsiveness pass — Tailwind responsive utilities
- [x] Bug fixing + testing
- [x] Deploy MVP to staging — Railway production deployment ✅
- DELIVERABLE: ✅ Full MVP. User can drop idea → AI generates → approve → schedule → auto-publish → see metrics.
- **IMPLEMENTATION NOTES:**
  - Auto-publish: `check_and_publish` Celery Beat task every 60 seconds
  - Metrics: `fetch_post_metrics` Celery Beat task every 6 hours
  - Deployed to Railway: https://kovaagent-production.up.railway.app/
  - Build: Nixpacks → Procfile → start.sh → gunicorn
  - Database: Railway PostgreSQL plugin
  - UI overhaul: dark sidebar, glassmorphism cards, gradient accents

## ─── PHASE 2: Intelligence — "Predictive & Adaptive" (Weeks 9-16) — IN PROGRESS ───

### Sprint 5 (Week 9-10): Daily Brief + Analyst Agent ✅ COMPLETE
- [x] briefs app: DailyBrief, BriefItem models
- [x] Daily Brief generation (Celery Beat, runs at user's preferred time) — every 15 min via `generate_all_daily_briefs`
- [x] Daily Brief UI (the "command center" view) — performance insight, trending topics, suggested posts
- [x] Analyst Agent v1: Post-performance analysis — `apps/agents/analyst_agent.py`
- [x] Analyst Agent v1: Engagement prediction scoring — `predict_engagement()` hooked into content pipeline
- [x] Content DNA system: Track content attributes → performance correlation — `extract_content_dna()` + JSONField on Post
- [x] Content DNA display: "Your best performing content attributes" — `get_content_dna_summary()` in Daily Brief
- DELIVERABLE: ✅ Users get a Daily Brief with scored content + insights.
- **IMPLEMENTATION NOTES:**
  - Analyst Agent: 4 functions — `analyze_performance`, `extract_content_dna`, `predict_engagement`, `get_content_dna_summary`
  - Daily Brief: `apps/briefs/tasks.py` — gathers performance + Content DNA + pipeline stats, LLM compiles brief
  - Content DNA stored as `content_dna` JSONField on Post model (migration 0004)
  - `extract_content_dna` + `predict_engagement` hooked into `generate_from_seed` pipeline
  - Celery Beat: `generate-daily-briefs` every 15 min

### Sprint 6 (Week 11-12): Research Agent + Adapt Agent ✅ COMPLETE
- [x] Research Agent v1: Trending topic detection (web search + social signals) — `apps/agents/research_agent.py`
- [x] Research Agent: Opportunity briefs in Daily Brief — rich trending data with urgency/relevance scoring
- [x] Adapt Agent v1: Audience activity pattern analysis — `apps/agents/adapt_agent.py`
- [x] Adapt Agent: Smart scheduling (suggest optimal times) — `suggest_optimal_times()` with historical analysis
- [x] Auto-schedule feature (let Adapt Agent choose all times) — `auto_schedule_post()` conflict-aware
- [x] Agent configuration UI (enable/disable, set autonomy level) — `/agents/<slug>/` + custom instructions editor
- [x] Agent activity log (see history of agent actions) — `/agents/activity/` with filtering
- DELIVERABLE: ✅ Agents proactively find trends + optimize timing.
- **IMPLEMENTATION NOTES:**
  - Research Agent: `discover_trends()` (LLM-powered, urgency/relevance), `generate_content_angles()` (platform-specific)
  - Adapt Agent: `_analyze_time_performance()`, `suggest_optimal_times()`, `auto_schedule_post()` (conflict-aware)
  - Agent Activity Log: `apps/agents/views.py::agent_activity_log` — filterable by agent type
  - Agent Detail/Config: `apps/agents/views.py::agent_detail` + `agent_update_instructions`
  - `auto_schedule_post` hooked into content pipeline when `auto_approve_posts` enabled
  - Celery Beat: `run-daily-research` every 12 hours
  - New URLs: `/agents/activity/`, `/agents/<slug>/`, `/agents/<slug>/instructions/`
  - Templates: `activity_log.html`, `detail.html` (new), `control.html` + `agent_status.html` (updated)

### Sprint 7 (Week 13-14): Billing + Growth Features ✅
- [x] billing app: BillingEvent model + PLAN_LIMITS config (4 tiers)
- [x] Stripe Checkout integration (subscribe to plan)
- [x] Stripe Customer Portal (manage subscription, invoices)
- [x] Stripe webhooks (5 event handlers, idempotent processing)
- [x] Free 14-day trial flow (via Stripe subscription_data)
- [x] Plan enforcement middleware (platform connect + post creation limits)
- [x] Pricing page with plan comparison (KES/USD toggle, 4 tiers)
- [x] Agent email reports (Daily Brief → HTML email for Growth+ plans)
- [x] Billing overview dashboard (subscription status, plan limits grid)
- [x] Checkout success/cancel pages
- [x] BillingEvent admin with search + filters
- [x] UserProfile fields: subscription_status, trial_ends_at, current_period_end
- DELIVERABLE: Monetization works. Users can subscribe and pay. ✅
- COMMIT: 6481e9a — 17 files, 1306 insertions

### Sprint 8 (Week 15-16): Quality + More Platforms ✅ COMPLETE
- [x] Post preview per platform (mock how it'll look) — 9 platform-specific mockups + character limit warnings
- [x] Carousel/multi-image post support — MediaAttachment model with ordering
- [x] Add YouTube provider — `apps/platforms/providers/youtube.py`
- [x] Add Pinterest provider — `apps/platforms/providers/pinterest.py`
- [x] Add Threads provider — `apps/platforms/providers/threads.py`
- [x] Add Bluesky provider — `apps/platforms/providers/bluesky.py` (AT Protocol, app password auth)
- [x] Competitor tracking (manual add, basic metric monitoring) — Full AI competitor intelligence engine with insights
- [x] Performance + security audit — CSP, HSTS, rate limiting, Sentry, Resend email
- [x] Load testing — Locust load test suite
- DELIVERABLE: ✅ 9 platforms, previews, competitor intel, production hardened.
- **IMPLEMENTATION NOTES:**
  - Providers: YouTube, Pinterest, Threads, Bluesky (all in `apps/platforms/providers/`)
  - Competitor Intel: `Competitor`, `CompetitorAnalysis`, `CompetitorInsight` models + LLM analysis
  - Preview: HTMX modal with realistic platform mockups (Twitter, LinkedIn, IG, FB, TikTok, YT, Pinterest, Threads, Bluesky)
  - Security: Sentry (Django+Celery integrations), CSP headers (django-csp), allauth rate limiting, HSTS preload
  - Email: Resend SMTP relay wired up for Daily Brief emails
  - Calendar view: `/content/calendar/` timeline view by date

## ─── PHASE 3: Autonomy — "The System Runs Itself" (Weeks 17-24) ───

### Sprint 9 (Week 17-18): Engage Agent + Community ✅ COMPLETE
- [x] engage app: Interaction, Superfan models — sentiment tracking, tier system (RISING/LOYAL/SUPERFAN)
- [x] Engage Agent v1: Monitor comments/mentions across platforms — `apps/agents/engage_agent.py`
- [x] Engage Agent: Draft replies with confidence scoring — LLM-powered, brand-voice-aware
- [x] Auto-reply for high-confidence responses — configurable per agent
- [x] Flagged items in Daily Brief — pending interactions surfaced
- [x] Unified inbox (all engagement in one place) — `engage/inbox` with status/sentiment/platform filters
- [x] Relationship scoring (track interaction frequency per audience member) — Superfan tiers by interaction count
- DELIVERABLE: ✅ Community engagement automated. Inbox, sentiment, superfan detection working.
- **IMPLEMENTATION NOTES:**
  - Models: `Interaction` (status: NEW/AI_REPLIED/USER_REPLIED/IGNORED/FLAGGED, sentiment tracking), `Superfan` (tiers + interaction counting)
  - Engage Agent cycle: fetch interactions → analyze sentiment → generate replies → auto-respond (30min Celery Beat)
  - Unified inbox: filter by status, sentiment, platform. Send AI-suggested replies.
  - Skips `get_mentions()` for Facebook/Instagram (only Twitter/Bluesky support it)

### Sprint 10 (Week 19-20): Full Orchestration ✅ COMPLETE
- [x] Chief Strategist Agent: Coordinate all agents — `apps/agents/strategist_agent.py` (8h Celery Beat cycle)
- [x] Full seed-to-publish pipeline (seed → research → create → score → schedule → publish → engage → learn)
- [ ] Content A/B testing: Auto-generate variations, test them
- [x] Self-adjusting strategy (Analyst → Create Agent feedback loop) — Content DNA feeds back into creation
- [x] Superfan detection + alerts — Superfan model with tier escalation
- DELIVERABLE: ✅ Strategist orchestrates all agents. Proactive content seeds. Full autonomous pipeline.
- **IMPLEMENTATION NOTES:**
  - Strategist: `run_strategy_cycle()` gathers inputs from all agents, makes LLM-powered decisions, creates proactive ContentSeeds
  - Autonomy levels: Manual (seeds as suggestions) vs Autonomous (auto-create → generate → schedule)
  - Feeds into Daily Brief compilation
  - Fixed: `posting_frequency` type mismatch, missing `strategist.decide` model config

### Sprint 11 (Week 21-22): Teams, Help, Admin Dashboard, API, Email System ✅ COMPLETE
- [x] teams app: Team, TeamMember, TeamInvitation, TeamActivity, Brand models
- [x] Team invitations and roles (admin, editor, viewer) — token-based invites, 7-day expiry
- [x] Team activity feed — TeamActivity model with event logging
- [x] Multi-brand support — Brand model linked to teams
- [x] Help center: HelpArticle + HelpCategory models, admin management, public /learn/ section
- [x] Admin dashboard: overview, users, content, agents, platforms, billing, engage, teams, analytics, A/B tests, system health, logs — 15+ views
- [x] REST API v1: /api/v1/ — briefs, content, agents, analytics, engage endpoints with token auth
- [x] Full email system: apps/emails/ — EmailLog model (19 types, 8 statuses), EmailService, 12 Celery tasks, 20 HTML templates
- [x] Email admin dashboard: /dashboard/emails/ — stats, charts, log, detail, test email, broadcast
- [x] Email wiring: welcome (signup), payment confirmation/failed/receipt (Stripe+M-Pesa), plan changes, cancellations, payment reminders, team invitations, daily briefs, weekly reports
- [x] Resend webhook handler: delivery/open/click/bounce tracking via provider_message_id
- DELIVERABLE: ✅ Teams, help center, admin dashboard, API, and full email system operational.
- **IMPLEMENTATION NOTES:**
  - Email: `apps/emails/` — EmailService singleton, central `_send()` method, all emails logged to EmailLog
  - Templates: 20 HTML email templates extending `base_email.html` (table layout, responsive, branded)
  - Async: All emails sent via Celery tasks (never blocking HTTP requests), max_retries=3
  - Admin: /dashboard/emails/ with stats cards, 30-day volume chart, filterable log, detail view, test/broadcast actions
  - Wired into: accounts (signals), billing (services + tasks + mpesa), teams (views), briefs (tasks)
  - Celery Beat: `send-weekly-reports-all` weekly on Monday 8AM
  - See docs/EMAIL_SYSTEM_GUIDE.md for complete reference

### Sprint 12 (Week 23-24): Polish + Scale ✅ COMPLETE
- [x] Sentry error monitoring + alerting — Django + Celery integrations, release tracking
- [x] CSP security headers (django-csp) — script/style/img/font/connect/frame policies
- [x] Authentication rate limiting — allauth built-in: login, signup, password reset
- [x] Health check endpoint — `/health/` for Railway + uptime monitors
- [x] Email sending (Resend SMTP) — Full email system: 19 types, 20 templates, admin dashboard, webhook tracking
- [x] Production security hardening — HSTS preload, referrer policy, cookie security, CSRF
- [x] Load testing suite — Locust: authenticated flows, agent cycles, realistic user simulation
- [x] Platform Account Type System — SocialAccount.account_type field (personal/business/creator/page/organization)
- [x] Twitter/X Media Upload — Full chunked media upload via v1.1 API (images + video with async processing)
- [x] LinkedIn Company Pages — Organization auth scopes, page selection UI, org-level publishing
- [x] Instagram Creator Guide — In-app instructions for converting personal → Creator account
- [x] Platform Capability Badges — Account type badges on connected accounts, FB/IG limitations documented in UI
- [x] Performance optimization — DB indexes on all hot queries (content, analytics, billing, agents), Redis caching on insights (5-min TTL), select_related on Celery tasks
- [x] Onboarding improvements — OnboardingMiddleware enforces step-by-step completion, signals auto-setup on signup
- [x] Help docs / knowledge base — 18 articles across 5 categories, public /learn/ section, usage analytics tracking
- [x] OAuth token encryption — django-fernet-fields-v2 with EncryptedCharField on access_token/refresh_token
- [x] LLM optimization — Batched calls (13→3 per seed), paid auto-fallback, LLMConfig singleton, admin dashboard
- [x] Cost economics dashboard — /dashboard/costs/ with per-plan unit economics, model pricing, scenario calculator
- [x] Per-plan LLM model routing — Plan-aware model resolution, per-task overrides, admin UI, rate limits

## ─── PHASE 4: Moat — "Unbeatable" (Weeks 25-32) — MOSTLY COMPLETE ───

### Sprint 13 (Week 25-28): Agency + Platform ✅ COMPLETE
- [x] Agency multi-brand management — Brand model per team, role-based access (owner/admin/editor/viewer), plan-based team limits
- [x] Revenue attribution engine — Conversion model (click/lead/sale/custom), UTM tracking, API endpoint, analytics dashboard
- [x] Public API v1 — 10 endpoints (platforms, seeds, posts, analytics, agents, conversions), token + session auth
- [x] API documentation — docs/API_REFERENCE.md (auth, pagination, errors, all endpoints with examples)
- [x] Mobile PWA — manifest.json, service worker (cache-first + offline fallback), installable on iOS/Android
- DELIVERABLE: ✅ Agency-ready platform. Multi-brand, revenue tracking, API, mobile app.

### Phase 4 — Deferred Items (Not blocking launch)
- [ ] White-label client dashboards — Custom domains work, but report UI not brandable per client yet
- [ ] Interactive API docs — No Swagger/OpenAPI UI (drf-spectacular), hand-written docs only
- [ ] Custom agent skills / marketplace — Agents are hard-coded, no plugin/skill architecture
- [ ] Open-source self-hosted edition — Docker infra exists, needs licensing + packaging
- [ ] Advanced AI features (voice memo, video generation) — Image generation works, no audio/video yet

## ─── PHASE 5: WhatsApp Intelligence — "Own the Most Important Channel" (Post-Launch) ───

### Context
WhatsApp is the operating system of business and social life in Kenya (90%+ smartphone
penetration). 7.4M+ MSMEs run businesses through WhatsApp. Status is viewed more than
Instagram Stories. No existing tool treats WhatsApp as a first-class content + intelligence
channel — they're all customer support tools. This is category creation.

### Sprint 5A: WhatsApp Provider + Conversational AI
- [ ] WhatsApp Cloud API provider (extends BaseProvider, Graph API v21.0)
- [ ] OAuth flow via Facebook Business (shared infra with FB/IG provider)
- [ ] Send/receive text, image, video, document messages
- [ ] Template message registration + sending (pre-approved by Meta)
- [ ] Interactive messages: button replies, list menus, product cards, CTAs
- [ ] Webhook handler for incoming messages + delivery/read receipts
- [ ] Business profile management (name, about, photo, address)
- [ ] Conversational AI auto-reply (brand-voice trained, not generic chatbot)
- [ ] Language Intelligence: auto-detect Swahili/Sheng/English, respond in same language
- [ ] Smart routing: AI handles 80% of FAQs, flags complex queries to human with context
- [ ] Catalog assistant: customer asks about products → AI pulls from WhatsApp Catalog, sends cards
- DELIVERABLE: WhatsApp connected, AI handles customer conversations 24/7.

### Sprint 5B: Meme Intelligence Engine (THE UNIQUE MOAT)
- [ ] Trend Detection: monitor Kenyan Twitter/X (KOT), TikTok Kenya, Reddit r/Kenya, FB meme pages
- [ ] Meme Ranking: score each meme by virality velocity, brand-safety, cultural relevance, humor type
- [ ] Cultural Intelligence: Sheng references, political context (safe vs risky), local events
  - (Mashujaa Day, election cycle, KPL season, county-specific humor)
- [ ] Meme Adaptation: AI takes trending meme FORMAT and adapts to user's brand/product/context
  - Not reposting — REMIXING (original meme + brand context = viral brand content)
- [ ] Meme queue with Kenya peak times (6-8am commute, 12-1pm lunch, 6-9pm evening scroll)
- [ ] Celery Beat task: `discover-trending-memes` — runs every 2-4 hours, scores + adapts
- DELIVERABLE: Users get auto-curated, brand-adapted memes from Kenyan trends.
- UNIQUENESS TEST: Nobody does AI-powered meme intelligence localized to Kenya.

### Sprint 5C: Status Content Studio
- [ ] Status Content Queue: AI-curated content ready for WhatsApp Status
- [ ] One-tap share: deep link to WhatsApp with pre-loaded media (API workaround for Status)
- [ ] Status templates: new product, offer/discount, testimonial, BTS, poll/question
- [ ] AI content generation: Status-optimized (short, visual, punchy, Kenyan tone)
- [ ] Smart scheduling: AI learns when user's contacts are most active
- [ ] Status calendar: 7-day visual planner with mix optimization
  - (don't post 3 promos in a row — mix memes, quotes, BTS, offers)
- [ ] Cross-platform repurposing: take LinkedIn/IG/TikTok post → AI-adapt for Status format
- DELIVERABLE: Full Status content pipeline. AI does 95% of work, user taps once to share.

### Sprint 5D: Broadcast Intelligence + Analytics
- [ ] Smart segmentation: AI segments contacts by purchase history, message frequency, interests
- [ ] Campaign builder: visual builder for broadcast campaigns with personalization tokens
- [ ] Drip sequences: automated multi-day sequences (onboarding, re-engagement, cart abandonment)
- [ ] Timing optimization: AI sends each message at optimal time for each contact (not blast)
- [ ] Compliance guard: auto-check templates comply with Meta policies before submission
- [ ] Message analytics: response rates, avg response time, conversation volume trends
- [ ] Customer sentiment: AI analyzes incoming messages for sentiment trends over time
- [ ] Revenue attribution: link WhatsApp conversations to conversions/sales
- [ ] Weekly digest: "Top-performing Status was the chapati meme (847 views). Response time improved 34%."
- DELIVERABLE: Broadcast campaigns + full analytics. WhatsApp becomes a measurable growth channel.

### Sprint 5E: WhatsApp Channels + Future
- [ ] Channel content curation: AI selects best content for channel posts
- [ ] Cross-post from Kova: content from any platform adapted + pushed to Channel
- [ ] Channel growth analytics: follower trends, reach, engagement per post
- [ ] Full Status automation (when Meta opens the API — future-ready architecture)
- DELIVERABLE: WhatsApp Channels managed by Kova. Ready for Status API when it drops.

### WhatsApp Phase — Key Technical Notes
- Provider: `apps/platforms/providers/whatsapp.py` (extends BaseProvider)
- Shared FB Business infra: same Meta App as FB/IG, same Graph API
- Meme engine: new app `apps/memes/` (trend detection + adaptation pipeline)
- Webhook receiver: new endpoint in `apps/platforms/` for incoming messages
- Template management: store approved templates in DB, render with context vars
- Deep link for Status: `whatsapp://send?text=...` or `https://wa.me/?text=...` with media
- Celery Beat tasks: `discover-trending-memes` (every 2-4h), `process-whatsapp-messages` (real-time via webhook)


# ============================================================================
# 10. UI/UX PRINCIPLES & KEY SCREENS
# ============================================================================

## 10.1 Design Principles
1. SIMPLE > POWERFUL — Hide complexity. Surface only what needs attention.
2. ACTION-ORIENTED — Every screen drives toward a decision or action.
3. NO EMPTY DASHBOARDS — If there's no data, show helpful onboarding, not blank charts.
4. MOBILE-FIRST — Many creators check social on phones. Design for small screens first.
5. DARK MODE — Support from day one. Tailwind makes this easy.
6. SPEED — Server-rendered + HTMX = fast. No loading spinners for basic navigation.

## 10.2 Key Screens

### Screen 1: Daily Brief (HOME — default logged-in view)
- Morning greeting + summary stats
- Performance snapshot (yesterday's results)
- Trend alert cards (from Research Agent)
- Today's content queue (approve/edit/reject each)
- Flagged engagement items (comments needing your reply)
- Agent activity summary ("here's what your agents did since you last visited")

### Screen 2: Content Studio
- Seed idea input (big text area: "What's on your mind?")
- AI generates → shows platform-native previews
- Edit inline, approve, reject
- Schedule or let Adapt Agent assign timing

### Screen 3: Content Queue / Calendar
- Toggle: list view / calendar view
- Drag and drop to reschedule (Alpine.js + HTMX)
- Color-coded by platform
- Status badges (draft, approved, scheduled, published)
- Filter by platform, status, date range

### Screen 4: Agent Control Center
- Each agent: status (active/disabled), autonomy level (slider)
- Activity log per agent (what it did, when, why)
- Agent "thinking" transparency: see the reasoning behind decisions
- Cost tracking (tokens/money used per agent)

### Screen 5: Insights (NOT a dashboard)
- "Here's what's working" — top performing content DNA attributes
- "Here's what to change" — strategy recommendations from Analyst Agent
- "Your audience" — growth trends, superfan list, engagement patterns
- Everything framed as ACTIONS, not charts

### Screen 6: Community Inbox
- All comments, DMs, mentions in one stream
- Agent-drafted replies (approve or edit)
- Relationship scores next to each person's name
- Filter by: needs my reply, agent handled, all

### Screen 7: Settings
- Profile + brand voice configuration
- Connected social accounts
- Agent preferences
- Subscription + billing
- Team management (Phase 3)

### Screen 8: Onboarding (first-time wizard)
Step 1: Brand Basics — company name, website, industry, content language (11 options), key products/services (key_offerings)
Step 2: Your Voice — brand voice description, brand voice examples, tone attributes (12-option visual grid), target audience, content pillars (with industry-based smart suggestions), brand restrictions/guardrails (collapsible section)
Step 3: Goals & Preferences — goals (multi-select), posting frequency (enforced by AI), auto-approve toggle, auto-engage toggle (AI replies to positive comments)


# ============================================================================
# 11. AUTHENTICATION & SECURITY
# ============================================================================

## 11.1 Authentication
- Email + password registration (Django auth)
- Email verification required (send confirmation link)
- Session-based auth (Django sessions — simple with HTMX)
- Password reset via email
- Future: Google/GitHub OAuth social login

## 11.2 Security Measures
- All social media tokens encrypted at rest (django-fernet-fields or similar)
- CSRF protection on all forms (Django default + HTMX config)
- Rate limiting on API endpoints (django-ratelimit)
- Content Security Policy headers
- HTTPS enforced in production
- Input sanitization on all user inputs
- SQL injection prevention (Django ORM — parameterized queries by default)
- XSS prevention (Django auto-escaping in templates by default)
- Secrets in environment variables, never in code
- Regular dependency security audits (pip-audit)
- OWASP Top 10 compliance checklist before each release

## 11.3 Data Privacy
- Users can export all their data
- Users can delete their account and all associated data
- Agent memory is per-user, never shared
- We don't store social media passwords — only OAuth tokens
- Privacy policy clearly states what data agents access


# ============================================================================
# 12. PRICING & BILLING
# ============================================================================

## 12.1 Plans

### Free Trial
- 7 days, full Growth plan access
- No credit card required to start
- Credit card required to continue after trial

### Starter — $39/month
- 3 social accounts
- Research Agent + Create Agent only
- 100 AI-generated posts per month
- Manual scheduling only
- Basic post metrics
- Email support

### Growth — $79/month (Main plan, most users)
- 8 social accounts
- ALL 5 agents active
- Unlimited AI-generated posts
- Autonomous scheduling (Adapt Agent)
- Daily Brief
- Engagement management (Engage Agent)
- Predictive scoring (Analyst Agent)
- Content DNA insights
- Priority support

### Pro — $149/month
- 20 social accounts
- Everything in Growth
- Team collaboration (up to 5 members)
- Competitor intelligence
- White-label reports
- Advanced Content DNA lab
- API access
- Dedicated support

### Agency — $299/month
- Unlimited social accounts
- Everything in Pro
- Multi-brand workspaces
- Unlimited team members
- Client dashboards
- Custom agent fine-tuning per brand
- Priority AI models
- Dedicated account manager

## 12.2 Billing Implementation
- Stripe Checkout for new subscriptions
- Stripe Customer Portal for self-service management
- Stripe Webhooks for lifecycle events
- Pro-rated upgrades/downgrades
- Grace period: 3 days after failed payment before downgrading
- Annual billing option: 2 months free (17% discount)


# ============================================================================
# 13. TESTING STRATEGY
# ============================================================================

## 13.1 Testing Levels

### Unit Tests (pytest + Django test framework)
- Model validation and methods
- Service layer business logic
- Agent prompt construction
- Platform provider formatting
- Utility functions

### Integration Tests
- OAuth flow completion (mocked external APIs)
- Content pipeline: seed → generate → approve → schedule → publish
- Celery task execution
- Agent system: input → output correctness
- Stripe webhook handling

### End-to-End Tests (Playwright or Selenium)
- User registration → onboarding → first post published
- Daily Brief interaction
- Agent configuration changes
- Billing flows

### Agent Tests
- Prompt regression: ensure agent outputs stay consistent
- Guardrail tests: agent doesn't go off-brand
- Cost tests: ensure no runaway API calls

## 13.2 Testing Rules
- All new features require tests before merge
- Minimum 80% code coverage target
- Tests must pass in CI before deploy
- Mock ALL external APIs (social platforms, Stripe, LLMs) in tests
- Agent testing uses recorded/fixture responses, not live LLM calls


# ============================================================================
# 14. DEPLOYMENT & INFRASTRUCTURE
# ============================================================================

## 14.1 Local Development
- Docker Compose: Django + PostgreSQL + Redis + Celery Worker + Celery Beat
- Hot reload enabled for Django
- Tailwind CSS watch mode
- .env file for local secrets

## 14.2 Staging
- Same infrastructure as production, smaller scale
- Deployed on every push to `develop` branch
- Used for final testing before production release

## 14.3 Production
- Docker containers deployed to Railway / Render / VPS
- Managed PostgreSQL (or self-managed on VPS)
- Managed Redis (or self-managed on VPS)
- S3-compatible storage for media files
- GitHub Actions CI/CD pipeline:
  1. Run tests
  2. Build Docker image
  3. Push to container registry
  4. Deploy to production
- Sentry for error monitoring
- Health check endpoint (/health/)
- Database backups: daily automated

## 14.4 Scaling Considerations (future)
- Celery workers: scale independently (more workers = more agent parallelism)
- Django: stateless, can run multiple instances behind a load balancer
- PostgreSQL: read replicas if needed
- Redis: cluster mode if needed
- CDN for static files and media


# ============================================================================
# 15. METRICS & SUCCESS CRITERIA
# ============================================================================

## 15.1 Business Metrics
- MRR (Monthly Recurring Revenue) — primary business metric
- Trial → Paid conversion rate (target: >15%)
- Monthly churn rate (target: <5%)
- Average Revenue Per User (ARPU)
- Customer Acquisition Cost (CAC)
- User count by plan tier

## 15.2 Product Metrics
- Daily Active Users (DAU) — people opening Kova daily
- Posts generated by agents per user per week
- Posts approved vs rejected (agent quality signal)
- Average time in app per session (target: <5 minutes)
- Agent confidence accuracy (predicted engagement vs actual)
- Platforms connected per user
- Daily Brief open rate

## 15.3 Technical Metrics
- API response time (p50, p95, p99)
- Post publish success rate (target: >99%)
- Agent task completion rate
- Error rate
- Uptime (target: 99.9%)


# ============================================================================
# 16. RISKS & MITIGATIONS
# ============================================================================

| # | Risk                                      | Impact | Mitigation                                                    |
|---|-------------------------------------------|--------|---------------------------------------------------------------|
| 1 | Social platform API changes/restrictions  | HIGH   | Abstract provider layer. One change per provider, not system-wide. Monitor platform changelogs. |
| 2 | LLM costs spiral for heavy users          | HIGH   | Token budgets per plan. Use cheaper models (GPT-4o-mini) for simple tasks. Cache common generations. |
| 3 | Agent produces off-brand/harmful content   | HIGH   | Human-in-the-loop by default. Content safety filters. Brand guardrails in prompts. |
| 4 | OAuth app approval takes too long          | MEDIUM | Start approval process Week 1. Build with 1-2 platforms first. |
| 5 | Users don't trust AI autonomy             | MEDIUM | Default to "Guided" autonomy. Show agent reasoning. Build trust gradually. |
| 6 | Competitor copies the concept             | MEDIUM | Speed to market + compounding agent memory = moat. First-mover advantage. |
| 7 | Celery tasks fail silently               | MEDIUM | Robust error handling. Dead letter queue. Sentry alerts. Retry logic. |
| 8 | Scope creep during development            | MEDIUM | This roadmap. Phase-gated releases. Ship MVP fast, iterate. |
| 9 | Vector DB performance at scale            | LOW    | pgvector handles millions of vectors. Migrate to dedicated if needed later. |
| 10| Stripe integration complexity             | LOW    | Use Stripe Checkout + Customer Portal (hosted by Stripe). Minimal custom billing. |


# ============================================================================
# 17. FUTURE VISION (Post-Launch)
# ============================================================================

## 17.1 The North Star (12-18 months out)
"Kova Agent runs your complete social media presence autonomously for 30 days
while you're on vacation — and your audience never notices."

## 17.2 Future Capabilities
1. **Agent Marketplace**: Users create and share custom agent "skills" (e.g., "Real Estate Agent Pack" — knows how to create property listings across platforms)
2. **Revenue Attribution Engine**: Connect Kova to Stripe/Shopify/GA to trace: social post → website visit → purchase. Prove ROI.
3. **Content Mutation**: Post version A underperforms in 2 hours → system auto-generates version B with different hook, posts to remaining platforms
4. **Voice/Video Input**: Record a 30-second video explanation → agents transform it into written posts, audiograms, video clips for every platform
5. **Agency White-Label**: Agencies run Kova under their own brand for clients
6. **Open-Source Core**: Release a self-hosted community edition to build developer community + funnel to paid cloud version
7. **Mobile App**: PWA or native app for approve-on-the-go
8. **Enterprise SSO + Compliance**: SOC 2, SSO, audit logs for enterprise clients
9. **Predictive Audience Builder**: Agent suggests WHO to follow/engage with to grow optimally
10. **Cross-Platform Narrative Engine**: Maintain a single narrative across platforms that unfolds over weeks (episodic content)

## 17.3 The Endgame
Kova Agent becomes the default operating system for anyone's social media presence.
Not a tool they use. Not an app they open. An invisible intelligence that operates
on their behalf, growing their brand while they focus on their actual work.

Creator economy + AI autonomy = Kova Agent.


# ============================================================================
# END OF ROADMAP
# ============================================================================
# This document will be updated as we build and learn.
# Every PR should reference which phase/sprint/feature it addresses.
# When in doubt, refer back to Section 1: Core Philosophy.
# ============================================================================
