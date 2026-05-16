"""Tests for the booking integration app (Phase 2 W7-8).

Covers:
  * Model basics
  * Slot engine — working hours, advance notice, conflict subtraction
  * Public booking flow (book → confirm → done)
  * Owner-side list / detail / status transitions
  * Engage Agent intent detection + reply augmentation
  * Revenue rollup (booking_revenue merges into total_revenue)
  * WhatsApp confirmation signals (stubbed)
"""
from __future__ import annotations

from datetime import datetime, timedelta, time
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.bookings.models import Booking, BookingLink
from apps.bookings.slots import free_slots


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        username="salonowner",
        email="owner@kova.ai",
        password="OwnerPass123!",
        full_name="Salon Owner",
    )
    UserProfile.objects.filter(user=u).update(
        plan="growth", company_name="Test Salon",
    )
    u.onboarding_completed = True
    u.save(update_fields=["onboarding_completed"])
    return u


@pytest.fixture
def owner_client(client, owner):
    client.login(email="owner@kova.ai", password="OwnerPass123!")
    return client


@pytest.fixture
def link(owner):
    link = BookingLink.objects.create(
        user=owner,
        slug="testsalon",
        label="Book at Test Salon",
        industry_template="salon",
        services=[
            {"name": "Box braids", "duration_minutes": 180, "price_kes": 3500},
            {"name": "Cornrows", "duration_minutes": 120, "price_kes": 2000},
        ],
        advance_notice_minutes=60,
        max_advance_days=30,
        owner_whatsapp="254712345678",
    )
    link.working_hours = link.default_working_hours()
    link.save()
    return link


def _next_weekday(weekday: int):
    """Return next date with given weekday (0=Mon)."""
    today = timezone.localdate()
    days = (weekday - today.weekday()) % 7
    if days == 0:
        days = 7
    return today + timedelta(days=days)


# ── Models ─────────────────────────────────────────────────────────────────


class TestBookingLink:
    def test_default_working_hours_has_seven_keys(self, link):
        wh = link.working_hours
        assert set(wh.keys()) == {"mon", "tue", "wed", "thu", "fri", "sat", "sun"}

    def test_str_includes_slug(self, link):
        assert link.slug in str(link)

    def test_unique_slug(self, owner, link):
        with pytest.raises(Exception):
            BookingLink.objects.create(
                user=owner, slug=link.slug, label="dup",
            )


class TestBookingModel:
    def test_user_property_returns_link_owner(self, link, owner):
        b = Booking.objects.create(
            booking_link=link,
            customer_name="A", customer_phone="254700000000",
            service_name="Box braids", duration_minutes=180, price_kes=3500,
            scheduled_at=timezone.now() + timedelta(days=2),
        )
        assert b.user == owner


# ── Slot engine ────────────────────────────────────────────────────────────


class TestSlotEngine:
    def test_no_slots_on_closed_day(self, link):
        # Set sun to closed (default already)
        sunday = _next_weekday(6)
        assert free_slots(link, sunday, duration_minutes=60) == []

    def test_slots_within_working_hours(self, link):
        wednesday = _next_weekday(2)
        slots = free_slots(link, wednesday, duration_minutes=60, granularity_minutes=60)
        # Wed 09:00-18:00 minus a final 60-min that wouldn't fit → 9 slots
        assert len(slots) >= 8
        assert all(s.hour >= 9 and s.hour <= 17 for s in slots)

    def test_busy_interval_subtracts_slots(self, link):
        wednesday = _next_weekday(2)
        block_start = timezone.make_aware(
            datetime.combine(wednesday, time(10, 0)),
            timezone.get_current_timezone(),
        )
        Booking.objects.create(
            booking_link=link,
            customer_name="busy", customer_phone="x",
            service_name="Box braids", duration_minutes=120, price_kes=0,
            scheduled_at=block_start,
        )
        slots = free_slots(link, wednesday, duration_minutes=60, granularity_minutes=60)
        # 10:00, 11:00 should be removed by the 2h block
        hours = {s.hour for s in slots}
        assert 10 not in hours
        assert 11 not in hours

    def test_advance_notice_drops_too_soon(self, link):
        # Find a working day at least 2 days out so we have slots, then
        # bump advance_notice to 7 days
        link.advance_notice_minutes = 60 * 24 * 7
        link.save(update_fields=["advance_notice_minutes"])
        wednesday = _next_weekday(2)
        slots = free_slots(link, wednesday, duration_minutes=60)
        assert slots == []

    def test_max_advance_blocks_far_dates(self, link):
        link.max_advance_days = 1
        link.save(update_fields=["max_advance_days"])
        far = timezone.localdate() + timedelta(days=10)
        assert free_slots(link, far, duration_minutes=60) == []


# ── Public booking flow ────────────────────────────────────────────────────


class TestPublicBookingFlow:
    def test_public_book_page_renders(self, client, link):
        resp = client.get(reverse("bookings:public_book", kwargs={"slug": link.slug}))
        assert resp.status_code == 200
        assert b"Box braids" in resp.content

    def test_public_book_404_for_inactive(self, client, link):
        link.is_active = False
        link.save(update_fields=["is_active"])
        resp = client.get(reverse("bookings:public_book", kwargs={"slug": link.slug}))
        assert resp.status_code == 404

    def test_slots_endpoint_returns_json(self, client, link):
        wednesday = _next_weekday(2)
        url = reverse("bookings:slots", kwargs={"pk": link.pk})
        resp = client.get(f"{url}?date={wednesday.isoformat()}&duration=60")
        assert resp.status_code == 200
        data = resp.json()
        assert "slots" in data
        assert len(data["slots"]) > 0

    def test_confirm_creates_booking(self, client, link):
        wednesday = _next_weekday(2)
        # Pick a real slot from the engine
        slots = free_slots(link, wednesday, duration_minutes=180)
        assert slots, "fixture must produce at least one slot"
        slot = slots[0]
        url = reverse("bookings:public_confirm", kwargs={"slug": link.slug})
        resp = client.post(url, {
            "customer_name": "Mary",
            "customer_phone": "254712345678",
            "customer_email": "mary@example.com",
            "service_name": "Box braids",
            "scheduled_at": slot.isoformat(),
            "source_channel": "qr",
        }, HTTP_X_REQUESTED_WITH="XMLHttpRequest")
        assert resp.status_code == 200, resp.content
        b = Booking.objects.get(booking_link=link)
        assert b.customer_name == "Mary"
        assert b.price_kes == Decimal("3500")
        assert b.source_channel == "qr"

    def test_confirm_rejects_unavailable_slot(self, client, link):
        # Random non-slot time (e.g. 03:00 — outside working hours)
        bad = timezone.now() + timedelta(days=3)
        bad = bad.replace(hour=3, minute=0)
        url = reverse("bookings:public_confirm", kwargs={"slug": link.slug})
        resp = client.post(url, {
            "customer_name": "Mary", "customer_phone": "254700000000",
            "service_name": "Box braids",
            "scheduled_at": bad.isoformat(),
        })
        assert resp.status_code == 400
        assert Booking.objects.filter(booking_link=link).count() == 0

    def test_confirm_unknown_service_400(self, client, link):
        slots = free_slots(link, _next_weekday(2), duration_minutes=60)
        url = reverse("bookings:public_confirm", kwargs={"slug": link.slug})
        resp = client.post(url, {
            "customer_name": "Mary", "customer_phone": "254700000000",
            "service_name": "Massage",  # not in fixture services
            "scheduled_at": slots[0].isoformat() if slots else "",
        })
        assert resp.status_code == 400


# ── Owner-side views ───────────────────────────────────────────────────────


class TestOwnerViews:
    def test_list_requires_login(self, client):
        resp = client.get(reverse("bookings:list"))
        assert resp.status_code in (302, 401)

    def test_list_shows_user_links(self, owner_client, link):
        resp = owner_client.get(reverse("bookings:list"))
        assert resp.status_code == 200
        assert link.label.encode() in resp.content

    def test_link_detail_renders(self, owner_client, link):
        resp = owner_client.get(reverse("bookings:link_detail", kwargs={"pk": link.pk}))
        assert resp.status_code == 200

    def test_link_calendar_renders(self, owner_client, link):
        resp = owner_client.get(reverse("bookings:link_calendar", kwargs={"pk": link.pk}))
        assert resp.status_code == 200

    def test_complete_transitions_status(self, owner_client, link):
        b = Booking.objects.create(
            booking_link=link,
            customer_name="A", customer_phone="x",
            service_name="Box braids", duration_minutes=180, price_kes=3500,
            scheduled_at=timezone.now() + timedelta(days=2),
        )
        owner_client.post(reverse("bookings:booking_complete", kwargs={"pk": b.pk}))
        b.refresh_from_db()
        assert b.status == "completed"
        assert b.completed_at is not None

    def test_cancel_transitions_status(self, owner_client, link):
        b = Booking.objects.create(
            booking_link=link,
            customer_name="A", customer_phone="x",
            service_name="Box braids", duration_minutes=180, price_kes=3500,
            scheduled_at=timezone.now() + timedelta(days=2),
        )
        owner_client.post(reverse("bookings:booking_cancel", kwargs={"pk": b.pk}))
        b.refresh_from_db()
        assert b.status == "cancelled"


# ── Engage Agent intent detection ──────────────────────────────────────────


class TestBookingIntent:
    @pytest.mark.parametrize("msg", [
        "can I book braids saturday?",
        "are you open thursday?",
        "I want an appointment please",
        "any time available tomorrow?",
        "what time is free?",
        "reserve a slot for me",
    ])
    def test_detects_intent(self, msg):
        from apps.agents.booking_intent import detect_booking_intent
        assert detect_booking_intent(msg) is True

    @pytest.mark.parametrize("msg", [
        "love your work!",
        "how much do you charge",
        "where are you located",
        "",
    ])
    def test_no_false_positives(self, msg):
        from apps.agents.booking_intent import detect_booking_intent
        assert detect_booking_intent(msg) is False

    def test_augment_appends_booking_link(self, owner, link):
        from apps.agents.booking_intent import augment_reply_with_booking_link
        out = augment_reply_with_booking_link(
            "Sure! We have slots open.", owner, "can I book?",
        )
        assert link.slug in out
        assert "Tap to book" in out

    def test_augment_skips_when_no_link(self, db):
        from apps.agents.booking_intent import augment_reply_with_booking_link
        u = User.objects.create_user(
            username="noLink", email="nolink@kova.ai", password="x",
        )
        out = augment_reply_with_booking_link("Sure!", u, "book please")
        assert out == "Sure!"

    def test_augment_skips_when_no_intent(self, owner, link):
        from apps.agents.booking_intent import augment_reply_with_booking_link
        out = augment_reply_with_booking_link("Hello!", owner, "thanks!")
        assert out == "Hello!"


# ── Revenue rollup ─────────────────────────────────────────────────────────


class TestRevenueRollup:
    def test_booking_revenue_in_summary(self, owner, link):
        Booking.objects.create(
            booking_link=link,
            customer_name="A", customer_phone="x",
            service_name="Box braids", duration_minutes=180,
            price_kes=Decimal("3500"),
            scheduled_at=timezone.now() + timedelta(days=2),
            status="confirmed",
        )
        Booking.objects.create(
            booking_link=link,
            customer_name="B", customer_phone="y",
            service_name="Cornrows", duration_minutes=120,
            price_kes=Decimal("2000"),
            scheduled_at=timezone.now() + timedelta(days=3),
            status="completed",
        )
        from apps.analytics.revenue import get_revenue_summary
        summary = get_revenue_summary(owner, days=30)
        assert summary["totals"]["booking_revenue"] == Decimal("5500")
        assert summary["totals"]["booking_count"] == 2
        assert summary["totals"]["total_revenue"] == Decimal("5500")

    def test_cancelled_bookings_not_counted(self, owner, link):
        Booking.objects.create(
            booking_link=link,
            customer_name="A", customer_phone="x",
            service_name="Box braids", duration_minutes=180,
            price_kes=Decimal("3500"),
            scheduled_at=timezone.now() + timedelta(days=2),
            status="cancelled",
        )
        from apps.analytics.revenue import get_revenue_summary
        summary = get_revenue_summary(owner, days=30)
        assert summary["totals"]["booking_revenue"] == Decimal("0")


# ── WhatsApp confirmation signal (stubbed) ─────────────────────────────────


class TestConfirmationSignal:
    def test_confirmation_timestamps_set_on_create(self, link):
        b = Booking.objects.create(
            booking_link=link,
            customer_name="A", customer_phone="254712345678",
            service_name="Box braids", duration_minutes=180, price_kes=3500,
            scheduled_at=timezone.now() + timedelta(days=2),
            status="confirmed",
        )
        b.refresh_from_db()
        # The signal stamps both timestamps because the WhatsApp app
        # isn't fully configured in tests — the soft fallback succeeds.
        assert b.customer_confirmation_sent_at is not None
        assert b.owner_confirmation_sent_at is not None

    def test_pending_booking_does_not_send(self, link):
        b = Booking.objects.create(
            booking_link=link,
            customer_name="A", customer_phone="x",
            service_name="Box braids", duration_minutes=180, price_kes=3500,
            scheduled_at=timezone.now() + timedelta(days=2),
            status="pending",
        )
        b.refresh_from_db()
        assert b.customer_confirmation_sent_at is None
        assert b.owner_confirmation_sent_at is None
