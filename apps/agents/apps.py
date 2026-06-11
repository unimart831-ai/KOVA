import logging

from django.apps import AppConfig

logger = logging.getLogger(__name__)


class AgentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.agents"
    verbose_name = "AI Agents"

    def ready(self):
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

        if not openrouter_key:
            logger.warning(
                "OPENROUTER_API_KEY is not set — vision and LLM calls routed through "
                "OpenRouter will fail with 401 User not found. Add a valid key in Railway env."
            )
            return

        if openrouter_key.startswith("sk-or-v1-") and len(openrouter_key) < 24:
            logger.warning(
                "OPENROUTER_API_KEY looks truncated or invalid — expect 401 errors from OpenRouter."
            )
