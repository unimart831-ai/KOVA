import uuid

from django.conf import settings
from django.db import models


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
        on_delete=models.CASCADE,
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
        "max_posts_per_month": 10,
        "max_seeds_per_month": 5,
        "agents_enabled": ["create", "analyst"],
        "daily_brief": True,
        "email_brief": False,
        "engagement_agent": False,
        "competitor_tracking": False,
        "ai_image_generation": False,
        "auto_approve": False,
        "price_kes": 99,
        "price_usd": 1,
        "trial_days": 14,
    },
    "growth": {
        "label": "Kazi / Growth",
        "max_social_accounts": 3,
        "max_posts_per_month": 50,
        "max_seeds_per_month": 30,
        "agents_enabled": ["create", "analyst", "research", "adapt"],
        "daily_brief": True,
        "email_brief": True,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "auto_approve": False,
        "price_kes": 500,
        "price_usd": 5,
        "trial_days": 14,
    },
    "pro": {
        "label": "Biashara / Pro",
        "max_social_accounts": 10,
        "max_posts_per_month": 999999,  # Unlimited
        "max_seeds_per_month": 999999,
        "agents_enabled": ["create", "analyst", "research", "adapt", "engage", "strategist"],
        "daily_brief": True,
        "email_brief": True,
        "engagement_agent": True,
        "competitor_tracking": True,
        "ai_image_generation": True,
        "auto_approve": True,
        "price_kes": 1500,
        "price_usd": 15,
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
        "auto_approve": True,
        "price_kes": 3500,
        "price_usd": 29,
        "trial_days": 14,
    },
}


def get_plan_limits(plan_tier):
    """Get the limits for a plan tier. Defaults to starter if unknown."""
    return PLAN_LIMITS.get(plan_tier, PLAN_LIMITS["starter"])


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
        on_delete=models.CASCADE,
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
