from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.core.accounts"
    label = "accounts"
    verbose_name = "Accounts"

    def ready(self):
        import apps.core.accounts.signals  # noqa: F401
