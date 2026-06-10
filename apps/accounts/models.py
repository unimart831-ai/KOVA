import re
import uuid
from django.contrib.auth.models import AbstractUser
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone as tz

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
    phone_number = models.CharField(
        max_length=15, blank=True, default="",
        help_text="Kenyan phone number (07xx, 01xx, 02xx). Multiple users can share a number.",
    )
    brief_email_enabled = models.BooleanField(
        default=True,
        help_text="Send the daily brief to your email (Growth plan and above).",
    )
    brief_whatsapp_enabled = models.BooleanField(
        default=True,
        help_text="Send a morning brief ping to WhatsApp (Pro plan and above).",
    )
    money_board_digest_enabled = models.BooleanField(
        default=False,
        help_text="Daily email/in-app digest when money board counts need attention.",
    )

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

    def soft_delete(self):
        """Soft-delete user: mangle email/username to free them for re-registration,
        deactivate the account, and remove allauth EmailAddress records."""
        from allauth.account.models import EmailAddress

        # Remove allauth email records so the email is fully freed
        EmailAddress.objects.filter(user=self).delete()

        # Mangle email & username so the unique constraint is freed
        stamp = int(tz.now().timestamp())
        self.email = f"deleted_{stamp}_{self.pk}@deleted.local"
        self.username = f"deleted_{stamp}_{self.pk}"
        self.is_active = False
        self.is_deleted = True
        self.deleted_at = tz.now()
        self.save(update_fields=[
            "email", "username", "is_active",
            "is_deleted", "deleted_at",
        ])

    def delete(self, using=None, keep_parents=False):
        """Route instance.delete() through soft_delete so the account is never hard-deleted."""
        self.soft_delete()


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
        FOOD_RESTAURANT = "food_restaurant", "Food & Restaurant"
        WHOLESALE_RETAIL = "wholesale_retail", "Wholesale & Retail"
        SALON_BEAUTY = "salon_beauty", "Salon & Beauty Services"
        FASHION_BEAUTY = "fashion_beauty", "Fashion & Beauty"
        TRAVEL_TOURISM = "travel_tourism", "Travel & Tourism"
        MEDIA_ENTERTAINMENT = "media_entertainment", "Media & Entertainment"
        AGRICULTURE = "agriculture", "Agriculture"
        LOGISTICS_TRANSPORT = "logistics_transport", "Logistics & Transport"
        CONSTRUCTION = "construction", "Construction & Manufacturing"
        LEGAL = "legal", "Legal Services"
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
    industry_other = models.CharField(
        max_length=100, blank=True, default="",
        help_text="Custom industry name when 'Other' is selected.",
    )
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
    photoroom_brand_template = models.JSONField(
        default=dict,
        blank=True,
        help_text=(
            "Optional locked Photoroom Plus styling: shadow_mode, padding, ai_seed, "
            "outline_color, style_suffix, enabled."
        ),
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
    is_agency_approved = models.BooleanField(
        default=False,
        help_text="When True, user may subscribe to the Agency plan via sales onboarding.",
    )
    # Content seed quota (Studio) — admin overrides for testing & promotions
    seed_quota_reset_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Seeds before this time are not counted toward the monthly limit.",
    )
    seed_monthly_limit_override = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="When set, replaces plan max_seeds_per_month for this user.",
    )
    seed_monthly_bonus = models.PositiveIntegerField(
        default=0,
        help_text="Extra seeds added on top of plan limit (promotions).",
    )
    # Agent autonomy preferences
    auto_approve_posts = models.BooleanField(
        default=False,
        help_text="If True, agents can publish without approval.",
    )
    auto_engage = models.BooleanField(
        default=False,
        help_text=(
            "DEPRECATED — use engage_autonomy_level instead. Kept for two "
            "release cycles to avoid breaking admin tools / external API "
            "clients that haven't migrated yet. Phase 1 W2 (May 2026)."
        ),
    )

    class EngageAutonomyLevel(models.TextChoices):
        OFF = "off", "Off — no AI replies"
        SUGGEST = "suggest", "Suggest — AI drafts, I approve every one"
        GRADUATED = "graduated", "Graduated — auto-send safe replies, queue tricky ones"
        AGGRESSIVE = "aggressive", "Aggressive — auto-send aggressively (Agency only)"

    engage_autonomy_level = models.CharField(
        max_length=20,
        choices=EngageAutonomyLevel.choices,
        default=EngageAutonomyLevel.SUGGEST,
        help_text=(
            "How much social media autonomy to give the Engage Agent. "
            "OFF disables AI replies entirely. SUGGEST queues every AI reply "
            "for review. GRADUATED auto-sends at confidence ≥ 0.85 and queues "
            "0.50-0.85 as drafts. AGGRESSIVE auto-sends at ≥ 0.70. "
            "Plan-tier-gated — see docs/specs/ENGAGE_AGENT_V2_SPEC.md."
        ),
    )
    engage_trial_replies_this_week = models.PositiveSmallIntegerField(
        default=0,
        help_text="Starter trial: auto-replies sent this ISO week.",
    )
    engage_trial_week_start = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Week boundary for engage_trial_replies_this_week reset.",
    )
    # ── Operations Autopilot (Jun 2026) — off by default ──
    autopilot_auto_publish_approved = models.BooleanField(
        default=False,
        help_text="Publish approved posts when scheduled_at is due — no extra click.",
    )
    autopilot_auto_enroll_leads = models.BooleanField(
        default=False,
        help_text="Auto-enroll new leads in your default Welcome nurture sequence.",
    )
    autopilot_auto_create_wa_leads = models.BooleanField(
        default=False,
        help_text="When True, inbound WhatsApp messages from new numbers auto-create a lead stub.",
    )
    autopilot_wa_followup_24h = models.BooleanField(
        default=False,
        help_text="Send a utility follow-up if a customer message has no owner reply in 24h.",
    )
    autopilot_wa_faq_replies = models.BooleanField(
        default=False,
        help_text="Auto-reply to WhatsApp messages matching your FAQ keyword rules.",
    )
    wa_faq_answers = models.JSONField(
        default=list,
        blank=True,
        help_text='Up to 5 FAQ rules: [{"keywords": ["hours", "open"], "reply": "..."}]',
    )

    emergency_pause = models.BooleanField(
        default=False,
        help_text="If True, ALL autonomous agent actions are halted immediately. "
                  "No publishing, no seeds, no replies, no media queue processing.",
    )
    content_safety_strike_count = models.PositiveSmallIntegerField(
        default=0,
        help_text="Count of confirmed or high-severity content policy violations.",
    )
    suspended_for_policy = models.BooleanField(
        default=False,
        help_text="When True, user cannot publish until staff clears the suspension.",
    )
    auto_publish_paused = models.BooleanField(
        default=False,
        help_text="When True, this user's posts are not auto-published (manual only).",
    )
    snap_blocked_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When set and in the future, Snap to Sell is blocked for this user only.",
    )
    snap_blocked_incident = models.ForeignKey(
        "content.ContentSafetyIncident",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        help_text="Incident that applied the current snap block (cleared on dismiss).",
    )

    # ── Content Autopilot (Phase 3, May 2026) ──
    autopilot_enabled = models.BooleanField(
        default=False,
        help_text="If True, Kova prepares a weekly content plan preview every Monday. "
                  "You review and approve the strategy before posts are generated.",
    )
    autopilot_posts_per_week = models.PositiveSmallIntegerField(
        default=5,
        help_text="Target number of posts per week when autopilot is active (1-14).",
    )
    autopilot_platforms = models.JSONField(
        default=list, blank=True,
        help_text='Platforms for autopilot to target. Empty = all connected. ["instagram", "linkedin"]',
    )

    auto_email_marketing = models.BooleanField(
        default=True,
        help_text="If True, Kova auto-sends AI email campaigns and recycles top posts to your list.",
    )
    commerce_autopilot = models.BooleanField(
        default=False,
        verbose_name="Commerce Autopilot",
        help_text=(
            "Snap a photo only — AI names, prices, creates posts, and publishes your catalog."
        ),
    )
    catalog_showcase_weekly = models.BooleanField(
        default=True,
        verbose_name="Weekly catalog showcase",
        help_text=(
            "If True, Kova builds a carousel + reel of your in-stock catalog "
            "(name + price per item) at most once per week."
        ),
    )
    catalog_showcase_last_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time a catalog showcase carousel/reel was generated.",
    )

    # ── Adapt Agent v2 (Phase 1 W3-4, May 2026) ──
    # The autonomous learning loop. Reads per-user post performance every
    # 12h and mutates these fields to bias future content toward winners.
    # Spec: docs/specs/ADAPT_AGENT_V2_SPEC.md
    pillar_weights = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Per-pillar rotation weights (0.2-2.0, default 1.0). Adapt "
            "Agent v2 mutates these based on per-pillar engagement. The "
            "Strategist + Create agents pull from pillars proportionally."
        ),
    )
    dna_preferences = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Promoted / retired Content DNA patterns from the Adapt loop. "
            'Shape: {"promoted": [{"combo": {...}, "boost": 1.5, ...}, ...], '
            '"retired": [{"combo": {...}, "set_at": "..."}, ...]}'
        ),
    )
    optimal_schedule = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Per-platform optimal posting hours/days from Adapt v1's "
            'scheduling optimiser. Shape: {"instagram": {"best_hours": '
            '[9, 18], "best_days": ["mon", "tue"]}, ...}'
        ),
    )
    adapt_paused = models.BooleanField(
        default=False,
        help_text=(
            "If True, Adapt Agent v2 skips this user. Manual override for "
            "users who want to lock their settings in place."
        ),
    )
    adapt_last_run_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp of the most recent Adapt v2 cycle for this user.",
    )
    # ── Default CTA settings (Sprint 6B) ──
    default_cta_type = models.CharField(
        max_length=20,
        choices=[
            ("none", "No CTA"),
            ("link", "Link / URL"),
            ("phone", "Phone Call"),
            ("email", "Email"),
            ("whatsapp", "WhatsApp"),
            ("kova_link", "Kova Link Page"),
        ],
        default="none",
        help_text="Default CTA type for new posts.",
    )
    default_cta_url = models.CharField(max_length=500, blank=True, help_text="Default CTA destination URL.")
    cta_phone = models.CharField(max_length=20, blank=True, help_text="Phone number for phone CTAs.")
    cta_email = models.EmailField(blank=True, help_text="Email address for email CTAs.")
    cta_whatsapp = models.CharField(max_length=20, blank=True, help_text="WhatsApp number for WhatsApp CTAs.")
    # ── Kova Link Page ──
    page_slug = models.SlugField(
        max_length=60, unique=True, null=True, blank=True, db_index=True,
        help_text="Public slug for the Kova Link Page (/p/<slug>/). Auto-set to username.",
    )
    page_headline = models.CharField(
        max_length=160, blank=True,
        help_text="One-line tagline shown on the public page.",
    )
    page_active = models.BooleanField(
        default=True,
        help_text="Whether the public Kova Link Page is visible.",
    )
    # ── Kova Pixel (Sprint T2A) ──
    pixel_token = models.CharField(
        max_length=64, null=True, blank=True, unique=True, db_index=True,
        help_text="Unique token for Kova Pixel website tracking. Generated on first access.",
    )
    # ── Geographic / market context (used by holiday awareness, regional content) ──
    country = models.CharField(
        max_length=2,
        blank=True,
        default="",
        help_text="ISO 3166-1 alpha-2 country code (e.g., 'RW', 'KE', 'US'). "
                  "Drives which holidays surface for this user.",
    )
    city = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Primary city — used for localized content references.",
    )
    secondary_markets = models.JSONField(
        default=list,
        blank=True,
        help_text="Additional ISO 3166-1 alpha-2 codes the business serves. "
                  "E.g., ['UG', 'TZ']. Phase 4 multi-market feature.",
    )
    # ── Onboarding funnel telemetry ──
    onboarding_step_timestamps = models.JSONField(
        default=dict, blank=True,
        help_text="First-hit ISO timestamp per onboarding step. "
                  "Keys: step_1_completed, step_2_completed, step_3_completed, "
                  "step_4_completed, intelligence_started, intelligence_completed.",
    )
    onboarding_intelligence_started_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Dispatch time of run_onboarding_intelligence. "
                  "Used by the completion screen to detect stuck polling.",
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

    def record_onboarding_step(self, step_name):
        """Stamp an onboarding step at its first occurrence. Idempotent."""
        steps = self.onboarding_step_timestamps or {}
        if step_name in steps:
            return
        steps[step_name] = tz.now().isoformat()
        self.onboarding_step_timestamps = steps
        self.save(update_fields=["onboarding_step_timestamps", "updated_at"])
