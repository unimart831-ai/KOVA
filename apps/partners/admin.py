from django.contrib import admin

from .models import Commission, MilestoneAward, Partner, PartnerApplication, Referral


@admin.register(PartnerApplication)
class PartnerApplicationAdmin(admin.ModelAdmin):
    list_display = ["full_name", "email", "status", "created_at", "reviewed_at"]
    list_filter = ["status"]
    search_fields = ["full_name", "email", "company"]
    readonly_fields = ["created_at"]
    actions = ["approve_applications", "reject_applications"]

    @admin.action(description="Approve selected applications")
    def approve_applications(self, request, queryset):
        from django.utils import timezone

        queryset.update(status="approved", reviewed_at=timezone.now())

    @admin.action(description="Reject selected applications")
    def reject_applications(self, request, queryset):
        from django.utils import timezone

        queryset.update(status="rejected", reviewed_at=timezone.now())


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
