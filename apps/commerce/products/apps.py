from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.commerce.products"
    label = "products"
    verbose_name = "Product Catalog"

    def ready(self):
        import apps.commerce.products.signals  # noqa: F401
