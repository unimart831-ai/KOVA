"""
Development settings for Kova Agent.
"""

from .base import *  # noqa: F401, F403

# ─── DEBUG ───────────────────────────────────────────────────────────────────
DEBUG = True
ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "testserver"]

# ─── DEV APPS ────────────────────────────────────────────────────────────────
INSTALLED_APPS += [  # noqa: F405
    # "debug_toolbar",  # Disabled: doesn't work well with Daphne ASGI
    "django_browser_reload",
]

# ─── DEV MIDDLEWARE ──────────────────────────────────────────────────────────
MIDDLEWARE += [  # noqa: F405
    # "debug_toolbar.middleware.DebugToolbarMiddleware",
    "django_browser_reload.middleware.BrowserReloadMiddleware",
]

INTERNAL_IPS = ["127.0.0.1"]

# ─── EMAIL (print to console in dev) ────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# ─── STATIC ──────────────────────────────────────────────────────────────────
# In dev, Django serves static files directly. No whitenoise needed.

# ─── ALLAUTH (relax email verification in dev) ──────────────────────────────
ACCOUNT_EMAIL_VERIFICATION = "none"

# ─── DATABASE (SQLite for local dev without Docker) ─────────────────────────
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}

# ─── CACHE (in-memory for local dev without Redis) ──────────────────────────
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}

# ─── CHANNELS (in-memory for local dev without Redis) ───────────────────────
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels.layers.InMemoryChannelLayer",
    }
}

# ─── CELERY ───────────────────────────────────────────────────────────────────
# Local SQLite stack usually has REDIS_URL in .env but Redis may not be running.
# Default: no broker → fire_task() uses daemon threads (never blocks onboarding).
# Opt in to a real broker with CELERY_USE_REDIS=1 (Redis must be up on REDIS_URL).
if env.bool("CELERY_USE_REDIS", default=False):  # noqa: F405
    CELERY_TASK_ALWAYS_EAGER = False
else:
    CELERY_BROKER_URL = ""
    CELERY_RESULT_BACKEND = ""
    CELERY_TASK_ALWAYS_EAGER = False
CELERY_TASK_EAGER_PROPAGATES = True

# ─── LOGGING (INFO in dev — DEBUG floods I/O and slows every request) ────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{levelname}] {asctime} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}
