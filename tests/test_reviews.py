"""Tests for the review request loop (Phase 3 W9).

Covers:
  * Sentiment classifier
  * Auto-schedule on Lead.status=converted + Booking.status=completed
  * send_review_request happy path + email fallback
  * send_due_review_requests batch task
  * process_response: positive → ContentSeed; negative → escalated flag
  * Public response webhook
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.accounts.models import User, UserProfile
from apps.commerce.bookings.models import Booking, BookingLink
from apps.commerce.leads.models import Lead
from apps.commerce.reviews.models import ReviewRequest
from apps.commerce.reviews.sentiment import classify
from apps.commerce.reviews.services import process_response, send_review_request
from apps.commerce.reviews.tasks import send_due_review_requests


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture
def owner(db):
    u = User.objects.create_user(
        username="owner",
        email="owner@kova.ai",
        password="OwnerPass123!",
        full_name="Test Owner",
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
    l = BookingLink.objects.create(
        user=owner, slug="testbiz", label="Book us",
        services=[{"name": "Braids", "duration_minutes": 180, "price_kes": 3500}],
    )
    l.working_hours = l.default_working_hours()
    l.save()
    return l


# ── Sentiment ──────────────────────────────────────────────────────────────


class TestSentiment:
    @pytest.mark.parametrize("text", [
        "Great service, loved it!",
        "Asante sana, vizuri sana",
        "Perfect ❤",
        "5/5 best salon in town",
    ])
    def test_positive(self, text):
        label, score = classify(text)
        assert label == "positive"
        assert score >= 0.5

    @pytest.mark.parametrize("text", [
        "Terrible experience, never again",
        "Slow and rude staff, awful",
        "Mbaya sana, sijaridhika",
        "1/5 worst service",
    ])
    def test_negative(self, text):
        label, score = classify(text)
        assert label == "negative"

    def test_empty(self):
        label, score = classify("")
        assert label == "neutral"


# ── Auto-schedule signals ──────────────────────────────────────────────────


class TestAutoSchedule:
    def test_lead_converted_creates_review(self, owner):
        lead = Lead.objects.create(
            user=owner, email="c@x.com", name="Customer", phone="254700000000",
        )
        assert ReviewRequest.objects.filter(lead=lead).count() == 0
        lead.status = Lead.Status.CONVERTED
        lead.save()
        assert ReviewRequest.objects.filter(lead=lead).count() == 1

    def test_lead_other_status_no_review(self, owner):
        lead = Lead.objects.create(
            user=owner, email="c@x.com", name="Customer",
        )
        lead.status = Lead.Status.QUALIFIED
        lead.save()
        assert ReviewRequest.objects.filter(lead=lead).count() == 0

    def test_booking_completed_creates_review(self, owner, link):
        b = Booking.objects.create(
            booking_link=link,
            customer_name="Mary", customer_phone="254712345678",
            service_name="Braids", duration_minutes=180,
            price_kes=Decimal("3500"),
            scheduled_at=timezone.now() + timedelta(days=2),
            status="confirmed",
        )
        # Now complete
        b.status = "completed"
        b.completed_at = timezone.now()
        b.save()
        assert ReviewRequest.objects.filter(booking=b).count() == 1
        rr = ReviewRequest.objects.get(booking=b)
        assert rr.channel == ReviewRequest.Channel.WHATSAPP
        assert rr.customer_phone == "254712345678"

    def test_double_save_does_not_duplicate(self, owner):
        lead = Lead.objects.create(user=owner, email="c@x.com")
        lead.status = "converted"
        lead.save()
        lead.save()  # save again
        assert ReviewRequest.objects.filter(lead=lead).count() == 1


# ── Send + batch task ──────────────────────────────────────────────────────


class TestSendReviewRequest:
    def test_send_marks_sent(self, owner):
        # Give the request an email so the email fallback fires when WA
        # isn't configured in the test environment — status should be SENT.
        req = ReviewRequest.objects.create(
            user=owner, customer_name="Mary",
            customer_phone="254712345678",
            customer_email="mary@test.com",
            scheduled_at=timezone.now(),
        )
        send_review_request(req)
        req.refresh_from_db()
        assert req.status == ReviewRequest.Status.SENT
        assert req.sent_at is not None

    def test_batch_picks_up_due(self, owner):
        req = ReviewRequest.objects.create(
            user=owner, customer_name="A", customer_phone="254700000000",
            customer_email="a@test.com",
            scheduled_at=timezone.now() - timedelta(minutes=5),
        )
        future = ReviewRequest.objects.create(
            user=owner, customer_name="B", customer_phone="254700000001",
            customer_email="b@test.com",
            scheduled_at=timezone.now() + timedelta(hours=12),
        )
        sent = send_due_review_requests()
        assert sent == 1
        req.refresh_from_db()
        future.refresh_from_db()
        assert req.status == ReviewRequest.Status.SENT
        assert future.status == ReviewRequest.Status.PENDING


# ── Response processing ────────────────────────────────────────────────────


class TestProcessResponse:
    def test_positive_creates_content_seed(self, owner):
        req = ReviewRequest.objects.create(
            user=owner, customer_name="Mary",
            customer_phone="254700000000",
            scheduled_at=timezone.now(),
            status=ReviewRequest.Status.SENT,
        )
        process_response(req, "Asante sana, vizuri sana! Loved it ❤")
        req.refresh_from_db()
        assert req.sentiment == ReviewRequest.Sentiment.POSITIVE
        assert req.content_seed is not None
        assert "testimonial" in req.content_seed.idea.lower()

    def test_negative_flags_for_brief(self, owner):
        req = ReviewRequest.objects.create(
            user=owner, customer_name="X",
            customer_phone="254700000000",
            scheduled_at=timezone.now(),
            status=ReviewRequest.Status.SENT,
        )
        process_response(req, "Terrible service, never again")
        req.refresh_from_db()
        assert req.sentiment == ReviewRequest.Sentiment.NEGATIVE
        assert req.escalated_in_brief is True
        assert req.content_seed is None


# ── Views ──────────────────────────────────────────────────────────────────


class TestViews:
    def test_list_requires_login(self, client):
        assert client.get(reverse("reviews:list")).status_code in (302, 401)

    def test_list_shows_users_reviews(self, owner, owner_client):
        req = ReviewRequest.objects.create(
            user=owner, customer_name="Mary",
            customer_phone="254700000000",
            scheduled_at=timezone.now(),
        )
        resp = owner_client.get(reverse("reviews:list"))
        assert resp.status_code == 200
        assert b"Mary" in resp.content

    def test_capture_response_public(self, client, owner):
        req = ReviewRequest.objects.create(
            user=owner, customer_name="A", customer_phone="x",
            scheduled_at=timezone.now(),
            status=ReviewRequest.Status.SENT,
        )
        url = reverse("reviews:respond", kwargs={"pk": req.pk})
        resp = client.post(url, {"text": "Perfect, loved it!"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["sentiment"] == "positive"
        req.refresh_from_db()
        assert req.status == ReviewRequest.Status.RESPONDED

    def test_capture_response_blocks_duplicate(self, client, owner):
        req = ReviewRequest.objects.create(
            user=owner, customer_name="A", customer_phone="x",
            scheduled_at=timezone.now(),
            status=ReviewRequest.Status.RESPONDED,
            response_text="already",
        )
        url = reverse("reviews:respond", kwargs={"pk": req.pk})
        resp = client.post(url, {"text": "second attempt"})
        assert resp.status_code == 200
        assert resp.json().get("already") is True

    def test_capture_response_empty_400(self, client, owner):
        req = ReviewRequest.objects.create(
            user=owner, customer_name="A", customer_phone="x",
            scheduled_at=timezone.now(),
        )
        url = reverse("reviews:respond", kwargs={"pk": req.pk})
        assert client.post(url, {"text": ""}).status_code == 400
