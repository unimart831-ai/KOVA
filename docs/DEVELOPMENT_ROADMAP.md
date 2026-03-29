# ============================================================================
# KOVA AGENT — DEVELOPMENT ROADMAP
# ============================================================================
# Autonomous Social Intelligence Platform
# "Your social media runs itself. You stay in control."
#
# This document is the SINGLE SOURCE OF TRUTH for building Kova Agent.
# Every decision, every sprint, every feature traces back to here.
# Last Updated: March 27, 2026
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
- Python 3.12+
- Django 5.x (web framework, ORM, admin, auth, sessions)
- Django REST Framework (API layer for agent communication + mobile-ready endpoints)
- Celery (distributed task queue — ALL agent operations run as Celery tasks)
- Redis (Celery broker + caching + real-time pub/sub)
- PostgreSQL 16+ (primary database)
- Django Channels (WebSocket support for real-time agent status + notifications)

## 3.2 Frontend
- Django Templates (server-rendered HTML — fast, SEO-friendly)
- HTMX (dynamic interactions without JavaScript frameworks)
- Alpine.js (lightweight client-side interactivity: modals, dropdowns, toggles)
- Tailwind CSS (utility-first styling — responsive, fast to build)
- No build step needed for HTMX/Alpine.js (CDN or static files)

## 3.3 AI & Agent Layer
- LangGraph OR CrewAI (multi-agent orchestration framework)
  Decision: Evaluate both in Phase 1 Week 1, choose one
  - LangGraph: More flexible, lower-level, MIT licensed
  - CrewAI: More opinionated, faster setup, role-based agents
- OpenAI API (GPT-4o/GPT-4o-mini) — primary LLM
- Anthropic API (Claude) — secondary/fallback LLM
- User can choose their LLM provider (future: open-source models)

## 3.4 Data & Memory
- PostgreSQL (structured data: users, posts, schedules, analytics)
- pgvector extension (vector storage for content DNA + agent memory)
  NOTE: This keeps everything in one database — simpler than separate ChromaDB
- Redis (ephemeral: agent state, task queue, rate limiting, caching)

## 3.5 External Services
- Social platform OAuth + APIs (see Section 7)
- Resend or Django SMTP (transactional email: notifications, Daily Brief email)
- Stripe (subscription billing)
- S3-compatible storage (media files: images, videos for posts)
  Options: AWS S3, Cloudflare R2 (cheaper), MinIO (self-hosted)

## 3.6 Development Tools
- Git + GitHub (version control)
- Docker + Docker Compose (local development + deployment)
- pytest + Django test framework (testing)
- Ruff (Python linting + formatting)
- pre-commit hooks (code quality gates)

## 3.7 Deployment
- Docker containers
- Target: Railway, Render, or VPS (DigitalOcean/Hetzner)
- CI/CD: GitHub Actions
- Monitoring: Sentry (errors), basic health checks


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
| X/Twitter | OAuth 2.0   | Post text/images, read metrics, read mentions | Free tier: 1500 posts/mo    |
| LinkedIn  | OAuth 2.0   | Post text/images/articles, read metrics    | Requires LinkedIn app review |
| Instagram | OAuth via FB | Post images/carousels/reels, read comments | Requires Facebook app review |
| Facebook  | OAuth 2.0   | Post to pages, read metrics, read comments | Requires Facebook app review |
| TikTok    | OAuth 2.0   | Post videos via Content Posting API        | Requires TikTok app review   |

## 7.2 Phase 2 Platforms (add 4 more)
- YouTube (OAuth 2.0 — upload videos, read metrics)
- Pinterest (OAuth 2.0 — create pins, read metrics)
- Threads (via Instagram API — post text/images)
- Bluesky (AT Protocol — open, no review needed)

## 7.3 Phase 3+ Platforms
- Reddit, Mastodon, Telegram, Discord, Medium, Dev.to, WordPress

## 7.4 Integration Architecture
- Each platform = a Provider class inheriting from BaseProvider
- BaseProvider defines interface: connect(), publish(), get_metrics(), get_engagement()
- Each provider implements platform-specific logic
- Token refresh handled automatically by background task
- All API calls go through rate-limit-aware wrapper
- Failed publishes retry with exponential backoff (max 3 retries)


# ============================================================================
# 8. FEATURE MAP (Complete)
# ============================================================================

## 8.1 MUST HAVE (MVP — Phase 1)
- [ ] User registration + login (email + password)
- [ ] User onboarding flow (brand voice, goals, industry, connect platforms)
- [ ] Connect social accounts via OAuth (5 platforms)
- [ ] Content seed input (text box — drop a rough idea)
- [ ] Create Agent: Seed → platform-native content generation
- [ ] Post approval workflow (approve / edit / reject)
- [ ] Manual scheduling (pick date/time)
- [ ] Content queue view (list of upcoming posts)
- [ ] Basic calendar view (month/week)
- [ ] Auto-publish at scheduled time
- [ ] Post status tracking (draft → approved → scheduled → published → failed)
- [ ] Basic post metrics display (likes, comments, shares after publishing)
- [ ] Settings: manage connected accounts
- [ ] Settings: update brand voice / profile
- [ ] Responsive UI (works on mobile browsers)
- [ ] Landing page (marketing homepage)
- [ ] Pricing page

## 8.2 SHOULD HAVE (Phase 2)
- [ ] Daily Brief (morning summary + action items)
- [ ] Analyst Agent v1: Engagement prediction (score before publishing)
- [ ] Research Agent v1: Trending topic detection in user's niche
- [ ] Adapt Agent: Smart scheduling (optimal times based on user's audience)
- [ ] Content DNA system: Track which content attributes drive engagement
- [ ] Email Daily Brief (receive brief in inbox)
- [ ] Multi-image / carousel support
- [ ] Post preview (see how it will look on each platform)
- [ ] Basic competitor tracking (manually add competitor accounts)
- [ ] Agent activity log (see what agents did and why)
- [ ] Agent configuration (enable/disable agents, set autonomy level)
- [ ] Stripe billing integration
- [ ] Free trial (7 days)

## 8.3 NICE TO HAVE (Phase 3)
- [ ] Engage Agent: Comment/DM monitoring + auto-reply drafts
- [ ] Relationship Memory: Track audience members, superfans
- [ ] Unified inbox (all comments/DMs across platforms)
- [ ] Full agent orchestration (Chief Strategist coordinates all agents)
- [ ] Content A/B testing (auto-generate variations)
- [ ] Team features: invite members, roles, approval workflows
- [ ] Hashtag research + suggestions
- [ ] Re-queue evergreen content
- [ ] Voice memo input (speech-to-text → content seed)
- [ ] AI image generation for posts

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


# ============================================================================
# 9. BUILD PHASES (Detailed Sprint Plans)
# ============================================================================

## ─── PHASE 1: MVP — "AI-Assisted Scheduling" (Weeks 1-8) ───

### Sprint 1 (Week 1-2): Foundation
- [x] Create Django project with proper structure
- [ ] Configure settings (base, dev, prod)
- [ ] Set up Docker + Docker Compose (Django, PostgreSQL, Redis)
- [ ] Set up Celery with Redis broker
- [ ] Install and configure: HTMX, Alpine.js, Tailwind CSS
- [ ] Create base.html template with Tailwind + HTMX + Alpine
- [ ] Create app layout template (sidebar + main area)
- [ ] accounts app: User model, registration, login, logout
- [ ] accounts app: User profile + onboarding form
- [ ] Basic landing page (marketing)
- [ ] Evaluate LangGraph vs CrewAI — choose one
- DELIVERABLE: User can register, login, complete onboarding. App looks good.

### Sprint 2 (Week 3-4): Platform Connections
- [ ] platforms app: SocialAccount model
- [ ] BaseProvider abstract class
- [ ] X/Twitter OAuth flow + provider
- [ ] LinkedIn OAuth flow + provider
- [ ] Instagram/Facebook OAuth flow + provider
- [ ] TikTok OAuth flow + provider (if API access approved)
- [ ] Token refresh background task
- [ ] "Connect Account" UI in settings
- [ ] Connected accounts dashboard
- DELIVERABLE: User can connect their social media accounts.

### Sprint 3 (Week 5-6): Content Pipeline + Create Agent
- [ ] content app: ContentSeed, Post, MediaAsset models
- [ ] Content seed input form ("Drop your idea here")
- [ ] Create Agent v1: text seed → multi-platform posts
- [ ] Brand voice training: Use user's sample posts to fine-tune agent output
- [ ] Post editor (edit AI-generated content before approving)
- [ ] Post approval flow (approve / edit / reject)
- [ ] Content queue view (upcoming posts list)
- [ ] Calendar view (basic month view with scheduled posts)
- [ ] Media upload support (images)
- DELIVERABLE: User drops an idea → AI generates platform-native posts → user approves.

### Sprint 4 (Week 7-8): Publishing + Polish
- [ ] Scheduling system: pick date/time for each post
- [ ] Auto-publish Celery task (fires at scheduled_at, calls platform API)
- [ ] Publish status tracking + error handling + retry
- [ ] Post metrics: fetch basic metrics after publishing (periodic task)
- [ ] Post detail view (see metrics after publishing)
- [ ] Notification system (in-app: post published, post failed)
- [ ] Error states + empty states throughout the app
- [ ] Mobile responsiveness pass
- [ ] Bug fixing + testing
- [ ] Deploy MVP to staging
- DELIVERABLE: Full MVP. User can drop idea → AI generates → approve → schedule → auto-publish → see metrics.

## ─── PHASE 2: Intelligence — "Predictive & Adaptive" (Weeks 9-16) ───

### Sprint 5 (Week 9-10): Daily Brief + Analyst Agent
- [ ] briefs app: DailyBrief, BriefItem models
- [ ] Daily Brief generation (Celery Beat, runs at user's preferred time)
- [ ] Daily Brief UI (the "command center" view)
- [ ] Analyst Agent v1: Post-performance analysis
- [ ] Analyst Agent v1: Engagement prediction scoring
- [ ] Content DNA system: Track content attributes → performance correlation
- [ ] Content DNA display: "Your best performing content attributes"
- DELIVERABLE: Users get a Daily Brief with scored content + insights.

### Sprint 6 (Week 11-12): Research Agent + Adapt Agent
- [ ] Research Agent v1: Trending topic detection (web search + social signals)
- [ ] Research Agent: Opportunity briefs in Daily Brief
- [ ] Adapt Agent v1: Audience activity pattern analysis
- [ ] Adapt Agent: Smart scheduling (suggest optimal times)
- [ ] Auto-schedule feature (let Adapt Agent choose all times)
- [ ] Agent configuration UI (enable/disable, set autonomy level)
- [ ] Agent activity log (see history of agent actions)
- DELIVERABLE: Agents proactively find trends + optimize timing.

### Sprint 7 (Week 13-14): Billing + Growth Features
- [ ] billing app: Plan, Subscription models
- [ ] Stripe Checkout integration (subscribe to plan)
- [ ] Stripe Customer Portal (manage subscription, invoices)
- [ ] Stripe webhooks (subscription lifecycle events)
- [ ] Free 7-day trial flow
- [ ] Plan enforcement (feature gating based on subscription)
- [ ] Pricing page with plan comparison
- [ ] Agent email reports (Daily Brief → email)
- DELIVERABLE: Monetization works. Users can subscribe and pay.

### Sprint 8 (Week 15-16): Quality + More Platforms
- [ ] Post preview per platform (mock how it'll look)
- [ ] Carousel/multi-image post support
- [ ] Add YouTube provider
- [ ] Add Pinterest provider
- [ ] Add Threads provider
- [ ] Add Bluesky provider
- [ ] Competitor tracking (manual add, basic metric monitoring)
- [ ] Performance + security audit
- [ ] Load testing
- DELIVERABLE: 9 platforms, previews, billing, ready for public launch.

## ─── PHASE 3: Autonomy — "The System Runs Itself" (Weeks 17-24) ───

### Sprint 9 (Week 17-18): Engage Agent + Community
- [ ] engage app: AudienceMember, Conversation models
- [ ] Engage Agent v1: Monitor comments/mentions across platforms
- [ ] Engage Agent: Draft replies with confidence scoring
- [ ] Auto-reply for high-confidence responses
- [ ] Flagged items in Daily Brief
- [ ] Unified inbox (all engagement in one place)
- [ ] Relationship scoring (track interaction frequency per audience member)

### Sprint 10 (Week 19-20): Full Orchestration
- [ ] Chief Strategist Agent: Coordinate all agents
- [ ] Full seed-to-publish pipeline (seed → research → create → score → schedule → publish → engage → learn)
- [ ] Content A/B testing: Auto-generate variations, test them
- [ ] Self-adjusting strategy (Analyst → Create Agent feedback loop)
- [ ] Superfan detection + alerts

### Sprint 11 (Week 21-22): Team Features
- [ ] Team invitations and roles (admin, editor, viewer)
- [ ] Approval workflows (editor creates → admin approves)
- [ ] Team activity feed
- [ ] Multi-brand support (Agency plan groundwork)

### Sprint 12 (Week 23-24): Polish + Scale
- [ ] Performance optimization (query optimization, caching)
- [ ] Comprehensive error handling
- [ ] Onboarding improvements based on user feedback
- [ ] Help docs / knowledge base
- [ ] Security hardening
- [ ] Monitoring + alerting setup

## ─── PHASE 4: Moat — "Unbeatable" (Weeks 25+) ───
- Agency multi-brand management
- White-label client dashboards/reports
- Revenue attribution engine
- Custom agent skills / marketplace
- Public API + developer docs
- Mobile PWA
- Open-source self-hosted edition
- Advanced AI features (voice memo input, AI video generation)


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
Step 1: Welcome — what is Kova Agent, how it works (30-second video)
Step 2: Your brand — name, industry, goals, brand voice description
Step 3: Voice training — paste 5-10 of your best past posts
Step 4: Connect accounts — OAuth flows for platforms
Step 5: Preferences — set Daily Brief time, autonomy comfort level
Step 6: First seed — drop your first content idea, see AI magic


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
