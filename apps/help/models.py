import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Article(models.Model):
    """
    A help/educational article. Serves both in-product help (audience=user)
    and the public SEO blog (audience=prospect). Migrated from the static
    ARTICLES registry in apps.help.views; new entries are authored by the
    Educator agent and gated by founder review before publish.
    """

    class Category(models.TextChoices):
        GETTING_STARTED = "getting-started", "Getting Started"
        CONTENT = "content", "Content & Publishing"
        AGENTS = "agents", "AI Agents"
        ANALYTICS = "analytics", "Analytics & Insights"
        ACCOUNT = "account", "Account & Billing"
        TIPS = "tips", "Tips & Best Practices"
        PRODUCT_UPDATES = "product-updates", "Product Updates"

    class Audience(models.TextChoices):
        USER = "user", "In-product users"
        PROSPECT = "prospect", "Public / prospects"
        BOTH = "both", "Both"

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        REVIEW = "review", "Ready for Review"
        PUBLISHED = "published", "Published"
        ARCHIVED = "archived", "Archived"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    slug = models.SlugField(max_length=120, unique=True, db_index=True)
    title = models.CharField(max_length=200)
    excerpt = models.CharField(
        max_length=300,
        blank=True,
        default="",
        help_text="Short description shown on cards and in search results.",
    )
    body_md = models.TextField(
        blank=True,
        default="",
        help_text="Markdown source. Rendered to body_html on save.",
    )
    body_html = models.TextField(
        blank=True,
        default="",
        help_text="Cached HTML rendered from body_md.",
    )
    category = models.CharField(
        max_length=30,
        choices=Category.choices,
        default=Category.GETTING_STARTED,
        db_index=True,
    )
    audience = models.CharField(
        max_length=10,
        choices=Audience.choices,
        default=Audience.USER,
        db_index=True,
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.DRAFT,
        db_index=True,
    )
    order = models.PositiveSmallIntegerField(
        default=0,
        help_text="Sort order within a category. Lower = earlier.",
    )
    hero_image = models.CharField(
        max_length=500,
        blank=True,
        default="",
        help_text="URL to the article's hero image (R2 or external).",
    )
    meta_title = models.CharField(
        max_length=70,
        blank=True,
        default="",
        help_text="SEO <title>. Falls back to title when blank.",
    )
    meta_description = models.CharField(
        max_length=160,
        blank=True,
        default="",
        help_text="SEO meta description. Falls back to excerpt when blank.",
    )
    tags = models.JSONField(default=list, blank=True)
    reading_minutes = models.PositiveSmallIntegerField(default=1)

    # Authorship & review
    author_agent = models.CharField(
        max_length=30,
        blank=True,
        default="",
        help_text="Agent that drafted this article (e.g. 'educator'). Blank if human-authored.",
    )
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="articles_reviewed",
        help_text="Founder/staff user who approved publication.",
    )

    # Legacy template support: articles migrated from the static registry
    # still render via their original templates/help/articles/{slug}.html file
    # until their bodies are ported to markdown. Leave blank for new articles.
    legacy_template = models.CharField(
        max_length=200,
        blank=True,
        default="",
        help_text="Legacy template path for migrated articles. Blank for markdown-rendered articles.",
    )

    view_count = models.PositiveIntegerField(default=0)
    published_at = models.DateTimeField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "order", "title"]
        indexes = [
            models.Index(fields=["status", "audience", "-published_at"]),
            models.Index(fields=["category", "order"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.get_status_display()})"

    @property
    def description(self) -> str:
        """Alias used by card/search templates that were written against the
        legacy static-registry shape. New code should reference .excerpt."""
        return self.excerpt

    @property
    def is_published(self) -> bool:
        return self.status == self.Status.PUBLISHED

    @property
    def is_public(self) -> bool:
        return self.is_published and self.audience in (
            self.Audience.PROSPECT,
            self.Audience.BOTH,
        )

    @property
    def is_in_app(self) -> bool:
        return self.is_published and self.audience in (
            self.Audience.USER,
            self.Audience.BOTH,
        )

    def mark_published(self, reviewer=None):
        self.status = self.Status.PUBLISHED
        self.published_at = timezone.now()
        if reviewer is not None:
            self.reviewed_by = reviewer
        self.save(update_fields=["status", "published_at", "reviewed_by", "updated_at"])

    def save(self, *args, **kwargs):
        from apps.utils.html_sanitize import sanitize_html

        if self.body_html:
            self.body_html = sanitize_html(self.body_html)
        super().save(*args, **kwargs)


class ArticleTopic(models.Model):
    """A candidate topic for the Educator agent to draft an article about.
    Seeded manually or suggested by the Research agent."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        DRAFTED = "drafted", "Drafted"
        SKIPPED = "skipped", "Skipped"

    class Source(models.TextChoices):
        MANUAL = "manual", "Manual"
        RESEARCH = "research", "Research agent"
        GAP = "gap", "Content gap"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200, unique=True)
    rationale = models.TextField(
        blank=True,
        default="",
        help_text="Why this topic matters — shown to the agent in its prompt.",
    )
    suggested_category = models.CharField(
        max_length=30,
        choices=Article.Category.choices,
        default=Article.Category.TIPS,
    )
    audience = models.CharField(
        max_length=10,
        choices=Article.Audience.choices,
        default=Article.Audience.USER,
    )
    priority = models.PositiveSmallIntegerField(
        default=50,
        help_text="Higher number = drafted sooner. 0-100.",
    )
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.MANUAL)
    drafted_article = models.ForeignKey(
        Article,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="topic",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    drafted_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-priority", "created_at"]
        indexes = [models.Index(fields=["status", "-priority"])]

    def __str__(self):
        return self.title


class ChangelogEntry(models.Model):
    """A shipped feature, fix, or announcement. Feeds the weekly Kova Report."""

    class Category(models.TextChoices):
        FEATURE = "feature", "New Feature"
        IMPROVEMENT = "improvement", "Improvement"
        FIX = "fix", "Fix"
        ANNOUNCEMENT = "announcement", "Announcement"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=200)
    body_md = models.TextField(
        blank=True,
        default="",
        help_text="Markdown description, 1-3 sentences. Shown in the newsletter.",
    )
    category = models.CharField(
        max_length=15, choices=Category.choices, default=Category.FEATURE, db_index=True,
    )
    shipped_at = models.DateTimeField(default=timezone.now, db_index=True)
    is_public = models.BooleanField(
        default=True,
        help_text="Include in public newsletter. Uncheck for internal-only notes.",
    )
    linked_article = models.ForeignKey(
        Article,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="changelog_mentions",
        help_text="Optional deep-dive article for this change.",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-shipped_at"]
        verbose_name_plural = "Changelog entries"

    def __str__(self):
        return f"[{self.get_category_display()}] {self.title}"


class WeeklyDigest(models.Model):
    """The 'Kova This Week' platform-wide newsletter section. Compiled by the
    Educator from ChangelogEntry + recent Articles, founder-approved, then
    appended to the existing per-user weekly report email."""

    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        APPROVED = "approved", "Approved"
        SENT = "sent", "Sent"
        SKIPPED = "skipped", "Skipped"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    week_end = models.DateField(
        unique=True,
        help_text="Sunday (inclusive) of the week this digest covers.",
    )
    intro_html = models.TextField(blank=True, default="")
    changelog_html = models.TextField(blank=True, default="")
    articles_html = models.TextField(blank=True, default="")
    stats_html = models.TextField(blank=True, default="")
    raw_content = models.JSONField(
        default=dict,
        blank=True,
        help_text="Structured output from the Educator agent (before HTML render).",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.DRAFT, db_index=True,
    )
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="digests_approved",
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-week_end"]

    def __str__(self):
        return f"Kova Digest — week ending {self.week_end} ({self.get_status_display()})"

    def combined_html(self) -> str:
        """Render the three sections into one block for the weekly email."""
        parts = [self.intro_html, self.changelog_html, self.articles_html, self.stats_html]
        return "\n".join(p for p in parts if p.strip())

    def approve(self, user):
        self.status = self.Status.APPROVED
        self.approved_by = user
        self.approved_at = timezone.now()
        self.save(update_fields=["status", "approved_by", "approved_at", "updated_at"])

    def save(self, *args, **kwargs):
        from apps.utils.html_sanitize import sanitize_html

        for field in ("intro_html", "changelog_html", "articles_html", "stats_html"):
            value = getattr(self, field, "")
            if value:
                setattr(self, field, sanitize_html(value))
        super().save(*args, **kwargs)


class NewsletterSubscriber(models.Model):
    """Public newsletter signup — collected from the /blog/ surface. These are
    PROSPECTS (no User account required), kept separate from the tenant-scoped
    apps.emails.EmailSubscriber model which belongs to individual Kova users."""

    class Source(models.TextChoices):
        BLOG = "blog", "Blog subscribe form"
        LANDING = "landing", "Landing page"
        ARTICLE = "article", "Article footer"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        UNSUBSCRIBED = "unsubscribed", "Unsubscribed"
        BOUNCED = "bounced", "Bounced"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField(unique=True, db_index=True)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.ACTIVE, db_index=True,
    )
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.BLOG)
    source_slug = models.CharField(
        max_length=120, blank=True, default="",
        help_text="If signed up from a specific article, the article slug.",
    )
    unsubscribe_token = models.CharField(
        max_length=64, unique=True, db_index=True, blank=True, default="",
    )
    subscribed_at = models.DateTimeField(auto_now_add=True)
    unsubscribed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-subscribed_at"]
        indexes = [models.Index(fields=["status", "-subscribed_at"])]

    def __str__(self):
        return f"{self.email} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        if not self.unsubscribe_token:
            import secrets
            self.unsubscribe_token = secrets.token_urlsafe(32)
        super().save(*args, **kwargs)

    def unsubscribe(self):
        self.status = self.Status.UNSUBSCRIBED
        self.unsubscribed_at = timezone.now()
        self.save(update_fields=["status", "unsubscribed_at"])


class HelpPageView(models.Model):
    """Tracks each help article view for usage analytics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="help_views",
    )
    page_type = models.CharField(
        max_length=20,
        choices=[("center", "Help Center"), ("article", "Article")],
    )
    article_slug = models.CharField(max_length=120, blank=True, default="")
    article_title = models.CharField(max_length=255, blank=True, default="")
    category = models.CharField(max_length=60, blank=True, default="")
    viewed_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-viewed_at"]
        indexes = [
            models.Index(fields=["article_slug", "viewed_at"]),
            models.Index(fields=["user", "viewed_at"]),
        ]

    def __str__(self):
        if self.article_slug:
            return f"{self.user} → {self.article_slug} @ {self.viewed_at:%Y-%m-%d %H:%M}"
        return f"{self.user} → Help Center @ {self.viewed_at:%Y-%m-%d %H:%M}"
