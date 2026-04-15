"""
Product signals — auto-actions when stock changes.

When a product's stock status changes, these signals:
  1. Invalidate all product-related caches
  2. Auto-pause scheduled posts that promote out-of-stock products
  3. Auto-generate "Back in Stock" content seeds when products are restocked
  4. Create stock alerts for significant stock changes
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="products.Product")
def on_product_save(sender, instance, created, **kwargs):
    """
    Fires after every Product save. Handles:
    - Cache invalidation (always)
    - OOS auto-pause (when product goes out of stock)
    - Restock seed generation (when product comes back in stock)
    """
    from apps.products.utils import invalidate_product_cache

    user = instance.user
    invalidate_product_cache(user)

    if created:
        return  # No stock transitions on brand new products

    # Services and digital products don't have stock — skip all stock logic
    if not instance.tracks_stock:
        return

    # Detect stock status transitions via StockUpdate records
    from apps.products.models import StockUpdate

    latest_update = (
        StockUpdate.objects.filter(product=instance)
        .order_by("-created_at")
        .first()
    )

    if not latest_update:
        return

    old_status = latest_update.previous_status
    new_status = latest_update.new_status

    # Transition: anything → OUT_OF_STOCK → auto-pause scheduled posts
    if new_status == "out_of_stock" and old_status != "out_of_stock":
        try:
            from apps.products.utils import pause_oos_scheduled_posts
            paused = pause_oos_scheduled_posts(user, instance.name)
            if paused:
                logger.info(
                    "Auto-paused %d posts for OOS product '%s' (user: %s)",
                    paused, instance.name, user.email,
                )

                # Create a stock alert about the auto-pause
                from apps.products.models import StockAlert
                StockAlert.objects.create(
                    user=user,
                    product=instance,
                    alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                    message=(
                        f"⚠️ {instance.name} is out of stock. "
                        f"Auto-paused {paused} scheduled post(s) that mention it."
                    ),
                )
        except Exception as e:
            logger.warning("Auto-pause for OOS product failed: %s", e)

    # Transition: OUT_OF_STOCK → anything else → auto-generate restock seed
    elif old_status == "out_of_stock" and new_status != "out_of_stock":
        try:
            from apps.products.utils import generate_restock_seed
            created_seed = generate_restock_seed(user, instance.name)
            if created_seed:
                logger.info(
                    "Auto-created restock seed for '%s' (user: %s)",
                    instance.name, user.email,
                )

                from apps.products.models import StockAlert
                StockAlert.objects.create(
                    user=user,
                    product=instance,
                    alert_type=StockAlert.AlertType.RESTOCKED,
                    message=(
                        f"🎉 {instance.name} is back in stock! "
                        f"Auto-created a 'Back in Stock' content seed."
                    ),
                )
        except Exception as e:
            logger.warning("Auto restock seed generation failed: %s", e)
