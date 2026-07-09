# KOVA Architecture Audit

**Date:** July 2026

---

## System Overview

Kova is a Django 5.1 modular monolith deployed on Railway. The Django project package is `config` (physically at `docs/config/`). All application code lives under `kova_agent/apps/`.

### Technology Stack

| Layer | Technology |
|-------|-----------|
| Framework | Django 5.1 |
| Database | PostgreSQL 16 + pgvector |
| Cache/Broker | Redis |
| Task Queue | Celery + django-celery-beat |
| WebSocket | Django Channels + Daphne |
| Frontend | HTMX + Alpine.js + Tailwind CSS |
| API | Django REST Framework + drf-spectacular |
| AI/ML | LangChain, LangGraph, OpenAI, Anthropic, OpenRouter |
| Image Processing | Photoroom, Fal.ai, Bannerbear, Pillow |
| Payments | M-Pesa (Daraja), Stripe |
| Email | Resend (via django-anymail) |
| Storage | Cloudflare R2 (via boto3/django-storages) |
| Deployment | Railway (Nixpacks), Docker |
| Monitoring | Sentry |
| Video | Remotion (React/TypeScript subproject) |

---

## Application Inventory (27 Apps)

### Core Business Logic

| App | Purpose | Models | Status |
|-----|---------|--------|--------|
| `accounts` | User auth, onboarding, Business Brain, profile settings | 3 | Production |
| `agents` | 6 AI agents, LLM router, token budgets, memory | 4 | Production |
| `content` | Posts, scheduling, campaigns, content safety, voice memos | 10 | Production |
| `products` | Product catalog, Snap-to-Sell, Photoroom pipeline, commerce | 9 | Production |
| `whatsapp` | WhatsApp Cloud API — inbox, commerce, broadcasts, channels | 14 | Production |
| `platforms` | Social account OAuth, token refresh, platform providers | 1 | Production |
| `briefs` | Daily AI briefings, WhatsApp owner commands | 2 | Production |

### Growth & Revenue

| App | Purpose | Models | Status |
|-----|---------|--------|--------|
| `analytics` | Post metrics, competitor intel, conversions, Kova Pixel | 13 | Partial |
| `leads` | CRM-lite, lead scoring, nurture sequences | 5 | Partial |
| `billing` | M-Pesa + Stripe subscriptions, plan enforcement | 9 | Production |
| `engage` | Social inbox, AI auto-reply, superfans | 3 | Production |
| `bookings` | Appointment booking with attribution | 2 | Production |
| `links` | Link-in-bio pages, lead capture forms | 6 | Production |

### Extensions

| App | Purpose | Models | Status |
|-----|---------|--------|--------|
| `emails` | Transactional + marketing email via Resend | 7 | Partial |
| `teams` | Multi-brand agency management | 5 | Partial |
| `partners` | Referral program + marketplace B2B | 10 | Stub/Early |
| `reviews` | Post-conversion review request loop | 1 | Partial |
| `qr_attribution` | QR codes + walk-in attribution | 3 | Implemented |
| `notifications` | In-app notifications + WebSocket | 2 | Production |
| `calendar_intel` | Holiday/cultural moment awareness | 0 | Production |
| `help` | Help center + public blog (Educator agent) | 6 | Production |

### Infrastructure / Support

| App | Purpose | Models | Status |
|-----|---------|--------|--------|
| `admin_dashboard` | Staff ops dashboard (~250 routes) | 0 | Production |
| `api` | REST API v1 + partner marketplace API | 0 | Partial |
| `media` | Media orchestration (Photoroom, Fal, Bannerbear, Remotion) | 0 | Production |
| `profile_audit` | Social profile completeness audit | 0 | Experimental |
| `kova_page` | Public business profile pages | 0 | Legacy (duplicate) |
| `campaigns` | Legacy — migrations only | 0 | Deprecated |

---

## Service Layer

| Service | Location | Purpose |
|---------|----------|---------|
| Billing Service | `apps/billing/services.py` | Stripe lifecycle management |
| M-Pesa Service | `apps/billing/mpesa_services.py` | M-Pesa STK Push, callbacks, subscription management |
| Email Service | `apps/emails/services.py` | Template registry, send helpers |
| Review Service | `apps/reviews/services.py` | Review request loop, sentiment classification |
| WhatsApp Service | `apps/whatsapp/services.py` | Unified outbound messaging, window management |

---

## AI Agent Architecture

```
[Research Agent] ──→                                  ──→ [Create Agent]
[Analyst Agent]  ──→  Chief Strategist (orchestrator) ──→ [Adapt Agent]
[Engage Agent]   ──→                                  ──→ [Daily Brief]
[Growth Data]    ──→                                  ──→ [Dashboard]
```

| Agent | File | Purpose |
|-------|------|---------|
| Research | `agents/research_agent.py` | Trend discovery via Tavily web search |
| Create | `agents/create_agent.py` | Strategic content generation from seeds |
| Strategist | `agents/strategist_agent.py` | Orchestrates all agents, growth intelligence |
| Analyst | `agents/analyst_agent.py` | Performance analysis, Content DNA extraction |
| Adapt | `agents/adapt_agent.py` | Learning loop — mutates weights and preferences |
| Engage | `agents/engage_agent.py` | Comment/DM analysis and AI replies |
| Educator | `agents/educator_agent.py` | Platform blog articles (internal use) |

**Supporting infrastructure:**
- `agents/llm.py` — Multi-provider LLM abstraction (OpenAI, Anthropic, OpenRouter)
- `agents/memory.py` — Agent memory, history injection, outcome measurement
- `agents/budget.py` — Per-user daily token budget enforcement
- `agents/pricing.py` — Token cost registry
- `agents/schemas.py` — Pydantic output schemas
- `agents/visual_strategy.py` — Maps content to visual type
- `agents/media.py` — AI image generation (Together/Pollinations/FLUX)
- `agents/graphics.py` — Branded text-overlay graphics
- `agents/carousel.py` — Multi-slide carousel generator

---

## Scheduled Jobs (Celery Beat)

| Schedule | Task | App |
|----------|------|-----|
| Daily | `generate_all_daily_briefs` | briefs |
| Daily | `run_daily_research` | agents |
| Daily | `check_mpesa_subscriptions` | billing |
| Periodic | `check_and_publish_due_posts` | content |
| Periodic | `run_engage_cycle` | agents |
| Periodic | `run_adapt_cycle` | agents |
| Periodic | `run_strategy_cycle` | agents |
| Periodic | `refresh_expiring_tokens` | platforms |
| Periodic | `process_nurture_steps` | leads |
| Periodic | `send_followup_nudges` | whatsapp |
| Periodic | `execute_broadcast` | whatsapp |
| Monthly | `calculate_monthly_commissions` | partners |

---

## External Integrations

| Integration | Purpose | Status |
|-------------|---------|--------|
| Meta WhatsApp Cloud API | Messaging, commerce, templates | Production |
| Meta Graph API | Facebook + Instagram publishing, DMs | Production |
| TikTok Content Posting API | Video/photo publishing | Working prototype |
| LinkedIn REST API | Post publishing | Working prototype |
| OpenAI | LLM generation, Whisper transcription | Production |
| Anthropic | LLM generation (Claude) | Production |
| OpenRouter | Vision moderation, fallback routing | Production |
| Tavily | Web search for Research Agent | Production |
| Photoroom | Product image enhancement (18 modules) | Production |
| Fal.ai | Flux image edit + Kling video | Partial |
| Bannerbear | Branded carousel slides | Partial |
| Together AI | Image generation (FLUX) | Production |
| Pollinations | Image generation (fallback) | Production |
| HuggingFace | Image generation (FLUX fallback) | Production |
| Stripe | Subscription billing | Production |
| M-Pesa (Daraja) | Subscription + commerce payments | Production |
| Resend | Transactional email | Production |
| Cloudflare R2 | Object storage | Production |
| Sentry | Error monitoring | Production |
| Shopify | Store integration, webhooks | Stub |
| Remotion | Programmatic video rendering | Experimental |

---

## URL Structure

### Public Routes (no auth)
- `/` — Marketing landing
- `/k/<slug>/` — Kova Link pages
- `/p/<slug>/` — Business profile pages
- `/shop/<page_slug>/` — Public storefront
- `/c/<campaign_slug>/` — Campaign landing pages
- `/book/<slug>/` — Public booking
- `/qr/<token>/` — QR scan landing
- `/walkin/<slug>/` — Walk-in cashier
- `/blog/`, `/learn/` — Public content
- `/partners/` — Partner program

### Authenticated Routes (business owner)
- `/brief/` — Dashboard/home (Daily Brief)
- `/content/` — Content studio, queue, calendar
- `/products/` — Product management, commerce
- `/agents/` — AI agent control
- `/analytics/` — Insights, competitors, revenue
- `/engage/` — Social inbox
- `/whatsapp/` — WhatsApp inbox, broadcasts, channels
- `/leads/` — CRM
- `/links/` — Link pages management
- `/platforms/` — Social account connections
- `/billing/` — Subscription management
- `/teams/` — Team/brand management
- `/accounts/settings/` — Profile and Business Brain

### Staff Routes
- `/dashboard/` — Admin ops (141 templates, ~250 routes)
- `/admin/` — Django admin

### API Routes
- `/api/v1/` — REST API (Pro/Agency plans)
- `/api/v1/partner/` — Marketplace partner API
- `/api/schema/` — OpenAPI documentation

---

## Database Architecture

### Model Count by Domain

| Domain | Models | Key Tables |
|--------|--------|------------|
| WhatsApp | 14 | Conversations, Messages, Templates, Broadcasts, Channels, CustomerMemory |
| Analytics | 13 | PostMetric, Competitor, Conversion, GrowthSnapshot, WebsiteEvent |
| Content | 10 | ContentSeed, Post, Campaign, ABTest, WeeklyContentPlan |
| Commerce | 9 | Product, Category, StockUpdate, BusinessAsset, CommercePayment |
| Billing | 9 | BillingEvent, MpesaPayment, PlanPrice, DiscountCode |
| Partners | 10 | Partner, Referral, Commission, MarketplacePartner |
| Emails | 7 | EmailLog, EmailCampaign, EmailSequence, EmailSubscriber |
| Links | 6 | KovaPage, KovaLink, LinkClick, KovaForm |
| Help | 6 | Article, Changelog, WeeklyDigest |
| Leads | 5 | Lead, LeadActivity, NurtureSequence |
| Teams | 5 | Team, Brand, TeamMember |
| Agents | 4 | AgentConfig, AgentAction, LLMConfig, UserTokenBucket |
| Accounts | 3 | User, UserProfile, PilotMetricsSnapshot |
| Engage | 3 | Interaction, EngageReply, Superfan |
| QR | 3 | QRCode, QRScan, WalkInEvent |
| Notifications | 2 | Notification, NotificationPreference |
| Briefs | 2 | DailyBrief, BriefWhatsAppLog |
| Bookings | 2 | BookingLink, Booking |
| Platforms | 1 | SocialAccount |
| Reviews | 1 | ReviewRequest |

### Hub Models (highest FK reference count)
1. `accounts.User` — referenced by nearly every app
2. `content.Post` — publishing, analytics, leads, bookings, QR, email
3. `platforms.SocialAccount` — OAuth connections; hub for WhatsApp + publishing
4. `products.Product` — commerce, content, conversions, payments
5. `content.ContentSeed` / `MarketingCampaign` — content generation pipeline
6. `teams.Brand` — multi-brand content scoping

---

## Deployment Architecture

```
Railway Platform
├── Web (Daphne ASGI + Gunicorn fallback)
├── Worker (Celery — 3 priority queues: critical/default/low)
├── Beat (Celery Beat scheduler)
└── Release (migrations + collectstatic)

External Services
├── PostgreSQL 16 (Railway managed)
├── Redis (Railway managed)
├── Cloudflare R2 (media storage)
├── Sentry (error monitoring)
└── Meta / OpenAI / Stripe / M-Pesa / etc.
```

---

## Architecture Assessment

### Strengths
- Clean app separation with minimal circular dependencies
- Proper service layer for complex operations (billing, WhatsApp, email)
- AI agents are well-isolated with shared LLM abstraction
- Celery priority queues prevent low-priority tasks from blocking critical operations
- Token budget system prevents LLM cost overrun
- Content safety gates with fail-closed publishing

### Weaknesses
- `docs/config/` as the Django project package is confusing (should be `config/`)
- No formal service layer pattern — business logic split between views, tasks, and ad-hoc modules
- 18 Photoroom files suggest over-engineering for a single integration
- Partner marketplace (10 models) is premature for V1
- Duplicate model names across apps (`PageView`, `WeeklyDigest`, `SequenceEnrollment`)
- Legacy `campaigns` app still in INSTALLED_APPS (migrations-only)
- `kova_page` app duplicates functionality in `links` app
