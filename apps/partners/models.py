import secrets
import string
from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


# ── Commission tiers ──────────────────────────────────────────────────────────

COMMISSION_TIERS = [
    # (min_active_clients, rate)
    (1, Decimal("0.15")),    # 1–25  → 15%
    (26, Decimal("0.20")),   # 26–75 → 20%
    (76, Decimal("0.25")),   # 76–150 → 25%
    (151, Decimal("0.30")),  # 150+  → 30%
]

MILESTONE_BONUSES = [
    # (clients_required, bonus_kes, label, extras)
    (10, 2_500, "Ambassador", "Ambassador badge"),
    (25, 10_000, "Connector", "Commission → 20%"),
    (50, 50_000, "Catalyst", "Featured on website"),
    (100, 200_000, "Powerhouse", "Commission → 25% + Profit Share"),
    (250, 500_000, "Legend", "Commission → 30% + Higher profit share"),
]

PROFIT_SHARE_TIERS = [
    # (min_active_clients, share_rate, min_avg_retention_months)
    (100, Decimal("0.01"), 6),   # 1% quarterly
    (200, Decimal("0.02"), 6),   # 2% quarterly
    (500, Decimal("0.03"), 6),   # 3% quarterly + Advisory seat
]


def generate_referral_code(name: str = "") -> str:
    """Generate a unique referral code like KOVA-JAMES-A3X7."""
    prefix = name.strip().upper().replace(" ", "")[:8] if name else "PARTNER"
    suffix = "".join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    return f"KOVA-{prefix}-{suffix}"


def get_commission_rate(active_count: int) -> Decimal:
    """Return the commission rate for a given active client count."""
    rate = Decimal("0.15")
    for threshold, tier_rate in COMMISSION_TIERS:
        if active_count >= threshold:
            rate = tier_rate
    return rate


def get_next_milestone(total_referred: int):
    """Return the next milestone dict or None if all achieved."""
    for clients, bonus, label, extras in MILESTONE_BONUSES:
        if total_referred < clients:
            return {
                "clients_required": clients,
                "bonus_kes": bonus,
                "label": label,
                "extras": extras,
                "progress": total_referred,
                "remaining": clients - total_referred,
            }
    return None


# ── Models ────────────────────────────────────────────────────────────────────

class PartnerApplication(models.Model):
    """Application to join the Growth Partners Program."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="partner_application",
        null=True,
        blank=True,
        help_text="Linked Kova account (optional at application time)",
    )
    full_name = models.CharField(max_length=200)
    email = models.EmailField()
    phone = models.CharField(max_length=30, blank=True)
    company = models.CharField(max_length=200, blank=True)
    website = models.URLField(blank=True)
    audience_description = models.TextField(
        help_text="Describe your audience, channels, and how you plan to promote Kova."
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.full_name} ({self.get_status_display()})"


class Partner(models.Model):
    """An approved Growth Partner with referral tracking."""

    class Tier(models.TextChoices):
        STARTER = "starter", "Starter (15%)"
        CONNECTOR = "connector", "Connector (20%)"
        CATALYST = "catalyst", "Catalyst (25%)"
        POWERHOUSE = "powerhouse", "Powerhouse (30%)"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="partner_profile",
    )
    application = models.OneToOneField(
        PartnerApplication,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="partner",
    )
    referral_code = models.CharField(
        max_length=30, unique=True, db_index=True,
        help_text="Unique code like KOVA-JAMES-A3X7",
    )
    tier = models.CharField(
        max_length=15, choices=Tier.choices, default=Tier.STARTER
    )
    commission_rate = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("0.15"),
        help_text="Current commission rate (0.15 = 15%)",
    )
    profit_share_rate = models.DecimalField(
        max_digits=4, decimal_places=2, default=Decimal("0.00"),
        help_text="Quarterly profit share rate (0.00 = not eligible)",
    )
    is_active = models.BooleanField(default=True)
    total_earned_kes = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00")
    )
    pending_payout_kes = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("0.00")
    )
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-joined_at"]

    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} — {self.referral_code}"

    def save(self, *args, **kwargs):
        if not self.referral_code:
            name = self.user.get_full_name() or self.user.email.split("@")[0]
            self.referral_code = generate_referral_code(name)
        super().save(*args, **kwargs)

    # ── Computed properties ──

    @property
    def active_referrals_count(self):
        return self.referrals.filter(is_active=True, is_flagged=False, activated_at__isnull=False).count()

    @property
    def pending_referrals_count(self):
        return self.referrals.filter(is_active=True, is_flagged=False, activated_at__isnull=True).count()

    @property
    def flagged_referrals_count(self):
        return self.referrals.filter(is_flagged=True).count()

    @property
    def total_referrals_count(self):
        return self.referrals.count()

    @property
    def next_milestone(self):
        return get_next_milestone(self.active_referrals_count)

    def recalculate_tier(self):
        """Recalculate commission rate and tier based on active client count."""
        count = self.active_referrals_count
        rate = get_commission_rate(count)
        # Milestone overrides (higher rate wins)
        for clients, _, _, _ in MILESTONE_BONUSES:
            if count >= clients:
                pass  # Milestone rate upgrades handled by commission tiers already
        self.commission_rate = rate
        if count >= 151:
            self.tier = self.Tier.POWERHOUSE
        elif count >= 76:
            self.tier = self.Tier.CATALYST
        elif count >= 26:
            self.tier = self.Tier.CONNECTOR
        else:
            self.tier = self.Tier.STARTER
        self.save(update_fields=["commission_rate", "tier"])


class Referral(models.Model):
    """Tracks a single referred client."""

    partner = models.ForeignKey(
        Partner, on_delete=models.CASCADE, related_name="referrals"
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name="referred_by",
    )
    referral_code_used = models.CharField(max_length=30)
    signed_up_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Set when client completes 2 consecutive paid months",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="False if client canceled or was flagged",
    )
    commission_expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="24 months from first payment",
    )
    consecutive_paid_months = models.PositiveIntegerField(default=0)
    current_plan = models.CharField(max_length=20, blank=True)
    # Anti-sybil fields
    signup_ip = models.GenericIPAddressField(
        null=True, blank=True,
        help_text="IP address at signup — used for sybil detection",
    )
    is_flagged = models.BooleanField(
        default=False,
        help_text="True if referral triggered anti-fraud checks",
    )
    flag_reason = models.TextField(
        blank=True,
        help_text="Why this referral was flagged (IP clustering, disposable email, etc.)",
    )

    class Meta:
        ordering = ["-signed_up_at"]

    def __str__(self):
        status = "Active" if self.activated_at else "Pending"
        return f"{self.referred_user.email} → {self.partner.referral_code} ({status})"

    @property
    def is_commission_active(self):
        """True if commission is still being generated for this referral."""
        if not self.activated_at or not self.is_active:
            return False
        if self.commission_expires_at and timezone.now() > self.commission_expires_at:
            return False
        return True


class Commission(models.Model):
    """Monthly commission record for a partner."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"

    partner = models.ForeignKey(
        Partner, on_delete=models.CASCADE, related_name="commissions"
    )
    referral = models.ForeignKey(
        Referral, on_delete=models.CASCADE, related_name="commissions",
        null=True, blank=True,
    )
    period_start = models.DateField()
    period_end = models.DateField()
    client_revenue_kes = models.DecimalField(max_digits=10, decimal_places=2)
    commission_rate = models.DecimalField(max_digits=4, decimal_places=2)
    amount_kes = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )
    paid_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-period_start"]

    def __str__(self):
        return f"{self.partner.referral_code} — {self.period_start} — KES {self.amount_kes}"


class MilestoneAward(models.Model):
    """Record of a milestone bonus awarded to a partner."""

    partner = models.ForeignKey(
        Partner, on_delete=models.CASCADE, related_name="milestones"
    )
    clients_required = models.PositiveIntegerField()
    label = models.CharField(max_length=50)
    bonus_kes = models.DecimalField(max_digits=10, decimal_places=2)
    extras = models.CharField(max_length=200, blank=True)
    awarded_at = models.DateTimeField(auto_now_add=True)
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-awarded_at"]
        unique_together = [("partner", "clients_required")]

    def __str__(self):
        return f"{self.partner.referral_code} — {self.label} ({self.clients_required} clients)"
