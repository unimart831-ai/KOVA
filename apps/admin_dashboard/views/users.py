import csv
from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.accounts.models import User, UserProfile
from apps.admin_dashboard.decorators import staff_required


@staff_required
def user_list(request):
    """User management list with search, filter, sort."""
    qs = User.objects.select_related("profile").all()

    # ── Search ───────────────────────────────────────────────────────────
    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(email__icontains=search) |
            Q(full_name__icontains=search) |
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

    staff_filter = request.GET.get("is_staff", "")
    if staff_filter == "yes":
        qs = qs.filter(is_staff=True)
    elif staff_filter == "no":
        qs = qs.filter(is_staff=False)

    # ── Annotate ─────────────────────────────────────────────────────────
    qs = qs.annotate(
        post_count=Count("posts", distinct=True),
        platform_count=Count("social_accounts", filter=Q(social_accounts__is_active=True), distinct=True),
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

    context = {
        "page_title": "User Management",
        "page_obj": page,
        "search": search,
        "current_plan": plan,
        "current_status": status,
        "current_industry": industry,
        "current_onboarded": onboarded,
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
def user_detail(request, pk):
    """Full user detail with tabs: profile, content, platforms, agents, billing, engagement, briefs."""
    from apps.agents.models import AgentAction, AgentConfig
    from apps.analytics.models import PostMetric
    from apps.billing.models import MpesaPayment
    from apps.briefs.models import DailyBrief
    from apps.content.models import ContentSeed, Post
    from apps.engage.models import Interaction, Superfan
    from apps.platforms.models import SocialAccount

    user = get_object_or_404(User.objects.select_related("profile"), pk=pk)
    now = timezone.now()
    tab = request.GET.get("tab", "profile")

    context = {
        "page_title": f"User: {user.full_name or user.email}",
        "target_user": user,
        "profile": user.profile,
        "tab": tab,
    }

    if tab == "profile":
        pass  # user + profile already in context

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


@staff_required
@require_POST
def user_change_plan(request, pk):
    """Change a user's plan tier."""
    user = get_object_or_404(User, pk=pk)
    new_plan = request.POST.get("plan", "")
    if new_plan in dict(UserProfile.PlanTier.choices):
        user.profile.plan = new_plan
        user.profile.save(update_fields=["plan", "updated_at"])
    return redirect("admin_dashboard:user_detail", pk=pk)


@staff_required
@require_POST
def user_toggle_staff(request, pk):
    """Toggle staff status."""
    user = get_object_or_404(User, pk=pk)
    if user != request.user:  # Can't demote yourself
        user.is_staff = not user.is_staff
        user.save(update_fields=["is_staff"])
    return redirect("admin_dashboard:user_detail", pk=pk)


@staff_required
def user_export_csv(request):
    """Export all users as CSV."""
    response = HttpResponse(content_type="text/csv")
    response["Content-Disposition"] = 'attachment; filename="kova_users.csv"'
    writer = csv.writer(response)
    writer.writerow([
        "Email", "Name", "Company", "Industry", "Plan",
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
