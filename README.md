# Kova Agent

**Your social media runs itself. You stay in control.**

Kova Agent is an autonomous social media intelligence platform powered by 6 specialized AI agents that research trends, create content, optimize timing, engage your audience, and analyze performance.

## Tech Stack

- **Backend:** Django 5.x, Django REST Framework, Celery, Redis, PostgreSQL
- **Frontend:** Django Templates, HTMX, Alpine.js, Tailwind CSS
- **AI:** LangGraph/CrewAI, OpenAI, Anthropic
- **Infrastructure:** Docker, Docker Compose

## Quick Start

### 1. Clone & setup environment

```bash
cd kova_agent
python -m venv venv
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
# Terminal 1 — Django
python manage.py runserver

# Terminal 2 — Tailwind CSS watcher
npm run dev:css
```

### 7. Open in browser

- App: http://localhost:8000
- Admin: http://localhost:8000/admin

## Project Structure

```
kova_agent/
├── apps/
│   ├── accounts/      # User model, auth, onboarding
│   ├── platforms/     # Connected social accounts
│   ├── content/       # Posts, media, scheduling
│   ├── agents/        # AI agent configs & action logs
│   ├── analytics/     # Post metrics & insights
│   ├── briefs/        # Daily briefings
│   ├── engage/        # Comments, replies, interactions
│   └── billing/       # Stripe subscriptions
├── config/
│   ├── settings/      # Split settings (base, dev, prod)
│   ├── urls.py        # Root URL configuration
│   ├── celery.py      # Celery configuration
│   └── wsgi.py / asgi.py
├── templates/
│   ├── layouts/       # Base layouts (app, marketing)
│   ├── components/    # Reusable UI components
│   ├── account/       # Allauth overrides (login, signup)
│   ├── accounts/      # Settings, onboarding
│   ├── pages/         # Landing page
│   └── [app]/         # Per-app templates
├── static/
│   ├── css/           # Tailwind input/output
│   ├── js/            # Alpine.js app code
│   └── images/
├── docs/
│   └── DEVELOPMENT_ROADMAP.md
├── requirements/
│   ├── base.txt
│   ├── development.txt
│   └── production.txt
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── package.json
└── tailwind.config.js
```

## Development Roadmap

See [docs/DEVELOPMENT_ROADMAP.md](docs/DEVELOPMENT_ROADMAP.md) for the full 12-sprint plan.

## AI Agents

| Agent | Role |
|-------|------|
| 🔍 Research | Monitors trends, competitors, and industry news |
| ✍️ Content Creator | Generates posts in your brand voice |
| 🔄 Platform Adapter | Optimizes content for each platform |
| 💬 Engagement | Monitors and responds to interactions |
| 📊 Analytics | Tracks performance and finds patterns |
| 🧠 Chief Strategist | Orchestrates all agents, compiles daily briefs |

## License

Proprietary. All rights reserved.
