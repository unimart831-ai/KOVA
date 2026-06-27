# Kova Agent

**Your social media runs itself. You stay in control.**

Kova Agent is an autonomous social media intelligence platform for African SMEs, powered by 6 specialized AI agents that research trends, create content in your brand voice, optimize per platform, engage your audience with safety rails, and compile daily strategy briefs — all while tracking revenue attribution from social post to M-Pesa payment.

## Tech Stack

- **Backend:** Django 5.1, Django REST Framework, Celery + Redis, PostgreSQL 16 (pgvector)
- **Frontend:** Django Templates, HTMX 2.0, Alpine.js 3.14, Tailwind CSS 3.4
- **AI:** Custom agent layer (`apps/agents/`), OpenAI/Anthropic/OpenRouter/DeepSeek via LLM router, Tavily web search, FLUX image generation
- **Payments:** M-Pesa STK Push (Kenya primary), Stripe (international)
- **Infrastructure:** Railway (Nixpacks), Docker Compose (local), Cloudflare R2 (media), Sentry (monitoring)
- **Messaging:** WhatsApp Cloud API, Resend (transactional email)

## Quick Start

### 1. Clone & setup environment

**Requires Python 3.12** (see `.python-version`). On Windows, use the launcher if `python` points to an older version:

```bash
cd kova_agent
py -3.12 -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux
pip install -r requirements/development.txt
```

### 2. Install Tailwind

```bash
npm install
```

### 3. Setup environment variables

```bash
copy .env.example .env
# Edit .env with your actual keys
```

### 4. Start services (Docker)

```bash
docker-compose up -d db redis
```

### 5. Run migrations

```bash
python manage.py migrate
python manage.py createsuperuser
```

### 6. Run development server

Open two terminals:

```bash
# Terminal 1 — Django (Python 3.12)
py -3.12 manage.py runserver

# Terminal 2 — Tailwind CSS watcher
npm run dev:css
```

### 7. Open in browser

- App: http://localhost:8000
- Admin: http://localhost:8000/admin

## Project Structure

```
kova_agent/
├── apps/                    # 27 Django apps (modular monolith)
│   ├── accounts/            # User model, auth, onboarding, brand intelligence
│   ├── platforms/           # Social account OAuth (9 providers)
│   ├── content/             # Posts, scheduling, A/B tests, voice briefs, media
│   ├── agents/              # AI agent configs, LLM router, token budgets
│   ├── analytics/           # Post metrics, competitors, revenue attribution, Kova Pixel
│   ├── briefs/              # Daily AI briefings
│   ├── engage/              # Inbox, auto-reply with safety rails, superfans
│   ├── billing/             # M-Pesa + Stripe subscriptions, plan enforcement
│   ├── notifications/       # In-app notification system
│   ├── emails/              # Transactional + marketing email (Resend)
│   ├── teams/               # Multi-brand agency management
│   ├── partners/            # Referral program + marketplace B2B API
│   ├── leads/               # CRM-lite, nurture sequences, lead scoring
│   ├── products/            # Product catalog, stock tracking, snap-to-sell
│   ├── campaigns/           # Cross-channel campaign orchestration
│   ├── whatsapp/            # WhatsApp Cloud API (inbox, broadcasts, status, channels)
│   ├── memes/               # Meme trend intelligence + brand adaptation
│   ├── calendar_intel/      # Holiday/cultural moment awareness
│   ├── links/               # Link-in-bio pages + lead capture forms
│   ├── kova_page/           # Public business profile pages
│   ├── media_queue/         # Photo drip publishing queue
│   ├── profile_audit/       # Social profile completeness audits
│   ├── qr_attribution/      # QR codes + walk-in attribution
│   ├── bookings/            # Appointment booking with post attribution
│   ├── reviews/             # Post-conversion review request loop
│   ├── help/                # Help center + public blog
│   ├── admin_dashboard/     # Internal ops dashboard (~100 routes)
│   └── api/                 # REST API v1 + partner marketplace API
├── config/
│   ├── settings/            # Split settings (base, development, production)
│   ├── urls.py              # Root URL configuration
│   ├── celery.py            # Celery configuration (3 priority queues)
│   └── wsgi.py / asgi.py
├── templates/               # ~394 Django HTML templates
│   ├── layouts/             # Base layouts (app, marketing, admin)
│   ├── components/          # Reusable UI components (modals, cards, icons)
│   └── [app]/               # Per-app templates + partials
├── static/
│   ├── css/                 # Tailwind input/output
│   └── js/                  # Kova Pixel, service worker
├── tests/                   # ~390+ pytest tests + Locust load tests
├── docs/                    # 50+ docs (roadmap, API, specs, business)
├── requirements/            # Split: base, development, production
├── .github/workflows/       # CI pipeline (lint, test, security)
├── docker-compose.yml       # Local full stack (web, Postgres, Redis, Celery, Tailwind)
├── Dockerfile               # Development container
├── Procfile                 # Railway process types
├── nixpacks.toml            # Railway build config
└── manage.py
```

## Development

### Pre-commit hooks

```bash
pip install pre-commit
pre-commit install
```

### Running tests

```bash
pytest                          # Run all tests with coverage
pytest -m "not slow"            # Skip slow tests
pytest --cov-report=html        # Generate HTML coverage report
```

### CI Pipeline

GitHub Actions runs on every push/PR:
- **Lint** — ruff check + format verification
- **Test** — full test suite with PostgreSQL + Redis, coverage threshold (70%)
- **Security** — checks for hardcoded secrets, Django deployment settings

## AI Agents

| Agent | Role | Plan |
|-------|------|------|
| Research | Monitors trends, competitors, and industry news via Tavily | Growth+ |
| Content Creator | Generates posts in your brand voice with safety checks | All |
| Platform Adapter | Optimizes content DNA, schedule, and pillar weights per platform | Growth+ |
| Engagement | Monitors and auto-responds with graduated autonomy + safety rails | Pro+ |
| Analyst | Tracks performance, content DNA analysis, prediction scoring | All |
| Chief Strategist | Orchestrates all agents, compiles daily briefs, weekly plans | Pro+ |

## Pricing

| Plan | Price | Key Features |
|------|-------|-------------|
| **Kova** | KES 1,300/mo (~USD 10) | 4 accounts, 30 campaigns/mo, all 6 AI agents, commerce, leads, revenue dashboard |
| Trial | Free — 7 days, 5 campaigns | Full Kova features for evaluation |
| Agency | Contact sales | White-label, multi-brand, API access, custom limits |

> Legacy tiers (Jipange, Kazi, Biashara, Wakala) are grandfathered for existing subscribers.
> New signups receive the single **Kova** plan. See `apps/billing/models.py` → `PLAN_LIMITS` for authoritative limits.

## Documentation

- [Development Roadmap](docs/DEVELOPMENT_ROADMAP.md) — 12-sprint master plan
- [API Reference](docs/API_REFERENCE.md) — REST API v1
- [Platform Setup](docs/PLATFORM_DEVELOPER_SETUP.md) — OAuth for 9 platforms
- [Testing Guide](docs/KOVA_TESTING_GUIDE.md) — Test procedures and coverage
- [Co-Founder Audit](docs/COFOUNDER_PLATFORM_AUDIT_2026_05.md) — Full system audit (May 2026)

## License

Proprietary. All rights reserved.
