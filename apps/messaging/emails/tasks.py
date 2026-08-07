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

    Renders templates directly (bypasses adapter.render_mail which needs
    a request context that doesn't exist in Celery workers).
    """
    from django.template.loader import render_to_string, TemplateDoesNotExist

    try:
        # Build render context with user object if available
        render_ctx = dict(context)
        if "user_email" in context:
            from apps.core.accounts.models import User
            try:
                render_ctx["user"] = User.objects.get(email=context["user_email"])
            except User.DoesNotExist:
                pass

        # Render subject
        subject = render_to_string(f"{template_prefix}_subject.txt", render_ctx)
        subject = " ".join(subject.splitlines()).strip()

        # Render bodies (HTML + plain text)
        bodies = {}
        for ext in ["html", "txt"]:
            try:
                bodies[ext] = render_to_string(
                    f"{template_prefix}_message.{ext}", render_ctx
                ).strip()
            except TemplateDoesNotExist:
                if ext == "txt" and not bodies:
                    raise

        from_email = settings.DEFAULT_FROM_EMAIL

        # Build message
        if "txt" in bodies:
            msg = EmailMultiAlternatives(subject, bodies["txt"], from_email, [email])
            if "html" in bodies:
                msg.attach_alternative(bodies["html"], "text/html")
        else:
            from django.core.mail import EmailMessage
            msg = EmailMessage(subject, bodies["html"], from_email, [email])
            msg.content_subtype = "html"

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
    from apps.messaging.emails.services import email_service

    user = None
    if user_id:
        from apps.core.accounts.models import User
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
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_welcome(user)
    except Exception as e:
        logger.error("Welcome email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_payment_confirmation", autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_payment_confirmation_email(user_id, amount, plan, provider="stripe", receipt_number=""):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_payment_confirmation(user, amount, plan, provider, receipt_number)
    except Exception as e:
        logger.error("Payment confirmation email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_payment_failed", autoretry_for=(Exception,), retry_backoff=60, max_retries=3)
def send_payment_failed_email(user_id, plan=None):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_payment_failed(user, plan)
    except Exception as e:
        logger.error("Payment failed email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_plan_changed")
def send_plan_changed_email(user_id, old_plan, new_plan):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_plan_changed(user, old_plan, new_plan)
    except Exception as e:
        logger.error("Plan changed email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_subscription_canceled")
def send_subscription_canceled_email(user_id):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_subscription_canceled(user)
    except Exception as e:
        logger.error("Subscription canceled email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_payment_reminder")
def send_payment_reminder_email(user_id, days_until_expiry):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_payment_reminder(user, days_until_expiry)
    except Exception as e:
        logger.error("Payment reminder email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_team_invitation")
def send_team_invitation_email(to_email, inviter_name, team_name, invite_url):
    from apps.messaging.emails.services import email_service
    try:
        email_service.send_team_invitation(to_email, inviter_name, team_name, invite_url)
    except Exception as e:
        logger.error("Team invitation email failed for %s: %s", to_email, e)


@shared_task(name="emails.send_weekly_report")
def send_weekly_report_email(user_id, report_data):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_weekly_report(user, report_data)
    except Exception as e:
        logger.error("Weekly report email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_feature_announcement")
def send_feature_announcement_email(user_id, feature_title, feature_description, cta_url=""):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_feature_announcement(user, feature_title, feature_description, cta_url)
    except Exception as e:
        logger.error("Feature announcement email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_usage_warning")
def send_usage_warning_email(user_id, resource, current, limit):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_usage_warning(user, resource, current, limit)
    except Exception as e:
        logger.error("Usage warning email failed for user %s: %s", user_id, e)


# ─── Partner emails ─────────────────────────────────────────────────────────

@shared_task(name="emails.send_partner_app_received")
def send_partner_app_received_email(to_email, full_name, user_id=None):
    from apps.messaging.emails.services import email_service
    user = None
    if user_id:
        from apps.core.accounts.models import User
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
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        user = User.objects.get(pk=user_id)
        email_service.send_partner_application_approved(user, referral_code)
    except Exception as e:
        logger.error("Partner app approved email failed for user %s: %s", user_id, e)


@shared_task(name="emails.send_partner_approved_no_account")
def send_partner_app_approved_no_account_email(to_email, full_name):
    from apps.messaging.emails.services import email_service
    try:
        email_service.send_partner_approved_no_account(to_email, full_name)
    except Exception as e:
        logger.error("Partner approved (no account) email failed for %s: %s", to_email, e)


@shared_task(name="emails.send_partner_app_rejected")
def send_partner_app_rejected_email(to_email, full_name, user_id=None, reason=""):
    from apps.messaging.emails.services import email_service
    user = None
    if user_id:
        from apps.core.accounts.models import User
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
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        partner_user = User.objects.get(pk=partner_user_id)
        email_service.send_partner_new_referral(partner_user, referred_email, total_referrals)
    except Exception as e:
        logger.error("Partner new referral email failed for user %s: %s", partner_user_id, e)


@shared_task(name="emails.send_partner_milestone")
def send_partner_milestone_email(partner_user_id, milestone_label, bonus_kes, extras=""):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service
    try:
        partner_user = User.objects.get(pk=partner_user_id)
        email_service.send_partner_milestone(partner_user, milestone_label, bonus_kes, extras)
    except Exception as e:
        logger.error("Partner milestone email failed for user %s: %s", partner_user_id, e)


@shared_task(name="emails.send_marketplace_seller_welcome")
def send_marketplace_seller_welcome_email(user_id, marketplace_name, marketplace_slug="", branding=None):
    from apps.core.accounts.models import User
    from apps.messaging.emails.services import email_service

    try:
        user = User.objects.get(pk=user_id)
        email_service.send_marketplace_seller_welcome(user, marketplace_name, branding or {})
    except Exception as e:
        logger.error(
            "Marketplace seller welcome email failed for user %s (%s): %s",
            user_id, marketplace_slug, e,
        )


# ─── Scheduled tasks ────────────────────────────────────────────────────────

@shared_task(name="emails.check_trial_expiry_emails")
def check_trial_expiry_emails():
    """
    Send trial expiry email sequence: Day 7, 3, 1, and 0 before trial end.

    Runs daily via Celery Beat. Uses day-of check to avoid duplicate sends
    (each day_marker only fires once per user since trial_ends_at is fixed).
    """
    from apps.core.accounts.models import UserProfile
    from apps.messaging.emails.services import email_service

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

    from apps.core.accounts.models import UserProfile
    from apps.create.content.models import Post
    from apps.messaging.emails.services import email_service

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    profiles = UserProfile.objects.filter(
        subscription_status__in=("active", "trialing"),
    ).select_related("user")

    # Pull the approved Kova digest once; inlined into every recipient's email.
    # If nothing has been approved for this cycle, personal section sends alone.
    from apps.create.agents.educator_agent import get_latest_sendable_digest
    digest = get_latest_sendable_digest()
    digest_html = digest.combined_html() if digest else ""

    sent = 0
    for profile in profiles:
        user = profile.user
        posts = Post.objects.filter(user=user, created_at__gte=week_ago)
        published = posts.filter(status="published").count()
        total = posts.count()

        report_data = {
            "posts_created": total,
            "posts_published": published,
            "plan": profile.get_plan_display() if hasattr(profile, "get_plan_display") else profile.plan,
            "period_start": week_ago.strftime("%b %d"),
            "period_end": now.strftime("%b %d, %Y"),
            "kova_digest": digest_html,
        }

        email_service.send_weekly_report(user, report_data)
        sent += 1

    if digest and digest_html:
        from django.utils import timezone as _tz
        digest.status = digest.Status.SENT
        digest.sent_at = _tz.now()
        digest.save(update_fields=["status", "sent_at", "updated_at"])

    logger.info("Weekly reports sent: %d (digest=%s)", sent, digest.week_end if digest else None)
    return sent


@shared_task(name="emails.send_monthly_reports_all")
def send_monthly_reports_all():
    """
    Send monthly attribution performance reports to all eligible users.
    Uses the full gather_report_data pipeline for rich attribution data.
    Runs once a month via Celery Beat.
    """
    from apps.core.accounts.models import UserProfile
    from apps.insight.analytics.reports import gather_report_data
    from apps.messaging.emails.services import email_service

    profiles = UserProfile.objects.filter(
        subscription_status__in=("active", "trialing"),
    ).select_related("user")

    sent = 0
    for profile in profiles:
        user = profile.user
        try:
            report_data = gather_report_data(user, days=30)
            email_service.send_monthly_report(user, report_data)
            sent += 1
        except Exception:
            logger.exception("Monthly report failed for user %s", user.email)

    logger.info("Monthly reports sent: %d", sent)
    return sent


# ─── Campaign & Sequence tasks ──────────────────────────────────────────────

@shared_task(name="emails.send_campaign", bind=True, max_retries=2, default_retry_delay=120)
def send_campaign_task(self, campaign_id):
    """
    Send an email campaign to all active subscribers on its target list.

    Flow: campaign.status → sending → iterate subscribers → send each → sent
    Creates an EmailLog per recipient and updates campaign metrics.
    """
    from apps.messaging.emails.models import EmailCampaign, EmailLog, EmailSubscriber
    from apps.messaging.emails.services import email_service

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

        from apps.messaging.emails.automation import is_mailable_email
        if not is_mailable_email(subscriber.email):
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
    from apps.messaging.emails.models import EmailSequence, EmailSequenceStep, SequenceEnrollment
    from apps.messaging.emails.services import email_service

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

            from apps.messaging.emails.automation import (
                ai_generate_sequence_step,
                is_mailable_email,
                send_marketing_email_to_subscriber,
            )

            if not is_mailable_email(subscriber.email):
                enrollment.status = SequenceEnrollment.Status.CANCELLED
                enrollment.save(update_fields=["status"])
                continue

            html_content = step.html_content
            if not html_content.strip() or step.ai_generated:
                html_content = ai_generate_sequence_step(
                    subscriber.user, subscriber, enrollment.sequence, step,
                )

            send_marketing_email_to_subscriber(
                subscriber,
                step.subject,
                html_content,
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


@shared_task(name="emails.sync_leads_to_subscribers_all")
def sync_leads_to_subscribers_all():
    """
    Daily backfill: sync all leads with emails into EmailSubscriber records.
    Keeps lists populated even if a signal was missed.
    """
    from apps.core.accounts.models import UserProfile
    from apps.messaging.emails.subscriber_sync import sync_leads_for_user

    profiles = UserProfile.objects.filter(
        subscription_status__in=("active", "trialing"),
    ).select_related("user")

    total_synced = 0
    for profile in profiles:
        try:
            result = sync_leads_for_user(profile.user)
            total_synced += result.get("synced", 0)
        except Exception:
            logger.exception("Lead→subscriber sync failed for user %s", profile.user.email)

    logger.info("Lead→subscriber sync complete: %d contacts processed", total_synced)
    return total_synced


@shared_task(name="emails.process_scheduled_campaigns")
def process_scheduled_campaigns():
    """Send campaigns that reached their scheduled_at time."""
    from apps.messaging.emails.models import EmailCampaign

    now = timezone.now()
    due = EmailCampaign.objects.filter(
        status=EmailCampaign.Status.SCHEDULED,
        scheduled_at__lte=now,
    )
    queued = 0
    for campaign in due[:50]:
        send_campaign_task.delay(str(campaign.pk))
        queued += 1
    return queued


@shared_task(name="emails.retry_pending_auto_campaigns")
def retry_pending_auto_campaigns():
    """Send AI-generated drafts once subscriber lists have contacts."""
    from apps.messaging.emails.automation import retry_all_pending_campaigns

    return retry_all_pending_campaigns()
