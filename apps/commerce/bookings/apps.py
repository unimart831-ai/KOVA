from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.commerce.bookings"
    label = "bookings"
    verbose_name = "Bookings"

    def ready(self):
        from apps.commerce.bookings import signals  # noqa: F401
