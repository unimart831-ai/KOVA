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

    # External integration (e-commerce platforms)
    product_url = models.URLField(
        blank=True,
        help_text="Direct purchase/product page URL — used for 'Shop Now' CTAs in generated content.",
    )
    external_id = models.CharField(
        max_length=255, blank=True,
        help_text="SKU or external platform product ID — for syncing with Shopify, WooCommerce, etc.",
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

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = ProductManager()

    class Meta:
        ordering = ["-is_featured", "-created_at"]
        unique_together = ["user", "name"]
        indexes = [
            models.Index(fields=["user", "stock_status"]),
            models.Index(fields=["user", "is_featured"]),
            models.Index(fields=["user", "is_active"]),
            models.Index(fields=["user", "offering_type"]),
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

    @property
    def all_image_urls(self):
        """Return list of all image URLs (primary + additional). Used for carousel content."""
        urls = []
        if self.image:
            urls.append(self.image.url)
        if self.additional_images:
            urls.extend(self.additional_images)
        return urls

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
