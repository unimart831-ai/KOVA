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
