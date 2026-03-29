import uuid
from django.conf import settings
from django.db import models


class ContentSeed(models.Model):
    """A raw idea dropped by the user — the starting point for the Create Agent."""

    class SeedStatus(models.TextChoices):
        NEW = "new", "New"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Posts Generated"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_seeds")
    idea = models.TextField(help_text="Your raw idea, topic, or content seed.")
    notes = models.TextField(blank=True, help_text="Additional context or instructions for the AI.")
    target_platforms = models.JSONField(
        default=list, blank=True,
        help_text='Platforms to generate for, e.g. ["twitter", "linkedin"]. Empty = all connected.',
    )
    status = models.CharField(max_length=20, choices=SeedStatus.choices, default=SeedStatus.NEW)
    error_message = models.TextField(blank=True)
    batch_strategy = models.TextField(blank=True, help_text="AI-generated content strategy for this batch of posts.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Seed: {self.idea[:60]}"


class Post(models.Model):
    """A social media post — draft, scheduled, or published."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING_APPROVAL = "pending_approval", "Pending Approval"
        APPROVED = "approved", "Approved"
        SCHEDULED = "scheduled", "Scheduled"
        PUBLISHING = "publishing", "Publishing..."
        PUBLISHED = "published", "Published"
        FAILED = "failed", "Failed"
        REJECTED = "rejected", "Rejected"

    class ContentType(models.TextChoices):
        ORIGINAL = "original", "Original"
        REPURPOSED = "repurposed", "Repurposed"
        CURATED = "curated", "Curated"
        REPLY = "reply", "Reply"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    seed = models.ForeignKey(
        ContentSeed, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts",
    )
    social_account = models.ForeignKey(
        "platforms.SocialAccount", on_delete=models.CASCADE, related_name="posts"
    )
    content_text = models.TextField()
    content_type = models.CharField(max_length=20, choices=ContentType.choices, default=ContentType.ORIGINAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)

    # Media
    media_urls = models.JSONField(default=list, blank=True)

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    # AI metadata
    generated_by_agent = models.CharField(max_length=100, blank=True)
    predicted_engagement_score = models.FloatField(null=True, blank=True)
    ai_reasoning = models.TextField(blank=True, help_text="Why the agent chose this content/timing.")
    ai_angle = models.CharField(max_length=255, blank=True, help_text="The strategic angle chosen for this platform.")
    ai_framework = models.CharField(max_length=100, blank=True, help_text="Content framework used (e.g. Hook→Value→CTA).")

    # Content DNA — attributes for performance correlation
    content_dna = models.JSONField(
        default=dict, blank=True,
        help_text='Content attributes for analysis. E.g. {"format": "question", "tone": "inspirational", "topic": "success_story", "has_cta": true, "has_stats": true, "length": "short"}',
    )

    # Platform post reference
    platform_post_id = models.CharField(max_length=255, blank=True)
    platform_post_url = models.URLField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_status_display()} — {self.content_text[:60]}"


class MediaAttachment(models.Model):
    """Images or videos attached to a post."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="attachments")
    file = models.FileField(upload_to="post_media/%Y/%m/")
    file_type = models.CharField(max_length=20)  # image, video, gif
    alt_text = models.CharField(max_length=500, blank=True)
    order = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return f"Media for {self.post_id} ({self.file_type})"
