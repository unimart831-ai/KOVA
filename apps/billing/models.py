import uuid

from django.conf import settings
from django.core.cache import cache
from django.db import models
from django.utils import timezone


class BillingEvent(models.Model):
    """Audit trail for payment events (Stripe + M-Pesa)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    stripe_event_id = models.CharField(max_length=255, unique=True, blank=True, default="")
    event_type = models.CharField(max_length=100)  # e.g. checkout.session.completed, mpesa.stk_callback
    provider = models.CharField(
        max_length=20,
        choices=[("stripe", "Stripe"), ("mpesa", "M-Pesa")],
        default="stripe",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="billing_events",
    )
    data = models.JSONField(default=dict)
    processed = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["stripe_event_id"]),
            models.Index(fields=["event_type", "-created_at"]),
            models.Index(fields=["provider", "-created_at"]),
        ]

    def __str__(self):
        return f"[{self.provider}] {self.event_type} ({self.stripe_event_id or self.id})"


class MpesaPayment(models.Model):
    """Tracks M-Pesa STK Push payments for subscriptions and campaign add-ons."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"          # STK push sent, waiting for user
        COMPLETED = "completed", "Completed"    # User confirmed, payment received
        FAILED = "failed", "Failed"             # User canceled or timeout
        EXPIRED = "expired", "Expired"          # No callback after timeout

    class PaymentKind(models.TextChoices):
        SUBSCRIPTION = "subscription", "Subscription"
        CAMPAIGN_ADDON = "campaign_addon", "Campaign add-on"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="mpesa_payments",
    )
    # M-Pesa identifiers
    checkout_request_id = models.CharField(max_length=100, unique=True, db_index=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    receipt_number = models.CharField(max_length=50, blank=True, db_index=True)

    # Payment details
    phone_number = models.CharField(max_length=15)  # 254XXXXXXXXX
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    plan_tier = models.CharField(max_length=20)      # starter, growth, pro, agency, kova
    payment_kind = models.CharField(
        max_length=20,
        choices=PaymentKind.choices,
        default=PaymentKind.SUBSCRIPTION,
    )
    addon_pack_id = models.CharField(
        max_length=20,
        blank=True,
        help_text="boost, scale, or burst when payment_kind=campaign_addon",
    )
    currency = models.CharField(max_length=3, default="KES")

    # Status tracking
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.TextField(blank=True)

    # Subscription tracking
    is_renewal = models.BooleanField(default=False)
    subscription_period_start = models.DateTimeField(null=True, blank=True)
    subscription_period_end = models.DateTimeField(null=True, blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
        ]

    def __str__(self):
        return f"M-Pesa {self.amount} KES → {self.user} ({self.get_status_display()})"

    @property
    def is_campaign_addon(self) -> bool:
        return self.payment_kind == self.PaymentKind.CAMPAIGN_ADDON


class CampaignAddonPurchase(models.Model):
    """Audit record when a user buys extra campaign quota via M-Pesa."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="campaign_addon_purchases",
    )
    mpesa_payment = models.OneToOneField(
        MpesaPayment,
        on_delete=models.PROTECT,
        related_name="addon_purchase",
    )
    pack_id = models.CharField(max_length=20)
    campaigns_granted = models.PositiveIntegerField()
    bonus_before = models.PositiveIntegerField(default=0)
    bonus_after = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["pack_id", "-created_at"]),
        ]

    def __str__(self):
        return f"+{self.campaigns_granted} campaigns ({self.pack_id}) → {self.user_id}"


# ─── Plan Limits ─────────────────────────────────────────────────────────────
# Defines what each plan tier can do. Used by middleware and views.
#
# Public pricing: single Kova plan (KES 1,300). Agency is sales-approved only.
# New users get a 7-day Kova trial (5 campaigns) — see TRIAL_FEATURE_PLAN.
# Kova plan limits — authoritative source: docs/KOVA_BUILD_CHECKLIST.md
#
# Platform ladder (5 channels: FB, IG, TikTok, LinkedIn, WhatsApp):
#   Starter 2 · Growth 4 (WA inbox wedge) · Pro 5 (full WA Business)
# Single public plan: docs/KOVA_BUILD_CHECKLIST.md
# Legacy tiers (starter/growth/pro) remain for grandfathered subscribers.
PLAN_LIMITS = {
    "kova": {
        "label": "Kova",
        "max_social_accounts": 4,
        "max_posts_per_month": 9999,
        "max_seeds_per_month": 30,
        "max_photoroom_scenes_per_campaign": 12,
        "daily_llm_tokens": 250_000,
        "monthly_llm_tokens": 5_000_000,
        "agents_enabled": ["create", "analyst", "research", "adapt", "engage"],
        "daily_brief": True,
        "email_brief": True,
        "whatsapp_brief": False,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "ai_images_per_month": 60,
        "visual_enhancements_per_month": 500,
        "plus_max_variants_per_product": 4,
        "visual_enhance_premium": False,
        "auto_approve": False,
        "ab_testing": True,
        "max_team_members": 0,
        "kova_pages": 3,
        "kova_links_per_page": 20,
        "kova_forms": True,
        "max_leads": 100,
        "leads_can_edit": True,
        "email_subscribers": 2500,
        "email_lists": 5,
        "email_campaigns_per_month": 10,
        "email_sequences": 3,
        "max_products": 50,
        "product_quantity_tracking": True,
        "product_csv_import": True,
        "shopify_integration": True,
        "mpesa_commerce": True,
        "multi_touch_attribution": True,
        "revenue_dashboard": True,
        "whatsapp_enabled": False,
        "whatsapp_inbox_enabled": True,
        "whatsapp_marketing_conversations_per_month": 50,
        "memes_enabled": False,
        "adapt_v2_enabled": True,
        "max_campaigns": 30,
        "kling_reels_enabled": False,
        "bannerbear_carousels_enabled": True,
        "fal_flux_edits_per_month": 10,
        "price_kes": 1300,
        "price_usd": 10,
        "trial_days": 7,
        "public": True,
    },
    "starter": {
        "label": "Jipange / Starter",
        "max_social_accounts": 2,
        "max_posts_per_month": 18,
        "max_seeds_per_month": 8,
        "daily_llm_tokens": 50_000,
        "monthly_llm_tokens": 1_000_000,
        "agents_enabled": ["create", "analyst"],
        "daily_brief": True,
        "email_brief": False,
        "whatsapp_brief": False,
        "engagement_agent": False,
        "engage_trial_enabled": True,
        "engage_trial_auto_replies_per_week": 5,
        "competitor_tracking": False,
        "ai_image_generation": False,
        "ai_images_per_month": 0,
        "visual_enhancements_per_month": 8,
        "plus_max_variants_per_product": 4,
        "visual_enhance_premium": False,
        "auto_approve": False,
        "ab_testing": False,
        "max_team_members": 0,
        "kova_pages": 1,
        "kova_links_per_page": 5,
        "kova_forms": False,
        "max_leads": 10,
        "leads_can_edit": False,
        "email_subscribers": 50,
        "email_lists": 1,
        "email_campaigns_per_month": 2,
        "email_sequences": 0,
        "max_products": 5,
        "product_quantity_tracking": False,
        "product_csv_import": False,
        "shopify_integration": False,
        "mpesa_commerce": False,
        "multi_touch_attribution": False,
        "revenue_dashboard": True,
        "whatsapp_enabled": False,
        "whatsapp_inbox_enabled": False,
        "whatsapp_marketing_conversations_per_month": 0,
        "memes_enabled": False,
        "adapt_v2_enabled": False,
        "max_campaigns": 2,
        "kling_reels_enabled": False,
        "bannerbear_carousels_enabled": False,
        "fal_flux_edits_per_month": 0,
        "price_kes": 499,
        "price_usd": 4,
        "trial_days": 7,
    },
    "growth": {
        "label": "Kazi / Growth",
        "max_social_accounts": 4,
        "max_posts_per_month": 60,
        "max_seeds_per_month": 30,
        "daily_llm_tokens": 200_000,
        "monthly_llm_tokens": 4_000_000,
        "agents_enabled": ["create", "analyst", "research", "adapt"],
        "daily_brief": True,
        "email_brief": True,
        "whatsapp_brief": False,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "ai_images_per_month": 50,
        "visual_enhancements_per_month": 30,
        "plus_max_variants_per_product": 4,
        "visual_enhance_premium": False,
        "auto_approve": False,
        "ab_testing": True,
        "max_team_members": 0,
        "kova_pages": 3,
        "kova_links_per_page": 20,
        "kova_forms": True,
        "max_leads": 100,
        "leads_can_edit": True,
        "email_subscribers": 2500,
        "email_lists": 5,
        "email_campaigns_per_month": 10,
        "email_sequences": 3,
        "max_products": 30,
        "product_quantity_tracking": True,
        "product_csv_import": True,
        "shopify_integration": True,
        "mpesa_commerce": True,
        "multi_touch_attribution": False,
        "revenue_dashboard": True,
        "whatsapp_enabled": False,
        "whatsapp_inbox_enabled": True,
        "whatsapp_marketing_conversations_per_month": 50,
        "memes_enabled": False,
        "adapt_v2_enabled": True,
        "max_campaigns": 5,
        "kling_reels_enabled": False,
        "bannerbear_carousels_enabled": True,
        "fal_flux_edits_per_month": 10,
        "price_kes": 1499,
        "price_usd": 11,
        "trial_days": 7,
    },
    "pro": {
        "label": "Biashara / Pro",
        "max_social_accounts": 5,
        "max_posts_per_month": 150,
        "max_seeds_per_month": 60,
        "daily_llm_tokens": 500_000,
        "monthly_llm_tokens": 10_000_000,
        "agents_enabled": ["create", "analyst", "research", "adapt", "engage", "strategist"],
        "daily_brief": True,
        "email_brief": True,
        "whatsapp_brief": True,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "ai_images_per_month": 100,
        "visual_enhancements_per_month": 100,
        "plus_max_variants_per_product": 4,
        "visual_enhance_premium": True,
        "auto_approve": True,
        "ab_testing": True,
        "max_team_members": 5,
        "kova_pages": 10,
        "kova_links_per_page": 100,
        "kova_forms": True,
        "max_leads": 5000,
        "leads_can_edit": True,
        "email_subscribers": 25000,
        "email_lists": 15,
        "email_campaigns_per_month": 30,
        "email_sequences": 10,
        "max_products": 100,
        "product_quantity_tracking": True,
        "product_csv_import": True,
        "shopify_integration": True,
        "mpesa_commerce": True,
        "multi_touch_attribution": True,
        "revenue_dashboard": True,
        "whatsapp_enabled": True,
        "whatsapp_inbox_enabled": True,
        "whatsapp_marketing_conversations_per_month": 300,
        "memes_enabled": True,
        "adapt_v2_enabled": True,
        "max_campaigns": 15,
        "kling_reels_enabled": True,
        "bannerbear_carousels_enabled": True,
        "fal_flux_edits_per_month": 30,
        "price_kes": 2999,
        "price_usd": 22,
        "trial_days": 7,
    },
    "agency": {
        "label": "Wakala / Agency",
        "max_social_accounts": 25,
        "max_posts_per_month": 300,
        "max_seeds_per_month": 120,
        "daily_llm_tokens": 2_000_000,
        "monthly_llm_tokens": 40_000_000,
        "agents_enabled": ["create", "analyst", "research", "adapt", "engage", "strategist"],
        "daily_brief": True,
        "email_brief": True,
        "whatsapp_brief": True,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "ai_images_per_month": 200,
        "visual_enhancements_per_month": 150,
        "plus_max_variants_per_product": 4,
        "visual_enhance_premium": True,
        "auto_approve": True,
        "ab_testing": True,
        "max_team_members": 25,
        "kova_pages": 50,
        "kova_links_per_page": 200,
        "kova_forms": True,
        "max_leads": 10000,
        "leads_can_edit": True,
        "email_subscribers": 100000,
        "email_lists": 50,
        "email_campaigns_per_month": 50,
        "email_sequences": 20,
        "max_products": 500,
        "product_quantity_tracking": True,
        "product_csv_import": True,
        "shopify_integration": True,
        "mpesa_commerce": True,
        "multi_touch_attribution": True,
        "revenue_dashboard": True,
        "whatsapp_enabled": True,
        "whatsapp_inbox_enabled": True,
        "whatsapp_marketing_conversations_per_month": 1000,
        "memes_enabled": True,
        "adapt_v2_enabled": True,
        "max_campaigns": 25,
        "kling_reels_enabled": True,
        "bannerbear_carousels_enabled": True,
        "fal_flux_edits_per_month": 100,
        "price_kes": 7999,
        "price_usd": 59,
        "trial_days": 7,
        "public": False,
        "requires_agency_approval": True,
    },
}

# Customer-facing tier (legacy starter/growth/pro hidden from checkout).
PUBLIC_PLAN_TIERS = ("kova",)

# Active free trials use Kova limits with a reduced campaign quota.
TRIAL_FEATURE_PLAN = "kova"
TRIAL_CAMPAIGN_LIMIT = 5

# Extra campaign packs (subscribe on top of base 30/month).
CAMPAIGN_ADDON_PACKS = {
    "boost": {
        "id": "boost",
        "label": "+10 campaigns / month",
        "campaigns": 10,
        "price_kes": 450,
        "price_usd": 4,
        "recurring": True,
    },
    "scale": {
        "id": "scale",
        "label": "+30 campaigns / month",
        "campaigns": 30,
        "price_kes": 1200,
        "price_usd": 9,
        "recurring": True,
    },
    "burst": {
        "id": "burst",
        "label": "+5 campaigns (this month)",
        "campaigns": 5,
        "price_kes": 250,
        "price_usd": 2,
        "recurring": False,
    },
}


def get_campaign_addon_packs():
    """Public add-on packs for pricing UI."""
    return CAMPAIGN_ADDON_PACKS.copy()


def _get_db_prices():
    """Load DB price overrides with caching (5 min TTL)."""
    cached = cache.get("plan_price_overrides")
    if cached is not None:
        return cached
    try:
        overrides = {
            p.tier: {"price_kes": p.price_kes, "price_usd": p.price_usd}
            for p in PlanPrice.objects.filter(is_active=True)
        }
    except Exception:
        overrides = {}
    cache.set("plan_price_overrides", overrides, 300)
    return overrides


def get_plan_limits(plan_tier):
    """Get the limits for a plan tier. DB prices override hardcoded ones."""
    base = PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["kova"]).copy()
    overrides = _get_db_prices()
    if plan_tier in overrides:
        base["price_kes"] = overrides[plan_tier]["price_kes"]
        base["price_usd"] = overrides[plan_tier]["price_usd"]
    return base


def is_active_trial(profile) -> bool:
    """True when subscription_status is trialing and the trial window has not ended."""
    if not profile or profile.subscription_status != "trialing":
        return False
    end = profile.trial_ends_at or profile.current_period_end
    if not end:
        return True
    return end >= timezone.now()


def get_effective_plan_tier(profile) -> str:
    """Plan tier used for feature/limit enforcement (trial → Kova limits, 5 campaigns)."""
    if is_active_trial(profile):
        return TRIAL_FEATURE_PLAN
    if profile and profile.plan in PLAN_LIMITS:
        return profile.plan
    return "kova"


def get_user_plan_limits(user):
    """Effective limits for a user — trialing users receive Kova with trial campaign cap."""
    profile = getattr(user, "profile", None)
    tier = get_effective_plan_tier(profile)
    limits = get_plan_limits(tier)
    if is_active_trial(profile):
        limits = limits.copy()
        limits["label"] = "Kova trial"
        limits["max_seeds_per_month"] = TRIAL_CAMPAIGN_LIMIT
    return limits


SIDEBAR_PLAN_NAMES = {
    "kova": "Kova",
    "starter": "Starter",
    "growth": "Growth",
    "pro": "Pro",
    "agency": "Agency",
}


def get_sidebar_plan_display(user) -> dict:
    """
    Plan label for the app sidebar — Kova trial, paid tier, Free, or Agency pending.

    Returns dict with keys: label, variant (free|trial|paid|pending|none), is_staff.
    Uses profile already on user — no extra queries when profile is cached.
    """
    if not getattr(user, "is_authenticated", False):
        return {"label": "", "variant": "none", "is_staff": False}

    is_staff = bool(user.is_staff or user.is_superuser)
    profile = getattr(user, "profile", None)
    if not profile:
        return {"label": "Free", "variant": "free", "is_staff": is_staff}

    if is_active_trial(profile):
        return {"label": "Kova trial", "variant": "trial", "is_staff": is_staff}

    plan = (profile.plan or "starter").lower()
    status = profile.subscription_status or "none"

    if plan == "agency" and not profile.is_agency_approved:
        return {"label": "Agency pending", "variant": "pending", "is_staff": is_staff}

    tier_name = SIDEBAR_PLAN_NAMES.get(plan, profile.get_plan_display())

    if status in ("active", "past_due"):
        return {"label": tier_name, "variant": "paid", "is_staff": is_staff}

    if status in ("none", "canceled", "incomplete"):
        return {"label": "Free", "variant": "free", "is_staff": is_staff}

    if status == "trialing":
        return {"label": "Free", "variant": "free", "is_staff": is_staff}

    return {"label": tier_name, "variant": "paid", "is_staff": is_staff}


def can_subscribe_to_agency(user) -> bool:
    """Agency checkout requires explicit sales approval on the profile."""
    profile = getattr(user, "profile", None)
    return bool(profile and getattr(profile, "is_agency_approved", False))


def get_public_plan_limits():
    """Plans shown on the customer pricing page."""
    return {tier: get_plan_limits(tier) for tier in PUBLIC_PLAN_TIERS}


def get_all_plan_limits():
    """Get all plans with DB price overrides applied."""
    overrides = _get_db_prices()
    result = {}
    for tier, plan in PLAN_LIMITS.items():
        p = plan.copy()
        if tier in overrides:
            p["price_kes"] = overrides[tier]["price_kes"]
            p["price_usd"] = overrides[tier]["price_usd"]
        result[tier] = p
    return result


class SubscriptionOverride(models.Model):
    """Audit trail for admin-initiated subscription changes."""

    class ActionType(models.TextChoices):
        PLAN_CHANGE = "plan_change", "Plan Change"
        TRIAL_EXTENSION = "trial_extension", "Trial Extension"
        COMP_ACCESS = "comp_access", "Complimentary Access"
        STATUS_CHANGE = "status_change", "Status Change"
        BULK_GRANT = "bulk_grant", "Bulk Grant"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="subscription_overrides",
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="admin_overrides",
    )
    action = models.CharField(max_length=30, choices=ActionType.choices)

    # What changed
    previous_plan = models.CharField(max_length=20, blank=True)
    new_plan = models.CharField(max_length=20, blank=True)
    previous_status = models.CharField(max_length=20, blank=True)
    new_status = models.CharField(max_length=20, blank=True)
    days_granted = models.PositiveIntegerField(default=0)
    expires_at = models.DateTimeField(null=True, blank=True)

    # Context
    reason = models.TextField(help_text="Why this override was applied")
    batch_id = models.CharField(
        max_length=50, blank=True,
        help_text="Groups bulk operations together",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["batch_id"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} → {self.user} by {self.admin}"


class ContentSeedQuotaLog(models.Model):
    """Audit trail for admin content seed quota adjustments."""

    class Action(models.TextChoices):
        RESET_USAGE = "reset_usage", "Reset usage counter"
        SET_LIMIT_OVERRIDE = "set_limit_override", "Set monthly limit override"
        CLEAR_LIMIT_OVERRIDE = "clear_limit_override", "Clear limit override"
        SET_BONUS = "set_bonus", "Set bonus seeds"
        ADDON_PURCHASE = "addon_purchase", "Campaign add-on purchase"
        CLEAR_ALL = "clear_all", "Clear all overrides"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="seed_quota_logs",
    )
    admin = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="seed_quota_admin_actions",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    reason = models.TextField()
    used_before = models.PositiveIntegerField(default=0)
    max_before = models.PositiveIntegerField(default=0)
    remaining_before = models.PositiveIntegerField(default=0)
    plan_label = models.CharField(max_length=40, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.get_action_display()} → {self.user_id}"


# ─── Dynamic Pricing ────────────────────────────────────────────────────────

class PlanPrice(models.Model):
    """Admin-managed plan prices. Overrides PLAN_LIMITS when active."""

    TIER_CHOICES = [
        ("starter", "Jipange / Starter"),
        ("growth", "Kazi / Growth"),
        ("pro", "Biashara / Pro"),
        ("agency", "Wakala / Agency"),
    ]

    tier = models.CharField(max_length=20, choices=TIER_CHOICES, unique=True)
    price_kes = models.PositiveIntegerField(help_text="Monthly price in KES")
    price_usd = models.PositiveIntegerField(help_text="Monthly price in USD")
    is_active = models.BooleanField(
        default=True,
        help_text="When inactive, falls back to hardcoded PLAN_LIMITS price",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Plan Price"
        verbose_name_plural = "Plan Prices"

    def __str__(self):
        return f"{self.get_tier_display()} — KES {self.price_kes} / ${self.price_usd}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        cache.delete("plan_price_overrides")


# ─── Discount Codes ─────────────────────────────────────────────────────────

class DiscountCode(models.Model):
    """Promotional discount codes for subscriptions."""

    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED_KES = "fixed_kes", "Fixed Amount (KES)"
        FIXED_USD = "fixed_usd", "Fixed Amount (USD)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(
        max_length=30, unique=True, db_index=True,
        help_text="Unique code (auto-uppercased)",
    )
    description = models.CharField(max_length=200, blank=True, help_text="Internal admin note")

    # Discount amount
    discount_type = models.CharField(max_length=20, choices=DiscountType.choices)
    discount_value = models.DecimalField(
        max_digits=10, decimal_places=2,
        help_text="Percentage (e.g. 20 for 20%) or fixed amount",
    )

    # Restrictions
    applicable_plans = models.JSONField(
        default=list, blank=True,
        help_text='Plan tiers this applies to. Empty list = all plans. e.g. ["growth","pro"]',
    )
    max_uses = models.PositiveIntegerField(
        default=0, help_text="Total max redemptions. 0 = unlimited.",
    )
    max_uses_per_user = models.PositiveIntegerField(
        default=1, help_text="Max redemptions per user.",
    )
    current_uses = models.PositiveIntegerField(default=0, editable=False)

    # Validity
    valid_from = models.DateTimeField(help_text="When the code becomes active")
    valid_until = models.DateTimeField(help_text="When the code expires")
    is_active = models.BooleanField(default=True)

    # Metadata
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="+",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["is_active", "valid_from", "valid_until"]),
        ]

    def __str__(self):
        return f"{self.code} ({self.get_discount_type_display()}: {self.discount_value})"

    def save(self, *args, **kwargs):
        self.code = self.code.upper().strip()
        super().save(*args, **kwargs)

    @property
    def is_valid(self):
        """Check if the code is currently usable."""
        now = timezone.now()
        if not self.is_active:
            return False
        if now < self.valid_from or now > self.valid_until:
            return False
        if self.max_uses > 0 and self.current_uses >= self.max_uses:
            return False
        return True

    @property
    def is_expired(self):
        return timezone.now() > self.valid_until

    def can_user_use(self, user):
        """Check if a specific user can use this code."""
        if not self.is_valid:
            return False
        user_uses = self.redemptions.filter(user=user).count()
        return user_uses < self.max_uses_per_user

    def applies_to_plan(self, plan_tier):
        """Check if this discount applies to a given plan."""
        if not self.applicable_plans:
            return True
        return plan_tier in self.applicable_plans

    def calculate_discount(self, original_kes, original_usd):
        """Return (discounted_kes, discounted_usd, saved_kes, saved_usd)."""
        if self.discount_type == self.DiscountType.PERCENTAGE:
            pct = self.discount_value / 100
            saved_kes = int(original_kes * pct)
            saved_usd = int(original_usd * pct)
        elif self.discount_type == self.DiscountType.FIXED_KES:
            saved_kes = min(int(self.discount_value), original_kes)
            saved_usd = 0
        elif self.discount_type == self.DiscountType.FIXED_USD:
            saved_kes = 0
            saved_usd = min(int(self.discount_value), original_usd)
        else:
            saved_kes, saved_usd = 0, 0

        return (
            max(0, original_kes - saved_kes),
            max(0, original_usd - saved_usd),
            saved_kes,
            saved_usd,
        )


class DiscountRedemption(models.Model):
    """Records each discount code usage."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    discount_code = models.ForeignKey(
        DiscountCode,
        on_delete=models.PROTECT,
        related_name="redemptions",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="discount_redemptions",
    )
    plan_tier = models.CharField(max_length=20)
    original_amount = models.DecimalField(max_digits=10, decimal_places=2)
    discounted_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_saved = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default="KES")
    redeemed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-redeemed_at"]
        indexes = [
            models.Index(fields=["discount_code", "user"]),
        ]

    def __str__(self):
        return f"{self.user} used {self.discount_code.code} — saved {self.currency} {self.amount_saved}"


class AgencySalesInquiry(models.Model):
    """Agency / Wakala tier intake — submitted via Contact sales on pricing."""

    class Status(models.TextChoices):
        NEW = "new", "New"
        CONTACTED = "contacted", "Contacted"
        CLOSED = "closed", "Closed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="agency_sales_inquiries",
    )
    name = models.CharField(max_length=200)
    email = models.EmailField(db_index=True)
    phone = models.CharField(max_length=30, blank=True)
    company_name = models.CharField(max_length=255, blank=True)
    message = models.TextField()
    client_count = models.PositiveIntegerField(null=True, blank=True)
    plan_interest = models.CharField(max_length=30, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    staff_notes = models.TextField(blank=True)
    contacted_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "agency sales inquiry"
        verbose_name_plural = "agency sales inquiries"

    def __str__(self):
        label = self.company_name or self.name
        return f"{label} <{self.email}> ({self.get_status_display()})"
