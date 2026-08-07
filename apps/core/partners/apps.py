from django.apps import AppConfig


class PartnersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core.partners"
    label = "partners"
    verbose_name = "Growth Partners"

    def ready(self):
        import apps.core.partners.signals  # noqa: F401
