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
