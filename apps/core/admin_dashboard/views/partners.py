"""
Admin dashboard views for the Growth Partners Program.
Overview, applications management, partners list, referrals, commissions.
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.admin_dashboard.decorators import senior_staff_required, staff_required
from apps.core.partners.models import (
    Commission,
    MarketplacePartner,
    MarketplaceSellerAccount,
    MilestoneAward,
    Partner,
    PartnerApplication,
    PayoutRequest,
    Referral,
    WebhookDeliveryLog,
    generate_api_key,
    generate_referral_code,
    hash_api_key,
)


@staff_required
def partners_overview(request):
    """Partners program overview — key metrics, applications, top partners."""
    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)
    thirty_days_ago = now - timedelta(days=30)

    # ── Key metrics ──────────────────────────────────────────────────────
    total_partners = Partner.objects.filter(is_active=True).count()
    total_applications = PartnerApplication.objects.count()
    pending_applications = PartnerApplication.objects.filter(status="pending").count()
    total_referrals = Referral.objects.count()
    active_referrals = Referral.objects.filter(is_active=True, activated_at__isnull=False).count()
    pending_referrals = Referral.objects.filter(is_active=True, activated_at__isnull=True).count()

    # Revenue metrics
    total_commissions_paid = Commission.objects.filter(
        status="paid",
    ).aggregate(total=Sum("amount_kes"))["total"] or Decimal("0.00")
    total_commissions_pending = Commission.objects.filter(
        status__in=["pending", "approved"],
    ).aggregate(total=Sum("amount_kes"))["total"] or Decimal("0.00")
    total_milestones_paid = MilestoneAward.objects.filter(
        paid=True,
    ).aggregate(total=Sum("bonus_kes"))["total"] or Decimal("0.00")

    # 7-day activity
    applications_7d = PartnerApplication.objects.filter(created_at__gte=seven_days_ago).count()
    referrals_7d = Referral.objects.filter(signed_up_at__gte=seven_days_ago).count()
    partners_7d = Partner.objects.filter(joined_at__gte=seven_days_ago).count()

    # ── Tier breakdown ───────────────────────────────────────────────────
    tier_breakdown = list(
        Partner.objects.filter(is_active=True)
        .values("tier")
        .annotate(count=Count("id"))
        .order_by("tier")
    )

    # ── Application status breakdown ─────────────────────────────────────
    app_breakdown = list(
        PartnerApplication.objects.values("status")
        .annotate(count=Count("id"))
        .order_by("status")
    )

    # ── Referral growth (30-day chart) ───────────────────────────────────
    daily_referrals = (
        Referral.objects.filter(signed_up_at__gte=thirty_days_ago)
        .annotate(date=TruncDate("signed_up_at"))
        .values("date")
        .annotate(count=Count("id"))
        .order_by("date")
    )
    chart_labels = [item["date"].strftime("%b %d") for item in daily_referrals]
    chart_data = [item["count"] for item in daily_referrals]

    # ── Top partners (by active referrals) ───────────────────────────────
    top_partners = (
        Partner.objects.filter(is_active=True)
        .annotate(
            ref_count=Count("referrals"),
            active_count=Count(
                "referrals",
                filter=Q(referrals__is_active=True, referrals__activated_at__isnull=False),
            ),
            total_earned=Sum("commissions__amount_kes", filter=Q(commissions__status="paid")),
        )
        .select_related("user")
        .order_by("-active_count")[:10]
    )

    # ── Recent applications ──────────────────────────────────────────────
    recent_applications = (
        PartnerApplication.objects.select_related("user")
        .order_by("-created_at")[:10]
    )

    # ── Recent referrals ─────────────────────────────────────────────────
    recent_referrals = (
        Referral.objects.select_related("partner__user", "referred_user")
        .order_by("-signed_up_at")[:10]
    )

    # ── Marketplace integrations ─────────────────────────────────────────
    active_marketplaces = MarketplacePartner.objects.filter(is_active=True).count()
    total_marketplaces = MarketplacePartner.objects.count()
    webhook_failed_7d = WebhookDeliveryLog.objects.filter(
        created_at__gte=seven_days_ago,
        status=WebhookDeliveryLog.Status.FAILED,
    ).count()
    webhook_success_7d = WebhookDeliveryLog.objects.filter(
        created_at__gte=seven_days_ago,
        status=WebhookDeliveryLog.Status.SUCCESS,
    ).count()
    recent_webhook_failures = (
        WebhookDeliveryLog.objects.filter(status=WebhookDeliveryLog.Status.FAILED)
        .select_related("marketplace")
        .order_by("-created_at")[:8]
    )
    from apps.core.partners.unimart_partner import resolve_unimart_partner

    unimart_mp = resolve_unimart_partner()

    context = {
        "page_title": "Growth Partners",
        # Key metrics
        "total_partners": total_partners,
        "total_applications": total_applications,
        "pending_applications": pending_applications,
        "total_referrals": total_referrals,
        "active_referrals": active_referrals,
        "pending_referrals": pending_referrals,
        "total_commissions_paid": total_commissions_paid,
        "total_commissions_pending": total_commissions_pending,
        "total_milestones_paid": total_milestones_paid,
        # 7d
        "applications_7d": applications_7d,
        "referrals_7d": referrals_7d,
        "partners_7d": partners_7d,
        # Breakdowns
        "tier_breakdown": tier_breakdown,
        "app_breakdown": app_breakdown,
        # Chart
        "chart_labels": json.dumps(chart_labels),
        "chart_data": json.dumps(chart_data),
        # Lists
        "top_partners": top_partners,
        "recent_applications": recent_applications,
        "recent_referrals": recent_referrals,
        # Marketplace
        "active_marketplaces": active_marketplaces,
        "total_marketplaces": total_marketplaces,
        "webhook_failed_7d": webhook_failed_7d,
        "webhook_success_7d": webhook_success_7d,
        "recent_webhook_failures": recent_webhook_failures,
        "unimart_mp": unimart_mp,
    }
    return render(request, "admin_dashboard/partners/overview.html", context)


@staff_required
def partners_webhook_logs(request):
    """Platform-wide marketplace webhook delivery log."""
    logs = WebhookDeliveryLog.objects.select_related("marketplace").order_by("-created_at")

    status_filter = request.GET.get("status")
    if status_filter in dict(WebhookDeliveryLog.Status.choices):
        logs = logs.filter(status=status_filter)

    marketplace_id = request.GET.get("marketplace")
    if marketplace_id:
        logs = logs.filter(marketplace_id=marketplace_id)

    event = request.GET.get("event", "").strip()
    if event:
        logs = logs.filter(event__icontains=event)

    paginator = Paginator(logs, 50)
    page = paginator.get_page(request.GET.get("page"))

    marketplaces = MarketplacePartner.objects.order_by("name")

    context = {
        "page_title": "Marketplace Webhook Logs",
        "logs": page,
        "status_choices": WebhookDeliveryLog.Status.choices,
        "current_status": status_filter,
        "current_marketplace": marketplace_id,
        "current_event": event,
        "marketplaces": marketplaces,
        "failed_7d": WebhookDeliveryLog.objects.filter(
            created_at__gte=timezone.now() - timedelta(days=7),
            status=WebhookDeliveryLog.Status.FAILED,
        ).count(),
    }
    return render(request, "admin_dashboard/partners/webhook_logs.html", context)


@staff_required
def application_list(request):
    """Paginated applications list with filters."""
    applications = PartnerApplication.objects.select_related("user").order_by("-created_at")

    status_filter = request.GET.get("status")
    search = request.GET.get("q", "").strip()

    if status_filter:
        applications = applications.filter(status=status_filter)
    if search:
        applications = applications.filter(
            Q(full_name__icontains=search) |
            Q(email__icontains=search) |
            Q(company__icontains=search)
        )

    paginator = Paginator(applications, 50)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page_title": "Partner Applications",
        "applications": page,
        "status_choices": PartnerApplication.Status.choices,
        "current_status": status_filter,
        "search": search,
        "pending_count": PartnerApplication.objects.filter(status="pending").count(),
    }
    return render(request, "admin_dashboard/partners/applications.html", context)


@senior_staff_required
@require_POST
def application_action(request):
    """Approve or reject a single application from the admin dashboard."""
    app_id = request.POST.get("application_id")
    action = request.POST.get("action")  # "approve" or "reject"
    reason = request.POST.get("reason", "").strip()

    application = get_object_or_404(PartnerApplication, pk=app_id)

    if action == "approve" and application.status == "pending":
        application.status = "approved"
        application.reviewed_at = timezone.now()
        application.save(update_fields=["status", "reviewed_at"])

        # Auto-create Partner if user linked
        if application.user and not Partner.objects.filter(user=application.user).exists():
            name = application.full_name or application.user.get_full_name()
            is_campus = application.application_type == PartnerApplication.ApplicationType.CAMPUS_REP
            partner = Partner.objects.create(
                user=application.user,
                application=application,
                referral_code=generate_referral_code(name),
                application_type=application.application_type,
                commission_rate=Decimal("0.20") if is_campus else Decimal("0.15"),
                tier=Partner.Tier.CONNECTOR if is_campus else Partner.Tier.STARTER,
            )
            try:
                from apps.messaging.emails.tasks import send_partner_app_approved_email
                send_partner_app_approved_email.delay(str(application.user.pk), partner.referral_code)
            except Exception:
                pass
        elif not application.user:
            # No Kova account yet — send email telling them to create one
            try:
                from apps.messaging.emails.tasks import send_partner_app_approved_no_account_email
                send_partner_app_approved_no_account_email.delay(
                    application.email,
                    application.full_name,
                )
            except Exception:
                pass

        return JsonResponse({"ok": True, "message": f"Application by {application.full_name} approved."})

    elif action == "reject" and application.status == "pending":
        application.status = "rejected"
        application.reviewed_at = timezone.now()
        if reason:
            application.admin_notes = reason
        application.save(update_fields=["status", "reviewed_at", "admin_notes"])

        try:
            from apps.messaging.emails.tasks import send_partner_app_rejected_email
            send_partner_app_rejected_email.delay(
                application.email,
                application.full_name,
                str(application.user.pk) if application.user else None,
                reason,
            )
        except Exception:
            pass

        return JsonResponse({"ok": True, "message": f"Application by {application.full_name} rejected."})

    return JsonResponse({"ok": False, "message": "Invalid action or application not pending."}, status=400)


@staff_required
def partner_list(request):
    """Paginated active partners list."""
    partners = (
        Partner.objects.annotate(
            ref_count=Count("referrals"),
            active_count=Count(
                "referrals",
                filter=Q(referrals__is_active=True, referrals__activated_at__isnull=False),
            ),
        )
        .select_related("user")
        .order_by("-joined_at")
    )

    tier_filter = request.GET.get("tier")
    search = request.GET.get("q", "").strip()

    if tier_filter:
        partners = partners.filter(tier=tier_filter)
    if search:
        partners = partners.filter(
            Q(user__email__icontains=search) |
            Q(referral_code__icontains=search) |
            Q(user__first_name__icontains=search) |
            Q(user__last_name__icontains=search)
        )

    paginator = Paginator(partners, 50)
    page = paginator.get_page(request.GET.get("page"))

    context = {
        "page_title": "Partners",
        "partners": page,
        "tier_choices": Partner.Tier.choices,
        "current_tier": tier_filter,
        "search": search,
    }
    return render(request, "admin_dashboard/partners/partners.html", context)


@staff_required
def partner_detail(request, pk):
    """Detailed view of a single partner — referrals, commissions, milestones."""
    partner = get_object_or_404(
        Partner.objects.select_related("user", "application"), pk=pk
    )
    referrals = partner.referrals.select_related("referred_user").order_by("-signed_up_at")[:50]
    commissions = partner.commissions.order_by("-period_start")[:20]
    milestones = partner.milestones.all()
    payout_requests = partner.payout_requests.order_by("-created_at")[:20]

    context = {
        "page_title": f"Partner: {partner.referral_code}",
        "partner": partner,
        "referrals": referrals,
        "commissions": commissions,
        "milestones": milestones,
        "payout_requests": payout_requests,
        "active_count": partner.active_referrals_count,
        "pending_count": partner.pending_referrals_count,
        "total_count": partner.total_referrals_count,
    }
    return render(request, "admin_dashboard/partners/detail.html", context)


@senior_staff_required
@require_POST
def partner_mark_commissions_paid(request, pk):
    """Mark selected (or all pending) commissions paid and adjust partner balances."""
    partner = get_object_or_404(Partner, pk=pk)
    commission_ids = request.POST.getlist("commission_ids")
    mark_all = request.POST.get("mark_all") == "1"

    qs = partner.commissions.filter(status__in=[Commission.Status.PENDING, Commission.Status.APPROVED])
    if not mark_all and commission_ids:
        qs = qs.filter(pk__in=commission_ids)
    elif not mark_all:
        messages.error(request, "Select commissions to pay or use Mark all pending.")
        return redirect("admin_dashboard:partner_detail", pk=pk)

    now = timezone.now()
    total = qs.aggregate(total=Sum("amount_kes"))["total"] or Decimal("0.00")
    updated = qs.update(status=Commission.Status.PAID, paid_at=now)

    if updated:
        partner.pending_payout_kes = max(Decimal("0.00"), partner.pending_payout_kes - total)
        partner.total_earned_kes += total
        partner.save(update_fields=["pending_payout_kes", "total_earned_kes"])
        messages.success(request, f"Marked {updated} commission(s) paid — KES {total:,.0f}.")
    else:
        messages.info(request, "No pending commissions to mark as paid.")

    return redirect("admin_dashboard:partner_detail", pk=pk)


@senior_staff_required
@require_POST
def partner_payout_action(request, pk, request_id):
    """Approve, mark paid, or reject a partner payout request."""
    partner = get_object_or_404(Partner, pk=pk)
    payout = get_object_or_404(PayoutRequest, pk=request_id, partner=partner)
    action = request.POST.get("action")
    now = timezone.now()

    if action == "approve" and payout.status == PayoutRequest.Status.PENDING:
        payout.status = PayoutRequest.Status.APPROVED
        payout.reviewed_at = now
        payout.save(update_fields=["status", "reviewed_at"])
        messages.success(request, f"Approved payout request for KES {payout.amount_kes:,.0f}.")
    elif action == "paid" and payout.status in (
        PayoutRequest.Status.PENDING, PayoutRequest.Status.APPROVED,
    ):
        payout.status = PayoutRequest.Status.PAID
        payout.reviewed_at = payout.reviewed_at or now
        payout.paid_at = now
        payout.save(update_fields=["status", "reviewed_at", "paid_at"])
        partner.pending_payout_kes = max(
            Decimal("0.00"), partner.pending_payout_kes - payout.amount_kes,
        )
        partner.total_earned_kes += payout.amount_kes
        partner.save(update_fields=["pending_payout_kes", "total_earned_kes"])
        messages.success(request, f"Marked payout KES {payout.amount_kes:,.0f} as paid.")
    elif action == "reject" and payout.status == PayoutRequest.Status.PENDING:
        payout.status = PayoutRequest.Status.REJECTED
        payout.reviewed_at = now
        payout.admin_notes = request.POST.get("reason", payout.admin_notes)
        payout.save(update_fields=["status", "reviewed_at", "admin_notes"])
        messages.info(request, "Payout request rejected.")
    else:
        messages.error(request, "Invalid payout action.")

    return redirect("admin_dashboard:partner_detail", pk=pk)


# ══════════════════════════════════════════════════════════════════════════════
# MARKETPLACE PARTNERS
# ══════════════════════════════════════════════════════════════════════════════

DEFAULT_WEBHOOK_EVENTS = [
    "seller.activated",
    "product.synced",
    "content.generated",
    "post.published",
]


def _parse_json_field(raw: str, field_name: str):
    raw = (raw or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, dict):
        raise ValueError(f"{field_name} must be a JSON object")
    return parsed


def _marketplace_integration_stats(mp):
    """Aggregate stats for admin marketplace dashboards."""
    from apps.create.content.models import Post
    from apps.commerce.products.models import Product

    seller_stats = mp.seller_accounts.aggregate(
        total_content=Sum("content_generated"),
        total_products=Sum("products_synced"),
    )
    products_qs = Product.objects.filter(marketplace_partner=mp, is_active=True)
    posts_published = Post.objects.filter(
        product__marketplace_partner=mp,
        status=Post.Status.PUBLISHED,
    ).count()

    return {
        "content_generated_total": seller_stats["total_content"] or 0,
        "seller_products_reported": seller_stats["total_products"] or 0,
        "products_active": products_qs.count(),
        "posts_published": posts_published,
        "webhook_configured": bool(mp.webhook_url),
        "webhook_events": mp.get_setting("webhook_events", DEFAULT_WEBHOOK_EVENTS),
        "max_products_per_seller": mp.get_setting("max_products_per_seller", 500),
    }


@staff_required
def marketplace_list(request):
    """List all marketplace partners with key stats."""
    marketplaces = (
        MarketplacePartner.objects.select_related("partner__user")
        .annotate(
            total_content=Sum("seller_accounts__content_generated"),
            active_sellers=Count("seller_accounts", filter=Q(seller_accounts__status="active")),
            products_count=Count(
                "synced_products",
                filter=Q(synced_products__is_active=True),
                distinct=True,
            ),
        )
        .order_by("-created_at")
    )

    totals = MarketplaceSellerAccount.objects.aggregate(
        content=Sum("content_generated"),
    )

    context = {
        "page_title": "Marketplace Partners",
        "marketplaces": marketplaces,
        "total_marketplaces": marketplaces.count(),
        "active_marketplaces": marketplaces.filter(is_active=True).count(),
        "total_content_generated": totals["content"] or 0,
        "default_webhook_events": DEFAULT_WEBHOOK_EVENTS,
    }
    return render(request, "admin_dashboard/partners/marketplace_list.html", context)


@staff_required
def marketplace_detail(request, pk):
    """Detailed view of a marketplace partner — sellers, products, stats, config."""
    from django.conf import settings

    mp = get_object_or_404(
        MarketplacePartner.objects.select_related("partner__user"), pk=pk
    )

    sellers = mp.seller_accounts.select_related("user").order_by("-provisioned_at")[:50]
    from apps.commerce.products.models import Product
    products_synced = Product.objects.filter(marketplace_partner=mp, is_active=True).count()

    seller_stats = mp.seller_accounts.values("status").annotate(count=Count("id"))
    seller_breakdown = {row["status"]: row["count"] for row in seller_stats}
    integration = _marketplace_integration_stats(mp)
    webhook_logs = mp.webhook_logs.order_by("-created_at")[:30]
    import_result = request.session.pop(f"marketplace_import_{mp.pk}", None)

    context = {
        "page_title": f"Marketplace: {mp.name}",
        "mp": mp,
        "sellers": sellers,
        "products_synced": products_synced,
        "seller_breakdown": seller_breakdown,
        "active_sellers": seller_breakdown.get("active", 0),
        "invited_sellers": seller_breakdown.get("invited", 0),
        "suspended_sellers": seller_breakdown.get("suspended", 0),
        "integration": integration,
        "site_url": getattr(settings, "SITE_URL", "").rstrip("/"),
        "product_field_mapping_json": json.dumps(mp.product_field_mapping or {}, indent=2),
        "seller_data_mapping_json": json.dumps(mp.seller_data_mapping or {}, indent=2),
        "webhook_events_json": json.dumps(integration["webhook_events"], indent=2),
        "sync_direction_choices": MarketplacePartner.SyncDirection.choices,
        "default_webhook_events": DEFAULT_WEBHOOK_EVENTS,
        "webhook_logs": webhook_logs,
        "import_result": import_result,
        "vendor_join_url": f"{getattr(settings, 'SITE_URL', '').rstrip('/')}/partners/{mp.slug}/join/",
    }
    return render(request, "admin_dashboard/partners/marketplace_detail.html", context)


@staff_required
def marketplace_import(request, pk):
    """Dedicated CSV vendor import page (visible entry point for file-based onboarding)."""
    from django.conf import settings

    mp = get_object_or_404(
        MarketplacePartner.objects.select_related("partner__user"), pk=pk
    )
    import_result = request.session.pop(f"marketplace_import_{mp.pk}", None)
    site_url = getattr(settings, "SITE_URL", "").rstrip("/")
    return render(request, "admin_dashboard/partners/marketplace_import.html", {
        "page_title": f"Import vendors: {mp.name}",
        "mp": mp,
        "import_result": import_result,
        "vendor_join_url": f"{site_url}/partners/{mp.slug}/join/",
    })


@senior_staff_required
@require_POST
def marketplace_import_sellers(request, pk):
    """Upload sellers CSV (and optional products CSV) for file-based onboarding."""
    mp = get_object_or_404(MarketplacePartner, pk=pk)
    sellers_file = request.FILES.get("sellers_csv")
    products_file = request.FILES.get("products_csv")
    redirect_to = request.POST.get("redirect_to", "detail")

    def _import_redirect():
        if redirect_to == "import":
            return redirect("admin_dashboard:marketplace_import", pk=mp.pk)
        return redirect("admin_dashboard:marketplace_detail", pk=mp.pk)

    if not sellers_file:
        messages.error(request, "Choose a sellers CSV file to upload.")
        return _import_redirect()

    from apps.core.partners.marketplace_csv_import import import_products_csv, import_sellers_csv

    seller_summary = import_sellers_csv(mp, sellers_file)
    s = seller_summary.to_dict()["summary"]
    msg_parts = [
        f"{s['provisioned']} provisioned",
        f"{s['already_exists']} already existed",
        f"{s['failed']} failed",
    ]
    if s["pending_added"]:
        msg_parts.append(f"{s['pending_added']} added to invite list")
    messages.success(request, f"Seller import complete: {', '.join(msg_parts)}.")

    for err in seller_summary.errors[:5]:
        messages.warning(request, err)

    if products_file:
        product_summary = import_products_csv(mp, products_file)
        p = product_summary.to_dict()["summary"]
        messages.success(
            request,
            f"Product import: {p['products_created']} created, "
            f"{p['products_updated']} updated, {p['failed']} failed.",
        )
        for err in product_summary.errors[:5]:
            messages.warning(request, err)

    request.session[f"marketplace_import_{mp.pk}"] = seller_summary.to_dict()
    return _import_redirect()


@senior_staff_required
@require_POST
def marketplace_update(request, pk):
    """Update marketplace partner configuration from admin dashboard."""
    mp = get_object_or_404(MarketplacePartner, pk=pk)

    try:
        settings_data = dict(mp.settings or {})
        if request.POST.get("max_products_per_seller"):
            settings_data["max_products_per_seller"] = int(request.POST["max_products_per_seller"])

        webhook_events_raw = request.POST.get("webhook_events_json", "").strip()
        if webhook_events_raw:
            events = json.loads(webhook_events_raw)
            if not isinstance(events, list):
                raise ValueError("Webhook events must be a JSON array")
            settings_data["webhook_events"] = events

        mp.name = request.POST.get("name", mp.name).strip()
        mp.contact_name = request.POST.get("contact_name", "").strip()
        mp.contact_email = request.POST.get("contact_email", "").strip()
        mp.website = request.POST.get("website", "").strip()
        mp.notes = request.POST.get("notes", "").strip()
        mp.seller_identity_field = request.POST.get("seller_identity_field", mp.seller_identity_field)
        mp.seller_default_plan = request.POST.get("seller_default_plan", mp.seller_default_plan)
        mp.sync_direction = request.POST.get("sync_direction", mp.sync_direction)
        mp.default_product_currency = request.POST.get("default_product_currency", mp.default_product_currency)
        mp.billing_model = request.POST.get("billing_model", mp.billing_model)
        mp.max_sellers = int(request.POST.get("max_sellers", mp.max_sellers))
        mp.webhook_url = request.POST.get("webhook_url", "").strip()
        mp.is_active = request.POST.get("is_active") == "on"
        mp.auto_activate_sellers = request.POST.get("auto_activate_sellers") == "on"
        mp.enforce_marketplace_cta = request.POST.get("enforce_marketplace_cta") == "on"
        mp.auto_snap_on_sync = request.POST.get("auto_snap_on_sync") == "on"
        mp.enrich_descriptions = request.POST.get("enrich_descriptions") == "on"
        mp.seller_welcome_email = request.POST.get("seller_welcome_email") == "on"
        mp.is_sandbox = request.POST.get("is_sandbox") == "on"
        mp.product_field_mapping = (
            _parse_json_field(
                request.POST.get("product_field_mapping_json", ""),
                "Product field mapping",
            )
            if request.POST.get("product_field_mapping_json", "").strip()
            else mp.product_field_mapping
        )
        mp.seller_data_mapping = (
            _parse_json_field(
                request.POST.get("seller_data_mapping_json", ""),
                "Seller data mapping",
            )
            if request.POST.get("seller_data_mapping_json", "").strip()
            else mp.seller_data_mapping
        )
        mp.settings = settings_data

        new_secret = request.POST.get("webhook_secret", "").strip()
        if new_secret:
            mp.webhook_secret = new_secret

        if mp.billing_model == "per_seller":
            mp.rate_per_seller_kes = Decimal(request.POST.get("rate_per_seller_kes", mp.rate_per_seller_kes))
        if mp.billing_model == "flat_fee":
            mp.flat_fee_kes = Decimal(request.POST.get("flat_fee_kes", mp.flat_fee_kes))

        mp.save()
        messages.success(request, f"Updated configuration for {mp.name}.")
    except (ValueError, json.JSONDecodeError) as exc:
        messages.error(request, str(exc))
    except Exception as exc:
        messages.error(request, f"Could not save marketplace settings: {exc}")

    return redirect("admin_dashboard:marketplace_detail", pk=mp.pk)


@senior_staff_required
def marketplace_create(request):
    """Create a new marketplace partner (generates API key)."""
    if request.method == "GET":
        partners = Partner.objects.filter(is_active=True).select_related("user")
        return render(request, "admin_dashboard/partners/marketplace_create.html", {
            "page_title": "Create Marketplace Partner",
            "partners": partners,
            "billing_models": MarketplacePartner.BillingModel.choices,
            "seller_identity_choices": MarketplacePartner.SellerIdentity.choices,
        })

    # POST — create the marketplace
    partner_id = request.POST.get("partner_id")
    partner = get_object_or_404(Partner, pk=partner_id)

    # Generate API key (show once)
    raw_key = generate_api_key()
    key_hash = hash_api_key(raw_key)
    key_prefix = raw_key[:8]

    mp = MarketplacePartner.objects.create(
        name=request.POST.get("name", "").strip(),
        slug=request.POST.get("slug", "").strip(),
        partner=partner,
        api_key_hash=key_hash,
        api_key_prefix=key_prefix,
        contact_email=request.POST.get("contact_email", "").strip(),
        contact_name=request.POST.get("contact_name", "").strip(),
        website=request.POST.get("website", "").strip() or "",
        seller_identity_field=request.POST.get("seller_identity_field", "email"),
        seller_default_plan=request.POST.get("seller_default_plan", "growth"),
        max_sellers=int(request.POST.get("max_sellers", 1000)),
        billing_model=request.POST.get("billing_model", "per_seller"),
        auto_activate_sellers=request.POST.get("auto_activate_sellers") == "on",
        enforce_marketplace_cta=request.POST.get("enforce_marketplace_cta") == "on",
        auto_snap_on_sync=request.POST.get("auto_snap_on_sync") == "on",
        enrich_descriptions=request.POST.get("enrich_descriptions") == "on",
        default_product_currency=request.POST.get("default_product_currency", "KES").strip() or "KES",
        webhook_url=request.POST.get("webhook_url", "").strip(),
        webhook_secret=request.POST.get("webhook_secret", "").strip(),
        settings={
            "max_products_per_seller": int(request.POST.get("max_products_per_seller", 500)),
            "webhook_events": DEFAULT_WEBHOOK_EVENTS,
        },
        notes=request.POST.get("notes", "").strip(),
    )

    # Show the raw API key ONE TIME
    return render(request, "admin_dashboard/partners/marketplace_created.html", {
        "page_title": f"Marketplace Created: {mp.name}",
        "mp": mp,
        "raw_api_key": raw_key,
    })


@staff_required
def partners_health(request):
    """Partner health slice — sync errors, webhook failures, content backlog."""
    seven_days_ago = timezone.now() - timedelta(days=7)
    stale_cutoff = timezone.now() - timedelta(days=2)

    webhook_failures_7d = WebhookDeliveryLog.objects.filter(
        status=WebhookDeliveryLog.Status.FAILED,
        created_at__gte=seven_days_ago,
    ).count()

    recent_failures = (
        WebhookDeliveryLog.objects.filter(status=WebhookDeliveryLog.Status.FAILED)
        .select_related("marketplace")
        .order_by("-created_at")[:15]
    )

    stale_sync_count = MarketplaceSellerAccount.objects.filter(
        status=MarketplaceSellerAccount.Status.ACTIVE,
    ).filter(
        Q(last_product_sync__isnull=True) | Q(last_product_sync__lt=stale_cutoff),
    ).count()

    zero_content_sellers = MarketplaceSellerAccount.objects.filter(
        status=MarketplaceSellerAccount.Status.ACTIVE,
        content_generated=0,
    ).count()

    active_marketplaces = MarketplacePartner.objects.filter(is_active=True).count()

    return render(request, "admin_dashboard/partners/health.html", {
        "page_title": "Partner health",
        "webhook_failures_7d": webhook_failures_7d,
        "recent_failures": recent_failures,
        "stale_sync_count": stale_sync_count,
        "zero_content_sellers": zero_content_sellers,
        "active_marketplaces": active_marketplaces,
    })
