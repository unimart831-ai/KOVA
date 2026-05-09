"""
Tests for Phase 2: schemas, quality gates, generator, watcher.

The Claude API call itself is mocked — we verify everything around it.
"""
import json
from datetime import date, timedelta
from unittest.mock import patch, MagicMock

import pytest
from django.utils import timezone

from apps.accounts.models import User, UserProfile
from apps.calendar_intel.models import (
    CustomEvent,
    Holiday,
    HolidayDraft,
    HolidayOccurrence,
)
from apps.calendar_intel.quality_gates import (
    GLOBAL_BANNED_PHRASES,
    check_post_copy,
    filter_passing,
)
from apps.calendar_intel.schemas import (
    HolidayDraftItem,
    HolidayDraftsOutput,
    PlatformVersions,
)


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────
@pytest.fixture
def rw_user_with_account(db):
    """User with country, industry, brand voice, and an active SocialAccount."""
    from apps.platforms.models import SocialAccount
    u = User.objects.create_user(
        username="iranzi_gen",
        email="iranzi_gen@kova.ai",
        password="TestPass123!",
        full_name="Iranzi Gen",
    )
    UserProfile.objects.filter(user=u).update(
        country="RW",
        city="Kigali",
        industry="food_restaurant",
        company_name="Briquettes Co",
        brand_voice="Direct, no-nonsense. Speaks to busy households who care about cost and the environment.",
    )
    SocialAccount.objects.create(
        user=u, platform="instagram", username="briquettesco",
        is_active=True, access_token="fake",
    )
    SocialAccount.objects.create(
        user=u, platform="linkedin", username="briquettes-co",
        is_active=True, access_token="fake",
    )
    return User.objects.get(pk=u.pk)


@pytest.fixture
def mothers_day_occurrence(db):
    h = Holiday.objects.create(
        name="Mother's Day",
        slug="mothers-day-test",
        date_type="nth_weekday",
        date_config={"month": 5, "weekday": 6, "n": 2},
        countries=["RW", "KE", "US"],
        category="cultural",
        sensitivity_level="safe",
        default_relevance_score=80,
        suggested_post_count=2,
        lead_time_days=9,
        tone_hint="warm",
        industries=["retail", "f_and_b"],
        angles=["Honor a specific mother", "A gift idea"],
        avoid_phrases=["Happy Mother's Day to all the moms"],
        is_active=True,
    )
    return HolidayOccurrence.objects.create(
        holiday=h, year=2026, date=date(2026, 5, 10),
    )


# ──────────────────────────────────────────────────────────────────────────
# Schemas
# ──────────────────────────────────────────────────────────────────────────
def test_platform_versions_filters_empty():
    pv = PlatformVersions(instagram="hi", linkedin=None, twitter="", facebook="ok")
    items = pv.items_with_content()
    keys = [k for k, _ in items]
    assert "instagram" in keys
    assert "facebook" in keys
    assert "linkedin" not in keys
    assert "twitter" not in keys


def test_platform_versions_rejects_overlong_twitter():
    """281+ char Twitter copy must fail validation."""
    long_text = "x" * 281
    with pytest.raises(Exception):
        PlatformVersions(twitter=long_text)


def test_holiday_drafts_output_requires_at_least_one():
    with pytest.raises(Exception):
        HolidayDraftsOutput(drafts=[])


def test_holiday_drafts_output_caps_at_four():
    """min_length=1, max_length=4 — five drafts must be rejected."""
    item = HolidayDraftItem(
        angle_used="some angle",
        platform_versions=PlatformVersions(instagram="hello world this is fine"),
    )
    with pytest.raises(Exception):
        HolidayDraftsOutput(drafts=[item] * 5)


# ──────────────────────────────────────────────────────────────────────────
# Quality gates
# ──────────────────────────────────────────────────────────────────────────
def test_check_post_copy_empty_blocks():
    res = check_post_copy("instagram", "")
    assert res.is_blocking
    assert "empty content" in res.blocking_reasons[0]


def test_check_post_copy_global_banned_phrase_blocks():
    res = check_post_copy(
        "instagram",
        "Happy Mother's Day to all the moms out there! Big love from us at Kova.",
    )
    # 'happy {holiday}' is in our list, but here we wrote actual 'Happy Mother's Day'
    # which doesn't match the literal '{holiday}' placeholder. Use a real banned phrase.
    res = check_post_copy("instagram", "On this special day we celebrate moms everywhere!")
    assert res.is_blocking


def test_check_post_copy_moment_avoid_phrase_blocks():
    res = check_post_copy(
        "instagram",
        "Wishing all the moms a beautiful day from our family kitchen.",
        moment_avoid_phrases=["Wishing all the moms"],
    )
    assert res.is_blocking


def test_check_post_copy_twitter_overlong_blocks():
    res = check_post_copy("twitter", "x" * 290)
    assert res.is_blocking
    assert any("280" in r for r in res.blocking_reasons)


def test_check_post_copy_clean_text_passes():
    res = check_post_copy(
        "instagram",
        "For the moms who fill the kitchen with stories, our briquettes burn long enough for the whole evening.",
    )
    assert not res.is_blocking


def test_check_post_copy_url_warns_not_blocks():
    res = check_post_copy(
        "facebook",
        "Order now at https://briquettes.co — same-day delivery in Kigali for the next 24 hours.",
    )
    assert not res.is_blocking
    assert any("URL" in w for w in res.warnings)


def test_check_post_copy_hashtag_spam_warns():
    text = "Mom's day spread #mom #love #family #food #cooking #kigali #rwanda #african #briquettes #eco"
    res = check_post_copy("instagram", text)
    assert any("hashtag spam" in w for w in res.warnings)


def test_filter_passing_separates_blocked_and_passing():
    posts = [
        ("instagram", "On this special day we celebrate moms everywhere!"),  # banned phrase
        ("linkedin", "For the founders who started in their mothers' kitchens — today's a quiet thank-you."),
        ("twitter", "x" * 290),  # too long
    ]
    passing, blocked = filter_passing(posts)
    assert len(passing) == 1
    assert passing[0][0] == "linkedin"
    assert len(blocked) == 2


# ──────────────────────────────────────────────────────────────────────────
# Generator (mocked LLM)
# ──────────────────────────────────────────────────────────────────────────
def _make_llm_response(json_dict):
    """Build a fake LLMResponse-like object."""
    resp = MagicMock()
    resp.content = json.dumps(json_dict)
    resp.input_tokens = 100
    resp.output_tokens = 200
    resp.total_tokens = 300
    return resp


def test_generator_creates_posts_for_passing_drafts(
    rw_user_with_account, mothers_day_occurrence,
):
    from apps.calendar_intel.generator import generate_drafts_for_holiday_draft
    from apps.content.models import Post

    today = timezone.now().date()
    target = mothers_day_occurrence.date

    draft = HolidayDraft.objects.create(
        user=rw_user_with_account,
        holiday_occurrence=mothers_day_occurrence,
        target_date=target,
        relevance_score=80,
        status=HolidayDraft.Status.QUEUED,
    )

    fake_response = _make_llm_response({
        "drafts": [
            {
                "angle_used": "Honor a specific mother",
                "rationale": "Story-led posts outperform generic praise on this user's feed.",
                "platform_versions": {
                    "instagram": "Mama Theo cooked breakfast for 5 every day for 30 years. This Sunday, our briquettes will keep the porridge warm for two whole hours.",
                    "linkedin": "The mothers we know don't ask for grand gestures — they ask for things that work. Briquettes that burn longer mean fewer interruptions in the kitchen this Mother's Day.",
                    "twitter": None,
                    "facebook": None,
                },
                "suggested_publish_time": None,
            },
        ],
    })

    with patch("apps.calendar_intel.generator.llm_generate", return_value=fake_response), \
         patch("apps.calendar_intel.generator.get_model_for_task", return_value="claude-sonnet-4-6"):
        count = generate_drafts_for_holiday_draft(draft.id)

    assert count == 2  # instagram + linkedin
    draft.refresh_from_db()
    assert draft.status == HolidayDraft.Status.DRAFTS_READY
    assert draft.posts_generated.count() == 2

    posts = list(draft.posts_generated.all())
    platforms = sorted(p.platform for p in posts)
    assert platforms == ["instagram", "linkedin"]
    for p in posts:
        assert p.status == "pending_approval"
        assert p.generated_by_agent == "holiday_watcher"
        assert p.ai_angle == "Honor a specific mother"
        assert p.scheduled_at is not None


def test_generator_idempotent_returns_existing_count(
    rw_user_with_account, mothers_day_occurrence,
):
    """If status is already DRAFTS_READY, don't re-generate."""
    from apps.calendar_intel.generator import generate_drafts_for_holiday_draft

    draft = HolidayDraft.objects.create(
        user=rw_user_with_account,
        holiday_occurrence=mothers_day_occurrence,
        target_date=mothers_day_occurrence.date,
        relevance_score=80,
        status=HolidayDraft.Status.DRAFTS_READY,
    )

    with patch("apps.calendar_intel.generator.llm_generate") as mock_gen:
        result = generate_drafts_for_holiday_draft(draft.id)
        assert mock_gen.call_count == 0  # didn't call LLM
    assert result == 0  # no posts attached


def test_generator_marks_failed_on_empty_llm_response(
    rw_user_with_account, mothers_day_occurrence,
):
    from apps.calendar_intel.generator import generate_drafts_for_holiday_draft

    draft = HolidayDraft.objects.create(
        user=rw_user_with_account,
        holiday_occurrence=mothers_day_occurrence,
        target_date=mothers_day_occurrence.date,
        relevance_score=80,
        status=HolidayDraft.Status.QUEUED,
    )

    empty_resp = MagicMock()
    empty_resp.content = ""
    with patch("apps.calendar_intel.generator.llm_generate", return_value=empty_resp), \
         patch("apps.calendar_intel.generator.get_model_for_task", return_value="claude-sonnet-4-6"):
        count = generate_drafts_for_holiday_draft(draft.id)

    assert count == 0
    draft.refresh_from_db()
    assert draft.status == HolidayDraft.Status.FAILED
    assert "empty content" in draft.generation_error.lower()


def test_generator_marks_failed_on_no_connected_platforms(
    db, mothers_day_occurrence,
):
    """User without active social accounts should fail cleanly."""
    from apps.calendar_intel.generator import generate_drafts_for_holiday_draft

    u = User.objects.create_user(
        username="noplatform",
        email="noplatform@kova.ai",
        password="TestPass123!",
    )
    UserProfile.objects.filter(user=u).update(country="RW", industry="food_restaurant")

    draft = HolidayDraft.objects.create(
        user=u,
        holiday_occurrence=mothers_day_occurrence,
        target_date=mothers_day_occurrence.date,
        relevance_score=80,
        status=HolidayDraft.Status.QUEUED,
    )

    count = generate_drafts_for_holiday_draft(draft.id)
    assert count == 0
    draft.refresh_from_db()
    assert draft.status == HolidayDraft.Status.FAILED
    assert "social accounts" in draft.generation_error.lower()


def test_generator_drops_posts_with_banned_phrases(
    rw_user_with_account, mothers_day_occurrence,
):
    """Generator should silently filter blocked posts and persist only the clean ones."""
    from apps.calendar_intel.generator import generate_drafts_for_holiday_draft

    draft = HolidayDraft.objects.create(
        user=rw_user_with_account,
        holiday_occurrence=mothers_day_occurrence,
        target_date=mothers_day_occurrence.date,
        relevance_score=80,
        status=HolidayDraft.Status.QUEUED,
    )

    fake_response = _make_llm_response({
        "drafts": [
            {
                "angle_used": "Honor a specific mother",
                "rationale": "good angle",
                "platform_versions": {
                    "instagram": "On this special day we celebrate moms everywhere!",  # banned
                    "linkedin": "For the founders who started in their mothers' kitchens — today's a thank-you.",
                },
            },
        ],
    })

    with patch("apps.calendar_intel.generator.llm_generate", return_value=fake_response), \
         patch("apps.calendar_intel.generator.get_model_for_task", return_value="claude-sonnet-4-6"):
        count = generate_drafts_for_holiday_draft(draft.id)

    assert count == 1   # only LinkedIn survived
    draft.refresh_from_db()
    assert draft.status == HolidayDraft.Status.DRAFTS_READY
    posts = list(draft.posts_generated.all())
    assert len(posts) == 1
    assert posts[0].platform == "linkedin"


# ──────────────────────────────────────────────────────────────────────────
# Watcher
# ──────────────────────────────────────────────────────────────────────────
def test_watcher_enqueues_drafts_for_eligible_users(
    rw_user_with_account, mothers_day_occurrence,
):
    """Watcher should create HolidayDraft + enqueue generation for relevant moments."""
    from apps.calendar_intel.tasks import _process_user

    rw_user_with_account.onboarding_completed = True
    rw_user_with_account.save()

    # Run when Mother's Day is 9 days away (within lead time)
    today = mothers_day_occurrence.date - timedelta(days=9)
    with patch("apps.calendar_intel.tasks.generate_drafts_for_moment.delay") as mock_delay:
        queued = _process_user(rw_user_with_account, today)

    assert queued >= 1
    assert HolidayDraft.objects.filter(
        user=rw_user_with_account,
        holiday_occurrence=mothers_day_occurrence,
    ).exists()
    assert mock_delay.called


def test_watcher_idempotent_does_not_double_queue(
    rw_user_with_account, mothers_day_occurrence,
):
    """Calling the watcher twice for the same window should not re-queue."""
    from apps.calendar_intel.tasks import _process_user

    rw_user_with_account.onboarding_completed = True
    rw_user_with_account.save()
    today = mothers_day_occurrence.date - timedelta(days=9)

    with patch("apps.calendar_intel.tasks.generate_drafts_for_moment.delay") as mock_delay:
        _process_user(rw_user_with_account, today)
        first_call_count = mock_delay.call_count
        # Mark the draft as DRAFTS_READY (simulating successful generation)
        d = HolidayDraft.objects.get(
            user=rw_user_with_account, holiday_occurrence=mothers_day_occurrence,
        )
        d.status = HolidayDraft.Status.DRAFTS_READY
        d.save()
        # Second pass — should not queue again
        _process_user(rw_user_with_account, today)
        assert mock_delay.call_count == first_call_count


def test_watcher_skips_dismissed_drafts(
    rw_user_with_account, mothers_day_occurrence,
):
    """If user dismissed an existing draft, watcher shouldn't recreate."""
    from apps.calendar_intel.tasks import _process_user

    rw_user_with_account.onboarding_completed = True
    rw_user_with_account.save()
    today = mothers_day_occurrence.date - timedelta(days=9)

    HolidayDraft.objects.create(
        user=rw_user_with_account,
        holiday_occurrence=mothers_day_occurrence,
        target_date=mothers_day_occurrence.date,
        relevance_score=80,
        status=HolidayDraft.Status.DISMISSED,
    )

    with patch("apps.calendar_intel.tasks.generate_drafts_for_moment.delay") as mock_delay:
        _process_user(rw_user_with_account, today)
        assert mock_delay.call_count == 0
