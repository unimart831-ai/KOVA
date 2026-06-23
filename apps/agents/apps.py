import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AgentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agents"
    verbose_name = "AI Agents"

    def ready(self):
        import sys

        # Avoid DB queries during schema management (Django 5+ startup warning).
        if len(sys.argv) > 1 and sys.argv[1] in {
            "migrate",
            "makemigrations",
            "flush",
            "test",
            "collectstatic",
            "createsuperuser",
            "shell",
            "check",
            "showmigrations",
            "loaddata",
        }:
            return

        from django.conf import settings

        openrouter_key = (getattr(settings, "OPENROUTER_API_KEY", "") or "").strip()
        default_provider = getattr(settings, "DEFAULT_LLM_PROVIDER", "openai")

        try:
            from apps.agents.llm import _get_llm_config

            config = _get_llm_config()
            if config and config.pk:
                default_provider = config.default_provider or default_provider
        except Exception:
            pass

        uses_openrouter = default_provider == "openrouter" or bool(openrouter_key)
        if not uses_openrouter:
            return

        from apps.agents.llm import validate_openrouter_key

        ok, msg = validate_openrouter_key()
        if not ok:
            logger.warning("OpenRouter LLM misconfigured: %s", msg)
