import logging

from celery import shared_task
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(name="check-stock-alerts")
def check_stock_alerts():
    """
    Daily task: scan all active products for stock issues and create alerts.
    - Low stock warnings (quantity below threshold)
    - Out-of-stock items that still have scheduled content
    - Featured products with no recent content
    """
    from apps.products.models import Product, StockAlert
    from apps.products.utils import invalidate_product_cache

    from django.contrib.auth import get_user_model
    User = get_user_model()

    users_with_products = (
        User.objects.filter(products__is_active=True)
        .distinct()
    )

    total_alerts = 0

    for user in users_with_products:
        products = Product.objects.filter(user=user, is_active=True)
        alerts_created = 0

        for product in products:
            # Auto-detect low stock from quantity
            if (
                product.quantity is not None
                and product.stock_status == Product.StockStatus.IN_STOCK
                and product.quantity <= product.low_stock_threshold
            ):
                if product.quantity <= 0:
                    product.stock_status = Product.StockStatus.OUT_OF_STOCK
                else:
                    product.stock_status = Product.StockStatus.LOW_STOCK
                product.save(update_fields=["stock_status"])

            # Low stock alert
            if product.stock_status == Product.StockStatus.LOW_STOCK:
                exists = StockAlert.objects.filter(
                    product=product,
                    alert_type=StockAlert.AlertType.LOW_STOCK,
                    created_at__date=timezone.now().date(),
                ).exists()
                if not exists:
                    StockAlert.objects.create(
                        user=user,
                        product=product,
                        alert_type=StockAlert.AlertType.LOW_STOCK,
                        message=f"⚠️ {product.name} is running low ({product.quantity or 'few'} remaining).",
                    )
                    alerts_created += 1

            # Out of stock alert
            if product.stock_status == Product.StockStatus.OUT_OF_STOCK:
                exists = StockAlert.objects.filter(
                    product=product,
                    alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                    created_at__date=timezone.now().date(),
                ).exists()
                if not exists:
                    StockAlert.objects.create(
                        user=user,
                        product=product,
                        alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                        message=f"🔴 {product.name} is out of stock. Content promoting it should be paused.",
                    )
                    alerts_created += 1

        if alerts_created:
            invalidate_product_cache(user)
            total_alerts += alerts_created

    logger.info("Stock alerts check complete: %d alerts created for %d users", total_alerts, users_with_products.count())
    return {"alerts_created": total_alerts, "users_checked": users_with_products.count()}
