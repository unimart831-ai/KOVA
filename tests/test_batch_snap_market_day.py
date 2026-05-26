"""Tests for Batch Snap Market Day Mode intelligence."""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse

from apps.products.batch_snap_intelligence import (
    build_batch_identification_prompt,
    is_batch_placeholder_name,
    parse_stall_brief,
    resolve_batch_item_price,
    _heuristic_stall_parse,
)


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
