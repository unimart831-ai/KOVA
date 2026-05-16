"""Django admin for QR / walk-in attribution.

Read-mostly: ops staff use admin to debug attribution claims, not to
mass-edit. Edits happen through the user-facing UI.
"""
from django.contrib import admin

from .models import QRCode, QRScan, WalkInEvent


@admin.register(QRCode)
class QRCodeAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "token", "landing_template", "is_active", "created_at")
    list_filter = ("landing_template", "is_active", "created_at")
    search_fields = ("label", "token", "user__email", "user__username")
    readonly_fields = ("id", "token", "created_at", "updated_at")
    raw_id_fields = ("user", "campaign", "post")
    date_hierarchy = "created_at"


@admin.register(QRScan)
class QRScanAdmin(admin.ModelAdmin):
    list_display = ("qr_code", "scanned_at", "visitor_id", "user_agent")
    list_filter = ("scanned_at",)
    search_fields = ("qr_code__label", "qr_code__token", "visitor_id")
    readonly_fields = ("id", "scanned_at", "visitor_id", "user_agent", "ip_hash")
    raw_id_fields = ("qr_code",)
    date_hierarchy = "scanned_at"


@admin.register(WalkInEvent)
class WalkInEventAdmin(admin.ModelAdmin):
    list_display = (
        "recorded_at", "user", "attribution_source", "revenue", "currency",
        "qr_code", "scan",
    )
    list_filter = ("attribution_source", "currency", "recorded_at")
    search_fields = (
        "user__email", "user__username",
        "attribution_label", "notes",
        "qr_code__label", "qr_code__token",
    )
    readonly_fields = ("id", "recorded_at")
    raw_id_fields = ("user", "qr_code", "scan")
    date_hierarchy = "recorded_at"
