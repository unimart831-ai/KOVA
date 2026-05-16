"""Signals that schedule a ReviewRequest when a Lead converts or a
Booking is completed."""
from __future__ import annotations

import logging
from datetime import timedelta

from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils import timezone

logger = logging.getLogger(__name__)


REVIEW_DELAY_HOURS = 24


@receiver(post_save, sender="leads.Lead")
def schedule_review_on_lead_converted(sender, instance, created, **kwargs):
    """When Lead.status transitions to converted, schedule a review."""
    if instance.status != "converted":
        return
    from apps.reviews.models import ReviewRequest

    # Already scheduled?
    if ReviewRequest.objects.filter(lead=instance).exists():
        return

    ReviewRequest.objects.create(
        user=instance.user,
        lead=instance,
        customer_name=instance.name or "",
        customer_email=instance.email or "",
        customer_phone=instance.phone or "",
        channel=(
            ReviewRequest.Channel.WHATSAPP
            if instance.phone else ReviewRequest.Channel.EMAIL
        ),
        scheduled_at=timezone.now() + timedelta(hours=REVIEW_DELAY_HOURS),
    )


@receiver(post_save, sender="bookings.Booking")
def schedule_review_on_booking_completed(sender, instance, created, **kwargs):
    """When Booking.status transitions to completed, schedule a review."""
    if instance.status != "completed":
        return
    from apps.reviews.models import ReviewRequest

    if ReviewRequest.objects.filter(booking=instance).exists():
        return

    ReviewRequest.objects.create(
        user=instance.booking_link.user,
        booking=instance,
        customer_name=instance.customer_name,
        customer_phone=instance.customer_phone,
        customer_email=instance.customer_email,
        channel=(
            ReviewRequest.Channel.WHATSAPP
            if instance.customer_phone else ReviewRequest.Channel.EMAIL
        ),
        scheduled_at=timezone.now() + timedelta(hours=REVIEW_DELAY_HOURS),
    )
