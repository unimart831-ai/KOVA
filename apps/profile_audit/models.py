"""
Profile audit models — capture the state of a user's connected social
profile, identify gaps, and track AI-suggested updates through the
approve/apply pipeline.

ProfileAudit  : a snapshot of a SocialAccount's profile state at a moment.
                Immutable — never edited after creation. New audit = new row.
ProfileUpdateSuggestion : an AI-generated suggested value for a single field,
                          tied to an audit. Moves through the
                          pending -> approved -> applied state machine.
"""
from django.conf import settings
from django.db import models


class ProfileAudit(models.Model):
    """An immutable snapshot of a SocialAccount's profile state.

    Created by the nightly profile-audit Celery task. We never update an
    existing row — when an audit re-runs we create a new row. This keeps
    a clean before/after timeline visible on the dashboard."""

    social_account = models.ForeignKey(
        "platforms.SocialAccount",
        on_delete=models.CASCADE,
        related_name="profile_audits",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile_audits",
    )

    completeness_score = models.PositiveSmallIntegerField(
        default=0,
        help_text="0-100. Weighted score of how complete the profile is.",
    )

    fields_present = models.JSONField(
        default=dict,
        help_text="{field_name: current_value} for fields the platform exposes",
    )
    fields_missing = models.JSONField(
        default=list,
        help_text="List of field names absent or empty on the profile.",
    )
    fields_thin = models.JSONField(
        default=list,
        help_text="Fields present but too short / placeholder-like.",
    )

    raw_profile = models.JSONField(
        default=dict, blank=True,
        help_text="Raw API response for debugging. Truncated to avoid huge rows.",
    )
    error = models.TextField(
        blank=True,
        help_text="If the audit itself failed (API error etc), the reason.",
    )

    audited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-audited_at"]
        indexes = [
            models.Index(fields=["user", "-audited_at"]),
            models.Index(fields=["social_account", "-audited_at"]),
        ]

    def __str__(self):
        return f"{self.social_account} — {self.completeness_score}/100"

    @property
    def has_gaps(self) -> bool:
        return bool(self.fields_missing) or bool(self.fields_thin)

    @property
    def severity(self) -> str:
        """For UI display."""
        if self.error:
            return "error"
        if self.completeness_score >= 85:
            return "good"
        if self.completeness_score >= 60:
            return "ok"
        if self.completeness_score >= 30:
            return "low"
        return "critical"


class ProfileUpdateSuggestion(models.Model):
    """An AI-generated suggested value for one profile field.

    Created in batches when an audit completes (one suggestion per gap).
    Moves through:
      pending  -> approved -> applied (success path)
      pending  -> dismissed             (user said no)
      approved -> failed                (API push failed; can retry)
    """

    class Status(models.TextChoices):
        PENDING = "pending", "Pending review"
        APPROVED = "approved", "Approved — queued to apply"
        APPLIED = "applied", "Applied successfully"
        DISMISSED = "dismissed", "Dismissed by user"
        FAILED = "failed", "Apply failed"

    audit = models.ForeignKey(
        ProfileAudit, on_delete=models.CASCADE, related_name="suggestions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile_update_suggestions",
    )
    social_account = models.ForeignKey(
        "platforms.SocialAccount", on_delete=models.CASCADE,
        related_name="profile_update_suggestions",
    )

    field_name = models.CharField(
        max_length=80,
        help_text="Platform-agnostic field key: bio, description, website, etc.",
    )
    current_value = models.TextField(
        blank=True, help_text="What's there now (empty if missing).",
    )
    suggested_value = models.TextField(
        help_text="What Kova proposes to write.",
    )
    reasoning = models.TextField(
        blank=True,
        help_text="One-line explanation surfaced in the UI so users know "
                  "why the AI suggested this.",
    )

    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING,
    )

    # Apply trail
    applied_at = models.DateTimeField(null=True, blank=True)
    applied_value = models.TextField(
        blank=True,
        help_text="The value the platform reports AFTER our PATCH. May "
                  "differ slightly from suggested_value if the platform "
                  "trims / normalizes (e.g., strips emoji, truncates).",
    )
    api_response = models.JSONField(
        default=dict, blank=True,
        help_text="Last API response — kept for debugging.",
    )
    error_message = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["social_account", "status"]),
            models.Index(fields=["status", "-created_at"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["audit", "field_name"],
                name="profile_suggestion_unique_per_audit_field",
            ),
        ]

    def __str__(self):
        return f"{self.social_account} · {self.field_name} ({self.status})"

    @property
    def is_actionable(self) -> bool:
        return self.status in (self.Status.PENDING, self.Status.FAILED)
