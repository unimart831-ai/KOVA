import uuid
from django.conf import settings
from django.db import models


class Interaction(models.Model):
    """Tracked comment/reply/DM from the platform."""

    class InteractionType(models.TextChoices):
        COMMENT = "comment", "Comment"
        REPLY = "reply", "Reply"
        MENTION = "mention", "Mention"
        DM = "dm", "Direct Message"

    class Status(models.TextChoices):
        NEW = "new", "New"
        AI_REPLIED = "ai_replied", "AI Replied"
        USER_REPLIED = "user_replied", "User Replied"
        IGNORED = "ignored", "Ignored"
        FLAGGED = "flagged", "Flagged"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="interactions")
    social_account = models.ForeignKey(
        "platforms.SocialAccount", on_delete=models.SET_NULL, null=True, blank=True, related_name="interactions",
    )
    platform = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Denormalized platform name — preserved when social_account is disconnected.",
    )
    post = models.ForeignKey("content.Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="interactions")
    interaction_type = models.CharField(max_length=20, choices=InteractionType.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW, db_index=True)
    author_name = models.CharField(max_length=255)
    author_username = models.CharField(max_length=255, blank=True)
    content = models.TextField()
    ai_suggested_reply = models.TextField(blank=True)
    ai_reply_sent = models.TextField(blank=True)
    user_edited_reply = models.BooleanField(
        default=False,
        help_text="Whether the user modified the AI-suggested reply before sending.",
    )
    # ── Engage Agent v2 (Phase 1 W2 May 2026) ──
    # The LLM produces these alongside the reply text; engage_routing.route_reply
    # uses confidence + safety_flags to decide auto-send vs draft vs escalate.
    ai_confidence = models.FloatField(
        null=True, blank=True,
        help_text="Engage Agent LLM confidence in the suggested reply (0.0-1.0).",
    )
    ai_intent = models.CharField(
        max_length=30, blank=True, db_index=True,
        help_text=(
            "Classified intent: hours, booking, pricing, complaint, praise, "
            "spam, other. Used by safety rails to gate auto-send."
        ),
    )
    safety_flags = models.JSONField(
        default=list, blank=True,
        help_text=(
            "Reasons the reply must NOT auto-send regardless of confidence. "
            "Populated by engage_routing.safety_check (complaint, long_reply, "
            "refund_keyword, cold_first_contact, pricing_without_cta, etc.)."
        ),
    )
    platform_interaction_id = models.CharField(max_length=255, blank=True, db_index=True)
    sentiment = models.CharField(max_length=20, blank=True, db_index=True)  # positive, neutral, negative
    created_at = models.DateTimeField(auto_now_add=True)
    responded_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the first reply (AI or human) was sent.",
    )

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["social_account", "-created_at"]),
            models.Index(fields=["user", "sentiment", "-created_at"]),
        ]

    @property
    def response_time_seconds(self):
        """Seconds between interaction received and first reply."""
        if self.responded_at and self.created_at:
            return (self.responded_at - self.created_at).total_seconds()
        return None


class EngageReply(models.Model):
    """Audit log of every Engage Agent auto-sent reply (Phase 1 W2 May 2026).

    One row per AUTO_SEND verdict from `engage_routing.route_reply`. Carries
    the snapshots needed for:

      * The 5-minute undo window — `can_undo_until` + the platform's
        comment_id stored in `platform_reply_id` so we can call the
        provider's delete_comment.
      * Post-window corrections — the user can still say "I would have
        replied differently" even after undo expires; that correction
        becomes a few-shot example for future replies to the same contact.
      * Adapt Agent v2 (W3-4) — corrections lower the weight of the LLM
        patterns that produced them.

    Spec: docs/specs/ENGAGE_AGENT_V2_SPEC.md
    """

    class CorrectionReason(models.TextChoices):
        TONE = "tone", "Wrong tone"
        FACTS = "facts", "Wrong facts"
        LENGTH = "length", "Wrong length"
        TIMING = "timing", "Wrong timing / should have escalated"
        OTHER = "other", "Other"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    interaction = models.OneToOneField(
        "engage.Interaction",
        on_delete=models.CASCADE,
        related_name="engage_reply",
    )
    sent_text = models.TextField(
        help_text="The exact text that was auto-sent to the platform.",
    )
    confidence = models.FloatField(
        help_text="LLM confidence at send time (0.0-1.0).",
    )
    autonomy_level = models.CharField(
        max_length=20,
        help_text=(
            "Snapshot of the user's engage_autonomy_level when this reply "
            "was sent. Lets us audit later if a plan downgrade should have "
            "blocked it."
        ),
    )
    safety_flags_snapshot = models.JSONField(
        default=list, blank=True,
        help_text="The safety_flags list at send time (empty when clean).",
    )
    platform_reply_id = models.CharField(
        max_length=255, blank=True, db_index=True,
        help_text=(
            "The platform's comment/reply ID returned from post_comment. "
            "Used by undo to call provider.delete_comment."
        ),
    )
    sent_at = models.DateTimeField(auto_now_add=True)
    can_undo_until = models.DateTimeField(
        help_text="5 minutes after sent_at by default. After this, only the correction flow remains.",
    )

    # ── Undo ────────────────────────────────────────────────────────
    undone_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the user successfully undid the auto-send.",
    )
    undo_error = models.TextField(
        blank=True,
        help_text="If the platform delete API failed during undo, the error text.",
    )

    # ── Correction (few-shot learning signal) ───────────────────────
    correction_text = models.TextField(
        blank=True,
        help_text="What the user would have said instead.",
    )
    correction_reason = models.CharField(
        max_length=20,
        blank=True,
        choices=CorrectionReason.choices,
        help_text="High-level reason the auto-send was wrong.",
    )
    corrected_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-sent_at"]
        indexes = [
            models.Index(fields=["interaction"]),
            models.Index(fields=["sent_at"]),
        ]

    def can_undo(self):
        """True if the 5-minute undo window is still open and not yet undone."""
        from django.utils import timezone
        return self.undone_at is None and timezone.now() < self.can_undo_until


class Superfan(models.Model):
    """
    Tracked repeat engager — someone who interacts with the brand frequently.
    Detected by the Engage Agent, surfaced by the Strategist in Daily Briefs.
    """

    class Tier(models.TextChoices):
        RISING = "rising", "Rising"          # 3-5 interactions
        LOYAL = "loyal", "Loyal"             # 6-15 interactions
        SUPERFAN = "superfan", "Superfan"    # 16+ interactions

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="superfans")
    author_username = models.CharField(max_length=255, db_index=True)
    author_name = models.CharField(max_length=255)
    platforms = models.JSONField(default=list, blank=True, help_text="Platforms this person engages on")
    interaction_count = models.PositiveIntegerField(default=0)
    tier = models.CharField(max_length=20, choices=Tier.choices, default=Tier.RISING)
    last_sentiment = models.CharField(max_length=20, blank=True)
    first_seen = models.DateTimeField(auto_now_add=True)
    last_interaction_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True, help_text="AI-generated notes about this person's engagement patterns.")

    class Meta:
        ordering = ["-interaction_count"]
        unique_together = ["user", "author_username"]

    def __str__(self):
        return f"{self.author_name} ({self.get_tier_display()}) — {self.interaction_count} interactions"

    def update_tier(self):
        """Recalculate tier based on interaction count."""
        if self.interaction_count >= 16:
            self.tier = self.Tier.SUPERFAN
        elif self.interaction_count >= 6:
            self.tier = self.Tier.LOYAL
        else:
            self.tier = self.Tier.RISING
