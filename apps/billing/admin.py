from django.contrib import admin

from apps.billing.models import (
    AgencySalesInquiry,
    BillingEvent,
    CampaignAddonPurchase,
    DiscountCode,
    DiscountRedemption,
    MpesaPayment,
    PlanPrice,
    SubscriptionOverride,
)


@admin.register(AgencySalesInquiry)
class AgencySalesInquiryAdmin(admin.ModelAdmin):
    list_display = ["name", "email", "company_name", "status", "client_count", "created_at"]
    list_filter = ["status", "plan_interest", "created_at"]
    search_fields = ["name", "email", "company_name", "phone", "message"]
    readonly_fields = ["id", "user", "created_at", "updated_at", "contacted_at", "closed_at"]
    ordering = ["-created_at"]


@admin.register(BillingEvent)
class BillingEventAdmin(admin.ModelAdmin):
    list_display = ["provider", "event_type", "stripe_event_id", "user", "processed", "created_at"]
    list_filter = ["provider", "event_type", "processed", "created_at"]
    search_fields = ["stripe_event_id", "user__email"]
    readonly_fields = ["id", "stripe_event_id", "event_type", "provider", "user", "data", "processed", "error_message", "created_at"]
    ordering = ["-created_at"]


@admin.register(MpesaPayment)
class MpesaPaymentAdmin(admin.ModelAdmin):
    list_display = ["user", "amount", "payment_kind", "plan_tier", "addon_pack_id", "status", "receipt_number", "created_at"]
    list_filter = ["status", "payment_kind", "plan_tier", "created_at"]
    search_fields = ["user__email", "phone_number", "receipt_number", "checkout_request_id"]
    readonly_fields = [
        "id", "user", "checkout_request_id", "merchant_request_id", "receipt_number",
        "phone_number", "amount", "plan_tier", "currency", "status", "result_code",
        "result_desc", "is_renewal", "subscription_period_start", "subscription_period_end",
        "created_at", "completed_at",
    ]
    ordering = ["-created_at"]


@admin.register(CampaignAddonPurchase)
class CampaignAddonPurchaseAdmin(admin.ModelAdmin):
    list_display = ["user", "pack_id", "campaigns_granted", "bonus_before", "bonus_after", "created_at"]
    list_filter = ["pack_id", "created_at"]
    search_fields = ["user__email", "pack_id"]
    readonly_fields = [
        "id", "user", "mpesa_payment", "pack_id", "campaigns_granted",
        "bonus_before", "bonus_after", "created_at",
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


@admin.register(SubscriptionOverride)
class SubscriptionOverrideAdmin(admin.ModelAdmin):
    """Audit trail of manual plan changes — comp accounts, trial extensions,
    refunds, plan migrations. Critical for support & finance reconciliation."""

    list_display = [
        "user", "action", "previous_plan", "new_plan",
        "days_granted", "admin", "expires_at", "created_at",
    ]
    list_filter = ["action", "new_plan", "previous_plan", "created_at"]
    search_fields = ["user__email", "admin__email", "reason", "batch_id"]
    readonly_fields = ["created_at"]
    raw_id_fields = ["user", "admin"]
    date_hierarchy = "created_at"
