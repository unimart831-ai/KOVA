"""Public Commerce Link pages — no login required."""

from __future__ import annotations

import logging
from decimal import Decimal
from urllib.parse import quote

from django.db import IntegrityError, transaction
from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from apps.products.commerce_links import (
    resolve_page_slug,
    resolve_public_product,
    resolve_public_shop,
)
from apps.products.commerce_reels import get_public_product_reel, get_public_shop_reels
from apps.products.commerce_seo import (
    brand_name,
    build_commerce_page_seo,
    build_shop_page_seo,
)
from apps.products.product_copy import format_product_description
from apps.products.product_cta import (
    primary_action_label_for,
    public_action_heading_for,
    resolve_direct_offer_action_url,
)

logger = logging.getLogger(__name__)


def _track_commerce_view(request, product, profile):
    try:
        from apps.analytics.models import Conversion

        Conversion.objects.create(
            user=product.user,
            product=product,
            conversion_type=Conversion.ConversionType.CLICK,
            event_name="commerce_link_view",
            metadata={
                "page_slug": profile.page_slug or "",
                "commerce_slug": product.commerce_slug,
                "referrer": request.META.get("HTTP_REFERER", "")[:500],
            },
        )
    except Exception:
        logger.exception("commerce link view tracking failed for product %s", product.pk)


def _whatsapp_url(profile, text: str) -> str:
    whatsapp = profile.cta_whatsapp or ""
    if not whatsapp:
        return ""
    return f"https://wa.me/{whatsapp}?text={quote(text)}"


def _product_description_paragraphs(product, profile, user) -> tuple[str, list[str]]:
    """Buyer-facing description blocks; fall back to stored copy on format errors."""
    try:
        description = format_product_description(
            product.description or "",
            product_name=product.name,
            brand=brand_name(profile, user),
            price=product.display_price or "",
        )
    except Exception:
        logger.exception("format_product_description failed for product %s", product.pk)
        description = (product.description or "").strip()
    paragraphs = [p.strip() for p in description.split("\n\n") if p.strip()]
    return description, paragraphs


@require_GET
def public_shop_index(request, page_slug):
    profile, products = resolve_public_shop(page_slug)
    if not profile or not products:
        raise Http404

    user = profile.user
    brand = brand_name(profile, user)
    wa_text = f"Hi! I'd like to browse your offers — {brand}."
    seo = build_shop_page_seo(request, profile, user, products)
    shop_reels = get_public_shop_reels(profile)
    from apps.teams.branding import get_commerce_branding

    commerce_branding = get_commerce_branding(user)
    if commerce_branding.get("custom_domain"):
        seo["canonical_url"] = f"https://{commerce_branding['custom_domain']}/shop/{resolve_page_slug(profile)}/"

    return render(request, "products/public/shop_index.html", {
        "profile": profile,
        "products": products,
        "user": user,
        "shop_slug": resolve_page_slug(profile),
        "brand_name": brand,
        "wa_url": _whatsapp_url(profile, wa_text),
        "shop_reels": shop_reels,
        "commerce_branding": commerce_branding,
        **seo,
    })


@require_GET
def public_commerce_link(request, page_slug, commerce_slug):
    profile, product = resolve_public_product(page_slug, commerce_slug)
    if not product:
        raise Http404

    _track_commerce_view(request, product, profile)

    user = product.user
    brand = brand_name(profile, user)
    whatsapp = profile.cta_whatsapp or ""
    wa_text = (
        f"Hi! I'm interested in {product.name}"
        f"{f' ({product.display_price})' if product.display_price else ''} "
        f"from your Kova offer page."
    )
    wa_url = _whatsapp_url(profile, wa_text)

    from apps.billing.models import get_user_plan_limits

    seller_limits = get_user_plan_limits(user)
    mpesa_commerce_enabled = bool(seller_limits.get("mpesa_commerce"))
    mpesa_available = bool(
        product.offering_type == product.OfferingType.PRODUCT
        and
        mpesa_commerce_enabled
        and product.price
        and product.currency == "KES"
        and product.stock_status != product.StockStatus.OUT_OF_STOCK
    )
    primary_action_url = resolve_direct_offer_action_url(product, request)
    primary_action_label = primary_action_label_for(product) if primary_action_url else ""

    shop_slug = resolve_page_slug(profile)
    seo = build_commerce_page_seo(
        request,
        product,
        profile,
        user,
        mpesa_available=mpesa_available,
        whatsapp_available=bool(whatsapp),
    )
    product_reel = get_public_product_reel(product)
    product_description, product_description_paragraphs = _product_description_paragraphs(
        product, profile, user,
    )

    return render(request, "products/public/commerce_link.html", {
        "profile": profile,
        "product": product,
        "product_description": product_description,
        "product_description_paragraphs": product_description_paragraphs,
        "user": user,
        "shop_slug": shop_slug,
        "brand_name": brand,
        "whatsapp": whatsapp,
        "wa_url": wa_url,
        "mpesa_available": mpesa_available,
        "action_heading": public_action_heading_for(product),
        "primary_action_url": primary_action_url,
        "primary_action_label": primary_action_label,
        "primary_action_external": primary_action_url.startswith(("http://", "https://")) if primary_action_url else False,
        "product_reel": product_reel,
        **seo,
    })


@csrf_exempt
@ratelimit(key="ip", rate="5/m", method="POST", block=True)
@require_POST
def public_commerce_pay(request, page_slug, commerce_slug):
    """Initiate M-Pesa STK push for a product on a public commerce link."""
    profile, product = resolve_public_product(page_slug, commerce_slug)
    if not product:
        raise Http404

    if product.offering_type != product.OfferingType.PRODUCT:
        return JsonResponse(
            {"error": "Direct M-Pesa checkout is not enabled for this offer yet. Use the booking or access link instead."},
            status=400,
        )

    if not product.price or product.currency != "KES":
        return JsonResponse({"error": "M-Pesa pay is only available for KES-priced items."}, status=400)

    from apps.billing.models import get_user_plan_limits

    if not get_user_plan_limits(product.user).get("mpesa_commerce"):
        return JsonResponse(
            {"error": "This shop has not enabled M-Pesa checkout on their plan."},
            status=403,
        )

    phone = (request.POST.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"error": "Phone number is required."}, status=400)

    from django.conf import settings as django_settings

    from apps.billing.mpesa import format_phone_number, initiate_stk_push
    from apps.products.models import CommercePayment, Product

    try:
        formatted_phone = format_phone_number(phone)
    except ValueError:
        return JsonResponse({"error": "Use format 07XXXXXXXX or 254XXXXXXXXX."}, status=400)

    amount = int(Decimal(product.price))
    if amount < 1:
        return JsonResponse({"error": "Invalid product price."}, status=400)

    # ── Idempotency: reject duplicate STK push within the same 5-min window ──
    txn_ref = CommercePayment.build_transaction_ref(
        product.user_id, product.pk, formatted_phone,
    )
    existing = CommercePayment.objects.filter(
        transaction_ref=txn_ref,
        status__in=[CommercePayment.Status.PENDING, CommercePayment.Status.COMPLETED],
    ).first()
    if existing:
        if existing.status == CommercePayment.Status.COMPLETED:
            return JsonResponse({
                "error": "This payment has already been completed.",
                "payment_id": str(existing.pk),
            }, status=409)
        existing.attempts_count = (existing.attempts_count or 1) + 1
        existing.save(update_fields=["attempts_count"])
        return JsonResponse({
            "ok": True,
            "message": "A payment is already in progress. Check your phone for the M-Pesa prompt.",
            "checkout_id": existing.checkout_request_id,
            "payment_id": str(existing.pk),
        })

    # ── Race-safe stock check: lock the product row + verify quantity ──
    with transaction.atomic():
        locked_product = (
            Product.objects.select_for_update().get(pk=product.pk)
        )
        if locked_product.stock_status == Product.StockStatus.OUT_OF_STOCK:
            return JsonResponse({"error": "This item is out of stock."}, status=400)
        if locked_product.tracks_stock and locked_product.quantity is not None and locked_product.quantity < 1:
            locked_product.stock_status = Product.StockStatus.OUT_OF_STOCK
            locked_product.save(update_fields=["stock_status"])
            return JsonResponse({"error": "This item is out of stock."}, status=400)

    ref_suffix = str(product.pk).replace("-", "")[:8]
    account_ref = f"KOVA{ref_suffix}"[:12]

    commerce_callback_url = (
        getattr(django_settings, "MPESA_COMMERCE_CALLBACK_URL", "")
        or django_settings.MPESA_CALLBACK_URL
    )

    try:
        result = initiate_stk_push(
            phone_number=formatted_phone,
            amount=amount,
            account_reference=account_ref,
            transaction_desc=product.name[:13],
            callback_url=commerce_callback_url,
        )
    except (ConnectionError, ValueError) as exc:
        logger.error("Commerce STK failed for product %s: %s", product.pk, exc)
        return JsonResponse({"error": "M-Pesa is temporarily unavailable. Try WhatsApp instead."}, status=503)

    checkout_id = result.get("CheckoutRequestID", "")
    try:
        payment = CommercePayment.objects.create(
            user=product.user,
            product=product,
            transaction_ref=txn_ref,
            checkout_request_id=checkout_id,
            merchant_request_id=result.get("MerchantRequestID", ""),
            phone_number=formatted_phone,
            amount=product.price,
            currency=product.currency,
            source=CommercePayment.Source.COMMERCE_LINK,
        )
    except IntegrityError:
        dup = CommercePayment.objects.filter(transaction_ref=txn_ref).first()
        return JsonResponse({
            "ok": True,
            "message": "Check your phone and enter your M-Pesa PIN to complete payment.",
            "checkout_id": dup.checkout_request_id if dup else checkout_id,
            "payment_id": str(dup.pk) if dup else "",
        })

    return JsonResponse({
        "ok": True,
        "message": "Check your phone and enter your M-Pesa PIN to complete payment.",
        "checkout_id": checkout_id,
        "payment_id": str(payment.pk),
    })


@csrf_exempt
@require_GET
def commerce_payment_status(request, payment_id):
    """JSON endpoint for polling payment status from the buyer's browser."""
    from apps.products.models import CommercePayment

    try:
        import uuid as _uuid
        _uuid.UUID(str(payment_id))
    except (ValueError, AttributeError):
        return JsonResponse({"error": "Invalid payment ID."}, status=400)

    payment = (
        CommercePayment.objects
        .filter(pk=payment_id)
        .select_related("product")
        .first()
    )
    if not payment:
        return JsonResponse({"error": "Payment not found."}, status=404)

    data = {
        "status": payment.status,
        "amount": str(payment.amount),
        "currency": payment.currency,
    }
    if payment.status == CommercePayment.Status.COMPLETED:
        data["receipt_number"] = payment.receipt_number
        data["completed_at"] = payment.completed_at.isoformat() if payment.completed_at else ""
        if payment.product:
            data["product_name"] = payment.product.name
    elif payment.status == CommercePayment.Status.FAILED:
        data["result_desc"] = payment.result_desc or "Payment was not completed."
    return JsonResponse(data)
