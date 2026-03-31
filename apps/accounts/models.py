import uuid
from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Custom user model for Kova Agent."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField("email address", unique=True)
    full_name = models.CharField(max_length=255, blank=True)
    timezone = models.CharField(max_length=63, default="UTC")
    onboarding_completed = models.BooleanField(default=False)
    daily_brief_time = models.TimeField(default="09:00:00")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)

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
    # Subscription
    plan = models.CharField(max_length=20, choices=PlanTier.choices, default=PlanTier.STARTER)
    payment_provider = models.CharField(
        max_length=20,
        choices=[("none", "None"), ("stripe", "Stripe"), ("mpesa", "M-Pesa")],
        default="none",
    )
    # Stripe fields (kept for future international billing)
    stripe_customer_id = models.CharField(max_length=255, blank=True)
    stripe_subscription_id = models.CharField(max_length=255, blank=True)
    # M-Pesa fields
    mpesa_phone = models.CharField(
        max_length=15,
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

    def __str__(self):
        return f"Profile: {self.user}"
