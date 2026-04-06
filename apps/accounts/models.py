import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models

from apps.accounts.soft_delete import SoftDeleteMixin, SoftDeleteUserManager
from apps.platforms.encryption import EncryptedTokenField


class User(SoftDeleteMixin, AbstractUser):
    """Custom user model for Kova Agent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=63, default="UTC")
    onboarding_completed = models.BooleanField(default=False)
    daily_brief_time = models.TimeField(default="09:00:00")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

    # Override the default SoftDeleteManager with UserManager-compatible version
    objects = SoftDeleteUserManager()

    # allauth uses email as login
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    class Meta:
        ordering = ["-date_joined"]

    def __str__(self):
        return self.full_name or self.email

    @property
    def first_initial(self):
        name = self.full_name or self.email
        return name[0].upper() if name else "?"


class UserProfile(models.Model):
    """Extended profile for brand voice, goals, etc."""

    class Industry(models.TextChoices):
        SAAS = "saas", "SaaS / Software"
        ECOMMERCE = "ecommerce", "E-Commerce"
        AGENCY = "agency", "Agency / Marketing"
        CREATOR = "creator", "Creator / Influencer"
        CONSULTING = "consulting", "Consulting / Professional Services"
        NONPROFIT = "nonprofit", "Nonprofit"
        EDUCATION = "education", "Education"
        HEALTH = "health", "Health & Wellness"
        FINANCE = "finance", "Finance"
        REAL_ESTATE = "real_estate", "Real Estate"
        OTHER = "other", "Other"

    class PlanTier(models.TextChoices):
        STARTER = "starter", "Starter"
        GROWTH = "growth", "Growth"
        PRO = "pro", "Pro"
        AGENCY = "agency", "Agency"

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="profile")
    brand_voice = models.TextField(
        blank=True,
        help_text="Describe your brand's tone and style. E.g., 'Professional but approachable, uses humor occasionally.'",
    )
    brand_voice_examples = models.JSONField(
        default=list,
        blank=True,
        help_text="Sample posts that represent your brand voice.",
    )
    tone_attributes = models.JSONField(
        default=list,
        blank=True,
        help_text="Structured tone descriptors. E.g., ['confident', 'witty', 'educational']",
    )
    industry = models.CharField(max_length=30, choices=Industry.choices, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    website_url = models.URLField(blank=True)
    goals = models.JSONField(
        default=list,
        blank=True,
        help_text='Social media goals. E.g., ["Grow followers", "Drive traffic", "Generate leads"]',
    )
    target_audience = models.TextField(
        blank=True,
        help_text="Describe your target audience.",
    )
    content_pillars = models.JSONField(
        default=list,
        blank=True,
        help_text="Main topics/themes for content.",
    )
    posting_frequency = models.PositiveIntegerField(
        default=5,
        help_text="Target posts per week.",
    )
    # ── Enhanced brand intelligence fields ──
    brand_restrictions = models.TextField(
        blank=True,
        help_text="Topics, words, or themes to avoid. E.g., 'Never mention competitors by name.'",
    )
    content_language = models.CharField(
        max_length=30,
        choices=[
            ("en", "English"),
            ("sw", "Swahili"),
            ("sw_en", "Swahili & English mix"),
            ("fr", "French"),
            ("fr_en", "French & English mix"),
            ("yo", "Yoruba"),
            ("yo_en", "Yoruba & English mix"),
            ("zu", "Zulu"),
            ("sheng", "Sheng"),
            ("pidgin", "Pidgin English"),
            ("other", "Other"),
        ],
        default="en",
        help_text="Primary language for generated content.",
    )
    key_offerings = models.JSONField(
        default=list,
        blank=True,
        help_text="Main products or services. E.g., ['Custom cakes', 'Catering', 'Baking classes']",
    )
    platform_priority = models.JSONField(
        default=dict,
        blank=True,
        help_text="Platform importance ranking. E.g., {'linkedin': 1, 'twitter': 2, 'instagram': 3}",
    )
    # ── Visual brand identity ──
    brand_colors = models.JSONField(
        default=list,
        blank=True,
        help_text="Brand color hex codes. E.g., ['#FF5733', '#1A1A2E', '#FFFFFF']",
    )
    visual_style = models.CharField(
        max_length=30,
        choices=[
            ("photography", "Photography / Real Photos"),
            ("illustration", "Illustrations / Drawn Art"),
            ("flat_design", "Flat Design / Minimal"),
            ("3d_render", "3D Renders"),
            ("collage", "Collage / Mixed Media"),
            ("abstract", "Abstract / Artistic"),
            ("corporate", "Corporate / Clean"),
            ("vibrant", "Vibrant / Colorful"),
            ("dark_moody", "Dark / Moody"),
            ("auto", "Let AI Decide"),
        ],
        default="auto",
        help_text="Preferred visual style for AI-generated images.",
    )
    brand_logo_url = models.URLField(
        blank=True,
        help_text="Public URL to brand logo for overlay on graphics.",
    )
    # Subscription
    plan = models.CharField(max_length=20, choices=PlanTier.choices, default=PlanTier.STARTER)
    payment_provider = models.CharField(
        max_length=20,
        choices=[("none", "None"), ("stripe", "Stripe"), ("mpesa", "M-Pesa")],
        default="none",
    )
    # Stripe fields (kept for future international billing)
    stripe_customer_id = EncryptedTokenField(blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    # M-Pesa fields
    mpesa_phone = EncryptedTokenField(
        blank=True,
        help_text="Kenyan phone number for M-Pesa payments (254XXXXXXXXX)",
    )
    subscription_status = models.CharField(
        max_length=20,
        choices=[
            ("active", "Active"),
            ("trialing", "Trialing"),
            ("past_due", "Past Due"),
            ("canceled", "Canceled"),
            ("incomplete", "Incomplete"),
            ("none", "None"),
        ],
        default="none",
    )
    trial_ends_at = models.DateTimeField(null=True, blank=True)
    current_period_end = models.DateTimeField(null=True, blank=True)
    # Agent autonomy preferences
    auto_approve_posts = models.BooleanField(
        default=False,
        help_text="If True, agents can publish without approval.",
    )
    auto_engage = models.BooleanField(
        default=False,
        help_text="If True, engage agent can respond to comments automatically.",
    )
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        indexes = [
            models.Index(fields=["subscription_status", "plan"]),
            models.Index(fields=["payment_provider", "subscription_status"]),
        ]

    def __str__(self):
        return f"Profile: {self.user}"
