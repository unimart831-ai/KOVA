# Kova V1 Scope Definition

**Date:** July 2026

---

## V1 Promise

> A business owner can manage their online presence by chatting with Kova on WhatsApp, while the web platform quietly handles orchestration, commerce management, integrations, analytics, and configuration.

---

## Scope Categories

### Launch in V1

Features that are implemented, aligned with the vision, and required to deliver the V1 promise.

---

#### WhatsApp Business Operations

| Feature | Module | Status |
|---------|--------|--------|
| Owner Daily Brief (WhatsApp delivery) | `briefs` | Ready |
| Owner commands (approve, reject, brief, score, leads, money, snap) | `briefs/whatsapp_commands.py` | Ready |
| Customer conversations (AI auto-reply) | `whatsapp/tasks.py` | Ready |
| FAQ Autopilot | `whatsapp/autopilot.py` | Ready |
| Follow-up nudges (24h) | `whatsapp/autopilot.py` | Ready |
| Conversational commerce (browse, order, pay) | `whatsapp/commerce.py` | Ready |
| M-Pesa in-chat payments | `whatsapp/commerce_enhanced.py` | Ready |
| Customer memory | `whatsapp/memory.py` | Ready |
| WhatsApp webhook (inbound/status) | `whatsapp/webhook.py` | Ready |
| Outbound messaging service | `whatsapp/services.py` | Ready |
| Template management | `whatsapp/models.py` | Ready |
| Owner onboarding via WhatsApp | `whatsapp/owner_onboarding.py` | Ready |

---

#### AI Intelligence Engine

| Feature | Module | Status |
|---------|--------|--------|
| Business Brain (6-layer DNA) | `accounts/business_brain.py` | Ready |
| Chief Strategist Agent | `agents/strategist_agent.py` | Ready |
| Create Agent (content generation) | `agents/create_agent.py` | Ready |
| Research Agent (trend discovery) | `agents/research_agent.py` | Ready |
| Analyst Agent (performance analysis) | `agents/analyst_agent.py` | Ready |
| Adapt Agent (learning loop) | `agents/adapt_agent.py` | Ready |
| Engage Agent (social replies) | `agents/engage_agent.py` | Ready |
| LLM abstraction (multi-provider) | `agents/llm.py` | Ready |
| Token budget enforcement | `agents/budget.py` | Ready |
| Agent memory & outcomes | `agents/memory.py` | Ready |
| Visual strategy | `agents/visual_strategy.py` | Ready |
| AI image generation | `agents/media.py` | Ready |
| Branded graphics | `agents/graphics.py` | Ready |
| Content safety gates | `content/safety.py` | Ready |
| Voice memo transcription | `content/voice.py` | Ready |
| Platform copy rewrite | `content/platform_rewrite.py` | Ready |
| Industry playbooks (cold start) | `agents/playbooks.py` | Ready |

---

#### Content & Publishing

| Feature | Module | Status |
|---------|--------|--------|
| Content generation from seeds | `content/tasks.py` | Ready |
| Post scheduling + auto-publish | `content/tasks.py` | Ready |
| Facebook publishing | `platforms/providers/instagram_facebook.py` | Ready |
| Instagram publishing | `platforms/providers/instagram_facebook.py` | Ready |
| WhatsApp Status publishing | `whatsapp/models.py` (StatusContent) | Ready |
| Post metrics collection | `content/tasks.py` | Ready |
| Content queue (approval workflow) | `content/queue.html` | Ready |
| Content calendar | `content/calendar.html` | Ready |
| Weekly content plan | `content/models.py` (WeeklyContentPlan) | Ready |
| Token refresh + health | `platforms/tasks.py` | Ready |
| Platform outage detection | `platforms/outage.py` | Ready |

---

#### Commerce

| Feature | Module | Status |
|---------|--------|--------|
| Product catalog (CRUD) | `products/` | Ready |
| Product categories | `products/models.py` | Ready |
| Public storefront | `products/public/` templates | Ready |
| Snap-to-Sell (photo → product) | `products/owner_snap_whatsapp.py` | Ready |
| M-Pesa commerce payments | `products/models.py` (CommercePayment) | Ready |
| WhatsApp ordering flow | `whatsapp/commerce.py` | Ready |
| Booking links | `bookings/` | Ready |
| Public booking page | `bookings/public/` | Ready |
| Stock tracking + alerts | `products/models.py` | Ready |
| Photoroom product images | `products/photoroom.py` (core) | Ready |
| Commerce link pages | `products/public/commerce_link.html` | Ready |

---

#### Lead Management (Simplified)

| Feature | Module | Status |
|---------|--------|--------|
| Lead capture (storefront/WhatsApp/forms) | `leads/models.py` | Ready |
| Lead list + detail | `leads/` views | Ready |
| Lead scoring | `leads/tasks.py` | Ready |
| WhatsApp lead notifications (via LEADS command) | `briefs/whatsapp_commands.py` | Ready |
| KovaForms (lead capture) | `links/models.py` | Ready |

---

#### Web Platform (Orchestration)

| Feature | Module | Status |
|---------|--------|--------|
| Dashboard/brief homepage | `briefs/home.html` | Ready (simplify) |
| Platform connections (OAuth) | `platforms/` | Ready |
| Business settings + Brain | `accounts/` | Ready |
| Analytics overview | `analytics/insights.html` | Ready (simplify) |
| Billing/subscription | `billing/` | Ready |
| Notification preferences | `notifications/` | Ready |
| Link page management | `links/` | Ready |

---

#### Infrastructure

| Feature | Module | Status |
|---------|--------|--------|
| Auth (email + Facebook + Google) | `accounts/`, allauth | Ready |
| Onboarding flow | `accounts/onboarding.html` | Ready |
| M-Pesa subscriptions | `billing/mpesa_services.py` | Ready |
| Stripe subscriptions | `billing/services.py` | Ready |
| Email transactional (Resend) | `emails/services.py` | Ready |
| Health checks | `apps/system/health_checks.py` | Ready |
| Celery task queues | `docs/config/celery.py` | Ready |
| WebSocket notifications | `notifications/` | Ready |
| REST API (basic) | `apps/api/` | Ready |
| Error monitoring (Sentry) | `docs/config/settings/production.py` | Ready |

---

### Move to V1.1 (1-2 months post-launch)

| Feature | Reason for Deferral |
|---------|-------------------|
| TikTok publishing | Needs app approval validation |
| LinkedIn publishing | B2B niche; lower priority |
| WhatsApp Broadcast sequences | Advanced feature; basic broadcasts sufficient for V1 |
| WhatsApp Channels | Advanced distribution; not core |
| Email marketing (campaigns, sequences) | WhatsApp broadcasts are primary channel for African SMEs |
| Advanced analytics (attribution, content intelligence) | Basic metrics sufficient for launch |
| Performance recycle (auto-republish) | Unvalidated feature |
| Nurture sequences (leads) | Basic lead management sufficient |
| Review request loop | Post-purchase feature; not core to initial launch |
| Carousel generation (Bannerbear) | AI images + graphics sufficient for V1 |
| Video/Reel generation (Fal/Kling) | Complex; image content sufficient for launch |
| Photoroom advanced (virtual models, video, food presets) | Core Photoroom sufficient |
| Engage graduated autonomy (auto-send) | Draft-only mode safer for launch |
| Superfan detection | Nice-to-have analytics |
| Calendar intel (holiday content) | Useful but not blocking |

---

### Move to V2 (3-6 months post-launch)

| Feature | Reason for Deferral |
|---------|-------------------|
| Teams / Multi-brand management | Single business owner is V1 target |
| Partner marketplace (B2B) | No active partners yet |
| QR attribution + walk-in tracking | Physical retail feature |
| A/B testing | Requires sufficient content volume |
| Competitor intelligence (screenshots, landscape) | Advanced analytics |
| Shopify integration | African SMEs unlikely to use Shopify |
| Kova Pixel (website events) | Requires technical setup from SME |
| Advanced CRM (pipeline, kanban) | Simple lead list sufficient |
| Remotion video rendering | Experimental |
| Multi-brand Business Brain | Depends on Teams feature |
| Voice-note-to-action pipeline | Requires testing with real users |
| WhatsApp-editable Brain | Nice conversational UX but not blocking |

---

### Archive (Keep Code, Remove from UI)

| Feature | Reason |
|---------|--------|
| Profile audit | Web-centric; doesn't serve WhatsApp-first |
| Compare pages (Buffer, manual, NAS) | Marketing pages, not product features |
| Campus rep page | Marketing, not product |
| Competitor screenshots | Unvalidated experiment |
| Conversion journeys (multi-touch) | Over-engineered for V1 |

---

### Remove (Delete Code)

| Item | Reason |
|------|--------|
| `campaigns` app from INSTALLED_APPS | Already empty; migrations-only |
| `media_queue` no-op task | Dead code |
| `memes` references | Non-existent app |
| `fundraising/` from Docker builds | Not runtime code |
| `marketing/` from Docker builds | Not runtime code |

---

## V1 Feature Count

| Category | Features |
|----------|----------|
| WhatsApp Operations | 12 |
| AI Intelligence | 17 |
| Content & Publishing | 11 |
| Commerce | 11 |
| Lead Management | 5 |
| Web Orchestration | 7 |
| Infrastructure | 10 |
| **Total V1 Features** | **73** |

---

## V1 App Usage

Apps actively serving V1:

| App | V1 Role |
|-----|---------|
| `accounts` | Auth, onboarding, Business Brain, settings |
| `agents` | All 6 AI agents + infrastructure |
| `analytics` | Basic post metrics + revenue (simplified) |
| `billing` | Subscriptions (M-Pesa + Stripe) |
| `bookings` | Booking links + public pages |
| `briefs` | Daily brief + WhatsApp commands |
| `content` | Content generation, scheduling, publishing, safety |
| `emails` | Transactional email only (not marketing) |
| `engage` | AI auto-reply to social comments/DMs |
| `leads` | Basic lead capture + list |
| `links` | Link-in-bio pages + forms |
| `media` | Media orchestration (simplified) |
| `notifications` | In-app notifications |
| `platforms` | OAuth, token management, providers |
| `products` | Product catalog, storefront, Snap-to-Sell, Photoroom |
| `whatsapp` | Full WhatsApp infrastructure |

Apps **hidden** in V1 (code remains, UI removed):
- `calendar_intel` (runs silently in background)
- `help` (public pages remain; internal editing deferred)
- `partners` (hidden from navigation)
- `qr_attribution` (hidden from navigation)
- `reviews` (hidden from navigation)
- `teams` (hidden from navigation)

Apps **removed** from V1:
- `campaigns` (deprecated)
- `kova_page` (templates remain for `/p/` routes; no management UI)
- `profile_audit` (archived)
