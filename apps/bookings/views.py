"""Booking integration views (Phase 2 W7-8).

User-authenticated:
  bookings_list      GET  /bookings/                    list BookingLinks + recent
  link_create        GET/POST /bookings/links/new/      create BookingLink
  link_detail        GET  /bookings/links/<id>/         edit BookingLink
  link_calendar      GET  /bookings/links/<id>/calendar/ calendar view
  booking_detail     GET  /bookings/<id>/               single booking
  booking_complete   POST /bookings/<id>/complete/      mark completed
  booking_cancel     POST /bookings/<id>/cancel/        cancel

Public:
  public_book        GET  /book/<slug>/                 pick + book
  public_confirm     POST /book/<slug>/confirm/         create booking
  public_done        GET  /book/<slug>/done/<bid>/      thank-you page

Slot-availability data:
  slots_for_date     GET  /bookings/links/<id>/slots/?date=YYYY-MM-DD&service=...
"""
from __future__ import annotations

import json
from datetime import date as date_cls, datetime, timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import IntegrityError
from django.http import HttpResponse, JsonResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.text import slugify
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from apps.bookings.models import Booking, BookingLink
from apps.bookings.slots import free_slots


# ── User-side management ────────────────────────────────────────────────────


@login_required
def bookings_list(request):
    links = (
        BookingLink.objects.filter(user=request.user)
        .order_by("-created_at")
    )
    recent = (
        Booking.objects.filter(booking_link__user=request.user)
        .select_related("booking_link")
        .order_by("-created_at")[:20]
    )
    upcoming = (
        Booking.objects.filter(
            booking_link__user=request.user,
            status__in=[Booking.Status.CONFIRMED, Booking.Status.PENDING],
            scheduled_at__gte=timezone.now(),
        )
        .select_related("booking_link")
        .order_by("scheduled_at")[:10]
    )
    return render(request, "bookings/list.html", {
        "links": links,
        "recent": recent,
        "upcoming": upcoming,
        "page_title": "Bookings",
    })


@login_required
def link_create(request):
    if request.method == "POST":
        label = (request.POST.get("label") or "").strip()
        if not label:
            messages.error(request, "Give your booking page a name.")
            return redirect("bookings:link_create")

        slug_base = slugify(request.POST.get("slug") or request.user.username or label)[:36]
        slug = slug_base
        i = 2
        while BookingLink.objects.filter(slug=slug).exists():
            slug = f"{slug_base}-{i}"[:40]
            i += 1

        industry = request.POST.get("industry_template", "generic")
        if industry not in dict(BookingLink.IndustryTemplate.choices):
            industry = "generic"

        services = _parse_services(request.POST)

        link = BookingLink.objects.create(
            user=request.user,
            slug=slug,
            label=label,
            industry_template=industry,
            services=services,
            owner_whatsapp=(request.POST.get("owner_whatsapp") or "").strip(),
            owner_email=(request.POST.get("owner_email") or "").strip(),
        )
        link.working_hours = link.default_working_hours()
        link.save(update_fields=["working_hours"])

        messages.success(request, f"Created booking page: {link.label}")
        return redirect("bookings:link_detail", pk=link.pk)

    return render(request, "bookings/link_form.html", {
        "industries": BookingLink.IndustryTemplate.choices,
        "page_title": "New Booking Page",
    })


@login_required
def link_detail(request, pk):
    link = get_object_or_404(BookingLink, pk=pk, user=request.user)

    if request.method == "POST":
        link.label = (request.POST.get("label") or link.label).strip()[:200]
        link.owner_whatsapp = (request.POST.get("owner_whatsapp") or "").strip()
        link.owner_email = (request.POST.get("owner_email") or "").strip()
        link.advance_notice_minutes = int(
            request.POST.get("advance_notice_minutes") or link.advance_notice_minutes
        )
        link.max_advance_days = int(
            request.POST.get("max_advance_days") or link.max_advance_days
        )
        services = _parse_services(request.POST)
        if services:
            link.services = services

        # Optional working_hours JSON pasted from the form
        wh_raw = (request.POST.get("working_hours_json") or "").strip()
        if wh_raw:
            try:
                link.working_hours = json.loads(wh_raw)
            except json.JSONDecodeError:
                messages.error(request, "Working hours JSON is invalid — kept previous.")

        link.save()
        messages.success(request, "Saved.")
        return redirect("bookings:link_detail", pk=link.pk)

    public_url = request.build_absolute_uri(
        reverse("bookings:public_book", kwargs={"slug": link.slug})
    )
    return render(request, "bookings/link_form.html", {
        "link": link,
        "public_url": public_url,
        "industries": BookingLink.IndustryTemplate.choices,
        "page_title": link.label,
        "is_edit": True,
    })


@login_required
def link_calendar(request, pk):
    link = get_object_or_404(BookingLink, pk=pk, user=request.user)
    today = timezone.localdate()
    days_ahead = 14
    days = []
    for offset in range(days_ahead):
        d = today + timedelta(days=offset)
        days.append({
            "date": d,
            "bookings": list(
                link.bookings.filter(
                    scheduled_at__date=d,
                    status__in=[
                        Booking.Status.CONFIRMED, Booking.Status.PENDING,
                        Booking.Status.COMPLETED,
                    ],
                ).order_by("scheduled_at")
            ),
        })
    return render(request, "bookings/link_calendar.html", {
        "link": link,
        "days": days,
        "page_title": f"{link.label} · Calendar",
    })


@login_required
def booking_detail(request, pk):
    booking = get_object_or_404(
        Booking.objects.select_related("booking_link"),
        pk=pk, booking_link__user=request.user,
    )
    return render(request, "bookings/detail.html", {
        "booking": booking,
        "page_title": str(booking),
    })


@login_required
@require_POST
def booking_complete(request, pk):
    booking = get_object_or_404(
        Booking, pk=pk, booking_link__user=request.user,
    )
    booking.status = Booking.Status.COMPLETED
    booking.completed_at = timezone.now()
    booking.save(update_fields=["status", "completed_at"])
    messages.success(request, "Marked completed.")
    return redirect("bookings:booking_detail", pk=booking.pk)


@login_required
@require_POST
def booking_cancel(request, pk):
    booking = get_object_or_404(
        Booking, pk=pk, booking_link__user=request.user,
    )
    booking.status = Booking.Status.CANCELLED
    booking.save(update_fields=["status"])
    messages.success(request, "Cancelled.")
    return redirect("bookings:booking_detail", pk=booking.pk)


# ── Slot data endpoint ──────────────────────────────────────────────────────


@require_GET
def slots_for_date(request, pk):
    """JSON: free start times on a date for a given service duration.

    Public — anyone with the BookingLink ID can query slots. The slug
    is also acceptable; we just need to know which link.
    """
    link = get_object_or_404(BookingLink, pk=pk, is_active=True)
    raw_date = request.GET.get("date", "")
    try:
        on_date = datetime.strptime(raw_date, "%Y-%m-%d").date()
    except ValueError:
        return HttpResponseBadRequest("date must be YYYY-MM-DD")
    try:
        duration = int(request.GET.get("duration", "60"))
    except ValueError:
        duration = 60
    slots = free_slots(link, on_date, duration_minutes=duration)
    return JsonResponse({
        "date": raw_date,
        "duration_minutes": duration,
        "slots": [s.isoformat() for s in slots],
    })


# ── Public booking flow ─────────────────────────────────────────────────────


@require_GET
def public_book(request, slug):
    """The mobile-first booking page customers tap into."""
    link = get_object_or_404(BookingLink, slug=slug, is_active=True)
    profile = getattr(link.user, "profile", None)
    return render(request, "bookings/public/book.html", {
        "link": link,
        "services": link.services or [],
        "brand_name": (profile.company_name if profile else "") or link.label,
        "brand_logo": (profile.brand_logo_url if profile else ""),
        "max_advance_days": link.max_advance_days,
    })


@csrf_exempt
@require_POST
def public_confirm(request, slug):
    """POST: create the Booking. CSRF-exempt because public unauthenticated."""
    link = get_object_or_404(BookingLink, slug=slug, is_active=True)

    customer_name = (request.POST.get("customer_name") or "").strip()[:120]
    customer_phone = (request.POST.get("customer_phone") or "").strip()[:20]
    customer_email = (request.POST.get("customer_email") or "").strip()[:254]
    service_name = (request.POST.get("service_name") or "").strip()[:200]
    scheduled_iso = (request.POST.get("scheduled_at") or "").strip()
    source = (request.POST.get("source_channel") or "direct").strip()[:40]

    if not customer_name or not customer_phone or not service_name or not scheduled_iso:
        return HttpResponseBadRequest("Missing required fields.")

    try:
        scheduled_at = datetime.fromisoformat(scheduled_iso)
        if timezone.is_naive(scheduled_at):
            scheduled_at = timezone.make_aware(scheduled_at, timezone.get_current_timezone())
    except ValueError:
        return HttpResponseBadRequest("scheduled_at must be ISO format.")

    # Snapshot price + duration from the service catalog
    service = next(
        (s for s in (link.services or []) if s.get("name") == service_name),
        None,
    )
    if not service:
        return HttpResponseBadRequest("Unknown service.")
    duration = int(service.get("duration_minutes") or 60)
    price = Decimal(str(service.get("price_kes") or 0))

    # Re-check the slot is actually free
    available = free_slots(link, scheduled_at.date(), duration_minutes=duration)
    if not any(s.replace(microsecond=0) == scheduled_at.replace(microsecond=0) for s in available):
        return HttpResponseBadRequest(
            "That time isn't available anymore — please pick another."
        )

    try:
        booking = Booking.objects.create(
            booking_link=link,
            customer_name=customer_name,
            customer_phone=customer_phone,
            customer_email=customer_email,
            service_name=service_name,
            duration_minutes=duration,
            price_kes=price,
            scheduled_at=scheduled_at,
            status=Booking.Status.CONFIRMED,
            source_channel=source,
            confirmed_at=timezone.now(),
        )
    except IntegrityError:
        return HttpResponseBadRequest(
            "That slot was just taken — please pick another time."
        )

    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return JsonResponse({
            "ok": True,
            "booking_id": str(booking.id),
            "done_url": reverse("bookings:public_done", kwargs={
                "slug": slug, "bid": booking.pk,
            }),
        })
    return redirect("bookings:public_done", slug=slug, bid=booking.pk)


@require_GET
def public_done(request, slug, bid):
    link = get_object_or_404(BookingLink, slug=slug, is_active=True)
    booking = get_object_or_404(Booking, pk=bid, booking_link=link)
    return render(request, "bookings/public/confirm.html", {
        "link": link,
        "booking": booking,
    })


# ── helpers ─────────────────────────────────────────────────────────────────


def _parse_services(post) -> list[dict]:
    """Parse repeated `service_name[]`, `service_duration[]`, `service_price[]`
    inputs into a clean list."""
    names = post.getlist("service_name[]")
    durations = post.getlist("service_duration[]")
    prices = post.getlist("service_price[]")
    services = []
    for name, dur, price in zip(names, durations, prices):
        name = (name or "").strip()[:200]
        if not name:
            continue
        try:
            d = int(dur or 60)
        except ValueError:
            d = 60
        try:
            p = float(price or 0)
        except ValueError:
            p = 0
        services.append({
            "name": name,
            "duration_minutes": max(15, min(d, 600)),
            "price_kes": p,
        })
    return services
