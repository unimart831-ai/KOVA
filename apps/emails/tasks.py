"""
Celery tasks for async email sending.

Every email in the platform goes through a Celery task so it never
blocks a request/response cycle.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)


# ─── Allauth async email task ────────────────────────────────────────────────

@shared_task(name="emails.send_allauth_email", bind=True, max_retries=3, default_retry_delay=30)
def send_allauth_email(self, template_prefix, email, context):
    """
    Send an allauth email (verification, password reset, etc.) asynchronously.

    Called by our custom AsyncEmailAccountAdapter instead of allauth's
    synchronous msg.send(). This prevents SMTP timeouts from killing
    Gunicorn workers during signup.
    """
    from allauth.account.adapter import DefaultAccountAdapter
    from django.contrib.sites.models import Site

    try:
        # Reconstruct the context that allauth's render_mail expects
        adapter = DefaultAccountAdapter()

        # Rebuild site object
        try:
            current_site = Site.objects.get_current()
        except Exception:
            from types import SimpleNamespace
            current_site = SimpleNamespace(
                name=context.get("current_site_name", "Kova Agent"),
                domain=context.get("current_site_domain", "kovaagent.com"),
            )
        context["current_site"] = current_site

        # Rebuild user if we have the email
        if "user_email" in context:
            from apps.accounts.models import User
            try:
                context["user"] = User.objects.get(email=context["user_email"])
            except User.DoesNotExist:
                pass

        # Use allauth's render_mail to get the proper subject/body/html
        msg = adapter.render_mail(template_prefix, email, context)
        msg.send()

        logger.info("Allauth email sent: template=%s to=%s", template_prefix, email)
    except Exception as exc:
        logger.error("Allauth email failed: template=%s to=%s error=%s", template_prefix, email, exc)
        raise self.retry(exc=exc)


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

@shared_task(name="emails.send_welcome", autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_welcome_email(user_id):
    """Send welcome email to a newly registered user."""
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_welcome(user)
    except Exception as e:
        logger.error("Welcome email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_payment_confirmation", autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_payment_confirmation_email(user_id, amount, plan, provider="stripe", receipt_number=""):
    from apps.accounts.models import User
    from apps.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_payment_confirmation(user, amount, plan, provider, receipt_number)
    except Exception as e:
        logger.error("Payment confirmation email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_payment_failed", autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
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


@shared_task(name="emails.send_partner_approved_no_account")
def send_partner_app_approved_no_account_email(to_email, full_name):
    from apps.emails.services import email_service
    try:
        email_service.send_partner_approved_no_account(to_email, full_name)
    except Exception as e:
        logger.error("Partner approved (no account) email failed for %s: %s", to_email, e)


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

@shared_task(name="emails.check_trial_expiry_emails")
def check_trial_expiry_emails():
    """
    Send trial expiry email sequence: Day 7, 3, 1, and 0 before trial end.

    Runs daily via Celery Beat. Uses day-of check to avoid duplicate sends
    (each day_marker only fires once per user since trial_ends_at is fixed).
    """
    from apps.accounts.models import UserProfile
    from apps.emails.services import email_service

    now = timezone.now()

    # Day markers: (days_until_expiry, subject_hint)
    day_markers = [7, 3, 1, 0]

    profiles = UserProfile.objects.filter(
        subscription_status="trialing",
        trial_ends_at__isnull=False,
    ).select_related("user")

    sent = 0
    for profile in profiles:
        days_left = (profile.trial_ends_at - now).days

        if days_left in day_markers:
            email_service.send_trial_ending(profile.user, days_left)
            sent += 1
            logger.info(
                "Trial expiry email sent: user=%s days_left=%d",
                profile.user.email, days_left,
            )

    logger.info("Trial expiry emails sent: %d", sent)
    return sent

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


# ─── Campaign & Sequence tasks ──────────────────────────────────────────────

@shared_task(name="emails.send_campaign", bind=True, max_retries=2, default_retry_delay=120)
def send_campaign_task(self, campaign_id):
    """
    Send an email campaign to all active subscribers on its target list.

    Flow: campaign.status → sending → iterate subscribers → send each → sent
    Creates an EmailLog per recipient and updates campaign metrics.
    """
    from apps.emails.models import EmailCampaign, EmailLog, EmailSubscriber
    from apps.emails.services import email_service

    try:
        campaign = EmailCampaign.objects.select_related("target_list", "user").get(pk=campaign_id)
    except EmailCampaign.DoesNotExist:
        logger.error("send_campaign_task: Campaign %s not found", campaign_id)
        return

    if campaign.status not in (EmailCampaign.Status.DRAFT, EmailCampaign.Status.SCHEDULED):
        logger.warning("send_campaign_task: Campaign %s status is %s, skipping", campaign_id, campaign.status)
        return

    if not campaign.target_list:
        logger.error("send_campaign_task: Campaign %s has no target list", campaign_id)
        campaign.status = EmailCampaign.Status.CANCELLED
        campaign.save(update_fields=["status"])
        return

    # Mark as sending
    campaign.status = EmailCampaign.Status.SENDING
    campaign.save(update_fields=["status"])

    subscribers = campaign.target_list.get_active_subscribers()
    sent_count = 0
    failed_count = 0

    for subscriber in subscribers.iterator():
        # Skip if subscriber has unsubscribed or bounced
        if subscriber.status != EmailSubscriber.Status.ACTIVE:
            continue

        try:
            # Build context for the campaign email
            context = {
                "campaign_name": campaign.name,
                "preview_text": campaign.preview_text,
                "html_content": campaign.html_content,
                "subscriber_name": subscriber.name or subscriber.email.split("@")[0],
                "subscriber_email": subscriber.email,
                "unsubscribe_url": f"{getattr(settings, 'SITE_URL', '')}/emails/unsubscribe/{subscriber.unsubscribe_token}/",
            }

            from_name = campaign.from_name or campaign.user.profile.company_name or "Kova Agent"
            from_email = f"{from_name} <{settings.DEFAULT_FROM_EMAIL.split('<')[-1].rstrip('>')}" if "<" in settings.DEFAULT_FROM_EMAIL else settings.DEFAULT_FROM_EMAIL

            log = EmailLog.objects.create(
                user=campaign.user,
                to_email=subscriber.email,
                from_email=settings.DEFAULT_FROM_EMAIL,
                email_type="promotional",
                subject=campaign.subject,
                status=EmailLog.Status.QUEUED,
                metadata={"campaign_id": str(campaign.pk), "subscriber_id": str(subscriber.pk)},
            )

            html_body = campaign.html_content
            text_body = campaign.text_content or strip_tags(html_body)

            msg = EmailMultiAlternatives(
                subject=campaign.subject,
                body=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[subscriber.email],
            )
            if campaign.reply_to:
                msg.reply_to = [campaign.reply_to]
            msg.attach_alternative(html_body, "text/html")

            # Unsubscribe headers
            unsub_url = context["unsubscribe_url"]
            msg.extra_headers["List-Unsubscribe"] = f"<{unsub_url}>"
            msg.extra_headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"

            # Message-ID for webhook correlation
            from_domain = settings.DEFAULT_FROM_EMAIL.split("@")[-1].rstrip(">")
            msg.extra_headers["Message-ID"] = f"<{log.pk}@{from_domain}>"

            msg.send(fail_silently=False)

            log.status = EmailLog.Status.SENT
            log.sent_at = timezone.now()
            log.save(update_fields=["status", "sent_at"])
            sent_count += 1

        except Exception as e:
            logger.error("Campaign %s: failed to send to %s: %s", campaign_id, subscriber.email, e)
            failed_count += 1
            if 'log' in locals():
                log.status = EmailLog.Status.FAILED
                log.error_message = str(e)[:500]
                log.failed_at = timezone.now()
                log.save(update_fields=["status", "error_message", "failed_at"])

    # Update campaign metrics and mark as sent
    campaign.total_sent = sent_count
    campaign.status = EmailCampaign.Status.SENT
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=["total_sent", "status", "sent_at"])

    logger.info("Campaign %s sent: %d delivered, %d failed", campaign.name, sent_count, failed_count)
    return {"sent": sent_count, "failed": failed_count}


@shared_task(name="emails.process_email_sequences")
def process_email_sequences():
    """
    Process due email sequence steps.

    Finds all active enrollments where next_send_at <= now,
    sends the current step email, and advances the enrollment.

    Runs every 30 minutes via Celery Beat.
    """
    from apps.emails.models import EmailSequence, EmailSequenceStep, SequenceEnrollment
    from apps.emails.services import email_service

    now = timezone.now()
    due_enrollments = SequenceEnrollment.objects.filter(
        status=SequenceEnrollment.Status.ACTIVE,
        next_send_at__lte=now,
        sequence__is_active=True,
    ).select_related("sequence", "subscriber", "subscriber__user")

    sent = 0
    completed = 0

    for enrollment in due_enrollments:
        try:
            # Get the current step
            step = EmailSequenceStep.objects.filter(
                sequence=enrollment.sequence,
                step_number=enrollment.current_step,
            ).first()

            if not step:
                # No more steps — mark as completed
                enrollment.status = SequenceEnrollment.Status.COMPLETED
                enrollment.completed_at = now
                enrollment.next_send_at = None
                enrollment.save(update_fields=["status", "completed_at", "next_send_at"])
                completed += 1
                continue

            subscriber = enrollment.subscriber

            # Skip if subscriber is no longer active
            if subscriber.status != "active":
                enrollment.status = SequenceEnrollment.Status.CANCELLED
                enrollment.save(update_fields=["status"])
                continue

            # Send the step email
            context = {
                "subscriber_name": subscriber.name or subscriber.email.split("@")[0],
                "subscriber_email": subscriber.email,
                "sequence_name": enrollment.sequence.name,
                "step_number": step.step_number,
                "html_content": step.html_content,
                "unsubscribe_url": f"{getattr(settings, 'SITE_URL', '')}/emails/unsubscribe/{subscriber.unsubscribe_token}/",
            }

            email_service._send(
                email_type="promotional",
                to_email=subscriber.email,
                context=context,
                user=subscriber.user,
                subject=step.subject,
                metadata={
                    "sequence_id": str(enrollment.sequence.pk),
                    "step_number": step.step_number,
                    "enrollment_id": str(enrollment.pk),
                },
            )
            sent += 1

            # Advance to next step
            next_step = EmailSequenceStep.objects.filter(
                sequence=enrollment.sequence,
                step_number=enrollment.current_step + 1,
            ).first()

            if next_step:
                from datetime import timedelta
                delay = timedelta(days=next_step.delay_days, hours=next_step.delay_hours)
                enrollment.current_step += 1
                enrollment.next_send_at = now + delay
                enrollment.save(update_fields=["current_step", "next_send_at"])
            else:
                # That was the last step
                enrollment.current_step += 1
                enrollment.status = SequenceEnrollment.Status.COMPLETED
                enrollment.completed_at = now
                enrollment.next_send_at = None
                enrollment.save(update_fields=["current_step", "status", "completed_at", "next_send_at"])
                completed += 1

        except Exception as e:
            logger.error(
                "Sequence step failed: enrollment=%s step=%d error=%s",
                enrollment.pk, enrollment.current_step, e,
            )

    logger.info("Email sequences processed: %d sent, %d completed", sent, completed)
    return {"sent": sent, "completed": completed}
