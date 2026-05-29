import uuid

from django.conf import settings
from django.db import models


class ProductCategory(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="product_categories"
    )
    name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)
    position = models.PositiveIntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["position", "name"]
        unique_together = ["user", "name"]
        verbose_name_plural = "product categories"

    def __str__(self):
        return self.name


class ProductManager(models.Manager):
    def in_stock(self, user):
        return self.filter(user=user, is_active=True, stock_status=Product.StockStatus.IN_STOCK)

    def low_stock(self, user):
        return self.filter(user=user, is_active=True, stock_status=Product.StockStatus.LOW_STOCK)

    def out_of_stock(self, user):
        return self.filter(user=user, is_active=True, stock_status=Product.StockStatus.OUT_OF_STOCK)

    def featured(self, user):
        return self.filter(user=user, is_active=True, is_featured=True)

    def promotable(self, user):
        """Products that are in stock or low stock — safe to promote."""
        return self.filter(
            user=user,
            is_active=True,
            stock_status__in=[Product.StockStatus.IN_STOCK, Product.StockStatus.LOW_STOCK,
                              Product.StockStatus.MADE_TO_ORDER, Product.StockStatus.UNLIMITED],
        )


class Product(models.Model):
    class OfferingType(models.TextChoices):
        PRODUCT = "product", "Physical Product"
        SERVICE = "service", "Service"
        DIGITAL = "digital", "Digital Product"

    class StockStatus(models.TextChoices):
        IN_STOCK = "in_stock", "In Stock"
        LOW_STOCK = "low_stock", "Low Stock"
        OUT_OF_STOCK = "out_of_stock", "Out of Stock"
        MADE_TO_ORDER = "made_to_order", "Made to Order"
        UNLIMITED = "unlimited", "Unlimited / Digital"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="products"
    )
    offering_type = models.CharField(
        max_length=10, choices=OfferingType.choices, default=OfferingType.PRODUCT,
        help_text="Product, service, or digital — determines how AI talks about it",
    )
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    category = models.ForeignKey(
        ProductCategory, on_delete=models.SET_NULL, null=True, blank=True, related_name="products"
    )
    price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    currency = models.CharField(max_length=5, default="KES")
    price_range_min = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    price_range_max = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    image = models.ImageField(upload_to="product_images/", blank=True)
    additional_images = models.JSONField(
        default=list, blank=True,
        help_text='URLs of extra product images for carousel content, e.g. ["/media/product_images/side.jpg", "https://cdn.example.com/img.jpg"]',
    )
    exclude_primary_image = models.BooleanField(
        default=False,
        help_text="When true, original upload is kept on file but omitted from carousels and posts.",
    )

    # External integration (e-commerce platforms)
    product_url = models.URLField(
        blank=True,
        help_text="Direct purchase/product page URL — used for 'Shop Now' CTAs in generated content.",
    )
    booking_link = models.ForeignKey(
        "bookings.BookingLink",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        help_text="If this is a service, use this booking page as the primary fulfillment path.",
    )
    fulfillment_url = models.URLField(
        blank=True,
        help_text="Optional external booking, access, or delivery URL for service and digital offers.",
    )
    fulfillment_notes = models.TextField(
        blank=True,
        help_text="Optional instructions for how customers book, access, or receive this offer.",
    )
    commerce_slug = models.SlugField(
        max_length=60,
        blank=True,
        db_index=True,
        help_text="Public slug for Commerce Link (/shop/<page>/<slug>/). Auto-generated.",
    )
    external_id = models.CharField(
        max_length=255, blank=True,
        help_text="SKU or external platform product ID — for syncing with Shopify, WooCommerce, etc.",
    )

    # Source tracking (marketplace / API / manual)
    class Source(models.TextChoices):
        MANUAL = "manual", "Manual Entry"
        SNAP = "snap", "Snap to Sell"
        CSV = "csv", "CSV Import"
        API = "api", "API"
        MARKETPLACE = "marketplace", "Marketplace Sync"

    source = models.CharField(
        max_length=15, choices=Source.choices, default=Source.MANUAL,
    )
    marketplace_partner = models.ForeignKey(
        "partners.MarketplacePartner", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="synced_products",
        help_text="Which marketplace synced this product (if source=marketplace)",
    )
    last_synced_at = models.DateTimeField(
        null=True, blank=True,
        help_text="Last time this product was updated via marketplace sync",
    )
    marketplace_metadata = models.JSONField(
        default=dict, blank=True,
        help_text=(
            "Marketplace-specific product data that doesn't map to Kova fields. "
            'E.g. {"condition": "used", "old_price": 5000, "variants": [{"size": "XL"}], '
            '"specifications": [{"key": "Material", "value": "Cotton"}], '
            '"campus_codes": ["USIU", "KU"], "vendor_net_price": 4500, "commission_pct": 10}'
        ),
    )

    # Stock (only relevant for physical products)
    stock_status = models.CharField(
        max_length=20, choices=StockStatus.choices, default=StockStatus.IN_STOCK,
    )
    quantity = models.PositiveIntegerField(null=True, blank=True, help_text="Leave blank if you don't track exact numbers")
    low_stock_threshold = models.PositiveIntegerField(default=5, help_text="Flag as low stock below this number")

    # Flags
    is_featured = models.BooleanField(default=False, help_text="Push harder in content")
    is_active = models.BooleanField(default=True)
    tags = models.JSONField(default=list, blank=True, help_text='E.g. ["bestseller", "new arrival"]')

    class VisualMode(models.TextChoices):
        AS_IS = "as_is", "Use as-is"
        QUICK_POLISH = "quick_polish", "Quick polish"
        PRO_SCENE = "pro_scene", "Studio polish"

    visual_mode = models.CharField(
        max_length=20,
        choices=VisualMode.choices,
        default=VisualMode.PRO_SCENE,
        help_text="How Kova treats product photos before content generation.",
    )

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    batch_snap_session = models.ForeignKey(
        "products.BatchSnapSession",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="products",
        help_text="Market Day batch this product was created in (Batch Snap)",
    )
    batch_index = models.PositiveSmallIntegerField(
        null=True,
        blank=True,
        help_text="Order within a Batch Snap session (0-based)",
    )

    objects = ProductManager()

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        unique_together = ["user", "name"]
        indexes = [
            models.Index(fields=["user", "stock_status"]),
            models.Index(fields=["user", "is_featured"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "offering_type"]),
            models.Index(fields=["user", "commerce_slug"]),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["user", "commerce_slug"],
                condition=models.Q(commerce_slug__gt=""),
                name="unique_commerce_slug_per_user",
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def tracks_stock(self):
        """Services and digital products don't have stock — skip all stock logic."""
        return self.offering_type == self.OfferingType.PRODUCT

    @property
    def display_price(self):
        if self.price:
            return f"{self.currency} {self.price:,.0f}"
        if self.price_range_min and self.price_range_max:
            return f"{self.currency} {self.price_range_min:,.0f}–{self.price_range_max:,.0f}"
        return ""

    @staticmethod
    def _coerce_image_url(value) -> str:
        if isinstance(value, str):
            return value.strip()
        return ""

    @property
    def all_image_urls(self):
        """Return list of image URLs used for carousel and post content."""
        urls: list[str] = []
        if self.image and not self.exclude_primary_image:
            try:
                primary = self._coerce_image_url(self.image.url)
            except Exception:
                primary = ""
            if primary:
                urls.append(primary)
        for item in self.additional_images or []:
            url = self._coerce_image_url(item)
            if url and url not in urls:
                urls.append(url)
        return urls

    @property
    def carousel_image_urls(self):
        """Square feed images for carousels — excludes story/banner/preflight assets."""
        from apps.products.photoroom_plus import filter_carousel_urls

        return filter_carousel_urls(self.all_image_urls)

    @property
    def shop_gallery_urls(self):
        """Clean product photos for public shop pages — no promo/text overlay slides."""
        from apps.products.photoroom_plus import filter_shop_gallery_urls

        urls = filter_shop_gallery_urls(self.all_image_urls)
        if urls:
            return urls
        return self.carousel_image_urls

    @property
    def cover_image_url(self):
        """Best thumbnail: first active content image, else original if nothing else."""
        active = self.all_image_urls
        if active:
            return active[0]
        if self.image:
            return self.image.url
        return ""

    @property
    def sync_source_label(self) -> str:
        """Human label for where this product was imported from."""
        if self.source == self.Source.MARKETPLACE and self.marketplace_partner_id:
            return self.marketplace_partner.name
        meta = self.marketplace_metadata or {}
        if meta.get("shopify"):
            domain = meta.get("shop_domain") or "Shopify"
            return f"Shopify · {domain.replace('.myshopify.com', '')}"
        if self.source == self.Source.API:
            return "Connected store"
        if self.source == self.Source.CSV:
            return "CSV import"
        if self.source == self.Source.SNAP:
            return "Snap to Sell"
        return ""

    @property
    def uses_external_buy_link(self) -> bool:
        from apps.products.product_cta import uses_marketplace_cta
        return uses_marketplace_cta(self)

    @property
    def has_service_fulfillment(self) -> bool:
        return self.offering_type == self.OfferingType.SERVICE and bool(
            self.booking_link_id or (self.fulfillment_url or "").strip()
        )

    @property
    def has_digital_fulfillment(self) -> bool:
        return self.offering_type == self.OfferingType.DIGITAL and bool(
            (self.fulfillment_url or "").strip() or (self.product_url or "").strip()
        )

    def check_low_stock(self):
        """Auto-update status if quantity drops below threshold. Skips services/digital."""
        if not self.tracks_stock:
            return
        if self.quantity is not None and self.stock_status == self.StockStatus.IN_STOCK:
            if self.quantity <= 0:
                self.stock_status = self.StockStatus.OUT_OF_STOCK
            elif self.quantity <= self.low_stock_threshold:
                self.stock_status = self.StockStatus.LOW_STOCK


class StockUpdate(models.Model):
    class Reason(models.TextChoices):
        MANUAL = "manual", "Manual Update"
        SALE = "sale", "Sale"
        RESTOCK = "restock", "Restock"
        ADJUSTMENT = "adjustment", "Adjustment"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="stock_updates")
    previous_status = models.CharField(max_length=20, choices=Product.StockStatus.choices)
    new_status = models.CharField(max_length=20, choices=Product.StockStatus.choices)
    previous_quantity = models.PositiveIntegerField(null=True, blank=True)
    new_quantity = models.PositiveIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=20, choices=Reason.choices, default=Reason.MANUAL)
    notes = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.product.name}: {self.previous_status} → {self.new_status}"


class StockAlert(models.Model):
    class AlertType(models.TextChoices):
        LOW_STOCK = "low_stock", "Low Stock Warning"
        OUT_OF_STOCK = "out_of_stock", "Out of Stock"
        RESTOCKED = "restocked", "Restocked"
        FEATURED_NO_CONTENT = "featured_no_content", "Featured — No Recent Content"
        OVERSTOCK_NO_PROMO = "overstock_no_promo", "In Stock — Not Being Promoted"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="stock_alerts"
    )
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name="alerts")
    alert_type = models.CharField(max_length=30, choices=AlertType.choices)
    message = models.CharField(max_length=500)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.product.name}"


# ══════════════════════════════════════════════════════════════════════════════
# RECEIPT TO RESTOCK — Snap a receipt/invoice → AI extracts items → auto-restock + content
# ══════════════════════════════════════════════════════════════════════════════


class RestockScan(models.Model):
    """
    Receipt/invoice photo → AI vision extracts products + quantities →
    auto-updates stock levels → triggers 'back in stock' content.

    Bridges physical supply chain (paper receipt) to digital marketing in one snap.
    """

    class Status(models.TextChoices):
        UPLOADED = "uploaded", "Uploaded"
        ANALYZING = "analyzing", "AI Analyzing Receipt"
        MATCHING = "matching", "Matching Products"
        UPDATING = "updating", "Updating Stock"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="restock_scans",
    )
    image = models.ImageField(
        upload_to="restock_scans/%Y/%m/",
        help_text="Photo of delivery receipt, invoice, or packing list",
    )
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.UPLOADED, db_index=True,
    )

    # ── AI extraction ──
    extracted_items = models.JSONField(
        default=list, blank=True,
        help_text=(
            "Items extracted from receipt by AI vision:\n"
            '[{"name": "Samsung A54", "quantity": 10, "unit_price": 42000,\n'
            '  "matched_product_id": "uuid-here", "match_confidence": 0.92},\n'
            ' {"name": "iPhone 15 Case", "quantity": 50, "unit_price": 500,\n'
            '  "matched_product_id": null, "match_confidence": 0}]'
        ),
    )
    supplier_name = models.CharField(
        max_length=200, blank=True,
        help_text="Supplier/vendor name extracted from receipt",
    )
    receipt_date = models.DateField(
        null=True, blank=True,
        help_text="Date on the receipt (if extracted)",
    )
    receipt_total = models.DecimalField(
        max_digits=12, decimal_places=2, null=True, blank=True,
        help_text="Total amount on the receipt (if extracted)",
    )
    receipt_currency = models.CharField(max_length=5, default="KES")

    # ── Results ──
    products_matched = models.PositiveIntegerField(
        default=0,
        help_text="Number of extracted items matched to existing products",
    )
    products_updated = models.PositiveIntegerField(
        default=0,
        help_text="Number of products whose stock was actually updated",
    )
    items_not_matched = models.JSONField(
        default=list, blank=True,
        help_text="Items that couldn't be matched to existing products",
    )
    content_seed = models.ForeignKey(
        "content.ContentSeed", on_delete=models.SET_NULL,
        null=True, blank=True, related_name="restock_scans",
        help_text="ContentSeed for 'back in stock' posts (auto-generated)",
    )

    # ── Metadata ──
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-created_at"]),
        ]

    def __str__(self):
        return f"RestockScan {self.pk} — {self.products_updated} updated ({self.get_status_display()})"


class BatchSnapSession(models.Model):
    """Market Day Mode — one Batch Snap launch (stall table → shop + content bundle)."""

    class Status(models.TextChoices):
        PROCESSING = "processing", "Processing items"
        FINALIZING = "finalizing", "Building stall launch"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="batch_snap_sessions",
    )
    stall_title = models.CharField(max_length=120, blank=True)
    voice_transcript = models.TextField(blank=True)
    stall_notes = models.TextField(blank=True)
    stall_context = models.JSONField(default=dict, blank=True)
    offering_type = models.CharField(max_length=10, default="product")
    default_price = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    default_currency = models.CharField(max_length=5, default="KES")
    launch_bundle = models.BooleanField(
        default=True,
        help_text="When true, create stall showcase reel + collection post + seller ping",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PROCESSING,
        db_index=True,
    )
    product_count = models.PositiveSmallIntegerField(default=0)
    items_processed = models.PositiveSmallIntegerField(default=0)
    shop_url = models.URLField(blank=True, max_length=500)
    bundle_seed = models.ForeignKey(
        "content.ContentSeed",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="batch_snap_sessions",
    )
    bundle_post_ids = models.JSONField(default=list, blank=True)
    whatsapp_message = models.TextField(blank=True)
    whatsapp_sent = models.BooleanField(default=False)
    error_message = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finalized_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        title = self.stall_title or f"Batch {self.product_count} items"
        return f"BatchSnapSession {title} ({self.get_status_display()})"


class CommercePayment(models.Model):
    """Tracks M-Pesa STK payments for product sales via Commerce Links / WhatsApp."""

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        EXPIRED = "expired", "Expired"

    class Source(models.TextChoices):
        COMMERCE_LINK = "commerce_link", "Commerce Link"
        WHATSAPP = "whatsapp", "WhatsApp"

    IDEMPOTENCY_WINDOW_SECONDS = 300  # 5 minutes

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="commerce_payments",
    )
    product = models.ForeignKey(
        Product, on_delete=models.SET_NULL, null=True, blank=True, related_name="commerce_payments",
    )
    transaction_ref = models.CharField(
        max_length=255, unique=True, db_index=True,
        help_text="Idempotency key: user_id:product_id:phone:timestamp_bucket",
    )
    checkout_request_id = models.CharField(max_length=100, unique=True, db_index=True)
    merchant_request_id = models.CharField(max_length=100, blank=True)
    receipt_number = models.CharField(max_length=50, blank=True, db_index=True)
    phone_number = models.CharField(max_length=15)
    amount = models.DecimalField(max_digits=12, decimal_places=2)
    currency = models.CharField(max_length=5, default="KES")
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.COMMERCE_LINK)
    result_code = models.IntegerField(null=True, blank=True)
    result_desc = models.TextField(blank=True)
    attempts_count = models.PositiveSmallIntegerField(
        default=1,
        help_text="How many STK push attempts the buyer made for this transaction",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["product", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["transaction_ref"]),
        ]

    def __str__(self):
        return f"Commerce {self.amount} {self.currency} — {self.get_status_display()}"

    @staticmethod
    def build_transaction_ref(user_id, product_id, phone: str) -> str:
        """
        Build a deterministic idempotency key scoped to a 5-minute bucket.
        Same buyer + product + phone within the same bucket → same ref.
        """
        from django.utils import timezone as tz
        import math
        bucket = math.floor(tz.now().timestamp() / CommercePayment.IDEMPOTENCY_WINDOW_SECONDS)
        return f"{user_id}:{product_id}:{phone}:{bucket}"
