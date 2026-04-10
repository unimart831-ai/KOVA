"""Data migration: update LLMConfig singleton to paid DeepSeek models.

The DB row was stuck on deprecated free models (qwen/qwen3.6-plus:free)
which return 404. This updates it to working paid models.
"""

from django.db import migrations


def update_llm_config(apps, schema_editor):
    LLMConfig = apps.get_model("agents", "LLMConfig")
    try:
        config = LLMConfig.objects.get(pk=1)
    except LLMConfig.DoesNotExist:
        # No DB row — defaults from the model class will be used (already updated)
        return

    config.default_model = "deepseek/deepseek-v3.2"
    config.model_premium = "deepseek/deepseek-v3.2"
    config.model_workhorse = "deepseek/deepseek-v3.2"
    config.model_fast = "deepseek/deepseek-v3.2"
    config.paid_fallback_model = "google/gemini-2.0-flash-001"
    config.paid_fallback_provider = "openrouter"
    config.paid_fallback_enabled = True
    config.free_fallback_models = []
    config.save()


def revert_llm_config(apps, schema_editor):
    """Revert is a no-op — old models are deprecated anyway."""
    pass


class Migration(migrations.Migration):
    dependencies = [
        ("agents", "0007_plan_model_overrides_and_rate_limits"),
    ]

    operations = [
        migrations.RunPython(update_llm_config, revert_llm_config),
    ]
