from django.apps import AppConfig


class ContentConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.create.content"
    label = "content"
    verbose_name = "Content"

    def ready(self):
        import apps.create.content.signals  # noqa: F401
