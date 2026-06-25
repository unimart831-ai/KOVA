"""QR / Walk-in attribution data model (Phase 2 W5-6, May 2026).

Closes the loop from social post → walk-in customer for SMEs whose
revenue happens in-person (salons, restaurants, retail). The Kova
Pixel handles the digital half; this module handles the physical half.

Spec: docs/specs/QR_ATTRIBUTION_SPEC.md.

Three models:
  * QRCode      — a printed / displayable QR tied to a campaign or post
  * QRScan      — one row per scan of /qr/<token>/
  * WalkInEvent — a walk-in (manually attributed via the cashier UI)
"""
from __future__ import annotations

import secrets
import string
import uuid

from django.conf import settings
from django.db import models


def _generate_token(length: int = 10) -> str:
    """A short, unguessable URL-safe slug. ~58 bits of entropy at len=10."""
    alphabet = string.ascii_lowercase + string.digits
    return "".join(secrets.choice(alphabet) for _ in range(length))


class QRCode(models.Model):
    """A printed / displayable QR that ties scans back to a campaign / post.

    The `token` is what appears in the public URL: /qr/<token>/. Short
    enough to be readable on a paper flyer if needed.
    """

    class LandingTemplate(models.TextChoices):
        DISCOUNT = "discount", "Show a discount"
        MENU = "menu", "Show menu / catalog"
        BOOKING = "booking", "Book an appointment"
        FOLLOW = "follow", "Follow us on social"
        CUSTOM = "custom", "Custom message"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="qr_codes",
    )
    token = models.SlugField(max_length=12, unique=True, db_index=True)
    label = models.CharField(
        max_length=200,
        help_text="Human-readable name. E.g. \"Jamhuri flyer\", \"Door sticker\", \"Receipt corner\".",
    )

    # What this QR points back to for attribution
    campaign = models.ForeignKey(
        "content.MarketingCampaign", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="qr_codes",
    )
    post = models.ForeignKey(
        "content.Post", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="qr_codes",
    )

    # Landing page customization
    landing_template = models.CharField(
        max_length=20, choices=LandingTemplate.choices,
        default=LandingTemplate.DISCOUNT,
    )
    landing_payload = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Template-specific config. Shapes per template:\n"
            "  discount → {discount_pct, valid_until, terms}\n"
            "  menu     → {menu_image_url, today_special}\n"
            "  booking  → {booking_link, contact_whatsapp}\n"
            "  follow   → {instagram_handle, facebook_url}\n"
            "  custom   → {headline, body, cta_text, cta_url}"
        ),
    )

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
        return f"{self.label} ({self.token})"

    def save(self, *args, **kwargs):
        if not self.token:
            # Retry on the off chance of collision (1 in ~10^14 at len=10)
            for _ in range(5):
                candidate = _generate_token()
                if not QRCode.objects.filter(token=candidate).exists():
                    self.token = candidate
                    break
        super().save(*args, **kwargs)


class QRScan(models.Model):
    """One row per public scan of /qr/<token>/."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    qr_code = models.ForeignKey(
        QRCode, on_delete=models.CASCADE, related_name="scans",
    )
    scanned_at = models.DateTimeField(auto_now_add=True, db_index=True)

    # Visitor identification — set as a cookie on the landing page so a
    # later WalkInEvent can be tied back even when the customer doesn't
    # explicitly say "I saw the QR".
    visitor_id = models.CharField(max_length=64, db_index=True, blank=True)

    # Light-touch context (no PII, no precise IP)
    user_agent = models.CharField(max_length=300, blank=True)
    ip_hash = models.CharField(
        max_length=64, blank=True,
        help_text="SHA-256 hash of the source IP — for dedup, never stored raw.",
    )

    class Meta:
        ordering = ["-scanned_at"]
        indexes = [
            models.Index(fields=["qr_code", "-scanned_at"]),
            models.Index(fields=["visitor_id", "-scanned_at"]),
        ]

    def __str__(self):
        return f"Scan of {self.qr_code.token} at {self.scanned_at}"


class WalkInEvent(models.Model):
    """A walk-in customer attributed (manually) to a marketing channel.

    Recorded via the public-per-business cashier UI at /walkin/<slug>/.
    No login required for the cashier — the URL is the auth.
    """

    class AttributionSource(models.TextChoices):
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        WHATSAPP = "whatsapp", "WhatsApp"
        TIKTOK = "tiktok", "TikTok"
        FLYER = "flyer", "Flyer / Poster"
        WORD_OF_MOUTH = "word_of_mouth", "Word of mouth"
        WALK_BY = "walk_by", "Walked by / signage"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="walk_in_events",
    )

    # Optional ties back to a specific scan / QR — populated when the
    # customer scanned a Kova QR before walking in (visitor_id cookie
    # match). Null when the cashier recorded a generic "Instagram"
    # attribution without a scan having happened.
    scan = models.ForeignKey(
        QRScan, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="walk_ins",
    )
    qr_code = models.ForeignKey(
        QRCode, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="walk_ins",
    )

    # What the cashier tapped on the cashier UI
    attribution_source = models.CharField(
        max_length=30, choices=AttributionSource.choices,
        default=AttributionSource.OTHER, db_index=True,
    )
    attribution_label = models.CharField(
        max_length=80, blank=True,
        help_text="Free-text fallback when source=other.",
    )

    # Optional revenue tag — many SMEs skip this and just want conversions
    revenue = models.DecimalField(
        max_digits=10, decimal_places=2,
        null=True, blank=True,
        help_text="Optional KES revenue from this walk-in.",
    )
    currency = models.CharField(max_length=5, default="KES")
    notes = models.TextField(blank=True)

    # Optional contact capture for lead bridge (cashier UI)
    customer_phone = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Optional phone — creates a Lead when set.",
    )
    customer_name = models.CharField(
        max_length=200, blank=True,
        help_text="Optional name captured at cashier.",
    )

    # When + by whom
    recorded_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-recorded_at"]
        indexes = [
            models.Index(fields=["user", "-recorded_at"]),
            models.Index(fields=["user", "attribution_source", "-recorded_at"]),
            models.Index(fields=["qr_code", "-recorded_at"]),
        ]

    def __str__(self):
        return f"Walk-in via {self.get_attribution_source_display()} on {self.recorded_at:%Y-%m-%d}"
