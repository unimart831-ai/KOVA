import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone
from django.utils.text import slugify


class KovaPage(models.Model):
    """
    A user's link-in-bio / landing page.
    Public URL: /k/<slug>/
    Each user can have multiple pages (plan-gated).
    """

    class ThemeChoices(models.TextChoices):
        MINIMAL = "minimal", "Minimal"
        BOLD = "bold", "Bold"
        GRADIENT = "gradient", "Gradient"
        DARK = "dark", "Dark"
        NEON = "neon", "Neon"
        WARM = "warm", "Warm"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="kova_pages",
    )
    title = models.CharField(max_length=100, help_text="Page headline, e.g. your brand name")
    slug = models.SlugField(
        max_length=60,
        unique=True,
        help_text="URL path: kovaagent.com/k/your-slug",
    )
    bio = models.TextField(max_length=300, blank=True, help_text="Short description under the title")
    avatar_url = models.URLField(blank=True, help_text="Profile image URL")
    theme = models.CharField(
        max_length=20,
        choices=ThemeChoices.choices,
        default=ThemeChoices.MINIMAL,
    )
    custom_css = models.TextField(blank=True, help_text="Pro plan: custom CSS overrides")
    background_color = models.CharField(max_length=7, default="#ffffff", help_text="Hex color")
    text_color = models.CharField(max_length=7, default="#111827", help_text="Hex color")
    accent_color = models.CharField(max_length=7, default="#10B981", help_text="Hex color for buttons")

    # SEO / social sharing
    seo_title = models.CharField(max_length=60, blank=True)
    seo_description = models.CharField(max_length=160, blank=True)
    og_image_url = models.URLField(blank=True, help_text="Social share image")

    # Tracking
    is_published = models.BooleanField(default=True)
    total_views = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["slug"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.slug})"

    def get_absolute_url(self):
        return f"/k/{self.slug}/"

    def save(self, *args, **kwargs):
        from apps.utils.html_sanitize import sanitize_user_css

        if self.custom_css:
            self.custom_css = sanitize_user_css(self.custom_css)
        if not self.slug:
            base = slugify(self.title)[:50]
            slug = base
            n = 1
            while KovaPage.objects.filter(slug=slug).exclude(pk=self.pk).exists():
                slug = f"{base}-{n}"
                n += 1
            self.slug = slug
        super().save(*args, **kwargs)


class KovaLink(models.Model):
    """A single link on a KovaPage (e.g. website, shop, social profile)."""

    class LinkType(models.TextChoices):
        URL = "url", "External URL"
        SOCIAL = "social", "Social Profile"
        EMAIL = "email", "Email"
        PHONE = "phone", "Phone / WhatsApp"
        HEADER = "header", "Section Header"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(
        KovaPage,
        on_delete=models.CASCADE,
        related_name="links",
    )
    link_type = models.CharField(max_length=20, choices=LinkType.choices, default=LinkType.URL)
    title = models.CharField(max_length=100)
    url = models.URLField(blank=True, help_text="Required for URL and Social types")
    icon = models.CharField(max_length=50, blank=True, help_text="Icon name, e.g. 'instagram', 'globe'")
    thumbnail_url = models.URLField(blank=True)
    is_featured = models.BooleanField(default=False, help_text="Highlighted with accent color")
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    # Analytics
    total_clicks = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["order", "-created_at"]
        indexes = [
            models.Index(fields=["page", "order"]),
        ]

    def __str__(self):
        return f"{self.title} → {self.url or self.link_type}"


class LinkClick(models.Model):
    """Tracks each click on a KovaLink for analytics."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    link = models.ForeignKey(
        KovaLink,
        on_delete=models.CASCADE,
        related_name="clicks",
    )
    # Visitor metadata (no PII stored — just aggregate-useful data)
    referrer = models.URLField(blank=True)
    country = models.CharField(max_length=2, blank=True, help_text="ISO country code from GeoIP")
    device_type = models.CharField(
        max_length=10,
        blank=True,
        choices=[("mobile", "Mobile"), ("desktop", "Desktop"), ("tablet", "Tablet")],
    )
    # UTM passthrough — if user arrived at Kova page via a UTM link
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=200, blank=True)

    clicked_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-clicked_at"]
        indexes = [
            models.Index(fields=["link", "-clicked_at"]),
        ]

    def __str__(self):
        return f"Click on {self.link_id} at {self.clicked_at}"


class KovaForm(models.Model):
    """
    A simple lead capture form on a KovaPage.
    Collects name + email + optional custom fields.
    Growth+ feature.
    """

    class FormType(models.TextChoices):
        CONTACT = "contact", "Contact Form"
        NEWSLETTER = "newsletter", "Newsletter Signup"
        WAITLIST = "waitlist", "Waitlist / Interest"
        BOOKING = "booking", "Booking Request"
        CUSTOM = "custom", "Custom Form"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(
        KovaPage,
        on_delete=models.CASCADE,
        related_name="forms",
    )
    form_type = models.CharField(max_length=20, choices=FormType.choices, default=FormType.CONTACT)
    title = models.CharField(max_length=100, default="Get in Touch")
    description = models.TextField(max_length=300, blank=True)
    button_text = models.CharField(max_length=50, default="Submit")
    success_message = models.CharField(max_length=200, default="Thanks! We'll be in touch.")

    # Which fields to show (all optional except email)
    show_name_field = models.BooleanField(default=True)
    show_phone_field = models.BooleanField(default=False)
    show_message_field = models.BooleanField(default=True)
    custom_fields = models.JSONField(
        default=list,
        blank=True,
        help_text='List of {"label": "...", "type": "text|select|textarea", "required": bool, "options": [...]}',
    )

    # Notification settings
    notify_on_submission = models.BooleanField(default=True)
    notification_email = models.EmailField(blank=True, help_text="Override — defaults to account email")

    is_active = models.BooleanField(default=True)
    total_submissions = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.title} on {self.page.title}"


class FormSubmission(models.Model):
    """A single submission from a KovaForm — becomes a Lead in Sprint 6C."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    form = models.ForeignKey(
        KovaForm,
        on_delete=models.CASCADE,
        related_name="submissions",
    )
    # Core fields
    name = models.CharField(max_length=200, blank=True)
    email = models.EmailField()
    phone = models.CharField(max_length=20, blank=True)
    message = models.TextField(blank=True)
    custom_data = models.JSONField(default=dict, blank=True, help_text="Responses to custom fields")

    # Source tracking
    referrer = models.URLField(blank=True)
    utm_source = models.CharField(max_length=100, blank=True)
    utm_medium = models.CharField(max_length=100, blank=True)
    utm_campaign = models.CharField(max_length=200, blank=True)
    page_slug = models.CharField(max_length=60, blank=True, help_text="Which Kova page they were on")

    is_read = models.BooleanField(default=False)
    submitted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-submitted_at"]
        indexes = [
            models.Index(fields=["form", "-submitted_at"]),
            models.Index(fields=["email"]),
            models.Index(fields=["is_read", "-submitted_at"]),
        ]

    def __str__(self):
        return f"{self.name or self.email} → {self.form.title}"


class PageView(models.Model):
    """Daily aggregated page view stats for a KovaPage (no PII)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(
        KovaPage,
        on_delete=models.CASCADE,
        related_name="daily_views",
    )
    date = models.DateField()
    views = models.PositiveIntegerField(default=0)
    unique_visitors = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("page", "date")
        ordering = ["-date"]
        indexes = [
            models.Index(fields=["page", "-date"]),
        ]

    def __str__(self):
        return f"{self.page.slug} — {self.date}: {self.views} views"
