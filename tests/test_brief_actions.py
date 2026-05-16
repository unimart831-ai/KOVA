"""Tests for the action-tense brief data builder (Phase 3 W12).

Covers `_build_action_summary` — the helper that aggregates concrete
agent activity over the last 24 hours so the Daily Brief LLM can
write in AI-first-person ("I auto-replied to 7 comments…").
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.bookings.models import Booking, BookingLink
from apps.briefs.tasks import _build_action_summary
from apps.qr_attribution.models import WalkInEvent
from apps.reviews.models import ReviewRequest


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        username="owner", email="owner@kova.ai", password="x",
        full_name="Test",
    )
    UserProfile.objects.filter(user=u).update(plan="growth")
    return u


class TestActionSummary:
    def test_empty_shape(self, owner):
        s = _build_action_summary(owner)
        assert s["engage"] == {"auto_sent": 0, "escalated": 0, "drafts_pending": 0}
        assert s["walk_ins"] == 0
        assert s["bookings_completed"] == 0
        assert s["reviews"]["scheduled"] == 0

    def test_walkins_in_window(self, owner):
        WalkInEvent.objects.create(
            user=owner, attribution_source="instagram", revenue=Decimal("3000"),
        )
        WalkInEvent.objects.create(
            user=owner, attribution_source="flyer", revenue=Decimal("1500"),
        )
        s = _build_action_summary(owner)
        assert s["walk_ins"] == 2

    def test_completed_bookings_in_window(self, owner):
        link = BookingLink.objects.create(
            user=owner, slug="x", label="X",
            services=[{"name": "S", "duration_minutes": 60, "price_kes": 1000}],
        )
        b = Booking.objects.create(
            booking_link=link,
            customer_name="A", customer_phone="x",
            service_name="S", duration_minutes=60, price_kes=Decimal("1000"),
            scheduled_at=timezone.now() - timedelta(hours=4),
            status="completed",
            completed_at=timezone.now() - timedelta(hours=2),
        )
        s = _build_action_summary(owner)
        assert s["bookings_completed"] == 1

    def test_old_bookings_excluded(self, owner):
        link = BookingLink.objects.create(
            user=owner, slug="x", label="X",
            services=[{"name": "S", "duration_minutes": 60, "price_kes": 1000}],
        )
        Booking.objects.create(
            booking_link=link,
            customer_name="old", customer_phone="x",
            service_name="S", duration_minutes=60, price_kes=Decimal("1000"),
            scheduled_at=timezone.now() - timedelta(days=10),
            status="completed",
            completed_at=timezone.now() - timedelta(days=5),
        )
        s = _build_action_summary(owner)
        assert s["bookings_completed"] == 0

    def test_negative_review_escalations_surface(self, owner):
        # Create a responded negative review escalation
        rr = ReviewRequest.objects.create(
            user=owner,
            customer_name="Mary",
            customer_phone="254700000000",
            scheduled_at=timezone.now(),
            status=ReviewRequest.Status.RESPONDED,
            sentiment=ReviewRequest.Sentiment.NEGATIVE,
            response_text="Service was slow and rude",
            responded_at=timezone.now() - timedelta(hours=2),
            escalated_in_brief=True,
        )
        s = _build_action_summary(owner)
        neg = s["reviews"]["negative_to_review"]
        assert len(neg) == 1
        assert neg[0]["customer"] == "Mary"
        assert "Service was slow" in neg[0]["preview"]

    def test_positive_review_seeded_count(self, owner):
        from apps.content.models import ContentSeed
        seed = ContentSeed.objects.create(user=owner, idea="testimonial")
        ReviewRequest.objects.create(
            user=owner,
            customer_name="Happy",
            customer_phone="x",
            scheduled_at=timezone.now(),
            status=ReviewRequest.Status.RESPONDED,
            sentiment=ReviewRequest.Sentiment.POSITIVE,
            response_text="Loved it!",
            content_seed=seed,
            responded_at=timezone.now() - timedelta(hours=3),
        )
        s = _build_action_summary(owner)
        assert s["reviews"]["positive_seeds"] == 1
