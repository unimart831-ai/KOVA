"""
Tests for Phase 3 work:
  - engagement_history_multiplier (real implementation)
  - Notifications on draft-ready
  - Holiday refine view (GET + POST)
  - Custom event edit view
"""
from datetime import date, timedelta
from unittest.mock import patch, MagicMock
import json
import uuid

import pytest

from apps.accounts.models import User, UserProfile
from apps.calendar_intel.models import (
    CustomEvent,
    Holiday,
    HolidayDraft,
    HolidayOccurrence,
    UserHolidayPreference,
)
from apps.calendar_intel.relevance import engagement_history_multiplier


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────
@pytest.fixture
def rw_user(db):
    u = User.objects.create_user(
        username=f"p3_{uuid.uuid4().hex[:8]}",
        email=f"p3_{uuid.uuid4().hex[:8]}@kova.test",
        password="TestPass123!",
    )
    u.onboarding_completed = True
    u.save()
    UserProfile.objects.filter(user=u).update(country="RW", industry="food_restaurant")
    return User.objects.get(pk=u.pk)


@pytest.fixture
def rw_user_with_ig(rw_user, db):
    from apps.platforms.models import SocialAccount
    SocialAccount.objects.create(
        user=rw_user, platform="instagram",
        username=f"ig_{uuid.uuid4().hex[:6]}",
        is_active=True, access_token="x",
    )
    return rw_user


@pytest.fixture
def holiday_with_occurrence(db):
    h = Holiday.objects.create(
        name="Test Mother's Day", slug=f"test-mday-{uuid.uuid4().hex[:6]}",
        date_type="nth_weekday",
        date_config={"month": 5, "weekday": 6, "n": 2},
        countries=["RW"],
        category="cultural",
        sensitivity_level="safe",
        default_relevance_score=80,
        suggested_post_count=2,
        lead_time_days=9,
        tone_hint="warm",
        industries=["f_and_b"],
        angles=["Honor a specific mother"],
        is_active=True,
    )
    HolidayOccurrence.objects.create(holiday=h, year=2026, date=date(2026, 5, 10))
    return h


# ──────────────────────────────────────────────────────────────────────────
# Engagement history multiplier
# ──────────────────────────────────────────────────────────────────────────
def test_engagement_history_no_past_posts_returns_neutral(holiday_with_occurrence, rw_user):
    assert engagement_history_multiplier(holiday_with_occurrence, rw_user) == 1.0


def test_engagement_history_boosts_winners(holiday_with_occurrence, rw_user_with_ig):
    """Past holiday posts averaging 15+ above baseline → 1.3x boost."""
    from apps.content.models import Post
    from apps.analytics.models import PostMetric
    from apps.platforms.models import SocialAccount

    sa = SocialAccount.objects.filter(user=rw_user_with_ig).first()

    # Create the baseline first: a regular published post with score=50
    base_post = Post.objects.create(
        user=rw_user_with_ig, social_account=sa, platform="instagram",
        content_text="regular post", status="published",
    )
    PostMetric.objects.create(post=base_post, actual_score=50.0)

    # Now a past holiday post that overperformed (score=80, baseline=avg of 50/80=65)
    # Actually for the multiplier we want past avg - baseline >= 15.
    # past_avg=80, baseline=(50+80)/2=65, delta=15 → 1.3x
    occ = HolidayOccurrence.objects.filter(holiday=holiday_with_occurrence).first()
    draft = HolidayDraft.objects.create(
        user=rw_user_with_ig,
        holiday_occurrence=occ,
        target_date=occ.date,
        relevance_score=80,
        status=HolidayDraft.Status.APPROVED,
    )
    hpost = Post.objects.create(
        user=rw_user_with_ig, social_account=sa, platform="instagram",
        content_text="holiday post",
        status="published",
        generated_by_agent="holiday_watcher",
    )
    PostMetric.objects.create(post=hpost, actual_score=80.0)
    draft.posts_generated.add(hpost)

    mult = engagement_history_multiplier(holiday_with_occurrence, rw_user_with_ig)
    assert mult == 1.3


def test_engagement_history_dampens_flops(holiday_with_occurrence, rw_user_with_ig):
    """Past holiday posts averaging 15+ below baseline → 0.7x dampen."""
    from apps.content.models import Post
    from apps.analytics.models import PostMetric
    from apps.platforms.models import SocialAccount

    sa = SocialAccount.objects.filter(user=rw_user_with_ig).first()

    # Baseline = 70
    base = Post.objects.create(
        user=rw_user_with_ig, social_account=sa, platform="instagram",
        content_text="regular", status="published",
    )
    PostMetric.objects.create(post=base, actual_score=70.0)

    # Holiday post = 30, baseline (avg incl this) = 50, delta = -20 → 0.7x
    occ = HolidayOccurrence.objects.filter(holiday=holiday_with_occurrence).first()
    draft = HolidayDraft.objects.create(
        user=rw_user_with_ig,
        holiday_occurrence=occ,
        target_date=occ.date,
        relevance_score=80,
        status=HolidayDraft.Status.APPROVED,
    )
    hpost = Post.objects.create(
        user=rw_user_with_ig, social_account=sa, platform="instagram",
        content_text="holiday", status="published",
        generated_by_agent="holiday_watcher",
    )
    PostMetric.objects.create(post=hpost, actual_score=30.0)
    draft.posts_generated.add(hpost)

    mult = engagement_history_multiplier(holiday_with_occurrence, rw_user_with_ig)
    assert mult == 0.7


def test_engagement_history_neutral_when_close_to_baseline(holiday_with_occurrence, rw_user_with_ig):
    """Past holiday posts within ±15 of baseline → 1.0x (no strong signal)."""
    from apps.content.models import Post
    from apps.analytics.models import PostMetric
    from apps.platforms.models import SocialAccount

    sa = SocialAccount.objects.filter(user=rw_user_with_ig).first()

    base = Post.objects.create(
        user=rw_user_with_ig, social_account=sa, platform="instagram",
        content_text="r", status="published",
    )
    PostMetric.objects.create(post=base, actual_score=55.0)

    occ = HolidayOccurrence.objects.filter(holiday=holiday_with_occurrence).first()
    draft = HolidayDraft.objects.create(
        user=rw_user_with_ig, holiday_occurrence=occ, target_date=occ.date,
        relevance_score=80, status=HolidayDraft.Status.APPROVED,
    )
    hpost = Post.objects.create(
        user=rw_user_with_ig, social_account=sa, platform="instagram",
        content_text="h", status="published",
        generated_by_agent="holiday_watcher",
    )
    PostMetric.objects.create(post=hpost, actual_score=60.0)
    draft.posts_generated.add(hpost)

    mult = engagement_history_multiplier(holiday_with_occurrence, rw_user_with_ig)
    assert mult == 1.0


# ──────────────────────────────────────────────────────────────────────────
# Notifications on draft-ready
# ──────────────────────────────────────────────────────────────────────────
def test_generator_creates_notification_on_success(holiday_with_occurrence, rw_user_with_ig):
    from apps.calendar_intel.generator import generate_drafts_for_holiday_draft
    from apps.notifications.models import Notification

    occ = HolidayOccurrence.objects.filter(holiday=holiday_with_occurrence).first()
    draft = HolidayDraft.objects.create(
        user=rw_user_with_ig, holiday_occurrence=occ, target_date=occ.date,
        relevance_score=80, status=HolidayDraft.Status.QUEUED,
    )
    fake = MagicMock()
    fake.content = json.dumps({
        "drafts": [{
            "angle_used": "Honor a specific mother",
            "rationale": "good angle",
            "platform_versions": {
                "instagram": "For the moms who fill the kitchen with stories — our briquettes burn long enough for the whole evening of memories.",
            },
        }],
    })
    fake.input_tokens = 100; fake.output_tokens = 200

    n_before = Notification.objects.filter(user=rw_user_with_ig).count()

    with patch("apps.calendar_intel.generator.llm_generate", return_value=fake), \
         patch("apps.calendar_intel.generator.get_model_for_task", return_value="claude-sonnet-4-6"):
        count = generate_drafts_for_holiday_draft(draft.id)

    assert count == 1
    n_after = Notification.objects.filter(user=rw_user_with_ig).count()
    assert n_after == n_before + 1
    n = Notification.objects.filter(user=rw_user_with_ig).order_by("-created_at").first()
    assert "Test Mother's Day" in n.message
    assert "draft" in n.message.lower()


def test_generator_no_notification_on_failure(holiday_with_occurrence, rw_user_with_ig):
    """When generation fails (empty LLM), no notification fires."""
    from apps.calendar_intel.generator import generate_drafts_for_holiday_draft
    from apps.notifications.models import Notification

    occ = HolidayOccurrence.objects.filter(holiday=holiday_with_occurrence).first()
    draft = HolidayDraft.objects.create(
        user=rw_user_with_ig, holiday_occurrence=occ, target_date=occ.date,
        relevance_score=80, status=HolidayDraft.Status.QUEUED,
    )
    empty = MagicMock(); empty.content = ""

    n_before = Notification.objects.filter(user=rw_user_with_ig).count()
    with patch("apps.calendar_intel.generator.llm_generate", return_value=empty), \
         patch("apps.calendar_intel.generator.get_model_for_task", return_value="claude-sonnet-4-6"):
        generate_drafts_for_holiday_draft(draft.id)
    n_after = Notification.objects.filter(user=rw_user_with_ig).count()
    assert n_after == n_before


# ──────────────────────────────────────────────────────────────────────────
# Holiday refine view
# ──────────────────────────────────────────────────────────────────────────
def test_holiday_refine_get_renders(client, holiday_with_occurrence, rw_user_with_ig):
    client.force_login(rw_user_with_ig)
    resp = client.get(f"/calendar/preferences/{holiday_with_occurrence.id}/refine/")
    assert resp.status_code == 200
    body = resp.content.decode()
    # Apostrophe in 'Mother's Day' is HTML-escaped to &#x27; — match the
    # safe parts of the name plus the form sections.
    assert "Test Mother" in body and "Day" in body
    assert "Lead time" in body
    assert "Posts to draft" in body
    assert "Your personal angles" in body


def test_holiday_refine_post_creates_preference(client, holiday_with_occurrence, rw_user_with_ig):
    client.force_login(rw_user_with_ig)
    assert not UserHolidayPreference.objects.filter(
        user=rw_user_with_ig, holiday=holiday_with_occurrence,
    ).exists()

    resp = client.post(
        f"/calendar/preferences/{holiday_with_occurrence.id}/refine/",
        {
            "is_enabled": "on",
            "auto_draft_posts": "on",
            "custom_lead_time_days": "14",
            "custom_post_count": "3",
            "custom_relevance_score": "95",
            "personal_angles": "My personal angle one\nMy personal angle two",
        },
    )
    assert resp.status_code == 302  # redirect after save
    pref = UserHolidayPreference.objects.get(
        user=rw_user_with_ig, holiday=holiday_with_occurrence,
    )
    assert pref.is_enabled
    assert pref.auto_draft_posts
    assert pref.custom_lead_time_days == 14
    assert pref.custom_post_count == 3
    assert pref.custom_relevance_score == 95
    assert "My personal angle one" in pref.notes


def test_holiday_refine_post_clears_blank_customs(client, holiday_with_occurrence, rw_user_with_ig):
    """Blank inputs should null out the custom fields, falling back to Holiday defaults."""
    client.force_login(rw_user_with_ig)
    UserHolidayPreference.objects.create(
        user=rw_user_with_ig, holiday=holiday_with_occurrence,
        is_enabled=True,
        custom_lead_time_days=14,
        custom_post_count=3,
    )
    client.post(
        f"/calendar/preferences/{holiday_with_occurrence.id}/refine/",
        {
            "is_enabled": "on",
            "auto_draft_posts": "on",
            "custom_lead_time_days": "",
            "custom_post_count": "",
            "custom_relevance_score": "",
            "personal_angles": "",
        },
    )
    pref = UserHolidayPreference.objects.get(
        user=rw_user_with_ig, holiday=holiday_with_occurrence,
    )
    assert pref.custom_lead_time_days is None
    assert pref.custom_post_count is None
    assert pref.custom_relevance_score is None


# ──────────────────────────────────────────────────────────────────────────
# Custom event edit
# ──────────────────────────────────────────────────────────────────────────
def test_custom_event_edit_get_prefills_form(client, rw_user_with_ig):
    client.force_login(rw_user_with_ig)
    ev = CustomEvent.objects.create(
        user=rw_user_with_ig,
        name="Our anniversary",
        date=date(2026, 5, 15),
        recurrence="yearly",
        description="Founded 2024",
    )
    resp = client.get(f"/calendar/custom/{ev.id}/edit/")
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "Our anniversary" in body
    assert "Edit moment" in body
    assert "2026-05-15" in body


def test_custom_event_edit_post_updates(client, rw_user_with_ig):
    client.force_login(rw_user_with_ig)
    ev = CustomEvent.objects.create(
        user=rw_user_with_ig,
        name="Old name",
        date=date(2026, 5, 15),
        recurrence="yearly",
    )
    resp = client.post(f"/calendar/custom/{ev.id}/edit/", {
        "name": "New name",
        "date": "2026-06-20",
        "recurrence": "once",
        "description": "Updated",
    })
    assert resp.status_code == 302
    ev.refresh_from_db()
    assert ev.name == "New name"
    assert ev.date == date(2026, 6, 20)
    assert ev.recurrence == "once"
    assert ev.description == "Updated"


def test_custom_event_edit_cannot_access_others(client, rw_user_with_ig, db):
    """A user must not be able to edit another user's custom event."""
    other = User.objects.create_user(
        username=f"other_{uuid.uuid4().hex[:6]}",
        email=f"other_{uuid.uuid4().hex[:6]}@kova.test",
        password="x",
    )
    ev = CustomEvent.objects.create(
        user=other, name="Other's event", date=date(2026, 5, 15),
    )
    client.force_login(rw_user_with_ig)
    resp = client.get(f"/calendar/custom/{ev.id}/edit/")
    assert resp.status_code == 404
