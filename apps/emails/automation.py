"""
Email marketing automation — zero-setup sends for MSME users.

Handles: AI content generation, auto-send gates, welcome sequences,
performance-recycle → campaign, and pending draft retries.
"""

import json
import logging
import re

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

WELCOME_SEQUENCE_NAME = "Welcome new contacts"
PLACEHOLDER_DOMAINS = ("kova.page",)


def is_mailable_email(email: str) -> bool:
    """Skip WhatsApp/page placeholder addresses that cannot receive mail."""
    if not email or "@" not in email:
        return False
    local, domain = email.strip().lower().rsplit("@", 1)
    if domain in PLACEHOLDER_DOMAINS:
        return False
    if local.startswith(("wa_", "fb_", "noemail_", "noreply")):
        return False
    return True


def auto_email_enabled(user) -> bool:
    profile = getattr(user, "profile", None)
    if not profile:
        return True
    return getattr(profile, "auto_email_marketing", True)


def bootstrap_email_automation(user):
    """Full setup: list, lead sync, welcome sequence, pending campaign retry."""
    from apps.emails.subscriber_sync import bootstrap_email_marketing

    result = bootstrap_email_marketing(user)
    ensure_welcome_sequence(user)
    pending = retry_pending_campaigns_for_user(user)
    result["pending_sent"] = pending.get("sent", 0)
    return result


def ensure_welcome_sequence(user):
    """
    Create a 3-step welcome drip for new subscribers.
    Always created — core automation, not counted against manual sequence limits.
    """
    from apps.emails.models import EmailSequence, EmailSequenceStep

    sequence, created = EmailSequence.objects.get_or_create(
        user=user,
        name=WELCOME_SEQUENCE_NAME,
        defaults={
            "trigger_type": EmailSequence.TriggerType.SUBSCRIBER_ADDED,
            "trigger_config": {},
            "is_active": True,
        },
    )
    if not created and not sequence.is_active:
        sequence.is_active = True
        sequence.save(update_fields=["is_active"])

    if not sequence.steps.exists():
        steps = [
            (1, 0, 0, "Welcome — glad you're here"),
            (2, 2, 0, "Something useful from us"),
            (3, 5, 0, "Stay in touch"),
        ]
        for num, days, hours, subject in steps:
            EmailSequenceStep.objects.create(
                sequence=sequence,
                step_number=num,
                delay_days=days,
                delay_hours=hours,
                subject=subject,
                html_content="",
                ai_generated=True,
            )

    enroll_existing_subscribers(sequence)
    return sequence


def enroll_existing_subscribers(sequence):
    """Backfill enrollments when welcome sequence is first created."""
    from datetime import timedelta

    from apps.emails.models import EmailSequenceStep, EmailSubscriber, SequenceEnrollment

    first_step = EmailSequenceStep.objects.filter(sequence=sequence, step_number=1).first()
    if not first_step:
        return 0

    now = timezone.now()
    delay = timedelta(days=first_step.delay_days, hours=first_step.delay_hours)
    enrolled = 0

    subscribers = EmailSubscriber.objects.filter(
        user=sequence.user,
        status=EmailSubscriber.Status.ACTIVE,
    )
    for subscriber in subscribers.iterator():
        if not is_mailable_email(subscriber.email):
            continue
        _, was_created = SequenceEnrollment.objects.get_or_create(
            sequence=sequence,
            subscriber=subscriber,
            defaults={
                "current_step": 1,
                "status": SequenceEnrollment.Status.ACTIVE,
                "next_send_at": now + delay,
            },
        )
        if was_created:
            enrolled += 1
    return enrolled


def ai_generate_email_content(user, prompt, *, source_post=None):
    """Generate subject + HTML body via LLM. Returns dict or None."""
    try:
        from apps.agents.llm_router import call_llm

        profile = getattr(user, "profile", None)
        brand = ""
        if profile:
            brand = (
                f"Business: {profile.company_name or 'local business'}. "
                f"Voice: {profile.brand_voice or 'warm and professional'}. "
                f"Industry: {profile.industry or 'general'}."
            )

        post_context = ""
        if source_post:
            post_context = f"\nInspired by this top post ({source_post.platform}): \"{source_post.content_text[:400]}\"\n"

        llm_prompt = (
            "Write a marketing email for a small business subscriber list.\n\n"
            f"{brand}\n"
            f"Goal: {prompt}\n"
            f"{post_context}\n"
            "Return ONLY valid JSON:\n"
            '{"subject": "max 60 chars", "preview_text": "inbox preview", '
            '"body_html": "<p>200-350 words, simple HTML paragraphs only</p>"}'
        )

        response = call_llm(prompt=llm_prompt, task="create.write", user=user, json_mode=True)
        text = response.get("text", "").strip()
        if text.startswith("```"):
            text = re.sub(r"^```(?:json)?\n?", "", text)
            text = re.sub(r"\n?```$", "", text)
        return json.loads(text)
    except Exception as exc:
        logger.error("AI email generation failed for %s: %s", user.email, exc)
        return None


def ai_generate_sequence_step(user, subscriber, sequence, step):
    """Generate sequence step HTML when empty."""
    profile = getattr(user, "profile", None)
    business = getattr(profile, "company_name", "") if profile else "our business"
    prompt = (
        f"Write step {step.step_number} of the '{sequence.name}' email sequence.\n"
        f"Business: {business}. Subscriber: {subscriber.name or subscriber.email}.\n"
        f"Subject line: {step.subject}\n"
        "Keep under 150 words, warm and helpful, one soft CTA.\n"
        'Return JSON: {"body_html": "<p>...</p>"}'
    )
    result = ai_generate_email_content(user, prompt)
    if result:
        return result.get("body_html") or result.get("body") or f"<p>{step.subject}</p>"
    return f"<p>{step.subject}</p>"


def create_email_campaign(
    user,
    *,
    name,
    subject,
    html_content,
    preview_text="",
    source_post=None,
    ai_generated=True,
    auto_send=True,
):
    """Create EmailCampaign on default list; optionally queue send."""
    from apps.emails.models import EmailCampaign
    from apps.emails.subscriber_sync import ensure_default_list

    default_list = ensure_default_list(user)
    campaign = EmailCampaign.objects.create(
        user=user,
        name=name[:200],
        subject=subject[:255],
        preview_text=(preview_text or subject)[:255],
        html_content=html_content,
        text_content=strip_tags(html_content),
        from_name=(getattr(getattr(user, "profile", None), "company_name", "") or "")[:200],
        target_list=default_list,
        status=EmailCampaign.Status.DRAFT,
        ai_generated=ai_generated,
        source_post=source_post,
    )

    if auto_send and auto_email_enabled(user):
        try_auto_send_campaign(campaign)

    return campaign


def try_auto_send_campaign(campaign):
    """
    Send immediately if plan allows and list has mailable subscribers.
    Returns dict with status.
    """
    from apps.billing.models import get_plan_limits
    from apps.emails.models import EmailCampaign, EmailSubscriber

    if campaign.status not in (EmailCampaign.Status.DRAFT, EmailCampaign.Status.SCHEDULED):
        return {"skipped": "wrong_status"}

    if not auto_email_enabled(campaign.user):
        return {"skipped": "auto_disabled"}

    if not campaign.target_list:
        return {"skipped": "no_list"}

    mailable = [
        s for s in campaign.target_list.get_active_subscribers()
        if s.status == EmailSubscriber.Status.ACTIVE and is_mailable_email(s.email)
    ]
    if not mailable:
        return {"skipped": "no_subscribers"}

    from apps.billing.models import get_user_plan_limits

    limits = get_user_plan_limits(campaign.user)
    monthly_limit = limits.get("email_campaigns_per_month")
    if monthly_limit is not None:
        month_start = timezone.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        sent_this_month = EmailCampaign.objects.filter(
            user=campaign.user,
            status=EmailCampaign.Status.SENT,
            sent_at__gte=month_start,
        ).count()
        if sent_this_month >= monthly_limit:
            return {"skipped": "plan_limit"}

    from apps.emails.tasks import send_campaign_task

    send_campaign_task.delay(str(campaign.pk))
    return {"queued": True, "recipients": len(mailable)}


def create_ai_campaign(user, prompt, *, source_post=None, name=None, auto_send=True):
    """AI-generate content and create campaign."""
    generated = ai_generate_email_content(user, prompt, source_post=source_post)
    if not generated:
        generated = {
            "subject": prompt[:60],
            "preview_text": prompt[:120],
            "body_html": f"<p>{prompt}</p>",
        }

    return create_email_campaign(
        user,
        name=name or f"Auto: {generated.get('subject', prompt[:40])}",
        subject=generated.get("subject", prompt[:60]),
        html_content=generated.get("body_html", f"<p>{prompt}</p>"),
        preview_text=generated.get("preview_text", ""),
        source_post=source_post,
        ai_generated=True,
        auto_send=auto_send,
    )


def send_performance_recycle(recycle):
    """Turn a PerformanceRecycle draft into a sent EmailCampaign."""
    from apps.analytics.models import PerformanceRecycle
    from apps.emails.models import EmailCampaign

    if recycle.email_campaign_id:
        campaign = recycle.email_campaign
        result = try_auto_send_campaign(campaign)
        if result.get("queued"):
            recycle.status = PerformanceRecycle.Status.SENT
            recycle.sent_at = timezone.now()
            recycle.save(update_fields=["status", "sent_at"])
        return campaign

    user = recycle.user
    post = recycle.source_post

    campaign = create_email_campaign(
        user,
        name=f"Top post → email ({post.platform})",
        subject=recycle.email_subject or "What's working for us",
        html_content=recycle.email_body_html or f"<p>{post.content_text}</p>",
        source_post=post,
        ai_generated=True,
        auto_send=False,
    )

    recycle.email_campaign = campaign
    if try_auto_send_campaign(campaign).get("queued"):
        recycle.status = PerformanceRecycle.Status.SENT
        recycle.sent_at = timezone.now()
    recycle.save(update_fields=["email_campaign", "status", "sent_at"])
    return campaign


def retry_pending_campaigns_for_user(user):
    """Send AI drafts that were waiting for subscribers."""
    from apps.emails.models import EmailCampaign

    sent = 0
    drafts = EmailCampaign.objects.filter(
        user=user,
        status=EmailCampaign.Status.DRAFT,
        ai_generated=True,
    ).order_by("created_at")[:5]

    for campaign in drafts:
        result = try_auto_send_campaign(campaign)
        if result.get("queued"):
            sent += 1
    return {"sent": sent}


def retry_all_pending_campaigns():
    """Daily: send AI drafts once lists have subscribers."""
    from apps.accounts.models import UserProfile

    total = 0
    profiles = UserProfile.objects.filter(
        subscription_status__in=("active", "trialing"),
        auto_email_marketing=True,
    ).select_related("user")

    for profile in profiles:
        try:
            total += retry_pending_campaigns_for_user(profile.user).get("sent", 0)
        except Exception:
            logger.exception("Pending campaign retry failed for %s", profile.user.email)
    return total


def send_marketing_email_to_subscriber(subscriber, subject, html_content, metadata=None):
    """Send one marketing email with raw HTML (sequences, one-offs)."""
    from apps.emails.models import EmailLog, EmailSubscriber

    if subscriber.status != EmailSubscriber.Status.ACTIVE:
        return None
    if not is_mailable_email(subscriber.email):
        return None

    log = EmailLog.objects.create(
        user=subscriber.user,
        to_email=subscriber.email,
        from_email=settings.DEFAULT_FROM_EMAIL,
        email_type="promotional",
        subject=subject,
        status=EmailLog.Status.QUEUED,
        metadata=metadata or {},
    )

    text_body = strip_tags(html_content)
    msg = EmailMultiAlternatives(
        subject=subject,
        body=text_body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[subscriber.email],
    )
    msg.attach_alternative(html_content, "text/html")

    unsub_url = f"{getattr(settings, 'SITE_URL', '')}/emails/unsubscribe/{subscriber.unsubscribe_token}/"
    msg.extra_headers["List-Unsubscribe"] = f"<{unsub_url}>"
    msg.extra_headers["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    from_domain = settings.DEFAULT_FROM_EMAIL.split("@")[-1].rstrip(">")
    msg.extra_headers["Message-ID"] = f"<{log.pk}@{from_domain}>"

    msg.send(fail_silently=False)
    log.status = EmailLog.Status.SENT
    log.sent_at = timezone.now()
    log.save(update_fields=["status", "sent_at"])
    return log
