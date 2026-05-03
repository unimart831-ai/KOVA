"""
Models for the Media Queue app.

A per-platform photo queue with rhythm-based scheduling.
Users upload their own photos, set a posting rhythm, and Kova
auto-publishes them on schedule — a content drip system.
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class MediaQueue(models.Model):
    """
    A photo queue tied to one social account.
    Stores rhythm configuration (how often, what times, which days).
    """

    class RhythmType(models.TextChoices):
        DAILY = "daily", "Daily"       # Post N times per day on selected days
        WEEKLY = "weekly", "Weekly"    # Post on specific days at specific times

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="media_queues",
    )
    social_account = models.ForeignKey(
        "platforms.SocialAccount",
        on_delete=models.CASCADE,
        related_name="media_queues",
    )
    name = models.CharField(max_length=100, blank=True, help_text="Optional label, e.g. 'Product Photos'")
    is_active = models.BooleanField(default=True)

    # ── Rhythm settings ──────────────────────────────────────────
    rhythm_type = models.CharField(
        max_length=10,
        choices=RhythmType.choices,
        default=RhythmType.DAILY,
    )
    # Daily mode: list of time strings, e.g. ["09:00", "13:00", "18:00"]
    # Weekly mode: list of {day, time} objects, e.g. [{"day": 0, "time": "09:00"}, {"day": 2, "time": "14:00"}]
    time_slots = models.JSONField(
        default=list,
        help_text='Daily: ["09:00","13:00"] | Weekly: [{"day":0,"time":"09:00"}]',
    )
    # Days when queue is active (0=Mon..6=Sun). Empty = every day. Only used in daily mode.
    active_days = models.JSONField(
        default=list,
        help_text="Active days (0=Mon..6=Sun). Empty list means every day.",
    )
    timezone = models.CharField(max_length=50, default="UTC")

    # ── Batch settings ───────────────────────────────────────────
    posts_per_slot = models.PositiveIntegerField(
        default=1,
        help_text="How many photos to post per time slot (1 = single, 2+ = bulk).",
    )

    # ── Notifications ────────────────────────────────────────────
    notify_when_low = models.PositiveIntegerField(
        default=3,
        help_text="Alert user when queue drops to N items or fewer.",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("user", "social_account")]
        verbose_name = "Media Queue"
        verbose_name_plural = "Media Queues"

    def __str__(self):
        label = self.name or self.social_account.get_platform_display()
        return f"{label} queue — {self.user}"

    # ── Convenience properties ───────────────────────────────────

    @property
    def queued_count(self):
        return self.items.filter(status=QueueItem.Status.QUEUED).count()

    @property
    def published_count(self):
        return self.items.filter(status=QueueItem.Status.PUBLISHED).count()

    @property
    def is_low(self):
        return self.queued_count <= self.notify_when_low

    @property
    def next_item(self):
        return (
            self.items
            .filter(status=QueueItem.Status.QUEUED)
            .order_by("order", "created_at")
            .first()
        )

    @property
    def platform(self):
        return self.social_account.platform


class QueueItem(models.Model):
    """Individual photo in a media queue."""

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        PUBLISHING = "publishing", "Publishing"
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    queue = models.ForeignKey(MediaQueue, on_delete=models.CASCADE, related_name="items")

    # ── Photo + caption ──────────────────────────────────────────
    image = models.ImageField(upload_to="queue_media/%Y/%m/")
    image_cropped = models.ImageField(
        upload_to="queue_media/%Y/%m/cropped/",
        blank=True,
        help_text="Auto-cropped version optimised for the target platform.",
    )
    caption = models.TextField(blank=True, help_text="Optional caption for this post.")
    caption_variants = models.JSONField(
        default=list,
        blank=True,
        help_text='AI caption variants. Each: {"text": "...", "angle": "Hook|Value|Social|Promo"}.',
    )
    active_variant = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Index of the user-selected variant. Null = auto-rotate by publish count.",
    )

    # ── Ordering + scheduling ────────────────────────────────────
    order = models.PositiveIntegerField(default=0, db_index=True)
    scheduled_for = models.DateTimeField(
        null=True, blank=True, db_index=True,
        help_text="Calculated publish time based on queue rhythm.",
    )

    # ── Publishing state ─────────────────────────────────────────
    status = models.CharField(
        max_length=15,
        choices=Status.choices,
        default=Status.QUEUED,
        db_index=True,
    )
    published_at = models.DateTimeField(null=True, blank=True)
    post = models.ForeignKey(
        "content.Post",
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name="queue_source",
        help_text="Post created when this item is published (for analytics).",
    )
    platform_post_id = models.CharField(max_length=255, blank=True)
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "created_at"]
        verbose_name = "Queue Item"
        verbose_name_plural = "Queue Items"
        indexes = [
            models.Index(fields=["queue", "status", "scheduled_for"]),
        ]

    def __str__(self):
        return f"#{self.order} — {self.get_status_display()}"

    @property
    def image_url(self):
        """Return the best available image URL (cropped if available)."""
        if self.image_cropped:
            return self.image_cropped.url
        return self.image.url

    @property
    def active_variant_text(self):
        """Return the text of the currently selected caption variant, or None."""
        variants = self.caption_variants or []
        if variants and self.active_variant is not None and self.active_variant < len(variants):
            return variants[self.active_variant]["text"]
        return None
