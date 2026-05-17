"""Booking integration data model (Phase 2 W7-8).

Two models:
  * BookingLink — a bookable surface tied to a user (one calendar)
  * Booking     — a single confirmed-or-pending appointment

For SMEs whose conversion is an appointment, not a click. Spec:
docs/specs/BOOKING_SPEC.md.
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class BookingLink(models.Model):
    """A bookable surface — one calendar per BookingLink."""

    class IndustryTemplate(models.TextChoices):
        SALON = "salon", "Salon / Beauty"
        REAL_ESTATE = "real_estate", "Real estate viewing"
        FITNESS = "fitness", "Fitness / training"
        CONSULTANT = "consultant", "Consultant / coach"
        CLINIC = "clinic", "Clinic / health"
        GENERIC = "generic", "Generic"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="booking_links",
    )
    slug = models.SlugField(max_length=40, unique=True, db_index=True)
    label = models.CharField(
        max_length=200,
        help_text="What customers see at the top of the booking page.",
    )
    industry_template = models.CharField(
        max_length=20, choices=IndustryTemplate.choices,
        default=IndustryTemplate.GENERIC,
    )

    services = models.JSONField(
        default=list, blank=True,
        help_text=(
            "List of bookable services. Shape: "
            "[{name, duration_minutes, price_kes}, ...]"
        ),
    )
    working_hours = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Per-weekday open windows. Keys mon/tue/.../sun, "
            "value list of {start, end} in HH:MM."
        ),
    )
    timezone = models.CharField(max_length=40, default="Africa/Nairobi")
    advance_notice_minutes = models.PositiveIntegerField(
        default=120,
        help_text="Customers can't book within this many minutes of now.",
    )
    max_advance_days = models.PositiveIntegerField(
        default=30,
        help_text="Customers can't book more than this many days out.",
    )

    owner_whatsapp = models.CharField(max_length=20, blank=True)
    owner_email = models.EmailField(blank=True)

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "is_active"]),
        ]

    def __str__(self):
        return f"{self.label} ({self.slug})"

    def default_working_hours(self):
        """A reasonable default Tues-Sat business-day window."""
        return {
            "mon": [{"start": "09:00", "end": "18:00"}],
            "tue": [{"start": "09:00", "end": "18:00"}],
            "wed": [{"start": "09:00", "end": "18:00"}],
            "thu": [{"start": "09:00", "end": "18:00"}],
            "fri": [{"start": "09:00", "end": "18:00"}],
            "sat": [{"start": "09:00", "end": "16:00"}],
            "sun": [],
        }


class Booking(models.Model):
    """A single appointment on a BookingLink."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"
        NO_SHOW = "no_show", "No-show"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    booking_link = models.ForeignKey(
        BookingLink, on_delete=models.CASCADE, related_name="bookings",
    )

    customer_name = models.CharField(max_length=120)
    customer_phone = models.CharField(max_length=20)
    customer_email = models.EmailField(blank=True)

    service_name = models.CharField(max_length=200)
    duration_minutes = models.PositiveIntegerField()
    price_kes = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    scheduled_at = models.DateTimeField(db_index=True)

    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.CONFIRMED, db_index=True,
    )

    # Attribution — where did this booking come from?
    source_post = models.ForeignKey(
        "content.Post", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bookings",
    )
    source_campaign = models.ForeignKey(
        "campaigns.Campaign", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bookings",
    )
    source_qr = models.ForeignKey(
        "qr_attribution.QRCode", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="bookings",
    )
    source_channel = models.CharField(
        max_length=40, blank=True,
        help_text="engage_agent, qr, direct, walk_in, manual",
    )

    customer_confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    owner_confirmation_sent_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-scheduled_at"]
        unique_together = [("booking_link", "scheduled_at")]
        indexes = [
            models.Index(fields=["booking_link", "scheduled_at"]),
            models.Index(fields=["booking_link", "status", "-scheduled_at"]),
            models.Index(fields=["status", "scheduled_at"]),
        ]

    def __str__(self):
        return (
            f"{self.customer_name} · {self.service_name} · "
            f"{self.scheduled_at:%Y-%m-%d %H:%M}"
        )

    @property
    def user(self):
        """Owner of the booking_link — convenience for analytics."""
        return self.booking_link.user
