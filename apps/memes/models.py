"""
Meme Intelligence Engine — models.

Captures the full meme lifecycle:
- Trend discovery (what's going viral in Kenya / globally)
- Meme ranking (virality, brand-safety, cultural relevance)
- Brand adaptation (remix trending formats with user's brand context)
- Cultural calendar (Kenyan events, holidays, cultural moments)
"""

import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


# ─── TRENDING MEME ───────────────────────────────────────────────────────────

class TrendingMeme(models.Model):
    """
    A detected meme trend or viral format.

    Discovered by the Meme Discovery task (Celery) which uses the Research Agent
    pattern — LLM + web search to identify what's trending, score it, and extract
    the reusable format.

    Memes have a shelf life. A meme trending today is stale by Friday.
    The `lifecycle` field tracks where the meme is in its viral curve.
    """

    class Category(models.TextChoices):
        SOCIAL = "social", "Social / Lifestyle"
        POLITICAL = "political", "Political"
        SPORTS = "sports", "Sports"
        ENTERTAINMENT = "entertainment", "Entertainment"
        BUSINESS = "business", "Business / Finance"
        TECH = "tech", "Tech"
        FOOD = "food", "Food / Culture"
        MUSIC = "music", "Music"
        EDUCATION = "education", "Education"
        GENERAL = "general", "General Humor"

    class HumorType(models.TextChoices):
        OBSERVATIONAL = "observational", "Observational"
        SATIRICAL = "satirical", "Satirical"
        ABSURD = "absurd", "Absurd / Surreal"
        WORDPLAY = "wordplay", "Wordplay / Puns"
        SITUATIONAL = "situational", "Situational"
        RELATABLE = "relatable", "Relatable / Everyday"
        SELF_DEPRECATING = "self_deprecating", "Self-Deprecating"
        REACTION = "reaction", "Reaction / Response"

    class Lifecycle(models.TextChoices):
        EMERGING = "emerging", "Emerging"          # Just starting to trend
        TRENDING = "trending", "Trending"          # Peak virality window
        PEAKED = "peaked", "Peaked"                # Still relevant but slowing
        FADING = "fading", "Fading"                # Being overused
        DEAD = "dead", "Dead"                      # Don't use — stale

    class SourcePlatform(models.TextChoices):
        TWITTER = "twitter", "Twitter/X"
        TIKTOK = "tiktok", "TikTok"
        INSTAGRAM = "instagram", "Instagram"
        FACEBOOK = "facebook", "Facebook"
        REDDIT = "reddit", "Reddit"
        YOUTUBE = "youtube", "YouTube"
        WHATSAPP = "whatsapp", "WhatsApp"
        CROSS_PLATFORM = "cross_platform", "Cross-Platform"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # Core meme info
    title = models.CharField(max_length=255, help_text="Short name for the meme/trend")
    description = models.TextField(help_text="What this meme is about and why it's trending")
    format_description = models.TextField(
        help_text="The reusable FORMAT of the meme — the template others can adapt. "
        "E.g., 'Top text: expectation. Bottom text: reality with a twist.'"
    )
    example_text = models.TextField(
        blank=True,
        help_text="An example of this meme in the wild (the original or a popular version)",
    )
    image_description = models.TextField(
        blank=True,
        help_text="Description of the visual component if it's an image meme",
    )

    # Classification
    category = models.CharField(max_length=20, choices=Category.choices, default=Category.GENERAL, db_index=True)
    humor_type = models.CharField(max_length=20, choices=HumorType.choices, default=HumorType.RELATABLE)
    source_platform = models.CharField(
        max_length=20, choices=SourcePlatform.choices, default=SourcePlatform.CROSS_PLATFORM,
    )
    source_url = models.URLField(blank=True, help_text="Original source or example URL")

    # Scoring (0-100)
    virality_score = models.PositiveIntegerField(
        default=0, help_text="How viral is this? 0=niche, 100=everyone's sharing it",
    )
    brand_safety_score = models.PositiveIntegerField(
        default=50, help_text="How safe for brands? 0=risky, 100=universally safe",
    )
    cultural_relevance_score = models.PositiveIntegerField(
        default=50, help_text="How culturally relevant to Kenya? 0=foreign, 100=deeply Kenyan",
    )
    adaptability_score = models.PositiveIntegerField(
        default=50, help_text="How easy to adapt to different brands? 0=very niche, 100=universal format",
    )

    # Lifecycle
    lifecycle = models.CharField(max_length=20, choices=Lifecycle.choices, default=Lifecycle.EMERGING, db_index=True)
    detected_at = models.DateTimeField(default=timezone.now)
    peak_at = models.DateTimeField(null=True, blank=True, help_text="When virality peaked")
    expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Estimated expiry — after this, the meme is stale",
    )

    # Metadata
    tags = models.JSONField(default=list, blank=True, help_text="Tags like 'KOT', 'genZ', 'sheng'")
    related_events = models.JSONField(
        default=list, blank=True,
        help_text="Related cultural events or moments driving this meme",
    )
    sensitivity_notes = models.TextField(
        blank=True, help_text="Warnings about political, cultural, or social sensitivity",
    )
    target_demographics = models.JSONField(
        default=list, blank=True,
        help_text="Who this meme resonates with, e.g., ['gen_z', 'nairobi', 'campus']",
    )
    adaptation_count = models.PositiveIntegerField(default=0, help_text="How many brand adaptations created")

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-virality_score", "-detected_at"]
        indexes = [
            models.Index(fields=["lifecycle", "-virality_score"]),
            models.Index(fields=["category", "lifecycle"]),
            models.Index(fields=["-detected_at"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_lifecycle_display()})"

    @property
    def is_usable(self):
        """Can this meme still be adapted? Not dead or expired."""
        if self.lifecycle == self.Lifecycle.DEAD:
            return False
        if self.expires_at and timezone.now() > self.expires_at:
            return False
        return True

    @property
    def overall_score(self):
        """Weighted composite score for ranking."""
        return int(
            self.virality_score * 0.3
            + self.brand_safety_score * 0.25
            + self.cultural_relevance_score * 0.25
            + self.adaptability_score * 0.2
        )


# ─── MEME ADAPTATION ────────────────────────────────────────────────────────

class MemeAdaptation(models.Model):
    """
    A brand-adapted version of a trending meme.

    The AI takes the trending meme's FORMAT and remixes it with the user's
    brand context. This is NOT reposting — it's creating original content
    inspired by the trend format.
    """

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"
        REJECTED = "rejected", "Rejected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meme_adaptations")
    trending_meme = models.ForeignKey(
        TrendingMeme, on_delete=models.CASCADE, related_name="adaptations",
    )

    # Adapted content
    adapted_text = models.TextField(help_text="The brand-adapted meme content")
    adapted_caption = models.TextField(blank=True, help_text="Platform caption for the meme post")
    platform_targets = models.JSONField(
        default=list, help_text='Which platforms to post on, e.g., ["twitter", "instagram"]',
    )
    image_prompt = models.TextField(
        blank=True,
        help_text="AI image generation prompt for visual meme (if applicable)",
    )

    # Scoring
    brand_relevance_score = models.PositiveIntegerField(
        default=0, help_text="How relevant is this adaptation to the user's brand? 0-100",
    )
    humor_preserved_score = models.PositiveIntegerField(
        default=0, help_text="How well does the adaptation preserve the humor? 0-100",
    )

    # Status
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT, db_index=True)
    post = models.ForeignKey(
        "content.Post", on_delete=models.SET_NULL, null=True, blank=True,
        related_name="meme_adaptation",
        help_text="The Post created from this adaptation (once approved and queued)",
    )

    # AI metadata
    ai_reasoning = models.TextField(blank=True, help_text="Why the AI chose this adaptation angle")
    model_used = models.CharField(max_length=100, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status", "-created_at"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"Adaptation of '{self.trending_meme.title}' for {self.user}"


# ─── KENYAN EVENT ────────────────────────────────────────────────────────────

class KenyanEvent(models.Model):
    """
    Cultural calendar entry for Kenya.

    Used by the Meme Discovery engine for contextual awareness:
    - What holidays/events are coming up?
    - What's culturally sensitive right now?
    - What topics have high meme potential?

    Pre-populated with fixture data, admin-editable.
    """

    class EventType(models.TextChoices):
        NATIONAL_HOLIDAY = "national_holiday", "National Holiday"
        CULTURAL = "cultural", "Cultural Event"
        SPORTS = "sports", "Sports Event"
        POLITICAL = "political", "Political Event"
        RELIGIOUS = "religious", "Religious Holiday"
        CAMPUS = "campus", "Campus / Youth Event"
        MUSIC = "music", "Music / Entertainment"
        COMMERCIAL = "commercial", "Commercial / Business"

    class MemePotential(models.TextChoices):
        HIGH = "high", "High"
        MEDIUM = "medium", "Medium"
        LOW = "low", "Low"

    class Sensitivity(models.TextChoices):
        SAFE = "safe", "Safe — universally fine"
        MODERATE = "moderate", "Moderate — be thoughtful"
        SENSITIVE = "sensitive", "Sensitive — tread carefully"
        AVOID = "avoid", "Avoid — don't meme this"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    date = models.DateField(help_text="Date of the event (or start date)")
    end_date = models.DateField(null=True, blank=True, help_text="End date for multi-day events")
    event_type = models.CharField(max_length=20, choices=EventType.choices, db_index=True)
    meme_potential = models.CharField(max_length=10, choices=MemePotential.choices, default=MemePotential.MEDIUM)
    sensitivity = models.CharField(max_length=10, choices=Sensitivity.choices, default=Sensitivity.SAFE)
    annual = models.BooleanField(default=True, help_text="Does this event repeat every year?")
    tags = models.JSONField(default=list, blank=True, help_text="Tags for AI context")
    meme_angles = models.JSONField(
        default=list, blank=True,
        help_text="Suggested meme angles for this event, e.g., ['traffic humor', 'family gatherings']",
    )

    class Meta:
        ordering = ["date"]
        indexes = [
            models.Index(fields=["date", "event_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.date})"

    @property
    def is_upcoming(self):
        """Is this event within the next 7 days?"""
        today = timezone.now().date()
        return today <= self.date <= today + timezone.timedelta(days=7)


# ─── MEME PREFERENCES ───────────────────────────────────────────────────────

class MemePreferences(models.Model):
    """
    Per-user meme preferences — controls what the Meme Engine generates.
    """

    class RiskTolerance(models.TextChoices):
        CONSERVATIVE = "conservative", "Conservative — only universally safe memes"
        MODERATE = "moderate", "Moderate — some edginess OK"
        BOLD = "bold", "Bold — push boundaries (but still brand-safe)"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="meme_preferences",
    )
    is_active = models.BooleanField(
        default=True, help_text="Enable meme discovery and adaptation for this user",
    )
    risk_tolerance = models.CharField(
        max_length=15, choices=RiskTolerance.choices, default=RiskTolerance.MODERATE,
    )
    preferred_categories = models.JSONField(
        default=list, blank=True,
        help_text="Meme categories this user wants, e.g., ['social', 'business', 'food']",
    )
    excluded_categories = models.JSONField(
        default=list, blank=True,
        help_text="Categories to never show, e.g., ['political']",
    )
    preferred_humor_types = models.JSONField(
        default=list, blank=True,
        help_text="Humor types this user likes, e.g., ['relatable', 'wordplay']",
    )
    max_memes_per_week = models.PositiveIntegerField(
        default=5, help_text="Maximum meme posts per week",
    )
    auto_queue = models.BooleanField(
        default=False,
        help_text="Automatically queue approved adaptations to the content pipeline",
    )
    preferred_platforms = models.JSONField(
        default=list, blank=True,
        help_text='Platforms for meme posts, e.g., ["twitter", "instagram"]',
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Meme preferences"

    def __str__(self):
        return f"Meme prefs for {self.user}"
