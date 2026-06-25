from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django_ratelimit.decorators import ratelimit

from .forms import MarketplaceVendorJoinForm, PartnerApplicationForm
from .models import (
    COMMISSION_TIERS,
    MILESTONE_BONUSES,
    PROFIT_SHARE_TIERS,
    Partner,
    PartnerApplication,
    PayoutRequest,
)


# ── Article Registry ──────────────────────────────────────────────────────────

ARTICLES = [
    {
        "slug": "how-it-works",
        "title": "How the Growth Partners Program Works",
        "description": "A complete guide to earning recurring commissions by referring clients to Kova Agent.",
        "icon": "🔄",
        "color": "kova",
        "order": 1,
    },
    {
        "slug": "commission-tiers",
        "title": "Commission Tiers Explained",
        "description": "Understand how your commission rate grows from 15% to 30% as you bring more clients.",
        "icon": "📈",
        "color": "blue",
        "order": 2,
    },
    {
        "slug": "milestone-bonuses",
        "title": "Milestone Bonuses & Rewards",
        "description": "One-time cash bonuses at 10, 25, 50, 100, and 250 active clients.",
        "icon": "🏆",
        "color": "amber",
        "order": 3,
    },
    {
        "slug": "profit-sharing",
        "title": "Profit Sharing for Elite Partners",
        "description": "How top partners earn 1–3% of Kova's quarterly net profits.",
        "icon": "💎",
        "color": "purple",
        "order": 4,
    },
    {
        "slug": "getting-started",
        "title": "Getting Started as a Partner",
        "description": "Step-by-step guide from application to your first commission payout.",
        "icon": "🚀",
        "color": "green",
        "order": 5,
    },
    {
        "slug": "faq",
        "title": "Frequently Asked Questions",
        "description": "Answers to common questions about referrals, payouts, and program rules.",
        "icon": "❓",
        "color": "rose",
        "order": 6,
    },
]

_ARTICLE_MAP = {a["slug"]: a for a in ARTICLES}


# ── Public Views (no login required) ─────────────────────────────────────────


def partners_landing(request):
    """Main Growth Partners Program landing page."""
    context = {
        "commission_tiers": [
            {"range": "1–25 clients", "rate": "15%", "example": "KES 4,875/mo"},
            {"range": "26–75 clients", "rate": "20%", "example": "KES 13,000/mo"},
            {"range": "76–150 clients", "rate": "25%", "example": "KES 32,500/mo"},
            {"range": "150+ clients", "rate": "30%", "example": "KES 58,500/mo"},
        ],
        "milestones": [
            {"clients": m[0], "bonus": f"KES {m[1]:,}", "label": m[2], "extras": m[3]}
            for m in MILESTONE_BONUSES
        ],
        "articles": ARTICLES,
    }
    return render(request, "partners/landing.html", context)


def partners_article(request, slug):
    """Individual article/explainer page."""
    article = _ARTICLE_MAP.get(slug)
    if not article:
        from django.http import Http404
        raise Http404("Article not found")

    # Find prev/next for navigation
    idx = next(i for i, a in enumerate(ARTICLES) if a["slug"] == slug)
    prev_article = ARTICLES[idx - 1] if idx > 0 else None
    next_article = ARTICLES[idx + 1] if idx < len(ARTICLES) - 1 else None

    context = {
        "article": article,
        "articles": ARTICLES,
        "prev_article": prev_article,
        "next_article": next_article,
        "commission_tiers": COMMISSION_TIERS,
        "milestones": MILESTONE_BONUSES,
        "profit_tiers": PROFIT_SHARE_TIERS,
    }
    return render(request, f"partners/articles/{slug}.html", context)


@ratelimit(key="ip", rate="5/m", method="POST", block=True)
def partners_apply(request):
    """Application form for the Growth Partners Program."""
    campus_track = request.GET.get("track", "").strip().lower() == "campus"
    # If already applied, show status
    if request.user.is_authenticated:
        existing = PartnerApplication.objects.filter(user=request.user).first()
        if existing:
            return render(request, "partners/apply_status.html", {"application": existing})
        # If already a partner, redirect to dashboard
        if hasattr(request.user, "partner_profile"):
            return redirect("partners:dashboard")

    if request.method == "POST":
        form = PartnerApplicationForm(request.POST)
        if form.is_valid():
            application = form.save(commit=False)
            if request.user.is_authenticated:
                application.user = request.user
            if campus_track or request.POST.get("application_type") == "campus_rep":
                application.application_type = PartnerApplication.ApplicationType.CAMPUS_REP
            application.save()

            # Send confirmation email (async)
            try:
                from apps.emails.tasks import send_partner_app_received_email
                send_partner_app_received_email.delay(
                    application.email,
                    application.full_name,
                    str(request.user.pk) if request.user.is_authenticated else None,
                )
            except Exception:
                pass  # Don't block submission if email fails

            messages.success(
                request,
                "Application submitted! We'll review it within 48 hours.",
            )
            return render(request, "partners/apply_success.html", {"application": application})
    else:
        initial = {}
        if request.user.is_authenticated:
            initial["email"] = request.user.email
            initial["full_name"] = request.user.get_full_name()
        form = PartnerApplicationForm(initial=initial)

    return render(request, "partners/apply.html", {
        "form": form,
        "campus_track": campus_track,
    })


# ── Authenticated Partner Dashboard ──────────────────────────────────────────


@login_required
def partner_dashboard(request):
    """Partner's dashboard with stats, referrals, earnings."""
    try:
        partner = request.user.partner_profile
    except Partner.DoesNotExist:
        # Not a partner yet — check for application
        application = PartnerApplication.objects.filter(user=request.user).first()
        if application:
            return render(request, "partners/apply_status.html", {"application": application})
        return redirect("partners:apply")

    referrals = partner.referrals.select_related("referred_user").order_by("-signed_up_at")[:20]
    recent_commissions = partner.commissions.order_by("-period_start")[:10]
    milestones = partner.milestones.all()
    payout_requests = partner.payout_requests.order_by("-created_at")[:10]
    click_count = partner.clicks.count()

    context = {
        "partner": partner,
        "referrals": referrals,
        "recent_commissions": recent_commissions,
        "milestones": milestones,
        "payout_requests": payout_requests,
        "click_count": click_count,
        "referral_short_url": request.build_absolute_uri(
            reverse("referral_redirect", kwargs={"referral_code": partner.referral_code})
        ),
        "min_payout_kes": PayoutRequest.MIN_AMOUNT_KES,
        "next_milestone": partner.next_milestone,
        "active_count": partner.active_referrals_count,
        "pending_count": partner.pending_referrals_count,
        "total_count": partner.total_referrals_count,
    }
    return render(request, "partners/dashboard.html", context)


def referral_redirect(request, referral_code):
    """
    GET /r/<referral_code>/ — log click, set kova_ref cookie, redirect to signup with UTMs.
    """
    from django.conf import settings

    from .middleware import ReferralMiddleware
    from .models import Partner, ReferralClick

    code = referral_code.strip().upper()
    partner = Partner.objects.filter(referral_code__iexact=code, is_active=True).first()

    ReferralClick.objects.create(
        partner=partner,
        referral_code=code,
        ip_address=request.META.get("REMOTE_ADDR"),
        user_agent=(request.META.get("HTTP_USER_AGENT") or "")[:500],
        landing_path=request.path,
    )

    params = urlencode({
        "ref": code,
        "utm_source": "partner",
        "utm_medium": "referral",
        "utm_campaign": code,
    })
    signup_url = f"{reverse('account_signup')}?{params}"
    response = redirect(signup_url)

    if not request.COOKIES.get(ReferralMiddleware.COOKIE_NAME):
        response.set_cookie(
            ReferralMiddleware.COOKIE_NAME,
            code,
            max_age=ReferralMiddleware.COOKIE_MAX_AGE,
            httponly=True,
            samesite="Lax",
            secure=not settings.DEBUG,
        )
    return response


@login_required
def partner_payout_request(request):
    """Partner self-service M-Pesa payout request."""
    from decimal import Decimal, InvalidOperation

    from .models import PayoutRequest

    try:
        partner = request.user.partner_profile
    except Partner.DoesNotExist:
        return redirect("partners:apply")

    if request.method == "POST":
        mpesa = request.POST.get("mpesa_number", "").strip()
        amount_raw = request.POST.get("amount_kes", "").strip()

        try:
            amount = Decimal(amount_raw)
        except (InvalidOperation, ValueError):
            messages.error(request, "Enter a valid payout amount.")
            return redirect("partners:dashboard")

        if amount < PayoutRequest.MIN_AMOUNT_KES:
            messages.error(request, f"Minimum payout is KES {PayoutRequest.MIN_AMOUNT_KES:.0f}.")
            return redirect("partners:dashboard")

        if amount > partner.pending_payout_kes:
            messages.error(request, "Amount exceeds your pending payout balance.")
            return redirect("partners:dashboard")

        if not mpesa:
            messages.error(request, "M-Pesa number is required.")
            return redirect("partners:dashboard")

        PayoutRequest.objects.create(
            partner=partner,
            amount_kes=amount,
            mpesa_number=mpesa,
        )
        messages.success(request, "Payout request submitted. We process requests by the 15th.")
        return redirect("partners:dashboard")

    return redirect("partners:dashboard")


@login_required
def partner_assets(request):
    """Partner marketing asset kit and referral link generator."""
    try:
        partner = request.user.partner_profile
    except Partner.DoesNotExist:
        return redirect("partners:apply")

    short_url = request.build_absolute_uri(
        reverse("referral_redirect", kwargs={"referral_code": partner.referral_code})
    )
    return render(request, "partners/assets.html", {
        "partner": partner,
        "referral_short_url": short_url,
        "click_count": partner.clicks.count(),
    })


@ratelimit(key="ip", rate="10/m", block=True)
def marketplace_vendor_join(request, slug):
    """
    Self-serve vendor signup for a marketplace partner (e.g. UNIMART).

    UNIMART shares: /partners/unimart/join/?usk=USK-00123
    """
    from django.shortcuts import get_object_or_404

    from apps.partners.marketplace_csv_import import provision_vendor_self_serve
    from apps.partners.models import MarketplacePartner

    mp = get_object_or_404(MarketplacePartner, slug=slug, is_active=True)
    initial = {}
    usk_query = request.GET.get("usk", "").strip()
    if usk_query:
        initial["external_seller_id"] = usk_query

    if request.method == "POST":
        form = MarketplaceVendorJoinForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            response, _status = provision_vendor_self_serve(
                mp,
                external_seller_id=data["external_seller_id"],
                full_name=data["full_name"],
                email=data["email"],
                business_name=data["business_name"],
                business_url=data.get("business_url") or "",
            )
            if response.get("status") in ("provisioned", "already_exists"):
                if response.get("approval_required"):
                    messages.success(
                        request,
                        "Application received! UNIMART will approve your Kova account shortly. "
                        "Watch your email for next steps.",
                    )
                else:
                    messages.success(
                        request,
                        "You're on Kova! Check your email to set your password and connect social accounts.",
                    )
                return render(request, "partners/marketplace_join_success.html", {
                    "marketplace": mp,
                    "result": response,
                })
            if response.get("error"):
                form.add_error(None, response["error"])
    else:
        form = MarketplaceVendorJoinForm(initial=initial)

    return render(request, "partners/marketplace_join.html", {
        "form": form,
        "marketplace": mp,
    })
