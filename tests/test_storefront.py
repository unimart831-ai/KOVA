"""Tests for storefront resolver and shop content helpers."""

import pytest

from apps.accounts.models import UserProfile
from apps.products.models import Product, ProductCategory
from apps.products.storefront import (
    about_blurb,
    featured_products,
    products_by_category,
    resolve_archetype,
    resolve_hero_mode,
    resolve_storefront,
    resolve_vibe,
    shop_faq_items,
    shop_footer_data,
)


@pytest.mark.django_db
class TestStorefrontResolver:
    def test_industry_maps_to_archetype(self, user):
        user.profile.industry = UserProfile.Industry.FASHION_BEAUTY
        assert resolve_archetype(user.profile) == "boutique"

        user.profile.industry = UserProfile.Industry.WHOLESALE_RETAIL
        assert resolve_archetype(user.profile) == "market_stall"

        user.profile.industry = UserProfile.Industry.SAAS
        assert resolve_archetype(user.profile) == "modern_dark"

    def test_vibe_defaults_from_industry(self, user):
        user.profile.industry = UserProfile.Industry.CREATOR
        user.profile.storefront_vibe = ""
        assert resolve_vibe(user.profile) == "reels_first"

        user.profile.industry = UserProfile.Industry.ECOMMERCE
        assert resolve_vibe(user.profile) == "minimal_catalog"

    def test_vibe_override(self, user):
        user.profile.industry = UserProfile.Industry.ECOMMERCE
        user.profile.storefront_vibe = UserProfile.StorefrontVibe.MAGAZINE
        assert resolve_vibe(user.profile) == "magazine"

    def test_hero_mode_reels_when_reels_present(self, user):
        user.profile.industry = UserProfile.Industry.CREATOR
        products = [
            Product(user=user, name="A", commerce_slug="a"),
            Product(user=user, name="B", commerce_slug="b"),
        ]
        reels = [{"video_url": "https://cdn.example.com/1.mp4"}]
        assert resolve_hero_mode(user.profile, products, reels) == "reels"

    def test_hero_mode_featured_carousel(self, user):
        user.profile.industry = UserProfile.Industry.FASHION_BEAUTY
        products = [
            Product(user=user, name="A", is_featured=True),
            Product(user=user, name="B", is_featured=True),
        ]
        assert resolve_hero_mode(user.profile, products, []) == "featured_carousel"

    def test_resolve_storefront_shape(self, user):
        user.profile.industry = UserProfile.Industry.FOOD_RESTAURANT
        user.profile.brand_colors = ["#FF5733", "#1A1A2E"]
        user.profile.visual_style = "photography"
        products = [Product(user=user, name="Item", commerce_slug="item")]
        storefront = resolve_storefront(user.profile, user, products, [])

        assert storefront["archetype"] == "market_stall"
        assert storefront["vibe"] == "classic_shop"
        assert storefront["hero_mode"] in {"compact", "brand_story", "featured_carousel", "reels"}
        assert storefront["theme_tokens"]["primary"] == "#FF5733"
        assert storefront["theme_tokens"]["surface"] == "light"
        assert storefront["powered_by_kova"] is True
        assert isinstance(storefront["section_order"], list)
        assert "heading" in storefront["font_pair"]


@pytest.mark.django_db
class TestStorefrontHelpers:
    def test_about_blurb_from_brand_voice(self, user):
        user.profile.brand_voice = "We bake fresh daily. Our cakes use local ingredients. Visit us in Westlands."
        assert "We bake fresh daily." in about_blurb(user.profile)
        assert "local ingredients" in about_blurb(user.profile)

    def test_about_blurb_from_key_offerings(self, user):
        user.profile.brand_voice = ""
        user.profile.key_offerings = ["Custom cakes", "Catering"]
        blurb = about_blurb(user.profile)
        assert "Custom cakes" in blurb

    def test_shop_faq_items(self, user):
        user.profile.wa_faq_answers = [
            {"keywords": ["hours", "open"], "reply": "Mon–Sat 9am–6pm"},
            {"keywords": ["delivery"], "reply": "Same-day in Nairobi"},
        ]
        items = shop_faq_items(user.profile)
        assert len(items) == 2
        assert items[0]["answer"] == "Mon–Sat 9am–6pm"

    def test_shop_footer_data(self, user):
        user.profile.shop_footer = {
            "hours": "9am–5pm",
            "delivery_note": "Free pickup",
            "policy_url": "https://example.com/policy",
        }
        footer = shop_footer_data(user.profile)
        assert footer["hours"] == "9am–5pm"
        assert footer["policy_url"].startswith("https://")

    def test_featured_products_prefers_featured(self, user):
        featured = Product.objects.create(
            user=user, name="Star", is_featured=True, commerce_slug="star",
        )
        Product.objects.create(user=user, name="Regular", commerce_slug="regular")
        all_products = list(Product.objects.filter(user=user))
        result = featured_products(all_products)
        assert result[0].pk == featured.pk

    def test_products_by_category(self, user):
        cat = ProductCategory.objects.create(user=user, name="Skincare")
        p1 = Product.objects.create(
            user=user, name="Lotion", category=cat, commerce_slug="lotion",
        )
        p2 = Product.objects.create(user=user, name="Other", commerce_slug="other")
        groups = products_by_category([p1, p2])
        assert len(groups) == 2
        assert groups[0]["name"] == "Skincare"
        assert groups[0]["products"][0].pk == p1.pk
