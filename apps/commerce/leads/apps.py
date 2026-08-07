from django.apps import AppConfig


class LeadsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.commerce.leads"
    label = "leads"
    verbose_name = "Lead Inbox"

    def ready(self):
        import apps.commerce.leads.signals  # noqa: F401
