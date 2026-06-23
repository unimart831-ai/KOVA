"""Tests for blueprint post-renderers."""

from __future__ import annotations

import pytest

from apps.accounts.models import User, UserProfile
from apps.bookings.models import BookingLink
from apps.content.renderers import (
    apply_blueprint_renderer,
    blueprint_quality_score,
    compose_content_from_slots,
    extract_slots_from_content,
)


@pytest.fixture
def user(db):
    u = User.objects.create_user(username="r", email="r@kova.ai", password="x")
    UserProfile.objects.filter(user=u).update(company_name="Glow Salon", business_model="service")
    BookingLink.objects.create(
        user=u,
        slug="glow-salon",
        label="Glow Salon",
        services=[{"name": "Haircut", "duration_minutes": 45, "price_kes": 1500}],
        working_hours={"mon": [{"start": "09:00", "end": "18:00"}]},
    )
    return u


def test_extract_and_compose_instagram_slots():
    text = "Fresh fades today\nBook your slot.\n#nairobi #salon"
    slots = extract_slots_from_content(text, "instagram")
    assert slots["hook"] == "Fresh fades today"
    assert "#nairobi" in slots["hashtags"]
    rebuilt = compose_content_from_slots(slots, "instagram")
    assert "Fresh fades" in rebuilt


def test_apply_blueprint_adds_booking_cta(user):
    blueprint = {
        "objective": "book",
        "asset_type": "service",
        "title": "Haircut",
        "platforms": [{"platform": "instagram", "format": "feed", "slots": {}}],
        "metadata": {},
    }
    pd = {"platform": "instagram", "content_text": "Walk-ins welcome this week."}
    out = apply_blueprint_renderer(pd, blueprint, user)
    assert "book" in out["content_text"].lower()
    assert out.get("post_format") == "image"
    score = blueprint_quality_score(out, blueprint)
    assert score >= 55


def test_quality_score_low_without_content():
    blueprint = {
        "objective": "sell",
        "asset_type": "product",
        "platforms": [{"platform": "facebook", "format": "feed", "slots": {}}],
    }
    pd = {"platform": "facebook", "content_text": "Hi"}
    score = blueprint_quality_score(pd, blueprint)
    assert score < 70
