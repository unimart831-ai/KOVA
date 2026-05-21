"""Tests for the onboarding automation layer:

- industry_packs.apply_pack — fills empty profile fields based on industry
- magic_fill._infer_industry — maps platform category strings to Industry choices
- KovaSignupForm.signup — no-op hook (phone collected in onboarding Step 1)

These are the load-bearing pieces of the Tier-1/Tier-2 onboarding rework. If
any of them regress, new users get a worse first-run experience.
"""

import pytest

from apps.accounts.models import User, UserProfile
from apps.accounts.industry_packs import apply_pack, get_pack, PACKS
from apps.accounts.magic_fill import _infer_industry
from apps.accounts.forms import OnboardingStep1Form
from apps.accounts.onboarding_flow import apply_url_inference_to_profile, finish_onboarding


# ── industry_packs ──────────────────────────────────────────────────────────

class TestIndustryPacks:
    def test_get_pack_returns_valid_shape_for_every_industry(self):
        required = {"tone_attributes", "content_pillars", "goals",
                    "posting_frequency", "default_cta_type", "visual_style"}
        for industry in PACKS:
            pack = get_pack(industry)
            assert required <= set(pack), f"{industry} missing keys"
            assert isinstance(pack["tone_attributes"], list)
            assert isinstance(pack["posting_frequency"], int)

    def test_get_pack_falls_back_for_unknown_industry(self):
        pack = get_pack("not_an_industry")
        assert pack["tone_attributes"]  # has defaults
        assert pack["posting_frequency"] > 0

    def test_get_pack_normalizes_warm_alias(self):
        # Salon pack uses "warm" internally — should surface as "empathetic"
        pack = get_pack("salon_beauty")
        assert "warm" not in pack["tone_attributes"]
        assert "empathetic" in pack["tone_attributes"]

    def test_every_pack_tone_is_in_valid_vocabulary(self):
        valid = {
            "confident", "approachable", "witty", "professional", "casual",
            "bold", "educational", "inspirational", "empathetic",
            "authoritative", "playful", "minimalist",
        }
        for industry in PACKS:
            tones = get_pack(industry)["tone_attributes"]
            assert set(tones) <= valid, f"{industry} has invalid tones: {tones}"


@pytest.mark.django_db
class TestApplyPack:
    def _fresh_user(self, *, industry="salon_beauty"):
        u = User.objects.create_user(
            username="apply-pack", email="ap@b.com", password="P1!",
        )
        # The post_save signal already created UserProfile.
        p = u.profile
        p.industry = industry
        p.save(update_fields=["industry"])
        return u, p

    def test_apply_pack_fills_empty_fields(self):
        u, p = self._fresh_user()
        applied = apply_pack(p, p.industry)

        assert "tone_attributes" in applied
        assert "content_pillars" in applied
        assert "goals" in applied
        assert p.tone_attributes  # populated
        assert p.content_pillars
        assert p.goals
        # Salon-specific expectations
        assert p.default_cta_type == "whatsapp"

    def test_apply_pack_does_not_overwrite_user_data(self):
        u, p = self._fresh_user()
        p.tone_attributes = ["bold"]
        p.content_pillars = ["My existing pillar"]
        p.save(update_fields=["tone_attributes", "content_pillars"])

        applied = apply_pack(p, p.industry)

        assert "tone_attributes" not in applied
        assert "content_pillars" not in applied
        assert p.tone_attributes == ["bold"]
        assert p.content_pillars == ["My existing pillar"]

    def test_apply_pack_treats_default_cta_none_as_empty(self):
        # default_cta_type defaults to "none" — pack should overwrite it
        u, p = self._fresh_user()
        assert p.default_cta_type == "none"

        apply_pack(p, p.industry)

        assert p.default_cta_type != "none"


# ── magic_fill industry inference ───────────────────────────────────────────

class TestInferIndustry:
    @pytest.mark.parametrize("category,expected", [
        ("Hair Salon", "salon_beauty"),
        ("Beauty, Cosmetic & Personal Care", "salon_beauty"),
        ("Nail Bar", "salon_beauty"),
        ("Restaurant", "food_restaurant"),
        ("Coffee Shop", "food_restaurant"),
        ("Bakery", "food_restaurant"),
        ("Hotel & Lodge", "travel_tourism"),
        ("Safari Tours", "travel_tourism"),
        ("Health Clinic", "health"),
        ("Dental Practice", "health"),
        ("Law Firm", "legal"),
        ("Marketing Agency", "agency"),
        ("Software Company", "saas"),
        ("Boutique", "wholesale_retail"),
        ("Fashion Designer", "fashion_beauty"),
        ("School", "education"),
        ("NGO", "nonprofit"),
        ("", None),
        ("Random gibberish", None),
    ])
    def test_inference(self, category, expected):
        assert _infer_industry(category) == expected


# ── onboarding Step 1 phone ─────────────────────────────────────────────────

@pytest.mark.django_db
class TestOnboardingStep1Phone:
    def _user_with_profile(self):
        u = User.objects.create_user(
            username="step1", email="step1@b.com", password="P1!",
        )
        return u, u.profile

    def test_kenyan_phone_sets_timezone_and_country(self):
        u, p = self._user_with_profile()
        data = {
            "full_name": "Test User",
            "timezone": "UTC",
            "phone_number": "0712345678",
            "company_name": "Acme",
            "website_url": "",
            "industry": "agency",
            "industry_other": "",
            "content_language": "en",
            "key_offerings_text": "",
        }
        form = OnboardingStep1Form(data=data, instance=p, user=u)
        assert form.is_valid(), form.errors
        form.save()

        u.refresh_from_db()
        assert u.phone_number == "0712345678"
        assert u.timezone == "Africa/Nairobi"
        assert u.profile.country == "KE"
        assert u.profile.mpesa_phone == "0712345678"

    def test_international_phone_accepted(self):
        u, p = self._user_with_profile()
        data = {
            "full_name": "Test User",
            "timezone": "UTC",
            "phone_number": "+1 555 123 4567",
            "company_name": "Acme",
            "website_url": "",
            "industry": "agency",
            "industry_other": "",
            "content_language": "en",
            "key_offerings_text": "",
        }
        form = OnboardingStep1Form(data=data, instance=p, user=u)
        assert form.is_valid(), form.errors
        form.save()
        u.refresh_from_db()
        assert u.phone_number == "+15551234567"

    def test_invalid_phone_rejected(self):
        u, p = self._user_with_profile()
        data = {
            "full_name": "Test User",
            "timezone": "UTC",
            "phone_number": "abc",
            "company_name": "Acme",
            "website_url": "",
            "industry": "agency",
            "industry_other": "",
            "content_language": "en",
            "key_offerings_text": "",
        }
        form = OnboardingStep1Form(data=data, instance=p, user=u)
        assert not form.is_valid()
        assert "phone_number" in form.errors


@pytest.mark.django_db
class TestFinishOnboarding:
    def test_finish_without_platform(self, monkeypatch):
        u = User.objects.create_user(
            username="fin", email="fin@b.com", password="P1!",
        )
        monkeypatch.setattr(
            "apps.emails.tasks.send_welcome_email.delay",
            lambda pk: None,
        )
        monkeypatch.setattr(
            "apps.emails.automation.bootstrap_email_automation",
            lambda user: None,
        )
        monkeypatch.setattr(
            "apps.utils.fire_task",
            lambda task, pk: None,
        )

        finish_onboarding(u, skipped_platform_connect=True)

        u.refresh_from_db()
        assert u.onboarding_completed is True
        assert u.profile.trial_ends_at is not None
        assert (u.profile.onboarding_step_timestamps or {}).get("platform_connect_deferred")


@pytest.mark.django_db
class TestUrlInferencePersistence:
    def test_apply_url_inference_skips_nonempty_fields(self):
        u = User.objects.create_user(
            username="url", email="url@b.com", password="P1!",
        )
        p = u.profile
        p.brand_voice = "Existing voice"
        p.save(update_fields=["brand_voice"])

        updated = apply_url_inference_to_profile(p, {
            "brand_voice": "Inferred voice",
            "target_audience": "Inferred audience",
            "content_pillars": ["A", "B"],
        })

        p.refresh_from_db()
        assert p.brand_voice == "Existing voice"
        assert p.target_audience == "Inferred audience"
        assert "target_audience" in updated
        assert "brand_voice" not in updated


# ── Merged Step 2 "Review your brand" form ──────────────────────────────────

@pytest.mark.django_db
class TestMergedReviewForm:
    """The merged form replaces old Step 2 (voice/visuals) + Step 3 (goals/
    autonomy/CTA). It must save fields from both halves and persist the helper
    fields (tone_selection, content_pillars_text, etc.) back onto the model."""

    def _user_with_profile(self):
        u = User.objects.create_user(
            username="rev", email="rev@b.com", password="P1!",
            daily_brief_time="07:00",
        )
        return u, u.profile

    def test_form_renders_with_all_section_fields(self):
        from apps.accounts.forms import OnboardingStep2ReviewForm
        u, p = self._user_with_profile()
        form = OnboardingStep2ReviewForm(instance=p, user=u)

        expected_fields = {
            # Voice & audience
            "brand_voice", "target_audience", "tone_selection",
            "brand_voice_examples_text",
            # Content
            "content_pillars_text", "brand_restrictions",
            # Visuals
            "visual_style", "brand_colors_text",
            # Goals & cadence
            "goals_selection", "posting_frequency", "daily_brief_time",
            # Autonomy
            "auto_approve_posts", "engage_autonomy_level",
            # CTA
            "default_cta_type", "default_cta_url", "cta_whatsapp",
        }
        assert expected_fields <= set(form.fields)

    def test_form_saves_voice_and_goals_in_one_pass(self):
        from apps.accounts.forms import OnboardingStep2ReviewForm
        u, p = self._user_with_profile()

        data = {
            "brand_voice": "Friendly and direct.",
            "target_audience": "Nairobi salon owners aged 25-45.",
            "tone_selection": ["warm" if False else "approachable", "playful"],
            "content_pillars_text": "Transformations\nClient stories\nTips",
            "brand_voice_examples_text": "",
            "brand_colors_text": "#FF5733, #1A1A2E",
            "brand_restrictions": "",
            "visual_style": "photography",
            "goals_selection": ["grow_followers", "generate_leads"],
            "posting_frequency": 5,
            "daily_brief_time": "07:00",
            "auto_approve_posts": False,
            "engage_autonomy_level": "suggest",
            "default_cta_type": "whatsapp",
            "default_cta_url": "",
            "cta_whatsapp": "254712345678",
        }
        form = OnboardingStep2ReviewForm(data=data, instance=p, user=u)
        assert form.is_valid(), form.errors
        form.save()

        p.refresh_from_db()
        # Voice fields persisted
        assert p.brand_voice == "Friendly and direct."
        assert p.target_audience.startswith("Nairobi salon")
        assert "approachable" in p.tone_attributes
        assert "playful" in p.tone_attributes
        # Pillars split from textarea
        assert p.content_pillars == ["Transformations", "Client stories", "Tips"]
        # Colors split from comma-string
        assert p.brand_colors == ["#FF5733", "#1A1A2E"]
        # Goals + autonomy + CTA — proves old Step 3 fields save too
        assert "grow_followers" in p.goals
        assert p.posting_frequency == 5
        assert p.engage_autonomy_level == "suggest"
        assert p.default_cta_type == "whatsapp"

    def test_form_preserves_user_pillars_on_redisplay(self):
        from apps.accounts.forms import OnboardingStep2ReviewForm
        u, p = self._user_with_profile()
        p.content_pillars = ["Pillar A", "Pillar B"]
        p.tone_attributes = ["bold"]
        p.save(update_fields=["content_pillars", "tone_attributes"])

        form = OnboardingStep2ReviewForm(instance=p, user=u)
        assert "Pillar A\nPillar B" == form.fields["content_pillars_text"].initial
        assert form.fields["tone_selection"].initial == ["bold"]

    def test_field_order_is_review_friendly(self):
        """Voice should appear before goals, autonomy before CTA — so the
        reviewer scrolls in a logical reading order."""
        from apps.accounts.forms import OnboardingStep2ReviewForm
        u, p = self._user_with_profile()
        form = OnboardingStep2ReviewForm(instance=p, user=u)
        names = list(form.fields.keys())

        assert names.index("brand_voice") < names.index("goals_selection")
        assert names.index("tone_selection") < names.index("posting_frequency")
        assert names.index("auto_approve_posts") < names.index("default_cta_type")


# ── Admin instrumentation markers ────────────────────────────────────────────

@pytest.mark.django_db
class TestInstrumentation:
    """The admin Onboarding Funnel reads these markers from
    UserProfile.onboarding_step_timestamps. If they stop firing, the admin
    dashboard's Tier 1/2 adoption panels go blank."""

    def _fresh_user(self):
        return User.objects.create_user(
            username="instr", email="instr@b.com", password="P1!",
        )

    def test_industry_pack_apply_records_marker(self):
        from apps.accounts.industry_packs import apply_pack
        u = self._fresh_user()
        p = u.profile
        p.industry = "salon_beauty"
        p.save(update_fields=["industry"])

        apply_pack(p, "salon_beauty")

        p.refresh_from_db()
        assert any(
            k.startswith("industry_pack_applied:") for k in (p.onboarding_step_timestamps or {})
        ), p.onboarding_step_timestamps

    def test_industry_pack_marker_includes_industry_key(self):
        from apps.accounts.industry_packs import apply_pack
        u = self._fresh_user()
        p = u.profile
        p.industry = "food_restaurant"
        p.save(update_fields=["industry"])

        apply_pack(p, "food_restaurant")

        p.refresh_from_db()
        assert "industry_pack_applied:food_restaurant" in (p.onboarding_step_timestamps or {})

    def test_magic_fill_records_marker_with_platform(self, monkeypatch):
        """Magic Fill should record `magic_fill_applied:<platform>` when at
        least one field is populated. This is what powers the provider
        breakdown panel."""
        from apps.accounts.magic_fill import apply_magic_fill
        from apps.platforms.models import SocialAccount

        u = self._fresh_user()

        account = SocialAccount.objects.create(
            user=u, platform="instagram", platform_user_id="123",
            username="testbiz", display_name="Test Biz",
            access_token="dummy", is_active=True,
        )

        # Stub the audit to return a real-looking ProfileSnapshot.
        class FakeAudit:
            error = ""
            fields_present = {
                "bio": "We make great coffee in Nairobi.",
                "website": "https://testbiz.co.ke",
                "category": "Coffee Shop",
            }

        monkeypatch.setattr(
            "apps.profile_audit.auditor.audit_social_account",
            lambda *args, **kwargs: FakeAudit(),
        )

        applied = apply_magic_fill(u, account)
        assert applied, "Magic Fill should have populated at least one field"

        u.profile.refresh_from_db()
        stamps = u.profile.onboarding_step_timestamps or {}
        assert "magic_fill_applied:instagram" in stamps
