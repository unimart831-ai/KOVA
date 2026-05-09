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
@require_POST
def custom_event_delete(request, event_id):
    from apps.calendar_intel.models import CustomEvent
    event = get_object_or_404(CustomEvent, id=event_id, user=request.user)
    event.delete()
    return redirect("calendar_intel:preferences")
