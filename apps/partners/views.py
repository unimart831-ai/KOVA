from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .forms import PartnerApplicationForm
from .models import (
    COMMISSION_TIERS,
    MILESTONE_BONUSES,
    PROFIT_SHARE_TIERS,
    Partner,
    PartnerApplication,
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
            {"range": "1–25 clients", "rate": "15%", "example": "KES 1,875/mo"},
            {"range": "26–75 clients", "rate": "20%", "example": "KES 7,500/mo"},
            {"range": "76–150 clients", "rate": "25%", "example": "KES 18,750/mo"},
            {"range": "150+ clients", "rate": "30%", "example": "KES 30,000/mo"},
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
        "prev_article": prev_article,
        "next_article": next_article,
        "commission_tiers": COMMISSION_TIERS,
        "milestones": MILESTONE_BONUSES,
        "profit_tiers": PROFIT_SHARE_TIERS,
    }
    return render(request, f"partners/articles/{slug}.html", context)


def partners_apply(request):
    """Application form for the Growth Partners Program."""
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
            application.save()
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

    return render(request, "partners/apply.html", {"form": form})


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

    context = {
        "partner": partner,
        "referrals": referrals,
        "recent_commissions": recent_commissions,
        "milestones": milestones,
        "next_milestone": partner.next_milestone,
        "active_count": partner.active_referrals_count,
        "pending_count": partner.pending_referrals_count,
        "total_count": partner.total_referrals_count,
    }
    return render(request, "partners/dashboard.html", context)
