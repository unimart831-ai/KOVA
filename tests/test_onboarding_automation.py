"""Tests for the onboarding automation layer:

- industry_packs.apply_pack — fills empty profile fields based on industry
- magic_fill._infer_industry — maps platform category strings to Industry choices
- KovaSignupForm.signup — saves phone at signup (required field)

These are the load-bearing pieces of the Tier-1/Tier-2 onboarding rework. If
any of them regress, new users get a worse first-run experience.
"""

import pytest

from apps.accounts.models import User, UserProfile
from apps.accounts.industry_packs import apply_pack, get_pack, PACKS
from apps.accounts.magic_fill import _infer_industry
from apps.accounts.forms import OnboardingExpressStep1Form, OnboardingStep1Form, KovaSignupForm, PhoneCaptureForm
from apps.accounts.onboarding_flow import apply_url_inference_to_profile, finish_onboarding
from apps.accounts.brand_preview import build_brand_preview
from apps.accounts.onboarding_express import ensure_brand_defaults, record_intent
from apps.accounts.setup_mission import build_setup_mission, is_commerce_industry


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
            "phone_number": "0712345678",
            "company_name": "Acme",
            "website_url": "",
            "industry": "agency",
            "industry_other": "",
        }
        form = OnboardingExpressStep1Form(data=data, instance=p, user=u)
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
            "phone_number": "+1 555 123 4567",
            "company_name": "Acme",
            "website_url": "",
            "industry": "agency",
            "industry_other": "",
        }
        form = OnboardingExpressStep1Form(data=data, instance=p, user=u)
        assert form.is_valid(), form.errors
        form.save()
        u.refresh_from_db()
        assert u.phone_number == "+15551234567"

    def test_invalid_phone_rejected(self):
        u, p = self._user_with_profile()
        data = {
            "full_name": "Test User",
            "phone_number": "abc",
            "company_name": "Acme",
            "website_url": "",
            "industry": "agency",
            "industry_other": "",
        }
        form = OnboardingExpressStep1Form(data=data, instance=p, user=u)
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


# ── Legacy Step 2 review form (Settings only — not express onboarding UI) ──

@pytest.mark.django_db
class TestLegacyReviewForm:
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


@pytest.mark.django_db
class TestExpressOnboardingHelpers:
    def test_record_intent(self):
        u = User.objects.create_user(username="intent", email="i@b.com", password="P1!")
        p = u.profile
        record_intent(p, "sell")
        assert (p.onboarding_step_timestamps or {}).get("intent_sell")

    def test_ensure_brand_defaults_fills_voice(self):
        u = User.objects.create_user(username="defs", email="d@b.com", password="P1!")
        p = u.profile
        p.company_name = "Kawaida Shop"
        p.industry = "ecommerce"
        p.save(update_fields=["company_name", "industry"])

        ensure_brand_defaults(p, u)

        p.refresh_from_db()
        assert (p.brand_voice or "").strip()
        assert p.goals
        assert p.default_cta_type == "whatsapp"

    def test_build_brand_preview(self):
        u = User.objects.create_user(
            username="prev", email="p@b.com", password="P1!", full_name="Pat",
        )
        p = u.profile
        p.company_name = "Pat's Boutique"
        p.industry = "fashion_beauty"
        p.brand_voice = "Warm and stylish."
        p.tone_attributes = ["approachable", "confident"]
        p.content_pillars = ["New arrivals", "Style tips"]
        p.save()

        preview = build_brand_preview(p, u)
        assert preview["company_name"] == "Pat's Boutique"
        assert preview["is_commerce"] is True
        assert preview["tones"]

    def test_setup_mission_includes_commerce_items(self):
        u = User.objects.create_user(username="miss", email="m@b.com", password="P1!")
        p = u.profile
        p.industry = "ecommerce"
        p.company_name = "Shop"
        p.save(update_fields=["industry", "company_name"])
        u.onboarding_completed = True
        u.save(update_fields=["onboarding_completed"])

        mission = build_setup_mission(u, stats={
            "has_platform": False,
            "has_published": False,
            "has_scheduled": False,
            "created_week": 0,
            "product_tasks_week": 0,
        })
        keys = {item["key"] for item in mission["items"]}
        assert "snap" in keys
        assert "shop" in keys


@pytest.mark.django_db
class TestWhatsappOnboardingPing:
    def test_template_includes_name_and_url(self, monkeypatch, settings):
        settings.KOVA_ONBOARDING_TEMPLATE_NAME = "kova_onboarding_ready"
        settings.WHATSAPP_PHONE_NUMBER_ID = "123"
        settings.WHATSAPP_ACCESS_TOKEN = "token"
        settings.SITE_URL = "https://app.kovaagent.com"

        u = User.objects.create_user(
            username="wa", email="wa@b.com", password="P1!",
            full_name="Jane Doe", phone_number="0712345678",
        )

        captured = {}

        class FakeProvider:
            def send_template_message(self, **kwargs):
                captured.update(kwargs)
                return {"success": True}

        monkeypatch.setattr(
            "apps.platforms.providers.whatsapp.WhatsAppProvider",
            FakeProvider,
        )

        from apps.agents.onboarding_tasks import _send_completion_whatsapp_ping

        assert _send_completion_whatsapp_ping(u) is True
        params = captured["components"][0]["parameters"]
        assert params[0]["text"] == "Jane"
        assert params[1]["text"] == "https://app.kovaagent.com/brief/"

    def test_whatsapp_url_for_commerce_user(self, monkeypatch, settings):
        settings.KOVA_ONBOARDING_TEMPLATE_NAME = "kova_onboarding_ready"
        settings.WHATSAPP_PHONE_NUMBER_ID = "123"
        settings.WHATSAPP_ACCESS_TOKEN = "token"
        settings.SITE_URL = "https://app.kovaagent.com"

        u = User.objects.create_user(
            username="wacom", email="wacom@b.com", password="P1!",
            full_name="Jane Doe", phone_number="0712345678",
        )
        u.profile.industry = "ecommerce"
        u.profile.save()

        captured = {}

        class FakeProvider:
            def send_template_message(self, **kwargs):
                captured.update(kwargs)
                return {"success": True}

        monkeypatch.setattr(
            "apps.platforms.providers.whatsapp.WhatsAppProvider",
            FakeProvider,
        )

        from apps.agents.onboarding_tasks import _send_completion_whatsapp_ping

        assert _send_completion_whatsapp_ping(u) is True
        assert captured["components"][0]["parameters"][1]["text"] == "https://app.kovaagent.com/products/snap/"


@pytest.mark.django_db
class TestExpressOnboardingViews:
    def _login_client(self, client, user):
        client.force_login(user)
        return client

    def _user_with_phone(self, username="route", email="route@b.com"):
        u = User.objects.create_user(username=username, email=email, password="P1!")
        u.phone_number = "0712345678"
        u.save(update_fields=["phone_number"])
        return u

    def test_choose_path_records_intent_and_routes_sell(self, client):
        u = self._user_with_phone(username="route", email="r@b.com")
        self._login_client(client, u)
        resp = client.post(
            "/accounts/onboarding/start/",
            {"intent": "sell"},
            follow=False,
        )
        assert resp.status_code == 302
        assert "step=1" in resp.url
        assert "via=sell" in resp.url
        u.refresh_from_db()
        assert (u.profile.onboarding_step_timestamps or {}).get("intent_sell")

    def test_choose_path_routes_social_links_to_magic_connect(self, client):
        u = self._user_with_phone(username="socialroute", email="social@b.com")
        self._login_client(client, u)
        resp = client.post(
            "/accounts/onboarding/start/",
            {"intent": "grow", "link": "https://instagram.com/kovaagent"},
            follow=False,
        )
        assert resp.status_code == 302
        assert resp.url == "/accounts/onboarding/magic/"

    def test_infer_from_url_endpoint_is_accessible_during_onboarding(self, client):
        u = self._user_with_phone(username="inferapi", email="infer@b.com")
        self._login_client(client, u)
        resp = client.post("/accounts/api/infer-from-url/", {"url": ""}, follow=False)
        assert resp.status_code == 400
        assert resp.json()["error"] == "Paste a URL first."

    def test_infer_from_url_returns_social_profile_hint(self, client):
        u = self._user_with_phone(username="socialhint", email="hint@b.com")
        self._login_client(client, u)
        resp = client.post(
            "/accounts/api/infer-from-url/",
            {"url": "https://linkedin.com/in/kovaagent"},
            follow=False,
        )
        assert resp.status_code == 400
        payload = resp.json()
        assert payload["error_type"] == "social_profile"
        assert payload["redirect_url"] == "/accounts/onboarding/magic/"

    def test_express_wizard_confirm_finishes_onboarding(self, client, monkeypatch):
        u = User.objects.create_user(username="wiz", email="w@b.com", password="P1!")
        u.phone_number = "0712345678"
        u.onboarding_completed = False
        u.save()
        p = u.profile
        p.company_name = "Test Shop"
        p.industry = "ecommerce"
        p.save()

        monkeypatch.setattr(
            "apps.emails.tasks.send_welcome_email.delay",
            lambda pk: None,
        )
        monkeypatch.setattr(
            "apps.emails.automation.bootstrap_email_automation",
            lambda user: None,
        )
        monkeypatch.setattr("apps.utils.fire_task", lambda task, pk: None)

        self._login_client(client, u)
        resp = client.post("/accounts/onboarding/?step=2", follow=False)
        assert resp.status_code == 302
        assert "onboarding/complete" in resp.url

        u.refresh_from_db()
        assert u.onboarding_completed is True
        assert (u.profile.onboarding_step_timestamps or {}).get("step_2_completed")

    def test_step2_requires_step1_basics(self, client):
        u = User.objects.create_user(username="gate", email="g@b.com", password="P1!")
        u.phone_number = "0712345678"
        u.save()
        self._login_client(client, u)
        resp = client.get("/accounts/onboarding/?step=2", follow=False)
        assert resp.status_code == 302
        assert "step=1" in resp.url


@pytest.mark.django_db
class TestSignupPhoneRequired:
    def test_kova_signup_form_requires_phone(self):
        form = KovaSignupForm(data={
            "email": "new@b.com",
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
            "phone_number": "",
        })
        assert not form.is_valid()
        assert "phone_number" in form.errors

    def test_kova_signup_form_saves_phone(self):
        u = User.objects.create_user(username="sig", email="sig@b.com", password="P1!")
        form = KovaSignupForm(data={
            "email": "sig@b.com",
            "password1": "Str0ngPass!",
            "password2": "Str0ngPass!",
            "phone_number": "0712345678",
        })
        assert form.is_valid(), form.errors
        form.signup(None, u)
        u.refresh_from_db()
        assert u.phone_number == "0712345678"

    def test_collect_phone_view(self, client):
        u = User.objects.create_user(username="oauth", email="oauth@b.com", password="P1!")
        client.force_login(u)
        resp = client.post(
            "/accounts/onboarding/phone/",
            {"phone_number": "0711223344"},
            follow=False,
        )
        assert resp.status_code == 302
        u.refresh_from_db()
        assert u.phone_number == "0711223344"
