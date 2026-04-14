import uuid
from django.conf import settings
from django.db import models

from apps.accounts.soft_delete import SoftDeleteMixin


class ContentSeed(models.Model):
    """A raw idea dropped by the user — the starting point for the Create Agent."""

    class SeedStatus(models.TextChoices):
        NEW = "new", "New"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Posts Generated"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="content_seeds")
    brand = models.ForeignKey(
        "teams.Brand", on_delete=models.SET_NULL, null=True, blank=True, related_name="content_seeds",
        help_text="Brand this content is for. Null = user's default brand voice.",
    )
    idea = models.TextField(help_text="Your raw idea, topic, or content seed.")
    notes = models.TextField(blank=True, help_text="Additional context or instructions for the AI.")
    target_platforms = models.JSONField(
        default=list, blank=True,
        help_text='Platforms to generate for, e.g. ["twitter", "linkedin"]. Empty = all connected.',
    )
    generate_images = models.BooleanField(
        default=False,
        help_text="When True, generate AI images for ALL platforms (not just visual-first ones like Instagram).",
    )
    status = models.CharField(max_length=20, choices=SeedStatus.choices, default=SeedStatus.NEW, db_index=True)
    error_message = models.TextField(blank=True)
    batch_strategy = models.TextField(blank=True, help_text="AI-generated content strategy for this batch of posts.")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Seed: {self.idea[:60]}"


class Post(SoftDeleteMixin, models.Model):
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

    class MediaStatus(models.TextChoices):
        NONE = "none", "No media"
        PENDING = "pending", "Pending generation"
        GENERATED = "generated", "AI-generated"
        UPLOADED = "uploaded", "Manually uploaded"
        FAILED = "failed", "Generation failed"

    # Platforms that REQUIRE an image/video — text-only posts will fail.
    MEDIA_REQUIRED_PLATFORMS = {"instagram", "tiktok", "pinterest"}

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="posts")
    brand = models.ForeignKey(
        "teams.Brand", on_delete=models.SET_NULL, null=True, blank=True, related_name="posts",
        help_text="Brand this post belongs to. Null = user's default brand voice.",
    )
    seed = models.ForeignKey(
        ContentSeed, on_delete=models.SET_NULL, null=True, blank=True, related_name="posts",
    )
    social_account = models.ForeignKey(
        "platforms.SocialAccount", on_delete=models.SET_NULL, null=True, blank=True, related_name="posts",
    )
    platform = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Denormalized platform name — preserved when social_account is disconnected.",
    )
    content_text = models.TextField()
    content_type = models.CharField(max_length=20, choices=ContentType.choices, default=ContentType.ORIGINAL)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)

    # Media
    media_urls = models.JSONField(default=list, blank=True)
    media_prompt = models.TextField(
        blank=True,
        help_text="AI image prompt used for generation. Stored for retry capability.",
    )
    media_status = models.CharField(
        max_length=20,
        choices=MediaStatus.choices,
        default=MediaStatus.NONE,
        help_text="Tracks whether AI image generation succeeded, failed, or was skipped.",
    )

    # Visual strategy tracking — enables analytics on which visual type performs best
    VISUAL_STRATEGY_CHOICES = [
        ("none", "No visual"),
        ("ai_photo", "AI-generated photo"),
        ("quote_card", "Quote card"),
        ("tip_graphic", "Tip graphic"),
        ("stat_highlight", "Stat highlight"),
        ("cta_banner", "CTA banner"),
        ("carousel", "Carousel"),
        ("story_graphic", "Story graphic"),
    ]
    visual_strategy = models.CharField(
        max_length=30, choices=VISUAL_STRATEGY_CHOICES, default="none", db_index=True,
        help_text="Which visual strategy was used for this post. Stored for analytics.",
    )
    visual_metadata = models.JSONField(
        default=dict, blank=True,
        help_text='Visual generation details: {"image_prompt": "...", "template": "...", "model": "...", "provider": "..."}',
    )

    # Scheduling
    scheduled_at = models.DateTimeField(null=True, blank=True, db_index=True)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)

    # AI metadata
    generated_by_agent = models.CharField(max_length=100, blank=True)
    predicted_engagement_score = models.FloatField(null=True, blank=True)
    ai_reasoning = models.TextField(blank=True, help_text="Why the agent chose this content/timing.")
    ai_angle = models.CharField(max_length=255, blank=True, help_text="The strategic angle chosen for this platform.")
    ai_framework = models.CharField(max_length=100, blank=True, help_text="Content framework used (e.g. Hook→Value→CTA).")

    # Intelligence feedback loop — tracks what AI suggested vs. what user approved
    ai_original_text = models.TextField(
        blank=True,
        help_text="Original AI-generated text before user edits. Set once during generation, never overwritten.",
    )
    user_edited = models.BooleanField(
        default=False,
        help_text="Whether the user modified the AI-generated content.",
    )
    edit_distance_ratio = models.FloatField(
        null=True, blank=True,
        help_text="0.0 = no changes, 1.0 = completely rewritten. Measures how much user changed AI output.",
    )

    # User quality rating — quick feedback on AI-generated content
    RATING_CHOICES = [
        (1, "👎 Poor"),
        (2, "👍 Good"),
        (3, "🔥 Great"),
    ]
    user_rating = models.PositiveSmallIntegerField(
        null=True, blank=True, choices=RATING_CHOICES,
        help_text="User's quality rating of AI-generated content (1=poor, 2=good, 3=great).",
    )

    # Content DNA — attributes for performance correlation
    content_dna = models.JSONField(
        default=dict, blank=True,
        help_text='Content attributes for analysis. E.g. {"format": "question", "tone": "inspirational", "topic": "success_story", "has_cta": true, "has_stats": true, "length": "short"}',
    )

    # A/B Testing
    ab_test = models.ForeignKey(
        "ABTest", on_delete=models.SET_NULL, null=True, blank=True, related_name="variants",
    )
    variant_label = models.CharField(max_length=10, blank=True, help_text="Variant label: A, B, C…")

    # Platform post reference
    platform_post_id = models.CharField(max_length=255, blank=True)
    platform_post_url = models.URLField(blank=True)

    # ── Smart CTA System (Sprint 6B) ──
    CTA_TYPE_CHOICES = [
        ("none", "No CTA"),
        ("link", "Link / URL"),
        ("phone", "Phone Call"),
        ("email", "Email"),
        ("whatsapp", "WhatsApp"),
        ("kova_link", "Kova Link Page"),
    ]
    cta_type = models.CharField(max_length=20, choices=CTA_TYPE_CHOICES, default="none")
    cta_text = models.CharField(max_length=255, blank=True, help_text="CTA copy, e.g. 'Book a free consultation →'")
    cta_url = models.CharField(max_length=500, blank=True, help_text="Destination URL or contact info for the CTA.")
    utm_source = models.CharField(max_length=50, blank=True, help_text="Auto-populated from platform name.")
    utm_medium = models.CharField(max_length=50, default="social", blank=True)
    utm_campaign = models.CharField(max_length=100, blank=True, help_text="From seed or user campaign.")
    utm_content = models.CharField(max_length=100, blank=True, help_text="Post ID for A/B tracking.")
    first_comment = models.TextField(blank=True, help_text="For LinkedIn: CTA link goes in first comment instead of body.")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["social_account", "status", "-scheduled_at"]),
            models.Index(fields=["user", "-scheduled_at"]),
            models.Index(fields=["user", "media_status"]),
            models.Index(fields=["seed", "status"]),
        ]

    def __str__(self):
        return f"{self.get_status_display()} — {self.content_text[:60]}"

    @property
    def has_media(self):
        """True if the post has at least one image/video attached."""
        return bool(self.media_urls) or self.attachments.exists()

    @property
    def needs_media(self):
        """True if this post's platform requires media and none is attached."""
        plat = self.platform or (self.social_account.platform if self.social_account else "")
        return plat in self.MEDIA_REQUIRED_PLATFORMS and not self.has_media

    @property
    def full_tracked_url(self):
        """Builds the CTA URL with UTM parameters appended."""
        if not self.cta_url or self.cta_type in ("none", "phone", "email", "whatsapp"):
            return self.cta_url
        from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
        parsed = urlparse(self.cta_url)
        params = parse_qs(parsed.query)
        if self.utm_source:
            params["utm_source"] = [self.utm_source]
        if self.utm_medium:
            params["utm_medium"] = [self.utm_medium]
        if self.utm_campaign:
            params["utm_campaign"] = [self.utm_campaign]
        if self.utm_content:
            params["utm_content"] = [self.utm_content]
        flat = {k: v[0] for k, v in params.items()}
        new_query = urlencode(flat)
        return urlunparse(parsed._replace(query=new_query))

    def populate_utm(self):
        """Auto-fill UTM fields from post context."""
        if not self.utm_source:
            plat = self.platform or (self.social_account.platform if self.social_account else "")
            self.utm_source = plat or "direct"
        if not self.utm_medium:
            self.utm_medium = "social"
        if not self.utm_campaign and self.seed:
            self.utm_campaign = str(self.seed.pk)[:8]
        if not self.utm_content:
            self.utm_content = str(self.pk)[:8]

    @property
    def media_warning(self):
        """User-facing warning message for media issues."""
        if self.media_status == self.MediaStatus.FAILED:
            return "Image generation failed. Upload an image or retry."
        if self.needs_media:
            if self.social_account:
                platform_name = self.social_account.get_platform_display()
            else:
                platform_name = (self.platform or "This platform").title()
            return f"{platform_name} requires an image. Upload one before approving."
        return ""


class ABTest(models.Model):
    """A/B Test — group post variants to find the best-performing content."""

    class Status(models.TextChoices):
        GENERATING = "generating", "Generating Variants"
        DRAFT = "draft", "Variants Ready"
        RUNNING = "running", "Running"
        CONCLUDED = "concluded", "Concluded"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="ab_tests",
    )
    name = models.CharField(max_length=255)
    seed = models.ForeignKey(
        ContentSeed, on_delete=models.SET_NULL, null=True, blank=True, related_name="ab_tests",
    )
    social_account = models.ForeignKey(
        "platforms.SocialAccount", on_delete=models.SET_NULL, null=True, blank=True, related_name="ab_tests",
    )
    platform = models.CharField(
        max_length=20, blank=True, db_index=True,
        help_text="Denormalized platform name — preserved when social_account is disconnected.",
    )
    variant_count = models.PositiveSmallIntegerField(default=3)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.GENERATING, db_index=True,
    )
    winner = models.ForeignKey(
        "Post", on_delete=models.SET_NULL, null=True, blank=True, related_name="+",
    )
    test_duration_hours = models.PositiveIntegerField(
        default=48, help_text="Hours after last variant published before declaring winner.",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    concluded_at = models.DateTimeField(null=True, blank=True)
    conclusion_summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "A/B Test"
        verbose_name_plural = "A/B Tests"

    def __str__(self):
        return f"A/B: {self.name[:50]}"

    @property
    def is_overdue(self):
        """True if running and past its test duration window."""
        if self.status != self.Status.RUNNING or not self.started_at:
            return False
        from django.utils import timezone as tz
        from datetime import timedelta
        return tz.now() > self.started_at + timedelta(hours=self.test_duration_hours)


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


class PostVersion(models.Model):
    """Immutable snapshot of a post's content, created on each edit or regeneration."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="versions")
    version_number = models.PositiveIntegerField()
    content_text = models.TextField()
    source = models.CharField(
        max_length=20,
        choices=[("user_edit", "User Edit"), ("regeneration", "AI Regeneration"), ("creation", "Created")],
        default="user_edit",
    )
    edited_by = models.ForeignKey(
        "accounts.User", on_delete=models.SET_NULL, null=True, blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-version_number"]
        unique_together = [("post", "version_number")]

    def __str__(self):
        return f"v{self.version_number} of {self.post_id}"
