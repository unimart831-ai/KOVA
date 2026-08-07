import hashlib
import secrets
import string
import uuid
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

    class ApplicationType(models.TextChoices):
        STANDARD = "standard", "Standard Partner"
        CAMPUS_REP = "campus_rep", "Campus Rep"

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
    application_type = models.CharField(
        max_length=20,
        choices=ApplicationType.choices,
        default=ApplicationType.STANDARD,
        db_index=True,
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
    application_type = models.CharField(
        max_length=20,
        choices=PartnerApplication.ApplicationType.choices,
        default=PartnerApplication.ApplicationType.STANDARD,
        db_index=True,
    )
    stripe_connect_account_id = models.CharField(
        max_length=255, blank=True,
        help_text="Stripe Connect account ID for international payouts (v2 full Connect).",
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
    last_payment_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Timestamp of last counted subscription payment (dedupes webhook retries)",
    )
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
        unique_together = [("partner", "referral", "period_start")]

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


class ReferralClick(models.Model):
    """Tracks clicks on partner referral short links."""

    partner = models.ForeignKey(
        Partner, on_delete=models.SET_NULL, null=True, blank=True, related_name="clicks",
    )
    referral_code = models.CharField(max_length=30, db_index=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    landing_path = models.CharField(max_length=500, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["referral_code", "-created_at"]),
            models.Index(fields=["partner", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.referral_code} @ {self.created_at:%Y-%m-%d %H:%M}"


class PayoutRequest(models.Model):
    """Partner-initiated payout request (M-Pesa or Stripe Connect)."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending Review"
        APPROVED = "approved", "Approved"
        PAID = "paid", "Paid"
        REJECTED = "rejected", "Rejected"

    MIN_AMOUNT_KES = Decimal("500.00")

    partner = models.ForeignKey(
        Partner, on_delete=models.CASCADE, related_name="payout_requests",
    )
    amount_kes = models.DecimalField(max_digits=10, decimal_places=2)
    mpesa_number = models.CharField(
        max_length=30, blank=True,
        help_text="Kenyan M-Pesa number (254XXXXXXXXX).",
    )
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING, db_index=True,
    )
    admin_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    paid_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.partner.referral_code} — KES {self.amount_kes} ({self.get_status_display()})"


# ══════════════════════════════════════════════════════════════════════════════
# MARKETPLACE PARTNER SYSTEM
# ══════════════════════════════════════════════════════════════════════════════


def generate_api_key():
    """Generate a 40-char hex API key (displayed once, stored hashed)."""
    return secrets.token_hex(20)


def hash_api_key(raw_key: str) -> str:
    """SHA-256 hash for storage — never store raw keys."""
    return hashlib.sha256(raw_key.encode()).hexdigest()


class MarketplacePartner(models.Model):
    """
    A marketplace (Jumia, Jiji, Unimart, etc.) that provisions Kova
    accounts for their sellers and syncs product catalogs via API.

    Each marketplace has unique configuration: seller identity schemes,
    product schemas, billing models, and content rules.
    """

    class BillingModel(models.TextChoices):
        PER_SELLER = "per_seller", "Per Active Seller / Month"
        FLAT_FEE = "flat_fee", "Flat Monthly Fee"
        REVENUE_SHARE = "revenue_share", "Revenue Share"
        FREE_PILOT = "free_pilot", "Free Pilot (time-limited)"

    class SellerIdentity(models.TextChoices):
        EMAIL = "email", "Email Address"
        PHONE = "phone", "Phone Number"
        EXTERNAL_ID = "external_id", "Marketplace Seller ID"

    class SyncDirection(models.TextChoices):
        PUSH = "push", "Push (Marketplace → Kova)"
        PULL = "pull", "Pull (Kova fetches from Marketplace)"
        BOTH = "both", "Bidirectional Sync"

    # ── Identity ──
    name = models.CharField(
        max_length=200,
        help_text="Marketplace name (e.g. 'Jumia Kenya', 'Jiji Nigeria')",
    )
    slug = models.SlugField(
        max_length=80, unique=True,
        help_text="URL-safe identifier (e.g. 'jumia-ke', 'jiji-ng')",
    )
    partner = models.OneToOneField(
        Partner, on_delete=models.CASCADE, related_name="marketplace",
        help_text="Links to referral partner for commission tracking",
    )
    logo_url = models.URLField(blank=True)
    website = models.URLField(blank=True)
    contact_email = models.EmailField(blank=True)
    contact_name = models.CharField(max_length=200, blank=True)

    # ── API Credentials ──
    api_key_hash = models.CharField(
        max_length=64, unique=True, db_index=True,
        help_text="SHA-256 hash of the API key — raw key shown only on creation",
    )
    api_key_prefix = models.CharField(
        max_length=8,
        help_text="First 8 chars of the key for identification (e.g. 'kmp_a3x7')",
    )
    api_key_created_at = models.DateTimeField(auto_now_add=True)
    api_key_last_used = models.DateTimeField(null=True, blank=True)

    # ── Seller Configuration ──
    seller_identity_field = models.CharField(
        max_length=15, choices=SellerIdentity.choices, default=SellerIdentity.EMAIL,
        help_text="How this marketplace identifies sellers — determines provisioning lookup",
    )
    auto_activate_sellers = models.BooleanField(
        default=True,
        help_text="If True, sellers are active immediately. If False, seller must confirm/opt-in.",
    )
    seller_default_plan = models.CharField(
        max_length=20, default="growth",
        help_text="Plan tier assigned to provisioned sellers (starter/growth/pro/agency)",
    )
    max_sellers = models.PositiveIntegerField(
        default=1000,
        help_text="Contract limit on total provisioned sellers",
    )
    seller_welcome_email = models.BooleanField(
        default=True,
        help_text="Send welcome/activation email to provisioned sellers",
    )

    # ── Product Sync Configuration ──
    sync_direction = models.CharField(
        max_length=10, choices=SyncDirection.choices, default=SyncDirection.PUSH,
    )
    auto_snap_on_sync = models.BooleanField(
        default=True,
        help_text="Auto-trigger Snap to Sell vision AI when products are synced",
    )
    enforce_marketplace_cta = models.BooleanField(
        default=True,
        help_text="Force all generated content to link back to marketplace product pages",
    )
    product_field_mapping = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Maps marketplace product fields to Kova fields. "
            'E.g. {"title": "name", "sku": "external_id", "link": "product_url", '
            '"amount": "price", "photo": "image_url"}'
        ),
    )
    default_product_currency = models.CharField(
        max_length=5, default="KES",
        help_text="Currency for products if marketplace doesn't send currency per product",
    )

    # ── Billing ──
    billing_model = models.CharField(
        max_length=15, choices=BillingModel.choices, default=BillingModel.PER_SELLER,
    )
    rate_per_seller_kes = models.DecimalField(
        max_digits=10, decimal_places=2, default=Decimal("150.00"),
        help_text="Monthly rate per active seller (for per_seller billing)",
    )
    flat_fee_kes = models.DecimalField(
        max_digits=12, decimal_places=2, default=Decimal("0.00"),
        help_text="Monthly flat fee (for flat_fee billing)",
    )
    revenue_share_pct = models.DecimalField(
        max_digits=5, decimal_places=2, default=Decimal("0.00"),
        help_text="% of seller subscription revenue shared (for revenue_share billing)",
    )
    pilot_expires_at = models.DateTimeField(
        null=True, blank=True,
        help_text="When the free pilot period ends (for free_pilot billing)",
    )

    # ── Flexible Settings (marketplace-specific) ──
    settings = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Marketplace-specific config. Examples:\n"
            '{"allowed_platforms": ["instagram", "facebook", "tiktok"]}\n'
            '{"content_approval_required": true}\n'
            '{"max_products_per_seller": 200}\n'
            '{"branding": {"accent_color": "#F68B1E", "powered_by_text": "Powered by Kova"}}\n'
            '{"webhook_events": ["seller.activated", "content.generated", "product.synced"]}\n'
            '{"restricted_content_types": ["meme"]}'
        ),
    )

    # ── Webhooks ──
    # ── Description enrichment ──
    enrich_descriptions = models.BooleanField(
        default=True,
        help_text=(
            "Auto-append marketplace-specific data (condition, variants, specs) "
            "to product descriptions so AI generates richer content."
        ),
    )
    seller_data_mapping = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Maps marketplace seller fields to seller_metadata keys. "
            'E.g. {"business_name": "shop_name", "seller_tier": "tier", '
            '"campus_codes": "locations"}'
        ),
    )

    # ── Webhooks ──
    webhook_url = models.URLField(
        blank=True,
        help_text="URL to receive event notifications (seller activated, content generated, etc.)",
    )
    webhook_secret = models.CharField(
        max_length=64, blank=True,
        help_text="Secret for signing webhook payloads (HMAC-SHA256)",
    )

    is_sandbox = models.BooleanField(
        default=False,
        help_text="Sandbox mode — sellers provisioned but posts dry-run instead of publishing live",
    )

    # ── Status ──
    is_active = models.BooleanField(default=True)
    notes = models.TextField(blank=True, help_text="Internal notes about this partnership")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "marketplace partner"
        verbose_name_plural = "marketplace partners"

    def __str__(self):
        return f"{self.name} ({self.slug})"

    @property
    def active_sellers_count(self):
        return self.seller_accounts.filter(status="active").count()

    @property
    def total_sellers_count(self):
        return self.seller_accounts.count()

    @property
    def total_products_synced(self):
        from apps.commerce.products.models import Product
        return Product.objects.filter(marketplace_partner=self, is_active=True).count()

    @property
    def can_provision_sellers(self):
        return self.is_active and self.total_sellers_count < self.max_sellers

    def get_setting(self, key, default=None):
        """Safely get a marketplace-specific setting."""
        return self.settings.get(key, default) if self.settings else default

    def verify_api_key(self, raw_key: str) -> bool:
        return hash_api_key(raw_key) == self.api_key_hash

    @classmethod
    def authenticate(cls, raw_key: str):
        """Look up a marketplace partner by raw API key. Returns (partner, None) or (None, error)."""
        key_hash = hash_api_key(raw_key)
        try:
            mp = cls.objects.select_related("partner", "partner__user").get(
                api_key_hash=key_hash, is_active=True,
            )
            mp.api_key_last_used = timezone.now()
            mp.save(update_fields=["api_key_last_used"])
            return mp, None
        except cls.DoesNotExist:
            return None, "Invalid or inactive API key"


class MarketplaceSellerAccount(models.Model):
    """
    Links a marketplace seller to their Kova user account.

    One seller can only belong to one marketplace (enforced by unique user+marketplace).
    The external_seller_id is the marketplace's identifier for this seller.
    """

    class Status(models.TextChoices):
        INVITED = "invited", "Invited (pending activation)"
        ACTIVE = "active", "Active"
        SUSPENDED = "suspended", "Suspended by marketplace"
        CHURNED = "churned", "Churned / Deactivated"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    marketplace = models.ForeignKey(
        MarketplacePartner, on_delete=models.CASCADE, related_name="seller_accounts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="marketplace_seller_accounts",
    )
    external_seller_id = models.CharField(
        max_length=255,
        help_text="Marketplace's ID for this seller (e.g. Jumia seller ID, Jiji vendor code)",
    )
    status = models.CharField(
        max_length=12, choices=Status.choices, default=Status.INVITED,
    )

    # ── Seller business info (universal across marketplaces) ──
    business_name = models.CharField(
        max_length=200, blank=True,
        help_text="Seller's shop/business name on the marketplace",
    )
    business_url = models.URLField(
        blank=True,
        help_text="Direct URL to seller's store on the marketplace",
    )

    # ── Seller metadata (flexible, varies per marketplace) ──
    seller_metadata = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Marketplace-specific seller info. Examples:\n"
            '{"shop_name": "Jane Electronics", "shop_url": "https://jumia.co.ke/jane-electronics"}\n'
            '{"seller_tier": "gold", "store_rating": 4.7, "campus_codes": ["USIU", "KU"]}\n'
            '{"location": "Nairobi", "category": "Electronics", "is_approved": true, '
            '"delivery_zones": ["same_campus", "same_city"]}'
        ),
    )

    # ── Sync tracking ──
    products_synced = models.PositiveIntegerField(default=0)
    last_product_sync = models.DateTimeField(null=True, blank=True)
    content_generated = models.PositiveIntegerField(
        default=0,
        help_text="Total content pieces generated for this seller via marketplace",
    )

    # ── Timestamps ──
    provisioned_at = models.DateTimeField(auto_now_add=True)
    activated_at = models.DateTimeField(null=True, blank=True)
    suspended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-provisioned_at"]
        unique_together = [
            ("marketplace", "user"),
            ("marketplace", "external_seller_id"),
        ]
        indexes = [
            models.Index(fields=["marketplace", "status"]),
            models.Index(fields=["external_seller_id"]),
        ]
        verbose_name = "marketplace seller account"
        verbose_name_plural = "marketplace seller accounts"

    def __str__(self):
        return f"{self.user.email} @ {self.marketplace.name} ({self.get_status_display()})"

    def activate(self):
        """Activate this seller account."""
        self.status = self.Status.ACTIVE
        self.activated_at = timezone.now()
        self.save(update_fields=["status", "activated_at"])

    def suspend(self):
        """Suspend this seller account (marketplace-initiated)."""
        self.status = self.Status.SUSPENDED
        self.suspended_at = timezone.now()
        self.save(update_fields=["status", "suspended_at"])


class WebhookDeliveryLog(models.Model):
    """Audit log for outbound marketplace webhook dispatches."""

    class Status(models.TextChoices):
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    marketplace = models.ForeignKey(
        MarketplacePartner, on_delete=models.CASCADE, related_name="webhook_logs",
    )
    event = models.CharField(max_length=50, db_index=True)
    payload_hash = models.CharField(max_length=64, blank=True)
    status = models.CharField(max_length=10, choices=Status.choices, db_index=True)
    response_code = models.PositiveIntegerField(null=True, blank=True)
    attempts = models.PositiveIntegerField(default=1)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["marketplace", "-created_at"]),
        ]

    def __str__(self):
        return f"{self.marketplace.slug} — {self.event} — {self.status}"
