from django.contrib import admin

from apps.billing.models import BillingEvent, MpesaPayment


@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    list_display = ["provider", "event_type", "stripe_event_id", "user", "processed", "created_at"]
    list_filter = ["provider", "event_type", "processed", "created_at"]
    search_fields = ["stripe_event_id", "user__email"]
    readonly_fields = ["id", "stripe_event_id", "event_type", "provider", "user", "data", "processed", "error_message", "created_at"]
    ordering = ["-created_at"]


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ["user", "amount", "plan_tier", "status", "receipt_number", "phone_number", "created_at"]
    list_filter = ["status", "plan_tier", "created_at"]
    search_fields = ["user__email", "phone_number", "receipt_number", "checkout_request_id"]
    readonly_fields = [
        "id", "user", "checkout_request_id", "merchant_request_id", "receipt_number",
        "phone_number", "amount", "plan_tier", "currency", "status", "result_code",
        "result_desc", "is_renewal", "subscription_period_start", "subscription_period_end",
        "created_at", "completed_at",
    ]
    ordering = ["-created_at"]
