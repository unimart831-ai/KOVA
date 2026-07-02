import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AgentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agents"
    verbose_name = "AI Agents"

    def ready(self):
        import sys

        # Defer DB queries until the first real request/task — never during
        # Django startup, schema management, or ASGI/WSGI server boot.
        # Django raises RuntimeWarning if any ORM call happens here (D5+ check).
        _SKIP_COMMANDS = {
            "migrate", "makemigrations", "flush", "test",
            "collectstatic", "createsuperuser", "shell", "check",
            "showmigrations", "loaddata",
        }
        # argv[0] is manage.py OR a WSGI/ASGI server binary (daphne, uvicorn,
        # gunicorn). When the server boots, argv[1] may not exist at all.
        _cmd = sys.argv[1] if len(sys.argv) > 1 else ""
        if _cmd in _SKIP_COMMANDS or not _cmd:
            return
        # Only run the OpenRouter key validation for explicit management commands
        # that need it (e.g. pilot_smoke). Never during server startup.
        # The LLMConfig is loaded lazily on first generate() call instead.
        from django.conf import settings

        openrouter_key = (getattr(settings, "OPENROUTER_API_KEY", "") or "").strip()
        default_provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "openai")

        uses_openrouter = default_provider == "openrouter" or bool(openrouter_key)
        if not uses_openrouter:
            return

        from apps.agents.llm import validate_openrouter_key

        ok, msg = validate_openrouter_key()
        if not ok:
            logger.warning("OpenRouter LLM misconfigured: %s", msg)
