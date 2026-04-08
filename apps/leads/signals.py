from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.links.models import FormSubmission


@receiver(post_save, sender=FormSubmission)
def create_lead_from_submission(sender, instance, created, **kwargs):
    """Auto-create or update a Lead when a form submission comes in."""
    if not created:
        return

    from apps.leads.models import Lead, LeadActivity

    form = instance.form
    page = form.page
    user = page.user

    lead, was_created = Lead.objects.get_or_create(
        user=user,
        email=instance.email,
        defaults={
            "name": instance.name,
            "phone": instance.phone,
            "source_type": Lead.Source.FORM_SUBMISSION,
            "source_form": form,
            "source_submission": instance,
            "metadata": {
                "utm_source": instance.utm_source,
                "utm_medium": instance.utm_medium,
                "utm_campaign": instance.utm_campaign,
                "page_slug": instance.page_slug,
                "custom_data": instance.custom_data or {},
            },
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
