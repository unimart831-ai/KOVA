from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = "apps.messaging.notifications"
    verbose_name = 'Notifications'
    label = "notifications"
