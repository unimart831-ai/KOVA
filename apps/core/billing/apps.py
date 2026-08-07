from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core.billing"
    verbose_name = "Billing"
    label = "billing"
