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
├── apps/                    # 5 domains → Django apps (modular monolith)
│   ├── core/                # Identity, billing, teams, ops
│   │   ├── accounts/        # Users, auth, onboarding, brand intelligence
│   │   ├── platforms/       # Social OAuth (+ profile_audit)
│   │   ├── billing/         # M-Pesa + Stripe
│   │   ├── teams/           # Multi-brand agencies
│   │   ├── partners/        # Referrals / marketplace
│   │   └── admin_dashboard/ # Internal ops
│   ├── create/              # Make & publish
│   │   ├── content/         # Posts, studio, scheduling
│   │   ├── agents/          # AI agents + LLM router
│   │   ├── media/           # Media orchestration
│   │   └── briefs/          # Daily briefings + calendar preferences
│   ├── messaging/           # Conversations & outreach
│   │   ├── engage/          # Needs-reply hub, comments, FB/IG DMs
│   │   ├── whatsapp/        # WhatsApp Cloud API workspace
│   │   ├── emails/          # Transactional + marketing email
│   │   └── notifications/   # In-app notifications
│   ├── commerce/            # Sell & convert
│   │   ├── products/        # Catalog, snap-to-sell, Photoroom
│   │   ├── links/           # Link-in-bio (/k/) + Business Hub (/p/)
│   │   ├── leads/           # CRM-lite
│   │   ├── bookings/        # Appointments (FEATURE_BOOKINGS)
│   │   ├── reviews/         # Post-sale reviews (FEATURE_REVIEWS)
│   │   └── qr_attribution/  # QR / walk-in (FEATURE_QR_ATTRIBUTION)
│   └── insight/             # Measure & expose
│       ├── analytics/       # Metrics, pixel, attribution
│       ├── api/             # REST API v1
│       └── help/            # Help center + system maps
├── config/                  # Django settings, urls, celery, ASGI/WSGI
├── templates/
├── static/
├── tests/
├── docs/
└── manage.py
```

Django **app labels** (migration history) are unchanged — only Python import paths moved under domains.

Stub apps folded: `calendar_intel` → `briefs`, `profile_audit` → `platforms` (URL names preserved).

Optional surfaces: `KOVA_FEATURES` / `FEATURE_*` env vars (defaults on). See `apps/README.md`.

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

- [Docs index](docs/README.md) — all essential docs
- [Development Roadmap](docs/DEVELOPMENT_ROADMAP.md) — product / sprint plan
- [API Reference](docs/API_REFERENCE.md) — REST API v1
- [Platform Setup](docs/PLATFORM_DEVELOPER_SETUP.md) — OAuth for social platforms
- [Testing Guide](docs/KOVA_TESTING_GUIDE.md) — test procedures and coverage
- [Legacy & debt](docs/v1-audit/TECHNICAL_DEBT_REGISTER.md) — known debt register

## License

Proprietary. All rights reserved.
