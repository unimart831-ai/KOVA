from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

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
            "url_name": "briefs:home",
            "icon": "📊",
        },
    ]

    completed = sum(1 for i in items if i["done"])
    total = len(items)

    if completed == total:
        return None  # All done — no need to show

    return {
        "items": items,
        "completed": completed,
        "total": total,
        "percent": int((completed / total) * 100),
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
        user=user, created_at__gte=week_ago,
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
        "page_title": "Daily Brief",
    })
