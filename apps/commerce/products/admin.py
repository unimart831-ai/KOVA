from django.contrib import admin

from apps.commerce.products.models import (
    Product,
    ProductCategory,
    RestockScan,
    StockAlert,
    StockUpdate,
)


class StockUpdateInline(admin.TabularInline):
    model = StockUpdate
    extra = 0
    readonly_fields = ("previous_status", "new_status", "previous_quantity", "new_quantity", "reason", "created_at")
    ordering = ("-created_at",)


@admin.register(ProductCategory)
class ProductCategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "position", "is_active")
    list_filter = ("is_active",)
    search_fields = ("name", "user__email")


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "user", "stock_status", "price", "currency", "is_featured", "is_active")
    list_filter = ("stock_status", "is_featured", "is_active")
    search_fields = ("name", "user__email")
    readonly_fields = ("created_at", "updated_at")
    inlines = [StockUpdateInline]


@admin.register(StockUpdate)
class StockUpdateAdmin(admin.ModelAdmin):
    list_display = ("product", "previous_status", "new_status", "reason", "created_at")
    list_filter = ("reason", "new_status")
    readonly_fields = ("created_at",)


@admin.register(StockAlert)
class StockAlertAdmin(admin.ModelAdmin):
    list_display = ("product", "alert_type", "user", "is_read", "created_at")
    list_filter = ("alert_type", "is_read")
    search_fields = ("product__name", "user__email")
    readonly_fields = ("created_at",)


@admin.register(RestockScan)
class RestockScanAdmin(admin.ModelAdmin):
    """User uploads a restock receipt/photo, AI extracts items and matches to
    the catalog. Admin used to debug extraction failures and unmatched items."""

    list_display = (
        "user", "status", "supplier_name", "receipt_date",
        "products_matched", "products_updated", "created_at",
    )
    list_filter = ("status", "receipt_currency")
    search_fields = ("user__email", "supplier_name", "error_message")
    readonly_fields = ("created_at", "completed_at")
    raw_id_fields = ("user", "content_seed")
    date_hierarchy = "created_at"
