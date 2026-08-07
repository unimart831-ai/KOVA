from django.apps import AppConfig


class EmailsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.messaging.emails"
    label = "emails"
    verbose_name = "Emails"

    def ready(self):
        import apps.messaging.emails.signals  # noqa: F401
