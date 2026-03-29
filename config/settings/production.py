"""
Production settings for Kova Agent.
Deployed on Railway.
"""

from .base import *  # noqa: F401, F403

# ─── ENFORCE SECRET_KEY ──────────────────────────────────────────────────────
if SECRET_KEY == "INSECURE-dev-key-change-me-in-production":  # noqa: F405
    import warnings
    warnings.warn(
        "SECRET_KEY is using the insecure default! Set SECRET_KEY in Railway environment variables.",
        stacklevel=1,
    )

# ─── SECURITY ────────────────────────────────────────────────────────────────
DEBUG = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"

# ─── ALLOWED HOSTS & CSRF ───────────────────────────────────────────────────
# Allow all Railway subdomains (*.railway.app)
ALLOWED_HOSTS += [".railway.app"]  # noqa: F405
CSRF_TRUSTED_ORIGINS += ["https://*.railway.app"]  # noqa: F405

# Optional: custom domain (set CUSTOM_DOMAIN in Railway env vars)
CUSTOM_DOMAIN = env("CUSTOM_DOMAIN", default="")  # noqa: F405
if CUSTOM_DOMAIN:
    ALLOWED_HOSTS.append(CUSTOM_DOMAIN)  # noqa: F405
    CSRF_TRUSTED_ORIGINS.append(f"https://{CUSTOM_DOMAIN}")  # noqa: F405

# ─── STATIC FILES (WhiteNoise) ──────────────────────────────────────────────
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

# ─── DATABASE ────────────────────────────────────────────────────────────────
# Railway provides DATABASE_URL automatically when you add a Postgres plugin.
# django-environ parses it from base.py. Add connection health settings:
DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# ─── CELERY ──────────────────────────────────────────────────────────────────
# Railway Redis: use REDIS_URL from env (base.py reads it already).
# No changes needed unless you want a separate broker URL.

# ─── EMAIL ───────────────────────────────────────────────────────────────────
EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")  # noqa: F405

# Disable email verification until a real email provider is configured
ACCOUNT_EMAIL_VERIFICATION = "none"

# ─── LOGGING ─────────────────────────────────────────────────────────────────
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
    },
}

# ─── SENTRY ──────────────────────────────────────────────────────────────────
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    try:
        import sentry_sdk
        sentry_sdk.init(
            dsn=SENTRY_DSN,
            traces_sample_rate=0.1,
            profiles_sample_rate=0.1,
        )
    except ImportError:
        pass

# ─── ALLAUTH ─────────────────────────────────────────────────────────────────
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
