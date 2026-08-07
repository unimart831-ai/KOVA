import csv
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.core.accounts.models import User, UserProfile
from apps.core.accounts.segments import get_mode_label, infer_business_mode
from apps.core.admin_dashboard.decorators import senior_staff_required, staff_required, superuser_required


def _user_mode_payload(user):
    connected_platforms = [account.platform for account in user.social_accounts.all() if account.is_active]
    mode = infer_business_mode(user.profile, connected_platforms)
    return {
        "key": mode,
        "label": get_mode_label(mode),
    }


@staff_required
def user_list(request):
    """User management list with search, filter, sort."""
    qs = User.objects.select_related("profile").prefetch_related("social_accounts").all()

    # ── Search ───────────────────────────────────────────────────────────
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(email__icontains=search) |
            Q(full_name__icontains=search) |
            Q(phone_number__icontains=search) |
            Q(profile__company_name__icontains=search)
        )

    # ── Filters ──────────────────────────────────────────────────────────
    plan = request.GET.get("plan", "")
    if plan:
        qs = qs.filter(profile__plan=plan)

    status = request.GET.get("status", "")
    if status:
        qs = qs.filter(profile__subscription_status=status)

    industry = request.GET.get("industry", "")
    if industry:
        qs = qs.filter(profile__industry=industry)

    onboarded = request.GET.get("onboarded", "")
    if onboarded == "yes":
        qs = qs.filter(onboarding_completed=True)
    elif onboarded == "no":
        qs = qs.filter(onboarding_completed=False)

    phone_filter = request.GET.get("phone", "")
    if phone_filter == "yes":
        qs = qs.exclude(phone_number="")
    elif phone_filter == "no":
        qs = qs.filter(Q(phone_number="") | Q(phone_number__isnull=True))

    staff_filter = request.GET.get("is_staff", "")
    if staff_filter == "yes":
        qs = qs.filter(is_staff=True)
    elif staff_filter == "no":
        qs = qs.filter(is_staff=False)

    # ── Annotate ─────────────────────────────────────────────────────────
    qs = qs.annotate(
        post_count=Count("posts", distinct=True),
        platform_count=Count("social_accounts", filter=Q(social_accounts__is_active=True), distinct=True),
        offer_count=Count("products", filter=Q(products__is_active=True), distinct=True),
        service_offer_count=Count(
            "products",
            filter=Q(products__is_active=True, products__offering_type="service"),
            distinct=True,
        ),
        digital_offer_count=Count(
            "products",
            filter=Q(products__is_active=True, products__offering_type="digital"),
            distinct=True,
        ),
        service_ready_count=Count(
            "products",
            filter=Q(products__is_active=True, products__offering_type="service")
            & (Q(products__booking_link__isnull=False) | Q(products__fulfillment_url__gt="")),
            distinct=True,
        ),
        digital_ready_count=Count(
            "products",
            filter=Q(products__is_active=True, products__offering_type="digital")
            & (Q(products__fulfillment_url__gt="") | Q(products__product_url__gt="")),
            distinct=True,
        ),
    )

    # ── Sort ─────────────────────────────────────────────────────────────
    sort = request.GET.get("sort", "-date_joined")
    valid_sorts = {
        "date_joined", "-date_joined", "email", "-email",
        "full_name", "-full_name", "post_count", "-post_count",
    }
    if sort not in valid_sorts:
        sort = "-date_joined"
    qs = qs.order_by(sort)

    # ── Pagination ───────────────────────────────────────────────────────
    paginator = Paginator(qs, 25)
    page = paginator.get_page(request.GET.get("page", 1))
    for user in page.object_list:
        user.admin_business_mode = _user_mode_payload(user)

    context = {
        "page_title": "User Management",
        "page_obj": page,
        "search": search,
        "current_plan": plan,
        "current_status": status,
        "current_industry": industry,
        "current_onboarded": onboarded,
        "current_phone": phone_filter,
        "current_staff": staff_filter,
        "current_sort": sort,
        "total_count": paginator.count,
        "plan_choices": UserProfile.PlanTier.choices,
        "industry_choices": UserProfile.Industry.choices,
        "status_choices": [
            ("active", "Active"), ("trialing", "Trialing"),
            ("past_due", "Past Due"), ("canceled", "Canceled"), ("none", "None"),
        ],
    }
    return render(request, "admin_dashboard/users/list.html", context)


@staff_required
def user_usage_detail(request, pk):
    """Kova plan monthly usage — dedicated admin page."""
    user = get_object_or_404(
        User.objects.select_related("profile").prefetch_related("social_accounts"),
        pk=pk,
    )
    from apps.core.admin_dashboard.user_usage import get_admin_user_usage

    return render(request, "admin_dashboard/users/usage.html", {
        "page_title": f"Usage: {user.full_name or user.email}",
        "target_user": user,
        "profile": user.profile,
        "usage": get_admin_user_usage(user),
        "business_mode": _user_mode_payload(user),
    })


@staff_required
def user_detail(request, pk):
    """Full user detail with tabs: profile, usage, content, platforms, agents, billing, engagement, briefs."""
    from apps.create.agents.models import AgentAction, AgentConfig
    from apps.insight.analytics.models import PostMetric
    from apps.core.billing.models import MpesaPayment
    from apps.create.briefs.models import DailyBrief
    from apps.create.content.models import ContentSeed, MarketingCampaign, Post
    from apps.create.content.models import VoiceBrief
    from apps.messaging.engage.models import Interaction, Superfan
    from apps.core.platforms.models import SocialAccount
    from apps.commerce.products.models import Product

    user = get_object_or_404(
        User.objects.select_related("profile").prefetch_related("social_accounts"),
        pk=pk,
    )
    now = timezone.now()
    tab = request.GET.get("tab", "profile")
    business_mode = _user_mode_payload(user)
    active_platforms = SocialAccount.objects.filter(user=user, is_active=True).order_by("platform")
    offer_qs = Product.objects.filter(user=user, is_active=True)
    offer_counts = {
        "total": offer_qs.count(),
        "physical": offer_qs.filter(offering_type=Product.OfferingType.PRODUCT).count(),
        "service": offer_qs.filter(offering_type=Product.OfferingType.SERVICE).count(),
        "digital": offer_qs.filter(offering_type=Product.OfferingType.DIGITAL).count(),
    }
    fulfillment_counts = {
        "service_ready": offer_qs.filter(
            offering_type=Product.OfferingType.SERVICE,
        ).filter(
            Q(booking_link__isnull=False) | Q(fulfillment_url__gt=""),
        ).count(),
        "digital_ready": offer_qs.filter(
            offering_type=Product.OfferingType.DIGITAL,
        ).filter(
            Q(fulfillment_url__gt="") | Q(product_url__gt=""),
        ).count(),
    }
    command_counts = {
        "briefs": DailyBrief.objects.filter(user=user).count(),
        "voice_briefs": VoiceBrief.objects.filter(user=user).count(),
        "ready_moments": 0,
        "campaigns": MarketingCampaign.objects.filter(user=user).count(),
    }

    context = {
        "page_title": f"User: {user.full_name or user.email}",
        "target_user": user,
        "profile": user.profile,
        "tab": tab,
        "business_mode": business_mode,
        "active_platforms": active_platforms,
        "offer_counts": offer_counts,
        "fulfillment_counts": fulfillment_counts,
        "command_counts": command_counts,
    }

    if tab == "usage":
        from apps.core.admin_dashboard.user_usage import get_admin_user_usage

        context["usage"] = get_admin_user_usage(user)

    elif tab == "profile":
        from apps.core.billing.enforcement import get_seed_usage
        from apps.core.billing.models import ContentSeedQuotaLog

        context["seed_usage"] = get_seed_usage(user)
        context["seed_quota_logs"] = (
            ContentSeedQuotaLog.objects.filter(user=user)
            .select_related("admin")
            .order_by("-created_at")[:10]
        )

    elif tab == "content":
        seeds = ContentSeed.objects.filter(user=user).order_by("-created_at")[:20]
        posts = Post.objects.filter(user=user).select_related("social_account").order_by("-created_at")[:30]
        post_stats = Post.objects.filter(user=user).values("status").annotate(c=Count("id"))
        context.update({
            "seeds": seeds,
            "posts": posts,
            "post_stats": {s["status"]: s["c"] for s in post_stats},
            "total_posts": Post.objects.filter(user=user).count(),
            "total_seeds": ContentSeed.objects.filter(user=user).count(),
        })

    elif tab == "platforms":
        accounts = SocialAccount.objects.filter(user=user).order_by("platform")
        context["social_accounts"] = accounts

    elif tab == "agents":
        configs = AgentConfig.objects.filter(user=user)
        recent_actions = AgentAction.objects.filter(user=user).order_by("-created_at")[:30]
        token_total = AgentAction.objects.filter(
            user=user, tokens_used__gt=0,
        ).aggregate(total=Sum("tokens_used"))["total"] or 0
        agent_stats = (
            AgentAction.objects.filter(user=user)
            .values("agent_type")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                tokens=Sum("tokens_used"),
            )
        )
        context.update({
            "agent_configs": configs,
            "recent_actions": recent_actions,
            "token_total": token_total,
            "agent_stats": {s["agent_type"]: s for s in agent_stats},
        })

    elif tab == "billing":
        payments = MpesaPayment.objects.filter(user=user).order_by("-created_at")[:20]
        total_revenue = MpesaPayment.objects.filter(
            user=user, status="completed",
        ).aggregate(total=Sum("amount"))["total"] or 0
        context.update({
            "payments": payments,
            "total_revenue": total_revenue,
        })

    elif tab == "engagement":
        interactions = Interaction.objects.filter(user=user).order_by("-created_at")[:30]
        superfans = Superfan.objects.filter(user=user).order_by("-interaction_count")[:10]
        interaction_stats = Interaction.objects.filter(user=user).values("status").annotate(c=Count("id"))
        context.update({
            "interactions": interactions,
            "superfans": superfans,
            "interaction_stats": {s["status"]: s["c"] for s in interaction_stats},
            "total_interactions": Interaction.objects.filter(user=user).count(),
        })

    elif tab == "briefs":
        briefs = DailyBrief.objects.filter(user=user).order_by("-date")[:30]
        context["briefs"] = briefs

    return render(request, "admin_dashboard/users/detail.html", context)


@senior_staff_required
@require_POST
def user_change_plan(request, pk):
    """Change a user's plan tier. Requires senior staff (superuser)."""
    user = get_object_or_404(User, pk=pk)
    new_plan = request.POST.get("plan", "")
    if new_plan in dict(UserProfile.PlanTier.choices):
        user.profile.plan = new_plan
        user.profile.save(update_fields=["plan", "updated_at"])
    return redirect("admin_dashboard:user_detail", pk=pk)


@superuser_required
@require_POST
def user_toggle_staff(request, pk):
    """Toggle staff status. Requires superuser."""
    user = get_object_or_404(User, pk=pk)
    if user != request.user:  # Can't demote yourself
        user.is_staff = not user.is_staff
        user.save(update_fields=["is_staff"])
    return redirect("admin_dashboard:user_detail", pk=pk)


@superuser_required
@require_POST
def user_toggle_active(request, pk):
    """Activate or deactivate a user. Requires superuser."""
    user = get_object_or_404(User, pk=pk)
    if user != request.user:  # Can't deactivate yourself
        user.is_active = not user.is_active
        user.save(update_fields=["is_active"])
    return redirect("admin_dashboard:user_detail", pk=pk)


@superuser_required
@require_POST
def user_delete(request, pk):
    """Soft-delete a user. Requires superuser."""
    user = get_object_or_404(User, pk=pk)
    if user != request.user:  # Can't delete yourself
        user.soft_delete()
    return redirect("admin_dashboard:user_list")


@superuser_required
def user_export_csv(request):
    """Export all users as CSV. Requires superuser."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="kova_users.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Email", "Name", "Phone", "Company", "Industry", "Plan",
        "Status", "Payment Provider", "Joined", "Onboarded",
        "Posts Published", "Platforms Connected",
    ])
    users = User.objects.select_related("profile").annotate(
        post_count=Count("posts", filter=Q(posts__status="published"), distinct=True),
        platform_count=Count("social_accounts", filter=Q(social_accounts__is_active=True), distinct=True),
    )
    for u in users:
        writer.writerow([
            u.email,
            u.full_name,
            u.phone_number,
            u.profile.company_name,
            u.profile.get_industry_display() if u.profile.industry else "",
            u.profile.get_plan_display(),
            u.profile.subscription_status,
            u.profile.payment_provider,
            u.date_joined.strftime("%Y-%m-%d"),
            "Yes" if u.onboarding_completed else "No",
            u.post_count,
            u.platform_count,
        ])
    return response
