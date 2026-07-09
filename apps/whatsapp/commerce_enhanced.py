"""
Experimental WhatsApp commerce handler (NOT wired to production webhook).

Production customer commerce uses ``apps.whatsapp.commerce`` — including
multi-item cart + M-Pesa checkout. This module is a prototype state machine
kept for reference; do not import from ``whatsapp/tasks.py`` until merged.

Planned enhancements here (partial):
- Catalog browsing with search and category filtering
- Product details with images via WhatsApp media messages
- In-chat M-Pesa payment initiation + status tracking
- Post-purchase flow (receipt, review request, cross-sell)
- Lead enrichment on every commerce interaction
"""
from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation

from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ═════════════════════════════════════════════════════════════════════════════
# STATES
# ═════════════════════════════════════════════════════════════════════════════


class CommerceState:
    """Conversation commerce states tracked in WhatsAppConversation.metadata."""
    IDLE = "idle"
    BROWSING = "browsing"
    VIEWING_PRODUCT = "viewing_product"
    AWAITING_PAYMENT_CONFIRM = "awaiting_payment_confirm"
    PAYMENT_PENDING = "payment_pending"
    PAYMENT_COMPLETE = "payment_complete"
    POST_PURCHASE = "post_purchase"


# Keywords that signal the buyer wants to shop (English + Swahili basics).
_SHOPPING_KEYWORDS = frozenset({
    "buy", "price", "cost", "how much", "order", "purchase",
    "shop", "catalog", "products", "menu", "what do you sell",
    "available", "stock", "catalogue", "bei", "nunua",
    "show me", "i want", "do you have",
})


# ═════════════════════════════════════════════════════════════════════════════
# MAIN ENTRY POINT
# ═════════════════════════════════════════════════════════════════════════════


def handle_enhanced_commerce(conversation, message_text: str, social_account) -> dict | None:
    """
    Enhanced commerce handler.  Returns a response dict or ``None`` if the
    message is not commerce-related and should fall through to AI auto-reply.

    Response format::

        {
            "type": "text" | "interactive_list" | "interactive_buttons" | "image_with_buttons",
            "body": str,
            "items": [...],         # for lists
            "button_text": str,     # for lists
            "buttons": [...],       # for buttons
            "image_url": str,       # for image messages
        }
    """
    try:
        return _route(conversation, message_text, social_account)
    except Exception:
        logger.exception(
            "Enhanced commerce handler error for conversation %s",
            conversation.pk,
        )
        return None


def _route(conversation, message_text: str, social_account) -> dict | None:
    user = social_account.user
    metadata = conversation.metadata or {}
    commerce_state = metadata.get("commerce_state", CommerceState.IDLE)

    text_lower = (message_text or "").strip().lower()

    # Global escape — reset on explicit cancel regardless of state.
    if text_lower in ("cancel", "exit", "stop", "quit") and commerce_state != CommerceState.IDLE:
        _update_commerce_state(conversation, CommerceState.IDLE)
        return {"type": "text", "body": "No problem! Type 'menu' whenever you'd like to browse again."}

    if _is_shopping_intent(text_lower) and commerce_state == CommerceState.IDLE:
        return _show_catalog_menu(user, conversation)

    if commerce_state == CommerceState.BROWSING:
        return _handle_category_browse(user, conversation, text_lower)

    if commerce_state == CommerceState.VIEWING_PRODUCT:
        return _handle_product_action(user, conversation, text_lower)

    if commerce_state == CommerceState.AWAITING_PAYMENT_CONFIRM:
        return _handle_payment_confirm(user, conversation, text_lower)

    if commerce_state == CommerceState.PAYMENT_PENDING:
        return check_payment_and_notify(conversation)

    if commerce_state == CommerceState.PAYMENT_COMPLETE:
        return _handle_post_purchase(user, conversation, text_lower)

    return None


# ═════════════════════════════════════════════════════════════════════════════
# INTENT DETECTION
# ═════════════════════════════════════════════════════════════════════════════


def _is_shopping_intent(text: str) -> bool:
    """Return ``True`` if *text* contains any shopping keyword."""
    return any(kw in text for kw in _SHOPPING_KEYWORDS)


# ═════════════════════════════════════════════════════════════════════════════
# CATALOG / CATEGORY MENU
# ═════════════════════════════════════════════════════════════════════════════


def _show_catalog_menu(user, conversation) -> dict:
    """Show product categories as a WhatsApp list message."""
    try:
        from apps.products.models import Product, ProductCategory
    except ImportError:
        return {"type": "text", "body": "Our catalog isn't available right now. Please try again later."}

    categories = (
        ProductCategory.objects
        .filter(user=user, is_active=True)
        .order_by("position")[:10]
    )

    uncategorized_count = (
        Product.objects
        .filter(user=user, is_active=True, category__isnull=True)
        .exclude(stock_status="out_of_stock")
        .count()
    )

    items = []
    for cat in categories:
        product_count = (
            Product.objects
            .filter(user=user, category=cat, is_active=True)
            .exclude(stock_status="out_of_stock")
            .count()
        )
        if product_count:
            items.append({
                "id": f"cat_{cat.pk}",
                "title": cat.name[:24],
                "description": f"{product_count} items available",
            })

    if uncategorized_count:
        items.append({
            "id": "cat_all",
            "title": "All Products",
            "description": f"{uncategorized_count} more items",
        })

    if not items:
        return {
            "type": "text",
            "body": "We don't have any products available right now. Check back soon!",
        }

    _update_commerce_state(conversation, CommerceState.BROWSING)

    profile = getattr(user, "profile", None)
    business_name = (getattr(profile, "company_name", "") or "") or "our store"

    return {
        "type": "interactive_list",
        "body": f"Welcome to {business_name}! Browse our catalog below:",
        "button_text": "View Categories",
        "items": [{"title": "Categories", "rows": items}],
    }


# ═════════════════════════════════════════════════════════════════════════════
# CATEGORY BROWSE → PRODUCT LIST
# ═════════════════════════════════════════════════════════════════════════════


def _handle_category_browse(user, conversation, text: str) -> dict:
    """Handle category selection — show matching products."""
    try:
        from apps.products.models import Product
    except ImportError:
        return {"type": "text", "body": "Products are unavailable. Please try later."}

    if text.startswith("cat_"):
        category_id = text.removeprefix("cat_")
        if category_id == "all":
            products = (
                Product.objects
                .filter(user=user, is_active=True)
                .exclude(stock_status="out_of_stock")
                .order_by("-is_featured", "-created_at")[:5]
            )
        else:
            products = (
                Product.objects
                .filter(user=user, category_id=category_id, is_active=True)
                .exclude(stock_status="out_of_stock")
                .order_by("-is_featured", "-created_at")[:5]
            )
    elif text in ("menu", "back", "categories"):
        _update_commerce_state(conversation, CommerceState.IDLE)
        return _show_catalog_menu(user, conversation)
    else:
        # Free-text search by product name
        products = (
            Product.objects
            .filter(user=user, is_active=True, name__icontains=text)
            .exclude(stock_status="out_of_stock")[:5]
        )

    if not products:
        return {
            "type": "text",
            "body": "No products found in that category. Try another or type 'menu' to see all categories.",
        }

    buttons = []
    product_list_text = ""
    for i, product in enumerate(products[:3]):
        price_str = f"KES {product.price:,.0f}" if product.price else "Price on request"
        product_list_text += f"\n{i + 1}. *{product.name}* — {price_str}"
        buttons.append({
            "id": f"prod_{product.pk}",
            "title": product.name[:20],
        })

    if len(products) > 3:
        product_list_text += f"\n\n_…and {len(products) - 3} more. Type a product name to search._"

    _update_commerce_state(conversation, CommerceState.VIEWING_PRODUCT, {
        "browsing_products": [str(p.pk) for p in products[:3]],
    })

    return {
        "type": "interactive_buttons",
        "body": f"Here's what we have:{product_list_text}\n\nTap to view details:",
        "buttons": buttons,
    }


# ═════════════════════════════════════════════════════════════════════════════
# PRODUCT DETAIL + BUY INTENT
# ═════════════════════════════════════════════════════════════════════════════


def _handle_product_action(user, conversation, text: str) -> dict:
    """Handle product detail view or buy intent."""
    try:
        from apps.products.models import Product
    except ImportError:
        return {"type": "text", "body": "Product details are unavailable right now."}

    if text.startswith("prod_"):
        product_id = text.removeprefix("prod_")
        try:
            product = Product.objects.get(pk=product_id, user=user, is_active=True)
        except Product.DoesNotExist:
            return {"type": "text", "body": "Product not found. Type 'menu' to browse again."}

        price_str = f"KES {product.price:,.0f}" if product.price else "Price on request"
        stock_str = ""
        if product.stock_status == "low_stock":
            stock_str = "\n⚠️ *Limited stock remaining*"

        description = (product.description or "")[:300]

        body = (
            f"*{product.name}*\n"
            f"{price_str}{stock_str}\n\n"
            f"{description}\n\n"
            f"Would you like to order this?"
        )

        _update_commerce_state(conversation, CommerceState.AWAITING_PAYMENT_CONFIRM, {
            "selected_product_id": str(product.pk),
            "selected_product_name": product.name,
            "selected_product_price": str(product.price or 0),
        })

        buttons = [
            {"id": "buy_confirm", "title": "Buy Now"},
            {"id": "browse_more", "title": "Browse More"},
        ]

        response: dict = {
            "type": "interactive_buttons",
            "body": body,
            "buttons": buttons,
        }

        if product.image:
            try:
                response["image_url"] = product.image.url
                response["type"] = "image_with_buttons"
            except Exception:
                pass

        return response

    if text in ("menu", "back", "categories"):
        _update_commerce_state(conversation, CommerceState.IDLE)
        return _show_catalog_menu(user, conversation)

    return {"type": "text", "body": "Tap a product button above, or type 'menu' to browse categories."}


# ═════════════════════════════════════════════════════════════════════════════
# PAYMENT CONFIRMATION + STK PUSH
# ═════════════════════════════════════════════════════════════════════════════


def _handle_payment_confirm(user, conversation, text: str) -> dict:
    """Handle buy confirmation and initiate M-Pesa STK push."""
    metadata = conversation.metadata or {}

    if text in ("buy_confirm", "yes", "buy", "order", "confirm"):
        product_id = metadata.get("selected_product_id")
        product_name = metadata.get("selected_product_name", "item")
        price_raw = metadata.get("selected_product_price", "0")

        buyer_phone = conversation.contact_wa_id

        try:
            price = Decimal(price_raw)
        except (InvalidOperation, TypeError):
            price = Decimal("0")

        if not buyer_phone or price <= 0:
            _update_commerce_state(conversation, CommerceState.IDLE)
            return {"type": "text", "body": "Unable to process this order. Please contact us directly."}

        # Re-check stock at the moment of purchase — it may have sold out
        # while the customer was deciding.
        if product_id:
            from apps.products.models import Product

            product = Product.objects.filter(pk=product_id, user=user).first()
            if product and product.stock_status == "out_of_stock":
                _update_commerce_state(conversation, CommerceState.IDLE)
                return {
                    "type": "text",
                    "body": (
                        f"Sorry, *{product.name}* just sold out. 😔\n\n"
                        "Type 'menu' to browse other products — we'll let you "
                        "know when it's back in stock!"
                    ),
                }

        payment = _initiate_whatsapp_payment(user, product_id, buyer_phone, price)

        if payment:
            _update_commerce_state(conversation, CommerceState.PAYMENT_PENDING, {
                "payment_id": str(payment.pk),
            })
            return {
                "type": "text",
                "body": (
                    f"💳 *Payment initiated!*\n\n"
                    f"An M-Pesa prompt has been sent to your phone for *KES {price:,.0f}*.\n\n"
                    f"Please enter your PIN to complete the purchase of *{product_name}*.\n\n"
                    f"_I'll confirm once payment is received._"
                ),
            }

        _update_commerce_state(conversation, CommerceState.IDLE)
        return {
            "type": "text",
            "body": "Sorry, we couldn't initiate the payment right now. Please try again or contact us directly.",
        }

    if text in ("browse_more", "no", "back", "cancel"):
        _update_commerce_state(conversation, CommerceState.IDLE)
        return _show_catalog_menu(user, conversation)

    return {
        "type": "text",
        "body": "Reply 'yes' to confirm your purchase, or 'back' to keep browsing.",
    }


# ═════════════════════════════════════════════════════════════════════════════
# POST-PURCHASE
# ═════════════════════════════════════════════════════════════════════════════


def _handle_post_purchase(user, conversation, text: str) -> dict:
    """Handle post-purchase interactions (thank-you, cross-sell prompt)."""
    metadata = conversation.metadata or {}
    product_name = metadata.get("selected_product_name", "your item")

    if text in ("menu", "shop", "browse"):
        _update_commerce_state(conversation, CommerceState.IDLE)
        return _show_catalog_menu(user, conversation)

    _update_commerce_state(conversation, CommerceState.IDLE)

    return {
        "type": "text",
        "body": (
            f"Thank you for purchasing *{product_name}*! 🎉\n\n"
            f"Your order has been confirmed. The seller will arrange delivery.\n\n"
            f"Type 'menu' to browse more products."
        ),
    }


# ═════════════════════════════════════════════════════════════════════════════
# M-PESA PAYMENT HELPERS
# ═════════════════════════════════════════════════════════════════════════════


def _initiate_whatsapp_payment(user, product_id: str, phone: str, amount: Decimal):
    """
    Initiate an M-Pesa STK push for a WhatsApp commerce purchase.

    Returns a ``CommercePayment`` on success or ``None`` on failure.
    """
    try:
        from apps.billing.mpesa import format_phone_number, initiate_stk_push
        from apps.products.models import CommercePayment, Product

        product = Product.objects.get(pk=product_id, user=user)

        if product.tracks_stock and product.quantity is not None and product.quantity <= 0:
            return None

        formatted_phone = format_phone_number(phone)
        if not formatted_phone:
            return None

        transaction_ref = CommercePayment.build_transaction_ref(
            user.pk, product.pk, formatted_phone,
        )

        existing = CommercePayment.objects.filter(
            transaction_ref=transaction_ref,
            status=CommercePayment.Status.PENDING,
        ).first()
        if existing:
            return existing

        checkout_result = initiate_stk_push(
            phone_number=formatted_phone,
            amount=int(amount),
            account_reference=f"Kova-{str(product.pk)[:6]}",
            transaction_desc=f"Pay {product.name[:13]}",
        )

        if not checkout_result or not checkout_result.get("CheckoutRequestID"):
            return None

        payment = CommercePayment.objects.create(
            user=user,
            product=product,
            phone_number=formatted_phone,
            amount=amount,
            checkout_request_id=checkout_result["CheckoutRequestID"],
            merchant_request_id=checkout_result.get("MerchantRequestID", ""),
            transaction_ref=transaction_ref,
            source=CommercePayment.Source.WHATSAPP,
        )

        return payment

    except Exception:
        logger.exception("WhatsApp payment initiation failed for user=%s product=%s", user.pk, product_id)
        return None


def check_payment_and_notify(conversation) -> dict | None:
    """
    Check whether a pending payment has completed.

    Called when the buyer sends a follow-up message while in
    ``PAYMENT_PENDING`` state, or periodically from a Celery task.
    Returns a response dict for the buyer, or ``None`` if still pending.
    """
    metadata = conversation.metadata or {}
    payment_id = metadata.get("payment_id")
    if not payment_id:
        return None

    try:
        from apps.products.models import CommercePayment

        payment = CommercePayment.objects.get(pk=payment_id)

        if payment.status == CommercePayment.Status.COMPLETED:
            _update_commerce_state(conversation, CommerceState.PAYMENT_COMPLETE)
            _enrich_lead_after_purchase(conversation, payment)

            product_name = metadata.get("selected_product_name", "your item")
            return {
                "type": "text",
                "body": (
                    f"✅ *Payment confirmed!*\n\n"
                    f"Receipt: {payment.receipt_number}\n"
                    f"Item: {product_name}\n"
                    f"Amount: KES {payment.amount:,.0f}\n\n"
                    f"Thank you for your purchase! The seller has been notified.\n\n"
                    f"Type 'menu' to continue shopping."
                ),
            }

        if payment.status == CommercePayment.Status.FAILED:
            _update_commerce_state(conversation, CommerceState.IDLE)
            return {
                "type": "text",
                "body": "❌ Payment was not completed. Would you like to try again? Type 'buy' or 'menu' to browse.",
            }

        if payment.status == CommercePayment.Status.EXPIRED:
            _update_commerce_state(conversation, CommerceState.IDLE)
            return {
                "type": "text",
                "body": "⏰ Payment expired. Type 'buy' to try again or 'menu' to browse products.",
            }

        # Still pending — acknowledge the buyer.
        return {
            "type": "text",
            "body": "⏳ We're still waiting for the M-Pesa confirmation. Please check your phone and enter your PIN.",
        }

    except Exception:
        logger.exception("Payment check failed for conversation %s", conversation.pk)

    return None


# ═════════════════════════════════════════════════════════════════════════════
# LEAD ENRICHMENT
# ═════════════════════════════════════════════════════════════════════════════


def _enrich_lead_after_purchase(conversation, payment):
    """Enrich the lead record after a successful WhatsApp purchase."""
    try:
        from apps.leads.bridges import create_lead_from_commerce_payment
        create_lead_from_commerce_payment(payment)
    except Exception:
        logger.debug("Lead enrichment skipped for payment %s", payment.pk)


# ═════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT
# ═════════════════════════════════════════════════════════════════════════════


def _update_commerce_state(conversation, state: str, extra_data: dict | None = None):
    """Persist the commerce state (and optional extra keys) in conversation metadata."""
    metadata = conversation.metadata if conversation.metadata is not None else {}
    metadata["commerce_state"] = state
    if extra_data:
        metadata.update(extra_data)
    conversation.metadata = metadata
    conversation.save(update_fields=["metadata"])


# ═════════════════════════════════════════════════════════════════════════════
# WHATSAPP API RESPONSE FORMATTER
# ═════════════════════════════════════════════════════════════════════════════


def format_whatsapp_response(response: dict) -> dict:
    """
    Convert the internal response dict to a WhatsApp Cloud API message payload.

    Used by the webhook handler to send the actual message via
    ``POST /{phone-number-id}/messages``.
    """
    msg_type = response.get("type", "text")
    body = response.get("body", "")

    if msg_type == "text":
        return {
            "messaging_product": "whatsapp",
            "type": "text",
            "text": {"body": body},
        }

    if msg_type == "interactive_list":
        return {
            "messaging_product": "whatsapp",
            "type": "interactive",
            "interactive": {
                "type": "list",
                "body": {"text": body},
                "action": {
                    "button": response.get("button_text", "View Options"),
                    "sections": response.get("items", []),
                },
            },
        }

    if msg_type in ("interactive_buttons", "image_with_buttons"):
        buttons_raw = response.get("buttons", [])
        buttons = [
            {"type": "reply", "reply": {"id": b["id"], "title": b["title"]}}
            for b in buttons_raw[:3]
        ]

        interactive: dict = {
            "type": "button",
            "body": {"text": body},
            "action": {"buttons": buttons},
        }

        if msg_type == "image_with_buttons" and response.get("image_url"):
            interactive["header"] = {
                "type": "image",
                "image": {"link": response["image_url"]},
            }

        return {
            "messaging_product": "whatsapp",
            "type": "interactive",
            "interactive": interactive,
        }

    # Fallback — plain text.
    return {
        "messaging_product": "whatsapp",
        "type": "text",
        "text": {"body": body},
    }
