"""
Email models — tracks every email sent from the platform.
"""

import uuid

from django.conf import settings
from django.db import models


class EmailLog(models.Model):
    """Audit trail for every email sent by Kova Agent."""

    class EmailType(models.TextChoices):
        # Authentication
        VERIFICATION = "verification", "Email Verification"
        PASSWORD_RESET = "password_reset", "Password Reset"
        PASSWORD_CHANGED = "password_changed", "Password Changed"

        # Onboarding
        WELCOME = "welcome", "Welcome"

        # Transactional — billing
        PAYMENT_CONFIRMATION = "payment_confirmation", "Payment Confirmation"
        INVOICE = "invoice", "Invoice"
        RECEIPT = "receipt", "Receipt"
        PAYMENT_FAILED = "payment_failed", "Payment Failed"
        PAYMENT_REMINDER = "payment_reminder", "Payment Reminder"
        PLAN_CHANGED = "plan_changed", "Plan Changed"
        SUBSCRIPTION_CANCELED = "subscription_canceled", "Subscription Canceled"
        TRIAL_ENDING = "trial_ending", "Trial Ending"

        # Team
        TEAM_INVITATION = "team_invitation", "Team Invitation"

        # Reports
        WEEKLY_REPORT = "weekly_report", "Weekly Report"
        DAILY_BRIEF = "daily_brief", "Daily Brief"

        # Product
        FEATURE_ANNOUNCEMENT = "feature_announcement", "Feature Announcement"

        # Marketing
        PROMOTIONAL = "promotional", "Promotional"

        # Partners
        PARTNER_APPLICATION_RECEIVED = "partner_app_received", "Partner Application Received"
        PARTNER_APPLICATION_APPROVED = "partner_app_approved", "Partner Application Approved"
        PARTNER_APPROVED_NO_ACCOUNT = "partner_approved_noacc", "Partner Approved (No Account)"
        PARTNER_APPLICATION_REJECTED = "partner_app_rejected", "Partner Application Rejected"
        PARTNER_NEW_REFERRAL = "partner_new_referral", "Partner New Referral"
        PARTNER_MILESTONE_ACHIEVED = "partner_milestone", "Partner Milestone Achieved"

        # System
        USAGE_WARNING = "usage_warning", "Usage Warning"
        SYSTEM = "system", "System"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        DELIVERED = "delivered", "Delivered"
        OPENED = "opened", "Opened"
        CLICKED = "clicked", "Clicked"
        BOUNCED = "bounced", "Bounced"
        FAILED = "failed", "Failed"
        SPAM = "spam", "Marked as Spam"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="email_logs",
        null=True,
        blank=True,
        help_text="Null for emails sent to non-users (e.g. team invitations).",
    )
    to_email = models.EmailField(db_index=True)
    from_email = models.EmailField(default="")
    email_type = models.CharField(
        max_length=30, choices=EmailType.choices, db_index=True,
    )  # max_length covers longest key: partner_app_received (20 chars)
    subject = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.QUEUED, db_index=True,
    )
    # Resend message ID for webhook tracking
    provider_message_id = models.CharField(
        max_length=255, blank=True, default="", db_index=True,
    )
    # Metadata (extra context: plan name, amount, etc.)
    metadata = models.JSONField(default=dict, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    opened_at = models.DateTimeField(null=True, blank=True)
    clicked_at = models.DateTimeField(null=True, blank=True)
    failed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["email_type", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.get_email_type_display()}] → {self.to_email} ({self.get_status_display()})"


# ────────────────────────────────────────────────────────────────────
# Sprint 6D — Email Marketing Engine
# ────────────────────────────────────────────────────────────────────


class EmailSubscriber(models.Model):
    """
    An email subscriber belonging to a Kova user.
    Auto-created from Lead records, Kova Form submissions, or CSV import.
    """

    class Source(models.TextChoices):
        KOVA_FORM = "kova_form", "Kova Form"
        MANUAL = "manual", "Manual Entry"
        IMPORT = "import", "CSV Import"
        SOCIAL_BIO = "social_bio", "Social Bio Link"
        API = "api", "API"
        LEAD_SYNC = "lead_sync", "Lead Sync"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"
        BOUNCED = "bounced", "Bounced"
        COMPLAINED = "complained", "Complained"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_subscribers"
    )
    email = models.EmailField(db_index=True)
    name = models.CharField(max_length=200, blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    source_form = models.ForeignKey(
        "links.KovaForm", on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )
    lead = models.ForeignKey(
        "leads.Lead", on_delete=models.SET_NULL, null=True, blank=True, related_name="subscriber"
    )
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    tags = models.JSONField(default=list, blank=True)
    engagement_score = models.FloatField(default=50.0, help_text="0-100 engagement health score.")
    metadata = models.JSONField(default=dict, blank=True)
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)
    bounce_count = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["-subscribed_at"]
        unique_together = ["user", "email"]
        indexes = [
            models.Index(fields=["user", "status", "-subscribed_at"]),
            models.Index(fields=["email"]),
        ]

    def __str__(self):
        return f"{self.name or self.email} ({self.get_status_display()})"

    def record_bounce(self):
        self.bounce_count += 1
        if self.bounce_count >= 3:
            self.status = self.Status.BOUNCED
        self.save(update_fields=["bounce_count", "status"])


class EmailList(models.Model):
    """A named subscription list or smart segment."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_lists"
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    subscribers = models.ManyToManyField(EmailSubscriber, blank=True, related_name="lists")
    filter_rules = models.JSONField(
        default=dict, blank=True,
        help_text="Smart list filter rules: tags, source, engagement_score range, etc.",
    )
    is_smart = models.BooleanField(
        default=False,
        help_text="Smart lists auto-populate from filter rules instead of manual assignment.",
    )
    subscriber_count = models.PositiveIntegerField(default=0, help_text="Cached count for display.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({self.subscriber_count} subscribers)"

    def refresh_count(self):
        if self.is_smart:
            self.subscriber_count = self.get_smart_queryset().count()
        else:
            self.subscriber_count = self.subscribers.filter(status=EmailSubscriber.Status.ACTIVE).count()
        self.save(update_fields=["subscriber_count"])

    def get_smart_queryset(self):
        """Build queryset from filter_rules for smart lists."""
        qs = EmailSubscriber.objects.filter(user=self.user, status=EmailSubscriber.Status.ACTIVE)
        rules = self.filter_rules or {}
        if "tags" in rules:
            for tag in rules["tags"]:
                qs = qs.filter(tags__contains=[tag])
        if "source" in rules:
            qs = qs.filter(source=rules["source"])
        if "min_engagement" in rules:
            qs = qs.filter(engagement_score__gte=rules["min_engagement"])
        return qs

    def get_active_subscribers(self):
        """Return active subscribers for sending."""
        if self.is_smart:
            return self.get_smart_queryset()
        return self.subscribers.filter(status=EmailSubscriber.Status.ACTIVE)


class EmailCampaign(models.Model):
    """A single email campaign (newsletter, announcement, etc.)."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SCHEDULED = "scheduled", "Scheduled"
        SENDING = "sending", "Sending"
        SENT = "sent", "Sent"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_campaigns"
    )
    name = models.CharField(max_length=200, help_text="Internal campaign name.")
    subject = models.CharField(max_length=255)
    preview_text = models.CharField(max_length=255, blank=True, help_text="The preview snippet in inbox.")
    html_content = models.TextField(blank=True)
    text_content = models.TextField(blank=True, help_text="Plain text fallback.")
    from_name = models.CharField(max_length=200, blank=True, help_text="Sender display name.")
    reply_to = models.EmailField(blank=True)

    # Targeting
    target_list = models.ForeignKey(
        EmailList, on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns"
    )

    # Status & scheduling
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    scheduled_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    # Metrics
    total_sent = models.PositiveIntegerField(default=0)
    total_opened = models.PositiveIntegerField(default=0)
    total_clicked = models.PositiveIntegerField(default=0)
    total_bounced = models.PositiveIntegerField(default=0)
    total_unsubscribed = models.PositiveIntegerField(default=0)

    # AI & attribution
    ai_generated = models.BooleanField(default=False)
    source_post = models.ForeignKey(
        "content.Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="email_campaigns"
    )

    # A/B variants
    variant_of = models.ForeignKey(
        "self", on_delete=models.SET_NULL, null=True, blank=True, related_name="variants"
    )
    variant_label = models.CharField(max_length=10, blank=True, help_text="A, B, C…")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.get_status_display()})"

    @property
    def open_rate(self):
        if self.total_sent:
            return round(self.total_opened / self.total_sent * 100, 1)
        return 0

    @property
    def click_rate(self):
        if self.total_sent:
            return round(self.total_clicked / self.total_sent * 100, 1)
        return 0


class EmailSequence(models.Model):
    """Automated email drip sequence triggered by an event."""

    class TriggerType(models.TextChoices):
        FORM_SUBMISSION = "form_submission", "Form Submission"
        TAG_ADDED = "tag_added", "Tag Added"
        SUBSCRIBER_ADDED = "subscriber_added", "Subscriber Added"
        LEAD_STATUS_CHANGE = "lead_status_change", "Lead Status Change"
        MANUAL = "manual", "Manual Enrollment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="email_sequences"
    )
    name = models.CharField(max_length=200)
    trigger_type = models.CharField(max_length=30, choices=TriggerType.choices)
    trigger_config = models.JSONField(
        default=dict, blank=True,
        help_text="Trigger params: form_id, tag_name, list_id, etc.",
    )
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.name} ({'Active' if self.is_active else 'Inactive'})"


class EmailSequenceStep(models.Model):
    """A single step in an automated email sequence."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(
        EmailSequence, on_delete=models.CASCADE, related_name="steps"
    )
    step_number = models.PositiveSmallIntegerField()
    delay_days = models.PositiveSmallIntegerField(default=0, help_text="Days after previous step.")
    delay_hours = models.PositiveSmallIntegerField(default=0, help_text="Hours after previous step.")
    subject = models.CharField(max_length=255)
    html_content = models.TextField(blank=True)
    text_content = models.TextField(blank=True)
    ai_generated = models.BooleanField(default=False)

    class Meta:
        ordering = ["step_number"]
        unique_together = ["sequence", "step_number"]

    def __str__(self):
        return f"Step {self.step_number}: {self.subject}"


class SequenceEnrollment(models.Model):
    """Tracks a subscriber's progress through a sequence."""

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        COMPLETED = "completed", "Completed"
        PAUSED = "paused", "Paused"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    sequence = models.ForeignKey(
        EmailSequence, on_delete=models.CASCADE, related_name="enrollments"
    )
    subscriber = models.ForeignKey(
        EmailSubscriber, on_delete=models.CASCADE, related_name="enrollments"
    )
    current_step = models.PositiveSmallIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.ACTIVE)
    next_send_at = models.DateTimeField(null=True, blank=True)
    enrolled_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-enrolled_at"]
        unique_together = ["sequence", "subscriber"]

    def __str__(self):
        return f"{self.subscriber.email} in {self.sequence.name} (step {self.current_step})"
