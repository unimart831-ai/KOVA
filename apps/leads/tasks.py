"""
Lead nurture Celery tasks — process timed follow-up sequences.
"""

import logging
from datetime import timedelta

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="leads.process_nurture_steps")
def process_nurture_steps():
    """
    Process due nurture sequence steps.

    Finds all active lead enrollments where next_step_at <= now,
    executes the current step, and advances to the next.

    Runs every 30 minutes via Celery Beat.
    """
    from apps.leads.models import LeadActivity, LeadEnrollment, NurtureStep

    now = timezone.now()
    due = LeadEnrollment.objects.filter(
        completed=False,
        paused=False,
        next_step_at__lte=now,
        sequence__is_active=True,
    ).select_related("lead", "lead__user", "sequence")

    processed = 0
    completed = 0

    for enrollment in due:
        try:
            step = NurtureStep.objects.filter(
                sequence=enrollment.sequence,
                order=enrollment.current_step,
            ).first()

            if not step:
                # No more steps — done
                enrollment.completed = True
                enrollment.save(update_fields=["completed"])
                completed += 1
                continue

            lead = enrollment.lead

            # Skip if lead is already converted or lost
            if lead.status in ("converted", "lost"):
                enrollment.completed = True
                enrollment.save(update_fields=["completed"])
                completed += 1
                continue

            # Execute the step action
            if step.action_type == NurtureStep.ActionType.SEND_EMAIL:
                _send_nurture_email(lead, step)
            elif step.action_type == NurtureStep.ActionType.ADD_TAG:
                if step.tag_value and step.tag_value not in lead.tags:
                    lead.tags.append(step.tag_value)
                    lead.save(update_fields=["tags"])
                    LeadActivity.objects.create(
                        lead=lead,
                        activity_type=LeadActivity.ActivityType.TAG_ADDED,
                        description=f"Auto-tag from nurture: {step.tag_value}",
                    )
            elif step.action_type == NurtureStep.ActionType.CHANGE_STATUS:
                if step.status_value:
                    old = lead.status
                    lead.status = step.status_value
                    lead.save(update_fields=["status"])
                    LeadActivity.objects.create(
                        lead=lead,
                        activity_type=LeadActivity.ActivityType.STATUS_CHANGED,
                        description=f"Nurture auto-status: {old} → {step.status_value}",
                    )

            processed += 1

            # Advance to next step
            next_step = NurtureStep.objects.filter(
                sequence=enrollment.sequence,
                order=enrollment.current_step + 1,
            ).first()

            if next_step:
                enrollment.current_step += 1
                enrollment.next_step_at = now + timedelta(hours=next_step.delay_hours)
                enrollment.save(update_fields=["current_step", "next_step_at"])
            else:
                enrollment.completed = True
                enrollment.save(update_fields=["completed"])
                completed += 1

        except Exception as e:
            logger.error(
                "Nurture step failed: enrollment=%s step=%d error=%s",
                enrollment.pk, enrollment.current_step, e,
            )

    logger.info("Nurture steps processed: %d executed, %d completed", processed, completed)
    return {"processed": processed, "completed": completed}


def _send_nurture_email(lead, step):
    """Send a nurture follow-up email to a lead. AI-generates content if empty."""
    from apps.emails.services import email_service
    from apps.leads.models import LeadActivity

    if not lead.email:
        return

    # Get business name from user profile
    profile = getattr(lead.user, "profile", None)
    business_name = getattr(profile, "company_name", "") if profile else ""

    subject = step.email_subject
    body = step.email_body

    # AI-generate email content if the user left subject/body empty
    if not subject or not body:
        ai_subject, ai_body = _ai_generate_nurture_email(lead, step, business_name)
        subject = subject or ai_subject
        body = body or ai_body

    email_service._send(
        email_type="lead_nurture",
        to_email=lead.email,
        context={
            "lead_name": lead.name or lead.email.split("@")[0],
            "business_name": business_name,
            "email_body": body,
        },
        user=lead.user,
        subject=subject or "Following up",
    )

    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.EMAIL_SENT,
        description=f"Nurture email: {subject or 'Follow-up'}",
    )


def _ai_generate_nurture_email(lead, step, business_name):
    """
    Use LLM to generate a nurture email subject+body when the user
    hasn't written them. Returns (subject, body) tuple.
    Falls back to generic content on any error.
    """
    try:
        from apps.agents.llm import generate, get_model_for_task

        sequence = step.sequence
        step_num = step.order + 1
        total_steps = sequence.steps.count()
        lead_source = lead.get_source_display() if hasattr(lead, "get_source_display") else lead.source

        prompt = (
            f"Write a short, warm follow-up email for a lead nurture sequence.\n\n"
            f"Business: {business_name or 'a local business'}\n"
            f"Sequence: {sequence.name}\n"
            f"Step {step_num} of {total_steps}\n"
            f"Lead name: {lead.name or 'there'}\n"
            f"Lead source: {lead_source}\n"
            f"Delay since last step: {step.delay_hours} hours\n\n"
            f"Rules:\n"
            f"- Keep it under 150 words\n"
            f"- Be conversational and human, not salesy\n"
            f"- If this is step 1, introduce the business warmly\n"
            f"- If later steps, add value (tip, insight, or offer)\n"
            f"- End with a soft CTA (reply, visit, or call)\n\n"
            f"Return ONLY valid JSON: {{\"subject\": \"...\", \"body\": \"...\"}}"
        )

        model = get_model_for_task("create.write", user=lead.user)
        resp = generate(model=model, prompt=prompt, temperature=0.7, max_tokens=400)

        if resp and resp.text:
            import json
            data = json.loads(resp.text.strip().strip("`").strip())
            return data.get("subject", ""), data.get("body", "")
    except Exception as e:
        logger.warning("AI nurture email generation failed: %s", e)

    # Fallback
    lead_name = lead.name or "there"
    return (
        f"Quick follow-up from {business_name or 'us'}",
        f"Hi {lead_name},\n\nJust wanted to check in and see if there's anything "
        f"we can help you with. Feel free to reply to this email anytime.\n\n"
        f"Best,\n{business_name or 'The team'}",
    )


@shared_task(name="leads.score_all_leads")
def score_all_leads():
    """
    Daily task: re-compute priority for all active leads.
    Enrolls newly-qualified HIGH_PRIORITY leads into matching sequences.
    """
    from apps.leads.models import Lead

    active_leads = Lead.objects.exclude(
        status__in=[Lead.Status.CONVERTED, Lead.Status.LOST]
    )

    rescored = 0
    upgraded = 0

    for lead in active_leads.iterator():
        old_priority = lead.priority
        lead.compute_priority()
        if lead.priority != old_priority:
            lead.save(update_fields=["priority"])
            rescored += 1

            # If priority upgraded to HIGH, check for HIGH_PRIORITY sequences
            if lead.priority == Lead.Priority.HIGH and old_priority != Lead.Priority.HIGH:
                enroll_lead_in_sequences(lead)
                upgraded += 1

    logger.info("Lead scoring: %d rescored, %d upgraded to high", rescored, upgraded)
    return {"rescored": rescored, "upgraded_to_high": upgraded}


def enroll_lead_in_sequences(lead):
    """
    Auto-enroll a lead in matching active nurture sequences.

    Called from:
    - Lead post_save signal (new leads)
    - score_all_leads task (priority upgrades)
    - create_lead_from_submission signal (after priority computation)
    Won't double-enroll — checks for existing enrollment.
    """
    from apps.leads.models import LeadEnrollment, NurtureSequence, NurtureStep

    sequences = NurtureSequence.objects.filter(
        user=lead.user,
        is_active=True,
    )

    now = timezone.now()

    for seq in sequences:
        # Check trigger match
        if seq.trigger == NurtureSequence.Trigger.ALL_NEW:
            pass  # matches all
        elif seq.trigger == NurtureSequence.Trigger.FROM_FORM:
            if lead.source_type != "form_submission":
                continue
        elif seq.trigger == NurtureSequence.Trigger.FROM_SOCIAL:
            if lead.source_type not in ("social_dm", "social_comment"):
                continue
        elif seq.trigger == NurtureSequence.Trigger.HIGH_PRIORITY:
            if lead.priority != "high":
                continue
        elif seq.trigger == NurtureSequence.Trigger.FROM_PLATFORM:
            if lead.source_platform != seq.trigger_platform:
                continue
        elif seq.trigger == NurtureSequence.Trigger.MANUAL:
            continue  # manual sequences are not auto-enrolled
        else:
            continue

        # Don't double-enroll
        if LeadEnrollment.objects.filter(lead=lead, sequence=seq).exists():
            continue

        # Get first step to calculate delay
        first_step = NurtureStep.objects.filter(sequence=seq, order=0).first()
        if not first_step:
            continue

        LeadEnrollment.objects.create(
            lead=lead,
            sequence=seq,
            current_step=0,
            next_step_at=now + timedelta(hours=first_step.delay_hours),
        )

        logger.info("Lead %s enrolled in nurture '%s'", lead.email, seq.name)
