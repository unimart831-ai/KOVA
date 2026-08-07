from django.apps import AppConfig


class AnalyticsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.insight.analytics"
    verbose_name = "Analytics"
    label = "analytics"
