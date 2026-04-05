from datetime import timedelta

from django.core.paginator import Paginator
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render
from django.utils import timezone

from apps.admin_dashboard.decorators import staff_required


@staff_required
def teams_overview(request):
    """Teams overview — total teams, members, invitations, role distribution."""
    from apps.teams.models import Team, TeamActivity, TeamInvitation, TeamMember

    now = timezone.now()
    seven_days_ago = now - timedelta(days=7)

    total_teams = Team.objects.count()
    total_members = TeamMember.objects.count()
    teams_7d = Team.objects.filter(created_at__gte=seven_days_ago).count()
    members_7d = TeamMember.objects.filter(joined_at__gte=seven_days_ago).count()

    # Brands
    from apps.teams.models import Brand
    total_brands = Brand.objects.count()
    active_brands = Brand.objects.filter(is_active=True).count()
    brands_7d = Brand.objects.filter(created_at__gte=seven_days_ago).count()

    # Invitations
    total_invitations = TeamInvitation.objects.count()
    pending_invitations = TeamInvitation.objects.filter(
        accepted=False, expires_at__gt=now,
    ).count()
    accepted_invitations = TeamInvitation.objects.filter(accepted=True).count()
    expired_invitations = TeamInvitation.objects.filter(
        accepted=False, expires_at__lte=now,
    ).count()

    # Role distribution
    role_breakdown = list(
        TeamMember.objects.values("role")
        .annotate(count=Count("id"))
        .order_by("role")
    )

    # Team size distribution
    team_sizes = list(
        Team.objects.annotate(member_count=Count("members"))
        .values("member_count")
        .annotate(team_count=Count("id"))
        .order_by("member_count")
    )

    # Largest teams
    largest_teams = (
        Team.objects.annotate(member_count=Count("members"))
        .select_related("owner")
        .order_by("-member_count")[:10]
    )

    # Recent team activity (all teams)
    recent_activity = (
        TeamActivity.objects.select_related("team", "actor")
        .order_by("-created_at")[:15]
    )

    # Activity type breakdown (7d)
    activity_breakdown = list(
        TeamActivity.objects.filter(created_at__gte=seven_days_ago)
        .values("event_type")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    context = {
        "page_title": "Teams",
        "total_teams": total_teams,
        "total_members": total_members,
        "teams_7d": teams_7d,
        "members_7d": members_7d,
        "total_brands": total_brands,
        "active_brands": active_brands,
        "brands_7d": brands_7d,
        "total_invitations": total_invitations,
        "pending_invitations": pending_invitations,
        "accepted_invitations": accepted_invitations,
        "expired_invitations": expired_invitations,
        "role_breakdown": role_breakdown,
        "team_sizes": team_sizes,
        "largest_teams": largest_teams,
        "recent_activity": recent_activity,
        "activity_breakdown": activity_breakdown,
    }
    return render(request, "admin_dashboard/teams/overview.html", context)


@staff_required
def team_list(request):
    """All teams with search, filter, pagination."""
    from apps.teams.models import Team

    qs = Team.objects.annotate(
        member_count=Count("members", distinct=True),
        invitation_count=Count("invitations", distinct=True),
        brand_count=Count("brands", distinct=True),
    ).select_related("owner")

    search = request.GET.get("q", "").strip()
    if search:
        qs = qs.filter(
            Q(name__icontains=search) |
            Q(owner__email__icontains=search) |
            Q(owner__full_name__icontains=search)
        )

    sort = request.GET.get("sort", "-created_at")
    valid_sorts = {"created_at", "-created_at", "member_count", "-member_count", "name", "-name"}
    if sort not in valid_sorts:
        sort = "-created_at"
    qs = qs.order_by(sort)

    paginator = Paginator(qs, 30)
    page = paginator.get_page(request.GET.get("page", 1))

    context = {
        "page_title": "All Teams",
        "page_obj": page,
        "search": search,
        "current_sort": sort,
        "total_count": paginator.count,
    }
    return render(request, "admin_dashboard/teams/list.html", context)


@staff_required
def team_detail(request, pk):
    """Single team detail — members, invitations, content."""
    from apps.content.models import Post
    from apps.teams.models import Brand, Team, TeamActivity, TeamInvitation, TeamMember

    team = get_object_or_404(
        Team.objects.select_related("owner").annotate(
            member_count=Count("members"),
        ),
        pk=pk,
    )
    members = TeamMember.objects.filter(team=team).select_related("user").order_by("role")
    invitations = TeamInvitation.objects.filter(team=team).order_by("-created_at")[:20]

    # Team brands
    brands = Brand.objects.filter(team=team).order_by("-created_at")

    # Team activity feed
    team_activity = (
        TeamActivity.objects.filter(team=team)
        .select_related("actor")
        .order_by("-created_at")[:20]
    )

    # Team content stats
    member_user_ids = list(members.values_list("user_id", flat=True))
    team_posts = Post.objects.filter(user_id__in=member_user_ids)
    content_stats = {
        "total": team_posts.count(),
        "published": team_posts.filter(status="published").count(),
        "pending": team_posts.filter(status="pending_approval").count(),
        "drafts": team_posts.filter(status="draft").count(),
    }

    context = {
        "page_title": f"Team: {team.name}",
        "team": team,
        "members": members,
        "invitations": invitations,
        "content_stats": content_stats,
        "brands": brands,
        "team_activity": team_activity,
        "now": timezone.now(),
    }
    return render(request, "admin_dashboard/teams/detail.html", context)
