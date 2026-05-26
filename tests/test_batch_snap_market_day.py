"""Tests for Batch Snap Market Day Mode intelligence."""

import pytest

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
