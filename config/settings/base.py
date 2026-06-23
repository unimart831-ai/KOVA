"""
Base settings for Kova Agent.
Shared across all environments (development, production).
"""

import os
from pathlib import Path

import environ

from config.redis_channels import build_channels_redis_layer_config

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
SECRET_KEY = env("SECRET_KEY", default="django-insecure-dev-only-key-DO-NOT-USE-IN-PRODUCTION")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])

# ─── GOOGLE OAUTH (optional) ─────────────────────────────────────────────────
GOOGLE_OAUTH_CLIENT_ID = env("GOOGLE_OAUTH_CLIENT_ID", default="")
GOOGLE_OAUTH_CLIENT_SECRET = env("GOOGLE_OAUTH_CLIENT_SECRET", default="")
GOOGLE_OAUTH_ENABLED = bool(GOOGLE_OAUTH_CLIENT_ID and GOOGLE_OAUTH_CLIENT_SECRET)

# ─── FACEBOOK OAUTH (optional — enables social sign-up + auto-connect) ───────
FACEBOOK_APP_ID = env("FACEBOOK_APP_ID", default="")
FACEBOOK_APP_SECRET = env("FACEBOOK_APP_SECRET", default="")

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
    "django.contrib.humanize",
    "django.contrib.postgres",
]

THIRD_PARTY_APPS = [
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.facebook",
    "crispy_forms",
    "crispy_tailwind",
    "django_htmx",
    "django_celery_beat",
    "django_extensions",
    "rest_framework",
    "rest_framework.authtoken",
    "drf_spectacular",
    "channels",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.platforms",
    "apps.content",
    "apps.agents",
    "apps.analytics",
    "apps.briefs",
    "apps.calendar_intel",
    "apps.media",
    "apps.engage",
    "apps.billing",
    "apps.notifications",
    "apps.emails",
    "apps.admin_dashboard",
    "apps.help",
    "apps.teams",
    "apps.partners",
    "apps.links",
    "apps.leads",
    "apps.products",
    "apps.campaigns",
    "apps.whatsapp",
    "apps.qr_attribution",
    "apps.bookings",
    "apps.reviews",
    "apps.kova_page",
    "apps.api",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ─── MIDDLEWARE ───────────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "apps.accounts.middleware.HealthCheckMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.accounts.middleware.ProfilePrefetchMiddleware",
    "apps.accounts.middleware.RequirePhoneMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "django_htmx.middleware.HtmxMiddleware",
    "apps.accounts.middleware.OnboardingMiddleware",
    "apps.billing.middleware.PlanEnforcementMiddleware",
    "apps.partners.middleware.ReferralMiddleware",
    "apps.analytics.middleware.FeatureUsageMiddleware",
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
                "apps.products.context_processors.product_nav",
                "apps.billing.context_processors.plan_limit_notice",
                "apps.billing.context_processors.user_plan_sidebar",
                "apps.accounts.context_processors.nav_badges",
                "apps.accounts.context_processors.kova_voice",
                "apps.teams.context_processors.agency_theme",
                "apps.admin_dashboard.context_processors.admin_nav",
                "apps.media.context_processors.media_capabilities",
            ],
        },
    },
]

# ─── DATABASE ────────────────────────────────────────────────────────────────
DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://kova:kova@localhost:5432/kova_agent"),
}
# Reuse DB connections for 10 minutes (prevents connection exhaustion on Railway)
DATABASES["default"]["CONN_MAX_AGE"] = env.int("DB_CONN_MAX_AGE", default=600)
# Connection health checks to avoid stale connections from pool
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True

# ─── CACHE / REDIS ───────────────────────────────────────────────────────────
REDIS_URL = env("REDIS_URL", default="")

if REDIS_URL:
    _REDIS_CACHE_OPTIONS = {
        "socket_connect_timeout": env.float("REDIS_SOCKET_CONNECT_TIMEOUT", default=5.0),
        "socket_timeout": env.float("REDIS_SOCKET_TIMEOUT", default=5.0),
        "retry_on_timeout": True,
        "health_check_interval": 30,
    }
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.redis.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": _REDIS_CACHE_OPTIONS,
        }
    }
    SESSION_ENGINE = "django.contrib.sessions.backends.cached_db"
    SESSION_CACHE_ALIAS = "default"
    # Same REDIS_URL as Celery; channels_redis needs higher socket timeouts on Railway.
    _CHANNEL_REDIS_CONNECT_TIMEOUT = env.float("CHANNEL_REDIS_CONNECT_TIMEOUT", default=15.0)
    _CHANNEL_REDIS_SOCKET_TIMEOUT = env.float("CHANNEL_REDIS_SOCKET_TIMEOUT", default=15.0)
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": build_channels_redis_layer_config(
                REDIS_URL,
                socket_connect_timeout=_CHANNEL_REDIS_CONNECT_TIMEOUT,
                socket_timeout=_CHANNEL_REDIS_SOCKET_TIMEOUT,
            ),
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
    "recover-stuck-publishing-posts": {
        "task": "content.recover_stuck_publishing_posts",
        "schedule": 600.0,  # every 10 minutes — clear queue spinner after IG timeouts
    },
    "recover-stuck-media-generation": {
        "task": "content.recover_stuck_media_generation",
        "schedule": 600.0,  # every 10 minutes — mark stuck media gen as failed
    },
    "recover-stuck-reel-compose": {
        "task": "content.recover_stuck_reel_compose",
        "schedule": 600.0,  # every 10 minutes — re-queue stuck reel MP4 jobs
    },
    "fetch-all-recent-metrics": {
        "task": "content.fetch_all_recent_metrics",
        "schedule": 6 * 3600.0,  # every 6 hours
    },
    "refresh-expiring-tokens": {
        "task": "platforms.refresh_expiring_tokens",
        "schedule": 30 * 60.0,  # every 30 minutes
    },
    "warn-expiring-tokens": {
        "task": "platforms.warn_expiring_tokens",
        "schedule": 24 * 3600.0,  # daily — proactive 7-day and 1-day user warnings
    },
    "generate-daily-briefs": {
        "task": "briefs.generate_all_daily_briefs",
        "schedule": 15 * 60.0,  # every 15 minutes — checks which users' brief time has passed
    },
    "send-money-board-digests": {
        "task": "briefs.send_money_board_digests",
        "schedule": 24 * 3600.0,  # daily — opt-in money chase digest
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
    "calculate-partner-commissions": {
        "task": "partners.calculate_monthly_commissions",
        "schedule": 24 * 3600.0,  # daily — no-ops except when previous month not yet billed
    },
    "check-partner-milestones": {
        "task": "partners.check_partner_milestones",
        "schedule": 24 * 3600.0,  # daily — award milestone bonuses when thresholds hit
    },
    "measure-agent-outcomes": {
        "task": "agents.measure_agent_outcomes",
        "schedule": 12 * 3600.0,  # every 12 hours — score past agent actions against outcomes
    },
    "flush-pageview-buffer": {
        "task": "analytics.flush_pageview_buffer",
        "schedule": 30.0,  # every 30 seconds — drain analytics buffer
    },
    "expire-stale-commerce-payments": {
        "task": "products.expire_stale_commerce_payments",
        "schedule": 300.0,  # every 5 minutes — expire pending payments >10 min old
    },
    "check-stock-alerts": {
        "task": "check-stock-alerts",
        "schedule": 24 * 3600.0,  # daily — scan products for stock issues
    },
    "auto-promote-products": {
        "task": "products.auto_promote_products",
        "schedule": 24 * 3600.0,  # daily — random catalog sample (~30% of users/day)
    },
    "weekly-catalog-showcase": {
        "task": "products.weekly_catalog_showcase",
        "schedule": 24 * 3600.0,  # daily check — each user at most once per 7 days
    },
    "recycle-top-content": {
        "task": "content.recycle_top_content",
        "schedule": 24 * 3600.0,  # daily — repurpose high-performing old content
    },
    "detect-top-performers-email": {
        "task": "analytics.detect_top_performers",
        "schedule": 24 * 3600.0,  # daily — find top posts → generate email campaign drafts
    },
    # Adapt Agent v2 — the autonomous learning loop. Reads each user's
    # last 30 days of post performance and mutates their UserProfile to
    # bias future content toward winners. Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md.
    "run-adapt-cycle": {
        "task": "agents.run_adapt_cycle",
        "schedule": 12 * 3600.0,  # every 12h — match Engage / Strategist drum
    },
    "track-audience-growth": {
        "task": "agents.track_audience_growth",
        "schedule": 24 * 3600.0,  # daily — snapshot follower counts for growth intelligence
    },
    "check-trial-expiry-emails": {
        "task": "emails.check_trial_expiry_emails",
        "schedule": 24 * 3600.0,  # daily — send trial countdown emails (day 7, 3, 1, 0)
    },
    "send-weekly-reports": {
        "task": "emails.send_weekly_reports_all",
        "schedule": 7 * 24 * 3600.0,  # weekly — performance summary emails
    },
    "process-email-sequences": {
        "task": "emails.process_email_sequences",
        "schedule": 30 * 60.0,  # every 30 min — advance sequence enrollments
    },
    "sync-leads-to-subscribers": {
        "task": "emails.sync_leads_to_subscribers_all",
        "schedule": 24 * 3600.0,  # daily — backfill email subscribers from leads
    },
    "retry-pending-auto-campaigns": {
        "task": "emails.retry_pending_auto_campaigns",
        "schedule": 6 * 3600.0,  # every 6h — send AI drafts once lists have subscribers
    },
    "process-scheduled-email-campaigns": {
        "task": "emails.process_scheduled_campaigns",
        "schedule": 15 * 60.0,  # every 15 min — dispatch scheduled campaigns
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
    "whatsapp-followup-nudges": {
        "task": "whatsapp.send_followup_nudges",
        "schedule": 3600.0,  # hourly — 24h missed-reply follow-ups
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
    # Monthly attribution report emails
    "send-monthly-reports": {
        "task": "emails.send_monthly_reports_all",
        "schedule": 30 * 24 * 3600.0,  # monthly — full attribution report emails
    },
    # Lead nurture sequence processing
    "process-lead-nurture": {
        "task": "leads.process_nurture_steps",
        "schedule": 30 * 60.0,  # every 30 min — advance nurture enrollments
    },
    # Lead priority scoring
    "score-all-leads": {
        "task": "leads.score_all_leads",
        "schedule": 24 * 3600.0,  # daily — composite scoring, auto-enroll high-priority leads
    },
    "reengage-stale-leads": {
        "task": "leads.reengage_stale_leads",
        "schedule": 24 * 3600.0,  # daily — win-back enrollments for 7+ day inactive leads
    },
    # Educator agent — platform-level content authoring
    "educator-draft-weekly-article": {
        "task": "agents.educator_draft_weekly_article",
        "schedule": 7 * 24 * 3600.0,  # weekly — drafts one article from the topic backlog
    },
    "educator-compile-weekly-digest": {
        "task": "agents.educator_compile_weekly_digest",
        "schedule": 7 * 24 * 3600.0,  # weekly — assembles the Kova digest before Sunday send
    },
    "snapshot-pilot-metrics": {
        "task": "accounts.snapshot_pilot_metrics",
        "schedule": 24 * 3600.0,  # nightly — TEST_BUSINESSES pilot dashboard snapshot
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
ACCOUNT_ADAPTER = "apps.accounts.adapter.AsyncEmailAccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "phone_number*", "password1*", "password2*"]
ACCOUNT_SIGNUP_FORM_CLASS = "apps.accounts.forms.KovaSignupForm"
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_SIGNUP_REDIRECT_URL = "/accounts/onboarding/"
LOGIN_REDIRECT_URL = "/brief/"
LOGOUT_REDIRECT_URL = "/"
LOGIN_URL = "/accounts/login/"

SOCIALACCOUNT_ADAPTER = "apps.accounts.adapter.KovaSocialAccountAdapter"
SOCIALACCOUNT_AUTO_SIGNUP = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True

SOCIALACCOUNT_PROVIDERS = {}

if GOOGLE_OAUTH_ENABLED:
    SOCIALACCOUNT_PROVIDERS["google"] = {
        "APP": {
            "client_id": GOOGLE_OAUTH_CLIENT_ID,
            "secret": GOOGLE_OAUTH_CLIENT_SECRET,
            "key": "",
        },
        "SCOPE": ["profile", "email"],
        "AUTH_PARAMS": {"access_type": "online"},
    }

# Facebook Login — dual purpose: user identity + publishing auto-connect.
# Uses the same FACEBOOK_APP_ID/SECRET as the platform provider.
#
# Meta App Dashboard → Facebook Login for Business → Settings → Valid OAuth Redirect URIs:
#   {SITE_URL}/platforms/callback/facebook/   — signup, login, and platform connect (primary)
#   {SITE_URL}/platforms/callback/instagram/  — Instagram connect
#   {SITE_URL}/accounts/facebook/login/callback/ — legacy django-allauth (optional)
FACEBOOK_OAUTH_ENABLED = bool(FACEBOOK_APP_ID and FACEBOOK_APP_SECRET)
if FACEBOOK_OAUTH_ENABLED:
    SOCIALACCOUNT_PROVIDERS["facebook"] = {
        "APP": {
            "client_id": FACEBOOK_APP_ID,
            "secret": FACEBOOK_APP_SECRET,
            "key": "",
        },
        "METHOD": "oauth2",
        "SCOPE": [
            "email",
            "public_profile",
            "pages_manage_metadata",
            "pages_manage_posts",
            "pages_read_engagement",
            "instagram_content_publish",
            "instagram_manage_insights",
            "instagram_manage_comments",
        ],
        "FIELDS": ["id", "email", "name", "first_name", "last_name", "picture"],
        "AUTH_PARAMS": {"auth_type": "rerequest"},
        "EXCHANGE_TOKEN": True,
        "VERSION": "v25.0",
    }

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
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.CursorPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Kova Agent API",
    "DESCRIPTION": "REST API for Kova Agent — autonomous social media intelligence for African SMEs.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": r"/api/v1/",
    "TAGS": [
        {"name": "Platforms", "description": "Connected social accounts"},
        {"name": "Seeds", "description": "Content seed management"},
        {"name": "Posts", "description": "Post lifecycle management"},
        {"name": "Analytics", "description": "Performance metrics and attribution"},
        {"name": "Agents", "description": "AI agent configuration and actions"},
        {"name": "Products", "description": "Product catalog management"},
        {"name": "Conversions", "description": "Revenue attribution events"},
    ],
}

# ─── AI / LLM CONFIG ────────────────────────────────────────────────────────
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
GROQ_API_KEY = env("GROQ_API_KEY", default="")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
DEFAULT_LLM_PROVIDER = env("DEFAULT_LLM_PROVIDER", default="openai")  # openai | anthropic | openrouter
DEFAULT_LLM_MODEL = env("DEFAULT_LLM_MODEL", default="gpt-4o-mini")
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

# ─── CONTENT SAFETY (OpenRouter moderation) ─────────────────────────────────
CONTENT_SAFETY_ENABLED = env.bool("CONTENT_SAFETY_ENABLED", default=False)
CONTENT_SAFETY_MODEL = env(
    "CONTENT_SAFETY_MODEL",
    default="google/gemini-2.0-flash-001",
)
CONTENT_SAFETY_NOTIFY_EMAIL = env("CONTENT_SAFETY_NOTIFY_EMAIL", default="")
# Lenient sex-only defaults — raise threshold to tighten without code changes.
CONTENT_SAFETY_HIGH_SEVERITY_THRESHOLD = env.int(
    "CONTENT_SAFETY_HIGH_SEVERITY_THRESHOLD", default=85,
)
CONTENT_SAFETY_STRIKE_SUSPEND_THRESHOLD = env.int(
    "CONTENT_SAFETY_STRIKE_SUSPEND_THRESHOLD", default=3,
)
CONTENT_SAFETY_SNAP_BLOCK_HOURS = env.int("CONTENT_SAFETY_SNAP_BLOCK_HOURS", default=72)

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
    # Educator — long-form authoring + digest summarisation (platform-level).
    # Matches Create tier: articles and newsletters are customer-facing and land
    # on public pages / every user's inbox, so quality is worth the premium cost.
    # Volume is low (~3 calls/week) so budget impact is small.
    "educator.draft_article": env("LLM_MODEL_EDUCATOR_DRAFT", default=LLM_MODEL_PREMIUM),
    "educator.compile_digest": env("LLM_MODEL_EDUCATOR_DIGEST", default=LLM_MODEL_PREMIUM),
    "educator.suggest_topics": env("LLM_MODEL_EDUCATOR_TOPICS", default=LLM_MODEL_PREMIUM),
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

# Local product photo expansion (Photoroom Plus + Pillow promo frames)
PHOTO_VARIATIONS_ENABLED = env.bool("PHOTO_VARIATIONS_ENABLED", default=True)

# Studio polish (Photoroom Plus v2/edit) — see docs/VISUAL_ENHANCEMENT_SPEC.md
VISUAL_ENHANCE_ENABLED = env.bool("VISUAL_ENHANCE_ENABLED", default=True)
PHOTOROOM_API_KEY = env("PHOTOROOM_API_KEY", default="")
PHOTOROOM_MONTHLY_POOL = env.int("PHOTOROOM_MONTHLY_POOL", default=5000)
PHOTOROOM_POOL_RESERVE = env.int("PHOTOROOM_POOL_RESERVE", default=500)
PHOTOROOM_MONTHLY_COST_USD = env.float("PHOTOROOM_MONTHLY_COST_USD", default=500.0)
PHOTOROOM_OUTPUT_SIZE = env("PHOTOROOM_OUTPUT_SIZE", default="1080x1080")
PHOTOROOM_PADDING = env.float("PHOTOROOM_PADDING", default=0.06)
PHOTOROOM_DEFAULT_SHADOW = env("PHOTOROOM_DEFAULT_SHADOW", default="ai.preset-soft")
PHOTOROOM_SANDBOX = env.bool("PHOTOROOM_SANDBOX", default=False)
# Phase A/B — see docs/Photoroom upgrade.md
PHOTOROOM_PREFLIGHT_ENABLED = env.bool("PHOTOROOM_PREFLIGHT_ENABLED", default=True)
PHOTOROOM_PREFLIGHT_MAX_REPAIRS = env.int("PHOTOROOM_PREFLIGHT_MAX_REPAIRS", default=2)
PHOTOROOM_CHANNEL_EXPORTS_ENABLED = env.bool("PHOTOROOM_CHANNEL_EXPORTS_ENABLED", default=True)
PHOTOROOM_MARKETPLACE_EXPORT_ENABLED = env.bool("PHOTOROOM_MARKETPLACE_EXPORT_ENABLED", default=True)
PHOTOROOM_MARKETPLACE_SIZE = env("PHOTOROOM_MARKETPLACE_SIZE", default="1000x1000")
PHOTOROOM_MARKETPLACE_PADDING = env.float("PHOTOROOM_MARKETPLACE_PADDING", default=0.075)
PHOTOROOM_MARKET_DAY_ENABLED = env.bool("PHOTOROOM_MARKET_DAY_ENABLED", default=True)
PHOTOROOM_RELIGHT_PRODUCT_MODE = env(
    "PHOTOROOM_RELIGHT_PRODUCT_MODE", default="ai.preserve-hue-and-saturation",
)
PHOTOROOM_STORY_SIZE = env("PHOTOROOM_STORY_SIZE", default="1080x1920")
PHOTOROOM_BANNER_SIZE = env("PHOTOROOM_BANNER_SIZE", default="1920x1080")
PHOTOROOM_SLIDE_ROLES_ENABLED = env.bool("PHOTOROOM_SLIDE_ROLES_ENABLED", default=True)
PHOTOROOM_CREATIVE_SCENES_ENABLED = env.bool(
    "PHOTOROOM_CREATIVE_SCENES_ENABLED", default=True,
)  # Commerce-first grounded AI scenes (table, shelf, wall, retail)
PHOTOROOM_BRAND_TEMPLATE_ENABLED = env.bool("PHOTOROOM_BRAND_TEMPLATE_ENABLED", default=True)
PHOTOROOM_MIN_SCENE_VARIANTS = env.int("PHOTOROOM_MIN_SCENE_VARIANTS", default=3)
PHOTOROOM_MIN_AI_SCENES = env.int("PHOTOROOM_MIN_AI_SCENES", default=2)
PHOTOROOM_MAX_AI_SCENES = env.int("PHOTOROOM_MAX_AI_SCENES", default=3)
PHOTOROOM_VARIANT_LAYOUTS_ENABLED = env.bool("PHOTOROOM_VARIANT_LAYOUTS_ENABLED", default=True)
# Edit With AI — lifestyle staging + angle variations (docs.photoroom.com Edit With AI)
PHOTOROOM_EDIT_WITH_AI_ENABLED = env.bool("PHOTOROOM_EDIT_WITH_AI_ENABLED", default=True)
PHOTOROOM_EDIT_WITH_AI_MAX_PER_PACK = env.int("PHOTOROOM_EDIT_WITH_AI_MAX_PER_PACK", default=2)

# Motion reel director — recipe rotation, 5 slides, role-based motion (apps/content/reel_director.py)
REEL_MAX_SLIDES = env.int("REEL_MAX_SLIDES", default=5)
REEL_DIRECTOR_ENABLED = env.bool("REEL_DIRECTOR_ENABLED", default=True)
# Phase 2 — PhotoFix, Composition, Video (see docs.photoroom.com)
PHOTOROOM_PHOTOFIX_ENABLED = env.bool("PHOTOROOM_PHOTOFIX_ENABLED", default=True)
PHOTOROOM_PHOTOFIX_ALWAYS = env.bool("PHOTOROOM_PHOTOFIX_ALWAYS", default=False)
PHOTOROOM_COMPOSITION_ENABLED = env.bool("PHOTOROOM_COMPOSITION_ENABLED", default=True)
PHOTOROOM_VIDEO_ENABLED = env.bool("PHOTOROOM_VIDEO_ENABLED", default=False)
PHOTOROOM_REEL_USE_VIDEO_API = env.bool("PHOTOROOM_REEL_USE_VIDEO_API", default=True)
PHOTOROOM_VIRTUAL_MODEL_ENABLED = env.bool("PHOTOROOM_VIRTUAL_MODEL_ENABLED", default=False)
# Doc-aligned v2/edit behaviour (uncertainty, smart crop, sandbox caps)
PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD = env.float("PHOTOROOM_UNCERTAINTY_HIGH_THRESHOLD", default=0.6)
PHOTOROOM_UNCERTAINTY_PROBE_ENABLED = env.bool("PHOTOROOM_UNCERTAINTY_PROBE_ENABLED", default=True)
PHOTOROOM_SANDBOX_DAILY_LIMIT = env.int("PHOTOROOM_SANDBOX_DAILY_LIMIT", default=100)
PHOTOROOM_SANDBOX_MONTHLY_LIMIT = env.int("PHOTOROOM_SANDBOX_MONTHLY_LIMIT", default=1000)
PHOTOROOM_SMART_CROP_PADDING = env("PHOTOROOM_SMART_CROP_PADDING", default="10%")
PHOTOROOM_SCALING = env("PHOTOROOM_SCALING", default="fill")  # fit | fill
PHOTOROOM_EXPAND_MAX_WORKERS = env.int("PHOTOROOM_EXPAND_MAX_WORKERS", default=2)
PHOTOROOM_DEFAULT_BLUR_MODE = env("PHOTOROOM_DEFAULT_BLUR_MODE", default="bokeh")  # bokeh | gaussian
PHOTOROOM_DEFAULT_BLUR_RADIUS = env.float("PHOTOROOM_DEFAULT_BLUR_RADIUS", default=0.01)
# Phase 2 — Basic cutout routing, food preset, apparel review, shadow model
PHOTOROOM_BASIC_API_KEY = env("PHOTOROOM_BASIC_API_KEY", default="")
PHOTOROOM_BASIC_ROUTING_ENABLED = env.bool("PHOTOROOM_BASIC_ROUTING_ENABLED", default=True)
PHOTOROOM_REVIEW_ALTERATIONS = env.bool("PHOTOROOM_REVIEW_ALTERATIONS", default=True)
PHOTOROOM_AI_SHADOWS_MODEL_ENABLED = env.bool("PHOTOROOM_AI_SHADOWS_MODEL_ENABLED", default=True)
BEAUTIFY_SEED_DEFAULT = 117879368
EDIT_WITH_AI_SEED_DEFAULT = 2016886668

# Phase 5: Platform engagement expansion
ENGAGE_DM_INBOX_ENABLED = env.bool("ENGAGE_DM_INBOX_ENABLED", default=True)
TIKTOK_RESEARCH_API_ENABLED = env.bool("TIKTOK_RESEARCH_API_ENABLED", default=False)

# Legacy — also used by media orchestration (Fal.ai Flux + Kling)
FAL_KEY = env("FAL_KEY", default="")
FAL_API_KEY = env("FAL_API_KEY", default="")  # preferred alias
FAL_KLING_MODEL = env(
    "FAL_KLING_MODEL",
    default="fal-ai/kling-video/v2.1/master/image-to-video",
)
FAL_FLUX_EDIT_MODEL = env("FAL_FLUX_EDIT_MODEL", default="fal-ai/flux-pro/kontext")

# Bannerbear — branded carousel templates
BANNERBEAR_API_KEY = env("BANNERBEAR_API_KEY", default="")
BANNERBEAR_TEMPLATES = {
    "product_carousel_cover": env("BANNERBEAR_TEMPLATE_COVER", default=""),
    "product_carousel_slide": env("BANNERBEAR_TEMPLATE_SLIDE", default=""),
    "product_carousel_cta": env("BANNERBEAR_TEMPLATE_CTA", default=""),
}

# Media orchestration master switch
MEDIA_ORCHESTRATION_ENABLED = env.bool("MEDIA_ORCHESTRATION_ENABLED", default=True)

HF_TOKEN = env("HF_TOKEN", default="")                        # https://huggingface.co/settings/tokens — FLUX.1-schnell (free)
TOGETHER_API_KEY = env("TOGETHER_API_KEY", default="")        # https://api.together.xyz — sign up, add $5 credit
TOGETHER_IMAGE_MODEL = env("TOGETHER_IMAGE_MODEL", default="black-forest-labs/FLUX.1-schnell")  # $0.003/image
POLLINATIONS_API_KEY = env("POLLINATIONS_API_KEY", default="") # https://pollinations.ai — Flux Schnell
AI_IMAGE_MODEL = env("AI_IMAGE_MODEL", default="flux")        # Pollinations model: flux | gptimage | zimage

# ─── WEB SEARCH (Tavily — real-time trend data for Research Agent) ───────────
# Free tier: 1000 searches/month — sign up at https://tavily.com
# When configured, Research Agent uses real web data instead of LLM hallucinations.
TAVILY_API_KEY = env("TAVILY_API_KEY", default="")

# ─── STRIPE (kept for future international billing) ─────────────────────────
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_PRICE_STARTER = env("STRIPE_PRICE_STARTER", default="")  # KES 499/mo — 7-day trial
STRIPE_PRICE_GROWTH = env("STRIPE_PRICE_GROWTH", default="")
STRIPE_PRICE_PRO = env("STRIPE_PRICE_PRO", default="")
STRIPE_PRICE_AGENCY = env("STRIPE_PRICE_AGENCY", default="")

# ─── M-PESA (Daraja API — primary payment for Kenya) ────────────────────────
MPESA_ENVIRONMENT = env("MPESA_ENVIRONMENT", default="sandbox")  # sandbox | production
MPESA_CONSUMER_KEY = env("MPESA_CONSUMER_KEY", default="")
MPESA_CONSUMER_SECRET = env("MPESA_CONSUMER_SECRET", default="")
MPESA_SHORTCODE = env("MPESA_SHORTCODE", default="174379")       # Sandbox default
MPESA_PASSKEY = env("MPESA_PASSKEY", default="")
MPESA_CALLBACK_URL = env("MPESA_CALLBACK_URL", default="")       # e.g. https://yourdomain.com/billing/webhook/mpesa/
MPESA_COMMERCE_CALLBACK_URL = env("MPESA_COMMERCE_CALLBACK_URL", default="")  # e.g. https://yourdomain.com/analytics/webhooks/mpesa/commerce/
MPESA_WEBHOOK_SECRET = env("MPESA_WEBHOOK_SECRET", default="")   # Optional: append ?token=<secret> to callback URL
MPESA_TRIAL_DAYS = env.int("MPESA_TRIAL_DAYS", default=7)

# ─── SOCIAL PLATFORM OAUTH ───────────────────────────────────────────────────
TWITTER_CLIENT_ID = env("TWITTER_CLIENT_ID", default="")
TWITTER_CLIENT_SECRET = env("TWITTER_CLIENT_SECRET", default="")
LINKEDIN_CLIENT_ID = env("LINKEDIN_CLIENT_ID", default="")
LINKEDIN_CLIENT_SECRET = env("LINKEDIN_CLIENT_SECRET", default="")
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
WHATSAPP_VERIFY_TOKEN = env("WHATSAPP_VERIFY_TOKEN", default="")
WHATSAPP_APP_SECRET = env("WHATSAPP_APP_SECRET", default="")            # For webhook signature validation
FB_WA_CONFIG_ID = env("FB_WA_CONFIG_ID", default="")                    # Facebook Login for Business config ID (Embedded Signup)

# Engage Agent v2 — graduated autonomy rollout flag.
#
# Default False so a code-only deploy doesn't surprise prod by auto-sending
# replies. Flip to True (per user or globally) when the W2 work has been
# observed safe on internal test accounts (Kawaida / Nyama / Mara).
#
# Spec: docs/specs/ENGAGE_AGENT_V2_SPEC.md
#
# Even when this is False, the new routing layer is still exercised — every
# AI reply runs through `engage_routing.route_reply()` and gets confidence,
# intent, and safety_flags persisted on the Interaction. The only thing
# this flag gates is whether AUTO_SEND decisions actually post to platforms
# vs. fall back to DRAFT_FOR_REVIEW.
ENGAGE_GRADUATED_AUTONOMY_ENABLED = env.bool("ENGAGE_GRADUATED_AUTONOMY_ENABLED", default=False)

# Adapt Agent v2 — learning loop rollout flag.
#
# Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md
#
# Default False so the new loop runs in DRY-RUN MODE for a week before
# any user profile actually changes. In dry-run, the agent still computes
# what mutations it WOULD make and writes them to AgentAction with
# action_status="dry_run" — but UserProfile is untouched. Lets us audit
# the threshold calibration on real data before flipping.
#
# Kill switch for Adapt v2 mutations. Defaults to True — the per-plan gate
# in PLAN_LIMITS["adapt_v2_enabled"] controls which tiers actually mutate.
# Set to False in env to force dry-run for ALL users (emergency brake).
ADAPT_AGENT_V2_ENABLED = env.bool("ADAPT_AGENT_V2_ENABLED", default=True)

# Onboarding completion ping — fires from agents.onboarding_tasks once the
# "agency first meeting" task chain finishes. Requires an approved Meta
# template; leave empty to disable (graceful no-op).
#
# Template body suggestion (1 variable for first_name):
#   "Karibu {{1}}! Your AI agency just finished setting up. Tap to see your
#   first posts → kova.ai/studio"
KOVA_ONBOARDING_TEMPLATE_NAME = env("KOVA_ONBOARDING_TEMPLATE_NAME", default="")
KOVA_ONBOARDING_TEMPLATE_LANG = env("KOVA_ONBOARDING_TEMPLATE_LANG", default="en")

# Daily brief WhatsApp ping — fires after each DailyBrief is generated (Pro+).
# Template: body (3 vars) + URL button index 0 + Quick reply "Approve" + "Score"
# See docs/DAILY_BRIEF_WHATSAPP_SETUP.md
KOVA_DAILY_BRIEF_TEMPLATE_NAME = env("KOVA_DAILY_BRIEF_TEMPLATE_NAME", default="")
KOVA_DAILY_BRIEF_TEMPLATE_LANG = env("KOVA_DAILY_BRIEF_TEMPLATE_LANG", default="en")
# Dynamic URL suffix for template button 0 (template URL: https://domain/brief/{{1}}).
# Set empty string if your template uses a fully static URL with no variable.
KOVA_DAILY_BRIEF_URL_SUFFIX = env("KOVA_DAILY_BRIEF_URL_SUFFIX", default="utm_source=whatsapp")

STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# ─── SITE URL ────────────────────────────────────────────────────────────────
SITE_URL = env("SITE_URL", default="http://localhost:8000")

# ─── SHOPIFY INTEGRATION ─────────────────────────────────────────────────────
SHOPIFY_API_KEY = env("SHOPIFY_API_KEY", default="")
SHOPIFY_API_SECRET = env("SHOPIFY_API_SECRET", default="")
SHOPIFY_SCOPES = env(
    "SHOPIFY_SCOPES",
    default="read_products,write_products,read_orders,read_inventory",
)

# ─── EMAIL ───────────────────────────────────────────────────────────────────
# Default: console backend for dev. Production uses Resend SMTP.
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Kova Agent <noreply@kovaagent.com>")
RESEND_API_KEY = env("RESEND_API_KEY", default="")
RESEND_WEBHOOK_SECRET = env("RESEND_WEBHOOK_SECRET", default="")
