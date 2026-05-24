"""
EmailService — single interface for all email sending in Kova Agent.

Usage:
    from apps.emails.services import email_service

    email_service.send_welcome(user)
    email_service.send_payment_confirmation(user, amount="500 KES", plan="Growth")
    email_service.send_team_invitation(to_email="new@example.com", team_name="Acme", invite_url="...")
"""

import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.utils import timezone
from django.utils.html import strip_tags

from apps.emails.models import EmailLog

logger = logging.getLogger(__name__)


# ─── Template registry ───────────────────────────────────────────────────────
# Maps email_type → (template_path, default_subject)

EMAIL_TEMPLATES = {
    # Authentication
    "verification": ("emails/verification.html", "Verify your email — Kova Agent"),
    "password_reset": ("emails/password_reset.html", "Reset your password — Kova Agent"),
    "password_changed": ("emails/password_changed.html", "Your password was changed — Kova Agent"),

    # Onboarding
    "welcome": ("emails/welcome.html", "Welcome to Kova Agent! 🎉"),

    # Billing
    "payment_confirmation": ("emails/payment_confirmation.html", "Payment confirmed — Kova Agent"),
    "invoice": ("emails/invoice.html", "Your invoice from Kova Agent"),
    "receipt": ("emails/receipt.html", "Payment receipt — Kova Agent"),
    "payment_failed": ("emails/payment_failed.html", "Payment failed — action needed"),
    "payment_reminder": ("emails/payment_reminder.html", "Your subscription is expiring soon"),
    "plan_changed": ("emails/plan_changed.html", "Your plan has been updated — Kova Agent"),
    "subscription_canceled": ("emails/subscription_canceled.html", "Your subscription has been canceled"),
    "trial_ending": ("emails/trial_ending.html", "Your trial ends soon — Kova Agent"),

    # Team
    "team_invitation": ("emails/team_invitation.html", "You've been invited to join a team on Kova Agent"),

    # Reports
    "weekly_report": ("emails/weekly_report.html", "Your weekly performance report — Kova Agent"),
    "daily_brief": ("emails/daily_brief.html", "Your Daily Brief — Kova Agent"),

    # Product
    "feature_announcement": ("emails/feature_announcement.html", "What's new in Kova Agent"),

    # Marketing
    "promotional": ("emails/promotional.html", "Special offer from Kova Agent"),

    # System
    "usage_warning": ("emails/usage_warning.html", "You're approaching your plan limits"),
    "system": ("emails/system.html", "Important update from Kova Agent"),

    # Partners
    "partner_app_received": ("emails/partner_app_received.html", "We received your Growth Partner application — Kova Agent"),
    "partner_app_approved": ("emails/partner_app_approved.html", "You're approved! Welcome to the Growth Partners Program 🎉"),
    "partner_approved_noacc": ("emails/partner_approved_no_account.html", "You're approved! Create your account to get started 🎉"),
    "partner_app_rejected": ("emails/partner_app_rejected.html", "Update on your Growth Partner application — Kova Agent"),
    "partner_new_referral": ("emails/partner_new_referral.html", "New referral! Someone signed up with your link 🔥"),
    "partner_milestone": ("emails/partner_milestone.html", "Milestone achieved! You've unlocked a bonus 🏆"),

    # Monthly attribution report
    "monthly_report": ("emails/monthly_report.html", "Your monthly performance report — Kova Agent"),

    # Lead nurture
    "lead_nurture": ("emails/lead_nurture.html", "Following up"),
}


class EmailService:
    """Central email service. All emails in the platform go through this class."""

    def _send(self, email_type, to_email, context=None, user=None, subject=None, metadata=None):
        """
        Core send method. Renders template, sends email, logs to EmailLog.

        Args:
            email_type: Key from EMAIL_TEMPLATES / EmailLog.EmailType
            to_email: Recipient email address
            context: Dict of template context variables
            user: Optional User instance (for logging)
            subject: Override default subject
            metadata: Extra JSON metadata to store in log
        Returns:
            EmailLog instance
        """
        template_path, default_subject = EMAIL_TEMPLATES.get(
            email_type, ("emails/system.html", "Notification from Kova Agent")
        )
        subject = subject or default_subject

        # Base context available in every email
        base_context = {
            "site_url": getattr(settings, "SITE_URL", "https://kovaagent.com"),
            "current_year": timezone.now().year,
        }
        if user:
            base_context["user"] = user
            base_context["first_name"] = user.first_name or user.email.split("@")[0]

            # Generate one-click unsubscribe URL for this recipient
            unsubscribe_url = self._get_unsubscribe_url(user, to_email)
            if unsubscribe_url:
                base_context["unsubscribe_url"] = unsubscribe_url

        if context:
            base_context.update(context)

        # Create log entry
        log = EmailLog.objects.create(
            user=user,
            to_email=to_email,
            from_email=settings.DEFAULT_FROM_EMAIL,
            email_type=email_type,
            subject=subject,
            status=EmailLog.Status.QUEUED,
            metadata=metadata or {},
        )

        try:
            html_body = render_to_string(template_path, base_context)
            text_body = strip_tags(html_body)

            msg = EmailMultiAlternatives(
                subject=subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[to_email],
            )
            msg.attach_alternative(html_body, "text/html")

            # Add List-Unsubscribe headers (RFC 8058) for email client support
            unsub_url = base_context.get("unsubscribe_url")
            if unsub_url:
                msg.extra_headers["List-Unsubscribe"] = f"<{unsub_url}>"
                msg.extra_headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

            # Set a custom Message-ID containing our log UUID so Resend
            # echoes it back in webhooks and we can correlate delivery events.
            from_domain = settings.DEFAULT_FROM_EMAIL.split("@")[-1].rstrip(">")
            msg.extra_headers["Message-ID"] = f"<{log.pk}@{from_domain}>"

            msg.send(fail_silently=False)

            log.status = EmailLog.Status.SENT
            log.sent_at = timezone.now()
            log.save(update_fields=["status", "sent_at"])

            logger.info("Email sent: type=%s to=%s", email_type, to_email)

        except Exception as e:
            log.status = EmailLog.Status.FAILED
            log.failed_at = timezone.now()
            log.error_message = str(e)[:500]
            log.save(update_fields=["status", "failed_at", "error_message"])
            logger.error("Email failed: type=%s to=%s error=%s", email_type, to_email, e)

        return log

    def _get_unsubscribe_url(self, user, to_email):
        """
        Get or create an unsubscribe URL for this user/email combo.
        Returns None if subscriber record doesn't exist (transactional-only recipient).
        """
        from apps.emails.models import EmailSubscriber

        try:
            subscriber = EmailSubscriber.objects.get(user=user, email=to_email)
        except EmailSubscriber.DoesNotExist:
            return None

        if not subscriber.unsubscribe_token:
            subscriber.save()  # triggers token generation in save()

        site_url = getattr(settings, "SITE_URL", "https://kovaagent.com")
        return f"{site_url}/emails/unsubscribe/{subscriber.unsubscribe_token}/"

    # ─── Authentication emails ───────────────────────────────────────────

    def send_welcome(self, user):
        return self._send(
            "welcome", user.email, user=user,
            context={
                "studio_url": f"{settings.SITE_URL}/content/studio/",
                "brief_url": f"{settings.SITE_URL}/brief/",
                "platforms_url": f"{settings.SITE_URL}/platforms/",
                "help_url": f"{settings.SITE_URL}/learn/",
            },
        )

    def send_password_changed(self, user):
        return self._send("password_changed", user.email, user=user)

    # ─── Billing emails ─────────────────────────────────────────────────

    def send_payment_confirmation(self, user, amount, plan, provider="stripe", receipt_number=""):
        return self._send(
            "payment_confirmation", user.email, user=user,
            context={"amount": amount, "plan": plan, "provider": provider, "receipt_number": receipt_number},
            metadata={"amount": str(amount), "plan": plan, "provider": provider},
        )

    def send_payment_failed(self, user, plan=None):
        return self._send(
            "payment_failed", user.email, user=user,
            context={"plan": plan or user.profile.get_plan_display()},
        )

    def send_plan_changed(self, user, old_plan, new_plan):
        return self._send(
            "plan_changed", user.email, user=user,
            context={"old_plan": old_plan, "new_plan": new_plan},
            metadata={"old_plan": old_plan, "new_plan": new_plan},
        )

    def send_subscription_canceled(self, user):
        return self._send("subscription_canceled", user.email, user=user)

    def send_payment_reminder(self, user, days_until_expiry):
        return self._send(
            "payment_reminder", user.email, user=user,
            context={"days_until_expiry": days_until_expiry},
        )

    def send_trial_ending(self, user, days_left):
        return self._send(
            "trial_ending", user.email, user=user,
            context={"days_left": days_left},
        )

    def send_invoice(self, user, amount, plan, invoice_date, invoice_number=""):
        return self._send(
            "invoice", user.email, user=user,
            context={
                "amount": amount, "plan": plan,
                "invoice_date": invoice_date, "invoice_number": invoice_number,
            },
            metadata={"amount": str(amount), "invoice_number": invoice_number},
        )

    def send_receipt(self, user, amount, plan, receipt_number, payment_method=""):
        return self._send(
            "receipt", user.email, user=user,
            context={
                "amount": amount, "plan": plan,
                "receipt_number": receipt_number, "payment_method": payment_method,
            },
            metadata={"amount": str(amount), "receipt_number": receipt_number},
        )

    # ─── Team emails ────────────────────────────────────────────────────

    def send_team_invitation(self, to_email, inviter_name, team_name, invite_url):
        return self._send(
            "team_invitation", to_email,
            context={
                "inviter_name": inviter_name,
                "team_name": team_name,
                "invite_url": invite_url,
            },
            metadata={"team_name": team_name, "inviter": inviter_name},
        )

    # ─── Reports ────────────────────────────────────────────────────────

    def send_weekly_report(self, user, report_data):
        return self._send(
            "weekly_report", user.email, user=user,
            context={"report": report_data},
        )

    def send_daily_brief(self, user, *, brief, your_move="", top_decisions=None,
                         brief_url="", approve_url=""):
        delta = brief.kova_score_delta or 0
        subject = f"Your Daily Brief — {brief.date.strftime('%b %d, %Y')}"
        if delta > 0:
            subject = f"☀️ Score +{delta} — {subject}"
        elif brief.posts_pending:
            subject = f"📋 {brief.posts_pending} posts waiting — {subject}"

        return self._send(
            "daily_brief", user.email, user=user,
            context={
                "brief": brief,
                "your_move": your_move,
                "top_decisions": top_decisions or [],
                "brief_url": brief_url,
                "approve_url": approve_url,
            },
            subject=subject,
        )

    def send_monthly_report(self, user, report_data):
        return self._send(
            "monthly_report", user.email, user=user,
            context={"report": report_data, "user": user},
        )

    # ─── Product / Marketing ────────────────────────────────────────────

    def send_feature_announcement(self, user, feature_title, feature_description, cta_url=""):
        return self._send(
            "feature_announcement", user.email, user=user,
            context={
                "feature_title": feature_title,
                "feature_description": feature_description,
                "cta_url": cta_url or f"{settings.SITE_URL}/brief/",
            },
        )

    def send_promotional(self, user, promo_title, promo_body, cta_text="", cta_url=""):
        return self._send(
            "promotional", user.email, user=user,
            context={
                "promo_title": promo_title,
                "promo_body": promo_body,
                "cta_text": cta_text or "Check it out",
                "cta_url": cta_url or f"{settings.SITE_URL}/billing/",
            },
        )

    # ─── System ─────────────────────────────────────────────────────────

    def send_usage_warning(self, user, resource, current, limit):
        pct = round((current / limit) * 100) if limit else 0
        return self._send(
            "usage_warning", user.email, user=user,
            context={"resource": resource, "current": current, "limit": limit, "pct": pct},
        )

    # ─── Partners ────────────────────────────────────────────────────────

    def send_partner_application_received(self, to_email, full_name, user=None):
        return self._send(
            "partner_app_received", to_email, user=user,
            context={"applicant_name": full_name},
            metadata={"applicant_name": full_name},
        )

    def send_partner_application_approved(self, user, referral_code, dashboard_url=""):
        return self._send(
            "partner_app_approved", user.email, user=user,
            context={
                "referral_code": referral_code,
                "dashboard_url": dashboard_url or f"{getattr(settings, 'SITE_URL', '')}/partners/dashboard/",
                "partners_url": f"{getattr(settings, 'SITE_URL', '')}/partners/",
            },
            metadata={"referral_code": referral_code},
        )

    def send_partner_approved_no_account(self, to_email, full_name):
        return self._send(
            "partner_approved_noacc", to_email,
            context={
                "applicant_name": full_name,
                "signup_url": f"{getattr(settings, 'SITE_URL', '')}/accounts/signup/",
                "partners_url": f"{getattr(settings, 'SITE_URL', '')}/partners/",
            },
            metadata={"applicant_name": full_name},
        )

    def send_partner_application_rejected(self, to_email, full_name, user=None, reason=""):
        return self._send(
            "partner_app_rejected", to_email, user=user,
            context={"applicant_name": full_name, "reason": reason},
        )

    def send_partner_new_referral(self, partner_user, referred_email, total_referrals=0):
        return self._send(
            "partner_new_referral", partner_user.email, user=partner_user,
            context={
                "referred_email": referred_email,
                "total_referrals": total_referrals,
                "dashboard_url": f"{getattr(settings, 'SITE_URL', '')}/partners/dashboard/",
            },
            metadata={"referred_email": referred_email},
        )

    def send_partner_milestone(self, partner_user, milestone_label, bonus_kes, extras=""):
        return self._send(
            "partner_milestone", partner_user.email, user=partner_user,
            context={
                "milestone_label": milestone_label,
                "bonus_kes": bonus_kes,
                "extras": extras,
                "dashboard_url": f"{getattr(settings, 'SITE_URL', '')}/partners/dashboard/",
            },
            metadata={"milestone": milestone_label, "bonus_kes": str(bonus_kes)},
        )


# Singleton instance — import this in other apps
email_service = EmailService()
