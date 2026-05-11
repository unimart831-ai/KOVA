"""
Views for the calendar_intel app.

Phase 1 Week 2 surface area:
  - GET /calendar/preferences/         : preferences dashboard
  - POST /calendar/preferences/<id>/   : HTMX toggle enable/disable
  - POST /calendar/preferences/<id>/mute/ : mute this year
  - GET /calendar/htmx/upcoming/       : upcoming widget for Brief
"""
from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from apps.calendar_intel.models import Holiday, UserHolidayPreference
from apps.calendar_intel.selectors import (
    all_for_preferences,
    top_upcoming_for_brief,
)


@login_required
def preferences(request):
    """User-facing preferences page — see/toggle holidays the user gets."""
    user = request.user
    profile = getattr(user, "profile", None)

    moments = all_for_preferences(user, days_ahead=365)

    # Build quick lookups
    pref_by_holiday_id = {
        p.holiday_id: p
        for p in user.holiday_preferences.select_related("holiday")
    }
    holiday_ids = {m.holiday_id for m in moments if m.holiday_id}
    holidays_by_id = {
        h.id: h for h in Holiday.objects.filter(id__in=holiday_ids)
    }

    # Group moments by category for display
    grouped: dict[str, list] = {}
    for m in moments:
        if m.source == "custom":
            continue
        holiday_obj = holidays_by_id.get(m.holiday_id)
        if not holiday_obj:
            continue
        key = m.category or "other"
        grouped.setdefault(key, []).append({
            "moment": m,
            "holiday": holiday_obj,
            "preference": pref_by_holiday_id.get(m.holiday_id),
        })

    custom_events = list(user.custom_events.filter(is_active=True).order_by("date"))

    context = {
        "page_title": "Holidays & Moments",
        "country": getattr(profile, "country", "") or "",
        "city": getattr(profile, "city", "") or "",
        "industry": getattr(profile, "industry", "") or "",
        "grouped_moments": grouped,
        "custom_events": custom_events,
        "total_moments": len(moments),
    }
    return render(request, "calendar_intel/preferences.html", context)


@login_required
@require_POST
def htmx_preference_toggle(request, holiday_id):
    """Toggle is_enabled on a UserHolidayPreference. Creates row if missing.
    Returns the updated row partial for HTMX swap."""
    holiday = get_object_or_404(Holiday, id=holiday_id, is_active=True)
    pref, _ = UserHolidayPreference.objects.get_or_create(
        user=request.user, holiday=holiday,
        defaults={"is_enabled": True},
    )
    # If already enabled and not muted, disable. Else enable.
    if pref.is_enabled and not pref.muted_until:
        pref.is_enabled = False
    else:
        pref.is_enabled = True
        pref.muted_until = None
    pref.save()
    return _render_pref_row(request, holiday, pref)


@login_required
@require_POST
def htmx_preference_mute_year(request, holiday_id):
    """Mute a holiday until Jan 1 next year."""
    holiday = get_object_or_404(Holiday, id=holiday_id, is_active=True)
    pref, _ = UserHolidayPreference.objects.get_or_create(
        user=request.user, holiday=holiday,
    )
    next_year = timezone.now().date().replace(month=1, day=1) + timedelta(days=400)
    pref.muted_until = next_year.replace(month=1, day=1)
    pref.save()
    return _render_pref_row(request, holiday, pref)


def _render_pref_row(request, holiday: Holiday, pref: UserHolidayPreference):
    """Render the row partial used for HTMX swaps."""
    # Build a minimal moment-like context for the row template
    today = timezone.now().date()
    next_occ = (
        holiday.occurrences
        .filter(date__gte=today)
        .order_by("date")
        .first()
    )
    return render(request, "calendar_intel/partials/_preference_row.html", {
        "holiday": holiday,
        "preference": pref,
        "next_occ": next_occ,
        "today": today,
    })


@login_required
def htmx_upcoming(request):
    """Brief sidebar widget — top 3 upcoming moments. Used by Daily Brief."""
    moments = top_upcoming_for_brief(request.user, count=3)
    return render(request, "calendar_intel/partials/_upcoming_widget.html", {
        "moments": moments,
    })


# ──────────────────────────────────────────────────────────────────────────
# Custom events — Phase 1 minimal CRUD (form-based, no HTMX yet)
# ──────────────────────────────────────────────────────────────────────────
@login_required
def holiday_refine(request, holiday_id):
    """Per-holiday detail page. Edit custom lead time, post count, relevance,
    and personal angles. Shows past performance for this holiday × user."""
    holiday = get_object_or_404(Holiday, id=holiday_id, is_active=True)
    pref = UserHolidayPreference.objects.filter(
        user=request.user, holiday=holiday,
    ).first()

    if request.method == "POST":
        if not pref:
            pref = UserHolidayPreference(user=request.user, holiday=holiday)

        # is_enabled: posted as form field
        pref.is_enabled = request.POST.get("is_enabled") == "on"
        pref.auto_draft_posts = request.POST.get("auto_draft_posts") == "on"

        # Sliders — optional, blank means use Holiday defaults
        lead = request.POST.get("custom_lead_time_days", "").strip()
        pref.custom_lead_time_days = int(lead) if lead.isdigit() else None

        post_count = request.POST.get("custom_post_count", "").strip()
        pref.custom_post_count = int(post_count) if post_count.isdigit() else None

        relevance = request.POST.get("custom_relevance_score", "").strip()
        pref.custom_relevance_score = (
            max(0, min(100, int(relevance))) if relevance.isdigit() else None
        )

        # Personal angles (newline-separated textarea -> JSON list)
        personal_angles_text = request.POST.get("personal_angles", "").strip()
        if personal_angles_text:
            angles_list = [
                a.strip() for a in personal_angles_text.splitlines() if a.strip()
            ]
            pref.notes = "\n".join(angles_list)[:200]
        else:
            pref.notes = ""

        pref.save()
        return redirect("calendar_intel:holiday_refine", holiday_id=holiday.id)

    # Past performance for THIS holiday for this user
    past_performance = _gather_past_performance(request.user, holiday)
    next_occ = holiday.occurrences.filter(
        date__gte=timezone.now().date(),
    ).order_by("date").first()

    context = {
        "holiday": holiday,
        "preference": pref,
        "next_occ": next_occ,
        "past_performance": past_performance,
        "personal_angles_text": pref.notes if pref else "",
        "page_title": f"{holiday.name} — refine",
    }
    return render(request, "calendar_intel/holiday_refine.html", context)


def _gather_past_performance(user, holiday) -> dict:
    """Stats on past holiday-watcher posts for this user × holiday."""
    from django.db.models import Avg
    from apps.content.models import Post

    past_qs = Post.objects.filter(
        user=user,
        generated_by_agent="holiday_watcher",
        holiday_drafts__holiday_occurrence__holiday=holiday,
    ).distinct()

    published_count = past_qs.filter(status="published").count()
    if not published_count:
        return {
            "post_count": past_qs.count(),
            "published_count": 0,
            "avg_score": None,
            "baseline_avg": None,
        }

    avg_score = past_qs.filter(status="published").aggregate(
        avg=Avg("metrics__actual_score"),
    )["avg"]
    baseline = Post.objects.filter(
        user=user, status="published",
    ).aggregate(avg=Avg("metrics__actual_score"))["avg"]

    return {
        "post_count": past_qs.count(),
        "published_count": published_count,
        "avg_score": round(avg_score, 1) if avg_score is not None else None,
        "baseline_avg": round(baseline, 1) if baseline is not None else None,
    }


@login_required
def custom_event_add(request):
    """Add a custom moment (anniversary, launch, etc.)."""
    if request.method == "POST":
        from apps.calendar_intel.models import CustomEvent
        from datetime import date as date_cls

        name = request.POST.get("name", "").strip()
        date_str = request.POST.get("date", "").strip()
        recurrence = request.POST.get("recurrence", "yearly")
        description = request.POST.get("description", "").strip()

        if not name or not date_str:
            return render(request, "calendar_intel/custom_event_form.html", {
                "error": "Name and date are required.",
                "form_data": request.POST,
            })

        try:
            event_date = date_cls.fromisoformat(date_str)
        except ValueError:
            return render(request, "calendar_intel/custom_event_form.html", {
                "error": "Invalid date format. Use YYYY-MM-DD.",
                "form_data": request.POST,
            })

        CustomEvent.objects.create(
            user=request.user,
            name=name,
            description=description,
            date=event_date,
            recurrence=recurrence,
        )
        return redirect("calendar_intel:preferences")

    return render(request, "calendar_intel/custom_event_form.html", {})


@login_required
def custom_event_edit(request, event_id):
    """Edit an existing custom event. Same template as add (reuse form)."""
    from apps.calendar_intel.models import CustomEvent
    from datetime import date as date_cls

    event = get_object_or_404(CustomEvent, id=event_id, user=request.user)

    if request.method == "POST":
        name = request.POST.get("name", "").strip()
        date_str = request.POST.get("date", "").strip()
        recurrence = request.POST.get("recurrence", "yearly")
        description = request.POST.get("description", "").strip()

        if not name or not date_str:
            return render(request, "calendar_intel/custom_event_form.html", {
                "error": "Name and date are required.",
                "form_data": request.POST,
                "event": event,
            })

        try:
            event_date = date_cls.fromisoformat(date_str)
        except ValueError:
            return render(request, "calendar_intel/custom_event_form.html", {
                "error": "Invalid date format. Use YYYY-MM-DD.",
                "form_data": request.POST,
                "event": event,
            })

        event.name = name
        event.date = event_date
        event.recurrence = recurrence
        event.description = description
        event.save()
        return redirect("calendar_intel:preferences")

    # GET — render form pre-filled
    return render(request, "calendar_intel/custom_event_form.html", {
        "event": event,
        "form_data": {
            "name": event.name,
            "date": event.date.isoformat(),
            "recurrence": event.recurrence,
            "description": event.description,
        },
    })


@login_required
@require_POST
def custom_event_delete(request, event_id):
    from apps.calendar_intel.models import CustomEvent
    event = get_object_or_404(CustomEvent, id=event_id, user=request.user)
    event.delete()
    return redirect("calendar_intel:preferences")
