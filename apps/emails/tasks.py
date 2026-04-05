"""
Celery tasks for async email sending.

Every email in the platform goes through a Celery task so it never
blocks a request/response cycle.
"""

import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="emails.send_email", bind=True, max_retries=3, default_retry_delay=60)
def send_email_task(self, email_type, to_email, user_id=None, context=None, subject=None, metadata=None):
    """
    Generic async email task.

    Args:
        email_type: Key from EMAIL_TEMPLATES
        to_email: Recipient email
        user_id: Optional user UUID (string)
        context: Template context dict
        subject: Override subject
        metadata: Extra JSON metadata
    """
    from apps.emails.services import email_service

    user = None
    if user_id:
        from apps.accounts.models import User
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            logger.warning("send_email_task: User %s not found, sending without user context", user_id)

    try:
        email_service._send(
            email_type=email_type,
            to_email=to_email,
            context=context or {},
            user=user,
            subject=subject,
            metadata=metadata or {},
        )
    except Exception as exc:
        logger.error("send_email_task failed: type=%s to=%s error=%s", email_type, to_email, exc)
        raise self.retry(exc=exc)


# ─── Convenience tasks (named, easy to call from other apps) ─────────────────

@shared_task(name="emails.send_welcome")
def send_welcome_email(user_id):
    """Send welcome email to a newly registered user."""
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_welcome(user)
    except Exception as e:
        logger.error("Welcome email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_payment_confirmation")
def send_payment_confirmation_email(user_id, amount, plan, provider="stripe", receipt_number=""):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_payment_confirmation(user, amount, plan, provider, receipt_number)
    except Exception as e:
        logger.error("Payment confirmation email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_payment_failed")
def send_payment_failed_email(user_id, plan=None):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_payment_failed(user, plan)
    except Exception as e:
        logger.error("Payment failed email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_plan_changed")
def send_plan_changed_email(user_id, old_plan, new_plan):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_plan_changed(user, old_plan, new_plan)
    except Exception as e:
        logger.error("Plan changed email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_subscription_canceled")
def send_subscription_canceled_email(user_id):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_subscription_canceled(user)
    except Exception as e:
        logger.error("Subscription canceled email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_payment_reminder")
def send_payment_reminder_email(user_id, days_until_expiry):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_payment_reminder(user, days_until_expiry)
    except Exception as e:
        logger.error("Payment reminder email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_team_invitation")
def send_team_invitation_email(to_email, inviter_name, team_name, invite_url):
    from apps.emails.services import email_service
    try:
        email_service.send_team_invitation(to_email, inviter_name, team_name, invite_url)
    except Exception as e:
        logger.error("Team invitation email failed for %s: %s", to_email, e)


@shared_task(name="emails.send_weekly_report")
def send_weekly_report_email(user_id, report_data):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_weekly_report(user, report_data)
    except Exception as e:
        logger.error("Weekly report email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_feature_announcement")
def send_feature_announcement_email(user_id, feature_title, feature_description, cta_url=""):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_feature_announcement(user, feature_title, feature_description, cta_url)
    except Exception as e:
        logger.error("Feature announcement email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_usage_warning")
def send_usage_warning_email(user_id, resource, current, limit):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_usage_warning(user, resource, current, limit)
    except Exception as e:
        logger.error("Usage warning email failed for user %s: %s", user_id, e)


# ─── Partner emails ─────────────────────────────────────────────────────────

@shared_task(name="emails.send_partner_app_received")
def send_partner_app_received_email(to_email, full_name, user_id=None):
    from apps.emails.services import email_service
    user = None
    if user_id:
        from apps.accounts.models import User
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            pass
    try:
        email_service.send_partner_application_received(to_email, full_name, user)
    except Exception as e:
        logger.error("Partner app received email failed for %s: %s", to_email, e)


@shared_task(name="emails.send_partner_app_approved")
def send_partner_app_approved_email(user_id, referral_code):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_partner_application_approved(user, referral_code)
    except Exception as e:
        logger.error("Partner app approved email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_partner_app_rejected")
def send_partner_app_rejected_email(to_email, full_name, user_id=None, reason=""):
    from apps.emails.services import email_service
    user = None
    if user_id:
        from apps.accounts.models import User
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            pass
    try:
        email_service.send_partner_application_rejected(to_email, full_name, user, reason)
    except Exception as e:
        logger.error("Partner app rejected email failed for %s: %s", to_email, e)


@shared_task(name="emails.send_partner_new_referral")
def send_partner_new_referral_email(partner_user_id, referred_email, total_referrals=0):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        partner_user = User.objects.get(pk=partner_user_id)
        email_service.send_partner_new_referral(partner_user, referred_email, total_referrals)
    except Exception as e:
        logger.error("Partner new referral email failed for user %s: %s", partner_user_id, e)


@shared_task(name="emails.send_partner_milestone")
def send_partner_milestone_email(partner_user_id, milestone_label, bonus_kes, extras=""):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        partner_user = User.objects.get(pk=partner_user_id)
        email_service.send_partner_milestone(partner_user, milestone_label, bonus_kes, extras)
    except Exception as e:
        logger.error("Partner milestone email failed for user %s: %s", partner_user_id, e)


# ─── Scheduled tasks ────────────────────────────────────────────────────────

@shared_task(name="emails.send_weekly_reports_all")
def send_weekly_reports_all():
    """
    Send weekly performance reports to all eligible users.
    Runs every Monday via Celery Beat.
    """
    from datetime import timedelta

    from django.db.models import Count, Q

    from apps.accounts.models import UserProfile
    from apps.content.models import Post
    from apps.emails.services import email_service

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    profiles = UserProfile.objects.filter(
        subscription_status__in=("active", "trialing"),
    ).select_related("user")

    sent = 0
    for profile in profiles:
        user = profile.user
        # Gather basic weekly stats
        posts = Post.objects.filter(user=user, created_at__gte=week_ago)
        published = posts.filter(status="published").count()
        total = posts.count()

        report_data = {
            "posts_created": total,
            "posts_published": published,
            "plan": profile.get_plan_display() if hasattr(profile, "get_plan_display") else profile.plan,
            "period_start": week_ago.strftime("%b %d"),
            "period_end": now.strftime("%b %d, %Y"),
        }

        email_service.send_weekly_report(user, report_data)
        sent += 1

    logger.info("Weekly reports sent: %d", sent)
    return sent
