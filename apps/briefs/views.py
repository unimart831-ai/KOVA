from django.contrib.auth.decorators import login_required
from django.shortcuts import render, redirect
from django.utils import timezone

from apps.briefs.models import DailyBrief


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

    return render(request, "briefs/home.html", {
        "brief": brief,
        "recent_briefs": recent_briefs,
        "published_today": published_today,
        "failed_count": failed_count,
        "scheduled_count": scheduled_count,
        "page_title": "Daily Brief",
    })
