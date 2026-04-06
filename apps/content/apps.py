from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.content"
    verbose_name = "Content"

    def ready(self):
        import apps.content.signals  # noqa: F401
