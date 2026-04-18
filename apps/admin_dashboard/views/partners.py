"""
Admin dashboard views for the Growth Partners Program.
Overview, applications management, partners list, referrals, commissions.
"""

import json
from datetime import timedelta
from decimal import Decimal

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.db.models.functions import TruncDate
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.admin_dashboard.decorators import senior_staff_required, staff_required
from apps.partners.models import (
    Commission,
    MarketplacePartner,
    MarketplaceSellerAccount,
    MilestoneAward,
    Partner,
    PartnerApplication,
    Referral,
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
    }
    return render(request, "admin_dashboard/partners/overview.html", context)


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
            partner = Partner.objects.create(
                user=application.user,
                application=application,
                referral_code=generate_referral_code(name),
            )
            try:
                from apps.emails.tasks import send_partner_app_approved_email
                send_partner_app_approved_email.delay(str(application.user.pk), partner.referral_code)
            except Exception:
                pass
        elif not application.user:
            # No Kova account yet — send email telling them to create one
            try:
                from apps.emails.tasks import send_partner_app_approved_no_account_email
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
            from apps.emails.tasks import send_partner_app_rejected_email
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

    context = {
        "page_title": f"Partner: {partner.referral_code}",
        "partner": partner,
        "referrals": referrals,
        "commissions": commissions,
        "milestones": milestones,
        "active_count": partner.active_referrals_count,
        "pending_count": partner.pending_referrals_count,
        "total_count": partner.total_referrals_count,
    }
    return render(request, "admin_dashboard/partners/detail.html", context)


# ══════════════════════════════════════════════════════════════════════════════
# MARKETPLACE PARTNERS
# ══════════════════════════════════════════════════════════════════════════════


@staff_required
def marketplace_list(request):
    """List all marketplace partners with key stats."""
    marketplaces = MarketplacePartner.objects.select_related("partner__user").order_by("-created_at")

    context = {
        "page_title": "Marketplace Partners",
        "marketplaces": marketplaces,
        "total_marketplaces": marketplaces.count(),
        "active_marketplaces": marketplaces.filter(is_active=True).count(),
    }
    return render(request, "admin_dashboard/partners/marketplace_list.html", context)


@staff_required
def marketplace_detail(request, pk):
    """Detailed view of a marketplace partner — sellers, products, stats."""
    mp = get_object_or_404(
        MarketplacePartner.objects.select_related("partner__user"), pk=pk
    )

    sellers = mp.seller_accounts.select_related("user").order_by("-provisioned_at")[:50]
    from apps.products.models import Product
    products_synced = Product.objects.filter(marketplace_partner=mp, is_active=True).count()

    # Seller status breakdown
    seller_stats = mp.seller_accounts.values("status").annotate(count=Count("id"))
    seller_breakdown = {row["status"]: row["count"] for row in seller_stats}

    context = {
        "page_title": f"Marketplace: {mp.name}",
        "mp": mp,
        "sellers": sellers,
        "products_synced": products_synced,
        "seller_breakdown": seller_breakdown,
        "active_sellers": seller_breakdown.get("active", 0),
        "invited_sellers": seller_breakdown.get("invited", 0),
        "suspended_sellers": seller_breakdown.get("suspended", 0),
    }
    return render(request, "admin_dashboard/partners/marketplace_detail.html", context)


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
        notes=request.POST.get("notes", "").strip(),
    )

    # Show the raw API key ONE TIME
    return render(request, "admin_dashboard/partners/marketplace_created.html", {
        "page_title": f"Marketplace Created: {mp.name}",
        "mp": mp,
        "raw_api_key": raw_key,
    })
