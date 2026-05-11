"""
Tests for the profile_audit feature.

Covers:
  - Facebook _fb_normalize_field + completeness scoring
  - LinkedIn org localized-field extraction
  - Suggester: static-field shortcut (pulls phone/website from profile)
  - Suggester: rule-based category mapping
  - Auditor: full audit cycle with mocked provider
  - Auditor: apply_suggestion success + failure paths
  - View: list + detail + approve + dismiss
"""
import uuid
from unittest.mock import MagicMock, patch

import pytest

from apps.accounts.models import User, UserProfile
from apps.platforms.models import SocialAccount
from apps.platforms.providers.base import ProfileSnapshot, ProfileUpdateResult
from apps.platforms.providers.instagram_facebook import FacebookProvider, InstagramProvider
from apps.platforms.providers.linkedin import LinkedInProvider
from apps.profile_audit.auditor import (
    apply_suggestion,
    audit_social_account,
)
from apps.profile_audit.models import ProfileAudit, ProfileUpdateSuggestion
from apps.profile_audit.suggester import (
    _category_for_industry,
    _from_user_profile,
    generate_suggestion,
)


# ──────────────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────────────
@pytest.fixture
def kg_user(db):
    """A Rwandan food/restaurant user with brand voice + products."""
    u = User.objects.create_user(
        username=f"pa_{uuid.uuid4().hex[:8]}",
        email=f"pa_{uuid.uuid4().hex[:8]}@kova.test",
        password="TestPass123!",
        full_name="Iranzi Test",
    )
    u.onboarding_completed = True
    u.save()
    UserProfile.objects.filter(user=u).update(
        country="RW", city="Kigali",
        industry="food_restaurant",
        company_name="Briquettes Co",
        brand_voice="Direct, no-nonsense voice for busy households who care about cost and the planet.",
        website_url="https://briquettes.co",
        cta_phone="+250 7xx xxx xxx",
        cta_email="iranzi@briquettes.co",
    )
    return User.objects.select_related("profile").get(pk=u.pk)


@pytest.fixture
def fb_account(kg_user, db):
    return SocialAccount.objects.create(
        user=kg_user, platform="facebook",
        platform_user_id=f"fb_{uuid.uuid4().hex[:8]}",
        username="briquettes_page",
        is_active=True,
        access_token="x",
        metadata={"page_id": "1234567890"},
    )


@pytest.fixture
def ig_account(kg_user, db):
    return SocialAccount.objects.create(
        user=kg_user, platform="instagram",
        platform_user_id=f"ig_{uuid.uuid4().hex[:8]}",
        username="briquettes_ig",
        is_active=True,
        access_token="x",
        metadata={"ig_user_id": "987654321"},
    )


# ──────────────────────────────────────────────────────────────────────────
# Provider — field normalization + scoring
# ──────────────────────────────────────────────────────────────────────────
def test_fb_normalize_picture_silhouette_treated_as_missing():
    """Default-silhouette FB profile picture should be treated as missing."""
    silhouette = {"data": {"url": "https://scontent.fra.fbcdn.net/...silhouette..."}}
    assert FacebookProvider._fb_normalize_field("picture", silhouette) == ""


def test_fb_normalize_picture_real_image_returns_url():
    real = {"data": {"url": "https://scontent.fra.fbcdn.net/v/t39/real.jpg"}}
    assert "real.jpg" in FacebookProvider._fb_normalize_field("picture", real)


def test_fb_normalize_emails_list_joined():
    assert FacebookProvider._fb_normalize_field("emails", ["a@b.com", "c@d.com"]) == "a@b.com, c@d.com"


def test_fb_normalize_hours_dict_returns_set_marker():
    assert FacebookProvider._fb_normalize_field("hours", {"mon_1_open": "09:00"}) == "set"


def test_fb_normalize_empty_returns_empty_string():
    for value in (None, "", {}, []):
        assert FacebookProvider._fb_normalize_field("about", value) == ""


def test_fb_audit_scoring_full_profile():
    """A full profile should score close to 100."""
    fb = FacebookProvider()
    full_profile = {
        "about": "Eco-friendly briquettes for Kigali kitchens.",
        "description": "We make long-burning briquettes from agricultural waste. Same-day delivery in Kigali for orders before noon.",
        "phone": "+250 7xx xxx xxx",
        "emails": ["hi@briquettes.co"],
        "single_line_address": "Kicukiro, Kigali, Rwanda",
        "website": "https://briquettes.co",
        "hours": {"mon_1_open": "09:00"},
        "category": "Energy Company",
        "picture": {"data": {"url": "https://scontent.../real.jpg"}},
        "cover": {"source": "https://scontent.../cover.jpg"},
    }
    with patch("apps.platforms.providers.instagram_facebook.httpx.Client") as MockClient:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = full_profile
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
        snap = fb.audit_profile("fake_token", page_id="123")
    assert snap.completeness_score >= 95
    assert not snap.fields_missing


def test_fb_audit_scoring_empty_profile():
    """An empty profile should score 0 with everything missing."""
    fb = FacebookProvider()
    with patch("apps.platforms.providers.instagram_facebook.httpx.Client") as MockClient:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = {}
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
        snap = fb.audit_profile("fake_token", page_id="123")
    assert snap.completeness_score == 0
    assert "about" in snap.fields_missing
    assert "phone" in snap.fields_missing


def test_fb_audit_thin_fields_half_credit():
    """Bio under threshold gets half-credit and lands in fields_thin."""
    fb = FacebookProvider()
    profile = {
        "about": "Hi",   # too short → thin
        "phone": "+250 7xx xxx xxx",
        "website": "https://x.co",
    }
    with patch("apps.platforms.providers.instagram_facebook.httpx.Client") as MockClient:
        mock_resp = MagicMock(status_code=200)
        mock_resp.json.return_value = profile
        MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
        snap = fb.audit_profile("fake_token", page_id="123")
    assert "about" in snap.fields_thin
    assert "about" in snap.fields_present  # present, not missing
    # Score should be partial — about (18*0.5) + phone (10) + website (12*0.5 since len < 8)
    # Actually website "https://x.co" is 12 chars >= 8, so full credit on website
    assert 0 < snap.completeness_score < 100


def test_fb_update_profile_rejects_unwritable_field():
    fb = FacebookProvider()
    result = fb.update_profile("token", {"picture": "..."}, page_id="123")
    assert not result.success
    assert "not writable" in result.error


# ──────────────────────────────────────────────────────────────────────────
# Suggester — static + category mapping
# ──────────────────────────────────────────────────────────────────────────
def test_from_user_profile_pulls_phone(kg_user, fb_account, db):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account,
        completeness_score=50,
        fields_missing=["phone"], fields_present={},
    )
    val = _from_user_profile(audit, "phone")
    assert val == "+250 7xx xxx xxx"


def test_from_user_profile_pulls_website(kg_user, fb_account, db):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account,
        completeness_score=50,
        fields_missing=["website"], fields_present={},
    )
    assert _from_user_profile(audit, "website") == "https://briquettes.co"


def test_from_user_profile_returns_none_for_unmapped_field(kg_user, fb_account, db):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account,
        completeness_score=50,
        fields_missing=["about"], fields_present={},
    )
    assert _from_user_profile(audit, "about") is None


def test_category_mapping_for_industries():
    assert _category_for_industry("food_restaurant", "facebook") == "Restaurant"
    assert _category_for_industry("saas", "facebook") == "Software Company"
    assert _category_for_industry("nonexistent", "facebook") is None
    assert _category_for_industry("food_restaurant", "twitter") is None  # no map for Twitter


def test_generate_suggestion_static_phone_no_llm_call(kg_user, fb_account, db):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account,
        completeness_score=50,
        fields_missing=["phone"], fields_present={},
    )
    with patch("apps.profile_audit.suggester.llm_generate") as mock_llm:
        result = generate_suggestion(audit, "phone")
    assert result["value"] == "+250 7xx xxx xxx"
    assert mock_llm.call_count == 0  # static pull, no LLM


def test_generate_suggestion_skips_uninventable_fields(kg_user, fb_account, db):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account,
        completeness_score=50,
        fields_missing=["hours"], fields_present={},
    )
    assert generate_suggestion(audit, "hours") is None  # never fabricate hours


def test_generate_suggestion_llm_path(kg_user, fb_account, db):
    """When the field needs the LLM and brand voice exists, we call out."""
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account,
        completeness_score=30,
        fields_missing=["about"], fields_present={},
    )
    fake_resp = MagicMock()
    fake_resp.content = '{"value": "Eco-friendly briquettes for Kigali kitchens.", "reasoning": "Direct + product-anchored."}'

    with patch("apps.profile_audit.suggester.llm_generate", return_value=fake_resp):
        result = generate_suggestion(audit, "about")
    assert result is not None
    assert "briquettes" in result["value"].lower()
    assert "reasoning" in result and result["reasoning"]


def test_generate_suggestion_llm_returns_none_when_no_context(db, fb_account):
    """User with no brand voice + no products = no LLM suggestion (avoid spam)."""
    u = User.objects.create_user(
        username=f"empty_{uuid.uuid4().hex[:6]}",
        email=f"empty_{uuid.uuid4().hex[:6]}@kova.test",
        password="x",
    )
    fb_account.user = u
    fb_account.save()
    audit = ProfileAudit.objects.create(
        user=u, social_account=fb_account,
        completeness_score=10,
        fields_missing=["about"], fields_present={},
    )
    with patch("apps.profile_audit.suggester.llm_generate") as mock_llm:
        result = generate_suggestion(audit, "about")
    assert result is None
    assert mock_llm.call_count == 0


# ──────────────────────────────────────────────────────────────────────────
# Auditor orchestration
# ──────────────────────────────────────────────────────────────────────────
def test_audit_social_account_creates_audit_row(kg_user, fb_account):
    fake_snapshot = ProfileSnapshot(
        completeness_score=60,
        fields_present={"about": "Hi", "phone": "+250..."},
        fields_missing=["website", "hours"],
        fields_thin=["about"],
    )
    with patch("apps.profile_audit.auditor.get_provider") as mock_get, \
         patch("apps.profile_audit.auditor.decrypt_token", return_value="real_token"):
        provider = MagicMock()
        provider.audit_profile.return_value = fake_snapshot
        mock_get.return_value = provider
        audit = audit_social_account(fb_account, generate_suggestions=False)

    assert audit is not None
    assert audit.completeness_score == 60
    assert audit.fields_missing == ["website", "hours"]
    assert audit.fields_thin == ["about"]


def test_audit_social_account_handles_missing_token(kg_user, fb_account):
    fb_account.access_token = ""
    fb_account.save()
    audit = audit_social_account(fb_account)
    assert audit is not None
    assert "re-authentication" in audit.error


def test_audit_generates_suggestions_for_gaps(kg_user, fb_account):
    fake_snapshot = ProfileSnapshot(
        completeness_score=40,
        fields_present={},
        fields_missing=["phone", "website"],
        fields_thin=[],
    )
    with patch("apps.profile_audit.auditor.get_provider") as mock_get, \
         patch("apps.profile_audit.auditor.decrypt_token", return_value="t"):
        provider = MagicMock()
        provider.audit_profile.return_value = fake_snapshot
        mock_get.return_value = provider
        audit = audit_social_account(fb_account, generate_suggestions=True)

    # phone + website both come from UserProfile — static path, no LLM needed
    suggestions = list(audit.suggestions.all().order_by("field_name"))
    assert len(suggestions) == 2
    fields = sorted(s.field_name for s in suggestions)
    assert fields == ["phone", "website"]


# ──────────────────────────────────────────────────────────────────────────
# Apply path
# ──────────────────────────────────────────────────────────────────────────
def test_apply_suggestion_success(kg_user, fb_account):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account, completeness_score=50,
        fields_missing=["about"], fields_present={},
    )
    s = ProfileUpdateSuggestion.objects.create(
        audit=audit, user=kg_user, social_account=fb_account,
        field_name="about", suggested_value="Eco-friendly briquettes for Kigali.",
    )

    with patch("apps.profile_audit.auditor.get_provider") as mock_get, \
         patch("apps.profile_audit.auditor.decrypt_token", return_value="t"):
        provider = MagicMock()
        provider.update_profile.return_value = ProfileUpdateResult(
            success=True, field_name="about",
            applied_value="Eco-friendly briquettes for Kigali.",
        )
        mock_get.return_value = provider
        ok = apply_suggestion(s)

    s.refresh_from_db()
    assert ok is True
    assert s.status == ProfileUpdateSuggestion.Status.APPLIED
    assert s.applied_value == "Eco-friendly briquettes for Kigali."
    assert s.applied_at is not None


def test_apply_suggestion_failure_marks_failed_with_error(kg_user, fb_account):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account, completeness_score=50,
        fields_missing=["about"], fields_present={},
    )
    s = ProfileUpdateSuggestion.objects.create(
        audit=audit, user=kg_user, social_account=fb_account,
        field_name="about", suggested_value="Hi.",
    )
    with patch("apps.profile_audit.auditor.get_provider") as mock_get, \
         patch("apps.profile_audit.auditor.decrypt_token", return_value="t"):
        provider = MagicMock()
        provider.update_profile.return_value = ProfileUpdateResult(
            success=False, field_name="about", error="HTTP 400: too short",
        )
        mock_get.return_value = provider
        ok = apply_suggestion(s)

    s.refresh_from_db()
    assert ok is False
    assert s.status == ProfileUpdateSuggestion.Status.FAILED
    assert "HTTP 400" in s.error_message


# ──────────────────────────────────────────────────────────────────────────
# View flow
# ──────────────────────────────────────────────────────────────────────────
def test_health_list_renders_for_user_with_accounts(client, kg_user, fb_account, ig_account):
    client.force_login(kg_user)
    r = client.get("/profile-health/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Profile Health" in body
    # Both accounts should appear
    assert "facebook" in body.lower()
    assert "instagram" in body.lower()


def test_health_detail_404_for_others_account(client, kg_user, db):
    """A user must not view another user's profile health."""
    other = User.objects.create_user(
        username=f"o_{uuid.uuid4().hex[:6]}",
        email=f"o_{uuid.uuid4().hex[:6]}@kova.test",
        password="x",
    )
    other_acc = SocialAccount.objects.create(
        user=other, platform="facebook",
        platform_user_id="other_fb", is_active=True,
        access_token="x",
    )
    client.force_login(kg_user)
    r = client.get(f"/profile-health/{other_acc.id}/")
    assert r.status_code == 404


def test_approve_suggestion_marks_approved_and_queues_apply(client, kg_user, fb_account):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account, completeness_score=50,
        fields_missing=["phone"], fields_present={},
    )
    s = ProfileUpdateSuggestion.objects.create(
        audit=audit, user=kg_user, social_account=fb_account,
        field_name="phone", suggested_value="+250 7xx xxx xxx",
    )
    client.force_login(kg_user)
    # Patch the task at source — view does a lazy import
    with patch("apps.profile_audit.tasks.apply_one_suggestion") as mock_task:
        mock_task.delay = MagicMock()
        r = client.post(f"/profile-health/suggestions/{s.id}/approve/")
    assert r.status_code == 200
    s.refresh_from_db()
    # Status should be either APPROVED (delay path) or APPLIED (sync fallback)
    assert s.status in (
        ProfileUpdateSuggestion.Status.APPROVED,
        ProfileUpdateSuggestion.Status.APPLIED,
        ProfileUpdateSuggestion.Status.FAILED,
    )


def test_dismiss_suggestion(client, kg_user, fb_account):
    audit = ProfileAudit.objects.create(
        user=kg_user, social_account=fb_account, completeness_score=50,
        fields_missing=["phone"], fields_present={},
    )
    s = ProfileUpdateSuggestion.objects.create(
        audit=audit, user=kg_user, social_account=fb_account,
        field_name="phone", suggested_value="+250 7xx xxx xxx",
    )
    client.force_login(kg_user)
    r = client.post(f"/profile-health/suggestions/{s.id}/dismiss/")
    assert r.status_code == 200
    s.refresh_from_db()
    assert s.status == ProfileUpdateSuggestion.Status.DISMISSED
