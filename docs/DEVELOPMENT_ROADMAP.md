# ============================================================================
# KOVA AGENT — DEVELOPMENT ROADMAP
# ============================================================================
# Autonomous Social Intelligence Platform
# "Your social media runs itself. You stay in control."
#
# This document is the SINGLE SOURCE OF TRUTH for building Kova Agent.
# Every decision, every sprint, every feature traces back to here.
# Last Updated: April 7, 2026
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
| Phase 5 | Post-Launch  | ⏳ Not Started | WhatsApp Intelligence, Meme Engine, Status Studio |
| Phase 6 | Post-Phase 5 | ⏳ Not Started | Kova Links, CTA System, Lead Inbox, Email Marketing, Superfan Workflows, Video AI, Revenue Attribution |
| Phase 7 | Post-Phase 6 | ⏳ Not Started | Commerce Pipeline, Revenue Prediction, Audience Genome, Kova Score, Network Intelligence, Strategic Foresight, Digital Business Passport |
| Phase 8 | Post-Phase 7 | ⏳ Deferred | White-label UI, Agent Marketplace, Open-source |

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
- ~~[ ] Advanced AI features (voice memo, video generation)~~ — Voice memo ✅ complete, Video AI → Phase 6 Sprint 6F

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


## ─── PHASE 6: Conversion Loop — "Close the Gap" (Post-Phase 5) ───
##
## THE PROBLEM THIS PHASE SOLVES:
## ─────────────────────────────
## Kova currently owns Research → Create → Schedule → Publish → Engage.
## But the value chain is: Content → Engagement → LEAD CAPTURE → NURTURE → SALE → LOYALTY.
## We DROP the user at lead capture. They scramble with Linktree + Mailchimp + Typeform +
## Google Analytics separately. An operating system doesn't have gaps in the middle.
##
## This phase closes the loop. After Phase 6, a business owner in Nairobi can go from
## "I have a KES 299/month Kova account" to "my social media generates measurable leads
## and revenue" — without leaving Kova. That's the operating system promise.
##
## ORIGIN: Expert consultation (April 2026) + MailerLite email-social integration analysis.
## Expert's core insight: "Key success depends on having a form — a Call to Action.
## Make sure content has a number, an email, or a link to click for more information.
## Have a back end where leads can be viewed and responded to."
##
## PRIORITY RATIONALE (Impact × Feasibility):
## P0 = Must build first. Unlocks everything else. Small-to-medium effort.
## P1 = Build once P0 is live. Creates the "operating system" differentiation.
## P2 = Build after P1. Deepens the moat. Loyalty + media intelligence.
## P3 = Build after P2. Full-cycle revenue attribution + design intelligence.

### Sprint 6A: Kova Links — Link-in-Bio + Landing Pages (P0) ⏳ NOT STARTED
##
## WHY THIS IS P0:
## Every social media post that says "link in bio" sends traffic somewhere.
## Right now, that somewhere is Linktree ($5-24/mo), a random website, or nowhere.
## Kova builds the content, schedules it, publishes it — then loses control at the
## most valuable moment: when someone actually wants to act. That's insane.
## Kova Links = we own that moment. And Linktree becomes unnecessary.
##

- [ ] New Django app: `apps/links/`
- [ ] **KovaPage model** — one landing page per user (upgradeable to multiple on higher plans)
  - Fields: user, slug (unique URL), title, bio, avatar, theme (preset color schemes),
    background_color, text_color, accent_color, custom_css (Pro+ plans only),
    is_published, visit_count, created_at, updated_at
  - URL pattern: `kovaagent.com/l/{slug}` or custom domain mapping (future)
- [ ] **KovaLink model** — individual links on the landing page
  - Fields: page (FK), title, url, icon (optional emoji/icon class), position (ordering),
    click_count, is_active, link_type (choices: url, email, phone, whatsapp, form),
    created_at, updated_at
  - Ordering: drag-and-drop via Alpine.js sortable
- [ ] **LinkClick model** — analytics per click
  - Fields: link (FK), clicked_at, referrer, user_agent, ip_hash (privacy-safe),
    country (GeoIP lookup), device_type (mobile/desktop/tablet), source_platform
    (which social platform drove the click — from UTM or referrer header)
- [ ] **KovaForm model** — embedded lead capture forms on landing pages
  - Fields: page (FK), title, description, fields_config (JSONField — defines form fields),
    submit_button_text, success_message, notification_email (where to send alerts),
    is_active, submission_count
  - Default fields_config: [{"name": "name", "type": "text", "required": true},
    {"name": "email", "type": "email", "required": true},
    {"name": "phone", "type": "tel", "required": false},
    {"name": "message", "type": "textarea", "required": false}]
- [ ] **FormSubmission model** — captured leads from forms
  - Fields: form (FK), data (JSONField — submitted field values), source_platform,
    source_post (FK to Post, nullable), utm_source, utm_medium, utm_campaign,
    ip_hash, submitted_at, is_read, is_contacted
- [ ] Landing page builder UI (HTMX-powered, live preview)
  - Theme selector (5-8 preset themes matching Kova brand aesthetic)
  - Link editor (add/remove/reorder/toggle links)
  - Form builder (toggle form on/off, customize fields)
  - Preview panel (mobile + desktop mockup)
  - URL: `/links/edit/`
- [ ] Public landing page renderer — `/l/{slug}/`
  - Fast server-rendered page (no auth required, minimal assets, fast LCP)
  - Mobile-optimized (most visitors come from social on phones)
  - Link click tracking (async — don't block redirect)
  - Form submission handler (HTMX — no page reload)
  - SEO: og:title, og:description, og:image meta tags
  - 2-3 max colors enforced (expert advice: "Content design should have 2 colours, maximum 3")
- [ ] Kova Links analytics dashboard — `/links/analytics/`
  - Total visits, click-through rate, top links, traffic by platform
  - Form submissions list with read/unread status
  - Time-series chart: visits + clicks over 30 days
  - Source breakdown: which social platform drives most traffic
- [ ] Plan limits: Free = 1 page, 5 links | Growth = 3 pages, 20 links, forms | Pro = unlimited, custom CSS, multiple forms
- DELIVERABLE: Users have a Kova-hosted link-in-bio page with lead capture forms. No Linktree needed.
- UNIQUENESS TEST: No competitor (Buffer, Hootsuite, Later, Sprout) has a built-in link-in-bio
  with AI-integrated lead capture. Linktree doesn't create content. Kova does both.
- **TECHNICAL NOTES:**
  - Public pages: WhiteNoise-served, cached aggressively (1hr TTL), invalidated on edit
  - Click tracking: fire-and-forget Celery task (don't slow down redirects)
  - Form submissions: rate-limited (10/min per IP) to prevent spam
  - GeoIP: django-geoip2 or ip-api.com free tier (1000 req/min)
  - Drag-and-drop: Alpine.js + SortableJS (already used in media queue)
  - Mobile-first: TailwindCSS responsive, no JS framework

### Sprint 6B: Smart CTA System (P0) ⏳ NOT STARTED
##
## WHY THIS IS P0:
## The expert was unambiguous: "Make sure the content has a number, an email, or a link
## to click for more information." Currently, Kova's Create Agent generates content with
## has_cta tracked in Content DNA, but there's no URL field, no phone field, no email field
## on the Post model, and no auto-UTM generation. CTAs are words without links.
##

- [ ] **Post model additions** (migration in `apps/content/`):
  - `cta_url` — CharField, nullable — the link attached to this post's CTA
  - `cta_type` — CharField choices: none, link, phone, email, whatsapp, kova_link
  - `cta_text` — CharField — the CTA copy (e.g., "Book a free consultation →")
  - `utm_source` — auto-populated from platform name
  - `utm_medium` — auto-populated as "social"
  - `utm_campaign` — auto-populated from content seed or user-defined campaign
  - `utm_content` — auto-populated from post ID (for A/B tracking)
  - `full_tracked_url` — property that builds the complete UTM-tagged URL
- [ ] **Auto-UTM generation** in Create Agent pipeline:
  - When user has a Kova Link page → auto-set `cta_url` to their landing page
  - When user provides a URL → auto-append UTM parameters
  - UTM format: `?utm_source={platform}&utm_medium=social&utm_campaign={seed_slug}&utm_content={post_id}`
  - Create Agent prompt update: "Include a CTA in every post. Reference the user's
    preferred CTA type (link, phone, WhatsApp, email) from their profile settings."
- [ ] **CTA preferences in UserProfile**:
  - `default_cta_type` — what kind of CTA to include by default
  - `default_cta_url` — default landing page or website URL
  - `cta_phone` — business phone number for phone CTAs
  - `cta_email` — business email for email CTAs
  - `cta_whatsapp` — WhatsApp number for WhatsApp CTAs
  - Settings UI: `/settings/cta/` — configure default CTA behavior
- [ ] **CTA performance tracking**:
  - Link `LinkClick` (from Sprint 6A) back to source Post via utm_content
  - New analytics view: "Which CTAs convert best?" — by type, by platform, by content DNA
  - Content DNA enhancement: track `cta_type` as a performance variable
  - Adapt Agent update: factor CTA performance into content strategy recommendations
- [ ] **Post editor CTA section**:
  - In post approval/edit UI: CTA type selector, URL field, preview of tracked URL
  - One-click "Use my Kova Link" button (auto-fills from user's landing page)
  - UTM preview: show exactly what URL will be used
- [ ] **Platform-specific CTA formatting**:
  - Twitter: URL at end of tweet (counts toward character limit — budget for it)
  - LinkedIn: URL in first comment (better for algorithm) — auto-generate comment
  - Instagram: "Link in bio" text + auto-update Kova Link page with post-specific link
  - Facebook: URL embedded in post or as link preview
  - TikTok: "Link in bio" reference
- DELIVERABLE: Every Kova post has a trackable CTA. Users can prove which posts drive traffic.
- **TECHNICAL NOTES:**
  - UTM generation: utility function in `apps/content/utils.py`
  - URL shortening: not initially (adds complexity). Use full UTM URLs.
  - LinkedIn first-comment: new field `first_comment` on Post model, auto-published after post
  - Instagram link-in-bio: auto-update KovaLink with latest post's destination URL

### Sprint 6C: Lead Inbox + CRM Lite (P1) ⏳ NOT STARTED
##
## WHY THIS IS P1:
## The expert said: "Have a back end where leads can be viewed and responded to."
## Once Kova Links captures leads (Sprint 6A) and CTAs drive traffic (Sprint 6B),
## users need a place to SEE and ACT on those leads. Without this, form submissions
## are just database rows nobody reads.
##
## This is NOT a full CRM. It's a "Lead Inbox" — think unified inbox but for leads,
## not social comments. Enough to respond, tag, and track. Not Salesforce.
##

- [ ] New Django app: `apps/leads/`
- [ ] **Lead model** — every person who submits a form, clicks a tracked link, or is captured from social
  - Fields: user (FK — the Kova user who owns this lead), name, email, phone,
    source_type (choices: form_submission, social_dm, social_comment, manual, api),
    source_platform (which social platform or "kova_links"),
    source_post (FK to Post, nullable — which post drove them),
    source_form (FK to KovaForm, nullable),
    status (choices: new, contacted, qualified, converted, lost),
    priority (choices: high, medium, low — auto-scored),
    tags (JSONField — user-defined labels like "interested in product X"),
    notes (TextField — user's private notes on this lead),
    metadata (JSONField — extra context from form or social),
    first_seen_at, last_activity_at, converted_at (nullable)
  - Unique constraint: (user, email) — prevents duplicate leads per user
  - Auto-dedup: if same email submits multiple forms, merge into one Lead record
- [ ] **LeadActivity model** — timeline of interactions with a lead
  - Fields: lead (FK), activity_type (choices: form_submitted, email_sent, email_opened,
    social_interaction, note_added, status_changed, phone_called, whatsapp_sent),
    description, metadata (JSONField), created_at
  - Auto-logged: form submissions, email sends, status changes
  - Manual: user adds notes, logs phone calls
- [ ] **Lead auto-scoring** (priority assignment):
  - High: submitted form + clicked multiple links + from LinkedIn (professional intent)
  - Medium: submitted form OR multiple link clicks
  - Low: single link click, no form submission
  - Score factors: source_platform, number of interactions, recency, form fields filled
  - AI scoring (Pro+ plans): Analyst Agent evaluates lead quality from form data + social context
- [ ] **Lead Inbox UI** — `/leads/`
  - Inbox-style list view: new leads highlighted, sortable by date/status/priority/platform
  - Filter: by status, priority, source platform, date range, tags
  - Lead detail view: full profile + activity timeline + source post + linked social interactions
  - Quick actions: change status, add note, send email (via Kova email system), tag
  - Bulk actions: mark as contacted, change priority, export CSV
- [ ] **Lead notifications**:
  - In-app notification when new lead captured
  - Email notification: "You got a new lead from Instagram!" (configurable frequency)
  - Daily Brief integration: "You captured 5 new leads yesterday. 2 are high-priority from LinkedIn."
  - Push notification (PWA): immediate alert for high-priority leads
- [ ] **Superfan → Lead bridge**:
  - When Engage Agent detects a Superfan (16+ interactions), auto-create a Lead record
  - Source type: `social_comment`, platform preserved, interaction history linked
  - Notification: "Your superfan @handle has engaged 20 times. They're now in your leads."
  - This closes the gap: Engage Agent identifies gold → Lead Inbox lets you act on it
- [ ] **Lead analytics dashboard** — `/leads/analytics/`
  - Total leads by source (pie chart: forms, social DMs, superfan conversions)
  - Lead-to-conversion funnel: new → contacted → qualified → converted (with drop-off rates)
  - Leads by platform (which social platform generates the most leads)
  - Leads by post (which content generates the most captures)
  - Response time tracking: how fast does the user follow up on new leads
- [ ] Plan limits: Free = view only (max 10 leads) | Growth = full inbox, 100 leads | Pro = unlimited, AI scoring, export
- DELIVERABLE: Users see leads in one place, get notified, can respond and track conversion.
- **TECHNICAL NOTES:**
  - Dedup: on FormSubmission save, check for existing Lead with same email → merge
  - Superfan bridge: signal on Superfan tier change → auto-create Lead
  - Email from inbox: reuse EmailService with new `lead_followup` email type
  - Export: CSV download via StreamingHttpResponse (no heavy libraries)

### Sprint 6D: Email Marketing Engine (P1) ⏳ NOT STARTED
##
## WHY THIS IS P1:
## The MailerLite article nails it: "You don't own your social media audience. You can wake
## up one morning to find your Facebook deleted." Email is the only channel where users OWN
## their audience. Kova currently has a transactional email system (receipts, briefs, team
## invites). This sprint adds MARKETING email: campaigns, lists, sequences.
##
## THE UNIQUE KOVA ANGLE:
## Nobody — not Mailchimp, not Buffer, not Hootsuite — has a system where the SAME AI that
## writes your social posts ALSO writes your email campaigns, using the SAME brand voice,
## the SAME Content DNA, the SAME learning loop. That's category-defining.
## Social + Email from one AI brain = Kova's unfair advantage.
##

- [ ] Extend `apps/emails/` (don't create new app — email infra already exists)
- [ ] **EmailSubscriber model** — the user's email audience
  - Fields: user (FK — the Kova user who owns this subscriber), email, name,
    source (choices: kova_form, manual_import, social_bio, api),
    source_post (FK to Post, nullable — which post or form captured them),
    status (choices: active, unsubscribed, bounced, complained),
    tags (JSONField — segmentation labels),
    engagement_score (0-100 — opens/clicks history),
    subscribed_at, unsubscribed_at (nullable),
    metadata (JSONField — extra context)
  - Unique constraint: (user, email) — one subscriber per email per Kova user
  - Auto-populate from Lead model: when a Lead has an email → auto-create subscriber (with consent flag)
  - GDPR compliance: double opt-in flow, unsubscribe link in every email, data export/deletion
- [ ] **EmailList model** — segmentation groups
  - Fields: user (FK), name, description, filter_rules (JSONField — dynamic segment definitions),
    subscriber_count (cached), is_smart (bool — auto-updating based on rules vs static list),
    created_at, updated_at
  - Smart lists: "All leads from Instagram", "Subscribers who opened last 3 emails",
    "High-engagement superfans"
  - Static lists: manual add/remove
- [ ] **EmailCampaign model** — broadcast emails
  - Fields: user (FK), name, subject, preview_text, html_content, text_content,
    from_name, reply_to, target_list (FK to EmailList), status (choices: draft,
    scheduled, sending, sent, cancelled), scheduled_at, sent_at, total_sent,
    total_opened, total_clicked, total_bounced, total_unsubscribed,
    ai_generated (bool — was content written by Create Agent),
    source_post (FK to Post, nullable — repurposed from a social post),
    created_at, updated_at
  - A/B testing: `variant_of` (FK to self) + `variant_label` (A/B) + `variant_percentage` (50/50)
- [ ] **EmailSequence model** — automated multi-step email flows
  - Fields: user (FK), name, trigger_type (choices: form_submission, tag_added,
    subscriber_added, lead_status_change, manual), is_active, created_at
  - Steps: `EmailSequenceStep` — sequence (FK), step_number, delay_days,
    delay_hours, subject, html_content, text_content, ai_generated
  - Example sequences:
    - Welcome sequence: Day 0 (welcome), Day 2 (introduce your story), Day 5 (best content roundup)
    - Re-engagement: Day 0 (we miss you), Day 3 (best of what you missed), Day 7 (special offer)
    - Lead nurture: Day 0 (thanks for reaching out), Day 1 (case study), Day 3 (book a call CTA)
- [ ] **AI email content generation** (Create Agent extension):
  - "Write an email campaign about [topic]" — same brand voice as social posts
  - "Turn this LinkedIn post into a newsletter" — social-to-email repurposing
  - "Write a 3-part welcome sequence" — AI generates full sequence from brand context
  - Content DNA applied: same attributes that work in social (has_cta, tone, topic) used in emails
  - Subject line A/B generation: Create Agent suggests 2-3 subject variants
- [ ] **Campaign builder UI** — `/emails/campaigns/new/`
  - Visual email editor (block-based, HTMX-powered, no WYSIWYG library dependency)
  - Template gallery: 8-10 pre-built email templates (announcement, newsletter, product, personal)
  - AI assist: "Generate email about..." button → Create Agent writes content
  - Preview: desktop + mobile mockup (inline)
  - Send test email, schedule, or send now
  - A/B setup: toggle variant mode, auto-split audience
- [ ] **Email analytics dashboard** — extends existing `/dashboard/emails/`
  - Campaign performance: opens, clicks, bounces, unsubscribes per campaign
  - Subscriber growth chart: new subscribers over time, by source
  - Engagement heatmap: what time do subscribers open emails (feed back to send-time optimization)
  - Top-performing emails: ranked by open rate, click rate
  - Social↔Email cross-analytics: "Subscribers who also engage on LinkedIn convert 3× more"
- [ ] **Social → Email integration** (the dynamic duo):
  - Social post → Newsletter: one-click "Send this post as email" on any published post
  - Email → Social: "Share in email" links in every campaign (social sharing buttons)
  - Facebook Custom Audiences: export subscriber list → upload to FB Ads (manual CSV for now)
  - Cross-platform retargeting: tag subscribers by which social platform they came from
  - Daily Brief addition: "Your email campaign 'Spring Sale' had 42% open rate. Your LinkedIn
    audience converts to subscribers 3× better than Twitter — consider more LinkedIn-to-email CTAs."
- [ ] **Compliance & deliverability**:
  - CAN-SPAM / GDPR: unsubscribe link in every email (auto-injected), physical address in footer
  - Double opt-in: optional per list (configurable) — `confirmation_email` type added to EmailService
  - Bounce handling: auto-deactivate emails after 3 consecutive bounces
  - Spam scoring: basic content checks (all caps, spammy words, link-to-text ratio)
  - Sending limits: rate-limited by plan (Free: 100/mo, Growth: 2,500/mo, Pro: 25,000/mo)
  - Resend integration: use existing Resend SMTP + webhooks (already built for transactional)
- [ ] Plan limits: Free = 100 emails/mo, 1 list, no sequences | Growth = 2,500/mo, 5 lists, 3 sequences |
  Pro = 25,000/mo, unlimited lists, unlimited sequences, A/B testing, AI email generation
- DELIVERABLE: Users can build email lists, send AI-written campaigns, and run automated sequences — all
  from the same platform that manages their social media, using the same AI brain and brand voice.
- UNIQUENESS TEST: No tool on the market has one AI that writes both social AND email content from
  a unified brand voice + Content DNA. Mailchimp has AI but doesn't do social. Buffer does social
  but has zero email. Kova is the first to unify both channels under one intelligence layer.
- **TECHNICAL NOTES:**
  - Email sending: Celery tasks, batched (not all at once), respect Resend rate limits
  - Templates: Django template engine (same as transactional emails), extend `base_email.html`
  - Unsubscribe: one-click header (`List-Unsubscribe-Post` RFC 8058) + footer link
  - Subscriber import: CSV upload with field mapping UI (name, email, tags)
  - Smart lists: filter_rules evaluated at send time (dynamic segment, not cached membership)

### Sprint 6E: Superfan Workflows + Loyalty Engine (P2) ⏳ NOT STARTED
##
## WHY THIS IS P2:
## The expert's 4th metric tier: "Loyalty — key metrics is shares and referrals to friends
## and relatives." Kova's Engage Agent already identifies Superfans (16+ interactions).
## But identification without action is waste. This sprint turns superfan DATA into
## superfan RELATIONSHIPS — automated thank-yous, referral triggers, ambassador programs.
##

- [ ] **SuperfanWorkflow model** — automated actions triggered by superfan behavior
  - Fields: user (FK), trigger_type (choices: tier_reached, interaction_count,
    consecutive_days_engaged, shared_post, referred_friend),
    action_type (choices: send_dm, send_email, add_tag, create_lead, notify_user),
    trigger_config (JSONField — e.g., {"tier": "SUPERFAN", "interaction_count": 20}),
    action_config (JSONField — e.g., {"dm_template": "Thanks for being amazing!"}),
    is_active, times_triggered, created_at
- [ ] **ReferralProgram model** — track shares and referrals
  - Fields: user (FK), referral_code (unique), reward_description,
    total_referrals, total_conversions, is_active
  - Linked to: KovaLink (add referral link to landing page), Post (include referral CTA)
- [ ] **ReferralTracking model** — individual referral events
  - Fields: program (FK), referred_by_superfan (FK to Superfan, nullable),
    referred_email, referred_name, status (clicked/signed_up/converted),
    referral_url, created_at, converted_at
- [ ] **Automated superfan actions**:
  - Auto-DM when someone reaches SUPERFAN tier: "You're one of our biggest supporters! [custom message]"
  - Auto-email: "Thank you for being a superfan — here's an exclusive [offer/content/preview]"
  - Auto-tag in Lead Inbox: superfans auto-tagged as "champion" → prioritized lead
  - Auto-notify user: "Congratulations! @handle just became a Superfan on Instagram"
  - Auto-share request: "Your superfan @handle shared 5 posts this month — consider featuring them"
- [ ] **Loyalty analytics dashboard** — `/engage/loyalty/`
  - Superfan growth: new superfans per week/month
  - Top advocates: ranked by shares, referrals, and interaction frequency
  - Referral funnel: clicks → signups → conversions (with attribution)
  - Share tracking: which content gets shared most, by which superfans
  - Lifetime engagement value: estimated impact of each superfan on reach
- [ ] **Engage Agent update**: factor loyalty signals into reply strategy
  - Superfans get priority in reply queue (faster AI response)
  - Reply tone for superfans: warmer, more personal, acknowledges history
  - Strategy suggestion: "You have 12 superfans on Twitter. Consider a dedicated thank-you thread."
- [ ] Plan limits: Free = view superfans only | Growth = basic workflows (3 triggers) |
  Pro = unlimited workflows, referral program, ambassador dashboard
- DELIVERABLE: Superfan identification leads to automated relationship-building and word-of-mouth growth.
- **TECHNICAL NOTES:**
  - DM sending: reuse platform provider `send_message()` methods (already exist for Twitter/IG)
  - Referral links: append `?ref={code}` to KovaLink URLs, track in LinkClick model
  - Workflow engine: simple Celery task triggered by Django signal on Superfan save/update

### Sprint 6F: Video Intelligence + Content Design Rules (P2) ⏳ NOT STARTED
##
## WHY THIS IS P2:
## Expert: "Video works best. Picture comes second. Story comes third. Plain text rarely attracts."
## Also: "Content design should have 2 colours, maximum 3. Anything beyond this is chaotic."
## Kova handles images. It doesn't touch video. And it has no color/design enforcement.
##

- [ ] **Video content support enhancements**:
  - `Post.media_type` field: choices: none, image, video, carousel, story, reel, poll
  - Video metadata: duration, aspect_ratio, has_captions, thumbnail_url on MediaAttachment
  - Video-specific metrics: `view_count`, `avg_watch_time`, `completion_rate` on PostMetric
  - Adapt Agent update: recommend video vs image vs text based on Content DNA performance data
    (e.g., "Videos on your Instagram get 3× more engagement than images — prioritize video seeds")
  - Create Agent update: when generating for video-first platforms (TikTok, YouTube, Reels),
    output a video script with: hook (first 3 seconds), body, CTA, suggested B-roll, caption text
- [ ] **AI video generation** (API-based, not local):
  - Integration options: RunwayML Gen-3, Pika Labs, or HeyGen for talking-head videos
  - Workflow: Create Agent writes script → Video API generates clip → user previews → approve → publish
  - Cost tier: Premium model tier (expensive — Pro plan only, with per-video billing)
  - MVP: 15-30 second clips, single aspect ratio (9:16 for Reels/TikTok/Shorts)
  - Fallback: if video generation fails, auto-generate image post as backup
- [ ] **Story/Reel templates**:
  - Template library: 10-15 story/reel structures (before/after, tutorial, day-in-life, Q&A,
    countdown, product showcase, testimonial)
  - Create Agent selects template based on content seed + platform
  - Output: structured story frames (slide 1: hook, slide 2: content, slide 3: CTA)
- [ ] **Content design rules** (brand kit enforcement):
  - UserProfile additions: `brand_colors` (JSONField — max 3 colors as hex values),
    `brand_font` (choice of web-safe fonts), `brand_logo_url`
  - Validation: reject color palette with 4+ colors in design prompts
  - Image generation prompt: "Use ONLY these colors: {brand_colors}. Maximum 3 colors."
  - Landing page (Kova Links): auto-apply brand colors to theme
  - Email templates: auto-apply brand colors to header/CTA buttons
  - Visual consistency score: Analyst Agent flags posts with off-brand colors
- [ ] **Content format recommendations** (data-driven):
  - New Content DNA attribute: `media_format` (video/image/carousel/text/story)
  - Adapt Agent: track engagement by media_format per platform → recommend optimal format
  - Daily Brief: "Your audience engages 2.5× more with video on TikTok. This week,
    3 of 5 posts are text-only. Consider adding video content."
  - Create Agent: auto-suggest media format at generation time
- [ ] Plan limits: Free = image only | Growth = video scripts + story templates |
  Pro = AI video generation (limited credits), brand kit enforcement
- DELIVERABLE: Kova recommends and creates the right media format for each platform,
  enforces brand design rules, and (on Pro plans) generates short-form video.
- **TECHNICAL NOTES:**
  - Video generation: API call from Create Agent, async Celery task, poll for completion
  - Video storage: upload to user's connected platform directly (no Kova hosting needed)
  - Brand colors: validated on save (max 3 colors, valid hex format)
  - Story frames: JSON structure → rendered as carousel preview in post editor

### Sprint 6G: Revenue Attribution + Payment Integration (P3) ⏳ NOT STARTED
##
## WHY THIS IS P3:
## Expert's 3rd metric tier: "Selling — key metrics is no. of sales made from social media
## i.e integrated with online payment systems or tracking of sales."
## Kova has a Conversion model (click/lead/sale) with UTM tracking — good architecture.
## But UTMs aren't auto-generated, and there's no direct payment system integration.
## This sprint connects the dots: post → click → sale → revenue attributed to post.
##

- [ ] **Auto-UTM system activation** (builds on Sprint 6B infrastructure):
  - Every published post auto-generates UTM parameters (no user action required)
  - UTM stored on Post model and embedded in CTA URL
  - Dashboard: "Revenue by Campaign" → shows which content seeds drive the most revenue
- [ ] **Shopify integration** (webhook-based):
  - User connects Shopify store via API key
  - Webhook listener: `orders/create` → extract UTM from order referring URL
  - Auto-create Conversion record: type=sale, revenue=order total, linked to Post via utm_content
  - Dashboard: "This Instagram post generated 12 sales (KES 45,000)"
- [ ] **M-Pesa integration** (for African e-commerce):
  - M-Pesa STK push payment tracking (already have M-Pesa for billing — extend for commerce)
  - Payment reference linking: include post_id in M-Pesa payment description
  - Auto-create Conversion: type=sale, revenue=amount, platform=whatsapp/other
  - Support: Daraja API (Safaricom) for payment confirmation webhooks
- [ ] **Google Analytics 4 sync** (optional):
  - GA4 Measurement Protocol: send Kova post events → GA4 for cross-platform attribution
  - Import GA4 conversion events → Kova (sync UTM-tagged conversions back)
  - Benefit: users who already have GA4 don't need to change their setup
- [ ] **Multi-touch attribution** (Pro plan):
  - Current: last-click only (whoever clicked last gets credit)
  - Enhancement: track full journey (first touch, assists, last touch)
  - Model: weighted attribution (40% first touch, 20% each assist, 40% last touch)
  - Dashboard: "This person saw your Twitter thread → clicked LinkedIn post → bought from Instagram link"
- [ ] **Revenue dashboard enhancement** — extends existing `/analytics/` attribution view:
  - Revenue by platform (which social platform drives the most sales)
  - Revenue by content type (videos sell more than text? Images more than threads?)
  - Revenue by CTA type (link CTAs vs WhatsApp CTAs vs phone CTAs)
  - ROI calculator: "You spent KES 299/month on Kova. Your social content generated KES 145,000 in tracked sales.
    ROI: 48,400%." — THIS is the number that prevents churn.
  - Weekly email: "Your weekly revenue attribution: 8 sales (KES 23,400) tracked to social media"
- [ ] Plan limits: Free = basic UTM tracking | Growth = Shopify + M-Pesa + revenue dashboard |
  Pro = GA4 sync, multi-touch attribution, ROI reporting, weekly revenue emails
- DELIVERABLE: Users can prove exactly how much money their social media generates.
  This is the #1 feature that justifies the subscription — when users see ROI, they never churn.
- **TECHNICAL NOTES:**
  - Shopify webhook: new endpoint in `apps/api/` with HMAC verification
  - M-Pesa: extend existing `apps/billing/mpesa.py` Daraja integration
  - GA4: Measurement Protocol v2 (server-side events, no client JS needed)
  - Attribution: new `ConversionTouchpoint` model for multi-touch journey tracking

### Phase 6 — Key Metrics (How We Know It's Working)
| Metric | Target | How Measured |
|--------|--------|-------------|
| Kova Links adoption | 60%+ of active users create a landing page within 2 weeks | KovaPage created_at vs user signup date |
| Form submission rate | 5%+ of landing page visitors submit a form | FormSubmission count / KovaPage visit_count |
| Lead-to-contacted rate | 50%+ of leads contacted within 48 hours | Lead.status change timestamps |
| Email subscriber growth | 20%+ month-over-month growth per active user | EmailSubscriber growth rate by user |
| CTA click-through rate | 2%+ average across all posts with tracked CTAs | LinkClick count / Post impressions |
| Revenue attribution | 30%+ of Pro users track at least 1 sale back to social | Conversion records with type=sale |
| Churn reduction | 40% lower churn for users with active Kova Links + Email | Subscription cancellation rate segmented by feature usage |

### Phase 6 — Technical Architecture Notes
- **No new external services** for P0/P1: everything runs on existing stack (Django, Celery, Resend, PostgreSQL)
- **Resend scales**: currently used for transactional email only. Resend supports marketing email
  at same API/SMTP setup. No migration needed. Just higher volume.
- **Database**: new models add ~8 tables. All have created_at indexes for time-series queries.
  Estimated row growth: ~10K leads/mo, ~50K link clicks/mo, ~100K email events/mo at 1000 active users.
- **Celery tasks**: 4 new periodic tasks:
  - `process-form-submissions` (real-time via webhook or every 5 min batch)
  - `send-email-campaigns` (on-demand, rate-limited per plan)
  - `run-superfan-workflows` (every 30 min, after engage cycle)
  - `sync-conversion-events` (every hour, from Shopify/GA4 webhooks)
- **Plan enforcement**: extend existing `PlanEnforcementMiddleware` with new limits


## ─── PHASE 7: Business Intelligence OS — "See What Nobody Else Can See" (Post-Phase 6) ───
##
## THE CATEGORY SHIFT THIS PHASE CREATES:
## ───────────────────────────────────────
## After Phase 6, Kova is a Social Media Operating System — content, engagement, leads, email, revenue.
## After Phase 7, Kova becomes a BUSINESS INTELLIGENCE OPERATING SYSTEM — it doesn't just help
## businesses DO things (post, email, capture). It helps businesses KNOW things (predict, decide, evolve).
##
## Every tool in the market is an ACTION tool. None is a KNOWLEDGE tool.
## Phase 7 makes Kova the first platform that turns social media data into business intelligence
## that users cannot get anywhere else — not from Buffer, not from HubSpot, not from Google Analytics.
##
## MISSION: "Kova doesn't just run your social media. Kova tells you where your business should go next."
##
## RANKING: These 7 inventions are ordered by value addition to the BIOS mission.
## Each builds on the data layer before it, creating compounding intelligence.
##
## Data dependency chain:
## Sprint 7A (Commerce Pipeline) → 7B (Revenue Prediction) → 7C (Audience Genome)
## → 7D (Kova Score) → 7E (Network Intelligence) → 7F (Strategic Foresight)
## → 7G (Digital Business Passport)
##
## Each sprint generates data that the next sprint consumes. This ISN'T arbitrary ordering —
## it's an intelligence pipeline where each layer makes the next layer smarter.

### Sprint 7A: Autonomous Content-to-Commerce Pipeline ⏳ NOT STARTED
## ──────────────────────────────────────────────────────
## VALUE RANK: #1 — Highest Immediate Value
## BIOS CONTRIBUTION: Closes the last human bottleneck. After this, content → money is fully autonomous.
## PREREQUISITE: Phase 6 complete (Kova Links, CTA system, Lead Inbox, Email sequences)
## GENERATES DATA FOR: Revenue Prediction (7B), Audience Genome (7C), Kova Score (7D)
##
## THE INVISIBLE PROBLEM:
## Business owners miss 80% of buying signals buried in their social comments and DMs.
## Someone comments "How much?" at 11pm. The owner sees it at 8am. The buyer already
## found a competitor. Average social inquiry response time: 5+ hours. Purchase intent
## decay: 50% lost after 30 minutes. The content works. The human-speed response kills it.
##

- [ ] **CommercialIntentDetector** — AI classifier in Engage Agent
  - Input: incoming comments, DMs, mentions across all platforms
  - Classification: COMMERCIAL (price inquiry, availability check, order request, location question,
    delivery inquiry, booking request) vs NON-COMMERCIAL (praise, question, opinion, spam)
  - Confidence scoring: 0-100 (auto-act above 85, flag for review 60-84, ignore below 60)
  - Training: fine-tuned on Kova network data (across all users' commercial interactions)
  - Multi-language: English, Swahili, Sheng detection + response in same language
  - Context awareness: distinguish "How much?" (buying) from "How much effort?" (discussion)

- [ ] **AutoCommerceResponse model** — auto-generated commercial replies
  - Fields: interaction (FK), intent_type (choices: price_inquiry, availability_check,
    booking_request, delivery_inquiry, bulk_order, custom_order, comparison_question),
    confidence_score, auto_reply_text, product_info_attached (JSONField — catalog items),
    follow_up_channel (choices: dm, email, whatsapp, kova_link),
    lead_created (FK to Lead), sequence_triggered (FK to EmailSequence),
    conversion_value_estimate (Decimal — AI-estimated deal value),
    status (choices: auto_sent, pending_review, user_edited, cancelled), created_at

- [ ] **Product/Service Catalog model** — user's offerings (used by commerce AI)
  - Fields: user (FK), name, description, price, currency, price_range_min, price_range_max,
    category, image_url, availability_status (in_stock/out_of_stock/made_to_order),
    delivery_zones (JSONField — areas served), lead_time_days,
    payment_methods (JSONField — M-Pesa, bank, card, cash), is_active
  - Purpose: Engage Agent pulls from catalog to answer "How much?" accurately
  - Import: manual entry or CSV upload (future: Shopify sync from Phase 6G)

- [ ] **Commerce automation pipeline** (the full auto-flow):
  ```
  Comment/DM detected
  → Intent classifier: COMMERCIAL (confidence: 92%, type: price_inquiry)
  → Catalog lookup: match "wedding cake" → product "3-Tier Wedding Cake, KES 15,000-25,000"
  → Auto-reply drafted: "Thanks for your interest! Our 3-tier wedding cakes start at KES 15,000.
     I'll send you our full catalog and delivery info 🎂"
  → Auto-DM: product link (Kova Link) + price sheet + WhatsApp CTA
  → Lead auto-created: source=Instagram comment, interest="3-tier cake", value_est=KES 15,000
  → Email sequence triggered: "Product inquiry" (3-part nurture)
  → If M-Pesa active: payment link included in follow-up message
  → Notification to owner: "High-intent lead captured. Est. value: KES 15,000. Nurture running."
  ```

- [ ] **Commerce settings UI** — `/settings/commerce/`
  - Toggle commerce detection on/off per platform
  - Set confidence threshold for auto-responses (default: 85)
  - Manage product catalog (CRUD)
  - Configure default follow-up channel (DM, email, WhatsApp)
  - Review auto-responses before they fire (optional human-in-loop mode)
  - Templates: customize auto-reply templates by intent type

- [ ] **Commerce dashboard** — `/analytics/commerce/`
  - Commercial intents detected this week/month
  - Auto-response success rate (replied → lead created → converted)
  - Response time comparison: AI response (seconds) vs manual response (hours)
  - Revenue captured from auto-commerce (linked to Conversion model)
  - Missed opportunities: commercial intents that weren't acted on
  - Top products/services inquired about (demand intelligence)

- [ ] **Daily Brief integration**:
  - "While you slept, Kova detected 7 buying signals, auto-responded to 5,
    created 3 high-intent leads, and started 2 nurture sequences.
    Estimated pipeline value: KES 67,000."

- [ ] Plan limits: Free = detection only (alerts, no auto-response) | Growth = auto-response,
  10 catalog items, DM follow-up | Pro = full pipeline, unlimited catalog, email+WhatsApp
  follow-up, AI deal value estimation
- DELIVERABLE: Social engagement automatically triggers sales pipeline. Content literally sells itself.
  The user wakes up to captured leads and running nurture sequences — not missed comments.
- UNIQUENESS TEST: No social media tool auto-detects commercial intent in comments and triggers
  a lead → nurture → payment pipeline. Hootsuite has auto-responses but they're template-based,
  not intent-aware. Sprout has smart inbox but routes to humans. Kova is the first to close
  the loop autonomously.
- **TECHNICAL NOTES:**
  - Intent classifier: LLM-based (Workhorse tier model), not traditional ML (no training data needed initially)
  - Catalog matching: fuzzy text match on product names + LLM context (handles "that blue cake" → Birthday Cake - Blue Theme)
  - Response time: target <60 seconds from comment to auto-reply (Celery task priority: HIGH)
  - Rate limiting: max 50 auto-responses/hour per user (prevent spam-like behavior on platforms)
  - Platform compliance: respect each platform's automation policies (Twitter: no auto-DM spam, etc.)

### Sprint 7B: Revenue Prediction Engine — "Know Before You Post" ⏳ NOT STARTED
## ──────────────────────────────────────────────────────────────────
## VALUE RANK: #2 — Core Intelligence Layer
## BIOS CONTRIBUTION: Turns content from a "hope-based activity" into an "investment with projected returns."
## PREREQUISITE: Sprint 7A + Phase 6 revenue attribution data (minimum 90 days of conversion data per user)
## GENERATES DATA FOR: Kova Score (7D), Strategic Foresight (7F)
##
## THE INVISIBLE PROBLEM:
## Every business posts content and HOPES it leads to money. They see analytics AFTER the fact.
## "That post got 500 likes." So what? Did it make money? Will the next one?
## Nobody can answer: "If I create X content this month, how much revenue will it likely generate?"
## Because nobody has the full data chain: content attributes → engagement → leads → revenue.
## After Phase 6 + Sprint 7A, Kova does.
##

- [ ] **RevenuePrediction model** — per-post revenue forecast
  - Fields: post (FK), predicted_revenue (Decimal), confidence_interval_low (Decimal),
    confidence_interval_high (Decimal), prediction_factors (JSONField — what drove the prediction),
    actual_revenue (Decimal, nullable — filled when conversions tracked),
    prediction_accuracy (Float, nullable — actual vs predicted),
    model_version (CharField — track prediction model iterations), created_at
  - Populated: at post creation time (before publishing), updated when conversions roll in

- [ ] **ContentRevenueProfile** — per-user revenue patterns learned from history
  - Fields: user (FK), profile_data (JSONField — the learned patterns), data_points_count,
    last_calculated_at, confidence_level (choices: low/medium/high — based on data volume)
  - Profile structure:
    ```json
    {
      "revenue_by_topic": {"wedding_cakes": 15200, "birthday_cakes": 8400, "tutorials": 1200},
      "revenue_by_format": {"video": 12800, "image": 5600, "carousel": 3200, "text": 400},
      "revenue_by_platform": {"instagram": 18400, "facebook": 5200, "whatsapp": 3600},
      "revenue_by_cta_type": {"whatsapp": 14200, "link": 5800, "phone": 3200, "email": 1400},
      "revenue_by_day": {"thursday": 5800, "tuesday": 4200, "monday": 3100},
      "revenue_by_hour": {"9": 2400, "13": 3100, "18": 4800},
      "avg_revenue_per_post": 2840,
      "avg_leads_per_post": 1.8,
      "avg_lead_to_conversion_rate": 0.23,
      "avg_conversion_value": 12400,
      "high_value_content_dna": {"format": "video", "tone": "educational", "has_cta": true, "topic": "wedding"}
    }
    ```
  - Recalculated: weekly via Celery task (rolling 90-day window)

- [ ] **MonthlyRevenueForecast model** — projected monthly revenue from content plan
  - Fields: user (FK), month, year, projected_revenue, projected_leads, projected_conversions,
    content_plan_summary (JSONField — what's planned), actual_revenue (filled end of month),
    forecast_accuracy, created_at
  - Generated: 1st of each month + updated weekly as content is published/tracked

- [ ] **Prediction engine** (in Analyst Agent):
  - Inputs: Content DNA attributes, platform, posting time, CTA type, media format,
    historical performance for similar content, product catalog pricing
  - Model: LLM-based pattern matching initially (no ML model training needed),
    with rule-based adjustments from ContentRevenueProfile
  - Output: revenue prediction + confidence interval + factors explanation
  - Example: "This video post about wedding cakes on Instagram with WhatsApp CTA
    is predicted to generate KES 8,000-15,000 in revenue (confidence: medium).
    Factors: wedding content averages KES 12,400 revenue, video format +80% vs text,
    Thursday posting +35%, WhatsApp CTA converts 3× better than link CTA."

- [ ] **Revenue optimization suggestions**:
  - Create Agent integration: "You're planning 8 posts this week. Projected revenue: KES 42,000.
    Swap post #3 from text→video (+KES 4,200 projected). Change post #6 CTA from link→WhatsApp
    (+KES 2,800 projected). Optimized projection: KES 49,000."
  - Auto-optimize mode (Pro plan): AI automatically adjusts content plan to maximize projected revenue
  - Content seed suggestions: "Based on revenue patterns, create more [topic] content with
    [format] and [CTA type]. Projected uplift: KES X per month."

- [ ] **Revenue prediction dashboard** — `/analytics/revenue-forecast/`
  - Monthly forecast widget: "This month's projected revenue: KES 165,000 (82% of target)"
  - Revenue by content category: which topics/formats generate the most money
  - Prediction accuracy tracker: how good are our forecasts (improves over time)
  - Content investment calculator: "If you create X more [type] posts, estimated additional revenue: KES Y"
  - Historical: predicted vs actual revenue per month (builds trust in the system)

- [ ] **Daily Brief integration**:
  - "Your content plan this week projects KES 47,000 in revenue.
    To hit your KES 65,000 target: publish 4 more video posts about [topic]
    with WhatsApp CTAs. Estimated uplift: KES 18,000 (±5K)."
  - "Post #42 (wedding cake tutorial) is tracking at KES 12,800 in attributed revenue—
    your highest-performing post this month. Create Agent has generated 3 similar content
    seeds for your approval."

- [ ] Plan limits: Free = view past revenue data only | Growth = basic per-post predictions |
  Pro = monthly forecasts, optimization suggestions, auto-optimize mode
- DELIVERABLE: Content becomes a measurable investment. Users see projected returns BEFORE posting.
  Monthly revenue forecasts replace guesswork with data-driven targets.
- UNIQUENESS TEST: No social media tool predicts revenue per post. Analytics tools show
  what happened. Ad platforms predict ROAS on paid campaigns. Nobody predicts organic content
  revenue. Kova is the first because it has the only complete data chain: content DNA →
  engagement → leads → conversions → revenue.
- **TECHNICAL NOTES:**
  - Minimum data requirement: 50+ posts with tracked conversions before predictions activate
  - Cold start: until enough data, show industry benchmarks from Network Intelligence (7E)
  - Accuracy tracking: prediction_accuracy stored per post, used to calibrate future predictions
  - LLM cost: one prediction call per post (Workhorse tier), cached in RevenuePrediction model
  - Recalibration: weekly Celery task recalculates ContentRevenueProfile, adjusts all active predictions

### Sprint 7C: Audience Genome — "Know Your People Deeper Than They Know Themselves" ⏳ NOT STARTED
## ──────────────────────────────────────────────────────────────────────────────────────────
## VALUE RANK: #3 — Deepest Intelligence Layer
## BIOS CONTRIBUTION: Transforms blind content creation into precision-targeted communication.
## PREREQUISITE: Phase 6 data (leads, email engagement) + Sprint 7A (commerce signals)
## GENERATES DATA FOR: Kova Score (7D — audience quality signal), Network Intelligence (7E),
##                     Strategic Foresight (7F — trend detection from audience behavior shifts)
##
## THE INVISIBLE PROBLEM:
## Businesses think they know their audience. They don't. They know demographics (25-34, female, Nairobi).
## They have no idea: what makes their audience SAVE vs like (intent signal), when they're in
## "buying mode" vs "browsing mode," which competitors they follow, what they complain about
## to OTHER brands (unmet needs), or how their interests are SHIFTING over time.
## Current analytics tools show WHAT happened. The Audience Genome shows WHO your people are,
## what they WANT, and what they'll do NEXT.
##

- [ ] **AudienceGenome model** — living psychographic map per user
  - Fields: user (FK), genome_data (JSONField — the full genome structure),
    data_points_analyzed (Integer), confidence_level (low/medium/high),
    last_calculated_at, version (Integer — track genome evolution)
  - Genome structure (4 layers):
    ```json
    {
      "behavioral_dna": {
        "content_preferences": {
          "video": {"engagement_multiplier": 3.2, "save_rate": 0.08, "share_rate": 0.04},
          "image": {"engagement_multiplier": 1.8, "save_rate": 0.05, "share_rate": 0.02},
          "text": {"engagement_multiplier": 0.6, "save_rate": 0.01, "share_rate": 0.01}
        },
        "topic_affinity": {
          "wedding_cakes": {"score": 92, "trend": "rising", "revenue_correlation": 0.87},
          "tutorials": {"score": 78, "trend": "stable", "revenue_correlation": 0.45},
          "behind_the_scenes": {"score": 65, "trend": "declining", "revenue_correlation": 0.12}
        },
        "platform_behavior": {
          "instagram": {"primary_action": "save", "peak_hours": [9, 13, 19], "avg_session": "browse_to_buy"},
          "linkedin": {"primary_action": "comment", "peak_hours": [8, 12, 17], "avg_session": "professional"},
          "tiktok": {"primary_action": "share", "peak_hours": [20, 21, 22], "avg_session": "entertainment"}
        },
        "engagement_triggers": ["educational_content", "price_transparency", "video_tutorials", "local_references"]
      },
      "interest_evolution": {
        "rising": [{"topic": "delivery_service", "growth_rate": 230, "signal_source": "comments+dms"}],
        "declining": [{"topic": "store_visit", "decline_rate": 40, "since": "2026-01"}],
        "seasonal": [{"topic": "christmas_cakes", "peak_months": [11, 12], "avg_uplift": 180}],
        "emerging": [{"topic": "vegan_options", "first_detected": "2026-03", "mentions": 23}]
      },
      "commercial_intent": {
        "high_intent_signals": ["saves_product_posts", "clicks_pricing_links", "dms_about_availability"],
        "conversion_segments": {
          "hot": {"size_pct": 8, "avg_conversion_time_days": 3, "avg_order_value": 15000},
          "warm": {"size_pct": 22, "avg_conversion_time_days": 14, "avg_order_value": 8000},
          "cold": {"size_pct": 70, "avg_conversion_time_days": null, "avg_order_value": null}
        },
        "price_sensitivity": "medium",
        "purchase_cycle_avg_days": 12
      },
      "relationship_depth": {
        "passive_followers_pct": 65,
        "active_engagers_pct": 22,
        "advocates_pct": 8,
        "customers_pct": 4,
        "churning_pct": 1,
        "churn_risk_indicators": ["engagement_drop_14d", "unfollow_after_promo_content"]
      }
    }
    ```

- [ ] **AudienceShift model** — detected changes in audience behavior
  - Fields: user (FK), shift_type (choices: interest_rising, interest_declining,
    behavior_change, sentiment_shift, demand_signal, churn_risk),
    description, evidence (JSONField — supporting data points),
    magnitude (low/medium/high), detected_at, is_acted_on,
    suggested_action, suggested_content_seed (text)

- [ ] **Genome computation engine** (new Celery task: `compute-audience-genome`, weekly):
  - Aggregates: PostMetric data (engagement patterns by content type, time, topic),
    Lead data (source, conversion rate, interests), Interaction data (comment sentiment,
    DM topics, engagement frequency), Superfan data (advocate behavior patterns),
    EmailSubscriber data (open/click patterns, segment behavior),
    Conversion data (purchase patterns, values, triggers)
  - LLM analysis layer: interprets raw data into human-readable genome narrative
  - Change detection: compares current genome vs previous version, generates AudienceShift records

- [ ] **Audience Genome dashboard** — `/analytics/audience/`
  - Visual genome map: interactive display of all 4 layers
  - Interest heatmap: which topics are hot/cold/rising/declining
  - Segment breakdown: hot/warm/cold audience with conversion probabilities
  - Behavior trends: how audience behavior is changing over time
  - Demand signals: "Your audience is asking about [X] — consider building this into your offerings"
  - Churn alerts: "15 superfans haven't engaged in 14 days. Risk of losing 40% within 7 days."

- [ ] **Agent integrations** (genome feeds intelligence to ALL agents):
  - **Create Agent**: "Write about [topic] because audience affinity score is 92 and rising.
    Use video format (3.2× engagement multiplier). Include price transparency (engagement trigger)."
  - **Adapt Agent**: "Schedule for 9am Instagram, 12pm LinkedIn (peak buying hours for your audience).
    Avoid 3-5pm TikTok (your audience browses but doesn't buy during this window)."
  - **Research Agent**: "Your audience's rising interest in 'delivery service' (230% growth in comments)
    suggests content about delivery logistics would resonate. Here are trending angles."
  - **Engage Agent**: "This commenter is in the 'hot' segment (8% of audience, 3-day avg conversion).
    Prioritize response. Use commercial intent pipeline."
  - **Strategist Agent**: "Audience genome shows 'behind the scenes' content declining in interest.
    Reduce from 3/week to 1/week. Reallocate to 'tutorial' content (rising, high revenue correlation)."

- [ ] **Product intelligence** (genome as business advisor):
  - Demand detection: "Your audience mentioned 'delivery' in 67 comments and 12 DMs this month.
    Consider adding delivery service — estimated demand: 200+ potential customers."
  - Pricing insight: "Audience commercial_intent shows medium price sensitivity. Your competitors
    charge KES 15K-25K. Your KES 8K pricing may signal lower quality. Test at KES 12K."
  - New product suggestions: "Emerging interest in 'vegan options' (23 mentions since March).
    No content about this yet. First-mover content opportunity."

- [ ] Plan limits: Free = basic content preferences only | Growth = full 4-layer genome,
  monthly audience shifts | Pro = weekly genome updates, demand signals, product intelligence,
  agent genome integration
- DELIVERABLE: Living psychographic intelligence that makes every agent smarter and gives users
  business insights no survey, analytics tool, or focus group could provide — because it's
  built from REAL behavior, not self-reported preferences.
- UNIQUENESS TEST: Sprout Social has audience demographics. Hootsuite has basic sentiment.
  Buffer has optimal posting times. NOBODY builds a multi-layer psychographic genome from
  the combined data of content performance + lead behavior + email engagement + purchase patterns.
  That data combination exists ONLY in Kova after Phase 6.
- **TECHNICAL NOTES:**
  - Computation cost: 1 LLM call per user per week (Workhorse tier), processes aggregated data
  - Storage: genome_data is ~5-10KB JSON per user, acceptable for PostgreSQL JSONField
  - Privacy: genome describes aggregate audience behavior, not individual people. No PII stored.
  - Cold start: genome activates after 30+ published posts with engagement data
  - Visualization: Chart.js heatmaps + Alpine.js interactive panels (existing stack)

### Sprint 7D: Kova Score — Digital Brand Credit Score ⏳ NOT STARTED
## ──────────────────────────────────────────────────────
## VALUE RANK: #4 — Quantified Trust Layer
## BIOS CONTRIBUTION: Turns invisible digital presence into a quantifiable, verifiable, bankable asset.
## PREREQUISITE: Sprints 7A-7C (commerce data + revenue predictions + audience quality signals)
## GENERATES DATA FOR: Network Intelligence (7E — benchmark scoring), Digital Business Passport (7G)
##
## THE INVISIBLE PROBLEM:
## In Africa (and emerging markets), businesses struggle with TRUST. Follower counts are fake.
## Engagement can be bought. There's no verified, standardized measure of digital brand health.
## A customer can't tell if an Instagram bakery is legit. A bank can't value a business's
## digital presence for a loan. A partner can't verify influence is real.
## The infrastructure of digital trust doesn't exist. Kova builds it.
##

- [ ] **KovaScore model** — composite brand health score per user
  - Fields: user (FK), score (Integer 0-1000), tier (choices: emerging 0-299,
    growing 300-549, established 550-749, premium 750-899, elite 900-1000),
    components (JSONField — individual signal scores), calculated_at,
    score_trend (choices: rising, stable, declining), trend_magnitude (Float),
    percentile_in_industry (Float — where they rank vs peers),
    is_verified (Bool — passed Kova verification checks), verification_date
  - Score components (weighted):
    ```json
    {
      "content_consistency": {"score": 85, "weight": 0.15, "factors": "312 posts in 12 months, 92% weekly consistency"},
      "audience_growth": {"score": 72, "weight": 0.15, "factors": "18% organic growth, no purchased followers detected"},
      "engagement_depth": {"score": 88, "weight": 0.15, "factors": "4.2% engagement rate, high comment/save ratio"},
      "sentiment_health": {"score": 76, "weight": 0.10, "factors": "82% positive sentiment, 12% neutral, 6% negative"},
      "response_reliability": {"score": 91, "weight": 0.10, "factors": "12 min avg response time, 94% response rate"},
      "lead_conversion": {"score": 68, "weight": 0.10, "factors": "23% lead-to-customer rate, up from 18% last quarter"},
      "revenue_attribution": {"score": 82, "weight": 0.10, "factors": "KES 180K/month tracked social revenue, stable trend"},
      "platform_diversity": {"score": 70, "weight": 0.05, "factors": "7/9 platforms active, not dependent on single channel"},
      "content_quality": {"score": 80, "weight": 0.10, "factors": "Content DNA: high originality, strong CTA effectiveness"}
    }
    ```
  - Recalculated: weekly via Celery task `compute-kova-scores`

- [ ] **KovaScoreHistory model** — track score evolution over time
  - Fields: user (FK), score, components_snapshot (JSONField), calculated_at
  - Retained: monthly snapshots for long-term trend analysis (daily for current quarter)

- [ ] **ScoreVerification model** — verification checks passed
  - Fields: user (FK), check_type (choices: identity_confirmed, business_registered,
    phone_verified, website_verified, social_accounts_authentic,
    revenue_data_validated, content_original),
    status (passed/failed/pending), verified_at, evidence (JSONField)
  - Verified scores carry the "Kova Verified" badge (higher trust weight)

- [ ] **Score computation engine** (Celery task: `compute-kova-scores`, weekly):
  - Pulls from: PostMetric (consistency, engagement), AudienceGenome (growth patterns),
    Interaction (response time, sentiment), Lead (conversion rate), Conversion (revenue),
    Post (content quality via Content DNA), SocialAccount (platform diversity)
  - Anti-gaming: detect and penalize purchased followers (sudden spikes without engagement),
    fake engagement (like bursts without profile diversity), content plagiarism (via Content DNA uniqueness)
  - Confidence rating: score reliability increases with account age and data volume

- [ ] **Kova Score badge system** — embeddable trust badges
  - Badge types: "Kova Verified — Score: 812", "Kova Established Business",
    "Fast Responder", "Revenue Verified", "Top 10% in [Industry]"
  - Embed code: HTML snippet for websites, email signatures
  - Social proof: badge displays on user's Kova Link landing page
  - WhatsApp Business: badge image for profile photo overlay
  - Badge verification: public URL `kovaagent.com/verify/{user_slug}` shows live score + verification status

- [ ] **Score insights dashboard** — `/analytics/kova-score/`
  - Score overview: current score, tier, trend, industry percentile
  - Component breakdown: radar chart (9 signals), with improvement suggestions per signal
  - Score history: line chart over time (monthly trajectory)
  - Improvement actions: "To increase your score from 720 to 800: improve response time
    (currently 45 min, target: <20 min), increase video content ratio (currently 20%, target: 50%),
    track revenue attribution for at least 5 more posts."
  - Industry comparison: "Your score: 720 (Top 30% in Hospitality in Nairobi)"
  - Badge manager: generate and copy embed codes

- [ ] **External value channels** (future API integrations):
  - Banking API: anonymized Kova Score data available to partner banks (with user consent)
    for alternative credit assessment. Revenue share model: Kova earns per credit inquiry.
  - Marketplace presence: Kova Score visible in user discovery / collaboration features
  - Partnership matching: businesses can find collaborators filtered by score + industry + location

- [ ] Plan limits: Free = view your score only | Growth = score + history + improvement suggestions +
  basic badge | Pro = verified badge, industry benchmarks, embeddable badges, banking data sharing opt-in
- DELIVERABLE: Every Kova business has a quantified, verified digital brand score. Scores build trust
  with customers, unlock banking products, enable quality partnerships, and make digital presence
  a measurable business asset.
- UNIQUENESS TEST: No social media tool quantifies brand health into a single, verified score.
  Klout tried (2008-2018) and failed — they only measured social influence, not business performance.
  Kova Score is fundamentally different: it measures BUSINESS health (revenue, conversions, response time,
  content quality) not vanity metrics (followers, likes). It's a business credit score, not an influence score.
- **TECHNICAL NOTES:**
  - Score computation: aggregation queries + 1 LLM call per user for narrative explanation (Workhorse tier)
  - Anti-gaming: statistical anomaly detection (follower growth rate vs engagement rate correlation)
  - Badge verification: public endpoint, no auth required, cached 1 hour, rate-limited
  - Banking API: future development, requires data partnership agreements + GDPR/data protection compliance
  - Storage: KovaScoreHistory grows ~52 rows/user/year (weekly). At 10K users = 520K rows/year — negligible

### Sprint 7E: Network Intelligence — "See What No Individual Can See" ⏳ NOT STARTED
## ──────────────────────────────────────────────────────────────────────
## VALUE RANK: #5 — Aggregate Intelligence Layer
## BIOS CONTRIBUTION: Individual analytics show YOUR data. Network Intelligence shows THE MARKET.
## PREREQUISITE: Meaningful user base (500+ active users minimum for statistical significance)
## GENERATES DATA FOR: Strategic Foresight (7F), Digital Business Passport (7G — industry benchmarks)
##
## THE INVISIBLE PROBLEM:
## Every Kova user operates in isolation. They see THEIR analytics, THEIR audience, THEIR performance.
## But Kova — as a PLATFORM — sees patterns across ALL users. That aggregate intelligence is
## worth more than any individual account's data. No individual user can see market trends,
## industry benchmarks, pricing intelligence, or collaboration opportunities. The platform can.
## This is the "ant colony" invention — no individual ant understands the full picture,
## but the colony makes intelligent decisions from aggregate behavior.
##

- [ ] **NetworkInsight model** — system-generated market intelligence
  - Fields: insight_type (choices: industry_trend, pricing_intelligence, content_benchmark,
    collaboration_opportunity, market_gap, seasonal_pattern, emerging_category),
    industry (CharField — which industry this insight applies to),
    region (CharField — geographic scope: city, country, global),
    title, description, evidence (JSONField — anonymized supporting data),
    magnitude (low/medium/high), confidence (Float 0-1),
    affected_user_count (how many Kova users this is relevant to),
    suggested_action, is_active, published_at, expires_at

- [ ] **IndustryBenchmark model** — rolling benchmarks per industry per region
  - Fields: industry, region, period (month/quarter), metrics (JSONField),
    user_count_in_segment (minimum 50 for privacy), calculated_at
  - Metrics structure:
    ```json
    {
      "avg_engagement_rate": 3.8,
      "top_10_pct_engagement_rate": 7.2,
      "avg_posts_per_week": 5.2,
      "avg_lead_conversion_rate": 0.18,
      "avg_revenue_per_post": 2840,
      "top_content_formats": ["video", "carousel", "image"],
      "top_posting_days": ["thursday", "tuesday", "saturday"],
      "avg_response_time_minutes": 34,
      "avg_kova_score": 520,
      "top_growing_topics": ["delivery", "sustainable_packaging", "AI_tools"],
      "declining_topics": ["office_visits", "print_advertising"]
    }
    ```

- [ ] **NetworkTrend model** — detected market-wide trends
  - Fields: trend_name, description, industries_affected (JSONField — list),
    regions_affected (JSONField), growth_rate_pct (weekly),
    first_detected_at, current_velocity (accelerating/stable/decelerating),
    content_adopter_count (how many Kova users are creating content about this),
    content_gap_score (high demand but low content supply = opportunity),
    suggested_content_angles (JSONField)

- [ ] **Network computation engine** (Celery task: `compute-network-intelligence`, weekly):
  - Data sources: anonymized aggregate PostMetric, Content DNA topics, Lead sources,
    Conversion data (values only, no PII), AudienceGenome interest trends,
    KovaScore distributions, product catalog categories
  - Privacy architecture:
    - NEVER expose individual user data
    - Minimum segment size: 50 users (k-anonymity threshold)
    - No user identifiers in any network insight
    - Users can opt-out of contributing to network data
    - All aggregation runs on anonymized views, not raw tables
  - Intelligence generation:
    - Trend detection: topic velocity across all Content DNA → rising/declining topics
    - Benchmark calculation: percentile distributions per industry/region
    - Market gap detection: high audience demand (comments, DMs) vs low content supply
    - Seasonal patterns: year-over-year engagement patterns (requires 12+ months of network data)
    - Complementary matching: audience overlap analysis for collaboration suggestions

- [ ] **Network Intelligence surfaces** (how users see it):
  - **Daily Brief section** — "Market Intelligence":
    - "Content about 'AI automation' in legal services is getting 3× more engagement this week
      across your industry. Consider creating content about this NOW."
    - "Your engagement rate is 4.2%. Top 10% in your industry: 7.2%. Gap: more video content
      and Thursday posting."
  - **Dedicated dashboard** — `/analytics/market/`:
    - Industry benchmarks: where you stand vs peers (anonymized percentile charts)
    - Rising trends: topics gaining traction in your industry (with suggested content angles)
    - Market gaps: high-demand topics with low content supply (first-mover opportunities)
    - Pricing intelligence: "Businesses like yours with similar audiences charge KES 15K-25K
      for this category. You're at KES 8K."
    - Collaboration radar: "A photographer in your area with 28% audience overlap is gaining
      traction with complementary content." (opt-in only, user chooses to be discoverable)
  - **Create Agent integration**: content seeds enriched with network signals
  - **Strategist Agent integration**: weekly strategy considers market context, not just user's own data

- [ ] Plan limits: Free = basic industry benchmark (your engagement vs average) |
  Growth = full benchmarks + rising trends + market gaps | Pro = pricing intelligence,
  collaboration radar, real-time trend alerts, Create Agent market-aware generation
- DELIVERABLE: Every Kova user gets market intelligence that was previously accessible only to
  enterprises with research teams. The platform's collective intelligence benefits every individual user.
- UNIQUENESS TEST: No social media tool provides anonymized cross-user market intelligence.
  Sprout Social has industry report PDFs (annual, generic). Hootsuite has Social Trends reports
  (yearly, high-level). Kova provides REAL-TIME, LOCALIZED, INDUSTRY-SPECIFIC intelligence
  from ACTUAL business performance data — not surveys or estimates.
- **TECHNICAL NOTES:**
  - Privacy: all queries use anonymized aggregate views. Data minimization principle throughout.
  - Minimum viable network: 500+ active users needed. Below this, show global benchmarks only.
  - Computation: weekly batch job, ~30 minutes for 10K users (aggregate SQL queries + 1 LLM call per industry)
  - Storage: ~100 NetworkInsight records per week, ~50 IndustryBenchmark records per month — lightweight
  - Regional detection: from user timezone + lead location data (GeoIP) + profile settings

### Sprint 7F: Strategic Foresight Engine — "See Tomorrow's Market Today" ⏳ NOT STARTED
## ──────────────────────────────────────────────────────────────────────
## VALUE RANK: #6 — Forward-Looking Advisory Layer
## BIOS CONTRIBUTION: Transforms Kova from "reports what happened" to "advises what to do next."
## PREREQUISITE: All Sprint 7A-7E data layers (commerce, revenue, genome, score, network)
## GENERATES DATA FOR: Digital Business Passport (7G — trajectory indicators)
##
## THE INVISIBLE PROBLEM:
## Small businesses are REACTIVE. They respond to trends after they peak. They adjust strategy
## after losing customers. They change pricing after competitors move. They have zero foresight
## capability — that's reserved for corporations with strategy consultants charging $500/hour.
## Kova gives every KES 299/month user a strategy advisor powered by ALL available data.
##

- [ ] **StrategicForecast model** — forward-looking business intelligence
  - Fields: user (FK), forecast_type (choices: revenue_forecast, trend_opportunity,
    risk_alert, competitive_shift, audience_churn_risk, demand_signal,
    collaboration_opportunity, pricing_recommendation, product_suggestion),
    timeframe (choices: this_week, next_2_weeks, this_month, next_quarter),
    title, description, evidence (JSONField — data backing the forecast),
    confidence (Float 0-1), impact_estimate (CharField — "KES 48,000 potential" or "25% churn risk"),
    suggested_actions (JSONField — list of recommended steps),
    auto_generated_seeds (JSONField — content seed IDs created from this forecast),
    status (choices: active, acted_on, expired, dismissed), created_at, expires_at

- [ ] **ForesightEngine** (new module in Strategist Agent):
  - Data inputs (combines ALL Phase 6 + 7 data):
    - Content performance history (30/60/90 day windows)
    - Revenue attribution + RevenuePrediction accuracy trends
    - AudienceGenome shifts (interest_evolution layer)
    - KovaScore trajectory + component trends
    - NetworkInsight trends + industry benchmarks
    - Competitor analysis data (from analytics app)
    - Seasonal patterns from network data
    - Commercial intent patterns from 7A
  - Forecast types generated:

  **Revenue Forecasts**:
  - Monthly revenue projection with confidence intervals
  - Content investment recommendations to hit revenue targets
  - Risk-adjusted forecasting (accounts for seasonal dips, competitor moves)

  **Opportunity Detection**:
  - "Home delivery searches across your audience are up 230% MoM. 3 competitors haven't adapted.
    OPPORTUNITY WINDOW: ~3 weeks. Auto-generated 5 content seeds about delivery options."
  - "Emerging interest in vegan options (23 mentions, first detected March).
    No competitor content about this in your market. First-mover advantage available."

  **Risk Alerts**:
  - "Your Instagram engagement dropped 18% over 14 days. In similar businesses, this pattern
    preceded a 25% audience decline within 21 days. Cause: last 8 posts were text-only.
    Your audience prefers video (3.2× engagement). Corrective action: switch to 60% video
    for 2 weeks. Projected recovery: 14 days."
  - "Your superfan @handle hasn't engaged in 16 days (previously daily). Churn risk: high.
    Recommend: personalized re-engagement DM + exclusive content."

  **Competitive Intelligence**:
  - "Competitor [X] increased posting frequency by 40% this month. Their engagement is rising
    on topics you're declining on. Consider: match their frequency on [topic] or differentiate
    with [alternative angle]."

  **Pricing & Product**:
  - "Based on audience genome (medium price sensitivity) + network intelligence (industry avg KES 15K-25K)
    + your current conversion rate: raising price from KES 8K to KES 12K is projected to increase
    revenue 35% while decreasing conversion rate only 8%. Net positive: KES 18K/month."
  - "Demand signal: 67 comments + 12 DMs about delivery this month. If you launch delivery,
    estimated additional monthly revenue: KES 45K-80K (based on similar Kova businesses
    who added delivery)."

- [ ] **Daily Brief — Foresight section** (the centerpiece experience):
  ```
  📡 STRATEGIC FORESIGHT (next 2-4 weeks):

  💰 REVENUE FORECAST:
  • This month's projection: KES 165,000 (82% of your KES 200K target)
  • To close the gap: 4 more video posts about wedding cakes + WhatsApp CTAs
  • Estimated uplift: KES 48,000 (±15K). Content seeds ready for approval.

  🔥 OPPORTUNITY WINDOW (estimated 3 weeks):
  • "Home delivery" demand rising sharply in your audience (+230% MoM)
  • 0 of your 5 tracked competitors are posting about this
  • Auto-generated seeds: "We Now Deliver!" announcement + delivery zone map + FAQ post

  ⚠️ RISK ALERT:
  • Instagram engagement declining 18% (14-day trend). Historical pattern:
    leads to 25% audience drop in 21 days. Root cause: text-heavy content.
  • Auto-correction recommended: 60% video content for next 2 weeks.
  • Projected recovery: within 14 days if action taken now.

  🤝 COLLABORATION SIGNAL:
  • Florist (Kova Score: 720, 28% audience overlap) gaining traction with wedding content.
  • Cross-promotion projected reach: 3,400 new audience members.
  • Auto-drafted collaboration proposal ready for review.

  📈 PRICING INSIGHT:
  • Your industry peers price at KES 15K-25K. You're at KES 8K.
  • Test price increase to KES 12K: projected +35% revenue, -8% conversion rate. Net positive.
  ```

- [ ] **Auto-action on forecasts** (Pro plan):
  - When opportunity detected: auto-generate content seeds for user approval
  - When risk detected: auto-adjust content mix (more video, different topics)
  - When pricing insight generated: create A/B test content with different price points
  - When collaboration opportunity: draft outreach message for user review
  - All auto-actions are suggestions — user approves, never fully autonomous for strategic decisions

- [ ] **Foresight accuracy tracking**:
  - Store forecast → compare with actual outcome after timeframe expires
  - Track accuracy by forecast type (revenue forecasts most measurable)
  - Use accuracy data to improve future forecasts (calibration loop)
  - Show users: "Our revenue forecasts have been 82% accurate over the last 3 months"

- [ ] Plan limits: Free = none (must be Growth+) | Growth = basic risk alerts + monthly revenue forecast
  | Pro = full foresight (all forecast types), auto-generated seeds, collaboration matching,
  pricing recommendations, product suggestions
- DELIVERABLE: Every Kova user gets a strategic advisor that sees around corners. Not analytics
  reports about yesterday — actionable foresight about tomorrow. This is the moment Kova
  transitions from "social media tool" to "business intelligence operating system."
- UNIQUENESS TEST: This is entirely new. No social media tool, no analytics platform, no
  CRM generates forward-looking strategic advice from the combination of content performance +
  audience behavior + commercial intent + revenue data + network intelligence + competitor data.
  The closest analogy is a management consultant — Kova delivers that as a $7/month feature.
- **TECHNICAL NOTES:**
  - Computation: Strategist Agent extended with foresight module. 1 LLM call per user per day (Premium tier
    model — this is the highest-value output, worth the cost). Results cached for Daily Brief.
  - Data freshness: revenue predictions refreshed weekly, audience genome weekly, network insights weekly,
    competitor data weekly. Foresight runs daily, combining latest available data.
  - Confidence calibration: starts at low confidence, increases as historical accuracy proves out
  - Auto-seed generation: Create Agent called inline when opportunity/risk detected (Workhorse tier)

### Sprint 7G: Digital Business Passport — "Your Business Identity, Verified and Portable" ⏳ NOT STARTED
## ────────────────────────────────────────────────────────────────────────────────────────
## VALUE RANK: #7 — The Endgame Play
## BIOS CONTRIBUTION: Makes Kova's data a financial + economic asset beyond the platform itself.
## PREREQUISITE: All Sprint 7A-7F (needs full intelligence stack for a meaningful passport)
## GENERATES: External revenue streams (banking partnerships, marketplace, government data partnerships)
##
## THE INVISIBLE PROBLEM:
## In emerging markets, businesses have NO standardized digital identity. They exist on scattered
## platforms with no verified track record. Banks can't assess them (thin credit files).
## Customers can't verify they're legitimate (fraud rampant). Investors can't evaluate traction
## without expensive due diligence. The trust infrastructure of digital commerce doesn't exist.
## Kova builds it — because after Sprint 7A-7F, Kova has the ONLY verified, multi-signal
## dataset of business performance that spans content → engagement → leads → revenue → reputation.
##

- [ ] **DigitalPassport model** — verified portable business identity
  - Fields: user (FK), passport_slug (unique — public URL identifier),
    display_name, business_description, industry, location_city, location_country,
    kova_score (FK to KovaScore — live reference, always current),
    verified_since (Date — when they first reached verified status),
    active_platforms_count, total_posts, consistency_rate (Float),
    audience_size_verified (Integer — engagement-validated, not raw followers),
    avg_monthly_leads, avg_monthly_revenue_tracked (Decimal),
    response_time_avg_minutes, content_quality_grade (A/B/C/D/F),
    badges (JSONField — earned badges list), is_public (Bool — user controls visibility),
    is_verified (Bool — passed all verification checks),
    verification_level (choices: basic, standard, premium),
    created_at, updated_at, last_verified_at

- [ ] **PassportBadge model** — earned achievements
  - Fields: badge_type (choices: consistent_creator, revenue_verified, fast_responder,
    audience_growth, content_quality, multi_platform, community_builder,
    industry_leader, rising_star, one_year_active),
    earned_criteria (JSONField — what triggered this badge),
    display_name, icon, description
  - Auto-award: Celery task checks badge criteria weekly, awards new badges

- [ ] **PassportVerificationLevel** — tiered verification depth
  - Basic: email verified + 3+ months active + Kova Score 300+
  - Standard: Basic + business registration document + phone verified + 6+ months active + Score 500+
  - Premium: Standard + revenue data validated + physical address verified + 12+ months + Score 700+

- [ ] **Public passport page** — `kovaagent.com/p/{passport_slug}`
  - Public-facing page showing verified business identity
  - Displays: business name, description, industry, location, Kova Score (live),
    active since date, platform presence, badges earned, response time,
    content consistency grade, audience engagement tier
  - Does NOT show: revenue data, lead data, internal analytics (privacy-protected)
  - Trust signals: "Verified by Kova — data backed by 12 months of tracked performance"
  - QR code: for print materials, business cards, physical signage
  - Responsive: optimized for mobile (most views will be phone-based)

- [ ] **Passport sharing + embedding**:
  - Embeddable widget: HTML snippet for websites/blogs (shows live Kova Score + badges)
  - Email signature badge: compact image + link to public passport
  - Social profile link: "Kova Verified Business" link for social bios
  - WhatsApp Business: badge image overlay for profile photo
  - Print-ready: PDF export of passport for offline use (business meetings, bank applications)

- [ ] **External partnership infrastructure** (the revenue expansion):
  - **Banking Data API** (future — requires legal framework):
    - User consents to share anonymized Kova data with partner banks
    - API endpoint: bank queries user's passport → receives: Kova Score, months active,
      revenue attribution summary, consistency metrics, audience quality grade
    - Use case: SMB loan application supplemented with Kova digital presence data
    - Revenue model: per-inquiry fee from banks (estimated: $1-5 per credit check)
    - Privacy: user grants per-bank consent, can revoke anytime, data minimized to credit-relevant signals
  - **Kova Business Directory** (future):
    - Opt-in directory of Kova-verified businesses, searchable by industry + location + score
    - Consumer trust tool: "Find Kova Verified businesses in Nairobi"
    - SEO: public passport pages rank for "[business name] + reviews/verified"
    - Revenue model: free listing, featured placement on Pro plan
  - **Government/NGO Data Partnerships** (future):
    - Anonymized aggregate data: "15,000 active businesses in Nairobi registered on Kova,
      3,200 in hospitality, average social revenue KES 85K/month"
    - Use case: economic development reporting, SMB support program targeting
    - Revenue model: data licensing for market intelligence reports

- [ ] **Business transfer protocol** (future):
  - When a business is sold, passport + Kova Score + Content DNA + lead pipeline transfers to new owner
  - Transfer verification: both parties confirm in-app, Kova validates account continuity
  - Passport note: "Business transferred on [date]. Previous track record preserved."
  - Use case: makes digital-native businesses SELLABLE as verified assets

- [ ] Plan limits: Free = none (Growth+ only) | Growth = basic passport (public page + basic badges) |
  Pro = premium passport (all badges, embed, QR, PDF export, bank data sharing opt-in, directory listing)
- DELIVERABLE: Every Kova business has a verified, portable digital identity that creates value
  OUTSIDE the platform — in banking, partnerships, marketplace trust, and business transactions.
  Kova transitions from a tool that helps business internally to infrastructure that represents
  businesses externally. That's a platform play, not a SaaS play.
- UNIQUENESS TEST: Nothing like this exists. Google Business Profile is basic and unverified.
  LinkedIn company pages show self-reported data. Klout (RIP) measured vanity influence.
  Kova's Digital Passport is backed by 12+ months of VERIFIED performance data across
  content quality, audience behavior, lead conversion, and revenue attribution. It's not
  a profile — it's a CREDIT REPORT for your digital business.
- **TECHNICAL NOTES:**
  - Public passport pages: server-rendered, cached (1hr), SEO-optimized (og: tags, structured data)
  - QR codes: python-qrcode library, generated on demand, cached
  - PDF export: WeasyPrint or xhtml2pdf (Django-compatible, no external service needed)
  - Banking API: sensitive — requires legal counsel, data protection impact assessment, regulatory
    compliance (Kenya Data Protection Act 2019, GDPR if serving EU). DO NOT build without legal review.
  - Directory: simple Django ListView with filters, public pages already handle individual display

### Phase 7 — The Intelligence Pipeline (Why This Order Matters)

```
Sprint 7A: Commerce Pipeline
    ↓ Generates: commercial intent data, auto-conversion data, product demand signals
Sprint 7B: Revenue Prediction
    ↓ Consumes: conversion data. Generates: per-post revenue projections, content ROI patterns
Sprint 7C: Audience Genome
    ↓ Consumes: all engagement + conversion + email data. Generates: psychographic intelligence
Sprint 7D: Kova Score
    ↓ Consumes: all business signals. Generates: quantified trust, verifiable brand health
Sprint 7E: Network Intelligence
    ↓ Consumes: anonymized aggregate from all users. Generates: market intelligence, benchmarks
Sprint 7F: Strategic Foresight
    ↓ Consumes: ALL above layers. Generates: forward-looking business advice
Sprint 7G: Digital Business Passport
    ↓ Consumes: score + genome + foresight trajectory. Generates: EXTERNAL VALUE (banking, trust, portability)
```

Each sprint produces data that makes the next sprint more intelligent.
Skipping ahead breaks the intelligence chain.

### Phase 7 — Key Metrics (How We Know It's Working)
| Metric | Target | How Measured |
|--------|--------|-------------|
| Commerce auto-response conversion rate | 15%+ of auto-responses lead to a sale | Conversion records from CommercialIntentDetector pipeline |
| Revenue prediction accuracy | 80%+ within ±20% of actual revenue after 6 months of calibration | RevenuePrediction.prediction_accuracy rolling average |
| Audience Genome activation rate | 70%+ of users with 30+ posts have an active genome | AudienceGenome count vs eligible user count |
| Kova Score adoption | 50%+ of active users view their score monthly | Score dashboard page views / MAU |
| Verified business passports | 30%+ of users active 6+ months achieve Standard verification | DigitalPassport.is_verified count |
| Network Intelligence engagement | 60%+ of Growth/Pro users click on market insights in Daily Brief | NetworkInsight click-through tracking |
| Foresight accuracy | 75%+ of acted-on forecasts achieve within 25% of projected outcome | StrategicForecast accuracy tracking (outcome vs prediction) |
| External revenue (banking API) | First banking partnership signed within 6 months of 7G launch | Partnership agreement executed |
| Churn impact | Users with active Kova Score have 50%+ lower churn than users without | Subscription churn rate segmented by feature usage |

### Phase 7 — Revenue Model Evolution
```
BEFORE PHASE 7:
  Revenue = SaaS subscriptions only ($2-$21/month per user)
  Model: Linear (revenue grows with user count)

AFTER PHASE 7:
  Revenue = SaaS subscriptions
           + Banking data licensing (per-inquiry fee from partner banks)
           + Network Intelligence reports (sold to enterprises/governments)
           + Marketplace commissions (collaborations facilitated by Kova)
           + Featured directory placement (premium visibility for businesses)
  Model: PLATFORM (revenue grows with user count × data value × external partnerships)
```

### Phase 7 — Technical Architecture Notes
- **New Celery tasks** (5 additions):
  - `detect-commercial-intent` — real-time, triggered by Engage Agent cycle (every 30 min)
  - `compute-audience-genome` — weekly per user
  - `compute-kova-scores` — weekly per user
  - `compute-network-intelligence` — weekly, global aggregate
  - `generate-strategic-forecasts` — daily per user (Growth+)
- **Database growth**: Phase 7 adds ~12 new models, ~15 tables.
  Estimated growth at 10K users: ~500K new rows/month (mostly RevenuePrediction, AudienceShift,
  NetworkInsight, StrategicForecast records). PostgreSQL handles this comfortably.
- **LLM cost per user per week** (Phase 7 additions):
  - Commerce intent: ~5-10 calls (Workhorse tier) — triggered per commercial interaction
  - Revenue prediction: 1 call per post (Workhorse)
  - Audience genome: 1 call/week (Workhorse)
  - Kova Score narrative: 1 call/week (Fast tier)
  - Network intelligence: shared across users (1 call per industry per week, not per user)
  - Strategic foresight: 1 call/day (Premium tier — highest-value output)
  - Estimated total: ~15-25 LLM calls/user/week additional. At 10K users: ~200K calls/week.
    Cost managed by model tier system (Workhorse for most, Premium only for foresight).
- **Privacy framework** (critical for 7E-7G):
  - All network intelligence: k-anonymity (minimum 50 users per segment)
  - All external data sharing: explicit user opt-in with granular consent
  - Banking data: data protection impact assessment required before development
  - No PII in any aggregate or network model. Ever.
  - Compliance: Kenya Data Protection Act 2019 + GDPR (if serving international users)


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
"Kova Agent runs your complete digital business presence autonomously —
creating content, engaging community, capturing leads, nurturing relationships,
predicting revenue, advising strategy, and building verified trust —
while you focus on what you do best. Your business grows while you sleep."

## 17.2 Future Capabilities (Phase 8+)
1. **Agent Marketplace**: Users create and share custom agent "skills" (e.g., "Real Estate Agent Pack" — knows how to create property listings across platforms)
2. ~~**Revenue Attribution Engine**~~ → MOVED TO PHASE 6 (Sprint 6G)
3. **Content Mutation**: Post version A underperforms in 2 hours → system auto-generates version B with different hook, posts to remaining platforms
4. ~~**Voice/Video Input**~~ → Voice memo ✅ complete, Video AI → Phase 6 Sprint 6F
5. **Agency White-Label**: Agencies run Kova under their own brand for clients
6. **Open-Source Core**: Release a self-hosted community edition to build developer community + funnel to paid cloud version
7. **Mobile App**: PWA or native app for approve-on-the-go (PWA MVP ✅ complete in Phase 4)
8. **Enterprise SSO + Compliance**: SOC 2, SSO, audit logs for enterprise clients
9. ~~**Predictive Audience Builder**~~ → MOVED TO PHASE 7 (Sprint 7C — Audience Genome)
10. **Cross-Platform Narrative Engine**: Maintain a single narrative across platforms that unfolds over weeks (episodic content)
11. ~~**Email Marketing**~~ → MOVED TO PHASE 6 (Sprint 6D)
12. ~~**Lead Capture + CRM**~~ → MOVED TO PHASE 6 (Sprint 6C)
13. ~~**Link-in-Bio / Landing Pages**~~ → MOVED TO PHASE 6 (Sprint 6A)
14. ~~**Revenue Prediction**~~ → MOVED TO PHASE 7 (Sprint 7B)
15. ~~**Digital Trust / Credit Scoring**~~ → MOVED TO PHASE 7 (Sprint 7D — Kova Score + Sprint 7G — Digital Passport)

## 17.3 The Evolution Arc
```
Phase 1-4:  CONTENT TOOL        → "AI helps you post better"
Phase 5:    CHANNEL OWNER        → "AI owns the conversation on WhatsApp"
Phase 6:    OPERATING SYSTEM     → "AI runs your entire marketing: content + leads + email + revenue"
Phase 7:    INTELLIGENCE SYSTEM  → "AI tells your business where to go next"
Phase 8+:   PLATFORM / ECOSYSTEM → "AI connects businesses, banks, and markets"
```

## 17.4 The Endgame
Kova Agent becomes the BUSINESS INTELLIGENCE OPERATING SYSTEM for the creator and SMB economy.

Not a tool they use. Not an app they open. An invisible intelligence that:
1. Creates and publishes content autonomously (Phase 1-4)
2. Engages community and captures leads (Phase 3+6)
3. Nurtures relationships via email and social (Phase 6)
4. Detects buying signals and closes sales automatically (Phase 7A)
5. Predicts revenue and advises on content investment (Phase 7B)
6. Understands their audience deeper than any survey (Phase 7C)
7. Quantifies their digital brand into a bankable score (Phase 7D)
8. Shows them market intelligence only platforms can see (Phase 7E)
9. Advises where their business should go next (Phase 7F)
10. Represents their business with a verified digital identity (Phase 7G)

The trust infrastructure of digital commerce in Africa doesn't exist.
Kova builds it — one verified business at a time.

Creator economy + AI autonomy + closed-loop conversion + business intelligence + digital trust = Kova Agent.


# ============================================================================
# END OF ROADMAP
# ============================================================================
# This document will be updated as we build and learn.
# Every PR should reference which phase/sprint/feature it addresses.
# When in doubt, refer back to Section 1: Core Philosophy.
# ============================================================================
