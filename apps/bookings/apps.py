from django.apps import AppConfig


class BookingsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.bookings"
    label = "bookings"
    verbose_name = "Bookings"

    def ready(self):
        from apps.bookings import signals  # noqa: F401
