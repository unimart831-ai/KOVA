from django.contrib import admin
from django.utils import timezone

from .models import (
    Commission,
    MarketplacePartner,
    MarketplaceSellerAccount,
    MilestoneAward,
    Partner,
    PartnerApplication,
    Referral,
    generate_referral_code,
)


@admin.register(PartnerApplication)
class PartnerApplicationAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "status", "created_at", "reviewed_at"]
    list_filter = ["status"]
    search_fields = ["full_name", "email", "company"]
    readonly_fields = ["created_at"]
    actions = ["approve_applications", "reject_applications"]

    @admin.action(description="Approve selected applications")
    def approve_applications(self, request, queryset):
        now = timezone.now()
        approved = 0
        for application in queryset.filter(status="pending"):
            application.status = "approved"
            application.reviewed_at = now
            application.save(update_fields=["status", "reviewed_at"])
            approved += 1

            # Auto-create Partner if user is linked
            if application.user and not Partner.objects.filter(user=application.user).exists():
                name = application.full_name or application.user.get_full_name()
                partner = Partner.objects.create(
                    user=application.user,
                    application=application,
                    referral_code=generate_referral_code(name),
                )
                # Send approval email with referral code
                try:
                    from apps.messaging.emails.tasks import send_partner_app_approved_email
                    send_partner_app_approved_email.delay(str(application.user.pk), partner.referral_code)
                except Exception:
                    pass
            elif application.user:
                # Partner already exists, still send email
                try:
                    partner = Partner.objects.get(user=application.user)
                    from apps.messaging.emails.tasks import send_partner_app_approved_email
                    send_partner_app_approved_email.delay(str(application.user.pk), partner.referral_code)
                except Exception:
                    pass
            else:
                # No Kova account yet — send approval email telling them to create one
                try:
                    from apps.messaging.emails.tasks import send_partner_app_approved_no_account_email
                    send_partner_app_approved_no_account_email.delay(
                        application.email,
                        application.full_name,
                    )
                except Exception:
                    pass

        self.message_user(request, f"{approved} application(s) approved.")

    @admin.action(description="Reject selected applications")
    def reject_applications(self, request, queryset):
        now = timezone.now()
        for application in queryset.filter(status="pending"):
            application.status = "rejected"
            application.reviewed_at = now
            application.save(update_fields=["status", "reviewed_at"])

            # Send rejection email
            try:
                from apps.messaging.emails.tasks import send_partner_app_rejected_email
                send_partner_app_rejected_email.delay(
                    application.email,
                    application.full_name,
                    str(application.user.pk) if application.user else None,
                )
            except Exception:
                pass

        self.message_user(request, f"Applications rejected.")


@admin.register(Partner)
class PartnerAdmin(admin.ModelAdmin):
    list_display = [
        "user",
        "referral_code",
        "tier",
        "commission_rate",
        "active_referrals_count",
        "total_earned_kes",
        "is_active",
    ]
    list_filter = ["tier", "is_active"]
    search_fields = ["user__email", "referral_code"]
    readonly_fields = ["joined_at", "total_earned_kes", "pending_payout_kes"]

    def active_referrals_count(self, obj):
        return obj.active_referrals_count

    active_referrals_count.short_description = "Active Clients"


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = [
        "referred_user",
        "partner",
        "referral_code_used",
        "signed_up_at",
        "activated_at",
        "is_active",
        "current_plan",
    ]
    list_filter = ["is_active"]
    search_fields = ["referred_user__email", "partner__referral_code"]
    readonly_fields = ["signed_up_at"]


@admin.register(Commission)
class CommissionAdmin(admin.ModelAdmin):
    list_display = [
        "partner",
        "period_start",
        "period_end",
        "client_revenue_kes",
        "commission_rate",
        "amount_kes",
        "status",
    ]
    list_filter = ["status"]
    search_fields = ["partner__referral_code"]
    readonly_fields = ["created_at"]


@admin.register(MilestoneAward)
class MilestoneAwardAdmin(admin.ModelAdmin):
    list_display = ["partner", "label", "clients_required", "bonus_kes", "paid", "awarded_at"]
    list_filter = ["paid"]
    search_fields = ["partner__referral_code"]


@admin.register(MarketplacePartner)
class MarketplacePartnerAdmin(admin.ModelAdmin):
    """B2B marketplace integration partners. Each has an API key and a
    pool of seller accounts (MarketplaceSellerAccount)."""

    list_display = [
        "name", "slug", "billing_model", "max_sellers",
        "is_active", "auto_activate_sellers", "created_at",
    ]
    list_filter = ["is_active", "billing_model", "auto_activate_sellers", "sync_direction"]
    search_fields = ["name", "slug", "contact_email", "contact_name", "notes"]
    readonly_fields = [
        "created_at", "updated_at", "api_key_prefix",
        "api_key_created_at", "api_key_last_used",
    ]
    prepopulated_fields = {"slug": ("name",)}
    raw_id_fields = ["partner"]
    fieldsets = (
        ("Identity", {
            "fields": ("name", "slug", "partner", "logo_url", "website", "is_active"),
        }),
        ("Contact", {"fields": ("contact_name", "contact_email")}),
        ("API access", {
            "fields": ("api_key_prefix", "api_key_created_at", "api_key_last_used"),
            "description": "API key itself is stored as a hash and not displayable. Rotate via the partner API.",
        }),
        ("Seller provisioning", {
            "fields": (
                "seller_identity_field", "auto_activate_sellers",
                "seller_default_plan", "max_sellers",
                "seller_welcome_email", "seller_data_mapping",
            ),
        }),
        ("Sync & products", {
            "fields": (
                "sync_direction", "auto_snap_on_sync",
                "enforce_marketplace_cta", "product_field_mapping",
                "default_product_currency", "enrich_descriptions",
            ),
        }),
        ("Billing & commercials", {
            "fields": (
                "billing_model", "rate_per_seller_kes",
                "flat_fee_kes", "revenue_share_pct", "pilot_expires_at",
            ),
        }),
        ("Webhooks", {"fields": ("webhook_url", "webhook_secret"), "classes": ("collapse",)}),
        ("Internal", {"fields": ("notes", "settings", "created_at", "updated_at"), "classes": ("collapse",)}),
    )


@admin.register(MarketplaceSellerAccount)
class MarketplaceSellerAccountAdmin(admin.ModelAdmin):
    """A single seller's account inside a marketplace. Links a User to the
    parent MarketplacePartner with external_seller_id for cross-referencing."""

    list_display = [
        "external_seller_id", "marketplace", "user", "status",
        "business_name", "products_synced", "content_generated",
        "provisioned_at",
    ]
    list_filter = ["status", "marketplace"]
    search_fields = ["external_seller_id", "business_name", "business_url", "user__email"]
    readonly_fields = [
        "provisioned_at", "activated_at", "suspended_at",
        "last_product_sync",
    ]
    raw_id_fields = ["marketplace", "user"]
    date_hierarchy = "provisioned_at"
