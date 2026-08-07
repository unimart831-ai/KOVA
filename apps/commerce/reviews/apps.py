from django.apps import AppConfig


class ReviewsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.commerce.reviews"
    label = "reviews"
    verbose_name = "Review Requests"

    def ready(self):
        from apps.commerce.reviews import signals  # noqa: F401
