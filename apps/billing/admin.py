from django.contrib import admin

from apps.billing.models import BillingEvent


@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    list_display = ["event_type", "stripe_event_id", "user", "processed", "created_at"]
    list_filter = ["event_type", "processed", "created_at"]
    search_fields = ["stripe_event_id", "user__email"]
    readonly_fields = ["id", "stripe_event_id", "event_type", "user", "data", "processed", "error_message", "created_at"]
    ordering = ["-created_at"]
