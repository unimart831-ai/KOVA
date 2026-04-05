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
    )
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
