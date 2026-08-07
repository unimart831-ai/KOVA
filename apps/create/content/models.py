import uuid
from django.conf import settings
from django.db import models

from apps.core.accounts.soft_delete import SoftDeleteMixin


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
    product = models.ForeignKey(
        "products.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="content_seeds",
        help_text="Product this seed promotes. Enables product-to-content pipeline tracking.",
    )
    idea = models.TextField(help_text="Your raw idea, topic, or content seed.")
    notes = models.TextField(blank=True, help_text="Additional context or instructions for the AI.")
    template_family = models.CharField(
        max_length=40,
        blank=True,
        default="",
        db_index=True,
        help_text="Canonical Template Family key (e.g. offer, booking_cta). See template_families.py.",
    )
    target_platforms = models.JSONField(
        default=list, blank=True,
        help_text='Platforms to generate for, e.g. ["twitter", "linkedin"]. Empty = all connected.',
    )
    generate_images = models.BooleanField(
        default=False,
        help_text="When True, generate AI images for ALL platforms (not just visual-first ones like Instagram).",
    )
    class Intent(models.TextChoices):
        PROBLEM_AWARENESS = "problem_awareness", "Problem Awareness"
        SOLUTION = "solution", "Solution Education"
        PROOF = "proof", "Proof / Testimonial"
        OFFER = "offer", "Offer / CTA"
        AUTHORITY = "authority", "Authority / Expertise"

    status = models.CharField(max_length=20, choices=SeedStatus.choices, default=SeedStatus.NEW, db_index=True)
    target_intent = models.CharField(
        max_length=30, choices=Intent.choices, blank=True,
        help_text="Content intent the Strategist wants this seed to target.",
    )
    error_message = models.TextField(blank=True)
    generation_log = models.JSONField(
        default=list,
        blank=True,
        help_text="Live Create Agent steps shown during post generation.",
    )
    batch_strategy = models.TextField(blank=True, help_text="AI-generated content strategy for this batch of posts.")
    blueprint = models.JSONField(
        default=dict,
        blank=True,
        help_text="ContentBlueprint spec — platform slots and objective from BusinessAsset.",
    )
    weekly_plan = models.ForeignKey(
        "WeeklyContentPlan",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="seeds",
        help_text="Set when this seed was created by Content Autopilot.",
    )
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


class MarketingCampaign(models.Model):
    """
    One marketing campaign — user-facing unit (internally tied to ContentSeed).

    A campaign bundles reel + carousel + posts + commerce destination for one opportunity.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        GENERATING = "generating", "Generating"
        REVIEW = "review", "Ready for review"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"
        FAILED = "failed", "Failed"

    class Objective(models.TextChoices):
        SALES = "sales", "Sales"
        LEADS = "leads", "Leads"
        AWARENESS = "awareness", "Awareness"
        BOOKINGS = "bookings", "Bookings"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="marketing_campaigns",
    )
    content_seed = models.OneToOneField(
        ContentSeed, on_delete=models.CASCADE, related_name="marketing_campaign",
    )
    business_asset = models.ForeignKey(
        "products.BusinessAsset", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="marketing_campaigns",
    )
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=80, blank=True)
    objective = models.CharField(
        max_length=20, choices=Objective.choices, default=Objective.SALES,
    )
    template_family = models.CharField(
        max_length=40,
        blank=True,
        default="",
        db_index=True,
        help_text="Canonical Template Family key selected for this campaign.",
    )
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True,
    )
    quality_score = models.PositiveSmallIntegerField(
        null=True, blank=True,
        help_text="Campaign quality 0–100 from blueprint QA.",
    )
    proposal_meta = models.JSONField(
        default=dict, blank=True,
        help_text="Seed proposal angle, formats, rationale when picked from multi-proposal flow.",
    )
    commerce_url = models.URLField(blank=True, help_text="Campaign or product commerce page CTA.")
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        db_index=True,
        help_text="When the offer ends — campaign page auto-archives after this.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return self.title[:80]


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
        BLOCKED = "blocked", "Blocked (Policy)"
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
    product = models.ForeignKey(
        "products.Product", on_delete=models.SET_NULL, null=True, blank=True, related_name="posts",
        help_text="Product this post promotes. Inherited from seed or set directly.",
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
    content_intent = models.CharField(
        max_length=30, choices=ContentSeed.Intent.choices, blank=True,
        help_text="What this post is designed to do: attract attention, educate, prove, offer, or build authority.",
    )
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

    # ── Post format — explicit format type for publishing routing ───────────
    class PostFormat(models.TextChoices):
        TEXT = "text", "Text"
        IMAGE = "image", "Image"
        CAROUSEL = "carousel", "Carousel"
        STORY = "story", "Story"
        REEL = "reel", "Reel"
        VIDEO = "video", "Video"

    post_format = models.CharField(
        max_length=20, choices=PostFormat.choices, default=PostFormat.TEXT, db_index=True,
        help_text="The content format — drives which publish API endpoint is called.",
    )

    # Carousel slides — ordered array of slide data
    # Structure: [{"heading": str, "body": str, "image_prompt": str, "image_url": str}]
    carousel_slides = models.JSONField(
        default=list, blank=True,
        help_text="Ordered carousel slides. Each: {heading, body, image_prompt, image_url}.",
    )

    # Aspect ratio — hints image generation and delivery format
    class AspectRatio(models.TextChoices):
        SQUARE = "square", "Square (1:1)"
        PORTRAIT = "portrait", "Portrait (4:5)"
        LANDSCAPE = "landscape", "Landscape (16:9)"
        STORY = "story", "Story / Reel (9:16)"

    aspect_ratio = models.CharField(
        max_length=20, choices=AspectRatio.choices, default=AspectRatio.SQUARE, blank=True,
        help_text="Aspect ratio for image/video generation. Derived from post_format if not set.",
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
    first_comment = models.TextField(blank=True, help_text="First comment to post immediately after publishing. Used for Facebook (links in body reduce organic reach 50-70%) and LinkedIn (link-in-comments drives more profile clicks). Auto-populated for Facebook when a product or website URL is available.")
    publish_error = models.TextField(
        blank=True,
        help_text="Last publish failure message from the platform API (shown in Queue).",
    )

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
            models.Index(fields=["user", "status", "published_at"], name="content_post_user_pub_idx"),
        ]

    def __str__(self):
        return f"{self.get_status_display()} — {self.content_text[:60]}"

    @property
    def publish_needs_retry(self) -> bool:
        """True when publish failed or was blocked by QA — show Retry in queue."""
        if self.status == self.Status.FAILED:
            return True
        return (self.ai_reasoning or "").startswith("QA GATE")

    @property
    def publish_failure_message(self) -> str:
        """User-facing publish failure text for Queue / detail views."""
        if self.publish_error:
            return self.publish_error
        if self.ai_reasoning and self.ai_reasoning.startswith("Publish error:"):
            return self.ai_reasoning[len("Publish error:"):].strip()
        if self.ai_reasoning and self.ai_reasoning.startswith("QA GATE"):
            return self.ai_reasoning
        return ""

    @property
    def has_media(self):
        """True if the post has at least one image/video attached."""
        if self.post_format == self.PostFormat.REEL and self.reel_has_video:
            return True
        return bool(self.media_urls) or self.attachments.exists()

    @property
    def reel_meta(self):
        return self.visual_metadata or {}

    @property
    def reel_compose_status(self):
        if self.post_format != self.PostFormat.REEL:
            return ""
        return self.reel_meta.get("video_compose_status", "")

    @property
    def reel_compose_backend(self):
        """Resolved reel production backend for UI labels."""
        if self.post_format != self.PostFormat.REEL:
            return ""
        backend = self.reel_meta.get("reel_compose_backend")
        if backend:
            return backend
        if self.reel_meta.get("prefer_kling_video"):
            return "kling"
        if self.reel_meta.get("prefer_photoroom_video"):
            return "photoroom"
        return "ffmpeg"

    @property
    def reel_compose_backend_label(self):
        from apps.create.media.labels import reel_backend_label

        return reel_backend_label(self.reel_compose_backend or "ffmpeg")

    @property
    def reel_compose_hint(self):
        from apps.create.media.labels import reel_compose_hint

        return reel_compose_hint(self.reel_compose_backend or "ffmpeg")

    @property
    def carousel_backend_label(self):
        from apps.create.media.labels import carousel_backend_label

        meta = self.visual_metadata or {}
        return carousel_backend_label(meta.get("carousel_backend", "local"))

    @property
    def reel_has_video(self):
        from apps.create.content.video_compose import is_video_url

        video_url = self.reel_meta.get("reel_video_url")
        if video_url and is_video_url(video_url):
            return True
        for url in self.media_urls or []:
            if is_video_url(url):
                return True
        return self.attachments.filter(file_type="video").exists()

    @property
    def reel_video_url(self):
        if self.reel_meta.get("reel_video_url"):
            return self.reel_meta["reel_video_url"]
        from apps.create.content.video_compose import is_video_url

        for url in self.media_urls or []:
            if is_video_url(url):
                return url
        video_att = self.attachments.filter(file_type="video").order_by("order").first()
        if video_att and video_att.file:
            return video_att.file.url
        return ""

    @property
    def reel_thumbnail_url(self):
        thumb = self.reel_meta.get("reel_thumbnail_url")
        if thumb:
            return thumb
        from apps.create.content.video_compose import is_video_url

        for url in self.media_urls or []:
            if url and not is_video_url(url):
                return url
        for att in self.attachments.filter(file_type="image").order_by("order"):
            if att.file:
                return att.file.url
        sources = self.reel_meta.get("source_images") or []
        return sources[0] if sources else ""

    @property
    def reel_is_carousel_variant(self):
        return (
            self.post_format == self.PostFormat.REEL
            and self.reel_meta.get("reel_template") == "carousel_to_video"
        )

    @property
    def reel_compose_pending(self):
        if self.post_format != self.PostFormat.REEL:
            return False
        if self.reel_compose_status == "pending":
            return True
        if self.reel_has_video:
            return False
        if self.reel_compose_status == "failed":
            return False
        # Images/source slides exist but MP4 not ready yet (queued or starting)
        return bool(
            self.reel_meta.get("source_images")
            or self.media_urls
            or self.attachments.filter(file_type="image").exists()
        )

    @property
    def media_processing(self):
        """True while AI images or motion reel composition are in progress."""
        if self.media_status == self.MediaStatus.PENDING:
            return True
        return self.reel_compose_pending

    @property
    def reel_source_slide_urls(self):
        """Source images used before reel composition (carousel → reel)."""
        urls = list(self.reel_meta.get("source_images") or [])
        if urls:
            return urls
        from apps.create.content.video_compose import is_video_url

        return [u for u in (self.media_urls or []) if u and not is_video_url(u)]

    @property
    def needs_media(self):
        """True if this post's platform requires media and none is attached."""
        plat = self.platform or (self.social_account.platform if self.social_account else "")
        return plat in self.MEDIA_REQUIRED_PLATFORMS and not self.has_media

    @property
    def full_tracked_url(self):
        """Builds the CTA URL with UTM parameters appended."""
        return self.tracked_url(self.cta_url) if self.cta_url and self.cta_type not in (
            "none", "phone", "email", "whatsapp"
        ) else self.cta_url

    def tracked_url(self, url):
        """Canonical UTM injector — append THIS post's UTM fields to any URL.

        Used by the publishing pipeline (apps/content/tasks.py) so every link
        in the post body, first comment, and CTA gets attributed back to this
        post and the campaign that owns it. This is the load-bearing function
        for revenue attribution.

        Idempotent: returns the URL unchanged if it's empty, not http(s), or
        already carries any `utm_*` parameter. Auto-fills the Post's UTM
        fields from context (platform, seed, post id) if they aren't set yet,
        but does NOT save them — the caller should `populate_utm()` + save
        before publish if it wants the values persisted.
        """
        if not url:
            return url
        if not (url.startswith("http://") or url.startswith("https://")):
            return url
        from urllib.parse import urlencode, urlparse, parse_qs, urlunparse
        parsed = urlparse(url)
        params = parse_qs(parsed.query)
        # Don't overwrite if any UTM is already present on the URL.
        if any(k.startswith("utm_") for k in params):
            return url

        # Use the Post's UTM if present, else derive from context.
        utm_source = self.utm_source or (
            self.platform or (self.social_account.platform if self.social_account_id else "") or "direct"
        )
        utm_medium = self.utm_medium or "social"
        utm_campaign = self.utm_campaign or (str(self.seed_id)[:8] if self.seed_id else f"kova_{str(self.pk)[:8]}")
        # utm_content is the post id prefix — used by Pixel attribution at
        # apps/analytics/pixel.py:_attribute_to_post to range-query Post.id.
        utm_content = self.utm_content or str(self.pk)[:8]

        params["utm_source"] = [utm_source]
        params["utm_medium"] = [utm_medium]
        params["utm_campaign"] = [utm_campaign]
        params["utm_content"] = [utm_content]
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
            try:
                campaign = self.seed.marketing_campaign
            except Exception:
                campaign = None
            if campaign and campaign.slug:
                self.utm_campaign = campaign.slug[:100]
            else:
                self.utm_campaign = str(self.seed.pk)[:8]
        if not self.utm_content:
            self.utm_content = str(self.pk)[:8]

    @property
    def media_warning(self):
        """User-facing warning message for media issues."""
        if self.post_format == self.PostFormat.REEL:
            if self.reel_compose_status == "failed":
                err = self.reel_meta.get("video_compose_error", "")
                base = "Motion reel failed to compose."
                return f"{base} {err}".strip() if err else base
            if self.reel_compose_pending:
                return ""
        if self.media_status == self.MediaStatus.FAILED:
            if self.post_format == self.PostFormat.REEL:
                return "Image step failed. Retry or re-compose the reel."
            if self.post_format == self.PostFormat.STORY:
                return "Story image generation failed. Upload a 9:16 image or retry."
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


# ══════════════════════════════════════════════════════════════════════════════
# VOICE TO CAMPAIGN — Record a voice memo, AI builds an entire campaign
# ══════════════════════════════════════════════════════════════════════════════


class VoiceBrief(models.Model):
    """
    Voice memo → AI transcription → intent extraction → full campaign.

    A seller records a 30-second voice note ("I just restocked Samsung A54,
    push it hard this week on IG and email my list") and Kova auto-generates:
    Campaign + multi-platform ContentSeeds + optional EmailCampaign.
    """

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        TRANSCRIBING = "transcribing", "Transcribing Audio"
        EXTRACTING = "extracting", "Extracting Intent"
        GENERATING = "generating", "Generating Campaign"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="voice_briefs",
    )
    audio_file = models.FileField(
        upload_to="voice_briefs/%Y/%m/",
        help_text="Audio file (mp3, m4a, ogg, wav, webm) — max 5 minutes",
    )
    duration_seconds = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Duration extracted from audio metadata",
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.UPLOADED, db_index=True,
    )

    # ── AI transcription ──
    transcript = models.TextField(
        blank=True,
        help_text="Whisper-generated transcript of the voice memo",
    )
    language_detected = models.CharField(
        max_length=10, blank=True,
        help_text="Detected language code (en, sw, sheng, etc.)",
    )

    # ── AI intent extraction ──
    ai_extraction = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Structured extraction from transcript:\n"
            '{"products": ["Samsung A54"], "platforms": ["instagram", "facebook"],\n'
            ' "urgency": "this_week", "audience": "students",\n'
            ' "cta_type": "whatsapp", "tone": "excited",\n'
            ' "key_message": "Back in stock at KES 45,000",\n'
            ' "include_email": true, "budget_hint": null}'
        ),
    )

    # ── Generated outputs ──
    campaign = models.ForeignKey(
        "content.MarketingCampaign", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="voice_briefs",
        help_text="The marketing campaign auto-generated from this voice brief",
    )
    seeds_created = models.PositiveIntegerField(
        default=0,
        help_text="Number of content seeds generated",
    )
    email_campaign = models.ForeignKey(
        "emails.EmailCampaign", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="voice_briefs",
        help_text="Optional email campaign generated if user mentioned email/subscribers",
    )

    # ── Metadata ──
    error_message = models.TextField(blank=True)
    processing_time_ms = models.PositiveIntegerField(
        null=True, blank=True,
        help_text="Total wall-clock processing time in milliseconds",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"VoiceBrief {self.pk} ({self.get_status_display()})"


class WeeklyContentPlan(models.Model):
    """
    AI Content Autopilot — weekly content planning with preview-before-generate.

    Lifecycle:
      planning → pending_review → (user approves) → generating → active → completed
    """

    class Status(models.TextChoices):
        PLANNING = "planning", "Planning"
        PENDING_REVIEW = "pending_review", "Awaiting Your Approval"
        GENERATING = "generating", "Generating Content"
        SCHEDULING = "scheduling", "Optimizing Schedule"
        ACTIVE = "active", "Active — Publishing"
        COMPLETED = "completed", "Week Completed"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="weekly_content_plans",
    )
    week_start = models.DateField(help_text="Monday of the plan week")
    week_end = models.DateField(help_text="Sunday of the plan week")
    status = models.CharField(max_length=15, choices=Status.choices, default=Status.PLANNING, db_index=True)

    # Strategist output
    strategy = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Strategist's weekly plan: {theme, goals, daily_topics: "
            "[{day, topic, intent, platforms, notes}], content_mix}"
        ),
    )
    strategy_reasoning = models.TextField(blank=True, help_text="Why the Strategist chose this strategy")
    planning_log = models.JSONField(
        default=list, blank=True,
        help_text="Live strategist steps shown during plan preview generation.",
    )

    # Execution tracking
    seeds_created = models.PositiveIntegerField(default=0)
    posts_generated = models.PositiveIntegerField(default=0)
    posts_published = models.PositiveIntegerField(default=0)
    posts_failed = models.PositiveIntegerField(default=0)

    # Performance (populated after the week completes)
    performance_summary = models.JSONField(
        default=dict, blank=True,
        help_text="Post-week performance: {total_impressions, total_engagement, avg_engagement_rate, top_post_id}",
    )

    # Email digest
    review_email_sent = models.BooleanField(default=False)
    review_email_sent_at = models.DateTimeField(null=True, blank=True)

    # Error tracking
    error_message = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-week_start"]
        unique_together = ["user", "week_start"]
        indexes = [
            models.Index(fields=["user", "status", "-week_start"]),
        ]

    def __str__(self):
        return f"Week of {self.week_start} — {self.get_status_display()}"


class ContentSafetyIncident(models.Model):
    """Logged when content fails moderation — staff review queue."""

    class Source(models.TextChoices):
        SNAP = "snap", "Snap to Sell"
        BATCH_SNAP = "batch_snap", "Batch Snap"
        PUBLISH = "publish", "Publish gate"
        APPROVE = "approve", "Approval gate"
        UPLOAD = "upload", "Upload"
        VISION = "vision", "Vision analyze"

    class ReviewStatus(models.TextChoices):
        PENDING = "pending", "Pending review"
        DISMISSED = "dismissed", "Dismissed (false positive)"
        CONFIRMED = "confirmed", "Confirmed violation"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="content_safety_incidents",
    )
    post = models.ForeignKey(
        Post,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="safety_incidents",
    )
    source = models.CharField(max_length=20, choices=Source.choices, db_index=True)
    image_url = models.CharField(
        max_length=2000,
        blank=True,
        help_text="HTTPS URL or private storage path for staff review.",
    )
    reasons = models.JSONField(default=list, blank=True)
    categories = models.JSONField(default=list, blank=True)
    severity = models.PositiveSmallIntegerField(default=0, db_index=True)
    review_status = models.CharField(
        max_length=20,
        choices=ReviewStatus.choices,
        default=ReviewStatus.PENDING,
        db_index=True,
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_safety_incidents",
    )
    action_taken = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["review_status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Incident {self.pk} — {self.user.email} ({self.get_source_display()})"


class SystemSafetyConfig(models.Model):
    """Singleton platform-wide content safety controls."""

    auto_publish_paused = models.BooleanField(
        default=False,
        help_text="When True, no posts are auto-published platform-wide.",
    )
    paused_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    paused_at = models.DateTimeField(null=True, blank=True)
    content_safety_checks_enabled = models.BooleanField(
        default=True,
        help_text=(
            "When False, staff have paused all moderation checks "
            "(vision, API text, local blocklist). Env CONTENT_SAFETY_ENABLED "
            "must still be true for this to take effect."
        ),
    )
    content_safety_paused_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    content_safety_paused_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "System Safety Configuration"
        verbose_name_plural = "System Safety Configuration"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)
        SystemSafetyConfig._cached = None

    @classmethod
    def load(cls):
        if getattr(cls, "_cached", None) is not None:
            return cls._cached
        try:
            obj = cls.objects.get(pk=1)
        except cls.DoesNotExist:
            obj = cls()
        cls._cached = obj
        return obj

    _cached = None

    def __str__(self):
        state = "paused" if self.auto_publish_paused else "active"
        return f"SystemSafetyConfig ({state})"
