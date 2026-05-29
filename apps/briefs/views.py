from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.briefs.models import DailyBrief
from apps.engage.models import Superfan
from apps.utils.greetings import greeting_name


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

    # Engagement replies handled (AI or human sent a response)
    from apps.engage.models import Interaction
    replies_count = Interaction.objects.filter(
        user=user,
        responded_at__gte=week_ago,
    ).count()

    # Leads captured
    from apps.leads.models import Lead
    leads_count = Lead.objects.filter(
        user=user, first_seen_at__gte=week_ago,
    ).count()

    # If no activity at all, don't show the card
    product_tasks = 0
    try:
        from apps.briefs.operations_report import build_operations_report

        week_report = build_operations_report(user, hours=24 * 7)
        for cat in week_report.get("categories", []):
            if cat.get("id") in ("products", "inventory"):
                product_tasks += cat.get("count", 0)
    except Exception:
        pass

    total_actions = posts_published + posts_created + replies_count + leads_count + product_tasks
    if total_actions == 0:
        return None

    return {
        "posts_published": posts_published,
        "posts_created": posts_created,
        "replies_drafted": replies_count,
        "leads_captured": leads_count,
        "product_tasks": product_tasks,
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

    # Bookings needing attention today
    try:
        from apps.bookings.models import Booking
        today = timezone.now().date()
        bookings_today = Booking.objects.filter(
            booking_link__user=user,
            scheduled_at__date=today,
            status="pending",
        ).count()
        if bookings_today > 0:
            actions.append({
                "label": f"Confirm {bookings_today} booking{'s' if bookings_today != 1 else ''} today",
                "url_name": "bookings:list",
                "icon": "user",
                "priority": 2,
            })
    except Exception:
        pass

    return sorted(actions, key=lambda a: a["priority"])[:3]


from apps.briefs.delivery import extract_your_move
from apps.briefs.standup import build_standup_context, enrich_decisions


def _build_customer_pulse(user):
    """Live customer-facing signals for the Home sidebar."""
    from datetime import timedelta

    from apps.bookings.models import Booking
    from apps.engage.models import Interaction
    from apps.leads.models import Lead
    from apps.platforms.models import SocialAccount
    from apps.whatsapp.models import WhatsAppConversation

    today = timezone.now().date()
    week_ago = timezone.now() - timedelta(days=7)
    pulse = []

    inbox_waiting = Interaction.objects.filter(
        user=user, status__in=["new", "flagged"],
    ).count()
    if inbox_waiting:
        pulse.append({
            "label": "Social inbox",
            "detail": f"{inbox_waiting} waiting for reply",
            "url_name": "engage:inbox",
            "tone": "amber" if inbox_waiting >= 3 else "blue",
        })

    new_leads = Lead.objects.filter(user=user, status="new").count()
    if new_leads:
        pulse.append({
            "label": "Leads",
            "detail": f"{new_leads} new lead{'s' if new_leads != 1 else ''}",
            "url_name": "leads:list",
            "tone": "purple",
        })

    bookings_today = Booking.objects.filter(
        booking_link__user=user,
        scheduled_at__date=today,
        status__in=["pending", "confirmed"],
    ).count()
    if bookings_today:
        pulse.append({
            "label": "Bookings",
            "detail": f"{bookings_today} today",
            "url_name": "bookings:list",
            "tone": "green",
        })

    wa_accounts = SocialAccount.objects.filter(
        user=user, platform="whatsapp", is_active=True,
    )
    if wa_accounts.exists():
        wa_escalated = WhatsAppConversation.objects.filter(
            social_account__in=wa_accounts,
            status="escalated",
        ).count()
        if wa_escalated:
            pulse.append({
                "label": "WhatsApp",
                "detail": f"{wa_escalated} need{'s' if wa_escalated == 1 else ''} you",
                "url_name": "whatsapp:inbox",
                "tone": "red",
            })

    leads_this_week = Lead.objects.filter(
        user=user, first_seen_at__gte=week_ago,
    ).count()
    if leads_this_week and not new_leads:
        pulse.append({
            "label": "Leads",
            "detail": f"{leads_this_week} this week",
            "url_name": "leads:list",
            "tone": "purple",
        })

    return pulse


def _strategist_is_active(user):
    from apps.agents.models import AgentConfig
    return AgentConfig.objects.filter(
        user=user, agent_type="strategist", is_active=True,
    ).exists()


def _brief_time_has_passed(user):
    import zoneinfo
    try:
        user_tz = zoneinfo.ZoneInfo(user.timezone or "UTC")
    except (KeyError, Exception):
        user_tz = zoneinfo.ZoneInfo("UTC")
    local_now = timezone.now().astimezone(user_tz)
    return local_now.time() >= user.daily_brief_time


def _get_score_breakdown(brief):
    if not brief:
        return None
    return (brief.performance_summary or {}).get("score_breakdown")


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

    # Max count for bar chart scaling — prevents overflow when days have high counts
    max_count = max((d["count"] for d in days), default=1) or 1

    return {
        "days": days,
        "consistency_pct": consistency_pct,
        "days_with_posts": days_with_posts,
        "this_week_total": this_week,
        "trend_pct": trend_pct,
        "trend_direction": "up" if trend_pct > 0 else ("down" if trend_pct < 0 else "flat"),
        "max_count": max_count,
    }


def _parse_research_updated_at(brief):
    """Parse the ISO string stored in performance_summary into a datetime object.
    Django's timesince filter requires a datetime, not a string."""
    if not brief:
        return None
    raw = (brief.performance_summary or {}).get("research_updated_at")
    if not raw:
        return None
    try:
        from datetime import datetime
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _get_dismissed_decisions(brief):
    """Return the dismissed decision indices as a list (never None).
    Old briefs that pre-date this feature won't have the key — return [] so
    template `in` checks work correctly."""
    if not brief:
        return []
    return (brief.performance_summary or {}).get("dismissed_decisions") or []


def _normalize_trending_topics(brief):
    """Ensure each topic's `platforms` field is a list of strings.
    LLMs occasionally return a single string instead of a list — normalize
    so the template `{% for p in topic.platforms %}` always iterates safely."""
    if not brief:
        return []
    topics = brief.trending_topics or []
    normalized = []
    for topic in topics:
        if isinstance(topic, dict):
            platforms = topic.get("platforms", [])
            if isinstance(platforms, str):
                platforms = [platforms] if platforms else []
            topic = {**topic, "platforms": platforms}
        normalized.append(topic)
    return normalized


@login_required
def brief_home(request):
    """Show today's daily brief, or the most recent one while today's is pending."""
    from apps.accounts.segments import build_surface_experience
    from apps.platforms.models import SocialAccount

    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=request.user, date=today).first()
    brief_is_stale = False

    if brief and not brief.is_read:
        brief.is_read = True
        brief.save(update_fields=["is_read"])
    elif not brief:
        brief = DailyBrief.objects.filter(user=request.user).first()
        brief_is_stale = brief is not None

    if not request.user.onboarding_completed:
        return redirect("accounts:onboarding")

    recent_briefs = DailyBrief.objects.filter(user=request.user).exclude(
        date=brief.date if brief else today,
    )[:7]

    superfans = Superfan.objects.filter(user=request.user)[:5]

    upcoming_moments = []
    holiday_drafts_ready = 0
    ready_moment_packs = []
    moment_pack_id = request.GET.get("moment_pack", "").strip()
    try:
        from apps.calendar_intel.selectors import top_upcoming_for_brief
        from apps.calendar_intel.models import HolidayDraft
        upcoming_moments = top_upcoming_for_brief(request.user, count=3)
        ready_moment_packs = list(
            HolidayDraft.objects.filter(
                user=request.user,
                status=HolidayDraft.Status.DRAFTS_READY,
            ).select_related(
                "holiday_occurrence__holiday",
                "custom_event",
            ).order_by("target_date")[:5]
        )
        holiday_drafts_ready = len(ready_moment_packs)
        if not moment_pack_id and ready_moment_packs:
            moment_pack_id = str(ready_moment_packs[0].pk)
    except Exception:
        pass

    performance = brief.performance_summary if brief else {}
    decisions_needed = enrich_decisions(performance.get("decisions_needed", []))
    operations_update = performance.get("operations_update", "")
    standup_context = build_standup_context(request.user, brief) if brief else None

    from apps.briefs.dashboard import get_cached_home_extras
    home_extras = get_cached_home_extras(request.user, brief)
    connected_platforms = list(
        SocialAccount.objects.filter(user=request.user, is_active=True)
        .values_list("platform", flat=True)
    )

    return render(request, "briefs/home.html", {
        "brief": brief,
        "brief_is_stale": brief_is_stale,
        "brief_time_passed": _brief_time_has_passed(request.user),
        "strategist_active": _strategist_is_active(request.user),
        "greeting_name": greeting_name(request.user),
        "your_move": extract_your_move(brief.summary if brief else ""),
        "decisions_needed": decisions_needed,
        "standup_context": standup_context,
        "score_breakdown": _get_score_breakdown(brief),
        "recent_briefs": recent_briefs,
        "superfans": superfans,
        "research_updated_at": _parse_research_updated_at(brief),
        "dismissed_decisions": _get_dismissed_decisions(brief),
        "trending_topics": _normalize_trending_topics(brief),
        "upcoming_moments": upcoming_moments,
        "holiday_drafts_ready": holiday_drafts_ready,
        "ready_moment_packs": ready_moment_packs,
        "moment_pack_id": moment_pack_id,
        "operations_update": operations_update,
        "page_title": "Home",
        "segment_surface": build_surface_experience(
            profile=getattr(request.user, "profile", None),
            connected_platforms=connected_platforms,
        ),
        **home_extras,
    })


def _safe_revenue_stat(user):
    """Wrapper around get_revenue_stat_card that never raises into the view.

    Revenue stats are eye-candy on the home page — a query error here must
    not break the daily brief render. Returns None on any failure so the
    template can hide the card.
    """
    try:
        from apps.analytics.revenue import get_revenue_stat_card
        return get_revenue_stat_card(user)
    except Exception:
        import logging
        logging.getLogger(__name__).exception(
            "Revenue stat card failed for %s — hiding card", user.email,
        )
        return None


@login_required
def operations_report_partial(request):
    """HTMX lazy-load for the operations report panel."""
    from apps.briefs.dashboard import get_cached_operations_report

    today = timezone.now().date()
    brief = DailyBrief.objects.filter(user=request.user, date=today).first()
    operations_report = get_cached_operations_report(request.user, hours=24)
    operations_update = ""
    if brief and brief.performance_summary:
        operations_update = brief.performance_summary.get("operations_update", "")

    return render(request, "briefs/_operations_report.html", {
        "operations_report": operations_report,
        "operations_update": operations_update,
    })


@login_required
def brief_detail(request, date):
    """Show a historical daily brief by date (YYYY-MM-DD)."""
    from datetime import date as date_type
    try:
        brief_date = date_type.fromisoformat(date)
    except ValueError:
        from django.http import Http404
        raise Http404("Invalid date format")

    brief = DailyBrief.objects.filter(user=request.user, date=brief_date).first()
    if not brief:
        from django.http import Http404
        raise Http404("Brief not found")

    today = timezone.now().date()
    recent_briefs = (
        DailyBrief.objects.filter(user=request.user)
        .exclude(date=brief_date)
        .order_by("-date")[:7]
    )

    published_today = request.user.posts.filter(status="published", published_at__date=today).count()
    failed_count = request.user.posts.filter(status="failed").count()
    scheduled_count = request.user.posts.filter(status__in=["approved", "scheduled"]).count()

    superfans = Superfan.objects.filter(user=request.user)[:5]

    from apps.platforms.models import SocialAccount
    has_connected_platform = SocialAccount.objects.filter(user=request.user, is_active=True).exists()

    # Upcoming holidays / cultural moments — same forward-looking widget as the home brief
    upcoming_moments = []
    holiday_drafts_ready = 0
    try:
        from apps.calendar_intel.selectors import top_upcoming_for_brief
        from apps.calendar_intel.models import HolidayDraft
        upcoming_moments = top_upcoming_for_brief(request.user, count=3)
        holiday_drafts_ready = HolidayDraft.objects.filter(
            user=request.user,
            status=HolidayDraft.Status.DRAFTS_READY,
        ).count()
    except Exception:
        pass

    # Profile health alerts — same as home brief
    profile_health_alerts = []
    try:
        from apps.profile_audit.models import ProfileAudit, ProfileUpdateSuggestion
        from django.db.models import Max
        latest_ids = list(
            ProfileAudit.objects.filter(user=request.user)
            .values("social_account_id")
            .annotate(latest_id=Max("id"))
            .values_list("latest_id", flat=True)
        )
        for audit in (
            ProfileAudit.objects
            .filter(id__in=latest_ids, completeness_score__lt=70, error="")
            .select_related("social_account")[:3]
        ):
            profile_health_alerts.append({
                "platform": audit.social_account.platform,
                "score": audit.completeness_score,
                "pending": audit.suggestions.filter(
                    status=ProfileUpdateSuggestion.Status.PENDING,
                ).count(),
                "account_id": audit.social_account_id,
            })
    except Exception:
        pass

    performance = brief.performance_summary or {}
    operations_report = performance.get("operations_report") or {}
    if not operations_report.get("categories"):
        try:
            from apps.briefs.operations_report import build_operations_report

            operations_report = build_operations_report(request.user, hours=24)
        except Exception:
            operations_report = {"has_activity": False, "categories": [], "recent_tasks": []}

    return render(request, "briefs/detail.html", {
        "brief": brief,
        "brief_date": brief_date,
        "is_historical": True,
        "today": today,
        "recent_briefs": recent_briefs,
        "published_today": published_today,
        "failed_count": failed_count,
        "scheduled_count": scheduled_count,
        "superfans": superfans,
        "has_connected_platform": has_connected_platform,
        "momentum": _build_momentum_data(request.user),
        "value_summary": _build_value_summary(request.user),
        "brief_streak": _build_brief_streak(request.user),
        "research_updated_at": _parse_research_updated_at(brief),
        "dismissed_decisions": _get_dismissed_decisions(brief),
        "trending_topics": _normalize_trending_topics(brief),
        "upcoming_moments": upcoming_moments,
        "holiday_drafts_ready": holiday_drafts_ready,
        "profile_health_alerts": profile_health_alerts,
        "quick_actions": [],
        "setup_checklist": None,
        "operations_report": operations_report,
        "operations_update": performance.get("operations_update", ""),
        "page_title": f"Brief — {brief_date.strftime('%b %d, %Y')}",
    })


@login_required
@require_POST
def brief_dismiss_decision(request):
    """
    HTMX endpoint: dismiss a decision item from the brief.
    Stores the dismissed item index in performance_summary.dismissed_decisions
    so it doesn't re-appear on page reload.
    Returns empty 200 to remove the element via hx-swap="outerHTML".
    """
    brief_id = request.POST.get("brief_id", "").strip()
    item_index = request.POST.get("item_index", "").strip()

    if not brief_id or not item_index.isdigit():
        return HttpResponse(status=400)

    try:
        brief = DailyBrief.objects.get(id=brief_id, user=request.user)
        ps = brief.performance_summary or {}
        dismissed = ps.get("dismissed_decisions", [])
        idx = int(item_index)
        if idx not in dismissed:
            dismissed.append(idx)
        ps["dismissed_decisions"] = dismissed
        brief.performance_summary = ps
        brief.save(update_fields=["performance_summary"])
    except DailyBrief.DoesNotExist:
        return HttpResponse(status=404)

    # Return empty — HTMX will replace the <li> with nothing
    return HttpResponse("", content_type="text/html")


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
    # Platform hint from the suggestion (e.g. "linkedin" or "facebook,instagram")
    platform_hint = request.POST.get("platform_hint", "").strip()

    if not idea:
        if request.headers.get("HX-Request"):
            return HttpResponse(
                '<span class="text-xs text-red-500">No idea provided</span>',
                content_type="text/html",
            )
        return redirect("brief:home")

    # Use suggestion's platform(s) if provided and user has them connected;
    # fall back to user's first 3 active platforms.
    active_platforms = set(
        SocialAccount.objects.filter(user=request.user, is_active=True)
        .values_list("platform", flat=True)
    )
    if platform_hint:
        hint_platforms = [p.strip() for p in platform_hint.split(",") if p.strip()]
        target_platforms = [p for p in hint_platforms if p in active_platforms] or list(active_platforms)[:3]
    else:
        target_platforms = list(active_platforms)[:3]

    seed_idea = idea
    if context:
        seed_idea += f"\n\nContext: {context}"

    notes = f"Created from Daily Brief ({action_type})"

    ContentSeed.objects.create(
        user=request.user,
        idea=seed_idea,
        notes=notes,
        target_platforms=target_platforms[:3],
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


@login_required
def brief_archive_list(request):
    """List of archived daily briefs."""
    briefs = DailyBrief.objects.filter(
        user=request.user, is_archived=True,
    ).order_by("-brief_date")[:50]
    return render(request, "briefs/archive.html", {
        "page_title": "Brief Archive",
        "briefs": briefs,
    })


@login_required
@require_POST
def archive_brief(request):
    """Toggle archive status of a brief."""
    brief_id = request.POST.get("brief_id")
    brief = get_object_or_404(DailyBrief, id=brief_id, user=request.user)
    brief.is_archived = not brief.is_archived
    brief.save(update_fields=["is_archived"])
    if brief.is_archived:
        messages.success(request, "Brief archived.")
    else:
        messages.success(request, "Brief restored.")
    if request.headers.get("HX-Request"):
        return HttpResponse(status=204)
    return redirect(request.META.get("HTTP_REFERER") or reverse("brief:home"))
