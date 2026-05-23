"""Public Commerce Link pages — no login required."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.http import Http404, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from apps.products.commerce_links import resolve_public_product

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


@require_GET
def public_commerce_link(request, page_slug, commerce_slug):
    profile, product = resolve_public_product(page_slug, commerce_slug)
    if not product:
        raise Http404

    _track_commerce_view(request, product, profile)

    user = product.user
    whatsapp = profile.cta_whatsapp or ""
    wa_text = (
        f"Hi! I'm interested in {product.name}"
        f"{f' ({product.display_price})' if product.display_price else ''} "
        f"from your shop link."
    )
    from urllib.parse import quote

    wa_url = f"https://wa.me/{whatsapp}?text={quote(wa_text)}" if whatsapp else ""

    mpesa_available = bool(
        product.price
        and product.currency == "KES"
        and product.stock_status != product.StockStatus.OUT_OF_STOCK
    )

    from apps.products.commerce_links import resolve_page_slug

    shop_slug = resolve_page_slug(profile)

    return render(request, "products/public/commerce_link.html", {
        "profile": profile,
        "product": product,
        "user": user,
        "shop_slug": shop_slug,
        "brand_name": profile.company_name or user.full_name or "Shop",
        "whatsapp": whatsapp,
        "wa_url": wa_url,
        "mpesa_available": mpesa_available,
        "page_title": product.name,
    })


@csrf_exempt
@ratelimit(key="ip", rate="5/m", method="POST", block=True)
@require_POST
def public_commerce_pay(request, page_slug, commerce_slug):
    """Initiate M-Pesa STK push for a product on a public commerce link."""
    profile, product = resolve_public_product(page_slug, commerce_slug)
    if not product:
        raise Http404

    if not product.price or product.currency != "KES":
        return JsonResponse({"error": "M-Pesa pay is only available for KES-priced items."}, status=400)

    if product.stock_status == product.StockStatus.OUT_OF_STOCK:
        return JsonResponse({"error": "This item is out of stock."}, status=400)

    phone = (request.POST.get("phone") or "").strip()
    if not phone:
        return JsonResponse({"error": "Phone number is required."}, status=400)

    from apps.billing.mpesa import format_phone_number, initiate_stk_push
    from apps.products.models import CommercePayment

    try:
        formatted_phone = format_phone_number(phone)
    except ValueError:
        return JsonResponse({"error": "Use format 07XXXXXXXX or 254XXXXXXXXX."}, status=400)

    amount = int(Decimal(product.price))
    if amount < 1:
        return JsonResponse({"error": "Invalid product price."}, status=400)

    ref_suffix = str(product.pk).replace("-", "")[:8]
    account_ref = f"KOVA{ref_suffix}"[:12]

    try:
        result = initiate_stk_push(
            phone_number=formatted_phone,
            amount=amount,
            account_reference=account_ref,
            transaction_desc=product.name[:13],
        )
    except (ConnectionError, ValueError) as exc:
        logger.error("Commerce STK failed for product %s: %s", product.pk, exc)
        return JsonResponse({"error": "M-Pesa is temporarily unavailable. Try WhatsApp instead."}, status=503)

    checkout_id = result.get("CheckoutRequestID", "")
    CommercePayment.objects.create(
        user=product.user,
        product=product,
        checkout_request_id=checkout_id,
        merchant_request_id=result.get("MerchantRequestID", ""),
        phone_number=formatted_phone,
        amount=product.price,
        currency=product.currency,
        source=CommercePayment.Source.COMMERCE_LINK,
    )

    return JsonResponse({
        "ok": True,
        "message": "Check your phone and enter your M-Pesa PIN to complete payment.",
        "checkout_id": checkout_id,
    })
