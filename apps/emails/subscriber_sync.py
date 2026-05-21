"""
Automatic email subscriber acquisition — keeps lists populated without manual entry.

Sources: Kova Form leads, Lead Inbox, manual adds, pixel/API leads.
"""

import logging

from django.db import transaction
from django.utils import timezone

logger = logging.getLogger(__name__)

DEFAULT_LIST_NAME = "All contacts"


def ensure_default_list(user):
    """Return the user's primary list — auto-created smart list of all active subscribers."""
    from apps.emails.models import EmailList

    email_list = EmailList.objects.filter(user=user, name=DEFAULT_LIST_NAME).first()
    if email_list:
        email_list.refresh_count()
        return email_list

    email_list = EmailList.objects.create(
        user=user,
        name=DEFAULT_LIST_NAME,
        description="All active email subscribers — auto-synced from leads and forms.",
        is_smart=True,
        filter_rules={},
    )
    email_list.refresh_count()
    return email_list


def upsert_subscriber(
    user,
    email,
    *,
    name="",
    source=None,
    lead=None,
    source_form=None,
    tags=None,
):
    """
    Create or update an EmailSubscriber and attach to the default list.

    Returns (subscriber, created).
    """
    from apps.emails.automation import is_mailable_email
    from apps.emails.models import EmailSubscriber

    if not email or not email.strip():
        return None, False

    email = email.strip().lower()
    if not is_mailable_email(email):
        return None, False
    source = source or EmailSubscriber.Source.LEAD_SYNC

    defaults = {
        "name": (name or "").strip(),
        "source": source,
        "status": EmailSubscriber.Status.ACTIVE,
    }
    if lead:
        defaults["lead"] = lead
    if source_form:
        defaults["source_form"] = source_form

    subscriber, created = EmailSubscriber.objects.get_or_create(
        user=user,
        email=email,
        defaults=defaults,
    )

    updated_fields = []
    if not created:
        if name and not subscriber.name:
            subscriber.name = name.strip()
            updated_fields.append("name")
        if lead and not subscriber.lead_id:
            subscriber.lead = lead
            updated_fields.append("lead")
        if source_form and not subscriber.source_form_id:
            subscriber.source_form = source_form
            updated_fields.append("source_form")
        if subscriber.status == EmailSubscriber.Status.UNSUBSCRIBED:
            pass  # respect unsubscribe — do not reactivate
        if updated_fields:
            subscriber.save(update_fields=updated_fields)

    if tags:
        merged = list(set((subscriber.tags or []) + tags))
        if merged != (subscriber.tags or []):
            subscriber.tags = merged
            subscriber.save(update_fields=["tags"])

    _add_to_default_list(user, subscriber)
    if created:
        enroll_subscriber_in_sequences(subscriber)

    return subscriber, created


def sync_lead(lead):
    """Sync a single Lead record to EmailSubscriber."""
    from apps.emails.models import EmailSubscriber
    from apps.leads.models import Lead

    if not lead.email:
        return None, False

    source_map = {
        Lead.Source.FORM_SUBMISSION: EmailSubscriber.Source.KOVA_FORM,
        Lead.Source.MANUAL: EmailSubscriber.Source.MANUAL,
        Lead.Source.IMPORT: EmailSubscriber.Source.IMPORT,
        Lead.Source.API: EmailSubscriber.Source.API,
        Lead.Source.SOCIAL_DM: EmailSubscriber.Source.LEAD_SYNC,
        Lead.Source.SOCIAL_COMMENT: EmailSubscriber.Source.LEAD_SYNC,
    }
    source = source_map.get(lead.source_type, EmailSubscriber.Source.LEAD_SYNC)

    return upsert_subscriber(
        lead.user,
        lead.email,
        name=lead.name or "",
        source=source,
        lead=lead,
        source_form=getattr(lead, "source_form", None),
        tags=["lead"],
    )


def sync_leads_for_user(user):
    """Backfill subscribers from all leads with email addresses."""
    from apps.leads.models import Lead

    created = 0
    updated = 0
    for lead in Lead.objects.filter(user=user).exclude(email="").iterator():
        _, was_created = sync_lead(lead)
        if was_created:
            created += 1
        else:
            updated += 1

    default_list = ensure_default_list(user)
    default_list.refresh_count()
    return {"created": created, "synced": updated + created, "list_count": default_list.subscriber_count}


def _add_to_default_list(user, subscriber):
    """Add subscriber to the default manual backup list membership for non-smart sends."""
    from apps.emails.models import EmailList, EmailSubscriber

    if subscriber.status != EmailSubscriber.Status.ACTIVE:
        return

    email_list = ensure_default_list(user)
    if not email_list.is_smart:
        email_list.subscribers.add(subscriber)
        email_list.refresh_count()


def enroll_subscriber_in_sequences(subscriber):
    """Auto-enroll new subscribers in matching active email sequences."""
    from datetime import timedelta

    from apps.emails.models import (
        EmailSequence,
        EmailSequenceStep,
        SequenceEnrollment,
    )

    trigger_types = [EmailSequence.TriggerType.SUBSCRIBER_ADDED]
    if subscriber.source == subscriber.Source.KOVA_FORM:
        trigger_types.append(EmailSequence.TriggerType.FORM_SUBMISSION)

    sequences = EmailSequence.objects.filter(
        user=subscriber.user,
        is_active=True,
        trigger_type__in=trigger_types,
    )

    now = timezone.now()
    for sequence in sequences:
        config = sequence.trigger_config or {}
        if sequence.trigger_type == EmailSequence.TriggerType.FORM_SUBMISSION:
            form_id = config.get("form_id")
            if form_id and subscriber.source_form_id:
                if str(subscriber.source_form_id) != str(form_id):
                    continue

        enrollment, created = SequenceEnrollment.objects.get_or_create(
            sequence=sequence,
            subscriber=subscriber,
            defaults={"current_step": 1, "status": SequenceEnrollment.Status.ACTIVE},
        )
        if not created:
            continue

        first_step = EmailSequenceStep.objects.filter(sequence=sequence, step_number=1).first()
        if first_step:
            delay = timedelta(days=first_step.delay_days, hours=first_step.delay_hours)
            enrollment.next_send_at = now + delay
            enrollment.save(update_fields=["next_send_at"])


def bootstrap_email_marketing(user):
    """One-call setup: default list + lead sync + welcome sequence + pending sends."""
    from apps.emails.automation import bootstrap_email_automation

    return bootstrap_email_automation(user)
