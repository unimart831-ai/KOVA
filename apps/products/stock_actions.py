"""
Stock change logging and automated transition actions.

Call log_stock_change() AFTER saving the product so transitions run reliably.
"""

import logging

from apps.products.models import Product, StockUpdate

logger = logging.getLogger(__name__)


def log_stock_change(
    product,
    *,
    previous_status,
    previous_quantity,
    reason=StockUpdate.Reason.MANUAL,
    notes="",
):
    """
    Record a stock update and run OOS pause / restock seed automation.
    Returns StockUpdate or None if nothing changed.
    """
    new_status = product.stock_status
    new_quantity = product.quantity

    if previous_status == new_status and previous_quantity == new_quantity:
        return None

    update = StockUpdate.objects.create(
        product=product,
        previous_status=previous_status,
        new_status=new_status,
        previous_quantity=previous_quantity,
        new_quantity=new_quantity,
        reason=reason,
        notes=notes,
    )
    apply_stock_transition_actions(product, previous_status, new_status)
    return update


def apply_stock_transition_actions(product, old_status, new_status):
    """OOS → pause posts; restock → back-in-stock content seed."""
    if not product.tracks_stock:
        return

    user = product.user

    if new_status == Product.StockStatus.OUT_OF_STOCK and old_status != Product.StockStatus.OUT_OF_STOCK:
        try:
            from apps.products.models import StockAlert
            from apps.products.utils import pause_oos_scheduled_posts

            paused = pause_oos_scheduled_posts(user, product.name)
            if paused:
                StockAlert.objects.create(
                    user=user,
                    product=product,
                    alert_type=StockAlert.AlertType.OUT_OF_STOCK,
                    message=(
                        f"⚠️ {product.name} is out of stock. "
                        f"Auto-paused {paused} scheduled post(s) that mention it."
                    ),
                )
        except Exception as exc:
            logger.warning("Auto-pause for OOS product failed: %s", exc)

    elif old_status == Product.StockStatus.OUT_OF_STOCK and new_status != Product.StockStatus.OUT_OF_STOCK:
        try:
            from apps.products.models import StockAlert
            from apps.products.utils import generate_restock_seed

            if generate_restock_seed(user, product.name, product=product):
                StockAlert.objects.create(
                    user=user,
                    product=product,
                    alert_type=StockAlert.AlertType.RESTOCKED,
                    message=(
                        f"🎉 {product.name} is back in stock! "
                        f"Auto-created a 'Back in Stock' post in your Queue."
                    ),
                )
        except Exception as exc:
            logger.warning("Auto restock seed generation failed: %s", exc)


def record_sale(product, quantity=1, notes=""):
    """Decrement stock when a sale is recorded."""
    if not product.tracks_stock or product.quantity is None:
        return None

    old_status = product.stock_status
    old_quantity = product.quantity
    product.quantity = max(0, old_quantity - quantity)
    product.check_low_stock()
    product.save(update_fields=["quantity", "stock_status", "updated_at"])

    return log_stock_change(
        product,
        previous_status=old_status,
        previous_quantity=old_quantity,
        reason=StockUpdate.Reason.SALE,
        notes=notes or f"Sale recorded (−{quantity})",
    )
