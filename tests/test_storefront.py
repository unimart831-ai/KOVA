"""Tests for storefront resolver and shop content helpers."""

import pytest
from django.urls import reverse

from apps.accounts.models import UserProfile
from apps.products.models import Product, ProductCategory
from apps.products.storefront import (
    about_blurb,
    catalog_section_label,
    featured_products,
    hero_carousel_slides,
    hero_promo_products,
    products_by_category,
    resolve_archetype,
    resolve_hero_layout,
    resolve_hero_mode,
    resolve_storefront,
    resolve_vibe,
    shop_faq_items,
    shop_footer_data,
    split_marketplace_hero_promos,
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

    def test_hero_carousel_slides_prefers_reels(self, user):
        product = Product.objects.create(
            user=user, name="Reel Item", commerce_slug="reel-item", price=500,
        )
        reels = [{
            "commerce_slug": "reel-item",
            "video_url": "https://cdn.example.com/reel.mp4",
            "product_name": "Reel Item",
            "product_price": "KSh 500",
        }]
        slides = hero_carousel_slides(reels, [product], brand_name="Shop")
        assert slides[0]["kind"] == "reel"
        assert len(slides) == 1

    def test_hero_promo_products_backfills_catalog(self, user):
        products = [
            Product.objects.create(user=user, name=f"Item {i}", commerce_slug=f"item-{i}")
            for i in range(4)
        ]
        promos = hero_promo_products(products, limit=4)
        assert len(promos) == 4

    def test_resolve_hero_layout_spotlight_for_small_shop(self, user):
        products = [Product.objects.create(user=user, name="Solo", commerce_slug="solo")]
        promos = hero_promo_products(products)
        slides = hero_carousel_slides([], products, brand_name="Shop")
        assert resolve_hero_layout(products, promos, slides) == "spotlight"

    def test_split_marketplace_hero_promos_skips_carousel_slugs(self, user):
        p1 = Product.objects.create(user=user, name="A", commerce_slug="a")
        p2 = Product.objects.create(user=user, name="B", commerce_slug="b")
        p3 = Product.objects.create(user=user, name="C", commerce_slug="c")
        slides = [{"kind": "product", "commerce_slug": "a"}]
        left, right = split_marketplace_hero_promos([p1, p2, p3], slides, per_side=1)
        assert p1 not in left and p1 not in right
        assert left == [p2]
        assert right == [p3]

    def test_catalog_section_label_single_all_offers(self, user):
        groups = [{"name": "All offers", "products": []}]
        assert catalog_section_label(groups) == "Products"

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

    def test_products_by_category_all_uncategorized(self, user):
        p1 = Product.objects.create(user=user, name="Alpha", commerce_slug="alpha")
        p2 = Product.objects.create(user=user, name="Beta", commerce_slug="beta")
        groups = products_by_category([p1, p2])
        assert len(groups) == 1
        assert groups[0]["name"] == "All offers"
        assert len(groups[0]["products"]) == 2

    def test_shop_index_renders_uncategorized_products_only(self, client, user):
        user.profile.page_slug = "uncategorized-shop"
        user.profile.company_name = "Uncategorized Shop"
        user.profile.save()
        Product.objects.create(
            user=user,
            name="Solo Item",
            price=900,
            commerce_slug="solo-item",
            stock_status=Product.StockStatus.IN_STOCK,
        )
        response = client.get(
            reverse("public_shop", kwargs={"page_slug": "uncategorized-shop"}),
        )
        assert response.status_code == 200
        assert b"All offers" in response.content
        assert b"Solo Item" in response.content
