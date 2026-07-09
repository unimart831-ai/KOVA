"""
Product signals — cache invalidation on save; commerce → lead loop.
Stock transition automation lives in stock_actions.log_stock_change().
"""

import logging

from django.db.models.signals import post_save, pre_save
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
            from apps.products.product_cta import uses_marketplace_cta

            if not instance.product_url and not uses_marketplace_cta(instance):
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


@receiver(pre_save, sender="products.CommercePayment")
def _track_commerce_payment_status(sender, instance, **kwargs):
    from apps.products.models import CommercePayment

    if instance.pk:
        try:
            previous = CommercePayment.objects.get(pk=instance.pk)
            instance._was_completed = previous.status == CommercePayment.Status.COMPLETED
        except CommercePayment.DoesNotExist:
            instance._was_completed = False
    else:
        instance._was_completed = False


@receiver(post_save, sender="products.CommercePayment")
def on_commerce_payment_completed(sender, instance, **kwargs):
    """Every buyer becomes a lead — belt-and-suspenders with M-Pesa webhook."""
    from apps.products.models import CommercePayment

    if instance.status != CommercePayment.Status.COMPLETED:
        return
    if getattr(instance, "_was_completed", False):
        return
    try:
        from apps.leads.bridges import create_lead_from_commerce_payment
        create_lead_from_commerce_payment(instance)
    except Exception:
        logger.exception(
            "Failed to create lead from commerce payment %s", instance.pk,
        )

    # Close the revenue loop: attribute to funnel + cross-sell.
    try:
        from apps.products.post_purchase import run_post_purchase
        run_post_purchase(instance)
    except Exception:
        logger.exception(
            "Post-purchase loop failed for commerce payment %s", instance.pk,
        )

    # WhatsApp-first: alert the owner (in-app + WhatsApp) after commit,
    # for every completion path (M-Pesa webhook, card, manual).
    try:
        from django.db import transaction

        from apps.products.commerce_wa_orders import notify_seller_payment_received

        transaction.on_commit(lambda: notify_seller_payment_received(instance))
    except Exception:
        logger.exception(
            "Owner payment alert failed for commerce payment %s", instance.pk,
        )
