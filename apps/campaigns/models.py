import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Campaign(models.Model):
    """Cross-channel campaign that orchestrates content, email, and conversion."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        APPROVED = "approved", "Approved"
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        COMPLETED = "completed", "Completed"
        CANCELLED = "cancelled", "Cancelled"

    class Objective(models.TextChoices):
        AWARENESS = "awareness", "Brand Awareness"
        ENGAGEMENT = "engagement", "Engagement"
        TRAFFIC = "traffic", "Website Traffic"
        LEADS = "leads", "Lead Generation"
        SALES = "sales", "Sales / Conversions"
        LAUNCH = "launch", "Product Launch"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="campaigns"
    )
    brand = models.ForeignKey(
        "teams.Brand", on_delete=models.SET_NULL, null=True, blank=True, related_name="campaigns"
    )

    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    objective = models.CharField(max_length=20, choices=Objective.choices, default=Objective.AWARENESS)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    # Scheduling
    start_date = models.DateField(null=True, blank=True)
    end_date = models.DateField(null=True, blank=True)

    # Targeting
    target_platforms = models.JSONField(default=list, blank=True, help_text="e.g. ['instagram','twitter','linkedin']")
    target_audience = models.TextField(blank=True, help_text="Description of target audience")

    # UTM — auto-generated slug flows into all linked Posts
    utm_campaign_tag = models.SlugField(max_length=100, blank=True, help_text="Auto-generated UTM campaign tag")

    # Organization
    tags = models.JSONField(default=list, blank=True)

    # Linked content
    content_seeds = models.ManyToManyField(
        "content.ContentSeed", through="CampaignSeed", blank=True, related_name="campaigns"
    )
    email_campaigns = models.ManyToManyField(
        "emails.EmailCampaign", through="CampaignEmail", blank=True, related_name="campaigns"
    )

    # Cached aggregates (refreshed when campaign is viewed)
    metrics_snapshot = models.JSONField(default=dict, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        if not self.utm_campaign_tag and self.name:
            from django.utils.text import slugify
            self.utm_campaign_tag = slugify(self.name)[:100]
        super().save(*args, **kwargs)

    @property
    def is_editable(self):
        return self.status in (self.Status.DRAFT, self.Status.PENDING_APPROVAL)

    @property
    def duration_days(self):
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days
        return None

    @property
    def days_remaining(self):
        if self.end_date:
            remaining = (self.end_date - timezone.now().date()).days
            return max(remaining, 0)
        return None

    @property
    def total_posts(self):
        return sum(cs.seed.posts.count() for cs in self.campaign_seeds.select_related("seed"))

    @property
    def published_posts(self):
        return sum(
            cs.seed.posts.filter(status="published").count()
            for cs in self.campaign_seeds.select_related("seed")
        )


class CampaignSeed(models.Model):
    """Links a Campaign to a ContentSeed with ordering."""

    class Role(models.TextChoices):
        PRIMARY = "primary", "Primary Content"
        SUPPORTING = "supporting", "Supporting"
        FOLLOW_UP = "follow_up", "Follow-up"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="campaign_seeds")
    seed = models.ForeignKey("content.ContentSeed", on_delete=models.CASCADE, related_name="campaign_links")
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.PRIMARY)
    sequence_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence_order", "created_at"]
        unique_together = [("campaign", "seed")]

    def __str__(self):
        return f"{self.campaign.name} → {self.seed.idea[:40]}"


class CampaignEmail(models.Model):
    """Links a Campaign to an EmailCampaign."""

    class Role(models.TextChoices):
        ANNOUNCEMENT = "announcement", "Announcement"
        FOLLOW_UP = "follow_up", "Follow-up"
        REMINDER = "reminder", "Reminder"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="campaign_emails")
    email_campaign = models.ForeignKey(
        "emails.EmailCampaign", on_delete=models.CASCADE, related_name="campaign_links"
    )
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.ANNOUNCEMENT)
    sequence_order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["sequence_order", "created_at"]
        unique_together = [("campaign", "email_campaign")]

    def __str__(self):
        return f"{self.campaign.name} → {self.email_campaign.name}"


class CampaignNote(models.Model):
    """Activity log / comments on a campaign."""

    class NoteType(models.TextChoices):
        COMMENT = "comment", "Comment"
        STATUS_CHANGE = "status_change", "Status Change"
        APPROVAL = "approval", "Approval"
        CONTENT_ADDED = "content_added", "Content Added"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    campaign = models.ForeignKey(Campaign, on_delete=models.CASCADE, related_name="notes")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    content = models.TextField()
    note_type = models.CharField(max_length=20, choices=NoteType.choices, default=NoteType.COMMENT)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_note_type_display()}: {self.content[:50]}"
