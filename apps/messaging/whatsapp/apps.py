from django.apps import AppConfig


class WhatsappConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.messaging.whatsapp"
    verbose_name = "WhatsApp"
    label = "whatsapp"
