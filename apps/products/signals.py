"""
Product signals — cache invalidation on save.
Stock transition automation lives in stock_actions.log_stock_change().
"""

import logging

from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender="products.Product")
def on_product_save(sender, instance, created, **kwargs):
    from apps.products.utils import invalidate_product_cache

    invalidate_product_cache(instance.user)

    if instance.is_active and not instance.commerce_slug:
        from apps.products.commerce_links import ensure_commerce_slug
        from apps.products.models import Product

        try:
            slug = ensure_commerce_slug(instance, save=False)
            updates = {"commerce_slug": slug}
            if not instance.product_url:
                from apps.products.commerce_links import commerce_link_path
                from django.conf import settings

                path = commerce_link_path(instance, instance.user.profile)
                site = getattr(settings, "SITE_URL", "").rstrip("/")
                updates["product_url"] = f"{site}{path}" if site else path
            Product.objects.filter(pk=instance.pk).update(**updates)
        except Exception:
            logger.exception(
                "Failed to assign commerce slug/link for product %s", instance.pk,
            )
