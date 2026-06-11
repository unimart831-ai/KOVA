"""
Production settings for Kova Agent.
Deployed on Railway.
"""

from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403

# ─── ENFORCE PRODUCTION SECRETS ──────────────────────────────────────────────
# Refuse to boot in production if any of these are missing or set to a known
# insecure default. Failing loudly here is far better than silently shipping
# a broken trust boundary — these are the keys that protect every user's
# session and every encrypted OAuth token.
if SECRET_KEY.startswith("django-insecure") or SECRET_KEY == "INSECURE-dev-key-change-me-in-production":  # noqa: F405
    raise ImproperlyConfigured(
        "SECRET_KEY is set to the insecure default in production. "
        "Set SECRET_KEY in Railway environment variables to a strong random value."
    )

# FIELD_ENCRYPTION_KEY must be a dedicated key — falling back to SECRET_KEY
# means a session-secret leak would also expose every stored OAuth token.
if not env("FIELD_ENCRYPTION_KEY", default=""):  # noqa: F405
    raise ImproperlyConfigured(
        "FIELD_ENCRYPTION_KEY must be set in production (separate from SECRET_KEY). "
        "Generate one with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    )

# ─── SECURITY ────────────────────────────────────────────────────────────────
DEBUG = False
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# Lax is the right default for SaaS: protects against CSRF on cross-site
# top-level POST requests while still allowing normal navigation flows
# (e.g. clicking an email link to land in an authenticated session).
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SESSION_COOKIE_AGE = 60 * 60 * 24 * 30  # 30 days
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True

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
MIDDLEWARE.append("csp.middleware.CSPMiddleware")  # noqa: F405

# ─── MEDIA STORAGE (Cloudflare R2 / S3-compatible) ──────────────────────────
# R2 is S3-compatible with free egress. Set these env vars on Railway:
#   AWS_STORAGE_BUCKET_NAME, AWS_S3_ENDPOINT_URL,
#   AWS_S3_ACCESS_KEY_ID, AWS_S3_SECRET_ACCESS_KEY
_R2_BUCKET = env("AWS_STORAGE_BUCKET_NAME", default="")  # noqa: F405
if _R2_BUCKET:
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "addressing_style": "path",  # R2 requires path-style addressing
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
    AWS_STORAGE_BUCKET_NAME = _R2_BUCKET
    AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="")  # noqa: F405
    AWS_S3_ACCESS_KEY_ID = env("AWS_S3_ACCESS_KEY_ID", default="")  # noqa: F405
    AWS_S3_SECRET_ACCESS_KEY = env("AWS_S3_SECRET_ACCESS_KEY", default="")  # noqa: F405
    AWS_S3_REGION_NAME = "auto"
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_DEFAULT_ACL = None
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}
    AWS_QUERYSTRING_AUTH = False  # Public URLs for media (images served to platforms)
    AWS_LOCATION = "media"  # All uploads go under media/ prefix in the bucket
    # If custom domain set for R2 bucket (optional)
    _R2_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")  # noqa: F405
    if _R2_CUSTOM_DOMAIN:
        AWS_S3_CUSTOM_DOMAIN = _R2_CUSTOM_DOMAIN
        MEDIA_URL = f"https://{_R2_CUSTOM_DOMAIN}/media/"
    else:
        MEDIA_URL = f"{AWS_S3_ENDPOINT_URL}/{_R2_BUCKET}/media/"
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }

# ─── CONTENT SECURITY POLICY ────────────────────────────────────────────────
# django-csp with nonce-based inline script allowlisting.
# CSP_INCLUDE_NONCE_IN adds a per-request nonce to the CSP header and makes
# request.csp_nonce available in templates. Inline <script> tags must include
# nonce="{{ request.csp_nonce }}" to execute (see templates/base.html).
# Full removal of 'unsafe-inline' for style-src is DEFERRED — Alpine/HTMX and
# Tailwind utility classes rely on inline styles; audit before tightening.
# See docs/CSP.md for migration notes.
CSP_DEFAULT_SRC = ("'self'",)
CSP_INCLUDE_NONCE_IN = ["script-src"]
CSP_SCRIPT_SRC = ("'self'", "https://unpkg.com", "https://cdn.jsdelivr.net", "https://js.stripe.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com")
CSP_IMG_SRC = ("'self'", "data:", "https:", "blob:")
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com", "https://cdn.jsdelivr.net")
# wss: required for /ws/updates/ real-time (Engage, token warnings). Full nonce-based
# style-src removal deferred — Alpine/HTMX inline styles would break without audit.
CSP_CONNECT_SRC = ("'self'", "https://api.stripe.com", "wss:")
CSP_FRAME_SRC = ("'self'", "https://js.stripe.com")
CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)

# ─── DATABASE ────────────────────────────────────────────────────────────────
# Railway provides DATABASE_URL automatically when you add a Postgres plugin.
# django-environ parses it from base.py. Add connection health settings:
DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# ─── REDIS / CHANNELS (WebSockets) ───────────────────────────────────────────
# Celery, Django cache, and Channels all use REDIS_URL from base.py.
# WebSocket /ws/updates/ uses channels_redis (async); Celery uses sync redis —
# if Celery works but WS fails with "Timeout reading from redis.railway.internal",
# raise CHANNEL_REDIS_* timeouts (defaults 15s) or verify Redis is not sleeping.
# Optional overrides: CHANNEL_REDIS_CONNECT_TIMEOUT, CHANNEL_REDIS_SOCKET_TIMEOUT

# ─── EMAIL (Resend HTTP API via django-anymail) ──────────────────────────────
# Resend is the source of truth for transactional email in production. The
# previous filebased fallback to /tmp on Railway silently lost every email
# (ephemeral filesystem) including trial-expiry warnings and password resets.
# Refuse to boot without it so the failure is visible at deploy time.
RESEND_API_KEY = env("RESEND_API_KEY", default="")  # noqa: F405
if not RESEND_API_KEY:
    raise ImproperlyConfigured(
        "RESEND_API_KEY must be set in production. "
        "Without it, password resets and trial emails would be silently dropped."
    )

# Webhook signature secrets — unsigned callbacks rejected at the view layer when unset.
RESEND_WEBHOOK_SECRET = env("RESEND_WEBHOOK_SECRET", default="")  # noqa: F405
WHATSAPP_APP_SECRET = env("WHATSAPP_APP_SECRET", default="")  # noqa: F405
MPESA_WEBHOOK_SECRET = env("MPESA_WEBHOOK_SECRET", default="")  # noqa: F405
INSTALLED_APPS += ["anymail"]  # noqa: F405
EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
ANYMAIL = {
    "RESEND_API_KEY": RESEND_API_KEY,
}

# Email verification is non-negotiable in production — gates trial abuse and
# guarantees we have a deliverable address before billing the user.
ACCOUNT_EMAIL_VERIFICATION = "mandatory"

# ─── LOGGING ─────────────────────────────────────────────────────────────────
import logging as _logging
import re as _re


class _TokenRedactFilter(_logging.Filter):
    """Strip access_token, api_key, and secret values from all log records."""

    _PATTERNS = [
        _re.compile(r"(access_token=)[^\s&\"']+", _re.IGNORECASE),
        _re.compile(r"(api_key=)[^\s&\"']+", _re.IGNORECASE),
        _re.compile(r"(token=)[^\s&\"']+", _re.IGNORECASE),
    ]

    def filter(self, record):
        if record.args:
            record.msg, record.args = self._redact_msg(record.msg, record.args)
        else:
            if isinstance(record.msg, str):
                for pat in self._PATTERNS:
                    record.msg = pat.sub(r"\1[REDACTED]", record.msg)
        return True

    def _redact_msg(self, msg, args):
        try:
            formatted = msg % args if args else msg
        except (TypeError, ValueError):
            formatted = str(msg)
        for pat in self._PATTERNS:
            formatted = pat.sub(r"\1[REDACTED]", formatted)
        return formatted, None


LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_tokens": {
            "()": "config.settings.production._TokenRedactFilter",
        },
    },
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
            "filters": ["redact_tokens"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {"handlers": ["console"], "level": "INFO", "propagate": False},
        "apps": {"handlers": ["console"], "level": "INFO", "propagate": False},
        # Suppress noisy httpx request logging that dumps full URLs with tokens
        "httpx": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "httpcore": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# ─── SENTRY ──────────────────────────────────────────────────────────────────
# Mandatory in production — same fail-fast pattern as RESEND_API_KEY. Shipping
# without error tracking means payment, publish, and webhook failures go unseen.
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if not SENTRY_DSN:
    raise ImproperlyConfigured(
        "SENTRY_DSN must be set in production. "
        "Without it, exceptions in billing, publishing, and webhooks go unreported. "
        "Create a project at https://sentry.io and set SENTRY_DSN in Railway."
    )

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration

sentry_sdk.init(
    dsn=SENTRY_DSN,
    integrations=[
        DjangoIntegration(
            transaction_style="url",
            middleware_spans=True,
        ),
        CeleryIntegration(monitor_beat_tasks=True),
        LoggingIntegration(
            level=None,
            event_level="ERROR",
        ),
    ],
    traces_sample_rate=0.1,
    profiles_sample_rate=0.1,
    release=env("RAILWAY_GIT_COMMIT_SHA", default=None),  # noqa: F405
    environment="production",
    send_default_pii=False,
    before_send_transaction=lambda event, hint: (
        None if event.get("transaction") == "/health/" else event
    ),
)

# ─── CONTENT SAFETY ──────────────────────────────────────────────────────────
CONTENT_SAFETY_ENABLED = env.bool("CONTENT_SAFETY_ENABLED", default=True)  # noqa: F405

