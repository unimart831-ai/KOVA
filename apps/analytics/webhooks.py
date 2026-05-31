"""
Webhook receivers for external revenue sources.

Shopify: orders/create webhook → auto-creates Conversion records.
M-Pesa: commerce payment callback → auto-creates Conversion records.
"""

import hashlib
import hmac
import json
import logging
from decimal import Decimal

from django.conf import settings
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

logger = logging.getLogger(__name__)


# ─── Shopify Webhook ─────────────────────────────────────────────────────────


def _verify_shopify_hmac(body: bytes, hmac_header: str, secret: str) -> bool:
    """Verify Shopify webhook HMAC-SHA256 signature."""
    if not hmac_header or not secret:
        return False
    computed = hmac.new(
        secret.encode("utf-8"), body, hashlib.sha256
    ).digest()
    import base64
    expected = base64.b64encode(computed).decode("utf-8")
    return hmac.compare_digest(expected, hmac_header)


def _shopify_webhook_secret(store) -> str:
    """Per-store secret or app client secret for OAuth-installed stores."""
    if store.webhook_secret:
        return store.webhook_secret
    return getattr(settings, "SHOPIFY_API_SECRET", "")


def _get_shopify_store(shop_domain: str):
    from apps.analytics.models import ShopifyStore

    return ShopifyStore.objects.select_related("user").get(
        shop_domain=shop_domain, is_active=True,
    )


@csrf_exempt
@require_POST
def shopify_order_webhook(request):
    """
    Receive Shopify orders/create webhook.
    Auto-creates Conversion records with revenue attribution via UTM params.

    Shopify sends:
    - X-Shopify-Hmac-Sha256: HMAC signature
    - X-Shopify-Shop-Domain: myshop.myshopify.com
    - X-Shopify-Topic: orders/create
    """
    from apps.analytics.models import Conversion, ShopifyStore

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    body = request.body

    if not shop_domain:
        return HttpResponseBadRequest("Missing shop domain")

    # Find the store
    try:
        store = _get_shopify_store(shop_domain)
    except ShopifyStore.DoesNotExist:
        logger.warning("Shopify webhook from unknown store: %s", shop_domain)
        return HttpResponseForbidden("Unknown store")

    # Verify HMAC
    secret = _shopify_webhook_secret(store)
    if secret and not _verify_shopify_hmac(body, hmac_header, secret):
        logger.warning("Shopify HMAC verification failed for %s", shop_domain)
        return HttpResponseForbidden("Invalid signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    order_id = data.get("id")
    total_price = Decimal(str(data.get("total_price", "0")))
    currency = data.get("currency", "USD")

    # Extract UTM from landing_site or referring_site
    utm_source = ""
    utm_medium = ""
    utm_campaign = ""
    utm_content = ""

    landing_site = data.get("landing_site", "") or ""
    referring_site = data.get("referring_site", "") or ""

    # Parse UTM from landing site URL
    if landing_site:
        from urllib.parse import urlparse, parse_qs
        parsed = parse_qs(urlparse(landing_site).query)
        utm_source = parsed.get("utm_source", [""])[0]
        utm_medium = parsed.get("utm_medium", [""])[0]
        utm_campaign = parsed.get("utm_campaign", [""])[0]
        utm_content = parsed.get("utm_content", [""])[0]

    # Try to match post via utm_content (contains post ID)
    post = None
    if utm_content:
        from apps.content.models import Post
        post = Post.objects.filter(
            user=store.user,
            pk__startswith=utm_content,
        ).first()

    # Try to match product from line items
    product = None
    line_items = data.get("line_items", [])
    if line_items:
        product_title = line_items[0].get("title", "")
        if product_title:
            from apps.products.models import Product
            product = Product.objects.filter(
                user=store.user, name__iexact=product_title, is_active=True,
            ).first()

    # Deduplicate: don't create conversion if order_id already exists
    if Conversion.objects.filter(
        user=store.user, event_name=f"shopify_order_{order_id}",
    ).exists():
        return HttpResponse("OK (duplicate)", status=200)

    conversion = Conversion.objects.create(
        user=store.user,
        post=post,
        product=product,
        conversion_type=Conversion.ConversionType.SALE,
        revenue=total_price,
        event_name=f"shopify_order_{order_id}",
        utm_source=utm_source,
        utm_medium=utm_medium,
        utm_campaign=utm_campaign,
        utm_content=utm_content,
        metadata={
            "source": "shopify",
            "shop_domain": shop_domain,
            "order_id": order_id,
            "currency": currency,
            "line_items": [
                {"title": li.get("title", ""), "quantity": li.get("quantity", 0), "price": li.get("price", "0")}
                for li in line_items[:10]
            ],
            "customer_email": data.get("email", ""),
            "referring_site": referring_site,
        },
    )

    # Update store stats
    store.orders_tracked += 1
    store.total_revenue += total_price
    store.last_order_at = timezone.now()
    store.save(update_fields=["orders_tracked", "total_revenue", "last_order_at", "updated_at"])

    logger.info(
        "Shopify order %s tracked: %s %s → conversion %s (post=%s)",
        order_id, total_price, currency, conversion.pk, post.pk if post else "none",
    )
    return HttpResponse("OK", status=200)


@csrf_exempt
@require_POST
def shopify_product_webhook(request):
    """
    Receive Shopify products/create and products/update webhooks.
    Upserts Kova Product by external_id (Shopify product id).
    """
    from apps.products.shopify_import import upsert_shopify_product

    shop_domain = request.headers.get("X-Shopify-Shop-Domain", "")
    hmac_header = request.headers.get("X-Shopify-Hmac-Sha256", "")
    topic = request.headers.get("X-Shopify-Topic", "")
    body = request.body

    if not shop_domain:
        return HttpResponseBadRequest("Missing shop domain")

    try:
        store = _get_shopify_store(shop_domain)
    except ShopifyStore.DoesNotExist:
        logger.warning("Shopify product webhook from unknown store: %s", shop_domain)
        return HttpResponseForbidden("Unknown store")

    secret = _shopify_webhook_secret(store)
    if secret and not _verify_shopify_hmac(body, hmac_header, secret):
        logger.warning("Shopify product HMAC failed for %s", shop_domain)
        return HttpResponseForbidden("Invalid signature")

    try:
        data = json.loads(body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    try:
        _, action = upsert_shopify_product(store, data)
        logger.info(
            "Shopify product webhook %s for %s: %s (id=%s)",
            topic, shop_domain, action or "skipped", data.get("id"),
        )
    except Exception:
        logger.exception("Shopify product webhook upsert failed for %s", shop_domain)
        return HttpResponse("Error", status=500)

    return HttpResponse("OK", status=200)


# ─── M-Pesa Commerce Webhook ─────────────────────────────────────────────────


@csrf_exempt
@require_POST
def mpesa_commerce_callback(request):
    """
    Receive M-Pesa commerce payment callbacks.
    Similar to billing callback, but for product sales (not subscriptions).

    Users embed a tracking reference in the M-Pesa payment description
    containing a post ID or product name. Format: "KOVA_{post_id_prefix}"
    """
    from apps.analytics.models import Conversion

    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return HttpResponseBadRequest("Invalid JSON")

    # Daraja callback structure
    body = data.get("Body", {}).get("stkCallback", {})
    result_code = body.get("ResultCode")
    checkout_id = body.get("CheckoutRequestID", "")

    if result_code != 0:
        if checkout_id:
            from apps.products.models import CommercePayment
            CommercePayment.objects.filter(
                checkout_request_id=checkout_id,
                status=CommercePayment.Status.PENDING,
            ).update(
                status=CommercePayment.Status.FAILED,
                result_code=result_code,
                result_desc=body.get("ResultDesc", ""),
            )
        return HttpResponse("OK", status=200)

    callback_metadata = body.get("CallbackMetadata", {}).get("Item", [])
    meta = {item["Name"]: item.get("Value") for item in callback_metadata}

    amount = Decimal(str(meta.get("Amount", 0)))
    receipt = meta.get("MpesaReceiptNumber", "")
    phone = str(meta.get("PhoneNumber", ""))

    if not receipt or not amount:
        return HttpResponse("OK", status=200)

    # Product commerce payments (Commerce Links / WhatsApp)
    from apps.products.models import CommercePayment
    from django.utils import timezone as tz

    commerce_payment = CommercePayment.objects.filter(
        checkout_request_id=checkout_id,
    ).select_related("product", "user").first()
    if commerce_payment:
        if commerce_payment.status == CommercePayment.Status.COMPLETED:
            return HttpResponse("OK (duplicate)", status=200)

        from django.db import transaction as db_transaction
        from django.db.models import F

        with db_transaction.atomic():
            commerce_payment.status = CommercePayment.Status.COMPLETED
            commerce_payment.receipt_number = receipt
            commerce_payment.result_code = result_code
            commerce_payment.completed_at = tz.now()
            commerce_payment.save(update_fields=[
                "status", "receipt_number", "result_code", "completed_at",
            ])

            # Atomically decrement stock on the product
            product = commerce_payment.product
            if product and product.tracks_stock and product.quantity is not None:
                from apps.products.models import Product
                updated = Product.objects.filter(
                    pk=product.pk, quantity__gte=1,
                ).update(quantity=F("quantity") - 1)
                if updated:
                    product.refresh_from_db()
                    if product.quantity <= 0:
                        product.stock_status = Product.StockStatus.OUT_OF_STOCK
                        product.save(update_fields=["stock_status"])
                    elif product.quantity <= product.low_stock_threshold:
                        product.stock_status = Product.StockStatus.LOW_STOCK
                        product.save(update_fields=["stock_status"])

        Conversion.objects.create(
            user=commerce_payment.user,
            product=commerce_payment.product,
            conversion_type=Conversion.ConversionType.SALE,
            revenue=amount,
            event_name=f"mpesa_{receipt}",
            metadata={
                "source": commerce_payment.source,
                "receipt_number": receipt,
                "phone_last4": phone[-4:],
                "checkout_request_id": checkout_id,
                "product_id": str(commerce_payment.product_id) if commerce_payment.product_id else "",
            },
        )

        try:
            from apps.leads.bridges import create_lead_from_commerce_payment
            create_lead_from_commerce_payment(commerce_payment)
        except Exception:
            logger.exception("Failed to create lead from commerce payment %s", commerce_payment.pk)

        if phone:
            try:
                from apps.whatsapp.services import send_commerce_payment_receipt
                send_commerce_payment_receipt(
                    commerce_payment, phone=phone, receipt=receipt, amount=amount,
                )
            except Exception:
                logger.exception("WhatsApp commerce receipt failed for %s", checkout_id)

        logger.info(
            "M-Pesa commerce payment tracked: %s KES %s product=%s",
            receipt, amount, commerce_payment.product_id,
        )
        return HttpResponse("OK", status=200)

    # Find user by phone number match
    from apps.accounts.models import User
    from apps.billing.models import MpesaPayment

    # Check if this is a Kova subscription payment (skip — handled by billing)
    if MpesaPayment.objects.filter(receipt_number=receipt).exists():
        return HttpResponse("OK (subscription)", status=200)

    # Try to find user by phone (stored in profile)
    user = None
    try:
        from apps.accounts.models import UserProfile
        profile = UserProfile.objects.filter(phone_number__endswith=phone[-9:]).first()
        if profile:
            user = profile.user
    except Exception:
        logger.exception("mpesa-commerce webhook: phone lookup failed for ...%s", phone[-4:])

    if not user:
        logger.info("M-Pesa commerce payment %s: no matching user for phone %s", receipt, phone[-4:])
        return HttpResponse("OK", status=200)

    # Deduplicate
    if Conversion.objects.filter(user=user, event_name=f"mpesa_{receipt}").exists():
        return HttpResponse("OK (duplicate)", status=200)

    Conversion.objects.create(
        user=user,
        conversion_type=Conversion.ConversionType.SALE,
        revenue=amount,
        event_name=f"mpesa_{receipt}",
        metadata={
            "source": "mpesa",
            "receipt_number": receipt,
            "phone_last4": phone[-4:],
        },
    )

    logger.info("M-Pesa commerce payment tracked: %s KES %s for user %s", receipt, amount, user.pk)
    return HttpResponse("OK", status=200)
