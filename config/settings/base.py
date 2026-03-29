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
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BEAT_SCHEDULE = {
    "check-and-publish-due-posts": {
        "task": "content.check_and_publish_due_posts",
        "schedule": 60.0,  # every 60 seconds
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
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

# ─── AI / LLM CONFIG ────────────────────────────────────────────────────────
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
ANTHROPIC_API_KEY = env("ANTHROPIC_API_KEY", default="")
OPENROUTER_API_KEY = env("OPENROUTER_API_KEY", default="")
DEFAULT_LLM_PROVIDER = env("DEFAULT_LLM_PROVIDER", default="openai")  # openai | anthropic | openrouter
DEFAULT_LLM_MODEL = env("DEFAULT_LLM_MODEL", default="gpt-4o-mini")

# ─── STRIPE ──────────────────────────────────────────────────────────────────
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")

# ─── SOCIAL PLATFORM OAUTH ───────────────────────────────────────────────────
TWITTER_CLIENT_ID = env("TWITTER_CLIENT_ID", default="")
TWITTER_CLIENT_SECRET = env("TWITTER_CLIENT_SECRET", default="")
LINKEDIN_CLIENT_ID = env("LINKEDIN_CLIENT_ID", default="")
LINKEDIN_CLIENT_SECRET = env("LINKEDIN_CLIENT_SECRET", default="")
FACEBOOK_APP_ID = env("FACEBOOK_APP_ID", default="")
FACEBOOK_APP_SECRET = env("FACEBOOK_APP_SECRET", default="")
TIKTOK_CLIENT_KEY = env("TIKTOK_CLIENT_KEY", default="")
TIKTOK_CLIENT_SECRET = env("TIKTOK_CLIENT_SECRET", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")

# ─── EMAIL ───────────────────────────────────────────────────────────────────
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="Kova Agent <noreply@kovaagent.com>")
