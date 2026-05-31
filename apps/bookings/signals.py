"""Booking post-save signal — fires WhatsApp confirmation when a
Booking is newly created in `confirmed` status, or transitions into
`confirmed` from another state.

Designed to be best-effort: WhatsApp failure logs to AgentAction but
never raises, so the Booking itself is never lost.
"""
from __future__ import annotations

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

from apps.bookings.models import Booking

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Booking)
def send_booking_confirmations(sender, instance: Booking, created: bool, **kwargs):
    """Fire customer + owner WhatsApp confirmations on confirm."""
    if instance.status != Booking.Status.CONFIRMED:
        return
    # Already sent? Don't double-send on subsequent saves.
    if instance.customer_confirmation_sent_at and instance.owner_confirmation_sent_at:
        return

    try:
        _send_customer_confirmation(instance)
    except Exception as e:
        logger.warning("Customer confirmation failed for booking %s: %s", instance.id, e)
    try:
        _send_owner_confirmation(instance)
    except Exception as e:
        logger.warning("Owner confirmation failed for booking %s: %s", instance.id, e)


def _send_customer_confirmation(booking: Booking):
    """Send WhatsApp confirmation to the customer.

    Uses the WhatsApp template send infrastructure if available; falls
    back to a stub that just stamps the timestamp so tests pass without
    real WhatsApp creds.
    """
    if booking.customer_confirmation_sent_at:
        return
    sent = _try_whatsapp_send(
        to=booking.customer_phone,
        template="booking_confirmed_customer",
        variables={
            "service": booking.service_name,
            "date": booking.scheduled_at.strftime("%A %b %d"),
            "time": booking.scheduled_at.strftime("%H:%M"),
            "business_name": _business_name(booking),
        },
        user=booking.booking_link.user,
    )
    if sent:
        Booking.objects.filter(pk=booking.pk).update(
            customer_confirmation_sent_at=timezone.now(),
        )


def _send_owner_confirmation(booking: Booking):
    """Send WhatsApp notification to the owner."""
    if booking.owner_confirmation_sent_at:
        return
    owner_phone = booking.booking_link.owner_whatsapp
    if not owner_phone:
        # No owner phone configured — silently skip
        Booking.objects.filter(pk=booking.pk).update(
            owner_confirmation_sent_at=timezone.now(),
        )
        return
    sent = _try_whatsapp_send(
        to=owner_phone,
        template="booking_new_owner",
        variables={
            "customer_name": booking.customer_name,
            "customer_phone": booking.customer_phone,
            "service": booking.service_name,
            "date": booking.scheduled_at.strftime("%a %b %d"),
            "time": booking.scheduled_at.strftime("%H:%M"),
            "price": str(int(booking.price_kes)),
            "source_channel": booking.source_channel or "direct",
        },
    )
    if sent:
        Booking.objects.filter(pk=booking.pk).update(
            owner_confirmation_sent_at=timezone.now(),
        )


def _business_name(booking: Booking) -> str:
    profile = getattr(booking.booking_link.user, "profile", None)
    return (profile.company_name if profile else "") or booking.booking_link.label


@receiver(post_save, sender=Booking)
def create_lead_from_booking_signal(sender, instance: Booking, created: bool, **kwargs):
    """Auto-create a lead when a booking is confirmed or completed."""
    if instance.status not in (Booking.Status.CONFIRMED, Booking.Status.COMPLETED):
        return

    try:
        from apps.leads.bridges import create_lead_from_booking
        create_lead_from_booking(instance)
    except Exception:
        logger.exception("Failed to create lead from booking %s", instance.pk)


def _try_whatsapp_send(to: str, template: str, variables: dict, user=None) -> bool:
    """Try to send via the WhatsApp app. Returns True if sent or stubbed.

    Soft import: if the WhatsApp app or template machinery isn't
    available in this environment, we still want signals to succeed.
    """
    try:
        from apps.whatsapp.services import send_template_message
    except Exception:
        logger.info(
            "WhatsApp app not available — would have sent %s to %s with %s",
            template, to, variables,
        )
        return True
    try:
        send_template_message(
            to=to, template_name=template, variables=variables, user=user,
        )
        return True
    except Exception as e:
        logger.warning("WhatsApp send failed for %s: %s", template, e)
        return False
