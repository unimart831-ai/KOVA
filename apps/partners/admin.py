from django.contrib import admin
from django.utils import timezone

from .models import Commission, MilestoneAward, Partner, PartnerApplication, Referral, generate_referral_code


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
        for application in queryset.filter(status="pending"):
            application.status = "approved"
            application.reviewed_at = now
            application.save(update_fields=["status", "reviewed_at"])

            # Auto-create Partner if user is linked
            if application.user and not Partner.objects.filter(user=application.user).exists():
                name = application.full_name or application.user.get_full_name()
                partner = Partner.objects.create(
                    user=application.user,
                    application=application,
                    referral_code=generate_referral_code(name),
                )
                # Send approval email
                try:
                    from apps.emails.tasks import send_partner_app_approved_email
                    send_partner_app_approved_email.delay(str(application.user.pk), partner.referral_code)
                except Exception:
                    pass
            elif application.user:
                # Partner already exists, still send email
                try:
                    partner = Partner.objects.get(user=application.user)
                    from apps.emails.tasks import send_partner_app_approved_email
                    send_partner_app_approved_email.delay(str(application.user.pk), partner.referral_code)
                except Exception:
                    pass

        self.message_user(request, f"{queryset.filter(status='approved').count()} applications approved.")

    @admin.action(description="Reject selected applications")
    def reject_applications(self, request, queryset):
        now = timezone.now()
        for application in queryset.filter(status="pending"):
            application.status = "rejected"
            application.reviewed_at = now
            application.save(update_fields=["status", "reviewed_at"])

            # Send rejection email
            try:
                from apps.emails.tasks import send_partner_app_rejected_email
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
