from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.commerce.links.models import FormSubmission


@receiver(post_save, sender=FormSubmission)
def create_lead_from_submission(sender, instance, created, **kwargs):
    """Auto-create or update a Lead when a form submission comes in."""
    if not created:
        return

    from apps.commerce.leads.models import Lead, LeadActivity

    form = instance.form
    page = form.page
    user = page.user

    from apps.core.billing.enforcement import check_leads_limit

    allowed, _msg = check_leads_limit(user, creating=True)
    if not allowed:
        return

    meta = {
        "utm_source": instance.utm_source,
        "utm_medium": instance.utm_medium,
        "utm_campaign": instance.utm_campaign,
        "page_slug": instance.page_slug,
        "custom_data": instance.custom_data or {},
    }
    campaign = None
    if instance.utm_campaign:
        from apps.create.content.campaign_attribution import resolve_marketing_campaign

        campaign = resolve_marketing_campaign(
            user,
            campaign_slug=instance.utm_campaign,
            utm_campaign=instance.utm_campaign,
            metadata=meta,
        )
        if campaign:
            meta["campaign_id"] = str(campaign.pk)
            meta["campaign_slug"] = campaign.slug

    lead, was_created = Lead.objects.get_or_create(
        user=user,
        email=instance.email,
        defaults={
            "name": instance.name,
            "phone": instance.phone,
            "source_type": Lead.Source.FORM_SUBMISSION,
            "source_form": form,
            "source_submission": instance,
            "marketing_campaign": campaign,
            "metadata": meta,
        },
    )

    if not was_created:
        # Update existing lead with latest info
        if instance.name and not lead.name:
            lead.name = instance.name
        if instance.phone and not lead.phone:
            lead.phone = instance.phone
        lead.source_submission = instance
        lead.save(update_fields=["name", "phone", "source_submission", "last_activity_at"])

    # Log the activity
    LeadActivity.objects.create(
        lead=lead,
        activity_type=LeadActivity.ActivityType.FORM_SUBMITTED,
        description=f"Submitted form '{form.title}' on /k/{instance.page_slug}/",
        metadata={
            "form_id": str(form.pk),
            "submission_id": str(instance.pk),
            "message": instance.message[:200] if instance.message else "",
        },
    )

    # Auto-score priority
    lead.compute_priority()
    lead.save(update_fields=["priority"])

    if was_created:
        from apps.commerce.leads.attribution import attribute_lead_to_campaign

        try:
            attribute_lead_to_campaign(lead, campaign=campaign)
        except Exception:
            import logging
            logging.getLogger(__name__).exception(
                "Failed to attribute lead %s to campaign", lead.pk
            )

    # Re-check enrollment after priority is computed (when autopilot enroll is on).
    if was_created:
        from apps.core.features import feature_enabled
        from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads
        from apps.commerce.leads.tasks import enroll_lead_in_sequences

        if feature_enabled("nurture", default=False) and should_auto_enroll_leads(user):
            try:
                enroll_lead_in_sequences(lead)
            except Exception:
                import logging
                logging.getLogger(__name__).exception(
                    "Failed to re-enroll lead %s after priority scoring", lead.pk
                )


@receiver(post_save, sender="leads.Lead")
def notify_owner_of_new_lead(sender, instance, created, **kwargs):
    """WhatsApp-first: ping the owner when a new lead arrives.

    Commerce-purchase leads are skipped — the payment alert already covers
    those. Sends are best-effort and never block lead creation.
    """
    if not created:
        return
    from apps.commerce.leads.models import Lead

    # Only alert for genuine inbound leads. Purchases are covered by the
    # payment alert; imports/API/manual are owner-initiated (no surprise).
    inbound_sources = {
        Lead.Source.FORM_SUBMISSION,
        Lead.Source.SOCIAL_DM,
        Lead.Source.SOCIAL_COMMENT,
        Lead.Source.BOOKING,
        Lead.Source.QR_SCAN,
        Lead.Source.WALK_IN,
    }
    if instance.source_type not in inbound_sources:
        return

    try:
        from apps.create.briefs.owner_alerts import notify_owner_hot_lead, notify_owner_new_lead

        if getattr(instance, "temperature", "") == "hot":
            notify_owner_hot_lead(instance)
        else:
            notify_owner_new_lead(instance)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Owner WhatsApp alert failed for new lead %s", instance.pk
        )


@receiver(post_save, sender="leads.Lead")
def attribute_new_lead(sender, instance, created, **kwargs):
    """Ensure every new lead gets campaign attribution + Conversion row."""
    if not created:
        return
    # Form-submission path already attributes above; still safe (idempotent).
    if instance.source_type == instance.Source.FORM_SUBMISSION:
        return
    try:
        from apps.commerce.leads.attribution import attribute_lead_to_campaign

        attribute_lead_to_campaign(instance)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to attribute new lead %s", instance.pk
        )


@receiver(post_save, sender="leads.Lead")
def enroll_new_lead_in_sequences(sender, instance, created, **kwargs):
    """Auto-enroll newly created leads into matching nurture sequences."""
    if not created:
        return

    from apps.core.features import feature_enabled

    if not feature_enabled("nurture", default=False):
        return

    from apps.commerce.leads.defaults import ensure_default_nurture_sequences
    from apps.commerce.leads.tasks import enroll_lead_in_sequences

    try:
        ensure_default_nurture_sequences(instance.user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to ensure default nurture sequences for user %s", instance.user_id
        )

    from apps.core.accounts.autopilot_helpers import should_auto_enroll_leads

    if not should_auto_enroll_leads(instance.user):
        return

    try:
        enroll_lead_in_sequences(instance)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to enroll lead %s in nurture sequences", instance.pk
        )
