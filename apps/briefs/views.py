from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.briefs.models import DailyBrief
from apps.engage.models import Superfan


def _build_setup_checklist(user):
    """
    Build a first-week setup checklist for new users.

    Returns None if the user has been active > 14 days (stop nudging).
    Returns a dict with items + completion stats otherwise.
    """
    from apps.platforms.models import SocialAccount
    from apps.content.models import Post

    profile = user.profile

    # Only show for first 14 days after sign-up
    days_since_signup = (timezone.now() - user.date_joined).days
    if days_since_signup > 14:
        return None

    has_platform = SocialAccount.objects.filter(user=user, is_active=True).exists()
    has_published = Post.objects.filter(user=user, status="published").exists()
    has_scheduled = Post.objects.filter(user=user, status__in=["approved", "scheduled"]).exists()
    has_brief = DailyBrief.objects.filter(user=user, is_read=True).exists()
    has_brand_voice = bool(profile.brand_voice and profile.brand_voice.strip())

    items = [
        {
            "key": "connect_platform",
            "label": "Connect a social account",
            "done": has_platform,
            "url_name": "platforms:list",
            "icon": "🔗",
        },
        {
            "key": "brand_voice",
            "label": "Set your brand voice",
            "done": has_brand_voice,
            "url_name": "accounts:settings",
            "icon": "🎯",
        },
        {
            "key": "first_post",
            "label": "Publish or schedule your first post",
            "done": has_published or has_scheduled,
            "url_name": "content:studio",
            "icon": "✍️",
        },
        {
            "key": "read_brief",
            "label": "Review your Daily Brief",
            "done": has_brief,
            "url_name": "brief:home",
            "icon": "📊",
        },
    ]

    completed = sum(1 for i in items if i["done"])
    total = len(items)

    if completed == total:
        return None  # All done — no need to show

    next_step = next((i for i in items if not i["done"]), None)

    return {
        "items": items,
        "completed": completed,
        "total": total,
        "percent": int((completed / total) * 100),
        "next_step": next_step,
    }


def _build_value_summary(user):
    """
    Build a "What Kova did for you this week" summary card.

    Shows concrete value delivered: posts published, engagements handled,
    content created, leads captured. Reinforces ROI during trial.
    """
    from datetime import timedelta

    from django.db.models import Count

    from apps.content.models import Post

    now = timezone.now()
    week_ago = now - timedelta(days=7)

    posts_published = Post.objects.filter(
        user=user, status="published", published_at__gte=week_ago,
    ).count()

    posts_created = Post.objects.filter(
        user=user, created_at__gte=week_ago,
    ).count()

    # Engagement replies drafted
    from apps.engage.models import Interaction
    replies_count = Interaction.objects.filter(
        user=user, created_at__gte=week_ago,
    ).count()

    # Leads captured
    from apps.leads.models import Lead
    leads_count = Lead.objects.filter(
        user=user, first_seen_at__gte=week_ago,
    ).count()

    # If no activity at all, don't show the card
    total_actions = posts_published + posts_created + replies_count + leads_count
    if total_actions == 0:
        return None

    return {
        "posts_published": posts_published,
        "posts_created": posts_created,
        "replies_drafted": replies_count,
        "leads_captured": leads_count,
    }


def _build_brief_streak(user):
    """Calculate consecutive days the user has read their brief."""
    from datetime import timedelta
    briefs = (
        DailyBrief.objects.filter(user=user, is_read=True)
        .order_by("-date")
        .values_list("date", flat=True)[:60]
    )
    if not briefs:
        return 0

    streak = 0
    expected = timezone.now().date()
    for d in briefs:
        if d == expected:
            streak += 1
            expected -= timedelta(days=1)
        elif d < expected:
            break
    return streak


def _build_quick_actions(user, brief):
    """Build a list of 1-3 most important morning actions from the brief."""
    actions = []

    # Posts awaiting approval
    if brief and brief.posts_pending > 0:
        actions.append({
            "label": f"Approve {brief.posts_pending} post{'s' if brief.posts_pending != 1 else ''}",
            "url_name": "content:studio",
            "icon": "edit",
            "priority": 1,
        })

    # Unanswered comments/messages
    try:
        from apps.engage.models import Interaction
        unanswered = Interaction.objects.filter(
            user=user, status__in=["new", "flagged"],
        ).count()
        if unanswered > 0:
            actions.append({
                "label": f"Reply to {unanswered} comment{'s' if unanswered != 1 else ''}",
                "url_name": "engage:inbox",
                "icon": "chat",
                "priority": 2,
            })
    except Exception:
        pass

    # New leads
    try:
        from apps.leads.models import Lead
        new_leads = Lead.objects.filter(user=user, status="new").count()
        if new_leads > 0:
            actions.append({
                "label": f"Review {new_leads} new lead{'s' if new_leads != 1 else ''}",
                "url_name": "leads:list",
                "icon": "user",
                "priority": 3,
            })
    except Exception:
        pass

    # Failed posts
    failed = user.posts.filter(status="failed").count()
    if failed > 0:
        actions.append({
            "label": f"Fix {failed} failed post{'s' if failed != 1 else ''}",
            "url_name": "content:queue",
            "icon": "alert",
            "priority": 1,
        })

    return sorted(actions, key=lambda a: a["priority"])[:3]


def _build_momentum_data(user):
    """Build 14-day posting consistency + trend data for sparkline."""
    from datetime import timedelta
    from django.db.models.functions import TruncDate
    from apps.content.models import Post

    today = timezone.now().date()
    fourteen_ago = today - timedelta(days=13)

    # Posts published per day over 14 days
    daily_posts = dict(
        Post.objects.filter(
            user=user,
            status="published",
            published_at__date__gte=fourteen_ago,
        )
        .annotate(day=TruncDate("published_at"))
        .values("day")
        .annotate(count=Count("id"))
        .values_list("day", "count")
    )

    days = []
    for i in range(14):
        d = fourteen_ago + timedelta(days=i)
        days.append({"date": d.strftime("%b %d"), "count": daily_posts.get(d, 0)})

    # Calculate consistency
    days_with_posts = sum(1 for d in days if d["count"] > 0)
    consistency_pct = int((days_with_posts / 14) * 100)

    # Weekly comparison
    this_week = sum(d["count"] for d in days[7:])
    last_week = sum(d["count"] for d in days[:7])
    if last_week > 0:
        trend_pct = int(((this_week - last_week) / last_week) * 100)
    else:
        trend_pct = 100 if this_week > 0 else 0

    return {
        "days": days,
        "consistency_pct": consistency_pct,
        "days_with_posts": days_with_posts,
        "this_week_total": this_week,
        "trend_pct": trend_pct,
        "trend_direction": "up" if trend_pct > 0 else ("down" if trend_pct < 0 else "flat"),
    }


@login_required
def brief_home(request):
    """Show today's daily brief, or the most recent one."""
    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=request.user, date=today).first()

    if brief and not brief.is_read:
        brief.is_read = True
        brief.save(update_fields=["is_read"])

    # If user hasn't completed onboarding, redirect
    if not request.user.onboarding_completed:
        return redirect("accounts:onboarding")

    recent_briefs = DailyBrief.objects.filter(user=request.user).exclude(date=today)[:7]

    # Quick stats for the sidebar
    published_today = request.user.posts.filter(
        status="published",
        published_at__date=today,
    ).count()
    failed_count = request.user.posts.filter(status="failed").count()
    scheduled_count = request.user.posts.filter(
        status__in=["approved", "scheduled"],
    ).count()

    # Top superfans to acknowledge
    superfans = Superfan.objects.filter(user=request.user)[:5]

    # Platform connection nudge — show if user has no active social accounts
    from apps.platforms.models import SocialAccount
    has_connected_platform = SocialAccount.objects.filter(
        user=request.user, is_active=True
    ).exists()

    return render(request, "briefs/home.html", {
        "brief": brief,
        "recent_briefs": recent_briefs,
        "published_today": published_today,
        "failed_count": failed_count,
        "scheduled_count": scheduled_count,
        "superfans": superfans,
        "has_connected_platform": has_connected_platform,
        "setup_checklist": _build_setup_checklist(request.user),
        "value_summary": _build_value_summary(request.user),
        "brief_streak": _build_brief_streak(request.user),
        "quick_actions": _build_quick_actions(request.user, brief) if brief else [],
        "momentum": _build_momentum_data(request.user),
        "page_title": "Daily Brief",
    })


@login_required
@require_POST
def brief_action(request):
    """
    One-click action from brief: turn a suggestion/trend into a ContentSeed.
    HTMX-aware — returns a success badge to swap inline.
    """
    from apps.content.models import ContentSeed
    from apps.platforms.models import SocialAccount

    idea = request.POST.get("idea", "").strip()
    context = request.POST.get("context", "").strip()
    action_type = request.POST.get("action_type", "suggestion")  # suggestion, trend, decision

    if not idea:
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<span class="text-xs text-red-500">No idea provided</span>',
                content_type="text/html",
            )
        return redirect("brief:home")

    platforms = list(
        SocialAccount.objects.filter(user=request.user, is_active=True)
        .values_list("platform", flat=True)
    )

    seed_idea = idea
    if context:
        seed_idea += f"\n\nContext: {context}"

    notes = f"Created from Daily Brief ({action_type})"

    ContentSeed.objects.create(
        user=request.user,
        idea=seed_idea,
        notes=notes,
        target_platforms=platforms[:3],
    )

    if request.headers.get("HX-Request"):
        return HttpResponse(
            '<span class="inline-flex items-center gap-1 text-xs font-medium text-green-600 dark:text-green-400">'
            '<svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">'
            '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>'
            '</svg>Queued for creation</span>',
            content_type="text/html",
        )
    return redirect("brief:home")
