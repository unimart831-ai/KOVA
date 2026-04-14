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
# django-csp: Restrict what the browser can load to prevent XSS/injection.
CSP_DEFAULT_SRC = ("'self'",)
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'", "'unsafe-eval'", "https://unpkg.com", "https://cdn.jsdelivr.net", "https://js.stripe.com")
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'", "https://cdn.jsdelivr.net", "https://fonts.googleapis.com")
CSP_IMG_SRC = ("'self'", "data:", "https:", "blob:")  # Allow platform avatars, media
CSP_FONT_SRC = ("'self'", "https://fonts.gstatic.com", "https://cdn.jsdelivr.net")
CSP_CONNECT_SRC = ("'self'", "https://api.stripe.com")
CSP_FRAME_SRC = ("'self'", "https://js.stripe.com")   # Stripe checkout iframe
CSP_OBJECT_SRC = ("'none'",)
CSP_BASE_URI = ("'self'",)
CSP_FORM_ACTION = ("'self'",)

# ─── DATABASE ────────────────────────────────────────────────────────────────
# Railway provides DATABASE_URL automatically when you add a Postgres plugin.
# django-environ parses it from base.py. Add connection health settings:
DATABASES["default"]["CONN_MAX_AGE"] = 600  # noqa: F405
DATABASES["default"]["CONN_HEALTH_CHECKS"] = True  # noqa: F405

# ─── CELERY ──────────────────────────────────────────────────────────────────
# Railway Redis: use REDIS_URL from env (base.py reads it already).
# No changes needed unless you want a separate broker URL.

# ─── EMAIL (Resend SMTP) ─────────────────────────────────────────────────────
# Resend provides SMTP relay: smtp.resend.com:465 (TLS)
# Set RESEND_API_KEY in Railway env vars to enable.
RESEND_API_KEY = env("RESEND_API_KEY", default="")  # noqa: F405
if RESEND_API_KEY:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = "smtp.resend.com"
    EMAIL_PORT = 465
    EMAIL_USE_SSL = True
    EMAIL_HOST_USER = "resend"
    EMAIL_HOST_PASSWORD = RESEND_API_KEY
else:
    # Silently discard emails rather than dumping HTML to stderr logs.
    # Set RESEND_API_KEY in Railway env vars to enable real delivery.
    EMAIL_BACKEND = "django.core.mail.backends.filebased.EmailBackend"
    EMAIL_FILE_PATH = "/tmp/kova-emails"
    import logging as _logging
    _logging.getLogger(__name__).warning(
        "RESEND_API_KEY not set — emails will be written to %s instead of sent",
        EMAIL_FILE_PATH,
    )

# Enable email verification once Resend is configured
ACCOUNT_EMAIL_VERIFICATION = "optional" if RESEND_API_KEY else "none"

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
SENTRY_DSN = env("SENTRY_DSN", default="")  # noqa: F405
if SENTRY_DSN:
    try:
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
                    level=None,        # Capture nothing from logging by default
                    event_level="ERROR",  # Send ERROR+ as Sentry events
                ),
            ],
            # Performance monitoring
            traces_sample_rate=0.1,   # 10% of requests
            profiles_sample_rate=0.1, # 10% of profiled transactions
            # Release tracking — set RAILWAY_GIT_COMMIT_SHA in Railway env
            release=env("RAILWAY_GIT_COMMIT_SHA", default=None),  # noqa: F405
            environment="production",
            # PII
            send_default_pii=False,
            # Don't capture health checks
            before_send_transaction=lambda event, hint: (
                None if event.get("transaction") == "/health/" else event
            ),
        )
    except ImportError:
        pass

