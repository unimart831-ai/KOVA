from django.apps import AppConfig


class QRAttributionConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.commerce.qr_attribution"
    label = "qr_attribution"
    verbose_name = "QR / Walk-in Attribution"

    def ready(self):
        import apps.commerce.qr_attribution.signals  # noqa: F401
