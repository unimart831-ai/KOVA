"""Review request loop data model (Phase 3 W9).

One model — `ReviewRequest` — that ties together:
  * Trigger source (Lead converted OR Booking completed)
  * Outreach attempt (WhatsApp first, email fallback)
  * Response capture (text + sentiment)
  * Branching outcome (content seed for positive, brief alert for negative)
"""
from __future__ import annotations

import uuid

from django.conf import settings
from django.db import models


class ReviewRequest(models.Model):
    """A single review-request lifecycle."""

    class Channel(models.TextChoices):
        WHATSAPP = "whatsapp", "WhatsApp"
        EMAIL = "email", "Email"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending (scheduled)"
        SENT = "sent", "Sent"
        RESPONDED = "responded", "Customer responded"
        FAILED = "failed", "Send failed"
        SKIPPED = "skipped", "Skipped"

    class Sentiment(models.TextChoices):
        POSITIVE = "positive", "Positive"
        NEUTRAL = "neutral", "Neutral"
        NEGATIVE = "negative", "Negative"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="review_requests",
    )

    # Trigger source — exactly one of these set
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="review_requests",
    )
    booking = models.ForeignKey(
        "bookings.Booking", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="review_requests",
    )

    # Outreach
    channel = models.CharField(
        max_length=12, choices=Channel.choices, default=Channel.WHATSAPP,
    )
    customer_name = models.CharField(max_length=120, blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    customer_email = models.EmailField(blank=True)

    # Lifecycle
    scheduled_at = models.DateTimeField(
        db_index=True,
        help_text="When to fire the outreach. Defaults to 24h after trigger.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices,
        default=Status.PENDING, db_index=True,
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    responded_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.TextField(blank=True)

    # Response capture
    response_text = models.TextField(blank=True)
    sentiment = models.CharField(
        max_length=10, choices=Sentiment.choices, blank=True,
    )
    sentiment_score = models.FloatField(
        null=True, blank=True,
        help_text="0.0 (negative) → 1.0 (positive)",
    )

    # Outcome — set when the loop branches
    content_seed = models.ForeignKey(
        "content.ContentSeed", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="from_review_requests",
    )
    escalated_in_brief = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["status", "scheduled_at"]),
        ]

    def __str__(self):
        return (
            f"Review {self.customer_name or self.customer_email or 'anon'} "
            f"({self.get_status_display()})"
        )

    @property
    def is_positive(self):
        return self.sentiment == self.Sentiment.POSITIVE

    @property
    def is_negative(self):
        return self.sentiment == self.Sentiment.NEGATIVE
