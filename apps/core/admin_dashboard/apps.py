from django.apps import AppConfig


class AdminDashboardConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core.admin_dashboard"
    verbose_name = "Admin Dashboard"
    label = "admin_dashboard"
