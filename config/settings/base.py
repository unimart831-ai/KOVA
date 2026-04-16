"""
Base settings for Kova Agent.
Shared across all environments (development, production).
"""

import os
from pathlib import Path

import environ

# ─── PATHS ───────────────────────────────────────────────────────────────────
# BASE_DIR = kova_agent/ (the project root containing manage.py)
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ─── ENVIRONMENT VARIABLES ───────────────────────────────────────────────────
env = environ.Env(
    DEBUG=(bool, False),
    ALLOWED_HOSTS=(list, []),
)

# Read .env file if it exists (not present on Railway — env vars are injected)
env_file = os.path.join(BASE_DIR, ".env")
if os.path.isfile(env_file):
    environ.Env.read_env(env_file)

# ─── CORE ────────────────────────────────────────────────────────────────────
SECRET_KEY = env("SECRET_KEY", default="INSECURE-dev-key-change-me-in-production")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ─── ENCRYPTION ──────────────────────────────────────────────────────────────
# Dedicated key for Fernet token encryption (falls back to SECRET_KEY)
FERNET_KEYS = [env("FIELD_ENCRYPTION_KEY", default=SECRET_KEY)]

# ─── APPLICATIONS ────────────────────────────────────────────────────────────
DJANGO_APPS = [
    "daphne",  # Must be before django.contrib.staticfiles for ASGI
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sites",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "crispy_forms",
    "crispy_tailwind",
    "django_htmx",
    "django_celery_beat",
    "django_extensions",
    "rest_framework",
    "rest_framework.authtoken",
    "channels",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.platforms",
    "apps.content",
    "apps.agents",
    "apps.analytics",
    "apps.briefs",
    "apps.engage",
    "apps.billing",
    "apps.notifications",
    "apps.emails",
    "apps.admin_dashboard",
    "apps.help",
    "apps.teams",
    "apps.partners",
    "apps.media_queue",
    "apps.links",
    "apps.leads",
    "apps.products",
    "apps.campaigns",
    "apps.whatsapp",
    "apps.memes",
    "apps.api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── MIDDLEWARE ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.accounts.middleware.OnboardingMiddleware",
    "apps.billing.middleware.PlanEnforcementMiddleware",
    "apps.partners.middleware.ReferralMiddleware",
]

# ─── URLS ────────────────────────────────────────────────────────────────────
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ─── TEMPLATES ───────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# ─── DATABASE ────────────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://kova:kova@localhost:5432/kova_agent"),
}

# ─── CACHE / REDIS ───────────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="")

if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {
                "hosts": [REDIS_URL],
            },
        },
    }
    CELERY_BROKER_URL = env("CELERY_BROKER_URL", default=REDIS_URL)
    CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default=REDIS_URL)
else:
    # Fallback: no Redis available (app still works without real-time features)
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        },
    }
    CELERY_BROKER_URL = ""
    CELERY_RESULT_BACKEND = ""
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_TASK_EAGER_PROPAGATES = True
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"
# Reduce Redis writes: short-lived results auto-expire after 1 hour
CELERY_RESULT_EXPIRES = 3600
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "check-and-publish-due-posts": {
        "task": "content.check_and_publish_due_posts",
        "schedule": 300.0,  # every 5 minutes
    },
    "fetch-all-recent-metrics": {
        "task": "content.fetch_all_recent_metrics",
        "schedule": 6 * 3600.0,  # every 6 hours
    },
    "refresh-expiring-tokens": {
        "task": "platforms.refresh_expiring_tokens",
        "schedule": 30 * 60.0,  # every 30 minutes
    },
    "generate-daily-briefs": {
        "task": "briefs.generate_all_daily_briefs",
        "schedule": 15 * 60.0,  # every 15 minutes — checks which users' brief time has passed
    },
    "run-daily-research": {
        "task": "agents.run_daily_research",
        "schedule": 12 * 3600.0,  # every 12 hours — trend data for daily briefs
    },
    "run-engage-cycle": {
        "task": "agents.run_engage_cycle",
        "schedule": 30 * 60.0,  # every 30 minutes — fetch, analyze, reply
    },
    "run-strategy-cycle": {
        "task": "agents.run_strategy_cycle",
        "schedule": 8 * 3600.0,  # every 8 hours — proactive content + strategy
    },
    "check-mpesa-subscriptions": {
        "task": "billing.check_mpesa_subscriptions",
        "schedule": 24 * 3600.0,  # daily — expiry checks, grace period, renewals
    },
    "analyze-all-competitors": {
        "task": "analyze-all-competitors",
        "schedule": 7 * 24 * 3600.0,  # weekly — AI competitive analysis
    },
    "evaluate-ab-tests": {
        "task": "content.evaluate_ab_tests",
        "schedule": 3600.0,  # every hour — check running A/B tests
    },
    "measure-agent-outcomes": {
        "task": "agents.measure_agent_outcomes",
        "schedule": 12 * 3600.0,  # every 12 hours — score past agent actions against outcomes
    },
    "process-media-queues-every-5-min": {
        "task": "media_queue.process_queues",
        "schedule": 300.0,  # every 5 minutes — publish queued media
    },
    "check-stock-alerts": {
        "task": "check-stock-alerts",
        "schedule": 24 * 3600.0,  # daily — scan products for stock issues
    },
    "track-audience-growth": {
        "task": "agents.track_audience_growth",
        "schedule": 24 * 3600.0,  # daily — snapshot follower counts for growth intelligence
    },
    "check-trial-expiry-emails": {
        "task": "emails.check_trial_expiry_emails",
        "schedule": 24 * 3600.0,  # daily — send trial countdown emails (day 7, 3, 1, 0)
    },
    "discover-trending-memes": {
        "task": "memes.discover_trending_memes",
        "schedule": 3 * 3600.0,  # every 3 hours — AI meme trend discovery
    },
    "adapt-memes-for-users": {
        "task": "memes.adapt_memes_for_users",
        "schedule": 4 * 3600.0,  # every 4 hours — create brand-adapted memes for users
    },
    "update-meme-lifecycle": {
        "task": "memes.update_meme_lifecycle",
        "schedule": 24 * 3600.0,  # daily — age out stale memes
    },
    # WhatsApp Sprint 5C — Status Studio
    "generate-status-queue": {
        "task": "whatsapp.generate_status_queue",
        "schedule": 24 * 3600.0,  # daily
    },
    # WhatsApp Sprint 5D — Broadcasts + Analytics
    "process-sequence-steps": {
        "task": "whatsapp.process_sequence_steps",
        "schedule": 30 * 60.0,  # every 30 minutes
    },
    "aggregate-daily-wa-analytics": {
        "task": "whatsapp.aggregate_daily_analytics",
        "schedule": 24 * 3600.0,  # daily
    },
    "generate-weekly-wa-digest": {
        "task": "whatsapp.generate_weekly_digest",
        "schedule": 7 * 24 * 3600.0,  # weekly
    },
    # WhatsApp Sprint 5E — Channels
    "curate-channel-content": {
        "task": "whatsapp.curate_channel_content",
        "schedule": 6 * 3600.0,  # every 6 hours
    },
}

# ─── AUTH ────────────────────────────────────────────────────────────────────
AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

# django-allauth config
SITE_ID = 1
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_SIGNUP_REDIRECT_URL = "/accounts/onboarding/"
LOGIN_REDIRECT_URL = "/brief/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

# Session: keep users logged in for 30 days
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days
SESSION_SAVE_EVERY_REQUEST = True         # Reset expiry on each request

# Allauth: always remember the session (skip "remember me" checkbox)
ACCOUNT_SESSION_REMEMBER = True
# Rate limiting (allauth built-in)
ACCOUNT_RATE_LIMITS = {
    "login": "5/m/ip,30/h/ip",          # 5 attempts/min, 30/hour per IP
    "login_failed": "5/m/ip,10/h/ip",   # After 10 failed/hour, lock out
    "signup": "5/m/ip,20/h/ip",          # 5 signups/min per IP
    "confirm_email": "3/m/key",          # 3 confirm attempts/min per key
    "reset_password": "5/m/ip,10/h/ip",  # 5 resets/min per IP
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ─── INTERNATIONALIZATION ────────────────────────────────────────────────────
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ─── STATIC FILES ────────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# ─── MEDIA FILES ─────────────────────────────────────────────────────────────
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# ─── DEFAULT PRIMARY KEY ─────────────────────────────────────────────────────
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ─── CRISPY FORMS ────────────────────────────────────────────────────────────
CRISPY_ALLOWED_TEMPLATE_PACKS = "tailwind"
CRISPY_TEMPLATE_PACK = "tailwind"

# ─── REST FRAMEWORK ─────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.TokenAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "apps.api.throttling.PlanBasedThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "20/minute",
        "user": "120/minute",
    },
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
}

# ─── AI / LLM CONFIG ────────────────────────────────────────────────────────
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
DEFAULT_LLM_PROVIDER = env("DEFAULT_LLM_PROVIDER", default="openai")  # openai | anthropic | openrouter
DEFAULT_LLM_MODEL = env("DEFAULT_LLM_MODEL", default="gpt-4o-mini")
# Paid fallback — auto-escalate to a DIFFERENT provider when the primary model fails.
# Gemini 2.0 Flash: $0.10/$0.40 per 1M tokens — fast, cheap, different provider for redundancy.
LLM_PAID_FALLBACK = env("LLM_PAID_FALLBACK", default="google/gemini-2.0-flash-001")
LLM_PAID_FALLBACK_PROVIDER = env("LLM_PAID_FALLBACK_PROVIDER", default="openrouter")

# Tiered model routing — right model for each task.
# Override individual tasks via env vars, or change the tier defaults.
# Tier: premium (creative writing) | workhorse (reasoning) | fast (classification)
# PRODUCTION: Using DeepSeek V3.2 — 89th-percentile intelligence, $0.26/$0.38 per 1M tokens.
# Estimated cost: ~$0.001/call × ~15 calls/day/user ≈ $0.50/month per active user.
# Updated 2026-04-10: Switched from unreliable free models to DeepSeek V3.2 paid.
LLM_MODEL_PREMIUM = env("LLM_MODEL_PREMIUM", default="deepseek/deepseek-v3.2")
LLM_MODEL_WORKHORSE = env("LLM_MODEL_WORKHORSE", default="deepseek/deepseek-v3.2")
LLM_MODEL_FAST = env("LLM_MODEL_FAST", default="deepseek/deepseek-v3.2")

AGENT_MODELS = {
    # Create Agent — user-facing content, needs top creative quality
    "create.generate": env("LLM_MODEL_CREATE_GENERATE", default=LLM_MODEL_PREMIUM),
    "create.regenerate": env("LLM_MODEL_CREATE_REGENERATE", default=LLM_MODEL_PREMIUM),
    "create.repurpose": env("LLM_MODEL_CREATE_REPURPOSE", default=LLM_MODEL_PREMIUM),
    # Engage Agent — replies are user-facing, analysis is not
    "engage.analyze": env("LLM_MODEL_ENGAGE_ANALYZE", default=LLM_MODEL_FAST),
    "engage.reply": env("LLM_MODEL_ENGAGE_REPLY", default=LLM_MODEL_PREMIUM),
    # Analyst Agent — structured data extraction, no creativity needed
    "analyst.performance": env("LLM_MODEL_ANALYST_PERFORMANCE", default=LLM_MODEL_FAST),
    "analyst.content_dna": env("LLM_MODEL_ANALYST_DNA", default=LLM_MODEL_FAST),
    "analyst.predict": env("LLM_MODEL_ANALYST_PREDICT", default=LLM_MODEL_FAST),
    # Research Agent — reasoning + semi-creative
    "research.trends": env("LLM_MODEL_RESEARCH_TRENDS", default=LLM_MODEL_WORKHORSE),
    "research.angles": env("LLM_MODEL_RESEARCH_ANGLES", default=LLM_MODEL_WORKHORSE),
    # Adapt Agent — data analysis
    "adapt.schedule": env("LLM_MODEL_ADAPT_SCHEDULE", default=LLM_MODEL_FAST),
    # Strategist — reasoning + synthesis
    "strategist.brief": env("LLM_MODEL_STRATEGIST_BRIEF", default=LLM_MODEL_WORKHORSE),
    "strategist.decide": env("LLM_MODEL_STRATEGIST_DECIDE", default=LLM_MODEL_WORKHORSE),
}

# ─── TOKEN COST REGISTRY ─────────────────────────────────────────────────────
# Per-model pricing in USD per 1K tokens: (input_cost, output_cost)
# Updated: 2026-04-02. Source: provider pricing pages.
# Add your models here. Unknown models fall back to DEFAULT_TOKEN_COST.
# Free models are explicitly $0. This ensures accurate cost tracking.
DEFAULT_TOKEN_COST = (0.0, 0.0)  # fallback for unrecognized models

MODEL_TOKEN_COSTS = {
    # ── Free OpenRouter models (dev) ──────────────────────────────────
    "nvidia/nemotron-3-super-120b-a12b:free":(0.0, 0.0),
    "openai/gpt-oss-120b:free":             (0.0, 0.0),
    "nvidia/nemotron-3-nano-30b-a3b:free":  (0.0, 0.0),
    "minimax/minimax-m2.5:free":            (0.0, 0.0),
    "z-ai/glm-4.5-air:free":               (0.0, 0.0),
    "mistralai/mistral-7b-instruct:free":   (0.0, 0.0),
    # Dead/deprecated — kept for historical cost lookups:
    "qwen/qwen3.6-plus:free":              (0.0, 0.0),
    "stepfun/step-3.5-flash:free":          (0.0, 0.0),
    "meta-llama/llama-4-maverick:free":     (0.0, 0.0),

    # ── OpenAI ────────────────────────────────────────────────────────
    "gpt-4o-mini":          (0.00015, 0.0006),   # $0.15/$0.60 per 1M
    "gpt-4o":               (0.0025,  0.01),      # $2.50/$10 per 1M
    "gpt-4o-2024-11-20":    (0.0025,  0.01),
    "gpt-4-turbo":          (0.01,    0.03),      # $10/$30 per 1M
    "gpt-3.5-turbo":        (0.0005,  0.0015),    # $0.50/$1.50 per 1M
    "o3-mini":              (0.0011,  0.0044),     # $1.10/$4.40 per 1M

    # ── Anthropic ─────────────────────────────────────────────────────
    "claude-3-5-haiku-20241022": (0.0008, 0.004),  # $0.80/$4 per 1M
    "claude-3-5-sonnet-20241022":(0.003,  0.015),   # $3/$15 per 1M
    "claude-3-opus-20240229":    (0.015,  0.075),    # $15/$75 per 1M
    "claude-sonnet-4-20250514":  (0.003,  0.015),

    # ── OpenRouter paid models ────────────────────────────────────────
    "google/gemini-2.0-flash-001":    (0.0001, 0.0004),  # $0.10/$0.40 per 1M
    "google/gemini-2.5-pro-preview":  (0.00125, 0.01),
    "google/gemini-3-flash-preview":  (0.0005, 0.003),   # $0.50/$3.00 per 1M
    "deepseek/deepseek-chat-v3-0324": (0.00014, 0.00028),
    "deepseek/deepseek-v3.2":         (0.00026, 0.00038), # $0.26/$0.38 per 1M — primary paid fallback
    "stepfun/step-3.5-flash":          (0.0001, 0.0003),  # $0.10/$0.30 per 1M
    "minimax/minimax-m2.7":            (0.0003, 0.0012),  # $0.30/$1.20 per 1M
    "meta-llama/llama-3.3-70b-instruct": (0.00039, 0.00039),
}

# ─── AI IMAGE GENERATION ─────────────────────────────────────────────────────
# Multi-provider with fallback: Hugging Face → Together.ai → Pollinations.ai
AI_IMAGE_GENERATION_ENABLED = env.bool("AI_IMAGE_GENERATION_ENABLED", default=True)
HF_TOKEN = env("HF_TOKEN", default="")                        # https://huggingface.co/settings/tokens — FLUX.1-schnell (free)
TOGETHER_API_KEY = env("TOGETHER_API_KEY", default="")        # https://api.together.xyz — sign up, add $5 credit
TOGETHER_IMAGE_MODEL = env("TOGETHER_IMAGE_MODEL", default="black-forest-labs/FLUX.1-schnell")  # $0.003/image
POLLINATIONS_API_KEY = env("POLLINATIONS_API_KEY", default="") # https://pollinations.ai — Flux Schnell
AI_IMAGE_MODEL = env("AI_IMAGE_MODEL", default="flux")        # Pollinations model: flux | gptimage | zimage

# ─── WEB SEARCH (Tavily — real-time trend data for Research Agent) ───────────
# Free tier: 1000 searches/month — sign up at https://tavily.com
# When configured, Research Agent uses real web data instead of LLM hallucinations.
TAVILY_API_KEY = env("TAVILY_API_KEY", default="")

# ─── WEB SEARCH (Tavily — real-time trend data for Research Agent) ───────────
# Free tier: 1000 searches/month — sign up at https://tavily.com
# When configured, Research Agent uses real web data instead of LLM hallucinations.
TAVILY_API_KEY = env("TAVILY_API_KEY", default="")

# ─── STRIPE (kept for future international billing) ─────────────────────────
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_PRICE_STARTER = env("STRIPE_PRICE_STARTER", default="")  # KES 99/mo — 14-day trial
STRIPE_PRICE_GROWTH = env("STRIPE_PRICE_GROWTH", default="")
STRIPE_PRICE_PRO = env("STRIPE_PRICE_PRO", default="")
STRIPE_PRICE_AGENCY = env("STRIPE_PRICE_AGENCY", default="")

# ─── M-PESA (Daraja API — primary payment for Kenya) ────────────────────────
MPESA_ENVIRONMENT = env("MPESA_ENVIRONMENT", default="sandbox")  # sandbox | production
MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = env("MPESA_SHORTCODE", default="174379")       # Sandbox default
MPESA_PASSKEY = env(
    "MPESA_PASSKEY",
    default="bfb279f9aa9bdbcf158e97dd71a467cd2e0c893059b10f78e6b72ada1ed2c919",  # Sandbox default
)
MPESA_CALLBACK_URL = env("MPESA_CALLBACK_URL", default="")       # e.g. https://yourdomain.com/billing/webhook/mpesa/
MPESA_WEBHOOK_SECRET = env("MPESA_WEBHOOK_SECRET", default="")   # Optional: append ?token=<secret> to callback URL
MPESA_TRIAL_DAYS = env.int("MPESA_TRIAL_DAYS", default=14)

# ─── SOCIAL PLATFORM OAUTH ───────────────────────────────────────────────────
TWITTER_CLIENT_ID = env("TWITTER_CLIENT_ID", default="")
TWITTER_CLIENT_SECRET = env("TWITTER_CLIENT_SECRET", default="")
LINKEDIN_CLIENT_ID = env("LINKEDIN_CLIENT_ID", default="")
LINKEDIN_CLIENT_SECRET = env("LINKEDIN_CLIENT_SECRET", default="")
FACEBOOK_APP_ID = env("FACEBOOK_APP_ID", default="")
FACEBOOK_APP_SECRET = env("FACEBOOK_APP_SECRET", default="")
FB_LOGIN_CONFIG_ID = env("FB_LOGIN_CONFIG_ID", default="")  # Facebook Login for Business config ID
TIKTOK_CLIENT_KEY = env("TIKTOK_CLIENT_KEY", default="")
TIKTOK_CLIENT_SECRET = env("TIKTOK_CLIENT_SECRET", default="")

# Sprint 8 — New platforms
YOUTUBE_CLIENT_ID = env("YOUTUBE_CLIENT_ID", default="")
YOUTUBE_CLIENT_SECRET = env("YOUTUBE_CLIENT_SECRET", default="")
PINTEREST_APP_ID = env("PINTEREST_APP_ID", default="")
PINTEREST_APP_SECRET = env("PINTEREST_APP_SECRET", default="")
THREADS_APP_ID = env("THREADS_APP_ID", default="")        # Falls back to FACEBOOK_APP_ID in provider
THREADS_APP_SECRET = env("THREADS_APP_SECRET", default="") # Falls back to FACEBOOK_APP_SECRET in provider

# ── WhatsApp Cloud API ────────────────────────────────────────────────────
WHATSAPP_PHONE_NUMBER_ID = env("WHATSAPP_PHONE_NUMBER_ID", default="")  # Meta phone number ID
WHATSAPP_ACCESS_TOKEN = env("WHATSAPP_ACCESS_TOKEN", default="")        # Permanent system user token
WHATSAPP_WABA_ID = env("WHATSAPP_WABA_ID", default="")                 # WhatsApp Business Account ID
WHATSAPP_VERIFY_TOKEN = env("WHATSAPP_VERIFY_TOKEN", default="kova-whatsapp-verify")  # Webhook verification
WHATSAPP_APP_SECRET = env("WHATSAPP_APP_SECRET", default="")            # For webhook signature validation

STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# ─── SITE URL ────────────────────────────────────────────────────────────────
SITE_URL = env("SITE_URL", default="http://localhost:8000")

# ─── EMAIL ───────────────────────────────────────────────────────────────────
# Default: console backend for dev. Production uses Resend SMTP.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Kova Agent <noreply@kovaagent.com>")
RESEND_API_KEY = env("RESEND_API_KEY", default="")
RESEND_WEBHOOK_SECRET = env("RESEND_WEBHOOK_SECRET", default="")
