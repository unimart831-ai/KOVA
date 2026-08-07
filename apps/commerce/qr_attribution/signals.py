"""QR / walk-in signals — bridge physical touchpoints into the lead inbox."""
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.commerce.qr_attribution.models import WalkInEvent


@receiver(post_save, sender=WalkInEvent)
def bridge_walkin_to_lead(sender, instance, created, **kwargs):
    """Create or update a Lead when cashier captures a phone number."""
    if not created:
        return
    if not (instance.customer_phone or "").strip():
        return

    from apps.commerce.leads.bridges import create_lead_from_walkin

    try:
        create_lead_from_walkin(instance)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Failed to create lead from walk-in %s", instance.pk
        )
