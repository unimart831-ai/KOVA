"""Django system checks for production readiness."""

from django.conf import settings
from django.core.checks import Warning, register


@register(deploy=True)
def sentry_dsn_deploy_check(app_configs, **kwargs):
    """Flag missing Sentry in deploy checks (CI + manual pre-release). Does not block boot."""
    if getattr(settings, "DEBUG", True):
        return []
    if getattr(settings, "SENTRY_DSN", ""):
        return []
    return [
        Warning(
            "SENTRY_DSN is not set. Production will run without error tracking. "
            "Create a project at https://sentry.io and set SENTRY_DSN in Railway.",
            id="kova.W001",
        )
    ]
