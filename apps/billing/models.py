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
    """Tracks M-Pesa STK Push payments for subscriptions."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"          # STK push sent, waiting for user
        COMPLETED = "completed", "Completed"    # User confirmed, payment received
        FAILED = "failed", "Failed"             # User canceled or timeout
        EXPIRED = "expired", "Expired"          # No callback after timeout

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
    plan_tier = models.CharField(max_length=20)      # starter, growth, pro, agency
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


# ─── Plan Limits ─────────────────────────────────────────────────────────────
# Defines what each plan tier can do. Used by middleware and views.
# Jipange is deliberately capped to keep AI cost < KES 40/user/month.
# It's a conversion funnel — not a revenue tier.
PLAN_LIMITS = {
    "starter": {
        "label": "Jipange / Starter",
        "max_social_accounts": 1,
        "max_posts_per_month": 15,
        "max_seeds_per_month": 5,
        "agents_enabled": ["create", "analyst"],
        "daily_brief": True,
        "email_brief": False,
        "engagement_agent": False,
        "competitor_tracking": False,
        "ai_image_generation": False,
        "ai_images_per_month": 0,
        "auto_approve": False,
        "ab_testing": False,
        "max_team_members": 0,
        "price_kes": 299,
        "price_usd": 2,
        "trial_days": 14,
    },
    "growth": {
        "label": "Kazi / Growth",
        "max_social_accounts": 3,
        "max_posts_per_month": 60,
        "max_seeds_per_month": 30,
        "agents_enabled": ["create", "analyst", "research", "adapt"],
        "daily_brief": True,
        "email_brief": True,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "ai_images_per_month": 50,
        "auto_approve": False,
        "ab_testing": True,
        "max_team_members": 0,
        "price_kes": 999,
        "price_usd": 7,
        "trial_days": 14,
    },
    "pro": {
        "label": "Biashara / Pro",
        "max_social_accounts": 10,
        "max_posts_per_month": 150,
        "max_seeds_per_month": 60,
        "agents_enabled": ["create", "analyst", "research", "adapt", "engage", "strategist"],
        "daily_brief": True,
        "email_brief": True,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "ai_images_per_month": 100,
        "auto_approve": True,
        "ab_testing": True,
        "max_team_members": 5,
        "price_kes": 1999,
        "price_usd": 14,
        "trial_days": 14,
    },
    "agency": {
        "label": "Wakala / Agency",
        "max_social_accounts": 25,
        "max_posts_per_month": 999999,
        "max_seeds_per_month": 999999,
        "agents_enabled": ["create", "analyst", "research", "adapt", "engage", "strategist"],
        "daily_brief": True,
        "email_brief": True,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "ai_images_per_month": 999999,
        "auto_approve": True,
        "ab_testing": True,
        "max_team_members": 25,
        "price_kes": 2999,
        "price_usd": 21,
        "trial_days": 14,
    },
}


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
    base = PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["starter"]).copy()
    overrides = _get_db_prices()
    if plan_tier in overrides:
        base["price_kes"] = overrides[plan_tier]["price_kes"]
        base["price_usd"] = overrides[plan_tier]["price_usd"]
    return base


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
