"""Tests for Batch Snap Market Day Mode intelligence."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.products.batch_snap_intelligence import (
    build_batch_identification_prompt,
    build_market_day_composition_prompt,
    build_stall_brand_lock,
    is_batch_placeholder_name,
    is_market_day_mode,
    parse_stall_brief,
    photoroom_template_from_stall_lock,
    resolve_batch_item_price,
    _heuristic_stall_parse,
    _heuristic_brand_from_text,
)


class TestMarketDayMode:
    def test_is_market_day_batch_snap(self):
        assert is_market_day_mode("batch_snap") is True
        assert is_market_day_mode("snap") is False
        assert is_market_day_mode(None) is False

    def test_composition_prompt_uses_stall_context(self):
        prompt = build_market_day_composition_prompt(
            {"stall_title": "Amara's Table", "market_context": "Kawaida market Saturday"},
        )
        assert "Amara's Table" in prompt
        assert "Kawaida market" in prompt


class TestStallBriefParsing:
    def test_heuristic_extracts_price(self):
        base = {
            "stall_title": "",
            "pricing_rules": {"default_price": None, "default_currency": "KES", "apply_default_to_blanks": True},
        }
        result = _heuristic_stall_parse("Everything 800 bob at Kawaida market", base, default_price=None, default_currency="KES")
        assert result["pricing_rules"]["default_price"] == 800.0
        assert result["language_mix"] == "mixed"

    def test_parse_stall_brief_fallback_without_llm(self, settings):
        settings.OPENAI_API_KEY = ""
        settings.GROQ_API_KEY = ""
        result = parse_stall_brief(
            transcript="All dresses 1200 shillings today",
            stall_title="Amara's table",
            default_currency="KES",
            item_count=5,
        )
        assert result["stall_title"] == "Amara's table"
        assert result["pricing_rules"]["default_price"] == 1200.0


class TestBatchNaming:
    def test_placeholder_detection(self):
        assert is_batch_placeholder_name("") is True
        assert is_batch_placeholder_name("Listing 3") is True
        assert is_batch_placeholder_name("Nike Air Max 90") is False


class TestBatchVisionPrompt:
    def test_prompt_includes_stall_context(self):
        prompt = build_batch_identification_prompt(
            offering_type="product",
            name="Listing 1",
            display_price="KES 800",
            photo_context="",
            stall_context={
                "stall_title": "Sunday Drop",
                "market_context": "Kawaida market",
                "pricing_rules": {"default_price": 800, "default_currency": "KES"},
                "campaign_tone": "energetic_market_day",
            },
            batch_index=0,
            batch_total=3,
            sibling_names=["Blue dress"],
            needs_name=True,
        )
        assert "Sunday Drop" in prompt
        assert "Kawaida market" in prompt
        assert "Blue dress" in prompt
        assert "product_name" in prompt


@pytest.mark.django_db
class TestBatchPriceResolution:
    def test_voice_default_applied(self, user):
        from apps.products.models import Product

        product = Product.objects.create(
            user=user,
            name="Listing 1",
            price=None,
            currency="KES",
        )
        price, source = resolve_batch_item_price(
            product=product,
            analysis={"detected_price": None},
            stall_context={"pricing_rules": {"default_price": 850, "default_currency": "KES", "apply_default_to_blanks": True}},
            form_price="",
        )
        assert price == 850
        assert source == "voice_default_price"

    def test_tag_price_wins(self, user):
        from apps.products.models import Product

        product = Product.objects.create(user=user, name="Item", price=None, currency="KES")
        price, source = resolve_batch_item_price(
            product=product,
            analysis={"detected_price": 999},
            stall_context={"pricing_rules": {"default_price": 500}},
            form_price="",
        )
        assert price == 999
        assert source == "tag"


@pytest.mark.django_db
class TestBatchSnapLaunchView:
    def test_launch_creates_session_and_products(self, client, user, monkeypatch):
        from apps.products.models import BatchSnapSession, Product

        user.onboarding_completed = True
        user.phone_number = "0712345678"
        user.save(update_fields=["onboarding_completed", "phone_number"])
        client.force_login(user)

        calls = []

        def fake_fire_task(*args):
            calls.append(args)

        monkeypatch.setattr("apps.utils.fire_task", fake_fire_task)

        photo = SimpleUploadedFile(
            "dress.jpg",
            (
                b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00"
                b"\xff\xdb\x00C\x00" + b"\x08" * 64 +
                b"\xff\xc0\x00\x11\x08\x00\x01\x00\x01\x03\x01\x11\x00\x02\x11\x01\x03\x11\x01"
                b"\xff\xda\x00\x08\x01\x01\x00\x00?\x00\xd2\xcf \xff\xd9"
            ),
            content_type="image/jpeg",
        )

        resp = client.post(
            reverse("products:snap_batch_launch"),
            {
                "stall_title": "Sunday Drop",
                "default_price": "800",
                "default_currency": "KES",
                "offering_type": "product",
                "name_0": "",
                "price_0": "",
                "currency_0": "KES",
                "context_0": "",
                "photos": [photo],
            },
            follow=False,
        )

        assert resp.status_code == 302
        assert resp["Location"].startswith(reverse("products:list") + "?batch=")
        assert BatchSnapSession.objects.filter(user=user, stall_title="Sunday Drop").count() == 1
        product = Product.objects.get(user=user, batch_index=0)
        assert product.name == "Listing 1"
        assert product.batch_snap_session is not None
        assert len(calls) == 1


class TestStallBrandLock:
    def test_heuristic_brand_extracts_coral(self):
        base = {"campaign_tone": "energetic_market_day"}
        out = _heuristic_brand_from_text("Coral table at Kawaida market", base)
        assert out["brand_colors"]["primary"] == "FF6B5B"
        assert "surface_vibe" in out

    def test_build_stall_brand_lock_stable_seed(self, user):
        profile = user.profile
        stall_context = {
            "stall_title": "Amara's Table",
            "stall_tagline": "Fresh today",
            "campaign_tone": "premium_boutique",
            "brand_colors": {"primary": "FF5733", "secondary": "1A1A1A"},
            "surface_vibe": "warm boutique marble",
            "scene_pack": "brand_studio",
        }
        lock_a = build_stall_brand_lock(
            stall_context, profile=profile, user_id=user.pk, session_id="sess-abc",
        )
        lock_b = build_stall_brand_lock(
            stall_context, profile=profile, user_id=user.pk, session_id="sess-abc",
        )
        assert lock_a["ai_background_seed"] == lock_b["ai_background_seed"]
        assert lock_a["studio_color_hex"] == "FF5733"
        assert lock_a["scene_pack"] == "brand_studio"
        assert lock_a["enabled"] is True

    def test_photoroom_template_from_stall_lock(self):
        lock = {
            "enabled": True,
            "shadow_mode": "ai.soft",
            "padding": "0.08",
            "ai_background_seed": 117879368,
            "outline_color_hex": "000000",
            "studio_color_hex": "FFF8F0",
            "style_suffix": "Market day stall",
            "source": "stall_brief",
        }
        template = photoroom_template_from_stall_lock(lock)
        assert template is not None
        assert template.enabled is True
        assert template.ai_background_seed == 117879368


@pytest.mark.django_db
class TestBatchPipelineGalleryPayload:
    def test_batch_status_exposes_gallery_scenes(self, user):
        from apps.products.batch_snap_pipeline import build_batch_snap_pipeline_status
        from apps.products.models import BatchSnapSession, Product
        from django.utils import timezone
        from apps.agents.models import AgentAction

        session = BatchSnapSession.objects.create(
            user=user,
            stall_title="Test Stall",
            stall_context={
                "brand_lock": {
                    "enabled": True,
                    "surface_vibe": "clean studio",
                    "scene_pack": "brand_studio",
                },
            },
        )
        pid = "77777777-7777-7777-7777-777777777777"
        url = f"/media/studio_polish/{pid}/studio_white_abc.jpg"
        product = Product.objects.create(
            id=pid,
            user=user,
            name="Batch Item",
            batch_snap_session=session,
            batch_index=0,
            additional_images=[url],
        )
        product.image = "product_images/orig.jpg"
        product.save()

        AgentAction.objects.create(
            user=user,
            agent_type="create",
            action_type="snap.vision_batch",
            description="vision",
            status=AgentAction.ActionStatus.COMPLETED,
            input_data={"product_id": str(product.pk), "session_id": str(session.pk)},
            output_data={},
            completed_at=timezone.now(),
        )
        AgentAction.objects.create(
            user=user,
            agent_type="create",
            action_type="commerce.studio_polish",
            description="polish",
            status=AgentAction.ActionStatus.COMPLETED,
            input_data={"product_id": str(product.pk)},
            output_data={
                "variant": "studio_white",
                "label": "Studio White",
                "url": url,
                "phase": "scene",
                "slide_role": "hero",
            },
            completed_at=timezone.now(),
        )

        data = build_batch_snap_pipeline_status(
            [str(product.pk)], user, session_id=str(session.pk),
        )
        assert data["brand_lock"]["surface_vibe"] == "clean studio"
        item = data["items"][0]
        assert item["hero_picker_ready"] is True
        assert len(item["gallery_scenes"]) >= 1
        assert any(s["url"] == url for s in item["gallery_scenes"])
