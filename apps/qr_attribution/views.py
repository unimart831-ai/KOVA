"""Views for the QR / Walk-in attribution surface (Phase 2 W5-6).

Public:
  scan_landing      GET  /qr/<token>/                  — anyone with the QR
  cashier_view      GET  /walkin/<slug>/               — cashier UI per business
  cashier_record    POST /walkin/<slug>/record/        — store the walk-in

User-authenticated:
  qr_list           GET  /qr/                          — list user's QR codes
  qr_create         GET/POST /qr/new/                  — create new QR
  qr_detail         GET  /qr/<id>/                     — single QR stats
  qr_edit           GET/POST /qr/<id>/edit/            — edit
  qr_delete         POST /qr/<id>/delete/              — soft-delete
  qr_print_pdf      GET  /qr/<id>/print/               — download print pack
  cashier_link      GET  /walkin/                      — show the user their
                                                          cashier URL
"""
from __future__ import annotations

import hashlib

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Sum, Count
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django_ratelimit.decorators import ratelimit

from apps.qr_attribution.models import QRCode, QRScan, WalkInEvent


# ── Visitor identification helpers ──────────────────────────────────────────


def _get_or_set_visitor_id(request, response=None):
    """Read visitor_id cookie or mint a new one. Cookie set in landing
    page response so a subsequent walk-in can be matched."""
    import uuid as _uuid
    visitor_id = request.COOKIES.get("kova_visitor_id")
    if not visitor_id:
        visitor_id = _uuid.uuid4().hex
    return visitor_id


def _ip_hash(request):
    """SHA-256 of the source IP. We never store raw IPs — only for
    dedup the same scan within a short window."""
    ip = (request.META.get("HTTP_X_FORWARDED_FOR", "").split(",")[0].strip()
          or request.META.get("REMOTE_ADDR", ""))
    if not ip:
        return ""
    return hashlib.sha256(ip.encode()).hexdigest()[:32]


# ── Public scan landing ─────────────────────────────────────────────────────


@ratelimit(key="ip", rate="60/m", method="GET", block=True)
@require_GET
def scan_landing(request, token):
    """Public page the customer lands on when they scan the QR."""
    qr = get_object_or_404(QRCode, token=token, is_active=True)

    visitor_id = _get_or_set_visitor_id(request)
    QRScan.objects.create(
        qr_code=qr,
        visitor_id=visitor_id,
        user_agent=request.META.get("HTTP_USER_AGENT", "")[:300],
        ip_hash=_ip_hash(request),
    )

    template_name = f"qr_attribution/landing/{qr.landing_template}.html"
    profile = getattr(qr.user, "profile", None)
    context = {
        "qr": qr,
        "payload": qr.landing_payload or {},
        "brand_name": (profile.company_name if profile else "") or qr.user.full_name or "",
        "brand_logo": (profile.brand_logo_url if profile else ""),
    }
    response = render(request, template_name, context)
    response.set_cookie(
        "kova_visitor_id", visitor_id,
        max_age=60 * 60 * 24 * 30,  # 30 days
        httponly=True, samesite="Lax",
    )
    return response


# ── User-side QR management ─────────────────────────────────────────────────


@login_required
def qr_list(request):
    """All QR codes the user owns + summary stats."""
    qrs = (
        QRCode.objects.filter(user=request.user)
        .annotate(scan_count=Count("scans"), walkin_count=Count("walk_ins"))
        .order_by("-created_at")
    )
    totals = WalkInEvent.objects.filter(user=request.user).aggregate(
        total_walkins=Count("id"),
        total_revenue=Sum("revenue"),
    )
    return render(request, "qr_attribution/list.html", {
        "qrs": qrs,
        "totals": totals,
        "page_title": "QR Codes & Walk-ins",
    })


@login_required
def qr_create(request):
    """Create a new QR code."""
    if request.method == "POST":
        label = (request.POST.get("label") or "").strip()
        if not label:
            messages.error(request, "Give your QR code a name (e.g., \"Jamhuri flyer\").")
            return redirect("qr_attribution:create")

        template = (request.POST.get("landing_template") or "discount").strip()
        if template not in dict(QRCode.LandingTemplate.choices):
            template = QRCode.LandingTemplate.DISCOUNT

        # Build landing_payload from the relevant form fields
        payload = {}
        if template == "discount":
            payload = {
                "discount_pct": int(request.POST.get("discount_pct", 10) or 10),
                "valid_until": request.POST.get("valid_until", "").strip(),
                "terms": request.POST.get("terms", "").strip()[:300],
            }
        elif template == "menu":
            payload = {
                "menu_image_url": request.POST.get("menu_image_url", "").strip(),
                "today_special": request.POST.get("today_special", "").strip()[:200],
            }
        elif template == "booking":
            payload = {
                "booking_link": request.POST.get("booking_link", "").strip(),
                "contact_whatsapp": request.POST.get("contact_whatsapp", "").strip(),
            }
        elif template == "follow":
            payload = {
                "instagram_handle": request.POST.get("instagram_handle", "").strip(),
                "facebook_url": request.POST.get("facebook_url", "").strip(),
            }
        else:  # custom
            payload = {
                "headline": request.POST.get("headline", "").strip()[:120],
                "body": request.POST.get("body", "").strip()[:500],
                "cta_text": request.POST.get("cta_text", "").strip()[:40],
                "cta_url": request.POST.get("cta_url", "").strip(),
            }

        # Optional campaign / post linkage
        campaign_id = request.POST.get("campaign_id") or None
        post_id = request.POST.get("post_id") or None

        qr = QRCode.objects.create(
            user=request.user,
            label=label,
            landing_template=template,
            landing_payload=payload,
            campaign_id=campaign_id if campaign_id else None,
            post_id=post_id if post_id else None,
        )
        messages.success(request, f"Created QR code: {qr.label}")
        return redirect("qr_attribution:detail", pk=qr.pk)

    # GET
    from apps.campaigns.models import Campaign
    from apps.content.models import Post
    campaigns = Campaign.objects.filter(user=request.user).order_by("-created_at")[:25]
    posts = Post.objects.filter(
        user=request.user, status="published",
    ).order_by("-published_at")[:25]
    return render(request, "qr_attribution/create.html", {
        "campaigns": campaigns,
        "posts": posts,
        "templates": QRCode.LandingTemplate.choices,
        "page_title": "Create QR Code",
    })


@login_required
def qr_detail(request, pk):
    """Stats for a single QR code."""
    qr = get_object_or_404(QRCode, pk=pk, user=request.user)
    scans = qr.scans.order_by("-scanned_at")[:50]
    walkins = qr.walk_ins.order_by("-recorded_at")[:50]
    totals = qr.walk_ins.aggregate(
        revenue=Sum("revenue"),
        count=Count("id"),
    )
    scan_count = qr.scans.count()
    conversion_rate = (
        round(100 * (totals["count"] or 0) / scan_count, 1)
        if scan_count else 0
    )
    public_url = request.build_absolute_uri(
        reverse("qr_attribution:scan_landing", kwargs={"token": qr.token})
    )
    return render(request, "qr_attribution/detail.html", {
        "qr": qr,
        "scans": scans,
        "walkins": walkins,
        "scan_count": scan_count,
        "walkin_count": totals["count"] or 0,
        "revenue_total": totals["revenue"] or 0,
        "conversion_rate": conversion_rate,
        "public_url": public_url,
        "page_title": qr.label,
    })


@login_required
@require_POST
def qr_delete(request, pk):
    """Soft-delete: mark inactive so scans + walk-ins are preserved."""
    qr = get_object_or_404(QRCode, pk=pk, user=request.user)
    qr.is_active = False
    qr.save(update_fields=["is_active", "updated_at"])
    messages.success(request, f"Archived QR code: {qr.label}")
    return redirect("qr_attribution:list")


@login_required
def qr_edit(request, pk):
    """Edit an existing QR code's label, template, and payload."""
    qr = get_object_or_404(QRCode, pk=pk, user=request.user)

    if request.method == "POST":
        label = (request.POST.get("label") or "").strip()
        if not label:
            messages.error(request, "Label cannot be empty.")
            return redirect("qr_attribution:edit", pk=pk)

        template = (request.POST.get("landing_template") or qr.landing_template).strip()
        if template not in dict(QRCode.LandingTemplate.choices):
            template = qr.landing_template

        payload = {}
        if template == "discount":
            payload = {
                "discount_pct": int(request.POST.get("discount_pct", 10) or 10),
                "valid_until": request.POST.get("valid_until", "").strip(),
                "terms": request.POST.get("terms", "").strip()[:300],
            }
        elif template == "menu":
            payload = {
                "menu_image_url": request.POST.get("menu_image_url", "").strip(),
                "today_special": request.POST.get("today_special", "").strip()[:200],
            }
        elif template == "booking":
            payload = {
                "booking_link": request.POST.get("booking_link", "").strip(),
                "contact_whatsapp": request.POST.get("contact_whatsapp", "").strip(),
            }
        elif template == "follow":
            payload = {
                "instagram_handle": request.POST.get("instagram_handle", "").strip(),
                "facebook_url": request.POST.get("facebook_url", "").strip(),
            }
        else:  # custom
            payload = {
                "headline": request.POST.get("headline", "").strip()[:120],
                "body": request.POST.get("body", "").strip()[:500],
                "cta_text": request.POST.get("cta_text", "").strip()[:40],
                "cta_url": request.POST.get("cta_url", "").strip(),
            }

        qr.label = label
        qr.landing_template = template
        qr.landing_payload = payload
        qr.save(update_fields=["label", "landing_template", "landing_payload", "updated_at"])
        messages.success(request, f"Updated QR code: {qr.label}")
        return redirect("qr_attribution:detail", pk=qr.pk)

    return render(request, "qr_attribution/edit.html", {
        "qr": qr,
        "templates": QRCode.LandingTemplate.choices,
        "page_title": f"Edit — {qr.label}",
    })


@login_required
def qr_print_pdf(request, pk):
    """Generate the print-pack PDF (3 sticker formats per QR)."""
    qr = get_object_or_404(QRCode, pk=pk, user=request.user)
    from apps.qr_attribution.pdf import generate_print_pack
    public_url = request.build_absolute_uri(
        reverse("qr_attribution:scan_landing", kwargs={"token": qr.token})
    )
    pdf_bytes = generate_print_pack(qr, public_url)
    response = HttpResponse(pdf_bytes, content_type="application/pdf")
    response["Content-Disposition"] = (
        f'attachment; filename="kova-qr-{qr.token}.pdf"'
    )
    return response


# ── Cashier UI ──────────────────────────────────────────────────────────────


@login_required
def cashier_link(request):
    """Show the user their per-business cashier URL so they can open
    it on the salon's phone / tablet / iPad."""
    # The cashier URL uses the user's username as the slug (already
    # unique). For Agency teams we'd issue a separate token; v2 keeps
    # it simple.
    cashier_url = request.build_absolute_uri(
        reverse("qr_attribution:cashier_view", kwargs={"slug": request.user.username})
    )
    return render(request, "qr_attribution/cashier_link.html", {
        "cashier_url": cashier_url,
        "page_title": "Cashier UI",
    })


@require_GET
def cashier_view(request, slug):
    """The phone-friendly button grid for staff to tap walk-in source."""
    from apps.accounts.models import User
    cashier_user = get_object_or_404(User, username=slug, is_active=True)
    return render(request, "qr_attribution/cashier.html", {
        "cashier_user": cashier_user,
        "sources": WalkInEvent.AttributionSource.choices,
        "page_title": f"Walk-ins · {cashier_user.full_name or cashier_user.username}",
    })


@csrf_exempt
@ratelimit(key="ip", rate="30/m", method="POST", block=True)
@require_POST
def cashier_record(request, slug):
    """POST endpoint the cashier UI hits to record a walk-in.

    CSRF-exempt because the cashier UI is unauthenticated (the URL slug
    IS the auth). To prevent abuse we rate-limit per IP via
    django-ratelimit elsewhere, and the slug must match a real user.
    """
    from apps.accounts.models import User
    cashier_user = get_object_or_404(User, username=slug, is_active=True)

    source = (request.POST.get("source") or "other").strip().lower()
    if source not in dict(WalkInEvent.AttributionSource.choices):
        source = WalkInEvent.AttributionSource.OTHER

    label = (request.POST.get("label") or "").strip()[:80]
    customer_name = (request.POST.get("customer_name") or "").strip()[:200]
    customer_phone = (request.POST.get("customer_phone") or "").strip()[:20]
    revenue_raw = (request.POST.get("revenue") or "").strip()
    try:
        revenue = float(revenue_raw) if revenue_raw else None
    except ValueError:
        revenue = None

    # Try to tie back to a recent scan (last 30 min) by visitor_id cookie
    scan = None
    qr_code = None
    visitor_id = request.COOKIES.get("kova_visitor_id")
    if visitor_id:
        from datetime import timedelta
        scan = (
            QRScan.objects
            .filter(
                qr_code__user=cashier_user,
                visitor_id=visitor_id,
                scanned_at__gte=timezone.now() - timedelta(minutes=30),
            )
            .order_by("-scanned_at")
            .first()
        )
        if scan:
            qr_code = scan.qr_code

    walkin = WalkInEvent.objects.create(
        user=cashier_user,
        scan=scan,
        qr_code=qr_code,
        attribution_source=source,
        attribution_label=label,
        customer_name=customer_name,
        customer_phone=customer_phone,
        revenue=revenue,
    )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({"ok": True, "walkin_id": str(walkin.id)})
    return redirect(reverse("qr_attribution:cashier_view", kwargs={"slug": slug}))
