from django.contrib import admin

from apps.billing.models import BillingEvent, DiscountCode, DiscountRedemption, MpesaPayment, PlanPrice


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


@admin.register(PlanPrice)
class PlanPriceAdmin(admin.ModelAdmin):
    list_display = ["tier", "price_kes", "price_usd", "is_active", "updated_by", "updated_at"]
    list_filter = ["is_active", "tier"]


@admin.register(DiscountCode)
class DiscountCodeAdmin(admin.ModelAdmin):
    list_display = ["code", "discount_type", "discount_value", "current_uses", "max_uses", "is_active", "valid_until"]
    list_filter = ["is_active", "discount_type", "valid_until"]
    search_fields = ["code", "description"]


@admin.register(DiscountRedemption)
class DiscountRedemptionAdmin(admin.ModelAdmin):
    list_display = ["user", "discount_code", "plan_tier", "amount_saved", "currency", "redeemed_at"]
    list_filter = ["currency", "redeemed_at"]
    search_fields = ["user__email", "discount_code__code"]
    readonly_fields = ["id", "discount_code", "user", "plan_tier", "original_amount", "discounted_amount", "amount_saved", "currency", "redeemed_at"]
