import uuid

from django.conf import settings
from django.db import models


class Lead(models.Model):
    """
    Unified lead record — one per email per user.
    Auto-created from form submissions, social comments, manual entry, or API.
    """

    class Source(models.TextChoices):
        FORM_SUBMISSION = "form_submission", "Form Submission"
        SOCIAL_DM = "social_dm", "Social DM"
        SOCIAL_COMMENT = "social_comment", "Social Comment"
        MANUAL = "manual", "Manual Entry"
        IMPORT = "import", "CSV / Import"
        API = "api", "API"

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        QUALIFIED = "qualified", "Qualified"
        CONVERTED = "converted", "Converted"
        LOST = "lost", "Lost"

    class Priority(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    class Temperature(models.TextChoices):
        HOT = "hot", "Hot"
        WARM = "warm", "Warm"
        COLD = "cold", "Cold"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="leads"
    )

    # Contact info
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=20, blank=True)

    # Source tracking
    source_type = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    source_platform = models.CharField(max_length=30, blank=True, help_text="e.g. instagram, linkedin, twitter")
    source_post = models.ForeignKey(
        "content.Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    source_form = models.ForeignKey(
        "links.KovaForm", on_delete=models.SET_NULL, null=True, blank=True, related_name="leads"
    )
    source_submission = models.ForeignKey(
        "links.FormSubmission", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    # CRM-lite
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.NEW)
    priority = models.CharField(max_length=10, choices=Priority.choices, default=Priority.MEDIUM)
    temperature = models.CharField(
        max_length=10, choices=Temperature.choices, default=Temperature.COLD,
        help_text="HOT = ready to buy now, WARM = interested, COLD = early awareness.",
    )
    tags = models.JSONField(default=list, blank=True)
    notes = models.TextField(blank=True)

    # Metadata
    metadata = models.JSONField(
        default=dict, blank=True,
        help_text="Extra data: UTM params, custom form fields, etc.",
    )

    # Timestamps
    first_seen_at = models.DateTimeField(auto_now_add=True)
    last_activity_at = models.DateTimeField(auto_now=True)
    converted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-first_seen_at"]
        unique_together = ["user", "email"]
        indexes = [
            models.Index(fields=["user", "status", "-first_seen_at"]),
            models.Index(fields=["user", "priority", "-first_seen_at"]),
            models.Index(fields=["user", "source_type"]),
            models.Index(fields=["user", "temperature", "-first_seen_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.name or self.email} ({self.get_status_display()})"

    def compute_priority(self):
        """Auto-score priority based on engagement signals."""
        score = 0
        activity_count = self.activities.count()
        score += min(activity_count * 2, 10)

        if self.source_type == self.Source.FORM_SUBMISSION:
            score += 3
        if self.phone:
            score += 2
        if self.source_platform in ("linkedin", "email"):
            score += 2

        if score >= 8:
            self.priority = self.Priority.HIGH
        elif score >= 4:
            self.priority = self.Priority.MEDIUM
        else:
            self.priority = self.Priority.LOW

    def compute_temperature(self):
        """
        Auto-score lead temperature from recency + engagement signals.

        HOT  — replied to enquiry, or multiple activities in the last 48h,
                or explicitly converted, or came via WhatsApp/DM (intent-first).
        WARM — form submission with phone, or 2+ activities, or LinkedIn source.
        COLD — everything else (awareness stage).
        """
        if self.status == self.Status.CONVERTED:
            self.temperature = self.Temperature.HOT
            return

        activity_count = getattr(self, "_activity_count_cache", None)
        if activity_count is None:
            activity_count = self.activities.count()

        is_intent_channel = self.source_type in (
            self.Source.SOCIAL_DM,
            self.Source.FORM_SUBMISSION,
        ) or self.source_platform in ("whatsapp",)

        if is_intent_channel and self.phone:
            self.temperature = self.Temperature.HOT
        elif activity_count >= 2 or self.source_platform in ("linkedin",):
            self.temperature = self.Temperature.WARM
        elif self.source_type == self.Source.FORM_SUBMISSION or activity_count >= 1:
            self.temperature = self.Temperature.WARM
        else:
            self.temperature = self.Temperature.COLD

    def save(self, *args, **kwargs):
        if not kwargs.get("update_fields") or "temperature" in (kwargs.get("update_fields") or []):
            self.compute_temperature()
        super().save(*args, **kwargs)


class LeadActivity(models.Model):
    """Timeline entry for a lead — tracks every touchpoint."""

    class ActivityType(models.TextChoices):
        FORM_SUBMITTED = "form_submitted", "Form Submitted"
        EMAIL_SENT = "email_sent", "Email Sent"
        EMAIL_OPENED = "email_opened", "Email Opened"
        EMAIL_CLICKED = "email_clicked", "Email Clicked"
        SOCIAL_INTERACTION = "social_interaction", "Social Interaction"
        NOTE_ADDED = "note_added", "Note Added"
        STATUS_CHANGED = "status_changed", "Status Changed"
        PHONE_CALLED = "phone_called", "Phone Called"
        WHATSAPP_SENT = "whatsapp_sent", "WhatsApp Sent"
        TAG_ADDED = "tag_added", "Tag Added"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="activities")
    activity_type = models.CharField(max_length=30, choices=ActivityType.choices)
    description = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name_plural = "Lead activities"
        indexes = [
            models.Index(fields=["lead", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_activity_type_display()} — {self.lead.email}"


# ─── Lead Nurture Sequences ─────────────────────────────────────────────────


class NurtureSequence(models.Model):
    """An automated follow-up sequence for leads."""

    class Trigger(models.TextChoices):
        ALL_NEW = "all_new", "All new leads"
        FROM_FORM = "from_form", "From form submissions"
        FROM_SOCIAL = "from_social", "From social (DMs & comments)"
        HIGH_PRIORITY = "high_priority", "High-priority leads only"
        FROM_PLATFORM = "from_platform", "From specific platform"
        MANUAL = "manual", "Manual enrollment only"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="nurture_sequences"
    )
    name = models.CharField(max_length=200)
    trigger = models.CharField(max_length=20, choices=Trigger.choices, default=Trigger.ALL_NEW)
    trigger_platform = models.CharField(max_length=30, blank=True, help_text="Platform filter when trigger=from_platform")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.get_trigger_display()})"

    @property
    def enrolled_count(self):
        return self.enrollments.count()

    @property
    def completed_count(self):
        return self.enrollments.filter(completed=True).count()


class NurtureStep(models.Model):
    """A single step in a nurture sequence."""

    class ActionType(models.TextChoices):
        SEND_EMAIL = "send_email", "Send Email"
        ADD_TAG = "add_tag", "Add Tag"
        CHANGE_STATUS = "change_status", "Change Status"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(NurtureSequence, on_delete=models.CASCADE, related_name="steps")
    order = models.PositiveIntegerField(default=0)
    delay_hours = models.PositiveIntegerField(default=1, help_text="Hours after previous step (or enrollment)")
    action_type = models.CharField(max_length=20, choices=ActionType.choices, default=ActionType.SEND_EMAIL)

    # Email fields
    email_subject = models.CharField(max_length=200, blank=True)
    email_body = models.TextField(blank=True)

    # Tag field
    tag_value = models.CharField(max_length=50, blank=True)

    # Status field
    status_value = models.CharField(max_length=20, blank=True, choices=Lead.Status.choices)

    class Meta:
        ordering = ["order"]
        unique_together = ["sequence", "order"]

    def __str__(self):
        return f"Step {self.order}: {self.get_action_type_display()}"

    @property
    def delay_display(self):
        """Human-readable delay: '2h', '1d', '3d 12h'."""
        if self.delay_hours == 0:
            return "Immediately"
        days, hours = divmod(self.delay_hours, 24)
        if days and hours:
            return f"{days}d {hours}h"
        if days:
            return f"{days}d"
        return f"{hours}h"


class LeadEnrollment(models.Model):
    """Tracks a lead's progress through a nurture sequence."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lead = models.ForeignKey(Lead, on_delete=models.CASCADE, related_name="enrollments")
    sequence = models.ForeignKey(NurtureSequence, on_delete=models.CASCADE, related_name="enrollments")
    current_step = models.PositiveIntegerField(default=0)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    next_step_at = models.DateTimeField(null=True, blank=True)
    completed = models.BooleanField(default=False)
    paused = models.BooleanField(default=False)

    class Meta:
        ordering = ["-enrolled_at"]
        unique_together = ["lead", "sequence"]
        indexes = [
            models.Index(fields=["completed", "paused", "next_step_at"]),
        ]

    def __str__(self):
        return f"{self.lead.email} → {self.sequence.name}"
